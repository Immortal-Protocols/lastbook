"""Check optional editorial data and the shipped module without building installers."""
import ast
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
GUARD = 'source-disagreements.json'
SCRIPT = ROOT / 'packaging/ship_app_files.py'


class SourceGuardPackage(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('ship_guard_fixture', SCRIPT)
        self.ship = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.ship)
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.fixture = Path(folder.name) / 'source'
        self.output = Path(folder.name) / 'ship'
        (self.fixture / 'web').mkdir(parents=True)
        (self.fixture / 'content/topics').mkdir(parents=True)
        (self.fixture / 'web/index.html').write_text('<p>Offline library</p>')
        (self.fixture / 'content/gaps.json').write_text('{}')

    def build(self):
        with (mock.patch.object(self.ship, 'ROOT', self.fixture),
              mock.patch.object(self.ship, 'EDITS', dict(self.ship.EDITS, text={})),
              mock.patch.object(sys, 'argv', [str(SCRIPT), str(self.output)]),
              mock.patch('builtins.print')):
            self.ship.main()

    def test_verbatim_optional_data_and_no_stale_guard_when_removed(self):
        guard = self.fixture / 'content' / GUARD
        data = b'[{"notice":"Checked comparison {source0}", "sources":[{"doc_id":"guide","page":1}]}]\n'
        guard.write_bytes(data)
        self.build()
        shipped = self.output / 'content' / GUARD
        self.assertEqual(shipped.read_bytes(), data)
        spec = ast.parse((ROOT / 'packaging/lastbook_macos.spec').read_text())
        nodes = [node for node in spec.body if isinstance(node, ast.FunctionDef) and node.name == 'files' or
                 isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in ('datas', 'hidden') for t in node.targets)]
        namespace = {'SHIP': self.output}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), '<mac spec data selection>', 'exec'), namespace)
        self.assertIn((str(shipped), 'content'), namespace['datas'])
        self.assertIn('engine.source_text', namespace['hidden'])
        self.assertIn('--hidden-import engine.source_text', (ROOT / 'packaging/build_app_windows.sh').read_text())
        self.assertIn('cp "$ROOT/engine/source_text.py" "$OPT/engine/"', (ROOT / 'packaging/linux/build_app_linux.sh').read_text())
        guard.unlink()
        self.build()
        self.assertFalse(shipped.exists())

    def test_guard_passes_the_same_privacy_scan(self):
        (self.fixture / 'content' / GUARD).write_text('[{"notice":"placeholdertown","sources":[]}]')
        with self.assertRaisesRegex(SystemExit, 'content/source-disagreements.json'):
            self.build()


if __name__ == '__main__':
    unittest.main()
