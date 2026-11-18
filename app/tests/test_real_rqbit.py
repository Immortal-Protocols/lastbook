"""Setup with the real, pinned rqbit (not test_setup.py's stand-in), in a disposable swarm on this computer. Never shipped.

A real rqbit seeds the pack on 127.0.0.1. Setup (engine/setup/api.Setup) downloads it from test_setup.py's local HTTPS server
and from that peer at once, through its own rqbit (share.Swarm), and seeds what it keeps through another (share.Seeder).
Every rqbit here is started with --listen-ip 127.0.0.1 and without DHT, trackers or local discovery, and the torrent has no web
seed, so nothing is reachable from outside this computer and nothing is announced anywhere. It covers turning BitTorrent on,
Pause, resuming at once, Cancel, turning it off midway, and sharing again after the app is closed and opened.

It runs only where rqbit has been fetched (python3 packaging/share/fetch_rqbit.py), and is skipped otherwise:

  python3 app/tests/test_real_rqbit.py
"""
import hashlib
import json
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parents[1])]
import test_setup as T  # noqa: E402
from engine.setup import api, download, manifest, share, torrent  # noqa: E402

RQ = share.binary()
LOOP = ['--listen-ip', '127.0.0.1', '--disable-dht', '--disable-lsd', '--disable-trackers']
MiB = 1 << 20


def rqbit_pids():
    if os.name == 'nt':
        out = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq rqbit.exe', '/FO', 'CSV', '/NH'], capture_output=True, text=True).stdout
        return {int(line.split('","')[1]) for line in out.splitlines() if line.startswith('"rqbit.exe"')}
    return {int(x) for x in subprocess.run(['pgrep', '-x', 'rqbit'], capture_output=True, text=True).stdout.split()}


def say(*a):
    print('  ..', *a, flush=True)


