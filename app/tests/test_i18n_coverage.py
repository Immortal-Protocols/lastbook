"""Hard-coded web and Setup chrome should not regress once those surfaces are wired."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'packaging'))
import i18n_scan as scan  # noqa: E402


def _is_later_surface(loc):
    later = ('shell_linux.py', 'shell_macos.py', 'shell_windows.py', 'main.py',
             'lastbook_setup.py', 'lastbook.desktop', 'native/')
    return any(part in loc for part in later)


class Coverage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        english, _ = scan.load_english()
        cls.english = english
        cls.hits = scan.scan_web() + scan.scan_python()
        cls.chrome = scan.unique_chrome(cls.hits)
        cls.totals = scan.summarize(cls.hits)[1]
        cls.web_setup_chrome = {
            text: locs for text, locs in cls.chrome.items()
            if any(not _is_later_surface(loc) for loc in locs)
        }

    def test_catalogues_are_paired(self):
        self.assertGreaterEqual(len(self.english), 1000)

    def test_no_unique_hardcoded_web_or_setup_chrome(self):
        leftover = {text: [loc for loc in locs if not _is_later_surface(loc)]
                    for text, locs in self.web_setup_chrome.items()}
        leftover = {t: locs for t, locs in leftover.items() if locs}
        self.assertEqual(
            leftover, {},
            'hard-coded web or Setup chrome left untranslated:\n' + '\n'.join(
                f'  {text!r}\n    {", ".join(locs)}' for text, locs in sorted(leftover.items())
            ),
        )

    def test_scanner_still_classifies_surfaces(self):
        self.assertGreater(self.totals['wired'], 1000)
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
                self.assertTrue(any(text == literal for text, _pre in hits), hits)
