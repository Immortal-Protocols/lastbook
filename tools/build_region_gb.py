#!/usr/bin/env python3
"""Build a detailed offline map of Greater London (GB-LON), with a place finder for British postcodes, places and roads.

  python3 tools/build_region_gb.py fetch    # downloads the sources, about 333 MB, into derived/regions/GB-LON/source/
  python3 tools/build_region_gb.py build    # writes derived/regions/GB-LON/data/, a map set shaped like a US state map
  python3 tools/build_region_gb.py demo     # adds an empty library beside it, for trying the map on its own
  python3 tools/build_region_gb.py check    # validates it, through the engine with the network blocked; exits 1 on a failure
  python3 server.py --data derived/regions/GB-LON/demo --no-index

Python 3.9 or newer and its standard library only. fetch is the only step that uses the network. Everything is written
under derived/regions/GB-LON/, so derived/geo/ and every other map set stay as they are. See docs/MAP-GB-LON.md.

Sources, all redistributable (the credit lines are in CREDIT and go into map.sqlite, map-set.json and build.json):
  - OpenStreetMap via Geofabrik, greater-london-YYMMDD-free.gpkg.zip and greater-london.poly (ODbL 1.0): streets, water,
    land, rail, buildings, place labels and help points, cut by tools/build_map.py, which is run unchanged.
  - Ordnance Survey, OS Open Names (Open Government Licence v3.0): every postcode in Great Britain with its locality and
    borough, plus settlements, named and numbered roads, stations, schools and hospitals.
  - Ordnance Survey, Code-Point Open (OGL v3.0): the postcodes Open Names leaves out (about 0.4 % of them).

Both OS products give British National Grid eastings and northings (OSGB36). They are converted to WGS 84 here with the
Ordnance Survey's own formulas: transverse Mercator on the Airy 1830 ellipsoid, then the published seven-parameter
Helmert transformation, which OS gives as good to about 5 m. That is plenty for a postcode or a place name.

The rows go in national.sqlite, not map.sqlite, because the engine reads help points from map.sqlite only inside a box
around Southern California (_poi_sources in server.py); a US state map does the same. map.sqlite is empty and carries
the map's source and date. The place finder is clipped to Geofabrik's outline of the extract, so everything it finds
has streets drawn around it.
"""
import argparse
import collections
import csv
import hashlib
import io
import json
import math
import os
import re
import shutil
import sqlite3
import struct
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

REGION = {
    'id': 'GB-LON',
    'name': 'Greater London',
    # The ONS Regions (December 2024) box from docs/REGIONS-UK.md (#103), widened by the 0.15 degrees US state maps use.
    'box': (-0.67, 51.13, 0.49, 51.85),
    'geofabrik': 'europe/united-kingdom/england/greater-london',
}
ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'derived' / 'regions' / REGION['id']
SOURCE, WORK, DATA, DEMO = BASE / 'source', BASE / 'work', BASE / 'data', BASE / 'demo'
GEO = DATA / 'derived' / 'geo'
MAP_FILES = ('national.sqlite', 'map.sqlite', 'places.sqlite', 'national-status.json', 'socal-cells.json')

UA = {'User-Agent': 'lastbook-region-build'}
GEOFABRIK = 'https://download.geofabrik.de/'
OS_API = 'https://api.os.uk/downloads/v1/products/'
OS_PRODUCTS = {'open-names': 'OpenNames', 'code-point': 'CodePointOpen'}
OSM_LICENCE = 'ODbL 1.0'
OGL = 'Open Government Licence v3.0 (www.ordnancesurvey.co.uk/opendata/licence redirects to it)'
CREDIT = ('© OpenStreetMap contributors (ODbL). Contains OS data © Crown copyright and database right {year}. '
          'Contains Royal Mail data © Royal Mail copyright and database right {year}. '
          'Contains National Statistics data © Crown copyright and database right {year}. OS data under the OGL v3.0.')


# ------------------------------------------------------------------------------------------- British National Grid --
AIRY = (6377563.396, 6356256.909)
WGS84 = (6378137.000, 6356752.3141)
F0, LAT0, LON0, E0, N0 = 0.9996012717, math.radians(49), math.radians(-2), 400000.0, -100000.0
# OSGB36 to WGS 84: the negation of the WGS 84 to OSGB36 set in OS's "A guide to coordinate systems in Great Britain".
# Translations in metres, scale in parts per one, rotations in arc-seconds.
HELMERT = {'tx': 446.448, 'ty': -125.157, 'tz': 542.060, 's': -20.4894e-6, 'rx': 0.1502, 'ry': 0.2470, 'rz': 0.8421}


def _meridian(b, n, lat):
    dl, sl = lat - LAT0, lat + LAT0
    return b * F0 * ((1 + n + 1.25 * n ** 2 + 1.25 * n ** 3) * dl
                     - (3 * n + 3 * n ** 2 + 21 / 8 * n ** 3) * math.sin(dl) * math.cos(sl)
                     + (15 / 8 * n ** 2 + 15 / 8 * n ** 3) * math.sin(2 * dl) * math.cos(2 * sl)
                     - 35 / 24 * n ** 3 * math.sin(3 * dl) * math.cos(3 * sl))


