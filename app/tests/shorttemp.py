"""Temporary folders short enough for the setup's own Windows path rule.

The setup refuses a library whose longest file would not fit in an ordinary Windows path: a
LastbookData path may be at most api.WINDOWS_MAX_PATH - 1 - api.LONGEST_INSIDE characters, which is
68. %TEMP% is usually C:\\Users\\<name>\\AppData\\Local\\Temp, so on Windows it is often already too
deep, and the setup and data-folder tests would then fail on that rule instead of on what they
test. One short folder is made for the whole run, on the system drive when %TEMP% is too deep --
the place app/main.py falls back to for the library itself -- and every test's own folder goes
inside it. Each candidate is checked with the setup's own path_too_deep after it is made, so the
answer is about the folder that really exists. If none is short enough the tests skip and say which
places were tried, rather than failing in a way that reads like a bug in the app.

Never packaged."""
import atexit, os, shutil, sys, tempfile, time, unittest
from pathlib import Path

from engine.setup import api

ROOT = None
# The deepest thing the two callers build before the setup is asked: a per-test folder (tempfile adds eight
# characters to the prefix), then test_data_folder's Windows layout. test_setup's own is 'place', which is shorter.
PROBE = 'lastbook-lookup-' + 'x' * 8 + '/Local/Lastbook'


def _too_deep(folder):
    return os.name == 'nt' and api.path_too_deep(folder / PROBE / api.DATA_NAME)   # the setup's own rule, not a copy of it


def _clean(folder):
    """Removed at exit, with a few tries: Windows will not remove a file another handle still has open."""
    for _ in range(5):
        try:
            shutil.rmtree(folder)
            return
        except OSError:
            time.sleep(0.2)
    print(f'shorttemp: could not remove {folder}', file=sys.stderr)


def _root():
    """One short folder for the whole run, from %TEMP% or the system drive, made once and removed at exit."""
    global ROOT
    if ROOT is not None:
        return ROOT
    tried = []
    for base in (Path(tempfile.gettempdir()), Path((os.environ.get('SystemDrive') or 'C:') + '\\')):
        try:
            made = Path(tempfile.mkdtemp(prefix='lb-', dir=base)).resolve()
        except OSError as e:
            tried.append(f'{base} ({type(e).__name__})')
            continue
        if _too_deep(made):
            tried.append(f'{base} (too deep for the setup\'s limit of {api.WINDOWS_MAX_PATH - 1 - api.LONGEST_INSIDE} characters)')
            _clean(made)
            continue
        atexit.register(_clean, made)
        ROOT = made
        return ROOT
    raise unittest.SkipTest('no folder short enough for the setup\'s Windows path rule: tried ' + ', '.join(tried))


def mkdtemp(prefix):
    """A temporary folder inside the run's short root."""
    return Path(tempfile.mkdtemp(prefix=prefix, dir=_root())).resolve()
