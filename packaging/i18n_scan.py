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
import io
import re
import sys
import tokenize
import ast
from html.parser import HTMLParser
from collections import defaultdict
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
}
DESKTOP_LOCALES = {'de', 'es_419', 'zh_Hans'}
DESKTOP_TRANSLATED_FIELDS = {'GenericName', 'Comment', 'Keywords'}

CONTENT = {
    'Lastbook', 'LastbookData', 'Lastbook videos', 'Español (Latinoamérica)',
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
    '(pointer: coarse)',
}

TECHNICAL_PREFIX = (
    'M12 ', 'M9 ', 'M4 ', 'M3 ', 'M5 ', 'M6 ', 'M7 ', 'M8 ', 'M10 ', 'M14 ',
    'M15 ', 'M16 ', 'M18 ', 'M20 ', 'M13 ', 'http', 'https', 'function ',
    'const ', 'return ', 'typeof ', 'window.', 'document.', 'class ',
)

LOG_CALLS = {'debug', 'error', 'info', 'log', 'print', 'warning', '_log', 'stop', 'ValueError', 'RuntimeError', 'OSError', 'end_page'}

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
    # A completed translation call elsewhere in the same statement must not
    # hide a different literal, especially inside a nested template.
    tail = pre.rsplit(';', 1)[-1][-300:]
    if _inside_translation_call(pre):
        return True
    if _inside_named_call(pre, {'setUiTitle', 'labelPair', 'backButton'}):
        return True
    if re.search(r"(?:ASK|ASK_TITLE|TOO_BIG|STOPPED|STUCK|APP_OPEN_TEXT|NO_RUNTIME)\s*=\s*\(?\s*$", tail):
        return True
    return False


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


def _inside_named_call(pre: str, names) -> bool:
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
                m = re.search(r'([A-Za-z_$][\w$]*)\s*$', pre[:i])
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
    return _inside_named_call(pre, {'tr', 'trHtml', 'trLang', 'trResult', 'chatResult', 'lastbookTr', 'native_t', 'installer_t', 'user_error', '_api_error', 't'})


def _inside_keyed_error_call(pre: str, post: str) -> bool:
    """Recognize literal fallbacks paired with an explicit translation key."""
    source = pre[-2000:] + post[:1000]
    if re.search(r"why_part\s*\(\s*['\"]setup\.", source):
        return True
    if re.search(r"title_key['\"]?\s*:\s*['\"]setup\.copyJobTitle", source):
        return True
    if re.search(r"(?:Failed|Refused|_fail|_refuse_carried_back)\s*\([\s\S]{0,1400}?\bkey\s*=\s*['\"](?:setup|update)\.", source):
        return True
    if re.search(r"_set\s*\([\s\S]{0,1200}?\bmessage_key\s*=\s*['\"]update\.", source):
        return True
    if re.search(r"\bkey\s*=\s*['\"]update\.[A-Za-z0-9_.-]+['\"]", pre[-1600:]) and re.search(r"message_key\s*=\s*key", post[:1600]):
        return True
    if re.search(r"['\"]error['\"]\s*:\s*f?['\"]?[\s\S]{0,600}?['\"]error_key['\"]\s*:\s*['\"](?:setup|update|hardware)\.", source):
        return True
    return bool(re.search(r"note\[['\"]error['\"]\]\s*=\s*['\"][\s\S]{0,600}?note\[['\"]key['\"]\]\s*=\s*['\"]setup\.", source))


def looks_technical(s: str) -> bool:
    if s in TECHNICAL_EXACT:
        return True
    if re.fullmatch(r'[A-Za-z0-9_.-]+\.py --[A-Za-z0-9_-]+', s):
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
    if s in {'{…} · {…}', '{…} · {…}{…}{…}', '· {…}'}:
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
    # The installer helper label() is a visible WinForms sink. Require the
    # literal to be its immediate first argument so a nearby helper definition
    # cannot misclassify a font name such as "Segoe UI". ZIMS is a data array
    # rendered as encyclopedia cards and result labels, so its literals are UI
    # even though the strings do not sit beside an HTML assignment.
    recent = pre[-2000:]
    zims = re.search(r'\b(?:const|let|var)\s+ZIMS\s*=\s*\[', recent)
    in_zims = bool(zims and ';' not in recent[zims.end():])
    display_data = re.search(
        r'\b(?:const|let|var)\s+[A-Za-z_$][\w$]*(?:STARTERS|PROMPTS|STATES|STAGES|LABELS|TYPES|FILTERS|OPTIONS|ACTIONS|ITEMS|CATEGORIES|SECTIONS)\w*\s*=\s*[\[{]',
        recent,
    )
    in_display_data = bool(display_data and ';' not in recent[display_data.end():])
    display_helpers = {'statusLine', 'toast', 'button', 'heading', 'paragraph', 'hint', 'notice', 'message', 'sec', 'fail'}
    return bool(DISPLAY_PRE.search(pre[-240:]) or _inside_named_call(pre, display_helpers)
                or re.search(r'\blabel\s*\(\s*f?$', pre[-80:]) or in_zims or in_display_data)

