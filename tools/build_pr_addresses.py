"""Build the Puerto Rico address sidecar from local OSM and Census extracts."""
import argparse
import collections
import hashlib
import json
import shutil
import sqlite3
import sys
import tempfile
import zipfile
from contextlib import closing
from datetime import datetime
from pathlib import Path

import osmium
from shapely import STRtree
from shapely.geometry import Point, Polygon, shape

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import pr_addresses
from engine.address_search import normalize
from tools import build_pr_rural

MEMBER = 'derived/geo/addresses/PR.sqlite'
ARCHIVE = 'Lastbook-Addresses-PR.zip'
BOUNDARIES = ('https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/1/query'
              '?where=STATE%3D%2772%27&outFields=NAME%2CGEOID&outSR=4326&geometryPrecision=5&f=geojson')
SCHEMA = """
    CREATE TABLE addr(num TEXT, street TEXT, norm TEXT, city TEXT, state TEXT, zip TEXT, lat REAL, lon REAL,
                      street_key TEXT, city_key TEXT, municipio_key TEXT, urbanization TEXT, urb_key TEXT);
    CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
    CREATE TABLE municipios(geoid TEXT PRIMARY KEY, name TEXT, records INTEGER);
"""


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def boundaries(path):
    features = json.loads(path.read_text(encoding='utf-8'))['features']
    areas = {}
    for feature in features:
        props = feature['properties']
        geoid = props['GEOID']
        area = shape(feature['geometry'])
        if (len(geoid) != 5 or not geoid.isdigit() or not geoid.startswith('72') or geoid in areas
                or area.geom_type not in ('Polygon', 'MultiPolygon') or area.is_empty or not area.is_valid):
            raise ValueError(f'Invalid Puerto Rico municipio: {geoid}')
        areas[geoid] = (props['NAME'].removesuffix(' Municipio'), area)
    if len(areas) != 78:
        raise ValueError('Expected all 78 Puerto Rico municipios.')
    geoids = sorted(areas)
    return geoids, [areas[g][0] for g in geoids], STRtree([areas[g][1] for g in geoids])


def position(obj):
    if obj.is_node() and obj.location.valid():
        return Point(obj.lon, obj.lat)
    if obj.is_way() and len(obj.nodes) >= 4 and obj.nodes[0].ref == obj.nodes[-1].ref:
        if all(n.location.valid() for n in obj.nodes):
            area = Polygon([(n.lon, n.lat) for n in obj.nodes])
            if area.is_valid and area.area > 0:
                return area.representative_point()
    return None


def urbanization(tags):
    # addr:place can also be a sector or other locality. Only use explicitly labeled urbanizaciones.
    value = tags.get('addr:urbanization', '').strip()
    if value:
        marked = pr_addresses.URB.fullmatch(value)
        return marked[1].strip() if marked else value
    for name in (tags.get('addr:place', ''), tags.get('addr:suburb', ''), tags.get('addr:neighbourhood', '')):
        marked = pr_addresses.URB.fullmatch(name.strip())
        if marked:
            return marked[1].strip()
    return ''


