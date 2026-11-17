#!/usr/bin/env python3
"""Zips a library's H.264 video copies (tools/videocompat output, e.g. build/video-compat/h264-v1) for the iPad installer:
LastbookData/derived/video-compat/h264-v1/{manifest.json,<video id>.mp4}, stored (MP4 does not compress further).
Only the files the manifest lists, each checked at its size, are included.

  python3 tools/make_video_copies_zip.py build/video-compat/h264-v1 OUT.zip [--only N]
"""
import json, sys, zipfile
from pathlib import Path

src, out = Path(sys.argv[1]), Path(sys.argv[2])
only = int(sys.argv[sys.argv.index('--only') + 1]) if '--only' in sys.argv else None
m = json.loads((src / 'manifest.json').read_text(encoding='utf-8'))
assert m.get('version') == 'h264-v1', 'not an h264-v1 manifest'
items = dict(sorted(m['items'].items())[:only] if only else m['items'].items())
for it in items.values():
    f = src / it['file']
    assert '/' not in it['file'] and f.stat().st_size == it['bytes'], f'{f} missing or the wrong size'
m = {**m, 'items': items}
base = 'LastbookData/derived/video-compat/h264-v1/'
tmp = out.with_suffix('.partial')
with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_STORED, allowZip64=True) as z:
    z.writestr(base + 'manifest.json', json.dumps(m, indent=2, sort_keys=True))
    for it in items.values():
        z.write(src / it['file'], base + it['file'])
tmp.replace(out)
print(out, out.stat().st_size, 'bytes,', len(items), 'copies')
