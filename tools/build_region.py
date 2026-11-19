#!/usr/bin/env python3
"""Build one UK region's whole map set into a folder, by running this repository's OpenStreetMap builders in order.

  python3 tools/build_region.py --src WORK/src --out WORK/regions GB-LON GB-SE

WORK/src holds what the builders read (nothing is downloaded here):
  england.gpkg       Geofabrik england-latest-free.gpkg.zip, unzipped (OpenStreetMap, ODbL)
  england.osm.pbf    Geofabrik england-latest.osm.pbf
  dem/               Copernicus GLO-30 cells for the region (see tools/build_terrain.py)
Each region goes to WORK/regions/<CODE>/ laid out like a library: derived/geo/*.sqlite,
derived/geo/addresses/<CODE>.sqlite, library-data/geography/resources/atlas.sqlite and map-set.json. Nothing here touches a
real library; copy those folders into one yourself (one map set at a time). The box for each code is `bbox.padded_0_15` in
docs/regions-uk-proposed.json. Per region: map, empty map.sqlite, addresses, terrain, water, dams, orchards, atlas, building
heights, place finder. Aerial photos are not built (there is no UK source). Needs pyosmium, numpy, Pillow, tifffile and
imagecodecs on the build machine only. A step that fails stops the run and prints its error.
"""
import argparse, json, os, shutil, sqlite3, subprocess, sys, time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CREDIT = ('Map data via Geofabrik (ODbL). Contains modified Copernicus DEM data, © DLR e.V. 2010-2014 and © Airbus Defence and Space '
          'GmbH 2014-2018, provided under COPERNICUS by the European Union and ESA')
SRC_GPKG = 'OpenStreetMap contributors, via Geofabrik england-latest-free.gpkg.zip (ODbL 1.0)'
SRC_PBF = 'OpenStreetMap contributors (ODbL), via Geofabrik england-latest.osm.pbf'
MAP_SET_FILES = ['derived/geo/national-status.json', 'derived/geo/map.sqlite', 'derived/geo/national.sqlite', 'derived/geo/terrain.sqlite',
                 'derived/geo/water.sqlite', 'derived/geo/crops.sqlite', 'library-data/geography/resources/atlas.sqlite',
                 'derived/geo/buildings.sqlite', 'derived/geo/places.sqlite']     # what map-set.json lists, and what a finished build replaces
NAMES = {'GB-NE': 'North East England', 'GB-NW': 'North West England', 'GB-YH': 'Yorkshire and The Humber', 'GB-EM': 'East Midlands',
         'GB-WM': 'West Midlands', 'GB-EE': 'East of England', 'GB-LON': 'London', 'GB-SE': 'South East England',
         'GB-SW': 'South West England'}


def run(label, args, env=None):
    t0 = time.time()
    r = subprocess.run([sys.executable, '-B', *map(str, args)], cwd=REPO, env=dict(os.environ, **(env or {})), capture_output=True, text=True)
    tail = (r.stdout.strip().splitlines() or [''])[-1]
    print(f'  {label}: {"ok" if r.returncode == 0 else "FAILED"} in {time.time() - t0:.0f}s: {tail}', flush=True)
    if r.returncode:
        print(r.stderr[-1500:], flush=True)
        raise SystemExit(f'{label} failed')


def publish(work, final, code):
    """Move a finished build over the region's folder, file by file. Only these files are replaced (whole, so no tile or row of an earlier
    run or box survives in them); anything else in that folder is left alone."""
    tails = ('', '-wal', '-shm', '-journal')
    for rel in [*MAP_SET_FILES, f'derived/geo/addresses/{code}.sqlite', 'map-set.json']:
        dst = final / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        for tail in tails[1:]:                     # an old file's journal must not be paired with the new file
            Path(f'{dst}{tail}').unlink(missing_ok=True)
        for tail in tails:
            src = Path(f'{work / rel}{tail}')
            if src.exists():
                os.replace(src, Path(f'{dst}{tail}'))


