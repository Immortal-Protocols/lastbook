"""Sharing downloads with other people: the person's own choice, off unless they turn it on (Library and local AI → Share).

With sharing on, setup keeps each downloaded file whose torrent is pinned in the manifest (engine/setup/torrent.py) instead of
deleting it once it is unpacked: in <library>.share beside the library, with its .torrent. While Lastbook is open those files
are seeded by rqbit, a BitTorrent program bundled with the app (by Igor Katson, Apache-2.0; the build fetches a pinned
release, packaging/share/). Lastbook itself opens no port and connects to nothing here: it starts rqbit, stops it, and asks it
(engine/setup/download.local_api) how much it has uploaded, which is added up across runs (Tally). rqbit is started
  - with its control API on 127.0.0.1 only, behind a password made for that run, and no UPnP (the router is not changed),
    saving no DHT state,
  - with only the torrents Lastbook hands it, each checked against its pinned pieces root first,
  - checking each file against its torrent before it uploads a byte (its own check, --overwrite),
  - tied to Lastbook: on Windows a job object ends it with the app, on Linux the parent-death signal, and on a Mac a watcher
    that ends it once Lastbook has ended, however it ends (_watch).
Peers it meets see this computer's address, as with any BitTorrent program; the setting says so.
"""
import atexit
import json
import os
import queue
import secrets
import subprocess
import sys
import threading
import time
import urllib.parse
from pathlib import Path

SUFFIX = '.share'
TALLY_EVERY = 15                    # seconds between readings of what rqbit has uploaded
ADD_TIMEOUT = 600                   # seconds a server's rqbit may take to answer a new torrent (Station.add)


def binary():
    """The bundled rqbit, or None (this build has none: sharing is not offered)."""
    name = 'rqbit.exe' if os.name == 'nt' else 'rqbit'
    places = []
    if getattr(sys, 'frozen', False):
        places.append(Path(getattr(sys, '_MEIPASS', Path(sys.executable).parent)) / 'share' / name)
    places.append(Path(__file__).resolve().parents[2] / 'derived' / 'share' / name)
    return next((p for p in places if p.is_file()), None)


def folder_for(target):
    """Where the kept downloads of a library go: <library>.share beside it."""
    return Path(target).with_name(Path(target).name + SUFFIX)


def arguments(folder, torrents, upload_bps=None, port=None):
    """rqbit's arguments to seed `torrents` (paths of .torrent files) whose data is in `folder`, its control API on 127.0.0.1:port."""
    args = ['--disable-dht-persistence', '--disable-upnp-port-forward', '-v', 'warn']
    if upload_bps:
        args += ['--ratelimit-upload', str(int(upload_bps))]
    if port:
        args += ['--http-api-listen-addr', f'127.0.0.1:{int(port)}']
    return args + ['download', '--overwrite'] + ([] if port else ['--disable-http-api']) + ['-o', str(folder)] + [str(t) for t in torrents]


def uploaded(port, secret):
    """What the rqbit at 127.0.0.1:port has uploaded since it started, from its own count, or None."""
    from . import download
    r = download.local_api(port, secret, 'GET', '/stats')
    if not r or r[0] != 200:
        return None
    try:
        n = json.loads(r[1])['counters']['uploaded_bytes']
    except (ValueError, KeyError, TypeError):
        return None
    return n if isinstance(n, int) and not isinstance(n, bool) and 0 <= n < 1 << 62 else None


class Tally:
    """Bytes uploaded to other people, all time, in its own file (not setup.json, which other actions rewrite). rqbit counts
    from 0 each time it starts, so each reading adds what came since that process's last reading, and a smaller one starts
    again from 0."""

    def __init__(self, path):
        self.path, self.lock, self.last = Path(path), threading.Lock(), {}

    def total(self):
        try:
            n = json.loads(self.path.read_text(encoding='utf-8')).get('uploaded_bytes', 0)
            return n if isinstance(n, int) and n >= 0 else 0
        except (OSError, ValueError, AttributeError):
            return 0

    def add(self, readings):
        """readings: {process: bytes it has uploaded so far}. Returns the total."""
        with self.lock:
            total, grew = self.total(), False
            for key, now in readings.items():
                if now is None:
                    continue
                before = self.last.get(key, 0)
                step = now - before if now >= before else now
                self.last[key] = now
                if step:
                    total += step
                    grew = True
            if grew:
                try:
                    self.path.parent.mkdir(parents=True, exist_ok=True)
                    tmp = self.path.with_suffix('.tmp')
                    tmp.write_text(json.dumps({'uploaded_bytes': total}), encoding='utf-8')
                    os.replace(tmp, self.path)
                except OSError as e:
                    print(f'setup: could not save what was shared: {e}', flush=True)
            return total


