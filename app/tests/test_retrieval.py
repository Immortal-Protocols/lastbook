"""Meaning-based search (retrieval.Index.semantic): per-document filtering. Small made-up index, no real library, no model.
Never packaged."""
import io, os, sys, tempfile, unittest
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


class EmbedProviders(unittest.TestCase):
    """Provider layers for the index build (CUDA, then DirectML, then CPU), with no GPU and no GPU onnxruntime needed."""
    CPU = ['CPUExecutionProvider']
    CUDA = ['CUDAExecutionProvider', 'CPUExecutionProvider']
    DML = ['DmlExecutionProvider', 'CPUExecutionProvider']
    ALL = ['CUDAExecutionProvider', 'DmlExecutionProvider', 'CPUExecutionProvider']

    def pick(self, offered, gpu, env=None):
        with mock.patch.dict(os.environ):
            os.environ.pop('LASTBOOK_EMBED_DEVICE', None)
            if env is not None:
                os.environ['LASTBOOK_EMBED_DEVICE'] = env
            return retrieval.embed_layers(offered, gpu)

    def test_layers_in_order_when_asked_and_offered(self):
        self.assertEqual(self.pick(self.ALL, True), [self.CUDA, self.DML, self.CPU])
        self.assertEqual(self.pick(self.CUDA, True), [self.CUDA, self.CPU])
        self.assertEqual(self.pick(self.DML, True), [self.DML, self.CPU])
        self.assertEqual(self.pick(self.CPU, True), [self.CPU])
        self.assertEqual(self.pick(self.ALL, False), [self.CPU])  # the running app never takes a GPU

    def test_environment_choice(self):
        for v in ('cpu', 'CPU', ' cpu ', 'vulkan'):
            self.assertEqual(self.pick(self.ALL, True, v), [self.CPU])
        for v in ('', 'auto'):
            self.assertEqual(self.pick(self.ALL, True, v), [self.CUDA, self.DML, self.CPU])
        self.assertEqual(self.pick(self.ALL, True, 'cuda'), [self.CUDA, self.CPU])
        self.assertEqual(self.pick(self.ALL, True, 'DirectML'), [self.DML, self.CPU])
        self.assertEqual(self.pick(self.CPU, True, 'directml'), [self.CPU])  # asked for but not offered

    def embedder(self, gpu, offered=None, fails=()):
        """Build an Embedder against a stubbed onnxruntime. Returns it, the (providers, options) asked for, the stub and
        stdout. A session whose first provider is in fails raises."""
        asked = []

        class Sess:
            def __init__(self, path, so, providers):
                asked.append((providers, so))
                if providers[0] in fails:
                    raise RuntimeError(f'{providers[0]} library not found')
                self.providers = providers
            def get_providers(self): return self.providers
            def get_inputs(self): return []

        class Tok:
            def enable_truncation(self, **k): pass
            def enable_padding(self): pass

        fake_ort = mock.Mock(SessionOptions=lambda: mock.Mock(spec=['intra_op_num_threads', 'enable_mem_pattern', 'execution_mode']),
                             InferenceSession=Sess, get_available_providers=lambda: offered or self.ALL)
        with mock.patch.object(retrieval, 'ort', fake_ort, create=True), \
                mock.patch.object(retrieval, 'Tokenizer', mock.Mock(from_file=lambda p: Tok()), create=True), \
                mock.patch.dict(os.environ), mock.patch('sys.stdout', new_callable=io.StringIO) as out:
            os.environ.pop('LASTBOOK_EMBED_DEVICE', None)
            return retrieval.Embedder(gpu=gpu), asked, fake_ort, out.getvalue()

    def test_embedder_takes_the_first_layer(self):
        self.assertEqual(self.embedder(True)[0].provider, 'CUDAExecutionProvider')
        self.assertEqual(self.embedder(True, offered=self.DML)[0].provider, 'DmlExecutionProvider')
        self.assertEqual(self.embedder(False)[0].provider, 'CPUExecutionProvider')

    def test_cuda_libraries_are_preloaded_only_for_cuda(self):
        _, _, ort, out = self.embedder(True)
        ort.preload_dlls.assert_called_once_with()
        self.assertIn('embedding with CUDAExecutionProvider', out)
        for gpu, offered in ((True, self.DML), (False, None)):
            _, _, ort, _ = self.embedder(gpu, offered=offered)
            ort.preload_dlls.assert_not_called()
        self.assertEqual(self.embedder(False)[3], '')  # the running app prints nothing

    def test_directml_session_options(self):
        _, asked, ort, _ = self.embedder(True, offered=self.DML)
        (providers, so), = asked
        self.assertEqual(providers, self.DML)
        self.assertIs(so.enable_mem_pattern, False)
        self.assertIs(so.execution_mode, ort.ExecutionMode.ORT_SEQUENTIAL)
        (_, so), = self.embedder(False)[1]
        self.assertIsNot(so.enable_mem_pattern, False)  # CPU: left as onnxruntime sets it
        self.assertIsNot(so.execution_mode, ort.ExecutionMode.ORT_SEQUENTIAL)

    def test_a_failing_layer_falls_through_to_the_next(self):
        emb, asked, _, out = self.embedder(True, fails={'CUDAExecutionProvider'})
        self.assertEqual([p for p, _ in asked], [self.CUDA, self.DML])
        self.assertEqual(emb.provider, 'DmlExecutionProvider')
        self.assertIn('CUDAExecutionProvider could not start (RuntimeError: CUDAExecutionProvider library not found); trying the next', out)
        emb, asked, _, out = self.embedder(True, fails={'CUDAExecutionProvider', 'DmlExecutionProvider'})
        self.assertEqual([p for p, _ in asked], [self.CUDA, self.DML, self.CPU])
        self.assertEqual(emb.provider, 'CPUExecutionProvider')
        self.assertIn('embedding with CPUExecutionProvider', out)

    def test_a_failing_cpu_session_still_raises(self):
        with self.assertRaises(RuntimeError):
            self.embedder(False, fails={'CPUExecutionProvider'})


if __name__ == '__main__':
    unittest.main()
