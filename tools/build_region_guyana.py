#!/usr/bin/env python3
"""Builds the source files for the Guyana (GY) detailed map from open data, in the same tables the US builders write.

  python3 tools/build_region_guyana.py all                      # fetch, build every layer, merge
  python3 tools/build_region_guyana.py fetch [LAYER ...]        # downloads only
  python3 tools/build_region_guyana.py build [LAYER ...]        # fetch what is missing, then build these layers:
                                                                #   streets places water terrain crops buildings
  python3 tools/build_region_guyana.py merge                    # copy the built rows into derived/geo/*.sqlite
  ... --box=W,S,E,N    limit everything to a smaller box (a test build); default is regions.box('GY')
  ... --workers N      terrain worker processes (default 4)

Then `python3 packaging/build_packs.py map GY` cuts the map set as for a US state, once build_packs knows the region
codes in packaging/regions/ (state_box asks regions.box(code)). Until then this tool runs on its own.

Run on a build machine, never in the app. It downloads about 2.1 GB for the whole country (1.8 GB of it terrain) into
derived/geo/sources/regions/GY/, and needs numpy, tifffile and imagecodecs for terrain and land cover.

Reads (licence, what to credit):
  OpenStreetMap, Geofabrik Guyana extract (guyana-latest-free.gpkg.zip)   ODbL 1.0, "© OpenStreetMap contributors"
  Copernicus DEM GLO-30, 1° COG tiles from the Copernicus DEM open bucket  Copernicus WorldDEM-30 licence: "produced using
      Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS
      by the European Union and ESA; all rights reserved", and the no-liability notice; both passed on with the data
  ESA WorldCover 10 m 2021 v200, 3° tiles (cropland class only)            CC BY 4.0, "© ESA WorldCover project 2021 /
      Contains modified Copernicus Sentinel data (2021) processed by ESA WorldCover consortium"
  Microsoft Global ML Building Footprints, the Guyana rows of dataset-links.csv   CDLA Permissive 2.0 per Microsoft's
      README (Overture lists it under ODbL; confirm before publishing)
  OCHA Guyana COD-AB admin levels 1 and 2 (shapefiles)                     CC BY-IGO, credit OCHA and DEVInfo LAC
The same sources and lines are in packaging/regions/GY.json ("sources", "attribution").

Writes derived/geo/regions/GY/<name>.sqlite, one file per US map file, with the US tables:
  national.sqlite   feat, feat_idx, poi, meta        roads, land, waterways, place labels (as tools/build_map.py), and
                                                     help points of the classes in tools/build_map.py POI_KEEP
  water.sqlite      resource, spatial, feat, feat_idx, meta, water_fts   water outlines and named lakes/reservoirs
                                                     (as tools/build_water.py; origin 'osm:GY'); no dams
  terrain.sqlite    tile, meta                       terrain-RGB PNG tiles z4-12 (as tools/build_terrain.py)
  crops.sqlite      resource, spatial, tile, meta    WorldCover cropland: ~600 m clickable cells (kind 'cropland') and
                                                     a colour overlay z7-13 (as tools/build_crops.py)
  buildings.sqlite  bldg, bldg_socal, bldg_osm, meta footprints in z14 buckets (tools/build_buildings.py's format;
                                                     part numbers from PART_BASE so they never meet the US ones)
  places.sqlite     place, place_fts                 OSM places and named points (source 'OpenStreetMap'), OCHA regions
                                                     and sub-regions (source 'OCHA')
There is no address index: no open address data for Guyana was found. `merge` adds these rows to derived/geo/*.sqlite,
replacing only rows an earlier merge of GY added. Rebuilding a US file that starts from empty (build_crops.py) drops
them, so merge again after that.
"""
import argparse, json, math, os, sqlite3, struct, sys, time, urllib.error, urllib.request, zipfile, zlib
from array import array
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / 'packaging'))
sys.path.insert(0, str(HERE / 'tools'))
import regions  # noqa: E402

CODE = 'GY'
GEO = HERE / 'derived/geo'
SRC = GEO / 'sources/regions' / CODE
OUT = GEO / 'regions' / CODE
LAYERS = ('streets', 'places', 'water', 'terrain', 'crops', 'buildings')
FILES = {'streets': 'national', 'places': 'places', 'water': 'water', 'terrain': 'terrain', 'crops': 'crops', 'buildings': 'buildings'}

OSM_URL = 'https://download.geofabrik.de/south-america/guyana-latest-free.gpkg.zip'
OCHA_URL = ('https://data.humdata.org/dataset/9647d5cc-9de9-4974-a8be-62fb12c19ffe/resource/'
            '483dd6a3-dbb8-49ac-b248-4fe13acf6acf/download/guy_admbnd_2021_shp.zip')
COPDEM_URL = 'https://copernicus-dem-30m.s3.amazonaws.com/{name}/{name}.tif'
WORLDCOVER_URL = 'https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/{name}.tif'
MSB_LINKS = 'https://minedbuildings.z5.web.core.windows.net/global-buildings/dataset-links.csv'
MSB_LOCATION = 'Guyana'
OSM_SOURCE = 'OpenStreetMap contributors, via Geofabrik guyana-latest-free.gpkg.zip (ODbL 1.0)'
DEM_SOURCE = 'Copernicus DEM GLO-30 (Copernicus WorldDEM-30, ESA and Airbus)'
WC_SOURCE = 'ESA WorldCover 10 m 2021 v200 (CC BY 4.0)'
MSB_SOURCE = 'Microsoft Global ML Building Footprints, release 2026-02-03'
PART_BASE = 900000          # buildings.sqlite part numbers for this region: PART_BASE + file number
DETAIL = 'Guyana'

# The same lists as tools/build_map.py (that file runs on import, so they are repeated here; a test keeps them equal).
ROAD_Z = {'motorway': 5, 'trunk': 6, 'motorway_link': 10, 'trunk_link': 10, 'primary': 8, 'primary_link': 12,
          'secondary': 10, 'secondary_link': 13, 'tertiary': 11, 'tertiary_link': 13, 'residential': 13,
          'unclassified': 13, 'living_street': 14, 'pedestrian': 14, 'busway': 14, 'service': 15,
          'track': 13, 'track_grade1': 13, 'track_grade2': 13, 'track_grade3': 13, 'track_grade4': 13, 'track_grade5': 13,
          'footway': 15, 'path': 14, 'cycleway': 14, 'steps': 16, 'bridleway': 14, 'unknown': 15}
LANDUSE_KEEP = {'park': 'park', 'forest': 'green', 'grass': 'green', 'meadow': 'green', 'scrub': 'green', 'heath': 'green',
                'recreation_ground': 'park', 'cemetery': 'park', 'allotments': 'farm', 'farmland': 'farm',
                'orchard': 'farm', 'vineyard': 'farm', 'farmyard': 'farm', 'residential': 'res', 'commercial': 'com',
                'retail': 'com', 'industrial': 'ind', 'military': 'ind', 'quarry': 'ind', 'landfill': 'ind'}
PLACE_Z = {'county': 7, 'city': 6, 'town': 9, 'suburb': 12, 'village': 11, 'hamlet': 14, 'locality': 14, 'island': 11,
           'farm': 15, 'region': 5}
