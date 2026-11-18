#!/usr/bin/env python3
"""Build an Ontario map archive and a checksum-pinned setup manifest, without publishing.

python3 -I -B packaging/build_ontario.py --gpkg /path/to/ontario.gpkg \
    --data-as-of YYYY-MM-DD --out derived/ontario

Input: Geofabrik's Ontario free OpenStreetMap GeoPackage (ODbL 1.0).
Optional: --addresses /path/to/addresses-CA-ON.sqlite, made by tools/build_addresses.py.
No US layers are reused. Terrain, crop surveys and official dam inventories are absent.
"""
import argparse
import contextlib
import datetime
import hashlib
import json
import os
import shutil
import sqlite3
import struct
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.regions import ONTARIO  # noqa: E402
from engine.paths import ro_uri  # noqa: E402
from engine.setup import install, manifest  # noqa: E402
from tools import build_map  # noqa: E402

SOURCE = 'OpenStreetMap contributors, via Geofabrik Ontario (ODbL 1.0)'
INCLUDES = 'Ontario streets, mapped buildings, waterways, towns and help points (OpenStreetMap)'
LIMITS = ['No elevation or contour tiles.', 'No Canadian crop survey or official dam inventory.',
          'OpenStreetMap coverage varies; mapped services may be closed or unavailable.']


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def source_receipt(path, dataset, url, licence, attribution, data_as_of=None):
    path = Path(path)
    return {'file': path.name, 'size': path.stat().st_size, 'sha256': digest(path),
            'dataset': dataset, 'url': url, 'licence': licence,
            'attribution': attribution, 'data_as_of': data_as_of}


def check_database(path):
    with contextlib.closing(sqlite3.connect(ro_uri(path), uri=True)) as db:
        if db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise ValueError(f'The database {Path(path).name} failed its integrity check.')


def places(national, destination):
    """The place finder uses the same SQLite/FTS5 schema on every desktop platform."""
    source = sqlite3.connect(ro_uri(national), uri=True)
    db = sqlite3.connect(destination)
    try:
        db.executescript("""CREATE TABLE place(id INTEGER PRIMARY KEY,name TEXT,kind TEXT,detail TEXT,lat REAL,lon REAL,rank INTEGER,source TEXT);
          CREATE VIRTUAL TABLE place_fts USING fts5(name,detail,content='place',content_rowid='id',tokenize='unicode61');""")
        insert = 'INSERT INTO place(name,kind,detail,lat,lon,rank,source) VALUES (?,?,?,?,?,?,?)'
        for kind, name, geometry in source.execute("SELECT cls,name,geom FROM feat WHERE layer='place' AND name IS NOT NULL AND name<>''"):
            _, _, x, y = struct.unpack_from('<iiii', geometry)
            db.execute(insert, (name, kind, 'Ontario, Canada', y / 1e6, x / 1e6, 1, 'OpenStreetMap'))
        for kind, name, lon, lat in source.execute("SELECT cls,name,lon,lat FROM poi WHERE name IS NOT NULL AND name<>''"):
            db.execute(insert, (name, kind.replace('_', ' '), 'Ontario, Canada', lat, lon, 4, 'OpenStreetMap'))
        db.execute("INSERT INTO place_fts(place_fts) VALUES('rebuild')")
        db.commit()
    finally:
        db.close()
        source.close()


def archive(folder, path, region_id, kind, data_as_of):
    files = sorted(p for p in folder.rglob('*') if p.is_file())
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as output:
        for file in files:
            output.write(file, file.relative_to(folder).as_posix())
    installed = sum(p.stat().st_size for p in files)
    return {'id': region_id, 'title': 'Ontario, Canada', 'kind': kind, 'available': True,
            'installed_bytes': installed, 'includes': INCLUDES if kind == 'province' else 'Ontario street addresses',
            'files': [{'name': path.name, 'url': f'https://downloads.lastbook.org/{"maps" if kind == "province" else "addresses"}/{data_as_of}/{path.name}',
                       'size': path.stat().st_size, 'sha256': digest(path), 'kind': 'zip'}]}


