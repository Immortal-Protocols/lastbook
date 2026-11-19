#!/usr/bin/env python3
"""Streaming OSM -> native Lastbook. Output directory must be NEW. Never publishes.
Build-only dependency: osmium==4.3.2 (BSD-2-Clause). No runtime dependency.
Reads an existing extract; does not download, install, or replace any data.
Requires an explicit memory-backed or file-backed sparse node index choice.
Multipolygons (all outer AND inner rings) assembled by libosmium's two-pass reader.
"""

import argparse, collections, datetime, errno, hashlib, json, math, os, re, resource, shutil, sqlite3, struct, time
from contextlib import contextmanager
from pathlib import Path
from importlib.metadata import version

try:
    import osmium
except ImportError:
    osmium = None

Handler = osmium.SimpleHandler if osmium else object
Q = 1_000_000
GIB = 1024**3


def disk_preflight(source, parent, node_index, minimum_gib=None):
    """Check build headroom, not a promise that a compressed input has a fixed ratio."""
    factor = 8 if node_index == 'sparse_file_array' else 5
    required = max(GIB, source.stat().st_size * factor)
    if minimum_gib is not None:
        if not math.isfinite(minimum_gib) or minimum_gib <= 0:
            raise ValueError('--min-free-gib must be a finite positive number')
        required = max(required, math.ceil(minimum_gib * GIB))
    free = shutil.disk_usage(parent).free
    if free < required:
        raise ValueError(
            f'Insufficient output/SQLite temporary disk space: need at least {required / GIB:.1f} GiB free; '
            f'{free / GIB:.1f} GiB available. Use another output filesystem; no staging directory created.'
        )
    return required


@contextmanager
def sqlite_scratch(out):
    """Own SQLite spill files before opening either database; restore caller env."""
    scratch = (out / 'sqlite-tmp').resolve()
    scratch.mkdir(mode=0o700)
    previous = {key: os.environ.get(key) for key in ('SQLITE_TMPDIR', 'TMPDIR')}
    try:
        for key in previous:
            os.environ[key] = str(scratch)
        yield scratch
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def storage_error(error, out):
    code = getattr(error, 'sqlite_errorcode', None)
    if (
        getattr(error, 'errno', None) == errno.ENOSPC
        or code == sqlite3.SQLITE_FULL
        or 'No space left' in str(error)
    ):
        return f'Output/SQLite temporary disk space exhausted. Free space on the filesystem holding {out}/sqlite-tmp and retry in a NEW staging directory.'
    if isinstance(error, sqlite3.Error):
        return f'SQLite build failed ({error}); check free space and write access for {out}/sqlite-tmp. Staging retained; nothing installed.'
    return f'Build failed ({error}); staging retained; nothing installed.'


