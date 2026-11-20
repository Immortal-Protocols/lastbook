#!/usr/bin/env python3
"""Share Lastbook's downloads from a server, on the command line: downloads each file whose torrent Lastbook's manifest pins,
checks it, and seeds it with rqbit for as long as this runs. Made for a Linux server; it runs on a Mac or Windows too.

  git clone --depth 1 https://github.com/Immortal-Protocols/lastbook && cd lastbook
  python3 packaging/share/fetch_rqbit.py          # rqbit for this machine, checked against its pinned SHA-256
  python3 tools/seed.py /srv/lastbook-share       # download, check, share; Ctrl-C stops, the same command goes on

  --list                what the manifest offers, which files can be shared yet, and what is here
  --only NAME[,NAME]    these files only (one without a torrent yet is downloaded now, and shared once it has one)
  --all                 every file, with a torrent or not
  --port N              the TCP port peers connect to (default 4240): let it through the firewall
  --upload-limit RATE   most bytes uploaded per second: 500K, 20M, 1G
  --connections N       connections to each server and mirror (default 4)
  --mirror URL          a copy of Lastbook's download site to take pieces from too (more than once for more)
  --no-peers            download from the servers and mirrors only (each file is still shared once it is here)
  --manifest FILE       this manifest-v1.json instead of the one on Lastbook's download site

Each file must match the SHA-256 the manifest pins, and a torrent is used only if its info hash and pieces root are the ones
the manifest pins; rqbit checks each file against that torrent before it uploads a byte of it. All of Lastbook's own traffic
goes through engine/setup/download.py. rqbit listens for peers on --port, so peers see this server's address, as with any
BitTorrent program; it changes no router (no UPnP) and its control API is on 127.0.0.1 only, behind a password made for each
run. Nothing is written outside the folder but rqbit itself, in this checkout. Python 3.11 or later, nothing to install.
"""
import sys

if sys.version_info < (3, 11):
    sys.exit('Lastbook needs Python 3.11 or later (this is %d.%d).' % sys.version_info[:2])

import argparse  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import shutil  # noqa: E402
import signal  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
import urllib.parse  # noqa: E402
from pathlib import Path  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.setup import download, manifest, share, torrent  # noqa: E402

PORT = 4240             # rqbit's own default for a server
RECHECK = 3600          # seconds between looks at the manifest, for torrents published since
STATUS = 300            # seconds between status lines while sharing
MARGIN = 2 ** 30        # free space left over beyond what the downloads need
STATE = '.lastbook-seed'
NOTHING_PINNED = ('Lastbook has not published a torrent for any of these files yet, so there is nothing to share. This keeps '
                  'running and looks again every hour. To download now and share each file once its torrent is published, '
                  'add --all or --only NAME.')
NOTHING_YET = ('Lastbook has not published a torrent for any of these files yet. They are downloaded now, and each is shared '
               'once its torrent is published (this looks every hour).')


def gb(n):
    return f'{n / 1e9:.1f} GB'


def rate(text):
    """'500K', '20M', '1G' or a number: bytes per second."""
    t = text.strip().upper().removesuffix('/S').removesuffix('B')
    mult = {'K': 1000, 'M': 1000 ** 2, 'G': 1000 ** 3}.get(t[-1:], 1)
    try:
        n = float(t[:-1] if t[-1:] in 'KMG' else t) * mult
    except ValueError:
        raise argparse.ArgumentTypeError(f'not a rate: {text} (try 500K, 20M or 1G)')
    if n < 1:
        raise argparse.ArgumentTypeError('the upload limit must be at least 1 byte per second')
    return int(n)


