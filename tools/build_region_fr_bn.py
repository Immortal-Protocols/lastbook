#!/usr/bin/env python3
"""Basse-Normandie (FR-BN: Calvados, Manche, Orne): a trial offline map set with all seven layers and street addresses.

  python3 tools/build_region_fr_bn.py fetch    # downloads the sources (about 2.4 GB) into derived/regions/FR-BN/source/
  python3 tools/build_region_fr_bn.py build    # unpacks them (about 12 GB) and writes derived/regions/FR-BN/data/
  python3 tools/build_region_fr_bn.py check    # validates it; exits non-zero on any failure
  python3 tools/build_region_fr_bn.py demo     # adds an empty library beside it, then prints the command below
  python3 server.py --data derived/regions/FR-BN/demo --no-index   # the map, place and address search, offline

Everything goes under derived/regions/FR-BN/, so no existing map set is touched. FR-BN is a trial area, not one of the
18 regions of docs/REGIONS-FR.md: it is three of the five departments of Normandie. Its address index is named BN
because an index name is two capital letters today. What this build holds and what it lacks: docs/MAP-FR-BN.md.

Sources (all redistributable; dates, sizes and checksums end up in derived/regions/FR-BN/build.json):
  - OpenStreetMap via Geofabrik (ODbL 1.0, "© OpenStreetMap contributors"): streets, land use, railways, named places
    and help points; the coastline, with the Channel Islands' coastline for the sea to the west.
  - Base Adresse Nationale (Licence Ouverte 2.0): street addresses.
  - IGN BD TOPO 3.5, BD ALTI 25 m and the RPG 2025 (Licence Ouverte 2.0): buildings and their heights, place names,
    lakes, ponds, springs and rivers, elevation, orchards and other perennial crops.
  - Sandre ROE (Licence Ouverte 2.0): dams and weirs.
The IGN archives are dated editions and are checked against the checksums below. The Geofabrik, BAN and ROE files are
the publishers' latest, so their checksums are recorded, not expected.

The fetch step needs the network; build, check and demo do not. Needs numpy, pyosmium and tifffile, as the US map tools
do, and either py7zr or a 7z program (7zz, 7z, 7za) to unpack the IGN archives.
"""
import argparse
import datetime
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / 'tools'
sys.path.insert(0, str(ROOT))

REGION = 'FR-BN'
INDEX = 'BN'  # address index and map set name: two capital letters today (engine/setup/manifest.py)
TITLE = 'Basse-Normandie (Calvados, Manche, Orne)'
DEPARTMENTS = ('14', '50', '61')
BOUNDS = (-2.11, 48.02, 1.13, 49.88)  # west, south, east, north: the three departments
# The sea is closed along this box. The mainland coastline of the extract stops inside it at both ends (the coast goes
# on in Bretagne and in Haute-Normandie), so each end is led to the box edge through the sea.
SEA_BOX = '-3.4,48.0,1.13,50.3'
SEA_END_VIA = '-1.66,48.68;-1.80,48.75;-2.6,48.75;-2.9,48.95;-3.4,48.95'
SEA_START_VIA = '0.0,50.3;0.0,49.47;0.10,49.44;0.22,49.44'

BASE = ROOT / 'derived' / 'regions' / REGION
SOURCE = BASE / 'source'
UNPACKED = BASE / 'unpacked'
DATA = BASE / 'data'
GEO = DATA / 'derived' / 'geo'
DEMO = BASE / 'demo'
BUILD_JSON = BASE / 'build.json'

ODBL = 'ODbL 1.0'
LO = 'Licence Ouverte 2.0'
GEOFABRIK = 'https://download.geofabrik.de/europe'
BAN = 'https://adresse.data.gouv.fr/data/ban/adresses/latest/csv'
IGN = 'https://data.geopf.fr/telechargement/download'
ROE = 'https://services.sandre.eaufrance.fr/geo/obs'
ROE_FILTER = ('<fes:Filter xmlns:fes="http://www.opengis.net/fes/2.0"><fes:PropertyIsEqualTo><fes:ValueReference>'
              'CdDepartement</fes:ValueReference><fes:Literal>{}</fes:Literal></fes:PropertyIsEqualTo></fes:Filter>')


