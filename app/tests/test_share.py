"""Share this library with my devices: a dedicated allowlist listener, a key on every
socket request, a normalized route for access and dispatch, and Stop that cuts streams.

  python3 -B -m unittest app.tests.test_share
"""
import io, json, os, socket, sys, tempfile, threading, time, unittest
from http.client import HTTPConnection
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'app'), str(HERE)]

import server  # noqa: E402
from engine import share  # noqa: E402
from engine.share_http import allowed, key_matches, normalize_route, presented_key, should_redirect_key  # noqa: E402


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

    def test_only_html_navigations_redirect_the_key(self):
        self.assertTrue(should_redirect_key('/', 'GET'))
        self.assertTrue(should_redirect_key('/index.html', 'GET'))
        self.assertTrue(should_redirect_key('/ui/about.html', 'GET'))
        self.assertFalse(should_redirect_key('/sw.js', 'GET'))
        self.assertFalse(should_redirect_key('/ui/app.js', 'GET'))
        self.assertFalse(should_redirect_key('/api/topics', 'GET'))
        self.assertFalse(should_redirect_key('/api/topics', 'POST'))
        self.assertFalse(should_redirect_key('/videos/a.mp4', 'GET'))
        self.assertFalse(should_redirect_key('/videos-external/a.mkv', 'GET'))
        self.assertFalse(should_redirect_key('/documents/a.pdf', 'GET'))
        self.assertFalse(should_redirect_key('/', 'GET', {'Range': 'bytes=0-99'}))
        self.assertFalse(should_redirect_key('/videos/a.mp4', 'GET', {'Range': 'bytes=0-99'}))
        self.assertFalse(should_redirect_key('/', 'HEAD'))


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
            return server.SHARE_SERVER
        server.load_lan_key()
        raw = server.bind_http(0, lan=True, handler=handler)
        from engine.share_http import ShareServer
        ShareServer(raw)
        server.SHARE_SERVER = raw
        t = threading.Thread(target=raw.serve_forever, daemon=True, name='lastbook-share-test')
        server._SHARE_THREAD = t
        t.start()
        share._save_flag(on=True)
        return raw

    def test_restore_does_nothing_when_off(self):
        share.restore()
        self.assertIsNone(server.SHARE_SERVER)
        self.assertFalse(share.wanted())

    def test_share_switch_is_not_on_the_listener(self):
        h = H(ip='127.0.0.1', body={'on': True}, listener=True)
        share.handle(h, 'POST')
        self.assertEqual(h.status, 403)
        self.assertIsNone(server.SHARE_SERVER)
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
        self.assertIsNotNone(server.SHARE_SERVER)
        share.stop(forget=True, wait=True)

    def test_start_and_stop_open_and_close_the_port(self):
        self.assertTrue(share.start())
        port = server.SHARE_SERVER.server_address[1]
        self.assertTrue(listening(port))
        share.stop(forget=True, wait=True)
        self.assertIsNone(server.SHARE_SERVER)
        deadline = time.time() + 2
        while time.time() < deadline and listening(port):
            time.sleep(0.05)
        self.assertFalse(listening(port))

    def test_stop_without_forget_keeps_the_preference(self):
        self.assertTrue(share.start())
        share.stop(forget=False, wait=True)
        self.assertTrue(share.wanted())
        self.assertIsNone(server.SHARE_SERVER)

    def test_restore_starts_when_left_on(self):
        self.settings.mkdir(parents=True, exist_ok=True)
        (self.settings / share.FLAG).write_text(json.dumps({'on': True}), encoding='utf-8')
        share.restore()
        self.assertIsNotNone(server.SHARE_SERVER)
        self.assertTrue(share.status()['on'])
        share.stop(forget=False, wait=True)

    def test_socket_client_needs_the_key_even_on_loopback(self):
        self._start()
        port = server.SHARE_SERVER.server_address[1]
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
        port = server.SHARE_SERVER.server_address[1]
        c = HTTPConnection('127.0.0.1', port, timeout=3)
        c.request('GET', '/api/topics', headers={'X-Lastbook-Key': 'nope'})
        r = c.getresponse(); r.read(); c.close()
        self.assertEqual(r.status, 403)

    def test_restart_after_stop_works(self):
        self.assertTrue(share.start())
        port1 = server.SHARE_SERVER.server_address[1]
        share.stop(forget=True, wait=True)
        self.assertFalse(listening(port1) and server.SHARE_SERVER is not None)
        self.assertTrue(share.start())
        port2 = server.SHARE_SERVER.server_address[1]
        self.assertTrue(listening(port2))
        share.stop(forget=True, wait=True)

    def test_html_query_key_redirects_to_a_clean_url(self):
        self._start()
        port = server.SHARE_SERVER.server_address[1]
        key = server.LAN_KEY
        c = HTTPConnection('127.0.0.1', port, timeout=3)
        c.request('GET', f'/?key={key}&from=videos')
        r = c.getresponse(); body = r.read(); headers = dict(r.getheaders()); c.close()
        self.assertEqual(r.status, 302)
        self.assertEqual(headers.get('Location'), '/?from=videos')
        cookie = headers.get('Set-Cookie') or headers.get('set-cookie') or ''
        self.assertIn('sg_key=', cookie)
        # After the cookie is set, the clean URL is enough.
        c = HTTPConnection('127.0.0.1', port, timeout=3)
        c.request('GET', '/?from=videos', headers={'Cookie': f'sg_key={key}'})
        r = c.getresponse(); r.read(); c.close()
        self.assertEqual(r.status, 200)

    def test_api_and_video_query_key_are_not_redirected(self):
        raw = self._start(SlowShare)
        port = raw.server_address[1]
        key = server.LAN_KEY
        c = HTTPConnection('127.0.0.1', port, timeout=3)
        c.request('GET', f'/sw.js?key={key}')
        r = c.getresponse(); r.read(); headers = dict(r.getheaders()); c.close()
        self.assertEqual(r.status, 200)
        self.assertIsNone(headers.get('Location'))
        c = HTTPConnection('127.0.0.1', port, timeout=3)
        c.request('GET', f'/videos/slow.bin?key={key}', headers={'Range': 'bytes=0-99'})
        r = c.getresponse(); body = r.read(); headers = dict(r.getheaders()); c.close()
        self.assertEqual(r.status, 206)
        self.assertIsNone(headers.get('Location'))
        self.assertEqual(len(body), 100)

    def test_finished_workers_are_removed(self):
        self._start()
        port = server.SHARE_SERVER.server_address[1]
        key = server.LAN_KEY
        wrapper = server.SHARE_SERVER.share
        for _ in range(5):
            c = HTTPConnection('127.0.0.1', port, timeout=3)
            c.request('GET', '/sw.js', headers={'X-Lastbook-Key': key})
            r = c.getresponse(); r.read(); c.close()
            self.assertEqual(r.status, 200)
        deadline = time.time() + 2
        while time.time() < deadline and wrapper.live_workers():
            time.sleep(0.05)
        self.assertEqual(wrapper.live_workers(), 0)

    def test_start_and_stop_sharing_leaves_the_local_reader(self):
        """The share switch must not start, stop, or report the ordinary loopback reader."""
        reader = server.bind_http(0, lan=False, handler=server.Handler)
        server.SERVER = reader
        rt = threading.Thread(target=reader.serve_forever, daemon=True, name='lastbook-reader-test')
        rt.start()
        rport = reader.server_address[1]
        try:
            c = HTTPConnection('127.0.0.1', rport, timeout=3)
            c.request('GET', '/sw.js')
            r = c.getresponse(); r.read(); c.close()
            self.assertEqual(r.status, 200)

            self.assertTrue(share.start())
            self.assertIs(server.SERVER, reader)
            self.assertIsNotNone(server.SHARE_SERVER)
            sport = server.SHARE_SERVER.server_address[1]
            self.assertNotEqual(sport, rport)
            self.assertTrue(share.status()['on'])
            self.assertEqual(share.status()['port'], sport)

            # The share listener still requires the key.
            c = HTTPConnection('127.0.0.1', sport, timeout=3)
            c.request('GET', '/sw.js')
            r = c.getresponse(); r.read(); c.close()
            self.assertEqual(r.status, 403)

            # The local reader stays up, still without a key.
            c = HTTPConnection('127.0.0.1', rport, timeout=3)
            c.request('GET', '/sw.js')
            r = c.getresponse(); r.read(); c.close()
            self.assertEqual(r.status, 200)

            share.stop(forget=True, wait=True)
            self.assertIsNone(server.SHARE_SERVER)
            self.assertIs(server.SERVER, reader)
            self.assertFalse(share.status()['on'])
            self.assertTrue(listening(rport))
            c = HTTPConnection('127.0.0.1', rport, timeout=3)
            c.request('GET', '/sw.js')
            r = c.getresponse(); r.read(); c.close()
            self.assertEqual(r.status, 200)
        finally:
            try:
                reader.shutdown()
            except Exception:
                pass
            try:
                reader.server_close()
            except Exception:
                pass
            rt.join(timeout=3)
            if server.SERVER is reader:
                server.SERVER = None


