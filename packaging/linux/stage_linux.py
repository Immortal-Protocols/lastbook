#!/usr/bin/env python3
"""The app folder every Linux package ships: /opt/lastbook in the .deb (build_app_linux.sh), /app/lastbook in the Flatpak
(flatpak/org.lastbook.Lastbook.yml). One list of program files for both, so a module the app starts importing reaches every
package or none: app/tests/test_stage_linux.py follows the app's imports and fails when one is missing here.

  python3 -I -B packaging/linux/stage_linux.py --source . --ship SHIP --vendor VENDOR --plugin libgstlastbooksrc.so --opt OPT
                                               [--version 1.1.16] [--llm derived/llm/bin-linux]

Inputs are prepared by the caller, as each package makes them its own way: SHIP holds web/, content/ and setup/manifest-v1.json
(ship_app_files.py and release_manifest.py), VENDOR the wheels installed for the package's Python (requirements_linux.txt),
and the plugin is lastbooksrc compiled for its GStreamer. The checkout is read by the names below only, never copied whole.
What sits around the app folder (launcher, menu entry, icons, compiled bytecode, the package itself) stays with each package.
"""
import argparse
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Our own program files: what the app imports on Linux (lastbook.py starts app/main.py with shell_linux), and nothing else.
PROGRAM_FILES = (
    'app/main.py', 'app/bridge.py', 'app/shell_linux.py', 'app/ui_language.py', 'app/contribute.py',
    'server.py', 'retrieval.py', 'assistant.py', 'llm_local.py',
    'engine/__init__.py', 'engine/paths.py', 'engine/library.py', 'engine/safe_paths.py', 'engine/encyclopedias.py',
    'engine/saved_pages.py', 'engine/address_search.py', 'engine/page_tables.py', 'engine/update.py', 'engine/notes.py',
    'engine/model_server.py',
    'engine/setup/__init__.py', 'engine/setup/api.py', 'engine/setup/download.py', 'engine/setup/hardware.py',
    'engine/setup/install.py', 'engine/setup/manifest.py', 'engine/setup/roots.pem',
)
LAUNCHER = 'packaging/linux/lastbook.py'   # lays the folder out as a PyInstaller build is, then starts app/main.py


def default_version():
    """The Linux version, where the .deb build keeps it: APP_VERSION in build_app_linux.sh."""
    text = (ROOT / 'packaging/linux/build_app_linux.sh').read_text(encoding='utf-8')
    found = re.search(r'^APP_VERSION="\$\{LASTBOOK_VERSION:-([^}"]+)\}"', text, re.M)
    if not found:
        raise ValueError('no APP_VERSION="${LASTBOOK_VERSION:-...}" line in build_app_linux.sh: give --version')
    return found.group(1)


def vendor_kept(rel):
    """What the packages keep of the installed wheels: no tests, no command-line tools, no numpy.f2py."""
    return not (rel.parts[0] in ('bin', 'pypdfium2_cli') or rel.parts[:2] in (('numpy', 'f2py'), ('numpy', 'testing'))
                or any(p in ('tests', 'testing', '__pycache__') for p in rel.parts[:-1]) or '_tests' in rel.name)


def runner_files(llm):
    """The local AI runner and what it loads, when there is one: lastbook-llm, its llama.cpp libraries, and their licences."""
    names = [llm / 'lastbook-llm'] + sorted(p for pattern in ('*.so*', 'LICENSE*', 'NOTICE*') for p in llm.glob(pattern))
    return [p for p in dict.fromkeys(names) if p.is_file()]


def stage(source, ship, vendor, plugin, opt, version, llm=None):
    source, ship, vendor, plugin, opt = (Path(p).resolve() for p in (source, ship, vendor, plugin, opt))
    if not re.fullmatch(r'[0-9A-Za-z][0-9A-Za-z.+~_-]*', version):
        raise ValueError(f'not a version: {version!r}')
    needed = [source / r for r in (*PROGRAM_FILES, LAUNCHER)] + [ship / 'web/index.html', ship / 'content', ship / 'setup/manifest-v1.json', plugin]
    missing = [str(p) for p in needed if not p.exists()]
    if missing:
        raise ValueError('missing: ' + ', '.join(missing))
    if llm and not (Path(llm) / 'lastbook-llm').is_file():
        raise ValueError(f'no lastbook-llm in {llm}')
    if opt.exists() and any(opt.iterdir()):
        raise ValueError(f'{opt} is not empty')

    def put(src, rel):
        dest = opt / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)

    for rel in PROGRAM_FILES:
        put(source / rel, rel)
    put(source / LAUNCHER, 'lastbook.py')
    for tree in ('web', 'content'):
        for f in sorted((ship / tree).rglob('*')):
            if f.is_file():
                put(f, Path(tree) / f.relative_to(ship / tree))
    put(ship / 'setup/manifest-v1.json', 'setup/manifest-v1.json')
    for f in sorted(vendor.rglob('*')):
        rel = f.relative_to(vendor)
        if f.is_file() and vendor_kept(rel):
            put(f, Path('lib') / rel)
    for f in runner_files(Path(llm).resolve()) if llm else ():
        put(f, Path('llm') / f.name)
    put(plugin, 'gst/libgstlastbooksrc.so')
    (opt / 'VERSION').write_text(version + '\n', encoding='utf-8')


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    for name in ('source', 'ship', 'vendor', 'plugin', 'opt'):
        ap.add_argument('--' + name, type=Path, required=True)
    ap.add_argument('--version', help="default: build_app_linux.sh's APP_VERSION")
    ap.add_argument('--llm', type=Path, help='a folder holding lastbook-llm (packaging/llm/build_llm_linux.sh)')
    a = ap.parse_args()
    stage(a.source, a.ship, a.vendor, a.plugin, a.opt, a.version or default_version(), a.llm)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError) as e:
        sys.exit(f'stage_linux: {e}')