def parse(argv):
    ap = argparse.ArgumentParser(prog='seed.py', description='Download Lastbook\'s files and share them with BitTorrent.',
                                 epilog='See docs/DOWNLOAD-SHARING.md.')
    ap.add_argument('folder', help='where the files go (made if missing); the same folder goes on where it stopped')
    ap.add_argument('--list', action='store_true', help='show what can be shared, and stop')
    ap.add_argument('--only', default='', help='these files only, by name, separated by commas')
    ap.add_argument('--all', action='store_true', help='every file, with a torrent or not')
    ap.add_argument('--port', type=int, default=PORT, help=f'the TCP port peers connect to (default {PORT})')
    ap.add_argument('--upload-limit', type=rate, default=None, metavar='RATE', help='most bytes uploaded per second: 500K, 20M, 1G')
    ap.add_argument('--connections', type=int, default=4, help='connections to each server and mirror (default 4)')
    ap.add_argument('--mirror', action='append', default=[], metavar='URL', help='a copy of Lastbook\'s download site')
    ap.add_argument('--no-peers', action='store_true', help='download from the servers and mirrors only')
    ap.add_argument('--manifest', metavar='FILE', help='this manifest-v1.json instead of Lastbook\'s')
    a = ap.parse_args(argv)
    if not 0 < a.port < 65536:
        ap.error('--port must be 1 to 65535')
    if not 1 <= a.connections <= 16:
        ap.error('--connections must be 1 to 16')
    return a


def load(a, allowed, context):
    """The manifest, checked as the app checks the one it fetches, or None (said why)."""
    if a.manifest:
        try:
            data = Path(a.manifest).read_bytes()
        except OSError as e:
            print(f'Could not read {a.manifest}: {e}', flush=True)
            return None
    else:
        data = download.fetch_small(manifest.REMOTE, limit=4 << 20, allowed=allowed, context=context, timeout=30)
        if data is None:
            print(f'Could not fetch {manifest.REMOTE}. Check the internet connection, then try again.', flush=True)
            return None
    try:
        m = manifest.validate(json.loads(data), allowed)
    except ValueError:
        m = None
    if m is None:
        print('The manifest is not one Lastbook can use.', flush=True)
    return m


def offered(m):
    """Every file the manifest offers now, each once: [{name, url, size, sha256, and torrent and mirrors when it has them}]."""
    out = {}
    for key in ('packs', 'maps', 'address_indexes'):
        for x in m.get(key, []):
            if x.get('available'):
                for f in x['files']:
                    out.setdefault(f['name'], f)
    for x in m.get('models', []):
        if x.get('available'):
            out.setdefault(x['file'], {'name': x['file'], 'url': x['url'], 'size': x['size'], 'sha256': x['sha256'],
                                       **{k: x[k] for k in ('torrent', 'mirrors') if k in x}})
    return list(out.values())


def pick(files, a):
    if a.only:
        names = {n.strip() for n in a.only.split(',') if n.strip()}
        return [f for f in files if f['name'] in names]
    return [f for f in files if a.all or f.get('torrent')]


def here(f, folder):
    """Whether the whole file is in the folder (checked when it was downloaded; rqbit checks it again before sharing it)."""
    p = folder / f['name']
    try:
        return p.stat().st_size == f['size'] and not Path(str(p) + '.part').exists()
    except OSError:
        return False


def on_disk(p):
    """Bytes a file takes on the disk (a sparse file's holes take none), 0 if it is not there."""
    try:
        st = os.stat(p)
    except OSError:
        return 0
    blocks = getattr(st, 'st_blocks', None)
    return min(st.st_size, blocks * 512) if blocks is not None else st.st_size


def needed(files, folder, state):
    return sum(max(0, f['size'] - on_disk(Path(str(folder / f['name']) + '.part')) - on_disk(state / 'swarm' / f['name']))
               for f in files if not here(f, folder))


def show(files, folder):
    width = max([len(f['name']) for f in files] + [4])
    print(f'{"NAME":{width}}  {"SIZE":>9}  TORRENT  HERE')
    for f in sorted(files, key=lambda f: f['size']):
        have = 'yes' if here(f, folder) else ('partly' if on_disk(Path(str(folder / f['name']) + '.part')) or
                                              on_disk(folder / STATE / 'swarm' / f['name']) else 'no')
        print(f'{f["name"]:{width}}  {gb(f["size"]):>9}  {"yes" if f.get("torrent") else "not yet":7}  {have}')
    pinned = [f for f in files if f.get('torrent')]
    print(f'\n{len(pinned)} of {len(files)} files can be shared now ({gb(sum(f["size"] for f in pinned))}).')
    if not pinned:
        print('Lastbook has not published a torrent for any file yet.')