class Seeder:
    """The rqbit processes seeding the kept files: one for each folder of data, each with its control API on 127.0.0.1 behind its
    own password, read every TALLY_EVERY seconds for what it has uploaded. command: the program to run instead of the bundled
    rqbit (tests). tally: where the uploaded bytes are added up."""

    def __init__(self, command=None, tally=None):
        self.command, self.tally = command, tally
        self.procs = []
        self.lock = threading.Lock()
        self._watch = None
        atexit.register(self.stop)

    def available(self):
        return bool(self.command or binary())

    def start(self, groups, upload_bps=None):
        """groups: {data folder: [torrent paths]}. Whatever ran before is stopped first. Returns the number of files seeded."""
        self.stop()
        prog = list(self.command) if self.command else ([str(binary())] if binary() else None)
        if not prog:
            return 0
        n = 0
        with self.lock:
            for folder, torrents in groups.items():
                if not torrents:
                    continue
                from . import download
                port, secret = download.loopback_port(), secrets.token_urlsafe(24)
                try:
                    p = _spawn(prog + arguments(folder, torrents, upload_bps, port), secret)
                except OSError as e:
                    print(f'setup: sharing could not start: {e}', flush=True)
                    continue
                self.procs.append((p, str(folder), [str(t) for t in torrents], port, secret))
                n += len(torrents)
            if n and self.tally is not None and not (self._watch and self._watch.is_alive()):
                self._watch = threading.Thread(target=self._count, daemon=True, name='setup-share-count')
                self._watch.start()
        if n:
            print(f'setup: sharing {n} files with BitTorrent', flush=True)
        return n

    def running(self):
        """[(data folder, [torrent paths])] of the processes still running. The watcher of one that has ended on its own goes too."""
        with self.lock:
            out = []
            for p, f, t, _, _ in self.procs:
                if p.poll() is None:
                    out.append((f, t))
                else:
                    _unwatch(p)
            return out

    def readings(self):
        """{process: bytes uploaded so far} of the processes running. The watcher of one that has ended on its own goes too."""
        with self.lock:
            procs = list(self.procs)
        out = {}
        for p, _, _, port, secret in procs:
            if p.poll() is None:
                out[(p.pid, port)] = uploaded(port, secret)
            else:
                _unwatch(p)
        return out

    def shared(self):
        """All the bytes uploaded to other people so far, with what the running processes say now."""
        if self.tally is None:
            return 0
        return self.tally.add(self.readings())

    def _count(self):
        while True:
            with self.lock:
                if not self.procs:
                    return
            self.shared()
            time.sleep(TALLY_EVERY)

    def stop(self):
        if self.tally is not None:
            self.shared()                  # the last reading, before the count goes with the process
        with self.lock:
            procs, self.procs = self.procs, []
        for p, _, _, _, _ in procs:
            _unwatch(p)
            if p.poll() is None:
                p.terminate()
        for p, _, _, _, _ in procs:
            try:
                p.wait(5)
            except subprocess.TimeoutExpired:
                p.kill()

_JOB = None


def _spawn(args, secret):
    """Starts rqbit with its control API password, no window, tied to Lastbook's life (raises OSError)."""
    kw = {'stdin': subprocess.DEVNULL, 'stdout': subprocess.DEVNULL, 'stderr': subprocess.DEVNULL, 'close_fds': True,
          'env': {**os.environ, 'RQBIT_HTTP_BASIC_AUTH_USERPASS': f'lastbook:{secret}'}}
    if os.name == 'nt':
        kw['creationflags'] = 0x08000000          # CREATE_NO_WINDOW
    elif sys.platform.startswith('linux'):
        kw['preexec_fn'] = _die_with_parent
        return _from_spawner(args, kw)
    p = subprocess.Popen(args, **kw)
    if os.name == 'nt':
        _tie(p)
    elif sys.platform == 'darwin':
        _watch(p)
    return p


# The Mac watcher: notes rqbit's start time, waits for the end of a pipe only Lastbook writes to, then ends rqbit only if that
# number still has the start time it noted. ps gives it to the second, so a number used again by another process is very
# unlikely to be hit.
_WATCH = 's=$(/bin/ps -o lstart= -p "$1"); read -r _; [ -n "$s" ] && [ "$(/bin/ps -o lstart= -p "$1")" = "$s" ] && kill -TERM "$1"'
_WATCH_LOCK = threading.Lock()


