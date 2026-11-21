"""Share this library with my devices: a dedicated allowlist listener, a key on every
socket request, a normalized route for access and dispatch, and Stop that cuts streams.

  python3 -B -m unittest app.tests.test_share
"""
import io, json, socket, sys, tempfile, threading, time, unittest
from http.client import HTTPConnection
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'app'), str(HERE)]

import server  # noqa: E402
from engine import share  # noqa: E402
from engine.share_http import allowed, key_matches, normalize_route, presented_key  # noqa: E402


def listening(port, host='127.0.0.1'):
    try:
        s = socket.create_connection((host, port), timeout=0.4)
        s.close()
        return True
    except OSError:
        return False


class H:
    """A stand-in for the desktop /api/share handler (the in-memory bridge)."""
    def __init__(self, ip='127.0.0.1', path='/api/share', body=None, cookie=None, listener=False):
        raw = b'' if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
        self.client_address, self.path = (ip, 1), path
        self.headers = {'Content-Length': str(len(raw))}
        if cookie:
            self.headers['Cookie'] = 'sg_key=' + cookie
        self.rfile, self.wfile, self.status = io.BytesIO(raw), io.BytesIO(), None
        self.SHARE_LISTENER = listener

    def send_json(self, obj, status=200, cache=None):
        self.status = status
        self.wfile.write(json.dumps(obj).encode())

    def answer(self):
        return json.loads(self.wfile.getvalue())


class NormalizeAndAllow(unittest.TestCase):
    def test_normalize_drops_query_and_collapses_dots_and_slashes(self):
        self.assertEqual(normalize_route('/api/topics?key=x'), '/api/topics')
        self.assertEqual(normalize_route('/api//topics'), '/api/topics')
        self.assertEqual(normalize_route('/api/./topics'), '/api/topics')
        self.assertEqual(normalize_route('/api/foo/../topics'), '/api/topics')
        self.assertEqual(normalize_route('/api/topics/'), '/api/topics')
        self.assertEqual(normalize_route('/'), '/')
        self.assertEqual(normalize_route('/%2e%2e/api/setup'), '/api/setup')
        self.assertEqual(normalize_route('/%2e%2e/%2e%2e/api/setup'), '/api/setup')
        self.assertEqual(normalize_route('/api/%2e/%2e/setup'), '/api/setup')
        self.assertEqual(normalize_route('/%252e%252e/api/setup'), '/api/setup')
        self.assertEqual(normalize_route('//api/setup'), '/api/setup')
        self.assertEqual(normalize_route('/api/./setup'), '/api/setup')
        self.assertIsNone(normalize_route('/api/top\0ics'))
        self.assertIsNone(normalize_route('/api/..\\setup'))

    def test_allowlist_is_deny_by_default(self):
        self.assertTrue(allowed('/api/topics', 'GET'))
        self.assertTrue(allowed('/api/find', 'HEAD'))
        self.assertTrue(allowed('/videos/demo.mp4', 'GET'))
        self.assertTrue(allowed('/ui/app.js', 'GET'))
        self.assertTrue(allowed('/documents/a/b.pdf', 'GET'))
        self.assertFalse(allowed('/api/setup', 'GET'))
        self.assertFalse(allowed('/api/setup/state', 'GET'))
        self.assertFalse(allowed('/api/update/check', 'GET'))
        self.assertFalse(allowed('/api/battery', 'GET'))
        self.assertFalse(allowed('/api/not-found', 'GET'))
        self.assertFalse(allowed('/api/not-found', 'POST'))
        self.assertFalse(allowed('/api/assistant/local', 'POST'))
        self.assertFalse(allowed('/api/tool/search_library', 'POST'))
        self.assertFalse(allowed('/api/tools', 'GET'))
        self.assertFalse(allowed('/api/share', 'GET'))
        self.assertFalse(allowed('/api/share', 'POST'))
        self.assertFalse(allowed('/ui/setup.html', 'GET'))
        self.assertFalse(allowed('/ui/setup.js', 'GET'))
        self.assertFalse(allowed('/ui/update.js', 'GET'))
        self.assertFalse(allowed('/api/chat', 'POST'))
        self.assertFalse(allowed('/api/retrieve', 'GET'))
        self.assertFalse(allowed('/etc/passwd', 'GET'))
        self.assertFalse(allowed('/', 'POST'))

    def test_ai_routes_only_when_opted_in(self):
        self.assertFalse(allowed('/api/chat', 'POST', ai=False))
        self.assertTrue(allowed('/api/chat', 'POST', ai=True))
        self.assertFalse(allowed('/api/retrieve', 'GET', ai=False))
        self.assertTrue(allowed('/api/retrieve', 'GET', ai=True))
        # Status is always listable, so a remote Chat tab can see that it is not shared.
        self.assertTrue(allowed('/api/assistant/status', 'GET', ai=False))
        self.assertFalse(allowed('/api/assistant/local', 'POST', ai=True))

    def test_traversal_and_encoding_cannot_reach_desktop_routes(self):
        attacks = (
            '/%2e%2e/api/setup',
            '//api/setup',
            '/api/./setup',
            '/API/setup',
            '/api/foo/../setup',
            '/api/setup%2fstate',
            '/%252e%252e/api/setup',
            '/ui/../api/setup',
            '/api/setup/',
            '/api/share',
        )
        for raw in attacks:
            route = normalize_route(raw)
            with self.subTest(raw=raw, route=route):
                self.assertFalse(allowed(route, 'GET'), f'{raw} -> {route}')
                self.assertFalse(allowed(route, 'POST'), f'{raw} -> {route}')

    def test_key_compare_is_constant_time_and_rejects_wrong_length(self):
        self.assertTrue(key_matches('abc', 'abc'))
        self.assertFalse(key_matches('abd', 'abc'))
        self.assertFalse(key_matches('ab', 'abc'))
        self.assertFalse(key_matches('', 'abc'))
        self.assertFalse(key_matches('abc', ''))

    def test_key_can_come_from_query_cookie_or_header(self):
        self.assertEqual(presented_key('/?key=secret', {}), ('secret', 'query'))
        self.assertEqual(presented_key('/', {'Cookie': 'sg_key=secret'}), ('secret', 'cookie'))
        self.assertEqual(presented_key('/', {'X-Lastbook-Key': 'secret'}), ('secret', 'header'))
        self.assertEqual(presented_key('/', {'Authorization': 'Bearer secret'}), ('secret', 'header'))
        self.assertEqual(presented_key('/', {}), (None, None))


