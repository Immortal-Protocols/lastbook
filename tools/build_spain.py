#!/usr/bin/env python3
"""Build a Spain map archive from locally supplied Geofabrik GeoPackages.

See docs/MAPS.md for the source list, licences and reproducible build steps.
This is a build-machine tool; it does not download data or run in Lastbook.
"""
import argparse
import hashlib
import json
import sqlite3
import struct
import sys
import zipfile
from pathlib import Path

import build_map

REGIONS = ('andalucia', 'aragon', 'asturias', 'cantabria', 'castilla-la-mancha',
           'castilla-y-leon', 'cataluna', 'ceuta', 'extremadura', 'galicia',
           'islas-baleares', 'la-rioja', 'madrid', 'melilla', 'murcia', 'navarra',
           'pais-vasco', 'valencia', 'canary-islands')


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for data in iter(lambda: f.read(4 * 1024 * 1024), b''):
            h.update(data)
    return h.hexdigest()


def empty_map(path):
    db = sqlite3.connect(path)
    db.executescript('''CREATE TABLE feat(id INTEGER PRIMARY KEY, layer TEXT, cls TEXT, name TEXT, minz INTEGER, geom BLOB);
      CREATE VIRTUAL TABLE feat_idx USING rtree(id, minx, maxx, miny, maxy, minz, maxz);
      CREATE TABLE poi(id INTEGER PRIMARY KEY, cls TEXT, name TEXT, lon REAL, lat REAL);
      CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);''')
    db.close()


def build_places(national, output):
    source = sqlite3.connect(Path(national).resolve().as_uri() + '?mode=ro', uri=True)
    db = sqlite3.connect(output)
    db.executescript('''CREATE TABLE place(id INTEGER PRIMARY KEY, name TEXT, kind TEXT, detail TEXT, lat REAL, lon REAL, rank INTEGER, source TEXT);
      CREATE VIRTUAL TABLE place_fts USING fts5(name, detail, content='place', content_rowid='id', tokenize='unicode61');''')
    query = 'INSERT INTO place(name,kind,detail,lat,lon,rank,source) VALUES (?,?,?,?,?,?,?)'
    for cls, name, data in source.execute("SELECT cls,name,geom FROM feat WHERE layer='place' AND name IS NOT NULL AND name<>''"):
        # A place is a point in build_map's packed coordinate format.
        if len(data) >= 16:
            _, count, x, y = struct.unpack_from('<iiii', data)
            if count:
                db.execute(query, (name, cls, 'Spain (OpenStreetMap)', y / 1e6, x / 1e6, 1, 'OpenStreetMap'))
    for cls, name, lon, lat in source.execute("SELECT cls,name,lon,lat FROM poi WHERE name IS NOT NULL AND name<>''"):
        db.execute(query, (name, cls.replace('_', ' '), 'Spain (OpenStreetMap)', lat, lon, 4, 'OpenStreetMap'))
    db.execute("INSERT INTO place_fts(place_fts) VALUES('rebuild')")
    db.commit()
    db.close()
    source.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir', required=True, type=Path, help='directory of extracted <region>.gpkg files')
    parser.add_argument('--output-dir', required=True, type=Path, help='new output directory')
    parser.add_argument('--data-date', default='unspecified', help='source snapshot date, e.g. 2026-11-15')
    parser.add_argument('--sample', action='store_true', help='allow incomplete extracts and label the result ES-SAMPLE')
    args = parser.parse_args()
    if args.sample:
        sources = sorted(args.input_dir.glob('*.gpkg'))
        if not sources:
            parser.error('sample requires at least one GeoPackage')
        name = 'ES-SAMPLE'
    else:
        sources = [args.input_dir / (region + '.gpkg') for region in REGIONS]
        missing = [p.name for p in sources if not p.is_file()]
        if missing:
            parser.error('missing required extracts: ' + ', '.join(missing))
        name = 'ES'
    if args.output_dir.exists():
        parser.error('output directory already exists; choose a new directory')
    geo = args.output_dir / name / 'derived/geo'
    geo.mkdir(parents=True)
    source_hashes = {p.name: sha256(p) for p in sources}
    meta = [('source', 'OpenStreetMap contributors, via Geofabrik (ODbL 1.0)'),
            ('license_url', 'https://opendatacommons.org/licenses/odbl/1-0/'),
            ('attribution', '© OpenStreetMap contributors'),
            ('data_as_of', args.data_date), ('coverage', 'Spain' if name == 'ES' else 'Spain sample: incomplete'),
            ('region', name), ('input_sha256', json.dumps(source_hashes, sort_keys=True))]
    build_map.build(sources, geo / 'national.sqlite', metadata=meta, include_islands=True)
    empty_map(geo / 'map.sqlite')
    build_places(geo / 'national.sqlite', geo / 'places.sqlite')
    db = sqlite3.connect(geo / 'national.sqlite')
    count = db.execute('SELECT count(*) FROM feat').fetchone()[0]
    db.close()
    (geo / 'national-status.json').write_text(json.dumps({'state': 'complete', 'stage': 'ready', 'features': count}))
    (geo / 'socal-cells.json').write_text('[]')
    root = args.output_dir / name
    files = {p.relative_to(root).as_posix(): p.stat().st_size for p in sorted(root.rglob('*')) if p.is_file()}
    (root / 'map-set.json').write_text(json.dumps({'name': name, 'files': files, 'bytes': sum(files.values())}, indent=1) + '\n')
    archive = args.output_dir / f'Lastbook-Map-{name}.zip'
    with zipfile.ZipFile(archive, 'w', allowZip64=True, compression=zipfile.ZIP_DEFLATED) as z:
        for path in sorted(p for p in root.rglob('*') if p.is_file()):
            zi = zipfile.ZipInfo(path.relative_to(root).as_posix(), date_time=(2026, 1, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            with path.open('rb') as src, z.open(zi, 'w', force_zip64=True) as dst:
                while chunk := src.read(4 * 1024 * 1024):
                    dst.write(chunk)
    with zipfile.ZipFile(archive) as z:
        installed = sum(i.file_size for i in z.infolist())
    print(json.dumps({'id': name, 'archive': str(archive), 'sha256': sha256(archive),
                      'download_bytes': archive.stat().st_size, 'installed_bytes': installed}, indent=2))


if __name__ == '__main__':
    main()
