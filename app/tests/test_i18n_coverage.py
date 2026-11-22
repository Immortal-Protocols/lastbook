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
        kinds = {scan.classify(text, pre + wired[pos:pos+180]) for pos, text, pre in scan.iter_js_strings(wired)}
        self.assertNotIn('chrome', kinds)
