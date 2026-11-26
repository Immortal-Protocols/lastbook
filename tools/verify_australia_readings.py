#!/usr/bin/env python3
"""Check installed Australian readings after normal app use, without changing them.

    python3 -B tools/verify_australia_readings.py --data /path/to/LastbookData \
        --require public --require personal --require trauma

Reconstructs matching-version source projections offline in a private temporary
directory. Checks originals, source conditions, catalogue metadata, extracted text
and every source search page. Checks FTS integrity on a temporary database copy.
This is separate from the existing exact, whole-library snapshot verifiers.
"""
import argparse
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
    from . import build_australia_reference as public
    from . import build_au_personal_first_aid as personal
    from . import build_au_trauma_reference as trauma
    from . import compose_australia_reference as common
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import build_australia_reference as public
    import build_au_personal_first_aid as personal
    import build_au_trauma_reference as trauma
    import compose_australia_reference as common

COLLECTIONS = {'public', 'personal', 'trauma'}
MAX_METADATA = 128 * 1024 * 1024
PERSONAL_NOTICE = 'AUSTRALIA-PERSONAL-FIRST-AID-SOURCES.json'


class Files:
    """Only inspect relevant ordinary files; unrelated logs are allowed to change."""
    def __init__(self, root):
        self.root = root
        self.seen = {}

    def token(self, rel):
        parts = common.relative(rel).parts
        path = self.root
        for n, part in enumerate(parts):
            path = path / part
            info = path.lstat()
            last = n == len(parts) - 1
            if stat.S_ISLNK(info.st_mode) or (not last and not stat.S_ISDIR(info.st_mode)) \
                    or (last and (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1)):
                raise ValueError('Reading check needs an ordinary, non-hardlinked file: ' + rel)
        return (info.st_dev, info.st_ino, info.st_mode, info.st_size, info.st_mtime_ns, info.st_ctime_ns)

    def check(self, rel):
        token = self.token(rel)
        if rel in self.seen and self.seen[rel] != token:
            raise ValueError('Relevant files changed during checking; close Lastbook and retry: ' + rel)
        self.seen[rel] = token
        return self.root / rel

    def json(self, rel):
        path = self.check(rel)
        if path.stat().st_size > MAX_METADATA:
            raise ValueError('Metadata exceeds the reading-check limit: ' + rel)
        with path.open('rb') as source:
            data = source.read(MAX_METADATA + 1)
        if len(data) > MAX_METADATA:
            raise ValueError('Metadata exceeds the reading-check limit: ' + rel)
        return json.loads(data.decode('utf-8'))

    def finish(self):
        for rel in self.seen:
            if self.token(rel) != self.seen[rel]:
                raise ValueError('Relevant files changed during checking; close Lastbook and retry: ' + rel)

    def object(self, rel):
        value = self.json(rel)
        if not isinstance(value, dict):
            raise ValueError('Expected a source metadata object: ' + rel)
        return value


def inactive_index(files):
    """Filesystem-copy only: never open the target database through SQLite."""
    index = files.check('library-data/search.sqlite')
    for suffix in ('-wal', '-journal', '-shm'):
        rel = 'library-data/search.sqlite' + suffix
        path = files.root / rel
        if not os.path.lexists(path):
            continue
        files.check(rel)
        if suffix in ('-wal', '-journal') and path.stat().st_size:
            raise ValueError('Close Lastbook and checkpoint SQLite before checking active journals')
        if suffix == '-shm' and not (files.root / 'library-data/search.sqlite-wal').is_file():
            raise ValueError('Close Lastbook before checking an index with a shared-memory sidecar')
    return index


def catalog(files):
    rows = files.json('library-data/catalog.json')
    if not isinstance(rows, list) or not rows:
        raise ValueError('Expected a nonempty catalogue')
    result = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not row['id'] or row['id'] in result:
            raise ValueError('Invalid or duplicate catalogue id')
        result[row['id']] = row
    return result


