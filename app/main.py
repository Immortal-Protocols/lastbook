"""Lastbook desktop app: the entry point. Opens a window around the engine, with no network port.

  Lastbook --data "<folder>"
  Lastbook --self-test        check that this copy can build and search a library index, print the result as JSON, exit

The data folder comes from --data, then LASTBOOK_DATA, then the person's remembered selection, then the app's own data
folder. Existing libraries elsewhere are opened only when the person chooses them. If no library is available, the app opens
setup (engine/setup/, web/setup.html) to download one or choose an existing library.
Output goes to <data>/derived/logs/lastbook.log, rotated by size, because a packaged app has no console.

Sharing with a phone, a chosen port and running with no window all belong to the server version: python server.py.
"""
import argparse
import json
import os
import sys
import tempfile
import threading
import time
import traceback
from contextlib import suppress
from pathlib import Path

FROZEN = bool(getattr(sys, 'frozen', False))
os.environ['ORT_DISABLE_TELEMETRY'] = '1'  # before anything imports onnxruntime; retrieval.py has the reason
if not FROZEN:
    sys.path[:0] = [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parents[1])]
LOG_LIMIT = 5 * 1024 * 1024
LOG_BACKUPS = 3


DATA_NAME = 'LastbookData'
CATALOG = os.path.join('library-data', 'catalog.json')
ASK_TITLE = 'Find your Lastbook library'
ASK = 'Lastbook needs its library folder, called LastbookData. Unzip the library you downloaded, then choose that folder.'


def app_folders():
    """(settings, this computer's app data): roaming and local on Windows, one place on a Mac, XDG's config and data folders on Linux."""
    if sys.platform.startswith('linux'):
        home = Path.home()
        return (Path(os.environ.get('XDG_CONFIG_HOME') or home / '.config') / 'Lastbook',
                Path(os.environ.get('XDG_DATA_HOME') or home / '.local' / 'share') / 'Lastbook')
    if sys.platform == 'win32':
        local = Path(os.environ.get('LOCALAPPDATA') or Path.home() / 'AppData' / 'Local')
        return Path(os.environ.get('APPDATA') or Path.home() / 'AppData' / 'Roaming') / 'Lastbook', local / 'Lastbook'
    mine = Path.home() / 'Library' / 'Application Support' / 'Lastbook'
    return mine, mine


def remembered():
    try:
        return Path(json.loads((app_folders()[0] / 'settings.json').read_text(encoding='utf-8'))['library'])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def remember(folder):
    settings = app_folders()[0] / 'settings.json'
    tmp = None
    try:
        settings.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=settings.parent,
                                         prefix=settings.name + '.', suffix='.tmp', delete=False) as out:
            tmp = Path(out.name)
            json.dump({'library': str(folder)}, out)
        os.replace(tmp, settings)   # a write cut short leaves the old choice, never half a file
    except OSError as e:   # it still opens this time; it asks again next time
        if tmp is not None:
            with suppress(OSError):
                tmp.unlink(missing_ok=True)
        print('could not remember the library:', e, flush=True)


def places():
    """The remembered selection and app-owned data only."""
    yield remembered()
    yield app_folders()[1] / DATA_NAME


def writable(folder):
    try:
        with tempfile.TemporaryFile(dir=folder):
            return True
    except OSError:
        return False


def shown(folder):
    """A folder as the person knows it: its name, not its whole path."""
    return folder.name or str(folder)


def check(folder):
    """(the library, None) if folder is LastbookData or holds it, else (None, why not) in a plain sentence."""
    for f in (folder, folder / DATA_NAME):
        try:
            if not (f / CATALOG).is_file():
                continue
        except OSError:
            continue
        if writable(f):
            return f, None
        return None, f'Lastbook cannot save in “{shown(f)}”. Move the LastbookData folder somewhere you can save to, then choose it there.'
    return None, f'“{shown(folder)}” is not a Lastbook library. Choose the folder called LastbookData, inside the library you unzipped.'


