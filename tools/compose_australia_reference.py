#!/usr/bin/env python3
"""Add the reviewed Australian readings to a NEW copy of a closed Lastbook library.

    python3 -B tools/compose_australia_reference.py --base /old/LastbookData --output /new/LastbookData

Entirely offline. The base is never opened for writing. The output includes every
base file, so its privacy and redistribution restrictions still apply. This is an
initial addition, not an updater or an official Setup pack. Close Lastbook first.
"""
import argparse
from collections import Counter
from contextlib import closing
import ctypes
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sqlite3
import stat
import sys
import tempfile

try:
    from . import build_australia_reference as au
except ImportError:  # Direct command-line invocation.
    import build_australia_reference as au

COLUMNS = ('doc_id', 'title', 'collection', 'category', 'path', 'page', 'body')
CONTENTS = ('id', 'kind', 'title', 'publisher', 'source_url', 'path', 'bytes')
LOCAL_NAME = 'local-australia-reference'
RESERVED = ('AUSTRALIA-REFERENCE.json', 'AUSTRALIA-SHA256SUMS.tsv', 'AUSTRALIA-COMPOSITION.json')


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def relative(value):
    if not isinstance(value, str) or not value or any(c in value for c in '\\\x00\t\r\n'):
        raise ValueError('Invalid relative library path')
    p = PurePosixPath(value)
    if not p.parts or p.is_absolute() or '..' in p.parts or ':' in p.parts[0] or p.as_posix() != value:
        raise ValueError('Invalid relative library path')
    return p


def inventory(root):
    """A closed, ordinary directory tree; detect concurrent edits before publishing."""
    result = {}
    def failed(error):
        raise error
    for directory, dirs, files in os.walk(root, followlinks=False, onerror=failed):
        for name in sorted(dirs + files):
            p = Path(directory) / name
            rel = p.relative_to(root).as_posix()
            relative(rel)
            s = p.lstat()
            if not (stat.S_ISREG(s.st_mode) or stat.S_ISDIR(s.st_mode)):
                raise ValueError('Library contains a link or special file: ' + rel)
            if name.endswith(('-wal', '-journal', '-shm')):
                raise ValueError('Close Lastbook and SQLite tools before composing: ' + rel)
            result[rel] = (s.st_dev, s.st_ino, s.st_mode, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    return result


def clone_or_copy(src, dst):
    """APFS copy-on-write where available; otherwise a full copy. Never hardlink."""
    clone = getattr(ctypes.CDLL(None, use_errno=True), 'clonefile', None) if sys.platform == 'darwin' else None
    if clone is not None:
        clone.argtypes = (ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int)
        clone.restype = ctypes.c_int
        if clone(os.fsencode(src), os.fsencode(dst), 0) == 0:
            return str(dst)
    return shutil.copy2(src, dst)


def write_json(path, value):
    # Replace a copied file rather than writing through any shared storage.
    temp = path.with_name(path.name + '.au-new')
    with temp.open('x', encoding='utf-8') as f:
        f.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def publish(staged, output):
    """Exclusive rename: even a concurrently created empty output must survive."""
    if sys.platform == 'win32':
        os.rename(staged, output)  # Windows rename refuses an existing destination.
        return
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform == 'darwin' and hasattr(libc, 'renamex_np'):
        rename = libc.renamex_np
        rename.argtypes = (ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint)
        args = (os.fsencode(staged), os.fsencode(output), 4)  # RENAME_EXCL
    elif sys.platform.startswith('linux') and hasattr(libc, 'renameat2'):
        rename = libc.renameat2
        rename.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
        args = (-100, os.fsencode(staged), -100, os.fsencode(output), 1)  # AT_FDCWD, RENAME_NOREPLACE
    else:
        raise OSError('This system does not provide exclusive directory renaming; no output published')
    rename.restype = ctypes.c_int
    if rename(*args) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), str(output))


def read_records(root):
    records = json.loads((root / 'library-data/catalog.json').read_text(encoding='utf-8'))
    if not isinstance(records, list) or not records:
        raise ValueError('Base catalog must be a nonempty record list')
    ids = set()
    for r in records:
        if not isinstance(r, dict) or not isinstance(r.get('id'), str) or not r['id'] or r['id'] in ids:
            raise ValueError('Invalid or duplicate base catalog id')
        ids.add(r['id'])
        for key in ('path', 'text_path'):
            if r.get(key):
                p = root / 'library-data' / relative(r[key])
                if not p.is_file():
                    raise ValueError('Base catalog file is missing: ' + r[key])
    return records


def read_only(path):
    return sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)


