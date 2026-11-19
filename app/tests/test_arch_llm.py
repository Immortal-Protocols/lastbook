"""The Arch build's local-AI wiring: the runner is bundled only when asked for,
and the template keeps the placeholders that carry it."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / 'packaging/linux/arch/build_arch.py'
TEMPLATE = ROOT / 'packaging/linux/arch/PKGBUILD.in'


class ArchBuildLlamaTest(unittest.TestCase):
    def test_llm_directory_without_runner_is_refused_before_any_build(self):
        with tempfile.TemporaryDirectory() as empty:
            done = subprocess.run([sys.executable, '-I', '-B', str(BUILD),
                                   '--manifest', str(Path(empty) / 'manifest-v1.json'),
                                   '--llm', empty],
                                  capture_output=True, text=True, timeout=60)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn('no executable lastbook-llm', done.stderr + done.stdout)

    def test_template_carries_the_runner_source_and_flag(self):
        text = TEMPLATE.read_text(encoding='utf-8')
        self.assertIn("@LLM_SOURCE@", text)
        self.assertIn("@LLM_SHA256@", text)
        self.assertIn("@LLM_ARGS@", text)
        # The flag reaches stage_linux.py, which is what actually copies llm/.
        self.assertRegex(text, r'stage_linux\.py.*@LLM_ARGS@|@LLM_ARGS@.*\|\| return 1')


if __name__ == '__main__':
    unittest.main()
