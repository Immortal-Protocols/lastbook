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