def torrent_for(f, state, allowed, context):
    """(torrent bytes, torrent.Pieces) when the manifest pins the file's torrent and the torrent is that one, else (None, None).
    Fetched from Lastbook's site only, and kept in the state folder."""
    t = f.get('torrent')
    if not t:
        return None, None
    keep = state / (f['name'] + '.torrent')
    for fetched in (False, True):
        if fetched:
            data = download.fetch_small(t['url'], limit=torrent.MAX_TORRENT, allowed=allowed, context=context, timeout=30)
        else:
            try:
                data = keep.read_bytes()
            except OSError:
                data = None
        if not data:
            continue
        try:
            pieces = torrent.piece_hashes(data, f['name'], f['size'], t['pieces_root'], t['piece_length'], t['infohash_v2'])
        except torrent.Bad as e:
            print(f'The torrent of {f["name"]} is not the one Lastbook pins ({e}); it is not used.', flush=True)
            continue
        if fetched:
            keep.write_bytes(data)
        return data, pieces
    return None, None


class Progress:
    """A line about a download every EVERY seconds."""
    EVERY = 30

    def __init__(self, name):
        self.name, self.last, self.t0, self.b0 = name, 0.0, time.time(), None

    def __call__(self, done, total, phase):
        now = time.time()
        if self.b0 is None:
            self.b0, self.t0 = done, now
        if now - self.last < self.EVERY:
            return
        self.last = now
        speed = (done - self.b0) / max(now - self.t0, 1e-6) if phase == 'downloading' else 0
        print(f'{self.name}: {phase} {gb(done)} of {gb(total)} ({100 * done / max(total, 1):.1f}%)'
              + (f', {speed / 1e6:.1f} MB/s' if speed else ''), flush=True)


def fetch(f, folder, state, data, pieces, a, control, allowed, context, command, extra, tally):
    """Downloads one file into the folder, checked against its pinned SHA-256: from its own address, its mirrors, and (with its
    torrent, unless --no-peers) other people. Raises download.Stopped, Failed or BadChecksum."""
    dest = folder / f['name']
    in_swarm, part = state / 'swarm' / f['name'], Path(str(dest) + '.part')
    mirrors = list(f.get('mirrors') or [])
    if manifest._from(f['url'], manifest.LIBRARY_HOSTS, allowed):           # a copy of the download site has the file at its path
        path = urllib.parse.urlsplit(f['url']).path
        mirrors += [m.rstrip('/') + path for m in a.mirror]
    swarm = None
    if pieces is not None and not a.no_peers and f['size'] >= download.PARALLEL_MIN and (command or share.binary()):
        in_swarm.parent.mkdir(parents=True, exist_ok=True)
        if part.exists() and not in_swarm.exists():
            os.replace(part, in_swarm)
        swarm = share.Swarm(data, tally=tally, command=command, extra=['--disable-tcp-listen', *extra])   # the Station takes peers in
    elif in_swarm.exists() and not part.exists():
        os.replace(in_swarm, part)
    print(f'Downloading {f["name"]} ({gb(f["size"])})' + (', from other people too' if swarm else ''), flush=True)
    d = download.Download(f['url'], dest, f['size'], f['sha256'], control, progress=Progress(f['name']), allowed=allowed,
                          context=context, connections=a.connections, pieces=pieces, mirrors=mirrors, swarm=swarm,
                          part=in_swarm if swarm else None)
    d.run()
    print(f'{f["name"]} is here, and matches its published SHA-256.', flush=True)