def data_folder(arg):
    """The folder named by --data or LASTBOOK_DATA as given, else the first library found, else None."""
    if arg:
        return Path(arg)
    if os.environ.get('LASTBOOK_DATA'):
        return Path(os.environ['LASTBOOK_DATA'])
    for folder in places():
        if folder is not None and (found := check(folder)[0]):
            return found
    return None


def choose_folder(message):
    if sys.platform == 'darwin':
        import shell_macos
        return shell_macos.choose_folder(ASK_TITLE, message)
    if sys.platform == 'win32':
        import shell_windows
        return shell_windows.choose_folder(ASK_TITLE, message)
    if sys.platform.startswith('linux'):
        import shell_linux
        return shell_linux.choose_folder(ASK_TITLE, message)
    show_error(message)
    return None


def ask_for_library():
    """Asks until the person chooses a library or quits. The choice is remembered."""
    message = ASK
    while True:
        chosen = choose_folder(message)
        if chosen is None:      # Quit
            return None
        if not chosen:          # the picker was cancelled: start over, without an old reason
            message = ASK
            continue
        found, message = check(Path(chosen))
        if found:
            remember(found)
            return found


# ---------------------------------------------------------------------------------------------------------------- setup --
def default_parent():
    """Where setup puts LastbookData unless the person chooses (default_choice has the reason when it is not the usual place)."""
    return default_choice()[0]


def default_choice():
    """(folder, why or None). The app's own data folder until the person chooses another. On Windows the library's longest file
    must fit in an ordinary path (engine/setup/api.py path_too_deep): when a long user name makes the per-user folder too deep,
    <system drive>:\\Lastbook instead, made and closed to other accounts (install.private_folder). If even that cannot be made,
    the per-user folder stays and setup asks the person to choose."""
    parent = app_folders()[1]
    if sys.platform == 'win32':
        from engine.setup import api as setup_api, install
        if setup_api.path_too_deep(parent / DATA_NAME):
            short = Path((os.environ.get('SystemDrive') or 'C:') + '\\') / 'Lastbook'
            if install.private_folder(short):
                return short, f'Saves to {short} because your user folder’s path is too long for the library’s longest file names.'
    return parent, None


def libraries_here():
    out = []
    for folder in places():
        if folder is not None and (found := check(folder)[0]) and found not in out:
            out.append(found)
    return out


def pick_folder(files=False):
    """The native folder or file picker, opened only at the person's request."""
    out, done = [], threading.Event()
    if sys.platform == 'darwin':
        import AppKit
        from PyObjCTools import AppHelper

        def ask():
            try:
                panel = AppKit.NSOpenPanel.openPanel()
                panel.setCanChooseDirectories_(not files)
                panel.setCanChooseFiles_(files)
                panel.setDirectoryURL_(AppKit.NSURL.fileURLWithPath_(str(app_folders()[1])))
                panel.setAllowsMultipleSelection_(False)
                panel.setCanCreateDirectories_(not files)
                panel.setPrompt_('Choose')
                if panel.runModal() == AppKit.NSModalResponseOK:
                    out.append(str(panel.URL().path()))
            finally:
                done.set()
        AppHelper.callAfter(ask)    # AppKit's panels belong to the main thread
    elif sys.platform == 'win32':
        import shell_windows

        def ask():
            try:
                out.append(shell_windows.pick_folder('Choose a library zip or model file' if files else 'Choose a folder', app_folders()[1], files=files))
            except Exception:
                traceback.print_exc()
            finally:
                done.set()
        threading.Thread(target=ask, daemon=True, name='pick-folder').start()   # pick_folder makes its own thread a COM apartment
    elif sys.platform.startswith('linux'):
        import shell_linux
        from gi.repository import GLib

        def ask():
            try:
                chosen = shell_linux.pick(files, str(app_folders()[1]))
                if chosen:
                    out.append(chosen)
            except Exception:
                traceback.print_exc()
            finally:
                done.set()
            return False
        GLib.idle_add(ask)      # GTK's dialogs belong to the main thread
    else:
        return None
    done.wait()
    return out[0] if out else None


def linux_dirs():
    """(data, cache) for WebKit's own storage on Linux: the page's saved settings, and what it can rebuild."""
    return str(app_folders()[1]), str(Path(os.environ.get('XDG_CACHE_HOME') or Path.home() / '.cache') / 'Lastbook')


