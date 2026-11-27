"""Inventory hard-coded user-visible strings and classify them.

Surfaces: the desktop web UI, Setup/engine API messages shown in the UI,
native shells (menus and dialogs), the Windows installer, and the Linux
.desktop file. Classes:

  wired     -- already a catalogue fallback (tr(), data-i18n, or native_t())
  chrome    -- user-visible UI that still needs a catalogue key
  content   -- library/data (titles, USDA crop names, pack names, brand)
  technical -- proven not shown to a person: identifiers, logs, headers, SVG,
               docstrings, CSS, paths (narrow shape or call-site rules only)
  unknown   -- anything else; default-deny treats it like chrome

Default-deny: a literal is only accepted when it is proven wired, proven
technical, or listed with a reason in packaging/i18n_allowlist.json (exact
file + exact string). Chrome, content and unknown are "unapproved" otherwise.

Run:  python3 -B packaging/i18n_scan.py          (report)
      python3 -B packaging/i18n_scan.py --check  (exit 1 on unapproved strings)
"""
from __future__ import annotations

import json
import io
import functools
import re
import sys
import tokenize
import ast
from html.parser import HTMLParser
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / 'web'
EN = ROOT / 'translations' / 'desktop' / 'en.json'

WEB_FILES = [
    'index.html', 'setup.html', 'app.js', 'setup.js', 'chat.js', 'map.js',
    'update.js', 'terrain3d.js', 'video-moments.js', 'speak.js', 'i18n-app.js',
]
# Runtime helpers with no interface copy: layout toggles, search-word folding,
# the service worker, i18n engine/DOM adapter and generated catalogue data.
WEB_NON_UI_FILES = {
    'plat.js', 'words.js', 'sw.js', 'i18n-core.js', 'i18n-dom.js',
    'i18n-en.js', 'i18n-locales.js',
}

PYTHON_SURFACES = {
    'engine/model-server': [ROOT / 'engine' / 'model_server.py'],
    'engine/setup': [
        ROOT / 'engine' / 'setup' / 'api.py',
        ROOT / 'engine' / 'setup' / 'download.py',
        ROOT / 'engine' / 'setup' / 'hardware.py',
        ROOT / 'engine' / 'setup' / 'install.py',
    ],
    'engine/update': [ROOT / 'engine' / 'update.py'],
    'app/main': [ROOT / 'app' / 'main.py'],
    'app/bridge': [ROOT / 'app' / 'bridge.py'],
    'native/macos': [ROOT / 'app' / 'shell_macos.py'],
    'native/macos-updater': [ROOT / 'app' / 'update_macos.py'],
    'app/contribute': [ROOT / 'app' / 'contribute.py'],
    'native/windows': [ROOT / 'app' / 'shell_windows.py'],
    'native/linux': [ROOT / 'app' / 'shell_linux.py'],
    'installer': [ROOT / 'packaging' / 'lastbook_setup.py'],
    'desktop': [ROOT / 'packaging' / 'linux' / 'lastbook.desktop'],
    'native/macos-bundle': [ROOT / 'packaging' / 'lastbook_macos.spec'],
    'assistant': [ROOT / 'assistant.py'],
    'server': [ROOT / 'server.py'],
}
DESKTOP_LOCALES = {'de', 'es_419', 'zh_Hans'}
DESKTOP_TRANSLATED_FIELDS = {'GenericName', 'Comment', 'Keywords'}

C_FILES = [ROOT / 'packaging' / 'setup_stub' / 'lastbook_setup_stub.c']
DESKTOP_LOCALES = {'de', 'es_419', 'zh_Hans'}
DESKTOP_TRANSLATED_FIELDS = {'GenericName', 'Comment', 'Keywords'}

CONTENT = {
    'Lastbook', 'LastbookData', 'Lastbook videos', 'Español (Latinoamérica)',
    ' · Lastbook',
    'English', 'Deutsch', '简体中文', 'US', '3D', 'CC', 'PDF', 'AI', 'ZIP', 'GB', 'SHA-256',
    'Almonds', 'Walnuts', 'Pecans', 'Pistachios', 'Cherries', 'Peaches',
    'Apples', 'Pears', 'Prunes', 'Nectarines', 'Plums', 'Apricots',
    'Pomegranates', 'Avocados', 'Olives', 'Citrus', 'Oranges', 'Grapes',
    'Blueberries', 'Cranberries', 'Caneberries', 'Asparagus',
    'Other tree crops', 'WHO', 'FEMA', 'CDC', 'EPA', 'USDA', 'NOAA',
    'UNICEF', 'MSF', 'Small', 'Medium', 'Large',
    'Where There Is No Doctor', 'National Center for Home Food Preservation',
    'Appropedia', 'Wikipedia', '© OpenStreetMap contributors · Microsoft buildings · USGS · USDA · NOAA · USACE · CDFW · CalGEM · Natural Earth',
}

TECHNICAL_EXACT = {
    'changed its ETag twice', 'ignores Range',
    'POST', 'GET', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'Content-Type',
    'Content-Range', 'ArrowDown', 'ArrowUp', 'ArrowLeft', 'ArrowRight',
    'Escape', 'Enter', 'AbortError', 'HEVC', 'START-HERE.txt',
    'LastbookData.setup', 'application/json', 'text/html',
    'T12:00:00', 'Polygon', 'use strict', 'ETag', 'If-None-Match',
    'Could not access the desktop language preference', 'Contents',
    'Unexpected desktop language preference', 'no byte range', 'no points', '?t=', '/v1/?$', 'SPUStandardUpdaterController', 'SystemRoot', 'NotFound', 'WindowsPowerShell',
    '(pointer: coarse)', 'Spanish|español|\\bkit de\\b',
    '#{…} [data-act="{…}"]',
}

TECHNICAL_PREFIX = (
    'M12 ', 'M9 ', 'M4 ', 'M3 ', 'M5 ', 'M6 ', 'M7 ', 'M8 ', 'M10 ', 'M14 ',
    'M15 ', 'M16 ', 'M18 ', 'M20 ', 'M13 ', 'http', 'https', 'function ',
    'const ', 'return ', 'typeof ', 'window.', 'document.', 'class ',
)

# Only real logging sinks. Exception messages (ValueError, RuntimeError, OSError)
# can be shown in a dialog or an installer error, so they are not exempt here.
LOG_CALLS = {'debug', 'info', 'log', 'print', 'warning', '_log', 'end_page'}

SVG_RE = re.compile(r'^M-?\d')
KEYISH = re.compile(r'^[A-Za-z][A-Za-z0-9_.-]{0,40}$')
STR_RE = re.compile(r"(?<!\\)(['\"])((?:(?!\1)[^\\\n]|\\.)*)\1")
TPL_RE = re.compile(r"`([^`$\\]|\\.)*`")
CSS_LIKE = re.compile(r'^[a-z][a-z0-9-]*(?: [a-z][a-z0-9-]*)*$')
TOKEN = re.compile(
    r'^(not found|btn plain|small muted|no_space|found_mismatch|checksum|'
    r'cancelled|paused|busy|not_done|not_library|unavailable|nothing|current|'
    r'fat|network|server|unpack|activate|copying|waiting|downloading|'
    r'verifying|installing)$',
    re.I,
)
DISPLAY_PRE = re.compile(
    r'innerHTML|outerHTML|textContent|innerText|document\.title|setTitle|Error\(|message\(|'
    r'setUiTitle|aria-label|placeholder|confirm\(|alert\(|toast\(|show_error|'
    r'MessageBox|MessageDialog|addButtonWithTitle_|setTitle_|setPrompt_|GenericName|'
    r'Comment=|Name=|\.Text\s*=|why\s*=|message\s*[:=]|[\'"]error[\'"]\s*:|Failed\(|_fail\(|live\.textContent|'
    r'set_tooltip|tooltip_text|add_buttons\(|initWithTitle_|ASK_TITLE|ASK\s*=|'
    r'TOO_BIG|STOPPED\s*=|APP_OPEN_TEXT|setWindowTitle|title\s*[:=]|menu\.append|view\.append|'
    r'helps\.append|_menu\(|statusLine\(|'
    # Native UI setters are calls, not assignments: panel.setPrompt_('Choose'),
    # alert.setMessageText_('…'), win.set_title('…'), Gtk.Label(label='…').
    r'set(?:Prompt|Message|MessageText|InformativeText|Title|Label|ToolTip|PlaceholderString|'
    r'PlaceholderText|NameFieldLabel|Subtitle|HeaderTitle|AttributedTitle|AlternateTitle)_\s*\(\s*$|'
    r'(?:add|insert)ItemWithTitle_[A-Za-z_]*\s*\(\s*$|'
    r'\bset_(?:title|label|text|markup|tooltip_text|tooltip|subtitle|placeholder_text|'
    r'markup_with_mnemonic|application_name|secondary_text)\s*\(\s*$|'
    r'\bnew_with_(?:label|mnemonic)\s*\(\s*$|'
    r'\b(?:label|text|title|tooltip_text|secondary_text|placeholder_text|markup|heading|subtitle)\s*=\s*$|'
    r'\bLabel\s*\(\s*$'
)


def load_english():
    data = json.loads(EN.read_text(encoding='utf-8'))
    vals = set()
    for v in data.values():
        if isinstance(v, dict):
            vals.update(str(x) for x in v.values())
        else:
            vals.add(v)
    return data, vals


@lru_cache(maxsize=1)
def _english_keys():
    return frozenset(load_english()[0])


@lru_cache(maxsize=1)
def _map_preset_keys():
    try:
        source = (WEB / 'map.js').read_text(encoding='utf-8')
    except OSError:
        return {}
    start = source.find('const PRESET_KEY = {')
    end = source.find('};', start)
    if start < 0 or end < 0:
        return {}
    block = source[start:end]
    return {(quoted or bare): key for quoted, bare, key in re.findall(
        r"(?:['\"]([^'\"]+)['\"]|([A-Za-z][A-Za-z0-9 ]*))\s*:\s*['\"](map\.preset\.[A-Za-z0-9_.-]+)['\"]", block
    )}


@lru_cache(maxsize=1)
def _map_data_catalogue_classes():
    """Resolve every hard-coded map label to the dynamic key its renderer uses."""
    try:
        source = (WEB / 'map.js').read_text(encoding='utf-8')
    except OSError:
        return {}
    keys = _english_keys()
    result = {}
    layers = re.search(r'\bconst\s+LAYERS\s*=\s*\[([\s\S]*?)\]\s*\.map\b', source)
    if layers:
        for match in re.finditer(r"\[\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]", layers.group(1)):
            ident, label, symbol = match.groups()
            result[label] = 'wired' if f'map.layer.{ident}' in keys else 'chrome'
            # These short values are map marker glyphs, not translated labels.
            result.setdefault(symbol, 'technical')
    groups = re.search(r'\bconst\s+GROUPS\s*=\s*\[([\s\S]*?)\]\s*;', source)
    if groups:
        for ident, label in re.findall(r"\[\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]", groups.group(1)):
            result[label] = 'wired' if f'map.group.{ident}' in keys else 'chrome'
    presets = re.search(r'\bconst\s+PRESETS\s*=\s*\[([\s\S]*?)\]\s*;', source)
    if presets:
        for label in re.findall(r"\[\s*['\"]([^'\"]+)['\"]\s*,\s*(?:\[|LAYERS\b)", presets.group(1)):
            key = _map_preset_keys().get(label)
            result[label] = 'wired' if key in keys else 'chrome'
    return result