def ign(product, name, sha256):
    return {'file': name + '.7z', 'url': f'{IGN}/{product}/{name}/{name}.7z', 'licence': LO, 'sha256': sha256,
            'attribution': 'IGN'}


def sources():
    out = [
        {'file': 'basse-normandie-latest-free.gpkg.zip', 'url': f'{GEOFABRIK}/france/basse-normandie-latest-free.gpkg.zip',
         'licence': ODBL, 'attribution': '© OpenStreetMap contributors'},
        {'file': 'basse-normandie-latest.osm.pbf', 'url': f'{GEOFABRIK}/france/basse-normandie-latest.osm.pbf',
         'licence': ODBL, 'attribution': '© OpenStreetMap contributors'},
        {'file': 'guernsey-jersey-latest.osm.pbf', 'url': f'{GEOFABRIK}/guernsey-jersey-latest.osm.pbf',
         'licence': ODBL, 'attribution': '© OpenStreetMap contributors'},
    ]
    for code in DEPARTMENTS:
        out.append({'file': f'adresses-{code}.csv.gz', 'url': f'{BAN}/adresses-{code}.csv.gz', 'licence': LO,
                    'attribution': 'Base Adresse Nationale'})
    out += [
        ign('BDTOPO', 'BDTOPO_3-5_TOUSTHEMES_GPKG_LAMB93_D014_2026-09-15',
            '9bb7665265b0eeeb363d22f081e229d3ca6a63030356cfbd9e02319c165f3aa4'),
        ign('BDTOPO', 'BDTOPO_3-5_TOUSTHEMES_GPKG_LAMB93_D050_2026-09-15',
            '9d8c5cdfffa148a8a4c9fdb1f3a575606d63df243aa128a1712e23ffa8bec176'),
        ign('BDTOPO', 'BDTOPO_3-5_TOUSTHEMES_GPKG_LAMB93_D061_2026-09-15',
            '41bea94df2b78e419a6eb102970fb584ddbc2cec9959d732319d66bfb9be3d53'),
        ign('BDALTI', 'BDALTIV2_2-0_25M_ASC_LAMB93-IGN69_D014_2022-12-21',
            'c33e2a7e4ca923d2880e0204e68c5fa0448296dd457e3a811ccc3261c42e4f0c'),
        ign('BDALTI', 'BDALTIV2_2-0_25M_ASC_LAMB93-IGN69_D050_2022-12-21',
            'c8085a2bf3f6b353ed9fe0fd7b310c059484432bfb0d6cf38da452bdea5196e3'),
        ign('BDALTI', 'BDALTIV2_2-0_25M_ASC_LAMB93-IGN69_D061_2023-01-12',
            '1c201bebc0d8c50c42aebad79fccb31f10ed1596879159f614504d359ee6d72c'),
        ign('RPG', 'RPG_4-0__GPKG_LAMB93_R28_2025-01-01',
            '85138049ca7e21a47dca2b80c23c5537c8059e234636edde325373185538c506'),
    ]
    for code in DEPARTMENTS:
        query = urllib.parse.urlencode({
            'SERVICE': 'WFS', 'VERSION': '2.0.0', 'REQUEST': 'GetFeature', 'typename': 'ObstEcoul_FXX',
            'SRSNAME': 'EPSG:4326', 'OUTPUTFORMAT': 'GEOJSON', 'FILTER': ROE_FILTER.format(code)})
        out.append({'file': f'roe-{code}.json', 'url': f'{ROE}?{query}', 'licence': LO, 'attribution': 'Sandre, OFB'})
    return out