def relaunch():
    """Start again, as the person would by opening the app: it then finds the library setup has just put in place."""
    argv = [sys.executable] + ([] if FROZEN else [str(Path(__file__).resolve())])
    if sys.platform.startswith('linux') and FROZEN:   # /usr/bin/python3 with its flags and Lastbook's launcher, without this run's arguments
        argv = [sys.executable] + list(sys.orig_argv[1:len(sys.orig_argv) - len(sys.argv) + 1])
    # The engine's current folder and startup flags must not override the
    # library switch staged by setup on the next normal launch.
    os.environ.pop('LASTBOOK_DATA', None)
    print(f'{time.strftime("%Y-%m-%d %H:%M:%S")} setup finished: starting again', flush=True)
    if sys.platform == 'win32':
        import subprocess
        subprocess.Popen(argv, close_fds=True, creationflags=0x00000008 | 0x00000200)   # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        os._exit(0)
    if sys.platform.startswith('linux') and 'shell_linux' in sys.modules:
        sys.modules['shell_linux'].before_exec()
    os.execv(argv[0], argv)     # same process, same Dock icon; pipes to helpers close on exec, so they end


def setup_finished(folder):
    remember(Path(folder))
    relaunch()


def setup_options():
    parent, why = default_choice()
    return {'settings_dir': app_folders()[0], 'default_parent': parent, 'default_why': why, 'on_finish': setup_finished,
            'pick_folder': pick_folder, 'look_for_libraries': libraries_here}


def language_file():
    from ui_language import FILENAME
    return app_folders()[0] / FILENAME


def run_setup():
    """No library yet: the window opens on setup instead. Nothing here reaches the network until the person starts a download."""
    from engine.setup import api as setup_api
    import bridge as B
    work = app_folders()[1] / 'Setup'      # the window's own files and this run's log, until there is a library
    open_log(work)
    print(f'{time.strftime("%Y-%m-%d %H:%M:%S")} start pid={os.getpid()} args={sys.argv[1:]} setup', flush=True)
    setup_api.configure(mode='first-run', **setup_options())
    if sys.platform == 'darwin':
        import shell_macos
        shell_macos.run(B.Bridge(setup_api.SetupServer, 'stream', B.ORIGIN_MAC, language_file=language_file()))
        return 0
    if sys.platform == 'win32':
        import ctypes
        ctypes.windll.kernel32.SetErrorMode(0x0003)
        import shell_windows
        problem = shell_windows.preflight()
        if problem:
            show_error(problem)
            return 3
        return shell_windows.run(setup_api.SetupServer, work, language_file=language_file())
    if sys.platform.startswith('linux'):
        import shell_linux
        shell_linux.run(B.Bridge(setup_api.SetupServer, 'stream', B.ORIGIN_MAC, language_file=language_file()), linux_dirs())
        return 0
    show_error('The Lastbook desktop app runs on Windows and macOS. Everywhere else, use the server version: python server.py')
    return 2


def show_error(message):
    if sys.platform == 'darwin':
        import shell_macos
        shell_macos.show_error(message)
    elif sys.platform == 'win32':
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, message, 'Lastbook', 0x10)  # MB_ICONERROR
    elif sys.platform.startswith('linux'):
        try:
            import shell_linux
            shell_linux.show_error(message)
        except Exception:     # no GTK here: the terminal below still says it
            pass
    if sys.stderr is not None:
        sys.stderr.write(message.rstrip('\n') + '\n')


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


