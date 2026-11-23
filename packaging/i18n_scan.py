"""Inventory hard-coded user-visible strings and classify them.

Surfaces: the desktop web UI, Setup/engine API messages shown in the UI,
native shells (menus and dialogs), the Windows installer, and the Linux
.desktop file. Classes:

  wired     -- already a catalogue fallback (tr(), data-i18n, or native_t())
  chrome    -- user-visible UI that still needs a catalogue key
  content   -- library/data (titles, USDA crop names, pack names, brand)
  technical -- identifiers, logs, headers, SVG, docstrings, not shown to a person

Run:  python3 -B packaging/i18n_scan.py
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / 'web'
EN = ROOT / 'translations' / 'desktop' / 'en.json'

WEB_FILES = [
    'index.html', 'setup.html', 'app.js', 'setup.js', 'chat.js', 'map.js',
    'update.js', 'terrain3d.js', 'video-moments.js', 'i18n-app.js',
]

PYTHON_SURFACES = {
    'engine/setup': [
        ROOT / 'engine' / 'setup' / 'api.py',
        ROOT / 'engine' / 'setup' / 'download.py',
        ROOT / 'engine' / 'setup' / 'hardware.py',
        ROOT / 'engine' / 'setup' / 'install.py',
    ],
    'app/main': [ROOT / 'app' / 'main.py'],
    'native/macos': [ROOT / 'app' / 'shell_macos.py'],
    'native/windows': [ROOT / 'app' / 'shell_windows.py'],
    'native/linux': [ROOT / 'app' / 'shell_linux.py'],
    'installer': [ROOT / 'packaging' / 'lastbook_setup.py'],
    'desktop': [ROOT / 'packaging' / 'linux' / 'lastbook.desktop'],
}

CONTENT = {
    'Lastbook', 'LastbookData', 'Lastbook videos', 'Español (Latinoamérica)',
    'English', 'US', '3D', 'CC', 'PDF', 'AI', 'ZIP', 'GB', 'SHA-256',
    'Almonds', 'Walnuts', 'Pecans', 'Pistachios', 'Cherries', 'Peaches',
    'Apples', 'Pears', 'Prunes', 'Nectarines', 'Plums', 'Apricots',
    'Pomegranates', 'Avocados', 'Olives', 'Citrus', 'Oranges', 'Grapes',
    'Blueberries', 'Cranberries', 'Caneberries', 'Asparagus',
    'Other tree crops', 'WHO', 'FEMA', 'CDC', 'EPA', 'USDA', 'NOAA',
    'UNICEF', 'MSF', 'Small', 'Medium', 'Large',
    'Where There Is No Doctor', 'National Center for Home Food Preservation',
}

TECHNICAL_EXACT = {
    'changed its ETag twice', 'ignores Range',
    'POST', 'GET', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'Content-Type',
    'Content-Range', 'ArrowDown', 'ArrowUp', 'ArrowLeft', 'ArrowRight',
    'Escape', 'Enter', 'AbortError', 'HEVC', 'START-HERE.txt',
    'LastbookData.setup', 'application/json', 'text/html',
    'T12:00:00', 'Polygon', 'use strict', 'ETag', 'If-None-Match',
}

TECHNICAL_PREFIX = (
    'M12 ', 'M9 ', 'M4 ', 'M3 ', 'M5 ', 'M6 ', 'M7 ', 'M8 ', 'M10 ', 'M14 ',
    'M15 ', 'M16 ', 'M18 ', 'M20 ', 'M13 ', 'http', 'https', 'function ',
    'const ', 'return ', 'typeof ', 'window.', 'document.', 'class ',
)

LOG_CONTEXT = (
    'console.', 'logger.', 'log(', '_log(', 'print(',
    'raise RuntimeError', 'raise ValueError', 'raise OSError',
)

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
    r'innerHTML|outerHTML|textContent|innerText|document\.title|setTitle|'
    r'setUiTitle|aria-label|placeholder|confirm\(|alert\(|toast\(|show_error|'
    r'MessageBox|MessageDialog|addButtonWithTitle_|setTitle_|GenericName|'
    r'Comment=|Name=|\.Text\s*=|why\s*=|Failed\(|_fail\(|live\.textContent|'
    r'set_tooltip|tooltip_text|add_buttons\(|initWithTitle_|ASK_TITLE|ASK\s*=|'
    r'TOO_BIG|STOPPED\s*=|APP_OPEN_TEXT|setWindowTitle|title\s*[:=]|menu\.append|view\.append|'
    r'helps\.append|_menu\('
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


def unescape(s, quote):
    if quote == "'":
        return s.replace(r"\'", "'").replace(r"\\", "\\")
    return s.replace(r'\"', '"').replace(r"\\", "\\")


def already_wired(pre: str) -> bool:
    # Only inspect the current statement. A translation call earlier in the
    # same function must not hide a later hard-coded label (the old 300-char
    # window caused this false positive, especially in compact JS).
    tail = pre.rsplit(';', 1)[-1][-300:]
    if re.search(r"(?:tr|native_t|installer_t|user_error|t)\s*\(", tail):
        return True
    if 'data-i18n' in tail:
        return True
    if re.search(r"(?:ASK|ASK_TITLE|TOO_BIG|STOPPED|STUCK|APP_OPEN_TEXT|NO_RUNTIME|setUiTitle|labelPair|backButton|GO)\s*[=(]", tail):
        return True
    if re.search(r"(?:key\s*=|\[\s*['\"]key['\"]\s*\]\s*=)\s*['\"](?:setup|native|installer|desktop|nav|chat|map)\.", tail):
        return True
    return False


def looks_technical(s: str) -> bool:
    if s in TECHNICAL_EXACT:
        return True
    if s.startswith(TECHNICAL_PREFIX) or SVG_RE.match(s):
        return True
    if re.match(r'^(?:m[\d-]|M[\d-]|0 0 \d)', s):
        return True
    if re.match(r'^(?:margin|padding|border|display|width|height|vertical-align|overflow-wrap)', s):
        return True
    if '${' in s or looks_like_markup(s):
        return True
    if s.startswith('<') and ' ' not in s[:6] and len(s) < 40:
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


def looks_ui(s: str) -> bool:
    if len(s) < 2 or s.strip() != s:
        return False
    if looks_technical(s) or s in CONTENT:
        return False
    if ' ' in s or any(c in s for c in '?!…·—–'):
        return True
    if s[0].isupper() and s.isascii() and s.isalpha() and len(s) >= 3:
        return True
    return False


def display_context(pre: str) -> bool:
    return bool(DISPLAY_PRE.search(pre[-240:]))


def classify(s: str, pre: str, post: str = '') -> str:
    # Wiring comes only from the source before this literal. Display and
    # technical classification can use both sides to recognize a DOM sink.
    context = pre + post
    prefix = pre.rsplit(';', 1)[-1][-300:]
    if already_wired(prefix) or 'data-i18n' in s:
        return 'wired'
    if TOKEN.match(s) or CSS_LIKE.match(s) or s == 'use strict':
        return 'technical'
    if any(c in context[-260:] for c in LOG_CONTEXT):
        return 'technical'
    if s in CONTENT:
        return 'content'
    if looks_technical(s):
        return 'technical'
    if looks_ui(s) and display_context(context):
        return 'chrome'
    # Flattened `${...}` templates are user-visible even when the prefix is only `return`.
    if looks_ui(s) and '{…}' in s:
        return 'chrome'
    return 'technical'


def strip_comments_js(text: str) -> str:
    out, i, n = [], 0, len(text)
    while i < n:
        if text.startswith('//', i):
            j = text.find('\n', i)
            if j < 0:
                out.append(' ' * (n - i))
                break
            out.append(' ' * (j - i) + '\n')
            i = j + 1
        elif text.startswith('/*', i):
            j = text.find('*/', i + 2)
            chunk = text[i: n if j < 0 else j + 2]
            out.append(re.sub(r'[^\n]', ' ', chunk))
            i = n if j < 0 else j + 2
        else:
            out.append(text[i])
            i += 1
    return ''.join(out)


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
    n = len(text)
    while i < n and depth:
        c = text[i]
        if c in "'\"":
            i = _skip_string(text, i)
            continue
        if c == '`':
            i = _skip_template(text, i)
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
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


def looks_like_markup(s):
    body = s.replace('{…}', ' ')
    if '<' in body and '>' in body and body.lstrip().startswith('<'):
        text = re.sub(r'<[^>]*>', ' ', body)
        text = re.sub(r'\{[^}]*\}', ' ', text)
        if not re.search(r'[A-Za-z]{3,}', text):
            return True
    return False


def iter_js_strings(text):
    text = strip_comments_js(text)
    for m in STR_RE.finditer(text):
        raw, q = m.group(2), m.group(1)
        s = unescape(raw, q)
        yield m.start(), s, text[max(0, m.start() - 180):m.start()]
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in "'\"":
            i = _skip_string(text, i)
            continue
        if c == '`':
            start = i
            end, parts = _template_parts(text, start)
            pre = text[max(0, start - 180):start]
            if any(kind == 'expr' for kind, _ in parts):
                flat = ''.join(lit if kind == 'lit' else '{…}' for kind, lit in parts)
                if flat.strip() and flat.strip() != '{…}':
                    yield start, flat, pre
            else:
                s = ''.join(lit for kind, lit in parts if kind == 'lit')
                yield start, s, pre
            i = end
            continue
        i += 1


def mask_py_docstrings(text: str) -> str:
    trip = chr(34) * 3
    trip2 = chr(39) * 3
    def blank(m):
        return re.sub(r'[^\n]', ' ', m.group(0))
    text = re.sub(re.escape(trip) + r'[\s\S]*?' + re.escape(trip), blank, text)
    text = re.sub(re.escape(trip2) + r'[\s\S]*?' + re.escape(trip2), blank, text)
    return text


def iter_py_strings(text: str):
    text = mask_py_docstrings(text)
    cleaned = []
    for line in text.splitlines(True):
        if line.lstrip().startswith('#'):
            cleaned.append('\n' if line.endswith('\n') else '')
        else:
            cleaned.append(line)
    body = ''.join(cleaned)
    for m in STR_RE.finditer(body):
        raw, q = m.group(2), m.group(1)
        s = raw.replace(r"\'", "'").replace(r'\"', '"')
        yield m.start(), s, body[max(0, m.start() - 200):m.start()], body


def scan_web():
    hits = []
    for name in WEB_FILES:
        path = WEB / name
        if not path.is_file():
            continue
        text = path.read_text(encoding='utf-8')
        it = iter_js_strings(text)
        for pos, s, pre in it:
            if not s or len(s) > 2000:
                continue
            post = text[pos:pos + 180]
            line = text[:pos].count('\n') + 1
            hits.append({'surface': f'web/{name}', 'line': line, 'text': s,
                         'class': classify(s, pre, post)})
    return hits


def scan_python():
    hits = []
    for surface, paths in PYTHON_SURFACES.items():
        for path in paths:
            if not path.is_file():
                continue
            text = path.read_text(encoding='utf-8')
            rel = str(path.relative_to(ROOT))
            for pos, s, pre, body in iter_py_strings(text):
                if not s or len(s) > 300:
                    continue
                post = body[pos:pos + 220]
                line = body[:pos].count('\n') + 1
                hits.append({'surface': surface, 'file': rel, 'line': line,
                             'text': s, 'class': classify(s, pre, post)})
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


def report(hits, key_count):
    by, totals = summarize(hits)
    chrome = unique_chrome(hits)
    lines = [f'Catalogue English keys: {key_count}', 'Totals by class:']
    for k in ('wired', 'chrome', 'content', 'technical'):
        lines.append(f'  {k:12} {totals[k]}')
    lines.append('\nBy surface (chrome / wired / content / technical):')
    for surf in sorted(by):
        c = by[surf]
        lines.append(
            f"  {surf:24} chrome={c['chrome']:4}  wired={c['wired']:4}  "
            f"content={c['content']:3}  technical={c['technical']:4}"
        )
    lines.append(f'\nUnique still-hardcoded chrome strings: {len(chrome)}')
    for text, locs in sorted(chrome.items(), key=lambda kv: (-len(kv[1]), kv[0].lower())):
        lines.append(f'  {text!r}')
        extra = ' …' if len(locs) > 8 else ''
        lines.append('    ' + ', '.join(locs[:8]) + extra)
    return '\n'.join(lines) + '\n', totals, chrome, by


def main(argv=None):
    english, _ = load_english()
    hits = scan_web() + scan_python()
    text, totals, chrome, by = report(hits, len(english))
    sys.stdout.write(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
