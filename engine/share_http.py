"""The local-network share listener: a dedicated handler, a read-only allowlist, and a
credential on every socket request.

This is separate from the desktop app's in-memory bridge and from server.py's loopback
Handler, which remain the only paths to settings, setup, updates, notes and other
private state. server.py --lan uses this same listener.
"""
from __future__ import annotations

import posixpath
import re
import secrets
import socket
import threading
import urllib.parse

# Library browsing (GET/HEAD). Deny by default: a path not listed here is refused.
SHARE_EXACT = frozenset({
    '/', '/index.html', '/sw.js', '/reader.css',
    '/api/topics', '/api/find', '/api/videos', '/api/shelves',
    '/api/collection', '/api/collection-search', '/api/search',
    '/api/library', '/api/places', '/api/health',
    '/api/map/info', '/api/map/near', '/api/map/pins', '/api/map/members',
    '/api/map/resources',
    '/api/assistant/status',  # answered by the share handler; Chat itself is opt-in
})

SHARE_PREFIXES = (
    '/ui/',
    '/api/doc/',
    '/api/page/',
    '/api/transcript/',
    '/api/videos/',
    '/api/shelf/',
    '/api/map/',
    '/zim/',
    '/documents/',
    '/pages/',
    '/videos/',
    '/videos-external/',
    '/transcripts/',
    '/metadata/videos/',
    '/courses/',
    '/collections/',
    '/assets/',
)

# Pages that turn the host or its settings; not served even under /ui/.
_UI_BLOCKED = ('setup', 'update')

# Host local AI, only when the person turned on that separate share option.
SHARE_AI_EXACT_GET = frozenset({'/api/retrieve'})
SHARE_AI_EXACT_POST = frozenset({'/api/chat'})


def normalize_route(raw):
    """One path for both the allowlist and dispatch.

    Query and fragment are dropped, percent-encoding is decoded (including nested
    encodings), slashes are collapsed, and '.' / '..' segments are resolved. Returns
    None when the target is not a usable path (NUL, backslash, or undecodable).
    """
    if raw is None:
        return None
    path = str(raw).split('?', 1)[0].split('#', 1)[0]
    if '\\' in path or '\0' in path:
        return None
    decoded = path
    for _ in range(5):
        nxt = urllib.parse.unquote(decoded)
        if nxt == decoded:
            break
        decoded = nxt
    else:
        return None
    if '\0' in decoded or '\\' in decoded:
        return None
    if not decoded.startswith('/'):
        decoded = '/' + decoded
    while '//' in decoded:
        decoded = decoded.replace('//', '/')
    norm = posixpath.normpath(decoded)
    if norm == '.':
        norm = '/'
    if not norm.startswith('/'):
        norm = '/' + norm
    if len(norm) > 1 and norm.endswith('/'):
        norm = norm[:-1]
    return norm


def _ui_ok(route):
    if not route.startswith('/ui/'):
        return False
    name = route[4:]
    first = name.split('/', 1)[0].lower()
    return not any(first.startswith(p) for p in _UI_BLOCKED)


def allowed(route, method='GET', ai=False):
    """True only if this method on this normalized route is on the share allowlist."""
    if not route:
        return False
    method = (method or 'GET').upper()
    if method not in ('GET', 'HEAD', 'POST'):
        return False
    if method == 'POST':
        return bool(ai) and route in SHARE_AI_EXACT_POST
    if route in SHARE_EXACT:
        return True
    if ai and route in SHARE_AI_EXACT_GET:
        return True
    if route.startswith('/ui/'):
        return _ui_ok(route)
    return any(route.startswith(p) for p in SHARE_PREFIXES if p != '/ui/')


def key_matches(given, expected):
    """Constant-time comparison. Different lengths are not equal and do not raise."""
    if not given or not expected:
        return False
    if isinstance(given, str):
        given = given.encode('utf-8')
    if isinstance(expected, str):
        expected = expected.encode('utf-8')
    if len(given) != len(expected):
        secrets.compare_digest(expected, expected)
        return False
    return secrets.compare_digest(given, expected)


def presented_key(path, headers):
    """The key the client sent, and where it came from: 'query', 'header', or 'cookie'."""
    get = headers.get if headers is not None else lambda *a: None
    qs = urllib.parse.parse_qs(urllib.parse.urlsplit(path or '').query)
    q = (qs.get('key') or [''])[0]
    if q:
        return q, 'query'
    auth = get('Authorization') or get('authorization') or ''
    if isinstance(auth, str) and auth.lower().startswith('bearer '):
        return auth[7:].strip(), 'header'
    hdr = get('X-Lastbook-Key') or get('x-lastbook-key')
    if hdr:
        return str(hdr).strip(), 'header'
    cookie = get('Cookie') or get('cookie') or ''
    m = re.search(r'(?:^|;\s*)sg_key=([^;]+)', cookie)
    if m:
        return urllib.parse.unquote(m.group(1)), 'cookie'
    return None, None


class ShareServer:
    """A ThreadingHTTPServer that can close every active client, including a stream in progress."""

    def __init__(self, server):
        self.server = server
        self._conns = set()
        self._threads = set()
        self._lock = threading.Lock()
        self.stopping = threading.Event()
        # Wrap the stock methods so we can see every socket and worker.
        orig_finish = server.finish_request
        orig_process = server.process_request
        orig_close = server.shutdown_request
        outer = self

        def finish_request(request, client_address):
            with outer._lock:
                outer._conns.add(request)
            try:
                return orig_finish(request, client_address)
            finally:
                with outer._lock:
                    outer._conns.discard(request)

        def process_request(request, client_address):
            t = threading.Thread(
                target=server.process_request_thread,
                args=(request, client_address),
                daemon=True,
                name='lastbook-share-client',
            )
            with outer._lock:
                outer._threads.add(t)
            t.start()

        def shutdown_request(request):
            try:
                return orig_close(request)
            finally:
                with outer._lock:
                    outer._conns.discard(request)

        server.finish_request = finish_request
        server.process_request = process_request
        server.shutdown_request = shutdown_request
        server.share = self

    def close_active(self):
        """Cut every connected client so an in-progress video or range response ends now."""
        self.stopping.set()
        with self._lock:
            socks = list(self._conns)
        for s in socks:
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                s.close()
            except OSError:
                pass

    def join_clients(self, timeout=5):
        import time
        with self._lock:
            threads = list(self._threads)
        end = timeout
        start = time.time()
        for t in threads:
            left = end - (time.time() - start)
            if left <= 0:
                break
            t.join(left)
        with self._lock:
            self._threads = {t for t in self._threads if t.is_alive()}

    def stop(self, wait=True):
        self.close_active()
        try:
            self.server.shutdown()
        except Exception:
            pass
        if wait:
            self.join_clients()
        try:
            self.server.server_close()
        except Exception:
            pass
