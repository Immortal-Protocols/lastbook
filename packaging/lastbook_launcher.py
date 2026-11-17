"""Lastbook launcher: the packaged app's entry point.

  Lastbook.exe --data "D:\\My Library"             window around the local server (pywebview)
  Lastbook.exe --data "D:\\My Library" --headless  server only, no window
  Lastbook.exe --data "D:\\My Library" --stop      ask a running headless copy on --port to finish and exit
  Lastbook.exe --data "D:\\My Library" --check     import every packaged library, write derived/logs/check.json, exit

The data folder comes from --data, then the LASTBOOK_DATA environment variable, then a folder named LastbookData
beside the program folder (from source: the project folder). It must contain library-data/catalog.json. Output goes to
<data>/derived/logs/lastbook.log, rotated by size, because the packaged exe has no console. Phone sharing stays off
unless --lan is given. --no-index keeps the semantic index from updating in the background.
"""
import argparse
import json
import os
import signal
import sys
import threading
import time
import traceback
import urllib.request
from pathlib import Path

FROZEN = bool(getattr(sys, 'frozen', False))
os.environ['ORT_DISABLE_TELEMETRY'] = '1'  # before anything imports onnxruntime; retrieval.py has the reason
if not FROZEN:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
LOG_LIMIT = 5 * 1024 * 1024
LOG_BACKUPS = 3


def data_folder(arg):
    if arg:
        return Path(arg)
    if os.environ.get('LASTBOOK_DATA'):
        return Path(os.environ['LASTBOOK_DATA'])
    if FROZEN:
        return Path(sys.executable).resolve().parent.parent / 'LastbookData'
    return Path(__file__).resolve().parents[1]


def write_stderr(message):
    """A windowed exe has no sys.stderr. Use the handle or the console of whoever started it, if there is one."""
    message = message.rstrip('\n') + '\n'
    if sys.stderr is not None:
        sys.stderr.write(message)
        sys.stderr.flush()
    elif os.name == 'nt':
        import ctypes
        import msvcrt
        kernel32 = ctypes.windll.kernel32
        kernel32.GetStdHandle.restype = ctypes.c_void_p
        handle = kernel32.GetStdHandle(-12)  # STD_ERROR_HANDLE, set when stderr is redirected
        if handle not in (None, 0, ctypes.c_void_p(-1).value):
            try:
                with os.fdopen(msvcrt.open_osfhandle(handle, os.O_WRONLY), 'w', encoding='utf-8', closefd=False) as f:
                    f.write(message)
                return
            except OSError:
                pass
        if kernel32.AttachConsole(-1):  # ATTACH_PARENT_PROCESS
            with open('CONOUT$', 'w', encoding='utf-8', errors='replace') as f:
                f.write(message)


def show_error(message, window):
    if window and os.name == 'nt':
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, message, 'Lastbook', 0x10)  # MB_ICONERROR
    else:
        write_stderr(message)


class RotatingLog:
    """Stands in for stdout and stderr: keeps lastbook.log and a few older copies, each up to LOG_LIMIT."""
    encoding = 'utf-8'
    errors = 'replace'

    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.Lock()
        self.file = open(self.path, 'ab')

    def write(self, text):
        data = text.encode('utf-8', 'replace')
        with self.lock:
            if self.file.tell() + len(data) > LOG_LIMIT:
                self.rotate()
            self.file.write(data)
            self.file.flush()
        return len(text)

    def rotate(self):
        self.file.close()
        try:
            for i in range(LOG_BACKUPS - 1, 0, -1):
                older = self.path.with_name(f'{self.path.name}.{i}')
                if older.exists():
                    os.replace(older, self.path.with_name(f'{self.path.name}.{i + 1}'))
            os.replace(self.path, self.path.with_name(f'{self.path.name}.1'))
            self.file = open(self.path, 'ab')
        except OSError:  # another copy has it open (Windows): start over rather than grow without limit
            self.file = open(self.path, 'wb')

    def flush(self):
        pass

    def isatty(self):
        return False


