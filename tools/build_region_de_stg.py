#!/usr/bin/env python3
"""Stuttgart (DE-STG): an offline map set with places, help points and street addresses.

  python3 tools/build_region_de_stg.py fetch    # downloads the Baden-Württemberg extract and the city boundary
  python3 tools/build_region_de_stg.py build    # writes the data folder derived/regions/DE-STG/data/
  python3 tools/build_region_de_stg.py check    # validates it; exits non-zero on any failure
  python3 tools/build_region_de_stg.py demo     # adds an empty library beside it, then prints the command below
  python3 server.py --data derived/regions/DE-STG/demo --no-index   # the map, place and address search, offline

Everything goes under derived/regions/DE-STG/, so no existing map set is touched. The region keeps a short
city code, DE-STG, because ISO 3166-2 stops at the state (DE-BW).

Sources (all redistributable; details, dates and checksums end up in derived/regions/DE-STG/build.json):
  - OpenStreetMap via Geofabrik, baden-wuerttemberg-latest.osm.pbf (ODbL 1.0, "© OpenStreetMap contributors"):
    streets, water, land use, buildings and named places, cut to the city boundary.
  - The Stuttgart city boundary from OpenStreetMap (relation 62375) through Nominatim (ODbL 1.0).
  - Street addresses from the same extract's addr:housenumber and addr:street tags (ODbL 1.0).

The fetch step needs the network and osmium-tool (brew install osmium-tool) for the extract and export; build and
check do not touch the network. No other dependency.
"""
import argparse
import datetime
import hashlib
import json
import math
import re
import shutil
import sqlite3
import struct
import subprocess
import sys
import time
import urllib.request
from array import array
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

REGION = 'DE-STG'
BASE = ROOT / 'derived' / 'regions' / REGION
SOURCE = BASE / 'source'
WORK = BASE / 'work'
DATA = BASE / 'data'
GEO = DATA / 'derived' / 'geo'
REPORT = BASE / 'build.json'
Q = 1e6

PBF_URL = 'https://download.geofabrik.de/europe/germany/baden-wuerttemberg-latest.osm.pbf'
BOUNDARY_URL = ('https://nominatim.openstreetmap.org/search?q=Stuttgart&format=json&polygon_geojson=1&limit=1')
BOUNDARY_UA = 'lastbook-region-builder/1.0 (offline map build; hello@lastbook.org)'
ATTRIBUTION = '© OpenStreetMap contributors'
LICENCE = 'ODbL 1.0'

ROAD_Z = {'motorway': 5, 'trunk': 6, 'motorway_link': 10, 'trunk_link': 10, 'primary': 8, 'primary_link': 12,
          'secondary': 10, 'secondary_link': 13, 'tertiary': 11, 'tertiary_link': 13, 'residential': 13,
          'unclassified': 13, 'living_street': 14, 'pedestrian': 14, 'busway': 14, 'service': 15,
          'track': 13, 'track_grade1': 13, 'track_grade2': 13, 'track_grade3': 13, 'track_grade4': 13,
          'track_grade5': 13, 'footway': 15, 'path': 14, 'cycleway': 14, 'steps': 16, 'bridleway': 14}
ROAD_SKIP = {'proposed', 'construction', 'abandoned', 'platform', 'bus_stop', 'razed', 'planned', 'corridor'}
LANDUSE_KEEP = {'park': 'park', 'forest': 'green', 'grass': 'green', 'meadow': 'green', 'scrub': 'green',
                'heath': 'green', 'recreation_ground': 'park', 'cemetery': 'park', 'allotments': 'farm',
                'farmland': 'farm', 'orchard': 'farm', 'vineyard': 'farm', 'farmyard': 'farm',
                'residential': 'res', 'commercial': 'com', 'retail': 'com', 'industrial': 'ind',
                'military': 'ind', 'quarry': 'ind', 'landfill': 'ind'}
