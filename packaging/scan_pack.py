"""Looks inside a finished pack for anything the spec forbids. Exit 0 only when every file on disk was read and nothing is wrong; anything else, a crash included, is exit 1.

  python -I -B scan_pack.py <pack folder> [--terms file] [--accepted file] [--snapshot dir] [--report file.json]

It shares no code with build_packs.py and trusts nothing the builder wrote. HTML goes through the browser tokenizer written here, not the html.parser the builder used: entities
decoded, tag and attribute case folded, tabs and newlines taken out of addresses. Each page is read three ways: as a browser would, with no element's content treated as raw text
(inside <svg> a <title> or <style> holds real tags), and after saved_pages.rewrite, which is what is really served. Private words come from the terms file and are never printed:
the report names them by line number. The household and working words come from packaging/ship_edits.json (forbidden), the list the app build's scans use, and fail as
term.household in the catalog, search, pages, text files and file names; third-party text that only names the place is accepted by path.
scan-accepted.tsv (path, reason, who, rules) can excuse the pdf.*, zim.* and term.* rules a line names for its path, and nothing else. Only the owner's decisions go in it.
"""
import argparse
import fnmatch
import hashlib
import html
import importlib.util
import json
import os
import re
import sqlite3
import struct
import sys
import traceback
import urllib.parse
import zipfile
import zlib
from collections import Counter, defaultdict
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
SPEC = json.loads((PROJECT / 'derived/packs/pack-spec.json').read_text(encoding='utf-8'))
ROOT_FILES = {'pack.json', 'pack-manifest.tsv', 'pack-contents.tsv'}
LIB_ROOT_FILES = {'catalog.json', 'search.sqlite', 'summary.json', 'reader.css'}
GEO_FILES = {'national.sqlite', 'map.sqlite', 'water.sqlite', 'terrain.sqlite', 'buildings.sqlite', 'crops.sqlite', 'places.sqlite', 'national-status.json', 'socal-cells.json'}
ATLAS = 'library-data/geography/resources/atlas.sqlite'
IMAGES = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
FOLDER_EXT = {
    'documents': {'.pdf', '.pptx', '.html', '.htm', '.txt', '.css'} | IMAGES | {'.svg'},
    'pages': set(SPEC['extension_allow_list']['pages']),
    'assets': set(SPEC['extension_allow_list']['assets']),
    'courses': set(SPEC['extension_allow_list']['courses']),
    'videos': {'.mp4', '.vtt'},
    'videos-external': {'.mp4', '.vtt'},
    'transcripts': {'.txt', '.vtt'},
    'text': {'.txt'},
    'metadata': IMAGES,
    'collections': {'.zim'},
}
SUMMARY_FIELDS = {'resources', 'pdfs', 'pdf_pages', 'web_pages', 'videos', 'collections', 'document_bytes'}
PACK_FIELDS = {'name', 'size', 'map', 'built', 'snapshot', 'sample', 'add_ons', 'counts', 'known_gaps', 'incomplete', 'content_revision'}
SIZE_NAMES = set(SPEC['sizes']) | set(SPEC['addons'])

ACCEPTABLE = ('pdf.', 'zim.', 'term.')
WEB_ANCHOR = 'html.web_anchor'
SHIP_EDITS = json.loads((PROJECT / 'packaging/ship_edits.json').read_text(encoding='utf-8'))
HOUSEHOLD = re.compile('|'.join(SHIP_EDITS['forbidden']).encode(), re.I)      # never written here: the words live in that file
ID_BACK = {new: old for old, new in SHIP_EDITS['id_prefixes'].items()}      # a pack ID back to its snapshot ID
PLACEHOLDER_OWNERS = {'see source', 'unnamed source', 'unknown'}
KIND_OF_EXT = {'.html': 'html', '.htm': 'html', '.svg': 'svg', '.pdf': 'pdf', '.mp4': 'video', '.zim': 'zim', '.pptx': 'pptx'}
RESERVED = {'con', 'prn', 'aux', 'nul'} | {f'{d}{i}' for d in ('com', 'lpt') for i in range(1, 10)}
USER_PATH = re.compile(rb'/Users/|/home/|/Volumes/|C:\\\\?Users')        # case-sensitive and only in our own files: third-party text is full of cdc.gov/mmwr/volumes/
LAN = re.compile(rb'\b(?:192\.168|10\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b|\b100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d{1,3}\.\d{1,3}\b|\b169\.254\.\d{1,3}\.\d{1,3}\b')

# ---------------------------------------------------------------- HTML as a browser reads it ----
SPACE = ' \t\n\f\r'
RAW = {'script', 'style', 'xmp', 'iframe', 'noembed', 'noframes', 'title', 'textarea'}
COMMENT_END = re.compile(r'--!?>')


def read_tag(s, i):
    """From just after '<' or '</': (name, [(attribute, value)], self-closing, next position). Follows the HTML standard's tag states, so that <img/src=x/onerror=y> is three attributes."""
    n = len(s)
    j = i
    while j < n and s[j] not in SPACE + '/>':
        j += 1
    name = s[i:j].lower()
    attrs = []
    closed = False
    i = j
    while i < n:
        c = s[i]
        if c in SPACE:
            i += 1
        elif c == '>':
            return name, attrs, closed, i + 1
        elif c == '/':
            closed = s.startswith('/>', i)
            i += 1
        else:
            j = i + 1 if c == '=' else i
            while j < n and s[j] not in SPACE + '/>=':
                j += 1
            key = s[i:j].lower()
            i = j
            while i < n and s[i] in SPACE:
                i += 1
            value = None
            if i < n and s[i] == '=':
                i += 1
                while i < n and s[i] in SPACE:
                    i += 1
                if i < n and s[i] in '"\'':
                    end = s.find(s[i], i + 1)
                    end = n if end < 0 else end
                    value = s[i + 1:end]
                    i = end + 1
                else:
                    j = i
                    while j < n and s[j] not in SPACE + '>':
                        j += 1
                    value = s[i:j]
                    i = j
            attrs.append((key, html.unescape(value) if value else (value if value is None else '')))
    return name, attrs, closed, n


