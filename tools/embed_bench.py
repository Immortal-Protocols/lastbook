#!/usr/bin/env python3
"""How fast, and how exactly, this computer makes meaning-index vectors on each layer the index build can use.

    python tools/embed_bench.py [--data FOLDER] [--n 2000] [--batch 48] [--gpu "card name"] [--json out.json]

It takes --n passages spread evenly through the meaning index that is already in the data folder (--data, else
LASTBOOK_DATA, else the app's own), and embeds them with retrieval.Embedder, the class `python retrieval.py` builds
the index with: first on the CPU, then on every GPU layer the installed onnxruntime offers (CUDA with onnxruntime-gpu,
DirectML with onnxruntime-directml). For each layer it prints passages per second, an estimate of the model step for the
whole index, and how close the vectors are to the CPU ones (cosine; nearest and 10 nearest passages within the sample).
The first batch of each layer is not timed.

The rest of the build does not depend on the layer: reading each document, cutting it into passages and writing them.
The tool times that on --docs documents spread through the library, with the build's own reading code, writing into a
temporary folder as the build writes into the index, and scales it to the whole index. Whole build = model step + rest.
Documents read recently may still be in the system's file cache, which makes this part look faster than a cold build.

The estimates are rough. On the one computer where they could be checked against timed full builds they were off by up to
a third, in both directions, and how they should be corrected is not known from one computer. Reports with a timed build
(`python retrieval.py` on a fresh data folder) next to this tool's output are what would make them better.

Nothing is written to the data folder. The index is read as immutable, so SQLite does not touch its -wal and -shm files
either; for that reason the tool first checks that no build or running Lastbook is writing to it, and stops if one is.
The printed table and the JSON hold no paths. Close other heavy programs first; the CPU layer uses half the logical
cores, as the build does.
"""

NOTE = ('Estimates are rough: checked against timed builds on one computer only, they were off by up to a third. '
        'A timed build next to these numbers is the most useful report.')
import argparse, json, os, platform, sqlite3, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def onnxruntime_package():
    from importlib import metadata
    for name in ('onnxruntime-gpu', 'onnxruntime-directml', 'onnxruntime'):
        try:
            return f'{name} {metadata.version(name)}'
        except metadata.PackageNotFoundError:
            pass
    return 'unknown'


def index_in_use(idx):
    """Why the meaning index in folder idx cannot be read safely now, or None. The tool reads it as immutable (SQLite
    then never touches its -wal or -shm files), which is only right while nothing else is writing to it."""
    from engine.paths import try_lock, unlock
    wal = idx / 'semantic.sqlite-wal'
    if wal.is_file() and wal.stat().st_size > 0:
        return 'the index has changes not yet folded into it (semantic.sqlite-wal is not empty): close Lastbook and try again'
    lock = idx / 'indexer.lock'
    if lock.is_file():
        with open(lock, 'rb') as f:  # read-only handle: testing the lock changes nothing
            try:
                try_lock(f)
            except OSError:
                return 'a build or Lastbook is adding to the index right now (indexer.lock is held): wait for it or close it'
            unlock(f)
    return None


