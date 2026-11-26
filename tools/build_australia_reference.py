#!/usr/bin/env python3
"""Build the reviewed Australian text supplement, entirely offline.

    python3 -B tools/build_australia_reference.py --output /path/to/new/LastbookData

Creates a separate, searchable reference library. Never modifies an installed library,
downloads anything, or claims to be an official Setup pack. See docs/AUSTRALIA-CONTENT.md.
"""
import argparse
from contextlib import closing
import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / 'content/regions/au'
SCHEMA = 'fts5(doc_id UNINDEXED,title,collection,category,path UNINDEXED,page UNINDEXED,body,tokenize="unicode61")'
ALLOWED = {'html', 'head', 'meta', 'title', 'body', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
           'p', 'ul', 'ol', 'li', 'strong', 'em', 'b', 'i', 'table', 'thead', 'tbody', 'tr',
           'th', 'td', 'caption', 'blockquote', 'dl', 'dt', 'dd', 'br', 'sup', 'sub', 'hr', 'a', 'bdi'}
VERBATIM_START = '<!-- unchanged-source:start -->'
VERBATIM_END = '<!-- unchanged-source:end -->'


class SourceText(HTMLParser):
    """Text projection for a reviewed unchanged excerpt; no wording normalization."""
    BLOCKS = {'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'ul', 'ol', 'dl', 'dt', 'dd',
              'table', 'tr', 'th', 'td', 'blockquote', 'br', 'hr'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in self.BLOCKS:
            self.parts.append('\n')

    handle_startendtag = handle_starttag

    def handle_endtag(self, tag):
        if tag in self.BLOCKS:
            self.parts.append('\n')

    def handle_data(self, data):
        self.parts.append(data)


def source_text(html):
    p = SourceText(); p.feed(html); p.close()
    # Only whitespace layout changes. Case, punctuation, spelling and wording stay.
    return re.sub(r'\s+', ' ', ''.join(p.parts)).strip()


def check_verbatim(record, data, source_dir):
    """ND is accepted only with an explicit, separately reviewed unchanged-body audit."""
    name = record.get('verbatim_audit', '')
    if record.get('reuse_mode') != 'unchanged-source-text' or not isinstance(name, str) or not name or Path(name).name != name or '\\' in name:
        raise ValueError('No-derivatives source needs an unchanged-text audit: ' + record['id'])
    audit = json.loads((source_dir / name).read_text(encoding='utf-8'))
    if not isinstance(audit, dict) or not isinstance(audit.get('records'), dict):
        raise ValueError('Invalid unchanged-source audit: ' + record['id'])
    entry = audit.get('records', {}).get(record['id'])
    if not isinstance(entry, dict) or entry.get('license') != record['license'] or \
            entry.get('source_url') != record.get('source_url') or entry.get('raw_sha256') != record.get('raw_sha256'):
        raise ValueError('Unchanged-source provenance does not match: ' + record['id'])
    html = data.decode('utf-8')
    if html.count(VERBATIM_START) != 1 or html.count(VERBATIM_END) != 1 or html.index(VERBATIM_START) >= html.index(VERBATIM_END):
        raise ValueError('Unchanged-source body markers are missing or ambiguous: ' + record['id'])
    body = html.split(VERBATIM_START, 1)[1].split(VERBATIM_END, 1)[0]
    text = source_text(body)
    if digest(body.encode('utf-8')) != entry.get('reader_body_sha256') or text != entry.get('source_text') or \
            digest(text.encode('utf-8')) != entry.get('source_text_sha256'):
        raise ValueError('No-derivatives source body changed; a new source/reuse review is required: ' + record['id'])


class Page(HTMLParser):
    """Reject active content; index the same source text that the reader opens."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag not in ALLOWED:
            raise ValueError('Unexpected HTML element: ' + tag)
        for name, value in attrs:
            if tag == 'a' and name == 'href':
                if not value or not value.startswith('/pages/au/') or '?' in value or '#' in value:
                    raise ValueError('Only local supplement links are allowed')
                if '..' in value or '\\' in value:
                    raise ValueError('Invalid local link')
                self.links.append(value.lstrip('/'))
            elif name == 'dir':
                if value not in {'ltr', 'rtl', 'auto'}:
                    raise ValueError('Invalid text direction')
            elif tag == 'ol' and name == 'type':
                if value not in {'1', 'a', 'A', 'i', 'I'}:
                    raise ValueError('Invalid ordered-list numbering')
            elif name not in {'lang', 'charset', 'rowspan', 'colspan', 'start'}:
                raise ValueError('Unexpected HTML attribute: ' + name)
        self.text.append('\n')

    handle_startendtag = handle_starttag

    def handle_endtag(self, tag):
        self.text.append('\n')

    def handle_data(self, data):
        self.text.append(data)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def checked_sources(source_dir=SOURCES):
    manifest = json.loads((source_dir / 'manifest.json').read_text(encoding='utf-8'))
    checked, ids, paths = [], set(), set()
    for entry in manifest['sources']:
        r = dict(entry)
        if r['id'] in ids or r['path'] in paths:
            raise ValueError('Duplicate source id or path')
        ids.add(r['id']); paths.add(r['path'])
        for key in ('snapshot', 'path'):
            p = Path(r[key])
            if p.is_absolute() or '..' in p.parts or '\\' in str(p):
                raise ValueError('Invalid source path')
        if not r['path'].startswith('pages/au/'):
            raise ValueError('Source is outside the supplement')
        data = (source_dir / r['snapshot']).read_bytes()
        if len(data) != r['bytes'] or digest(data) != r['sha256']:
            raise ValueError('Snapshot changed; review and update manifest: ' + r['id'])
        if r['license'] == 'CC-BY-ND-4.0':
            check_verbatim(r, data, source_dir)
        elif r['license'] not in {'CC-BY-4.0', 'CC-BY-3.0-AU', 'CC0-1.0'}:
            raise ValueError('Source needs redistribution permission: ' + r['id'])
        page = Page(); page.feed(data.decode('utf-8')); page.close()
        body = ''.join(page.text).strip()
        if len(body) < 150:
            raise ValueError('Source text is missing: ' + r['id'])
        checked.append((r, data, body, page.links))
    for r, _, _, links in checked:
        if any(link not in paths for link in links):
            raise ValueError('Unbundled local link: ' + r['id'])
    return manifest, checked


def build(output, source_dir=SOURCES):
    output = Path(output).absolute()
    if output.exists():
        raise ValueError('Output already exists; choose a new folder')
    manifest, sources = checked_sources(source_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Build beside the destination, then rename a complete folder into place.
    staging = Path(tempfile.mkdtemp(prefix='.au-reference-', dir=output.parent))
    try:
        lib = staging / 'library-data'; lib.mkdir()
        (lib / 'text').mkdir()
        records = []
        with closing(sqlite3.connect(lib / 'search.sqlite')) as db:
            db.execute('CREATE VIRTUAL TABLE pages USING ' + SCHEMA)
            for r, data, body, _ in sources:
                path = lib / r['path']; path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                text_path = 'text/' + r['id'] + '.txt'
                (lib / text_path).write_text(body, encoding='utf-8')
                record = {k: v for k, v in r.items() if k not in {'snapshot', 'raw_sha256'}}
                record.update(text_path=text_path, searchability='text')
                records.append(record)
                db.execute('INSERT INTO pages VALUES(?,?,?,?,?,?,?)',
                           (r['id'], r['title'], r['collection'], r['category'], r['path'], 1, body))
            db.commit()
            if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('Search index integrity check failed')
        (lib / 'catalog.json').write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (lib / 'summary.json').write_text(json.dumps({'resources': len(records), 'web_pages': len(records),
            'indexed_units': len(records), 'extraction_errors': [], 'missing_files': [],
            'document_bytes': sum(r['bytes'] for r in records)}, indent=2) + '\n', encoding='utf-8')
        (staging / 'AUSTRALIA-REFERENCE.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        files = sorted(p for p in staging.rglob('*') if p.is_file())
        receipt = 'path\tbytes\tsha256\n' + ''.join(
            f'{p.relative_to(staging).as_posix()}\t{p.stat().st_size}\t{digest(p.read_bytes())}\n' for p in files)
        (staging / 'AUSTRALIA-SHA256SUMS.tsv').write_text(receipt, encoding='utf-8')
        staging.rename(output)
    except BaseException:
        shutil.rmtree(staging)
        raise
    return len(records)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', required=True, type=Path)
    args = ap.parse_args()
    try:
        print(f'{build(args.output)} Australian references built offline')
    except (OSError, ValueError, KeyError) as e:
        ap.exit(1, str(e) + '\n')


if __name__ == '__main__':
    main()