def tokens(s, raw=True):
    """Yields ('text', t), ('start', name, attrs), ('end', name), ('comment', t), ('pi', t), ('doctype', t). With raw=False no element's content is special."""
    i, n = 0, len(s)
    while i < n:
        lt = s.find('<', i)
        if lt < 0:
            yield ('text', s[i:])
            return
        if lt > i:
            yield ('text', s[i:lt])
        i = lt
        c = s[i + 1:i + 2]
        if c == '!':
            if s.startswith('<!--', i):
                if s.startswith('>', i + 4):
                    end = i + 5
                elif s.startswith('->', i + 4):
                    end = i + 6
                else:
                    m = COMMENT_END.search(s, i + 4)
                    end = m.end() if m else n
                yield ('comment', s[i:end])
            else:
                j = s.find('>', i)
                end = n if j < 0 else j + 1
                yield ('doctype' if s[i + 2:i + 9].lower() == 'doctype' else 'comment', s[i:end])
            i = end
        elif c == '?':
            j = s.find('>', i)
            end = n if j < 0 else j + 1
            yield ('pi', s[i:end])
            i = end
        elif c == '/':
            d = s[i + 2:i + 3]
            if d.isascii() and d.isalpha():
                name, _, _, i = read_tag(s, i + 2)
                yield ('end', name)
            elif d == '>':
                i += 3
            elif d:
                j = s.find('>', i)
                end = n if j < 0 else j + 1
                yield ('comment', s[i:end])
                i = end
            else:
                yield ('text', '</')
                i += 2
        elif c.isascii() and c.isalpha():
            name, attrs, _, i = read_tag(s, i + 1)
            yield ('start', name, attrs)
            if raw and name == 'plaintext':
                yield ('text', s[i:])
                return
            if raw and name in RAW:
                m = re.compile(f'</{name}(?=[{SPACE}/>])', re.I).search(s, i)
                end = m.start() if m else n
                yield ('raw' if name not in ('title', 'textarea') else 'text', s[i:end], name)
                i = end
        else:
            yield ('text', '<')
            i += 1


def clean_url(v):
    return re.sub(r'[\t\r\n]', '', (v or '').strip(' \x00\x01\x02\x03\x04\x05\x06\x07\x08\x0b\x0c\x0e\x0f\x10\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b\x1c\x1d\x1e\x1f\t\r\n'))


INLINE_PICTURE = re.compile(rb';base64,[A-Za-z0-9+/=]+')
HAS_SCHEME = re.compile(r'^[a-z][a-z0-9+.\-]*:', re.I)
SCRIPTY = re.compile(r'^(?:javascript|vbscript|livescript|mocha|jscript):', re.I)
INERT = re.compile(r'^data:image/(?:png|jpe?g|gif|webp)[;,]', re.I)
CSS_INERT = re.compile(r'^data:(?:image|font|application/(?:x-)?font)', re.I)
WEB_LIKE = re.compile(r'^(?:[a-z]+://|[/\\]{2})', re.I)


def goes_out(v, inert=INERT):
    """True for anything that is not a plain local address: a scheme, //, and the \\\\ forms a browser reads as //."""
    v = clean_url(v)
    if inert.match(v):
        return False
    return bool(HAS_SCHEME.match(v)) or v[:2] in ('//', '\\\\', '/\\', '\\/')


URL_ATTRS = {'src', 'poster', 'background', 'data', 'lowsrc', 'dynsrc', 'longdesc', 'cite', 'icon', 'xml:base'}
OFF_ATTRS = {'action', 'formaction', 'ping', 'manifest', 'codebase', 'classid', 'archive', 'profile'}
BANNED_ELEMENTS = {'script', 'object', 'embed', 'applet', 'param', 'portal'}
OFF_META = {'refresh', 'set-cookie', 'content-security-policy', 'x-ua-compatible'}
IN_SRCSET = re.compile(r'(?:^|[\s,])(?:[a-z][a-z0-9+.\-]*:|[/\\]{2})', re.I)
CSS_COMMENT = re.compile(r'/\*.*?(?:\*/|$)', re.S)
CSS_ESCAPE = re.compile(r'\\([0-9a-fA-F]{1,6})\s?|\\(.)', re.S)
CSS_URLS = re.compile(r"""url\(\s*(?:"([^"]*)"|'([^']*)'|([^)]*))\s*\)""", re.I)
CSS_SETS = re.compile(r"""(?:image-set|src)\(\s*(?:"([^"]*)"|'([^']*)')""", re.I)


def css_hits(css):
    """Rules this CSS breaks. Comments and escapes come out first, as the browser's own reading does: u\\72l( is url(."""
    out = []
    css = CSS_COMMENT.sub('', css)
    css = CSS_ESCAPE.sub(lambda m: chr(min(int(m.group(1), 16), 0x10ffff) or 0xfffd) if m.group(1) else m.group(2), css)
    if re.search(r'@import', css, re.I):
        out.append('css.import')
    for rx in (CSS_URLS, CSS_SETS):
        for m in rx.finditer(css):
            if goes_out(m.group(1) or m.group(2) or (m.group(3) if rx is CSS_URLS else '') or '', CSS_INERT):
                out.append('css.remote_url')
    return out


def tag_hits(name, attrs):
    out = []
    a = {}
    for k, v in attrs:
        a.setdefault(k, v or '')
    if name in BANNED_ELEMENTS:
        out.append(f'html.element.{name}')
    if name == 'iframe' and (not a.get('src') or goes_out(a['src'])):
        out.append('html.element.iframe')
    if name == 'frame' and goes_out(a.get('src')):
        out.append('html.element.frame')
    if name == 'link' and not ('stylesheet' in a.get('rel', '').lower() and a.get('href') and not goes_out(a['href'])):
        out.append('html.element.link')
    if name == 'meta' and a.get('http-equiv', '').strip().lower() in OFF_META:
        out.append('html.element.meta')
    if name == 'base' and ('href' in a or 'xlink:href' in a):
        out.append('html.base_href')
    if name == 'img' and not clean_url(a.get('src')) and not clean_url(a.get('srcset')):
        out.append('html.image_with_no_source')
    for k, v in attrs:
        v = v or ''
        if k.startswith('on') and len(k) > 2:
            out.append('html.event_attribute')
        elif k in OFF_ATTRS:
            out.append(f'html.attr.{k}')
        elif k in ('href', 'xlink:href'):
            u = clean_url(v)
            if name in ('a', 'area'):
                if SCRIPTY.match(u) or u.lower().startswith('data:'):
                    out.append('html.script_link')
                elif goes_out(v):
                    out.append(WEB_ANCHOR if re.match(r'(?:https?:|//)', u, re.I) else 'html.non_web_link')
            elif goes_out(v):
                out.append('html.remote_href')
        elif k in URL_ATTRS:
            if SCRIPTY.match(clean_url(v)) or goes_out(v):
                out.append('html.remote_url')
        elif k in ('srcset', 'imagesrcset'):
            left = re.sub(r'data:image/(?:png|jpe?g|gif|webp)[;,][^\s]*', ' ', clean_url(v), flags=re.I)
            if IN_SRCSET.search(left):
                out.append('html.remote_srcset')
        elif k == 'style':
            out += css_hits(v)
        elif k.startswith('data-') and WEB_LIKE.match(clean_url(v)):
            out.append('html.data_attribute')
        elif name in ('animate', 'set') and k in ('to', 'from', 'by', 'values') and goes_out(v):
            out.append('html.animated_url')
    return out


