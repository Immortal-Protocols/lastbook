"""Join land outlines to the physical address on a permit or an optional CRIM physical-address export."""
import csv
import gzip
import hashlib
import json
import re

from shapely import make_valid
from shapely.geometry import shape

from engine import pr_parcels, pr_rural
from engine.pr_addresses import fold
from tools.build_pr_rural import Areas, features


def pages(folder, entry):
    count = 0
    fingerprint = hashlib.sha256()
    for name in entry['pages']:
        with gzip.open(folder / entry['folder'] / name, 'rb') as stream:
            for line in stream:
                fingerprint.update(line)
                count += 1
                yield json.loads(line)
    if count != entry['records']:
        raise ValueError('Incomplete local snapshot of ' + entry['source'])
    entry['sha256_uncompressed'] = fingerprint.hexdigest()


def address_fields(text):
    raw = pr_rural.plain(text)
    raw = re.sub(r'\bkm\.?\s*hm\.?(?=\s*#?\s*\d)', 'km ', raw)
    routes = pr_rural.ROAD.findall(raw)
    marks = list(pr_rural.KM.finditer(raw))
    if len(routes) != 1 or len(marks) > 1 or re.search(r'\b\d+\s*/\s*\d+\b', raw):
        return None
    meters = None
    hectos = pr_rural.HM.findall(raw)
    if marks:
        marker = marks[0]
        if re.match(r'\s*(?:-|/|al?\s)\s*\d', raw[marker.end():]) or re.search(r'\b(?:entre|desde|hasta|between)\b', raw):
            return None
        whole, _, frac = marker[1].replace(',', '.').partition('.')
        if len(hectos) > 1 or (frac and hectos):
            return None
        meters = int(whole) * 1000 + int(frac.ljust(3, '0')) + (int(hectos[0]) * 100 if hectos else 0)
    elif hectos or re.search(r'\b(?:km|kilometros?)\b', raw):
        return None
    postal = pr_rural.POSTAL.findall(raw)
    raw = pr_rural.POSTAL.sub(',', raw)
    details = pr_rural.qualifiers(raw)
    if details is None:
        return None
    lot, access = details
    sector = re.search(r'\b(?:sector|sect|sec|comunidad|com)\.?\s+([^,;\n]+?)(?=[,;\n]|$|'
                       r'\b(?:barrio|bo|municipio|interior|int|lot|lote|solar|carr|carretera|pr|km)\b)', raw)
    landmark = re.search(r'\b(?:frente a|al lado de|detras de|junto a|cerca de)\s+[^,;\n]+', raw)
    return (int(routes[0]), meters, lot, fold(sector[1]) if sector else '', int(bool(pr_rural.INSIDE.search(raw))),
            access, postal[0] if len(postal) == 1 and postal[0] != '00000' else '', fold(landmark[0]) if landmark else '')


def polygon_parts(geometry):
    if geometry.geom_type == 'Polygon':
        yield geometry
    elif hasattr(geometry, 'geoms'):
        for part in geometry.geoms:
            yield from polygon_parts(part)


def shape_rows(records, barrios, zones):
    for row in records:
        key = pr_parcels.number(str(row['catastro'] or ''))
        if not key or not row['geometry']:
            continue
        geom = shape(row['geometry'])
        if not geom.is_valid:
            geom = make_valid(geom)
        parts = list(polygon_parts(geom))
        if not parts or geom.is_empty or geom.area <= 0:
            continue
        center = geom.centroid
        if not geom.contains(center):
            center = max(parts, key=lambda part: part.area).representative_point()
        names, zips = barrios.at(center), zones.at(center)
        barrio, town = names[0] if len(names) == 1 else ('', '')
        rings = []
        for part in parts:
            # Keep the footprint of each component and its holes, in WGS84 map coordinates.
            part = part.simplify(.000004, preserve_topology=True)
            rings.extend([list(ring.coords) for ring in (part.exterior, *part.interiors)])
        yield (row['id'], key[:11], barrio, town, zips[0] if len(zips) == 1 else '',
               round(center.y, 6), round(center.x, 6), geom.area, json.dumps(rings, separators=(',', ':')))