@lru_cache(maxsize=1)
def _chat_starter_classes():
    """Map each rendered starter prompt to the catalogue key used by chat.js."""
    try:
        source = (WEB / 'chat.js').read_text(encoding='utf-8')
    except OSError:
        return {}
    block = re.search(r'\bconst\s+STARTERS\s*=\s*\[([\s\S]*?)\]\s*;', source)
    if not block:
        return {}
    keys = _english_keys()
    return {prompt: 'wired' if f'chat.starter.{ident}' in keys else 'chrome'
            for ident, prompt in re.findall(r"\[\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\]", block.group(1))}


def _mapped_map_label(s, pre):
    """Check dynamic map labels against the catalogue key used by their renderer."""
    status = _map_data_catalogue_classes().get(s)
    if status:
        return status
    status = _chat_starter_classes().get(s)
    if status and re.search(r'\bconst\s+STARTERS\s*=', pre[-1000:]):
        return status
    return None


def unescape(s, quote):
    if quote == "'":
        return s.replace(r"\'", "'").replace(r"\\", "\\")
    return s.replace(r'\"', '"').replace(r"\\", "\\")


def already_wired(pre: str) -> bool:
    # A completed translation call elsewhere in the same statement must not
    # hide a different literal, especially inside a nested template.
    tail = pre.rsplit(';', 1)[-1][-300:]
    if _inside_translation_call(pre):
        return True
    if _inside_named_call(pre, {'setUiTitle', 'labelPair', 'backButton'}):
        return True
    return False


_CONST_ASSIGN = re.compile(r'(?:^|[\n;])\s*(?:(?:const|let|var)\s+)?([A-Z][A-Z0-9_]{2,})\s*=\s*\(?\s*$')
_FALLBACK_CALLS = r'(?:native_t|installer_t|tr|trHtml|lastbookTr|_t)'


@lru_cache(maxsize=256)
def _source_text(source_file: str) -> str:
    try:
        return (ROOT / source_file).read_text(encoding='utf-8')
    except (OSError, ValueError):
        return ''


def _constant_is_catalogue_fallback(pre: str, source_file: str) -> bool:
    """An UPPER_CASE constant is wired only when every use of it in the file is the
    fallback argument of a translation call whose key is in the English catalogue.

    This replaces the old name list (ASK, TOO_BIG, …): a new constant with a
    hard-coded message and a direct display use is unapproved, whatever its name.
    """
    m = _CONST_ASSIGN.search(pre[-200:])
    if not m or not source_file:
        return False
    name = m.group(1)
    text = _source_text(source_file)
    if not text:
        return False
    keys = _english_keys()
    uses = [u for u in re.finditer(r'(?<![\w.$])' + name + r'(?![\w$])', text)]
    found = 0
    for u in uses:
        after = text[u.end():u.end() + 40]
        if re.match(r'\s*=(?!=)', after):
            continue  # the assignment itself
        before = text[max(0, u.start() - 200):u.start()]
        call = re.search(_FALLBACK_CALLS + r"\(\s*['\"]([A-Za-z0-9_.-]+)['\"]\s*,\s*(?:None\s*,\s*|null\s*,\s*)?$", before)
        if not call or call.group(1) not in keys:
            return False
        found += 1
    return found > 0


def _has_i18n_marker_in_tag(pre: str, post: str) -> bool:
    """Recognize a bound HTML attribute only when its marker shares the tag."""
    # `pre` ends before the current string literal and `post` starts there.
    # Anchor the tag boundary around that exact point; later nested tags must
    # not replace the current element's marker.
    before = pre[-4000:]
    after = post[:4000]
    start = before.rfind('<')
    end = after.find('>')
    tag = before[start:] + after[:end] if start >= 0 and end >= 0 else ''
    return bool(tag and re.search(r'\bdata-i18n(?:-[a-z-]+)?\s*=', tag))


_CALL_NAME_BEFORE = re.compile(r'([A-Za-z_$][\w$]*)\s*(?:\?\.)?\s*$')


def _inside_named_call(pre: str, names) -> bool:
    return _inside_named_call_cached(pre, frozenset(names))


@lru_cache(maxsize=65536)
def _inside_named_call_cached(pre: str, names) -> bool:
    """True when the current literal is nested in a call with one of these names."""
    stack = []
    n = len(pre)

    def code(i, stop_brace=False):
        braces = 0
        while i < n:
            if pre.startswith('//', i):
                end = pre.find('\n', i + 2)
                i = n if end < 0 else end + 1
                continue
            if pre.startswith('/*', i):
                end = pre.find('*/', i + 2)
                i = n if end < 0 else end + 2
                continue
            c = pre[i]
            if c in "'\"":
                i = _skip_string(pre, i)
                continue
            if c == '`':
                i = template(i)
                continue
            if c == '(':
                m = _CALL_NAME_BEFORE.search(pre, max(0, i - 120), i)
                stack.append(m.group(1) if m else '')
            elif c == ')' and stack:
                stack.pop()
            elif c == '{':
                braces += 1
            elif c == '}':
                if stop_brace and braces == 0:
                    return i + 1
                braces = max(0, braces - 1)
            i += 1
        return i

    def template(i):
        i += 1
        while i < n:
            if pre[i] == '\\':
                i += 2
            elif pre.startswith('${', i):
                i = code(i + 2, stop_brace=True)
            elif pre[i] == '`':
                return i + 1
            else:
                i += 1
        return i

    code(0)
    return any(name in names for name in stack)


def _inside_translation_call(pre: str) -> bool:
    """True when the string is an argument to an open translation call."""
    # A completed neighboring tr() cannot mark the next literal as translated.
    return _inside_named_call(pre, {'tr', 'trHtml', 'trLang', 'trResult', 'lastbookTr', 'native_t', 'installer_t', 'user_error', '_api_error', 't'})


def _inside_catalogued_fallback(pre: str, names) -> bool:
    """Recognize keyed helper fallbacks only when their English key exists."""
    keys = _english_keys()
    source = pre[-2000:]

    def remains_open(start):
        opening = source.find('(', start)
        if opening < 0:
            return False
        depth, i = 0, opening
        while i < len(source):
            c = source[i]
            if c in "'\"":
                i = _skip_string(source, i)
                continue
            if c == '`':
                i = _skip_template(source, i)
                continue
            if c == '(':
                depth += 1
            elif c == ')':
                depth -= 1
                if depth == 0:
                    return False
            i += 1
        return depth > 0

    for name in names:
        pattern = re.compile(r'\b' + re.escape(name) + r'\s*\(')
        for match in reversed(list(pattern.finditer(source))):
            if not remains_open(match.start()):
                continue
            args = source[match.end():]
            if name == 'setError':
                direct = (re.match(r"\s*[^,]+,\s*'([A-Za-z][A-Za-z0-9_.-]+)'\s*,", args) or
                          re.match(r'\s*[^,]+,\s*"([A-Za-z][A-Za-z0-9_.-]+)"\s*,', args))
            else:
                direct = (re.match(r"\s*'([A-Za-z][A-Za-z0-9_.-]+)'\s*,", args) or
                          re.match(r'\s*"([A-Za-z][A-Za-z0-9_.-]+)"\s*,', args))
            if direct and direct.group(1) in keys:
                return True
            if (name == 'tHtml' and re.match(r"\s*n\s*\?\s*PRESET_KEY\[n\][\s\S]*?:\s*['\"]map\.preset\.none['\"]\s*,", args)
                    and 'map.preset.none' in keys):
                return True
    return False


@lru_cache(maxsize=1)
def _english_values():
    english = load_english()[0]
    return {k: v for k, v in english.items()}


def _same_as_catalogue(key: str, text: str) -> bool:
    """True when text is exactly the English catalogue value of key.

    `{…}` in a flattened template literal stands for any interpolation, and a
    plural entry matches when one of its forms is the literal.
    """
    value = _english_values().get(key)
    forms = list(value.values()) if isinstance(value, dict) else [value]
    for form in forms:
        if not isinstance(form, str):
            continue
        if form == text:
            return True
        if '{…}' in text:
            pattern = '^' + re.escape(text).replace(re.escape('{…}'), r'(?:\{[^{}]+\}|.*?)') + '$'
            if re.match(pattern, form, re.S):
                return True
    return False


_KEY_LIT = r"""['"]([a-z][A-Za-z0-9_]*(?:\.[A-Za-z0-9_]+)+)['"]"""
_PAIR_RE = re.compile(_KEY_LIT + r"""\s*,\s*(?:(?:null|None|undefined|\{[^{}]*\}|[A-Za-z_$][\w$.]*(?:\([^()]*\))?)\s*,\s*)?"""
                      r"""(?:['"]?(?:message|error|why|text|fallback|label|title|status)['"]?\s*[:=]\s*)?$""")


def _keyed_pair(s: str, pre: str) -> bool:
    """`'catalogue.key', [params,] 'English'`: the literal is the fallback of the key
    right before it (a helper call, a tuple or an array row), and it is exactly
    the catalogue's English text. Only the immediately preceding tokens count."""
    m = _PAIR_RE.search(pre[-400:])
    return bool(m and _same_as_catalogue(m.group(1), s.strip() if s.strip() else s))


def _label_to_key(s: str, post: str) -> bool:
    """`{'English': 'catalogue.key'}`: a label-to-key map whose English text is the key's value."""
    m = re.match(r"""['"]\s*:\s*""" + _KEY_LIT, post[post.find(s) + len(s):][:200] if s in post[:len(s) + 4] else '')
    return bool(m and _same_as_catalogue(m.group(1), s))


_DUP_FALLBACK_RE = re.compile(r"""(?:lastbookTr|tr|trHtml|native_t|installer_t)\s*(?:\?\.)?\s*\(\s*""" + _KEY_LIT +
                              r"""\s*,\s*(?:null|None|\{[^{}]*\})\s*,\s*(['"])((?:(?!\2).|\\.)*)\2\s*\)\s*\|\|\s*$""")


def _duplicate_of_translated_fallback(s: str, pre: str) -> bool:
    """`lastbookTr?.('k', null, 'X') || 'X'`: the second X is the same English
    fallback, used only when the translation runtime is absent."""
    m = _DUP_FALLBACK_RE.search(pre[-600:])
    return bool(m and m.group(3) == s and _same_as_catalogue(m.group(1), s))