PLACE_KEEP = {'city', 'town', 'village', 'suburb', 'borough', 'quarter', 'neighbourhood', 'hamlet', 'locality'}
PLACE_Z = {'city': 6, 'town': 9, 'village': 11, 'borough': 9, 'suburb': 12, 'quarter': 13,
           'neighbourhood': 14, 'hamlet': 14, 'locality': 14}
POI_AMENITY = {'hospital', 'clinic', 'doctors', 'pharmacy', 'dentist', 'veterinary', 'fire_station', 'police',
               'drinking_water', 'toilet', 'shelter', 'community_centre', 'town_hall', 'school', 'library',
               'kindergarten', 'college', 'university', 'nursing_home', 'post_office', 'courthouse', 'embassy',
               'fuel', 'shelter', 'water_point'}
POI_AMENITY_ALIAS = {'toilets': 'toilet', 'townhall': 'town_hall', 'dentists': 'dentist', 'childcare': 'kindergarten',
                     'doctors': 'doctors'}
POI_SHOP = {'supermarket', 'convenience', 'doityourself', 'hardware', 'garden_centre', 'bicycle'}
POI_MAN_MADE = {'water_tower', 'water_works', 'water_tank', 'comms_tower'}
POI_STOP = {'stuttgart', 'baden-wuerttemberg', 'bw', 'deutschland', 'de'}


def log(*args):
    print(time.strftime('%H:%M:%S'), *args, flush=True)


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def download(url, dest, headers=None):
    log('download', url)
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=180) as response, open(dest, 'wb') as out:
        shutil.copyfileobj(response, out, 1 << 22)
    return dest


# ------------------------------------------------------------------ geometries ----

def wkb_flat(parts):
    """Pack rings/lines the way tools/build_map.py does: nparts, then per part npts and int32 lon/lat deltas."""
    a = array('i', [len(parts)])
    for part in parts:
        n = len(part) // 2
        a.append(n)
        lx = ly = 0
        for i in range(n):
            x, y = int(round(part[2 * i] * Q)), int(round(part[2 * i + 1] * Q))
            a.append(x - lx)
            a.append(y - ly)
            lx, ly = x, y
    return a.tobytes()


def flat_bbox(parts):
    xs = [v for part in parts for v in part[0::2]]
    ys = [v for part in parts for v in part[1::2]]
    return min(xs), max(xs), min(ys), max(ys)


def area_z(minx, maxx, miny, maxy, base):
    size = max(maxx - minx, maxy - miny)
    if size <= 0:
        return 17
    return max(base, min(16, int(math.log2(360 / size)) - 4))


def simplify(flat, tol):
    if len(flat) <= 4 or tol <= 0:
        return flat
    out = [flat[0], flat[1]]
    px, py = flat[0], flat[1]
    for i in range(2, len(flat) - 2, 2):
        x, y = flat[i], flat[i + 1]
        if abs(x - px) > tol or abs(y - py) > tol:
            out += [x, y]
            px, py = x, y
    out += [flat[-2], flat[-1]]
    return out


def geojson_parts(geometry):
    """(kind, parts) for a GeoJSON geometry, or (None, None)."""
    kind = geometry.get('type')
    coords = geometry.get('coordinates')
    if not coords:
        return None, None
    if kind == 'Point':
        return 'point', [[coords[0], coords[1]]]
    if kind == 'LineString':
        return 'line', [list(coords)]
    if kind == 'Polygon':
        return 'polygon', [list(ring) for ring in coords]
    if kind == 'MultiLineString':
        return 'line', [list(part) for part in coords]
    if kind == 'MultiPolygon':
        return 'polygon', [list(ring) for polygon in coords for ring in polygon]
    return None, None


def flatten(coords):
    out = []
    for x, y in coords:
        out += [x, y]
    return out


# ------------------------------------------------------------------ fetch ----

