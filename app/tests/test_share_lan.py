"""LAN checks for the share listener: a real bind on 0.0.0.0, requests from this
computer's non-loopback address, curl for auth, the allowlist, Range/206, and Stop.

  python3 -B -m unittest app.tests.test_share_lan
"""
import os, socket, subprocess, sys, tempfile, threading, time, unittest
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'app'), str(HERE)]

import server  # noqa: E402
from engine import share  # noqa: E402
from engine.share_http import ShareServer  # noqa: E402
from app.tests.test_share import SlowShare, listening  # noqa: E402

LOG = Path('/tmp/lastbook-share-lan-tests.txt')


def lan_ip():
    ip = server.lan_address()
    if ip and not ip.startswith('127.'):
        return ip
    # Fallback: first non-loopback IPv4.
    for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
        cand = info[4][0]
        if not cand.startswith('127.'):
            return cand
    return None


def curl(args, timeout=8):
    cmd = ['curl', '-sS', '-D', '-', '-o', '/tmp/lastbook-share-lan-body', '--max-time', str(timeout), *args]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 2)
    return cmd, r


class LanShare(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ip = lan_ip()
        cls.dir = tempfile.TemporaryDirectory()
        data = Path(cls.dir.name) / 'data'
        data.mkdir()
        cls.here_patch = mock.patch.object(server, 'HERE', data)
        cls.here_patch.start()
        server.LAN_KEY = None
        server.stop_lan(wait=True)
        share.configure(Path(cls.dir.name) / 'settings')
        share._ERROR = None
        server.load_lan_key()
        raw = server.bind_http(0, lan=True, handler=SlowShare)
        ShareServer(raw)
        server.SERVER = raw
        t = threading.Thread(target=raw.serve_forever, daemon=True, name='lastbook-share-lan')
        server._LAN_THREAD = t
        t.start()
        cls.port = raw.server_address[1]
        cls.key = server.LAN_KEY
        cls.base = f'http://{cls.ip or "127.0.0.1"}:{cls.port}'
        # Wait until the port accepts connections.
        deadline = time.time() + 3
        while time.time() < deadline and not listening(cls.port):
            time.sleep(0.05)
        cls.log = []
        cls.log.append(f'LAN test host={cls.ip} port={cls.port} bind=0.0.0.0')

    @classmethod
    def tearDownClass(cls):
        try:
            server.stop_lan(wait=True)
        finally:
            server.LAN_KEY = None
            share._SETTINGS_DIR = None
            cls.here_patch.stop()
            cls.dir.cleanup()
            LOG.write_text('\n'.join(cls.log) + '\n', encoding='utf-8')

    def _run(self, title, args, timeout=8):
        cmd, r = curl(args, timeout=timeout)
        line = f'$ {" ".join(cmd)}\nexit={r.returncode}\n{r.stdout[:2000]}\n{r.stderr}'
        self.log.append(f'--- {title} ---\n{line}')
        return r

    def test_01_non_loopback_is_available(self):
        self.assertTrue(self.ip, 'this machine has no non-loopback IPv4 address to curl')
        self.assertTrue(listening(self.port, '127.0.0.1'))

    def test_02_auth_required_from_lan_ip(self):
        r = self._run('no key', ['-o', '/dev/null', '-w', '%{http_code}', f'{self.base}/sw.js'])
        self.assertIn('403', r.stdout)

    def test_03_header_key_is_accepted(self):
        r = self._run('header key', ['-o', '/dev/null', '-w', '%{http_code}', '-H', f'X-Lastbook-Key: {self.key}', f'{self.base}/sw.js'])
        self.assertIn('200', r.stdout)

    def test_04_query_key_is_accepted(self):
        r = self._run('query key', ['-o', '/dev/null', '-w', '%{http_code}', f'{self.base}/sw.js?key={self.key}'])
        self.assertIn('200', r.stdout)

    def test_05_allowlist_blocks_setup(self):
        r = self._run('setup blocked', ['-o', '/dev/null', '-w', '%{http_code}', '-H', f'X-Lastbook-Key: {self.key}', f'{self.base}/api/setup/state'])
        self.assertIn('403', r.stdout)
        r = self._run('encoded traversal', ['-o', '/dev/null', '-w', '%{http_code}', '-H', f'X-Lastbook-Key: {self.key}', f'{self.base}/%2e%2e/api/setup'])
        self.assertIn('403', r.stdout)

    def test_06_chat_blocked_when_ai_off(self):
        r = self._run('chat blocked', ['-o', '/dev/null', '-w', '%{http_code}', '-H', f'X-Lastbook-Key: {self.key}', '-H', 'Content-Type: application/json', '-X', 'POST', '-d', '{"messages":[]}', f'{self.base}/api/chat'])
        self.assertIn('403', r.stdout)

    def test_07_range_is_206(self):
        r = self._run('range 206', ['-o', '/dev/null', '-w', '%{http_code}', '-H', f'X-Lastbook-Key: {self.key}', '-H', 'Range: bytes=0-99', '-I', f'{self.base}/videos/slow.bin'])
        # -I is HEAD; status is in the headers
        self.assertTrue('206' in r.stdout or 'HTTP/1.0 206' in r.stdout or 'HTTP/1.1 206' in r.stdout, r.stdout)

    def test_08_stop_cuts_stream_and_releases_port(self):
        url = f'{self.base}/videos/slow.bin'
        proc = subprocess.Popen(
            ['curl', '-sS', '-o', '/tmp/lastbook-share-lan-stream', '-H', f'X-Lastbook-Key: {self.key}',
             '-H', 'Range: bytes=0-1048575', '--max-time', '8', url],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        self.log.append(f'--- stream then stop ---\n$ curl -H X-Lastbook-Key:… Range bytes=0-1048575 {url}')
        time.sleep(0.25)
        server.stop_lan(wait=True)
        try:
            out, err = proc.communicate(timeout=6)
        except subprocess.TimeoutExpired:
            proc.kill()
            out, err = proc.communicate()
        size = os.path.getsize('/tmp/lastbook-share-lan-stream') if os.path.exists('/tmp/lastbook-share-lan-stream') else 0
        self.log.append(f'curl exit={proc.returncode} bytes={size} stderr={err.strip()}')
        self.assertFalse(listening(self.port))
        self.assertIsNone(server.SERVER)
        self.assertLess(size, 1024 * 1024)


if __name__ == '__main__':
    unittest.main()
