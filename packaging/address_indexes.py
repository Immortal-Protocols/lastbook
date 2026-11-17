"""Build and publish per-state offline address indexes from the saved Overture database.

The state map archives are independent of these sidecars. This tool writes payloads
and a local manifest fragment, leaving the release manifest to the setup publisher.

  python3 packaging/address_indexes.py build|publish|all                       # the US states, as before
  python3 packaging/address_indexes.py build --source derived/geo/addresses-CA.sqlite --codes CA-ON CA-BC
  python3 packaging/address_indexes.py publish --codes CA-ON CA-BC

A region outside the US (packaging/regions) is built only when named with --codes, from the file
tools/build_addresses.py --country wrote for it.
"""
import argparse
import concurrent.futures
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import time
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'derived/geo/addresses.sqlite'
OUT = ROOT / 'derived/packs/address-indexes'
RESULTS = ROOT / 'derived/packs/address-indexes.json'
RELEASE = '2026-10-21.0'
BASE = 'https://downloads.lastbook.org'
sys.path.insert(0, str(ROOT / 'packaging'))
import state_maps


def log(*args):
    print(time.strftime('%H:%M:%S'), *args, flush=True)


def sha_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def build(source_path=SOURCE, codes=None):
    """Read the large source table once and distribute batches to state databases."""
    OUT.mkdir(parents=True, exist_ok=True)
    codes = list(codes or state_maps.US_NAMES)
    unknown = [c for c in codes if c not in state_maps.NAMES]
    if unknown:
        raise SystemExit(f'unknown state or region: {unknown}')
    source = sqlite3.connect(f'file:{source_path}?mode=ro', uri=True)
    source_meta = dict(source.execute('SELECT key,value FROM meta'))
    connections = {}
    counts = defaultdict(int)
    skipped = defaultdict(int)
    for state in codes:
        path = OUT / f'{state}.partial.sqlite'
        path.unlink(missing_ok=True)
        db = sqlite3.connect(path)
        db.executescript('PRAGMA page_size=8192; PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF; '
                         'PRAGMA cache_size=-1024; PRAGMA temp_store=FILE; '
                         'CREATE TABLE addr(num TEXT, street TEXT, norm TEXT, city TEXT, state TEXT, zip TEXT, lat REAL, lon REAL); '
                         'CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT);')
        connections[state] = db
    cursor = source.execute('SELECT num,street,norm,city,state,zip,lat,lon FROM addr')
    processed = 0
    started = time.monotonic()
    while rows := cursor.fetchmany(100000):
        batches = defaultdict(list)
        for row in rows:
            state = row[4]
            if state not in connections:
                skipped[str(state)] += 1
                continue
            batches[state].append(row)
        for state, batch in batches.items():
            connections[state].executemany('INSERT INTO addr VALUES (?,?,?,?,?,?,?,?)', batch)
            counts[state] += len(batch)
        processed += len(rows)
        if processed % 5000000 == 0:
            log('split', f'{processed:,}', 'rows', f'{time.monotonic() - started:.0f}s')
    source.close()
    for state, db in connections.items():
        db.commit()
        log(state, 'indexing', f'{counts[state]:,}')
        db.executescript('CREATE INDEX addr_norm ON addr(norm,num); CREATE INDEX addr_num_norm ON addr(num,norm);')
        db.executemany('INSERT INTO meta VALUES (?,?)', [('state', state), ('count', str(counts[state])),
                        ('source', source_meta.get('source', 'Overture Maps addresses')),
                        ('source_built', source_meta.get('built', '')), ('release', RELEASE)])
        db.commit()
        check = db.execute('PRAGMA quick_check').fetchone()[0]
        if check != 'ok':
            raise RuntimeError(f'{state}: SQLite check failed: {check}')
        db.close()
        os.replace(OUT / f'{state}.partial.sqlite', OUT / f'{state}.sqlite')
    (OUT / ('build.json' if codes == list(state_maps.US_NAMES) else f'build-{"-".join(codes)}.json')).write_text(json.dumps({'counts': dict(counts), 'skipped': dict(skipped),
                                              'rows': processed, 'seconds': round(time.monotonic() - started)}, indent=2) + '\n')
    log('build complete', dict(counts), 'skipped', dict(skipped))


