"""Validate desktop translations and generate the two flat web assets."""
import argparse
import json
import re
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'translations' / 'desktop'
WEB = ROOT / 'web'
APP = ROOT / 'app'
NATIVE = APP / 'i18n_native.json'
INSTALLER = ROOT / 'packaging' / 'i18n_installer.json'
DESKTOP = ROOT / 'packaging' / 'linux' / 'lastbook.desktop'
STUB_HEADER = ROOT / 'packaging' / 'setup_stub' / 'i18n_messages.h'
MACOS_LOCALES = ROOT / 'packaging' / 'macos_locales'
INSTALLER_PREFIXES = ('installer.',)
DESKTOP_FIELDS = (
    ('desktop.genericName', 'GenericName'),
    ('desktop.comment', 'Comment'),
    ('desktop.keywords', 'Keywords'),
)
DESKTOP_LOCALE_NAMES = {'de': 'de', 'es-419': 'es_419', 'zh-Hans': 'zh_Hans'}
DESKTOP_LOCALE_ALIASES = {'es-419': ('es',), 'zh-Hans': ('zh_CN', 'zh_SG', 'zh')}
STUB_MESSAGE_KEYS = (
    'installer.setupTitle',
    'installer.stub.selfMissing', 'installer.stub.selfUnreadable',
    'installer.stub.damaged', 'installer.stub.tempMissing',
    'installer.stub.tempCreate', 'installer.stub.tempWrite',
    'installer.stub.unpackFailed', 'installer.stub.startFailed',
)
STUB_MESSAGE_NAMES = (
    'STUB_SETUP_TITLE', 'STUB_SELF_MISSING', 'STUB_SELF_UNREADABLE',
    'STUB_DAMAGED', 'STUB_TEMP_MISSING', 'STUB_TEMP_CREATE',
    'STUB_TEMP_WRITE', 'STUB_UNPACK_FAILED', 'STUB_START_FAILED',
)
MACOS_PERMISSION_KEYS = {
    'NSDesktopFolderUsageDescription': 'native.macosPermission.desktop',
    'NSDocumentsFolderUsageDescription': 'native.macosPermission.documents',
    'NSDownloadsFolderUsageDescription': 'native.macosPermission.downloads',
}
REQUIRED = {'en', 'es-419'}
COMPLETE = {'es-419'}
SCRIPTS = ('i18n-core.js', 'i18n-dom.js', 'i18n-en.js', 'i18n-locales.js', 'i18n-app.js')
ENTRIES = {'index.html': 'app.js', 'setup.html': 'setup.js'}
RUNTIME = (*SCRIPTS, *ENTRIES, *ENTRIES.values(), 'plat.js', 'speak.js', 'app.css', 'setup.css', 'sw.js')
LOCALE = re.compile(r'[a-z]{2,3}(?:-[A-Z][a-z]{3})?(?:-(?:[A-Z]{2}|[0-9]{3}))?')
KEY = re.compile(r'[A-Za-z][A-Za-z0-9_-]*(?:\.[A-Za-z0-9_-]+)*')
PLACEHOLDER = re.compile(r'\{([A-Za-z_][A-Za-z0-9_]*)\}')
PLURAL = re.compile(r'zero|one|two|few|many|other|=(?:0|[1-9][0-9]*)')
# Match the JavaScript catalogue validator's String.prototype.trim().
BLANK = re.compile(r'[\u0009-\u000d\u0020\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000\ufeff]*')


class LocalScripts(HTMLParser):
    """Collect the classic, immediately executed local script references."""

    def __init__(self):
        super().__init__()
        self.names = []

    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            attrs = dict(attrs)
            src = attrs.get('src') or ''
            if src.startswith('/ui/') and attrs.keys().isdisjoint(('async', 'defer', 'nomodule', 'type')):
                self.names.append(re.split(r'[?#]', src[4:], maxsplit=1)[0])


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate key {key!r}')
        result[key] = value
    return result


def placeholders(text):
    if not isinstance(text, str) or BLANK.fullmatch(text) or re.search(r'[{}]', PLACEHOLDER.sub('', text)):
        raise ValueError('expected nonempty text with named placeholders')
    text.encode('utf-8')  # reject unpaired surrogates, including those written as JSON escapes
    return set(PLACEHOLDER.findall(text))


def contract(value):
    if isinstance(value, str):
        return ('text', placeholders(value))
    if not isinstance(value, dict) or 'other' not in value:
        raise ValueError("expected text or plural forms with an 'other' form")
    names = placeholders(value['other']) - {'count'}
    exact = set()
    for form, text in value.items():
        if not PLURAL.fullmatch(form):
            raise ValueError(f'invalid plural form {form!r}')
        if form.startswith('='):
            if len(form) > 17 or int(form[1:]) > 9007199254740991:
                raise ValueError(f'unsafe exact plural form {form!r}')
            exact.add(form)
        if placeholders(text) - {'count'} != names:
            raise ValueError(f'inconsistent placeholders in plural form {form!r}')
    return ('plural', names, exact)