def csv_records(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        names = {fold(c).replace(' ', ''): c for c in reader.fieldnames or []}
        def field(*options):
            return next((names[name] for name in options if name in names), None)
        number = field('catastro', 'numcatastro')
        address = field('address', 'direccionfisica')
        town = field('municipio', 'municipality')
        if not (number and address and town):
            raise ValueError('CRIM CSV needs catastro, physical address and municipio columns.')
        for row in reader:
            yield {'catastro': row[number], 'address': row[address], 'municipio': row[town]}


def labels(db, records, source):
    for row in records:
        key = pr_parcels.number(str(row['catastro'] or '').strip())
        if not key:
            continue
        town = fold(row['municipio'] or '')
        places = db.execute('SELECT municipio FROM pr_parcel WHERE base=?', (key[:11],)).fetchall()
        if not places or (town and not any(town == fold(p[0]) for p in places)):
            continue
        if len(key) == 14 and key[11:] != '000':
            db.execute('INSERT OR IGNORE INTO pr_account VALUES (?)', (key,))
        values = address_fields(row['address'] or '')
        if values:
            # -1 in the unique index makes repeated records with an unreported km compare equal.
            db.execute('INSERT OR IGNORE INTO pr_parcel_address VALUES (?,?,?,?,?,?,?,?,?,?)',
                       (key[:11], *values, source))


def build(db, folder, rural, csv_files=()):
    manifest = json.loads((folder / 'sources.json').read_text(encoding='utf-8'))
    towns = dict(db.execute('SELECT geoid,name FROM municipios'))
    barrios = Areas(features(rural / 'barrios.json'), lambda p: (
        p['NAME'] if p['NAME'].endswith(' barrio-pueblo') else p['BASENAME'], towns[p['GEOID'][:5]]))
    zones = Areas(features(rural / 'zctas.json'), lambda p: p['ZCTA5'])
    db.executescript("""
        CREATE TABLE pr_parcel(id INTEGER PRIMARY KEY,base TEXT,barrio TEXT,municipio TEXT,zip TEXT,
                               lat REAL,lon REAL,area REAL,rings TEXT);
        CREATE TABLE pr_account(number TEXT PRIMARY KEY) WITHOUT ROWID;
        CREATE TABLE pr_parcel_address(base TEXT,route INTEGER,meters INTEGER,lot TEXT,sector TEXT,interior INTEGER,
                                       access TEXT,postal TEXT,landmark TEXT,source TEXT);
    """)
    db.executemany('INSERT INTO pr_parcel VALUES (?,?,?,?,?,?,?,?,?)',
                   shape_rows(pages(folder, manifest['parcels']), barrios, zones))
    db.executescript("""CREATE INDEX pr_parcel_number ON pr_parcel(base);
        CREATE UNIQUE INDEX pr_parcel_evidence ON pr_parcel_address
        (base,route,coalesce(meters,-1),lot,sector,interior,access,postal,landmark,source);""")
    for name in ('sip', 'arpe'):
        labels(db, pages(folder, manifest[name]), name.upper() + ' permit')
    for path in csv_files:
        labels(db, csv_records(path), 'CRIM')
    db.execute('CREATE INDEX pr_parcel_route ON pr_parcel_address(route,meters,base)')
    n = db.execute('SELECT count(DISTINCT base) FROM pr_parcel').fetchone()[0]
    if not n:
        raise ValueError('No indexed parcel geometry.')
    return {'parcels': n, 'addressed_parcels': db.execute('SELECT count(DISTINCT base) FROM pr_parcel_address').fetchone()[0],
            'address_sources': dict(db.execute('SELECT source,count(*) FROM pr_parcel_address GROUP BY source')),
            'municipios': dict(db.execute('SELECT municipio,count(DISTINCT base) FROM pr_parcel GROUP BY municipio')),
            'sources': {k: {f: v[f] for f in ('source','records','sha256_uncompressed')} for k,v in manifest.items()},
            'additional_csvs': [hashlib.sha256(path.read_bytes()).hexdigest() for path in csv_files]}
