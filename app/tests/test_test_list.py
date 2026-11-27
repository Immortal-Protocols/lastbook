"""The test command in CONTRIBUTING.md names every app/tests/test_*.py module, and only modules that exist.

A module left out of that command is a test nobody runs before a pull request: 28 had drifted out of it. The pull request
template points to the command instead of carrying a second copy that can drift on its own. Reads two text files; needs
no library, no server and no network.

  python3 -B -m unittest app.tests.test_test_list
"""
import re, sys, unittest
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
TESTS = ROOT / 'app' / 'tests'
MODULE = re.compile(r'\bapp\.tests\.(test_\w+)')


def test_command():
    """The first fenced block under "## Test" in CONTRIBUTING.md, as the modules it names, in order."""
    text = (ROOT / 'CONTRIBUTING.md').read_text(encoding='utf-8')
    section = text.split('\n## Test\n', 1)[1].split('\n## ', 1)[0]
    block = re.search(r'```\w*\n(.*?)```', section, re.S).group(1)
    return MODULE.findall(block)


class TestList(unittest.TestCase):
    def test_every_test_module_is_in_the_contributing_command(self):
        on_disk = {p.stem for p in TESTS.glob('test_*.py')}
        missing = sorted(on_disk - set(test_command()))
        self.assertEqual(missing, [], 'add these to the test command in CONTRIBUTING.md')

    def test_the_command_names_only_modules_that_exist_and_each_once(self):
        named = test_command()
        self.assertEqual(sorted(m for m in set(named) if not (TESTS / f'{m}.py').is_file()), [], 'no such file in app/tests/')
        self.assertEqual(sorted({m for m in named if named.count(m) > 1}), [], 'named twice')

    def test_the_pull_request_template_points_to_the_command_and_keeps_no_copy(self):
        template = (ROOT / '.github' / 'pull_request_template.md').read_text(encoding='utf-8')
        self.assertEqual(MODULE.findall(template), [], 'a second list drifts; point to CONTRIBUTING.md instead')
        self.assertIn('CONTRIBUTING.md#test', template)


if __name__ == '__main__':
    unittest.main()