@lru_cache(maxsize=64)
@functools.lru_cache(maxsize=None)
def _keyed_tables(source_file: str):
    """Map (TABLE, id) -> catalogue key for tables whose rows are read through a key.

    Two shapes are proven: a parallel `TABLE_KEY = { id: 'catalogue.key' }`
    object, and a dynamic key `tr('prefix.' + id, null, TABLE[id])`.
    """
    text = _source_text(source_file)
    out = {}
    for m in re.finditer(r'\b(?:const|let|var)\s+([A-Z][A-Z0-9_]*)_KEYS?\s*=\s*\{', text):
        table, start = m.group(1), m.end()
        end = text.find('}', start)
        for ident, key in re.findall(r"""['"]?([A-Za-z_$][\w$]*)['"]?\s*:\s*""" + _KEY_LIT, text[start:end]):
            out[(table, ident)] = key
    for m in re.finditer(r"""\b(?:tr|trHtml|tHtml|lastbookTr|native_t)\s*\(\s*['"]([a-z][\w.]*\.)['"]\s*\+\s*([A-Za-z_$][\w$]*)\s*,\s*[^,()]*,\s*([A-Z][A-Z0-9_]*)\[\2\]""", text):
        prefix, table = m.group(1), m.group(3)
        tm = re.search(r'\b(?:const|let|var)\s+' + table + r'\s*=\s*\{', text)
        if not tm:
            continue
        end = text.find('}', tm.end())
        for ident in re.findall(r"""['"]?([A-Za-z_$][\w$]*)['"]?\s*:\s*['"]""", text[tm.end():end]):
            out.setdefault((table, ident), prefix + ident)
    return out


@functools.lru_cache(maxsize=None)
def _keyed_table_literals(source_file: str):
    """{(ident, English literal): catalogue key} for rows of tables read through a key table."""
    text = _source_text(source_file)
    out = {}
    tables = {table for table, _ident in _keyed_tables(source_file)}
    for table in tables:
        tm = re.search(r'\b(?:const|let|var)\s+' + table + r'\s*=\s*\{', text)
        if not tm:
            continue
        end = text.find('};', tm.end())
        block = text[tm.end():end if end > 0 else len(text)]
        for ident, q, raw in re.findall(r"""['"]?([A-Za-z_$][\w$]*)['"]?\s*:\s*(['"])((?:\\.|(?!\2).)*)\2""", block):
            key = _keyed_tables(source_file).get((table, ident))
            if key:
                out[(ident, unescape(raw, q))] = key
    return out


def _keyed_table_value(s: str, pre: str, source_file: str) -> bool:
    """A row of `TABLE = {id: 'English'}` that is rendered through `TABLE_KEY[id]`
    (or a dynamic `'prefix.' + id` key), whose English equals the catalogue."""
    if not source_file:
        return False
    ident = re.search(r"""['"]?([A-Za-z_$][\w$]*)['"]?\s*:\s*$""", pre[-200:])
    if not ident:
        return False
    key = _keyed_table_literals(source_file).get((ident.group(1), s))
    return bool(key and _same_as_catalogue(key, s))


def _statement_pair(s: str, pre: str) -> bool:
    """A key literal earlier in the same statement whose catalogue English is exactly this
    literal: `key = c ? 'a.b' : 'c.d', fallback = c ? 'A' : 'C'`, `{nameKey: 'k', nameFallback: 'X'}`."""
    stmt = re.split(r';|\n\s*\n', pre[-600:])[-1]
    if not re.search(r'[A-Za-z]{2}', s):
        return False
    return any(_same_as_catalogue(k, s) for k in re.findall(_KEY_LIT, stmt))


def _colour_table_key(post: str) -> bool:
    """`{"Almonds": [150, 100, 50]}`: the literal is the lookup key of a colour table."""
    return bool(re.match(r"""['"]((?:\\.|[^'"\\])*)['"]\s*:\s*(?:\[\s*\d+\s*,\s*\d+\s*,\s*\d+|['"]#[0-9a-fA-F]{3,8}['"])""", post[:200]))


def _inside_uncatalogued_chat_fallback(pre: str) -> bool:
    """Recognize a user-facing third argument to chatTr when its key is missing."""
    source = pre[-2000:]
    keys = _english_keys()
    for match in reversed(list(re.finditer(r'\bchatTr\s*\(', source))):
        args = source[match.end():]
        depth = {'(': 0, '[': 0, '{': 0}
        commas = 0
        i = 0
        while i < len(args):
            c = args[i]
            if c in "'\"":
                i = _skip_string(args, i)
                continue
            if c == '`':
                i = _skip_template(args, i)
                continue
            if c == '(':
                depth['('] += 1
            elif c == ')':
                if depth['('] == depth['['] == depth['{'] == 0:
                    break
                depth['('] = max(0, depth['('] - 1)
            elif c == '[':
                depth['['] += 1
            elif c == ']':
                depth['['] = max(0, depth['['] - 1)
            elif c == '{':
                depth['{'] += 1
            elif c == '}':
                depth['{'] = max(0, depth['{'] - 1)
            elif c == ',' and not any(depth.values()):
                commas += 1
            i += 1
        if commas != 2:
            continue
        first = args.split(',', 1)[0]
        key = re.fullmatch(r"\s*['\"]([A-Za-z][A-Za-z0-9_.-]+)['\"]\s*", first)
        if key and key.group(1) not in keys:
            return True
    return False


def _short_visible_word(s: str) -> bool:
    """A short title-case word can be UI even though it resembles an identifier."""
    return (2 <= len(s) <= 12 and s.isascii() and s.isalpha()
            and s[0].isupper() and s[1:].islower())


def _markdown_blob_export(source: str, pos: int, end: int, value: str) -> bool:
    """Whether a string template is prose assigned to a text/markdown Blob."""
    before = source[max(0, pos - 240):pos]
    assignment = re.search(r'\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*$', before)
    if not assignment:
        return False
    name = re.escape(assignment.group(1))
    tail = source[end:end + 5000]
    blob = re.search(
        r'\bnew\s+Blob\s*\(\s*\[\s*' + name +
        r'\s*\]\s*,\s*\{[^}]{0,600}?\btype\s*:\s*[\'"]text/markdown[\'"]',
        tail, re.S,
    )
    if not blob:
        return False
    prose = re.sub(r'[#>*_`]+', ' ', value).strip()
    return looks_ui(prose)


_PY_STR = re.compile(r"""[rbfu]{0,2}(?:'(?:\\.|[^'\\\n])*'|"(?:\\.|[^"\\\n])*")""")


def _mask_strings(text: str) -> str:
    return _PY_STR.sub(lambda m: '_' * len(m.group(0)), text)


def _enclosing_call(pre: str, post: str):
    """(name, argument text) of the call whose parentheses hold the literal, or (None, '')."""
    window = re.sub(r"[rbfuRBFU]{1,2}$", '', pre[-1500:])
    masked = _mask_strings(window)
    depth = 0
    for i in range(len(masked) - 1, -1, -1):
        c = masked[i]
        if c == ')':
            depth += 1
        elif c == '(':
            if depth == 0:
                name = re.search(r'([A-Za-z_][\w.]*)\s*$', masked[:i])
                rest, d = _after_literal(post, pre)[:1500], 1
                mrest = _mask_strings(rest)
                end = len(rest)
                for j, ch in enumerate(mrest):
                    if ch == '(':
                        d += 1
                    elif ch == ')':
                        d -= 1
                        if d == 0:
                            end = j
                            break
                return (name.group(1).rsplit('.', 1)[-1] if name else None), window[i + 1:] + rest[:end]
            depth -= 1
        elif c in '\n' and depth == 0 and re.match(r'\s*(?:def|class)\b', masked[i + 1:i + 12] or ''):
            break
    return None, ''


def _after_literal(post: str, pre: str = '') -> str:
    """Source after the literal: post starts with the whole literal, or only with its closing
    quote when pre already ends with the opening one."""
    if re.search(r"['\"]$", pre) and post[:1] in ('"', "'"):
        return post[1:]
    m = _PY_STR.match(post)
    if m:
        return post[m.end():]
    return post[1:] if post[:1] in ('"', "'") else post


def _same_dict_rest(post: str) -> str:
    """The rest of the dict literal the literal sits in (up to its closing brace)."""
    masked, depth = _mask_strings(post[:1500]), 0
    for j, ch in enumerate(masked):
        if ch in '{[(':
            depth += 1
        elif ch in '}])':
            if depth == 0:
                return post[:j]
            depth -= 1
    return post[:1500]


def _inside_keyed_error_call(pre: str, post: str) -> bool:
    """A literal fallback that is itself the English of an explicit catalogue key.

    Anchored to the literal: it must be the value next to the key in the same dict,
    an argument of the same call that names the key, the note['error'] whose very next
    line sets note['key'], or a variable that is passed straight to why_part/message_key.
    Being merely near a keyed call proves nothing.
    """
    tail = pre[-300:]
    rest = _after_literal(post, pre)
    field = re.search(r"['\"](error|message|title)['\"]\s*:\s*f?['\"]?$", tail)
    if field:
        field = field.group(1)
        keyname = {'error': 'error_key', 'message': 'message_key', 'title': 'title_key'}[field]
        if re.search(r"['\"]%s['\"]\s*:\s*['\"](?:setup|update|hardware)\." % keyname, _same_dict_rest(rest)):
            return True
    if re.search(r"note\[['\"]error['\"]\]\s*=\s*f?['\"]?$", tail):
        if re.match(r"[^\n]*\n\s*note\[['\"]key['\"]\]\s*=\s*['\"]setup\.", rest):
            return True
    name, args = _enclosing_call(pre, post)
    if name in {'Failed', 'Refused', '_fail', '_refuse_carried_back'} and re.search(r"\bkey\s*=\s*['\"](?:setup|update)\.", args):
        return True
    if name == '_set' and re.search(r"\bmessage_key\s*=\s*['\"]update\.", args):
        return True
    var = re.search(r"\b([A-Za-z_]\w*)\s*\+?=\s*\(?\s*f?['\"]?$", tail)
    if var:
        v = re.escape(var.group(1))
        scope = post[:2500].split('\n    def ', 1)[0]
        if re.search(r"why_part\s*\(\s*['\"]setup\.[\w.]+['\"]\s*,\s*%s\b" % v, scope):
            return True
        # The variable is part of the message of the very next Refused/Failed call, which names its key.
        nxt = re.search(r"\b(?:Refused|Failed)\s*\(", scope)
        if nxt:
            _, call_args = _enclosing_call(scope[:nxt.end()] + ' ', scope[nxt.end():])
            if re.search(r"\b%s\b" % v, call_args) and re.search(r"\bkey\s*=\s*(?:['\"](?:setup|update)\.|['\"]setup\.[\w.]+['\"]\s+if\b)", call_args):
                return True
        if (re.search(r"\bmessage\s*=\s*%s\b" % v, scope) and re.search(r"message_key\s*=\s*key\b", scope)
                and re.search(r"\bkey\s*=\s*['\"]update\.[A-Za-z0-9_.-]+['\"]", pre[-1600:])):
            return True
    return False


def _inside_refused_keyed_message(pre: str, post: str) -> bool:
    """Recognize a message fragment passed to Refused with its catalogue key."""
    return bool(
        re.search(r'\bmessage\s*\+=\s*$', pre[-120:])
        and re.search(r"raise\s+Refused\s*\(\s*['\"]activate['\"]\s*,\s*message\s*,\s*key\s*=\s*key_stuck\s+or\s+key", post[:700])
    )


