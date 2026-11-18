#!/usr/bin/env python3
"""Parity check: the iPad engine (build/apidump) against the desktop server.py answering the same LastbookData clone.

  python3 tools/compare.py '/api/videos' '/api/map/tile/12/702/1635?v=1' ...
  python3 tools/compare.py -f tools/parity-paths.txt

Reference: a desktop server.py on 127.0.0.1:8960 started with --data build/LastbookData --no-index (a test clone, never a
real library). JSON is compared as data (key order ignored, floats to 1e-6). Binary answers are compared by sha256.
Exit 1 if any path differs.
"""
import hashlib, json, subprocess, sys, urllib.request, os
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REF = 'http://127.0.0.1:8960'
DATA = HERE / 'build' / 'LastbookData'
DESKTOP = os.environ.get('LASTBOOK_SOURCE', str(HERE.parents[1]))


def ref(path):
    try:
        with urllib.request.urlopen(REF + path, timeout=120) as r:
            return r.status, r.headers.get('Content-Type', ''), r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get('Content-Type', ''), e.read()


def ours(paths):
    import os
    out = subprocess.run([os.environ.get('APIDUMP_OUT') or str(HERE / 'build' / 'apidump'),str(DATA), DESKTOP, *[f'GET {p}' for p in paths]],
                         capture_output=True, text=True, check=True).stdout
    res = []
    # apidump prints "STATUS MSms PATH\nBODY" per path; bodies are one line (compact JSON or a binary summary)
    lines = out.rstrip('\n').split('\n')
    i = 0
    for p in paths:
        st, ms, _ = lines[i].split(' ', 2)
        res.append((int(st), ms, lines[i + 1] if i + 1 < len(lines) else ''))
        i += 2
    return res


def norm(v):
    if isinstance(v, float):
        return round(v, 6)
    if isinstance(v, dict):
        return {k: norm(x) for k, x in v.items()}
    if isinstance(v, list):
        return [norm(x) for x in v]
    return v


def first_diff(a, b, where='$'):
    if type(a) != type(b) and not (isinstance(a, (int, float)) and isinstance(b, (int, float))):
        return f'{where}: {type(a).__name__} {str(a)[:120]} != {type(b).__name__} {str(b)[:120]}'
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                return f'{where}.{k}: only in {"desktop" if k in a else "ipad"}'
            d = first_diff(a[k], b[k], f'{where}.{k}')
            if d:
                return d
        return None
    if isinstance(a, list):
        if len(a) != len(b):
            return f'{where}: {len(a)} items != {len(b)}'
        for i, (x, y) in enumerate(zip(a, b)):
            d = first_diff(x, y, f'{where}[{i}]')
            if d:
                return d
        return None
    if isinstance(a, float) or isinstance(b, float):
        return None if abs(a - b) <= 1e-6 * max(1, abs(a)) else f'{where}: {a} != {b}'
    return None if a == b else f'{where}: {str(a)[:120]} != {str(b)[:120]}'


def main(argv):
    paths = [l.strip() for l in open(argv[1]) if l.strip() and not l.startswith('#')] if argv[:1] == ['-f'] else argv
    bad = 0
    for p, (st, ms, body) in zip(paths, ours(paths)):
        rst, rmime, rbody = ref(p)
        if 'json' in rmime:
            try:
                d = first_diff(norm(json.loads(rbody)), norm(json.loads(body)))
            except ValueError as e:
                d = f'not JSON on ipad: {body[:200]}'
        elif rst == 204 or not rbody:
            d = None if st == rst else ''
        else:
            want = f'{len(rbody)} bytes sha256={hashlib.sha256(rbody).hexdigest()}'
            d = None if want in body else f'binary differs: desktop {rmime} {want} / ipad {body}'
        if st != rst:
            d = f'status {rst} != {st}' + (f'; {d}' if d else '')
        print(('ok   ' if d is None else 'DIFF ') + f'{p}  ({ms})' + ('' if d is None else f'\n     {d}'))
        bad += d is not None
    print(f'{len(paths) - bad}/{len(paths)} match')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