def detect(root, records, indexed, public_ids):
    found = set()
    if public_ids & (records.keys() | indexed) or (root / 'AUSTRALIA-REFERENCE.json').exists() \
            or (root / 'library-data/pages/au').exists():
        found.add('public')
    if any(uid.startswith('personal-au-') for uid in records.keys() | indexed) \
            or (root / PERSONAL_NOTICE).exists() or (root / 'library-data/documents/personal-au').exists():
        found.add('personal')
    if trauma.UID in records or trauma.UID in indexed or (root / trauma.NOTICE).exists() \
            or (root / trauma.RECEIPT).exists() or (root / 'library-data' / trauma.PDF).exists():
        found.add('trauma')
    return found


def lines(value):
    return value.replace('\r\n', '\n').replace('\r', '\n')


def temporary_parent(root):
    # Check explicit settings before tempfile probes a directory for writability.
    for name in ('TMPDIR', 'TEMP', 'TMP'):
        if os.environ.get(name):
            candidate = Path(os.environ[name]).resolve()
            if candidate == root or root in candidate.parents:
                raise ValueError('Choose a temporary directory outside the library before checking')
    parent = Path(tempfile.gettempdir()).resolve()
    if parent == root or root in parent.parents:
        raise ValueError('Choose a temporary directory outside the library before checking')
    return parent


def compare(files, records, actual, expected_root):
    expected_records = common.read_records(expected_root)
    units = 0
    with closing(common.read_only(expected_root / 'library-data/search.sqlite')) as expected:
        for record in expected_records:
            uid = record['id']
            if records.get(uid) != record:
                raise ValueError('Source catalogue metadata or restrictions differ: ' + uid)
            for key in ('path', 'text_path'):
                rel = 'library-data/' + record[key]
                target = files.check(rel)
                original = expected_root / rel
                if key == 'path':
                    if target.stat().st_size != original.stat().st_size or common.sha256(target) != common.sha256(original):
                        raise ValueError('Original reading differs: ' + uid)
                else:
                    maximum = original.stat().st_size * 4 + 1024
                    with target.open('rb') as source:
                        text = source.read(maximum + 1)
                    if len(text) > maximum or re.sub(r'\s+', ' ', text.decode('utf-8')).strip() != \
                            re.sub(r'\s+', ' ', original.read_text(encoding='utf-8')).strip():
                        raise ValueError('Extracted source text differs: ' + uid)
            sql = 'SELECT ' + ','.join(common.COLUMNS) + ' FROM pages WHERE doc_id=? ORDER BY CAST(page AS INTEGER),rowid'
            want = expected.execute(sql, (uid,)).fetchall()
            got = actual.execute(sql, (uid,)).fetchall()
            if any(not isinstance(row[-1], str) for row in got):
                raise ValueError('Source search pages have malformed text: ' + uid)
            # Preserve wording/order/page boundaries; tolerate only line-ending form.
            projected = lambda rows: [row[:-1] + (lines(row[-1]),) for row in rows]
            if projected(got) != projected(want):
                raise ValueError('Source search pages differ from the original projection: ' + uid)
            units += len(want)
    return len(expected_records), units