def looks_technical(s: str) -> bool:
    # Numeric detail templates such as “16.9 GB (16,947,541,728 bytes)”. The
    # words come from the size formatter and a catalogue-backed byte label;
    # this flattened punctuation-only shape is not a copy string of its own.
    if s == '{…} ({…})':
        return True
    if s in TECHNICAL_EXACT:
        return True
    if re.fullmatch(r"(?:class|data-i|lang|title)\s*=\s*['\"]?\{…\}['\"]?", s.strip()):
        return True
    if re.fullmatch(r'and \$\d+', s.strip()):
        return True
    if re.fullmatch(r'(?:·\s*)?\{…\}\s*%', s.strip()):
        return True
    if re.fullmatch(r'·\s*\{…\}\s*GB', s.strip()):
        return True
    if '<' in s and '>' in s:
        visible = re.sub(r'<[^>]*>', ' ', s)
        visible = re.sub(r'\{…\}', ' ', visible)
        if not re.search(r'[A-Za-z]{2,}', visible):
            return True
    if re.match(r'^(?:GET|POST|PUT|DELETE|PATCH|HEAD) /[^\r\n]* HTTP/\d(?:\.\d)?\r?\nHost:', s):
        return True
    if s.startswith('sandbox allow-scripts;'):
        return True
    if re.fullmatch(r'[A-Za-z0-9_.-]+\.py --[A-Za-z0-9_-]+', s):
        return True
    # A dynamic catalogue-key prefix is a resolver input, not display copy.
    if s == 'videos.row.{…}':
        return True
    if re.fullmatch(r'[A-Z][A-Za-z0-9]*(?:Enabled|Preconnect|Prefetch)', s):
        return True
    if s.startswith(TECHNICAL_PREFIX) or SVG_RE.match(s):
        return True
    if re.match(r'^(?:m[\d-]|M[\d-]|0 0 \d)', s):
        return True
    if re.match(r'^(?:margin|padding|border|display|width|height|vertical-align|overflow-wrap)', s):
        return True
    if re.match(r'^(?:#[\w-]+(?:,\s*[^;]+)?|\.[\w-]+(?:,\s*[^;]+)?)$', s):
        return True
    if re.fullmatch(r'\[value="\{…\}"\]', s):
        return True
    if re.fullmatch(r'&near=\{…\},\{…\}', s):
        return True
    if re.fullmatch(r'#[\w-]+\s+[a-zA-Z][\w-]*', s):
        return True
    if 'style="' in s or 'style=\\"' in s or s.startswith('/ui/'):
        return True
    if s.startswith('html{') or re.search(r'\b(?:margin|padding|background|font-family|border|pointer-events):[^ ]', s):
        return True
    if re.fullmatch(r'(?:bytes=)?[0-9{}…-]+(?:px)?(?: 0px 0px 0px)?', s):
        return True
    if re.fullmatch(r'min\(100%,\s*\{…\}px\)', s):
        return True
    if re.fullmatch(r'survival-chat-\{…\}\.md', s):
        return True
    if re.fullmatch(r'\d{3}\s+\{…\}px\s+-apple-system,Segoe UI(?:,Roboto)?(?:,sans-serif)?', s):
        return True
    if re.fullmatch(r'\{…\}(?:\s+\{…\})?px\s+-apple-system,Segoe UI(?:,Roboto)?(?:,sans-serif)?', s):
        return True
    if re.fullmatch(r'\{…\}\s+0\s+\{…\}', s):
        return True
    if s in {'{…} · {…}', '{…} · {…}{…}{…}', '{…} · {…} {…}', '· {…}'}:
        return True
    if re.fullmatch(r'\{…\} sources · \{…\}', s):
        return True
    if re.fullmatch(r'\{…\}(?:\s+\d+)?\s*(?:ft|mi|m|km|px)(?:\s*\([^)]*\))?', s, re.I):
        return True
    if '${' in s or looks_like_markup(s):
        return True
    if s.startswith('<') and ' ' not in s[:6] and len(s) < 40:
        return True
    if s.startswith('<') and '>' not in s:
        return True
    if s == 'indexing (other process)':
        return True
    if s.strip() in {'{…}', ''} or set(s) <= set('{…} \t\n'):
        return True
    body = s.replace('{…}', '')
    if body.startswith('calc('):
        return True
    if s.startswith('[') and ' ' not in body and body.endswith(']'):
        return True
    if re.fullmatch(r'[\[\](){}a-zA-Z0-9_.:/-]*', body) and not re.search(r'[A-Za-z]{4,}', body):
        return True
    if s.startswith('?from=') or (':' in s and 'px' in s):
        return True
    if KEYISH.match(s) and ' ' not in s and not s[0].isupper():
        return True
    if re.match(r'^[A-Z0-9_./:-]+$', s) and ' ' not in s:
        return True
    if s.startswith('#/') or s.startswith('/api/') or s.startswith('.'):
        return True
    if 'tr(' in s or 'native_t(' in s or 'installer_t(' in s:
        return True
    return False


_SQL_RE = re.compile(r'^\s*(?:SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|PRAGMA|WITH|ALTER|REPLACE|AND|OR|ORDER BY|GROUP BY|WHERE|LIMIT|JOIN|FROM|VALUES|ON CONFLICT)\b')
_REGEX_HINT = re.compile(r'\(\?[:=!i<]|\\[dswbSWDB]|\[\^|\$\)|\|\^|\^\(|\(\[|\]\+|\]\*|\.\*|\\\.|\\s\*')
_ATTR_TOKEN = re.compile(r'[a-z][a-z-]*(?:="[^"]*"|=)?')
_SIMPLE_SELECTOR = re.compile(r'[#.]?[a-zA-Z*][\w-]*(?:\[[^\]]*\]|[#.][\w-]+|::?[\w-]+(?:\([^)]*\))?)*|\[[^\]]*\](?:\[[^\]]*\])*')


_HTML_TAGS = frozenset('a abbr article aside audio b button canvas code details dialog div em fieldset figure footer form h1 h2 h3 h4 h5 h6 header hr i iframe img input label legend li main math menu nav object ol optgroup option p picture pre section select small source span strong sub summary sup svg table tbody td textarea tfoot th thead tr track u ul video'.split())


def _is_css_selector(t):
    parts = [x for x in re.split(r'[\s,>+~]+', t) if x]
    if not parts or not all(_SIMPLE_SELECTOR.fullmatch(x) for x in parts):
        return False
    return all(re.search(r'[#.\[:]', x) or x in _HTML_TAGS or x == '*' for x in parts)


def _is_attr_fragment(s):
    parts = s.split()
    return bool(parts) and all(_ATTR_TOKEN.fullmatch(x) for x in parts)


_PATH_CALLS = {'join', 'Path', 'joinpath', 'getenv', 'get', 'environ', 'expanduser', 'OpenKey', 'CreateKey',
               'QueryValueEx', 'SetValueEx', 'DeleteValue', 'glob', 'rglob', 'with_name', 'with_suffix',
               'objectForKey_', 'setObject_forKey_', 'valueForKey_', 'NSSelectorFromString', 'getattr',
               'hasattr', 'setattr', 'find_library', 'LoadLibrary', 'WinDLL', 'CDLL', 'loadLibrary', 'execute',
               'executemany', 'executescript', 'compile', 'search', 'match', 'fullmatch', 'sub', 'split',
               'findall', 'finditer', 'RegExp', 'querySelector', 'querySelectorAll', 'closest', 'matches',
               'getElementById', 'addEventListener', 'removeEventListener', 'dispatchEvent', 'Event',
               'CustomEvent', 'send_header', 'getheader', 'startswith', 'endswith', 'header', 'setRequestHeader',
               'fetch', 'urlopen', 'Request', 'run', 'Popen', 'check_output', 'check_call', 'call', 'mkdtemp',
               'NamedTemporaryFile', 'TemporaryDirectory', 'strftime', 'strptime', 'getElementsByTagName',
               'createElement', 'setAttribute', 'getAttribute', 'removeAttribute', 'toggleAttribute',
               'classList', 'add', 'remove', 'toggle', 'contains', 'replace', 'replaceAll', 'encode', 'decode'}