def merge_index(base, supplement, dest, ids):
    with closing(read_only(base)) as src, closing(sqlite3.connect(dest)) as db:
        src.backup(db)
        # The finished offline snapshot must not depend on WAL/SHM sidecars.
        db.execute('PRAGMA journal_mode=DELETE')
        sql = db.execute("SELECT sql FROM sqlite_master WHERE name='pages'").fetchone()
        if not sql or 'using fts5' not in sql[0].lower() or tuple(r[1] for r in db.execute('PRAGMA table_info(pages)')) != COLUMNS:
            raise ValueError('Base search index needs the seven-column Lastbook FTS5 pages table')
        if db.execute('PRAGMA integrity_check').fetchone() != ('ok',):
            raise ValueError('Base search index is damaged')
        existing = {r[0] for r in db.execute('SELECT DISTINCT doc_id FROM pages')}
        if ids & existing:
            raise ValueError('Australian ids already exist in the base search index; no files replaced')
        before = db.execute('SELECT count(*) FROM pages').fetchone()[0]
        with closing(read_only(supplement)) as additions:
            db.executemany('INSERT INTO pages VALUES(?,?,?,?,?,?,?)', additions.execute('SELECT ' + ','.join(COLUMNS) + ' FROM pages'))
        db.commit()
        db.execute("INSERT INTO pages(pages) VALUES('integrity-check')")
        if db.execute('PRAGMA integrity_check').fetchone() != ('ok',):
            raise ValueError('Combined search index integrity check failed')
        after = db.execute('SELECT count(*) FROM pages').fetchone()[0]
        if after != before + len(ids):
            raise ValueError('Unexpected number of Australian search rows')
    return before, after


def checksums(root, paths):
    return 'path\tbytes\tsha256\n' + ''.join(
        f'{rel}\t{(root / rel).stat().st_size}\t{sha256(root / rel)}\n' for rel in sorted(paths))


def verify(root):
    """Read-only integrity check for the complete local composition, not publisher authentication."""
    root = Path(root).resolve()
    tree = inventory(root)
    lines = (root / 'pack-manifest.tsv').read_text(encoding='utf-8').splitlines()
    if not lines or lines[0] != 'path\tbytes\tsha256':
        raise ValueError('Invalid composed pack manifest header')
    seen = set()
    for line in lines[1:]:
        fields = line.split('\t')
        if len(fields) != 3:
            raise ValueError('Invalid composed pack manifest row')
        rel, size, digest = fields
        relative(rel)
        if rel in seen or rel == 'pack-manifest.tsv' or not (root / rel).is_file():
            raise ValueError('Duplicate or missing manifest file: ' + rel)
        seen.add(rel)
        if str((root / rel).stat().st_size) != size or sha256(root / rel) != digest:
            raise ValueError('File differs from composed manifest: ' + rel)
    files = {rel for rel, value in tree.items() if stat.S_ISREG(value[2])}
    if seen != files - {'pack-manifest.tsv'}:
        raise ValueError('Composed manifest does not list every file')
    receipt = json.loads((root / 'AUSTRALIA-COMPOSITION.json').read_text(encoding='utf-8'))
    pack = json.loads((root / 'pack.json').read_text(encoding='utf-8'))
    records = read_records(root)
    if pack.get('name') != LOCAL_NAME or len(records) != receipt['records']:
        raise ValueError('Composition identity or catalog count differs')
    with closing(read_only(root / 'library-data/search.sqlite')) as db:
        if db.execute('PRAGMA integrity_check').fetchone() != ('ok',):
            raise ValueError('Composed search index is damaged')
        if db.execute('SELECT count(*) FROM pages').fetchone()[0] != receipt['search_units']:
            raise ValueError('Composed search row count differs')
    if inventory(root) != tree:
        raise ValueError('Composition changed while verifying; close Lastbook and try again')
    return {**receipt, 'verified_files': len(seen)}