ROAD_Z = {
    'motorway': 5,
    'trunk': 6,
    'motorway_link': 10,
    'trunk_link': 10,
    'primary': 8,
    'primary_link': 12,
    'secondary': 10,
    'secondary_link': 13,
    'tertiary': 11,
    'tertiary_link': 13,
    'residential': 13,
    'unclassified': 13,
    'living_street': 14,
    'pedestrian': 14,
    'busway': 14,
    'service': 15,
    'track': 13,
    'footway': 15,
    'path': 14,
    'cycleway': 14,
    'steps': 16,
    'bridleway': 14,
    'unknown': 15,
}
LAND = {
    'park': 'park',
    'forest': 'green',
    'wood': 'green',
    'grass': 'green',
    'grassland': 'green',
    'meadow': 'green',
    'scrub': 'green',
    'heath': 'green',
    'recreation_ground': 'park',
    'cemetery': 'park',
    'allotments': 'farm',
    'farmland': 'farm',
    'orchard': 'farm',
    'vineyard': 'farm',
    'farmyard': 'farm',
    'residential': 'res',
    'commercial': 'com',
    'retail': 'com',
    'industrial': 'ind',
    'military': 'ind',
    'quarry': 'ind',
    'landfill': 'ind',
}
PLACE_Z = {
    'country': 4,
    'state': 5,
    'province': 5,
    'county': 7,
    'city': 6,
    'town': 9,
    'suburb': 12,
    'village': 11,
    'hamlet': 14,
    'locality': 14,
    'island': 11,
    'farm': 15,
    'region': 5,
    'neighbourhood': 14,
}
POI_KEEP = {
    'hospital',
    'clinic',
    'doctors',
    'pharmacy',
    'chemist',
    'dentist',
    'veterinary',
    'fire_station',
    'police',
    'drinking_water',
    'water_tower',
    'water_works',
    'fountain',
    'toilet',
    'shelter',
    'community_centre',
    'town_hall',
    'school',
    'library',
    'supermarket',
    'convenience',
    'doityourself',
    'hardware',
    'garden_centre',
    'post_office',
    'camp_site',
    'wastewater_plant',
    'comms_tower',
    'spring',
    'park',
    'courthouse',
    'embassy',
    'nursing_home',
    'kindergarten',
    'college',
    'university',
    'bicycle_shop',
    'car_repair',
    'fuel',
    'beach',
}
ALIASES = {
    'toilets': 'toilet',
    'townhall': 'town_hall',
    'bicycle': 'bicycle_shop',
    'communications_tower': 'comms_tower',
}
SCHEMA = '''CREATE TABLE feat(id INTEGER PRIMARY KEY,layer TEXT,cls TEXT,name TEXT,minz INTEGER,geom BLOB);
CREATE VIRTUAL TABLE feat_idx USING rtree(id,minx,maxx,miny,maxy,minz,maxz);
CREATE TABLE poi(id INTEGER PRIMARY KEY,cls TEXT,name TEXT,lon REAL,lat REAL);
CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT);
CREATE TABLE feature_osm(id INTEGER PRIMARY KEY,osm_type TEXT,osm_id INTEGER);
CREATE TABLE poi_osm(id INTEGER PRIMARY KEY,osm_type TEXT,osm_id INTEGER);
'''
PSCHEMA = '''CREATE TABLE place(id INTEGER PRIMARY KEY,name TEXT,kind TEXT,detail TEXT,lat REAL,lon REAL,rank INTEGER,source TEXT);
CREATE VIRTUAL TABLE place_fts USING fts5(name,detail,content='place',content_rowid='id',tokenize='unicode61');
CREATE TABLE place_osm(id INTEGER PRIMARY KEY,osm_type TEXT,osm_id INTEGER);
CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT);'''


def stamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def atomic_json(path, data):
    p = Path(str(path) + '.tmp')
    p.write_text(json.dumps(data, indent=2))
    p.replace(path)


def bbox(parts):
    minx = miny = math.inf
    maxx = maxy = -math.inf
    for p in parts:
        for x, y in p:
            if not (
                math.isfinite(x)
                and math.isfinite(y)
                and -180 <= x <= 180
                and -90 <= y <= 90
            ):
                raise ValueError('invalid coordinate')
            minx = min(minx, x)
            maxx = max(maxx, x)
            miny = min(miny, y)
            maxy = max(maxy, y)
    return minx, maxx, miny, maxy


def pack(parts):
    # Explicit little endian: exact native int32 format on LastBook's x86_64 runtime.
    out = bytearray(struct.pack('<i', len(parts)))
    for p in parts:
        out.extend(struct.pack('<i', len(p)))
        lx = ly = 0
        for lon, lat in p:
            x, y = round(lon * Q), round(lat * Q)
            out.extend(struct.pack('<ii', x - lx, y - ly))
            lx, ly = x, y
    return bytes(out)


def area_z(b, base):
    size = max(b[1] - b[0], b[3] - b[2])
    return max(base, min(16, int(math.log2(360 / size)) - 4)) if size > 0 else 17


def poiclass(t):
    for key in (
        'amenity',
        'shop',
        'tourism',
        'leisure',
        'natural',
        'man_made',
        'healthcare',
    ):
        v = ALIASES.get(t.get(key), t.get(key))
        if v in POI_KEEP:
            return v
    if t.get('emergency') == 'shelter':
        return 'shelter'


