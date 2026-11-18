#!/usr/bin/env python3
"""Regression tests for web/app.js, chat.js, map.js and terrain3d.js, run in Node (node:test).

  python3 -B -m unittest app.tests.test_web_fixes [-v]

Needs Node on PATH; skipped without it. Never packaged."""
import shutil, subprocess, unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
NODE = shutil.which('node')


@unittest.skipUnless(NODE, 'needs node on PATH')
class WebFixes(unittest.TestCase):
    def test_node_suite(self):
        r = subprocess.run([NODE, '--test', str(HERE / 'web_fixes_test.mjs')], capture_output=True, text=True, encoding='utf-8', timeout=120)
        self.assertEqual(r.returncode, 0, (r.stdout + r.stderr)[-4000:])


if __name__ == '__main__':
    unittest.main()
