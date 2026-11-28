#!/usr/bin/env python3
"""How fast, and how exactly, this computer makes meaning-index vectors on each layer the index build can use.

    python tools/embed_bench.py [--data FOLDER] [--n 2000] [--batch 48] [--gpu "card name"] [--json out.json]

It takes --n passages spread evenly through the meaning index that is already in the data folder (--data, else
LASTBOOK_DATA, else the app's own), and embeds them with retrieval.Embedder, the class `python retrieval.py` builds
the index with: first on the CPU, then on every GPU layer the installed onnxruntime offers (CUDA with onnxruntime-gpu,
DirectML with onnxruntime-directml). For each layer it prints passages per second, an estimate of the model step for the
whole index, and how close the vectors are to the CPU ones (cosine; nearest and 10 nearest passages within the sample).
The first batch of each layer is not timed.

The index is opened read-only and nothing is written to the data folder. The printed table and the JSON hold no paths.
Close other heavy programs first; the CPU layer uses half the logical cores, as the build does.
"""
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


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--data', help='data folder (the one that holds derived/index); default LASTBOOK_DATA or the app\'s')
    ap.add_argument('--n', type=int, default=2000, help='passages to embed (default 2000)')
    ap.add_argument('--batch', type=int, default=48, help='passages per call (default 48, as the build)')
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
    db = sqlite3.connect(ro_uri(db_path), uri=True)
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
        row = {'layer': name, 'provider': emb.provider, 'passages_per_s': round(len(texts) / dt, 1),
               'model_step_estimate_min': round(total / (len(texts) / dt) / 60, 1)}
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
    print('| Layer | Passages/s | Model step, whole index (est.) | Lowest cosine vs CPU | Median | Nearest same | 10 nearest overlap |')
    print('|---|---|---|---|---|---|---|')
    for r in rows:
        if 'error' in r:
            print(f'| {r["layer"]} | {r["error"]} | | | | | |'); continue
        c = (f'{r["cos_min"]:.6f} | {r["cos_median"]:.6f} | {r["nearest_same"]:.1%} | {r["top10_overlap"]:.1%}'
             if 'cos_min' in r else '(reference) | | |')
        print(f'| {r["layer"]} | {r["passages_per_s"]} | {r["model_step_estimate_min"]} min | {c} |')
    if a.json:
        Path(a.json).write_text(json.dumps({'system': info, 'layers': rows}, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