def rest_of_build(retrieval, n_docs):
    """Time the build's other work on a sample of documents: reading and cutting them into passages (the build's own
    sources() and _texts()) and writing the rows and vectors as the build does, one transaction per document, into a
    temporary folder. Returns seconds per passage and what was sampled."""
    import tempfile
    import numpy as np
    sys.path.insert(0, str(retrieval.lastbook_paths.APP))
    import server
    ix = retrieval.Index.__new__(retrieval.Index)  # Index() would create tables in the data folder; these two methods need only:
    ix.catalog_fn, ix.trust_fn, ix.fts_db = server.catalog, server.trust, server.library.DB
    ix._excl = {'mtime': None, 'ids': set()}
    t0 = time.perf_counter()
    srcs = ix.sources()
    secs, passages, failed = time.perf_counter() - t0, 0, 0
    sample = srcs[::max(1, len(srcs) // n_docs)][:n_docs]
    with tempfile.TemporaryDirectory() as tmp:
        db = sqlite3.connect(os.path.join(tmp, 'semantic.sqlite'), isolation_level=None)
        db.execute('PRAGMA journal_mode=WAL')
        db.executescript('CREATE TABLE chunk(id INTEGER PRIMARY KEY, doc_id TEXT, page INTEGER, t REAL, text TEXT, active INTEGER DEFAULT 1);'
                         'CREATE INDEX chunk_doc ON chunk(doc_id);'
                         'CREATE TABLE docstate(doc_id TEXT PRIMARY KEY, sig TEXT, nchunks INTEGER, at REAL);')
        vec_path, start = os.path.join(tmp, 'vectors.f16'), 1
        for doc_id, sig, _, how in sample:
            t0 = time.perf_counter()
            try:
                parts = ix._texts(doc_id, how)
            except Exception:
                parts, failed = [], failed + 1
            v = np.zeros((len(parts), retrieval.DIM), dtype=np.float16)

            def w(db):
                db.execute('UPDATE chunk SET active=0 WHERE doc_id=?', (doc_id,))
                db.executemany('INSERT INTO chunk(id,doc_id,page,t,text,active) VALUES (?,?,?,?,?,1)',
                               [(start + j, doc_id, p[0], p[1], p[2]) for j, p in enumerate(parts)])
                db.execute('INSERT OR REPLACE INTO docstate VALUES (?,?,?,?)', (doc_id, sig, len(parts), time.time()))
                with open(vec_path, 'ab') as f:
                    f.write(v.tobytes())
            retrieval.Index.tx(db, w)
            secs += time.perf_counter() - t0
            start += len(parts)
            passages += len(parts)
        db.close()
    return {'documents_sampled': len(sample), 'documents': len(srcs), 'passages_sampled': passages,
            'unreadable_sampled': failed, 'seconds': round(secs, 1),
            'ms_per_passage': round(1000 * secs / passages, 3) if passages else None}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--data', help='data folder (the one that holds derived/index); default LASTBOOK_DATA or the app\'s')
    ap.add_argument('--n', type=int, default=2000, help='passages to embed (default 2000)')
    ap.add_argument('--batch', type=int, default=48, help='passages per call (default 48, as the build)')
    ap.add_argument('--docs', type=int, default=300, help='documents to read for the rest of the build (default 300; 0 skips it)')
    ap.add_argument('--gpu', default='', help='the graphics card, as you would name it, for the report')
    ap.add_argument('--json', help='also write the results to this file')
    a = ap.parse_args()
    if a.data:
        os.environ['LASTBOOK_DATA'] = a.data
    sys.path.insert(0, str(ROOT))
    import numpy as np
    import retrieval
    from engine.paths import ro_uri
    if not retrieval.AVAILABLE:
        sys.exit('The meaning model is not in this data folder (derived/models/bge-small-en-v1.5), '
                 f'or onnxruntime could not load: {getattr(retrieval, "IMPORT_ERROR", "")}')
    db_path = retrieval.IDX / 'semantic.sqlite'
    if not db_path.is_file():
        sys.exit('No meaning index in this data folder (derived/index/semantic.sqlite). Pass --data or set LASTBOOK_DATA.')
    busy = index_in_use(retrieval.IDX)
    if busy:
        sys.exit(f'Not measuring: {busy}.')
    db = sqlite3.connect(ro_uri(db_path) + '&immutable=1', uri=True)
    ids = [r[0] for r in db.execute('SELECT id FROM chunk WHERE active=1 ORDER BY id')]
    if not ids:
        sys.exit('The meaning index has no passages yet.')
    total = len(ids)
    pick = ids[::max(1, total // a.n)][:a.n]
    texts = [db.execute('SELECT text FROM chunk WHERE id=?', (i,)).fetchone()[0] for i in pick]
    db.close()

    offered = retrieval.ort.get_available_providers()
    layers = ['cpu'] + [name for name, p in retrieval.GPU_LAYERS if p in offered]
    info = {'os': f'{platform.system()} {platform.release()}', 'machine': platform.machine(), 'cpu': platform.processor(),
            'logical_cores': os.cpu_count(), 'python': platform.python_version(), 'onnxruntime': onnxruntime_package(),
            'offered': offered, 'gpu': a.gpu, 'passages': len(texts), 'index_passages': total, 'batch': a.batch}
    print(json.dumps(info), flush=True)

    rest = rest_of_build(retrieval, a.docs) if a.docs > 0 else None
    rest_min = round(rest['ms_per_passage'] * total / 60000, 1) if rest and rest['ms_per_passage'] else None
    if rest:
        rest['estimate_min'] = rest_min
        print(json.dumps({'rest_of_build': rest}), flush=True)

    rows, ref = [], None
    for name in layers:
        os.environ['LASTBOOK_EMBED_DEVICE'] = name
        try:
            emb = retrieval.Embedder(gpu=True)
        except Exception as e:
            rows.append({'layer': name, 'error': f'{type(e).__name__}: {e}'}); continue
        want = 'CPUExecutionProvider' if name == 'cpu' else dict(retrieval.GPU_LAYERS)[name]
        if emb.provider != want:
            rows.append({'layer': name, 'error': f'did not start (got {emb.provider})'}); continue
        emb.embed(texts[:a.batch])
        t0 = time.perf_counter()
        v = np.vstack([emb.embed(texts[i:i + a.batch]) for i in range(0, len(texts), a.batch)])
        dt = time.perf_counter() - t0
        model_min = round(total / (len(texts) / dt) / 60, 1)
        row = {'layer': name, 'provider': emb.provider, 'passages_per_s': round(len(texts) / dt, 1),
               'model_step_estimate_min': model_min,
               'build_estimate_min': round(model_min + rest_min, 1) if rest_min is not None else None}
        del emb
        if ref is None:
            ref = v
            s_ref = ref @ ref.T; np.fill_diagonal(s_ref, -1); top_ref = np.argsort(-s_ref, 1)[:, :10]
        else:
            cos = (v * ref).sum(1)
            s = v @ v.T; np.fill_diagonal(s, -1); top = np.argsort(-s, 1)[:, :10]
            row.update(cos_min=float(cos.min()), cos_p1=float(np.percentile(cos, 1)), cos_median=float(np.median(cos)),
                       max_abs_diff=float(np.abs(v - ref).max()),
                       nearest_same=float(np.mean(top[:, 0] == top_ref[:, 0])),
                       top10_overlap=float(np.mean([len(set(x) & set(y)) / 10 for x, y in zip(top, top_ref)])))
        rows.append(row)
        print(json.dumps(row), flush=True)

    print(f'\n{info["os"]}, {info["cpu"] or info["machine"]} ({info["logical_cores"]} logical cores)'
          f'{", " + a.gpu if a.gpu else ""}; {info["onnxruntime"]}; {len(texts)} of {total} passages, batch {a.batch}\n')
    if rest:
        print(f'Rest of the build (reading, cutting into passages, writing), from {rest["documents_sampled"]} of '
              f'{rest["documents"]} documents: {rest["ms_per_passage"]} ms a passage, about {rest_min} min for the whole '
              'index, the same on every layer.\n')
    print('| Layer | Passages/s | Model step (est.) | Whole build (est.) | Lowest cosine vs CPU | Median | Nearest same | 10 nearest overlap |')
    print('|---|---|---|---|---|---|---|---|')
    for r in rows:
        if 'error' in r:
            print(f'| {r["layer"]} | {r["error"]} | | | | | | |'); continue
        c = (f'{r["cos_min"]:.6f} | {r["cos_median"]:.6f} | {r["nearest_same"]:.1%} | {r["top10_overlap"]:.1%}'
             if 'cos_min' in r else '(reference) | | |')
        b = f'{r["build_estimate_min"]} min' if r['build_estimate_min'] is not None else ''
        print(f'| {r["layer"]} | {r["passages_per_s"]} | {r["model_step_estimate_min"]} min | {b} | {c} |')
    print(f'\n{NOTE}')
    if a.json:
        Path(a.json).write_text(json.dumps({'system': info, 'rest_of_build': rest, 'layers': rows, 'note': NOTE}, indent=1),
                                encoding='utf-8')


if __name__ == '__main__':
    main()
