"""Regression tests for engine bugs found in the audit: retrieval, assistant tools, query building, Range serving, saved pages.
Small made-up data only; no real library. Never packaged."""
import io, os, sqlite3, sys, tempfile, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(Path(__file__).resolve().parent)]
import fixture  # noqa: E402
os.environ.setdefault('LASTBOOK_DATA', str(fixture.ensure()))
os.environ.setdefault('SURVIVAL_MODEL_BASE', 'http://127.0.0.1:9')
os.environ.setdefault('SURVIVAL_DISABLE_INDEX_WATCH', '1')
import numpy as np  # noqa: E402
import retrieval, assistant, server  # noqa: E402
from engine import library, saved_pages  # noqa: E402

TEXT = 'Boil water for one full minute before drinking it, then let it cool and store it in a clean covered container.'


def vec(*xs):
    v = np.zeros(retrieval.DIM, dtype=np.float32)
    v[:len(xs)] = xs
    return v


class FakeEmb:
    def embed(self, texts):
        return np.array([vec(1.0)] * len(texts))


class Racy(retrieval.Index):
    """Records whether the index lock was held whenever mat/active were assigned."""
    unlocked = None

    def __setattr__(self, k, v):
        if k in ('mat', 'active') and v is not None and hasattr(self, 'lock') and not self.lock._is_owned():
            self.__dict__.setdefault('unlocked', []).append(k)
        super().__setattr__(k, v)


def make_index(tmp, rows, cls=retrieval.Index):
    """rows: [(doc_id, vector)]. Writes the chunk table and vectors, returns an Index with a fake embedder."""
    tmp = Path(tmp)
    with mock.patch.object(retrieval, 'IDX', tmp), mock.patch.object(retrieval, 'AVAILABLE', True), mock.patch.object(retrieval, 'Embedder', FakeEmb):
        idx = cls(lambda: {}, lambda r: ('', 1), tmp / 'fts.sqlite')
        db = idx._db()
        for i, (d, v) in enumerate(rows, 1):
            db.execute('INSERT INTO chunk(id,doc_id,page,t,text,active) VALUES(?,?,?,?,?,1)', (i, d, 1, float(i), TEXT))
        db.close()
        np.array([v for _, v in rows], dtype=np.float16).tofile(idx.vec_path)
        idx.emb = FakeEmb()
        idx._load(truncate=False)
    return idx


class Semantic(unittest.TestCase):
    def test_per_document_filter_applies_before_the_cut(self):
        rows = [('a', vec(1.0))] * 50 + [('b', vec(0.8, 0.6))]  # b scores 0.8: above the floor, far below fifty a's
        with tempfile.TemporaryDirectory() as tmp:
            idx = make_index(tmp, rows)
            got = idx.semantic('water', 1, lambda x: x == 'b')
        self.assertEqual([g['doc_id'] for g in got], ['b'])

    def test_per_document_filter_fetches_few_texts(self):
        rows = [('a', vec(1.0))] * 3000 + [('b', vec(0.8, 0.6))] * 3
        with tempfile.TemporaryDirectory() as tmp:
            idx = make_index(tmp, rows)
            fetched = []
            idx._ro().set_trace_callback(lambda q: fetched.append(q) if 'text FROM chunk WHERE id=' in q else None)
            got = idx.semantic('water', 2, lambda x: x == 'b')
        self.assertEqual(len(got), 2)
        self.assertLessEqual(len(fetched), 4)

    def test_mat_and_active_are_swapped_under_the_lock(self):
        with tempfile.TemporaryDirectory() as tmp:
            idx = make_index(tmp, [('a', vec(1.0))] * 3, cls=Racy)
            idx.__dict__.pop('unlocked', None)
            with mock.patch.object(retrieval, 'AVAILABLE', True):
                idx._load(truncate=False)
        self.assertEqual(idx.__dict__.get('unlocked'), None)


