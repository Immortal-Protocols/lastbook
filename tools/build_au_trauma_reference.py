#!/usr/bin/env python3
"""Build or compose one unchanged MHFA original for NONPROFIT use only.

Requires --nonprofit-purpose and an explicit --pdf-cache or --download choice.
Outputs a new library; an optional --base is copied and preserved. No runtime
network code, public-pack inclusion or general redistribution grant is added.
"""
import argparse
from collections import Counter
from contextlib import closing
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import urllib.parse
import urllib.request

try:
    from . import compose_australia_reference as common
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import compose_australia_reference as common

SCHEMA = 'fts5(doc_id UNINDEXED,title,collection,category,path UNINDEXED,page UNINDEXED,body,tokenize="unicode61")'

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


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'content/regions/au/nonprofit-trauma-source.json'
UID = 'au-mhfa-adult-traumatic-events'
PDF = 'documents/au-nonprofit/' + UID + '.pdf'
TEXT = 'text/' + UID + '.txt'
NOTICE = 'AUSTRALIA-TRAUMA-SOURCE.json'
RECEIPT = 'AUSTRALIA-TRAUMA-COMPOSITION.json'
NAME = 'local-australia-nonprofit-trauma'
MAX_PDF = 1_000_000


def source_record():
    manifest = json.loads(SOURCE.read_text(encoding='utf-8'))
    r = manifest['source']
    if (manifest.get('distribution') != 'nonprofit-only' or r.get('id') != UID
            or r.get('distribution') != 'nonprofit-only' or r.get('rights_physical_page') != 7
            or r.get('pages') != 7 or r.get('license') != 'LicenseRef-MHFA-nonprofit-reproduction'
            or not r.get('attribution') or not 0 < r['bytes'] <= MAX_PDF):
        raise ValueError('Expected the reviewed nonprofit MHFA source and its acknowledgement')
    return r


def allowed_url(url):
    u = urllib.parse.urlsplit(url)
    if (u.scheme != 'https' or u.hostname != 'mhfainternational.org'
            or u.username or u.password or u.port):
        raise ValueError('Source must use the official MHFA International HTTPS host')
    return url


class Redirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        allowed_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def source_bytes(r, cache):
    allowed_url(r['pdf_url'])
    if cache is not None:
        with (Path(cache) / (UID + '.pdf')).open('rb') as f:
            data = f.read(MAX_PDF + 1)
    else:
        req = urllib.request.Request(r['pdf_url'], headers={'User-Agent': 'Lastbook-nonprofit-source-builder/1.0'})
        with urllib.request.build_opener(Redirect()).open(req, timeout=60) as response:
            data = response.read(MAX_PDF + 1)
    import hashlib
    if not data.startswith(b'%PDF-') or len(data) != r['bytes'] or hashlib.sha256(data).hexdigest() != r['sha256']:
        raise ValueError('Original changed or is incomplete; source/reuse review required')
    return data


def verify(root):
    root = Path(root).resolve()
    result = common.verify(root, receipt_name=RECEIPT, local_name=NAME)
    source = source_record()
    notice = json.loads((root / NOTICE).read_text(encoding='utf-8'))
    records = {r['id']: r for r in common.read_records(root)}
    record = records.get(UID, {})
    if (notice.get('source') != source or notice.get('distribution') != 'nonprofit-only'
            or result.get('nonprofit_purpose') is not True or result.get('added_ids') != [UID]
            or record != {**source, 'path': PDF, 'text_path': TEXT, 'searchability': 'text'}
            or common.sha256(root / 'library-data' / PDF) != source['sha256']):
        raise ValueError('Nonprofit source, acknowledgement, restrictions or original differs')
    with closing(common.read_only(root / 'library-data/search.sqlite')) as db:
        rows = db.execute('SELECT page,path,body FROM pages WHERE doc_id=? ORDER BY CAST(page AS INTEGER)', (UID,)).fetchall()
        if [(row[0], row[1]) for row in rows] != [(n, PDF) for n in range(1, source['pages'] + 1)] or any(not row[2].strip() for row in rows):
            raise ValueError('Original physical-page search units differ')
        if (root / 'library-data' / TEXT).read_bytes().decode('utf-8') != '\n\f\n'.join(row[2] for row in rows):
            raise ValueError('Local text and source search units differ')
    return result


