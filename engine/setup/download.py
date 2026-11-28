"""The one way out: downloads for setup. This is the only module in Lastbook that opens a network connection.

  - HTTPS only, to the hosts in ALLOWED_HOSTS (or a subdomain of ALLOWED_SUFFIXES), port 443.
  - No proxy: http.client never reads the system's or the environment's proxy settings (urllib would), so a request goes
    straight to the host named, or nowhere.
  - A redirect is followed only to another allowed address, at most MAX_REDIRECTS times.
  - Resuming uses HTTP Range on the ETag saved beside the partial file. R2 ignores If-Range (it answers 206 whatever the ETag),
    so the check is made here: a 200 instead, or another total size, starts that file over. Another ETag on the 206 with
    the same total size does not by itself: a copy uploaded again has a new ETag and the same bytes. SAMPLES stretches of
    what is on disk are fetched again and compared; if they are the server's, the download carries on under the new ETag
    (the SHA-256 at the end still judges the whole file), and only if they are not does the file start over.
    (Not If-Match: on a redirect chain the first host's ETag is not the file's, so it would refuse every resume.)
  - The SHA-256 is computed while the bytes arrive. After a resume the bytes already on disk are read once to rebuild it.
  - A file of PARALLEL_MIN or more comes over CONNECTIONS connections at once, each asking for one PIECE with a closed Range
    (bytes=a-b). Pieces are handed out in order and at most AHEAD pieces past the first unfinished one, so the finished part
    is always a run from byte 0 plus a short window. That run is hashed as it completes (read back from the disk, still in the
    cache), so the SHA-256 is ready when the last piece lands: no second pass over a 400 GB file. Every 206 must carry the
    ETag and total size of the first; another ETag is checked as above (the hashed run is compared and kept, the window past
    it is fetched again), and a 200 to a Range goes back to one connection.
    The .json then says "parallel": true, and bytes_done is the hashed run: a resume keeps that and fetches the window again.
  - Giving up on broken connections says which: 'unreachable' when the host that broke never answered this download at all (a
    network that resets or blocks it, or no internet), else 'network' (it answered, then the connection kept breaking).
  - A file whose BitTorrent v2 pieces root is pinned in the manifest (engine/setup/torrent.py) comes in pieces that hold whole
    torrent pieces, and the run takes a piece only once its torrent pieces match their hashes as it is read back. So its pieces
    may also come from mirrors: any https host, listed in Lastbook's manifest or added by the person, each with connections of
    its own. A mirror that sends one wrong piece, or does not answer as a mirror should, is not asked again, and its pieces go
    back to the others. A mirror never fails the download, never moves the ETag, and never spends the busy server's wait. The
    file's SHA-256 is still the last word.
  - With BitTorrent on (engine/setup/share.py), a pinned file of PARALLEL_MIN or more also comes from other people: an rqbit
    of its own writes into the very same file from the front while these connections work from the back (Download._run_swarm).
    rqbit writes before it checks, so a piece of its counts only when it matches its torrent hash on the disk, and once every
    piece is in, rqbit is stopped and the file is judged by a full read, every piece and the whole SHA-256, with nothing else
    writing. That way never cuts the file short, and its .json lists the pieces done ("swarm") instead of a run from byte 0.
  - Plain HTTP goes to one place only: 127.0.0.1, to the rqbit Lastbook itself started for sharing (engine/setup/share.py), with
    a password made for that run (local_api). Nothing else is reached that way, and its answers are only read as numbers.
  - Nothing here runs unless the person started or resumed a download (or opened setup: one GET of the manifest).

Tests pass their own `allowed` and `context` to reach a local test server. The product never does.
"""
import base64
import errno
import hashlib
import http.client
import json
import os
import select
import socket
import ssl
import sys
import threading
import time
import weakref
import urllib.parse
from pathlib import Path

ALLOWED_HOSTS = frozenset({
    'downloads.lastbook.org',
    'huggingface.co',
    'cas-bridge.xethub.hf.co',
})
ALLOWED_SUFFIXES = ('.hf.co',)      # Hugging Face's download hosts (cas-bridge.xethub.hf.co and its siblings)
MAX_REDIRECTS = 5
TIMEOUT = 30                        # seconds without a byte before the connection counts as broken
CHUNK = 1024 * 1024
SAVE_EVERY = 2.0                    # seconds between saves of the partial file's .json
NETWORK_TRIES = 6                   # broken connections in a row, with no progress between them, before giving up
BACKOFF = (2, 4, 8, 15, 30, 30)
BUSY_BACKOFF = (5, 15, 30, 60, 120, 300)   # a server that answers 5xx or 429 is up but busy: wait longer, and keep at it
BUSY_LIMIT = 40 * 60                # seconds of waiting on a busy server, with no progress, before giving up
MAX_RETRY_AFTER = 600               # a Retry-After longer than this is not waited out in one go
USER_AGENT = 'Lastbook-setup/1'
CONNECTIONS = 8                     # at once, for one large file. One connection to downloads.lastbook.org gave ~2 MB/s, 8 ~13 MB/s
PARALLEL_MIN = 512 * 2 ** 20        # smaller files come over one connection, as before
PIECE = 16 * 2 ** 20                # bytes asked for in one Range
AHEAD = 2 * CONNECTIONS             # pieces handed out past the first unfinished one: the most the .part runs ahead of bytes_done
SAMPLES = 3                         # stretches of a partial file compared with the server's when its ETag changed: start, middle, end
SAMPLE = 1024 * 1024                # bytes in each
PIECE_TRIES = 3                     # times a piece from the file's own address may fail its torrent hash before the download stops
HARVEST_EVERY = 2.0                 # seconds between looks at what rqbit has put on the disk
HARVEST_MAX = 64                    # pieces looked at each time, from the first one not done


class Stopped(Exception):
    """The person paused or cancelled. .why is 'paused' or 'cancelled'."""

    def __init__(self, why):
        super().__init__(why)
        self.why = why


class Failed(Exception):
    """A plain sentence for the person, and a code from docs/SETUP-API.md."""

    def __init__(self, code, message, **extra):
        super().__init__(message)
        self.code, self.message, self.extra = code, message, extra


class BadChecksum(Failed):
    def __init__(self, message):
        super().__init__('checksum', message)


def disk_full(e):
    return isinstance(e, OSError) and (e.errno in (errno.ENOSPC, getattr(errno, 'EDQUOT', -1)) or getattr(e, 'winerror', None) in (112, 39))


def host_allowed(host, allowed=None):
    host = (host or '').lower().rstrip('.')
    if allowed is not None:
        return host in allowed
    return host in ALLOWED_HOSTS or any(host.endswith(s) and len(host) > len(s) for s in ALLOWED_SUFFIXES)


def url_allowed(url, allowed=None):
    """An https address on an allowed host, with no user name or password in it, on port 443 (a test's own hosts: any port)."""
    try:
        u = urllib.parse.urlsplit(url)
        port = u.port
    except ValueError:
        return False
    if u.scheme != 'https' or not u.hostname or u.username or u.password:
        return False
    if allowed is None and port not in (None, 443):
        return False
    return host_allowed(u.hostname, allowed)


def roots_path():
    """engine/setup/roots.pem, beside this file (in the packaged app, where the packaging puts it: engine/setup/ under _MEIPASS)."""
    here = Path(__file__).with_name('roots.pem')
    if not here.is_file() and getattr(sys, 'frozen', False):
        here = Path(getattr(sys, '_MEIPASS', '')) / 'engine' / 'setup' / 'roots.pem'
    return here


def tls_context():
    """TLS 1.2 or later, hostname checked, and trust in the roots of roots.pem only: never the system's store (see
    packaging/setup_roots.py for why and which). With the file missing, nothing is downloaded."""
    roots = roots_path()
    if not roots.is_file():
        raise Failed('network', 'This copy of Lastbook is missing its list of trusted download servers, so it cannot download. '
                                'Download Lastbook again.')
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)          # check_hostname on and CERT_REQUIRED; no default certificates loaded
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.load_verify_locations(cafile=str(roots))
    return ctx