POI_KEEP = {'hospital', 'clinic', 'doctors', 'pharmacy', 'chemist', 'dentist', 'veterinary', 'fire_station', 'police',
            'drinking_water', 'water_tower', 'water_works', 'fountain', 'toilet', 'shelter', 'community_centre',
            'town_hall', 'school', 'library', 'supermarket', 'convenience', 'doityourself', 'hardware', 'garden_centre',
            'post_office', 'camp_site', 'wastewater_plant', 'comms_tower', 'spring', 'park', 'courthouse', 'embassy',
            'nursing_home', 'kindergarten', 'college', 'university', 'bicycle_shop', 'car_repair', 'fuel', 'beach'}
PLACE_CLS = {'national_capital': 'city'}      # Geofabrik's class for the capital; the map and server.py know city and town
EXTRA_PLACE_Z = {'national_capital': 5}

# ESA WorldCover classes kept: code -> (name, resource kind, RGB). Land cover only, so one class.
WORLDCOVER = {40: ('Cropland', 'cropland', (230, 180, 60))}
WC_LEVEL = 2                # overview level read: 3° / 9000 px, about 37 m, near the 30 m of the US crop layer
CROP_BLOCK = 16             # 16 x 16 px of that level, about 600 m, as the US clickable cells
CROP_MAXZ, CROP_MINZ = 13, 7


# ------------------------------------------------------------- tiling ----
def box_arg(text):
    w, s, e, n = (float(v) for v in text.split(','))
    if not (-180 <= w < e <= 180 and -90 <= s < n <= 90):
        raise argparse.ArgumentTypeError(f'bad box {text}')
    return w, s, e, n


def default_box():
    return regions.box(CODE)


def copdem_tiles(box):
    """Copernicus GLO-30 tile names covering the box. A tile is named by its south-west corner."""
    w, s, e, n = box
    out = []
    for lat in range(math.floor(s), math.ceil(n)):
        for lon in range(math.floor(w), math.ceil(e)):
            out.append('Copernicus_DSM_COG_10_%s%02d_00_%s%03d_00_DEM' % ('N' if lat >= 0 else 'S', abs(lat), 'E' if lon >= 0 else 'W', abs(lon)))
    return out


def copdem_cell(name):
    """(top latitude, left longitude) of a GLO-30 tile, the key tools/build_terrain.py uses for a 1° cell."""
    p = name.split('_')
    lat = int(p[4][1:]) * (1 if p[4][0] == 'N' else -1)
    lon = int(p[6][1:]) * (1 if p[6][0] == 'E' else -1)
    return lat + 1, lon


def worldcover_tiles(box):
    """ESA WorldCover 2021 tile names covering the box. Tiles are 3° square, named by their south-west corner."""
    w, s, e, n = box
    out = []
    for lat in range(math.floor(s / 3) * 3, math.ceil(n / 3) * 3, 3):
        for lon in range(math.floor(w / 3) * 3, math.ceil(e / 3) * 3, 3):
            out.append('ESA_WorldCover_10m_2021_v200_%s%02d%s%03d_Map' % ('N' if lat >= 0 else 'S', abs(lat), 'E' if lon >= 0 else 'W', abs(lon)))
    return out


def worldcover_corner(name):
    """(west, north) of a WorldCover tile."""
    c = name.split('_')[5]
    lat = int(c[1:3]) * (1 if c[0] == 'N' else -1)
    lon = int(c[4:7]) * (1 if c[3] == 'E' else -1)
    return lon, lat + 3


def quadkey_box(qk):
    """(w, s, e, n) of a Bing quadkey tile (Microsoft's building files are cut by quadkey)."""
    x = y = 0
    for ch in qk:
        d = int(ch)
        x, y = x * 2 + (d & 1), y * 2 + (d >> 1)
    n = 2 ** len(qk)

    def lat(t):
        return math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * t / n))))
    return x / n * 360 - 180, lat(y + 1), (x + 1) / n * 360 - 180, lat(y)


def overlaps(a, b):
    return a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]


