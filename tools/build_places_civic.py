"""Civic places from five federal lists: derived/geo/places-civic.sqlite.

  derived/buildenv/bin/python tools/build_places_civic.py            # download what is missing, then build
  derived/buildenv/bin/python tools/build_places_civic.py --refresh  # download everything again first
  derived/buildenv/bin/python tools/build_places_civic.py --offline  # build from the files already downloaded

What goes in (nationwide, about 230k rows, conf 0.95):
  school        NCES EDGE geocoded public schools (2024-25) and private schools (2023-24)
                https://nces.ed.gov/programs/edge/Geographic/SchoolLocations (public domain). Virtual/online schools dropped.
  library       IMLS Public Libraries Survey FY2024 outlets (central + branch; bookmobiles and books-by-mail dropped)
                https://www.imls.gov/research-evaluation/data-collection/public-libraries-survey (public domain)
  nursing_home  CMS Nursing Home Provider Information, monthly, paged through the provider-data datastore API
                https://data.cms.gov/provider-data/dataset/4pq5-n9py (public domain). Every row has coordinates, so no geocoding.
  hospital      HIFLD Hospitals from the SeerAI HIFLD archive (s3://us-west-2.opendata.source.coop/seerai/hifld/hospitals),
                CLOSED ones dropped. The archive's own LICENSE.txt and README.md (saved next to the data) put the whole
                archive under CC BY 4.0, citation "SeerAI, Inc. (2025). HIFLD Archive. Retrieved from https://www.seer.ai/";
                the layer READMEs say nothing more. Anything shipping this file must carry that credit and licence link.
  shelter       FEMA National Shelter System facilities, same archive. These are the places registered to open as shelters
                (mostly schools, churches, community centres); the CLOSED status is per incident and is ignored. Named
                "Novi High School (shelter)", "(shelter, generator)" when it has one on site. A building listed once per
                room ('Lincoln High School, East Gym 1/2', '... West Gym 2/2') becomes one row.
  Hospitals and shelters placed far from their own ZIP code area are left out: the geocoder put several Los Angeles
  shelters (two golf courses 15 km away among them) on one school's point.

Why: OSM is thin in suburbs, and these are the places people go in a long blackout (schools and churches become shelters,
libraries are warming/cooling centres, hospitals and nursing homes have generators, medicine and vulnerable people).
Personal data is dropped: only a class, a clean name and a point are kept (no addresses, phone numbers or contacts). A side
table `detail` keeps a little game data per row as JSON (hospital beds/trauma/type/helipad/er = confirmed emergency department, shelter capacity/generator,
nursing home certified beds, school public/private).

Same place table as tools/build_places_overture.py so game/serve.py can merge it. Raw files live in
derived/geo/sources/civic/.
"""
import csv
import io
import json
import math
import re
import sqlite3
import sys
import time
import urllib.request
import zipfile
from datetime import date
from pathlib import Path

import duckdb

HERE = Path(__file__).resolve().parent.parent
SRC = HERE / 'derived/geo/sources/civic'
OUT = HERE / 'derived/geo/places-civic.sqlite'
CONF = 0.95
NCES_PUB = 'https://nces.ed.gov/programs/edge/data/EDGE_GEOCODE_PUBLICSCH_2425.zip'
NCES_PRIV = 'https://nces.ed.gov/programs/edge/data/EDGE_GEOCODE_PRIVATESCH_2324.zip'
IMLS = 'https://www.imls.gov/sites/default/files/2026-06/pls_fy2024_csv.zip'
CMS_META = 'https://data.cms.gov/provider-data/api/1/metastore/schemas/dataset/items/4pq5-n9py'
CMS_QUERY = 'https://data.cms.gov/provider-data/api/1/datastore/query/4pq5-n9py/0'
S3 = 'https://s3.us-west-2.amazonaws.com/us-west-2.opendata.source.coop'
HIFLD = {'hospitals': 'seerai/hifld/hospitals/hospitals/',
         'shelters': 'seerai/hifld/national-shelter-system-facilities/shelter-locations/'}
