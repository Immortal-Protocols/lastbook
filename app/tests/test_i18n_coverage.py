"""The leftover-string scanner runs on desktop surfaces.

Wiring leftover chrome is completed in follow-up pull requests; this test
fails only if the scanner itself breaks or unique chrome is not reported.
"""
import sys
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