def tile_range(box, z):
    """The z tiles (x0, x1, y0, y1) covering the box, as packaging/build_packs.py tile_range."""
    n = 2 ** z

    def merc(lat):
        return (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return int((box[0] + 180) / 360 * n), int((box[2] + 180) / 360 * n), int(merc(box[3])), int(merc(box[1]))


def supertiles(cells, box):
    """z8 supertiles (x, y) for the 1° terrain cells (top, left), limited to the box (as build_terrain.main)."""
    w, s, e, n = box
    keys = set()
    for top, left in cells:
        if left + 1 < w or left > e or top < s or top - 1 > n:
            continue
        x0, x1, y0, y1 = tile_range((max(left, w), max(top - 1, s), min(left + 1, e) - 1e-9, min(top, n) - 1e-9), 8)
        keys |= {(x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)}
    return sorted(keys, key=lambda k: (k[1] // 2, k[0], k[1]))


def place_zoom(cls, population=None):
    z = PLACE_Z.get(cls, EXTRA_PLACE_Z.get(cls, 14))
    try:
        if cls in ('city', 'town') and population and int(population) > 300000:
            z = 5
    except (TypeError, ValueError):
        pass
    return z


def water_layer(fclass):
    """OSM water area class -> (layer, cls) in water.sqlite feat, matching the NHD layers of tools/build_water.py."""
    if fclass.startswith('wetland'):
        return 'wet', 'wet'
    if fclass == 'reservoir':
        return 'water', 'reservoir'
    if fclass == 'river':
        return 'water', 'river'
    return 'water', 'water'


def water_point_kind(fclass, named, area_km2):
    """Clickable point for a water area, or None: named lakes and reservoirs, and unnamed ones of about an acre or more."""
    if fclass not in ('water', 'reservoir'):
        return None
    if not named and area_km2 < 0.004:
        return None
    if fclass == 'reservoir':
        return 'reservoir'
    return 'pond' if not named and area_km2 < 0.04 else 'lake'


def water_minz(area_km2):
    """Zoom at which an outline appears, as tools/build_water.py."""
    return max(5, min(14, round(14 - math.log2(max(area_km2, 1e-5) ** 0.5 / 0.02))))


def crop_lut():
    """uint8 lookup: WorldCover code -> 1-based index into WORLDCOVER's codes (0 = not kept)."""
    lut = bytearray(256)
    for i, c in enumerate(sorted(WORLDCOVER), 1):
        lut[c] = i
    return bytes(lut)


def acres_per_px(lat, deg):
    """Acres covered by one square pixel of `deg` degrees at this latitude."""
    return (deg * 111320 * math.cos(math.radians(lat))) * (deg * 110574) / 4046.86


# ----------------------------------------------------------- download ----
def fetch(url, dest, quiet=False):
    """Download once; a finished file is kept, a partial one is started again."""
    dest = Path(dest)
    if dest.exists() and dest.stat().st_size:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + '.part')
    req = urllib.request.Request(url, headers={'User-Agent': 'lastbook-map-build'})
    try:
        with urllib.request.urlopen(req, timeout=120) as r, open(tmp, 'wb') as f:
            while True:
                b = r.read(1 << 20)
                if not b:
                    break
                f.write(b)
    except urllib.error.HTTPError as err:
        tmp.unlink(missing_ok=True)
        if err.code in (403, 404):
            return None             # no tile there (open ocean)
        raise
    os.replace(tmp, dest)
    if not quiet:
        print(f'  {dest.relative_to(HERE) if dest.is_relative_to(HERE) else dest}: {dest.stat().st_size:,} bytes', flush=True)
    return dest


def osm_gpkg():
    z = fetch(OSM_URL, SRC / 'osm/guyana-latest-free.gpkg.zip')
    gpkg = SRC / 'osm/guyana.gpkg'
    if not gpkg.exists() or gpkg.stat().st_mtime < z.stat().st_mtime:
        with zipfile.ZipFile(z) as zf:
            member = next(m for m in zf.namelist() if m.endswith('.gpkg'))
            with zf.open(member) as src, open(str(gpkg) + '.part', 'wb') as dst:
                while True:
                    b = src.read(1 << 20)
                    if not b:
                        break
                    dst.write(b)
        os.replace(str(gpkg) + '.part', gpkg)
    return gpkg


def ocha_dir():
    z = fetch(OCHA_URL, SRC / 'ocha/guy_admbnd_2021_shp.zip')
    d = SRC / 'ocha/shp'
    if not (d / 'guy_admbnd_adm2_2021.shp').exists():
        with zipfile.ZipFile(z) as zf:
            for m in zf.namelist():
                if m.startswith('guy_admbnd_adm') and not m.endswith('/'):
                    zf.extract(m, d)
    return d


def ms_links(box):
    """(quadkey, url) of Microsoft's Guyana building files that meet the box."""
    import csv
    path = fetch(MSB_LINKS, SRC / 'msbuildings/dataset-links.csv')
    out = []
    with open(path, encoding='utf-8') as f:
        for r in csv.DictReader(f):
            if r['Location'] == MSB_LOCATION and overlaps(quadkey_box(r['QuadKey']), box):
                out.append((r['QuadKey'], r['Url']))
    return sorted(out)


def fetch_layers(layers, box):
    if {'streets', 'places', 'water'} & set(layers):
        osm_gpkg()
    if 'places' in layers:
        ocha_dir()
    if 'terrain' in layers:
        for name in copdem_tiles(box):
            fetch(COPDEM_URL.format(name=name), SRC / f'copdem/{name}.tif')
    if 'crops' in layers:
        for name in worldcover_tiles(box):
            fetch(WORLDCOVER_URL.format(name=name), SRC / f'worldcover/{name}.tif')
    if 'buildings' in layers:
        for qk, url in ms_links(box):
            fetch(url, SRC / f'msbuildings/{qk}.csv.gz')


# --------------------------------------------------------- geometries ----
def gpkg_parts(g):
    """GeoPackage geometry -> list of parts as flat [x, y, ...] lists (polygons give their rings), as tools/build_map.py."""
    flags = g[3]
    off = 8 + {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}[(flags >> 1) & 7]
    return _wkb_parts(g, off)[0]


def _wkb_parts(b, o):
    e = '<' if b[o] == 1 else '>'
    t = struct.unpack_from(e + 'I', b, o + 1)[0] % 1000
    o += 5
    if t == 1:
        x, y = struct.unpack_from(e + 'dd', b, o)
        return [[x, y]], o + 16
    if t == 2:
        n = struct.unpack_from(e + 'I', b, o)[0]
        return [list(struct.unpack_from(e + '%dd' % (2 * n), b, o + 4))], o + 4 + 16 * n
    if t == 3:
        nr = struct.unpack_from(e + 'I', b, o)[0]
        o += 4
        parts = []
        for _ in range(nr):
            n = struct.unpack_from(e + 'I', b, o)[0]
            parts.append(list(struct.unpack_from(e + '%dd' % (2 * n), b, o + 4)))
            o += 4 + 16 * n
        return parts, o
    if t in (4, 5, 6, 7):
        n = struct.unpack_from(e + 'I', b, o)[0]
        o += 4
        parts = []
        for _ in range(n):
            p, o = _wkb_parts(b, o)
            parts.extend(p)
        return parts, o
    raise ValueError('geometry type %d' % t)


def thin(flat, tol):
    """Drop points closer than tol (degrees) to the last kept one; keeps the ends (tools/build_map.py simplify)."""
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


def pack_flat(parts):
    """int32: nparts, then per part npts and lon/lat * 1e6 deltas: the feat.geom format of every map file."""
    a = array('i', [len(parts)])
    for p in parts:
        n = len(p) // 2
        a.append(n)
        lx = ly = 0
        for i in range(n):
            x, y = int(round(p[2 * i] * 1e6)), int(round(p[2 * i + 1] * 1e6))
            a.append(x - lx); a.append(y - ly)
            lx, ly = x, y
    return a.tobytes()


def flat_bbox(parts):
    xs = [v for p in parts for v in p[0::2]]
    ys = [v for p in parts for v in p[1::2]]
    return min(xs), max(xs), min(ys), max(ys)


def area_z(minx, maxx, miny, maxy, base):
    size = max(maxx - minx, maxy - miny)
    if size <= 0:
        return 17
    return max(base, min(16, int(math.log2(360 / size)) - 4))


def in_box(bb, box):
    """bb = (minx, maxx, miny, maxy)."""
    return bb[1] >= box[0] and bb[0] <= box[2] and bb[3] >= box[1] and bb[2] <= box[3]


def ring_points(flat):
    return list(zip(flat[0::2], flat[1::2]))


def ring_area_km2(r):
    s = 0
    for (x1, y1), (x2, y2) in zip(r, r[1:] + r[:1]):
        s += (x2 - x1) * (y2 + y1)
    lat = sum(y for _, y in r) / len(r)
    return abs(s) / 2 * 111.32 ** 2 * math.cos(math.radians(lat))


def inside_point(ring):
    """A point inside the ring (tools/build_water.py inside_point)."""
    ys = [y for _, y in ring]
    y0, y1 = min(ys), max(ys)
    best = None
    for f in (0.5, 0.35, 0.65, 0.2, 0.8):
        y = y0 + (y1 - y0) * f
        xs = sorted(x1 + (y - ya) * (x2 - x1) / (yb - ya) for (x1, ya), (x2, yb) in zip(ring, ring[1:] + ring[:1])
                    if (ya <= y < yb) or (yb <= y < ya))
        for a, b in zip(xs[0::2], xs[1::2]):
            if best is None or b - a > best[0]:
                best = (b - a, (a + b) / 2, y)
    return (best[1], best[2]) if best else (sum(x for x, _ in ring) / len(ring), sum(ys) / len(ring))


def read_dbf(path):
    b = Path(path).read_bytes()
    n, hl, rl = struct.unpack_from('<IHH', b, 4)
    fields, o = [], 32
    while b[o] != 0x0D:
        fields.append((b[o:o + 11].split(b'\0')[0].decode('ascii'), b[o + 16]))
        o += 32
    rows = []
    for i in range(n):
        r = b[hl + i * rl:hl + (i + 1) * rl]
        j, d = 1, {}
        for name, ln in fields:
            d[name] = r[j:j + ln].decode('utf-8', 'replace').strip()
            j += ln
        rows.append(d)
    return rows


def read_shp_polygons(path):
    """Polygon shapefile -> list of rings per record, each ring a list of (lon, lat)."""
    b = Path(path).read_bytes()
    out, o = [], 100
    while o < len(b):
        _, clen = struct.unpack_from('>ii', b, o)
        o += 8
        end = o + clen * 2
        st = struct.unpack_from('<i', b, o)[0]
        rings = []
        if st in (5, 15, 25):
            nparts, npts = struct.unpack_from('<ii', b, o + 36)
            starts = list(struct.unpack_from(f'<{nparts}i', b, o + 44)) + [npts]
            p0 = o + 44 + 4 * nparts
            xy = struct.unpack_from(f'<{2 * npts}d', b, p0)
            pts = list(zip(xy[0::2], xy[1::2]))
            rings = [pts[a:z] for a, z in zip(starts, starts[1:])]
        out.append(rings)
        o = end
    return out


# --------------------------------------------------------------- files ----
NATIONAL_SQL = '''CREATE TABLE IF NOT EXISTS feat(id INTEGER PRIMARY KEY, layer TEXT, cls TEXT, name TEXT, minz INTEGER, geom BLOB);
  CREATE VIRTUAL TABLE IF NOT EXISTS feat_idx USING rtree(id, minx, maxx, miny, maxy, minz, maxz);
  CREATE TABLE IF NOT EXISTS poi(id INTEGER PRIMARY KEY, cls TEXT, name TEXT, lon REAL, lat REAL);
  CREATE INDEX IF NOT EXISTS poi_cls ON poi(cls, lon, lat);
  CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);'''
WATER_SQL = '''CREATE TABLE IF NOT EXISTS resource(id INTEGER PRIMARY KEY, source_id TEXT, kind TEXT, name TEXT, lat REAL, lon REAL, detail TEXT, source TEXT, origin TEXT);
  CREATE INDEX IF NOT EXISTS resource_kind ON resource(kind);
  CREATE INDEX IF NOT EXISTS resource_origin ON resource(origin);
  CREATE VIRTUAL TABLE IF NOT EXISTS spatial USING rtree(id, minx, maxx, miny, maxy);
  CREATE TABLE IF NOT EXISTS feat(id INTEGER PRIMARY KEY, layer TEXT, cls TEXT, name TEXT, minz INTEGER, geom BLOB, origin TEXT);
  CREATE INDEX IF NOT EXISTS feat_origin ON feat(origin);
  CREATE VIRTUAL TABLE IF NOT EXISTS feat_idx USING rtree(id, minx, maxx, miny, maxy, minz, maxz);
  CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
  CREATE TABLE IF NOT EXISTS nhd_seen(pid TEXT PRIMARY KEY, origin TEXT);
  CREATE VIRTUAL TABLE IF NOT EXISTS water_fts USING fts5(name, other, tokenize="unicode61");'''
TERRAIN_SQL = '''CREATE TABLE IF NOT EXISTS tile(z INT, x INT, y INT, png BLOB, PRIMARY KEY(z,x,y)) WITHOUT ROWID;
  CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);'''
CROPS_SQL = '''CREATE TABLE IF NOT EXISTS resource(id INTEGER PRIMARY KEY, source_id TEXT, kind TEXT, name TEXT, lat REAL, lon REAL, detail TEXT, source TEXT);
  CREATE INDEX IF NOT EXISTS resource_kind ON resource(kind);
  CREATE VIRTUAL TABLE IF NOT EXISTS spatial USING rtree(id, minx, maxx, miny, maxy);
  CREATE TABLE IF NOT EXISTS tile(z INT, x INT, y INT, png BLOB, PRIMARY KEY(z,x,y)) WITHOUT ROWID;
  CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);'''
BUILDINGS_SQL = '''CREATE TABLE IF NOT EXISTS bldg(x INT, y INT, part INT, n INT, data BLOB, PRIMARY KEY(x,y,part)) WITHOUT ROWID;
  CREATE TABLE IF NOT EXISTS bldg_socal(x INT, y INT, part INT, n INT, data BLOB, PRIMARY KEY(x,y,part)) WITHOUT ROWID;
  CREATE TABLE IF NOT EXISTS bldg_osm(x INT, y INT, n INT, data BLOB, PRIMARY KEY(x,y)) WITHOUT ROWID;
  CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);'''
PLACES_SQL = '''CREATE TABLE IF NOT EXISTS place(id INTEGER PRIMARY KEY, name TEXT, kind TEXT, detail TEXT, lat REAL, lon REAL, rank INTEGER, source TEXT);
  CREATE VIRTUAL TABLE IF NOT EXISTS place_fts USING fts5(name, detail, content='place', content_rowid='id', tokenize='unicode61');'''
SCHEMA = {'national': NATIONAL_SQL, 'water': WATER_SQL, 'terrain': TERRAIN_SQL, 'crops': CROPS_SQL,
          'buildings': BUILDINGS_SQL, 'places': PLACES_SQL}


def fresh(name):
    """An empty region file with the US tables."""
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f'{name}.sqlite'
    for p in (path, Path(str(path) + '-wal'), Path(str(path) + '-shm'), Path(str(path) + '-journal')):
        p.unlink(missing_ok=True)
    db = sqlite3.connect(path)
    db.executescript('PRAGMA journal_mode=DELETE; PRAGMA synchronous=OFF;' + SCHEMA[name])
    return db


def stamp(db, key, value):
    db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', (key, value if isinstance(value, str) else json.dumps(value)))


def osm_as_of(gpkg):
    """The 'data as of' line Geofabrik writes in the README beside the GeoPackage, or ''."""
    readme = gpkg.parent / 'guyana-latest-free.gpkg.zip'
    try:
        with zipfile.ZipFile(readme) as zf:
            text = zf.read('README').decode('utf-8', 'replace')
        line = next(l for l in text.splitlines() if 'as of' in l)
        return line.split('as of', 1)[1].strip()
    except (OSError, KeyError, StopIteration, zipfile.BadZipFile):
        return ''


def each(src, table, cols='fclass,name'):
    for row in src.execute(f'SELECT geom,{cols} FROM {table}'):
        if row[0] is None:
            continue
        try:
            yield gpkg_parts(row[0]), row[1:]
        except (ValueError, struct.error):
            continue


# ------------------------------------------------------------- streets ----
def build_streets(box):
    """national.sqlite: roads, land, waterways, place labels and help points, as tools/build_map.py writes them."""
    gpkg = osm_gpkg()
    src = sqlite3.connect(f'file:{gpkg}?mode=ro', uri=True)
    db = fresh('national')
    fid = [0]

    def add(layer, cls, name, minz, parts):
        parts = [p for p in parts if len(p) >= 2]
        if not parts:
            return
        bb = flat_bbox(parts)
        if not in_box(bb, box):
            return
        fid[0] += 1
        db.execute('INSERT INTO feat VALUES (?,?,?,?,?,?)', (fid[0], layer, cls, name, minz, pack_flat(parts)))
        db.execute('INSERT INTO feat_idx VALUES (?,?,?,?,?,?,?)', (fid[0], *bb, minz, 30))

    for parts, (cls, name) in each(src, 'gis_osm_natural_a_free'):
        if cls == 'beach':
            add('beach', cls, name, area_z(*flat_bbox(parts), 10), parts)
    for parts, (cls, name) in each(src, 'gis_osm_landuse_a_free'):
        k = LANDUSE_KEEP.get(cls)
        if k:
            add('land', k, name, area_z(*flat_bbox(parts), 9), [thin(p, 0.00001) for p in parts])
    for parts, (cls,) in each(src, 'gis_osm_protected_areas_a_free', 'fclass'):
        add('land', 'park', None, area_z(*flat_bbox(parts), 8), [thin(p, 0.00002) for p in parts])
    for parts, (cls, name) in each(src, 'gis_osm_waterways_free'):
        add('waterway', cls, name, 10 if cls == 'river' else 13, parts)
    for parts, (cls, name) in each(src, 'gis_osm_railways_free'):
        add('rail', cls, name, 10 if cls == 'rail' else 13, parts)
    for parts, (cls, name, ref) in each(src, 'gis_osm_roads_free', 'fclass,name,ref'):
        add('road', cls, name or ref, ROAD_Z.get(cls, 15), parts)
    for parts, (cls, pop, name) in each(src, 'gis_osm_places_free', 'fclass,population,name'):
        if name:
            add('place', PLACE_CLS.get(cls, cls), name, place_zoom(cls, pop), parts)
    pid = 0
    for table in ('gis_osm_pois_free', 'gis_osm_pois_a_free', 'gis_osm_natural_free', 'gis_osm_natural_a_free'):
        for parts, (cls, name) in each(src, table):
            if cls not in POI_KEEP or (table == 'gis_osm_natural_free' and cls != 'spring'):
                continue
            minx, maxx, miny, maxy = flat_bbox(parts)
            lon, lat = (minx + maxx) / 2, (miny + maxy) / 2
            if not in_box((lon, lon, lat, lat), box):
                continue
            pid += 1
            db.execute('INSERT INTO poi VALUES (?,?,?,?,?)', (pid, cls, name, lon, lat))
    stamp(db, 'source', OSM_SOURCE)
    stamp(db, 'data_as_of', osm_as_of(gpkg))
    stamp(db, 'bounds', ','.join(f'{v:.2f}' for v in box))
    stamp(db, 'built', time.strftime('%Y-%m-%dT%H:%M:%S'))
    stamp(db, 'status', {'state': 'complete', 'stage': 'ready', 'features': fid[0]})
    db.commit()
    print(f'streets: {fid[0]:,} features, {pid:,} help points', flush=True)


# -------------------------------------------------------------- places ----
def build_places(box):
    """places.sqlite: OSM places and named help points, OCHA regions and sub-regions."""
    gpkg = osm_gpkg()
    src = sqlite3.connect(f'file:{gpkg}?mode=ro', uri=True)
    db = fresh('places')
    ins = 'INSERT INTO place(name,kind,detail,lat,lon,rank,source) VALUES (?,?,?,?,?,?,?)'
    n = 0

    def inside(lon, lat):
        return box[0] <= lon <= box[2] and box[1] <= lat <= box[3]
    for parts, (cls, name) in each(src, 'gis_osm_places_free'):
        x, y = parts[0][0], parts[0][1]
        if name and inside(x, y):
            db.execute(ins, (name, cls.replace('_', ' '), f'{DETAIL} (OpenStreetMap)', y, x, 1, 'OpenStreetMap'))
            n += 1
    for table in ('gis_osm_pois_free', 'gis_osm_pois_a_free'):
        for parts, (cls, name) in each(src, table):
            if not name or cls not in POI_KEEP:
                continue
            minx, maxx, miny, maxy = flat_bbox(parts)
            x, y = (minx + maxx) / 2, (miny + maxy) / 2
            if inside(x, y):
                db.execute(ins, (name, cls.replace('_', ' '), f'{DETAIL} (OpenStreetMap)', y, x, 4, 'OpenStreetMap'))
                n += 1
    shp = ocha_dir()
    for level, kind, name_key in ((1, 'region', 'ADM1_EN'), (2, 'sub-region', 'ADM2_EN')):
        base = shp / f'guy_admbnd_adm{level}_2021'
        for rec, rings in zip(read_dbf(f'{base}.dbf'), read_shp_polygons(f'{base}.shp')):
            if not rings:
                continue
            x, y = inside_point(max(rings, key=len))
            if not inside(x, y):
                continue
            detail = DETAIL if level == 1 else f"{rec['ADM1_EN']}, {DETAIL}"
            db.execute(ins, (rec[name_key], kind, detail, y, x, 2, 'OCHA'))
            n += 1
    db.execute("INSERT INTO place_fts(place_fts) VALUES ('rebuild')")
    db.commit()
    print(f'places: {n:,}', flush=True)


# --------------------------------------------------------------- water ----
def build_water(box):
    """water.sqlite: OSM water outlines and clickable lakes and reservoirs, as tools/build_water.py does for NHD."""
    import build_water as W
    gpkg = osm_gpkg()
    src = sqlite3.connect(f'file:{gpkg}?mode=ro', uri=True)
    db = fresh('water')
    origin = f'osm:{CODE}'
    n = pts = 0
    for osm_id, cls, name, blob in src.execute('SELECT osm_id,fclass,name,geom FROM gis_osm_water_a_free'):
        if blob is None:
            continue
        try:
            polys = W.wkb_polys(blob)
        except (ValueError, struct.error, KeyError):
            continue
        polys = [p for p in polys if p and len(p[0]) >= 4]
        if not polys:
            continue
        outer = max((p[0] for p in polys), key=len)
        xs = [x for x, _ in outer]; ys = [y for _, y in outer]
        if not in_box((min(xs), max(xs), min(ys), max(ys)), box):
            continue
        area = sum(W.ring_area_km2(p[0]) - sum(W.ring_area_km2(h) for h in p[1:]) for p in polys)
        layer, fcls = water_layer(cls or '')
        minz = water_minz(area)
        tol = 0.00002 if minz >= 12 else 0.00006 if minz >= 9 else 0.0002
        for poly in polys:
            rings = [r2 for r2 in (W.simplify(r, tol) for r in poly) if len(r2) >= 4]
            if not rings:
                continue
            rx = [x for x, _ in rings[0]]; ry = [y for _, y in rings[0]]
            cur = db.execute('INSERT INTO feat(layer,cls,name,minz,geom,origin) VALUES (?,?,?,?,?,?)', (layer, fcls, name or '', minz, W.pack(rings), origin))
            db.execute('INSERT INTO feat_idx VALUES (?,?,?,?,?,?,?)', (cur.lastrowid, min(rx), max(rx), min(ry), max(ry), minz, 30))
            n += 1
        kind = water_point_kind(cls or '', bool(name), area)
        if kind:
            lon, lat = W.inside_point(outer)
            detail = {'area_acres': round(area * 247.105, 1), 'state': DETAIL, 'source_map': 'OpenStreetMap'}
            cur = db.execute('INSERT INTO resource(source_id,kind,name,lat,lon,detail,source,origin) VALUES (?,?,?,?,?,?,?,?)',
                             (f'osm:{osm_id}', kind, name or '', lat, lon, json.dumps(detail, separators=(',', ':')), 'https://www.openstreetmap.org/', origin))
            db.execute('INSERT INTO spatial VALUES (?,?,?,?,?)', (cur.lastrowid, lon, lon, lat, lat))
            pts += 1
    water_index(db)
    stamp(db, origin, {'outlines': n, 'points': pts, 'built': time.strftime('%Y-%m-%dT%H:%M:%S')})
    db.commit()
    print(f'water: {n:,} outlines, {pts:,} points', flush=True)


def water_index(db):
    """The same full-text index as tools/build_water.py build_index."""
    db.executescript('DROP TABLE IF EXISTS water_fts; CREATE VIRTUAL TABLE water_fts USING fts5(name, other, tokenize="unicode61");')
    db.execute("INSERT INTO water_fts(rowid,name,other) SELECT id,name,COALESCE(json_extract(detail,'$.other_names'),'') FROM resource "
               "WHERE kind IN ('dam','reservoir','lake') AND name!=''")


# ------------------------------------------------------------- terrain ----
def _terrain_init(cells):
    import build_terrain as T
    T.CELLS = cells


def _terrain_job(key):
    import build_terrain as T
    tiles, h = T.supertile(key)
    return tiles, h, key


def build_terrain(box, workers):
    """terrain.sqlite: z4-12 terrain-RGB tiles, by tools/build_terrain.py's own tiling, from GLO-30 instead of 3DEP."""
    import numpy as np
    import build_terrain as T
    cells = {}
    for name in copdem_tiles(box):
        p = SRC / f'copdem/{name}.tif'
        if p.exists():
            cells[copdem_cell(name)] = str(p)
    if not cells:
        sys.exit('terrain: no GLO-30 tiles downloaded; run fetch terrain first')
    keys = supertiles(cells, box)
    db = fresh('terrain')
    t0, ntiles, low = time.time(), 0, {}
    with ProcessPoolExecutor(workers, initializer=_terrain_init, initargs=(cells,)) as pool:
        for i, f in enumerate(as_completed([pool.submit(_terrain_job, k) for k in keys]), 1):
            tiles, h8, key = f.result()
            db.executemany('INSERT OR REPLACE INTO tile VALUES (?,?,?,?)', tiles)
            ntiles += len(tiles)
            if h8 is not None:
                low[key] = h8
            if i % 10 == 0:
                db.commit()
                print(f'terrain: {i}/{len(keys)} supertiles, {ntiles:,} tiles, {time.time() - t0:.0f}s', flush=True)
    level = low
    for z in range(T.SUPERZ - 1, T.MINZ - 1, -1):
        nxt = {}
        for (x, y) in {(x // 2, y // 2) for x, y in level}:
            q = np.full((512, 512), np.nan, np.float32)
            for dy in (0, 1):
                for dx in (0, 1):
                    h = level.get((2 * x + dx, 2 * y + dy))
                    if h is not None:
                        q[dy * 256:(dy + 1) * 256, dx * 256:(dx + 1) * 256] = h
            h = T.down(q)
            nxt[(x, y)] = h
            db.execute('INSERT OR REPLACE INTO tile VALUES (?,?,?,?)', (z, x, y, T.png(h)))
            ntiles += 1
        level = nxt
    stamp(db, 'built', time.strftime('%Y-%m-%dT%H:%M:%S'))
    stamp(db, 'source', DEM_SOURCE)
    db.commit()
    print(f'terrain: {len(keys)} supertiles, {ntiles:,} tiles in {time.time() - t0:.0f}s', flush=True)


# --------------------------------------------------------------- crops ----
def crop_tile_classes(cls, west, north, deg, x, y, z):
    """256 x 256 class indexes for web-mercator tile z/x/y, nearest pixel of a north-up raster in degrees."""
    import numpy as np
    nz = 2 ** z
    t = (np.arange(256) + 0.5) / 256
    lon = (x + t) / nz * 360 - 180
    lat = np.degrees(np.arctan(np.sinh(math.pi * (1 - 2 * (y + t) / nz))))
    cc = np.floor((lon - west) / deg).astype(int)
    rr = np.floor((north - lat) / deg).astype(int)
    R, C = np.meshgrid(rr, cc, indexing='ij')
    ok = (R >= 0) & (R < cls.shape[0]) & (C >= 0) & (C < cls.shape[1])
    v = np.zeros((256, 256), np.uint8)
    v[ok] = cls[R[ok], C[ok]]
    return v


def build_crops(box):
    """crops.sqlite: WorldCover cropland as clickable ~600 m cells and a colour overlay, as tools/build_crops.py writes."""
    import numpy as np
    import tifffile
    import build_crops as K
    codes = sorted(WORLDCOVER)
    lut = np.frombuffer(crop_lut(), np.uint8)
    palette = np.zeros((len(codes) + 1, 4), np.uint8)
    for i, c in enumerate(codes, 1):
        palette[i] = (*WORLDCOVER[c][2], 190)
    db = fresh('crops')
    alltiles, npts = {}, 0
    for name in worldcover_tiles(box):
        path = SRC / f'worldcover/{name}.tif'
        if not path.exists():
            continue
        t0 = time.time()
        with tifffile.TiffFile(path) as tf:
            levels = tf.series[0].levels
            a = levels[min(WC_LEVEL, len(levels) - 1)].asarray()
        west, north = worldcover_corner(name)
        deg = 3 / a.shape[1]
        # keep only the box
        r0 = max(0, int((north - box[3]) / deg)); r1 = min(a.shape[0], int(math.ceil((north - box[1]) / deg)))
        c0 = max(0, int((box[0] - west) / deg)); c1 = min(a.shape[1], int(math.ceil((box[2] - west) / deg)))
        if r0 >= r1 or c0 >= c1:
            continue
        cls = np.zeros(a.shape, np.uint8)
        cls[r0:r1, c0:c1] = lut[a[r0:r1, c0:c1]]
        del a
        rows, cols = np.nonzero(cls)
        if not rows.size:
            print(f'{name}: no cropland in the box', flush=True)
            continue
        br, bc = rows // CROP_BLOCK, cols // CROP_BLOCK
        cell, count = np.unique(br.astype(np.int64) * 100000 + bc, return_counts=True)
        keep = count >= 20
        cell, count = cell[keep], count[keep]
        for cl, m in zip(cell.tolist(), count.tolist()):
            lat = north - ((cl // 100000) * CROP_BLOCK + CROP_BLOCK / 2) * deg
            lon = west + ((cl % 100000) * CROP_BLOCK + CROP_BLOCK / 2) * deg
            crop, kind, _ = WORLDCOVER[codes[0]]
            acres = round(m * acres_per_px(lat, deg), 1)
            cur = db.execute('INSERT INTO resource(source_id,kind,name,lat,lon,detail,source) VALUES (?,?,?,?,?,?,?)',
                             (f'{CODE}:{name}:{cl}', kind, crop, lat, lon,
                              json.dumps({'crop': crop, 'crop_acres': acres, 'year': 2021, 'land_cover': 'ESA WorldCover'}),
                              'https://esa-worldcover.org/'))
            db.execute('INSERT INTO spatial VALUES (?,?,?,?,?)', (cur.lastrowid, lon, lon, lat, lat))
            npts += 1
        # overlay: every z13 tile touched by a cropland pixel
        nz = 2 ** CROP_MAXZ
        plon = west + (cols[::7] + .5) * deg
        plat = north - (rows[::7] + .5) * deg
        tx = ((plon + 180) / 360 * nz).astype(int)
        ty = ((1 - np.log(np.tan(np.radians(plat)) + 1 / np.cos(np.radians(plat))) / math.pi) / 2 * nz).astype(int)
        ntile = 0
        for x_, y_ in set(zip(tx.tolist(), ty.tolist())):
            v = crop_tile_classes(cls, west, north, deg, x_, y_, CROP_MAXZ)
            if v.any():
                alltiles[(x_, y_)] = v if (x_, y_) not in alltiles else np.where(alltiles[(x_, y_)] > 0, alltiles[(x_, y_)], v)
                ntile += 1
        db.commit()
        print(f'{name}: {len(cell):,} cells, {ntile:,} tiles, {time.time() - t0:.0f}s', flush=True)
    level = alltiles
    for z in range(CROP_MAXZ, CROP_MINZ - 1, -1):
        for (x, y), v in level.items():
            db.execute('INSERT OR REPLACE INTO tile VALUES (?,?,?,?)', (z, x, y, K.png_rgba(palette[v])))
        if z > CROP_MINZ:
            nxt = {}
            for (x, y) in {(x // 2, y // 2) for x, y in level}:
                q = np.zeros((512, 512), np.uint8)
                for dy in (0, 1):
                    for dx in (0, 1):
                        v = level.get((2 * x + dx, 2 * y + dy))
                        if v is not None:
                            q[dy * 256:(dy + 1) * 256, dx * 256:(dx + 1) * 256] = v
                nxt[(x, y)] = K.down(q)
            level = nxt
    stamp(db, 'built', {'cells': npts, 'year': 2021, 'source': WC_SOURCE, 'at': time.strftime('%Y-%m-%dT%H:%M:%S')})
    db.commit()
    print(f'crops: {npts:,} clickable cells, {len(alltiles):,} detailed tiles', flush=True)


# ----------------------------------------------------------- buildings ----
def build_buildings(box):
    """buildings.sqlite: Microsoft footprints in tools/build_buildings.py's z14 buckets, cut to the box."""
    import build_buildings as B
    db = fresh('buildings')
    x0, x1, y0, y1 = tile_range(box, 14)
    total = 0
    for i, (qk, _) in enumerate(ms_links(box)):
        path = SRC / f'msbuildings/{qk}.csv.gz'
        if not path.exists():
            continue
        rows, n, _, _ = B.convert((PART_BASE + i, path, False))
        rows = [r for r in rows if x0 <= r[0] <= x1 and y0 <= r[1] <= y1]
        db.executemany('INSERT OR REPLACE INTO bldg VALUES (?,?,?,?,?)', rows)
        kept = sum(r[3] for r in rows)
        total += kept
        print(f'buildings {qk}: {kept:,} kept of {n:,}', flush=True)
    stamp(db, 'buildings', str(total))
    stamp(db, 'built', time.strftime('%Y-%m-%dT%H:%M:%S'))
    stamp(db, 'source', MSB_SOURCE)
    db.commit()
    print(f'buildings: {total:,}', flush=True)


# --------------------------------------------------------------- merge ----
def png_pixels(png):
    """(width, height, channels, rows of bytes) of a PNG written by tools/build_terrain.py or build_crops.py (8-bit
    RGB or RGBA, filter None or Up), or None for any other PNG."""
    if png[:8] != b'\x89PNG\r\n\x1a\n':
        return None
    i, idat, w = 8, b'', None
    while i < len(png):
        n = struct.unpack('>I', png[i:i + 4])[0]
        typ, data = png[i + 4:i + 8], png[i + 8:i + 8 + n]
        if typ == b'IHDR':
            w, h, depth, colour = struct.unpack('>IIBB', data[:10])
            if depth != 8 or colour not in (2, 6):
                return None
            ch = 3 if colour == 2 else 4
        elif typ == b'IDAT':
            idat += data
        i += 12 + n
    if w is None:
        return None
    raw = zlib.decompress(idat)
    stride = w * ch
    rows, prev = [], bytearray(stride)
    for r in range(h):
        f, line = raw[r * (stride + 1)], bytearray(raw[r * (stride + 1) + 1:(r + 1) * (stride + 1)])
        if f == 2:
            line = bytearray((a + b) & 255 for a, b in zip(line, prev))
        elif f != 0:
            return None
        rows.append(line)
        prev = line
    return w, h, ch, rows


def png_write(w, h, ch, rows):
    raw = b''.join(b'\x00' + bytes(r) for r in rows)
    chunk = lambda t, d: struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2 if ch == 3 else 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b''))


SEA = bytes((0x01, 0x86, 0xa0))     # terrain-RGB of 0 m, what build_terrain.py writes where it has no data


def combine_tiles(old, new):
    """One tile from a tile already in a US file and the region's tile for the same place (a low-zoom tile can cover
    both): the region's pixels where it has data (terrain: not 0 m; crops: not clear), the old ones elsewhere."""
    a, b = png_pixels(old), png_pixels(new)
    if not a or not b or a[:3] != b[:3]:
        return new
    w, h, ch, ra = a
    rb = b[3]
    out = []
    for la, lb in zip(ra, rb):
        line = bytearray(lb)
        for k in range(0, w * ch, ch):
            px = lb[k:k + ch]
            empty = px == SEA if ch == 3 else px[3] == 0
            if empty:
                line[k:k + ch] = la[k:k + ch]
        out.append(line)
    return png_write(w, h, ch, out)


def merge_tiles(db):
    """Copy r.tile into tile, combining with any tile already there."""
    for z, x, y, png in db.execute('SELECT r.tile.z,r.tile.x,r.tile.y,r.tile.png FROM r.tile').fetchall():
        old = db.execute('SELECT png FROM main.tile WHERE z=? AND x=? AND y=?', (z, x, y)).fetchone()
        db.execute('INSERT OR REPLACE INTO main.tile VALUES (?,?,?,?)', (z, x, y, combine_tiles(old[0], png) if old and old[0] != png else png))


def target(name):
    """The US map file the region's rows go into, made with the region's tables when it does not exist yet."""
    path = GEO / f'{name}.sqlite'
    db = sqlite3.connect(path)
    db.executescript(SCHEMA[name] if not db.execute("SELECT 1 FROM sqlite_master WHERE name IN ('feat','tile','bldg','place','resource')").fetchone()
                     else 'CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);' if name != 'places' else '')
    return db


def merge(box):
    """Add the region files' rows to derived/geo/*.sqlite, replacing rows an earlier GY merge added, so that
    packaging/build_packs.py cuts the GY map set from the same files as a US state."""
    key = f'region:{CODE}'
    done = []
    for name in ('national', 'water', 'terrain', 'crops', 'buildings', 'places'):
        src = OUT / f'{name}.sqlite'
        if not src.exists():
            continue
        db = target(name)
        db.execute('ATTACH DATABASE ? AS r', (str(src),))
        if name == 'national':
            old = db.execute('SELECT value FROM meta WHERE key=?', (key,)).fetchone()
            if old:
                ids = json.loads(old[0])
                if ids.get('feat'):
                    db.execute('DELETE FROM feat_idx WHERE id BETWEEN ? AND ?', ids['feat'])
                    db.execute('DELETE FROM feat WHERE id BETWEEN ? AND ?', ids['feat'])
                if ids.get('poi'):
                    db.execute('DELETE FROM poi WHERE id BETWEEN ? AND ?', ids['poi'])
            ids = {}
            f0 = (db.execute('SELECT max(id) FROM feat').fetchone()[0] or 0) + 1
            db.execute('INSERT INTO feat(id,layer,cls,name,minz,geom) SELECT id+?,layer,cls,name,minz,geom FROM r.feat', (f0 - 1,))
            db.execute('INSERT INTO feat_idx SELECT id+?,minx,maxx,miny,maxy,minz,maxz FROM r.feat_idx', (f0 - 1,))
            nf = db.execute('SELECT count(*) FROM r.feat').fetchone()[0]
            if nf:
                ids['feat'] = [f0, f0 + nf - 1]
            p0 = (db.execute('SELECT max(id) FROM poi').fetchone()[0] or 0) + 1
            db.execute('INSERT INTO poi(id,cls,name,lon,lat) SELECT id+?,cls,name,lon,lat FROM r.poi', (p0 - 1,))
            np_ = db.execute('SELECT count(*) FROM r.poi').fetchone()[0]
            if np_:
                ids['poi'] = [p0, p0 + np_ - 1]
            stamp(db, key, ids)
            stamp(db, f'source:{CODE}', OSM_SOURCE)
            done.append(f'national: {nf:,} features, {np_:,} help points')
        elif name == 'water':
            origin = f'osm:{CODE}'
            db.execute('DELETE FROM spatial WHERE id IN (SELECT id FROM resource WHERE origin=?)', (origin,))
            db.execute('DELETE FROM resource WHERE origin=?', (origin,))
            db.execute('DELETE FROM feat_idx WHERE id IN (SELECT id FROM feat WHERE origin=?)', (origin,))
            db.execute('DELETE FROM feat WHERE origin=?', (origin,))
            for rid, *row in db.execute('SELECT id,source_id,kind,name,lat,lon,detail,source,origin FROM r.resource').fetchall():
                cur = db.execute('INSERT INTO resource(source_id,kind,name,lat,lon,detail,source,origin) VALUES (?,?,?,?,?,?,?,?)', row)
                db.execute('INSERT INTO spatial SELECT ?,minx,maxx,miny,maxy FROM r.spatial WHERE id=?', (cur.lastrowid, rid))
            for fid, *row in db.execute('SELECT id,layer,cls,name,minz,geom,origin FROM r.feat').fetchall():
                cur = db.execute('INSERT INTO feat(layer,cls,name,minz,geom,origin) VALUES (?,?,?,?,?,?)', row)
                db.execute('INSERT INTO feat_idx SELECT ?,minx,maxx,miny,maxy,minz,maxz FROM r.feat_idx WHERE id=?', (cur.lastrowid, fid))
            db.execute('INSERT OR REPLACE INTO meta SELECT * FROM r.meta WHERE key=?', (origin,))
            water_index(db)
            done.append('water: ' + db.execute('SELECT value FROM meta WHERE key=?', (origin,)).fetchone()[0])
        elif name == 'terrain':
            merge_tiles(db)
            stamp(db, f'source:{CODE}', DEM_SOURCE)
            done.append('terrain: %s tiles' % format(db.execute('SELECT count(*) FROM r.tile').fetchone()[0], ','))
        elif name == 'crops':
            db.execute("DELETE FROM spatial WHERE id IN (SELECT id FROM resource WHERE source_id LIKE ?)", (f'{CODE}:%',))
            db.execute("DELETE FROM resource WHERE source_id LIKE ?", (f'{CODE}:%',))
            for rid, *row in db.execute('SELECT id,source_id,kind,name,lat,lon,detail,source FROM r.resource').fetchall():
                cur = db.execute('INSERT INTO resource(source_id,kind,name,lat,lon,detail,source) VALUES (?,?,?,?,?,?,?)', row)
                db.execute('INSERT INTO spatial SELECT ?,minx,maxx,miny,maxy FROM r.spatial WHERE id=?', (cur.lastrowid, rid))
            merge_tiles(db)
            stamp(db, f'built:{CODE}', db.execute("SELECT value FROM r.meta WHERE key='built'").fetchone()[0])
            done.append('crops: %s cells' % format(db.execute('SELECT count(*) FROM r.resource').fetchone()[0], ','))
        elif name == 'buildings':
            db.execute('DELETE FROM bldg WHERE part BETWEEN ? AND ?', (PART_BASE, PART_BASE + 99999))
            db.execute('INSERT INTO bldg SELECT * FROM r.bldg')
            stamp(db, f'source:{CODE}', MSB_SOURCE)
            done.append('buildings: %s' % format(db.execute('SELECT coalesce(sum(n),0) FROM r.bldg').fetchone()[0], ','))
        elif name == 'places':
            w, s, e, n = box
            db.execute("DELETE FROM place WHERE source IN ('OpenStreetMap','OCHA') AND lon BETWEEN ? AND ? AND lat BETWEEN ? AND ?", (w, e, s, n))
            db.execute('INSERT INTO place(name,kind,detail,lat,lon,rank,source) SELECT name,kind,detail,lat,lon,rank,source FROM r.place')
            db.execute("INSERT INTO place_fts(place_fts) VALUES ('rebuild')")
            done.append('places: %s' % format(db.execute('SELECT count(*) FROM r.place').fetchone()[0], ','))
        db.commit()
        db.execute('DETACH DATABASE r')
        db.close()
    for line in done:
        print('merged', line, flush=True)
    if not done:
        sys.exit(f'nothing to merge: build first ({OUT.relative_to(HERE)} is empty)')


# ---------------------------------------------------------------- main ----
BUILD = {'streets': build_streets, 'places': build_places, 'water': build_water, 'crops': build_crops, 'buildings': build_buildings}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('step', choices=('fetch', 'build', 'merge', 'all'))
    ap.add_argument('layers', nargs='*', metavar='LAYER', help=' '.join(LAYERS) + ' (default: all)')
    ap.add_argument('--box', type=box_arg, help='W,S,E,N (default: Guyana with the 0.15° margin)')
    ap.add_argument('--workers', type=int, default=4)
    a = ap.parse_args(argv)
    box = a.box or default_box()
    layers = a.layers or list(LAYERS)
    unknown = [l for l in layers if l not in LAYERS]
    if unknown:
        ap.error(f'unknown layer {", ".join(unknown)}; choose from {" ".join(LAYERS)}')
    print(f'{CODE}: box {", ".join(f"{v:.4f}" for v in box)}; layers {" ".join(layers)}', flush=True)
    if a.step in ('fetch', 'build', 'all'):     # a file already downloaded is not fetched again
        fetch_layers(layers, box)
    if a.step in ('build', 'all'):
        for layer in layers:
            if layer == 'terrain':
                build_terrain(box, a.workers)
            else:
                BUILD[layer](box)
    if a.step in ('merge', 'all'):
        merge(box)


if __name__ == '__main__':
    main()