def grid_to_osgb36(east, north):
    """National Grid easting and northing (metres) to OSGB36 latitude and longitude (degrees)."""
    a, b = AIRY
    e2, n = 1 - b * b / (a * a), (a - b) / (a + b)
    lat = (north - N0) / (a * F0) + LAT0
    m = _meridian(b, n, lat)
    while abs(north - N0 - m) >= 1e-5:
        lat += (north - N0 - m) / (a * F0)
        m = _meridian(b, n, lat)
    s = math.sin(lat)
    nu = a * F0 / math.sqrt(1 - e2 * s * s)
    rho = a * F0 * (1 - e2) / (1 - e2 * s * s) ** 1.5
    eta2 = nu / rho - 1
    t = math.tan(lat)
    t2, sec = t * t, 1 / math.cos(lat)
    vii = t / (2 * rho * nu)
    viii = t / (24 * rho * nu ** 3) * (5 + 3 * t2 + eta2 - 9 * t2 * eta2)
    ix = t / (720 * rho * nu ** 5) * (61 + 90 * t2 + 45 * t2 * t2)
    x = sec / nu
    xi = sec / (6 * nu ** 3) * (nu / rho + 2 * t2)
    xii = sec / (120 * nu ** 5) * (5 + 28 * t2 + 24 * t2 * t2)
    xiia = sec / (5040 * nu ** 7) * (61 + 662 * t2 + 1320 * t2 * t2 + 720 * t2 ** 3)
    de = east - E0
    return (math.degrees(lat - vii * de ** 2 + viii * de ** 4 - ix * de ** 6),
            math.degrees(LON0 + x * de - xi * de ** 3 + xii * de ** 5 - xiia * de ** 7))


def osgb36_to_grid(lat_deg, lon_deg):
    """OSGB36 latitude and longitude (degrees) to National Grid easting and northing (metres)."""
    a, b = AIRY
    e2, n = 1 - b * b / (a * a), (a - b) / (a + b)
    lat, lon = math.radians(lat_deg), math.radians(lon_deg)
    s, c, t = math.sin(lat), math.cos(lat), math.tan(lat)
    t2 = t * t
    nu = a * F0 / math.sqrt(1 - e2 * s * s)
    rho = a * F0 * (1 - e2) / (1 - e2 * s * s) ** 1.5
    eta2 = nu / rho - 1
    i = _meridian(b, n, lat) + N0
    ii = nu / 2 * s * c
    iii = nu / 24 * s * c ** 3 * (5 - t2 + 9 * eta2)
    iiia = nu / 720 * s * c ** 5 * (61 - 58 * t2 + t2 * t2)
    iv = nu * c
    v = nu / 6 * c ** 3 * (nu / rho - t2)
    vi = nu / 120 * c ** 5 * (5 - 18 * t2 + t2 * t2 + 14 * eta2 - 58 * t2 * eta2)
    dl = lon - LON0
    return E0 + iv * dl + v * dl ** 3 + vi * dl ** 5, i + ii * dl ** 2 + iii * dl ** 4 + iiia * dl ** 6


def _helmert(lat_deg, lon_deg, src, dst, sign):
    """Latitude and longitude on one ellipsoid to the other, through Earth-centred coordinates (height taken as 0)."""
    a, b = src
    e2 = 1 - b * b / (a * a)
    lat, lon = math.radians(lat_deg), math.radians(lon_deg)
    s = math.sin(lat)
    nu = a / math.sqrt(1 - e2 * s * s)
    x, y, z = nu * math.cos(lat) * math.cos(lon), nu * math.cos(lat) * math.sin(lon), (1 - e2) * nu * s
    k = math.pi / 648000
    tx, ty, tz, sc = (sign * HELMERT[key] for key in ('tx', 'ty', 'tz', 's'))
    rx, ry, rz = (sign * HELMERT[key] * k for key in ('rx', 'ry', 'rz'))
    x, y, z = (tx + (1 + sc) * x - rz * y + ry * z, ty + rz * x + (1 + sc) * y - rx * z, tz - ry * x + rx * y + (1 + sc) * z)
    a, b = dst
    e2 = 1 - b * b / (a * a)
    p = math.hypot(x, y)
    lat = math.atan2(z, p * (1 - e2))
    for _ in range(10):
        s = math.sin(lat)
        new = math.atan2(z + e2 * a / math.sqrt(1 - e2 * s * s) * s, p)
        done, lat = abs(new - lat) < 1e-12, new
        if done:
            break
    return math.degrees(lat), math.degrees(math.atan2(y, x))


def bng_to_wgs84(east, north):
    """National Grid easting and northing to WGS 84 (latitude, longitude), good to about 5 m."""
    return _helmert(*grid_to_osgb36(east, north), AIRY, WGS84, 1)