@unittest.skipUnless(RQ, 'no rqbit in derived/share (python3 packaging/share/fetch_rqbit.py fetches it)')
class RealSwarm(T.Base):
    PIECE = MiB

    def setUp(self):
        super().setUp()
        p = mock.patch.multiple(download, PIECE=self.PIECE, PARALLEL_MIN=0, HARVEST_EVERY=0.3)
        p.start()
        self.addCleanup(p.stop)
        self.started = []                                       # every rqbit the app starts: its arguments
        real = share._spawn

        def spawn(args, secret):
            self.started.append(list(args))
            return real(args, secret)
        p = mock.patch.object(share, '_spawn', spawn)
        p.start()
        self.addCleanup(p.stop)
        self.addCleanup(self.only_on_this_computer)
        zpath = self.tmp / 'Lastbook-Small.zip'                 # a pack big enough to pause in the middle: 40 MiB
        self.installed = T.make_pack(zpath, {'library-data/catalog.json': b'{"records": []}', 'pack.json': b'{"name": "small"}',
                                             'library-data/big.bin': os.urandom(36 * MiB), 'derived/geo/map.sqlite': os.urandom(3 * MiB)})
        self.zip = zpath.read_bytes()
        self.files.data['Lastbook-Small.zip'] = self.zip
        self.tdata, self.pin = torrent.make(zpath, 'Lastbook-Small.zip', self.PIECE)
        self.files.data['Lastbook-Small.zip.torrent'] = self.tdata
        self.before = rqbit_pids()
        peer = self.tmp / 'peer'                                # the other person: a real rqbit seeding the same pack
        peer.mkdir()
        (peer / 'Lastbook-Small.zip').write_bytes(self.zip)
        (self.tmp / 'peer.torrent').write_bytes(self.tdata)
        port, api_port, secret = download.loopback_port(), download.loopback_port(), 'peer'
        self.peer = subprocess.Popen([str(RQ), *LOOP, '--disable-upnp-port-forward', '--disable-dht-persistence', '-v', 'warn',
                                      '--listen-port', str(port), '--http-api-listen-addr', f'127.0.0.1:{api_port}',
                                      'download', '--overwrite', '-o', str(peer), str(self.tmp / 'peer.torrent')],
                                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                     env={**os.environ, 'RQBIT_HTTP_BASIC_AUTH_USERPASS': f'lastbook:{secret}'})
        self.addCleanup(lambda: (self.peer.terminate(), self.peer.wait(15)))
        self.wait_live(api_port, secret, 0)
        self.peers = [f'127.0.0.1:{port}']

    def only_on_this_computer(self):
        for args in self.started:
            self.assertIn('127.0.0.1', args[args.index('--listen-ip') + 1:args.index('--listen-ip') + 2], args)
            for flag in ('--disable-dht', '--disable-lsd', '--disable-trackers', '--disable-upnp-port-forward'):
                self.assertIn(flag, args)

    def wait_live(self, port, secret, tid, timeout=60):
        t0, st = time.time(), {}
        while time.time() - t0 < timeout:
            r = download.local_api(port, secret, 'GET', f'/torrents/{tid}/stats/v1')
            st = json.loads(r[1]) if r and r[0] == 200 else {}
            if st.get('state') == 'live' and st.get('finished'):
                return st
            time.sleep(0.2)
        self.fail(f'rqbit never had the whole file: {st}')

    def manifest(self):
        m = {'version': 1, 'published': '2026-11-18',
             'packs': [{'id': 'small', 'title': 'Small', 'summary': 's', 'records': 3, 'installed_bytes': self.installed, 'available': True,
                        'files': [{'name': 'Lastbook-Small.zip', 'url': f'{self.base}/Lastbook-Small.zip', 'size': len(self.zip),
                                   'sha256': T.sha(self.zip), 'kind': 'zip',
                                   'torrent': {'url': f'{self.base}/Lastbook-Small.zip.torrent', 'pieces_root': self.pin['pieces_root'],
                                               'infohash_v2': self.pin['infohash_v2'], 'piece_length': self.PIECE}}]}], 'models': []}
        return manifest.Manifest(bundled=manifest.validate(m, T.ALLOWED), remote=None, allowed=T.ALLOWED, context=self.ctx)

    def app(self, mode='first-run', current=None):
        """Setup with the real rqbit, every one it starts kept to this computer; people at 3 MB/s, so a Pause comes midway."""
        return self.setup(mode, current=current, manifest=self.manifest(), share_command=[str(RQ), *LOOP],
                          swarm_extra=['--ratelimit-download', str(3 * MiB)], swarm_peers=self.peers)

    def ours(self):
        return rqbit_pids() - self.before - {self.peer.pid}

    def item(self, s):
        return (s.public_job() or {}).get('items', [{}])[0]

    def until(self, what, timeout=60):
        t0 = time.time()
        while time.time() - t0 < timeout:
            if what():
                return
            time.sleep(0.1)
        self.fail('waited in vain')

    def test_on_pause_resume_cancel_off(self):
        s = self.app()
        self.addCleanup(s.seeder.stop)
        self.assertTrue(s.sharing()['available'])
        self.assertTrue(s.set_share(True)['on'])                                          # on
        self.files.pace = 0.4                                                              # the server slow: people do most
        s.start('small', False)
        self.until(lambda: self.item(s).get('from_peers', 0) > 2 * MiB)
        say('on: from people so far', self.item(s)['from_peers'], 'bytes; rqbit processes of the app:', len(self.ours()))
        self.assertGreaterEqual(len(self.ours()), 1)
        part = self.parent / 'LastbookData.setup' / 'downloads' / 'swarm' / 'Lastbook-Small.zip'
        t0 = time.time()
        j = s.pause()                                                                      # Pause
        took = time.time() - t0
        self.assertEqual(j['state'], 'paused')
        self.assertEqual(T.ParallelDownloads.download_threads(), [])
        self.assertEqual(self.ours(), set(), 'the app\'s rqbit outlived Pause')
        snap = hashlib.sha256(part.read_bytes()).digest()
        time.sleep(1.5)
        self.assertEqual(hashlib.sha256(part.read_bytes()).digest(), snap, 'the file changed after Pause returned')
        say(f'Pause: returned in {took:.2f} s; no download thread, no app rqbit, the file still')
        s.resume()                                                                         # resume at once
        before = self.item(s).get('from_peers', 0)
        self.until(lambda: self.item(s).get('from_peers', 0) > before + MiB)
        say('resume: from people again, now', self.item(s)['from_peers'], 'bytes')
        t0 = time.time()
        s.cancel()                                                                         # Cancel
        took = time.time() - t0
        self.assertEqual(self.ours(), set(), 'the app\'s rqbit outlived Cancel')
        downloads = self.parent / 'LastbookData.setup' / 'downloads'
        self.assertFalse(downloads.exists())
        time.sleep(1.5)
        self.assertFalse(downloads.exists(), 'a late write brought the download back')
        say(f'Cancel: returned in {took:.2f} s; the download removed and stays removed, no app rqbit')
        s.start('small', False)                                                            # off midway
        self.until(lambda: self.item(s).get('from_peers', 0) > MiB)
        s.set_share(False)
        self.until(lambda: not self.ours(), timeout=15)
        say('off: the app\'s rqbit ended while the download goes on from the server')
        self.files.pace = 0
        j = self.wait(s, timeout=120)
        self.assertEqual(j['state'], 'done', j)
        lib, _ = api.startup(self.settings)
        self.assertTrue(lib and (Path(lib) / 'library-data' / 'catalog.json').is_file(), lib)
        self.assertFalse((self.parent / 'LastbookData.share' / 'Lastbook-Small.zip').exists())   # sharing off: not kept
        say('done: installed from the server and people; nothing kept, sharing off')

    def test_kept_and_shared_again_after_a_restart(self):
        s = self.app()
        self.assertTrue(s.set_share(True)['on'])
        self.files.pace = 0.05
        s.start('small', False)
        j = self.wait(s, timeout=180)
        self.assertEqual(j['state'], 'done', j)
        self.assertGreater(j['items'][0].get('from_peers', 0), 0)
        kept = self.parent / 'LastbookData.share' / 'Lastbook-Small.zip'
        self.assertEqual(kept.read_bytes(), self.zip)
        say('downloaded with people,', j['items'][0]['from_peers'], 'bytes from them; kept to share')
        s.seeder.stop()                                                                    # the app closes
        self.assertEqual(self.ours(), set())
        lib, note = api.startup(self.settings)                                             # and opens again
        api.opened(self.settings, lib, note)
        m = self.app('manage', current=lib)
        self.addCleanup(m.seeder.stop)
        self.until(lambda: m.seeder.running(), timeout=20)
        _, _, _, port, secret = m.seeder.procs[0]
        st = self.wait_live(port, secret, 0)
        self.assertEqual(st.get('total_bytes'), len(self.zip))
        say(f'restart: sharing again; the app\'s rqbit checked the kept file and has all {st["total_bytes"]} bytes')


if __name__ == '__main__':
    print('rqbit:', RQ, flush=True)
    unittest.main(verbosity=2)
