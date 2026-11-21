"""Share this library with my devices: off unless turned on, no port when off, other devices are
read-only, and the access key is required.

  python3 -B -m unittest app.tests.test_share
"""
import io, json, socket, sys, tempfile, threading, time, unittest
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'app'), str(HERE)]

import server  # noqa: E402
from engine import share  # noqa: E402


def listening(port):
    try:
        s = socket.create_connection(('127.0.0.1', port), timeout=0.4)
        s.close()
        return True
    except OSError:
        return False


class H:
    """A stand-in for the HTTP handler, for /api/share and admit()."""
    def __init__(self, ip='127.0.0.1', path='/api/share', body=None, cookie=None):
        raw = b'' if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
        self.client_address, self.path = (ip, 1), path
        self.headers = {'Content-Length': str(len(raw))}
        if cookie:
            self.headers['Cookie'] = 'sg_key=' + cookie
        self.rfile, self.wfile, self.status, self.calls = io.BytesIO(raw), io.BytesIO(), None, []

    def send_response(self, s):
        self.status = s

    def send_header(self, *a):
        pass

    def end_headers(self):
        pass

    def send_json(self, obj, status=200, cache=None):
        self.status = status
        self.wfile.write(json.dumps(obj).encode())

    def deny(self):
        self.calls.append('deny')
        self.status = 403

    def deny_local_only(self):
        self.calls.append('local')
        self.status = 403

    def answer(self):
        return json.loads(self.wfile.getvalue())

    def lan_ok(self):
        return server.Handler.lan_ok(self)

    def admit(self):
        return server.Handler.admit(self)


class Share(unittest.TestCase):
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

    def test_off_by_default_and_missing_flag(self):
        self.assertFalse(share.wanted())
        self.assertFalse((self.settings / share.FLAG).exists())
        self.settings.mkdir()
        (self.settings / share.FLAG).write_text('{', encoding='utf-8')
        self.assertFalse(share.wanted())
        self.assertIsNone(server.SERVER)

    def test_restore_does_nothing_when_off(self):
        share.restore()
        self.assertIsNone(server.SERVER)
        self.assertFalse(share.wanted())

    def test_loopback_and_remote_allow_list(self):
        self.assertTrue(server.is_loopback('127.0.0.1'))
        self.assertTrue(server.is_loopback('::1'))
        self.assertTrue(server.is_loopback('::ffff:127.0.0.1'))
        self.assertFalse(server.is_loopback('192.168.1.20'))
        self.assertFalse(server.is_loopback('10.0.0.4'))
        blocked = (
            '/api/setup', '/api/setup/state', '/api/update/check', '/api/battery',
            '/api/not-found', '/api/not-found/1', '/api/assistant/local',
            '/api/tool/search_library', '/api/tools', '/api/share',
        )
        allowed = ('/', '/api/topics', '/api/find', '/api/chat', '/api/shelves', '/ui/setup.html')
        for path in blocked:
            with self.subTest(path=path):
                self.assertTrue(server.remote_blocked(path), path)
        for path in allowed:
            with self.subTest(path=path):
                self.assertFalse(server.remote_blocked(path), path)

    def test_key_required_and_remote_blocked_at_the_door(self):
        server.LAN_KEY = 'test-key-not-for-use'
        # This computer: setup stays available, no key needed.
        h = H(ip='127.0.0.1', path='/api/setup/state')
        self.assertTrue(h.admit())
        self.assertEqual(h.calls, [])
        # Another device, no key: refused.
        h = H(ip='192.168.1.20', path='/api/topics')
        self.assertFalse(h.admit())
        self.assertEqual(h.calls, ['deny'])
        # Another device, with the cookie: can read the library.
        h = H(ip='192.168.1.20', path='/api/topics', cookie='test-key-not-for-use')
        self.assertTrue(h.admit())
        self.assertEqual(h.calls, [])
        # But not setup, notes, updates, or the share switch.
        for path in ('/api/setup/state', '/api/update/check', '/api/battery', '/api/not-found',
                     '/api/assistant/local', '/api/tools', '/api/share'):
            h = H(ip='192.168.1.20', path=path, cookie='test-key-not-for-use')
            self.assertFalse(h.admit(), path)
            self.assertEqual(h.calls, ['local'], path)

    def test_share_switch_is_this_computer_only(self):
        h = H(ip='192.168.1.20', body={'on': True})
        share.handle(h, 'POST')
        self.assertEqual(h.status, 403)
        self.assertIsNone(server.SERVER)
        self.assertFalse(share.wanted())

    def test_start_and_stop_open_and_close_the_port(self):
        self.assertIsNone(server.SERVER)
        self.assertTrue(share.start())
        self.assertTrue(share.wanted())
        self.assertTrue(json.loads((self.settings / share.FLAG).read_text(encoding='utf-8'))['on'])
        port = server.SERVER.server_address[1]
        self.assertTrue(port)
        self.assertTrue(listening(port))
        st = share.status()
        self.assertTrue(st['on'])
        self.assertEqual(st['port'], port)
        if st['ip'] and st['link']:
            self.assertIn(server.LAN_KEY, st['link'])
            self.assertTrue(st['link'].startswith('http://'))
            self.assertNotIn('key', st)  # the raw key is not a field of its own
        share.stop(forget=True, wait=True)
        self.assertFalse(share.wanted())
        self.assertIsNone(server.SERVER)
        # The port may sit in TIME_WAIT for a moment; connection should be refused, or at least
        # the app no longer owns a server.
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

    def test_start_failure_does_not_raise(self):
        busy = socket.socket()
        busy.bind(('127.0.0.1', 0))
        taken = busy.getsockname()[1]
        self.addCleanup(busy.close)
        with mock.patch.object(server, 'SHARE_PORTS', [taken]):
            self.assertFalse(share.start())
        self.assertIsNone(server.SERVER)
        self.assertFalse(share.wanted())
        self.assertTrue(share._ERROR)

    def test_api_turns_sharing_on(self):
        h = H(ip='127.0.0.1', body={'on': True})
        share.handle(h, 'POST')
        self.assertEqual(h.status, 200)
        body = h.answer()
        self.assertTrue(body['on'])
        self.assertTrue(share.wanted())
        self.assertIsNotNone(server.SERVER)
        share.stop(forget=True, wait=True)


if __name__ == '__main__':
    unittest.main()