def wgs84_to_bng(lat, lon):
    return osgb36_to_grid(*_helmert(lat, lon, WGS84, AIRY, -1))


# ------------------------------------------------------------------------------------------------- the area itself --
def read_poly(path):
    """A Geofabrik .poly outline: [(is_hole, [(lon, lat), ...]), ...]."""
    rings, ring, hole = [], None, False
    for line in Path(path).read_text(encoding='utf-8').splitlines()[1:]:
        text = line.strip()
        if not text:
            continue
        if ring is None:
            if text == 'END':
                break
            hole, ring = text.startswith('!'), []
        elif text == 'END':
            rings.append((hole, ring))
            ring = None
        else:
            lon, lat = text.split()[:2]
            ring.append((float(lon), float(lat)))
    return rings


def _in_ring(x, y, ring):
    inside, j = False, len(ring) - 1
    for i, (xi, yi) in enumerate(ring):
        xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


class Area:
    """Point-in-outline, fast: a grid over the outline, where only cells an edge crosses need the exact test."""

    def __init__(self, rings, cells=256):
        self.rings = rings
        xs = [x for _, ring in rings for x, _ in ring]
        ys = [y for _, ring in rings for _, y in ring]
        self.box = (min(xs), min(ys), max(xs), max(ys))
        self.dx, self.dy = (self.box[2] - self.box[0]) / cells, (self.box[3] - self.box[1]) / cells
        self.edge, self.memo = set(), {}
        for _, ring in rings:
            for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
                steps = int(max(abs(x2 - x1) / self.dx, abs(y2 - y1) / self.dy) * 4) + 1
                for step in range(steps + 1):
                    cx, cy = self._cell(x1 + (x2 - x1) * step / steps, y1 + (y2 - y1) * step / steps)
                    self.edge.update((cx + i, cy + j) for i in (-1, 0, 1) for j in (-1, 0, 1))

    def _cell(self, x, y):
        return int((x - self.box[0]) / self.dx), int((y - self.box[1]) / self.dy)

    def exact(self, lon, lat):
        return (any(_in_ring(lon, lat, ring) for hole, ring in self.rings if not hole)
                and not any(_in_ring(lon, lat, ring) for hole, ring in self.rings if hole))

    def contains(self, lon, lat):
        if not (self.box[0] <= lon <= self.box[2] and self.box[1] <= lat <= self.box[3]):
            return False
        cell = self._cell(lon, lat)
        if cell in self.edge:
            return self.exact(lon, lat)
        if cell not in self.memo:
            self.memo[cell] = self.exact(self.box[0] + (cell[0] + .5) * self.dx, self.box[1] + (cell[1] + .5) * self.dy)
        return self.memo[cell]


def metres(lat1, lon1, lat2, lon2):
    """Short distances: plain enough for matching names a few hundred metres apart."""
    return math.hypot((lon2 - lon1) * math.cos(math.radians(lat1)) * 111320, (lat2 - lat1) * 110574)


# ------------------------------------------------------------------------------------------------------------ fetch --
def _get(url, method='GET'):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA, method=method), timeout=120)


def file_hash(path, kind='sha256'):
    h = hashlib.new(kind)
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def _download(url, dest, md5=None):
    if dest.exists() and (md5 is None or file_hash(dest, 'md5') == md5):
        return 'kept'
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + '.part')
    with _get(url) as response, open(part, 'wb') as f:
        shutil.copyfileobj(response, f, 1 << 20)
    if md5 and file_hash(part, 'md5') != md5:
        part.unlink()
        raise SystemExit(f"{dest.name}: the download does not match the publisher's checksum")
    part.replace(dest)
    return 'downloaded'


def fetch():
    found, now = {}, time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    with _get(GEOFABRIK + REGION['geofabrik'] + '-latest-free.gpkg.zip', 'HEAD') as response:
        url = response.geturl()          # 'latest' redirects to the dated file, whose name is what gets recorded
    osm = SOURCE / 'osm' / url.rsplit('/', 1)[1]
    state = _download(url, osm)
    with zipfile.ZipFile(osm) as z:
        if z.testzip() is not None:
            osm.unlink()
            raise SystemExit(f'{osm.name} is damaged; run fetch again')
        readme = z.read('README').decode('utf-8', 'replace')
    print(state, osm.name)
    found['osm'] = {'url': url, 'licence': OSM_LICENCE, 'data_as_of': _as_of(readme),
                    'note': 'Geofabrik publishes no checksum for GeoPackage files; the zip is tested and its SHA-256 recorded'}
    found['osm_poly'] = {'url': GEOFABRIK + REGION['geofabrik'] + '.poly', 'licence': OSM_LICENCE}
    print(_download(found['osm_poly']['url'], SOURCE / 'osm' / (Path(REGION['geofabrik']).name + '.poly')), 'outline')
    found['osm']['file'], found['osm_poly']['file'] = str(osm.relative_to(BASE)), f"source/osm/{Path(REGION['geofabrik']).name}.poly"
    for key, product in OS_PRODUCTS.items():
        with _get(OS_API + product) as response:
            version = json.load(response).get('version')
        with _get(OS_API + product + '/downloads') as response:
            item = next(d for d in json.load(response) if d.get('format') == 'CSV' and d.get('area') == 'GB')
        dest = SOURCE / key / item['fileName']
        print(_download(item['url'], dest, item.get('md5')), dest.name, version)
        found[key] = {'url': item['url'], 'file': str(dest.relative_to(BASE)), 'version': version, 'md5': item.get('md5'),
                      'licence': OGL}
    for item in found.values():
        path = BASE / item['file']
        item.update(bytes=path.stat().st_size, sha256=file_hash(path), fetched=now)
    (SOURCE / 'source.json').write_text(json.dumps(found, indent=1), encoding='utf-8')
    print('sources recorded in', (SOURCE / 'source.json').relative_to(ROOT))