LICENCE = ('NCES EDGE, IMLS PLS, CMS Provider Data: public domain (US federal). HIFLD hospitals and National Shelter System: '
           'SeerAI, Inc. (2025). HIFLD Archive. Retrieved from https://www.seer.ai/ - CC BY 4.0 '
           '(https://creativecommons.org/licenses/by/4.0/; stated in the archive LICENSE.txt, kept in sources/civic/hifld/); '
           'modified: filtered, renamed, rooms merged.')
PROFILES = HERE / 'derived/geo/profiles.sqlite'  # tools/build_profiles.py: ZIP code area centres, to catch bad geocodes
UA = {'User-Agent': 'blackout-game-builder/1.0'}


def get(url, timeout=120):
    """GET with retries and a clear error."""
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.read()
        except Exception as e:
            print(f'  {url}: {e}; retrying', flush=True)
            time.sleep(3 * (attempt + 1))
    raise SystemExit(f'could not read {url} (run with --offline to build from the files already downloaded)')


def fetch(url, dest, refresh=False):
    if dest.exists() and dest.stat().st_size and not refresh:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + '.part')
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=120) as r, open(tmp, 'wb') as f:
                while chunk := r.read(1 << 20):
                    f.write(chunk)
            tmp.replace(dest)
            print(f'  got {dest.name} ({dest.stat().st_size / 1e6:.1f} MB)')
            return dest
        except Exception as e:
            print(f'  {url}: {e}; retrying')
            time.sleep(3 * (attempt + 1))
    raise SystemExit(f'could not download {url}')


def download(refresh=False):
    fetch(NCES_PUB, SRC / 'nces/EDGE_GEOCODE_PUBLICSCH_2425.zip', refresh)
    fetch(NCES_PRIV, SRC / 'nces/EDGE_GEOCODE_PRIVATESCH_2324.zip', refresh)
    fetch(IMLS, SRC / 'imls/pls_fy2024_csv.zip', refresh)
    cms_download(refresh)
    for name in ('LICENSE.txt', 'README.md'):  # the archive's licence and citation
        fetch(f'{S3}/seerai/hifld/{name}', SRC / 'hifld' / name, refresh)
    for layer, prefix in HIFLD.items():
        xml = get(f'{S3}?list-type=2&prefix={prefix}', 60).decode()
        keys = [k for k in re.findall(r'<Key>([^<]+)</Key>', xml) if k.endswith('.parquet') or k.endswith('README.md')]
        if not any(k.endswith('.parquet') for k in keys):
            raise SystemExit(f'no parquet files listed under {prefix}')
        names = {'README.md' if k.endswith('README.md') else k.rsplit('/', 1)[1] for k in keys}
        for old in (SRC / 'hifld' / layer).glob('*.parquet'):  # a republished layer has new part-file names: drop the old parts
            if old.name not in names:
                print(f'  removing old {layer} part {old.name}')
                old.unlink()
        for k in keys:
            name = 'README.md' if k.endswith('README.md') else k.rsplit('/', 1)[1]
            fetch(f'{S3}/{k}', SRC / 'hifld' / layer / name, refresh)


def cms_download(refresh=False):
    """CMS's monthly CSV link answers 403 to scripts, so page the same table through its documented datastore API and
    keep the four columns used here, as cms/NH_ProviderInfo_<YYYY-MM-DD>.csv (the dataset's modified date)."""
    modified = json.loads(get(CMS_META, 60))['modified']
    dest = SRC / f'cms/NH_ProviderInfo_{modified}.csv'
    if dest.exists() and not refresh:
        return dest
    cols = ['provider_name', 'latitude', 'longitude', 'number_of_certified_beds']
    rows, off = [], 0
    while True:
        url = (f'{CMS_QUERY}?limit=1500&offset={off}&count=true&results=true&schema=false&keys=true&'
               + '&'.join(f'properties[]={c}' for c in cols))
        d = json.loads(get(url))
        rows += d['results']
        off += 1500
        if off >= int(d['count']):
            break
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest.with_suffix('.part'), 'w', newline='') as f:
        w = csv.DictWriter(f, cols)
        w.writeheader()
        w.writerows(rows)
    dest.with_suffix('.part').replace(dest)
    for old in (SRC / 'cms').glob('NH_ProviderInfo_*.csv'):  # keep only the newest month
        if old != dest:
            old.unlink()
    print(f'  got {dest.name} ({len(rows):,} nursing homes)')
    return dest