def proven_technical(s: str, pre: str = '', source_file: str = '') -> bool:
    """Narrow, shape- or call-site-based proof that a literal never reaches a person.

    Prose (several real words with a space) is never proven technical by a call
    site alone except when it is SQL, a regular expression or a GLSL shader.
    """
    t = s.strip()
    if not t:
        return True
    if _SQL_RE.match(t) and (re.search(r'\b(?:FROM|WHERE|LIMIT|JOIN|VALUES|BY|IN|LIKE)\b', t) or t.startswith('PRAGMA ')
                             or re.fullmatch(r'(?:AND|OR)\b.*', t)):
        return True  # SQL
    if re.search(r'\bLIKE \?|\b(?:AND|OR) \(?[\w.]+ ?(?:=|LIKE) ?\?', t):
        return True  # SQL condition with parameters
    if re.search(r'\b(?:SELECT|FROM|WHERE)\b.*\b(?:FROM|WHERE|LIKE|AND|OR)\b', t) and re.search(r'\?|\w+\.\w+|\bLIKE\b', t):
        return True  # SQL fragment
    if _REGEX_HINT.search(t) or (t.count('|') >= 2 and ' ' not in t.replace('| ', '|')) or re.fullmatch(r'(?:[\w-]+\|)+[\w-]+', t):
        return True
    if t.count('|') >= 2 and not re.search(r'[.;!]\s|,\s', t) or re.search(r'\([^()]*\|[^()]*\)', t) and not re.search(r'[.;!]\s', t):
        return True  # regular expressions with spaces in their alternatives
    if ' ' in t and re.fullmatch(r'[a-z0-9-]+(?: [a-z0-9-]+)+', t) and sum('-' in w for w in t.split()) * 2 >= len(t.split()):
        return True  # space-separated category slugs
    if ' ' in t and all(w in _HTML_TAGS for w in t.split()):
        return True  # CSS descendant selector of tag names
    if 'gl_FragColor' in t or 'gl_Position' in t or 'void main()' in t or t.startswith('precision ') or t.startswith('attribute vec'):
        return True
    if s != t and _is_attr_fragment(s) and not re.search(r'[A-Z]', s):
        return True  # ' checked', ' hidden', ' dir="rtl"', ' title='
    if re.fullmatch(r'[a-z0-9.+-]+/[a-z0-9.+*-]+(?:;\s*[a-z-]+=[\w.-]+)?', t):
        return True  # MIME types
    if re.fullmatch(r'(?:[A-Za-z]+:)?(?:/|~/|\./|\.\./)[^\s]*', t) or re.fullmatch(r'[\w.{}%*-]+(?:/[\w.{}%*-]+)+/?', t):
        return True  # paths and URL paths
    if re.fullmatch(r'[a-z][a-z0-9+.-]*:(?://)?[^\s]*', t):
        return True  # about:blank, blob:, data:, lastbook://app, copy:
    if re.fullmatch(r'[a-z][A-Za-z0-9]*:', t) or re.fullmatch(r'(?:[a-z][A-Za-z0-9]*:)+', t):
        return True  # Objective-C selectors
    if re.fullmatch(r'(?:CF|NS|LS|SU|IOPS|IO|kCF|kIO|DW|WS|UI|CG)[A-Z][A-Za-z0-9]*', t):
        return True  # Core Foundation, Info.plist and IOKit identifiers
    if re.fullmatch(r'[A-Z][a-z]+(?:[A-Z][a-z0-9]+)+', t) or re.fullmatch(r'_[A-Za-z0-9_]+', t):
        return True  # CamelCase registry values, struct fields and private attributes
    if re.fullmatch(r'[&?][\w.-]+=[^\s]*', t) or re.fullmatch(r'[\w-]+=(?:\{[^}]*\}|[\w.-]*)', t):
        return True  # query strings, header values such as max-age=60
    if re.search(r'[#.\[,>:]', t) and _is_css_selector(t):
        return True  # CSS selectors
    if ';' in t or re.fullmatch(r'[a-z-]+:\s*[^;:\s][^;]*', t):
        if all(re.fullmatch(r'\s*[a-z-]+\s*:\s*[^;]+', d) for d in t.split(';') if d.strip()) and not re.search(r'[A-Z]', t):
            return True  # inline CSS
    if re.fullmatch(r'%[YmdHMS%-]+(?:[^\w\s]?%[YmdHMS])*|[\w-]*%[YmdHMS][\w%:.-]*|[\w-]+-\*|[\w.-]*\*\.?[\w]*', t):
        return True  # date formats, globs
    if re.fullmatch(r'-{1,2}[A-Za-z][\w-]*', t) or re.fullmatch(r'[A-Z]:\\[^\s]*|Software\\.*|[A-Za-z]+\\[A-Za-z\\]+', t):
        return True  # CLI flags, Windows paths and registry keys
    if re.fullmatch(r'(?:\{[^{}]+\}|[^A-Za-z\s])*', t):
        return True  # placeholders and punctuation only
    if re.search(r'\$env:|New-Object\s+-ComObject|WScript\.Shell|CreateShortcut\(', t):
        return True  # PowerShell source run, never shown
    if re.fullmatch(r'[\w.-]+\.(?:json|sqlite|py|js|css|html|txt|md|zim|pbf|zip|gpkg|png|svg|exe|dll|dylib|so|plist|lproj|app|gguf|log|wav|mp4|webm|pdf|ico|icns)', t) or re.fullmatch(r'\{[^}]+\}\.lproj', t):
        return True  # file names
    if re.fullmatch(r'[\w-]+(?:,[\w-]+)+', t):
        return True  # comma-joined identifiers (OSM tag lists)
    if re.fullmatch(r'[A-Za-z][\w-]*(?:-[\w{}.-]+)+', t) and not ' ' in t and re.search(r'[a-z]', t) and t == t.lower():
        return True  # lane-{name}, download-{i}
    if re.fullmatch(r'[A-Za-z-]+:\s?[\w./ -]*', t) and t.split(':', 1)[0] in {'Host', 'Connection', 'Content-Type', 'Content-Length', 'Cookie', 'Origin', 'Range', 'Accept'}:
        return True  # HTTP header lines
    if ' ' not in t and source_file.endswith('.py'):
        first = re.search(r'([A-Za-z_][\w]*)\s*\(\s*(?:[rbuf]?)$', pre[-80:])
        if first and first.group(1) in _PATH_CALLS - {'get', 'replace', 'add', 'remove', 'toggle', 'contains', 'call', 'run', 'search', 'match', 'split', 'header', 'sub'}:
            return True  # first argument of a path, registry, ctypes, environment or SQL call
        if _inside_named_call(pre[-600:], {'join', 'Path', 'joinpath', 'OpenKey', 'CreateKey', 'QueryValueEx', 'SetValueEx'}):
            return True  # any segment of a path or registry key
    if ' ' not in t and re.search(r'/\s*$', pre[-20:]) and source_file.endswith('.py'):
        return True  # Path / 'Library' / 'Application Support' segment
    if re.fullmatch(r'(?:rgba?|hsla?)\([\d.,%\s]+\)|var\(--[\w-]+\)|\((?:hover|pointer|prefers-[\w-]+|max-width|min-width):\s*[\w-]+\)', t):
        return True  # CSS colour values, custom properties and media queries
    if re.fullmatch(r'(?:[1-9]00\s+)?\d+px\s+[-\w ,"]+', t) and re.search(r'sans-serif|serif|monospace|-apple-system', t):
        return True  # canvas font shorthand
    if re.search(r'=>|\bthis\.\w+\(|\blocation\.\w+\s*=|\bdocument\.\w+|\bwindow\.\w+|\binnerWidth\b', t) and re.search(r'[(=;]', t):
        return True  # JavaScript source evaluated in a web view
    if re.fullmatch(r'(?:aria|data)-[\w-]+="[^"]*"', t):
        return True  # HTML attribute
    if re.fullmatch(r'[a-z]+/[\w.+-]+;\s*codecs="[^"]+"', t):
        return True  # MIME type with codecs
    if re.fullmatch(r'bytes=[\d{}\w. -]*-[\d{}\w. -]*', t):
        return True  # HTTP Range value
    if re.fullmatch(r'\{[^{}]+\} \{[^{}]+\} HTTP/1\.[01]', t) or re.fullmatch(r'[A-Z][A-Za-z]*(?:-[A-Z][A-Za-z]*)*: \{[^\n]*\}', t) \
            or re.fullmatch(r'Origin: \{[^\n]*\}', t):
        return True  # HTTP request line and header lines built from values
    if re.search(r"(?:default|script|connect|object|frame|style|img|font|media|worker)-src\b|frame-ancestors\b", t) or re.fullmatch(r'sandbox(?: allow-[\w-]+)*;\s*', t):
        return True  # Content-Security-Policy
    if '(OI)(CI)' in t or re.fullmatch(r'[<>=!@]?[xcbB?hHiIlLqQnNefdspP0-9]+', t) and re.search(r'[<>=!@]', t):
        return True  # icacls grant, struct format
    if re.fullmatch(r'\{[^{}]+\}\.(?:py|json|txt|lproj)', t) or re.fullmatch(r'[\w-]+/\{[^{}]+\}\.\w+', t):
        return True  # generated file names
    if re.fullmatch(r'[A-Za-z_]{1,5}\{[^{}]+\}', t):
        return True  # generated identifiers such as S{n}, call_{i}
    if t.startswith('^') or re.search(r'\[[^\]]*\\[tns][^\]]*\]\{\d', t):
        return True  # regular expressions
    if re.fullmatch(r'\w+=\{[^{}]+\};(?: [\w-]+(?:=[\w/]+)?;?)+', t):
        return True  # Set-Cookie value
    if re.fullmatch(r'"\{[^{}]+\}"(?: /[A-Za-z]+)+', t):
        return True  # quoted command line with switches
    if re.fullmatch(r'\w+ = \{[^{}]+\}\\n', t) or re.fullmatch(r'X utf8', t):
        return True  # generated Python source and interpreter flags
    if re.fullmatch(r'&(?:[a-z]+|#\d+);', t):
        return True  # HTML entity
    if re.fullmatch(r'(?:\{[^{}]+\}|[^A-Za-z]|, )*', t):
        return True  # values joined with punctuation
    return False


def looks_ui(s: str) -> bool:
    if len(s) < 2 or s.strip() != s:
        return False
    if looks_technical(s) or s in CONTENT:
        return False
    if ' ' in s or any(c in s for c in '?!…·—–'):
        return True
    if s[0].isupper() and s.isascii() and s.isalpha() and len(s) >= 2:
        return True
    return False


def display_context(pre: str) -> bool:
    # The installer helper label() is a visible WinForms sink. Require the
    # literal to be its immediate first argument so a nearby helper definition
    # cannot misclassify a font name such as "Segoe UI". ZIMS is a data array
    # rendered as encyclopedia cards and result labels, so its literals are UI
    # even though the strings do not sit beside an HTML assignment.
    recent = pre[-2000:]
    zims = re.search(r'\b(?:const|let|var)\s+ZIMS\s*=\s*\[', recent)
    in_zims = bool(zims and ';' not in recent[zims.end():])
    display_data = re.search(
        r'\b(?:const|let|var)\s+(?:[A-Za-z_$][\w$]*)?(?:STARTERS|PROMPTS|STATES|STAGES|LABELS|TYPES|FILTERS|OPTIONS|ACTIONS|ITEMS|CATEGORIES|SECTIONS|LAYERS|GROUPS|PRESETS)\w*\s*=\s*[\[{]',
        recent,
    )
    in_display_data = bool(display_data and ';' not in recent[display_data.end():])
    display_helpers = {'statusLine', 'toast', 'button', 'heading', 'paragraph', 'hint', 'notice', 'message', 'sec', 'fail'}
    return bool(DISPLAY_PRE.search(pre[-240:]) or _inside_named_call(pre, display_helpers)
                or re.search(r'\blabel\s*\(\s*f?$', pre[-80:]) or re.search(r'\bsub\s*:\s*$', pre[-80:])
                or in_zims or in_display_data)

