#!/usr/bin/env python3
"""Independent check of a video-compat sidecar with ffmpeg (not AVFoundation, which built it).

  python3 tools/validate_videocompat.py LIBRARY_DATA SIDECAR_DIR [FFMPEG]

For every manifest item: the original still has its recorded size and sha256 (untouched); the copy has its recorded
size and sha256; container MP4 with 'moov' before 'mdat' (fast start); video h264 High; audio aac (LC) whenever the
original has audio, with the same sample rate and channels; same picture size; durations within 0.25 s; keyframes at
most ~2 s apart (seeking); the original's codec is the manifest's source_video (av01 or vp09). Every AV1 and VP9
original in the catalog has an item (the total line counts and lists the missing ones). Prints one line per item and a total; exit 1 on
any failure.
"""
import hashlib, json, re, struct, subprocess, sys
from pathlib import Path

SOURCE_CODECS = {'av01': 'av1', 'vp09': 'vp9'}   # manifest source_video -> ffmpeg's name
FFMPEG_DEFAULT = 'ffmpeg'


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(8 << 20), b''):
            h.update(b)
    return h.hexdigest()


def probe(ff, p):
    err = subprocess.run([ff, '-hide_banner', '-i', str(p)], capture_output=True, text=True).stderr
    dur = re.search(r'Duration: (\d+):(\d+):([\d.]+)', err)
    d = int(dur[1]) * 3600 + int(dur[2]) * 60 + float(dur[3]) if dur else None
    v = re.search(r'Stream #\S+.*?: Video: (\w+)(?: \(([^)]*)\))?.*?, (\d+)x(\d+)', err)
    a = re.search(r'Stream #\S+.*?: Audio: (\w+)(?: \(([^)]*)\))?.*?, (\d+) Hz, (\w+)', err)
    return {'dur': d, 'v': v and v[1], 'vprof': v and v[2], 'w': v and int(v[3]), 'h': v and int(v[4]),
            'a': a and a[1], 'aprof': a and a[2], 'rate': a and int(a[3]), 'ch': a and a[4], 'fmt': re.search(r"Input #0, ([\w,]+)", err)[1]}


def top_boxes(p):
    out = []
    with open(p, 'rb') as f:
        while True:
            h = f.read(8)
            if len(h) < 8:
                return out
            size, kind = struct.unpack('>I4s', h)
            if size == 1:
                size = struct.unpack('>Q', f.read(8))[0]
                f.seek(size - 16, 1)
            elif size == 0:
                out.append(kind.decode('latin1'))
                return out
            else:
                f.seek(size - 8, 1)
            out.append(kind.decode('latin1'))


def max_key_gap(ff, p):
    err = subprocess.run([ff, '-hide_banner', '-skip_frame', 'nokey', '-i', str(p), '-map', '0:v:0', '-vf', 'showinfo', '-f', 'null', '-'],
                         capture_output=True, text=True).stderr
    ts = [float(x) for x in re.findall(r'pts_time:([\d.]+)', err)]
    return max((b - a for a, b in zip(ts, ts[1:])), default=0.0), len(ts)


def main(lib, side, ff=FFMPEG_DEFAULT):
    lib, side = Path(lib), Path(side)
    m = json.loads((side / 'manifest.json').read_text())
    bad = 0
    for src, it in sorted(m['items'].items()):
        o, c = lib / src, side / it['file']
        po, pc = probe(ff, o), probe(ff, c)
        gap, keys = max_key_gap(ff, c)
        boxes = top_boxes(c)
        problems = []
        if o.stat().st_size != it['source_bytes'] or sha(o) != it['source_sha256']: problems.append('original changed')
        if c.stat().st_size != it['bytes'] or sha(c) != it['sha256']: problems.append('copy differs from manifest')
        want = SOURCE_CODECS.get(it.get('source_video'))
        if want is None or po['v'] != want: problems.append(f'original is {po["v"]}, manifest says {it.get("source_video")}')
        if 'mp4' not in pc['fmt']: problems.append(f'container {pc["fmt"]}')
        if 'moov' not in boxes or 'mdat' not in boxes or boxes.index('moov') > boxes.index('mdat'): problems.append(f'not fast-start {boxes}')
        if pc['v'] != 'h264' or 'High' not in (pc['vprof'] or ''): problems.append(f'video {pc["v"]} {pc["vprof"]}')
        if (po['w'], po['h']) != (pc['w'], pc['h']) and max(po['w'], po['h']) <= 1920: problems.append(f'size {pc["w"]}x{pc["h"]} vs {po["w"]}x{po["h"]}')
        if po['a']:
            if pc['a'] != 'aac' or 'LC' not in (pc['aprof'] or ''): problems.append(f'audio {pc["a"]} {pc["aprof"]}')
            if (pc['rate'], pc['ch']) != (po['rate'], po['ch']) and po['a'] == 'aac': problems.append(f'audio {pc["rate"]} {pc["ch"]} vs {po["rate"]} {po["ch"]}')
        elif pc['a']: problems.append('audio added')
        if po['dur'] is None or pc['dur'] is None or abs(po['dur'] - pc['dur']) > 0.25: problems.append(f'duration {pc["dur"]} vs {po["dur"]}')
        if gap > 2.1: problems.append(f'keyframe gap {gap:.2f}s')
        print(('ok   ' if not problems else 'FAIL ') + f'{it["id"]}  {po["dur"]:.1f}s  {it["source_bytes"]/1e6:.1f}->{it["bytes"]/1e6:.1f} MB  '
              f'{pc["w"]}x{pc["h"]} {pc["v"]}/{pc["a"]}  keys {keys} max gap {gap:.2f}s' + ('' if not problems else '  ' + '; '.join(problems)))
        bad += bool(problems)
    cat = json.loads((lib / 'catalog.json').read_text())
    local = [r for r in cat if r['kind'] == 'video' and (lib / r['path']).exists()]
    codec = {r['path']: probe(ff, lib / r['path'])['v'] for r in local}
    av1 = [r for r in local if codec[r['path']] == 'av1']
    vp9 = [r for r in local if codec[r['path']] == 'vp9']
    missing = [r['id'] for r in av1 + vp9 if r['path'] not in m['items']]
    shown = missing if len(missing) <= 10 else missing[:10] + [f'... {len(missing) - 10} more']
    print(f'local videos {len(local)}  av1 {len(av1)}  vp9 {len(vp9)}  copies {len(m["items"])}  missing {len(missing)} {shown}  '
          f'added {sum(i["bytes"] for i in m["items"].values())} bytes  failures {bad}')
    return 1 if bad or missing else 0


if __name__ == '__main__':
    sys.exit(main(*sys.argv[1:]))