def read_catalog(path):
    messages = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=unique_object)
    if not isinstance(messages, dict) or not messages:
        raise ValueError('expected a nonempty object of messages')
    schema = {}
    for key, value in messages.items():
        if not KEY.fullmatch(key):
            raise ValueError(f'invalid message key {key!r}')
        try:
            schema[key] = contract(value)
        except ValueError as error:
            raise ValueError(f'{key}: {error}') from error
    return messages, schema


def script(name, data):
    # The JavaScript is fixed. Quoted JSON parsed as data preserves keys and
    # avoids the special meaning of __proto__ in JavaScript object literals.
    json_data = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    literal = json.dumps(json_data, ensure_ascii=False).replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    return (f'/* Generated by packaging/i18n_catalogs.py from translations/desktop. */\n'
            f'globalThis.{name} = JSON.parse({literal});\n').encode('utf-8')


def desktop_entry(english, locales):
    if not {key for key, _field in DESKTOP_FIELDS}.issubset(english):
        return b''
    lines = ['[Desktop Entry]', 'Type=Application', 'Name=Lastbook']
    for key, field in DESKTOP_FIELDS:
        lines.append(f'{field}={english[key]}')
        for locale, suffix in DESKTOP_LOCALE_NAMES.items():
            value = locales.get(locale, {}).get(key)
            if value:
                lines.append(f'{field}[{suffix}]={value}')
        for locale, aliases in DESKTOP_LOCALE_ALIASES.items():
            value = locales.get(locale, {}).get(key)
            if value:
                lines.extend(f'{field}[{alias}]={value}' for alias in aliases)
    lines.extend([
        'Exec=/usr/bin/lastbook', 'Icon=lastbook', 'Terminal=false',
        'Categories=Education;Literature;',
        'StartupNotify=true', 'StartupWMClass=Lastbook', '',
    ])
    return ('\n'.join(lines)).encode('utf-8')


def c_wide_literal(value):
    escaped = []
    for char in value:
        code = ord(char)
        if char == '\\': escaped.append('\\\\')
        elif char == '"': escaped.append('\\"')
        elif char == '\n': escaped.append('\\n')
        elif char == '\r': escaped.append('\\r')
        elif char == '\t': escaped.append('\\t')
        elif code < 0x20 or code > 0x7e: escaped.append(f'\\u{code:04x}' if code <= 0xffff else f'\\U{code:08x}')
        else: escaped.append(char)
    return 'L"' + ''.join(escaped) + '"'


def stub_header(english, locales):
    if not set(STUB_MESSAGE_KEYS).issubset(english):
        return b''
    locale_names = {'en': 'STUB_LOCALE_EN', **{
        locale: 'STUB_LOCALE_' + locale.upper().replace('-', '_') for locale in locales
    }}
    all_locales = ['en', *sorted(locales)]
    enum_locales = ',\n'.join(f'    {locale_names[locale]}' for locale in all_locales)
    enum_messages = ',\n'.join(f'    {name}' for name in STUB_MESSAGE_NAMES)
    rows = []
    for locale in all_locales:
        catalog = english if locale == 'en' else locales[locale]
        values = [catalog.get(key, english[key]) for key in STUB_MESSAGE_KEYS]
        rows.append('    {' + ', '.join(c_wide_literal(value) for value in values) + '}')
    return (
        '/* Generated by packaging/i18n_catalogs.py; edit translations/desktop instead. */\n'
        '#ifndef LASTBOOK_SETUP_I18N_MESSAGES_H\n#define LASTBOOK_SETUP_I18N_MESSAGES_H\n'
        'enum StubLocale {\n' + enum_locales + '\n};\n'
        'enum StubMessage {\n' + enum_messages + ',\n    STUB_MESSAGE_COUNT\n};\n'
        'static const wchar_t *const STUB_MESSAGES[][STUB_MESSAGE_COUNT] = {\n'
        + ',\n'.join(rows) + '\n};\n'
        'static const wchar_t *stub_message(unsigned locale, unsigned message) {\n'
        '    if (locale >= sizeof(STUB_MESSAGES) / sizeof(STUB_MESSAGES[0])) locale = STUB_LOCALE_EN;\n'
        '    if (message >= STUB_MESSAGE_COUNT) message = STUB_SETUP_TITLE;\n'
        '    return STUB_MESSAGES[locale][message];\n}\n'
        '#endif\n'
    ).encode('ascii')


def openstep_string(value):
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n') + '"'


def macos_info_plist_strings(catalogs):
    if not set(MACOS_PERMISSION_KEYS.values()).issubset(catalogs['en']):
        return {}
    resources = {}
    for locale, catalog in [('en', catalogs['en']), *sorted(catalogs.items())]:
        suffix = locale
        entries = [f'{openstep_string(key)} = {openstep_string(catalog.get(message, catalogs["en"][message]))};'
                   for key, message in MACOS_PERMISSION_KEYS.items()]
        resources[f'{suffix}.lproj/InfoPlist.strings'] = ('\n'.join(entries) + '\n').encode('utf-8')
    return resources