def _as_of(readme):
    match = re.search(r'data as of (\S+)', readme)
    return match[1] if match else None


# ------------------------------------------------------------------------------------------------------------ build --
SETTLEMENT = {'City': 'city', 'Town': 'town', 'Village': 'village', 'Hamlet': 'hamlet', 'Suburban Area': 'suburb',
              'Other Settlement': 'settlement'}
ROAD = {'Named Road', 'Section Of Named Road', 'Numbered Road', 'Section Of Numbered Road'}
OTHER_KIND = {'Primary Education': 'school', 'Secondary Education': 'school', 'Non State Primary Education': 'school',
              'Non State Secondary Education': 'school', 'Special Needs Education': 'school',
              'Further Education': 'college', 'Higher or University Education': 'university',
              'Medical Care Accommodation': 'care home'}
# Lower ranks come first in the place finder (server.places), as in tools/build_places.py. Postcodes come last: each
# one's detail names its locality and borough, so a search for 'Paddington' or 'Tower Hamlets' matches thousands of
# them, and ranked any higher they would push the station, the roads and the borough itself out of the engine's first
# 200 matches. A postcode typed as such still comes first, because an exact name always sorts ahead.
RANK = {'settlement': 1, 'borough': 1, 'postcode district': 1, 'road': 3, 'other': 4, 'postcode': 5}


def join(*parts):
    out = []
    for part in parts:
        if part and part not in out:
            out.append(part)
    return ', '.join(out)


def os_rows(zip_path, header_member, data_prefix):
    """Every row of an OS CSV download as a dict, read straight from the zip."""
    with zipfile.ZipFile(zip_path) as z:
        header = z.read(header_member).decode('utf-8-sig').strip().splitlines()[-1].split(',') if header_member else None
        for name in sorted(z.namelist()):
            if name.startswith(data_prefix) and name.lower().endswith('.csv'):
                with z.open(name) as f:
                    for row in csv.reader(io.TextIOWrapper(f, encoding='utf-8-sig', errors='replace')):
                        yield dict(zip(header, row)) if header else row