def fetch():
    SOURCE.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    pbf = SOURCE / 'baden-wuerttemberg.osm.pbf'
    if not pbf.exists():
        download(PBF_URL, pbf)
    boundary_file = SOURCE / 'stuttgart-boundary.json'
    if not boundary_file.exists():
        download(BOUNDARY_URL, boundary_file, {'User-Agent': BOUNDARY_UA})
    try:
        hit = json.loads(boundary_file.read_text(encoding='utf-8'))[0]
    except (IndexError, json.JSONDecodeError) as error:
        raise SystemExit(f'{boundary_file} has no usable boundary: {error}')
    polygon = {'type': 'Feature', 'properties': {'name': hit.get('display_name', 'Stuttgart')},
               'geometry': hit['geojson']}
    (WORK / 'stuttgart-boundary.geojson').write_text(json.dumps(polygon), encoding='utf-8')
    city = WORK / 'stuttgart.osm.pbf'
    if not city.exists():
        log('extract', hit.get('display_name', 'Stuttgart'))
        subprocess.run(['osmium', 'extract', '--overwrite', '--polygon', str(WORK / 'stuttgart-boundary.geojson'),
                        '--output', str(city), str(pbf)], check=True)
    stream = WORK / 'stuttgart.geojsonseq'
    if not stream.exists():
        log('export')
        subprocess.run(['osmium', 'export', '--overwrite', '--add-unique-id', 'type_id',
                        '--geometry-types', 'point,linestring,polygon', '--output-format', 'geojsonseq',
                        '--output', str(stream), str(city)], check=True)
    data_as_of = None
    try:
        info = subprocess.run(['osmium', 'fileinfo', '-e', str(pbf)], check=True, capture_output=True, text=True).stdout
        found = re.search(r'osmosis_replication_timestamp=(\S+)', info)
        data_as_of = found.group(1) if found else None
    except (subprocess.CalledProcessError, OSError):
        pass
    sizes = {}
    for path in (pbf, city, stream):
        sizes[path.name] = {'bytes': path.stat().st_size, 'sha256': sha256(path)}
    fetched = {
        'sources': [
            {'name': 'OpenStreetMap via Geofabrik baden-wuerttemberg-latest.osm.pbf', 'url': PBF_URL,
             'licence': f'{LICENCE}, {ATTRIBUTION}', 'data_as_of': data_as_of,
             'fetched': time.strftime('%Y-%m-%dT%H:%M:%S')},
            {'name': 'Stuttgart city boundary, OpenStreetMap relation 62375 via Nominatim', 'url': BOUNDARY_URL,
             'licence': f'{LICENCE}, {ATTRIBUTION}', 'fetched': time.strftime('%Y-%m-%dT%H:%M:%S')},
        ],
        'files': sizes,
    }
    (SOURCE / 'fetched.json').write_text(json.dumps(fetched, indent=1, ensure_ascii=False), encoding='utf-8')
    log('fetched', json.dumps(sizes, ensure_ascii=False))


# ------------------------------------------------------------------ build ----

def map_poi(tags):
    amenity = tags.get('amenity')
    if amenity:
        cls = POI_AMENITY_ALIAS.get(amenity, amenity)
        if cls in POI_AMENITY:
            return cls
    shop = tags.get('shop')
    if shop in POI_SHOP:
        return 'bicycle_shop' if shop == 'bicycle' else shop
    if tags.get('tourism') == 'camp_site':
        return 'camp_site'
    if tags.get('man_made') in POI_MAN_MADE:
        return tags['man_made']
    if tags.get('natural') == 'spring':
        return 'spring'
    if tags.get('emergency') == 'assembly_point':
        return 'assembly_point'
    if tags.get('leisure') == 'sports_centre':
        return None
    return None