def compose(base, output):
    base, output = Path(base).absolute(), Path(output).absolute()
    if base.is_symlink() or not base.is_dir():
        raise ValueError('Base must be an ordinary library directory')
    if os.path.lexists(output):
        raise ValueError('Output already exists; choose a new folder')
    base, output = base.resolve(), output.resolve()
    if base == output or base in output.parents or output in base.parents:
        raise ValueError('Base and output must be separate directory trees')
    original = inventory(base)
    if any(name in original for name in RESERVED):
        raise ValueError('Base already has Australian supplement metadata; this tool only adds it once')
    records = read_records(base)
    pack = json.loads((base / 'pack.json').read_text(encoding='utf-8'))
    summary = json.loads((base / 'library-data/summary.json').read_text(encoding='utf-8'))
    if not isinstance(pack, dict) or not isinstance(summary, dict):
        raise ValueError('Base pack and summary metadata must be objects')
    _, sources = au.checked_sources()
    ids = {r['id'] for r, *_ in sources}
    if ids & {r['id'] for r in records}:
        raise ValueError('Australian ids already exist in the base catalog; no files replaced')
    for r, *_ in sources:
        for rel in (r['path'], 'text/' + r['id'] + '.txt'):
            target = 'library-data/' + str(relative(rel))
            # Also reject a file occupying an ancestor of a new document.
            if target in original or any('/'.join(target.split('/')[:n]) in original
                    and not stat.S_ISDIR(original['/'.join(target.split('/')[:n])][2])
                    for n in range(1, len(target.split('/')))):
                raise ValueError('Australian file path already exists in base: ' + rel)
    output.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='.au-compose-', dir=output.parent))
    try:
        supplement, staged = work / 'supplement', work / 'combined'
        au.build(supplement)
        shutil.copytree(base, staged, copy_function=clone_or_copy)
        if inventory(base) != original:
            raise ValueError('Base changed while copying; close Lastbook and try again')
        additions = read_records(supplement)
        new_files = ['AUSTRALIA-REFERENCE.json']
        for r in additions:
            for key in ('path', 'text_path'):
                rel = 'library-data/' + r[key]
                dest = staged / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(supplement / rel, dest)
                new_files.append(rel)
        shutil.copy2(supplement / 'AUSTRALIA-REFERENCE.json', staged / 'AUSTRALIA-REFERENCE.json')
        lib = staged / 'library-data'
        # Even a read-only open of a closed WAL-mode source can create sidecars.
        # Keep that source in scratch space, outside the published library.
        (lib / 'search.sqlite').replace(work / 'base-search.sqlite')
        before, after = merge_index(work / 'base-search.sqlite', supplement / 'library-data/search.sqlite',
                                    work / 'search.sqlite', ids)
        (work / 'search.sqlite').replace(lib / 'search.sqlite')
        combined = records + additions
        write_json(lib / 'catalog.json', combined)
        counts = Counter(r['kind'] for r in combined)
        summary.update(resources=len(combined), pdfs=counts['pdf'], pdf_pages=sum(r.get('pages') or 0 for r in combined),
                       web_pages=counts['html'] + counts['htm'], videos=counts['video'], collections=counts['zim'],
                       document_bytes=sum(r.get('bytes') or 0 for r in combined), indexed_units=after)
        write_json(lib / 'summary.json', summary)
        manifest = json.loads((staged / 'AUSTRALIA-REFERENCE.json').read_text(encoding='utf-8'))
        receipt = {'version': 1, 'supplement': manifest['id'], 'added_records': len(additions),
                   'base_records': len(records), 'records': len(combined), 'base_search_units': before, 'search_units': after,
                   'base_catalog_sha256': sha256(base / 'library-data/catalog.json'),
                   'base_pack_name': pack.get('name'), 'base_content_revision': pack.get('content_revision'),
                   'distribution': 'All base-library privacy and redistribution restrictions still apply. Do not publish this copy without reviewing the entire base.',
                   'setup': 'Local composition, not an official Setup pack. Setup Check/Repair are unavailable. Recreate from the closed original if needed.',
                   'checksums': 'AUSTRALIA-SHA256SUMS.tsv covers only added source files and the source manifest. pack-manifest.tsv covers the complete composed copy.'}
        pack.update(name=LOCAL_NAME, content_revision='local-' + manifest['id'], counts=dict(counts),
                    australia_composition={'base_name': receipt['base_pack_name'], 'base_content_revision': receipt['base_content_revision']})
        write_json(staged / 'pack.json', pack)
        write_json(staged / 'AUSTRALIA-COMPOSITION.json', receipt)
        contents = '\t'.join(CONTENTS) + '\n' + ''.join(
            '\t'.join(str(r.get(k, '')).replace('\t', ' ').replace('\r', ' ').replace('\n', ' ') for k in CONTENTS) + '\n'
            for r in combined if r['kind'] != 'metadata')
        (staged / 'pack-contents.tsv').unlink(missing_ok=True)
        (staged / 'pack-contents.tsv').write_text(contents, encoding='utf-8')
        (staged / 'AUSTRALIA-SHA256SUMS.tsv').write_text(checksums(staged, new_files), encoding='utf-8')
        files = [p.relative_to(staged).as_posix() for p in staged.rglob('*') if p.is_file() and p != staged / 'pack-manifest.tsv']
        (staged / 'pack-manifest.tsv').unlink(missing_ok=True)
        (staged / 'pack-manifest.tsv').write_text(checksums(staged, files), encoding='utf-8')
        if inventory(base) != original:
            raise ValueError('Base changed while composing; close Lastbook and try again')
        if os.path.lexists(output):
            raise ValueError('Output appeared while composing; no existing folder replaced')
        publish(staged, output)
        return receipt
    finally:
        shutil.rmtree(work)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument('--base', type=Path)
    mode.add_argument('--verify', type=Path, metavar='COMPOSED_LIBRARY', help='Read-only check against its complete file manifest')
    ap.add_argument('--output', type=Path)
    args = ap.parse_args()
    if bool(args.output) != bool(args.base):
        ap.error('--base requires --output; --verify does not accept --output')
    try:
        if args.verify:
            r = verify(args.verify)
            print(f"{r['verified_files']} files verified; {r['records']} records. No files changed.")
            return
        r = compose(args.base, args.output)
        print(f"{r['added_records']} Australian references added to a NEW copy; {r['records']} total records. Base unchanged.")
        print('The complete copy retains base-library privacy restrictions. It is not an official Setup pack; see AUSTRALIA-COMPOSITION.json.')
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as e:
        ap.exit(1, str(e) + '\n')


if __name__ == '__main__':
    main()