def _watch(p):
    """Mac: no job object and no parent-death signal, and the app's Quit (NSApplication terminate:, which calls exit()) and its
    start again after setup (os.execv, app/main.py relaunch) both skip atexit. So each rqbit gets a watcher, a /bin/sh holding the
    read end of a pipe whose write end only this process has: however Lastbook ends (Quit, a crash, Force Quit, that exec), the
    pipe closes and the watcher ends rqbit. Stopping rqbit ends its watcher first (_unwatch). If the watcher cannot start, rqbit
    is ended at once and OSError raised, so it never runs untied: Seeder.start and Swarm.start report that sharing or
    BitTorrent could not start."""
    try:
        p.watcher = subprocess.Popen(['/bin/sh', '-c', _WATCH, 'lastbook-rqbit-watch', str(p.pid)], stdin=subprocess.PIPE,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
    except OSError as e:
        p.terminate()
        try:
            p.wait(5)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait()
        raise OSError(f'rqbit could not be tied to Lastbook ({e})') from e


def _unwatch(p):
    """Ends p's watcher, if it has one: before Lastbook stops p itself, or once p has ended on its own."""
    with _WATCH_LOCK:                                # one caller takes it, even from two threads at once
        w, p.watcher = getattr(p, 'watcher', None), None
    if w is None:
        return
    if w.poll() is None:
        w.kill()                                     # killed in its read: it never gets to end anything
        w.wait()
    w.stdin.close()


_SPAWNER, _SPAWNER_LOCK = None, threading.Lock()


def _from_spawner(args, kw):
    """Linux: the parent-death signal comes when the *thread* that started the child ends, not the process. Seeding is started
    from a request's thread, a job's or a short one of its own, each of which ends at once, and rqbit would go with it. So every
    rqbit is started from one thread that lives as long as Lastbook (raises OSError as Popen does)."""
    global _SPAWNER
    with _SPAWNER_LOCK:
        if _SPAWNER is None:
            _SPAWNER = queue.Queue()
            threading.Thread(target=_spawner, args=(_SPAWNER,), daemon=True, name='setup-share-spawner').start()
    box, done = [], threading.Event()
    _SPAWNER.put((args, kw, box, done))
    done.wait()
    if isinstance(box[0], BaseException):
        raise box[0]
    return box[0]


def _spawner(q):
    while True:
        args, kw, box, done = q.get()
        try:
            box.append(subprocess.Popen(args, **kw))
        except BaseException as e:              # handed to the thread that asked
            box.append(e)
        done.set()


class Swarm:
    """One file downloaded from other people too: its own rqbit (server mode, nothing saved, its control API on 127.0.0.1 behind
    a password made for it) writing into the very file Lastbook downloads into, so there is one copy on the disk. rqbit fetches
    from the front; Lastbook's own connections work from the back. rqbit writes what peers send before it checks it, so nothing
    is taken on its word: download.py counts a piece only when it matches the torrent's piece hash on the disk, and the file is
    judged by a full read after stop(), once this process has ended and nothing else can write to it.
    command: rqbit (or a stand-in), extra: arguments before 'server' (tests: no DHT, loopback), peers: peers to try at once."""

    def __init__(self, torrent_data, wanted=lambda: True, tally=None, command=None, extra=(), peers=()):
        self.torrent, self.wanted, self.tally = torrent_data, wanted, tally
        self.command, self.extra, self.peers = command, list(extra), list(peers)
        self.proc, self.port, self.secret, self.id = None, None, None, None

    def start(self, folder):
        """rqbit on `folder`, the torrent added (its data file is the one in there). True once it took the torrent."""
        prog = list(self.command) if self.command else ([str(binary())] if binary() else None)
        if not prog:
            return False
        started = _server(prog, self.extra, folder, 'BitTorrent')
        if started is None:
            return False
        self.proc, self.port, self.secret = started
        atexit.register(self.stop)            # ended at a normal exit too, where nothing else ties it to Lastbook
        self.id = _add(self.port, self.secret, self.torrent, folder, self.peers)
        if self.id is None:
            print('setup: BitTorrent did not take the torrent; downloading from the servers only', flush=True)
            self.stop()
            return False
        return True

    def poll(self):
        """Bytes rqbit has fetched from other people so far (its own count), or None. What it uploaded goes to the tally."""
        from . import download
        p = self.proc
        if p is not None and p.poll() is not None:
            _unwatch(p)                              # rqbit ended on its own: its watcher goes too
        if not p or p.poll() is not None or self.id is None:
            return None
        if self.tally is not None:
            self.tally.add({('swarm', p.pid, self.port): uploaded(self.port, self.secret)})
        r = download.local_api(self.port, self.secret, 'GET', f'/torrents/{self.id}/stats/v1')
        try:
            n = json.loads(r[1])['live']['snapshot']['fetched_bytes'] if r and r[0] == 200 else None
        except (ValueError, KeyError, TypeError):
            return None
        return n if isinstance(n, int) and not isinstance(n, bool) and n >= 0 else None

    def stop(self):
        """Ends rqbit and returns only once its process has ended: after this, nothing but Lastbook writes to the file."""
        p, self.proc = self.proc, None
        if p is None:
            return
        atexit.unregister(self.stop)
        if self.tally is not None and p.poll() is None:
            self.tally.add({('swarm', p.pid, self.port): uploaded(self.port, self.secret)})
        _unwatch(p)
        if p.poll() is None:
            p.terminate()
        try:
            p.wait(15)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait(15)


def _server(prog, extra, folder, what):
    """Starts `rqbit server start` on folder (nothing saved), its control API on 127.0.0.1 behind a password made for it, and
    waits until it answers: (process, API port, password), or None. extra: arguments before 'server'."""
    from . import download
    port, secret = download.loopback_port(), secrets.token_urlsafe(24)
    extra = list(extra)
    base = [a for a in ('--disable-dht-persistence', '--disable-upnp-port-forward') if a not in extra]   # rqbit refuses a flag twice
    base += [] if '-v' in extra else ['-v', 'warn']
    args = prog + base + ['--http-api-listen-addr', f'127.0.0.1:{port}'] + extra + ['server', 'start', '--disable-persistence', str(folder)]
    try:
        proc = _spawn(args, secret)
    except OSError as e:
        print(f'setup: {what} could not start: {e}', flush=True)
        return None
    t0 = time.time()
    while time.time() - t0 < 20 and proc.poll() is None:
        r = download.local_api(port, secret, 'GET', '/stats')
        if r and r[0] == 200:
            break
        time.sleep(0.1)
    if proc.poll() is not None:
        print(f'setup: {what} stopped as it started (rqbit exit code {proc.returncode})', flush=True)
    return proc, port, secret


def _add(port, secret, data, folder, peers=(), timeout=5):
    """Adds a torrent to the rqbit at 127.0.0.1:port, its data in folder, which rqbit checks against the torrent first
    (overwrite: nothing there is thrown away). Its id there, or None."""
    from . import download
    query = 'overwrite=true&output_folder=' + urllib.parse.quote(str(folder), safe='')
    if peers:
        query += '&initial_peers=' + urllib.parse.quote(','.join(peers), safe='')
    r = download.local_api(port, secret, 'POST', '/torrents?' + query, body=data, timeout=timeout)
    try:
        n = json.loads(r[1])['id'] if r and r[0] == 200 else None
        return n if isinstance(n, int) and not isinstance(n, bool) else None
    except (ValueError, KeyError, TypeError):
        return None


class Station:
    """A server that shares Lastbook's downloads (tools/seed.py): one rqbit for as long as it runs, `server start` with nothing
    saved, listening for peers on a fixed port (so a firewall can let them in), no UPnP, its control API on 127.0.0.1 behind a
    password made for it. Torrents are added one at a time as their files are ready, without checking the others again; rqbit
    checks each file against its torrent before it uploads a byte of it. tally: where the uploaded bytes are added up.
    extra: more arguments before 'server' (tests: no DHT, loopback only)."""

    def __init__(self, folder, listen_port=None, upload_bps=None, command=None, extra=(), tally=None):
        self.folder, self.listen_port, self.upload_bps = Path(folder), listen_port, upload_bps
        self.command, self.extra, self.tally = command, list(extra), tally
        self.proc, self.port, self.secret, self.added = None, None, None, {}
        self._asking = None                     # the thread of an add still waiting for rqbit's answer

    def available(self):
        return bool(self.command or binary())

    def start(self):
        """True once rqbit answers."""
        prog = list(self.command) if self.command else ([str(binary())] if binary() else None)
        if not prog:
            return False
        extra = list(self.extra)
        if self.listen_port:
            extra += ['--listen-port', str(int(self.listen_port))]
        if self.upload_bps:
            extra += ['--ratelimit-upload', str(int(self.upload_bps))]
        started = _server(prog, extra, self.folder, 'sharing')
        if started is None:
            return False
        self.proc, self.port, self.secret = started
        atexit.register(self.stop)
        self.added = {}
        return self.running()

    def running(self):
        """True while rqbit runs. The watcher of one that has ended on its own goes too."""
        p = self.proc
        if p is None:
            return False
        if p.poll() is None:
            return True
        _unwatch(p)
        return False

    def add(self, name, torrent_data, stop=None):
        """Shares the file `name` in the folder by its torrent (already checked against its pin). True once rqbit took it; rqbit
        may take a while to check a large file before it offers any of it. A torrent added before is not added again.
        stop: an Event. The request waits for rqbit's answer on a thread of its own, so once `stop` is set (or rqbit ends) this
        returns False at once with the file not added; stop() then ends rqbit, and the request with it."""
        if name in self.added:
            return True
        if not self.running():
            return False
        box, done = [], threading.Event()

        def ask():
            try:
                box.append(_add(self.port, self.secret, torrent_data, self.folder, timeout=ADD_TIMEOUT))
            finally:
                done.set()
        self._asking = threading.Thread(target=ask, daemon=True, name='setup-share-add')
        self._asking.start()
        while not done.wait(0.1):
            if (stop is not None and stop.is_set()) or not self.running():
                return False
        n = box[0] if box else None
        if n is None:
            return False
        self.added[name] = n
        return True

    def shared(self):
        """All the bytes uploaded to other people so far, with what this rqbit says now (0 without a tally)."""
        if self.tally is None:
            return 0
        if not self.running():
            return self.tally.total()
        return self.tally.add({('station', self.proc.pid, self.port): uploaded(self.port, self.secret)})

    def stop(self):
        p = self.proc
        if p is None:
            return
        if self.tally is not None and p.poll() is None:
            self.shared()                      # the last reading, before the count goes with the process
        self.proc = None
        atexit.unregister(self.stop)
        _unwatch(p)                            # its watcher first, so it never acts on a process ended here
        if p.poll() is None:
            p.terminate()
        try:
            p.wait(15)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait(15)
        t, self._asking = self._asking, None
        if t is not None:
            t.join(5)                          # an add left waiting ends with rqbit's connection


def _tie(p):
    """Windows: rqbit goes in a job object that ends it when Lastbook ends, however it ends."""
    global _JOB
    try:
        import ctypes
        from ctypes import wintypes
        k32 = ctypes.WinDLL('kernel32', use_last_error=True)
        if _JOB is None:
            class IO(ctypes.Structure):
                _fields_ = [(n, ctypes.c_ulonglong) for n in ('r', 'w', 'o', 'rb', 'wb', 'ob')]

            class Basic(ctypes.Structure):
                _fields_ = [('PerProcessUserTimeLimit', ctypes.c_longlong), ('PerJobUserTimeLimit', ctypes.c_longlong),
                            ('LimitFlags', wintypes.DWORD), ('MinimumWorkingSetSize', ctypes.c_size_t),
                            ('MaximumWorkingSetSize', ctypes.c_size_t), ('ActiveProcessLimit', wintypes.DWORD),
                            ('Affinity', ctypes.c_size_t), ('PriorityClass', wintypes.DWORD), ('SchedulingClass', wintypes.DWORD)]

            class Extended(ctypes.Structure):
                _fields_ = [('Basic', Basic), ('Io', IO), ('ProcessMemoryLimit', ctypes.c_size_t), ('JobMemoryLimit', ctypes.c_size_t),
                            ('PeakProcessMemoryUsed', ctypes.c_size_t), ('PeakJobMemoryUsed', ctypes.c_size_t)]
            k32.CreateJobObjectW.restype = wintypes.HANDLE
            job = k32.CreateJobObjectW(None, None)
            info = Extended()
            info.Basic.LimitFlags = 0x2000                    # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not job or not k32.SetInformationJobObject(wintypes.HANDLE(job), 9, ctypes.byref(info), ctypes.sizeof(info)):
                raise OSError(ctypes.get_last_error(), 'job object')
            _JOB = job                                   # held open for the app's life: closing it ends the processes
        if not k32.AssignProcessToJobObject(wintypes.HANDLE(_JOB), wintypes.HANDLE(int(p._handle))):
            raise OSError(ctypes.get_last_error(), 'AssignProcessToJobObject')
    except (OSError, AttributeError, ValueError) as e:
        print(f'setup: sharing is not tied to Lastbook ({e}); it stops when Lastbook exits normally', flush=True)


def _die_with_parent():
    """Linux, in the child before rqbit starts: SIGTERM when the thread that started it ends, which is _spawner's: when Lastbook
    ends."""
    try:
        import ctypes
        import signal
        ctypes.CDLL(None).prctl(1, signal.SIGTERM)                # PR_SET_PDEATHSIG
    except (OSError, AttributeError):
        pass