class ReadPages(unittest.TestCase):
    def run_tool(self, rec, texts, pages):
        S = SimpleNamespace(catalog=lambda: {'by_id': {rec['id']: rec}}, page_texts=lambda r: texts,
                            public=lambda r: {'title': 'T', 'publisher': 'P', 'year': '', 'trust': 'x', 'pages': len(texts)})
        sess = assistant.Session()
        with mock.patch.object(assistant, 'S', S):
            out, _ = assistant.run_tool('read_pages', {'doc_id': rec['id'], 'pages': pages}, sess, [])
        return out, sess

    def test_document_with_no_text_does_not_raise(self):
        out, _ = self.run_tool({'id': 'd', 'kind': 'pdf'}, [], [1])
        self.assertIn('no text', out)

    def test_pptx_slides_keep_distinct_citations(self):
        out, sess = self.run_tool({'id': 'd', 'kind': 'pptx'}, ['first slide words', 'second slide words'], [1, 2])
        self.assertEqual(len(sess.sources), 2)
        self.assertIn('second slide words', [s['excerpt'] for s in sess.sources.values()])

    def test_pdf_same_page_still_dedupes(self):
        _, sess = self.run_tool({'id': 'd', 'kind': 'pdf'}, ['one', 'two'], [2, 2])
        self.assertEqual(len(sess.sources), 1)


class Words(unittest.TestCase):
    def test_lone_punctuation_is_not_a_search_word(self):
        content, groups = server.query_groups('water - purification _')
        self.assertEqual(content, ['water', 'purification'])
        self.assertNotIn('""', server.fts_expr(groups))


class FindCache(unittest.TestCase):
    def test_find_sees_a_reloaded_catalog(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = sqlite3.connect(Path(tmp) / 'fts.sqlite')
            db.execute('CREATE VIRTUAL TABLE pages USING fts5(doc_id, page, a, b, c, d, text)')
            db.execute('INSERT INTO pages VALUES(?,?,?,?,?,?,?)', ('d1', 1, '', '', '', '', 'rainwater harvesting tank'))
            db.commit(); db.close()
            rec = {'id': 'd1', 'kind': 'pdf', 'title': 'Rain Guide', 'path': 'documents/rain.pdf', 'collection': ''}
            cat = {'mtime': 1, 'by_id': {}, 'by_path': {}}
            with mock.patch.object(server.library, 'DB', Path(tmp) / 'fts.sqlite'), mock.patch.object(server, 'catalog', lambda: cat):
                server._find.cache_clear() if hasattr(server, '_find') else server.find.cache_clear()
                self.assertEqual(server.find('rainwater')['results'], [])
                cat.update(mtime=2, by_id={'d1': rec}, by_path={rec['path']: rec})
                self.assertEqual([r['id'] for r in server.find('rainwater')['results']], ['d1'])


class RangeLoop(unittest.TestCase):
    def test_file_shorter_than_stat_said_does_not_spin(self):
        class Gone(BaseException):
            pass

        class W(io.BytesIO):
            empties = 0

            def write(self, b):
                if not b:
                    self.empties += 1
                    if self.empties > 100:
                        raise Gone
                return super().write(b)
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / 'v.mp4'
            f.write_bytes(b'x' * 10)
            h = object.__new__(library.Handler)
            h.path, h.headers, h.wfile = '/v.mp4', {'Range': 'bytes=0-'}, W()
            h.connection = SimpleNamespace(settimeout=lambda t: None)
            h.file_ok = lambda p, folders=False: True
            h.translate_path = lambda p: str(f)
            h.send_response = h.send_header = h.end_headers = lambda *a: None
            h.send_error = lambda *a: None
            real = Path.stat

            def lying(self, *a, **k):
                r = real(self, *a, **k)
                return SimpleNamespace(st_size=100, st_mtime=r.st_mtime, st_mode=r.st_mode) if self == f else r
            with mock.patch.object(library, 'remote_records', lambda: {}), mock.patch.object(Path, 'stat', lying):
                try:
                    h.do_GET()
                except Gone:
                    self.fail('Range loop spun on an empty read')
            self.assertEqual(h.wfile.getvalue(), b'x' * 10)


class SavedPage(unittest.TestCase):
    def test_transcript_without_an_anchor_is_not_spliced_into_the_doctype(self):
        page = b'<!DOCTYPE html><html><head><title>t</title></head><body><track src="a.vtt"></body></html>'
        out = saved_pages.rewrite(page, lambda src: b'WEBVTT\n\n00:00.000 --> 00:01.000\nhello there\n')
        self.assertNotIn(b'lb-transcript', out.split(b'<head')[0])
        self.assertTrue(out.startswith(b'<!DOCTYPE html><html'))


if __name__ == '__main__':
    unittest.main()