def classify(s: str, pre: str, post: str = '', source_file: str = '') -> str:
    # Wiring comes only from the source before this literal. Display and
    # technical classification can use both sides to recognize a DOM sink.
    context = pre + post
    prefix = pre.rsplit(';', 1)[-1][-1600:]
    # A flattened template made only from translated expressions plus
    # punctuation is not a hard-coded message of its own.
    literal_remainder = re.sub(r'\{…\}', '', s)
    if ('tr(' in post[:4000] and not re.search(r'[A-Za-z]{2,}', literal_remainder)
            and '{…}' in s):
        return 'wired'
    mapped_error = bool(re.search(r"_fail\([^)]*\bkey\s*=\s*['\"](?:setup|native|installer)\.", pre))
    if ('__i18n_bound' in pre or _inside_translation_call(pre) or _inside_keyed_error_call(pre, post)
            or _inside_refused_keyed_message(pre, post)
            or _inside_catalogued_fallback(pre, {'message', 'tHtml', 'chatResult', 'chatTr', 'setError', 'trMarkup', 'keyedMessage'})
            or mapped_error or already_wired(prefix)
            or _constant_is_catalogue_fallback(pre, source_file)
            or _keyed_pair(s, pre) or _label_to_key(s, post) or _duplicate_of_translated_fallback(s, pre)
            or _keyed_table_value(s, pre, source_file) or _statement_pair(s, pre)
            or _has_i18n_marker_in_tag(pre, post) or 'data-i18n' in s):
        return 'wired'
    if '__no_js_fallback__' in pre:
        return 'technical'  # Static English fallback; localization needs the JavaScript runtime it explains.
    mapped_label = _mapped_map_label(s, pre) if source_file in ('web/map.js', 'web/chat.js') else None
    if mapped_label:
        return mapped_label
    if _colour_table_key(post):
        return 'technical'
    if s in CONTENT:
        return 'content'
    if proven_technical(s, pre, source_file):
        return 'technical'
    if _inside_uncatalogued_chat_fallback(pre):
        return 'chrome' if looks_ui(s.strip()) and not looks_technical(s.strip()) else 'technical'
    if '__visible_attribute__' in pre:
        return 'chrome' if looks_ui(s) else 'technical'
    # Fragments with intentional leading/trailing spaces occur in web
    # templates (for example, an optional suffix inside a rendered sentence).
    # Python prompts, SQL, and API values can contain whitespace too, so only
    # apply this UI heuristic to the explicitly enumerated web interface.
    web_ui_source = source_file.startswith('web/')
    if web_ui_source and s.strip() != s:
        fragment = s.strip()
        if fragment and fragment not in CONTENT and looks_ui(fragment) and not looks_technical(fragment):
            return 'chrome'
    if web_ui_source and s not in TECHNICAL_EXACT and s not in CONTENT and _short_visible_word(s) and display_context(pre):
        return 'chrome'
    if len(s) == 2 and s.isascii() and s.isalpha() and s[0].isupper() and display_context(pre):
        return 'chrome'
    if TOKEN.match(s) or _class_list(s, pre) or s == 'use strict':
        return 'technical'
    # Only the current literal's enclosing call makes it a log. A nearby print
    # in the same function must not hide a later MessageBox or other display sink.
    if _inside_named_call(pre, LOG_CALLS):
        return 'technical'
    short_label = len(s) == 2 and s.isascii() and s.isalpha() and s[0].isupper()
    if looks_technical(s) and not short_label:
        return 'technical'
    if looks_ui(s) and (display_context(pre) or (
            re.search(r"['\"]type['\"]\s*:\s*['\"]error['\"]", pre[-1200:])
            and re.search(r"['\"]text['\"]\s*:\s*$", pre[-240:]))):
        return 'chrome'
    if short_label and display_context(pre):
        return 'chrome'
    # Flattened `${...}` templates are user-visible even when the prefix is only `return`.
    if looks_ui(s) and '{…}' in s:
        return 'chrome'
    if proven_technical(s, pre, source_file):
        return 'technical'
    # Default-deny: prose that was not proven wired or technical is presumed
    # visible, wherever it sits. A sink the scanner does not know yet must not
    # turn an English sentence into "technical".
    if looks_ui(s):
        return 'chrome'
    if re.search(r'[A-Za-z]{2,}', s) and not KEYISH.match(s):
        return 'unknown'
    return 'technical'


@lru_cache(maxsize=1)
def _css_classes():
    """Class names the stylesheets and pages define; a lowercase list of them is a class attribute."""
    names = set()
    for path in list(WEB.glob('*.css')) + list(WEB.glob('*.html')) + list(WEB.glob('*.js')):
        text = path.read_text(encoding='utf-8', errors='replace')
        names.update(re.findall(r'\.([A-Za-z_][\w-]*)', text) if path.suffix == '.css' else ())
        for attr in re.findall(r'class(?:Name)?\s*=\s*["\']([^"\'$<>{}]*)', text):
            names.update(attr.split())
        for call in re.findall(r'classList\.(?:add|remove|toggle|contains)\(\s*["\']([\w-]+)', text):
            names.add(call)
    return names


def _class_list(s: str, pre: str) -> bool:
    """A lowercase class list: in a class attribute or classList call, or made only of defined class names."""
    if not CSS_LIKE.match(s):
        return False
    if re.search(r'''(?:class(?:Name)?\s*[=:]\s*["'`]?[^"'`<>]*|classList\.\w+\(\s*)$''', pre[-120:]):
        return True
    if ' ' not in s and ('-' in s or '_' in s):
        return True
    words = s.split()
    return all(w in _css_classes() for w in words) and (len(words) > 1 or s in _css_classes())


def strip_comments_js(text: str) -> str:
    """Blank JavaScript comments while preserving literals and source offsets.

    This small lexer follows quoted strings, template literal expressions and
    regular-expression literals so that `//` in visible text or a regexp is
    never mistaken for a line comment. It is deliberately non-transforming:
    every non-comment character remains at its original offset.
    """
    out = list(text)
    n = len(text)

    def blank(start, end):
        for at in range(start, end):
            if text[at] not in '\r\n':
                out[at] = ' '

    def quoted(i, quote):
        i += 1
        while i < n:
            if text[i] == '\\':
                i = min(n, i + 2)
            elif text[i] == quote:
                return i + 1
            else:
                i += 1
        return i

    def regexp(i):
        i += 1
        in_class = False
        while i < n:
            c = text[i]
            if c == '\\':
                i = min(n, i + 2)
            elif c in '\r\n':
                return i
            elif c == '[':
                in_class = True
                i += 1
            elif c == ']' and in_class:
                in_class = False
                i += 1
            elif c == '/' and not in_class:
                i += 1
                while i < n and (text[i].isalpha() or text[i].isdigit()):
                    i += 1
                return i
            else:
                i += 1
        return i

    def template(i):
        i += 1  # opening backtick
        while i < n:
            if text[i] == '\\':
                i = min(n, i + 2)
            elif text.startswith('${', i):
                i = code(i + 2, template_expr=True)
            elif text[i] == '`':
                return i + 1
            else:
                i += 1
        return i

    def code(i, template_expr=False):
        depth = 0
        regex_allowed = True
        while i < n:
            c = text[i]
            if c.isspace():
                i += 1
                continue
            if template_expr and c == '}' and depth == 0:
                return i + 1
            if c in "'\"":
                i = quoted(i, c)
                regex_allowed = False
                continue
            if c == '`':
                i = template(i)
                regex_allowed = False
                continue
            if text.startswith('//', i):
                end = i + 2
                while end < n and text[end] not in '\r\n':
                    end += 1
                blank(i, end)
                i = end
                continue
            if text.startswith('/*', i):
                end = text.find('*/', i + 2)
                end = n if end < 0 else end + 2
                blank(i, end)
                i = end
                continue
            if c == '/' and regex_allowed:
                i = regexp(i)
                regex_allowed = False
                continue
            if c == '{':
                depth += 1
                regex_allowed = True
                i += 1
                continue
            if c == '}':
                depth = max(0, depth - 1)
                regex_allowed = False
                i += 1
                continue
            if c.isalpha() or c in '_$':
                end = i + 1
                while end < n and (text[end].isalnum() or text[end] in '_$'):
                    end += 1
                regex_allowed = text[i:end] in {
                    'return', 'throw', 'case', 'delete', 'void', 'typeof', 'new',
                    'in', 'of', 'instanceof', 'yield', 'await', 'else', 'do',
                }
                i = end
                continue
            if c.isdigit():
                i += 1
                while i < n and (text[i].isalnum() or text[i] in '._'):
                    i += 1
                regex_allowed = False
                continue
            regex_allowed = c in '=(:,[!&|?;+-*%^~<>'
            i += 1
        return i

    code(0)
    return ''.join(out)


def strip_python_comments(text: str) -> str:
    """Blank Python comments without touching hashes inside strings."""
    lines = text.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    chars = list(text)
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type != tokenize.COMMENT:
                continue
            start = offsets[tok.start[0] - 1] + tok.start[1]
            end = offsets[tok.end[0] - 1] + tok.end[1]
            for i in range(start, end):
                if chars[i] != '\n':
                    chars[i] = ' '
    except (tokenize.TokenError, IndentationError):
        return text
    return ''.join(chars)


def _skip_string(text, i):
    """i points at an opening quote. Return the index after the closing quote."""
    quote = text[i]
    i += 1
    n = len(text)
    while i < n:
        if text[i] == '\\':
            i = min(i + 2, n)
            continue
        if text[i] == quote:
            return i + 1
        if quote != '`' and text[i] == '\n':
            return i
        i += 1
    return i


def _skip_js_expr(text, i):
    """i points at the first character of a ${...} expression. Return the index after its closing }."""
    depth = 1
    regex_allowed = True
    n = len(text)
    while i < n and depth:
        if text[i].isspace():
            i += 1
            continue
        if text.startswith('//', i):
            end = text.find('\n', i + 2)
            i = n if end < 0 else end + 1
            continue
        if text.startswith('/*', i):
            end = text.find('*/', i + 2)
            i = n if end < 0 else end + 2
            continue
        c = text[i]
        if c in "'\"":
            i = _skip_string(text, i)
            regex_allowed = False
            continue
        if c == '`':
            i = _skip_template(text, i)
            regex_allowed = False
            continue
        if c == '/' and regex_allowed:
            i += 1
            in_class = False
            while i < n:
                if text[i] == '\\':
                    i = min(n, i + 2)
                elif text[i] == '[':
                    in_class = True
                    i += 1
                elif text[i] == ']' and in_class:
                    in_class = False
                    i += 1
                elif text[i] == '/' and not in_class:
                    i += 1
                    while i < n and text[i].isalpha():
                        i += 1
                    break
                elif text[i] in '\r\n':
                    break
                else:
                    i += 1
            regex_allowed = False
            continue
        if c == '{':
            depth += 1
            regex_allowed = True
        elif c == '}':
            depth -= 1
            regex_allowed = False
        elif c.isalpha() or c in '_$':
            end = i + 1
            while end < n and (text[end].isalnum() or text[end] in '_$'):
                end += 1
            regex_allowed = text[i:end] in {
                'return', 'throw', 'case', 'delete', 'void', 'typeof', 'new',
                'in', 'of', 'instanceof', 'yield', 'await', 'else', 'do',
            }
            i = end
            continue
        elif c.isdigit():
            i += 1
            while i < n and (text[i].isalnum() or text[i] in '._'):
                i += 1
            regex_allowed = False
            continue
        else:
            regex_allowed = c in '=(:,[!&|?;+-*%^~<>'
        i += 1
    return i


def _skip_template(text, i):
    """i points at an opening backtick. Return the index after the closing backtick."""
    i += 1
    n = len(text)
    while i < n:
        if text[i] == '\\':
            i = min(i + 2, n)
            continue
        if text.startswith('${', i):
            i = _skip_js_expr(text, i + 2)
            continue
        if text[i] == '`':
            return i + 1
        i += 1
    return i


def _unescape_template(s):
    out = []
    i, n = 0, len(s)
    escapes = {'n': '\n', 't': '\t', 'r': '\r', '`': '`', '\\': '\\', '$': '$'}
    while i < n:
        if s[i] == '\\' and i + 1 < n:
            out.append(escapes.get(s[i + 1], s[i + 1]))
            i += 2
            continue
        out.append(s[i])
        i += 1
    return ''.join(out)


def _template_parts(text, start):
    """Return (end, parts) for a template starting at start. parts are ('lit', text) or ('expr', src)."""
    parts = []
    i = start + 1
    lit = i
    n = len(text)
    while i < n:
        if text[i] == '\\':
            i = min(i + 2, n)
            continue
        if text.startswith('${', i):
            parts.append(('lit', _unescape_template(text[lit:i])))
            expr_start = i + 2
            i = _skip_js_expr(text, expr_start)
            parts.append(('expr', text[expr_start:i - 1]))
            lit = i
            continue
        if text[i] == '`':
            parts.append(('lit', _unescape_template(text[lit:i])))
            return i + 1, parts
        i += 1
    parts.append(('lit', _unescape_template(text[lit:i])))
    return i, parts


