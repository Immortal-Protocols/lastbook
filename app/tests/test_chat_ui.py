"""Focused checks for the offline chat and appearance controller (requires Node)."""
from pathlib import Path
import shutil
import subprocess
import unittest

NODE = shutil.which('node')


@unittest.skipUnless(NODE, 'needs node on PATH')
class ChatUI(unittest.TestCase):
    def test_chat_behavior(self):
        result = subprocess.run([NODE, str(Path(__file__).with_name('chat_ui_test.mjs'))],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_appearance_behavior(self):
        result = subprocess.run([NODE, str(Path(__file__).with_name('appearance_ui_test.mjs'))],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