def build(code, src, regions, as_of_iso, as_of_text, workers):
    gpkg, pbf, dem = src / 'england.gpkg', src / 'england.osm.pbf', src / 'dem'
    boxes = {r['code']: r['bbox']['padded_0_15'] for r in json.loads((REPO / 'docs/regions-uk-proposed.json').read_text(encoding='utf-8'))['regions']}
    bbox = ','.join(str(v) for v in boxes[code])      # --bbox=... keeps a negative west value from reading as a flag
    final = regions / code
    out = regions / f'{code}.building'            # built here and moved over `final` only when every step has worked, so a failed run costs nothing
    shutil.rmtree(out, ignore_errors=True)
    geo = out / 'derived/geo'
    (geo / 'addresses').mkdir(parents=True, exist_ok=True)
    (out / 'library-data/geography/resources').mkdir(parents=True, exist_ok=True)
    print(f'{code} {bbox}', flush=True)
    t0 = time.time()
    run('map', ['tools/build_map.py', gpkg, geo / 'national.sqlite', f'--bbox={bbox}', '--source', SRC_GPKG, '--as-of', as_of_iso])
    # street tiles need an (empty) map.sqlite beside national.sqlite, and the app reads national-status.json
    db = sqlite3.connect(geo / 'map.sqlite')
    db.executescript('''CREATE TABLE IF NOT EXISTS feat(id INTEGER PRIMARY KEY, layer TEXT, cls TEXT, name TEXT, minz INTEGER, geom BLOB);
      CREATE VIRTUAL TABLE IF NOT EXISTS feat_idx USING rtree(id, minx, maxx, miny, maxy, minz, maxz);
      CREATE TABLE IF NOT EXISTS poi(id INTEGER PRIMARY KEY, cls TEXT, name TEXT, lon REAL, lat REAL);
      CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);''')
    db.commit(); db.close()
    (geo / 'national-status.json').write_text('{"state":"complete"}', encoding='utf-8')
    run('addresses', ['tools/build_addresses_osm.py', pbf, geo / f'addresses/{code}.sqlite', f'--bbox={bbox}', '--source', SRC_PBF])
    run('terrain', ['tools/build_terrain.py', f'--bbox={bbox}', '--workers', workers],
        {'LASTBOOK_TERRAIN_SRC': str(dem), 'LASTBOOK_TERRAIN_OUT': str(geo / 'terrain.sqlite'),
         'LASTBOOK_TERRAIN_SOURCE': 'Copernicus DEM GLO-30 (DSM), 2021 release'})
    env = {'LASTBOOK_GEO': str(geo), 'LASTBOOK_UNITS': 'metric'}
    run('water', ['tools/build_water.py', 'osm'], env)
    run('dams', ['tools/build_water.py', 'dams-osm', pbf, bbox], env)
    run('crops', ['tools/build_crops_osm.py', gpkg, geo / 'crops.sqlite', f'--bbox={bbox}', '--source', SRC_GPKG])
    run('atlas', ['tools/build_atlas_osm.py', pbf, out / 'library-data/geography/resources/atlas.sqlite', f'--bbox={bbox}', '--source', SRC_PBF])
    run('heights', ['tools/build_osm_heights.py', pbf],
        {'BUILDINGS_OUT': str(geo / 'buildings.sqlite'), 'LASTBOOK_BBOX': bbox, 'LASTBOOK_BUILDINGS_SOURCE': SRC_PBF})
    run('places', ['tools/build_places_osm.py', geo / 'national.sqlite', geo / f'addresses/{code}.sqlite', geo / 'places.sqlite',
                   '--area', NAMES[code]])
    size = {f: (out / f).stat().st_size for f in MAP_SET_FILES}
    (out / 'map-set.json').write_text(json.dumps({'name': code, 'files': size, 'bytes': sum(size.values()), 'seconds': round(time.time() - t0),
                                                 'units': 'metric', 'country': 'GB', 'credit': CREDIT, 'as_of': as_of_text}, indent=1),
                                      encoding='utf-8')
    publish(out, final, code)
    shutil.rmtree(out, ignore_errors=True)
    print(f'{code} done in {time.time() - t0:.0f}s, {sum(size.values()) / 1e9:.2f} GB', flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('codes', nargs='+', help=f'region codes: {", ".join(sorted(NAMES))}')
    ap.add_argument('--src', required=True, type=Path, help='folder with england.gpkg, england.osm.pbf and dem/')
    ap.add_argument('--out', required=True, type=Path, help='folder that gets one subfolder per region')
    ap.add_argument('--as-of', required=True, help='when the OpenStreetMap extract was cut, as 2026-11-17T02:05:48Z (the file header has it)')
    ap.add_argument('--workers', default='8', help='terrain worker processes')
    a = ap.parse_args()
    for c in a.codes:
        if c not in NAMES:
            sys.exit(f'unknown region code {c}; one of {", ".join(sorted(NAMES))}')
    text = time.strftime('%d %b %Y', time.strptime(a.as_of[:10], '%Y-%m-%d')).lstrip('0')
    for c in a.codes:
        build(c, a.src, a.out, a.as_of, text, a.workers)


if __name__ == '__main__':
    main()