def _template_expressions(text, start):
    """Return the source ranges of expressions directly inside a template."""
    i, n = start + 1, len(text)
    while i < n:
        if text[i] == '\\':
            i = min(i + 2, n)
            continue
        if text.startswith('${', i):
            expr_start = i + 2
            expr_end = _skip_js_expr(text, expr_start) - 1
            yield expr_start, expr_end
            i = expr_end + 1
            continue
        if text[i] == '`':
            return
        i += 1


def _iter_js_templates(text, base, source):
    """Yield template messages recursively, including nested template branches."""
    i, n = 0, len(text)
    while i < n:
        if text[i] in "'\"":
            i = _skip_string(text, i)
            continue
        if text[i] != '`':
            i += 1
            continue
        start = i
        end, parts = _template_parts(text, start)
        absolute = base + start
        pre = source[max(0, absolute - 2000):absolute]
        if any(kind == 'expr' for kind, _ in parts):
            flat = ''.join(lit if kind == 'lit' else '{…}' for kind, lit in parts)
            if flat.strip() and flat.strip() != '{…}':
                if _is_markup_fragment(flat):
                    for value, local_pre in _template_markup_strings(flat, pre):
                        yield absolute, value, local_pre
                else:
                    yield absolute, flat, pre
            for expr_start, expr_end in _template_expressions(text, start):
                yield from _iter_js_templates(text[expr_start:expr_end], base + expr_start, source)
        else:
            literal = ''.join(lit for kind, lit in parts if kind == 'lit')
            if _is_markup_fragment(literal):
                for value, local_pre in _template_markup_strings(literal, pre):
                    yield absolute, value, local_pre
            else:
                yield absolute, literal, pre
        i = end


def looks_like_markup(s):
    body = s.replace('{…}', ' ')
    if '<' in body and '>' in body and body.lstrip().startswith('<'):
        text = re.sub(r'<[^>]*>', ' ', body)
        text = re.sub(r'\{[^}]*\}', ' ', text)
        if not re.search(r'[A-Za-z]{3,}', text):
            return True
    return False


class _MarkupStrings(HTMLParser):
    """Yield visible text and accessible attributes from HTML template literals."""
    VISIBLE_ATTRIBUTES = {'alt', 'aria-description', 'aria-label', 'placeholder', 'title', 'value'}
    VOID_ELEMENTS = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}

    def __init__(self, prefix):
        super().__init__(convert_charrefs=True)
        self.prefix = prefix
        self.tags = []
        self.strings = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        markers = {key for key in values if key == 'data-i18n' or key.startswith('data-i18n-')}
        if tag not in self.VOID_ELEMENTS:
            self.tags.append((tag, markers))
        for name in self.VISIBLE_ATTRIBUTES:
            value = values.get(name)
            if value:
                marker = f'data-i18n-{name}'
                pre = self.prefix + ' ' + name + ' __visible_attribute__' + (' __i18n_bound_attribute__' if marker in markers else '')
                self.strings.append((value, pre))
        if tag == 'meta' and (values.get('name', '').lower() in {'description', 'twitter:description'}
                              or values.get('property', '').lower() == 'og:description'):
            value = values.get('content')
            if value:
                marker = 'data-i18n-content'
                pre = self.prefix + ' content __visible_attribute__' + (' __i18n_bound_attribute__' if marker in markers else '')
                self.strings.append((value, pre))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.tags) - 1, -1, -1):
            if self.tags[index][0] == tag:
                del self.tags[index:]
                break

    def handle_data(self, data):
        if any(tag in {'script', 'style'} for tag, _markers in self.tags):
            return
        value = data.strip()
        if value:
            wired = bool(self.tags and 'data-i18n' in self.tags[-1][1])
            no_js = any(tag == 'noscript' for tag, _markers in self.tags)
            marker = ' __no_js_fallback__' if no_js else ''
            self.strings.append((value, self.prefix + ' innerHTML' + (' __i18n_bound_text__' if wired else '') + marker))


def _template_markup_strings(flat, pre):
    # A single template can contain translated and untranslated elements. Do
    # not classify the whole template from a nearby marker: inspect each text
    # node and visible attribute in its own element context.
    parser = _MarkupStrings(pre)
    try:
        parser.feed(flat)
        parser.close()
    except Exception:
        return []
    return parser.strings


def _is_markup_fragment(value):
    return '<' in value and '>' in value and value.lstrip().startswith('<')


_JS_REGEX_LIT = re.compile(r'((?:=>|[(,=:!&|?{};])\s*)/(?![/*])((?:\\.|\[(?:\\.|[^\]\\\n])*\]|[^/\\\n\[\'"`])+)/[gimsuy]*')


def mask_js_regex(text):
    """Blank regular-expression literal bodies (same length) so quotes inside them are not strings."""
    return _JS_REGEX_LIT.sub(lambda m: m.group(1) + '/' + ' ' * len(m.group(2)) + m.group()[len(m.group(1)) + 1 + len(m.group(2)):], text)


def iter_js_strings(text):
    text = mask_js_regex(strip_comments_js(text))
    for m in STR_RE.finditer(text):
        raw, q = m.group(2), m.group(1)
        s = unescape(raw, q)
        pre = text[max(0, m.start() - 2000):m.start()]
        if _is_markup_fragment(s):
            for value, local_pre in _template_markup_strings(s, pre):
                yield m.start(), value, local_pre
        else:
            yield m.start(), s, pre
    yield from _iter_js_templates(text, 0, text)


def _offsets(text):
    rows = [0]
    for line in text.splitlines(keepends=True):
        rows.append(rows[-1] + len(line))
    return rows


def _ast_position(text, offsets, line, byte_col):
    source_line = text.splitlines(keepends=True)[line - 1]
    char_col = len(source_line.encode('utf-8')[:byte_col].decode('utf-8', 'ignore'))
    return offsets[line - 1] + char_col


def _python_docstring_ranges(text):
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return []
    offsets = _offsets(text)
    ranges = []
    owners = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
    for node in ast.walk(tree):
        if not isinstance(node, owners) or not node.body:
            continue
        first = node.body[0]
        if not isinstance(first, ast.Expr) or not isinstance(first.value, ast.Constant) or not isinstance(first.value.value, str):
            continue
        ranges.append((_ast_position(text, offsets, first.lineno, first.col_offset),
                       _ast_position(text, offsets, first.end_lineno, first.end_col_offset)))
    return ranges


def _python_string_value(literal):
    try:
        value = ast.literal_eval(literal)
        return value if isinstance(value, str) else None
    except (SyntaxError, ValueError):
        # f-strings are not literal-evaluable. Keep their readable text and
        # replace each expression with a stable placeholder for classification.
        match = re.match(r'(?is)^([rubf]*)("""|\'\'\'|"|\')([\s\S]*?)\2$', literal)
        if not match or 'f' not in match.group(1).lower() or 'b' in match.group(1).lower():
            return None
        body = match.group(3)
        body = re.sub(r'(?<!\{)\{(?:[^{}]|\{[^{}]*\})*\}(?!\})', '{…}', body)
        return body.replace('\\n', '\n').replace('\\t', '\t')


def _python_fstring_values(text, offsets, docstrings):
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError):
        return
    for node in ast.walk(tree):
        if not isinstance(node, ast.JoinedStr):
            continue
        start = _ast_position(text, offsets, node.lineno, node.col_offset)
        end = _ast_position(text, offsets, node.end_lineno, node.end_col_offset)
        if any(start < doc_end and end > doc_start for doc_start, doc_end in docstrings):
            continue
        parts = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            elif isinstance(value, ast.FormattedValue):
                expression = ast.unparse(value.value)
                field = '{' + expression
                if value.conversion != -1:
                    field += '!' + chr(value.conversion)
                if value.format_spec:
                    spec = ''.join(part.value for part in value.format_spec.values
                                   if isinstance(part, ast.Constant) and isinstance(part.value, str))
                    field += ':' + spec
                parts.append(field + '}')
        if parts:
            yield start, ''.join(parts)


def iter_py_strings(text: str):
    body = strip_python_comments(text)
    offsets = _offsets(text)
    chars = list(body)
    docstrings = _python_docstring_ranges(text)
    for start, end in docstrings:
        for at in range(start, end):
            if chars[at] not in '\r\n':
                chars[at] = ' '
    body = ''.join(chars)
    values = []
    try:
        tree = ast.parse(text)
        joined_ranges = []
        for node in ast.walk(tree):
            if isinstance(node, ast.JoinedStr):
                joined_ranges.append((_ast_position(text, offsets, node.lineno, node.col_offset),
                                      _ast_position(text, offsets, node.end_lineno, node.end_col_offset)))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            start = _ast_position(text, offsets, node.lineno, node.col_offset)
            end = _ast_position(text, offsets, node.end_lineno, node.end_col_offset)
            if any(start < doc_end and end > doc_start for doc_start, doc_end in docstrings):
                continue
            if any(start < joined_end and end > joined_start for joined_start, joined_end in joined_ranges):
                continue
            # Python combines adjacent literals into one Constant. Scanning
            # that value preserves the actual visible message at display sinks.
            values.append((start, node.value))
        values.extend(_python_fstring_values(text, offsets, docstrings))
        for start, value in sorted(values):
            yield start, value, body[max(0, start - 200):start], body
    except (SyntaxError, tokenize.TokenError, IndentationError):
        return


def scan_web():
    hits = []
    for name in WEB_FILES:
        path = WEB / name
        if not path.is_file():
            continue
        text = path.read_text(encoding='utf-8')
        if name.endswith('.html'):
            parser = _MarkupStrings(f'web/{name}')
            parser.feed(text)
            parser.close()
            for value, pre in parser.strings:
                if not value or len(value) > 2000:
                    continue
                line = text[:text.find(value)].count('\n') + 1 if value in text else 1
                hits.append({'surface': f'web/{name}', 'line': line, 'text': value,
                             'class': classify(value, pre, source_file=f'web/{name}')})
            continue
        hits.extend(scan_js_text(text, name))
    return hits


def scan_js_text(text, name):
    """Classify every string literal of one web script (also used by the mutation tests)."""
    hits = []
    for pos, s, pre in iter_js_strings(text):
        if not s or len(s) > 2000:
            continue
        end = _skip_template(text, pos) if text[pos] == '`' else _skip_string(text, pos)
        # Keep lookahead within this literal; same-tag HTML checks can
        # inspect the remainder of the current attribute/tag from here.
        post = text[pos:min(len(text), end + 600)]
        line = text[:pos].count('\n') + 1
        kind = classify(s, pre, post, source_file=f'web/{name}')
        if kind == 'technical' and _markdown_blob_export(text, pos, end, s):
            kind = 'chrome'
        hits.append({'surface': f'web/{name}', 'line': line, 'text': s, 'class': kind})
    return hits