def classify(s: str, pre: str, post: str = '') -> str:
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
            or mapped_error or already_wired(prefix)
            or _has_i18n_marker_in_tag(pre, post) or 'data-i18n' in s):
        return 'wired'
    if '__visible_attribute__' in pre:
        return 'chrome' if looks_ui(s) else 'technical'
    if TOKEN.match(s) or CSS_LIKE.match(s) or s == 'use strict':
        return 'technical'
    # Only the current literal's enclosing call makes it a log. A nearby print
    # in the same function must not hide a later MessageBox or other display sink.
    if _inside_named_call(pre, LOG_CALLS):
        return 'technical'
    if s in CONTENT:
        return 'content'
    if looks_technical(s):
        return 'technical'
    if looks_ui(s) and display_context(pre):
        return 'chrome'
    # Flattened `${...}` templates are user-visible even when the prefix is only `return`.
    if looks_ui(s) and '{…}' in s:
        return 'chrome'
    return 'technical'


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

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.tags) - 1, -1, -1):
            if self.tags[index][0] == tag:
                del self.tags[index:]
                break

    def handle_data(self, data):
        if any(tag in {'script', 'style', 'noscript'} for tag, _markers in self.tags):
            return
        value = data.strip()
        if value:
            wired = bool(self.tags and 'data-i18n' in self.tags[-1][1])
            self.strings.append((value, self.prefix + ' innerHTML' + (' __i18n_bound_text__' if wired else '')))


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


def iter_js_strings(text):
    text = strip_comments_js(text)
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
                             'class': classify(value, pre)})
            continue
        it = iter_js_strings(text)
        for pos, s, pre in it:
            if not s or len(s) > 2000:
                continue
            end = _skip_template(text, pos) if text[pos] == '`' else _skip_string(text, pos)
            # Keep lookahead within this literal; same-tag HTML checks can
            # inspect the remainder of the current attribute/tag from here.
            post = text[pos:min(len(text), end + 600)]
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
            if path.suffix == '.desktop':
                hits.extend(scan_desktop(path))
                continue
            text = strip_python_comments(path.read_text(encoding='utf-8'))
            rel = str(path.relative_to(ROOT))
            # These short labels are values in the Linux navigation table;
            # the corresponding key map sends them through native_t later.
            go_values = set()
            if rel in ('app/shell_linux.py', 'app/shell_macos.py'):
                go_match = re.search(r'\bGO\s*=\s*\[(.*?)\]', text, re.S)
                key_match = re.search(r'go_names\s*=\s*\{(.*?)\}', text, re.S)
                if go_match and key_match and 'native_t(go_names.get(name' in text:
                    go_values = set(re.findall(r"['\"]([^'\"]+)['\"]\s*,", go_match.group(1)))
                    translated_names = set(re.findall(r"['\"]([^'\"]+)['\"]\s*:\s*['\"]nav\.", key_match.group(1)))
                    go_values &= translated_names
            for pos, s, pre, body in iter_py_strings(text):
                if not s or len(s) > 300:
                    continue
                pre = body[max(0, pos - 200):pos]
                end = _skip_string(body, pos)
                post = body[pos:min(len(body), end + 1000)]
                line = body[:pos].count('\n') + 1
                if rel == 'engine/update.py':
                    pre = body[max(0, pos - 2000):pos]
                kind = 'wired' if s in go_values else classify(s, pre, post)
                hits.append({'surface': surface, 'file': rel, 'line': line,
                             'text': s, 'class': kind})
            if rel == 'app/bridge.py':
                embedded = re.search(r'(?m)^TOP_SCRIPT\s*=\s*r"""([\s\S]*?)"""', text)
                if embedded:
                    script = embedded.group(1)
                    line_offset = text[:embedded.start(1)].count('\n')
                    for pos, s, pre in iter_js_strings(script):
                        if not s or len(s) > 2000:
                            continue
                        line = line_offset + script[:pos].count('\n') + 1
                        hits.append({'surface': surface, 'file': rel, 'line': line,
                                     'text': s, 'class': classify(s, pre)})
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