def open_log(data):
    logs = data / 'derived' / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    log = RotatingLog(logs / 'lastbook.log')
    if sys.stdout is None or FROZEN:
        sys.stdout = log
    if sys.stderr is None or FROZEN:
        sys.stderr = log
    return logs


def search_index_check(table=None):
    """The packaged SQLite must make the library's search table as the app makes it and search it as the app does: the same
    self-test as app/main.py --self-test (engine/library.py search_self_test)."""
    import engine.paths  # noqa: F401  (first: it names the library folder that engine.library fixes when it is imported)
    import engine.library as library
    return library.search_self_test(table)


def check(data, logs):
    """Prove every packaged library imports from the packaged folder. Loads no model and opens no window."""
    out = {'frozen': FROZEN, 'executable': sys.executable, 'python': sys.version,
           'utf8_mode': sys.flags.utf8_mode, 'fs_encoding': sys.getfilesystemencoding(), 'data': str(data),
           'PATH': os.environ.get('PATH', '')}

    def attempt(name, fn):
        try:
            out[name] = fn()
        except BaseException as e:
            out[name] = f'FAILED {type(e).__name__}: {e}'

    def numpy_():
        import numpy
        return numpy.__version__

    def ort_():
        import onnxruntime
        return {'version': onnxruntime.__version__, 'providers': onnxruntime.get_available_providers(), 'model_loaded': False}

    def tokenizers_():
        import tokenizers
        return tokenizers.__version__

    def bs4_():
        import bs4
        return {'version': bs4.__version__, 'parsed': bs4.BeautifulSoup('<p>caf\u00e9</p>', 'html.parser').get_text()}

    def pdfium_():
        import pypdfium2
        import pypdfium2.version as v
        return {'pypdfium2': getattr(v, 'PYPDFIUM_INFO', None) and str(v.PYPDFIUM_INFO), 'pdfium': str(getattr(v, 'PDFIUM_INFO', ''))}

    def zim_():
        import libzim
        from libzim.reader import Archive
        zims = sorted((data / 'library-data' / 'collections').glob('*.zim'))
        a = Archive(zims[0])
        return {'version': getattr(libzim, '__version__', None), 'file': zims[0].name, 'entries': a.entry_count, 'has_fulltext_index': a.has_fulltext_index}

    def sqlite_():
        return search_index_check()

    def webview_():
        import webview
        return getattr(webview, '__version__', 'imported')

    def winforms_():  # the module that would build the window; importing it opens nothing
        import clr  # noqa: F401
        import webview.platforms.winforms as w
        return {'imported': True, 'renderer': getattr(w, 'renderer', None)}

    def lock_():
        from engine import paths as p
        lockfile = data / 'derived' / 'locktest.lock'
        a, b = open(lockfile, 'w'), open(lockfile, 'w')
        p.try_lock(a)
        try:
            p.try_lock(b)
            second = 'second lock was GRANTED (wrong)'
        except OSError:
            second = 'second lock refused (right)'
        p.unlock(a)
        p.try_lock(b)
        p.unlock(b)
        a.close()
        b.close()
        return second + '; after unlock, lock granted'

    def engine_():
        import server
        import retrieval
        import engine.library
        return {'imported': True, 'semantic_available': retrieval.AVAILABLE, 'onnxruntime_telemetry': retrieval.TELEMETRY,
                'LIB': str(server.LIB), 'WEB': str(server.WEB), 'remote_storage_loaded': engine.library.serve_remote is not None}

    for name, fn in [('numpy', numpy_), ('onnxruntime', ort_), ('tokenizers', tokenizers_), ('beautifulsoup4', bs4_),
                     ('pypdfium2', pdfium_), ('libzim', zim_), ('sqlite', sqlite_), ('pywebview', webview_),
                     ('pywebview_winforms', winforms_), ('lock', lock_), ('engine', engine_)]:
        attempt(name, fn)
    (logs / 'check.json').write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding='utf-8')
    return 1 if 'FAILED' in json.dumps(out) else 0


def wait_for(url, seconds=60):
    end = time.time() + seconds
    while time.time() < end:
        try:
            urllib.request.build_opener(urllib.request.ProxyHandler({})).open(url, timeout=2).read(1)
            return True
        except OSError:
            time.sleep(0.25)
    return False