def public_sha(url):
    process = subprocess.Popen(['curl', '-fLsS', '--retry', '3', '--max-time', '600', url], stdout=subprocess.PIPE)
    digest = hashlib.sha256()
    count = 0
    for chunk in iter(lambda: process.stdout.read(4 * 1024 * 1024), b''):
        digest.update(chunk)
        count += len(chunk)
    if process.wait() != 0:
        raise RuntimeError(f'Public download failed: {url}')
    return digest.hexdigest(), count


def publish_one(state, archive_dir=None):
    path = OUT / f'{state}.sqlite'
    kind = 'state-addresses' if state in state_maps.US_NAMES else 'region-addresses'
    db = sqlite3.connect(f'file:{path}?mode=ro', uri=True)
    count = int(dict(db.execute('SELECT key,value FROM meta'))['count'])
    db.close()
    if not count:
        log(state, 'no source addresses')
        return state, {'id': state, 'title': state_maps.NAMES[state], 'kind': kind,
                       'available': False, 'installed_bytes': 0, 'records': 0, 'files': [],
                       'unavailable_reason': 'The saved address source has no records for this state.'}
    archive_dir = archive_dir or OUT
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive = archive_dir / f'Lastbook-Addresses-{state}.zip'
    member = f'derived/geo/addresses/{state}.sqlite'
    with zipfile.ZipFile(archive.with_suffix('.partial'), 'w', compression=zipfile.ZIP_DEFLATED,
                         compresslevel=6, allowZip64=True) as output:
        output.write(path, member)
    os.replace(archive.with_suffix('.partial'), archive)
    with zipfile.ZipFile(archive) as output:
        if output.namelist() != [member] or output.testzip() is not None:
            raise RuntimeError(f'{state}: bad archive')
    digest = sha_file(archive)
    key = f'addresses/{RELEASE}/{archive.name}'
    log(state, 'uploading', archive.stat().st_size)
    state_maps.upload(state_maps.R.Context(), archive, key)
    url = f'{BASE}/{key}'
    actual, size = public_sha(url)
    if actual != digest or size != archive.stat().st_size:
        raise RuntimeError(f'{state}: public checksum mismatch')
    entry = {'id': state, 'title': state_maps.NAMES[state], 'kind': kind, 'available': True,
             'installed_bytes': path.stat().st_size, 'records': count,
             'files': [{'name': archive.name, 'url': url, 'size': size, 'sha256': digest, 'kind': 'zip'}]}
    log(state, 'published and verified', f'{count:,}', 'addresses')
    return state, entry


def publish(workers, codes=None):
    results = json.loads(RESULTS.read_text()) if RESULTS.exists() else {}
    priority = ['MI', 'CA', 'RI']
    order = list(codes) if codes else priority + [state for state in state_maps.US_NAMES if state not in priority]
    states = [state for state in order if state not in results]
    missing = [state for state in states if not (OUT / f'{state}.sqlite').is_file()]
    if missing:
        raise SystemExit(f'not built yet: {missing}')
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for future in concurrent.futures.as_completed([pool.submit(publish_one, state) for state in states]):
            state, entry = future.result()
            if entry:
                results[state] = entry
                temporary = RESULTS.with_suffix('.tmp')
                temporary.write_text(json.dumps(results, indent=2, sort_keys=True) + '\n')
                os.replace(temporary, RESULTS)
    log('published', len(results), 'state address indexes')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['build', 'publish', 'all'])
    parser.add_argument('--workers', type=int, default=3)
    parser.add_argument('--source', default=str(SOURCE), help='the file tools/build_addresses.py wrote')
    parser.add_argument('--codes', nargs='*', help='states or regions (default: every US state)')
    args = parser.parse_args()
    if args.action in ('build', 'all'):
        build(Path(args.source), args.codes)
    if args.action in ('publish', 'all'):
        publish(args.workers, args.codes)


if __name__ == '__main__':
    main()
