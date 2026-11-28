#!/usr/bin/env python3
"""Build a complete Lastbook map set for any place, from a Geofabrik "free" GeoPackage.

Lastbook ships detailed maps for a handful of US states. This builds the same set of files for a
place outside that list (a Brazilian state, a European country, ...) from the free OpenStreetMap
extract Geofabrik publishes for it, so the app can show the region's streets, water, land and
place names offline. It is a cleaned-up port of the two-script flow that produced the Rio de
Janeiro map for issue #53, and it is stdlib-only — the one exception is the optional --coast
step, which runs tools/build_coast.py and needs pyosmium.

  python3 tools/build_region.py <extract.gpkg | extract.zip> --name BR-RJ --label "Rio de Janeiro" \
      [--box west,south,east,north] [--coast <coastline.osm.pbf> --coast-close <lon>] \
      [--data /path/to/LastbookData]

Steps:
  1. tools/build_map.py converts the extract to derived/geo/national.sqlite (the detailed map).
  2. --box clips it to the box: a Brazilian state extract also holds its neighbouring states.
  3. --coast adds the OpenSea coastline: the free GeoPackage has no natural=coastline ways (only
     the full .osm.pbf has them), so without it the sea edge stays the ragged base world map.
  4. Assembles the rest of the set the app reads: places.sqlite, an empty map.sqlite
     placeholder, national-status.json, socal-cells.json ([]) and map-set.json.

The data folder (--data, else $LASTBOOK_DATA, else the repo root) must also hold library-data/,
which provides the base world map and the search library: clone it from an installed
LastbookData. The app then runs with --data /path/to/LastbookData (issue #53). See docs/MAPS.md.
"""
import argparse
import json
import os
import re
import shutil
import sqlite3
import struct
import subprocess
import sys
import tempfile
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]

# The feature tables tools/build_map.py reads, with the columns it selects. A small extract may
# lack some of them (a city has no railways), so any missing ones are stubbed in a copy.
GPKG_TABLES = {
    'gis_osm_water_a_free': 'fclass TEXT, name TEXT, geom BLOB',
    'gis_osm_natural_a_free': 'fclass TEXT, name TEXT, geom BLOB',
    'gis_osm_landuse_a_free': 'fclass TEXT, name TEXT, geom BLOB',
    'gis_osm_protected_areas_a_free': 'fclass TEXT, geom BLOB',
    'gis_osm_waterways_free': 'fclass TEXT, name TEXT, geom BLOB',
    'gis_osm_railways_free': 'fclass TEXT, name TEXT, geom BLOB',
    'gis_osm_roads_free': 'fclass TEXT, name TEXT, ref TEXT, geom BLOB',
    'gis_osm_buildings_a_free': 'fclass TEXT, name TEXT, geom BLOB',
    'gis_osm_places_free': 'fclass TEXT, population TEXT, name TEXT, geom BLOB',
    'gis_osm_pois_free': 'fclass TEXT, name TEXT, geom BLOB',
    'gis_osm_pois_a_free': 'fclass TEXT, name TEXT, geom BLOB',
    'gis_osm_natural_free': 'fclass TEXT, name TEXT, geom BLOB',
}


def die(msg):
    print('build_region: ' + msg, file=sys.stderr)
    sys.exit(1)


def run(cmd):
    print('+ ' + ' '.join(str(c) for c in cmd), flush=True)
    r = subprocess.run([str(c) for c in cmd])
    if r.returncode:
        die(f'failed: {" ".join(str(c) for c in cmd)}')


def open_extract(path, tempdirs):
    """Return the .gpkg to build from; unzip to a temp dir if given a .zip."""
    p = Path(path)
    if not p.exists():
        die(f'{path}: no such file — download the extract first, e.g.\n'
            '  curl -L -O https://download.geofabrik.de/south-america/brazil/sudeste-free-gpkg-latest.zip')
    if p.suffix == '.zip':
        td = tempfile.TemporaryDirectory(prefix='lastbook-region-')
        tempdirs.append(td)
        with zipfile.ZipFile(p) as z:
            z.extractall(td.name)
        gpkgs = list(Path(td.name).rglob('*.gpkg'))
        if len(gpkgs) != 1:
            die(f'{p}: expected exactly one .gpkg inside the zip, found {len(gpkgs)}')
        return gpkgs[0]
    if p.suffix == '.gpkg':
        return p
    die(f'{p}: expected a .gpkg file or a .zip containing one')


def ensure_tables(gpkg, tempdirs):
    """build_map reads a fixed list of tables; stub the missing ones in a byte copy (the input is never modified)."""
    db = sqlite3.connect(f'file:{gpkg}?mode=ro', uri=True)
    have = {r[0] for r in db.execute('SELECT name FROM sqlite_master WHERE type="table"')}
    db.close()
    missing = [t for t in GPKG_TABLES if t not in have]
    if not missing:
        return gpkg
    td = tempfile.TemporaryDirectory(prefix='lastbook-region-')
    tempdirs.append(td)
    copy = Path(td.name) / Path(gpkg).name
    shutil.copyfile(gpkg, copy)
    db = sqlite3.connect(copy)
    for t in missing:
        db.execute(f'CREATE TABLE {t}({GPKG_TABLES[t]})')
        print(f'stubbed missing table {t}', flush=True)
    db.commit()
    db.close()
    return copy