class Control:
    """Pause and cancel, from any thread. The download notices within one chunk or one second of waiting."""

    def __init__(self):
        self.ev = threading.Event()
        self.why = None

    def stop(self, why):
        if self.why != 'cancelled':
            self.why = why
        self.ev.set()

    def check(self):
        if self.ev.is_set():
            raise Stopped(self.why or 'paused')

    def sleep(self, s):
        if self.ev.wait(s):
            raise Stopped(self.why or 'paused')


class _StoppableConnection(http.client.HTTPSConnection):
    """A piece's connection, which a pause can end while it is still connecting or in the TLS handshake. The stock connect() blocks
    in both until the timeout, and only sets .sock once the handshake is over, so there is nothing to shut down before then.
    Here .sock is set as soon as each socket exists, and both steps wait in short slices, checking `stopping` between them."""

    SLICE = 0.25

    def __init__(self, host, port, timeout, context, stopping):
        super().__init__(host, port, timeout=timeout, context=context)
        self.stopping = stopping

    def _check(self):
        if self.stopping.is_set():
            raise Stopped('paused')

    def _wait(self, sock, write, deadline):
        """Until `sock` can be read (or written), a slice at a time. The third list is where Windows reports a refused connect."""
        while True:
            self._check()
            left = deadline - time.monotonic()
            if left <= 0:
                raise TimeoutError('timed out')
            r, w, x = select.select([] if write else [sock], [sock] if write else [], [sock], min(self.SLICE, left))
            if r or w or x:
                return

    def connect(self):
        deadline = time.monotonic() + self.timeout
        err = None
        for family, kind, proto, _, addr in socket.getaddrinfo(self.host, self.port, 0, socket.SOCK_STREAM):
            self._check()
            s = socket.socket(family, kind, proto)
            self.sock = s                                   # from here a pause can shut it down
            try:
                s.setblocking(False)
                code = s.connect_ex(addr)
                if code not in (0, errno.EINPROGRESS, errno.EWOULDBLOCK, getattr(errno, 'WSAEWOULDBLOCK', errno.EWOULDBLOCK)):
                    raise OSError(code, os.strerror(code))
                self._wait(s, True, deadline)
                code = s.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
                if code:
                    raise OSError(code, os.strerror(code))
                break
            except Stopped:
                s.close()
                raise
            except OSError as e:
                err = e
                s.close()
                self.sock = None
        else:
            raise err or OSError('no address for the download server')
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        ss = self._context.wrap_socket(s, server_hostname=self.host, do_handshake_on_connect=False)
        self.sock = ss                                      # the wrapped socket replaces the plain one, which it took over
        try:
            while True:
                self._check()                               # also catches a pause that shut the plain socket just before
                try:
                    ss.do_handshake()
                    break
                except ssl.SSLWantReadError:
                    self._wait(ss, False, deadline)
                except ssl.SSLWantWriteError:
                    self._wait(ss, True, deadline)
            ss.settimeout(self.timeout)
        except BaseException:
            ss.close()
            raise


def _cancellable_body(conn, response, stopping, timeout):
    """Keep TLS body reads cancellable without timing out the buffered reader on every poll."""
    raw = getattr(response.fp, 'raw', None)
    sock = conn.sock or getattr(raw, '_sock', None)  # HTTP/1.0 can transfer ownership to the response.
    if sock is None:
        return
    receive = type(sock).recv_into
    socket_ref = weakref.ref(sock)
    sock.setblocking(False)

    def recv_into(*args, **kwargs):
        deadline = time.monotonic() + timeout
        while True:
            if stopping.is_set():
                raise Stopped('paused')
            current = socket_ref()
            if current is None:
                raise OSError('download connection closed')
            try:
                return receive(current, *args, **kwargs)  # Drain decrypted TLS bytes before selecting.
            except (ssl.SSLWantReadError, ssl.SSLWantWriteError) as error:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('timed out')
                write = isinstance(error, ssl.SSLWantWriteError)
                select.select([] if write else [current], [current] if write else [], [current], min(.1, remaining))

    sock.recv_into = recv_into


def _netloc(url):
    return (urllib.parse.urlsplit(url).netloc or '').lower()


def _mirror_allowed(url, mirrors):
    """An https address on one of this file's mirrors (host and port as listed), with no user name or password."""
    try:
        u = urllib.parse.urlsplit(url)
        return u.scheme == 'https' and not u.username and not u.password and u.netloc.lower() in mirrors
    except ValueError:
        return False


def _open(url, start, etag, allowed, context, timeout, end=None, opened=None, stopping=None, answered=None, mirrors=()):
    """(connection, response, final url) for a GET from byte `start` (to byte `end`, included, when given), after following
    allowed redirects. `opened(conn)`, when given, hears of each connection, so another thread can close it. With `stopping`
    (an Event), connecting and the TLS handshake end soon after it is set, raising Stopped, rather than at the timeout.
    `answered(host)`, when given, hears of each host that sent an answer; a connection error carries the host it was for
    (`.lastbook_host`), so a caller can tell a host that never answers from one whose connection broke.
    mirrors: the hosts (host:port) of this file's mirrors, which may be asked as well."""
    for _ in range(MAX_REDIRECTS + 1):
        if not (url_allowed(url, allowed) or _mirror_allowed(url, mirrors)):
            raise Failed('network', 'Lastbook refused to download from an address it does not know.')
        u = urllib.parse.urlsplit(url)
        if stopping is not None:
            conn = _StoppableConnection(u.hostname, u.port or 443, timeout, context, stopping)
        else:
            conn = http.client.HTTPSConnection(u.hostname, u.port or 443, timeout=timeout, context=context)
        if opened:
            opened(conn)
        headers = {'User-Agent': USER_AGENT, 'Accept-Encoding': 'identity'}
        if end is not None:
            headers['Range'] = f'bytes={start}-{end}'
            if etag:
                headers['If-Range'] = etag
        elif start:
            headers['Range'] = f'bytes={start}-'
            if etag:
                headers['If-Range'] = etag
        try:
            conn.request('GET', (u.path or '/') + ('?' + u.query if u.query else ''), headers=headers)
            r = conn.getresponse()
        except (OSError, http.client.HTTPException) as e:
            e.lastbook_host = u.hostname
            raise
        if answered:
            answered(u.hostname)
        if stopping is not None:
            _cancellable_body(conn, r, stopping, timeout)
        if r.status in (301, 302, 303, 307, 308):
            loc = r.getheader('Location')
            r.close()
            conn.close()
            if not loc:
                raise Failed('network', 'The download server answered with a move to nowhere.')
            url = urllib.parse.urljoin(url, loc)
            continue
        return conn, r, url
    raise Failed('network', 'The download server sent Lastbook round in circles.')


def fetch_small(url, limit=1 << 20, allowed=None, context=None, timeout=10):
    """One small GET (the manifest). Bytes, or None on any failure."""
    try:
        conn, r, _ = _open(url, 0, None, allowed, context or tls_context(), timeout)
        try:
            if r.status != 200:
                return None
            data = r.read(limit + 1)
            return data if len(data) <= limit else None
        finally:
            conn.close()
    except (OSError, http.client.HTTPException, Failed, ValueError):
        return None