# --- names -------------------------------------------------------------------------------------------------------------
KEEP_UP = {'II', 'III', 'IV', 'VI', 'VII', 'VIII', 'IX', 'XI', 'XII', 'YMCA', 'YWCA', 'VFW', 'KIPP', 'USA', 'US', 'VA', 'PS', 'IS',
           'MS', 'HS', 'JHS', 'CS', 'ISD', 'USD', 'STEM', 'STEAM', 'ESE', 'ESL', 'AME', 'CME', 'UCLA', 'LDS', 'ROTC', 'NE', 'NW',
           'SE', 'SW', 'ER', 'ICU', 'UCSF', 'UNC', 'SDA', 'DC', 'KC', 'NYC', 'JFK', 'MLK', 'HCA', 'UPMC', 'UAB', 'UT', 'UC',
           'OSF', 'SSM', 'CHI', 'AHN', 'HSHS', 'MUSC', 'UNM', 'UVA', 'VCU', 'OHSU', 'NYU', 'CAMC', 'LTAC', 'LTACH', 'PK', 'TK', 'K-8',
           'K-12', 'PK-8', 'PK-12', 'P.S.', 'I.S.', 'M.S.', 'J.H.S.', 'H.S.', 'PS/IS', 'I.S./H.S.', 'MS/HS'}
SMALL = {'of', 'the', 'and', 'at', 'for', 'in', 'on', 'de', 'la', 'del', 'y', 'a', 'an', 'to'}


def nice_name(n):
    """Clean up a federal list name for players: sensible case, no Inc/LLC, no doubled spaces. Numbers are kept (PS 163)."""
    n = ' '.join((n or '').replace(' ', ' ').split()).strip(' -,;')
    if not n:
        return ''
    if n.isupper() or n.islower():
        words = []
        for i, w in enumerate(n.split(' ')):
            u = w.upper()
            if u in KEEP_UP or u.strip('(),') in KEEP_UP or (u != '(THE)' and re.fullmatch(r'\([A-Z]{2,5}\)', u)) or re.fullmatch(r'\(?(PK|TK|K)(-\d+)?\)?', u):  # (HCC), (PK-5)
                words.append(u)
            elif i and w.lower() in SMALL:
                words.append(w.lower())
            elif re.fullmatch(r'[A-Za-z]{1,2}\d+[A-Za-z]?', w):  # M2, PS9
                words.append(u)
            else:
                t = w.capitalize() if w.isalpha() else w.title()
                t = re.sub(r"'S\b", "'s", t)
                t = re.sub(r'^(Mc)([a-z])', lambda m: m[1] + m[2].upper(), t)
                t = re.sub(r'(\d)(St|Nd|Rd|Th)\b', lambda m: m[1] + m[2].lower(), t)
                words.append(t)
        n = ' '.join(words)
    n = re.sub(r'\s*\(?\b(dba|d/b/a)\b[^)]*\)?', '', n, flags=re.I)  # 'Calvin Christian School (Dba: Avail Academy)'
    n = re.sub(r'^(.*\S) \(The\)(.*)$', r'The \1\2', n)  # 'Riverview School (The)'
    # 'Smith (Jennie E.) Elementary School' -> 'Jennie E. Smith Elementary School'
    n = re.sub(r"^([A-Z][\w'-]+) \(([^()]*\.[^()]*?)\s*\) (.+)$", r'\2 \1 \3', n)
    n = re.sub(r'\s+El$', ' Elementary', n)  # Texas: 'Birch El'
    n = re.sub(r'\s+(J H|Jh)$', ' Junior High', n)
    n = re.sub(r'\s+(H S|Hs)$', ' High School', n)
    n = re.sub(r'\s+Int$', ' Intermediate', n)
    for a, b in ABBREV:
        n = a.sub(b, n)
    n = re.sub(r'(?<=[A-Za-z]{2})-([a-z])(?=[a-z]{3})', lambda m: '-' + m[1].upper(), n)  # 'Arts-manhattan'
    n = re.sub(r'(?<=\S) (Of|And|The|At|For|In|On|To) ', lambda m: f' {m[1].lower()} ', n)  # 'High School Of ...'
    return re.sub(r',?\s+(Inc|Llc|L\.l\.c|Co)\.?$', '', n, flags=re.I).strip(' ,|')