def build_database(osm, census, db_path, rural=None):
    geoids, names, tree = boundaries(census)
    counts = collections.Counter()
    skipped = collections.Counter()
    with closing(osmium.io.Reader(str(osm))) as reader:
        timestamp = reader.header().get('osmosis_replication_timestamp')
    try:
        datetime.strptime(timestamp or '', '%Y-%m-%dT%H:%M:%SZ')
    except ValueError as error:
        raise ValueError('The OSM input must identify its UTC replication snapshot.') from error
    with closing(sqlite3.connect(db_path)) as db:
        db.executescript(SCHEMA)
        objects = osmium.FileProcessor(str(osm)).with_locations('flex_mem')
        for obj in objects.with_filter(osmium.filter.KeyFilter('addr:housenumber')):
            tags = obj.tags
            num, street = tags['addr:housenumber'].strip(), tags.get('addr:street', '').strip()
            if not street:
                skipped['no_street'] += 1
                continue
            house = pr_addresses.NUMBER.fullmatch(num + ' x')
            if not house or house[2] != 'x' or not pr_addresses.street_key(street):
                skipped['unsupported_spelling'] += 1
                continue
            point = position(obj)
            if point is None:
                skipped['no_point_or_valid_closed_way'] += 1
                continue
            matches = tree.query(point, predicate='within')
            if len(matches) != 1:
                skipped['outside_or_ambiguous_municipio'] += 1
                continue
            index = int(matches[0])
            municipio = names[index]
            city = tags.get('addr:city', '').strip() or municipio
            urb = urbanization(tags)
            db.execute('INSERT INTO addr VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)', (
                house[1], street, normalize(street), city, 'PR', tags.get('addr:postcode', '').strip(),
                round(point.y, 6), round(point.x, 6), pr_addresses.street_key(street),
                pr_addresses.fold(city), pr_addresses.fold(municipio), urb, pr_addresses.fold(urb)))
            counts[geoids[index]] += 1
        records = sum(counts.values())
        if records == 0:
            raise ValueError('No usable Puerto Rico addresses in this extract.')
        db.executescript("""CREATE INDEX addr_num_norm ON addr(num,norm);
                            CREATE INDEX pr_num ON addr(num COLLATE NOCASE);""")
        metadata = {
            'state': 'PR', 'count': str(records), 'search_profile': pr_addresses.PROFILE,
            'source': pr_addresses.SOURCE, 'license': 'ODbL 1.0', 'license_url': 'https://opendatacommons.org/licenses/odbl/1-0/',
            'osm_source': 'https://download.geofabrik.de/north-america/us/puerto-rico.html',
            'osm_snapshot': timestamp, 'osm_sha256': sha(osm), 'municipio_source': BOUNDARIES, 'municipio_sha256': sha(census)
        }
        db.executemany('INSERT INTO municipios VALUES (?,?,?)', [(g, n, counts[g]) for g, n in zip(geoids, names)])
        coverage = {'records': records, 'sources': metadata, 'skipped': dict(skipped),
                    'municipios': {name: counts[g] for g, name in zip(geoids, names)}}
        if rural:
            coverage['rural'] = build_pr_rural.build(db, rural, sha)
            metadata['rural_sources'] = json.dumps(coverage['rural']['sources'], sort_keys=True)
        db.executemany('INSERT INTO meta VALUES (?,?)', sorted(metadata.items()))
        db.commit()
        if db.execute('PRAGMA integrity_check').fetchone() != ('ok',):
            raise ValueError('SQLite integrity check failed.')
    return coverage


def build(osm, census, output, rural=None):
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output) as staging:
        staging = Path(staging)
        database, archive = staging / 'PR.sqlite', staging / ARCHIVE
        coverage = build_database(osm, census, database, rural)
        # A fixed member timestamp makes identical inputs reproducible in the same toolchain.
        member = zipfile.ZipInfo(MEMBER)
        member.create_system = 3
        member.compress_type = zipfile.ZIP_DEFLATED
        member.external_attr = 0o100644 << 16
        with zipfile.ZipFile(archive, 'w') as package:
            with database.open('rb') as source, package.open(member, 'w') as dest:
                shutil.copyfileobj(source, dest)
        with zipfile.ZipFile(archive) as package:
            if package.namelist() != [MEMBER] or package.testzip() is not None:
                raise ValueError('Address archive failed verification.')
        date = coverage['sources']['osm_snapshot'][:10]
        digest = sha(archive)
        release = f'pr-rural-{date}-{digest[:12]}' if rural else f'pr-osm-{date}'
        entry = {'id': 'PR', 'title': 'Puerto Rico', 'kind': 'state-addresses', 'available': True,
                 'installed_bytes': database.stat().st_size, 'records': coverage['records'],
                 'files': [{'name': ARCHIVE, 'url': f'https://downloads.lastbook.org/addresses/{release}/{ARCHIVE}',
                            'size': archive.stat().st_size, 'sha256': digest, 'kind': 'zip'}]}
        coverage['sqlite_sha256'] = sha(database)
        for name, data in [('PR.coverage.json', coverage), ('PR.manifest.json', entry)]:
            (staging / name).write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + '\n', encoding='utf-8')
        for path in sorted(staging.iterdir()):
            path.replace(output / path.name)
    return entry


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('osm', type=Path, help='Geofabrik Puerto Rico .osm.pbf')
    parser.add_argument('municipios', type=Path, help='TIGERweb GeoJSON, Puerto Rico county equivalents, EPSG:4326')
    parser.add_argument('output', type=Path)
    parser.add_argument('--rural', type=Path, help='Folder of federal road, barrio, ZCTA and school snapshots')
    args = parser.parse_args()
    print(json.dumps(build(args.osm, args.municipios, args.output, args.rural), indent=2))