def build(output, *, cache=None, download=False, nonprofit_purpose=False, base=None):
    if not nonprofit_purpose:
        raise ValueError('This source requires an explicit nonprofit purpose (--nonprofit-purpose)')
    if bool(download) == (cache is not None):
        raise ValueError('Choose exactly one source mode: --pdf-cache or --download')
    output = Path(output).absolute()
    if os.path.lexists(output):
        raise ValueError('Output already exists; choose a new folder')
    output = output.resolve()
    r = source_record()
    original, base_records = None, []
    if base is not None:
        base = Path(base).absolute()
        if base.is_symlink() or not base.is_dir():
            raise ValueError('Base must be an ordinary library directory')
        base = base.resolve()
        if base == output or base in output.parents or output in base.parents:
            raise ValueError('Base and output must be separate directory trees')
        original = common.inventory(base)
        base_records = common.read_records(base)
        if UID in {row['id'] for row in base_records} or any(n in original for n in (NOTICE, RECEIPT)):
            raise ValueError('Source already exists; no originals replaced')
        for rel in ['library-data/' + PDF, 'library-data/' + TEXT]:
            if rel in original or any('/'.join(rel.split('/')[:n]) in original
                    and not (base / '/'.join(rel.split('/')[:n])).is_dir()
                    for n in range(1, len(rel.split('/')))):
                raise ValueError('Source file path already exists in base: ' + rel)
    # Fetch/extract before copying a potentially large library. No in-place writes.
    data = source_bytes(r, cache)
    pages = pdf_pages(data)
    if len(pages) != r['pages'] or any(not text.strip() for text in pages):
        raise ValueError('Original page count or text differs')
    output.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='.au-trauma-', dir=output.parent))
    try:
        staged, supplement = work / 'library', work / 'source.sqlite'
        if base is None:
            (staged / 'library-data').mkdir(parents=True)
            pack, summary = {}, {}
        else:
            shutil.copytree(base, staged, copy_function=common.clone_or_copy)
            if common.inventory(base) != original:
                raise ValueError('Base changed; close Lastbook before composing')
            pack = json.loads((base / 'pack.json').read_text(encoding='utf-8'))
            summary = json.loads((base / 'library-data/summary.json').read_text(encoding='utf-8'))
            if not isinstance(pack, dict) or not isinstance(summary, dict):
                raise ValueError('Expected base pack and summary objects')
        lib = staged / 'library-data'
        for path, content in [(PDF, data), (TEXT, '\n\f\n'.join(pages).encode('utf-8'))]:
            target = lib / path; target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as f:
                f.write(content)
        with closing(sqlite3.connect(supplement)) as db:
            db.execute('CREATE VIRTUAL TABLE pages USING ' + SCHEMA)
            db.executemany('INSERT INTO pages VALUES(?,?,?,?,?,?,?)',
                [(UID, r['title'], r['collection'], r['category'], PDF, n, text) for n, text in enumerate(pages, 1)])
            db.commit()
        if base is None:
            shutil.copy2(supplement, lib / 'search.sqlite'); before, after = 0, len(pages)
        else:
            for suffix in ('-wal', '-shm', '-journal'):
                (lib / ('search.sqlite' + suffix)).unlink(missing_ok=True)
            (lib / 'search.sqlite').unlink()
            before, after = common.merge_index(base / 'library-data/search.sqlite', supplement,
                lib / 'search.sqlite', {UID}, expected_units=len(pages))
        additions = {**r, 'path': PDF, 'text_path': TEXT, 'searchability': 'text'}
        records = base_records + [additions]; counts = Counter(row['kind'] for row in records)
        common.write_json(lib / 'catalog.json', records)
        summary.update(resources=len(records), pdfs=counts['pdf'], pdf_pages=sum(row.get('pages') or 0 for row in records),
            web_pages=counts['html'] + counts['htm'], videos=counts['video'], collections=counts['zim'],
            document_bytes=sum(row.get('bytes') or 0 for row in records), indexed_units=after)
        common.write_json(lib / 'summary.json', summary)
        notice = {'version': 1, 'distribution': 'nonprofit-only', 'source': r,
            'notice': 'This original is reproduced for a nonprofit purpose with source acknowledgement. No commercial-use grant or endorsement. All other library restrictions remain; a mixed private library must not be shared.'}
        common.write_json(staged / NOTICE, notice)
        receipt = dict(version=1, records=len(records), added_ids=[UID], added_records=1,
            base_records=len(base_records), base_search_units=before, search_units=after,
            original_pdf_pages=len(pages), nonprofit_purpose=True, distribution='nonprofit-only',
            download_requested=bool(download), base_pack_name=pack.get('name'),
            base_personal_marker_preserved=bool(base is not None and 'PERSONAL-USE-ONLY.json' in original),
            notice='Initial addition to a new copy; not an updater. Recreate from the retained base. Not an official Setup pack; Check/Repair are unavailable.')
        common.write_json(staged / RECEIPT, receipt)
        pack.update(name=NAME, counts=dict(counts), content_revision='local-trauma-' + r['sha256'][:20],
            nonprofit_source={'id': UID, 'distribution': 'nonprofit-only', 'source_sha256': r['sha256']})
        common.write_json(staged / 'pack.json', pack)
        contents = '\t'.join(common.CONTENTS) + '\n' + ''.join(
            '\t'.join(str(row.get(k, '')).replace('\t', ' ').replace('\r', ' ').replace('\n', ' ') for k in common.CONTENTS) + '\n'
            for row in records if row['kind'] != 'metadata')
        for name in ('pack-contents.tsv', 'pack-manifest.tsv'):
            (staged / name).unlink(missing_ok=True)
        (staged / 'pack-contents.tsv').write_text(contents, encoding='utf-8')
        files = sorted(p.relative_to(staged).as_posix() for p in staged.rglob('*') if p.is_file())
        (staged / 'pack-manifest.tsv').write_text(common.checksums(staged, files), encoding='utf-8')
        verify(staged)
        if base is not None and common.inventory(base) != original:
            raise ValueError('Base changed while composing; no output published')
        common.publish(staged, output)
        return receipt
    finally:
        shutil.rmtree(work)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--verify', type=Path)
    ap.add_argument('--output', type=Path)
    ap.add_argument('--base', type=Path)
    ap.add_argument('--pdf-cache', type=Path)
    ap.add_argument('--download', action='store_true')
    ap.add_argument('--nonprofit-purpose', action='store_true')
    args = ap.parse_args()
    try:
        if args.verify:
            if any((args.output, args.base, args.pdf_cache, args.download, args.nonprofit_purpose)):
                raise ValueError('--verify accepts only its library path')
            result = verify(args.verify)
        else:
            if args.output is None:
                raise ValueError('--output is required')
            result = build(args.output, cache=args.pdf_cache, download=args.download,
                nonprofit_purpose=args.nonprofit_purpose, base=args.base)
        print(json.dumps(result, indent=2))
    except (OSError, ValueError, KeyError) as e:
        ap.exit(1, str(e) + '\n')


if __name__ == '__main__':
    main()
