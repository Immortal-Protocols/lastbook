"""Add offline road measures and public school address landmarks to a PR address build."""
import json
import math
import re
from pathlib import Path

from shapely import STRtree, make_valid, prepare
from shapely.geometry import LineString, Point, shape

from engine import pr_rural

HPMS = 'https://geo.dot.gov/server/rest/services/Hosted/HPMS_FULL_PR_2024/FeatureServer/0'
BARRIOS = 'https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Places_CouSub_ConCity_SubMCD/MapServer/1'
ZCTAS = 'https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/PUMA_TAD_TAZ_UGA_ZCTA/MapServer/1'
SCHOOLS = 'https://nces.ed.gov/opengis/rest/services/K12_School_Locations/EDGE_GEOCODE_PUBLICSCH_2425/MapServer/0'
M_PER_MILE = 1609.344


class Areas:
    """Use source polygons, including both sides of a shared boundary when applicable."""
    def __init__(self, features, name):
        self.geometries, self.names = [], []
        for f in features:
            geom = shape(f['geometry'])
            if not geom.is_valid:
                geom = make_valid(geom)
            if geom.is_empty:
                raise ValueError('Empty area in the rural reference inputs.')
            prepare(geom)
            self.geometries.append(geom)
            self.names.append(name(f['properties']))
        self.tree = STRtree(self.geometries)

    def at(self, point):
        return sorted(self.names[i] for i in self.tree.query(point, predicate='intersects'))

    def splits(self, line):
        # Most short road edges lie in one area and never need a polygon overlay.
        cuts = set()
        for i in self.tree.query(line):
            polygon = self.geometries[i]
            if polygon.covers(line) or not polygon.intersects(line):
                continue
            crossing = polygon.boundary.intersection(line)
            pieces = list(crossing.geoms) if hasattr(crossing, 'geoms') else [crossing]
            for piece in pieces:
                if piece.geom_type == 'Point':
                    cuts.add(line.project(piece, normalized=True))
                elif piece.geom_type == 'LineString' and not piece.is_empty:
                    for xy in (piece.coords[0], piece.coords[-1]):
                        cuts.add(line.project(Point(xy), normalized=True))
        return cuts


def features(path):
    obj = json.loads(path.read_text(encoding='utf-8'))
    if obj.get('exceededTransferLimit') or not obj.get('features'):
        raise ValueError(f'Incomplete input: {path.name}')
    return obj['features']


def sections(roads, barrios, zctas, area_id):
    for f in roads:
        match = re.fullmatch(r'PR-0*(\d+)(?: [NSEW]B)?', f['attributes']['route_id'])
        if not match:
            continue  # ramps and connectors carry separate measures
        route = int(match[1])
        for path in (f.get('geometry') or {}).get('paths', []):
            for a, b in zip(path, path[1:]):
                if len(a) != 3 or len(b) != 3 or any(v is None or not math.isfinite(v) for v in (*a, *b)):
                    continue
                if a[2] > b[2]:
                    a, b = b, a
                x, y, miles = a
                dx, dy = b[0] - x, b[1] - y
                low, span = miles * M_PER_MILE, (b[2] - miles) * M_PER_MILE
                length = math.hypot(dx * math.cos(math.radians(y)), dy) * 111320
                if low < 0 or span <= 0 or length == 0 or span > length * 4 + 20:
                    continue  # invalid measure, stationary vertex, or calibration jump
                line = LineString([(x, y), (b[0], b[1])])
                cuts = sorted({0., 1.} | barrios.splits(line) | zctas.splits(line))
                for s, t in zip(cuts, cuts[1:]):
                    if (t - s) * span < 0.00001:
                        continue
                    mid = line.interpolate((s + t) / 2, normalized=True)
                    zones = zctas.at(mid) or ['']
                    start, end = low + s * span, low + t * span
                    for barrio, town in barrios.at(mid):
                        for zone in zones:
                            aid = area_id(barrio, town, zone)
                            for bucket in range(int(start // 1000), int(end // 1000) + 1):
                                yield (route, bucket, start, end, round(y + dy*s, 7), round(x + dx*s, 7),
                                       round(y + dy*t, 7), round(x + dx*t, 7), aid)


def build(db, folder, sha):
    folder = Path(folder)
    files = {k: folder / name for k, name in [('roads','hpms-roads.json'), ('barrios','barrios.json'),
                                               ('zctas','zctas.json'), ('schools','schools.json')]}
    towns = dict(db.execute('SELECT geoid,name FROM municipios'))

    def barrio_name(p):
        town = towns[p['GEOID'][:5]]
        return (p['NAME'] if p['NAME'].endswith(' barrio-pueblo') else p['BASENAME'], town)

    barrios = Areas(features(files['barrios']), barrio_name)
    zctas = Areas(features(files['zctas']), lambda p: p['ZCTA5'])
    db.executescript("""
        CREATE TABLE pr_area(id INTEGER PRIMARY KEY,barrio TEXT,municipio TEXT,zip TEXT);
        CREATE TABLE pr_road(route INTEGER,bucket INTEGER,low REAL,high REAL,lat0 REAL,lon0 REAL,lat1 REAL,lon1 REAL,area INTEGER);
        CREATE TABLE pr_school(route INTEGER,meters INTEGER,name TEXT,street TEXT,lat REAL,lon REAL,area INTEGER,postal TEXT,reported_city TEXT);
    """)
    ids = {}
    def area_id(barrio, town, zone):
        key = (barrio, town, zone)
        if key not in ids:
            ids[key] = len(ids) + 1
        return ids[key]

    db.executemany('INSERT INTO pr_road VALUES (?,?,?,?,?,?,?,?,?)',
                   sections(features(files['roads']), barrios, zctas, area_id))
    for school in features(files['schools']):
        a = school['attributes']
        addr = pr_rural.parse(a['STREET'] or '')
        if not addr or a['STATE'] != 'PR':
            continue
        point = Point(a['LON'], a['LAT'])
        for barrio, town in barrios.at(point):
            aid = area_id(barrio, town, a['ZIP'])
            db.execute('INSERT INTO pr_school VALUES (?,?,?,?,?,?,?,?,?)',
                       (addr.route, addr.meters, a['NAME'], a['STREET'], point.y, point.x, aid, a['ZIP'], a['CITY']))
    db.executemany('INSERT INTO pr_area VALUES (?,?,?,?)', [(aid, *area) for area, aid in ids.items()])
    db.executescript('CREATE INDEX rural_measure ON pr_road(route,bucket,low); '
                     'CREATE INDEX school_measure ON pr_school(route,meters);')
    totals = db.execute('SELECT count(DISTINCT route),count(*) FROM pr_road').fetchone()
    if not totals[0]:
        raise ValueError('No usable numbered, measured road paths in the input.')
    municipalities = dict(db.execute('SELECT municipio,count(DISTINCT route) FROM pr_area JOIN pr_road '
                                     'ON pr_area.id=pr_road.area GROUP BY municipio ORDER BY municipio'))
    return {'routes': totals[0], 'road_rows': totals[1], 'municipios_with_routes': municipalities,
            'school_locations': db.execute('SELECT count(*) FROM pr_school').fetchone()[0],
            'sources': {k: {'url': url, 'sha256': sha(files[k])} for k, url in
                        [('roads', HPMS), ('barrios', BARRIOS), ('zctas', ZCTAS), ('schools', SCHOOLS)]}}