def verify(data, required=()):
    required = set(required)
    if required - COLLECTIONS:
        raise ValueError('Unknown required Australian collection')
    root = Path(data).resolve(strict=True)
    if not root.is_dir():
        raise ValueError('Expected a library directory')
    files = Files(root)
    records = catalog(files)
    manifest, _ = public.checked_sources()
    public_ids = {r['id'] for r in manifest['sources']}
    reports = []
    with tempfile.TemporaryDirectory(prefix='lastbook-au-readings-', dir=temporary_parent(root)) as tmp:
        work = Path(tmp)
        # The target is opened only as ordinary read-only files. SQLite's special
        # FTS integrity command writes solely to this disposable private copy.
        shutil.copyfile(inactive_index(files), work / 'search.sqlite')
        inactive_index(files)
        files.finish()
        with closing(sqlite3.connect(work / 'search.sqlite')) as db:
            schema = db.execute("SELECT type,sql FROM sqlite_master WHERE name='pages'").fetchone()
            if not schema or schema[0] != 'table' or not re.match(r'CREATE\s+VIRTUAL\s+TABLE\s+.*?\s+USING\s+fts5\s*\(', schema[1], re.I) \
                    or tuple(row[1] for row in db.execute('PRAGMA table_info(pages)')) != common.COLUMNS:
                raise ValueError('Expected the seven-column Lastbook FTS5 index')
            if db.execute('PRAGMA integrity_check').fetchone() != ('ok',):
                raise ValueError('Copied search database failed its integrity check')
            db.execute("INSERT INTO pages(pages,rank) VALUES('integrity-check',1)")
            wanted = public_ids | {trauma.UID}
            indexed = {r[0] for r in db.execute('SELECT DISTINCT doc_id FROM pages WHERE doc_id IN (' +
                ','.join('?' for _ in wanted) + ") OR doc_id LIKE 'personal-au-%'", sorted(wanted))}
            found = detect(root, records, indexed, public_ids)
            if required - found:
                raise ValueError('Required collections are absent: ' + ', '.join(sorted(required - found)))
            if not found:
                raise ValueError('No recognised Australian collections; use matching-version metadata and --require')
            if 'public' in found:
                if files.json('AUSTRALIA-REFERENCE.json') != manifest:
                    raise ValueError('Public source manifest differs; use its matching tool revision')
                expected = work / 'public'; public.build(expected)
                readings, pages = compare(files, records, db, expected)
                reports.append(dict(collection='public', readings=readings, search_pages=pages))
            if 'personal' in found:
                notice_path = PERSONAL_NOTICE if (root / PERSONAL_NOTICE).exists() else 'PERSONAL-USE-ONLY.json'
                notice = files.object(notice_path)
                selection = notice.get('source_collection', 'basic')
                sources = personal.source_records(selection)
                # The composer preserves an existing base's potentially opaque
                # private marker. The source-specific notice below carries the
                # exact ANZCOR restriction; do not reinterpret inherited terms.
                marker = files.check('PERSONAL-USE-ONLY.json')
                if not marker.stat().st_size:
                    raise ValueError('Personal-use marker is empty')
                ids = {r['id'] for r in sources} | {'personal-au-reference'}
                if {uid for uid in records.keys() | indexed if uid.startswith('personal-au-')} != ids:
                    raise ValueError('Personal source ids differ from the declared collection')
                for source in sources:
                    files.check('library-data/documents/personal-au/' + source['id'] + '.pdf')
                expected = work / 'personal'
                personal.build(expected, cache=root / 'library-data/documents/personal-au', collection=selection)
                if notice != json.loads((expected / 'PERSONAL-USE-ONLY.json').read_text(encoding='utf-8')):
                    raise ValueError('Personal source notice differs from its matching source collection')
                readings, pages = compare(files, records, db, expected)
                reports.append(dict(collection='personal', selection=selection, readings=readings, search_pages=pages))
            if 'trauma' in found:
                files.check('library-data/' + trauma.PDF)
                receipt = files.object(trauma.RECEIPT)
                if receipt.get('nonprofit_purpose') is not True or receipt.get('added_ids') != [trauma.UID]:
                    raise ValueError('Explicit nonprofit source declaration is missing')
                expected = work / 'trauma'
                trauma.build(expected, cache=root / 'library-data/documents/au-nonprofit', nonprofit_purpose=True)
                if files.json(trauma.NOTICE) != json.loads((expected / trauma.NOTICE).read_text(encoding='utf-8')):
                    raise ValueError('Nonprofit source conditions or acknowledgement differ')
                readings, pages = compare(files, records, db, expected)
                reports.append(dict(collection='trauma', readings=readings, search_pages=pages))
        inactive_index(files)
        files.finish()
    return dict(scope='Matching-version Australian readings and their stored search content',
        collections=reports, readings=sum(r['readings'] for r in reports),
        search_pages=sum(r['search_pages'] for r in reports), relevant_files_checked=len(files.seen),
        fts_integrity='Passed on a private temporary database copy',
        target_writes=0, acquisition='Offline; existing originals only',
        not_checked='Other base-library files, maps, app/guide assets, logs/history, full snapshot identity, source currency or clinical approval')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data', required=True, type=Path)
    ap.add_argument('--require', choices=sorted(COLLECTIONS), action='append', default=[],
                    help='fail if this expected collection is entirely absent; repeat for multiple collections')
    args = ap.parse_args()
    try:
        print(json.dumps(verify(args.data, args.require), indent=2))
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as error:
        ap.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
