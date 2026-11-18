"""Existing paragraph-reading and ambiguous-source safeguards; no medical answers inferred."""
import json
import tempfile
import threading
import types
import unittest
from pathlib import Path
from unittest import mock

import assistant


class SourceGuards(unittest.TestCase):
    def setUp(self):
        self.record = {'id': 'guide', 'kind': 'pdf', 'path': 'documents/guide.pdf', 'pages': 1}
        self.public = {'title': 'Guide', 'publisher': 'Publisher', 'year': '2026', 'trust': 'public', 'pages': 1}
        self.server = types.SimpleNamespace(LIB=Path('/offline/library'), _pdf_lock=threading.RLock(),
                                            catalog=lambda: {'by_id': {'guide': self.record}},
                                            page_texts=lambda record: ['indexed text'], public=lambda record: self.public)
        patch = mock.patch.object(assistant, 'S', self.server)
        patch.start()
        self.addCleanup(patch.stop)

    def test_pdf_paragraph_order_is_read_from_original_for_plain_prose(self):
        body = 'First paragraph.\r\n\r\nSecond paragraph, including its condition.'
        textpage = mock.Mock()
        textpage.get_text_range.return_value = body
        page, pdf = mock.Mock(), mock.MagicMock()
        page.get_textpage.return_value = textpage
        pdf.__getitem__.return_value = page
        pdfium = types.SimpleNamespace(PdfDocument=mock.Mock(return_value=pdf))
        with mock.patch.dict('sys.modules', {'pypdfium2': pdfium}):
            result = assistant._page_body(self.record, 1)
        self.assertEqual(result, body.replace('\r\n', '\n'))
        pdfium.PdfDocument.assert_called_once_with('/offline/library/documents/guide.pdf')
        textpage.close.assert_called_once()
        page.close.assert_called_once()
        pdf.close.assert_called_once()

    def test_pdf_failure_is_visible_and_never_substituted_with_indexed_text(self):
        pdfium = types.SimpleNamespace(PdfDocument=mock.Mock(side_effect=OSError('unreadable')))
        with mock.patch.dict('sys.modules', {'pypdfium2': pdfium}):
            result = assistant._page_body(self.record, 1)
        self.assertIn('extraction failed', result)
        self.assertNotIn('indexed text', result)

    def test_original_source_path_cannot_escape_library(self):
        pdfium = types.SimpleNamespace(PdfDocument=mock.Mock())
        with mock.patch.dict('sys.modules', {'pypdfium2': pdfium}):
            result = assistant._page_body(dict(self.record, path='../../private.pdf'), 1)
        self.assertIn('invalid catalog path', result)
        pdfium.PdfDocument.assert_not_called()

    def test_read_pages_and_open_page_context_preserve_paragraph_text(self):
        body = 'First paragraph.\n\n20 units    amount A\n200 units   amount B'
        with mock.patch.object(assistant, '_page_body', return_value=body):
            result, summary = assistant.run_tool('read_pages', {'doc_id': 'guide', 'pages': [1]}, assistant.Session(), [])
            context = assistant.context_for('doc:guide:1', assistant.Session())
        self.assertIn(body, result)
        self.assertIn(body, context)
        self.assertEqual(summary['pages'], [1])

    def test_open_page_context_marks_cut_text_as_incomplete(self):
        with mock.patch.object(assistant, '_page_body', return_value='A' * 8001):
            context = assistant.context_for('doc:guide:1', assistant.Session())
        self.assertIn('SOURCE OMITTED', context)
        self.assertIn('No partial paragraph, table row or warning', context)
        self.assertNotIn('view_page', context)
        self.assertNotIn('A' * 8001, context)

    def test_excerpts_and_cut_pages_are_explicitly_incomplete(self):
        self.assertIn('Search excerpt only', assistant._bounded_source('short excerpt', 100))
        self.assertIn('SOURCE OMITTED', assistant._bounded_source('full page text', 5, True))
        self.assertNotIn('full page text', assistant._bounded_source('full page text', 5, True))
        self.assertEqual(assistant._bounded_source('full page', 100, True), 'full page')

    def test_model_evidence_preserves_spatial_layout_not_scrambled_stream(self):
        layout = 'Item            Count\nSmall crate       3\nLarge crate      11'
        self.server.page_texts = lambda record: [layout]
        textpage = mock.Mock()
        textpage.get_text_range.return_value = 'Small crate Large crate 3 11'
        page, pdf = mock.Mock(), mock.MagicMock()
        page.get_textpage.return_value = textpage
        pdf.__getitem__.return_value = page
        with mock.patch.dict('sys.modules', {'pypdfium2': types.SimpleNamespace(PdfDocument=lambda path: pdf)}):
            result = assistant._page_body(self.record, 1)
        self.assertIn(layout, result)
        self.assertIn('associations have NOT been verified', result)
        self.assertNotIn('Small crate Large crate 3 11', result)

    def test_non_pdf_flow_is_unchanged(self):
        record = dict(self.record, kind='html')
        self.assertEqual(assistant._page_body(record, 1), 'indexed text')
        self.assertEqual(assistant._page_body(record, 2), '')

    def test_editorial_conflict_check_uses_independent_raw_paragraphs(self):
        note = {'scope': {'subject': r'\bguide\b', 'intent': r'\bcheck\b'},
                'sources': [{'doc_id': 'guide', 'page': 1, 'requires': ['A source statement.']}],
                'finding': 'A checked condition.', 'notice': 'Checked disagreement {source0}.'}
        with tempfile.TemporaryDirectory() as folder:
            content = Path(folder) / 'content'
            content.mkdir()
            (content / 'source-disagreements.json').write_text(json.dumps([note]))
            self.server.APP = Path(folder)
            session = assistant.Session('Check this guide.')
            session.add({'doc_id': 'guide', 'page': 1})
            with mock.patch.object(assistant, '_page_paragraphs', return_value='A source statement.'), mock.patch.object(assistant, '_page_body', side_effect=AssertionError('model evidence is not independent verification')):
                self.assertEqual(assistant._verified_source_context(session, public=True), 'Checked disagreement [S1].')
                guidance = assistant._verified_source_context(session)
                self.assertEqual(guidance[0]['_comparison_refs'], ('S1',))
                self.assertIn('A checked condition.', guidance[0]['content'])
            with mock.patch.object(assistant, '_page_paragraphs', return_value='Different text.'):
                self.assertEqual(assistant._verified_source_context(session, public=True), '')

    def test_editorial_scope_requires_subject_and_intent_and_respects_exclusion(self):
        note = {'scope': {'subject': r'\blimb\b', 'intent': r'\bbleeding\b',
                          'exclude': r'\bclinical protocol\b'}}
        self.assertTrue(assistant._comparison_applies(note, 'Bleeding from a limb while waiting for EMS'))
        self.assertFalse(assistant._comparison_applies(note, 'Clinical protocol for limb bleeding'))
        self.assertFalse(assistant._comparison_applies(note, 'Bleeding from the abdomen'))
        self.assertFalse(assistant._comparison_applies(note, 'Pain in a limb'))
        self.assertFalse(assistant._comparison_applies({}, 'Bleeding from a limb'))
        self.assertFalse(assistant._comparison_applies({'scope': {'subject': '[', 'intent': 'bleeding'}}, 'Bleeding'))

    def test_native_model_cannot_call_image_tool(self):
        with mock.patch.object(assistant, 'local_on', return_value=True), mock.patch.object(self.server, 'render_page', create=True) as render:
            result, summary = assistant.run_tool('view_page', {'doc_id': 'guide', 'page': 1}, assistant.Session(), [])
        self.assertIn('cannot inspect page images', result)
        self.assertEqual(summary['error'], 'image_input_unavailable')
        render.assert_not_called()
        self.assertNotIn('view_page', assistant.SYSTEM_TEXT_ONLY)
        self.assertIn('text input only', assistant.SYSTEM_TEXT_ONLY)

if __name__ == '__main__':
    unittest.main()
