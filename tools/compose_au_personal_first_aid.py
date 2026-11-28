#!/usr/bin/env python3
"""Add pinned personal-use originals to a NEW copy of a closed full library.

    python3 -B tools/compose_au_personal_first_aid.py --base /old/LastbookData \
        --pdf-cache /my/originals --output /new/LastbookData

Use --download instead of --pdf-cache only to request the official originals.
The complete output is personal-use-only. No archive or runtime downloader is
created. The base, including an existing public Australian supplement, is retained.
"""
import argparse
from collections import Counter
from contextlib import closing
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import sys
import tempfile

try:
    from . import build_au_personal_first_aid as personal
    from . import compose_australia_reference as common
except ImportError:  # Direct command-line invocation.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import build_au_personal_first_aid as personal
    import compose_australia_reference as common

LOCAL_NAME = 'local-australia-personal-first-aid'
RECEIPT = 'AUSTRALIA-PERSONAL-FIRST-AID-COMPOSITION.json'
SOURCES = 'AUSTRALIA-PERSONAL-FIRST-AID-SOURCES.json'
CHECKSUMS = 'AUSTRALIA-PERSONAL-FIRST-AID-SHA256SUMS.tsv'
MARKER = 'PERSONAL-USE-ONLY.json'


def verify(root):
    """Check the full private snapshot, its personal-source flags and page counts."""
    root = Path(root).resolve()
    result = common.verify(root, receipt_name=RECEIPT, local_name=LOCAL_NAME)
    sources = json.loads((root / SOURCES).read_text(encoding='utf-8'))
    if not (root / MARKER).is_file() or sources.get('distribution') != 'personal-only':
        raise ValueError('Personal-use marker or source restrictions are missing')
    records = {r['id']: r for r in common.read_records(root)}
    if any(records.get(uid, {}).get('distribution') != 'personal-only' for uid in result['added_ids']):
        raise ValueError('A personal source lost its distribution restriction')
    with closing(common.read_only(root / 'library-data/search.sqlite')) as db:
        for source in sources['sources']:
            r = records.get(source['id'], {})
            path = 'documents/personal-au/' + source['id'] + '.pdf'
            if (r.get('path') != path or r.get('sha256') != source['sha256']
                    or common.sha256(root / 'library-data' / path) != source['sha256']):
                raise ValueError('Original personal PDF differs: ' + source['id'])
            pages = db.execute('SELECT page,path FROM pages WHERE doc_id=? ORDER BY CAST(page AS INTEGER)', (source['id'],)).fetchall()
            if pages != [(n, path) for n in range(1, source['pages'] + 1)]:
                raise ValueError('Personal source search pages differ: ' + source['id'])
    return result