ABBREV = [(re.compile(a, re.I), b) for a, b in [
    (r'\bCtr\b\.?', 'Center'), (r'\bHosp\b\.?', 'Hospital'), (r'\bMed\b\.?(?= (Center|Centre|Ctr))', 'Medical'), (r'\bMpls\b', 'Minneapolis'),
    (r"\bChildrens\b", "Children's"), (r'\bSch\b\.?', 'School'), (r'\b([PIM])\.\s+S\.', r'\1.S.'), (r'\s*&\s*', ' & '),
    (r'\s+-\s*|\s*-\s+', ' - '), (r'\s+Poc$', '')]]
# a building listed once per room: 'Lincoln High School, East Gym 1/2', 'Peck Park Auditorium 2 of 2'
ROOM_COUNT = re.compile(r'[,\s]*(\(?(bldg|building|area|room)\s*)?\d+\s*(/|of)\s*\d+\)?\s*$', re.I)
ROOM_WORDS = {'gym', 'gymnasium', 'auditorium', 'cafeteria', 'ballroom', 'multipurpose', 'mpr', 'room', 'rm', 'hall', 'social', 'chapel',
              'campus', 'bldg', 'building', 'new', 'old', 'main', 'large', 'small', 'north', 'south', 'east', 'west', 'upper', 'lower',
              'boys', 'girls', 'n.', 's.', 'e.', 'w.', 'level', '2nd', '1st', 'area', 'wing', 'annex', 'center)', '(gym)'}


def building_name(n):
    """'Lincoln High School, East Gym 1/2' -> 'Lincoln High School'; names without a room count are left alone."""
    if not ROOM_COUNT.search(n):
        return n
    n = ROOM_COUNT.sub('', n)
    n = re.sub(r'-(\w+)$', lambda m: '' if m[1].lower() in ROOM_WORDS else m[0], n)  # 'Catholic Church-Gym'
    m = re.search(r',\s|\s-\s|-\s|\s\(', n)
    if m and m.start() > 3:
        return n[:m.start()].strip()
    w = n.split()
    while len(w) > 2 and w[-1].lower() in ROOM_WORDS:
        w.pop()
    return ' '.join(w)


JUNK = re.compile(r'^(test|tbd|n/?a|none|unknown|shelter|\d+)$', re.I)
VIRTUAL = re.compile(r'virtual|online|cyber|e-?academy|e-?school|distance learning|homebound|home school', re.I)


def cell(v):
    return int(v * 20) if v >= 0 else int(v * 20) - 1


def ok(la, lo):
    return la is not None and lo is not None and -90 < la < 90 and -180 < lo < 180 and not (la == 0 and lo == 0)


