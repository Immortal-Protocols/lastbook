"""Hard-coded UI chrome should not regress: every user-visible string is catalogued."""
import ast
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'packaging'))
import i18n_scan as scan  # noqa: E402


def duplicate_test_methods(source, relative_path):
    tree = ast.parse(source, filename=relative_path)
    duplicates = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        methods = {}
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name.startswith('test_'):
                methods.setdefault(child.name, []).append(child.lineno)
        duplicates.extend(
            f'{relative_path}:{node.name}.{name} ({len(lines)} definitions at lines {", ".join(map(str, lines))})'
            for name, lines in methods.items() if len(lines) > 1
        )
    return duplicates


class Coverage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        english, _ = scan.load_english()
        cls.english = english
        cls.hits = scan.scan_web() + scan.scan_topics() + scan.scan_python() + scan.scan_c()
        cls.chrome = scan.unique_chrome(cls.hits)
        cls.totals = scan.summarize(cls.hits)[1]


    def scan_web_source(self, source):
            with tempfile.TemporaryDirectory(prefix='i18n-scan-web-') as temporary:
                web = Path(temporary)
                (web / 'audit.js').write_text(source, encoding='utf-8')
                with patch.object(scan, 'WEB', web), patch.object(scan, 'WEB_FILES', ['audit.js']):
                    return scan.scan_web()

    def test_scanner_detects_leading_space_ui_fragments(self):
            sample = '''function recommendLine() {
              const what = `${esc(p.title)}${r.ai && aiFits() ? ' with the local AI' : ''}`;
              return `<p class="s-rec">Suggested: ${what}</p>`;
            }'''
            hits = self.scan_web_source(sample)
            fragment = [hit for hit in hits if hit['text'] == ' with the local AI']
            self.assertEqual(len(fragment), 1, hits)
            self.assertEqual(fragment[0]['class'], 'chrome')

            self.assertEqual(scan.classify(' --lan', 'const command = '), 'technical')

    def test_scanner_detects_prose_exported_to_markdown(self):
            sample = '''function exportChat(c) {
              const md = `Exported chat notes from the offline library. Check each linked page before acting.`;
              new Blob([md], { type: 'text/markdown' });
            }'''
            hits = self.scan_web_source(sample)
            exported = [hit for hit in hits if hit['text'] == 'Exported chat notes from the offline library. Check each linked page before acting.']
            self.assertEqual(len(exported), 1, hits)
            self.assertEqual(exported[0]['class'], 'chrome')

    def test_scanner_detects_short_rendered_button_labels(self):
            sample = '''root.innerHTML = `${canAdd ? `<button>Add</button>` : ''}`;'''
            hits = self.scan_web_source(sample)
            add = [hit for hit in hits if hit['text'] == 'Add']
            self.assertEqual(len(add), 1, hits)
            self.assertEqual(add[0]['class'], 'chrome')
            self.assertEqual(scan.classify('Add', 'const action = '), 'technical')
            self.assertEqual(scan.classify('OK', "statusLine('"), 'chrome')

    def test_scanner_recognizes_chat_tr_keyed_fallbacks(self):
            sample = '''
              const known = chatTr('chat.exportTitle', { title }, 'Chat: {title}');
              const missing = chatTr('audit.missingKey', null, 'A new visible label');
            '''
            hits = self.scan_web_source(sample)
            known = [hit for hit in hits if hit['text'] == 'Chat: {title}']
            missing = [hit for hit in hits if hit['text'] == 'A new visible label']
            self.assertEqual(len(known), 1, hits)
            self.assertEqual(known[0]['class'], 'wired')
            self.assertEqual(len(missing), 1, hits)
            self.assertEqual(missing[0]['class'], 'chrome')

    def test_scanner_recognizes_other_keyed_message_helpers(self):
            sample = '''
              setError(message, 'chat.stoppedUnexpectedly', null, 'The answer stopped unexpectedly.');
              trMarkup('setup.error', null, 'Setup could not start.');
            '''
            hits = self.scan_web_source(sample)
            by_text = {hit['text']: hit['class'] for hit in hits}
            self.assertEqual(by_text['The answer stopped unexpectedly.'], 'wired')
            self.assertEqual(by_text['Setup could not start.'], 'wired')

    def test_scanner_preserves_urls_regex_templates_attributes_and_python_concatenation(self):
            js = "statusLine('Open https://example.org/help now');"
            url = next((text, pre) for _pos, text, pre in scan.iter_js_strings(js) if 'https://' in text)
            self.assertEqual(scan.classify(*url), 'chrome')

            nested = 'const x = "}"; root.innerHTML = `${/}/.test(x) ? `<button>Keep going</button>` : ""}`;'
            hits = [(text, pre) for _pos, text, pre in scan.iter_js_strings(nested)]
            pre = next((pre for text, pre in hits if text == 'Keep going'), None)
            self.assertIsNotNone(pre, hits)
            self.assertEqual(scan.classify('Keep going', pre), 'chrome')

            parser = scan._MarkupStrings('web/chat.js')
            parser.feed('<a title="Source {…}">{…}</a>')
            parser.close()
            source = next(((text, pre) for text, pre in parser.strings if text.startswith('Source ')), None)
            self.assertIsNotNone(source, parser.strings)
            self.assertEqual(scan.classify(*source), 'chrome')

            joined = next((text, pre, body) for _pos, text, pre, body in scan.iter_py_strings('label("Open " "folder")')
                          if text == 'Open folder')
            self.assertEqual(scan.classify(joined[0], joined[1], joined[2]), 'chrome')

    def test_python_test_method_names_are_unique_and_duplicate_fixtures_are_detected(self):
            fixture = '''class Duplicate(unittest.TestCase):
        def test_same(self): pass
        def test_same(self): pass
    '''
            self.assertEqual(duplicate_test_methods(fixture, 'fixture.py'), [
                'fixture.py:Duplicate.test_same (2 definitions at lines 2, 3)'])
            duplicates = []
            for path in sorted((ROOT / 'app' / 'tests').rglob('*.py')):
                duplicates.extend(duplicate_test_methods(
                    path.read_text(encoding='utf-8'), str(path.relative_to(ROOT))))
            self.assertEqual(duplicates, [], 'duplicate unittest methods: ' + '; '.join(duplicates))

    def test_bundled_manifest_summary_has_catalogue_key(self):
        source = (ROOT / 'packaging' / 'release_manifest.py').read_text(encoding='utf-8')
        self.assertIn("SMALL_SUMMARY_KEY = 'setup.packSummary.small'", source)
        self.assertIn("'summary_key': SMALL_SUMMARY_KEY", source)
        self.assertIn("MEDIUM_SUMMARY_KEY = 'setup.packSummary.medium'", source)
        self.assertIn('SUMMARY_KEYS = {', source)
        self.assertIn("pack.setdefault('summary_key', key)", source)
        self.assertIn('setup.packSummary.small', self.english)
        self.assertIn('setup.packSummary.medium', self.english)


    def test_catalogues_are_paired(self):
        self.assertGreaterEqual(len(self.english), 1000)

    def test_every_web_runtime_file_is_scanned_or_declared_non_ui(self):
        actual = {path.name for path in (ROOT / 'web').glob('*.js')} | {'index.html', 'setup.html'}
        inventoried = set(scan.WEB_FILES) | scan.WEB_NON_UI_FILES
        self.assertEqual(actual, inventoried,
                         f'unclassified web files: {sorted(actual - inventoried)}; stale entries: {sorted(inventoried - actual)}')

    def test_cli_scanner_includes_dynamic_topic_data(self):
        source = (ROOT / 'packaging' / 'i18n_scan.py').read_text(encoding='utf-8')
        self.assertIn('hits = scan_web() + scan_topics() + scan_python() + scan_c()', source)

    def test_literal_catalogue_references_exist(self):
        # Catch key typos and stale references across every scanned runtime,
        # not only JS tr() calls. setup.html/setup.json are asset filenames.
        keys = set(self.english)
        sources = [scan.WEB / name for name in scan.WEB_FILES]
        sources.extend(path for paths in scan.PYTHON_SURFACES.values() for path in paths)
        sources.append(ROOT / 'packaging' / 'release_manifest.py')
        referenced = set()
        for path in sources:
            if path.is_file():
                referenced.update(re.findall(r"['\"]((?:about|app|chat|common|copy|desktop|error|help|installer|language|library|map|native|nav|reader|saved|search|setup|time|topic|update|video|videos|wiki)\.[A-Za-z][A-Za-z0-9_.-]*)['\"]",
                                             path.read_text(encoding='utf-8')))
        referenced.difference_update({'setup.html', 'setup.json', 'app.zip', 'map.sqlite'})
        referenced.update({
            'desktop.genericName', 'desktop.comment', 'desktop.keywords',
            'installer.stub.selfMissing', 'installer.stub.selfUnreadable', 'installer.stub.damaged',
            'installer.stub.tempMissing', 'installer.stub.tempCreate', 'installer.stub.tempWrite',
            'installer.stub.unpackFailed', 'installer.stub.startFailed',
            'native.macosPermission.desktop', 'native.macosPermission.documents', 'native.macosPermission.downloads',
        })
        referenced = {key for key in referenced if not key.endswith('.')}
        self.assertGreaterEqual(len(referenced), 800)
        self.assertEqual(referenced - keys, set(),
                         f'catalogue references without English messages: {sorted(referenced - keys)}')

    def test_no_unique_hardcoded_chrome(self):
        # Default-deny: every chrome, content or unknown literal is either wired or listed
        # with a reason in packaging/i18n_allowlist.json, and every allowlist row still matches.
        leftover = scan.unique_unapproved(self.hits)
        self.assertEqual(
            leftover, {},
            'hard-coded UI text that is neither wired nor allowlisted:\n' + '\n'.join(
                f'  {text!r}\n    {", ".join(locs)}' for text, locs in sorted(leftover.items())
            ),
        )
        self.assertEqual(scan.stale_allowlist(self.hits), [])

    def test_dynamic_chat_action_selector_is_technical(self):
        selector = '#{…} [data-act="{…}"]'
        self.assertEqual(scan.classify(selector, 'document.querySelector(', ''), 'technical')

    def test_map_view_script_parses_without_duplicate_declarations(self):
        node = shutil.which('node')
        if not node:
            self.skipTest('requires Node.js to check browser JavaScript syntax')
        result = subprocess.run([node, '--check', str(ROOT / 'web' / 'map.js')],
                                capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_scanner_classifies_command_examples_native_keys_and_attribution(self):
        self.assertEqual(scan.classify('server.py --lan', "command: ", ""), 'technical')
        self.assertEqual(scan.classify('SystemRoot', "os.environ.get(", ""), 'technical')
        self.assertEqual(scan.classify('SPUStandardUpdaterController', "objc.lookUpClass(", ""), 'technical')
        self.assertEqual(scan.classify('The battery is only shown on this computer.', "return {'error': '", "', 'error_key': 'hardware.batteryLocalOnly'}"), 'wired')
        self.assertTrue(scan.looks_technical('NotFound'))
        self.assertTrue(scan.looks_technical('WindowsPowerShell'))
        self.assertEqual(scan.classify('© OpenStreetMap contributors · Microsoft buildings · USGS · USDA · NOAA · USACE · CDFW · CalGEM · Natural Earth', 'map attribution: ', ''), 'content')

    def test_macos_navigation_labels_are_wired_through_the_key_map(self):
        if not (ROOT / 'app' / 'i18n_native.json').exists():
            self.skipTest('native menu catalog is added with native shell localization')
        hits = scan.scan_python()
        rows = [h for h in hits if h.get('file') == 'app/shell_macos.py' and h['text'] in {'Videos', 'Map', 'Chat'}]
        self.assertEqual({h['text']: h['class'] for h in rows}, {'Videos': 'wired', 'Map': 'wired', 'Chat': 'wired'})

    def test_scanner_still_classifies_surfaces(self):
        # The inventory should keep seeing the desktop surfaces even when chrome is 0.
        self.assertGreater(self.totals['wired'], 1000)
        self.assertEqual(scan.unapproved(self.hits), [])

    def test_catalogued_helper_fallbacks_are_wired_but_missing_keys_are_not(self):
        for source, literal, expected in [
            ("el.innerHTML = `${tHtml('map.clickToList', null, 'Click to list them')}`;",
             'Click to list them', 'wired'),
            ("el.innerHTML = `${keyedMessage('setup.noAnswer', null, 'Lastbook did not answer.')}`;",
             'Lastbook did not answer.', 'wired'),
            ("el.innerHTML = `${tHtml('missing.newKey', null, 'Brand new visible string')}`;",
             'Brand new visible string', 'chrome'),
        ]:
            with self.subTest(literal=literal):
                _pos, text, pre = next(item for item in scan.iter_js_strings(source) if item[1] == literal)
                self.assertEqual(scan.classify(text, pre), expected)
        self.assertEqual(scan.classify('{…} ({…})', "return `<dt>${size(value)} (${trMarkup("), 'technical')
        self.assertEqual(scan.classify('Amount {…} ({…})', 'el.innerHTML = `'), 'chrome')

    def test_scanner_does_not_hide_visible_markup_after_a_translated_expression(self):
        sample = "main.innerHTML = `<div><h1>Map</h1>${tr('map.heading', null, 'Map')}<section><h2>Nearest to the map center</h2>" + (
            '<p>Additional visible copy long enough to move the sink outside the scanner lookahead.</p>' * 18) + '</section>`;'
        hits = list(scan.iter_js_strings(sample))
        pos, text, pre = next(item for item in hits if 'Nearest to the map center' in item[1])
        end = scan._skip_template(sample, pos) if sample[pos] == '`' else scan._skip_string(sample, pos)
        post = sample[pos:min(len(sample), end + 600)]
        self.assertEqual(scan.classify(text, pre, post), 'chrome')

    def test_scanner_finds_ask_offer_text_inside_a_long_dynamic_template(self):
        sample = "el.innerHTML = `<a><b>Ask the library: “${esc(q)}”</b><small>Get a written answer with the exact pages it came from</small>" + (
            '<p>Additional visible copy long enough to move the sink outside the scanner lookahead.</p>' * 18) + '</a>`;'
        hits = list(scan.iter_js_strings(sample))
        for text in ('Ask the library: “{…}”', 'Get a written answer with the exact pages it came from'):
            with self.subTest(text=text):
                pos, found, pre = next(item for item in hits if item[1] == text)
                end = scan._skip_template(sample, pos) if sample[pos] == '`' else scan._skip_string(sample, pos)
                post = sample[pos:min(len(sample), end + 600)]
                self.assertEqual(scan.classify(found, pre, post), 'chrome')




    def test_scanner_flattens_interpolated_templates(self):
        sample = 'live.textContent = `Hello, ${name}, welcome.`;'
        found = [text for _pos, text, _pre in scan.iter_js_strings(sample)]
        self.assertTrue(any('Hello,' in text and 'welcome' in text and '{…}' in text for text in found), found)
        chrome = [text for _pos, text, pre in scan.iter_js_strings(sample)
                  if scan.classify(text, pre + sample) == 'chrome']
        self.assertTrue(chrome, 'interpolated UI templates should be classified as chrome when unwired')

        wired = 'el.innerHTML = `${tr("about.x", {n}, "{n} of 1 video has no captions")}`;'
        kinds = {scan.classify(text, pre) for _pos, text, pre in scan.iter_js_strings(wired)}
        self.assertNotIn('chrome', kinds)

    def test_scanner_finds_untranslated_text_in_nested_templates(self):
        sample = '''
          root.innerHTML = `<div>${ready ? `<button>Stop</button>` : `<button>Keep going</button>`}</div>`;
        '''
        hits = [(text, pre) for _pos, text, pre in scan.iter_js_strings(sample)]
        for literal in ('Stop', 'Keep going'):
            with self.subTest(literal=literal):
                pre = next((pre for text, pre in hits if text == literal), None)
                self.assertIsNotNone(pre, f'nested template string {literal!r} was skipped: {hits!r}')
                self.assertEqual(scan.classify(literal, pre), 'chrome')

    def test_scanner_detects_hardcoded_encyclopedia_display_data(self):
        sample = "const ZIMS = [['mdwiki', 'Medical encyclopedia', 'MDWiki: plain-language articles']];"
        hits = [(text, pre) for _pos, text, pre in scan.iter_js_strings(sample)]
        for literal in ('Medical encyclopedia', 'MDWiki: plain-language articles'):
            with self.subTest(literal=literal):
                pre = next(pre for text, pre in hits if text == literal)
                self.assertEqual(scan.classify(literal, pre), 'chrome')

    def test_scanner_keeps_visible_url_strings(self):
        js = "statusLine('Open https://example.org/help now');"
        hits = [(text, pre) for _pos, text, pre in scan.iter_js_strings(js)]
        visible = next((text, pre) for text, pre in hits if 'https://example.org/help' in text)
        self.assertEqual(scan.classify(*visible), 'chrome')

    def test_scanner_finds_python_multiline_ui(self):
        py = 'message("""This window failed.\\nTry again.""")'
        hits = list(scan.iter_py_strings(py))
        visible = next((text, pre, body) for _pos, text, pre, body in hits
                       if 'This window failed.' in text)
        self.assertEqual(scan.classify(visible[0], visible[1], visible[2]), 'chrome')

    def test_scanner_classifies_ui_arrays_and_display_helpers(self):
        sample = "const ABOUT_STARTERS = { doc: ['Explain this page in simple words'] }; statusLine('Nothing is visible yet');"
        hits = [(text, pre) for _pos, text, pre in scan.iter_js_strings(sample)]
        by_text = {text: scan.classify(text, pre) for text, pre in hits}
        self.assertEqual(by_text.get('Explain this page in simple words'), 'chrome')
        self.assertEqual(by_text.get('Nothing is visible yet'), 'chrome')

    def test_scanner_preserves_regexps_templates_and_ignores_real_python_docstrings(self):
        js = r"const urlPattern = /https?:\/\//; const shown = `Open https://${host}/help`; // discarded\n"
        visible = [text for _pos, text, _pre in scan.iter_js_strings(js)]
        self.assertTrue(any('https://' in text and 'help' in text for text in visible), visible)
        self.assertFalse(any('discarded' in text for text in visible), visible)

        nested = 'const x = "}"; root.innerHTML = `${/}/.test(x) ? `<button>Keep going</button>` : ""}`;'
        nested_hits = [(text, pre) for _pos, text, pre in scan.iter_js_strings(nested)]
        label, pre = next(((text, pre) for text, pre in nested_hits if text == 'Keep going'), (None, None))
        self.assertIsNotNone(label, f'regex brace truncated a rendered template: {nested_hits!r}')
        self.assertEqual(scan.classify(label, pre), 'chrome')

        py = 'def render():\n    """Technical implementation notes."""\n    message("""This window failed.\\nTry again.""")\n'
        literals = [text for _pos, text, _pre, _body in scan.iter_py_strings(py)]
        self.assertFalse(any('Technical implementation notes' in text for text in literals), literals)
        self.assertIn('This window failed.\nTry again.', literals)

        concat = 'label("Open " "folder")'
        joined = [text for _pos, text, _pre, _body in scan.iter_py_strings(concat)]
        self.assertIn('Open folder', joined, joined)
        visible_label = next(hit for hit in scan.iter_py_strings(concat) if hit[1] == 'Open folder')
        self.assertEqual(scan.classify(visible_label[1], visible_label[2], visible_label[3]), 'chrome')

    def test_localized_runtime_paths_stay_wired(self):
        app = (ROOT / 'web' / 'app.js').read_text(encoding='utf-8')
        chat = (ROOT / 'web' / 'chat.js').read_text(encoding='utf-8')
        map_js = (ROOT / 'web' / 'map.js').read_text(encoding='utf-8')
        self.assertIn("trLang('guide.getReady'", app)
        self.assertIn("trLang('guide.goDeeper'", app)
        self.assertIn("'chat.explainPage'", chat)
        self.assertIn("'chat.sourceType.' + key", chat)
        self.assertIn("trHtml('chat.sourcesDisagree'", chat)
        self.assertIn("trHtml('chat.state.starting'", chat)
        self.assertIn('count: n, extra:', map_js)
        self.assertNotRegex(map_js, r'layerOf\(p\.cls\)\.label')

    def test_windows_picker_actions_use_native_catalogue_keys(self):
        if not (ROOT / 'app' / 'i18n_native.json').exists():
            self.skipTest('native picker translations are added with native shell localization')
        shell = (ROOT / 'app' / 'shell_windows.py').read_text(encoding='utf-8')
        self.assertIn("native_t('native.choose', 'Choose')", shell)
        self.assertIn("native_t('native.chooseLastbookData', 'Choose the folder called LastbookData')", shell)
        self.assertNotIn("wstr)('Choose')", shell)

    def test_scanner_reads_static_html_text_and_respects_i18n_markers(self):
        parser = scan._MarkupStrings('web/index.html')
        parser.feed('<p>Opening the guide…</p><p data-i18n="app.opening">Opening the guide…</p>')
        parser.close()
        matches = [(text, pre) for text, pre in parser.strings if text == 'Opening the guide…']
        self.assertEqual(len(matches), 2)
        self.assertEqual([scan.classify(text, pre) for text, pre in matches], ['chrome', 'wired'])

    def test_scanner_inventories_bound_meta_descriptions_and_no_javascript_fallback(self):
        html = (ROOT / 'web' / 'index.html').read_text(encoding='utf-8')
        parser = scan._MarkupStrings('web/index.html')
        parser.feed(html)
        parser.close()
        description = next((text, pre) for text, pre in parser.strings
                           if text.startswith('Offline survival and rebuilding guide:'))
        no_js = next((text, pre) for text, pre in parser.strings if text == 'Lastbook needs JavaScript.')
        self.assertEqual(scan.classify(*description), 'wired')
        self.assertEqual(scan.classify(*no_js), 'technical')

    def test_scanner_flags_unmapped_map_labels_and_short_visible_copy(self):
        for variable, label, source in [
            ('LAYERS', 'New layer', "const LAYERS = [['new-layer', '"),
            ('GROUPS', 'New group', "const GROUPS = [['new-group', '"),
        ]:
            with self.subTest(variable=variable):
                self.assertEqual(scan.classify(label, source), 'chrome')
        self.assertEqual(scan.classify('Go', "button.textContent = '"), 'chrome')
        self.assertEqual(scan.classify('OK', "statusLine('"), 'chrome')
        # The LAYERS id -> map.layer.* mapping is true only in map.js, which renders it.
        self.assertEqual(scan.classify('Hospitals', "const LAYERS = [['hospital', ", '', 'web/map.js'), 'wired')
        self.assertEqual(scan.classify('Hospitals', "const LAYERS = [['hospital', ", '', 'server.py'), 'chrome')
        self.assertEqual(scan._map_data_catalogue_classes()['Berries & asparagus'], 'wired')
        self.assertEqual(scan._map_data_catalogue_classes()['Dt'], 'technical')
        self.assertEqual(set(scan._chat_starter_classes().values()), {'wired'})

    def test_scanner_rejects_dynamic_map_label_without_a_key(self):
        source = "const LAYERS = [['new-clinic', 'A newly visible clinic category', 'N', '#fff', 'clinic', 'help']];"
        labels = [text for _pos, text, _pre in scan.iter_js_strings(source)]
        self.assertIn('A newly visible clinic category', labels)
        pre = source[:source.index("'A newly visible clinic category'")]
        self.assertEqual(scan.classify('A newly visible clinic category', pre), 'chrome')
        self.assertTrue(scan.looks_technical('videos.row.{…}'))

    def test_scanner_follows_arrow_regex_before_nested_visible_template(self):
        source = "root.innerHTML = `${(() => /}/.test('}'))() ? `<button>Keep visible copy</button>` : ''}`;"
        hits = [(text, pre) for _pos, text, pre in scan.iter_js_strings(source)]
        label = next((text, pre) for text, pre in hits if text == 'Keep visible copy')
        self.assertEqual(scan.classify(*label), 'chrome')

    def test_scanner_requires_catalogue_keys_for_topic_data(self):
        hits = scan.scan_topics()
        self.assertTrue(hits)
        self.assertTrue(all(hit['class'] == 'wired' for hit in hits),
                        [hit for hit in hits if hit['class'] != 'wired'])
        import tempfile
        import json
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / 'storm.json').write_text(
                json.dumps({'id': 'storm', 'title': 'Storm', 'short': 'Storm damage'}), encoding='utf-8')
            added = scan.scan_topics(Path(tmp))
        self.assertEqual({hit['class'] for hit in added}, {'chrome'})

    def test_scanner_finds_interpolated_visible_attributes(self):
        parser = scan._MarkupStrings('web/chat.js')
        parser.feed('<a title="Source {…}">{…}</a>')
        parser.close()
        source = next(((text, pre) for text, pre in parser.strings if text.startswith('Source ')), None)
        self.assertIsNotNone(source, parser.strings)
        self.assertEqual(scan.classify(*source), 'chrome')

    def test_scanner_inventories_linux_desktop_entry_messages(self):
        hits = scan.scan_python()
        rows = [hit for hit in hits if hit.get('file') == 'packaging/linux/lastbook.desktop']
        self.assertIn('Search and read the survival library on this computer, with no internet',
                      [hit['text'] for hit in rows], rows)
        self.assertEqual({hit['class'] for hit in rows if hit['text'].startswith('Search and read')}, {'wired'})

    def test_scanner_inventories_linux_desktop_search_keywords(self):
        hits = scan.scan_python()
        rows = [hit for hit in hits if hit.get('file') == 'packaging/linux/lastbook.desktop'
                and hit['text'] == 'survival;library;offline;first aid;']
        self.assertEqual(len(rows), 1, hits)
        self.assertEqual(rows[0]['class'], 'wired')

    def test_scanner_inventories_windows_setup_stub_messages(self):
        source = 'fail(L"The installer stopped unexpectedly.");'
        literal = next(hit for hit in scan.iter_c_strings(source) if hit[1])
        self.assertEqual(scan.classify(literal[1], literal[2]), 'chrome')
        self.assertTrue(any(hit['file'] == 'packaging/setup_stub/lastbook_setup_stub.c'
                            for hit in scan.scan_c()))

    def test_nearby_log_does_not_hide_a_visible_python_message(self):
        sample = "print('diagnostic only')\nmessage('This window stopped working.')"
        hits = list(scan.iter_py_strings(sample))
        shown = next(hit for hit in hits if hit[1] == 'This window stopped working.')
        self.assertEqual(scan.classify(shown[1], shown[2], shown[3][shown[0]:shown[0] + 100]), 'chrome')
        printed = next(hit for hit in hits if hit[1] == 'diagnostic only')
        self.assertEqual(scan.classify(printed[1], printed[2], printed[3][printed[0]:printed[0] + 100]), 'technical')

    def test_scanner_does_not_let_a_translation_elsewhere_in_an_expression_hide_text(self):
        sample = '''
          root.innerHTML = `${tr('setup.title', null, 'Settings')}${done ? `<a>Add your state’s address search</a>` : ''}`;
        '''
        hits = [(text, pre) for _pos, text, pre in scan.iter_js_strings(sample)]
        pre = next((pre for text, pre in hits if text == 'Add your state’s address search'), None)
        self.assertIsNotNone(pre, f'nested visible label was skipped: {hits!r}')
        self.assertEqual(scan.classify('Add your state’s address search', pre), 'chrome')

    def test_translated_words_are_never_used_as_platform_or_css_values(self):
        app = (ROOT / 'web' / 'app.js').read_text(encoding='utf-8')
        chat = (ROOT / 'web' / 'chat.js').read_text(encoding='utf-8')
        map_js = (ROOT / 'web' / 'map.js').read_text(encoding='utf-8')
        self.assertNotIn("tr('map.noneOn'", app)
        self.assertNotIn("tr('map.noneOn'", chat)
        self.assertIn("colorSpaceConversion: 'none', premultiplyAlpha: 'none'", map_js)
        self.assertIn("style.setProperty('display', 'none'", app)
        self.assertIn("x.style.display = 'none'", chat)
        self.assertNotRegex(map_js, r"createImageBitmap\([^\n]*tr\(")
        self.assertNotRegex(app, r"style\.setProperty\(['\"]display['\"],\s*tr\(")
        self.assertNotRegex(chat, r"style\.display\s*=\s*tr\(")
        self.assertLessEqual(scan.strip_comments_js(map_js).count("tr('map.noneOn'"), 1)

    def test_model_server_keyed_api_fallbacks_are_wired(self):
        keyed = "_api_error('no_answer', 'setup.err.modelServerNoAnswer', 'Nothing answers at {where}.', where=where)"
        hits = list(scan.iter_py_strings(keyed))
        message = next(hit for hit in hits if hit[1] == 'Nothing answers at {where}.')
        self.assertEqual(scan.classify(message[1], message[2], message[3][message[0]:message[0] + 100]), 'wired')

        unkeyed = "return {'code': 'no_answer', 'error': 'Nothing answers at {where}.'}"
        hits = list(scan.iter_py_strings(unkeyed))
        message = next(hit for hit in hits if hit[1] == 'Nothing answers at {where}.')
        self.assertEqual(scan.classify(message[1], message[2], message[3][message[0]:message[0] + 100]), 'chrome')

    def test_scanner_does_not_let_adjacent_translation_hide_literal(self):
        # A translation in the preceding statement must not classify the next
        # string as wired merely because it is nearby in the source text.
        sample = 'el.textContent = tr("about.title"); el.title = "Choose";'
        _pos, _text, pre = next(item for item in scan.iter_js_strings(sample) if item[1] == 'Choose')
        self.assertFalse(scan.already_wired(pre))

    def test_native_and_installer_literals_are_detectable(self):
        # Explicit regressions for missed visible native/installer strings.
        for sample, literal in [
            ('dialog.setWindowTitle("Version {VERSION}")', 'Version {VERSION}'),
            ('NSMenuItem(title: "Choose", action: nil)', 'Choose'),
        ]:
            with self.subTest(sample=sample):
                hits = [(text, pre) for _pos, text, pre in scan.iter_js_strings(sample)]
                if not hits:  # Python surfaces use the sibling Python scanner.
                    hits = [(text, pre) for _pos, text, pre, _body in scan.iter_py_strings(sample)]
                self.assertTrue(any(text == literal and scan.classify(text, pre) == 'chrome'
                                    for text, pre in hits), hits)

    def test_recent_native_features_are_in_the_scanner_inventory(self):
        files = {path.name for paths in scan.PYTHON_SURFACES.values() for path in paths}
        self.assertIn('update_macos.py', files)
        self.assertIn('contribute.py', files)

    def test_python_comment_stripping_keeps_hashes_inside_strings(self):
        source = '# "A comment that looks like visible UI"\nlabel = "Keep # in this value"  # trailing comment\n'
        stripped = scan.strip_python_comments(source)
        self.assertNotIn('A comment that looks like visible UI', stripped)
        self.assertNotIn('trailing comment', stripped)
        self.assertIn('"Keep # in this value"', stripped)

    def test_installer_label_and_appkit_prompt_are_display_sinks(self):
        # These were the two real misses from review: generic installer labels
        # and NSOpenPanel prompts must count as UI even when not wrapped yet.
        cases = [
            ("sub = label(f'Version {VERSION}', 94, 58, 380, 20)", 'Version {VERSION}'),
            ("panel.setPrompt_('Choose')", 'Choose'),
        ]
        for sample, literal in cases:
            with self.subTest(literal=literal):
                hits = [(text, pre) for _pos, text, pre, _body in scan.iter_py_strings(sample)]
                self.assertIn(literal, [text for text, _pre in hits], hits)
                pre = next(pre for text, pre in hits if text == literal)
                self.assertEqual(scan.classify(literal, pre), 'chrome')

    def test_catalogued_installer_and_appkit_fallbacks_stay_wired(self):
        cases = [
            ("sub = label(installer_t('installer.version', 'Version {version}', version=VERSION))",
             'Version {version}'),
            ("panel.setPrompt_(native_t('native.choose', 'Choose'))", 'Choose'),
        ]
        for sample, literal in cases:
            with self.subTest(literal=literal):
                hits = [(text, pre, body) for _pos, text, pre, body in scan.iter_py_strings(sample)]
                pre, body = next((pre, body) for text, pre, body in hits if text == literal)
                pos = body.index(literal)
                post = body[pos:pos + len(literal) + 100]
                self.assertEqual(scan.classify(literal, pre, post), 'wired')

    def test_keyed_update_fallbacks_stay_wired(self):
        cases = [
            ("return {'error': 'Updates are only open on this computer.', 'error_key': 'update.localOnly'}",
             'Updates are only open on this computer.'),
            ("return {'error': f'The check stopped on an internal error ({type(e).__name__}).', 'error_key': 'update.internalError'}",
             'The check stopped on an internal error ({type(e).__name__}).'),
            ("self._set('failed', message='The download site did not answer properly.', message_key='update.serverError')",
             'The download site did not answer properly.'),
            ("_refuse_carried_back(files, new, old, f'Lastbook could not move your files ({type(e).__name__}).', key='setup.err.couldNotMoveFilesIn')",
             'Lastbook could not move your files ({type(e).__name__}).'),
        ]
        for sample, expected in cases:
            with self.subTest(expected=expected):
                hits = list(scan.iter_py_strings(sample))
                self.assertIn(expected, [text for _pos, text, _pre, _body in hits], hits)
                pos, _text, pre, body = next(hit for hit in hits if hit[1] == expected)
                self.assertEqual(scan.classify(expected, pre, body[pos:pos + 800]), 'wired')

    def test_adjacent_wired_call_does_not_hide_visible_literal(self):
        sample = 'el.textContent = tr("about.title"); dialog.setWindowTitle("Choose");'
        hits = [(text, pre) for _pos, text, pre, _body in scan.iter_py_strings(sample)]
        choose = next((pre for text, pre in hits if text == 'Choose'), None)
        self.assertIsNotNone(choose)
        self.assertFalse(scan.already_wired(choose))
        self.assertEqual(scan.classify('Choose', choose), 'chrome')

    def test_html_marker_only_wires_its_own_tag(self):
        bound = '<button aria-label="Show or hide the sidebar" data-i18n-aria-label="nav.sidebarToggle">'
        _pos, _text, pre = next(item for item in scan.iter_js_strings(bound)
                                 if item[1] == 'Show or hide the sidebar')
        self.assertEqual(scan.classify('Show or hide the sidebar', pre, bound[_pos:]), 'wired')
        adjacent = '"trailing marker"; <button title="Choose">'
        _pos, _text, pre = next(item for item in scan.iter_js_strings(adjacent) if item[1] == 'Choose')
        self.assertFalse(scan._has_i18n_marker_in_tag(pre, adjacent[_pos:]))

    def test_template_marker_does_not_hide_neighboring_markup_text(self):
        sample = 'el.innerHTML = `<h1 data-i18n="about.title">About</h1><h2>Untranslated heading</h2><button aria-label="Open">Open</button>`;'
        hits = [(text, pre) for _pos, text, pre in scan.iter_js_strings(sample)]
        by_text = {text: scan.classify(text, pre) for text, pre in hits}
        self.assertEqual(by_text.get('About'), 'wired')
        self.assertEqual(by_text.get('Untranslated heading'), 'chrome')
        self.assertEqual(by_text.get('Open'), 'chrome')

    def test_void_element_marker_does_not_hide_later_text(self):
        sample = 'el.innerHTML = `<img data-i18n-alt="image.alt" alt="A map"><p>Untranslated text</p>`;'
        hits = [(text, pre) for _pos, text, pre in scan.iter_js_strings(sample)]
        by_text = {text: scan.classify(text, pre) for text, pre in hits}
        self.assertEqual(by_text.get('A map'), 'wired')
        self.assertEqual(by_text.get('Untranslated text'), 'chrome')

    def test_error_message_sink_keeps_user_messages_visible_to_scanner(self):
        sample = "throw new Error('The server refused the question (' + status + ').')"
        hits = [(text, pre) for _pos, text, pre in scan.iter_js_strings(sample)]
        message = next((text, pre) for text, pre in hits if 'server refused' in text)
        self.assertEqual(scan.classify(*message), 'chrome')
        self.assertEqual(scan.classify('Could not access the desktop language preference', 'new Error('), 'technical')

    def test_embedded_bridge_script_is_in_the_scan_inventory(self):
        hits = [hit for hit in scan.scan_python()
                if hit['file'] == 'app/bridge.py' and 'Lastbook stays offline' in hit['text']]
        self.assertEqual(len(hits), 1, hits)
        self.assertEqual(hits[0]['class'], 'wired', hits)

    def test_quoted_markup_is_scanned_per_visible_node(self):
        sample = 'el.innerHTML = "<p data-i18n=\\"about.title\\">About</p><p>Raw text</p>";'
        hits = [(text, pre) for _pos, text, pre in scan.iter_js_strings(sample)]
        by_text = {text: scan.classify(text, pre) for text, pre in hits}
        self.assertEqual(by_text.get('About'), 'wired')
        self.assertEqual(by_text.get('Raw text'), 'chrome')

    def test_translation_fallback_inside_open_tr_call_is_wired(self):
        sample = "return tr('chat.step.readPage', {title, pages}, 'Read {title}, page {pages}');"
        _pos, text, pre = next(item for item in scan.iter_js_strings(sample)
                               if item[1] == 'Read {title}, page {pages}')
        self.assertEqual(scan.classify(text, pre), 'wired')

    def test_webkit_feature_switch_names_are_technical(self):
        for name in ('PeerConnectionEnabled', 'LinkPreconnect', 'WebTransportEnabled'):
            with self.subTest(name=name):
                self.assertEqual(scan.classify(name, ''), 'technical')

    def test_linux_navigation_values_are_wired_via_native_key_map(self):
        source = "GO = [('Videos', '#/videos'), ('Map', '#/map'), ('Chat', '#/ask')]\ngo_names = {'Videos': 'nav.videos', 'Map': 'nav.map', 'Chat': 'nav.chat'}\ngo.append(native_t(go_names.get(name, ''), name))"
        go = re.search(r'\bGO\s*=\s*\[(.*?)\]', source, re.S)
        keys = re.search(r'go_names\s*=\s*\{(.*?)\}', source, re.S)
        values = set(re.findall(r"['\"]([^'\"]+)['\"]\s*,", go.group(1)))
        names = set(re.findall(r"['\"]([^'\"]+)['\"]\s*:\s*['\"]nav\.", keys.group(1)))
        values &= names
        self.assertEqual(values, {'Videos', 'Map', 'Chat'})
        self.assertEqual(scan.classify('Choose', 'dialog.setWindowTitle('), 'chrome')