def scan_topics(topics=ROOT / 'content' / 'topics'):
    """Inventory topic titles and short descriptions that the UI resolves by dynamic key."""
    english = load_english()[0]
    hits = []
    for path in sorted(topics.glob('*.json')):
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        topic_id = data.get('id') or path.stem
        try:
            relative = str(path.relative_to(ROOT))
        except ValueError:
            relative = path.name
        source = path.read_text(encoding='utf-8')
        for field, key in (('title', f'topic.{topic_id}'), ('short', f'topic.short.{topic_id}')):
            value = data.get(field)
            if not isinstance(value, str) or not value:
                continue
            line = next((i for i, row in enumerate(source.splitlines(), 1) if row.lstrip().startswith(f'"{field}"')), 1)
            hits.append({'surface': 'topic-data', 'file': relative, 'line': line,
                         'text': value, 'key': key, 'class': 'wired' if key in english else 'chrome'})
    return hits


def scan_python():
    hits = []
    for surface, paths in PYTHON_SURFACES.items():
        for path in paths:
            if not path.is_file():
                continue
            if path.suffix == '.desktop':
                hits.extend(scan_desktop(path))
                continue
            hits.extend(scan_python_text(path.read_text(encoding='utf-8'), str(path.relative_to(ROOT)), surface))
    return hits


def scan_python_text(source, rel, surface='python'):
    """Classify every string literal of one Python source (also used by the mutation tests)."""
    hits = []
    text = strip_python_comments(source)
    # These short labels are values in the navigation table; the key map
    # beside it sends them through native_t (checked here, not assumed).
    go_values = set()
    go_span = (0, 0)
    if rel in ('app/shell_linux.py', 'app/shell_macos.py'):
        go_match = re.search(r'\bGO\s*=\s*\[(.*?)\]', text, re.S)
        key_match = re.search(r'go_names\s*=\s*\{(.*?)\}', text, re.S)
        if go_match and key_match and 'native_t(go_names.get(name' in text:
            go_values = set(re.findall(r"['\"]([^'\"]+)['\"]\s*,", go_match.group(1)))
            translated_names = set(re.findall(r"['\"]([^'\"]+)['\"]\s*:\s*['\"]nav\.", key_match.group(1)))
            go_values &= translated_names
            go_span = go_match.span(1)
    embedded = re.search(r'(?m)^TOP_SCRIPT\s*=\s*r"""([\s\S]*?)"""', text) if rel == 'app/bridge.py' else None
    embedded_span = embedded.span() if embedded else (0, 0)   # scanned below literal by literal, as JavaScript
    for pos, s, pre, body in iter_py_strings(text):
        if not s or len(s) > 4000 or embedded_span[0] <= pos < embedded_span[1]:
            continue
        pre = body[max(0, pos - 800):pos]
        end = _skip_string(body, pos)
        post = body[pos:min(len(body), end + 1000)]
        line = body[:pos].count('\n') + 1
        if s in go_values and go_span[0] <= pos < go_span[1]:
            kind = 'wired'   # a GO row label, shown through native_t(go_names[...]) (checked above)
        else:
            kind = classify(s, pre, post, source_file=rel)
        hits.append({'surface': surface, 'file': rel, 'line': line, 'text': s, 'class': kind})
    if embedded:
        script = embedded.group(1)
        line_offset = text[:embedded.start(1)].count('\n')
        for pos, s, pre in iter_js_strings(script):
            if not s or len(s) > 2000:
                continue
            line = line_offset + script[:pos].count('\n') + 1
            hits.append({'surface': surface, 'file': rel, 'line': line,
                         'text': s, 'class': classify(s, pre, source_file=rel)})
    return hits


def scan_desktop(path):
    """Scan translated user-facing fields in a freedesktop .desktop file."""
    rows = []
    for line_no, raw in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        match = re.match(r'^(Name|GenericName|Comment|Keywords)(?:\[([A-Za-z0-9_-]+)\])?=(.*)$', raw)
        if match:
            key, locale, value = match.groups()
            rows.append((line_no, key, locale, value))
    variants = defaultdict(set)
    for _line, key, locale, _value in rows:
        if locale:
            variants[key].add(locale)
    hits = []
    for line, key, locale, value in rows:
        if key == 'Name' and value in CONTENT:
            kind = 'content'
        elif key in DESKTOP_TRANSLATED_FIELDS and DESKTOP_LOCALES.issubset(variants[key]):
            kind = 'wired'
        else:
            kind = 'chrome'
        hits.append({'surface': 'desktop', 'file': str(path.relative_to(ROOT)), 'line': line,
                     'text': value, 'class': kind})
    return hits


def iter_c_strings(text):
    """Yield C wide and narrow string literals after removing comments."""
    body = strip_comments_js(text)
    body = re.sub(r"(?<![A-Za-z0-9_])L?'(?:\\.|[^'\\\n])'", lambda m: ' ' * len(m.group()), body)  # char literals
    pattern = re.compile(r'(?<![A-Za-z0-9_])(?:L|u8|u|U)?"((?:\\.|[^"\\])*)"')
    for match in pattern.finditer(body):
        value = match.group(1).replace(r'\"', '"').replace(r'\\', '\\')
        yield match.start(), value, body[max(0, match.start() - 2000):match.start()], body


def scan_c():
    hits = []
    for path in C_FILES:
        if not path.is_file():
            continue
        for pos, value, pre, body in iter_c_strings(path.read_text(encoding='utf-8')):
            if not value or len(value) > 2000:
                continue
            hits.append({'surface': 'windows-setup-stub', 'file': str(path.relative_to(ROOT)),
                         'line': body[:pos].count('\n') + 1, 'text': value,
                         'class': classify(value, pre, source_file=str(path.relative_to(ROOT)))})
    return hits


def summarize(hits):
    by = defaultdict(lambda: defaultdict(int))
    for h in hits:
        by[h['surface']][h['class']] += 1
    totals = defaultdict(int)
    for counts in by.values():
        for k, n in counts.items():
            totals[k] += n
    return by, totals


def unique_chrome(hits):
    seen = {}
    for h in hits:
        if h['class'] != 'chrome':
            continue
        loc = f"{h.get('file') or h['surface']}:{h['line']}"
        seen.setdefault(h['text'], []).append(loc)
    return seen


ALLOWLIST_PATH = ROOT / 'packaging' / 'i18n_allowlist.json'
UNAPPROVED_CLASSES = ('chrome', 'content', 'unknown')


def load_allowlist(path: Path | None = None):
    """Exact file + exact string + reason. Nothing else can approve a literal."""
    path = path or ALLOWLIST_PATH
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding='utf-8'))
    entries = data.get('entries', []) if isinstance(data, dict) else data
    out = []
    for e in entries:
        if not isinstance(e, dict):
            raise ValueError(f'allowlist entry is not an object: {e!r}')
        file, string, why = e.get('file'), e.get('string'), (e.get('why') or '').strip()
        if not isinstance(file, str) or not file or not isinstance(string, str) or not string:
            raise ValueError(f'allowlist entry needs an exact file and string: {e!r}')
        if len(why) < 12:
            raise ValueError(f'allowlist entry needs a reason: {e!r}')
        row = {'file': file.replace('\\', '/'), 'string': string, 'why': why}
        if e.get('pending'):
            # Visible text a later PR of the stack wires; the row goes stale (and --check fails) once it does.
            row['pending'] = str(e['pending'])
        out.append(row)
    return out


def hit_file(h) -> str:
    return str(h.get('file') or h.get('surface') or '').replace('\\', '/')


def unapproved(hits, entries=None, surfaces=None):
    """Hits that are not proven wired or technical and not allowlisted.

    chrome, content and unknown all fail unless the exact file and string are
    listed in the allowlist with a reason. surfaces limits the check, e.g. to
    the web and Setup layer while native shells are still being wired.
    """
    entries = load_allowlist() if entries is None else entries
    allowed = {(e['file'], e['string']) for e in entries}
    out = []
    for h in hits:
        if h.get('class') not in UNAPPROVED_CLASSES:
            continue
        if surfaces is not None and not any(h['surface'] == x or h['surface'].startswith(x + '/') for x in surfaces):
            continue
        if (hit_file(h), h.get('text') or '') in allowed:
            continue
        out.append(h)
    return out


def unique_unapproved(hits, entries=None, surfaces=None):
    seen = {}
    for h in unapproved(hits, entries, surfaces):
        seen.setdefault(h['text'], []).append(f"{hit_file(h)}:{h['line']}")
    return seen


def stale_allowlist(hits, entries=None):
    """Allowlist rows that no longer match any scanned literal of an unapproved class."""
    entries = load_allowlist() if entries is None else entries
    present = {(hit_file(h), h.get('text') or '') for h in hits if h.get('class') in UNAPPROVED_CLASSES}
    return [e for e in entries if (e['file'], e['string']) not in present]


def scan_all():
    hits = scan_web() + scan_topics() + scan_python() + scan_c()
    return hits


def report(hits, key_count, entries=None):
    by, totals = summarize(hits)
    chrome = unique_chrome(hits)
    pending = unique_unapproved(hits, entries)
    lines = [f'Catalogue English keys: {key_count}', 'Totals by class:']
    for k in ('wired', 'chrome', 'content', 'unknown', 'technical'):
        lines.append(f'  {k:12} {totals[k]}')
    lines.append('\nBy surface (chrome / unknown / wired / content / technical):')
    for surf in sorted(by):
        c = by[surf]
        lines.append(
            f"  {surf:24} chrome={c['chrome']:4}  unknown={c['unknown']:3}  wired={c['wired']:4}  "
            f"content={c['content']:3}  technical={c['technical']:4}"
        )
    lines.append(f'\nUnique still-hardcoded chrome strings: {len(chrome)}')
    entries = load_allowlist() if entries is None else entries
    waiting = sorted({e['pending'] for e in entries if e.get('pending')})
    lines.append(f"Allowlisted as reviewed: {sum(1 for e in entries if not e.get('pending'))}; "
                 f"listed as pending wiring in a later PR: {sum(1 for e in entries if e.get('pending'))}"
                 + (f" ({', '.join(waiting)})" if waiting else ''))
    lines.append(f'Unapproved (not wired, not technical, not allowlisted): {len(pending)}')
    for text, locs in sorted(pending.items(), key=lambda kv: (-len(kv[1]), kv[0].lower())):
        lines.append(f'  {text!r}')
        extra = ' …' if len(locs) > 8 else ''
        lines.append('    ' + ', '.join(locs[:8]) + extra)
    return '\n'.join(lines) + '\n', totals, chrome, by


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    english, _ = load_english()
    hits = scan_all()
    entries = load_allowlist()
    text, totals, chrome, by = report(hits, len(english), entries)
    sys.stdout.write(text)
    stale = stale_allowlist(hits, entries)
    for e in stale:
        sys.stdout.write(f"stale allowlist entry: {e['file']}: {e['string']!r}\n")
    if '--check' in argv and (unapproved(hits, entries) or stale):
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