class ShareKeyFile(unittest.TestCase):
    """The share switch and server.py --lan both go through load_lan_key() / lan_key().
    Keys in these tests are synthetic, or compared without being printed."""

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

    def _kf(self):
        return self.data / 'derived' / 'lan-key'

    def test_fresh_folder_stays_off_and_has_no_key_until_start(self):
        """A new library, after the launch restore path, must not listen or write derived/lan-key."""
        self.assertFalse(self._kf().exists())
        share.restore()
        self.assertIsNone(server.SHARE_SERVER)
        self.assertFalse(share.wanted())
        self.assertFalse(self._kf().exists())
        self.assertTrue(share.start())
        kf = self._kf()
        self.assertTrue(kf.is_file())
        first = kf.read_text(encoding='utf-8').strip()
        self.assertGreaterEqual(len(first), 20)
        self.assertEqual(server.LAN_KEY, first)
        if os.name != 'nt':
            self.assertEqual(kf.stat().st_mode & 0o777, 0o600)

    def test_second_start_reuses_the_same_key(self):
        self.assertTrue(share.start())
        first = server.LAN_KEY
        share.stop(forget=True, wait=True)
        self.assertIsNone(server.SHARE_SERVER)
        self.assertTrue(share.start())
        self.assertEqual(server.LAN_KEY, first)
        self.assertEqual(self._kf().read_text(encoding='utf-8').strip(), first)

    def test_existing_key_from_an_older_version_is_reused_and_served(self):
        synthetic = 'synthetic-old-key-from-earlier-version'
        kf = self._kf()
        kf.parent.mkdir(parents=True, exist_ok=True)
        kf.write_text(synthetic, encoding='utf-8')
        if os.name != 'nt':
            os.chmod(kf, 0o644)
        self.assertTrue(share.start())
        self.assertEqual(server.LAN_KEY, synthetic)
        self.assertEqual(kf.read_text(encoding='utf-8'), synthetic)
        port = server.SHARE_SERVER.server_address[1]
        c = HTTPConnection('127.0.0.1', port, timeout=3)
        c.request('GET', '/sw.js', headers={'X-Lastbook-Key': synthetic})
        r = c.getresponse(); r.read(); c.close()
        self.assertEqual(r.status, 200)
        c = HTTPConnection('127.0.0.1', port, timeout=3)
        c.request('GET', '/sw.js', headers={'X-Lastbook-Key': 'wrong-synthetic-key'})
        r = c.getresponse(); r.read(); c.close()
        self.assertEqual(r.status, 403)

    def test_load_lan_key_wraps_lan_key(self):
        first = server.load_lan_key()
        second = server.load_lan_key()
        self.assertEqual(first, second)
        self.assertEqual(first, server.lan_key(self._kf()))
        self.assertEqual(server.LAN_KEY, first)

    def test_stop_closes_the_port_and_leaves_the_local_reader(self):
        reader = server.bind_http(0, lan=False, handler=server.Handler)
        server.SERVER = reader
        rt = threading.Thread(target=reader.serve_forever, daemon=True, name='lastbook-reader-keyfile-test')
        rt.start()
        rport = reader.server_address[1]
        try:
            self.assertTrue(share.start())
            sport = server.SHARE_SERVER.server_address[1]
            self.assertNotEqual(sport, rport)
            share.stop(forget=True, wait=True)
            self.assertIsNone(server.SHARE_SERVER)
            self.assertFalse(listening(sport))
            self.assertIs(server.SERVER, reader)
            self.assertTrue(listening(rport))
            c = HTTPConnection('127.0.0.1', rport, timeout=3)
            c.request('GET', '/sw.js')
            r = c.getresponse(); r.read(); c.close()
            self.assertEqual(r.status, 200)
        finally:
            try:
                reader.shutdown()
            except Exception:
                pass
            try:
                reader.server_close()
            except Exception:
                pass
            rt.join(timeout=3)
            if server.SERVER is reader:
                server.SERVER = None


