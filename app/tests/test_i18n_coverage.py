"""The leftover-string scanner runs on desktop surfaces.

Wiring leftover chrome is completed in follow-up pull requests; this test
fails only if the scanner itself breaks or unique chrome is not reported.
"""
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

    def test_scanner_reports_leftover_chrome(self):
        # Report-only in this pull request: unique chrome is wired in follow-ups.
        self.assertIsInstance(self.chrome, dict)
        self.assertGreater(self.totals['wired'] + self.totals['chrome'] + self.totals['technical'], 0)

    def test_scanner_still_classifies_surfaces(self):
        self.assertGreater(self.totals['wired'], 0)
        self.assertGreater(self.totals['technical'], 0)

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
