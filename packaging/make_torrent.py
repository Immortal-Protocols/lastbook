#!/usr/bin/env python3
"""Makes the hybrid (BitTorrent v1 and v2) torrents of published files, and pins them in the manifest (docs/DOWNLOAD-SHARING.md).

At release, one command for a whole release folder, after publish-packs has written the packs file:

  python3 -I -B packaging/make_torrent.py --release derived/release/<release> --manifest derived/release/manifest-v1.json
                                          [--release <another folder>] [--piece-mib 16] [--tracker udp://...] [--force]

For each file the packs file lists (packs, maps, address indexes) that is in one of those folders, it checks the file's size and
SHA-256 against its entry, writes <file>.torrent beside it, and pins it in that entry; packaging/release_manifest.py then carries
the pin into the app. Each file is read once. A file already pinned, with its .torrent beside it and adding up to the pin, is
left as it is (--force makes it again). The packs file is saved after each file, so a long run that stops keeps what it made.
At the end it lists the torrents to upload, each next to its file, at <file's url>.torrent. A file whose SHA-256 is not the
pinned one stops the run before anything is written for it: it is not the published file.

One file:

  python3 -I -B packaging/make_torrent.py derived/release/<release>/Lastbook-All.zip --url https://downloads.lastbook.org/Lastbook-All.zip
                                          [--manifest derived/release/manifest-v1.json]

Each torrent's web seed (BEP 19) is the file's own address, so a swarm always has a seed, and it has no creation date, so the same
file always gives the same torrent: anyone with the file can make it again and compare. The app trusts a torrent only as far as
it matches the pinned info-hash and pieces root, and the file only as far as its SHA-256, so neither the torrent nor any mirror
or peer can change a byte.
"""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT)]
from engine.setup import download, torrent        # noqa: E402


def _progress(name):
    def show(done, total):
        print(f'\r{name}: {done / total:6.1%} of {total / 1e9:.1f} GB', end='', file=sys.stderr, flush=True)
    return show


def _make(path, url, length, trackers, whole=None):
    """(torrent bytes, the pin for the file's entry, the full pin)."""
    data, pin = torrent.make(path, path.name, length, web_seeds=[url], trackers=trackers, progress=_progress(path.name), whole=whole)
    print(file=sys.stderr)
    return data, {'url': url + '.torrent', 'pieces_root': pin['pieces_root'], 'infohash_v2': pin['infohash_v2'], 'piece_length': length}, pin


def _entries(m):
    return [f for key in ('packs', 'maps', 'address_indexes') for x in m.get(key) or [] for f in x.get('files') or []]


def _save(path, m):
    tmp = Path(str(path) + '.tmp')
    tmp.write_text(json.dumps(m, indent=1) + '\n', encoding='utf-8')
    os.replace(tmp, path)


def release(folders, manifest_path, length, trackers=(), force=False):
    """Torrents and pins for every file of the packs file that is in one of `folders`. Returns 0, or exits with why not."""
    m = json.loads(Path(manifest_path).read_text(encoding='utf-8'))
    made, kept, absent = [], [], []
    for f in _entries(m):
        name = f.get('name') or ''
        path = next((Path(d) / name for d in folders if name and (Path(d) / name).is_file()), None)
        if path is None:
            absent.append(name)
            continue
        if path.stat().st_size != f.get('size'):
            sys.exit(f'{path} is {path.stat().st_size:,} bytes and the manifest says {f.get("size"):,}: it is not the published file')
        t = path.with_name(name + '.torrent')
        old = f.get('torrent')
        if old and not force and old.get('piece_length') == length and t.is_file():
            try:
                torrent.piece_hashes(t.read_bytes(), name, f['size'], old['pieces_root'], old['piece_length'], old.get('infohash_v2'))
                kept.append(name)
                continue
            except (torrent.Bad, KeyError):
                pass                                   # a torrent that does not add up to its pin is made again
        if not download.url_allowed(f.get('url')):
            sys.exit(f'{name}: {f.get("url")} is not on an allowed host (engine/setup/download.py)')
        whole = hashlib.sha256()
        data, entry, pin = _make(path, f['url'], length, trackers, whole)
        if whole.hexdigest() != f.get('sha256'):
            sys.exit(f'{path}: its SHA-256 is {whole.hexdigest()}, not the {f.get("sha256")} the manifest pins: it is not the '
                     'published file, so nothing was written for it')
        t.write_bytes(data)
        f['torrent'] = entry
        _save(manifest_path, m)                        # after each file: a long run that stops keeps what it made
        made.append((t, entry['url']))
        print(f'{name}: pinned, infohash v2 {pin["infohash_v2"]}', flush=True)
    print(f'\n{len(made)} torrents made, {len(kept)} already pinned, {len(absent)} files of the manifest not in '
          f'{", ".join(str(d) for d in folders)}.')
    if made:
        print('Upload each next to its file:')
        for t, url in made:
            print(f'  {t}  ->  {url}')
        print(f'Then run packaging/release_manifest.py: the pins in {manifest_path} go into the app.')
    return 0