def main(argv=None, allowed=None, context=None, command=None, extra=(), recheck=RECHECK, status=STATUS, stop=None):
    """The command. allowed, context, command and extra are for tests: their hosts, TLS roots, an rqbit stand-in and its
    arguments. stop: an Event that ends it as Ctrl-C does."""
    a = parse(argv)
    folder = Path(a.folder).expanduser().resolve()
    m = load(a, allowed, context)
    if m is None:
        return 1
    files = offered(m)
    if a.list:
        show(files, folder)
        return 0
    if a.only:
        unknown = {n.strip() for n in a.only.split(',') if n.strip()} - {f['name'] for f in files}
        if unknown:
            print(f'Not in the manifest: {", ".join(sorted(unknown))}. --list shows the names.', flush=True)
            return 1
    for u in a.mirror:
        if not manifest.mirror_ok(u, allowed) or urllib.parse.urlsplit(u).query:
            print(f'Not an https address Lastbook can use as a mirror: {u}', flush=True)
            return 1
    folder.mkdir(parents=True, exist_ok=True)
    state = folder / STATE
    state.mkdir(exist_ok=True)
    tally = share.Tally(state / 'shared.json')
    station = share.Station(folder, listen_port=a.port, upload_bps=a.upload_limit, command=command, extra=extra, tally=tally)
    if not station.available():
        print('rqbit is not here. Fetch the pinned copy for this machine first:\n'
              f'  python3 {ROOT / "packaging" / "share" / "fetch_rqbit.py"}', flush=True)
        return 1
    control, stop = download.Control(), stop or threading.Event()
    threading.Thread(target=lambda: (stop.wait(), control.stop('paused')), daemon=True, name='seed-stop').start()  # a download stops where it is
    _on_signals(stop)
    said_nothing = False
    try:
        while not stop.is_set():
            chosen = sorted(pick(files, a), key=lambda f: f['size'])
            if not any(f.get('torrent') for f in chosen) and not said_nothing:
                print(NOTHING_YET if a.all or a.only else NOTHING_PINNED, flush=True)
                said_nothing = True
            need, free = needed(chosen, folder, state), shutil.disk_usage(folder).free
            if need and need + MARGIN > free:          # nothing left to download needs no space
                print(f'These files need {gb(need)} more on the disk under {folder}, and it has {gb(free)} free. '
                      'Free some space, or choose fewer files with --only (--list shows them).', flush=True)
                return 1
            for f in chosen:
                if stop.is_set():
                    break
                data, pieces = torrent_for(f, state, allowed, context)
                if not here(f, folder):
                    try:
                        fetch(f, folder, state, data, pieces, a, control, allowed, context, command, extra, tally)
                    except download.Stopped:
                        break
                    except (download.Failed, download.BadChecksum) as e:
                        print(f'{f["name"]} did not download: {e}. It is tried again within the hour.', flush=True)
                        continue
                if data is not None and f['name'] not in station.added:
                    if not station.running() and not station.start():
                        print('rqbit did not start, so nothing is shared yet. It is tried again within the hour.', flush=True)
                        break
                    if station.add(f['name'], data, stop):            # a stop ends the wait for rqbit's answer
                        print(f'Sharing {f["name"]} (rqbit checks it against its torrent first).', flush=True)
                        if len(station.added) == 1:
                            print(f'Peers connect to this server on TCP port {a.port}; let it through the firewall.', flush=True)
                    elif stop.is_set():
                        break
                    else:
                        print(f'rqbit did not take {f["name"]}; it is tried again within the hour.', flush=True)
            next_check = time.time() + recheck
            while not stop.is_set() and time.time() < next_check:
                if stop.wait(max(0.0, min(status, next_check - time.time()))):
                    break
                if station.added and not station.running():
                    print('rqbit ended; starting it again.', flush=True)
                    station.added.clear()
                    break
                if station.running():
                    n = len(station.added)
                    print(f'Sharing {n} {"file" if n == 1 else "files"}; {gb(station.shared())} uploaded to other people so far.', flush=True)
            if not stop.is_set() and time.time() >= next_check:
                fresh = load(a, allowed, context)
                if fresh is not None:
                    files = offered(fresh)
    finally:
        station.stop()
        print(f'Stopped. {gb(tally.total())} uploaded to other people so far. The same command goes on from here.', flush=True)
    return 0


def _on_signals(stop):
    """Ctrl-C or SIGTERM sets `stop`: the download stops where it is (kept), then rqbit. The handler only writes a byte; a thread
    does the rest, so nothing in it waits on a lock the interrupted code may hold. A second Ctrl-C ends at once."""
    if threading.current_thread() is not threading.main_thread():
        return
    r, w = os.pipe()

    def watch():
        os.read(r, 1)
        print('\nStopping...', flush=True)
        stop.set()

    def handler(signum, frame):
        signal.signal(signal.SIGINT, signal.default_int_handler)
        os.write(w, b'x')
    threading.Thread(target=watch, daemon=True, name='seed-stop').start()
    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)


if __name__ == '__main__':
    sys.exit(main())