def say(text):
    """Print to whoever started the app; True if it was written. A packaged app on Windows has no sys.stdout: there it writes
    to the handle it was given when its output is redirected (a pipe or a file), else to the console of whatever started it,
    if there is one. It never raises: a packaged app would turn an error here into a dialog that waits for a click."""
    text = text.rstrip('\n') + '\n'
    try:
        if sys.stdout is not None:
            sys.stdout.write(text)
            sys.stdout.flush()
            return True
        if sys.platform != 'win32':     # no Python stream, but the process may still have been given one
            data = text.encode('utf-8')
            return os.write(1, data) == len(data)
        import ctypes
        import msvcrt
        kernel32 = ctypes.windll.kernel32
        kernel32.GetStdHandle.restype = ctypes.c_void_p
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        if handle not in (None, 0, ctypes.c_void_p(-1).value):
            try:
                with os.fdopen(msvcrt.open_osfhandle(handle, os.O_WRONLY | os.O_BINARY), 'w', encoding='utf-8', closefd=False) as f:
                    f.write(text)
                return True
            except OSError:
                pass
        if kernel32.AttachConsole(-1):  # ATTACH_PARENT_PROCESS
            with open('CONOUT$', 'w', encoding='utf-8', errors='replace') as f:
                f.write(text)
            return True
    except (OSError, ValueError):   # a closed pipe or stream
        pass
    return False


def shareable(text):
    """Text with the temporary folder as <tmp> and the person's home folder as ~, so a result can be pasted without their
    user name. Each folder also as an error message shows it, with its backslashes doubled, and on Windows in any case."""
    import re
    flags = re.I if sys.platform == 'win32' else 0
    for folder, name in ((tempfile.gettempdir(), '<tmp>'), (str(Path.home()), '~')):
        if len(folder) > 3:
            for form in (folder, folder.replace('\\', '\\\\')):
                text = re.sub(r'(?<![\w.-])' + re.escape(form) + r'(?![\w.-])', lambda m: name, text, flags=flags)   # a whole folder name, not the start or end of a longer one
    return text


def in_app(path):
    """A file's place inside the app's own folder (<app>/...); a file outside it, as the system's own Python on Linux, keeps
    its full path, with the home folder as ~."""
    if not path:
        return None
    base = Path(sys._MEIPASS if FROZEN else Path(__file__).resolve().parents[1]).resolve()
    try:
        return '<app>/' + Path(path).resolve().relative_to(base).as_posix()
    except ValueError:
        return shareable(str(path))


def sqlite_library():
    """On Windows, the SQLite DLL this process has loaded, as a path; None where that cannot be told. Python's _sqlite3 module
    names only itself, and Windows can resolve a DLL name to another copy than the one beside it."""
    if sys.platform != 'win32':
        return None
    import ctypes
    from ctypes import wintypes
    kernel32 = ctypes.windll.kernel32
    kernel32.GetModuleHandleW.restype = wintypes.HMODULE
    kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    kernel32.GetModuleFileNameW.argtypes = [wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]
    module = kernel32.GetModuleHandleW('sqlite3.dll')
    if not module:
        return None
    buffer = ctypes.create_unicode_buffer(32768)
    return buffer.value if kernel32.GetModuleFileNameW(module, buffer, len(buffer)) else None


def self_test():
    """--self-test: can this copy of Lastbook make the library's search index and search it as the app does, with the SQLite
    it runs with (engine/library.py search_self_test)? It searches as search() does and as the search box does
    (server.py query_groups and fts_expr). Prints one line of JSON and returns 0 when it can, 1 when not or when the result
    could not be written. A packaged Windows app also fails when its SQLite DLL came from outside the app's folder. It runs
    before anything else in main(): it opens no window and no library, reads and writes no settings, and writes nothing
    outside temporary folders of its own."""
    out = {'ok': False, 'frozen': FROZEN, 'python': sys.version.split()[0]}
    try:
        with tempfile.TemporaryDirectory(prefix='lastbook-self-test-', ignore_cleanup_errors=True) as empty:
            # The engine fixes its library folder when first imported, and run from source it loads the library's own
            # tools from there (see engine/library.py). An empty folder of its own keeps every library out.
            os.environ['LASTBOOK_DATA'] = empty
            os.environ.pop('LASTBOOK_LIBRARY', None)
            import sqlite3
            out['sqlite'] = sqlite3.sqlite_version
            out['sqlite_module'] = in_app(getattr(sys.modules.get('_sqlite3'), '__file__', None))
            dll = sqlite_library()
            if dll:
                out['sqlite_library'] = in_app(dll)
                if FROZEN and not out['sqlite_library'].startswith('<app>/'):
                    raise ValueError(f'the SQLite this app loaded is not its own: {out["sqlite_library"]}')
            import engine.paths  # noqa: F401  (first: it names the library folder that engine.library fixes when imported)
            import engine.library as library
            import server      # the search box's way into the index: /api/find runs server.find
            out['search'] = library.search_self_test(matchers={'server.find': lambda w: server.fts_expr(server.query_groups(w)[1])})
            out['ok'] = True
    except Exception as e:
        out['error'] = shareable(f'{type(e).__name__}: {e}')
    written = say(json.dumps(out))
    return 0 if out['ok'] and written else 1