def generate(source=SOURCE):
    paths = {p.stem: p for p in sorted(source.glob('*.json'))}
    missing = REQUIRED - paths.keys()
    if missing:
        raise ValueError(f'{source}: missing catalogues: {", ".join(sorted(missing))}')
    catalogs = {}
    for locale in ['en', *sorted(paths.keys() - {'en'})]:
        path = paths[locale]
        try:
            if not LOCALE.fullmatch(locale):
                raise ValueError(f'invalid catalogue locale {locale!r}')
            catalogs[locale], schema = read_catalog(path)
            if locale == 'en':
                reference = schema
            else:
                for key, entry in schema.items():
                    if key not in reference:
                        raise ValueError(f'unknown message key {key!r}')
                    if entry != reference[key]:
                        raise ValueError(f'incompatible message {key!r}')
                if locale in COMPLETE:
                    missing = sorted(reference.keys() - schema.keys())
                    if missing:
                        sample = ', '.join(repr(key) for key in missing[:10])
                        more = f' (and {len(missing) - 10} more)' if len(missing) > 10 else ''
                        raise ValueError(f'missing required translations: {sample}{more}')
        except (OSError, ValueError) as error:
            raise ValueError(f'{path}: {error}') from error
    english = catalogs.pop('en')
    native = json.dumps({'en': english, 'locales': catalogs}, ensure_ascii=False, indent=2, sort_keys=True).encode('utf-8') + b'\n'
    installer = {
        'en': {k: v for k, v in english.items() if k.startswith(INSTALLER_PREFIXES)},
        'locales': {loc: {k: v for k, v in cat.items() if k.startswith(INSTALLER_PREFIXES)} for loc, cat in catalogs.items()},
    }
    installer_bytes = json.dumps(installer, ensure_ascii=False, indent=2, sort_keys=True).encode('utf-8') + b'\n'
    generated = {
        'i18n-en.js': script('lastbookI18nEnglish', english),
        'i18n-locales.js': script('lastbookI18nLocales', catalogs),
        'native': native,
        'installer': installer_bytes,
        'desktop': desktop_entry(english, catalogs),
        'stub_header': stub_header(english, catalogs),
    }
    generated.update({'macos/' + name: contents for name, contents in macos_info_plist_strings({'en': english, **catalogs}).items()})
    return generated


def check_assets(web, generated):
    for name in RUNTIME:
        if not (web / name).is_file():
            raise ValueError(f'{web / name}: required localization asset missing')
    for name, expected in generated.items():
        if name in ('native', 'installer'):
            continue
        if name == 'desktop':
            path = DESKTOP
        elif name == 'stub_header':
            path = STUB_HEADER
        elif name.startswith('macos/'):
            path = MACOS_LOCALES / name.removeprefix('macos/')
        else:
            path = web / name
        if not path.is_file() or path.read_bytes() != expected:
            raise ValueError(f'{path}: stale catalogue. Run python3 packaging/i18n_catalogs.py')
    if web.resolve() == WEB.resolve():
        if not NATIVE.is_file() or NATIVE.read_bytes() != generated['native']:
            raise ValueError(f'{NATIVE}: stale catalogue. Run python3 packaging/i18n_catalogs.py')
        if not INSTALLER.is_file() or INSTALLER.read_bytes() != generated['installer']:
            raise ValueError(f'{INSTALLER}: stale catalogue. Run python3 packaging/i18n_catalogs.py')
    for page, controller in ENTRIES.items():
        scripts = LocalScripts()
        scripts.feed((web / page).read_text(encoding='utf-8'))
        scripts.close()
        expected = [*SCRIPTS, controller]
        if scripts.names[-len(expected):] != expected:
            raise ValueError(f'{web / page}: missing or misordered localization scripts')
    if web.resolve() != WEB.resolve():
        for name in RUNTIME:
            if name not in generated and (web / name).read_text(encoding='utf-8') != (WEB / name).read_text(encoding='utf-8'):
                raise ValueError(f'{web / name}: packaged web asset differs from source')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='check assets without writing')
    parser.add_argument('--web-dir', type=Path, help='check a staged or packaged web directory')
    args = parser.parse_args()
    if args.web_dir and not args.check:
        parser.error('--web-dir requires --check')
    try:
        generated = generate()
        if args.check:
            check_assets(args.web_dir or WEB, generated)
        else:
            for name, contents in generated.items():
                if name == 'native':
                    NATIVE.write_bytes(contents)
                elif name == 'installer':
                    INSTALLER.write_bytes(contents)
                elif name == 'desktop':
                    DESKTOP.write_bytes(contents)
                elif name == 'stub_header':
                    STUB_HEADER.write_bytes(contents)
                elif name.startswith('macos/'):
                    path = MACOS_LOCALES / name.removeprefix('macos/')
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(contents)
                else:
                    (WEB / name).write_bytes(contents)
    except (OSError, ValueError) as error:
        parser.exit(1, f'Localization: {error}\n')


if __name__ == '__main__':
    main()
