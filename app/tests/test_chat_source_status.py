"""Run the source admission UI fixture with Node (no browser or model required)."""
from pathlib import Path
import shutil
import subprocess
import unittest

NODE = shutil.which('node')


@unittest.skipUnless(NODE, 'needs Node on PATH')
class SourceStatus(unittest.TestCase):
    def test_verified_notice_and_incomplete_body(self):
        fixture = Path(__file__).with_name('chat_source_status_test.mjs')
        result = subprocess.run([NODE, str(fixture)], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
