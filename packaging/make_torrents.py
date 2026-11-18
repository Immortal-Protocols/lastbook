#!/usr/bin/env python3
"""Writes a BitTorrent file for each published pack, state map and address index, so people can share the downloads.

  python3 -I -B packaging/make_torrents.py --files /path/to/published [--manifest derived/release/setup/manifest-v1.json]
                                           [--out derived/release/torrents] [--tracker URL ...] [--only NAME ...] [--piece-mib N]

One single-file torrent per file in the manifest, named <file>.torrent. Each is a hybrid of BitTorrent v1 and v2 (BEP 52),
so old and new clients both read it, and lists the file's own address on downloads.lastbook.org as a web seed (BEP 19):
a client with no other peers fetches from there, so a torrent is never slower than the plain download. No tracker is
listed unless --tracker is given; clients find each other through DHT. The output is the same every time for the same
file and options (no creation date or creator), so a torrent can be rebuilt and compared.

The piece length is the smallest power of two from 256 KiB that keeps a file to about 4,096 pieces, up to 64 MiB (the All
pack: 64 MiB, 5,780 pieces). --piece-mib sets one length for every file instead, for example to match a downloader's segment.

Each file is read once. The same pass computes the v1 and v2 piece hashes and the file's SHA-256, and the torrent is
written only when that SHA-256 and the size match the manifest. torrents.json beside the torrents lists each one's
info-hashes and magnet link, for the download page, and the pin a manifest file entry could carry:
{"torrent": {"url": <file url>.torrent, "pieces_root", "infohash_v2", "piece_length"}}. Upload each torrent next to its file.

The local AI model is left out: it is published by its makers on Hugging Face, not on downloads.lastbook.org.
This script is a release tool. It is never packaged, and the app knows nothing about torrents: a person who downloads a
pack with a torrent client chooses the zip in setup ("Choose a library zip or AI model file"), which checks it as usual.
"""
import argparse
import hashlib
import json
import sys
import threading
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT)]
from engine.setup import manifest        # noqa: E402

BLOCK = 16 * 1024                       # BEP 52: v2 hashes 16 KiB blocks
MIN_PIECE = 256 * 1024
MAX_PIECE = 64 * 1024 * 1024
TARGET_PIECES = 4096                    # the smallest piece length, a power of two, that keeps a file to about this many pieces
ZERO = bytes(32)


def bencode(v):
    if isinstance(v, bool):
        raise TypeError('bencode has no booleans')
    if isinstance(v, int):
        return b'i%de' % v
    if isinstance(v, str):
        v = v.encode('utf-8')
    if isinstance(v, bytes):
        return b'%d:%s' % (len(v), v)
    if isinstance(v, list):
        return b'l' + b''.join(bencode(x) for x in v) + b'e'
    if isinstance(v, dict):
        items = sorted((k.encode('utf-8') if isinstance(k, str) else k, x) for k, x in v.items())
        return b'd' + b''.join(bencode(k) + bencode(x) for k, x in items) + b'e'
    raise TypeError(f'cannot bencode {type(v).__name__}')


def piece_length(size):
    n = MIN_PIECE
    while n < MAX_PIECE and size > n * TARGET_PIECES:
        n *= 2
    return n


def _pow2(n):
    p = 1
    while p < n:
        p *= 2
    return p


def merkle_root(hashes, leaves, pad=ZERO):
    """The root of a balanced binary SHA-256 tree over hashes, padded with pad to leaves (a power of two) entries."""
    layer = list(hashes) + [pad] * (leaves - len(hashes))
    while len(layer) > 1:
        layer = [hashlib.sha256(layer[i] + layer[i + 1]).digest() for i in range(0, len(layer), 2)]
    return layer[0]


def pad_root(leaves):
    """The root of a subtree of leaves all-zero leaf hashes: what stands in for a piece past the end of the file."""
    h = ZERO
    while leaves > 1:
        h, leaves = hashlib.sha256(h + h).digest(), leaves // 2
    return h


class Hashed:
    """What one read of a file gives: v1 piece hashes, v2 piece layer and pieces root, the file's SHA-256."""

    def __init__(self, path, plen, progress=lambda done, total: None):
        size = path.stat().st_size
        self.size, self.plen = size, plen
        whole, v1, layer, blocks_all = hashlib.sha256(), [], [], []
        per_piece = plen // BLOCK
        done = 0
        with open(path, 'rb') as f:
            while True:
                piece = f.read(plen)
                if not piece:
                    break
                t = threading.Thread(target=whole.update, args=(piece,))   # hashlib lets go of the GIL: the file's SHA-256 runs beside the pieces
                t.start()
                v1.append(hashlib.sha1(piece).digest())
                blocks = [hashlib.sha256(piece[i:i + BLOCK]).digest() for i in range(0, len(piece), BLOCK)]
                if size <= plen:
                    blocks_all = blocks
                else:
                    layer.append(merkle_root(blocks, per_piece))
                t.join()
                done += len(piece)
                progress(done, size)
        if done != size:
            raise OSError(f'{path.name} changed while it was read')
        self.sha256 = whole.hexdigest()
        self.pieces = b''.join(v1)
        if size == 0:
            self.root, self.layer = None, b''
        elif size <= plen:            # one piece: the tree is over the blocks alone, and there is no piece layer
            self.root, self.layer = merkle_root(blocks_all, _pow2(len(blocks_all))), b''
        else:
            self.root, self.layer = merkle_root(layer, _pow2(len(layer)), pad_root(per_piece)), b''.join(layer)