def one(path, url, length, trackers=(), manifest_path=None):
    path = Path(path)
    if not download.url_allowed(url):
        sys.exit(f'{url} is not on an allowed host (engine/setup/download.py)')
    hit = None
    if manifest_path:
        m = json.loads(Path(manifest_path).read_text(encoding='utf-8'))
        hits = [f for f in _entries(m) if f.get('name') == path.name]
        if len(hits) != 1:
            sys.exit(f'{manifest_path}: {len(hits)} entries for {path.name}, not one')
        hit = hits[0]
    whole = hashlib.sha256()
    data, entry, pin = _make(path, url, length, trackers, whole)
    if hit is not None:
        if hit.get('size') != pin['size']:
            sys.exit(f'{manifest_path}: {path.name} is {hit.get("size")} bytes there and {pin["size"]} here')
        if hit.get('sha256') and hit['sha256'] != whole.hexdigest():
            sys.exit(f'{path}: its SHA-256 is not the one {manifest_path} pins: it is not the published file, so nothing was written')
    out = path.with_name(path.name + '.torrent')
    out.write_bytes(data)
    print(f'{out}: {len(data):,} bytes, infohash v1 {pin["infohash_v1"]}, v2 {pin["infohash_v2"]}')
    print(f'magnet:?xt=urn:btih:{pin["infohash_v1"]}&xt=urn:btmh:1220{pin["infohash_v2"]}&dn={path.name}')
    print(json.dumps({'torrent': entry}, indent=1))
    if hit is not None:
        hit['torrent'] = entry
        _save(manifest_path, m)
        print(f'{manifest_path}: pinned')
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description='Torrents of published files, pinned in the manifest.')
    ap.add_argument('zip', nargs='?', help='one published file (or use --release for a whole release folder)')
    ap.add_argument('--url', help='where that file is published (its web seed); the torrent goes at <url>.torrent')
    ap.add_argument('--release', action='append', metavar='FOLDER',
                    help='a release folder: every file of --manifest found there gets its torrent and pin (more than once for more folders)')
    ap.add_argument('--manifest', help='the packs file (derived/release/manifest-v1.json) whose entries get the "torrent" pins')
    ap.add_argument('--force', action='store_true', help='with --release: make torrents again for files already pinned')
    ap.add_argument('--piece-mib', type=int, default=download.PIECE // 2 ** 20,
                    help='piece length in MiB, a power of two (default: the downloader\'s piece, so its pieces line up)')
    ap.add_argument('--tracker', action='append', default=[], help='a tracker to list (peers are also found through the DHT)')
    a = ap.parse_args(argv)
    length = a.piece_mib * 2 ** 20
    try:
        torrent.check_piece_length(length)
    except torrent.Bad as e:
        ap.error(str(e))
    if a.release:
        if a.zip or a.url:
            ap.error('--release makes the torrent of every file itself: give no file or --url with it')
        if not a.manifest:
            ap.error('--release needs --manifest, the packs file publish-packs writes')
        return release(a.release, a.manifest, length, a.tracker, a.force)
    if not a.zip or not a.url:
        ap.error('give a file and its --url, or --release FOLDER with --manifest')
    return one(a.zip, a.url, length, a.tracker, a.manifest)


if __name__ == '__main__':
    sys.exit(main())
