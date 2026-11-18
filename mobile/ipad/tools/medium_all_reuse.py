#!/usr/bin/env python3
"""Plans H.264 copies for Medium and All from the inventories, reusing existing copies by source sha256.

  python3 -I tools/medium_all_reuse.py OUT_JSON

Reads build/medium-all/inventory-{medium,all}.tsv and existing sidecar manifests (Small's build/video-compat/h264-v1,
and Medium's build/video-compat-medium/h264-v1 when present). An original is hashed only when its size equals the
source_bytes of an existing copy, so hundreds of GB are never read needlessly. Writes, per pack, the AV1/VP9 originals
with: reused-from (sidecar + sha256 confirmed) or needs-copy. Read-only on the packs.
"""
import csv, hashlib, json, os, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
PACKS = Path(os.environ.get('LASTBOOK_SOURCE', HERE.parents[1])) / 'derived/packs'
SIDECARS = [HERE / 'build/video-compat/h264-v1', HERE / 'build/video-compat-medium/h264-v1']


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(8 << 20), b''):
            h.update(b)
    return h.hexdigest()


def main(out):
    have = {}   # (bytes) -> list of (sidecar, item)
    for s in SIDECARS:
        mf = s / 'manifest.json'
        if mf.exists():
            for it in json.loads(mf.read_text())['items'].values():
                if (s / it['file']).exists() and (s / it['file']).stat().st_size == it['bytes']:
                    have.setdefault(it['source_bytes'], []).append((str(s.relative_to(HERE)), it))
    hashed = {}
    result = {}
    for pack in ['medium', 'all']:
        lib = PACKS / pack / 'library-data'
        rows = list(csv.DictReader(open(HERE / f'build/medium-all/inventory-{pack}.tsv'), delimiter='\t'))
        todo = []
        for r in sorted((r for r in rows if r['video'] in ('av01', 'vp09')), key=lambda r: int(r['bytes'])):
            n, reuse = int(r['bytes']), None
            for side, it in have.get(n, []):
                p = lib / r['path']
                key = (p.stat().st_ino, p.stat().st_dev, n)
                if key not in hashed:
                    hashed[key] = sha(p)
                if hashed[key] == it['source_sha256']:
                    reuse = {'sidecar': side, 'file': it['file'], 'bytes': it['bytes'], 'sha256': it['sha256']}
                    break
            todo.append({'id': r['id'], 'path': r['path'], 'bytes': n, 'video': r['video'], 'audio': r['audio'],
                         'duration': float(r['duration']), 'width': int(r['width']), 'height': int(r['height']),
                         'video_rate': int(r['video_rate']), 'reuse': reuse})
        result[pack] = todo
        av1 = [t for t in todo if t['video'] == 'av01']
        re_ = [t for t in av1 if t['reuse']]
        need = [t for t in av1 if not t['reuse']]
        vp9 = [t for t in todo if t['video'] == 'vp09']
        print(f"{pack}: av1 {len(av1)} ({sum(t['bytes'] for t in av1):,} B); reused by sha256 {len(re_)} "
              f"({sum(t['bytes'] for t in re_):,} B source, {sum(t['reuse']['bytes'] for t in re_):,} B copies); "
              f"need new {len(need)} ({sum(t['bytes'] for t in need):,} B, {sum(t['duration'] for t in need)/3600:.1f} h); "
              f"vp9 {len(vp9)} ({sum(t['bytes'] for t in vp9):,} B)")
    print(f"files hashed: {len(hashed)}  bytes hashed: {sum(k[2] for k in hashed):,}")
    Path(out).write_text(json.dumps(result, indent=1))


if __name__ == '__main__':
    main(sys.argv[1])