# --- sources -----------------------------------------------------------------------------------------------------------
def schools():
    z = zipfile.ZipFile(SRC / 'nces/EDGE_GEOCODE_PUBLICSCH_2425.zip')
    txt = next(n for n in z.namelist() if n.upper().endswith('.TXT'))
    for line in io.TextIOWrapper(z.open(txt), encoding='latin-1'):
        f = line.rstrip('\r\n').split('|')
        try:
            la, lo = float(f[-11]), float(f[-10])  # index from the end: a few rows carry an extra '|'
        except (ValueError, IndexError):
            continue
        if ok(la, lo) and not VIRTUAL.search(f[2]):
            yield 'school', f[2], la, lo, {'public': True}
    z = zipfile.ZipFile(SRC / 'nces/EDGE_GEOCODE_PRIVATESCH_2324.zip')
    dbf = SRC / 'nces/private'
    dbf.mkdir(exist_ok=True)
    for old in dbf.iterdir():  # only this zip's files, so a renamed shapefile can't be mixed up with an older one
        old.unlink()
    for n in z.namelist():
        if re.search(r'\.(shp|shx|dbf|prj|cpg)$', n, re.I):
            (dbf / Path(n).name).write_bytes(z.read(n))
    shp = next(dbf.glob('*.shp'))
    con = duckdb.connect()
    con.execute('LOAD spatial')
    for name, la, lo in con.execute(f"SELECT NAME, CAST(LAT AS DOUBLE), CAST(LON AS DOUBLE) FROM ST_Read('{shp}')").fetchall():
        if ok(la, lo) and not VIRTUAL.search(name or ''):
            yield 'school', name, la, lo, {'public': False}


def libraries():
    z = zipfile.ZipFile(SRC / 'imls/pls_fy2024_csv.zip')
    name = next(n for n in z.namelist() if re.search(r'outlet.*\.csv$', n, re.I))
    for r in csv.DictReader(io.TextIOWrapper(z.open(name), encoding='latin-1')):
        if r['C_OUT_TY'] in ('BS', 'BM'):
            continue
        try:
            la, lo = float(r['LATITUDE']), float(r['LONGITUD'])
        except ValueError:
            continue
        if ok(la, lo):
            yield 'library', r['LIBNAME'], la, lo, {}


def nh_file():
    return max((SRC / 'cms').glob('NH_ProviderInfo_*.csv'))


def nursing_homes():
    path = nh_file()
    for r in csv.DictReader(open(path, encoding='utf-8-sig', errors='replace')):
        try:
            la, lo = float(r['latitude']), float(r['longitude'])
        except ValueError:
            continue  # none today; a free bulk geocoder (Census) could fill these if CMS ever leaves gaps
        if ok(la, lo):
            beds = r.get('number_of_certified_beds') or ''
            yield 'nursing_home', r['provider_name'], la, lo, {'beds': int(float(beds))} if beds.strip() else {}


def hospital_er(typ, trauma):
    """'yes' when HIFLD itself confirms an emergency department, else None (unknown).

    Confirmed: a designated trauma level (every trauma centre runs one) or a CMS critical access hospital (the
    rules for that status require 24-hour emergency care). Other types, general acute care included, do not say,
    so they stay unknown. HIFLD never says that a hospital has none, so this never returns 'no'.
    """
    if (trauma or '').upper().startswith('LEVEL') or (typ or '').strip().upper() == 'CRITICAL ACCESS':
        return 'yes'
    return None


def hospital_detail(typ, beds, trauma, heli):
    d = {'type': (typ or '').lower() or None, 'beds': int(beds) if beds and beds > 0 else None,
         'trauma': trauma if trauma and trauma.upper().startswith('LEVEL') else None, 'helipad': heli == 'Y' or None,
         'er': hospital_er(typ, trauma)}
    return {k: v for k, v in d.items() if v}


def hospitals():
    con = duckdb.connect()
    files = f"{SRC / 'hifld/hospitals'}/*.parquet"
    q = f"""SELECT NAME, LATITUDE, LONGITUDE, BEDS, TRAUMA, TYPE, HELIPAD, ZIP FROM read_parquet('{files}')
            WHERE coalesce(STATUS, '') <> 'CLOSED'"""
    for name, la, lo, beds, trauma, typ, heli, zc in con.execute(q).fetchall():
        if ok(la, lo) and near_zip(la, lo, zc):
            yield 'hospital', name, la, lo, hospital_detail(typ, beds, trauma, heli)


