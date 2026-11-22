"""The local AI's thinking never reaches the answer, including a smaller model's (E2B, E4B) plain-text thinking that ends in a
thought block's close it never opened. Never packaged."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import llm_local                    # noqa: E402


class HideThinking(unittest.TestCase):
    def test_closed_block_goes(self):
        self.assertEqual(llm_local.hide_thinking('<|channel>thought\nhmm<channel|>Boil it for 1 minute.'), 'Boil it for 1 minute.')

    def test_unfinished_block_hides_what_follows(self):
        self.assertEqual(llm_local.hide_thinking('Answer so far <|channel>thought\nstill thinking'), 'Answer so far ')

    def test_stray_close_from_a_smaller_model(self):
        """E4B after a tool response: plain-text thinking, then a close it never opened, then the answer."""
        text = 'The user is asking about boiling. S4 says 1 minute.<channel|>Bring the water to a rolling boil for 1 minute [S4].'
        self.assertEqual(llm_local.hide_thinking(text), 'Bring the water to a rolling boil for 1 minute [S4].')

    def test_plain_answer_is_kept(self):
        self.assertEqual(llm_local.hide_thinking('Use 8 drops per gallon [S1].'), 'Use 8 drops per gallon [S1].')


if __name__ == '__main__':
    unittest.main()
