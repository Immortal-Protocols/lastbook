"""Join land outlines to the physical address on a permit or an optional CRIM physical-address export."""
import csv
import gzip
import hashlib
import json
import re

from shapely import make_valid
from shapely.geometry import shape

from engine import pr_parcels, pr_permit, pr_rural
from engine.pr_addresses import fold
from tools.build_pr_rural import Areas, features


# CRIM's municipio numbers differ from Census FIPS. Source: Tipos Contributivos 2025–26,
# https://portal.crim360.com/crimpr/CMS/DOCUMENTOS/download/362.pdf
CRIM_MUNICIPIOS = {
    '01': 'Aguadilla', '02': 'Isabela', '03': 'Quebradillas', '04': 'Camuy', '05': 'Hatillo',
    '06': 'Arecibo', '07': 'Barceloneta', '08': 'Manatí', '09': 'Vega Baja', '10': 'Vega Alta',
    '11': 'Dorado', '12': 'Toa Alta', '13': 'Toa Baja', '14': 'Cataño', '15': 'Bayamón',
    '16': 'Guaynabo', '19': 'Trujillo Alto', '20': 'Carolina', '21': 'Loíza', '22': 'Río Grande',
    '23': 'Luquillo', '24': 'Fajardo', '25': 'Rincón', '26': 'Aguada', '27': 'Moca',
    '28': 'Añasco', '29': 'Mayagüez', '30': 'San Sebastián', '31': 'Las Marías', '32': 'Maricao',
    '33': 'Lares', '34': 'Adjuntas', '35': 'Utuado', '36': 'Jayuya', '37': 'Ciales',
    '38': 'Morovis', '39': 'Orocovis', '40': 'Corozal', '41': 'Barranquitas', '42': 'Naranjito',
    '43': 'Comerío', '44': 'Cidra', '45': 'Aguas Buenas', '46': 'Caguas', '47': 'Gurabo',
    '48': 'San Lorenzo', '49': 'Juncos', '50': 'Las Piedras', '51': 'Humacao', '52': 'Naguabo',
    '53': 'Ceiba', '54': 'Hormigueros', '55': 'Cabo Rojo', '56': 'San Germán', '57': 'Lajas',
    '58': 'Sabana Grande', '59': 'Guánica', '60': 'Yauco', '61': 'Guayanilla', '62': 'Peñuelas',
    '63': 'Ponce', '64': 'Juana Díaz', '65': 'Villalba', '66': 'Coamo', '67': 'Santa Isabel',
    '68': 'Aibonito', '69': 'Salinas', '70': 'Cayey', '71': 'Guayama', '72': 'Arroyo',
    '73': 'Patillas', '74': 'Maunabo', '75': 'Yabucoa', '76': 'Vieques', '77': 'Culebra',
    '79': 'San Juan', '80': 'Canóvanas', '81': 'Florida',
}
PREFIXED_ACCOUNT = re.compile(r'([0-9]{2})-([0-9]{3}-[0-9]{3}-[0-9]{3}-[0-9]{2}(?:-[0-9]{3})?)')


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
        number = field('catastro', 'numcatastro', 'numdecatastro', 'numerocatastro', 'numerodecatastro')
        address = field('address', 'direccionfisica', 'dirfisica')
        town = field('municipio', 'municipality')
        if not (number and address and town):
            raise ValueError('CRIM CSV needs catastro, physical address and municipio columns.')
        for row in reader:
            yield {'catastro': row[number], 'address': row[address], 'municipio': row[town]}