class Places:
    def __init__(self, area):
        self.area = area
        lat0, lon0, lat1, lon1 = area.box[1], area.box[0], area.box[3], area.box[2]
        corners = [wgs84_to_bng(la, lo) for la in (lat0, lat1) for lo in (lon0, lon1)]
        self.grid = (min(e for e, _ in corners) - 1000, min(n for _, n in corners) - 1000,
                     max(e for e, _ in corners) + 1000, max(n for _, n in corners) + 1000)
        self.rows, self.named, self.postcodes = [], collections.defaultdict(list), {}
        self.counts = collections.Counter()

    def locate(self, east, north):
        """WGS 84 (lat, lon) for a National Grid point inside the area, else None."""
        try:
            east, north = float(east), float(north)
        except ValueError:
            return None
        g = self.grid
        if not (g[0] <= east <= g[2] and g[1] <= north <= g[3]) or (east == 0 and north == 0):
            return None
        lat, lon = bng_to_wgs84(east, north)
        return (round(lat, 6), round(lon, 6)) if self.area.contains(lon, lat) else None

    def add(self, name, kind, detail, lat, lon, rank, source):
        self.rows.append((name, kind, detail, lat, lon, rank, source))
        self.counts[kind] += 1

    def open_names(self, zip_path):
        sectors = collections.defaultdict(collections.Counter)   # 'SW1A 2' -> (locality, borough) seen there
        districts = collections.defaultdict(list)
        boroughs = collections.defaultdict(list)
        for r in os_rows(zip_path, 'Doc/OS_Open_Names_Header.csv', 'Data/'):
            local = r.get('LOCAL_TYPE', '')
            where = self.locate(r.get('GEOMETRY_X', ''), r.get('GEOMETRY_Y', ''))
            if not where or not r.get('NAME1'):
                continue
            lat, lon = where
            name, also = r['NAME1'], r.get('NAME2') if r.get('NAME2') not in ('', r['NAME1']) else ''
            borough, place = r.get('DISTRICT_BOROUGH', ''), r.get('POPULATED_PLACE', '')
            if local == 'Postcode':
                code = ' '.join(name.split()).upper()
                self.postcodes[code] = (lat, lon)
                self.add(code, 'postcode', join(place, borough), lat, lon, RANK['postcode'], 'OS Open Names')
                sectors[code[:-2]][(place, borough)] += 1
                districts[code.split()[0]].append((lat, lon, place, borough))
                if r.get('COUNTY_UNITARY') == 'Greater London' and borough:
                    boroughs[borough].append((lat, lon))
                continue
            if local in SETTLEMENT:
                kind, rank, detail = SETTLEMENT[local], RANK['settlement'], join(borough, r.get('COUNTY_UNITARY'))
            elif local in ROAD:
                kind, rank, detail = 'road', RANK['road'], join(place, borough, r.get('POSTCODE_DISTRICT'))
            else:
                first = local.split(',')[0]
                kind, rank, detail = OTHER_KIND.get(first, first.lower()), RANK['other'], join(place, borough, r.get('POSTCODE_DISTRICT'))
            if also:
                detail = join(detail, 'also called ' + also)
            self.add(name, kind, detail, lat, lon, rank, 'OS Open Names')
            self.named[name.lower()].append((lat, lon))
            if also:
                self.named[also.lower()].append((lat, lon))
        for code, members in districts.items():
            where = collections.Counter((p, b) for _, _, p, b in members).most_common(1)[0][0]
            self._centre(code, 'postcode district', join(*where), [(la, lo) for la, lo, _, _ in members], 'OS Open Names (middle of its postcodes)')
        for borough, members in boroughs.items():
            self._centre(borough, 'borough', 'Greater London', members, 'OS Open Names (middle of its postcodes)')
        self.sectors = sectors
        self.districts = districts

    def _centre(self, name, kind, detail, points, source):
        lat, lon = sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points)
        self.add(name, kind, detail, round(lat, 6), round(lon, 6), RANK[kind], source)
        self.named[name.lower()].append((lat, lon))

    def code_point(self, zip_path):
        """Postcodes Open Names does not carry. Code-Point has no names, so the locality comes from the postcode's sector."""
        for r in os_rows(zip_path, None, 'Data/CSV/'):
            if len(r) < 4 or r[1] == '90':                 # positional quality 90: no coordinates
                continue
            code = ' '.join(r[0].split()).upper()
            if code in self.postcodes:
                continue
            where = self.locate(r[2], r[3])
            if not where:
                continue
            seen = self.sectors.get(code[:-2]) or collections.Counter(
                (p, b) for _, _, p, b in self.districts.get(code.split()[0], []))
            detail = join(*seen.most_common(1)[0][0]) if seen else ''
            self.postcodes[code] = where
            self.add(code, 'postcode', detail, where[0], where[1], RANK['postcode'], 'OS Code-Point Open')

    def osm(self, national):
        """Named help points and place labels from the map itself, unless OS already has the same name close by."""
        db = sqlite3.connect(f'file:{national}?mode=ro', uri=True)
        label = f"{REGION['name']} (OpenStreetMap)"
        for cls, name, lon, lat in db.execute("SELECT cls,name,lon,lat FROM poi WHERE name IS NOT NULL AND name<>''"):
            if not any(metres(lat, lon, la, lo) < 300 for la, lo in self.named.get(name.lower(), ())):
                self.add(name, cls.replace('_', ' '), label, round(lat, 6), round(lon, 6), 4, 'OpenStreetMap')
        for cls, name, geom in db.execute("SELECT cls,name,geom FROM feat WHERE layer='place' AND name IS NOT NULL AND name<>''"):
            _, _, x, y = struct.unpack_from('<iiii', geom)
            lat, lon = y / 1e6, x / 1e6
            if self.area.contains(lon, lat) and not any(metres(lat, lon, la, lo) < 2000 for la, lo in self.named.get(name.lower(), ())):
                self.add(name, cls.replace('_', ' '), label, round(lat, 6), round(lon, 6), 1, 'OpenStreetMap')
        db.close()

    def write(self, path):
        path.unlink(missing_ok=True)
        db = sqlite3.connect(path)
        db.executescript('''CREATE TABLE place(id INTEGER PRIMARY KEY, name TEXT, kind TEXT, detail TEXT, lat REAL, lon REAL, rank INTEGER, source TEXT);
          CREATE VIRTUAL TABLE place_fts USING fts5(name, detail, content='place', content_rowid='id', tokenize='unicode61');''')
        db.executemany('INSERT INTO place(name,kind,detail,lat,lon,rank,source) VALUES (?,?,?,?,?,?,?)', self.rows)
        db.execute("INSERT INTO place_fts(place_fts) VALUES ('rebuild')")
        db.commit()
        db.execute('VACUUM')
        db.close()


