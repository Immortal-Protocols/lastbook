#!/usr/bin/env python3
"""List a library's videos that some supported computers can't play, and whether each has its H.264 copy (#49).

  python3 tools/check_video_formats.py [--data /path/to/LastbookData] [--all]

AV1 needs a hardware decoder in Lastbook on a Mac (M3 and later have one, M1 and M2 don't), and VP9 is not played by every
system's web view. Each such video should have an H.264 copy in derived/video-compat/h264-v1/ (built by
mobile/ipad/tools/videocompat); the desktop and iPad apps play the copy where the original can't be decoded.

The format is read from each file's own index: an MP4's sample description, or the codec id near the start of a WebM or MKV.
Only those bytes are read. A copy counts only as the app counts it: a plain file name in that folder, H.264, at the size
manifest.json gives. Exits 1 if any AV1 or VP9 video has no usable copy, so a pack build can stop on it. --all lists every video.
Nothing is asked of a server and no port is used.
"""
import argparse, json, os, struct, sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
NEEDS_COPY = {'av01': 'AV1', 'vp09': 'VP9'}
MKV_CODECS = {b'V_AV1': 'av01', b'V_VP9': 'vp09', b'V_VP8': 'vp08', b'V_MPEG4/ISO/AVC': 'avc1', b'V_MPEGH/ISO/HEVC': 'hvc1'}
CONTAINERS = (b'moov', b'trak', b'mdia', b'minf', b'stbl')
MAX_MOOV = 64 * 1024 * 1024


def mp4_formats(f, size):
    """The format codes of an MP4's tracks, in file order ('av01', 'mp4a'). [] if it is not an MP4 or its index can't be read."""
    found, at = [], 0
    while at + 8 <= size:
        f.seek(at)
        h = f.read(16)
        if len(h) < 8:
            break
        n, kind = struct.unpack('>I4s', h[:8])
        head = 8
        if n == 1 and len(h) == 16:
            n, head = struct.unpack('>Q', h[8:16])[0], 16
        elif n == 0:
            n = size - at
        if n < head or not kind.isascii():
            break
        if kind == b'moov':
            if n > MAX_MOOV:
                break
            f.seek(at)
            inside(f.read(n), head, n, found)
            break
        at += n
    return found


def inside(m, at, end, found):
    while at + 8 <= min(end, len(m)):
        n, kind = struct.unpack('>I4s', m[at:at + 8])
        head = 8
        if n == 1 and at + 16 <= len(m):
            n, head = struct.unpack('>Q', m[at + 8:at + 16])[0], 16
        if n < head or at + n > end:
            return
        if kind == b'stsd' and n >= head + 16 and at + head + 16 <= len(m):
            found.append(m[at + head + 12:at + head + 16].decode('latin-1'))
        elif kind in CONTAINERS:
            inside(m, at + head, at + n, found)
        at += n


def mkv_formats(f):
    """The video codec of a WebM or MKV, from the first megabyte, where its track list sits."""
    head = f.read(1024 * 1024)
    if not head.startswith(b'\x1a\x45\xdf\xa3'):
        return []
    return [code for key, code in MKV_CODECS.items() if key in head]


def formats(path):
    try:
        size = path.stat().st_size
        with open(path, 'rb') as f:
            return mkv_formats(f) or mp4_formats(f, size)
    except OSError:
        return []


def copies_folder(data):
    """The copies folder's real path, or None unless it really is where its path says, inside the data folder (no link)."""
    d = data / 'derived' / 'video-compat' / 'h264-v1'
    real, expected = os.path.realpath(d), os.path.join(os.path.realpath(data), 'derived', 'video-compat', 'h264-v1')
    return real if os.path.normcase(real) == os.path.normcase(expected) and os.path.isdir(real) else None


def copy_ok(f, size, folder):
    """A plain .mp4 name, really in the copies folder, not a link or a hard link, at size: as video_copy_ok() in server.py."""
    try:
        if f.name.startswith('.') or not f.name.lower().endswith('.mp4') or f.is_symlink() or not f.is_file():
            return False
        st = os.stat(f)
        return (os.path.normcase(os.path.realpath(f)) == os.path.normcase(os.path.join(folder, f.name))
                and st.st_nlink == 1 and st.st_size == size)
    except OSError:
        return False


def usable_copies(data):
    """{library path of an original: copy file}, by the same rules as video_copies() in server.py."""
    d = data / 'derived' / 'video-compat' / 'h264-v1'
    folder = copies_folder(data)
    if folder is None:
        return {}
    try:
        man = json.loads((d / 'manifest.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    if not isinstance(man, dict) or man.get('version') != 'h264-v1' or not isinstance(man.get('items'), dict):
        return {}
    out = {}
    for src, it in man['items'].items():
        if not isinstance(it, dict):
            continue
        name = str(it.get('file') or '')
        if not name or '/' in name or '\\' in name or name.startswith('.') or not name.lower().endswith('.mp4'):
            continue
        if it.get('video') != 'avc1' or it.get('source_video') not in NEEDS_COPY:
            continue
        size = it.get('bytes')
        if isinstance(src, str) and isinstance(size, int) and copy_ok(d / name, size, folder):
            out[src] = d / name
    return out


def main(args):
    ap = argparse.ArgumentParser(description='List videos that need an H.264 copy, and whether they have one.')
    ap.add_argument('--data', help='the data folder, the one that holds library-data/ (default: LASTBOOK_DATA, then this source tree)')
    ap.add_argument('--all', action='store_true', help='list every video, not only the ones that need a copy')
    a = ap.parse_args(args)
    data = Path(a.data or os.environ.get('LASTBOOK_DATA') or HERE)
    lib = data / 'library-data'
    try:
        catalog = json.loads((lib / 'catalog.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        sys.exit(f'No library at {lib} (no readable catalog.json). Pass --data or set LASTBOOK_DATA to the folder that holds library-data/.')
    copies = usable_copies(data)
    videos = [r for r in catalog if r.get('kind') == 'video']
    here = need = missing = 0
    for r in sorted(videos, key=lambda r: r['path']):
        p = lib / r['path']
        if not p.is_file():
            continue
        here += 1
        fmts = formats(p)
        codec = next((c for c in fmts if c in NEEDS_COPY), None) or next(iter(fmts), '?')
        if codec in NEEDS_COPY:
            need += 1
            ok = r['path'] in copies
            missing += not ok
            print(f"{NEEDS_COPY[codec]:4s} {'copy' if ok else 'NO COPY':7s} {r['path']}")
        elif a.all:
            print(f"{codec:4s} {'':7s} {r['path']}")
    print(f'{here} videos on this computer, {need} in AV1 or VP9, {missing} of those without a usable H.264 copy')
    return 1 if missing else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