def labels(db, records, source):
    for row in records:
        value = str(row['catastro'] or '').strip()
        town = fold(row['municipio'] or '')
        account = PREFIXED_ACCOUNT.fullmatch(value)
        if account:
            code, value = account.groups()
            if not town or town != fold(CRIM_MUNICIPIOS.get(code, '')):
                continue
        key = pr_parcels.number(value)
        if not key:
            continue
        # Address candidates share the outline of every polygon with this land number.
        # A number spanning different municipios cannot identify a permit's land unambiguously.
        places = {fold(p[0]) for p in db.execute('SELECT municipio FROM pr_parcel WHERE base=?', (key[:11],))}
        if len(places) != 1 or '' in places or (town and town not in places):
            continue
        if len(key) == 14 and key[11:] != '000':
            db.execute('INSERT OR IGNORE INTO pr_account VALUES (?)', (key,))
        wording = (row['address'] or '').strip()
        if town and wording:
            searchable = wording
            if source == 'CRIM':
                searchable = re.sub(r'(?:(?:^|,)\s*(?:PR|Puerto Rico))+(?:,\s*(00000|00[679]\d{2}(?:-\d{4})?))?\s*$',
                                    lambda m: ', ' + m[1] if m[1] and m[1] != '00000' else '', wording, flags=re.I)
                searchable = re.sub(r'\s*,\s*', ', ', searchable)
                searchable = re.sub(r'(?:^|(?<=,))\s*\.\s*,', '', searchable).strip(' ,.')
            if fold(searchable) in ('', 'n a', 'sin direccion', 'no disponible', town):
                continue
            signature = pr_permit.key(searchable, town, source=True, locality=source in ('CRIM', 'JP consulta'))
            if signature:
                if source in ('CRIM', 'JP consulta'):
                    db.execute('''DELETE FROM pr_permit_wording WHERE town=? AND source IN ('CRIM','JP consulta')
                        AND wording COLLATE NOCASE=? AND wording=? AND base=? AND source=?
                        AND (signature<>? OR postal<>?)''', (town, wording, wording, key[:11], source, *signature))
                db.execute('INSERT OR IGNORE INTO pr_permit_wording VALUES (?,?,?,?,?,?)',
                           (town, *signature, key[:11], source, wording))
        values = address_fields(wording)
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
    db.execute(pr_permit.SCHEMA)
    db.execute(pr_permit.VERBATIM_INDEX)
    db.execute(pr_permit.FIELDS_INDEX)
    for name in ('sip', 'arpe'):
        labels(db, pages(folder, manifest[name]), name.upper() + ' permit')
    csv_hashes = []
    for path in csv_files:
        labels(db, csv_records(path), 'CRIM')
        with path.open('rb') as stream:
            csv_hashes.append(hashlib.file_digest(stream, 'sha256').hexdigest())
    db.execute('CREATE INDEX pr_parcel_route ON pr_parcel_address(route,meters,base)')
    n = db.execute('SELECT count(DISTINCT base) FROM pr_parcel').fetchone()[0]
    if not n:
        raise ValueError('No indexed parcel geometry.')
    # A land number can have multiple permits and can also appear in a CRIM address export.
    counts = db.execute("""
        SELECT p.municipio, count(DISTINCT a.base),
               count(DISTINCT CASE WHEN a.source IN ('SIP permit', 'ARPE permit') THEN a.base END),
               count(DISTINCT CASE WHEN a.source = 'CRIM' THEN a.base END)
          FROM pr_parcel_address a JOIN pr_parcel p ON p.base = a.base
         GROUP BY p.municipio""")
    coverage = {town: {'addressed_parcels': 0, 'permit_parcels': 0, 'crim_address_parcels': 0}
                for town in sorted(towns.values())}
    for town, total, permits, crim in counts:
        coverage[town] = {'addressed_parcels': total, 'permit_parcels': permits, 'crim_address_parcels': crim}
    return {'parcels': n, 'addressed_parcels': db.execute('SELECT count(DISTINCT base) FROM pr_parcel_address').fetchone()[0],
            'permit_wordings': db.execute("SELECT count(*) FROM pr_permit_wording WHERE source IN ('SIP permit','ARPE permit')").fetchone()[0],
            'wordings_by_source': dict(db.execute('SELECT source,count(*) FROM pr_permit_wording GROUP BY source')),
            'address_coverage_by_municipio': coverage,
            'address_sources': dict(db.execute('SELECT source,count(*) FROM pr_parcel_address GROUP BY source')),
            'municipios': dict(db.execute('SELECT municipio,count(DISTINCT base) FROM pr_parcel GROUP BY municipio')),
            'sources': {k: {f: v[f] for f in ('source','records','sha256_uncompressed')} for k,v in manifest.items()},
            'additional_csvs': csv_hashes}