def stop_file(data, port):
    return data / 'derived' / f'lastbook-{port}.stop'


def ask_to_stop(data, port):
    """--stop: leave a file the running copy looks for. It deletes the file on its way out."""
    f = stop_file(data, port)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text('stop', encoding='utf-8')
    end = time.time() + 15
    while time.time() < end:
        if not f.exists():
            return 0
        time.sleep(0.25)
    f.unlink(missing_ok=True)
    write_stderr(f'Lastbook did not stop: nothing on port {port} answered the request.')
    return 1


def watch_for_stop(data, port, server):
    """A windowed exe has no console, so no Ctrl+C reaches it. Stop cleanly when --stop asks, or on a signal."""
    f = stop_file(data, port)
    f.unlink(missing_ok=True)  # left over from an earlier run

    def stop(*_):
        threading.Thread(target=lambda: server.SERVER and server.SERVER.shutdown(), daemon=True).start()

    for name in ('SIGINT', 'SIGTERM', 'SIGBREAK'):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), stop)

    def poll():
        while not f.exists():
            time.sleep(1)
        f.unlink(missing_ok=True)
        print(f'{time.strftime("%Y-%m-%d %H:%M:%S")} stop requested', flush=True)
        stop()

    threading.Thread(target=poll, daemon=True).start()


def main():
    ap = argparse.ArgumentParser(description='Lastbook')
    ap.add_argument('--data', help='data folder holding library-data/ and derived/ (or set LASTBOOK_DATA)')
    ap.add_argument('--port', type=int, default=8941)
    ap.add_argument('--headless', action='store_true', help='run the local server with no window')
    ap.add_argument('--no-index', action='store_true', help='do not update the semantic index in the background')
    ap.add_argument('--lan', action='store_true', help='also serve phones on the same network; off unless given')
    ap.add_argument('--stop', action='store_true', help='ask a running headless copy on --port to exit')
    ap.add_argument('--check', action='store_true', help='import every packaged library, write derived/logs/check.json, exit')
    a = ap.parse_args()
    window = not (a.headless or a.stop or a.check)
    data = data_folder(a.data).resolve()
    if not (data / 'library-data' / 'catalog.json').is_file():
        show_error(f'No library found.\n\n{data}\nhas no library-data/catalog.json.\n\nChoose the data folder with --data or LASTBOOK_DATA.', window)
        return 2
    if a.stop:
        return ask_to_stop(data, a.port)
    os.environ['LASTBOOK_DATA'] = str(data)
    logs = open_log(data)
    print(f'{time.strftime("%Y-%m-%d %H:%M:%S")} start pid={os.getpid()} args={sys.argv[1:]} data={data}', flush=True)
    if a.check:
        code = check(data, logs)
        print(f'check finished, exit code {code}', flush=True)
        return code
    sys.argv = ['server', '--port', str(a.port)] + ['--no-index'] * a.no_index + ['--lan'] * a.lan
    import server
    if a.headless:
        watch_for_stop(data, a.port, server)
        server.main()
        server.SERVER.server_close()
        print(f'{time.strftime("%Y-%m-%d %H:%M:%S")} stopped', flush=True)
        return 0
    import webview
    t = threading.Thread(target=server.main, daemon=True)
    t.start()
    url = f'http://127.0.0.1:{a.port}/'
    if not wait_for(url):
        print('server did not answer', flush=True)
        show_error(f'Lastbook could not start its local server on port {a.port}.\n\nDetails are in {logs / "lastbook.log"}.', True)
        return 1
    webview.create_window('Lastbook', url, width=1280, height=860)
    webview.start(private_mode=False, storage_path=str(data / 'derived' / 'webview'))
    os._exit(0)  # window closed: end the server thread too


if __name__ == '__main__':
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException as e:
        traceback.print_exc()
        show_error(f'Lastbook could not start: {type(e).__name__}: {e}', not {'--headless', '--check', '--stop'} & set(sys.argv))
        sys.exit(1)
