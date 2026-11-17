#!/usr/bin/env python3
"""Summarises build/medium-all/inventory-<pack>.tsv (from tools/videoinventory) for status notes.

  python3 tools/medium_all_summary.py build/medium-all/inventory-medium.tsv [SMALL_SIDECAR_MANIFEST]

Counts by video/audio codec, bytes and durations; with Small's sidecar manifest, the AV1 originals whose path and size
match a Small copy (reuse candidates; reuse itself is decided by sha256 elsewhere).
"""
import csv, json, sys
from collections import Counter, defaultdict

rows = list(csv.DictReader(open(sys.argv[1]), delimiter='\t'))
small = json.load(open(sys.argv[2]))['items'] if len(sys.argv) > 2 else {}
by = defaultdict(lambda: [0, 0, 0.0])
pairs = Counter()
res = Counter()
for r in rows:
    b = by[r['video']]
    b[0] += 1; b[1] += int(r['bytes']); b[2] += float(r['duration'])
    pairs[(r['video'], r['audio'])] += 1
    res[(r['video'], f"{r['width']}x{r['height']}")] += 1
print(f"videos {len(rows)}  bytes {sum(int(r['bytes']) for r in rows):,}  hours {sum(float(r['duration']) for r in rows)/3600:.1f}")
for k, (n, b, d) in sorted(by.items(), key=lambda x: -x[1][0]):
    print(f"  video {k:6} {n:5}  {b:,} bytes  {d/3600:.1f} h")
for (v, a), n in sorted(pairs.items(), key=lambda x: -x[1]):
    print(f"  pair {v}+{a}: {n}")
print('  resolutions:', ', '.join(f'{v} {r}: {n}' for (v, r), n in res.most_common(12)))
av1 = [r for r in rows if r['video'] == 'av01']
cand = [r for r in av1 if r['path'] in small and small[r['path']]['source_bytes'] == int(r['bytes'])]
print(f"av1 {len(av1)}  {sum(int(r['bytes']) for r in av1):,} bytes; Small-copy candidates by path+size {len(cand)} "
      f"({sum(int(r['bytes']) for r in cand):,} bytes)")
rest = [r for r in av1 if r not in cand]
print(f"av1 needing new copies {len(rest)}  {sum(int(r['bytes']) for r in rest):,} bytes  "
      f"{sum(float(r['duration']) for r in rest)/3600:.1f} h")
