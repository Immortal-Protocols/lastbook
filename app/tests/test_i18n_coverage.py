"""Hard-coded UI chrome should not regress: every user-visible string is catalogued."""
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
        cls.hits = scan.scan_web() + scan.scan_python()
        cls.chrome = scan.unique_chrome(cls.hits)
        cls.totals = scan.summarize(cls.hits)[1]

    def test_catalogues_are_paired(self):
        self.assertGreaterEqual(len(self.english), 1000)

    def test_every_web_runtime_file_is_scanned_or_declared_non_ui(self):
        actual = {path.name for path in (ROOT / 'web').glob('*.js')} | {'index.html', 'setup.html'}
        inventoried = set(scan.WEB_FILES) | scan.WEB_NON_UI_FILES
        self.assertEqual(actual, inventoried,
                         f'unclassified web files: {sorted(actual - inventoried)}; stale entries: {sorted(inventoried - actual)}')

    def test_literal_catalogue_references_exist(self):
        # Catch key typos and stale references across every scanned runtime,
        # not only JS tr() calls. setup.html/setup.json are asset filenames.
        keys = set(self.english)
        sources = [scan.WEB / name for name in scan.WEB_FILES]
        sources.extend(path for paths in scan.PYTHON_SURFACES.values() for path in paths)
        referenced = set()
        for path in sources:
            if path.is_file():
                referenced.update(re.findall(r"['\"]((?:about|app|chat|common|copy|desktop|error|help|installer|language|library|map|native|nav|reader|saved|search|setup|time|topic|update|video|videos|wiki)\.[A-Za-z][A-Za-z0-9_.-]*)['\"]",
                                             path.read_text(encoding='utf-8')))
        referenced.difference_update({'setup.html', 'setup.json', 'app.zip'})
        referenced = {key for key in referenced if not key.endswith('.')}
        self.assertGreaterEqual(len(referenced), 800)
        self.assertEqual(referenced - keys, set(),
                         f'catalogue references without English messages: {sorted(referenced - keys)}')

    def test_no_unique_hardcoded_chrome(self):
        leftover = {text: locs for text, locs in self.chrome.items()}
        self.assertEqual(
            leftover, {},
            'hard-coded UI chrome left untranslated:\n' + '\n'.join(
                f'  {text!r}\n    {", ".join(locs)}' for text, locs in sorted(leftover.items())
            ),
        )

    def test_scanner_still_classifies_surfaces(self):
        # The inventory should keep seeing the desktop surfaces even when chrome is 0.
        self.assertGreater(self.totals['wired'], 1000)
        self.assertEqual(self.totals['chrome'], 0)

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