class ShareKeyPrivate(unittest.TestCase):
    """The key file must be known to be private, or sharing does not start. Every key here is synthetic."""

    FAKE = 'synthetic-key-never-real'

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.data = Path(self.dir.name) / 'data'
        self.settings = Path(self.dir.name) / 'settings'
        self.data.mkdir()
        self.patches = [mock.patch.object(server, 'HERE', self.data), mock.patch.object(server, 'SHARE_PORTS', [0])]
        for p in self.patches:
            p.start()
        server.LAN_KEY = None
        share.configure(self.settings)
        share._ERROR = None
        server.stop_lan(wait=True)
        self.kf = self.data / 'derived' / 'lan-key'

    def tearDown(self):
        server.stop_lan(wait=True)
        server.LAN_KEY = None
        share._SETTINGS_DIR = None
        share._ERROR = None
        for p in self.patches:
            p.stop()
        self.dir.cleanup()

    def old_key(self, mode=0o644):
        self.kf.parent.mkdir(parents=True, exist_ok=True)
        self.kf.write_text(self.FAKE, encoding='utf-8')
        os.chmod(self.kf, mode)

    # --- the decision on a POSIX file
    @unittest.skipIf(os.name == 'nt', 'POSIX file modes')
    def test_private_file_passes(self):
        key = server.load_lan_key()
        self.assertEqual(server.LAN_KEY, key)
        self.assertTrue(server.key_file_private(self.kf))

    @unittest.skipIf(os.name == 'nt', 'POSIX file modes')
    def test_group_or_other_bits_are_not_private(self):
        self.old_key(0o644)
        self.assertFalse(server.key_file_private(self.kf))
        os.chmod(self.kf, 0o640)
        self.assertFalse(server.key_file_private(self.kf))
        os.chmod(self.kf, 0o600)
        self.assertTrue(server.key_file_private(self.kf))

    @unittest.skipIf(os.name == 'nt', 'POSIX file modes')
    def test_an_old_readable_key_is_tightened_and_accepted(self):
        self.old_key(0o644)
        self.assertEqual(server.load_lan_key(), self.FAKE)
        self.assertEqual(self.kf.stat().st_mode & 0o777, 0o600)

    @unittest.skipIf(os.name == 'nt', 'POSIX file modes')
    def test_chmod_refused_means_refusal(self):
        """A drive with no mode bits (exFAT, FAT): the old key stays readable by everyone, so there is no key and no sharing."""
        self.old_key(0o644)
        with mock.patch.object(server.os, 'chmod', side_effect=PermissionError('not permitted')):
            with self.assertRaises(server.KeyNotPrivate) as cm:
                server.load_lan_key()
        self.assertIsNone(server.LAN_KEY)
        self.assertEqual(str(cm.exception), server.KEY_NOT_PRIVATE)
        self.assertNotIn(self.FAKE, str(cm.exception))
        self.assertTrue(self.kf.exists())   # the person's own file is not deleted

    @unittest.skipIf(os.name == 'nt', 'POSIX file modes')
    def test_chmod_that_does_nothing_means_refusal(self):
        """chmod answers yes but the mode is stuck (some network and removable drives)."""
        self.old_key(0o644)
        with mock.patch.object(server.os, 'chmod', side_effect=lambda *a, **k: None):
            with self.assertRaises(server.KeyNotPrivate):
                server.load_lan_key()
        self.assertIsNone(server.LAN_KEY)

    def test_a_key_made_for_the_refusal_is_not_left_behind(self):
        with mock.patch.object(server, 'key_file_private', return_value=False):
            with self.assertRaises(server.KeyNotPrivate):
                server.load_lan_key()
        self.assertFalse(self.kf.exists())
        self.assertIsNone(server.LAN_KEY)

    def test_a_real_error_is_not_called_a_privacy_refusal(self):
        with mock.patch.object(server.tempfile, 'mkstemp', side_effect=OSError('disk full')):
            with self.assertRaises(OSError) as cm:
                server.load_lan_key()
        self.assertNotIsInstance(cm.exception, server.KeyNotPrivate)

    # --- Windows: who may open the file (SDDL text from the system; mocked here)
    USER = 'S-1-5-21-1000-2000-3000-1001'

    def test_windows_acl_only_user_system_admins_is_private(self):
        for sddl in (
            f'D:PAI(A;;FA;;;{self.USER})(A;;FA;;;SY)(A;;FA;;;BA)',
            f'D:(A;;FA;;;SY)(A;;FA;;;BA)(A;;0x1200a9;;;{self.USER})',
            'D:PAI(A;;FA;;;S-1-5-18)(A;;FA;;;S-1-5-32-544)(A;;FA;;;%s)' % self.USER,
            f'D:AI(A;ID;FA;;;{self.USER})(A;ID;FA;;;SY)(A;ID;FA;;;BA)(D;;FR;;;WD)',   # a refusal for Everyone only narrows
        ):
            with self.subTest(sddl=sddl):
                self.assertTrue(server.sddl_is_private(sddl, self.USER))

    def test_windows_acl_with_anyone_else_is_not_private(self):
        for who in ('WD', 'BU', 'AU', 'IU', 'S-1-1-0', 'S-1-5-32-545', 'S-1-5-21-1000-2000-3000-1002', 'CO', 'OW'):
            sddl = f'D:PAI(A;;FA;;;{self.USER})(A;;FA;;;SY)(A;;FA;;;BA)(A;;0x1200a9;;;{who})'
            with self.subTest(who=who):
                self.assertFalse(server.sddl_is_private(sddl, self.USER))

    def test_windows_acl_that_cannot_be_read_is_not_private(self):
        for sddl in ('', None, 'O:BAG:SY', 'D:', 'D:NO_ACCESS_CONTROL', 'D:(A;;FA;;SY)', 'D:(X;;FA;;;SY)', 'D:((A;;FA;;;SY'):
            with self.subTest(sddl=sddl):
                self.assertFalse(server.sddl_is_private(sddl, self.USER))
        self.assertFalse(server.sddl_is_private(f'D:(A;;FA;;;{self.USER})', None))

    def test_windows_access_list_that_cannot_be_asked_is_not_private(self):
        # Off Windows there is no such call, and on a drive with no access lists the call fails: both count as not private.
        if os.name != 'nt':
            self.assertFalse(server._windows_key_private(self.kf))

    def test_windows_uses_the_access_list_not_modes(self):
        with mock.patch.object(server.os, 'name', 'nt'), mock.patch.object(server, '_windows_key_private', return_value=True) as w:
            self.assertTrue(server.key_file_private(self.kf))
            w.assert_called_once_with(self.kf)
        with mock.patch.object(server.os, 'name', 'nt'), mock.patch.object(server, '_windows_key_private', return_value=False):
            self.assertFalse(server.key_file_private(self.kf))

    # --- the Share switch
    def refused_start(self):
        self.old_key(0o644)
        return mock.patch.object(server, 'key_file_private', return_value=False)

    def test_share_switch_refuses_without_starting_anything(self):
        reader = server.bind_http(0, lan=False, handler=server.Handler)
        server.SERVER = reader
        rt = threading.Thread(target=reader.serve_forever, daemon=True)
        rt.start()
        try:
            with self.refused_start(), mock.patch.object(server, 'bind_http', wraps=server.bind_http) as bind:
                self.assertFalse(share.start())
                bind.assert_not_called()   # no port was opened
            self.assertIsNone(server.SHARE_SERVER)
            st = share.status()
            self.assertFalse(st['on'])
            self.assertIsNone(st['link'])
            self.assertEqual(st['error'], server.KEY_NOT_PRIVATE)
            self.assertFalse(share.wanted())   # nothing was saved as "left on"
            self.assertTrue(listening(reader.server_address[1]))   # the local reader is untouched
        finally:
            reader.shutdown(); reader.server_close(); rt.join(timeout=3)
            server.SERVER = None

    def test_share_switch_api_returns_the_message(self):
        with self.refused_start():
            h = H(body={'on': True})
            share.handle(h, 'POST')
        body = json.loads(h.wfile.getvalue())
        self.assertEqual(body['on'], False)
        self.assertEqual(body['error'], server.KEY_NOT_PRIVATE)
        self.assertNotIn(self.FAKE, h.wfile.getvalue().decode())
        self.assertIsNone(server.SHARE_SERVER)

    def test_restore_after_relaunch_refuses_the_same_way(self):
        share._save_flag(on=True)
        with self.refused_start():
            share.restore()
        self.assertIsNone(server.SHARE_SERVER)
        self.assertEqual(share.status()['error'], server.KEY_NOT_PRIVATE)

    def test_refusal_clears_after_the_key_can_be_kept_private(self):
        with self.refused_start():
            self.assertFalse(share.start())
        self.assertTrue(share.start())   # the folder is fixed: the next try works
        self.assertIsNone(share.status()['error'])
        self.assertTrue(share.status()['on'])

    def test_the_key_is_never_printed_on_refusal(self):
        import contextlib
        out = io.StringIO()
        with self.refused_start(), contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            share.start()
        self.assertNotIn(self.FAKE, out.getvalue())

    # --- server.py --lan
    def test_lan_start_exits_with_the_same_message_and_opens_no_port(self):
        with self.refused_start(), mock.patch.object(server, 'bind_http') as bind:
            with self.assertRaises(SystemExit) as cm:
                server.serve(0, lan=True)
        bind.assert_not_called()
        self.assertEqual(str(cm.exception.code), server.KEY_NOT_PRIVATE)
        self.assertNotIn(self.FAKE, str(cm.exception.code))
        self.assertIsNone(server.SHARE_SERVER)


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
        server.SHARE_SERVER = raw
        t = threading.Thread(target=raw.serve_forever, daemon=True)
        server._SHARE_THREAD = t
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
        self.assertIsNone(server.SHARE_SERVER)
        # The downloader was cut (error or a short body), not given the full megabyte after a long wait.
        if got and len(got) >= 2 and got[0] == 206:
            self.assertLess(got[1], 1024 * 1024)
        else:
            self.assertTrue(err or (got and got[0] != 200))


if __name__ == '__main__':
    unittest.main()