def _empty_like(src, dest, meta):
    """map.sqlite as in a US state map: the same four tables, no rows, plus the map's own source and date."""
    dest.unlink(missing_ok=True)
    old = sqlite3.connect(f'file:{src}?mode=ro', uri=True)
    schema = [r[0] for r in old.execute("SELECT sql FROM sqlite_master WHERE name IN ('feat','feat_idx','poi','meta') ORDER BY name")]
    old.close()
    db = sqlite3.connect(dest)
    for sql in schema:
        db.execute(sql)
    db.executemany('INSERT INTO meta VALUES (?,?)', meta.items())
    db.commit()
    db.close()


def build():
    t0 = time.time()
    try:
        src = json.loads((SOURCE / 'source.json').read_text(encoding='utf-8'))
    except OSError:
        raise SystemExit('run fetch first: derived/regions/GB-LON/source/source.json is missing')
    for key, item in src.items():
        path = BASE / item['file']
        if not path.is_file() or path.stat().st_size != item['bytes'] or file_hash(path) != item['sha256']:
            raise SystemExit(f'{item["file"]} is missing or has changed since fetch; run fetch again')
    if DATA.exists():
        shutil.rmtree(DATA)                 # only ever this region's own output folder
    GEO.mkdir(parents=True)
    WORK.mkdir(exist_ok=True)

    osm_zip = BASE / src['osm']['file']
    gpkg = WORK / 'extract.gpkg'
    with zipfile.ZipFile(osm_zip) as z:
        member = next(i for i in z.infolist() if i.filename.endswith('.gpkg'))
        if not (gpkg.exists() and gpkg.stat().st_size == member.file_size):
            with z.open(member) as f, open(gpkg, 'wb') as out:
                shutil.copyfileobj(f, out, 1 << 20)
    year = _licence_year(BASE / src['open-names']['file'])
    credit = CREDIT.format(year=year)
    national = GEO / 'national.sqlite'
    print('streets, water, land, buildings and help points: tools/build_map.py', flush=True)
    subprocess.run([sys.executable, '-B', str(ROOT / 'tools' / 'build_map.py'), str(gpkg), str(national)], check=True)
    meta = {'source': f"OpenStreetMap contributors, via Geofabrik {Path(src['osm']['file']).name} ({OSM_LICENCE})",
            'data_as_of': src['osm']['data_as_of'], 'bounds': ','.join(f'{v:.2f}' for v in REGION['box']),
            'region': REGION['id'], 'credit': credit, 'built': time.strftime('%Y-%m-%dT%H:%M:%S')}
    db = sqlite3.connect(national)
    db.executemany('INSERT OR REPLACE INTO meta VALUES (?,?)', meta.items())
    features = db.execute('SELECT count(*) FROM feat').fetchone()[0]
    pins = db.execute('SELECT count(*) FROM poi').fetchone()[0]
    db.commit()
    db.close()
    _empty_like(national, GEO / 'map.sqlite', meta)
    (GEO / 'national-status.json').write_text(json.dumps({'state': 'complete', 'stage': 'ready', 'features': features}), encoding='utf-8')
    (GEO / 'socal-cells.json').write_text('[]', encoding='utf-8')

    print('place finder: OS Open Names, Code-Point Open, OpenStreetMap names', flush=True)
    places = Places(Area(read_poly(BASE / src['osm_poly']['file'])))
    places.open_names(BASE / src['open-names']['file'])
    places.code_point(BASE / src['code-point']['file'])
    places.osm(national)
    places.write(GEO / 'places.sqlite')

    sizes = {f'derived/geo/{name}': (GEO / name).stat().st_size for name in MAP_FILES}
    (DATA / 'map-set.json').write_text(json.dumps({'name': REGION['id'], 'title': REGION['name'], 'files': sizes,
                                                   'bytes': sum(sizes.values()), 'credit': credit}, indent=1), encoding='utf-8')
    outputs = {rel: {'bytes': size, 'sha256': file_hash(DATA / rel)} for rel, size in sizes.items()}
    record = {'region': REGION, 'built': meta['built'], 'seconds': round(time.time() - t0), 'python': sys.version.split()[0],
              'sources': src, 'credit': credit, 'outputs': outputs,
              'counts': {'features': features, 'help_points': pins, 'places': dict(sorted(places.counts.items(), key=lambda kv: -kv[1]))}}
    (BASE / 'build.json').write_text(json.dumps(record, indent=1, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({'seconds': record['seconds'], 'features': features, 'help_points': pins,
                      'places': sum(places.counts.values()), 'bytes': sum(sizes.values())}))


def _licence_year(zip_path):
    with zipfile.ZipFile(zip_path) as z:
        text = z.read('Doc/licence.txt').decode('utf-8', 'replace')
    years = re.findall(r'database rights? (\d{4})', text)
    return years[0] if years else time.strftime('%Y')


# ------------------------------------------------------------------------------------------------------------- demo --
def demo():
    """A data folder for trying the map on its own: the app also needs a library, so this adds an empty one.

    The map files stay in data/ (what a map download would hold); demo/ links to them. Its pack.json says which map it
    holds, as every published pack's does, so the Map page opens on this map's own area and offers only its layers."""
    if not (DATA / 'map-set.json').exists():
        raise SystemExit('run build first')
    (DEMO / 'library-data').mkdir(parents=True, exist_ok=True)
    (DEMO / 'library-data' / 'catalog.json').write_text('[]\n', encoding='utf-8')
    shutil.copyfile(DATA / 'map-set.json', DEMO / 'map-set.json')
    (DEMO / 'pack.json').write_text(json.dumps({'name': f"{REGION['id']} map demo", 'map': REGION['id'],
                                                'built': time.strftime('%Y-%m-%d'), 'note': 'made by tools/build_region_gb.py demo'},
                                               indent=1), encoding='utf-8')
    link = DEMO / 'derived'
    if not link.exists():
        try:
            link.symlink_to(Path('..') / 'data' / 'derived', target_is_directory=True)
        except OSError:       # Windows without symlink rights: a copy works the same
            shutil.copytree(DATA / 'derived', link)
    print(f'python3 server.py --data {DEMO.relative_to(ROOT)} --no-index')


# ------------------------------------------------------------------------------------------------------------ check --
ENGINE = r'''
import json, math, socket, sys
def refuse(*args, **kwargs):
    raise OSError('the network is blocked during the check')
socket.socket.connect = refuse
socket.create_connection = refuse
socket.getaddrinfo = refuse
import server
lat, lon, z = 51.5033, -0.1276, 15          # buildings are drawn from zoom 15 (_map_tile in server.py)
x = int((lon + 180) / 360 * 2 ** z)
y = int((1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * 2 ** z)
tile = json.loads(server.map_tile(z, x, y))
first = lambda q: [{k: p.get(k) for k in ('name', 'kind', 'detail', 'onMap')} for p in server.places(q)[:3]]
print(json.dumps({
    'postcode': first('SW1A 2AA'), 'postcode_no_space': first('sw1a2aa'), 'district': first('SW1A'),
    'borough': first('Croydon'), 'borough_only': first('Tower Hamlets'), 'road': first('Downing Street'), 'station': first('East Croydon'), 'area': first('Paddington'),
    'near': [{k: p[k] for k in ('cls', 'name', 'km')} for p in server.near(lat, lon, ['hospital', 'pharmacy', 'police'])],
    'contents': server.map_contents(), 'tile': {k: len(v) for k, v in tile.get('layers', {}).items()},
}))
'''


def check():
    failures = []

    def ok(condition, what):
        print(('ok    ' if condition else 'FAIL  ') + what)
        if not condition:
            failures.append(what)

    record = json.loads((BASE / 'build.json').read_text(encoding='utf-8'))
    for rel, out in record['outputs'].items():
        path = DATA / rel
        ok(path.is_file() and path.stat().st_size == out['bytes'] and file_hash(path) == out['sha256'], f'{rel} matches build.json')
    map_set = json.loads((DATA / 'map-set.json').read_text(encoding='utf-8'))
    ok(map_set['name'] == REGION['id'], f"map-set.json is named {REGION['id']}")
    ok(all((DATA / rel).stat().st_size == size for rel, size in map_set['files'].items()), 'map-set.json lists each file at its size')
    held = sorted(p.relative_to(DATA).as_posix() for p in DATA.rglob('*') if p.is_file())
    ok(held == sorted(['map-set.json', *map_set['files']]), 'the map set holds only its listed files (no -wal, -shm or strays)')
    for name in ('national.sqlite', 'map.sqlite', 'places.sqlite'):
        db = sqlite3.connect(f'file:{GEO / name}?mode=ro', uri=True)
        ok(db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok', f'{name} integrity_check')
        ok(db.execute('PRAGMA journal_mode').fetchone()[0] == 'delete', f'{name} journal mode is DELETE')
        db.close()

    w, s, e, n = REGION['box']
    nat = sqlite3.connect(f"file:{GEO / 'national.sqlite'}?mode=ro", uri=True)
    counts = dict(nat.execute('SELECT layer, count(*) FROM feat GROUP BY layer'))
    ok(counts.get('road', 0) > 200000 and counts.get('bldg', 0) > 500000, f"roads {counts.get('road', 0):,}, buildings {counts.get('bldg', 0):,}")
    kinds = dict(nat.execute('SELECT cls, count(*) FROM poi GROUP BY cls'))
    for cls, least in (('hospital', 30), ('pharmacy', 1000), ('fire_station', 50), ('police', 30), ('drinking_water', 50), ('supermarket', 500)):
        ok(kinds.get(cls, 0) >= least, f'{kinds.get(cls, 0):,} {cls} points (at least {least})')
    ok(nat.execute('SELECT count(*) FROM poi WHERE lon NOT BETWEEN ? AND ? OR lat NOT BETWEEN ? AND ?', (w, e, s, n)).fetchone()[0] == 0,
       'every help point is inside the region box')

    pl = sqlite3.connect(f"file:{GEO / 'places.sqlite'}?mode=ro", uri=True)
    pk = dict(pl.execute('SELECT kind, count(*) FROM place GROUP BY kind'))
    ok(pk.get('postcode', 0) > 150000, f"{pk.get('postcode', 0):,} postcodes")
    ok(pk.get('postcode district', 0) > 200, f"{pk.get('postcode district', 0):,} postcode districts")
    ok(pk.get('borough', 0) == 33, f"{pk.get('borough', 0)} boroughs (32 London boroughs and the City)")
    ok(pk.get('road', 0) > 30000, f"{pk.get('road', 0):,} roads")
    ok(sum(pk.get(k, 0) for k in SETTLEMENT.values()) > 500, f"{sum(pk.get(k, 0) for k in SETTLEMENT.values()):,} settlements and suburbs")
    ok(pl.execute('SELECT count(*) FROM place WHERE lon NOT BETWEEN ? AND ? OR lat NOT BETWEEN ? AND ?', (w, e, s, n)).fetchone()[0] == 0,
       'every place is inside the region box')
    # The grid conversion, checked against OpenStreetMap: the same named things, mapped independently, should not be
    # shifted one way. Any one pair differs by tens of metres; a wrong datum shift would move them all ~100 m or more.
    os_named = collections.defaultdict(list)
    for name, lat, lon in pl.execute("SELECT lower(name), lat, lon FROM place WHERE source='OS Open Names' AND kind NOT IN ('postcode','road')"):
        os_named[name].append((lat, lon))
    dx, dy = [], []
    for name, lon, lat in nat.execute("SELECT lower(name), lon, lat FROM poi WHERE name IS NOT NULL AND cls IN ('hospital','school','library','police','fire_station','college','university')"):
        near = [(metres(lat, lon, la, lo), la, lo) for la, lo in os_named.get(name, ())]
        if near and min(near)[0] < 300:
            _, la, lo = min(near)
            dx.append((lo - lon) * math.cos(math.radians(lat)) * 111320)
            dy.append((la - lat) * 110574)
    dx.sort(), dy.sort()
    mid = len(dx) // 2
    ok(len(dx) > 200 and abs(dx[mid]) < 25 and abs(dy[mid]) < 25,
       f'OS and OpenStreetMap agree: {len(dx)} pairs, median shift {dx[mid] if dx else 0:+.1f} m east, {dy[mid] if dy else 0:+.1f} m north')

    if not (DEMO / 'pack.json').exists():
        demo()
    env = dict(os.environ, LASTBOOK_DATA=str(DEMO), PYTHONPATH=str(ROOT))
    run = subprocess.run([sys.executable, '-B', '-c', ENGINE], cwd=ROOT, env=env, capture_output=True, text=True, timeout=600)
    ok(run.returncode == 0, 'the engine loads the map with the network blocked' + ('' if run.returncode == 0 else ': ' + run.stderr.strip()[-600:]))
    if run.returncode == 0:
        got = json.loads(run.stdout.strip().splitlines()[-1])
        top = lambda key: (got[key] or [{}])[0]
        ok(top('postcode').get('name') == 'SW1A 2AA' and top('postcode').get('onMap'), f"'SW1A 2AA' finds the postcode: {top('postcode')}")
        ok(top('postcode_no_space').get('name') == 'SW1A 2AA', f"'sw1a2aa' finds it too: {top('postcode_no_space')}")
        ok(top('district').get('kind') == 'postcode district', f"'SW1A' finds the postcode district: {top('district')}")
        ok({'settlement', 'borough'} <= {p['kind'] for p in got['borough']}, f"'Croydon' finds the town and the borough: {got['borough']}")
        ok(top('borough_only').get('kind') == 'borough', f"'Tower Hamlets' finds the borough: {top('borough_only')}")
        ok(top('road').get('kind') == 'road', f"'Downing Street' finds the road: {top('road')}")
        ok(any('station' in (p['kind'] or '') for p in got['station']), f"'East Croydon' finds the station: {got['station']}")
        # places() shows one hit per name in each 0.01° cell, so Paddington station and the area merge; a postcode must not lead
        ok(top('area').get('kind') == 'settlement', f"'Paddington' finds the area before any postcode: {got['area']}")
        hosp = [p for p in got['near'] if p['cls'] == 'hospital']
        ok(bool(hosp) and hosp[0]['km'] < 3, f"nearest hospital to Westminster: {hosp[:1]}")
        b = got['contents'].get('bounds') or [0, 0, 0, 0]
        ok(w <= b[0] and s <= b[1] and b[2] <= e and b[3] <= n, f"the map opens on its own area: {b}")
        ok(got['tile'].get('road', 0) > 100 and got['tile'].get('bldg', 0) > 100, f"a zoom-15 tile over Westminster draws: {got['tile']}")
    print(f'{len(failures)} failure(s)' if failures else 'all checks passed')
    return 1 if failures else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('step', choices=('fetch', 'build', 'demo', 'check'))
    step = parser.parse_args().step
    sys.exit({'fetch': fetch, 'build': build, 'demo': demo, 'check': check}[step]() or 0)


if __name__ == '__main__':
    main()
