"""tools/embed_bench.py: the check that no build or running Lastbook is writing to the index before it is read as
immutable. Temporary folders only, no model. Never packaged."""
import importlib.util, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from engine.paths import try_lock, unlock  # noqa: E402

spec = importlib.util.spec_from_file_location('embed_bench', ROOT / 'tools' / 'embed_bench.py')
embed_bench = importlib.util.module_from_spec(spec)
spec.loader.exec_module(embed_bench)


class IndexInUse(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.idx = Path(self.tmp.name)
        (self.idx / 'semantic.sqlite').write_bytes(b'')

    def tearDown(self):
        self.tmp.cleanup()

    def test_free_index(self):
        self.assertIsNone(embed_bench.index_in_use(self.idx))
        (self.idx / 'indexer.lock').write_bytes(b'')
        (self.idx / 'semantic.sqlite-wal').write_bytes(b'')  # left empty by a reader: still free
        self.assertIsNone(embed_bench.index_in_use(self.idx))

    def test_changes_waiting_in_the_wal(self):
        (self.idx / 'semantic.sqlite-wal').write_bytes(b'x' * 32)
        self.assertIn('semantic.sqlite-wal is not empty', embed_bench.index_in_use(self.idx))

    def test_lock_held_by_another_handle(self):
        lock = self.idx / 'indexer.lock'
        with open(lock, 'w') as held:  # as Index.update() holds it
            try_lock(held)
            try:
                self.assertIn('indexer.lock is held', embed_bench.index_in_use(self.idx))
            finally:
                unlock(held)
        self.assertIsNone(embed_bench.index_in_use(self.idx))
        self.assertEqual(lock.read_bytes(), b'')  # the check wrote nothing


if __name__ == '__main__':
    unittest.main()