def data_as_of(gpkg):
    """The newest ODbL timestamp in the extract, else the file mtime; ISO-8601 UTC."""
    try:
        db = sqlite3.connect(f'file:{gpkg}?mode=ro', uri=True)
        rows = db.execute('SELECT last_change FROM gpkg_contents WHERE last_change IS NOT NULL').fetchall()
        db.close()
        if rows:
            s = max(r[0] for r in rows)
            dt = datetime.fromisoformat(s.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    except (sqlite3.Error, ValueError):
        pass
    return datetime.fromtimestamp(Path(gpkg).stat().st_mtime, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def clip(nat, box):
    """Keep only features whose bbox touches the box; the R*Tree is the spatial index, so clip through it."""
    w, s, e, n = box
    db = sqlite3.connect(nat)
    # Delete feat rows first: the subquery needs the feat_idx rows still present.
    db.execute('DELETE FROM feat WHERE id IN (SELECT id FROM feat_idx WHERE NOT (maxx >= ? AND minx <= ? AND maxy >= ? AND miny <= ?))', (w, e, s, n))
    db.execute('DELETE FROM feat_idx WHERE NOT (maxx >= ? AND minx <= ? AND maxy >= ? AND miny <= ?)', (w, e, s, n))
    db.execute('DELETE FROM poi WHERE lon < ? OR lon > ? OR lat < ? OR lat > ?', (w, e, s, n))
    db.execute('CREATE INDEX IF NOT EXISTS poi_lonlat ON poi(lon, lat)')
    db.commit()    # VACUUM cannot run inside a transaction
    db.execute('VACUUM')
    db.commit()
    db.close()


def rebuild_places(data, label):
    """derived/geo/places.sqlite, matching tools/build_places.py's schema (the app selects kind and source)."""
    places = data / 'derived' / 'geo' / 'places.sqlite'
    places.unlink(missing_ok=True)
    db = sqlite3.connect(places)
    db.executescript('''CREATE TABLE place(id INTEGER PRIMARY KEY, name TEXT, kind TEXT, detail TEXT, lat REAL, lon REAL, rank INTEGER, source TEXT);
      CREATE VIRTUAL TABLE place_fts USING fts5(name, detail, content='place', content_rowid='id', tokenize='unicode61');''')
    src = sqlite3.connect(f'file:{data / "derived" / "geo" / "national.sqlite"}?mode=ro', uri=True)
    ins = 'INSERT INTO place(name,kind,detail,lat,lon,rank,source) VALUES (?,?,?,?,?,?,?)'
    n = 0
    for name, cls, lon, lat in src.execute("SELECT name, cls, lon, lat FROM poi WHERE name IS NOT NULL AND name<>''"):
        db.execute(ins, (name, cls.replace('_', ' '), label, lat, lon, 4, 'OpenStreetMap'))
        n += 1
    for cls, name, g in src.execute("SELECT cls, name, geom FROM feat WHERE layer='place' AND name IS NOT NULL"):
        _, _, x, y = struct.unpack_from('<iiii', g)
        db.execute(ins, (name, cls, label, y / 1e6, x / 1e6, 1, 'OpenStreetMap'))
        n += 1
    db.execute("INSERT INTO place_fts(place_fts) VALUES ('rebuild')")
    db.commit()
    db.close()
    src.close()
    return n


def write_map_placeholder(data):
    """An empty map.sqlite with the shipped schema: state maps keep their detail in national.sqlite."""
    m = data / 'derived' / 'geo' / 'map.sqlite'
    m.unlink(missing_ok=True)
    db = sqlite3.connect(m)
    db.executescript('''CREATE TABLE feat(id INTEGER PRIMARY KEY, layer TEXT, cls TEXT, name TEXT, minz INTEGER, geom BLOB);
      CREATE VIRTUAL TABLE feat_idx USING rtree(id, minx, maxx, miny, maxy, minz, maxz);
      CREATE TABLE poi(id INTEGER PRIMARY KEY, cls TEXT, name TEXT, lon REAL, lat REAL);
      CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
      CREATE INDEX poi_cls ON poi(cls, lon, lat);''')
    db.commit()
    db.close()


def main():
    ap = argparse.ArgumentParser(description='Build a Lastbook map set for a place from a Geofabrik free GeoPackage')
    ap.add_argument('extract', help='the .gpkg, or a .zip containing one (Geofabrik -free-gpkg-latest.zip)')
    ap.add_argument('--name', required=True, help='map-set name, e.g. BR-RJ (letters, digits, hyphens)')
    ap.add_argument('--label', required=True, help='human name, e.g. "Rio de Janeiro"')
    ap.add_argument('--box', help='clip to west,south,east,north degrees (a state extract holds its neighbours)')
    ap.add_argument('--coast', help='an .osm.pbf holding natural=coastline ways, for a real sea edge (needs pyosmium)')
    ap.add_argument('--coast-close', type=float, help='longitude well out to sea from the open coast, e.g. 10 for Brazil')
    ap.add_argument('--data', help='LastbookData folder (else $LASTBOOK_DATA, else the repo root)')
    # argparse would read a dash-leading value such as --box -46.7,-24.9,-40.1,-19.9 as an option; merge it.
    argv, i = [], 0
    while i < len(sys.argv[1:]):
        a = sys.argv[i + 1]
        if a in ('--name', '--label', '--box', '--coast', '--coast-close', '--data') and i + 2 <= len(sys.argv) - 1 and \
           sys.argv[i + 2].startswith('-') and not sys.argv[i + 2].startswith('--'):
            argv.append(f'{a}={sys.argv[i + 2]}')
            i += 2
        else:
            argv.append(a)
            i += 1
    a = ap.parse_args(argv)

    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]*', a.name):
        die(f'--name {a.name!r}: use letters, digits and hyphens, e.g. BR-RJ')
    box = None
    if a.box:
        try:
            box = [float(v) for v in a.box.split(',')]
        except ValueError:
            die(f'--box {a.box!r}: expected west,south,east,north')
        if len(box) != 4 or not (-180 <= box[0] < box[2] <= 180) or not (-90 <= box[1] < box[3] <= 90):
            die(f'--box {a.box!r}: expected west,south,east,north with west<east, south<north')
    if a.coast:
        if not Path(a.coast).exists():
            die(f'--coast {a.coast}: no such file')
        if a.coast_close is None:
            die('--coast needs --coast-close: a longitude well out to sea from the open coast')
        if not -180 < a.coast_close < 180:
            die(f'--coast-close {a.coast_close}: expected a longitude between -180 and 180')
        if subprocess.run([sys.executable, '-B', '-c', 'import osmium'], capture_output=True).returncode:
            die(f'pyosmium is not importable by {sys.executable} — the --coast step needs it (pip install osmium)')
    else:
        if a.coast_close is not None:
            die('--coast-close without --coast')
        print('note: no --coast: the free GeoPackage has no coastline, so the sea edge stays the base world map (see docs/MAPS.md)', flush=True)

    data = Path(a.data or os.environ.get('LASTBOOK_DATA') or HERE)
    if not data.is_dir():
        die(f'--data {data}: no such folder')
    geo = data / 'derived' / 'geo'
    geo.mkdir(parents=True, exist_ok=True)
    nat = geo / 'national.sqlite'

    tempdirs = []
    gpkg = open_extract(a.extract, tempdirs)
    gpkg = ensure_tables(gpkg, tempdirs)
    t0 = time.time()

    # build_map.py runs main() on import, so launch it as a subprocess; -I keeps it stdlib-only.
    run([sys.executable, '-I', '-B', HERE / 'tools' / 'build_map.py', gpkg, nat])

    if box:
        clip(nat, box)
    db = sqlite3.connect(nat)
    r = db.execute('SELECT count(*) FROM feat').fetchone()
    if not r[0]:
        db.close()
        die('the extract left no map features after clipping — check --box')
    b = db.execute('SELECT MIN(minx), MIN(miny), MAX(maxx), MAX(maxy) FROM feat_idx').fetchone()
    bounds = f'{b[0]:.4f},{b[1]:.4f},{b[2]:.4f},{b[3]:.4f}' if b[0] is not None else ''
    db.close()

    if a.coast:
        run([sys.executable, '-B', HERE / 'tools' / 'build_coast.py', a.coast, nat, f'{a.coast_close:g}'])
    nfeat = sqlite3.connect(f'file:{nat}?mode=ro', uri=True).execute('SELECT count(*) FROM feat').fetchone()[0]

    status = json.dumps({'state': 'complete', 'stage': 'ready', 'features': nfeat})
    asof = data_as_of(gpkg)
    db = sqlite3.connect(nat)
    db.execute('DELETE FROM meta')
    db.executemany('INSERT INTO meta VALUES (?,?)', [
        ('status', status),
        ('label', a.label),
        ('source', f'OpenStreetMap contributors, via Geofabrik {Path(a.extract).name} (ODbL 1.0)'),
        ('data_as_of', asof),
        ('bounds', bounds),
        ('built', time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())),
    ])
    db.commit()
    db.close()
    (geo / 'national-status.json').write_text(status, encoding='utf-8')

    nplaces = rebuild_places(data, a.label)
    write_map_placeholder(data)
    (geo / 'socal-cells.json').write_text('[]', encoding='utf-8')

    files = {}
    for f in sorted(geo.iterdir()):
        if f.is_file():
            files[f.relative_to(data).as_posix()] = f.stat().st_size
    (data / 'map-set.json').write_text(json.dumps({
        'name': a.name,
        'files': files,
        'bytes': sum(files.values()),
        'seconds': round(time.time() - t0),
    }, indent=1) + '\n', encoding='utf-8')

    print(f'done: {a.name} "{a.label}" — {nfeat} map features, {nplaces} places, {sum(files.values()) / 1e6:.0f} MB in {len(files)} files')
    for td in tempdirs:
        td.cleanup()


if __name__ == '__main__':
    main()