def shelters():
    con = duckdb.connect()
    files = f"{SRC / 'hifld/shelters'}/*.parquet"
    q = f"""SELECT shelter_name, latitude, longitude, max(evacuation_capacity), bool_or(upper(generator_onsite) = 'YES'), any_value(zip)
            FROM read_parquet('{files}') WHERE latitude IS NOT NULL AND latitude <> 0
            GROUP BY shelter_name, latitude, longitude ORDER BY shelter_name, latitude, longitude"""
    kept = {}  # (name, ~1 km cell) -> [lat, lon, capacity, generator]; one row per building, rooms added up
    for name, la, lo, cap, gen, zc in con.execute(q).fetchall():
        name = nice_name(building_name(nice_name(name)))
        if not ok(la, lo) or not name or JUNK.match(name) or not near_zip(la, lo, zc):
            continue
        hit = None
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                r = kept.get((name.lower(), int(la * 100) + dy, int(lo * 100) + dx))
                if r and abs(r[0] - la) < 0.003 and abs(r[1] - lo) < 0.004:
                    hit = r
        if hit:
            hit[2] += cap if cap and cap > 0 else 0
            hit[3] = hit[3] or bool(gen)
            continue
        kept[(name.lower(), int(la * 100), int(lo * 100))] = [la, lo, cap if cap and cap > 0 else 0, bool(gen), name]
    for la, lo, cap, gen, name in kept.values():
        d = {'capacity': cap or None, 'generator': True if gen else None}
        yield 'shelter', f"{name} (shelter{', generator' if gen else ''})", la, lo, {k: v for k, v in d.items() if v}


_zips = None


def near_zip(la, lo, zc):
    """False when the point is far outside its own ZIP code area (a bad geocode); True when that can't be checked."""
    global _zips
    if _zips is None:
        _zips = {}
        if PROFILES.exists():
            _zips = {z: (zla, zlo, a or 0) for z, zla, zlo, a in sqlite3.connect(PROFILES).execute('SELECT zip, lat, lon, aland_km2 FROM zcta')}
    z = _zips.get((zc or '').strip()[:5])
    if not z:
        return True
    km = math.hypot((lo - z[1]) * 111.32 * math.cos(math.radians(la)), (la - z[0]) * 110.57)
    return km <= max(8, 2 * math.sqrt(z[2] / math.pi) + 3)


def main():
    if '--offline' not in sys.argv:
        download('--refresh' in sys.argv)
    tmp = OUT.with_suffix('.tmp')
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.executescript('CREATE TABLE place(cls TEXT, name TEXT, lat REAL, lon REAL, conf REAL, gx INT, gy INT);'
                     'CREATE TABLE detail(id INTEGER PRIMARY KEY, info TEXT);'  # id = place.rowid
                     'CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);')
    counts = {}
    for gen in (schools, libraries, nursing_homes, hospitals, shelters):
        for cls, name, la, lo, info in gen():
            name = nice_name(name) if cls != 'shelter' else name
            if not name or JUNK.match(name):
                continue
            cur = db.execute('INSERT INTO place VALUES (?,?,?,?,?,?,?)', (cls, name, la, lo, CONF, cell(lo), cell(la)))
            if info:
                db.execute('INSERT INTO detail VALUES (?,?)', (cur.lastrowid, json.dumps(info, separators=(',', ':'))))
            counts[cls] = counts.get(cls, 0) + 1
        print(f'  {gen.__name__}: done')
    db.execute('CREATE INDEX place_grid ON place(gx, gy)')
    n = sum(counts.values())
    db.executemany('INSERT INTO meta VALUES (?,?)', [
        ('count', str(n)), ('classes', json.dumps(counts)),
        ('source', 'NCES EDGE school geocodes 2024-25/2023-24; IMLS PLS FY2024 outlets; CMS Nursing Home Provider Info '
                   f"({nh_file().stem.split('_')[-1]}); HIFLD archive hospitals and "
                   'National Shelter System facilities (SeerAI)'),
        ('licence', LICENCE), ('built', date.today().isoformat())])
    db.commit()
    db.close()
    tmp.replace(OUT)
    print(f'{n:,} places: ' + ', '.join(f'{k} {v:,}' for k, v in counts.items()))


if __name__ == '__main__':
    main()
