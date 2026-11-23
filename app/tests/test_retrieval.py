"""Meaning-based search (retrieval.Index.semantic): per-document filtering. Small made-up index, no real library, no model.
And the index's journal where the library's folder cannot hold WAL (retrieval.Index._journaled). Never packaged."""
import os, shutil, sqlite3, sys, tempfile, unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(Path(__file__).resolve().parent)]
import fixture  # noqa: E402
os.environ.setdefault('LASTBOOK_DATA', str(fixture.ensure()))
os.environ.setdefault('SURVIVAL_MODEL_BASE', 'http://127.0.0.1:9')
os.environ.setdefault('SURVIVAL_DISABLE_INDEX_WATCH', '1')
import numpy as np  # noqa: E402
import retrieval  # noqa: E402

TEXT = 'Boil water for one full minute before drinking it, then let it cool and store it in a clean covered container.'


def vec(*xs):
    v = np.zeros(retrieval.DIM, dtype=np.float32)
    v[:len(xs)] = xs
    return v


class FakeEmb:
    def embed(self, texts):
        return np.array([vec(1.0)] * len(texts))


def make_index(tmp, rows):
    """rows: [(doc_id, vector)]. Writes the chunk table and vectors, returns an Index with a fake embedder."""
    tmp = Path(tmp)
    with mock.patch.object(retrieval, 'IDX', tmp), mock.patch.object(retrieval, 'AVAILABLE', True), mock.patch.object(retrieval, 'Embedder', FakeEmb):
        idx = retrieval.Index(lambda: {}, lambda r: ('', 1), tmp / 'fts.sqlite')
        db = idx._db()
        for i, (d, v) in enumerate(rows, 1):
            db.execute('INSERT INTO chunk(id,doc_id,page,t,text,active) VALUES(?,?,?,?,?,1)', (i, d, 1, float(i), TEXT))
        db.close()
        np.array([v for _, v in rows], dtype=np.float16).tofile(idx.vec_path)
        idx.emb = FakeEmb()
        idx._load(truncate=False)
    return idx


def close_index(idx):
    """Close the read-only SQLite reader that _load() keeps per thread. Windows cannot delete the temp folder while it is open."""
    c = getattr(idx._tls, 'ro', None)
    if c is not None:
        c.close()
        idx._tls.ro = None


class Semantic(unittest.TestCase):
    def test_per_document_filter_applies_before_the_cut(self):
        rows = [('a', vec(1.0))] * 50 + [('b', vec(0.8, 0.6))]  # b scores 0.8: above the floor, far below fifty a's
        with tempfile.TemporaryDirectory() as tmp:
            idx = make_index(tmp, rows)
            try:
                got = idx.semantic('water', 1, lambda x: x == 'b')
            finally:
                close_index(idx)
        self.assertEqual([g['doc_id'] for g in got], ['b'])

    def test_per_document_filter_fetches_few_texts(self):
        rows = [('a', vec(1.0))] * 3000 + [('b', vec(0.8, 0.6))] * 3
        with tempfile.TemporaryDirectory() as tmp:
            idx = make_index(tmp, rows)
            try:
                fetched = []
                idx._ro().set_trace_callback(lambda q: fetched.append(q) if 'text FROM chunk WHERE id=' in q else None)
                got = idx.semantic('water', 2, lambda x: x == 'b')
            finally:
                close_index(idx)
        self.assertEqual(len(got), 2)
        self.assertLessEqual(len(fetched), 4)


class NoSharedMemory(sqlite3.Connection):
    """A connection as on the Flatpak document portal or a network share: a file in WAL format cannot be used, because its
    wal-index needs shared memory, except by a connection in exclusive locking mode, which keeps that index in its own memory."""
    exclusive = False

    def execute(self, sql, *args):
        statement = sql.replace(' ', '').upper()
        if statement == 'PRAGMALOCKING_MODE=EXCLUSIVE':
            self.exclusive = True
        settings_only = statement.startswith(('PRAGMABUSY_TIMEOUT', 'PRAGMALOCKING_MODE'))    # these never read the file
        if not settings_only and not self.exclusive and self.wal_file():
            raise sqlite3.OperationalError('disk I/O error')
        return super().execute(sql, *args)

    def executescript(self, script):
        if not self.exclusive and self.wal_file():
            raise sqlite3.OperationalError('disk I/O error')
        return super().executescript(script)

    def wal_file(self):
        path = self.execute_path
        return path.is_file() and path.read_bytes()[18:20] == b'\x02\x02'     # the header's read and write versions: 2 is WAL


class Journal(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='lastbook-journal-'))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.idx = retrieval.Index.__new__(retrieval.Index)
        self.idx.db_path = self.tmp / 'semantic.sqlite'

    def no_shared_memory(self):
        real = sqlite3.connect

        def connect(path, *a, **k):
            con = real(path, *a, factory=NoSharedMemory, **k)
            con.execute_path = Path(path)
            return con
        return mock.patch.object(retrieval.sqlite3, 'connect', connect)

    def mode(self):
        con = sqlite3.connect(self.idx.db_path)
        try:
            return con.execute('PRAGMA journal_mode').fetchone()[0]
        finally:
            con.close()

    def test_wal_where_the_folder_holds_it(self):
        self.idx._journaled().close()
        self.assertEqual(self.mode(), 'wal')

    def test_rollback_journal_where_it_cannot(self):
        with self.no_shared_memory():
            db = self.idx._journaled()
            db.executescript('CREATE TABLE t(x); INSERT INTO t VALUES (1);')
            self.assertEqual(db.execute('SELECT x FROM t').fetchone(), (1,))
            db.close()
        self.assertEqual(self.mode(), 'delete')

    def test_an_index_already_in_wal_is_switched_and_kept(self):
        db = self.idx._journaled()
        db.executescript('CREATE TABLE t(x); INSERT INTO t VALUES (7);')
        db.close()
        self.assertEqual(self.mode(), 'wal')
        with self.no_shared_memory():
            db = self.idx._journaled()
            self.assertEqual(db.execute('SELECT x FROM t').fetchone(), (7,))
            db.close()
        self.assertEqual(self.mode(), 'delete')

if __name__ == '__main__':
    unittest.main()
