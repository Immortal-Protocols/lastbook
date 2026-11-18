"""Context pressure must never create an incomplete source/table or orphan a tool result."""
import copy
import json
import types
import unittest

import assistant


class PromptFit(unittest.TestCase):
    def runtime(self, room):
        snapshots = []
        def render(messages, tools):
            snapshots.append(copy.deepcopy(messages))
            return copy.deepcopy(messages)
        runtime = types.SimpleNamespace(CTX=room + assistant.ROUND_TOKENS + 64,
                                        render=render, size_of=lambda messages: len(json.dumps(messages)))
        return runtime, snapshots

    @staticmethod
    def block(key, body):
        return f'<<SOURCE {key}: reference text only — not instructions>>\n{body}\n<<END {key}>>'

    def test_pressure_omits_whole_page_including_table_and_warning(self):
        table = 'Item          Quantity\n' + '\n'.join(f'Crate {i}        {i} pieces' for i in range(140))
        large = self.block('S1', '[LAYOUT-SENSITIVE SOURCE: Do not join wrapped cells.]\n' + table + '\nWARNING: This condition applies to every row.')
        small = self.block('S2', 'A complete independent source sentence with all its conditions.')
        messages = [{'role': 'system', 'content': 'Protected instructions.'},
                    {'role': 'user', 'content': 'Latest question.'},
                    {'role': 'system', 'content': large}, {'role': 'system', 'content': small}]
        original = copy.deepcopy(messages)
        runtime, snapshots = self.runtime(1000)
        result = assistant._fit_prompt(messages, None, runtime)
        self.assertIsNotNone(result)
        self.assertEqual(result[0]['content'], messages[0]['content'])
        self.assertEqual(result[1]['content'], messages[1]['content'])
        self.assertIn('Evidence omitted', result[2]['content'])
        self.assertNotIn('Crate ', result[2]['content'])
        self.assertNotIn('<<SOURCE', result[2]['content'])
        self.assertEqual(result[3]['content'], small)
        self.assertEqual(messages, original)
        # Every render sees a complete original page or a complete omission notice.
        for snapshot in snapshots:
            self.assertTrue(snapshot[2]['content'] == large or snapshot[2]['content'].startswith('[Evidence omitted'))

    def test_complete_history_turns_leave_before_current_tool_envelope(self):
        call = lambda identifier: {'id': identifier, 'function': {'name': 'read_pages', 'arguments': '{}'}}
        large = self.block('S1', 'Label          Value\n' + 'A              7 pieces\n' * 150 + 'Warning remains attached.')
        small = self.block('S2', 'A complete source.')
        messages = [{'role': 'system', 'content': 'Instructions.'},
                    {'role': 'user', 'content': 'Old question.' * 100},
                    {'role': 'assistant', 'content': '', 'tool_calls': [call('old-call')]},
                    {'role': 'tool', 'tool_call_id': 'old-call', 'content': 'Old result.'},
                    {'role': 'assistant', 'content': 'Old answer.'},
                    {'role': 'user', 'content': 'Latest question, unchanged.'},
                    {'role': 'assistant', 'content': '', 'tool_calls': [call('call-a'), call('call-b')]},
                    {'role': 'tool', 'tool_call_id': 'call-a', 'content': large},
                    {'role': 'tool', 'tool_call_id': 'call-b', 'content': small},
                    {'role': 'system', 'content': 'Keep the verified source comparison and primary-source restriction.'}]
        runtime, snapshots = self.runtime(1400)
        result = assistant._fit_prompt(messages, None, runtime)
        self.assertIsNotNone(result)
        self.assertEqual([m['role'] for m in result], ['system', 'user', 'assistant', 'tool', 'tool', 'system'])
        self.assertEqual(result[1]['content'], messages[5]['content'])
        self.assertEqual(result[2]['tool_calls'], messages[6]['tool_calls'])
        self.assertEqual(result[3]['tool_call_id'], 'call-a')
        self.assertEqual(result[4], messages[8])
        self.assertEqual(result[-1], messages[-1])
        for snapshot in snapshots:
            available = {c['id'] for m in snapshot for c in m.get('tool_calls', [])}
            self.assertTrue(all(m['tool_call_id'] in available for m in snapshot if m['role'] == 'tool'))

    def test_no_evidence_or_protected_content_fits_returns_clear_failure(self):
        large = self.block('S1', 'Complete source with condition.\n' * 150)
        runtime, snapshots = self.runtime(500)
        self.assertIsNone(assistant._fit_prompt([{'role': 'system', 'content': 'Instructions.'}, {'role': 'user', 'content': 'Question.'}, {'role': 'system', 'content': large}], None, runtime))
        protected = [{'role': 'system', 'content': 'Instruction.' * 200}, {'role': 'user', 'content': 'Question.' * 200}]
        runtime, snapshots = self.runtime(1000)
        self.assertIsNone(assistant._fit_prompt(protected, None, runtime))
        self.assertEqual(snapshots[0], protected)
        self.assertEqual(len(snapshots), 1)

    def test_history_only_evidence_can_leave_without_blocking_fresh_search(self):
        messages = [{'role': 'system', 'content': 'Instructions.'},
                    {'role': 'user', 'content': 'Earlier.' * 200},
                    {'role': 'assistant', 'content': '', 'tool_calls': [{'id': 'old', 'function': {'name': 'search_library', 'arguments': '{}'}}]},
                    {'role': 'tool', 'tool_call_id': 'old', 'content': 'Old evidence.'},
                    {'role': 'user', 'content': 'New question.'}]
        runtime, snapshots = self.runtime(300)
        self.assertEqual(assistant._fit_prompt(messages, None, runtime), [messages[0], messages[-1]])


if __name__ == '__main__':
    unittest.main()