def torrent(name, url, h, trackers=()):
    info = {'name': name, 'length': h.size, 'piece length': h.plen, 'pieces': h.pieces, 'meta version': 2,
            'file tree': {name: {'': {'length': h.size, **({'pieces root': h.root} if h.root else {})}}}}
    t = {'info': info, 'url-list': [url]}
    if h.layer:
        t['piece layers'] = {h.root: h.layer}
    if trackers:
        t['announce'] = trackers[0]
        t['announce-list'] = [[x] for x in trackers]
    raw = bencode(info)
    return bencode(t), hashlib.sha1(raw).hexdigest(), hashlib.sha256(raw).hexdigest()


def check_piece_length(n):
    if n < BLOCK or n & (n - 1):
        raise ValueError('the piece length must be a power of two of at least 16 KiB')
    return n


def magnet(name, size, btih, btmh, url, trackers=()):
    q = [('xt', f'urn:btih:{btih}'), ('xt', f'urn:btmh:1220{btmh}'), ('dn', name), ('xl', str(size)), ('ws', url)]
    q += [('tr', x) for x in trackers]
    return 'magnet:?' + '&'.join(f'{k}={urllib.parse.quote(v, safe=":/")}' for k, v in q)


def entries(m):
    """(name, url, size, sha256) for each published file: packs, state maps and address indexes, in manifest order."""
    seen = set()
    for key in ('packs', 'maps', 'address_indexes'):
        for x in m.get(key) or []:
            for f in x.get('files') or []:
                if f['name'] not in seen:
                    seen.add(f['name'])
                    yield f['name'], f['url'], f['size'], f['sha256']


class Progress:
    def __init__(self, name, every=10.0):
        self.name, self.every, self.start, self.last = name, every, time.monotonic(), 0.0

    def __call__(self, done, total):
        now = time.monotonic()
        if now - self.last < self.every and done < total:
            return
        self.last = now
        rate = done / max(now - self.start, 1e-6)
        left = (total - done) / rate if rate else 0
        unit, div = ('GB', 1e9) if total >= 1e9 else ('MB', 1e6)
        print(f'  {self.name}: {done / div:.1f} of {total / div:.1f} {unit}, {rate / 1e6:.0f} MB/s, {left / 60:.0f} min left',
              file=sys.stderr, flush=True)


def build(m, files, out, trackers=(), only=None, progress=Progress, plen=None):
    """Writes out/<name>.torrent for each file and out/torrents.json. Returns the list of problems (empty when all went well)."""
    out.mkdir(parents=True, exist_ok=True)
    listing, problems = [], []
    for name, url, size, sha in entries(m):
        if only and name not in only:
            continue
        path = files / name
        if not path.is_file():
            problems.append(f'{name}: not in {files}')
            continue
        if not size:
            problems.append(f'{name}: empty, and an empty file has no torrent')
            continue
        if path.stat().st_size != size:
            problems.append(f'{name}: {path.stat().st_size} bytes, the manifest says {size}')
            continue
        h = Hashed(path, plen or piece_length(size), progress(name))
        if h.sha256 != sha:
            problems.append(f'{name}: SHA-256 {h.sha256}, the manifest says {sha}')
            continue
        data, btih, btmh = torrent(name, url, h, trackers)
        (out / f'{name}.torrent').write_bytes(data)
        listing.append({'name': name, 'torrent': f'{name}.torrent', 'size': size, 'sha256': sha, 'btih': btih, 'btmh': '1220' + btmh,
                        'magnet': magnet(name, size, btih, btmh, url, trackers),
                        'pin': {'torrent': {'url': url + '.torrent', 'pieces_root': h.root.hex(), 'infohash_v2': btmh, 'piece_length': h.plen}}})
        print(f'{name}.torrent  btih {btih}', flush=True)
    if listing:
        (out / 'torrents.json').write_text(json.dumps({'version': 1, 'torrents': listing}, indent=1) + '\n', encoding='utf-8')
    return problems


def main():
    ap = argparse.ArgumentParser(description='Torrents for the published packs, state maps and address indexes.')
    ap.add_argument('--files', required=True, help='the folder holding the published files, by their manifest names')
    ap.add_argument('--manifest', default=str(ROOT / 'derived' / 'release' / 'setup' / 'manifest-v1.json'))
    ap.add_argument('--out', default=str(ROOT / 'derived' / 'release' / 'torrents'))
    ap.add_argument('--tracker', action='append', default=[], help='a tracker to list (repeat for more); none by default')
    ap.add_argument('--only', action='append', help='just this file name (repeat for more)')
    ap.add_argument('--piece-mib', type=int, help='one piece length for every file, in MiB (a power of two)')
    a = ap.parse_args()
    plen = None
    if a.piece_mib:
        try:
            plen = check_piece_length(a.piece_mib * 2 ** 20)
        except ValueError as e:
            sys.exit(str(e))
    m = manifest.validate(json.loads(Path(a.manifest).read_text(encoding='utf-8')))
    if m is None:
        sys.exit(f'{a.manifest} does not pass engine/setup/manifest.validate')
    problems = build(m, Path(a.files), Path(a.out), tuple(a.tracker), set(a.only) if a.only else None, plen=plen)
    for p in problems:
        print('not written: ' + p, file=sys.stderr)
    sys.exit(1 if problems else 0)


if __name__ == '__main__':
    main()