def feature_rows(tags, kind, parts):
    """(layer, cls, name, minz, parts) for a tagged OSM object; may be empty."""
    name = (tags.get('name') or '').strip() or None
    rows = []
    if kind == 'polygon':
        if tags.get('building'):
            rows.append(('bldg', tags.get('building') or '', None, 15, [simplify(parts[0], 0.000002)]))
        natural = tags.get('natural')
        if natural == 'water' or tags.get('landuse') in ('reservoir', 'basin'):
            rows.append(('water', 'water', name, area_z(*flat_bbox(parts), 7), [simplify(p, 0.00001) for p in parts]))
        elif natural == 'wetland' or tags.get('landuse') == 'salt_pond':
            rows.append(('wet', 'wetland', name, area_z(*flat_bbox(parts), 7), [simplify(p, 0.00001) for p in parts]))
        elif natural == 'beach':
            rows.append(('beach', 'beach', name, area_z(*flat_bbox(parts), 10), [simplify(p, 0.00001) for p in parts]))
        landuse = tags.get('landuse')
        if landuse in LANDUSE_KEEP:
            rows.append(('land', LANDUSE_KEEP[landuse], name, area_z(*flat_bbox(parts), 9),
                         [simplify(p, 0.00001) for p in parts]))
        elif tags.get('leisure') in ('park', 'nature_reserve') or tags.get('boundary') == 'protected_area':
            rows.append(('land', 'park', name, area_z(*flat_bbox(parts), 8), [simplify(p, 0.00001) for p in parts]))
    elif kind == 'line':
        highway = tags.get('highway')
        if highway and highway not in ROAD_SKIP:
            rows.append(('road', highway, name or tags.get('ref'), ROAD_Z.get(highway, 15), parts))
        railway = tags.get('railway')
        if railway and railway not in ('abandoned', 'razed', 'proposed', 'construction'):
            rows.append(('rail', railway, name, 10 if railway == 'rail' else 13, parts))
        waterway = tags.get('waterway')
        if waterway and waterway not in ('riverbank', 'dock', 'boatyard'):
            rows.append(('waterway', waterway, name, 10 if waterway == 'river' else 13, parts))
    elif kind == 'point':
        place = tags.get('place')
        if place in PLACE_KEEP and name:
            rows.append(('place', place, name, PLACE_Z.get(place, 14), parts))
    return rows


def fetched_data_as_of():
    """The extract's own replication timestamp (what Geofabrik means by 'contains all OSM data up to'), date only."""
    try:
        fetched = json.loads((SOURCE / 'fetched.json').read_text(encoding='utf-8'))
        stamp = fetched['sources'][0].get('data_as_of') or ''
    except (OSError, ValueError, IndexError, KeyError):
        stamp = ''
    return stamp[:10] or datetime.datetime.fromtimestamp(
        (SOURCE / 'baden-wuerttemberg.osm.pbf').stat().st_mtime, datetime.timezone.utc).strftime('%Y-%m-%d')


