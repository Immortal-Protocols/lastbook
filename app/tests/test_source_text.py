"""Synthetic, freely distributable examples; no private or medical source text."""
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

from engine.source_text import (extract_pdf_page, layout_sensitive, prepare_page,
                                TRUNCATION_WARNING)


class SourceText(unittest.TestCase):
    def test_paragraph_order_wins_for_ordinary_page(self):
        # A source's content stream can preserve reading order better than layout.
        paragraphs = 'First paragraph, including its condition.\r\n\r\nSecond paragraph.'
        layout = '   First paragraph,\nincluding its condition.\n\n   Second paragraph.'
        page = prepare_page(paragraphs, layout)
        self.assertEqual(page.text, paragraphs.replace('\r\n', '\n'))
        self.assertFalse(page.layout_sensitive)
        self.assertTrue(page.layout_available)
        self.assertFalse(page.warnings)

    def test_simple_grid_retains_row_and_column_positions(self):
        layout = 'Item          Size       Count\nBlue crate    Small      7\nRed crate     Large      4'
        scrambled = 'Item Size Count Blue crate Red crate Small Large 7 4'
        page = prepare_page(scrambled, layout)
        self.assertEqual(page.text, layout)
        self.assertTrue(page.layout_sensitive)
        self.assertIn('associations have NOT been verified', page.render())
        self.assertNotIn(scrambled, page.render())

    def test_wrapped_cells_do_not_get_joined_to_nearest_value(self):
        layout = ('Container                 Quantity\n'
                  'For a small\n'
                  '                             2 pieces\n'
                  'wooden box\n'
                  'For a large\n'
                  '                             9 pieces\n'
                  'metal box')
        page = prepare_page('2 pieces 9 pieces wooden box metal box', layout)
        self.assertEqual(page.text, layout)
        self.assertTrue(page.layout_sensitive)
        self.assertNotIn('wooden box | 2 pieces', page.render())
        self.assertIn('abstain', page.render())
        self.assertIn('when image input is available', page.render())

    def test_mixed_prose_and_table_keep_every_printed_column(self):
        layout = ('Read these notes first.       Item           Parts\n'
                  'These notes continue.       Small rack         3\n'
                  'Keep the whole warning.     Large rack        12')
        page = prepare_page('Unreliable stream order', layout)
        self.assertEqual(page.text, layout)
        for phrase in ('Read these notes first.', 'Keep the whole warning.', 'Large rack        12'):
            self.assertIn(phrase, page.render())

    def test_two_column_prose_is_explicitly_uncertain(self):
        layout = ('Left paragraph begins.          Right paragraph begins.\n'
                  'Left paragraph continues.       Right paragraph continues.')
        page = prepare_page('Left paragraph begins.\nLeft paragraph continues.\n\nRight paragraph begins.\nRight paragraph continues.', layout)
        self.assertTrue(page.layout_sensitive)
        self.assertEqual(page.text, layout)
        self.assertIn('mixing columns', page.render())

    def test_units_fractions_unicode_and_tabs_are_not_squashed(self):
        layout = 'Label\tCount\nA\t1/3 unit\nB\t½ unit'
        page = prepare_page('irrelevant', layout)
        self.assertEqual(page.text, layout.expandtabs(8))
        self.assertIn('1/3', page.text)
        self.assertIn('½', page.text)

    def test_empty_page_does_not_fall_back_to_model_memory(self):
        page = prepare_page('', '')
        self.assertTrue(page.unavailable)
        self.assertIn('Do not infer', page.render())
        self.assertIn('when image input is available', page.render())

    def test_missing_layout_is_not_treated_as_verified_plain_text(self):
        page = prepare_page('First cell\nSecond cell\n7 pieces')
        self.assertTrue(page.layout_sensitive)
        self.assertFalse(page.layout_available)
        self.assertIn('LAYOUT UNAVAILABLE', page.render())
        self.assertIn('not verified', page.render())

    def test_truncation_never_supplies_a_partial_row_or_warning(self):
        layout = 'Item            Value\n' + '\n'.join('Row %d           %d units' % (i, i) for i in range(200))
        page = prepare_page(layout, layout)
        limited = page.render(1000)
        self.assertTrue(page.bounded(1000).truncated)
        self.assertFalse(page.bounded(20000).truncated)
        self.assertEqual(limited, '[' + TRUNCATION_WARNING + ']')
        self.assertNotIn('Row 0', limited)
        self.assertLessEqual(len(limited), 1000)
        self.assertEqual(page.render(20000).split('\n\n', 1)[1], layout)
        with self.assertRaises(ValueError):
            page.render(100)

    def test_no_content_or_subject_specific_heuristics(self):
        self.assertTrue(layout_sensitive('Moss           Shade\nSand           Sun'))
        self.assertFalse(layout_sensitive('One sentence.\nAnother sentence.'))

    def test_pdfium_handles_close_on_success_and_failure(self):
        closed = []
        class Text:
            def get_text_range(self): return 'One paragraph.'
            def close(self): closed.append('text')
        class Page:
            def get_textpage(self): return Text()
            def close(self): closed.append('page')
        class PDF:
            def __init__(self, path): pass
            def __getitem__(self, number): return Page()
            def close(self): closed.append('pdf')
        with patch.dict(sys.modules, {'pypdfium2': types.SimpleNamespace(PdfDocument=PDF)}):
            result = extract_pdf_page(Path('/path/to/source.pdf'), 1, 'One paragraph.')
        self.assertEqual(result.text, 'One paragraph.')
        self.assertEqual(closed, ['text', 'page', 'pdf'])
        def fail(path): raise ValueError('/private/path/with-secret')
        with patch.dict(sys.modules, {'pypdfium2': types.SimpleNamespace(PdfDocument=fail)}):
            result = extract_pdf_page('/path/to/source.pdf', 1)
        self.assertTrue(result.unavailable)
        self.assertNotIn('/private', result.render())
        for number in (0, -1, True, '1'):
            with self.assertRaises(ValueError): extract_pdf_page('/path/to/source.pdf', number)


if __name__ == '__main__':
    unittest.main()
