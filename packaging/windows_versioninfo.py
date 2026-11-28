"""Write Windows VERSIONINFO for the app, Setup and uninstaller builds.

PyInstaller --version-file and llvm-windres already consume these formats on
the Windows build machine; this script only authors the text. es-419 has no
Windows LCID, so 0x080A (Spanish-Mexico, StringTable 080A04B0) stands in for
it, and 0x0C0A (Spanish-Spain, 0C0A04B0) carries the same Latin American
wording so a computer whose UI is es-ES still shows Spanish. German uses
0x0407 (Germany); Simplified Chinese uses 0x0804 (China) and 0x1004
(Singapore), with the same catalogue wording for both regions.

Usage (run from the Windows build scripts):

  python3 -I -B packaging/windows_versioninfo.py --format pyinstaller --kind app \\
      --version 1.1.15 --stamp 20261121-010203 --out version.txt
  python3 -I -B packaging/windows_versioninfo.py --format rc --kind setup \\
      --version 1.1.15 --stamp 20261121-010203 --out stub.rc
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'translations' / 'desktop'

# (StringTable key, LANGID, catalogue locale). 1200 is Unicode.
TABLES = (
    ('040904B0', 1033, 'en'),
    ('080A04B0', 2058, 'es-419'),
    ('0C0A04B0', 3082, 'es-419'),
    ('040704B0', 1031, 'de'),
    ('080404B0', 2052, 'zh-Hans'),
    ('100404B0', 4100, 'zh-Hans'),
)

KIND_DESCRIPTION = {
    'app': 'native.appFileDescription',
    'setup': 'installer.fileDescription',
    'uninstall': 'installer.uninstallFileDescription',
}


def load_catalogs(source=SOURCE):
    english = json.loads((source / 'en.json').read_text(encoding='utf-8'))
    locales = {
        locale: json.loads((source / f'{locale}.json').read_text(encoding='utf-8'))
        for locale in ('es-419', 'de', 'zh-Hans')
    }
    return english, locales


def message(english, locales, locale, key, params=None):
    table = english if locale == 'en' else locales.get(locale, {})
    text = table.get(key, english[key])
    if params:
        for name, value in params.items():
            text = text.replace('{' + name + '}', str(value))
    return text


def strings_for(kind, version, stamp, english, locales, locale):
    params = {'stamp': stamp} if stamp else None
    fields = [
        ('CompanyName', message(english, locales, locale, 'installer.companyName')),
        ('FileDescription', message(english, locales, locale, KIND_DESCRIPTION[kind])),
        ('FileVersion', version),
        ('ProductName', message(english, locales, locale, 'installer.productName')),
        ('ProductVersion', version),
    ]
    if stamp:
        fields.append(('Comments', message(english, locales, locale, 'installer.comments', params)))
    return fields


def _py_str(value):
    return "'" + value.replace('\\', '\\\\').replace("'", "\\'") + "'"


def render_pyinstaller(kind, version, stamp, english, locales):
    tables = []
    for table_id, _lang, locale in TABLES:
        fields = strings_for(kind, version, stamp, english, locales, locale)
        items = ', '.join(
            f"StringStruct({_py_str(name)}, {_py_str(value)})" for name, value in fields
        )
        tables.append(f"StringTable('{table_id}', [{items}])")
    translations = ', '.join(f'{lang}, 1200' for _table, lang, _loc in TABLES)
    filevers = version.replace('.', ', ') + ', 0'
    return (
        f"VSVersionInfo(ffi=FixedFileInfo(filevers=({filevers}), prodvers=({filevers})),\n"
        f"  kids=[StringFileInfo([{', '.join(tables)}]),\n"
        f"    VarFileInfo([VarStruct('Translation', [{translations}])])])\n"
    )


def _rc_str(value):
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


def render_rc(kind, version, stamp, english, locales, include_icon=True):
    # UTF-8 with code page 65001 so llvm-windres accepts accented FileDescription.
    dotted = version.replace('.', ',') + ',0'
    blocks = []
    for table_id, _lang, locale in TABLES:
        fields = strings_for(kind, version, stamp, english, locales, locale)
        values = '\n'.join(f'      VALUE "{name}", {_rc_str(value)}' for name, value in fields)
        blocks.append(f'    BLOCK "{table_id}"\n    BEGIN\n{values}\n    END')
    translations = ', '.join(f'0x{lang:X}, 1200' for _table, lang, _loc in TABLES)
    icon = '1 ICON "Lastbook.ico"\n' if include_icon else ''
    body = '\n'.join(blocks)
    return (
        f'#pragma code_page(65001)\n'
        f'{icon}1 VERSIONINFO\n'
        f'FILEVERSION {dotted}\n'
        f'PRODUCTVERSION {dotted}\n'
        f'BEGIN\n'
        f'  BLOCK "StringFileInfo"\n'
        f'  BEGIN\n'
        f'{body}\n'
        f'  END\n'
        f'  BLOCK "VarFileInfo"\n'
        f'  BEGIN\n'
        f'    VALUE "Translation", {translations}\n'
        f'  END\n'
        f'END\n'
    )


def write(path, text):
    Path(path).write_text(text, encoding='utf-8')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--format', choices=('pyinstaller', 'rc'), required=True)
    parser.add_argument('--kind', choices=KIND_DESCRIPTION, required=True)
    parser.add_argument('--version', required=True)
    parser.add_argument('--stamp', default='')
    parser.add_argument('--out', required=True)
    parser.add_argument('--source', type=Path, default=SOURCE)
    args = parser.parse_args(argv)
    english, locales = load_catalogs(args.source)
    if args.format == 'pyinstaller':
        text = render_pyinstaller(args.kind, args.version, args.stamp, english, locales)
    else:
        text = render_rc(args.kind, args.version, args.stamp, english, locales)
    write(args.out, text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