def compose(base, output, *, cache=None, download=False, records=None, collection='basic'):
    if bool(download) == (cache is not None):
        raise ValueError('Choose exactly one personal source mode: --pdf-cache or --download')
    base, output = Path(base).absolute(), Path(output).absolute()
    if base.is_symlink() or not base.is_dir():
        raise ValueError('Base must be an ordinary library directory')
    if os.path.lexists(output):
        raise ValueError('Output already exists; choose a new folder')
    base, output = base.resolve(), output.resolve()
    if base == output or base in output.parents or output in base.parents:
        raise ValueError('Base and output must be separate directory trees')
    original = common.inventory(base)
    if any(name in original for name in (RECEIPT, SOURCES, CHECKSUMS)):
        raise ValueError('Base already has a personal first-aid composition; this is an initial addition')
    if MARKER in original and not stat.S_ISREG(original[MARKER][2]):
        raise ValueError('Existing personal-use marker must be an ordinary file')
    base_records = common.read_records(base)
    pack = json.loads((base / 'pack.json').read_text(encoding='utf-8'))
    summary = json.loads((base / 'library-data/summary.json').read_text(encoding='utf-8'))
    if not isinstance(pack, dict) or not isinstance(summary, dict):
        raise ValueError('Base pack and summary metadata must be objects')
    if collection not in personal.COLLECTIONS:
        raise ValueError('Unknown personal source collection: ' + str(collection))
    sources = records if records is not None else personal.source_records(collection)
    if not sources:
        raise ValueError('Personal source list must not be empty')
    ids = {r['id'] for r in sources} | {'personal-au-reference'}
    if ids & {r['id'] for r in base_records}:
        raise ValueError('Personal ids already exist in the base catalog; no sources replaced')
    paths = ['pages/personal-au/index.html', 'text/personal-au-reference.txt']
    for source in sources:
        if not re.fullmatch(r'personal-au-[a-z0-9-]+', source['id']):
            raise ValueError('Invalid personal source id')
        paths += ['documents/personal-au/' + source['id'] + '.pdf', 'text/' + source['id'] + '.txt']
    for rel in paths:
        target = 'library-data/' + str(common.relative(rel))
        if target in original or any('/'.join(target.split('/')[:n]) in original
                and not stat.S_ISDIR(original['/'.join(target.split('/')[:n])][2])
                for n in range(1, len(target.split('/')))):
            raise ValueError('Personal file path already exists in base: ' + rel)
    output.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='.au-personal-compose-', dir=output.parent))
    try:
        supplement, staged = work / 'personal', work / 'combined'
        docs, pages = personal.build(supplement, cache, sources, collection=collection)
        additions = common.read_records(supplement)
        shutil.copytree(base, staged, copy_function=common.clone_or_copy)
        if common.inventory(base) != original:
            raise ValueError('Base changed while copying; close Lastbook and try again')
        new_files = [SOURCES]
        for r in additions:
            for key in ('path', 'text_path'):
                rel = 'library-data/' + r[key]
                dest = staged / rel; dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(supplement / rel, dest); new_files.append(rel)
        shutil.copy2(supplement / MARKER, staged / SOURCES)
        if MARKER not in original:
            shutil.copy2(supplement / MARKER, staged / MARKER); new_files.append(MARKER)
        lib = staged / 'library-data'
        (lib / 'search.sqlite').replace(work / 'base-search.sqlite')
        for suffix in ('-wal', '-shm', '-journal'):
            (lib / ('search.sqlite' + suffix)).unlink(missing_ok=True)
        before, after = common.merge_index(work / 'base-search.sqlite', supplement / 'library-data/search.sqlite',
                                            work / 'search.sqlite', ids, expected_units=pages + 1)
        (work / 'search.sqlite').replace(lib / 'search.sqlite')
        combined = base_records + additions
        common.write_json(lib / 'catalog.json', combined)
        counts = Counter(r['kind'] for r in combined)
        summary.update(resources=len(combined), pdfs=counts['pdf'], pdf_pages=sum(r.get('pages') or 0 for r in combined),
                       web_pages=counts['html'] + counts['htm'], videos=counts['video'], collections=counts['zim'],
                       document_bytes=sum(r.get('bytes') or 0 for r in combined), indexed_units=after)
        common.write_json(lib / 'summary.json', summary)
        source_notice = json.loads((staged / SOURCES).read_text(encoding='utf-8'))
        revision = personal.digest((common.sha256(base / 'library-data/catalog.json') +
                                    common.sha256(staged / SOURCES) + common.sha256(lib / 'search.sqlite')).encode())[:20]
        receipt = {'version': 1, 'added_records': len(additions), 'added_ids': sorted(ids), 'original_pdfs': docs,
                   'original_pdf_pages': pages, 'added_search_units': pages + 1,
                   'base_records': len(base_records), 'records': len(combined),
                   'base_search_units': before, 'search_units': after,
                   'base_catalog_sha256': common.sha256(base / 'library-data/catalog.json'),
                   'base_search_sha256': common.sha256(base / 'library-data/search.sqlite'),
                   'download_requested': bool(download),
                   'base_pack_name': pack.get('name'), 'base_content_revision': pack.get('content_revision'),
                   'base_personal_marker_preserved': MARKER in original,
                   'base_receipts': {name: common.sha256(base / name) for name in common.RESERVED if (base / name).is_file()},
                   'distribution': 'personal-only', 'permission_url': source_notice['permission_url'],
                   'notice': 'Do not redistribute this complete copy, PDFs, extracted text or index. All base-library restrictions still apply.',
                   'setup': 'Local composition, not an official Setup pack. Setup Check/Repair are unavailable. Recreate from the closed original.',
                   'checksums': 'The personal checksums cover new source files. pack-manifest.tsv covers the complete private copy. Base receipts describe the retained source snapshot.'}
        if collection != 'basic':
            receipt['source_collection'] = collection
        pack.update(name=LOCAL_NAME, content_revision='local-personal-au-' + revision, counts=dict(counts),
                    personal_first_aid_composition={'distribution': 'personal-only', 'base_name': receipt['base_pack_name'],
                                                   'base_content_revision': receipt['base_content_revision']})
        common.write_json(staged / 'pack.json', pack)
        common.write_json(staged / RECEIPT, receipt)
        contents = '\t'.join(common.CONTENTS) + '\n' + ''.join(
            '\t'.join(str(r.get(k, '')).replace('\t', ' ').replace('\r', ' ').replace('\n', ' ') for k in common.CONTENTS) + '\n'
            for r in combined if r['kind'] != 'metadata')
        (staged / 'pack-contents.tsv').unlink(missing_ok=True)
        (staged / 'pack-contents.tsv').write_text(contents, encoding='utf-8')
        (staged / CHECKSUMS).write_text(common.checksums(staged, new_files), encoding='utf-8')
        files = [p.relative_to(staged).as_posix() for p in staged.rglob('*') if p.is_file() and p != staged / 'pack-manifest.tsv']
        (staged / 'pack-manifest.tsv').unlink(missing_ok=True)
        (staged / 'pack-manifest.tsv').write_text(common.checksums(staged, files), encoding='utf-8')
        verify(staged)
        if common.inventory(base) != original:
            raise ValueError('Base changed while composing; close Lastbook and try again')
        common.publish(staged, output)
        return receipt
    finally:
        shutil.rmtree(work)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument('--base', type=Path)
    mode.add_argument('--verify', type=Path, metavar='PERSONAL_LIBRARY')
    source = ap.add_mutually_exclusive_group()
    source.add_argument('--download', action='store_true', help='explicitly request the pinned official originals')
    source.add_argument('--pdf-cache', type=Path, help='use already obtained originals offline')
    ap.add_argument('--collection', choices=personal.COLLECTIONS, help='optional collection; default basic keeps the existing six originals')
    ap.add_argument('--output', type=Path)
    a = ap.parse_args()
    if a.verify and (a.output or a.download or a.pdf_cache or a.collection is not None):
        ap.error('--verify does not accept output or source options')
    if a.base and (not a.output or not (a.download or a.pdf_cache is not None)):
        ap.error('--base requires --output and exactly one of --pdf-cache or --download')
    try:
        if a.verify:
            r = verify(a.verify)
            print(f"{r['verified_files']} files verified; {r['records']} personal-use library records. No files changed.")
        else:
            r = compose(a.base, a.output, cache=a.pdf_cache, download=a.download, collection=a.collection or 'basic')
            print(f"{r['original_pdfs']} original PDFs, {r['original_pdf_pages']} PDF pages added to a NEW copy; {r['records']} total records. Base unchanged.")
            print('PERSONAL USE ONLY: do not redistribute this library, PDFs, extracted text or index.')
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as e:
        ap.exit(1, str(e) + '\n')


if __name__ == '__main__':
    main()