def log(*args):
    print(time.strftime('%H:%M:%S'), *args, flush=True)


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def download(url, path):
    """To a .part file first, so a file with its final name is always whole."""
    part = path.with_name(path.name + '.part')
    request = urllib.request.Request(url, headers={'User-Agent': 'lastbook-region-builder'})
    with urllib.request.urlopen(request, timeout=300) as response, open(part, 'wb') as handle:
        shutil.copyfileobj(response, handle, 1 << 20)
        modified = response.headers.get('Last-Modified', '')
    part.replace(path)
    return modified


def fetch():
    SOURCE.mkdir(parents=True, exist_ok=True)
    known = read_build().get('sources', {})
    fetched = {}
    for source in sources():
        path = SOURCE / source['file']
        entry = dict(known.get(source['file'], {}))
        if path.exists():
            log('kept', source['file'])
        else:
            log('fetching', source['file'])
            entry = {'modified': download(source['url'], path), 'fetched': datetime.date.today().isoformat()}
        found = sha256(path)
        if source.get('sha256') and found != source['sha256']:
            raise SystemExit(f"{path}: SHA-256 {found} is not the expected {source['sha256']}. Delete the file to fetch it again.")
        entry.update({'url': source['url'], 'licence': source['licence'], 'attribution': source['attribution'],
                      'bytes': path.stat().st_size, 'sha256': found, 'sha256_expected': bool(source.get('sha256'))})
        fetched[source['file']] = entry
    write_build({'region': REGION, 'title': TITLE, 'sources': fetched})
    log('sources ready:', len(fetched), 'files,', sum(e['bytes'] for e in fetched.values()), 'bytes')