class ShareFlag(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.settings = Path(self.dir.name) / 'settings'
        share.configure(self.settings)
        share._ERROR = None

    def tearDown(self):
        share._SETTINGS_DIR = None
        share._ERROR = None
        self.dir.cleanup()

    def test_off_by_default_including_ai(self):
        self.assertFalse(share.wanted())
        self.assertFalse(share.wanted_ai())
        self.settings.mkdir()
        (self.settings / share.FLAG).write_text('{', encoding='utf-8')
        self.assertFalse(share.wanted())
        self.assertFalse(share.wanted_ai())

    def test_ai_persists_separately_from_on(self):
        share.set_ai(True)
        self.assertTrue(share.wanted_ai())
        self.assertFalse(share.wanted())
        share._save_flag(on=True)
        self.assertTrue(share.wanted_ai())
        share._save_flag(on=False)
        self.assertTrue(share.wanted_ai())


class ShareListener(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.data = Path(self.dir.name) / 'data'
        self.settings = Path(self.dir.name) / 'settings'
        self.data.mkdir()
        self.here_patch = mock.patch.object(server, 'HERE', self.data)
        self.ports_patch = mock.patch.object(server, 'SHARE_PORTS', [0])
        self.here_patch.start()
        self.ports_patch.start()
        server.LAN_KEY = None
        share.configure(self.settings)
        share._ERROR = None
        server.stop_lan(wait=True)

    def tearDown(self):
        try:
            share.stop(forget=False, wait=True)
        finally:
            server.stop_lan(wait=True)
            server.LAN_KEY = None
            share._SETTINGS_DIR = None
            share._ERROR = None
            self.ports_patch.stop()
            self.here_patch.stop()
            self.dir.cleanup()

    def _start(self, handler=None):
        if handler is None:
            self.assertTrue(share.start())
            return server.SERVER
        server.load_lan_key()
        raw = server.bind_http(0, lan=True, handler=handler)
        from engine.share_http import ShareServer
        ShareServer(raw)
        server.SERVER = raw
        t = threading.Thread(target=raw.serve_forever, daemon=True, name='lastbook-share-test')
        server._LAN_THREAD = t
        t.start()
        share._save_flag(on=True)
        return raw

    def test_restore_does_nothing_when_off(self):
        share.restore()
        self.assertIsNone(server.SERVER)
        self.assertFalse(share.wanted())

    def test_share_switch_is_not_on_the_listener(self):
        h = H(ip='127.0.0.1', body={'on': True}, listener=True)
        share.handle(h, 'POST')
        self.assertEqual(h.status, 403)
        self.assertIsNone(server.SERVER)
        h = H(ip='192.168.1.20', body={'on': True})
        share.handle(h, 'POST')
        self.assertEqual(h.status, 403)

    def test_api_turns_sharing_on_from_the_bridge(self):
        h = H(ip='127.0.0.1', body={'on': True})
        share.handle(h, 'POST')
        self.assertEqual(h.status, 200)
        body = h.answer()
        self.assertTrue(body['on'])
        self.assertFalse(body['ai'])
        self.assertIsNotNone(server.SERVER)
        share.stop(forget=True, wait=True)

    def test_start_and_stop_open_and_close_the_port(self):
        self.assertTrue(share.start())
        port = server.SERVER.server_address[1]
        self.assertTrue(listening(port))
        share.stop(forget=True, wait=True)
        self.assertIsNone(server.SERVER)
        deadline = time.time() + 2
        while time.time() < deadline and listening(port):
            time.sleep(0.05)
        self.assertFalse(listening(port))

    def test_stop_without_forget_keeps_the_preference(self):
        self.assertTrue(share.start())
        share.stop(forget=False, wait=True)
        self.assertTrue(share.wanted())
        self.assertIsNone(server.SERVER)

    def test_restore_starts_when_left_on(self):
        self.settings.mkdir(parents=True, exist_ok=True)
        (self.settings / share.FLAG).write_text(json.dumps({'on': True}), encoding='utf-8')
        share.restore()
        self.assertIsNotNone(server.SERVER)
        self.assertTrue(share.status()['on'])
        share.stop(forget=False, wait=True)

    def test_socket_client_needs_the_key_even_on_loopback(self):
        self._start()
        port = server.SERVER.server_address[1]
        key = server.LAN_KEY
        c = HTTPConnection('127.0.0.1', port, timeout=3)
        c.request('GET', '/sw.js')
        r = c.getresponse(); body = r.read(); c.close()
        self.assertEqual(r.status, 403)
        c = HTTPConnection('127.0.0.1', port, timeout=3)
        c.request('GET', '/sw.js', headers={'X-Lastbook-Key': key})
        r = c.getresponse(); body = r.read(); c.close()
        self.assertNotEqual(r.status, 403)
        c = HTTPConnection('127.0.0.1', port, timeout=3)
        c.request('GET', '/api/setup/state', headers={'X-Lastbook-Key': key})
        r = c.getresponse(); body = r.read(); c.close()
        self.assertEqual(r.status, 403)
        self.assertIn(b'not part of what is shared', body)

    def test_wrong_key_is_refused(self):
        self._start()
        port = server.SERVER.server_address[1]
        c = HTTPConnection('127.0.0.1', port, timeout=3)
        c.request('GET', '/api/topics', headers={'X-Lastbook-Key': 'nope'})
        r = c.getresponse(); r.read(); c.close()
        self.assertEqual(r.status, 403)

    def test_restart_after_stop_works(self):
        self.assertTrue(share.start())
        port1 = server.SERVER.server_address[1]
        share.stop(forget=True, wait=True)
        self.assertFalse(listening(port1) and server.SERVER is not None)
        self.assertTrue(share.start())
        port2 = server.SERVER.server_address[1]
        self.assertTrue(listening(port2))
        share.stop(forget=True, wait=True)


class SlowShare(server.ShareHandler):
    """A share handler that streams a large Range-capable file slowly, so Stop can cut it."""

    def do_HEAD(self):
        return self.do_GET()

    def do_GET(self):
        if not self.host_ok():
            return self.send_error(403)
        if not self.share_admit():
            return
        if self.share_route == '/videos/slow.bin':
            data = b'V' * (2 * 1024 * 1024)
            start, end, status = 0, len(data) - 1, 200
            rng = self.headers.get('Range') or ''
            if rng.startswith('bytes='):
                spec = rng.split('=', 1)[1].split(',')[0]
                a, _, b = spec.partition('-')
                try:
                    start = int(a) if a else 0
                    end = int(b) if b else len(data) - 1
                except ValueError:
                    start, end = 0, len(data) - 1
                end = min(end, len(data) - 1)
                status = 206
            chunk = data[start:end + 1]
            self.send_response(status)
            self.send_header('Content-Type', 'application/octet-stream')
            self.send_header('Content-Length', str(len(chunk)))
            self.send_header('Accept-Ranges', 'bytes')
            if status == 206:
                self.send_header('Content-Range', f'bytes {start}-{end}/{len(data)}')
            self.end_headers()
            if self.command == 'HEAD':
                return
            try:
                for i in range(0, len(chunk), 32 * 1024):
                    self.wfile.write(chunk[i:i + 32 * 1024])
                    self.wfile.flush()
                    time.sleep(0.05)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, TimeoutError):
                return
            return
        return super().do_GET()


class StopCutsStream(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.data = Path(self.dir.name) / 'data'
        self.data.mkdir()
        self.here_patch = mock.patch.object(server, 'HERE', self.data)
        self.here_patch.start()
        server.LAN_KEY = None
        server.stop_lan(wait=True)
        share.configure(Path(self.dir.name) / 'settings')
        share._ERROR = None

    def tearDown(self):
        server.stop_lan(wait=True)
        server.LAN_KEY = None
        share._SETTINGS_DIR = None
        self.here_patch.stop()
        self.dir.cleanup()

    def test_range_then_stop_cuts_the_stream_and_frees_the_port(self):
        server.load_lan_key()
        raw = server.bind_http(0, lan=True, handler=SlowShare)
        from engine.share_http import ShareServer
        ShareServer(raw)
        server.SERVER = raw
        t = threading.Thread(target=raw.serve_forever, daemon=True)
        server._LAN_THREAD = t
        t.start()
        port = raw.server_address[1]
        key = server.LAN_KEY
        got = []
        err = []

        def download():
            try:
                c = HTTPConnection('127.0.0.1', port, timeout=8)
                c.request('GET', '/videos/slow.bin', headers={'X-Lastbook-Key': key, 'Range': 'bytes=0-1048575'})
                r = c.getresponse()
                got.append(r.status)
                buf = b''
                while True:
                    piece = r.read(16 * 1024)
                    if not piece:
                        break
                    buf += piece
                got.append(len(buf))
                c.close()
            except Exception as e:
                err.append(e)

        worker = threading.Thread(target=download)
        worker.start()
        time.sleep(0.2)
        # First, a small Range request should get 206.
        c = HTTPConnection('127.0.0.1', port, timeout=3)
        c.request('HEAD', '/videos/slow.bin', headers={'X-Lastbook-Key': key, 'Range': 'bytes=0-99'})
        r = c.getresponse(); r.read(); c.close()
        self.assertEqual(r.status, 206)
        server.stop_lan(wait=True)
        worker.join(6)
        self.assertFalse(listening(port))
        self.assertIsNone(server.SERVER)
        # The downloader was cut (error or a short body), not given the full megabyte after a long wait.
        if got and len(got) >= 2 and got[0] == 206:
            self.assertLess(got[1], 1024 * 1024)
        else:
            self.assertTrue(err or (got and got[0] != 200))


if __name__ == '__main__':
    unittest.main()
