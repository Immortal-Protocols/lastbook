"""Gate new hard-coded UI copy and test scanner classification regressions."""
import sys
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'packaging'))
import i18n_scan as scan  # noqa: E402


class Coverage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        english, _ = scan.load_english()
        cls.english = english
        cls.hits = scan.scan_web() + scan.scan_topics() + scan.scan_python() + scan.scan_c()
        cls.chrome = scan.unique_chrome(cls.hits)
        cls.totals = scan.summarize(cls.hits)[1]
        cls.baseline = scan.load_chrome_baseline()

    def test_catalogues_are_paired(self):
        self.assertGreaterEqual(len(self.english), 1000)

    def test_scanner_reports_leftover_chrome(self):
        # Legacy entries remain visible in the inventory until follow-up work
        # wires them; this gate prevents this backlog from growing.
        self.assertIsInstance(self.chrome, dict)
        self.assertGreater(self.totals['wired'] + self.totals['chrome'] + self.totals['technical'], 0)

    def test_no_new_hardcoded_chrome_since_reviewed_baseline(self):
        added = scan.new_chrome(self.hits, self.baseline)
        self.assertEqual(added, [], f'new untranslated UI copy: {added!r}')

    def test_gate_detects_new_copy_and_extra_occurrences(self):
        baseline = scan.Counter({('web/index.html', '', 'Existing label'): 1})
        hits = [
            {'surface': 'web/index.html', 'text': 'Existing label', 'class': 'chrome'},
            {'surface': 'web/index.html', 'text': 'Existing label', 'class': 'chrome'},
            {'surface': 'web/index.html', 'text': 'New visible label', 'class': 'chrome'},
        ]
        self.assertEqual(scan.new_chrome(hits, baseline), [
            {'surface': 'web/index.html', 'file': '', 'text': 'Existing label', 'count': 1},
            {'surface': 'web/index.html', 'file': '', 'text': 'New visible label', 'count': 1},
        ])

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
        self.assertGreater(self.totals['wired'], 0)
        self.assertGreater(self.totals['technical'], 0)
        self.assertEqual(scan.new_chrome(self.hits, self.baseline), [])

    def test_cli_scanner_includes_dynamic_topics_and_windows_stub(self):
        source = (ROOT / 'packaging' / 'i18n_scan.py').read_text(encoding='utf-8')
        self.assertIn('hits = scan_web() + scan_topics() + scan_python() + scan_c()', source)

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

    def test_scanner_follows_arrow_regex_before_nested_visible_template(self):
        source = "root.innerHTML = `${(() => /}/.test('}'))() ? `<button>Keep visible copy</button>` : ''}`;"
        hits = [(text, pre) for _pos, text, pre in scan.iter_js_strings(source)]
        label = next(((text, pre) for text, pre in hits if text == 'Keep visible copy'), None)
        self.assertIsNotNone(label, f'regex brace truncated a rendered template: {hits!r}')
        self.assertEqual(scan.classify(*label), 'chrome')

    def test_scanner_detects_hardcoded_encyclopedia_display_data(self):
        sample = "const ZIMS = [['mdwiki', 'Medical encyclopedia', 'MDWiki: plain-language articles']];"
        hits = [(text, pre) for _pos, text, pre in scan.iter_js_strings(sample)]
        for literal in ('Medical encyclopedia', 'MDWiki: plain-language articles'):
            with self.subTest(literal=literal):
                pre = next(pre for text, pre in hits if text == literal)
                self.assertEqual(scan.classify(literal, pre), 'chrome')

    def test_scanner_reads_static_html_text_and_respects_i18n_markers(self):
        parser = scan._MarkupStrings('web/index.html')
        parser.feed('<p>Opening the guide…</p><p data-i18n="app.opening">Opening the guide…</p>')
        parser.close()
        matches = [(text, pre) for text, pre in parser.strings if text == 'Opening the guide…']
        self.assertEqual(len(matches), 2)
        self.assertEqual([scan.classify(text, pre) for text, pre in matches], ['chrome', 'wired'])

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

    def test_scanner_detects_short_rendered_button_labels(self):
        sample = '''root.innerHTML = `${canAdd ? `<button>Add</button>` : ''}`;'''
        hits = [(text, pre) for _pos, text, pre in scan.iter_js_strings(sample)]
        add = next((pre for text, pre in hits if text == 'Add'), None)
        self.assertIsNotNone(add, f'button label was skipped: {hits!r}')
        self.assertEqual(scan.classify('Add', add), 'chrome')

        # The short word by itself is not enough to call a code value UI.
        self.assertEqual(scan.classify('Add', 'const action = '), 'technical')
        self.assertEqual(scan.classify('OK', "statusLine('"), 'chrome')

    def test_scanner_checks_map_fallback_keys_and_ignores_markup_fragments(self):
        wired = "message('map.outsideDetail', null, 'Outside the area this map details, only main roads, towns and water show.')"
        text = next(hit for hit in scan.iter_js_strings(wired)
                    if hit[1].startswith('Outside the area'))
        self.assertEqual(scan.classify(text[1], text[2]), 'wired')

        missing = "message('map.missingKey', null, 'A newly hard-coded status')"
        text = next(hit for hit in scan.iter_js_strings(missing)
                    if hit[1] == 'A newly hard-coded status')
        self.assertEqual(scan.classify(text[1], text[2]), 'chrome')

        for fragment in (' lang="{…}"', ' title="{…}"', ' · <span class="muted">{…}</span>'):
            with self.subTest(fragment=fragment):
                self.assertEqual(scan.classify(fragment, 'return `'), 'technical')

    def test_scanner_detects_leading_space_ui_fragments(self):
        sample = '''function recommendLine() {
          const what = `${esc(p.title)}${r.ai && aiFits() ? ' with the local AI' : ''}`;
          return `<p class="s-rec">Suggested: ${what}</p>`;
        }'''
        hits = [(text, pre) for _pos, text, pre in scan.iter_js_strings(sample)]
        fragment = next((pre for text, pre in hits if text == ' with the local AI'), None)
        self.assertIsNotNone(fragment, f'leading-space UI fragment was skipped: {hits!r}')
        self.assertEqual(scan.classify(' with the local AI', fragment), 'chrome')

        # Protocol flags stay technical after trimming for UI classification.
        self.assertEqual(scan.classify(' --lan', 'const command = '), 'technical')

    def test_scanner_recognizes_chat_tr_keyed_fallbacks(self):
        wired = "const title = chatTr('chat.exportTitle', { title }, 'Chat: {title}')"
        hit = next(item for item in scan.iter_js_strings(wired) if item[1] == 'Chat: {title}')
        self.assertEqual(scan.classify(hit[1], hit[2]), 'wired')

        missing = "const title = chatTr('chat.newKey', null, 'A new visible label')"
        hit = next(item for item in scan.iter_js_strings(missing) if item[1] == 'A new visible label')
        self.assertEqual(scan.classify(hit[1], hit[2]), 'chrome')

    def test_scanner_recognizes_keyed_message_helpers(self):
        for sample, literal in [
            ("const label = chatTr('chat.exportTitle', { title }, 'Chat: {title}')", 'Chat: {title}'),
            ("setError(message, 'chat.stoppedUnexpectedly', null, 'The answer stopped unexpectedly.')", 'The answer stopped unexpectedly.'),
            ("trMarkup('setup.error', null, 'Setup could not start.')", 'Setup could not start.'),
        ]:
            with self.subTest(literal=literal):
                hit = next(item for item in scan.iter_js_strings(sample) if item[1] == literal)
                self.assertEqual(scan.classify(hit[1], hit[2]), 'wired')

        missing = "const label = chatTr('chat.newKey', null, 'A new visible label')"
        hit = next(item for item in scan.iter_js_strings(missing) if item[1] == 'A new visible label')
        self.assertEqual(scan.classify(hit[1], hit[2]), 'chrome')

    def test_scanner_treats_dynamic_attribute_selectors_as_technical(self):
        self.assertEqual(
            scan.classify('#{…} [data-act="{…}"]', 'document.querySelector(`'),
            'technical',
        )

    def test_scanner_detects_prose_exported_to_markdown(self):
        sample = '''function exportChat(c) {
          const md = `# ${c.title}\\n\\nExported from Lastbook (offline library) on ${chatDate(new Date())}.\\nAnswers were written by a local AI model from the library's documents. Check the linked pages; get trained help for anything serious.\\n`;
          new Blob([md], { type: 'text/markdown' });
        }'''
        hits = [(text, pre) for _pos, text, pre in scan.iter_js_strings(sample)]
        exported = next((text, pre) for text, pre in hits if text.startswith('# {…}') and 'Answers were written' in text)
        self.assertEqual(scan.classify(*exported), 'chrome')

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

    def test_scanner_inventories_desktop_name_comment_and_search_keywords(self):
        rows = [hit for hit in scan.scan_python() if hit.get('file') == 'packaging/linux/lastbook.desktop']
        self.assertTrue(any(hit['text'] == 'Search and read the survival library on this computer, with no internet'
                            and hit['class'] == 'wired' for hit in rows), rows)
        self.assertTrue(any(hit['text'] == 'survival;library;offline;first aid;'
                            and hit['class'] == 'wired' for hit in rows), rows)

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