def main():
    ap = argparse.ArgumentParser(description='Lastbook')
    ap.add_argument('--data', help='data folder holding library-data/ and derived/ (or set LASTBOOK_DATA)')
    ap.add_argument('--ask', action='store_true', help='ask for the library folder in a dialog instead of opening setup')
    ap.add_argument('--self-test', action='store_true', help='check that this copy can build and search a library index, then exit: '
                    'prints the result as JSON, exits 0 when it can and 1 when not, and opens no window and no library')
    if '--self-test' in sys.argv[1:]:   # before anything else, and whatever else is on the command line: an argument
        return self_test()              # argparse refused would exit with nothing said where a packaged app has no console
    a = ap.parse_args()
    if sys.platform.startswith('linux'):
        import shell_linux
        if not shell_linux.claim(str(app_folders()[1])):     # already open: that window comes to the front instead
            return 0
    note = None
    given = a.data or os.environ.get('LASTBOOK_DATA')    # a folder named outright is opened as it is: only its own staged switch is made
    from engine.setup import api as setup_api
    lib, note = setup_api.startup(app_folders()[0], only=Path(given) if given else None)   # before anything is open
    if lib and not given:
        remember(lib)
    data = data_folder(a.data)
    if data is None:
        if a.ask:
            data = ask_for_library()
            if data is None:
                return 0
        else:
            return run_setup()
    data = data.resolve()
    if not (data / CATALOG).is_file():   # only a folder named by --data or LASTBOOK_DATA gets here unchecked
        show_error(f'Lastbook could not find its library.\n\nIt looked in:\n{data}\n\nThat folder must hold {CATALOG}.')
        return 2
    os.environ['LASTBOOK_DATA'] = str(data)   # before the engine is imported: it reads this once
    os.environ.setdefault('LASTBOOK_LOCAL_AI', '1')   # the optional local AI (llm_local.py), used when its model file is found
    open_log(data)
    print(f'{time.strftime("%Y-%m-%d %H:%M:%S")} start pid={os.getpid()} args={sys.argv[1:]} data={data}', flush=True)
    if sys.platform == 'win32':
        import ctypes
        ctypes.windll.kernel32.SetErrorMode(0x0003)     # SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX: a crash here goes to nobody, and processes started from here inherit that
        import shell_windows
        problem = shell_windows.preflight()
        if problem:
            show_error(problem)
            return 3
    import server
    server.init()
    if not given or note:
        setup_api.opened(app_folders()[0], data, note)
    setup_api.configure(mode='manage', current=data, **setup_options())
    import assistant
    setup_api.follow_model_server(assistant.use_server)   # a model server chosen in Setup (#78)
    import bridge as B
    if sys.platform == 'darwin':
        import shell_macos
        shell_macos.run(B.Bridge(server, 'stream', B.ORIGIN_MAC, language_file=language_file()))
    elif sys.platform == 'win32':
        import shell_windows
        return shell_windows.run(server, data, language_file=language_file())
    elif sys.platform.startswith('linux'):
        import shell_linux
        shell_linux.run(B.Bridge(server, 'stream', B.ORIGIN_MAC, language_file=language_file()), linux_dirs())
    else:
        show_error('The Lastbook desktop app runs on Windows and macOS. Everywhere else, use the server version: python server.py')
        return 2
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except SystemExit as e:
        if isinstance(e.code, str):   # the engine refusing a setting: a packaged app has no console to say so on
            show_error(e.code)
            sys.exit(1)
        raise
    except BaseException as e:
        traceback.print_exc()
        show_error(f'Lastbook could not start: {type(e).__name__}: {e}')
        sys.exit(1)
