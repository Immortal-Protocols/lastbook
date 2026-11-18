"""Exercise current-turn evidence admission without a model process or network."""
import io
import json
from pathlib import Path
import re
import tempfile
import types
import unittest
from unittest import mock

import assistant
import llm_local


def packet(delta=None, reason=None):
    return {'choices': [{'delta': delta or {}, 'finish_reason': reason}]}


def stream(*packets):
    return io.BytesIO(b''.join(b'data: ' + (json.dumps(p).encode() if p != '[DONE]' else b'[DONE]') + b'\n\n'
                               for p in packets))


class CurrentEvidence(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.app = Path(folder.name)
        self.catalogue = {d: {'id': d, 'kind': 'pdf', 'pages': 1, 'path': f'documents/{d}.pdf'} for d in ('a', 'b')}
        self.server = types.SimpleNamespace(APP=self.app, CLINICAL=re.compile(r'(?!)'),
                                            catalog=lambda: {'by_id': self.catalogue},
                                            page_texts=lambda record: ['indexed'], public=self.hit)
        for key, value in {'S': self.server, 'LOCAL': None, 'INDEX': None}.items():
            patch = mock.patch.object(assistant, key, value)
            patch.start()
            self.addCleanup(patch.stop)

    def hit(self, record):
        return {'doc_id': record['id'], 'title': f"Source {record['id']}", 'publisher': 'Example Publisher',
                'year': '2026', 'trust': 'reference', 'kind': record['kind'], 'pages': record.get('pages'),
                'page': 1, 't': None, 'excerpt': 'An initial excerpt.', 'found_by': {'keyword': 1}}

    def chat(self, messages=None, about=None):
        events = []
        assistant.chat(messages or [{'role': 'user', 'content': 'Which source covers this?'}], about, events.append, lambda: False)
        return events

    def comparison(self, scope, finding='A checked comparison finding.'):
        (self.app / 'content').mkdir(exist_ok=True)
        note = {'scope': scope, 'sources': [{'doc_id': d, 'page': 1, 'requires': [f'Checked wording {d}.']} for d in ('a', 'b')],
                'finding': finding, 'notice': 'Checked source comparison {source0} {source1}.'}
        (self.app / 'content/source-disagreements.json').write_text(json.dumps([note]))
        return finding

    def test_scoped_comparison_preserves_both_originals_and_other_topics(self):
        finding = self.comparison({'subject': r'\b(?:perishable|refrigerator)\b', 'intent': r'\b(?:how long|hours)\b'})
        self.catalogue['c'] = {'id': 'c', 'kind': 'pdf', 'pages': 1, 'path': 'documents/c.pdf'}
        cases = [
            ('Is a heater suitable for an enclosed room?', 'Heating evidence [S3].', False, False),
            ('How long will a refrigerator keep food cold?', 'Food evidence [S1].', True, False),
            ('Is a heater suitable indoors? How long will the refrigerator keep food cold?',
             'Food evidence [S1]. Heating evidence [S3].', True, False),
            ('How long will a refrigerator keep food cold?', 'Claim about an omitted page [S2].', True, True),
        ]
        for question, reply, checked, omitted in cases:
            with self.subTest(question=question, omitted=omitted):
                history = [{'role': 'assistant', 'content': 'An old claim [S1, S2].'}, {'role': 'user', 'content': question}]

                def body(record, page):
                    if omitted and record['id'] == 'b':
                        return 'Long original with conditions. ' * 400
                    return f"Current page body {record['id']}."

                with (mock.patch.object(assistant, 'hybrid', return_value=list(map(self.hit, self.catalogue.values()))),
                      mock.patch.object(assistant, '_page_paragraphs', side_effect=lambda r, p: f"Checked wording {r['id']}."),
                      mock.patch.object(assistant, '_page_body', side_effect=body),
                      mock.patch.object(assistant, 'model_open', return_value=stream(packet({'content': reply}), '[DONE]')) as opened):
                    events = self.chat(history)
                model_messages = json.loads(opened.call_args.args[0].data)['messages']
                self.assertFalse(any(any(k.startswith('_') for k in message) for message in model_messages))
                self.assertEqual(model_messages[1]['content'], 'An old claim (earlier citations).')
                prompt = '\n'.join(m['content'] for m in model_messages)
                self.assertIn('Current page body a.', prompt)
                self.assertIn('Current page body c.', prompt)
                final = events[-1]
                self.assertEqual('Checked source comparison [S1] [S2].' in final['answer'], checked)
                if omitted:
                    self.assertIn('SOURCE OMITTED', prompt)
                    self.assertNotIn(finding, prompt)
                    self.assertEqual(final['error'], 'invalid_citations')
                    self.assertEqual(final['invalid'], ['S2'])
                    self.assertFalse(any(event['type'] == 'done' for event in events))
                else:
                    self.assertIn('Current page body b.', prompt)
                    self.assertEqual(final['type'], 'done')
                    if checked:
                        self.assertGreater(prompt.index(finding), prompt.index('Current page body b.'))
                        self.assertIn('[S1] doc_id=a, page 1; [S2] doc_id=b, page 1', prompt)
                    else:
                        self.assertNotIn(finding, prompt)
                    if 'Heating evidence' in reply:
                        self.assertIn('S3', [s['key'] for s in final['sources']])

    def test_omitted_or_unavailable_page_is_consulted_and_can_be_read_later(self):
        hit = self.hit(self.catalogue['a'])
        length = 'Long complete page and its conditions. ' * 300
        response = lambda: stream(packet({'content': 'A draft [S1].'}), '[DONE]')
        for body in (length, '', '[SOURCE TEXT UNAVAILABLE: No extractable text.]'):
            with self.subTest(body=body[:20]), mock.patch.object(assistant, 'hybrid', return_value=[hit]), \
                    mock.patch.object(assistant, '_page_body', return_value=body), mock.patch.object(assistant, 'model_open', return_value=response()):
                final = self.chat()[-1]
                self.assertEqual(final['error'], 'invalid_citations')
                self.assertEqual([s['key'] for s in final['consulted']], ['S1'])
        call = {'index': 0, 'id': 'read-a', 'function': {'name': 'read_pages', 'arguments': '{"doc_id":"a","pages":[1]}'}}
        with (mock.patch.object(assistant, 'hybrid', return_value=[hit]),
              mock.patch.object(assistant, '_page_body', side_effect=[length, 'A complete page including its condition.']),
              mock.patch.object(assistant, 'model_open', side_effect=[stream(packet({'tool_calls': [call]}, 'tool_calls'), '[DONE]'), response()]) as opened):
            final = self.chat()[-1]
        followup = json.loads(opened.call_args.args[0].data)['messages']
        self.assertEqual(followup[-1]['tool_call_id'], 'read-a')
        self.assertIn('A complete page including its condition.', followup[-1]['content'])
        self.assertEqual(final['type'], 'done')
        self.assertEqual([s['key'] for s in final['sources']], ['S1'])

    def test_native_context_fit_removed_evidence_cannot_validate_a_citation(self):
        local = mock.Mock()
        local.available.return_value = True
        local.ensure_running.return_value = None
        seen = []
        page_a = ('Large evidence A with conditions. ' * 210).strip()
        page_b = 'Complete evidence B with its limiting condition.'
        finding = self.comparison({'subject': r'\bsource\b', 'intent': r'\bcovers\b'})

        def generate(segs, max_tokens, cancelled, write, **kwargs):
            rendered = ''.join(text for text, _ in segs)
            seen.append(rendered)
            if len(seen) == 1:
                llm_local.CTX = 12000
                write('<|tool_call>call:read_pages{doc_id:<|"|>b<|"|>,pages:[1]}<tool_call|>')
            else:
                write('Use these references [S1][S2].')
            return {'reason': 'eog'}

        local.generate.side_effect = generate
        with (mock.patch.object(assistant, 'LOCAL', local), mock.patch.object(llm_local, 'CTX', 24000),
              mock.patch.object(llm_local, 'size_of', side_effect=lambda segs: sum(len(t) for t, _ in segs)),
              mock.patch.object(assistant, '_page_paragraphs', side_effect=lambda r, p: f"Checked wording {r['id']}."),
              mock.patch.object(assistant, '_page_body', side_effect=lambda r, p: page_a if r['id'] == 'a' else page_b)):
            final = self.chat(about='doc:a:1')[-1]
        self.assertEqual(len(seen), 2)
        self.assertIn(page_a, seen[0])
        self.assertIn('Evidence omitted', seen[1])
        self.assertNotIn(page_a, seen[1])
        self.assertIn(page_b, seen[1])
        self.assertNotIn(finding, seen[1])
        self.assertEqual(final['error'], 'invalid_citations')
        self.assertEqual(final['invalid'], ['S1'])
        self.assertIn('Checked source comparison [S1] [S2].', final['verified_notice'])
        self.assertEqual([s['key'] for s in final['verified_sources']], ['S1', 'S2'])

    def test_transcript_budget_never_slices_a_cue_or_context_window(self):
        video = self.catalogue['v'] = {'id': 'v', 'kind': 'video'}
        long = 'A conditional passage. ' * 150 + 'Required condition at the end.'
        self.server.transcript = lambda vid: {'cues': [{'t': 13, 'text': long}, {'t': 26, 'text': 'Complete next cue.'}]}
        sess = assistant.Session()
        tool, _ = assistant.run_tool('get_timed_transcript', {'video_id': video['id']}, sess, [])
        self.assertIn('SOURCE OMITTED', tool)
        self.assertNotIn('A conditional passage', tool)
        self.assertIn('Complete next cue.', tool)
        self.assertEqual(sess.prompt_message('tool', tool)['_evidence'], ('S2',))
        context = assistant.context_for('video:v:13', sess)
        self.assertIn('SOURCE OMITTED', context)
        self.assertNotIn('A conditional passage', context)
        self.assertNotIn('_evidence', sess.prompt_message('system', context))

    def test_no_hit_tool_and_final_round_preserve_retrieval_scope(self):
        call = {'index': 0, 'id': 'look-again', 'function': {'name': 'search_library', 'arguments': '{"query":"missing phrase"}'}}
        responses = [
            stream(packet({'tool_calls': [call]}), '[DONE]'),
            stream('[DONE]'),
            stream(packet({'content': 'I could not establish that from the retrieved material.'}), '[DONE]'),
        ]
        with (mock.patch.object(assistant, 'hybrid', return_value=[]),
              mock.patch.object(assistant, 'model_open', side_effect=responses) as opened):
            self.assertEqual(self.chat()[-1]['type'], 'done')
        prompt = '\n'.join(m['content'] for m in json.loads(opened.call_args.args[0].data)['messages'])
        self.assertIn('The initial search found no matching passages', prompt)
        self.assertIn('This search found no matching passages', prompt)
        self.assertIn('Not found in the retrieved pages:', prompt)
        self.assertNotIn('Not found in the library:', prompt)
        self.assertNotIn('library does not cover', prompt)

    def test_http_page_image_remains_multimodal_and_citable(self):
        self.server.render_page = mock.Mock(return_value=b'synthetic image bytes')
        call = {'index': 0, 'id': 'view-a', 'function': {'name': 'view_page', 'arguments': '{"doc_id":"a","page":1}'}}
        responses = [stream(packet({'tool_calls': [call]}), '[DONE]'), stream(packet({'content': 'See this image [S1].'}), '[DONE]')]
        with (mock.patch.object(assistant, 'hybrid', return_value=[]),
              mock.patch.object(assistant, 'model_open', side_effect=responses) as opened):
            final = self.chat()[-1]
        request = json.loads(opened.call_args.args[0].data)['messages']
        self.assertIn('view_page when a diagram or table matters', request[0]['content'])
        self.assertNotIn('this model has text input only', request[0]['content'].lower())
        self.assertEqual(request[-2]['tool_call_id'], 'view-a')
        self.assertTrue(request[-1]['content'][1]['image_url']['url'].startswith('data:image/png;base64,'))
        self.assertNotIn('_evidence', request[-1])
        self.assertEqual(final['type'], 'done')
        self.assertEqual([source['key'] for source in final['sources']], ['S1'])

    def test_page_evidence_warning_allows_vision_only_when_available(self):
        self.assertIn('when image input is available', assistant._bounded_source('excerpt', 100))
        self.assertIn('when image input is available', assistant.NO_SOURCE_TEXT)
        self.assertNotIn('view_page', assistant.SYSTEM_TEXT_ONLY)
        self.assertIn('This model has text input only', assistant.SYSTEM_TEXT_ONLY)

if __name__ == '__main__':
    unittest.main()