def html_hits(text):
    """Every rule the page breaks, by count. The two tokenizer views are the two ways the page's markup can be read."""
    hits = Counter()
    seen_any = False
    for t in tokens(text, raw=True):
        seen_any = True
        kind = t[0]
        if kind == 'start':
            hits.update(tag_hits(t[1], t[2]))
        elif kind == 'comment':
            hits['html.comment'] += 1
        elif kind == 'pi':
            hits['html.processing_instruction'] += 1
        elif kind == 'raw' and t[2] == 'style':
            hits.update(css_hits(t[1]))
    for t in tokens(text, raw=False):
        if t[0] == 'start':
            for rule in tag_hits(t[1], t[2]):
                if rule not in hits:
                    hits[rule + '.in_raw_text'] += 1
    return hits, seen_any


def srcset_urls(v):
    return [u.rstrip(',') for u in re.findall(r'(\S+)(?:\s+[^,]*)?(?:,|$)', v or '')]


def local_refs(text):
    """What a person clicks or sees and the pack must hold: links, images and picture sources. Stylesheets and frames are not here: an absent one shows nothing broken."""
    for t in tokens(text, raw=True):
        if t[0] != 'start':
            continue
        name, attrs = t[1], t[2]
        for k, v in attrs:
            if (name in ('a', 'area') and k in ('href', 'xlink:href')) or (name in ('img', 'source') and k == 'src'):
                yield v or ''
            elif name in ('img', 'source') and k == 'srcset':
                yield from srcset_urls(v)


def target_of(ref, page):
    """The path in the library that a local reference names, or None if it names no file: a fragment, or an address that leaves."""
    if goes_out(ref) or INERT.match(clean_url(ref)):
        return None
    ref = urllib.parse.unquote(clean_url(ref).split('#')[0].split('?')[0]).replace('\\', '/').strip()
    if not ref:
        return None
    target = os.path.normpath(ref.lstrip('/') if ref.startswith('/') else os.path.join(os.path.dirname(page), ref)).replace('\\', '/')
    return None if target.startswith('..') else target