def build_national():
    dst = sqlite3.connect(GEO / 'national.sqlite')
    dst.executescript('''PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;
      CREATE TABLE feat(id INTEGER PRIMARY KEY, layer TEXT, cls TEXT, name TEXT, minz INTEGER, geom BLOB);
      CREATE VIRTUAL TABLE feat_idx USING rtree(id, minx, maxx, miny, maxy, minz, maxz);
      CREATE TABLE poi(id INTEGER PRIMARY KEY, cls TEXT, name TEXT, lon REAL, lat REAL);
      CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);''')
    features = pois = 0
    addresses = {}
    seen_address = set()
    bounds = None

    def add_feature(layer, cls, name, minz, parts):
        nonlocal features, bounds
        if not parts:
            return
        features += 1
        minx, maxx, miny, maxy = flat_bbox(parts)
        bounds = (minx, miny, maxx, maxy) if bounds is None else (
            min(bounds[0], minx), min(bounds[1], miny), max(bounds[2], maxx), max(bounds[3], maxy))
        dst.execute('INSERT INTO feat VALUES (?,?,?,?,?,?)', (features, layer, cls, name, minz, wkb_flat(parts)))
        dst.execute('INSERT INTO feat_idx VALUES (?,?,?,?,?,?,?)', (features, minx, maxx, miny, maxy, minz, 30))

    def add_address(tags, lon, lat):
        number = (tags.get('addr:housenumber') or '').strip()
        street = (tags.get('addr:street') or '').strip()
        if not number or not street or lon is None or lat is None:
            return
        number = re.sub(r'\s+', '', number).upper()
        match = re.match(r'\d{1,4}[A-Z]?', number)
        if not match:
            return
        number = match.group(0)
        postcode = (tags.get('addr:postcode') or '').strip()
        if not re.fullmatch(r'\d{5}', postcode):
            postcode = ''
        district = (tags.get('addr:suburb') or tags.get('addr:district') or '').strip()
        city = (tags.get('addr:city') or 'Stuttgart').strip()
        key = (number, street, postcode, round(lat, 5), round(lon, 5))
        if key in seen_address:
            return
        seen_address.add(key)
        # keyed by postcode and district too: the same street and number exist in more than one district, and a
        # postcode-less object must not overwrite a mapped one
        addresses[(street, number, postcode, district)] = (street, number, city, postcode, district, round(lat, 6), round(lon, 6))

    with open(WORK / 'stuttgart.geojsonseq', encoding='utf-8') as stream:
        for line in stream:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            props = obj.get('properties') or {}
            kind, parts = geojson_parts(obj.get('geometry') or {})
            if kind is None:
                continue
            if kind == 'point':
                lon, lat = parts[0]
            else:
                parts = [flatten(part) for part in parts]
                minx, maxx, miny, maxy = flat_bbox(parts)
                lon, lat = (minx + maxx) / 2, (miny + maxy) / 2
            add_address(props, lon, lat)
            if not props:
                continue
            for layer, cls, name, minz, geometry in feature_rows(props, kind, parts):
                add_feature(layer, cls, name, minz, geometry)
            cls = map_poi(props)
            if cls:
                pois += 1
                dst.execute('INSERT INTO poi VALUES (?,?,?,?,?)',
                            (pois, cls, props.get('name'), round(lon, 6), round(lat, 6)))
    dst.execute('CREATE INDEX poi_cls ON poi(cls, lon, lat)')
    dst.executemany('INSERT INTO meta VALUES (?,?)', [
        ('source', f'{ATTRIBUTION}, Geofabrik baden-wuerttemberg-latest.osm.pbf ({LICENCE})'),
        ('data_as_of', fetched_data_as_of()),
        ('bounds', ','.join(f'{v:.4f}' for v in bounds)),
        ('region', REGION),
        ('help_points', 'all classes from OpenStreetMap (ODbL 1.0)'),
    ])
    dst.commit()
    dst.execute('VACUUM')
    dst.close()

    empty = sqlite3.connect(GEO / 'map.sqlite')
    try:
        empty.executescript('''CREATE TABLE feat(id INTEGER PRIMARY KEY, layer TEXT, cls TEXT, name TEXT, minz INTEGER, geom BLOB);
          CREATE VIRTUAL TABLE feat_idx USING rtree(id, minx, maxx, miny, maxy, minz, maxz);
          CREATE TABLE poi(id INTEGER PRIMARY KEY, cls TEXT, name TEXT, lon REAL, lat REAL);
          CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);''')
        meta_db = sqlite3.connect(f'file:{GEO / "national.sqlite"}?mode=ro', uri=True)
        try:
            empty.executemany('INSERT INTO meta VALUES (?,?)', meta_db.execute(
                "SELECT key,value FROM meta WHERE key IN ('source','data_as_of','bounds','region')").fetchall())
        finally:
            meta_db.close()
        empty.commit()
    finally:
        empty.close()
    return {'features': features, 'pois': pois, 'addresses': len(addresses), 'bounds': bounds}, addresses