def build(gpkg, out, data_as_of, addresses=None, base_manifest=None):
    datetime.date.fromisoformat(data_as_of)  # the source date is explicit, never inferred from the build date
    gpkg, out = Path(gpkg), Path(out)
    if not gpkg.is_file():
        raise ValueError('Provide the extracted Ontario OpenStreetMap GeoPackage with --gpkg.')
    out.mkdir(parents=True, exist_ok=True)
    destination = out / 'CA-ON'
    if destination.exists():
        raise ValueError(f'{destination} already exists; choose a new output folder.')
    with tempfile.TemporaryDirectory(prefix='ontario-', dir=out) as temporary:
        stage = Path(temporary)
        payload = stage / 'map'
        geo = payload / 'derived/geo'
        geo.mkdir(parents=True)
        inputs = [source_receipt(gpkg, 'Geofabrik Ontario OpenStreetMap GeoPackage',
                                 'https://download.geofabrik.de/north-america/canada/ontario.html',
                                 'ODbL-1.0', '© OpenStreetMap contributors', data_as_of)]
        build_map.build(gpkg, geo / 'national.sqlite', source_label=SOURCE,
                        data_as_of=data_as_of, bounds=','.join(map(str, ONTARIO['bounds'])))
        db = sqlite3.connect(geo / 'national.sqlite')
        try:
            features = db.execute('SELECT count(*) FROM feat').fetchone()[0]
            if not db.execute("SELECT 1 FROM feat WHERE layer='road' LIMIT 1").fetchone():
                raise ValueError('The Ontario source has no roads.')
            west, south, east, north = ONTARIO['bounds']
            if not db.execute("SELECT 1 FROM feat_idx i JOIN feat f ON f.id=i.id WHERE f.layer='road' "
                              'AND i.minx BETWEEN ? AND ? AND i.miny BETWEEN ? AND ? LIMIT 1',
                              (west, east, south, north)).fetchone():
                raise ValueError('The source does not contain roads within Ontario.')
            # An empty legacy map keeps the desktop tile handler compatible. All
            # Ontario features and help points live in the region-wide database.
            empty = sqlite3.connect(geo / 'map.sqlite')
            try:
                for name in ('feat', 'feat_idx', 'poi', 'meta'):
                    empty.execute(db.execute('SELECT sql FROM sqlite_master WHERE name=?', (name,)).fetchone()[0])
                empty.commit()
            finally:
                empty.close()
        finally:
            db.close()
        places(geo / 'national.sqlite', geo / 'places.sqlite')
        for database in geo.glob('*.sqlite'):
            check_database(database)
        (geo / 'national-status.json').write_text(json.dumps({'state': 'complete', 'stage': 'ready', 'features': features}))
        sizes = {p.relative_to(payload).as_posix(): p.stat().st_size for p in payload.rglob('*') if p.is_file()}
        (payload / 'map-set.json').write_text(json.dumps({
            'name': 'CA-ON', 'title': 'Ontario', 'country': 'CA', 'bounds': ONTARIO['bounds'],
            'data_as_of': data_as_of, 'source': SOURCE, 'attribution': '© OpenStreetMap contributors · ODbL 1.0',
            'known_gaps': LIMITS, 'files': sizes, 'bytes': sum(sizes.values()),
            'provenance': inputs, 'sha256': {name: digest(payload / name) for name in sizes},
        }, indent=2) + '\n')
        install.check_map(payload)
        result = json.loads(Path(base_manifest).read_text()) if base_manifest else {
            'version': 1, 'packs': [], 'models': [], 'maps': [], 'address_indexes': []}
        result['published'] = datetime.date.today().isoformat()
        entry = archive(payload, stage / 'Lastbook-Map-CA-ON.zip', 'CA-ON', 'province', data_as_of)
        result['maps'] = [x for x in result.get('maps', []) if x['id'] != 'CA-ON'] + [entry]
        if addresses:
            address_root = stage / 'addresses'
            address_path = address_root / 'derived/geo/addresses/CA-ON.sqlite'
            address_path.parent.mkdir(parents=True)
            with contextlib.closing(sqlite3.connect(ro_uri(addresses), uri=True)) as source:
                check_database(addresses)
                if source.execute("SELECT 1 FROM addr WHERE state != 'CA-ON' OR state IS NULL LIMIT 1").fetchone():
                    raise ValueError('The address source must contain only CA-ON rows.')
                if not source.execute('SELECT 1 FROM addr LIMIT 1').fetchone():
                    raise ValueError('The Ontario address source is empty.')
                metadata = dict(source.execute('SELECT key,value FROM meta')) if source.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='meta'").fetchone() else {}
                release = metadata.get('release')
                if not release:
                    import re
                    match = re.search(r'\b\d{4}-\d{2}-\d{2}\.\d+\b', metadata.get('source', ''))
                    release = match.group(0) if match else None
                address_receipt = source_receipt(addresses, 'Overture Maps Ontario addresses',
                    'https://docs.overturemaps.org/attribution/',
                    metadata.get('source_licence', 'See source release attribution'),
                    metadata.get('source_attribution', 'See source release attribution'))
                address_receipt['records'] = source.execute('SELECT count(*) FROM addr').fetchone()[0]
                address_receipt['release'] = release
                inputs.append(address_receipt)
                target = sqlite3.connect(address_path)
                try:
                    source.backup(target)
                finally:
                    target.close()
            entry = archive(address_root, stage / 'Lastbook-Addresses-CA-ON.zip', 'CA-ON', 'province-addresses', data_as_of)
            result['address_indexes'] = [x for x in result.get('address_indexes', []) if x['id'] != 'CA-ON'] + [entry]
        if manifest.validate(result) is None:
            raise ValueError('The generated setup manifest did not validate.')
        (stage / 'manifest-v1.json').write_text(json.dumps(result, indent=2) + '\n')
        outputs = {p.name: {'size': p.stat().st_size, 'sha256': digest(p)} for p in stage.glob('*.zip')}
        (stage / 'build-receipt.json').write_text(json.dumps({
            'region': 'CA-ON', 'built': datetime.date.today().isoformat(),
            'inputs': inputs, 'outputs': outputs, 'features': features,
            'known_gaps': LIMITS,
        }, indent=2) + '\n')
        # Move only the finished, checked artifacts into the output folder.
        payload.rename(stage / 'LastbookData')
        if (stage / 'addresses').exists():
            shutil.rmtree(stage / 'addresses')
        os.rename(stage, destination)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gpkg', required=True, type=Path)
    parser.add_argument('--data-as-of', required=True, help='Source snapshot date, YYYY-MM-DD')
    parser.add_argument('--out', type=Path, default=ROOT / 'derived/ontario')
    parser.add_argument('--addresses', type=Path)
    parser.add_argument('--base-manifest', type=Path, help='An existing setup manifest to extend')
    args = parser.parse_args()
    try:
        print(build(args.gpkg, args.out, args.data_as_of, args.addresses, args.base_manifest))
    except (ValueError, OSError, sqlite3.Error) as error:
        parser.exit(1, f'Ontario build failed: {error}\n')


if __name__ == '__main__':
    main()