def loopback_port():
    """A free TCP port on 127.0.0.1, for the control API of a program Lastbook starts (rqbit). Nothing listens on it here."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]
    finally:
        s.close()


def local_api(port, secret, method, path, body=None, limit=1 << 20, timeout=5):
    """One request to the control API of the rqbit Lastbook started (engine/setup/share.py), on 127.0.0.1 only, with the password
    made for that run: (status, bytes), or None. No redirect is followed and the answer is capped."""
    if not isinstance(port, int) or not 0 < port < 65536 or not isinstance(path, str) or not path.startswith('/'):
        return None
    conn = http.client.HTTPConnection('127.0.0.1', port, timeout=timeout)
    try:
        headers = {'Authorization': 'Basic ' + base64.b64encode(f'lastbook:{secret}'.encode()).decode(), 'User-Agent': USER_AGENT}
        if body is not None:
            headers['Content-Type'] = 'application/octet-stream'
        conn.request(method, path, body=body, headers=headers)
        r = conn.getresponse()
        data = r.read(limit + 1)
        return (r.status, data) if len(data) <= limit else None
    except (OSError, http.client.HTTPException, ValueError):
        return None
    finally:
        conn.close()

def _load_meta(path):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save_meta(path, d):
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(d, f)
    os.replace(tmp, path)


def _content_range(v):
    """(start, total) from 'bytes 100-199/1000', or None."""
    try:
        unit, _, rest = (v or '').partition(' ')
        span, _, total = rest.partition('/')
        return int(span.split('-')[0]), int(total)
    except ValueError:
        return None


class _DiskWriteError(OSError):
    """A write failed after possibly changing the partial file."""


def _write_all(f, data):
    """Write every byte, including short raw writes (#122); preserve disk errors."""
    view = memoryview(data)
    try:
        while view:
            n = f.write(view)
            if not n:
                raise OSError(errno.EIO, 'the disk took no bytes')
            view = view[n:]
    except OSError as e:
        raise _DiskWriteError(e.errno, e.strerror) from e


class Download:
    """One file: <dest>.part grows, with <dest>.part.json beside it (url, size, sha256, bytes done, ETag, and "parallel": true
    while pieces may lie past bytes done). run() returns once the whole file is there and its SHA-256 matches, renamed to <dest>.
    Raises Stopped, Failed or BadChecksum. progress(done, total, phase) is called as bytes arrive; phase is 'downloading' or
    'verifying'. waiting(seconds) is called before each wait on a busy server, over one connection or several. `connections`
    (default CONNECTIONS) is how many at once for a file of PARALLEL_MIN or more; 1 means one. pieces: the file's
    torrent.Pieces (its piece hashes, already checked against the pinned pieces root), or None. mirrors: other https addresses
    of the same file, asked only with pieces, each over as many connections as the file's own address. swarm: a share.Swarm
    to take pieces from other people too (only with pieces), writing into `part`, the file being downloaded, in a folder of
    its own; on_peers(n) hears the bytes taken from them so far."""

    def __init__(self, url, dest, size, sha256, control, progress=lambda d, t, p: None, allowed=None, context=None, timeout=TIMEOUT,
                 waiting=lambda s: None, connections=None, pieces=None, mirrors=(), swarm=None, part=None, on_peers=None):
        self.url, self.dest, self.size, self.sha256 = url, str(dest), int(size), sha256.lower()
        self.part, self.meta = str(part) if part else self.dest + '.part', self.dest + '.part.json'
        self.control, self.progress, self.waiting = control, progress, waiting
        self.allowed, self.context, self.timeout = allowed, context, timeout
        self.connections = connections
        self.answered = set()           # hosts that sent any answer to this download (a redirect counts)
        self.pieces = pieces if pieces is not None and pieces.size == self.size else None
        self.sources = [url] + ([m for m in dict.fromkeys(mirrors) if m != url] if self.pieces else [])
        self.mirror_hosts = frozenset(_netloc(m) for m in self.sources[1:])
        self.banned = set()             # mirrors not asked again in this run
        self.swarm = swarm if self.pieces else None
        self.on_peers = on_peers or (lambda n: None)
        self.st, self.from_back, self.peer_bytes = None, False, 0

    def _gave_up(self, e):
        """The Failed for connections that kept breaking: 'unreachable' (with the host) when the host they broke on never
        answered this download, so retrying on this network will not help; else 'network'. Either is a _KeptBreaking: with
        BitTorrent on, the server is asked again later while the download goes on from other people."""
        host = getattr(e, 'lastbook_host', None)
        if host and host not in self.answered:
            return _KeptBreaking('unreachable', f'Lastbook could not reach {host} from this network.', host=host)
        return _KeptBreaking('network', f'The connection kept breaking ({type(e).__name__}). Check the internet connection, then try again.')

    def done_bytes(self):
        """Bytes from 0 that are surely the file's: the .part's length, or after pieces, the hashed run the .json records."""
        try:
            n = min(os.path.getsize(self.part), self.size)
        except OSError:
            return 0
        meta = _load_meta(self.meta)
        if meta.get('parallel'):
            b = meta.get('bytes_done')
            n = min(n, b) if isinstance(b, int) and b >= 0 else 0
        return n

    def _parallel_wanted(self):
        n = CONNECTIONS if self.connections is None else self.connections
        return n > 1 and self.size >= PARALLEL_MIN

    def discard(self):
        for p in (self.part, self.meta, self.meta + '.tmp'):
            try:
                os.unlink(p)
            except OSError:
                pass

    def _rehash(self, n):
        """The SHA-256 of the first n bytes already on disk."""
        h = hashlib.sha256()
        done = 0
        with open(self.part, 'rb') as f:
            while done < n:
                self.control.check()
                b = f.read(min(8 * CHUNK, n - done))
                if not b:
                    break
                h.update(b)
                done += len(b)
                self.progress(done, n, 'verifying')
        return h, done

    def run(self):
        if os.path.isfile(self.dest) and os.path.getsize(self.dest) == self.size and not os.path.exists(self.part):
            return self.dest     # finished and checked before a restart
        os.makedirs(os.path.dirname(self.dest) or '.', exist_ok=True)
        meta = _load_meta(self.meta)
        if meta and (meta.get('sha256') != self.sha256 or meta.get('size') != self.size):
            self.discard()       # left by another version of this file
            meta = {}
        ctx = self.context or tls_context()
        if self.pieces and (self.swarm or meta.get('swarm')) and self._parallel_wanted():
            h = self._run_swarm(meta, ctx)      # with other people: its own way, before anything here could cut the file short
            if h is not None:
                return self._judged(h)
            meta = _load_meta(self.meta)        # rqbit did not start and nothing of that way is here: the usual way
        start = self.done_bytes()
        if start and not meta.get('etag'):
            start = 0            # nothing to tell the server which file those bytes came from
        if self.pieces and self._parallel_wanted():
            start -= start % self.pieces.length     # pieces hold whole torrent pieces: go on from the start of one
        with open(self.part, 'ab') as f:
            f.truncate(start)
        h, start = self._rehash(start) if start else (hashlib.sha256(), 0)
        if start:
            self.progress(start, self.size, 'downloading')   # the re-read is over: a wait for the server from here is shown as one
        etag = meta.get('etag')
        if start < self.size and self._parallel_wanted():
            h, start, etag = self._run_parallel(h, start, etag, ctx)
        tries = busy = waited = 0       # broken connections, busy answers, and seconds waited on them, with no progress
        ignored_once = False            # a 200 to a Range already asked about since the last progress
        while start < self.size:
            self.control.check()
            try:
                got = self._fetch(start, etag, h, ctx)
                start, etag = got
                tries = busy = waited = 0
                ignored_once = False
            except Stopped:
                raise
            except Failed:
                raise
            except _Restart as r:
                if r.whole and not ignored_once:      # one 200 to a Range can be a passing hiccup at the edge: ask once more first
                    ignored_once = True
                    print(f'setup: the server sent the whole of {os.path.basename(self.dest)} to a resume; asking again', flush=True)
                    self.control.sleep(1)
                    continue
                print(f'setup: the file on the server changed or ignores Range; starting {os.path.basename(self.dest)} over', flush=True)
                with open(self.part, 'r+b') as f:
                    f.truncate(0)
                h, start, etag = hashlib.sha256(), 0, None
                continue
            except _Busy as b:
                now = self.done_bytes()
                if now > start:
                    tries = busy = waited = 0
                    ignored_once = False
                start = now
                etag = _load_meta(self.meta).get('etag') or etag
                wait = min(max(BUSY_BACKOFF[min(busy, len(BUSY_BACKOFF) - 1)], b.wait), BUSY_LIMIT - waited)
                if wait <= 0:
                    raise Failed('server', f'The download server stayed busy ({b}). Try again later.')
                busy += 1
                waited += wait
                print(f'setup: the server is busy at {start} of {self.size} ({b}); trying again in {wait}s', flush=True)
                self.waiting(wait)
                self.control.sleep(wait)
            except ssl.SSLCertVerificationError:
                raise Failed('network', 'Lastbook could not confirm it is talking to the download server, so it stopped. '
                                        'A network that intercepts secure connections (some offices, hotels) can cause this.')
            except (OSError, http.client.HTTPException, ValueError) as e:
                if disk_full(e):
                    raise Failed('no_space', 'The disk filled up while downloading. Free some space, then try again.')
                now = self.done_bytes()
                if isinstance(e, _DiskWriteError):
                    # The OS may have written a prefix before raising. Rebuild the hash from those actual bytes.
                    h, now = self._rehash(now)
                if now > start:
                    tries = busy = waited = 0
                    ignored_once = False
                else:
                    tries += 1
                start = now
                etag = _load_meta(self.meta).get('etag') or etag
                if tries >= NETWORK_TRIES:
                    raise self._gave_up(e)
                print(f'setup: download broke at {start} of {self.size}: {type(e).__name__}: {e}; trying again', flush=True)
                self.control.sleep(BACKOFF[min(tries, len(BACKOFF) - 1)])
        return self._judged(h)

    def _judged(self, h):
        """The whole file is here and h is its SHA-256: renamed to <dest> if that matches, else thrown away (BadChecksum)."""
        if h.hexdigest() != self.sha256:
            self.discard()
            raise BadChecksum('The downloaded file did not match its published checksum.')
        os.replace(self.part, self.dest)
        try:
            os.unlink(self.meta)
        except OSError:
            pass
        return self.dest

    def _fetch(self, start, etag, h, ctx):
        """Reads until the end or a break. Returns (bytes done, etag). Raises _Restart when the server's file is not the one begun."""
        conn, r, final = _open(self.url, start, etag, self.allowed, ctx, self.timeout, answered=self.answered.add)
        try:
            if r.status == 416 or r.status >= 400:
                if 500 <= r.status < 600 or r.status == 429:
                    raise _Busy(r.status, r.getheader('Retry-After'))
                raise Failed('network', f'The download server refused the file (HTTP {r.status}).')
            new_etag = r.getheader('ETag')
            if r.status == 206:
                cr = _content_range(r.getheader('Content-Range'))
                if not cr or cr[0] != start or cr[1] != self.size:
                    raise _Restart(new_etag)
                if etag and new_etag and new_etag != etag:
                    if not self._same_bytes(start, ctx):    # a break while comparing is tried again like any other, the file kept
                        raise _Restart(new_etag)
                    print(f'setup: {os.path.basename(self.dest)} has a new ETag on the server and the same bytes; carrying on from {start}', flush=True)
            elif r.status == 200:
                if start:
                    raise _Restart(new_etag, whole=True)    # the server sent the whole file again: its copy changed, or it ignores Range
                length = r.getheader('Content-Length')
                if length is not None and length.isdigit() and int(length) != self.size:
                    raise BadChecksum(f'The file on the server is {int(length):,} bytes, not the {self.size:,} Lastbook expects.')
            else:
                raise OSError(f'HTTP {r.status}')
            etag = new_etag or etag
            meta = {'url': self.url, 'size': self.size, 'sha256': self.sha256, 'etag': etag, 'bytes_done': start}
            _save_meta(self.meta, meta)
            saved = time.time()
            with open(self.part, 'r+b', buffering=0) as f:
                f.seek(start)
                while start < self.size:
                    self.control.check()
                    b = r.read1(min(CHUNK, self.size - start))    # what has arrived, up to CHUNK: progress and pause stay quick on a slow line
                    if not b:
                        raise ConnectionError('the connection closed early')
                    _write_all(f, b)
                    h.update(b)
                    start += len(b)
                    self.progress(start, self.size, 'downloading')
                    if time.time() - saved > SAVE_EVERY:
                        f.flush()
                        meta['bytes_done'] = start
                        _save_meta(self.meta, meta)
                        saved = time.time()
                f.flush()
                os.fsync(f.fileno())
            meta['bytes_done'] = start
            _save_meta(self.meta, meta)
            return start, etag
        finally:
            try:
                conn.close()
            except OSError:
                pass


    def _same_bytes(self, n, ctx):
        """True when the first n bytes on disk are the server's, judged by SAMPLES stretches of them fetched again: the first
        and the last SAMPLE bytes, and those between, evenly spaced. False at the first byte that differs. An ETag is a name
        for the server's copy, not for its bytes, and the same file uploaded again gets a new one (#208): this looks at the
        bytes. It cannot see a change between the samples; the SHA-256 at the end does. Raises what a fetch raises (_Busy, an
        OSError, Failed) when a sample cannot be had, which tells nothing about the file."""
        size = min(SAMPLE, n)
        starts = sorted({round(i * (n - size) / max(1, SAMPLES - 1)) for i in range(SAMPLES)})
        with open(self.part, 'rb') as f:
            for a in starts:
                self.control.check()
                conn, r, _ = _open(self.url, a, None, self.allowed, ctx, self.timeout, end=a + size - 1, answered=self.answered.add)
                try:
                    if 500 <= r.status < 600 or r.status == 429:
                        raise _Busy(r.status, r.getheader('Retry-After'))
                    if r.status >= 400:
                        raise Failed('network', f'The download server refused the file (HTTP {r.status}).')
                    cr = _content_range(r.getheader('Content-Range'))
                    if r.status != 206 or not cr or cr[0] != a:
                        raise OSError(f'HTTP {r.status} to a check of the bytes at {a}')
                    if cr[1] != self.size:
                        return False
                    f.seek(a)
                    left = size
                    while left:
                        self.control.check()
                        b = r.read1(min(CHUNK, left))
                        if not b:
                            raise ConnectionError('the connection closed early')
                        if f.read(len(b)) != b:
                            return False
                        left -= len(b)
                finally:
                    try:
                        conn.close()
                    except OSError:
                        pass
        return True

    # ------------------------------------------------------------------------------------------ several connections --
    def _run_parallel(self, h, start, etag, ctx):
        """Pieces until the file is whole: (h, size, etag). Or, when the server will not send pieces, (h, start, etag) for the one
        connection to carry on from, with the .part cut back to the hashed run and the .json saying so."""
        changed = 0
        while True:
            try:
                return self._pieces(h, start, etag, ctx)
            except _Restart as r:
                h, start, etag = r.h, r.start, r.etag     # where the hashed run had got to
                if r.whole or changed:
                    why = 'ignores Range' if r.whole else 'changed its ETag twice'
                    print(f'setup: the server {why} for {os.path.basename(self.dest)}; carrying on over one connection', flush=True)
                    with open(self.part, 'r+b') as f:
                        f.truncate(start)
                    _save_meta(self.meta, {'url': self.url, 'size': self.size, 'sha256': self.sha256, 'etag': etag, 'bytes_done': start})
                    return h, start, etag
                changed += 1
                if start:                             # the hashed run may still be the server's bytes under a new ETag (#208)
                    try:
                        same = self._same_bytes(start, ctx)
                    except (_Busy, OSError, http.client.HTTPException, ValueError) as e:
                        # No answer either way. One connection asks from here under the old ETag, sees the new one, and makes
                        # the same comparison with its waits and tries; a later resume uses several connections again.
                        print(f'setup: could not compare {os.path.basename(self.dest)} with the server ({type(e).__name__}: {e}); carrying on over one connection', flush=True)
                        with open(self.part, 'r+b') as f:
                            f.truncate(start)
                        _save_meta(self.meta, {'url': self.url, 'size': self.size, 'sha256': self.sha256, 'etag': r.old, 'bytes_done': start})
                        return h, start, r.old
                    if same:
                        print(f'setup: {os.path.basename(self.dest)} has a new ETag on the server and the same bytes; carrying on from {start}', flush=True)
                        with open(self.part, 'r+b') as f:
                            f.truncate(start)         # the window past the hashed run may hold pieces of either copy
                        etag = r.new
                        continue
                print(f'setup: the file on the server changed; starting {os.path.basename(self.dest)} over', flush=True)
                with open(self.part, 'r+b') as f:
                    f.truncate(0)
                h, start, etag = hashlib.sha256(), 0, None

    def _pieces(self, h, start, etag, ctx):
        n = CONNECTIONS if self.connections is None else self.connections
        P = self.pieces
        st = _Pieces(start, self.size, etag, piece=max(PIECE, P.length) if P else None, checked=P is not None)
        st.banned = self.banned
        workers = [threading.Thread(target=self._worker, args=(st, ctx, None if k == 0 else src), daemon=True,
                                    name=f'download-{i}' if k == 0 else f'download-m{k}-{i}')
                   for k, src in enumerate(self.sources) if src not in self.banned for i in range(min(n, st.count))]
        meta = {'url': self.url, 'size': self.size, 'sha256': self.sha256, 'etag': etag, 'bytes_done': start, 'parallel': True}
        _save_meta(self.meta, meta)
        saved = time.time()
        reported = None
        for w in workers:
            w.start()
        try:
            with open(self.part, 'rb', buffering=0 if P else -1) as rf:     # unbuffered when a piece may be read again
                while start < self.size:
                    self.control.check()
                    with st.cv:
                        if st.error is None and not st.done.get(st.first):
                            st.cv.wait(0.5)
                        if st.error is not None:
                            raise st.error
                        ready = []
                        i = st.first
                        while st.done.get(i):
                            ready.append(i)
                            i += 1
                    for i in ready:                 # hash the run that just became whole, in order
                        a, b = st.span(i)
                        h2 = h.copy() if P else h   # with a pinned torrent, the run takes the piece once its torrent pieces match
                        check = _TorrentCheck(P, a) if P else None
                        rf.seek(a)
                        while a < b:
                            self.control.check()
                            chunk = rf.read(min(8 * CHUNK, b - a))
                            if not chunk:
                                raise OSError('the partial file is shorter than the pieces written to it')
                            h2.update(chunk)
                            if check:
                                check.update(chunk)
                            a += len(chunk)
                        if check and check.wrong:
                            self._wrong_piece(st, i)    # fetched again; raises Failed once the file's own address keeps sending it wrong
                            break
                        h = h2
                        start = b
                        with st.cv:
                            st.done.pop(i)
                            st.got.pop(i, None)
                            st.first = i + 1
                            st.cv.notify_all()
                    with st.cv:
                        inflight = sum(st.got.values())     # pieces not yet in the hashed run, whole or in part
                        announce, st.announce = st.announce, None
                    now = min(start + inflight, self.size)
                    if now != reported:                     # only as bytes arrive: a call with none would wipe the busy countdown
                        self.progress(now, self.size, 'downloading')
                        reported = now
                    if announce:
                        self.waiting(announce)              # from this thread, like progress: every connection waits on a busy server
                    if (ready and time.time() - saved > SAVE_EVERY) or start >= self.size:
                        with open(self.part, 'r+b') as f:      # what bytes_done vouches for is on the disk before it says so
                            os.fsync(f.fileno())
                        meta['etag'], meta['bytes_done'] = st.etag, start
                        _save_meta(self.meta, meta)
                        saved = time.time()
        except _Restart as r:
            r.new, r.old = r.etag, st.etag or etag      # the ETag just seen, and the one this download began under
            r.h, r.start, r.etag = h, start, (st.etag or etag) if r.whole else None
            raise
        finally:
            st.halt(workers)
            if start < self.size:
                meta['etag'], meta['bytes_done'] = st.etag or meta['etag'], start
                try:
                    _save_meta(self.meta, meta)
                except OSError:
                    pass
        return h, start, st.etag

    def _worker(self, st, ctx, mirror=None):
        """Takes pieces in order and fetches each, trying again where a connection broke. Hands any error to the coordinator.
        mirror: the address this connection asks instead of the file's own. A mirror that fails is dropped, not the download:
        the piece it had goes back to the others."""
        try:
            with open(self.part, 'r+b', buffering=0) as f:
                while not (mirror and mirror in st.banned):
                    i = st.take()
                    if i is None:
                        return
                    try:
                        done = self._piece(st, i, f, ctx, mirror)
                    except _MirrorFailed as e:
                        st.put_back(i)
                        if mirror not in st.banned:
                            st.banned.add(mirror)
                            print(f'setup: not using the mirror {_netloc(mirror)} for {os.path.basename(self.dest)}: {e}', flush=True)
                        return
                    if not done and not st.stopping.is_set():
                        st.put_back(i)          # its mirror was dropped while it came: another connection takes it
        except BaseException as e:      # noqa: B036 -- one place to hear it: the thread that hashes, and raises
            st.fail(e)

    def _wrong_piece(self, st, i):
        """Piece i was on the disk as it came, but its torrent pieces do not match: its source sent wrong bytes. A mirror is not
        asked again; the file's own address may send it PIECE_TRIES times. The piece is fetched again, or Failed is raised."""
        name, src = os.path.basename(self.dest), st.source.get(i, self.url)
        print(f'setup: the piece of {name} at {st.span(i)[0]} does not match its torrent piece hash; fetching it again', flush=True)
        if src != self.url:
            if src not in st.banned:
                st.banned.add(src)
                print(f'setup: not using the mirror {_netloc(src)} for {name} again: it sent a wrong piece', flush=True)
        else:
            st.redos[i] = st.redos.get(i, 0) + 1
            if st.redos[i] >= PIECE_TRIES:
                raise Failed('checksum', f'Part of {name} kept coming out different from its published hash. '
                                         'What was downloaded is kept: try again later.', kept=True)
        st.redo(i)

    def _piece(self, st, i, f, ctx, mirror=None):
        """Piece i over one connection, to the file's own address or a mirror. True once all of it is written. A mirror's
        trouble raises _MirrorFailed, and it never reaches the shared ETag, busy wait or error."""
        a, b = st.span(i)
        pos, tries, stray = a, 0, False
        src = mirror or self.url
        while pos < b:
            if st.stopping.is_set() or (mirror and mirror in st.banned):
                return False
            try:
                conn, r, _ = _open(src, pos, None if mirror else st.etag, self.allowed, ctx, self.timeout, end=b - 1,
                                   opened=st.opened, stopping=st.stopping, answered=self.answered.add, mirrors=self.mirror_hosts)
                try:
                    if mirror:
                        if r.status in (429,) or 500 <= r.status < 600:
                            raise OSError(f'HTTP {r.status}')    # busy: tried again on its own, never the shared wait
                        cr = _content_range(r.getheader('Content-Range'))
                        if r.status != 206 or not cr or cr[0] != pos or cr[1] != self.size:
                            raise _MirrorFailed(f'HTTP {r.status} {r.getheader("Content-Range") or ""}'.strip())
                        f.seek(pos)
                        while pos < b:
                            if st.stopping.is_set() or mirror in st.banned:
                                return False
                            chunk = r.read1(min(CHUNK, b - pos))
                            if not chunk:
                                raise ConnectionError('the connection closed early')
                            _write_all(f, chunk)
                            f.flush()
                            pos += len(chunk)
                            tries = 0
                            st.progress(i, pos - a)
                        continue
                    if 500 <= r.status < 600 or r.status == 429:
                        raise _Busy(r.status, r.getheader('Retry-After'))     # up but busy: wait, as over one connection
                    if r.status >= 400:
                        raise Failed('network', f'The download server refused the file (HTTP {r.status}).')
                    if r.status == 200:
                        st.same(r.getheader('ETag'))      # a server that honours If-Range sends 200 when its copy changed
                        if not stray:                     # one 200 to a Range can be a passing hiccup at the edge: ask once more
                            stray = True
                            print(f'setup: the server sent the whole file to the piece at {pos}; asking again', flush=True)
                            st.closed(conn)
                            if st.stopping.wait(1):
                                return False
                            continue
                        raise _Restart(r.getheader('ETag'), whole=True)
                    if r.status != 206:
                        raise OSError(f'HTTP {r.status}')
                    cr = _content_range(r.getheader('Content-Range'))
                    if not cr or cr[0] != pos:
                        raise _Restart(r.getheader('ETag'), whole=True)
                    if cr[1] != self.size:
                        raise BadChecksum(f'The file on the server is {cr[1]:,} bytes, not the {self.size:,} Lastbook expects.')
                    st.same(r.getheader('ETag'))
                    f.seek(pos)
                    while pos < b:
                        if st.stopping.is_set():
                            return False
                        chunk = r.read1(min(CHUNK, b - pos))
                        if not chunk:
                            raise ConnectionError('the connection closed early')
                        _write_all(f, chunk)
                        f.flush()
                        pos += len(chunk)
                        tries = 0
                        st.progress(i, pos - a)
                finally:
                    st.closed(conn)
            except (_Restart, Failed, Stopped) as e:
                if mirror and isinstance(e, Failed):
                    raise _MirrorFailed(e.message) from e           # e.g. a redirect to an address Lastbook does not know
                raise
            except _Busy as e:
                if st.stopping.is_set():
                    return False
                wait, new = st.busy_wait(e)             # Failed('server') once the shared budget is spent
                if new:
                    print(f'setup: the server is busy at {pos} of {self.size} ({e}); trying again in {wait}s', flush=True)
                while wait > 0:                         # until the shared wait ends, also if another connection extended it
                    if st.stopping.wait(wait):          # Pause, Cancel or another connection's error ends the wait at once
                        return False
                    wait = st.busy_rest()
            except ssl.SSLCertVerificationError:
                if mirror:
                    raise _MirrorFailed('its certificate could not be confirmed')
                raise Failed('network', 'Lastbook could not confirm it is talking to the download server, so it stopped. '
                                        'A network that intercepts secure connections (some offices, hotels) can cause this.')
            except (OSError, http.client.HTTPException, ValueError) as e:
                if st.stopping.is_set():
                    return False
                if disk_full(e):
                    raise Failed('no_space', 'The disk filled up while downloading. Free some space, then try again.')
                tries += 1
                if tries >= NETWORK_TRIES:
                    if mirror:
                        raise _MirrorFailed(f'its connection kept breaking ({type(e).__name__})')
                    raise self._gave_up(e)
                where = f' from the mirror {_netloc(src)}' if mirror else ''
                print(f'setup: piece at {pos} of {self.size}{where} broke: {type(e).__name__}: {e}; trying again', flush=True)
                if st.stopping.wait(BACKOFF[min(tries - 1, len(BACKOFF) - 1)]):
                    return False
        st.finish(i, src)
        return True

    # -------------------------------------------------------------------------------------------- with other people --
    def _run_swarm(self, meta, ctx):
        """The file from its own address, its mirrors and other people at once. rqbit (self.swarm) writes into this very file,
        fetching from the front; the connections here take pieces from the back. rqbit writes what a peer sends before it checks
        it, so a piece of its counts only when it matches its torrent piece hash on the disk (_harvest), and nothing seen while it
        runs is proof: once every piece is in, rqbit is stopped (its process has ended) and the whole file is read, each piece
        against its torrent hash and the whole for run() to compare with its SHA-256. A piece wrong in that read is fetched
        again from the servers, and the file read again. The file is never cut short here. Returns the hash of the whole file,
        or None when rqbit did not start and nothing done this way is here (the usual way then goes on)."""
        open(self.part, 'ab').close()
        folder = os.path.dirname(os.path.abspath(self.part))
        P = self.pieces
        st = _Swarmed(self.size, max(PIECE, P.length), meta.get('etag'))
        st.banned = self.banned
        on_disk, sw = os.path.getsize(self.part), meta.get('swarm') or {}
        if sw.get('piece') == st.piece:                  # left by this way: the pieces it had (all read again at the end)
            for a, b in sw.get('have') or []:
                for k in range(max(0, a), min(b, st.count)):
                    st.have[k] = st.span(k)[1] <= on_disk
        elif meta.get('etag'):                           # a .part from the usual way: its run from byte 0
            n = self.done_bytes()
            for k in range(st.count):
                st.have[k] = st.span(k)[1] <= n
        self.st, self.peer_bytes = st, 0
        sparse = bool(self.swarm) and _holes(folder) and _sparse(self.part)     # marked sparse only where far writes cost nothing
        on = bool(self.swarm) and self.swarm.start(folder)
        if not on and not sw:
            return None
        st.mode = ('back' if sparse else 'window') if on else 'front'
        self.from_back = st.mode == 'back'
        if on:
            print(f'setup: {os.path.basename(self.dest)} also comes from other people (BitTorrent) while it downloads', flush=True)
            if not sparse:
                print(f'setup: the disk under {os.path.basename(self.dest)} fills a gap when a file is written far ahead; the servers '
                      f'keep within {AHEAD * st.piece // 2 ** 20} MiB of the front', flush=True)
        try:
            while True:
                on = self._fill(st, ctx, on)
                if self.swarm is not None and self.swarm.proc is not None:
                    self.swarm.stop()           # rqbit's process has ended: from here only this writes to the file
                on = False
                print(f'setup: reading the whole of {os.path.basename(self.dest)} back to check it', flush=True)
                h, bad = self._verify_all(st)
                if not bad:
                    return h
                print(f'setup: {len(bad)} pieces of {os.path.basename(self.dest)} were not right on the disk; fetching them again', flush=True)
                for k in bad:
                    st.redos[k] = st.redos.get(k, 0) + 1
                    if st.redos[k] > PIECE_TRIES:
                        raise Failed('checksum', f'Part of {os.path.basename(self.dest)} kept coming out different from its published '
                                                 'hash. What was downloaded is kept: try again later.', kept=True)
                    st.drop(k)
                st.mode = 'front'
        finally:
            if self.swarm is not None and self.swarm.proc is not None:
                self.swarm.stop()
            self._save_swarm(st)

    def _fill(self, st, ctx, on):
        """Runs the connections (and with `on`, takes rqbit's pieces) until every piece is done. Returns whether rqbit is still on.
        Servers that will not send pieces, or keep failing, are asked again later while rqbit goes on; without rqbit that stops
        the download, with what is here kept. Every connection has ended before this returns or raises."""
        workers, retry_at = [], 0.0
        last_save = last_harvest = last_progress = 0.0
        name = os.path.basename(self.dest)
        try:
            while True:
                self.control.check()
                now = time.monotonic()
                if not workers and not st.complete() and now >= retry_at:
                    st.restart()
                    n = CONNECTIONS if self.connections is None else self.connections
                    workers = [threading.Thread(target=self._worker, args=(st, ctx, None if k == 0 else src), daemon=True,
                                                name=f'download-{i}' if k == 0 else f'download-m{k}-{i}')
                               for k, src in enumerate(self.sources) if src not in self.banned for i in range(n)]
                    for w in workers:
                        w.start()
                if on and not self.swarm.wanted():
                    print('setup: BitTorrent was turned off; the download goes on from the servers', flush=True)
                    self.swarm.stop()
                    on = False
                if on and now - last_harvest > HARVEST_EVERY:
                    self.swarm.poll()
                    taken = self._harvest(st)
                    if taken:
                        self.peer_bytes += taken
                        self.on_peers(self.peer_bytes)
                    last_harvest = now
                if now - last_save > SAVE_EVERY:
                    self._save_swarm(st)
                    last_save = now
                if now - last_progress > 0.25:
                    self.progress(st.received(), self.size, 'downloading')
                    last_progress = now
                if st.complete():
                    return on
                with st.cv:
                    err = st.error
                    announce, st.announce = st.announce, None
                if announce:
                    self.waiting(announce)
                if err is not None:
                    st.halt(workers)
                    workers = []
                    with st.cv:
                        st.error = None     # heard: it is not handled again while the servers wait to be asked again
                    if isinstance(err, _Restart) and not err.whole:       # the file on the server changed: nothing here is it
                        print(f'setup: the file on the server changed; starting {name} over', flush=True)
                        if on:
                            self.swarm.stop()
                            on = False
                        with open(self.part, 'r+b') as f:
                            f.truncate(0)
                        st.reset()
                        st.mode = 'front'
                        continue
                    # a server that will not send pieces, cannot be reached or stays busy is asked again later while rqbit goes on;
                    # one that refuses the file, or a certificate that cannot be confirmed, stops the download as without rqbit
                    waits = ((isinstance(err, _Restart) and err.whole) or isinstance(err, _KeptBreaking)
                             or (isinstance(err, Failed) and err.code == 'server'))
                    if on and waits:
                        why = 'will not send pieces' if isinstance(err, _Restart) else 'cannot be reached' if isinstance(err, _KeptBreaking) else 'stays busy'
                        print(f'setup: the server {why} for {name} now; BitTorrent goes on, the server is asked again later', flush=True)
                        retry_at = now + BACKOFF[-1]
                        continue
                    if isinstance(err, _Restart):
                        raise Failed('network', 'The download server will not send parts of the file right now. '
                                                'What was downloaded is kept: try again later.')
                    raise err
                with st.cv:
                    st.cv.wait(0.2)
        finally:
            if sys.exc_info()[0] is not None and self.swarm is not None and self.swarm.proc is not None:
                self.swarm.stop()   # stopping (Pause, Cancel, a failure): rqbit first, so it has ended even while a connection takes its time
            st.halt(workers)        # every connection has stopped before this returns

    def _harvest(self, st):
        """The pieces rqbit has put on the disk, from the first one not done on while they match their torrent piece hashes there
        (rqbit fetches from the front), at most HARVEST_MAX each time. Returns the bytes taken. A piece a connection is on counts
        too once it matches: that connection may be stuck on a server that will not answer, and what rqbit wrote is checked."""
        taken = checked = misses = 0
        k = next((i for i in range(st.count) if not st.have[i]), None)
        while k is not None and k < st.count and checked < HARVEST_MAX and misses < 4:   # 4 in a row: past what rqbit has
            if not st.have[k]:
                a, b = st.span(k)
                if self._on_disk(a, b):
                    misses = 0
                    st.finish(k, 'swarm')
                    taken += b - a
                else:
                    misses += 1             # not there yet, or a bad peer's bytes rqbit will fetch again
            k += 1
            checked += 1
        return taken

    def _on_disk(self, a, b, h=None):
        """Whether bytes a..b-1 are all on the disk and match their torrent pieces (a: where one starts), adding them to h."""
        check = _TorrentCheck(self.pieces, a)
        with open(self.part, 'rb', buffering=0) as f:
            f.seek(a)
            while a < b:
                self.control.check()
                chunk = f.read(min(8 * CHUNK, b - a))
                if not chunk:
                    return False
                if h is not None:
                    h.update(chunk)
                check.update(chunk)
                a += len(chunk)
        return not check.wrong

    def _verify_all(self, st):
        """The whole file read back: (its SHA-256, [pieces with a torrent piece that does not match, or not all there])."""
        h, bad = hashlib.sha256(), []
        for k in range(st.count):
            a, b = st.span(k)
            if not self._on_disk(a, b, h):
                bad.append(k)
            self.progress(b, self.size, 'verifying')
        return h, bad

    def _save_swarm(self, st):
        """The .json of this way: the pieces done, as [first, past last] runs. bytes_done stays 0: none of it is proof until the
        last read, so the usual way, should it take over, starts again from byte 0."""
        have, k = [], 0
        while k < st.count:
            if st.have[k]:
                j = k
                while j < st.count and st.have[j]:
                    j += 1
                have.append([k, j])
                k = j
            else:
                k += 1
        try:
            _save_meta(self.meta, {'url': self.url, 'size': self.size, 'sha256': self.sha256, 'etag': st.etag, 'bytes_done': 0,
                                   'parallel': True, 'swarm': {'piece': st.piece, 'have': have}})
        except OSError as e:
            print(f'setup: could not save the state of {os.path.basename(self.dest)}: {e}', flush=True)


class _TorrentCheck:
    """Bytes from `a` (where a torrent piece starts), fed in any chunks: .wrong once a torrent piece among them that has ended
    does not match its hash."""

    def __init__(self, pieces, a):
        self.P, self.pos, self.k = pieces, a, a // pieces.length
        self.h, self.wrong = pieces.hasher(self.k), False

    def update(self, b):
        view = memoryview(b)
        while view:
            end = self.P.span(self.k)[1]
            n = min(len(view), end - self.pos)
            self.h.update(view[:n])
            self.pos += n
            view = view[n:]
            if self.pos == end:
                self.wrong = self.wrong or self.h.digest() != self.P.hashes[self.k]
                self.k += 1
                self.h = self.P.hasher(self.k)


class _Pieces:
    """What the connections share: which pieces are handed out, done, how far each has got, the ETag, and the first error.
    checked: the file's torrent pieces are checked as the run is read back, so a piece can come back to be fetched again (redo),
    and the connections wait for that until the run is whole."""

    def __init__(self, start, size, etag, piece=None, checked=False):
        self.base, self.size, self.etag = start, size, etag
        self.piece, self.checked = piece or PIECE, checked
        self.count = -(-(size - start) // self.piece)
        self.again = []                 # pieces to fetch again (wrong, or left by a mirror), handed out before new ones
        self.source, self.redos, self.banned = {}, {}, set()
        self.next = self.first = 0      # piece numbers, counted from `start`
        self.done, self.got = {}, {}
        self.error = None
        self.cv = threading.Condition()
        self.stopping = threading.Event()
        self.conns = set()
        self.busy = self.waited = 0     # busy answers, and seconds waited on them, with no progress: one budget for all connections
        self.resume_at = 0.0            # (monotonic) the end of the wait now on; other connections that hear "busy" join it
        self.announce = None            # a new wait's seconds, for the coordinator to pass to waiting() (and so to the countdown)

    def span(self, i):
        a = self.base + i * self.piece
        return a, min(a + self.piece, self.size)

    def take(self):
        with self.cv:
            while not self.stopping.is_set():
                if self.again:
                    return self.again.pop(0)
                if self.next < self.count and self.next - self.first < AHEAD:
                    self.next += 1
                    return self.next - 1
                if self.next >= self.count and not (self.checked and self.first < self.count):
                    return None
                self.cv.wait(0.5)
            return None

    def put_back(self, i):
        """A piece a connection could not finish (its mirror was dropped): the next connection free takes it from its start."""
        with self.cv:
            self.got.pop(i, None)
            self.again.append(i)
            self.cv.notify_all()

    def redo(self, i):
        """A finished piece whose torrent pieces did not match: fetched again, before any new one."""
        with self.cv:
            self.done.pop(i, None)
            self.got.pop(i, None)
            self.source.pop(i, None)
            self.again.append(i)
            self.cv.notify_all()

    def progress(self, i, n):
        with self.cv:
            if n > self.got.get(i, 0):          # bytes arrived: the busy server's time limit starts again, as over one connection,
                self.busy = 0                   # but the rest of a wait still on comes after this progress, so it counts
                self.waited = max(0.0, self.resume_at - time.monotonic())
            self.got[i] = n

    def busy_wait(self, b):
        """(seconds, new) for a connection that heard 5xx or 429 (b: _Busy). The rule of the one-connection path: BUSY_BACKOFF,
        or the server's Retry-After when longer, within BUSY_LIMIT of waiting with no progress. But one wait at a time: a
        connection that hears "busy" while a wait is on joins it, so eight connections waiting together count the time once.
        A joining answer whose Retry-After reaches past the wait extends it (only the extension is charged, within the budget).
        new: this call started or extended the wait (it is announced). Raises Failed('server') once the budget is spent."""
        with self.cv:
            now = time.monotonic()
            if self.resume_at > now:
                extra = min(now + b.wait - self.resume_at, BUSY_LIMIT - self.waited)
                if extra <= 0:
                    return self.resume_at - now, False
                self.waited += extra
                self.resume_at += extra
                self.announce = self.resume_at - now
                self.cv.notify_all()
                return self.resume_at - now, True
            wait = min(max(BUSY_BACKOFF[min(self.busy, len(BUSY_BACKOFF) - 1)], b.wait), BUSY_LIMIT - self.waited)
            if wait <= 0:
                raise Failed('server', f'The download server stayed busy ({b}). Try again later.')
            self.busy += 1
            self.waited += wait
            self.resume_at = now + wait
            self.announce = wait
            self.cv.notify_all()
            return wait, True

    def busy_rest(self):
        """Seconds still to wait on the shared wait (another connection may have extended it), or 0."""
        with self.cv:
            return max(0.0, self.resume_at - time.monotonic())

    def finish(self, i, src=None):
        with self.cv:
            self.done[i] = True        # its bytes stay counted in .got until the hashed run reaches it
            if src:
                self.source[i] = src
            self.cv.notify_all()

    def same(self, etag):
        """The first ETag seen is the file's; a piece with another is from another copy of it."""
        with self.cv:
            if etag and self.etag and etag != self.etag:
                raise _Restart(etag)
            self.etag = self.etag or etag

    def fail(self, e):
        with self.cv:
            if self.error is None and not self.stopping.is_set():
                self.error = e
            self.cv.notify_all()

    def opened(self, conn):
        with self.cv:
            self.conns.add(conn)
            if self.stopping.is_set():
                raise Stopped('paused')

    def closed(self, conn):
        with self.cv:
            self.conns.discard(conn)
        try:
            conn.close()
        except OSError:
            pass

    def halt(self, workers):
        """Stops every connection at once: a read waiting on the network ends now, not at the timeout. A connection still
        connecting or in its handshake notices `stopping` within a slice. Returns only once every worker has ended, so
        nothing holds the .part open or writes to it after a pause."""
        with self.cv:
            self.stopping.set()
            conns = list(self.conns)
            self.cv.notify_all()
        for c in conns:
            try:
                if c.sock:
                    c.sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        for w in workers:
            w.join()        # each wait in a worker is bounded: by `stopping`, a shut socket, or the network timeout


class _Swarmed(_Pieces):
    """The pieces of a file that also comes from other people, rqbit writing into the same file: done in any order, by the
    servers, the mirrors or rqbit. Pieces are counted from byte 0. mode says which piece a connection takes next: 'back' (the
    highest not done, anywhere: the disk keeps gaps empty, so writing far ahead costs nothing), 'window' (the highest within
    AHEAD of the first not done: rqbit takes its front, and no write lands far ahead) or 'front' (the lowest, as without rqbit).
    The busy wait, the first error and halt() are _Pieces'."""

    def __init__(self, size, piece, etag):
        super().__init__(0, size, etag, piece=piece, checked=True)
        self.have = bytearray(self.count)       # 1: done
        self.claimed = set()
        self.mode = 'front'

    def is_done(self, k):
        return bool(self.have[k])

    def complete(self):
        return all(self.have)

    def received(self):
        with self.cv:
            return sum(b - a for a, b in (self.span(k) for k in range(self.count) if self.have[k])) + sum(self.got.values())

    def take(self):
        with self.cv:
            while not self.stopping.is_set():
                k = self._pick()
                if k is not None:
                    self.claimed.add(k)
                    return k
                if all(self.have):
                    return None
                self.cv.wait(0.5)
            return None

    def _pick(self):
        def free(k):
            return not self.have[k] and k not in self.claimed
        if self.mode == 'back':
            return next((k for k in range(self.count - 1, -1, -1) if free(k)), None)
        first = next((k for k in range(self.count) if not self.have[k]), None)
        if first is None:
            return None
        window = range(first, min(self.count, first + AHEAD))
        return next((k for k in (reversed(window) if self.mode == 'window' else window) if free(k)), None)

    def finish(self, i, src=None):
        with self.cv:
            self.have[i] = 1
            self.claimed.discard(i)
            self.got.pop(i, None)
            if src:
                self.source[i] = src
            self.cv.notify_all()

    def put_back(self, i):
        with self.cv:
            self.claimed.discard(i)
            self.got.pop(i, None)
            self.cv.notify_all()

    def drop(self, i):
        """A piece the last read found wrong: not done any more."""
        with self.cv:
            self.have[i] = 0
            self.source.pop(i, None)
            self.cv.notify_all()

    def restart(self):
        """New connections after halt(): no piece is taken, and no error is on."""
        with self.cv:
            self.stopping.clear()
            self.error = None
            self.claimed.clear()
            self.got.clear()
            self.conns.clear()

    def reset(self):
        """The file on the server changed: nothing done counts."""
        with self.cv:
            self.have = bytearray(self.count)
            self.source.clear()
            self.redos.clear()
            self.etag = None


class _Restart(Exception):
    def __init__(self, etag, whole=False):
        super().__init__('restart')
        self.etag, self.whole = etag, whole
        self.h, self.start = None, 0


class _Busy(Exception):
    """The server answered, but with 5xx or 429: the internet is fine, the server is not ready. .wait is its Retry-After, or 0."""

    def __init__(self, status, retry_after):
        super().__init__(f'HTTP {status}')
        try:
            self.wait = max(0, min(int(retry_after or 0), MAX_RETRY_AFTER))
        except ValueError:
            self.wait = 0           # an HTTP date, or nonsense: use the backoff alone


class _KeptBreaking(Failed):
    """Failed('network') for a connection that kept breaking: the server could not be reached, as opposed to one that refused."""


class _MirrorFailed(Exception):
    """A mirror that did not answer as a mirror should (a wrong range, size or status, a redirect elsewhere, a certificate it
    could not prove, a connection that kept breaking): it is not asked again, and the download goes on without it."""


def swarm_done(dest):
    """Bytes of <dest> that its BitTorrent download (Download._run_swarm) has done so far, from its .part.json, or None when the
    file is not coming that way. The data is elsewhere (in BitTorrent's folder), so the .json is what says how far it is."""
    meta = _load_meta(str(dest) + '.part.json')
    sw, size = meta.get('swarm'), meta.get('size')
    if not isinstance(sw, dict) or not isinstance(sw.get('piece'), int) or sw['piece'] <= 0 or not isinstance(size, int):
        return None
    n = 0
    for run in sw.get('have') or []:
        try:
            a, b = int(run[0]), int(run[1])
        except (TypeError, ValueError, IndexError):
            continue
        n += max(0, min(b * sw['piece'], size) - a * sw['piece'])
    return min(n, size)


def _sparse(path):
    """Windows: the file is marked sparse, so a write far from the front does not first fill everything before it with zeros
    (measured on NTFS: 17 s to write at 8 GiB into a plain file, 0.02 s into a sparse one). Returns whether that is so: elsewhere
    files have holes already; a Windows disk that cannot do it (some network shares) says no."""
    if os.name != 'nt':
        return True
    try:
        import ctypes
        import msvcrt
        from ctypes import wintypes
        k32 = ctypes.WinDLL('kernel32', use_last_error=True)
        k32.DeviceIoControl.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
                                        ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
        with open(path, 'r+b') as f:
            n = wintypes.DWORD()
            return bool(k32.DeviceIoControl(wintypes.HANDLE(msvcrt.get_osfhandle(f.fileno())), 0x900C4, None, 0, None, 0, ctypes.byref(n), None))
    except (OSError, AttributeError, ValueError):
        return False


def _allocated(path):
    """Bytes a file takes on its disk (less than its length where it has holes)."""
    if os.name == 'nt':
        import ctypes
        hi = ctypes.c_ulong()
        lo = ctypes.windll.kernel32.GetCompressedFileSizeW(str(path), ctypes.byref(hi))
        if lo == 0xFFFFFFFF and ctypes.windll.kernel32.GetLastError():
            raise OSError('GetCompressedFileSizeW')
        return (hi.value << 32) + lo
    return os.stat(path).st_blocks * 512


def _holes(folder):
    """Whether the disk under `folder` keeps a gap in a sparse file empty, so writing far ahead costs nothing. Some network shares
    take the sparse mark and fill the gap anyway: measured on a NAS share, 1 MiB written at 4 GiB took 22 s marked sparse or not,
    and the file then took all 4 GiB. A probe (4 KiB written at 64 MiB into a file marked sparse) tells them apart."""
    probe = os.path.join(folder, '.lastbook-holes')
    try:
        open(probe, 'wb').close()
        if not _sparse(probe):
            return False
        with open(probe, 'r+b', buffering=0) as f:
            f.seek(64 * 2 ** 20)
            f.write(b'h' * 4096)
        return _allocated(probe) < 8 * 2 ** 20
    except OSError:
        return False
    finally:
        try:
            os.unlink(probe)
        except OSError:
            pass