def build_addresses(addresses):
    from engine.address_search import normalize_as
    path = GEO / 'addresses' / f'{REGION}.sqlite'
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for street, number, city, postcode, district, lat, lon in addresses.values():
        norm = normalize_as('de-1', street)
        if not norm:
            continue
        rows.append((number, street, norm, city, REGION, postcode, lat, lon, district))
    db = sqlite3.connect(path)
    try:
        db.executescript(
            'PRAGMA page_size=8192; PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;'
            'CREATE TABLE addr(num TEXT, street TEXT, norm TEXT, city TEXT, state TEXT, zip TEXT, lat REAL, lon REAL, district TEXT);'
            'CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);')
        db.executemany('INSERT INTO addr VALUES (?,?,?,?,?,?,?,?,?)', rows)
        db.execute('CREATE INDEX addr_norm ON addr(norm, num)')
        db.execute('CREATE INDEX addr_zip ON addr(zip)')
        db.executemany('INSERT INTO meta VALUES (?,?)', [
            ('region', REGION), ('norm', 'de-1'), ('count', str(len(rows))),
            ('source', f'{ATTRIBUTION} ({LICENCE})'),
            ('built', time.strftime('%Y-%m-%dT%H:%M:%S')),
        ])
        db.commit()
    finally:
        db.close()
    return {'addresses': len(rows)}


