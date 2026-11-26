#!/usr/bin/env python3
"""Build a separate PERSONAL-USE-ONLY ANZCOR reference library.

    python3 -B tools/build_au_personal_first_aid.py --download --output /new/LastbookData

This is a build-time tool, not app/runtime download code. It downloads unchanged
originals only on request, or reads --pdf-cache without a connection. It never
modifies an installed library, creates a redistributable pack, or grants rights
to share the PDFs. See docs/AUSTRALIA-PERSONAL-FIRST-AID.md.
"""
import argparse
from contextlib import closing
import hashlib
import html
import json
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'content/regions/au/personal-sources.json'
MAX_PDF = 10_000_000
SCHEMA = 'fts5(doc_id UNINDEXED,title,collection,category,path UNINDEXED,page UNINDEXED,body,tokenize="unicode61")'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def allowed_url(url):
    u = urllib.parse.urlsplit(url)
    if u.scheme != 'https' or u.hostname != 'www.anzcor.org' or u.username or u.password or u.port:
        raise ValueError('Personal source must use the official ANZCOR HTTPS host')
    return url


class Redirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        allowed_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def source_bytes(record, cache):
    if not re.fullmatch(r'personal-au-[a-z0-9-]+', record['id']):
        raise ValueError('Invalid personal source id')
    if record.get('distribution') != 'personal-only' or not 0 < record['bytes'] <= MAX_PDF:
        raise ValueError('Expected a bounded personal-use source')
    allowed_url(record['pdf_url'])
    if cache is not None:
        with (Path(cache) / (record['id'] + '.pdf')).open('rb') as source:
            data = source.read(MAX_PDF + 1)
    else:
        request = urllib.request.Request(record['pdf_url'], headers={'User-Agent': 'Lastbook-personal-reference-builder/1.0'})
        with urllib.request.build_opener(Redirect()).open(request, timeout=60) as response:
            data = response.read(MAX_PDF + 1)
    if not data.startswith(b'%PDF-') or len(data) != record['bytes'] or digest(data) != record['sha256']:
        raise ValueError('Source changed or is incomplete; review required: ' + record['id'])
    return data


def pdf_pages(data):
    import pypdfium2
    doc = pypdfium2.PdfDocument(data)
    try:
        pages = []
        for n in range(len(doc)):
            page = doc[n]
            try:
                text = page.get_textpage()
                try:
                    pages.append(text.get_text_bounded())
                finally:
                    text.close()
            finally:
                page.close()
        return pages
    finally:
        doc.close()


def build(output, cache=None, records=None):
    output = Path(output).absolute()
    if output.exists():
        raise ValueError('Output already exists; choose a separate new folder')
    records = records if records is not None else json.loads(MANIFEST.read_text(encoding='utf-8'))['sources']
    output.parent.mkdir(parents=True, exist_ok=True)
    staged = Path(tempfile.mkdtemp(prefix='.personal-au-', dir=output.parent))
    try:
        lib = staged / 'library-data'; (lib / 'documents/personal-au').mkdir(parents=True)
        (lib / 'pages/personal-au').mkdir(parents=True); (lib / 'text').mkdir()
        catalog, total, seen = [], 0, set()
        with closing(sqlite3.connect(lib / 'search.sqlite')) as db:
            db.execute('CREATE VIRTUAL TABLE pages USING ' + SCHEMA)
            for original in records:
                r = dict(original)
                if r['id'] in seen:
                    raise ValueError('Duplicate personal source id')
                seen.add(r['id'])
                data = source_bytes(r, cache)
                pages = pdf_pages(data)
                if len(pages) != r['pages'] or any(not t.strip() for t in pages):
                    raise ValueError('PDF page count/text changed: ' + r['id'])
                r.update(path='documents/personal-au/' + r['id'] + '.pdf',
                         text_path='text/' + r['id'] + '.txt', searchability='text', distribution='personal-only')
                (lib / r['path']).write_bytes(data)  # Preserve the exact licensed original; no PDF rewriting.
                (lib / r['text_path']).write_text('\n\f\n'.join(pages), encoding='utf-8')
                for n, text in enumerate(pages, 1):
                    db.execute('INSERT INTO pages VALUES(?,?,?,?,?,?,?)',
                               (r['id'], r['title'], r['collection'], r['category'], r['path'], n, text))
                catalog.append(r); total += len(pages)
            body = '<h1>Australian personal-use first aid references</h1><p>Unmodified official ANZCOR guidelines, retrieved 17 November 2026. The original publication, review and version dates remain in each PDF. These are static offline references.</p>'
            body += '<p><strong>Personal-use copies only. Do not redistribute this library or upload its PDFs or extracted text. Public distribution needs written permission from the rights holder.</strong> Terms: https://www.anzcor.org/disclaimer-and-copyright .</p><ul>'
            for r in catalog:
                body += '<li><a href="/' + r['path'] + '">' + html.escape(r['title']) + '</a></li>'
            body += '</ul><p>No source procedure has been rewritten. Related sources referred to inside the original PDFs may not be included. Search the library to open a guideline in the document reader.</p>'
            page = ('<!doctype html><html lang="en-AU"><head><meta charset="utf-8"><title>Australian personal-use first aid references</title></head><body>' + body + '</body></html>').encode('utf-8')
            hub = {'id': 'personal-au-reference', 'title': 'Australian personal-use first aid references', 'kind': 'html',
                   'publisher': 'Lastbook contributors', 'collection': 'Australian personal-use first aid references',
                   'category': 'first-aid', 'path': 'pages/personal-au/index.html', 'bytes': len(page),
                   'sha256': digest(page), 'text_path': 'text/personal-au-reference.txt', 'distribution': 'personal-only',
                   'notes': 'This library contains restricted personal-use source documents. Do not redistribute it.'}
            text = 'Australian personal-use first aid references. Personal use only; not for redistribution.\n' + '\n'.join(r['title'] for r in catalog)
            (lib / hub['path']).write_bytes(page); (lib / hub['text_path']).write_text(text, encoding='utf-8')
            db.execute('INSERT INTO pages VALUES(?,?,?,?,?,?,?)', (hub['id'], hub['title'], hub['collection'], hub['category'], hub['path'], 1, text))
            catalog.append(hub); db.commit()
            if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('Search index integrity check failed')
        (lib / 'catalog.json').write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (lib / 'summary.json').write_text(json.dumps({'resources': len(catalog), 'pdfs': len(records), 'pdf_pages': total,
            'web_pages': 1, 'indexed_units': total + 1, 'extraction_errors': [], 'missing_files': []}, indent=2) + '\n', encoding='utf-8')
        (staged / 'PERSONAL-USE-ONLY.json').write_text(json.dumps({'distribution': 'personal-only',
            'permission_url': 'https://www.anzcor.org/disclaimer-and-copyright',
            'notice': 'Do not redistribute PDFs, extracted source text or this library without rights-holder permission.',
            'sources': records}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        staged.rename(output)
    except BaseException:
        shutil.rmtree(staged)
        raise
    return len(records), total


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument('--download', action='store_true', help='request the pinned original PDFs for personal use')
    mode.add_argument('--pdf-cache', type=Path, help='read already downloaded originals without a connection')
    ap.add_argument('--output', required=True, type=Path)
    a = ap.parse_args()
    try:
        docs, pages = build(a.output, a.pdf_cache)
        print(f'{docs} personal-use PDFs, {pages} pages; separate library built. Do not redistribute it.')
    except (OSError, ValueError, sqlite3.Error) as e:
        ap.exit(1, str(e) + '\n')


if __name__ == '__main__':
    main()