# ---------------------------------------------------------------- the scan ----
class Scan:
    def __init__(self, pack, terms, accepted, snapshot):
        self.pack, self.accepted, self.snapshot = pack, accepted, snapshot
        self.terms = [t.lower().encode() for t in terms]
        self.term_rx = re.compile(b'|'.join(re.escape(t) for t in self.terms), re.I) if self.terms else None
        self.fails = defaultdict(list)
        self.accepted_hits = defaultdict(list)
        self.listed = defaultdict(list)
        self.inspected = Counter()
        self.hashes = {}
        self.records = []
        self.size = None
        self.saved_pages = load_saved_pages()

    def fail(self, rule, path):
        if rule.startswith(ACCEPTABLE) and rule in self.accepted.get(path, ()):
            self.accepted_hits[rule].append(path)
        else:
            self.fails[rule].append(path)

    def list_only(self, rule, path):
        self.listed[rule].append(path)

    def term_lines(self, data):
        """The line numbers of the private words in these bytes. A word split by nothing and matched in any case."""
        if not self.term_rx:
            return set()
        return {self.terms.index(m.group(0).lower()) + 1 for m in self.term_rx.finditer(data)}

    def household(self, path, data):
        if HOUSEHOLD.search(data):
            self.fail('term.household', path)

    def owner_of(self, rel):
        """The record a text file belongs to, by its path: one accepted line covers a document, its text and its search rows."""
        return self.text_owner.get(rel, rel)

    def check_terms(self, rule, path, data):
        data = INLINE_PICTURE.sub(b'', data)      # a five-letter word turned up by chance in a picture's base64 on a real page
        for line in sorted(self.term_lines(data)):
            if f'term.{rule}' in self.accepted.get(path, ()):
                self.accepted_hits[f'term.{rule}'].append(path)
            else:
                self.fails[f'term.{rule}'].append(f'{path} (word on line {line} of the terms file)')

    # ---- every file, by name and kind of file
    def walk(self):
        out = []
        for root, dirs, files in os.walk(self.pack, followlinks=False):
            for d in list(dirs):
                p = Path(root) / d
                if p.is_symlink():
                    self.fail('file.symlink', p.relative_to(self.pack).as_posix())
                    dirs.remove(d)
            for f in files:
                out.append(Path(root) / f)
        return sorted(out)

    def name_rules(self, rel, st, is_link):
        parts = rel.split('/')
        name = parts[-1]
        low = name.lower()
        if is_link:
            self.fail('file.symlink', rel)
        if st.st_nlink > 1:
            self.fail('file.hard_link', rel)
        spec = SPEC['paths_excluded']
        for pat in spec['anywhere']:
            if fnmatch.fnmatchcase(low, pat.lower()):
                self.fail('file.excluded_name', rel)
        for pat in ('video-auth*', '*cookie*', '*.lock', '*.log'):
            if fnmatch.fnmatchcase(low, pat):
                self.fail('file.excluded_name', rel)
        if any(x.startswith('.') for x in parts[:-1]):
            self.fail('file.excluded_name', rel)
        self.check_terms('in_path', rel, rel.encode('utf-8', 'surrogateescape'))
        self.household(rel, rel.encode('utf-8', 'surrogateescape'))
        for s in parts:
            if s != s.rstrip('. ') or ':' in s or '\\' in s or s.split('.')[0].lower() in RESERVED or re.search(r'[<>"|?*\x00-\x1f]', s):
                self.fail('file.windows_refuses', rel)
                break
        if len(rel) > 200:
            self.fail('file.path_too_long', rel)
        if not self.allowed_place(parts, low):
            self.fail('file.not_allowed_here', rel)

    def allowed_place(self, parts, low):
        if len(parts) == 1:
            return low in ROOT_FILES
        if parts[0] == 'derived':
            return len(parts) == 3 and parts[1] == 'geo' and low in GEO_FILES
        if parts[0] != 'library-data':
            return False
        rest = parts[1:]
        if len(rest) == 1:
            return low in LIB_ROOT_FILES
        if '/'.join(parts) == ATLAS:
            return True
        exts = FOLDER_EXT.get(rest[0])
        if rest[0] == 'metadata' and rest[1] != 'videos':
            return False
        return exts is not None and os.path.splitext(low)[1] in exts

    def hash_file(self, path, rel):
        h = hashlib.sha256()
        with open(path, 'rb') as f:
            while chunk := f.read(1 << 22):
                h.update(chunk)
        self.hashes[rel] = h.hexdigest()

    def run(self):
        files = self.walk()
        if not files:
            self.fail('scan.read_nothing', '(no files in the pack)')
            return
        rels = []
        self.held = {p.relative_to(self.pack).as_posix().lower() for p in files}     # in any case: this disk and Windows both forgive a page's wrong case
        for p in files:
            rel = p.relative_to(self.pack).as_posix()
            rels.append(rel)
            try:
                st = os.lstat(p)
                self.name_rules(rel, st, p.is_symlink())
                if p.is_symlink():
                    continue
                self.hash_file(p, rel)
            except OSError as e:
                self.fail('scan.unreadable', f'{rel}: {e.__class__.__name__}')
        self.read_pack_files(rels)
        order = [r for r in rels if r not in self.done_early]
        for rel in order:
            p = self.pack / rel
            if p.is_symlink() or rel in self.unreadable():
                continue
            try:
                self.inspect(rel, p)
                self.inspected['files'] += 1
            except Exception as e:     # a file that cannot be read is never a file that passed
                self.fail('scan.unreadable', f'{rel}: {e.__class__.__name__}: {e}')
        self.check_manifest(rels)
        self.check_catalog(rels)
        if self.inspected['files'] + len(self.done_early) != len([r for r in rels if not (self.pack / r).is_symlink()]):
            self.fail('scan.not_every_file_read', f"{self.inspected['files'] + len(self.done_early)} read of {len(rels)}")
        on_disk = Counter(KIND_OF_EXT.get(os.path.splitext(r.lower())[1]) for r in order)
        for kind, n in on_disk.items():
            if kind and kind != 'map' and self.inspected[kind] != n:
                self.fail('scan.not_every_file_read', f'{kind}: {self.inspected[kind]} read of {n}')

    def unreadable(self):
        return {x.split(':')[0] for x in self.fails.get('scan.unreadable', [])}

    done_early = ()
    text_owner = {}

    def read_pack_files(self, rels):
        """The files every other check needs. Without them the scan cannot say anything, so that is a failure, not a skip."""
        self.done_early = set()
        info = self.load_json('pack.json', rels, 'pack')
        if isinstance(info, dict):
            self.size = info.get('size')
            self.info = info
            unknown = set(info) - PACK_FIELDS
            if unknown:
                self.fail('pack.field_not_allowed', 'pack.json')
            if self.size not in SIZE_NAMES:
                self.fail('pack.unknown_size', 'pack.json')
            if info.get('incomplete') != 0:
                self.fail('pack.incomplete', 'pack.json')
        else:
            self.info = {}
            self.fail('pack.missing', 'pack.json')
        cat = self.load_json('library-data/catalog.json', rels, 'catalog')
        if isinstance(cat, list) and cat and all(isinstance(r, dict) for r in cat):
            self.records = cat
            self.text_owner = {f"library-data/{r['text_path']}": f"library-data/{r.get('path')}" for r in cat if isinstance(r.get('text_path'), str)}
        else:
            self.fail('catalog.missing_or_empty', 'library-data/catalog.json')
        summary = self.load_json('library-data/summary.json', rels, 'summary')
        if not isinstance(summary, dict) or set(summary) - SUMMARY_FIELDS:
            self.fail('summary.fields', 'library-data/summary.json')
        status = 'derived/geo/national-status.json'
        if status in rels:
            s = self.load_json(status, rels, 'status')
            if not isinstance(s, dict) or set(s) - {'state', 'stage', 'features'}:
                self.fail('status.fields', status)

    def load_json(self, rel, rels, _kind):
        if rel not in rels:
            return None
        self.done_early.add(rel)
        data = (self.pack / rel).read_bytes()
        self.check_terms('own_json', rel, data)
        if rel != 'library-data/catalog.json':     # the catalog is read record by record, below
            self.household(rel, data)
        if USER_PATH.search(data):
            self.fail('own.user_path', rel)
        if LAN.search(data):
            self.fail('own.lan_address', rel)
        try:
            return json.loads(data)
        except ValueError:
            self.fail('scan.unreadable', f'{rel}: not JSON')
            return None

    def inspect(self, rel, p):
        low = rel.lower()
        ext = os.path.splitext(low)[1]
        if ext in ('.html', '.htm'):
            self.inspect_html(rel, p)
        elif ext == '.css':
            data = p.read_bytes()
            for rule in set(css_hits(data.decode('utf-8', 'replace'))):
                self.fail(rule, rel)
            self.check_terms('css', rel, data)
        elif ext == '.svg':
            self.inspect_svg(rel, p)
        elif ext == '.pdf':
            self.inspect_pdf(rel, p)
        elif ext == '.mp4':
            self.inspect_mp4(rel, p)
        elif ext == '.zim':
            self.inspect_zim(rel, p)
        elif ext == '.sqlite':
            if rel == 'library-data/search.sqlite':
                self.inspect_search(rel, p)
            else:
                self.inspect_map(rel, p)
        elif ext == '.pptx':
            self.inspect_pptx(rel, p)
        elif ext in ('.txt', '.vtt', '.tsv', '.json'):
            data = p.read_bytes()
            self.check_terms('text', rel, data)
            self.household(self.owner_of(rel), data)
        elif ext in IMAGES or ext in ('.ttf', '.woff', '.woff2', '.otf'):
            with open(p, 'rb') as f:
                self.check_terms('image_head', rel, f.read(65536))
        else:
            self.fail('file.unknown_type', rel)

    def inspect_html(self, rel, p):
        data = p.read_bytes()
        self.inspected['html'] += 1
        if data[:2] in (b'\xff\xfe', b'\xfe\xff') or data[:512].count(b'\0') > 64:
            self.fail('html.utf16', rel)
            return
        self.check_terms('html', rel, data)
        text = data.decode('utf-8', 'replace')
        self.check_terms('html', rel, html.unescape(text).encode('utf-8', 'surrogateescape'))
        self.household(rel, data)
        self.household(rel, html.unescape(text).encode('utf-8', 'surrogateescape'))
        hits, any_tokens = html_hits(text)
        if not any_tokens:
            self.fail('html.empty', rel)
        for rule in hits:
            self.fail(rule, rel)
        for ref in local_refs(text):
            target = target_of(ref, rel.removeprefix('library-data/'))
            if target and f'library-data/{target}'.lower() not in self.held and f'library-data/{target}/index.html'.lower() not in self.held:
                self.fail('page.dead_reference', rel)
                break

        def read_local(src):
            try:
                target = (p.parent / src).resolve()
                return target.read_bytes() if str(target).startswith(str(self.pack.resolve())) else None
            except OSError:
                return None
        served = self.saved_pages.rewrite(data, read_local).decode('utf-8', 'replace')
        again, _ = html_hits(served)
        for rule in again:
            if rule not in hits and rule + '.in_raw_text' not in hits:
                self.fail('served.' + rule, rel)

    def inspect_svg(self, rel, p):
        data = p.read_bytes()
        self.inspected['svg'] += 1
        self.check_terms('svg', rel, data)
        self.household(rel, data)
        text = data.decode('utf-8', 'replace')
        if re.search(r'<!ENTITY|<!DOCTYPE[^>]*\[', text, re.I):
            self.fail('svg.entity', rel)
        for t in tokens(text, raw=False):
            if t[0] != 'start':
                continue
            name, attrs = t[1], t[2]
            if name == 'script':
                self.fail('svg.script', rel)
            if name == 'foreignobject':
                self.fail('svg.foreign_object', rel)
            for k, v in attrs:
                if k.startswith('on') and len(k) > 2:
                    self.fail('svg.event_attribute', rel)
                elif k in ('href', 'xlink:href', 'src') and goes_out(v):
                    self.fail('svg.external_href', rel)
                elif k == 'style':
                    for rule in css_hits(v or ''):
                        self.fail('svg.' + rule, rel)
        for m in re.finditer(r'<style\b[^>]*>(.*?)</style', text, re.I | re.S):
            for rule in css_hits(m.group(1)):
                self.fail('svg.' + rule, rel)

    def inspect_pdf(self, rel, p):
        data = p.read_bytes()
        self.inspected['pdf'] += 1
        readable, encrypted = pdf_views(data)
        for marker, rule in PDF_FAIL:
            if marker.search(readable) or (rule in PDF_LONG and marker.search(data)):
                self.fail(rule, rel)
        if PDF_ADDRESS.search(readable) or (encrypted and pdf_page_links(data)):
            self.fail('pdf.web_link', rel)
        for marker, rule in PDF_LIST:
            if marker.search(readable):
                self.list_only(rule, rel)
        if encrypted:
            self.list_only('pdf.encrypted_not_fully_read', rel)
        self.check_terms('pdf', rel, readable)

    def inspect_mp4(self, rel, p):
        """Tags live in atoms beside the picture. The picture is hashed and not read: a short word turns up by chance in hundreds of GB of compressed data."""
        self.inspected['video'] += 1
        size = p.stat().st_size
        seen = 0
        with open(p, 'rb') as f:
            pos = 0
            while pos + 8 <= size:
                f.seek(pos)
                head = f.read(16)
                n, kind = struct.unpack('>I4s', head[:8])
                skip = 8
                if n == 1:
                    n = struct.unpack('>Q', head[8:16])[0]
                    skip = 16
                elif n == 0:
                    n = size - pos
                if n < skip:
                    self.fail('video.bad_atoms', rel)
                    break
                seen += 1
                if kind != b'mdat':
                    f.seek(pos + skip)
                    self.check_terms('video_tags', rel, f.read(min(n - skip, 1 << 28)))
                pos += n
        if not seen:
            self.fail('video.bad_atoms', rel)

    def inspect_zim(self, rel, p):
        self.inspected['zim'] += 1
        self.fail('zim.not_accepted', rel)

    def inspect_pptx(self, rel, p):
        self.inspected['pptx'] += 1
        with zipfile.ZipFile(p) as z:
            for name in z.namelist():
                if name.lower().endswith('vbaproject.bin'):
                    self.fail('pptx.macro', rel)
                if name.startswith('docProps/') and name.endswith('.xml'):
                    self.check_terms('pptx', rel, z.read(name))
                if name.endswith('.rels') and re.search(rb"""TargetMode\s*=\s*["']External["']""", z.read(name), re.I):
                    self.fail('pptx.external_link', rel)   # a link to the web: owner decision A, the build takes these out

    def inspect_search(self, rel, p):
        data = p.read_bytes()
        self.inspected['search'] += 1
        self.check_terms('search', rel, data)
        if data[18:20] != b'\x01\x01':
            self.fail('search.not_journal_delete', rel)
        del data
        db = sqlite3.connect(f'file:{p}?immutable=1', uri=True)
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            self.fail('search.integrity', rel)
        if db.execute('PRAGMA freelist_count').fetchone()[0]:
            self.fail('search.free_pages', rel)
        # The format a pack is meant to have is the one the spec asks for. build_packs.py makes the table with exactly this statement, and SQLite keeps it word for word and reads the
        # tokenizer from it each time the file is opened, so the statement itself is compared and nothing in it is run or worked out. An index from before the tokenizer changed
        # fails here once the spec asks for the new one, and passes against the spec it was built from.
        made = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='pages'").fetchone()
        if not made or made[0] != 'CREATE VIRTUAL TABLE pages USING ' + SPEC['search_index']['schema']:
            self.fail('search.schema_differs', rel)
        ids = {x for (x,) in db.execute('SELECT DISTINCT doc_id FROM pages')}
        rows = db.execute('SELECT count(*) FROM pages').fetchone()[0]
        where = {r.get('id'): f"library-data/{r.get('path')}" for r in self.records}
        for d, title, coll, cat, path, body in db.execute('SELECT doc_id,title,collection,category,path,body FROM pages'):
            if HOUSEHOLD.search('\n'.join(str(x) for x in (d, title, coll, cat, path)).encode('utf-8', 'surrogateescape')):
                self.fail('term.household', f'{rel}: {d}')        # our own fields: never excused
            elif body and HOUSEHOLD.search(body.encode('utf-8', 'surrogateescape')):
                self.household(where.get(d, f'{rel}: {d}'), body.encode('utf-8', 'surrogateescape'))
        db.close()
        if not rows:
            self.fail('search.no_rows', rel)
        by = {r.get('id'): r for r in self.records}
        for i in ids - set(by):
            self.fail('search.row_not_in_catalog', f'{rel}: {i}')
        for i in ids:
            if by.get(i, {}).get('kind') == 'metadata':
                self.fail('search.metadata_row', f'{rel}: {i}')

    def inspect_map(self, rel, p):
        self.inspected['map'] += 1
        with open(p, 'rb') as f:
            head = f.read(100)
        if head[:16] != b'SQLite format 3\0':
            self.fail('map.not_sqlite', rel)
            return
        if head[18:20] != b'\x01\x01':
            self.fail('map.not_journal_delete', rel)
        self.raw_paths(rel, p)
        db = sqlite3.connect(f'file:{p}?immutable=1', uri=True)
        shadow = {n for (n,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND sql LIKE 'CREATE VIRTUAL%'")}
        tables = [n for (n,) in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        for (sql,) in db.execute('SELECT sql FROM sqlite_master WHERE sql IS NOT NULL'):
            self.check_terms('map', rel, sql.encode())
        for t in tables:
            if any(t.startswith(s + '_') for s in shadow) or t in shadow:
                continue
            cols = [c[1] for c in db.execute(f'PRAGMA table_info("{t}")')]
            if t in ('meta', 'metadata', 'done', 'done_socal'):
                for row in db.execute(f'SELECT * FROM "{t}"'):
                    for x in row:
                        if isinstance(x, str):
                            self.check_terms('map', rel, x.encode('utf-8', 'surrogateescape'))
            for c in cols:
                if c in ('source', 'origin'):
                    for (x,) in db.execute(f'SELECT DISTINCT "{c}" FROM "{t}"'):
                        if isinstance(x, str):
                            self.check_terms('map', rel, x.encode('utf-8', 'surrogateescape'))
            for c in cols:
                if c in ('name', 'detail') and self.term_rx and t in ('place', 'resource', 'poi', 'feat'):
                    for (x,) in db.execute(f'SELECT "{c}" FROM "{t}" WHERE "{c}" IS NOT NULL'):
                        if isinstance(x, str) and self.term_lines(x.encode('utf-8', 'surrogateescape')):
                            self.list_only('map.word_in_a_place_name', f'{rel}: {t}.{c}')
        db.close()

    def raw_paths(self, rel, p):
        """A local path holding a private word, anywhere in the raw bytes: an updated row's old value stays in the page's free space, where no query sees it. Words alone are not
        enough here: short ones turn up by chance in tiles and as real street names."""
        with open(p, 'rb') as f:
            tail = b''
            while chunk := f.read(1 << 26):
                data = tail + chunk
                for m in USER_PATH.finditer(data):
                    if self.term_lines(data[m.start():m.start() + 200]):
                        self.fail('map.private_path_in_raw_bytes', rel)
                        return
                tail = data[-256:]

    # ---- across files
    def check_manifest(self, rels):
        rel = 'pack-manifest.tsv'
        if rel not in rels:
            self.fail('manifest.missing', rel)
            return
        lines = (self.pack / rel).read_text(encoding='utf-8', errors='surrogateescape').splitlines()[1:]
        if not lines:
            self.fail('manifest.empty', rel)
            return
        listed = {}
        for line in lines:
            parts = line.split('\t')
            listed[parts[0]] = parts
        on_disk = set(rels) - {rel}
        for x in on_disk - set(listed):
            self.fail('manifest.file_not_listed', x)
        for x in set(listed) - on_disk:
            self.fail('manifest.listed_file_absent', x)
        for x, parts in listed.items():
            if x in on_disk and self.hashes.get(x) != parts[2]:
                self.fail('manifest.hash_differs', x)

    def check_catalog(self, rels):
        if not self.records:
            return
        rel = 'library-data/catalog.json'
        have = set(rels)
        allowed = set(SPEC['catalog_fields_allowed'])
        ref = self.reference_catalog()
        verdicts = json.loads((PROJECT / SPEC['sources']['verdicts']).read_text(encoding='utf-8'))
        flagged = set(SPEC['video_filters']['flagged_28']['ids'])
        excluded = self.exclusions()
        sources_id = SPEC['sources_page']['record']['id']
        small_or_medium = self.size in ('small', 'medium')
        paths = {r.get('path') for r in self.records}
        for path in SPEC['known_gap_documents']:
            if path in paths or f'library-data/{path}' in have:
                self.fail('catalog.known_gap_present', path)
        for r in self.records:
            i = r.get('id')
            kind = r.get('kind')
            for k in r:
                if k not in allowed:
                    self.fail('catalog.field_not_allowed', f'{i}: {k}')
            for k in ('path', 'text_path', 'video_path', 'vtt_path', 'thumbnail_path'):
                v = r.get(k)
                if v and f'library-data/{v}' not in have:
                    if not (k == 'video_path' and kind == 'transcript' and not v):
                        self.fail('catalog.named_file_absent', f'{i}: {k}')
            for c in r.get('captions') or []:
                if f'library-data/{c}' not in have:
                    self.fail('catalog.named_file_absent', f'{i}: captions')
            if i == sources_id:
                continue
            base = ref.get(i) or ref.get(self.snapshot_id(i))
            if ref and base is None and not self.course_record(r, ref):
                self.fail('catalog.not_in_snapshot', i)
            if kind != 'metadata' and not str(r.get('publisher') or '').strip():
                self.fail('credit.publisher_missing', i)
            if str(r.get('publisher') or '').strip().lower() in PLACEHOLDER_OWNERS:
                self.fail('credit.placeholder_owner', i)
            if base and base.get('publisher') != r.get('publisher') and base.get('publisher') != 'See source':
                self.fail('credit.publisher_changed', i)
            if kind == 'transcript' and not r.get('video_path'):
                self.fail('catalog.transcript_with_no_video', i)
            if any(HOUSEHOLD.search(v.encode('utf-8', 'surrogateescape')) for v in r.values() if isinstance(v, str)) or any(HOUSEHOLD.search(str(c).encode()) for c in r.get('captions') or []):
                self.fail('term.household', f'{rel}: {i}')        # our own fields: never excused
            if base and base.get('source_url') and base.get('source_url') != r.get('source_url') and kind != 'metadata':
                self.fail('credit.source_changed', i)
            if kind == 'video' or (kind == 'metadata' and r.get('video_id')):
                vid = i if kind == 'video' else r.get('video_id')
                vr = verdicts.get(vid) or {}
                if vid in flagged or vr.get('dangerous'):
                    self.fail('member.flagged_video', vid)
                if vid in excluded:
                    self.fail('member.owner_removed', vid)
                if kind == 'video':
                    if not vr:
                        self.fail('member.no_verdict', vid)
                    elif vr.get('verdict') not in ('keep', 'reference'):
                        self.fail('member.dropped_video', vid)
            if kind == 'video' and self.size == 'corporals-corner' and r.get('publisher') != 'Corporals Corner':
                self.fail('member.not_this_add_on', i)
            if kind == 'video' and self.size == 'firearms-hunting' and r.get('category') not in ('firearm-safety-maintenance', 'hunting-game-processing'):
                self.fail('member.not_this_add_on', i)
            if small_or_medium:
                if r.get('publisher') == 'Corporals Corner':
                    self.fail('member.corporals', i)
                if kind in ('video', 'metadata', 'transcript') and r.get('category') in ('firearm-safety-maintenance', 'hunting-game-processing'):
                    self.fail('member.firearms', i)
                if i in SPEC['video_filters']['firearms_documents']:
                    self.fail('member.firearms', i)
            if kind in ('video', 'zim'):
                want = (base or {}).get('sha256') or r.get('sha256')
                if self.hashes.get(f"library-data/{r.get('path')}") != want:
                    self.fail(f'{kind}.hash_differs', r.get('path'))
            elif kind != 'metadata' and r.get('sha256') and self.hashes.get(f"library-data/{r.get('path')}") != r['sha256']:
                self.fail('catalog.hash_differs', r.get('path'))
        named = set()
        for r in self.records:
            named |= {f'library-data/{r[k]}' for k in ('path', 'text_path', 'vtt_path', 'thumbnail_path') if r.get(k)}
            named |= {f'library-data/{c}' for c in r.get('captions') or []}
        for x in have - named:
            top = x.split('/')[1] if x.startswith('library-data/') else ''
            if top in ('videos', 'videos-external', 'transcripts', 'text', 'metadata', 'collections') or (top == 'documents' and x.lower().endswith(('.pdf', '.pptx', '.txt'))):
                self.fail('member.file_no_record_names', x)
        ids = {r.get('id') for r in self.records}
        if sources_id not in ids or SPEC['sources_page']['path'] not in have:
            self.fail('credit.sources_page_missing', rel)
        else:
            page = html.unescape((self.pack / SPEC['sources_page']['path']).read_text(encoding='utf-8', errors='replace'))
            for pub in {r.get('publisher') for r in self.records if r.get('kind') in ('pdf', 'html', 'pptx', 'video', 'zim') and r.get('id') != sources_id}:
                if pub and pub not in page:
                    self.fail('credit.owner_not_on_sources_page', pub)

    @staticmethod
    def snapshot_id(i):
        for new, old in ID_BACK.items():
            if str(i).startswith(new):
                return old + i[len(new):]
        return i

    def course_record(self, r, ref):
        """A record the build makes so a course's pages can be reached: course-<folder>, its home page, the publisher of that folder's own records."""
        m = re.fullmatch(r'course-([a-z0-9][a-z0-9-]*)', str(r.get('id')))
        if not m or r.get('kind') != 'html' or r.get('path') != f'courses/{m.group(1)}/index.html':
            return False
        if getattr(self, '_course_owner', None) is None:
            self._course_owner = defaultdict(set)
            for x in ref.values():
                parts = str(x.get('path')).split('/')
                if parts[0] == 'courses' and len(parts) > 2:
                    self._course_owner[parts[1]].add(x.get('publisher'))
        return r.get('publisher') in self._course_owner.get(m.group(1), set())

    def reference_catalog(self):
        name = self.info.get('snapshot')
        base = self.snapshot or (PROJECT / 'derived/packs/snapshot' / name if name else None)
        p = base / 'catalog.json' if base else None
        if not p or not p.exists():
            self.fail('catalog.no_snapshot_to_compare', str(name))
            return {}
        return {r['id']: r for r in json.loads(p.read_text(encoding='utf-8'))}

    def exclusions(self):
        name = self.info.get('snapshot')
        base = self.snapshot or (PROJECT / 'derived/packs/snapshot' / name if name else None)
        p = base / 'video-exclusions.json' if base else None
        return set(json.loads(p.read_text(encoding='utf-8')).get('videos', {})) if p and p.exists() else set()


# ---------------------------------------------------------------- PDF ----
def pdf_rx(name):
    return re.compile(rb'/' + name + rb'(?![A-Za-z0-9])')


PDF_FAIL = [(pdf_rx(n.encode()), f'pdf.{n.lower()}') for n in ('JavaScript', 'Launch', 'SubmitForm', 'ImportData', 'GoToE', 'RichMedia', 'XFA', 'EmbeddedFile')]     # not /JS: an action that runs a script always also says /JavaScript, while /JS alone was base64 in thumbnails, chance bytes and a text setting in 20 real PDFs
PDF_LONG = {'pdf.javascript', 'pdf.submitform', 'pdf.importdata', 'pdf.richmedia'}   # too long to match by chance, so these are also looked for in the raw bytes
PDF_LIST = [(pdf_rx(n.encode()), f'pdf.listed.{n.lower()}') for n in ('OpenAction', 'GoToR', 'URI')]
PDF_ADDRESS = re.compile(rb'/(?:URI|Base)(?![A-Za-z0-9])\s*(?:\((?!\s*\))|<(?!<)\s*[^\s>]|\d+\s+\d+\s+R)')   # a link's address that is not empty, or one held elsewhere: the build empties them all (owner, 2026-11-03)
STREAM = re.compile(rb'(?<![A-Za-z])stream\r?\n')
NAME_ESCAPE = re.compile(rb'#([0-9a-fA-F]{2})')


def pdf_page_links(data):
    """Page links with an address, as pdfium reads them: the only way into an encrypted file's object streams."""
    import ctypes
    import pypdfium2 as pdfium
    import pypdfium2.raw as raw
    found = 0
    try:
        doc = pdfium.PdfDocument(data)
    except pdfium.PdfiumError:
        return 0
    for i in range(len(doc)):
        page = doc[i]
        pos, link = ctypes.c_int(0), raw.FPDF_LINK()
        while raw.FPDFLink_Enumerate(page.raw, ctypes.byref(pos), ctypes.byref(link)):
            act = raw.FPDFLink_GetAction(link)
            if act and raw.FPDFAction_GetType(act) == raw.PDFACTION_URI:
                n = raw.FPDFAction_GetURIPath(doc.raw, act, None, 0)
                buf = ctypes.create_string_buffer(max(n, 1))
                raw.FPDFAction_GetURIPath(doc.raw, act, buf, n)
                found += bool(buf.value.strip())
        page.close()
    doc.close()
    return found


def pdf_views(data):
    """(everything a PDF reader parses as objects, whether some of it could not be read). Compressed page contents are left out: short markers match them by chance.
    Object streams are inflated, unfiltered streams such as XMP are kept, and #xx in names is decoded, since /J#61vaScript is /JavaScript."""
    parts, pos, unreadable = [], 0, False
    for m in STREAM.finditer(data):
        if m.start() < pos:
            continue
        end = data.find(b'endstream', m.end())
        if end < 0:
            break
        head = data[max(pos, m.start() - 2048):m.start()]
        head = head[head.rfind(b' obj'):] if b' obj' in head else head
        parts.append(data[pos:m.start()])
        body = data[m.end():end]
        norm = NAME_ESCAPE.sub(lambda x: bytes([int(x.group(1), 16)]), head)
        if b'/ObjStm' in norm:
            try:
                parts.append(zlib.decompress(body) if b'/FlateDecode' in norm else body)
            except zlib.error:
                try:
                    parts.append(zlib.decompressobj().decompress(body))
                except zlib.error:
                    unreadable = True
        elif b'/Filter' not in norm:
            parts.append(body)
        pos = end + 9
    parts.append(data[pos:])
    return NAME_ESCAPE.sub(lambda x: bytes([int(x.group(1), 16)]), b'\n'.join(parts)), unreadable or b'/Encrypt' in data


def load_saved_pages():
    spec = importlib.util.spec_from_file_location('saved_pages', PROJECT / 'engine' / 'saved_pages.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_terms(path):
    """A missing or empty terms file is a failed scan: with no words to look for it would pass anything."""
    if not path or not Path(path).exists():
        return None
    return [t.strip() for t in Path(path).read_text(encoding='utf-8').splitlines() if t.strip() and not t.startswith('#')] or None


def read_accepted(path):
    """path -> the rules accepted for it. path, reason, who and rules (comma-separated): all four, or the line counts for nothing."""
    if not path or not Path(path).exists():
        return {}
    out = {}
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        parts = line.split('\t')
        if len(parts) >= 4 and all(x.strip() for x in parts[:4]) and not line.startswith('#'):
            out.setdefault(parts[0].strip(), set()).update(r.strip() for r in parts[3].split(',') if r.strip())
    return out


def report(scan, report_path):
    total = sum(len(v) for v in scan.fails.values())
    out = {'pack': str(scan.pack), 'result': 'FAIL' if total else 'PASS', 'failures': total, 'inspected': dict(scan.inspected),
           'rules': {k: {'count': len(v), 'paths': sorted(set(v))} for k, v in sorted(scan.fails.items())},
           'accepted': {k: sorted(set(v)) for k, v in sorted(scan.accepted_hits.items())},
           'listed': {k: {'count': len(v), 'paths': sorted(set(v))[:50]} for k, v in sorted(scan.listed.items())}}
    if report_path:
        Path(report_path).write_text(json.dumps(out, indent=1), encoding='utf-8')
    print(f"{out['result']}: {total} failures. Read: {dict(scan.inspected)}")
    for k, v in sorted(scan.fails.items()):
        print(f'  {k}: {len(v)}  e.g. {sorted(set(v))[:3]}')
    for k, v in sorted(scan.accepted_hits.items()):
        print(f'  accepted {k}: {len(v)}')
    for k, v in sorted(scan.listed.items()):
        print(f'  listed {k}: {len(v)}')
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('pack')
    ap.add_argument('--terms', default=str(PROJECT / 'derived/packs/private-terms.txt'))
    ap.add_argument('--accepted', default=str(PROJECT / 'derived/packs/scan-accepted.tsv'))
    ap.add_argument('--snapshot')
    ap.add_argument('--report')
    args = ap.parse_args(argv)
    os.nice(10)
    pack = Path(args.pack)
    terms = read_terms(args.terms)
    if not pack.is_dir():
        print(f'FAIL: no pack at {pack}')
        return 1
    if not terms:
        print('FAIL: no terms file, or it is empty: nothing to compare the pack with')
        return 1
    scan = Scan(pack, terms, read_accepted(args.accepted), Path(args.snapshot) if args.snapshot else None)
    scan.run()
    out = report(scan, args.report)
    if out['result'] == 'PASS' and not scan.inspected['files']:
        print('FAIL: nothing was read')
        return 1
    return 1 if out['failures'] else 0


def guarded_main(argv=None):
    try:
        return main(argv)
    except Exception:       # a crash is never a pass
        traceback.print_exc()
        print('FAIL: the scan crashed')
        return 1


if __name__ == '__main__':
    sys.exit(guarded_main())