def build_places():
    path = GEO / 'places.sqlite'
    path.unlink(missing_ok=True)
    db = sqlite3.connect(path)
    counts = {}
    try:
        db.executescript(
            "CREATE TABLE place(id INTEGER PRIMARY KEY, name TEXT, kind TEXT, detail TEXT, lat REAL, lon REAL, rank INTEGER, source TEXT);"
            "CREATE VIRTUAL TABLE place_fts USING fts5(name, detail, content='place', content_rowid='id', tokenize='unicode61');")
        insert = 'INSERT INTO place(name,kind,detail,lat,lon,rank,source) VALUES (?,?,?,?,?,?,?)'

        def add(kind, items):
            db.executemany(insert, items)
            counts[kind] = len(items)

        def center(geom):
            _, _, x, y = struct.unpack_from('<iiii', geom)
            return x / Q, y / Q

        add('city', [('Stuttgart', 'city', 'Baden-Württemberg, Germany', 48.7758, 9.1829, 0, 'OpenStreetMap')])

        national = sqlite3.connect(f'file:{GEO / "national.sqlite"}?mode=ro', uri=True)
        try:
            place_rows = []
            for cls, name, minx, maxx, miny, maxy in national.execute(
                    "SELECT f.cls, f.name, i.minx, i.maxx, i.miny, i.maxy FROM feat f JOIN feat_idx i ON i.id = f.id "
                    "WHERE f.layer='place' AND f.name IS NOT NULL AND f.name <> ''"):
                place_rows.append((name, cls, 'Stuttgart (OpenStreetMap)', (miny + maxy) / 2, (minx + maxx) / 2, 2,
                                   'OpenStreetMap'))
            add('osm_place', place_rows)

            streets = {}
            for name, minx, maxx, miny, maxy in national.execute(
                    "SELECT f.name, i.minx, i.maxx, i.miny, i.maxy FROM feat f JOIN feat_idx i ON i.id = f.id "
                    "WHERE f.layer='road' AND f.name IS NOT NULL AND f.name <> ''"):
                streets.setdefault(name, []).append(((miny + maxy) / 2, (minx + maxx) / 2))
            street_rows = []
            for name, points in sorted(streets.items()):
                points.sort()
                lat, lon = points[len(points) // 2]
                street_rows.append((name, 'street', 'Stuttgart', lat, lon, 3, 'OpenStreetMap'))
            add('street', street_rows)

            poi_rows = []
            for cls, name, lon, lat in national.execute(
                    "SELECT cls, name, lon, lat FROM poi WHERE name IS NOT NULL AND name <> ''"):
                poi_rows.append((name, cls.replace('_', ' '), 'Stuttgart', lat, lon, 4, 'OpenStreetMap'))
            add('poi', poi_rows)
        finally:
            national.close()

        addr = sqlite3.connect(f'file:{GEO / "addresses" / (REGION + ".sqlite")}?mode=ro', uri=True)
        try:
            postcodes = {}
            for code, lat, lon in addr.execute("SELECT zip, lat, lon FROM addr WHERE zip <> ''"):
                postcodes.setdefault(code, []).append((lat, lon))
            add('postcode', [(code, 'postcode area', 'Stuttgart', sorted(points)[len(points) // 2][0],
                              sorted(points)[len(points) // 2][1], 2, 'OpenStreetMap')
                             for code, points in sorted(postcodes.items())])

            districts = {}
            for district, lat, lon in addr.execute("SELECT district, lat, lon FROM addr WHERE district <> ''"):
                districts.setdefault(district, []).append((lat, lon))
            add('district', [(name, 'district (Stadtbezirk)', 'Stuttgart', sorted(points)[len(points) // 2][0],
                              sorted(points)[len(points) // 2][1], 2, 'OpenStreetMap')
                             for name, points in sorted(districts.items())])
        finally:
            addr.close()

        db.execute("INSERT INTO place_fts(place_fts) VALUES ('rebuild')")
        db.commit()
        db.execute('VACUUM')
    finally:
        db.close()
    return {'places': counts}


def build():
    if not (WORK / 'stuttgart.geojsonseq').exists():
        raise SystemExit('run fetch first: tools/build_region_de_stg.py fetch')
    fetched = json.loads((SOURCE / 'fetched.json').read_text(encoding='utf-8'))
    if DATA.exists():
        shutil.rmtree(DATA)
    GEO.mkdir(parents=True)
    started = time.time()
    counts = {}
    log('map (OpenStreetMap)')
    national_counts, address_rows = build_national()
    counts.update(national_counts)
    log('addresses')
    counts.update(build_addresses(address_rows))
    log('places')
    counts.update(build_places())
    map_files = {f.relative_to(DATA).as_posix(): f.stat().st_size for f in sorted(GEO.glob('*.sqlite'))}
    (DATA / 'map-set.json').write_text(
        json.dumps({'name': REGION, 'files': map_files, 'bytes': sum(map_files.values()),
                    'seconds': round(time.time() - started)}, indent=1), encoding='utf-8')
    outputs = {}
    for f in sorted(DATA.rglob('*')):
        if f.is_file():
            outputs[f.relative_to(DATA).as_posix()] = {'bytes': f.stat().st_size, 'sha256': sha256(f)}
    report = {'region': REGION, 'built': time.strftime('%Y-%m-%dT%H:%M:%S'), 'sources': fetched,
              'counts': counts, 'outputs': outputs,
              'note': 'map-set.json lists the map files; the address index is a separate sidecar, as for US states.'}
    REPORT.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding='utf-8')
    log('built in', round(time.time() - started), 's;', json.dumps(counts, ensure_ascii=False))


def check():
    from engine.address_search import find_addresses
    import server
    failures = []

    def expect(ok, what):
        print(('ok    ' if ok else 'FAIL  ') + what)
        if not ok:
            failures.append(what)

    report = json.loads(REPORT.read_text(encoding='utf-8'))
    for rel, info in report['outputs'].items():
        path = DATA / rel
        expect(path.is_file() and path.stat().st_size == info['bytes'] and sha256(path) == info['sha256'],
               f'{rel}: size and SHA-256 as built')
    map_set = json.loads((DATA / 'map-set.json').read_text(encoding='utf-8'))
    expect(map_set['name'] == REGION, f'map-set.json name is {REGION}')
    for rel in [*map_set['files'], f'derived/geo/addresses/{REGION}.sqlite']:
        db = sqlite3.connect(f'file:{DATA / rel}?mode=ro', uri=True)
        expect(db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok', f'{rel}: SQLite integrity')
        db.close()

    nat = sqlite3.connect(f'file:{GEO / "national.sqlite"}?mode=ro', uri=True)
    roads = nat.execute("SELECT count(*) FROM feat WHERE layer='road'").fetchone()[0]
    bldgs = nat.execute("SELECT count(*) FROM feat WHERE layer='bldg'").fetchone()[0]
    expect(roads > 5000, f'streets from OpenStreetMap: {roads:,} road ways')
    expect(bldgs > 50000, f'building outlines in Stuttgart: {bldgs:,}')
    for cls, low in (('hospital', 20), ('pharmacy', 80), ('fire_station', 10), ('police', 5),
                     ('clinic', 10), ('drinking_water', 40)):
        n = nat.execute('SELECT count(*) FROM poi WHERE cls=?', (cls,)).fetchone()[0]
        expect(n >= low, f'help points {cls}: {n:,} (expected at least {low:,})')
    bounds = nat.execute("SELECT value FROM meta WHERE key='bounds'").fetchone()[0]
    nat.close()

    addr = sqlite3.connect(f'file:{GEO / "addresses" / (REGION + ".sqlite")}?mode=ro', uri=True)
    n, bad_zip = addr.execute("SELECT count(*), sum(zip <> '' AND zip NOT GLOB '[0-9][0-9][0-9][0-9][0-9]') FROM addr").fetchone()
    expect(n > 20000, f'addresses in Stuttgart: {n:,}')
    expect(not bad_zip, f'every present postcode is five digits ({bad_zip} malformed)')
    samples = addr.execute("SELECT street, num, city FROM addr WHERE length(street) > 8 LIMIT 3").fetchall()
    addr.close()

    for street, num, city in samples:
        query = f'{street} {num}, {city}'
        found = find_addresses(query, GEO)
        expect(bool(found) and found[0]['name'] == f'{street} {num}',
               f'address search "{query}" -> {found[0]["name"] if found else "nothing"}')
    expect(find_addresses('Hauptstraße 99999 Stuttgart', GEO) == [], 'an unknown house number returns nothing')

    places = sqlite3.connect(f'file:{GEO / "places.sqlite"}?mode=ro', uri=True)
    hit = places.execute("SELECT count(*) FROM place_fts WHERE place_fts MATCH ?", ('"Stuttgart"',)).fetchone()[0]
    expect(hit > 0, 'place finder has Stuttgart')
    places.close()

    old = server.HERE, server.PLACEDB, server.WATERDB
    try:
        server.HERE = DATA
        server.PLACEDB = GEO / 'places.sqlite'
        server.WATERDB = DATA / 'no-water.sqlite'
        hits = server.places('Stuttgart')
        expect(any(hit['name'] == 'Stuttgart' for hit in hits), 'server.places("Stuttgart") finds the city')
    finally:
        server.HERE, server.PLACEDB, server.WATERDB = old

    if failures:
        raise SystemExit(f'{len(failures)} check(s) failed')
    print('all checks passed')


def demo():
    folder = BASE / 'demo'
    (folder / 'library-data').mkdir(parents=True, exist_ok=True)
    (folder / 'library-data' / 'catalog.json').write_text('[]\n', encoding='utf-8')
    link = folder / 'derived'
    if not link.exists():
        link.symlink_to(Path('..') / 'data' / 'derived', target_is_directory=True)
    print(f'python3 server.py --data {folder.relative_to(ROOT)} --no-index')


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('step', choices=('fetch', 'build', 'check', 'demo'))
    step = parser.parse_args().step
    {'fetch': fetch, 'build': build, 'check': check, 'demo': demo}[step]()


if __name__ == '__main__':
    main()