def read_build():
    try:
        return json.loads(BUILD_JSON.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def write_build(update):
    build = read_build()
    build.update(update)
    BASE.mkdir(parents=True, exist_ok=True)
    temporary = BUILD_JSON.with_name(BUILD_JSON.name + '.tmp')
    temporary.write_text(json.dumps(build, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    temporary.replace(BUILD_JSON)


def safe(names, archive):
    for name in names:
        member = Path(name)
        if member.is_absolute() or '..' in member.parts:
            raise SystemExit(f'{archive}: unsafe member {name}')


def unpack(name):
    """Each archive into its own folder, once. Downloaded archives are data: nothing in them is run."""
    archive = SOURCE / name
    target = UNPACKED / name.rsplit('.', 1)[0]
    if target.exists():
        return target
    log('unpacking', name)
    expected = next(s.get('sha256') for s in sources() if s['file'] == name)
    if expected and sha256(archive) != expected:   # checked again here: the file may have changed since "fetch"
        raise SystemExit(f'{archive}: not the expected file (SHA-256). Delete it and run "fetch" again.')
    temporary = target.with_name(target.name + '.part')
    shutil.rmtree(temporary, ignore_errors=True)
    temporary.mkdir(parents=True)
    if name.endswith('.zip'):
        with zipfile.ZipFile(archive) as handle:
            safe(handle.namelist(), archive)
            handle.extractall(temporary)
    else:
        try:
            import py7zr
        except ImportError:
            program = next((p for p in ('7zz', '7z', '7za') if shutil.which(p)), None)
            if not program:
                raise SystemExit('The IGN archives are .7z files: install py7zr (pip) or a 7z program (7zz, 7z, 7za).')
            subprocess.run([program, 'x', '-y', f'-o{temporary}', str(archive)], check=True, stdout=subprocess.DEVNULL)
        else:
            with py7zr.SevenZipFile(archive, 'r') as handle:
                safe(handle.getnames(), archive)
                handle.extractall(temporary)
    temporary.replace(target)
    return target


def tool(name, *arguments):
    log(name, '...')
    started = time.time()
    subprocess.run([sys.executable, '-I', str(TOOLS / name), *map(str, arguments)], check=True, cwd=ROOT,
                   stdout=subprocess.DEVNULL)
    log(name, 'done in', round(time.time() - started), 's')


def one(folder, pattern):
    found = sorted(folder.rglob(pattern))
    if len(found) != 1:
        raise SystemExit(f'{folder}: expected one {pattern}, found {len(found)}')
    return found[0]


def data_as_of(pbf):
    import osmium
    header = osmium.io.Reader(str(pbf)).header()
    return header.get('osmosis_replication_timestamp') or header.get('timestamp') or ''


def companions():
    """The small files a map set carries beside its layers, and its list of files."""
    mapdb = GEO / 'map.sqlite'   # the detail database of the Southern California map: empty here, as in a state map
    if not mapdb.exists():
        db = sqlite3.connect(mapdb)
        db.executescript('''CREATE TABLE feat(id INTEGER PRIMARY KEY, layer TEXT, cls TEXT, name TEXT, minz INTEGER, geom BLOB);
          CREATE VIRTUAL TABLE feat_idx USING rtree(id, minx, maxx, miny, maxy, minz, maxz);
          CREATE TABLE poi(id INTEGER PRIMARY KEY, cls TEXT, name TEXT, lon REAL, lat REAL);
          CREATE INDEX poi_cls ON poi(cls, lon, lat);
          CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);''')
        db.commit()
        db.close()
    db = sqlite3.connect((GEO / 'national.sqlite').as_uri() + '?mode=ro', uri=True)
    features = db.execute('SELECT count(*) FROM feat').fetchone()[0]
    db.close()
    (GEO / 'national-status.json').write_text(json.dumps({'state': 'complete', 'stage': 'ready', 'features': features}) + '\n')
    (GEO / 'socal-cells.json').write_text('[]\n')
    files = {f.relative_to(DATA).as_posix(): f.stat().st_size for f in sorted(GEO.rglob('*')) if f.is_file()}
    (DATA / 'map-set.json').write_text(json.dumps({'name': INDEX, 'files': files, 'bytes': sum(files.values())}, indent=1) + '\n')


def build():
    fetched = read_build().get('sources', {})
    missing = [s['file'] for s in sources() if s['file'] not in fetched or not (SOURCE / s['file']).exists()]
    if missing:
        raise SystemExit('Run "fetch" first. Missing: ' + ', '.join(missing))
    started = time.time()
    shutil.rmtree(DATA, ignore_errors=True)
    (GEO / 'addresses').mkdir(parents=True)
    pbf = SOURCE / 'basse-normandie-latest.osm.pbf'
    gpkg = one(unpack('basse-normandie-latest-free.gpkg.zip'), '*.gpkg')
    as_of = data_as_of(pbf)

    tool('build_map.py', gpkg, GEO / 'national.sqlite',
         '--source', f'OpenStreetMap contributors, via Geofabrik basse-normandie-latest-free.gpkg.zip ({ODBL})',
         '--data-as-of', as_of, '--bounds=' + ','.join(map(str, BOUNDS)), '--region', TITLE,
         '--no-buildings', '--no-waterways')   # outlines and river lines come from the BD TOPO below
    tool('build_coast.py', pbf, GEO / 'national.sqlite', '--also', SOURCE / 'guernsey-jersey-latest.osm.pbf',
         '--box=' + SEA_BOX, '--end-via=' + SEA_END_VIA, '--start-via=' + SEA_START_VIA)
    tool('build_addresses_ban.py', '--region', INDEX, '--departments', ','.join(DEPARTMENTS), '--title', TITLE,
         '--out', GEO / 'addresses' / f'{INDEX}.sqlite', *[SOURCE / f'adresses-{code}.csv.gz' for code in DEPARTMENTS])

    by_code = {s['file'].split('_D0')[1][:2]: s['file'] for s in sources() if s['file'].startswith('BDTOPO')}
    topo = [unpack(by_code[code]) for code in DEPARTMENTS]
    departments = ','.join(DEPARTMENTS)
    tool('build_buildings_bdtopo.py', '--out', GEO / 'buildings.sqlite', '--departments', departments, '--osm', pbf, *topo)
    tool('build_places_bdtopo.py', '--out', GEO / 'places.sqlite', '--departments', departments,
         '--postcodes', GEO / 'addresses' / f'{INDEX}.sqlite', *topo)
    roe = [argument for code in DEPARTMENTS for argument in ('--roe', SOURCE / f'roe-{code}.json')]
    tool('build_water_bdtopo.py', '--out', GEO / 'water.sqlite', '--departments', departments, *roe, *topo)

    alti = [unpack(s['file']) for s in sources() if s['file'].startswith('BDALTI')]
    tool('build_terrain_bdalti.py', '--src', *alti, '--out', GEO / 'terrain.sqlite', '--workers', min(4, os.cpu_count() or 1))
    rpg = one(unpack(next(s['file'] for s in sources() if s['file'].startswith('RPG'))), 'RPG_Parcelles.gpkg')
    tool('build_crops_rpg.py', '--rpg', rpg, '--mask', gpkg, '--out', GEO / 'crops.sqlite')

    companions()
    outputs = {f.relative_to(DATA).as_posix(): {'bytes': f.stat().st_size, 'sha256': sha256(f)}
               for f in sorted(DATA.rglob('*')) if f.is_file()}
    write_build({'data_as_of': as_of, 'built': datetime.datetime.now().isoformat(timespec='seconds'),
                 'bounds': list(BOUNDS), 'outputs': outputs})
    log('built', len(outputs), 'files,', sum(o['bytes'] for o in outputs.values()), 'bytes, in', round(time.time() - started), 's')


# Checks. Addresses of public buildings (two prefectures, three town halls), as a person would type them.
ADDRESSES = [
    ('2 rue Daniel Huet 14000 Caen', '2 Rue Daniel Huet', '14000 Caen', 49.1792, -0.3640),
    ('39 rue Saint-Blaise, 61000 Alençon', '39 Rue Saint-Blaise', '61000 Alençon', 48.4325, 0.0915),
    ('19 rue Laitière 14400 Bayeux', '19 Rue Laitière', '14400 Bayeux', 49.2762, -0.7026),
    # a delegated commune: the index keeps both names
    ('10 place Napoléon 50100 Cherbourg-en-Cotentin', '10 Place Napoleon', 'Cherbourg-Octeville, 50100 Cherbourg-en-Cotentin', 49.6424, -1.6242),
    ('10 place napoleon cherbourg octeville', '10 Place Napoleon', 'Cherbourg-Octeville, 50100 Cherbourg-en-Cotentin', 49.6424, -1.6242),
    # short forms, no accents, no postcode
    ('35 r st jean caen', '35 Rue Saint-Jean', '14000 Caen', 49.1822, -0.3594),
    ('5 pl gal de gaulle st lo', '5 Place Général de Gaulle', '50000 Saint-Lô', 49.1153, -1.0899),
    # the comma a French writer puts after the number
    ('39, rue Saint-Blaise 61000 Alençon', '39 Rue Saint-Blaise', '61000 Alençon', 48.4325, 0.0915),
]
NO_ADDRESS = [
    '99999 rue Saint-Jean 14000 Caen',       # no such house: never a guessed one
    '2 rue Daniel Huet 61000 Alençon',       # the street is in Caen
    '12 Main St Springfield IL 62704',       # a US address finds nothing in a French index
]
# (postcode, a commune it serves): the last two are postcodes the BD TOPO does not give, a delegated commune's own
POSTCODES = [('14000', 'Caen'), ('61000', 'Alençon'), ('14400', 'Bayeux'), ('50110', 'Tourlaville'), ('50460', 'Querqueville')]
PLACES = [('Caen', 49.18, -0.37), ('Granville', 48.84, -1.59), ('Alençon', 48.43, 0.09)]
COUNTS = [  # (file, statement, at least): well under the trial build's figures, so newer data still passes
    ('national.sqlite', 'SELECT count(*) FROM feat', 300000),
    ('national.sqlite', "SELECT count(*) FROM poi WHERE cls='hospital'", 40),
    ('national.sqlite', "SELECT count(*) FROM poi WHERE cls='pharmacy'", 300),
    ('national.sqlite', "SELECT count(*) FROM poi WHERE cls='fuel'", 250),
    ('national.sqlite', "SELECT count(*) FROM feat WHERE layer='ocean'", 1),
    (f'addresses/{INDEX}.sqlite', 'SELECT count(*) FROM addr', 750000),
    ('buildings.sqlite', "SELECT CAST(value AS INTEGER) FROM meta WHERE key='buildings'", 1400000),
    ('places.sqlite', 'SELECT count(*) FROM place', 80000),
    ('places.sqlite', "SELECT count(*) FROM place WHERE kind='postcode'", 190),
    ('water.sqlite', "SELECT count(*) FROM resource WHERE kind='dam'", 100),
    ('water.sqlite', "SELECT count(*) FROM resource WHERE kind='spring'", 1000),
    ('terrain.sqlite', 'SELECT count(*) FROM tile', 900),
    ('crops.sqlite', 'SELECT count(*) FROM resource', 1500),
]


def check():
    from engine.address_search import find_addresses, normalize_fr
    failures = []

    def expect(ok, what):
        print('ok  ' if ok else 'FAIL', what, flush=True)
        if not ok:
            failures.append(what)

    def scalar(name, statement):
        db = sqlite3.connect((GEO / name).as_uri() + '?mode=ro&immutable=1', uri=True)   # leaves no -shm or -wal file
        try:
            return db.execute(statement).fetchone()[0]
        finally:
            db.close()

    build = read_build()
    for rel, info in build.get('outputs', {}).items():
        f = DATA / rel
        expect(f.is_file() and f.stat().st_size == info['bytes'] and sha256(f) == info['sha256'], f'{rel}: size and SHA-256 as built')
    expect(bool(build.get('outputs')), 'build.json lists the outputs')
    layers = ['national.sqlite', 'map.sqlite', 'buildings.sqlite', 'places.sqlite', 'water.sqlite', 'terrain.sqlite',
              'crops.sqlite', f'addresses/{INDEX}.sqlite']
    for name in layers:
        expect((GEO / name).is_file() and scalar(name, 'PRAGMA quick_check') == 'ok', f'{name}: SQLite quick_check')
    allowed = set(layers) | {'national-status.json', 'socal-cells.json'}
    extra = sorted(f.relative_to(GEO).as_posix() for f in GEO.rglob('*') if f.is_file() and f.relative_to(GEO).as_posix() not in allowed
                   and not f.name.endswith(('-shm', '-wal')))   # SQLite's own, left by a reader of a WAL database
    expect(not extra, 'derived/geo holds only map set files' + (': ' + ', '.join(extra) if extra else ''))

    expect(scalar('national.sqlite', "SELECT value FROM meta WHERE key='region'") == TITLE, 'national.sqlite names its region')
    expect(scalar('national.sqlite', "SELECT value FROM meta WHERE key='bounds'") == ','.join(map(str, BOUNDS)), 'national.sqlite gives its bounds')
    expect(scalar(f'addresses/{INDEX}.sqlite', "SELECT value FROM meta WHERE key='country'") == 'FR', 'the address index says country = FR')
    for name, statement, least in COUNTS:
        found = scalar(name, statement)
        expect(found >= least, f'{name}: {statement[7:]} = {found:,} (at least {least:,})')   # [7:] drops 'SELECT '

    west, south, east, north = BOUNDS
    outside = scalar('national.sqlite', f'SELECT count(*) FROM poi WHERE lon<{west} OR lon>{east} OR lat<{south} OR lat>{north}')
    expect(outside == 0, f'every help point is inside the bounds ({outside} outside)')
    for name in ('buildings.sqlite', 'water.sqlite', 'terrain.sqlite', 'crops.sqlite', 'places.sqlite', f'addresses/{INDEX}.sqlite'):
        expect('Licence Ouverte' in (scalar(name, "SELECT value FROM meta WHERE key='source'") or ''), f'{name} names its source and licence')
    home = str(Path.home()).encode()   # a build path would name a machine and an account
    leaks = [f.name for f in sorted(GEO.rglob('*.sqlite')) if home in f.read_bytes()]
    expect(not leaks, 'no built file holds a path of this computer' + (': ' + ', '.join(leaks) if leaks else ''))

    for query, name, detail, lat, lon in ADDRESSES:
        found = find_addresses(query, GEO, limit=3)
        first = found[0] if found else {}
        near = bool(found) and abs(first['lat'] - lat) < 0.003 and abs(first['lon'] - lon) < 0.003   # about 300 m
        same = near and normalize_fr(first['name']) == normalize_fr(name) and normalize_fr(first['detail']) == normalize_fr(detail)
        expect(same, f'address "{query}" -> {first.get("name")}, {first.get("detail")}')   # spelling may gain an accent, the place may not move
    for query in NO_ADDRESS:
        found = find_addresses(query, GEO, limit=3)
        expect(not found, f'address "{query}" -> nothing' + (f' (found {found[0]["name"]})' if found else ''))

    db = sqlite3.connect((GEO / 'places.sqlite').as_uri() + '?mode=ro&immutable=1', uri=True)
    find = ('SELECT p.name, p.detail, p.lat, p.lon FROM place_fts f JOIN place p ON p.id=f.rowid WHERE place_fts MATCH ? '
            'ORDER BY p.rank, bm25(place_fts) LIMIT 200')   # the statement of server.places(), which then puts exact names first
    for postcode, commune in POSTCODES:
        rows = db.execute(find, (f'"{postcode}"*',)).fetchall()
        row = next((r for r in rows if r[0] == postcode), None)
        expect(bool(row) and commune in row[1], f'postcode {postcode} -> {row and row[1]}')
    for words, commune in (('50100 Cherbourg', 'Cherbourg-en-Cotentin'), ('14000 Caen', 'Caen')):   # as written on an envelope
        rows = db.execute(find, (' '.join(f'"{word}"*' for word in words.split()),)).fetchall()
        expect(any(r[0] == commune for r in rows), f'"{words}" -> {commune} among {len(rows)}')
    for name, lat, lon in PLACES:
        rows = db.execute(find, (f'"{name}"*',)).fetchall()
        row = next((r for r in rows if r[0] == name), None)
        expect(bool(row) and abs(row[2] - lat) < 0.05 and abs(row[3] - lon) < 0.05, f'place {name} -> {row and row[0]}')
    db.close()

    print(f'{len(failures)} failed' if failures else 'all checks passed')
    return 1 if failures else 0


def demo():
    """The data folder with an empty library beside it, so server.py starts on the map alone. Files are linked, not copied."""
    if not (GEO / 'national.sqlite').exists():
        raise SystemExit('Run "build" first.')
    shutil.rmtree(DEMO, ignore_errors=True)
    for f in sorted(DATA.rglob('*')):
        if f.is_file():
            target = DEMO / f.relative_to(DATA)
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.link(f, target)
            except OSError:
                shutil.copy2(f, target)
    library = DEMO / 'library-data'
    library.mkdir()
    (library / 'catalog.json').write_text('[]\n')
    (library / 'summary.json').write_text(json.dumps({'resources': 0, 'pdfs': 0, 'pdf_pages': 0, 'web_pages': 0, 'videos': 0,
                                                       'collections': 0, 'document_bytes': 0}) + '\n')
    (DEMO / 'pack.json').write_text(json.dumps({
        'name': 'Lastbook map trial: ' + TITLE, 'size': 'small', 'map': INDEX, 'built': datetime.date.today().isoformat(),
        'sample': False, 'add_ons': [], 'counts': {}, 'known_gaps': [], 'incomplete': 0}, indent=1) + '\n')
    print(f'python3 server.py --data {DEMO.relative_to(ROOT).as_posix()} --no-index')


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('step', choices=('fetch', 'build', 'check', 'demo'))
    step = parser.parse_args().step
    sys.exit({'fetch': fetch, 'build': build, 'check': check, 'demo': demo}[step]() or 0)


if __name__ == '__main__':
    main()