def area_layers(t):
    layers = []
    natural = t.get('natural')
    land = t.get('landuse')
    leisure = t.get('leisure')
    if (
        natural == 'water'
        or t.get('water')
        or land in ('reservoir', 'basin')
        or t.get('waterway') in ('riverbank', 'dock')
    ):
        layers.append(('water', t.get('water') or land or 'water', 7))
    if natural == 'wetland':
        layers.append(('wet', t.get('wetland') or 'wetland', 7))
    if natural == 'beach':
        layers.append(('beach', 'beach', 10))
    lc = LAND.get(land) or LAND.get(natural) or LAND.get(leisure)
    if lc:
        layers.append(('land', lc, 9))
    elif (
        t.get('boundary') in ('protected_area', 'national_park')
        or leisure == 'nature_reserve'
    ):
        layers.append(('land', 'park', 8))
    if t.get('building') and t['building'] != 'no':
        layers.append(('bldg', t['building'], 15))
    if t.get('place') == 'island':
        layers.append(('island', 'island', 7))
    return layers


class Build(Handler):
    def __init__(self, out, node_index, disk_budget):
        super().__init__()
        self.out = out
        self.node_index = node_index
        self.disk_budget = disk_budget
        self.started = time.monotonic()
        self.count = collections.Counter()
        self.layers = collections.Counter()
        self.pending = 0
        self.db = sqlite3.connect(out / 'canada-map.sqlite.building')
        self.pdb = sqlite3.connect(out / 'canada-places.sqlite.building')
        for db in (self.db, self.pdb):
            db.executescript(
                'PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF; PRAGMA cache_size=-32768; PRAGMA temp_store=FILE; PRAGMA mmap_size=0;'
            )
        self.db.executescript(SCHEMA)
        self.pdb.executescript(PSCHEMA)

    def progress(self, phase):
        self.db.commit()
        self.pdb.commit()
        self.pending = 0
        data = {
            'state': phase,
            'updated': stamp(),
            'elapsed_seconds': round(time.monotonic() - self.started),
            'counts': dict(self.count),
            'layers': dict(self.layers),
            'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        }
        atomic_json(self.out / 'progress.json', data)
        print(json.dumps(data), flush=True)

    def tick(self):
        self.pending += 1
        if self.pending >= 20000:
            self.progress('BUILDING')

    def add(self, layer, cls, name, z, parts, origin):
        if not parts or any(not p for p in parts):
            return
        b = bbox(parts)
        self.count['features'] += 1
        fid = self.count['features']
        self.layers[layer] += 1
        self.db.execute(
            'INSERT INTO feat VALUES(?,?,?,?,?,?)',
            (fid, layer, cls, name, z, pack(parts)),
        )
        self.db.execute('INSERT INTO feat_idx VALUES(?,?,?,?,?,?,?)', (fid, *b, z, 30))
        self.db.execute('INSERT INTO feature_osm VALUES(?,?,?)', (fid, *origin))
        self.tick()

    def place(self, name, cls, lon, lat, rank, t, origin):
        if not name:
            return
        region = (
            t.get('addr:province')
            or t.get('addr:state')
            or t.get('is_in:province')
            or t.get('is_in:state')
        )
        detail = (region + ', ' if region else '') + 'Canada (OpenStreetMap)'
        row = self.pdb.execute(
            'INSERT INTO place(name,kind,detail,lat,lon,rank,source) VALUES(?,?,?,?,?,?,?)',
            (
                name,
                cls.replace('_', ' '),
                detail,
                lat,
                lon,
                rank,
                'OpenStreetMap Canada',
            ),
        )
        self.pdb.execute(
            'INSERT INTO place_osm VALUES(?,?,?)', (row.lastrowid, *origin)
        )
        self.count['search_places'] += 1

    def points(self, t, lon, lat, origin):
        name = t.get('name') or t.get('name:en') or t.get('name:fr')
        cls = t.get('place')
        if cls and name:
            z = PLACE_Z.get(cls, 14)
            try:
                if (
                    cls in ('city', 'town')
                    and int(t.get('population', '0').replace(',', '')) > 300000
                ):
                    z = 5
            except ValueError:
                pass
            self.add('place', cls, name, z, [[(lon, lat)]], origin)
            self.place(name, cls, lon, lat, 1, t, origin)
        cls = poiclass(t)
        if cls:
            self.count['pois'] += 1
            pid = self.count['pois']
            self.db.execute(
                'INSERT INTO poi VALUES(?,?,?,?,?)', (pid, cls, name, lon, lat)
            )
            self.db.execute('INSERT INTO poi_osm VALUES(?,?,?)', (pid, *origin))
            self.place(name, cls, lon, lat, 4, t, origin)
            self.tick()

    def node(self, n):
        self.count['nodes_seen'] += 1
        if len(n.tags) and n.location.valid():
            self.points(dict(n.tags), n.location.lon, n.location.lat, ('node', n.id))
        if self.count['nodes_seen'] % 2000000 == 0:
            self.progress('NODES')

    def way(self, w):
        self.count['ways_seen'] += 1
        t = dict(w.tags)
        highway = t.get('highway')
        waterway = t.get('waterway')
        rail = t.get('railway')
        coastline = t.get('natural') == 'coastline'
        open_poi = not w.is_closed() and (poiclass(t) or t.get('place'))
        selected = (
            (highway and t.get('area') != 'yes')
            or (waterway and waterway not in ('riverbank', 'dock'))
            or rail
            or coastline
            or open_poi
        )
        if selected:
            self.count['selected_ways'] += 1
            if any(not n.location.valid() for n in w.nodes):
                self.count['missing_location_ways'] += 1
            elif len(w.nodes) >= 2:
                parts = [[(n.lon, n.lat) for n in w.nodes]]
                origin = ('way', w.id)
                name = t.get('name') or t.get('ref')
                if highway and t.get('area') != 'yes':
                    cls = highway
                    if highway == 'track' and t.get('tracktype') in (
                        'grade1',
                        'grade2',
                        'grade3',
                        'grade4',
                        'grade5',
                    ):
                        cls = 'track_' + t['tracktype']
                    self.add('road', cls, name, ROAD_Z.get(highway, 15), parts, origin)
                if waterway and waterway not in ('riverbank', 'dock'):
                    self.add(
                        'waterway',
                        waterway,
                        name,
                        10 if waterway == 'river' else 13,
                        parts,
                        origin,
                    )
                if rail:
                    self.add(
                        'rail', rail, name, 10 if rail == 'rail' else 13, parts, origin
                    )
                if coastline:
                    self.add('waterway', 'coastline', name, 5, parts, origin)
                if open_poi:
                    p = parts[0][len(parts[0]) // 2]
                    self.points(t, *p, origin)
        if self.count['ways_seen'] % 100000 == 0:
            self.progress('WAYS')

    def area(self, a):
        self.count['areas_seen'] += 1
        t = dict(a.tags)
        layers = area_layers(t)
        if not layers and not poiclass(t) and not t.get('place'):
            return
        parts = []
        for outer in a.outer_rings():
            parts.append([(n.lon, n.lat) for n in outer])
            parts.extend(
                [[(n.lon, n.lat) for n in ring] for ring in a.inner_rings(outer)]
            )
        if not parts:
            return
        # Rings stay separate, preserving holes for map.js evenodd fill.
        if any(len(p) < 4 or p[0] != p[-1] for p in parts):
            raise ValueError(f'unclosed assembled area {a.id}')
        b = bbox(parts)
        origin = ('way' if a.from_way() else 'relation', a.orig_id())
        name = t.get('name')
        for layer, cls, base in layers:
            self.add(
                layer,
                cls,
                None if layer == 'bldg' else name,
                15 if layer == 'bldg' else area_z(b, base),
                parts,
                origin,
            )
        # Area POIs use bounding-box centers, matching upstream build_map.py convention.
        self.points(t, (b[0] + b[1]) / 2, (b[2] + b[3]) / 2, origin)

    def finish(self, source, source_sha, date):
        self.progress('INDEXING')
        if self.count['missing_location_ways'] > max(
            10, self.count['selected_ways'] * 0.001
        ):
            raise ValueError('Excess missing node references')
        self.db.execute('CREATE INDEX poi_cls ON poi(cls,lon,lat)')
        self.db.execute('CREATE INDEX feat_layer_name ON feat(layer,name)')
        self.db.execute(
            'CREATE INDEX feature_osm_object ON feature_osm(osm_type,osm_id)'
        )
        self.pdb.execute("INSERT INTO place_fts(place_fts) VALUES('rebuild')")
        b = self.db.execute(
            'SELECT min(minx),min(miny),max(maxx),max(maxy) FROM feat_idx'
        ).fetchone()
        meta = {
            'source': 'OpenStreetMap Canada contributors via Geofabrik '
            + source.name
            + ' (ODbL 1.0)',
            'source_sha256': source_sha,
            'data_as_of': date,
            'built': stamp(),
            'bounds': ','.join(str(x) for x in b),
            'coverage': 'Canada extract; mapped roads/paths, rail, inland water, coastline outlines, land, buildings, places, selected POIs',
            'limitations': 'No satellite/elevation/routing/live status/comprehensive address or postcode search. Area POI positions approximate (bbox center). Coastlines are lines, not inferred ocean polygons. Extract may include adjacent-border features.',
            'converter': f'build_canada_map.py; osmium {version("osmium")}; int32 little-endian delta lon/lat * 1e6; all rings preserved',
            'node_index': self.node_index,
            'sqlite_temp': 'staging/sqlite-tmp',
            'disk_preflight_bytes': str(self.disk_budget),
        }
        for db in (self.db, self.pdb):
            db.executemany('INSERT INTO meta VALUES(?,?)', meta.items())
            db.commit()
        self.progress('BUILT_NEEDS_VALIDATION')
        self.db.close()
        self.pdb.close()
        atomic_json(
            self.out / 'build-receipt.json',
            {
                'state': 'BUILT_NEEDS_VALIDATION',
                'meta': meta,
                'counts': dict(self.count),
                'layers': dict(self.layers),
                'elapsed_seconds': round(time.monotonic() - self.started),
                'peak_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            },
        )


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        'source',
        type=Path,
        help='existing Canada .osm.pbf extract; never downloaded by this tool',
    )
    ap.add_argument('out', type=Path, help='new staging directory; must not exist')
    ap.add_argument(
        '--source-sha256', required=True, help='independently recorded source SHA256'
    )
    ap.add_argument(
        '--data-date',
        required=True,
        help='OSM replication timestamp, ISO 8601 with timezone',
    )
    ap.add_argument(
        '--node-index',
        required=True,
        choices=('sparse_mem_array', 'sparse_file_array'),
        help='explicit RAM/disk tradeoff; see docs/canada-map.md before a country build',
    )
    ap.add_argument(
        '--min-free-gib',
        type=float,
        help='raise required free output/scratch headroom above the source-size heuristic',
    )
    args = ap.parse_args()
    if osmium is None:
        ap.error(
            'Build dependency missing: install osmium==4.3.2 in a separate build environment'
        )
    if not re.fullmatch(r'[a-fA-F0-9]{64}', args.source_sha256):
        ap.error('--source-sha256 must be 64 hexadecimal digits')
    try:
        date = datetime.datetime.fromisoformat(args.data_date.replace('Z', '+00:00'))
        if date.tzinfo is None:
            raise ValueError('timezone required')
        with args.source.open('rb') as stream:
            actual = hashlib.file_digest(stream, 'sha256').hexdigest()
    except (OSError, ValueError) as error:
        ap.error(str(error))
    if actual != args.source_sha256.lower():
        ap.error('Source SHA256 mismatch; no output created')
    try:
        budget = disk_preflight(
            args.source, args.out.parent, args.node_index, args.min_free_gib
        )
        args.out.mkdir(exist_ok=False)
    except (OSError, ValueError) as error:
        ap.error(str(error))
    try:
        with sqlite_scratch(args.out):
            b = Build(args.out, args.node_index, budget)
            try:
                b.progress('RELATION_PREPASS')
                index = args.node_index
                if index == 'sparse_file_array':
                    index += ',' + str(args.out / 'node-locations.idx')
                b.apply_file(str(args.source), locations=True, idx=index)
                b.finish(args.source, actual, args.data_date)
            finally:
                b.db.close()
                b.pdb.close()
    except (OSError, sqlite3.Error, RuntimeError) as error:
        ap.exit(1, storage_error(error, args.out) + '\n')


if __name__ == '__main__':
    main()
