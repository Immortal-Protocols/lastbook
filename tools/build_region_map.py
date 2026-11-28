#!/usr/bin/env python3
"""Build a detailed offline map of one region outside the United States from an OpenStreetMap extract.

It writes a map set in the shape of a US state map (packaging/build_packs.py), with the files, tables and classes
the app already reads (docs/MAPS.md), so the engine and the interface need no change:

  <out>/<id>/derived/geo/national.sqlite       feat, feat_idx, poi, meta   streets, water, land, buildings, place
                                                                           labels, sea, and the help points
  <out>/<id>/derived/geo/map.sqlite            the same tables, empty      as in a state map
  <out>/<id>/derived/geo/places.sqlite         place, place_fts            the place finder
  <out>/<id>/derived/geo/national-status.json, socal-cells.json            as in a state map
  <out>/<id>/map-set.json                      name, files, bytes
  <out>/<id>.build.json                        source, dates, counts, sizes and SHA-256 of each file

It builds in a temporary folder beside <out>/<id> and moves the result into place only when the whole build has
succeeded. A build that fails or is stopped leaves no <out>/<id>, so the same command can simply be run again.

The rows go in national.sqlite, not map.sqlite, because the engine draws pins from map.sqlite only inside a box
around Southern California (_poi_sources in server.py).

  derived/buildenv/bin/python tools/build_region_map.py thailand-latest.osm.pbf \
      --id TH-10 --name Bangkok --bbox 100.17,13.34,101.09,14.11 --out derived/regions

The only source is the .osm.pbf (OpenStreetMap contributors, ODbL 1.0), which is read and never written.
Nothing is downloaded. It needs pyosmium, as tools/build_coast.py does. The output folder is new each time:
the tool refuses to replace a map that is already there, and it never touches derived/geo/.

What it keeps follows tools/build_map.py (same layers, classes and zoom rules), with these differences:
  - it reads raw OpenStreetMap tags, so it can keep a second name: the local name is the label, and the
    English name (name:en), when there is one, goes into the place finder so either script finds the place;
  - the sea is cut to the region's box, whichever side the sea is on (tools/build_coast.py assumes west);
  - roads, railways, water and land that cross the box are cut at its edge (building outlines are kept whole);
  - amenity=shelter is kept only when it is not a bus shelter;
  - a health facility tagged only healthcare=* is kept, and funiculars and cable cars are drawn as railways.
The box usually reaches past the region itself. With --boundary (the id of the region's OpenStreetMap boundary
relation), only place-finder rows inside that boundary carry the region's name in their detail line.
Addresses, terrain, crops and the US-only layers are not built.
"""
import argparse
import hashlib
import json
import math
import os
import re
import shutil
import signal
import sqlite3
import sys
import tempfile
import time
from array import array
from pathlib import Path

import osmium

Q = 1e6
ROAD_Z = {'motorway': 5, 'trunk': 6, 'motorway_link': 10, 'trunk_link': 10, 'primary': 8, 'primary_link': 12,
          'secondary': 10, 'secondary_link': 13, 'tertiary': 11, 'tertiary_link': 13, 'residential': 13,
          'unclassified': 13, 'living_street': 14, 'pedestrian': 14, 'busway': 14, 'service': 15,
          'track': 13, 'track_grade1': 13, 'track_grade2': 13, 'track_grade3': 13, 'track_grade4': 13, 'track_grade5': 13,
          'footway': 15, 'path': 14, 'cycleway': 14, 'steps': 16, 'bridleway': 14}
LANDUSE_KEEP = {'park': 'park', 'forest': 'green', 'grass': 'green', 'meadow': 'green', 'scrub': 'green', 'heath': 'green',
                'recreation_ground': 'park', 'cemetery': 'park', 'allotments': 'farm', 'farmland': 'farm',
                'orchard': 'farm', 'vineyard': 'farm', 'farmyard': 'farm', 'residential': 'res', 'commercial': 'com',
                'retail': 'com', 'industrial': 'ind', 'military': 'ind', 'quarry': 'ind', 'landfill': 'ind'}
NATURAL_LAND = {'wood': 'green', 'scrub': 'green', 'heath': 'green', 'grassland': 'green'}
LEISURE_LAND = {'park': 'park', 'garden': 'park', 'recreation_ground': 'park', 'nature_reserve': 'park'}
PLACE_Z = {'city': 6, 'town': 9, 'suburb': 12, 'quarter': 12, 'neighbourhood': 13, 'village': 11, 'hamlet': 14,
           'locality': 14, 'island': 11}
PLACE_RANK = {'city': 1, 'town': 1, 'suburb': 2, 'quarter': 2, 'village': 2, 'neighbourhood': 3, 'hamlet': 3,
              'locality': 3, 'island': 3}
RAIL = {'rail', 'light_rail', 'subway', 'tram', 'monorail', 'narrow_gauge', 'funicular'}
AERIALWAY = {'cable_car', 'gondola', 'mixed_lift'}  # public transport in some cities; drawn with the railways
WATERWAY = {'river', 'stream', 'canal', 'drain', 'ditch'}
# Help points: the classes tools/build_map.py keeps (POI_KEEP), found from raw tags.
AMENITY = {'hospital': 'hospital', 'clinic': 'clinic', 'doctors': 'doctors', 'pharmacy': 'pharmacy', 'dentist': 'dentist',
           'veterinary': 'veterinary', 'fire_station': 'fire_station', 'police': 'police',
           'drinking_water': 'drinking_water', 'fountain': 'fountain', 'toilets': 'toilet', 'shelter': 'shelter',
           'community_centre': 'community_centre', 'townhall': 'town_hall', 'school': 'school', 'library': 'library',
           'post_office': 'post_office', 'courthouse': 'courthouse', 'embassy': 'embassy',
           'nursing_home': 'nursing_home', 'kindergarten': 'kindergarten', 'college': 'college',
           'university': 'university', 'fuel': 'fuel'}
SHOP = {'supermarket': 'supermarket', 'convenience': 'convenience', 'doityourself': 'doityourself',
        'hardware': 'hardware', 'garden_centre': 'garden_centre', 'chemist': 'chemist', 'bicycle': 'bicycle_shop',
        'car_repair': 'car_repair'}
# healthcare=* is read only when amenity gives no class: many clinics and health posts carry this tag alone
HEALTHCARE = {'hospital': 'hospital', 'clinic': 'clinic', 'centre': 'clinic', 'doctor': 'doctors', 'pharmacy': 'pharmacy',
              'dentist': 'dentist'}
MAN_MADE = {'water_tower': 'water_tower', 'water_works': 'water_works', 'wastewater_plant': 'wastewater_plant'}
BUS_SHELTER = {'public_transport', 'bus', 'taxi'}


def poi_class(t):
    a = t.get('amenity')
    if a in AMENITY:
        if a == 'shelter' and t.get('shelter_type') in BUS_SHELTER:
            return None
        return AMENITY[a]
    hc = t.get('healthcare')
    if hc in HEALTHCARE:
        return HEALTHCARE[hc]
    s = t.get('shop')
    if s in SHOP:
        return SHOP[s]
    m = t.get('man_made')
    if m in MAN_MADE:
        return MAN_MADE[m]
    if m in ('tower', 'mast') and t.get('tower:type') == 'communication':
        return 'comms_tower'
    if t.get('tourism') == 'camp_site':
        return 'camp_site'
    if t.get('natural') == 'spring':
        return 'spring'
    if t.get('office') == 'diplomatic' or t.get('diplomatic') == 'embassy':
        return 'embassy'
    return None


def simplify(flat, tol):
    """Drop points closer than tol (degrees) to the previous kept point; keeps endpoints. As tools/build_map.py."""
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


def pack(parts):
    """int32 array: nparts, then for each part npts followed by quantized x,y deltas. As tools/build_map.py."""
    a = array('i', [len(parts)])
    for p in parts:
        n = len(p) // 2
        a.append(n)
        lx = ly = 0
        for i in range(n):
            x, y = int(round(p[2 * i] * Q)), int(round(p[2 * i + 1] * Q))
            a.append(x - lx); a.append(y - ly)
            lx, ly = x, y
    return a.tobytes()


def bounds(parts):
    xs = [v for p in parts for v in p[0::2]]
    ys = [v for p in parts for v in p[1::2]]
    return min(xs), max(xs), min(ys), max(ys)


def area_z(minx, maxx, miny, maxy, base):
    """Small polygons only appear when zoomed in. As tools/build_map.py."""
    size = max(maxx - minx, maxy - miny)
    if size <= 0:
        return 17
    return max(base, min(16, int(math.log2(360 / size)) - 4))


# ------------------------------------------------------------------ the sea
def clip_line(pts, box):
    """The pieces of an open line that lie inside the box, each starting and ending on the box edge where it was cut."""
    w, s, e, n = box

    def inside(p):
        return w <= p[0] <= e and s <= p[1] <= n

    def cross(a, b):
        """Where a->b crosses the box edge, ordered from a."""
        out = []
        dx, dy = b[0] - a[0], b[1] - a[1]
        for edge, d, lo, hi, other in ((w, dx, s, n, 0), (e, dx, s, n, 0), (s, dy, w, e, 1), (n, dy, w, e, 1)):
            if d == 0:
                continue
            t = (edge - a[other]) / d
            if 0 <= t <= 1:
                x, y = a[0] + t * dx, a[1] + t * dy
                v = y if other == 0 else x
                if lo <= v <= hi:
                    out.append((t, (edge, y) if other == 0 else (x, edge)))
        return [p for _, p in sorted(out)]

    pieces, cur = [], None
    for a, b in zip(pts, pts[1:]):
        ia, ib = inside(a), inside(b)
        if ia and cur is None:
            cur = [a]
        if ia and ib:
            cur.append(b)
            continue
        hits = cross(a, b)
        if ia and not ib and hits:
            cur.append(hits[-1])
            pieces.append(cur)
            cur = None
        elif not ia and ib and hits:
            cur = [hits[0], b]
        elif not ia and not ib and len(hits) >= 2:
            pieces.append([hits[0], hits[-1]])
        elif ia and not ib:
            pieces.append(cur)
            cur = None
    if cur and len(cur) > 1:
        pieces.append(cur)
    return [p for p in pieces if len(p) > 1]


def clip_ring(flat, box):
    """A closed ring (flat x,y list) cut to the box, one box edge at a time (Sutherland-Hodgman). [] if nothing is left."""
    pts = list(zip(flat[0::2], flat[1::2]))
    if pts[0] == pts[-1]:
        pts.pop()
    w, s, e, n = box
    for axis, edge, above in ((0, w, True), (0, e, False), (1, s, True), (1, n, False)):
        out = []
        for a, b in zip(pts, pts[1:] + pts[:1]):
            ia = a[axis] >= edge if above else a[axis] <= edge
            ib = b[axis] >= edge if above else b[axis] <= edge
            if ia:
                out.append(a)
            if ia != ib:
                t = (edge - a[axis]) / (b[axis] - a[axis])
                out.append((edge, a[1] + t * (b[1] - a[1])) if axis == 0 else (a[0] + t * (b[0] - a[0]), edge))
        pts = out
        if len(pts) < 3:
            return []
    return [v for p in pts + pts[:1] for v in p]


def cut(parts, box, ring):
    """Parts (flat x,y lists) cut to the box: rings stay closed, lines may come back as several pieces."""
    minx, maxx, miny, maxy = bounds(parts)
    w, s, e, n = box
    if minx >= w and maxx <= e and miny >= s and maxy <= n:
        return parts
    if ring:
        return [r for r in (clip_ring(p, box) for p in parts) if len(r) >= 8]
    return [[v for pt in piece for v in pt] for p in parts for piece in clip_line(list(zip(p[0::2], p[1::2])), box)]


class Boundary:
    """Whether a point is inside a boundary's rings (even-odd rule). Edges are sorted into latitude bands, so a
    test looks only at the edges that pass the point's latitude."""
    BANDS = 512

    def __init__(self, rings):
        ys = [y for ring in rings for _, y in ring]
        self.south, self.north = min(ys), max(ys)
        self.step = (self.north - self.south) / self.BANDS or 1.0
        self.bands = [[] for _ in range(self.BANDS)]
        for ring in rings:
            for (x0, y0), (x1, y1) in zip(ring, ring[1:]):
                if y0 != y1:
                    for k in range(self.band(min(y0, y1)), self.band(max(y0, y1)) + 1):
                        self.bands[k].append((x0, y0, x1, y1))

    def band(self, y):
        return min(self.BANDS - 1, max(0, int((y - self.south) / self.step)))

    def holds(self, lon, lat):
        if not self.south <= lat <= self.north:
            return False
        inside = False
        for x0, y0, x1, y1 in self.bands[self.band(lat)]:
            if (y0 > lat) != (y1 > lat) and lon < x0 + (lat - y0) * (x1 - x0) / (y1 - y0):
                inside = not inside
        return inside


def edge_pos(p, box):
    """Distance clockwise round the box edge from its north-west corner, or None if the point is not on the edge."""
    w, s, e, n = box
    x, y = p
    eps = 1e-9
    if abs(y - n) < eps:
        return x - w
    if abs(x - e) < eps:
        return (e - w) + (n - y)
    if abs(y - s) < eps:
        return (e - w) + (n - s) + (e - x)
    if abs(x - w) < eps:
        return 2 * (e - w) + (n - s) + (y - s)
    return None


def sea_rings(pieces, box):
    """Close coastline pieces into sea polygons. OpenStreetMap coastlines keep land on the left and water on the right,
    so from the end of a piece the sea continues clockwise round the box edge to the start of the next piece."""
    w, s, e, n = box
    total = 2 * (e - w) + 2 * (n - s)
    corners = [(0.0, (w, n)), (e - w, (e, n)), (e - w + n - s, (e, s)), (2 * (e - w) + n - s, (w, s))]
    ends = []
    for i, p in enumerate(pieces):
        a, b = edge_pos(p[0], box), edge_pos(p[-1], box)
        if a is not None and b is not None:
            ends.append((i, a, b))
    starts = sorted((a, i) for i, a, _ in ends)
    done, rings = set(), []
    for i, _, _ in ends:
        if i in done:
            continue
        ring, j = [], i
        while j not in done:
            done.add(j)
            ring += pieces[j]
            pos = next(b for k, _, b in ends if k == j)
            nxt = next(((a, k) for a, k in starts if a > pos), None)
            wrap = nxt is None
            if wrap:
                nxt = starts[0]
            stop = nxt[0] + (total if wrap else 0)
            for c, pt in corners + [(c + total, pt) for c, pt in corners]:
                if pos < c < stop:
                    ring.append(pt)
            j = nxt[1]
        ring.append(ring[0])
        rings.append(ring)
    return rings


def chains(ways):
    """Join coastline ways end to start. Returns (closed, points) for each chain."""
    by_start = {}
    for refs, pts in ways:
        by_start.setdefault(refs[0], []).append((refs, pts))
    used, out = set(), []
    ends = {refs[-1] for refs, _ in ways}
    order = sorted(ways, key=lambda w: w[0][0] in ends)  # begin with ways nothing leads into
    for refs, pts in order:
        if id(pts) in used:
            continue
        used.add(id(pts))
        r, p = list(refs), list(pts)
        while r[-1] != r[0]:
            nxt = [w for w in by_start.get(r[-1], []) if id(w[1]) not in used]
            if not nxt:
                break
            used.add(id(nxt[0][1]))
            r += nxt[0][0][1:]
            p += nxt[0][1][1:]
        out.append((r[0] == r[-1], p))
    return out


# ------------------------------------------------------------------ reading the extract
class Region(osmium.SimpleHandler):
    def __init__(self, box, prefer, boundary=None):
        super().__init__()
        self.box, self.prefer, self.boundary = box, prefer, boundary
        self.feats, self.pois, self.places, self.coast = [], [], [], []
        self.boundary_rings = []

    def touches(self, minx, maxx, miny, maxy):
        w, s, e, n = self.box
        return maxx >= w and minx <= e and maxy >= s and miny <= n

    def names(self, t):
        """(label, other name). The label is the local name unless --prefer en; the other one feeds search."""
        local, en = t.get('name'), t.get('name:en')
        if self.prefer == 'en' and en:
            return en, (local if local and local != en else None)
        return (local or en), (en if local and en and en != local else None)

    def add(self, layer, cls, name, minz, parts, ring=None):
        """Keep a feature. ring says how to cut it to the box: True for outlines, False for lines, None to keep it whole."""
        if ring is not None:
            parts = cut(parts, self.box, ring)
        if parts:
            self.feats.append((layer, cls, name, minz, parts))

    def point(self, t, lon, lat):
        cls = poi_class(t)
        if cls:
            label, other = self.names(t)
            self.pois.append((cls, label, other, lon, lat))

    def node(self, n):
        t = n.tags
        if not n.location.valid():
            return
        lon, lat = n.location.lon, n.location.lat
        if not self.touches(lon, lon, lat, lat):
            return
        place = t.get('place')
        if place in PLACE_Z and (t.get('name') or t.get('name:en')):
            label, other = self.names(t)
            z = PLACE_Z[place]
            pop = t.get('population', '')
            if place in ('city', 'town') and pop.isdigit() and int(pop) > 300000:
                z = 5
            self.add('place', place, label, z, [[lon, lat]])
            self.places.append((place, label, other, lon, lat))
        self.point(t, lon, lat)

    def way(self, w):
        t = w.tags
        hw, ww, rw, aw = t.get('highway'), t.get('waterway'), t.get('railway'), t.get('aerialway')
        coast = t.get('natural') == 'coastline'
        if not (coast or hw or ww in WATERWAY or rw in RAIL or aw in AERIALWAY):
            return
        try:
            flat = [v for n in w.nodes for v in (n.lon, n.lat)]
        except osmium.InvalidLocationError:
            return
        if len(flat) < 4 or not self.touches(min(flat[0::2]), max(flat[0::2]), min(flat[1::2]), max(flat[1::2])):
            return
        if coast:
            self.coast.append(([n.ref for n in w.nodes], list(zip(flat[0::2], flat[1::2]))))
            return
        label = self.names(t)[0]
        if hw:
            if hw == 'track' and t.get('tracktype') in ('grade1', 'grade2', 'grade3', 'grade4', 'grade5'):
                hw = 'track_' + t.get('tracktype')
            if hw in ROAD_Z and t.get('area') != 'yes':
                self.add('road', hw, label or t.get('ref'), ROAD_Z[hw], [flat], ring=False)
        elif ww in WATERWAY:
            self.add('waterway', ww, label, 10 if ww == 'river' else 13, [flat], ring=False)
        elif rw in RAIL and t.get('service') not in ('yard', 'siding', 'spur'):
            self.add('rail', rw, label, 10 if rw == 'rail' else 13, [flat], ring=False)
        elif aw in AERIALWAY:
            self.add('rail', aw, label, 13, [flat], ring=False)

    def area(self, a):
        if self.boundary and not a.from_way() and a.orig_id() == self.boundary:
            try:
                self.boundary_rings = [[(n.lon, n.lat) for n in ring] for outer in a.outer_rings()
                                       for ring in [outer] + list(a.inner_rings(outer))]
            except osmium.InvalidLocationError:
                pass
        t = a.tags
        nat, lu, lei = t.get('natural'), t.get('landuse'), t.get('leisure')
        bld = t.get('building')
        cls = poi_class(t)
        water = nat == 'water' or lu in ('reservoir', 'basin') or t.get('waterway') == 'riverbank'
        wet = nat == 'wetland'
        land = LANDUSE_KEEP.get(lu) or NATURAL_LAND.get(nat) or LEISURE_LAND.get(lei)
        park = t.get('boundary') in ('national_park', 'protected_area')
        if not (bld or cls or water or wet or land or park or nat == 'beach'):
            return
        try:
            rings = [[v for n in ring for v in (n.lon, n.lat)] for outer in a.outer_rings() for ring in
                     [outer] + list(a.inner_rings(outer))]
        except osmium.InvalidLocationError:
            return
        rings = [r for r in rings if len(r) >= 8]
        if not rings:
            return
        b = bounds(rings)
        if not self.touches(*b):
            return
        label = self.names(t)[0]
        if cls or nat == 'beach' or lei == 'park':
            kind = cls or ('beach' if nat == 'beach' else 'park')
            lab, other = self.names(t)
            self.pois.append((kind, lab, other, (b[0] + b[1]) / 2, (b[2] + b[3]) / 2))
        if water or wet:
            kind = 'wetland' if wet else ('reservoir' if lu in ('reservoir', 'basin') or t.get('water') == 'reservoir'
                                         else 'river' if t.get('water') in ('river', 'canal') or t.get('waterway') else 'water')
            self.add('wet' if wet else 'water', kind, label, area_z(*b, 7), [simplify(r, 0.00001) for r in rings], ring=True)
        elif nat == 'beach':
            self.add('beach', 'beach', label, area_z(*b, 10), rings, ring=True)
        elif bld:
            self.add('bldg', '' if bld == 'yes' else bld, None, 15, [simplify(rings[0], 0.000002)])
        elif park:
            self.add('land', 'park', None, area_z(*b, 8), [simplify(r, 0.00002) for r in rings], ring=True)
        elif land:
            self.add('land', land, label, area_z(*b, 9), [simplify(r, 0.00001) for r in rings], ring=True)


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


# ------------------------------------------------------------------ writing the map set
SCHEMA = '''PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;
  CREATE TABLE feat(id INTEGER PRIMARY KEY, layer TEXT, cls TEXT, name TEXT, minz INTEGER, geom BLOB);
  CREATE VIRTUAL TABLE feat_idx USING rtree(id, minx, maxx, miny, maxy, minz, maxz);
  CREATE TABLE poi(id INTEGER PRIMARY KEY, cls TEXT, name TEXT, lon REAL, lat REAL);
  CREATE INDEX poi_cls ON poi(cls, lon, lat);
  CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);'''
LAYER_ORDER = {'water': 0, 'wet': 0, 'beach': 1, 'land': 1, 'waterway': 2, 'rail': 2, 'road': 3, 'bldg': 4, 'place': 5}
GEO_NAMES = ('national.sqlite', 'map.sqlite', 'places.sqlite', 'national-status.json', 'socal-cells.json')


def unique_pois(pois):
    """Help points with exact repeats dropped (the same class and name at the same spot)."""
    seen = set()
    for cls, label, other, lon, lat in pois:
        key = (cls, label, round(lon, 5), round(lat, 5))
        if key not in seen:
            seen.add(key)
            yield cls, label, other, lon, lat


def write_map(geo, h, box, meta, buildings=True):
    """national.sqlite holds the rows; map.sqlite is the same tables with none, as in a state map.
    Returns (features by layer, help points by class)."""
    dst = sqlite3.connect(geo / 'national.sqlite')
    dst.executescript(SCHEMA)
    fid = 0
    count, kinds = {}, {}

    def feature(layer, cls, name, minz, parts):
        nonlocal fid
        fid += 1
        dst.execute('INSERT INTO feat VALUES (?,?,?,?,?,?)', (fid, layer, cls, name, minz, pack(parts)))
        dst.execute('INSERT INTO feat_idx VALUES (?,?,?,?,?,?,?)', (fid, *bounds(parts), minz, 30))
        count[layer] = count.get(layer, 0) + 1

    for layer, cls, name, minz, parts in sorted(h.feats, key=lambda f: LAYER_ORDER[f[0]]):
        if layer != 'bldg' or buildings:
            feature(layer, cls, name, minz, parts)
    # the sea, cut to the box; closed coastline rings inside the box are islands, drawn as land on top
    cs = chains(h.coast)
    sea = sea_rings([piece for closed, pts in cs if not closed for piece in clip_line(pts, box)], box)
    islands = [pts for closed, pts in cs if closed]
    for layer, group in (('ocean', sea), ('island', islands)):
        for ring in group:
            feature(layer, layer, None, 0, [[v for p in ring for v in p]])
    for pid, (cls, label, _, lon, lat) in enumerate(unique_pois(h.pois), 1):
        dst.execute('INSERT INTO poi VALUES (?,?,?,?,?)', (pid, cls, label, lon, lat))
        kinds[cls] = kinds.get(cls, 0) + 1
    status = {'state': 'complete', 'stage': 'ready', 'features': fid}
    # no build time in the files: the same extract and options give the same bytes, so a checksum can be compared
    dst.executemany('INSERT INTO meta VALUES (?,?)', meta + [('status', json.dumps(status))])
    dst.commit()
    dst.execute('VACUUM')
    dst.close()
    empty = sqlite3.connect(geo / 'map.sqlite')
    empty.executescript(SCHEMA)
    empty.executemany('INSERT INTO meta VALUES (?,?)', meta)
    empty.commit()
    empty.close()
    (geo / 'national-status.json').write_text(json.dumps(status), encoding='utf-8')
    (geo / 'socal-cells.json').write_text('[]', encoding='utf-8')
    return count, kinds


def write_places(geo, h, name, boundary=None):
    """places.sqlite: the place finder, in the shape tools/build_places.py writes. A row's detail line names the
    region, unless a boundary was given and the row lies outside it. Returns (rows, rows outside the boundary)."""
    db = sqlite3.connect(geo / 'places.sqlite')
    db.executescript('''CREATE TABLE place(id INTEGER PRIMARY KEY, name TEXT, kind TEXT, detail TEXT, lat REAL, lon REAL, rank INTEGER, source TEXT);
      CREATE VIRTUAL TABLE place_fts USING fts5(name, detail, content='place', content_rowid='id', tokenize='unicode61');''')
    rows = [(label, place, other, lon, lat, PLACE_RANK[place]) for place, label, other, lon, lat in h.places]
    rows += [(label, cls.replace('_', ' '), other, lon, lat, 4) for cls, label, other, lon, lat in unique_pois(h.pois) if label]
    outside = 0
    for label, kind, other, lon, lat, rank in rows:
        where = f'{name} (OpenStreetMap)'
        if boundary and not boundary.holds(lon, lat):
            where = 'OpenStreetMap'
            outside += 1
        db.execute('INSERT INTO place(name,kind,detail,lat,lon,rank,source) VALUES (?,?,?,?,?,?,?)',
                   (label, kind, f'{other} · {where}' if other else where, lat, lon, rank, 'OpenStreetMap'))
    db.execute("INSERT INTO place_fts(place_fts) VALUES ('rebuild')")
    db.commit()
    db.execute('VACUUM')
    db.close()
    return len(rows), outside


def build(args, box, root):
    """Read the extract and write the whole map set into root, an empty folder. Returns the build report."""
    t0 = time.time()
    pbf = Path(args.pbf)
    geo = root / 'derived' / 'geo'
    geo.mkdir(parents=True)
    header = osmium.io.Reader(str(pbf)).header()
    as_of = header.get('osmosis_replication_timestamp') or header.get('timestamp') or ''
    h = Region(box, args.prefer, args.boundary)
    h.apply_file(str(pbf), locations=True, idx='flex_mem')
    print('read', len(h.feats), 'features', len(h.pois), 'help points', len(h.places), 'places',
          len(h.coast), 'coast ways', round(time.time() - t0), 's', flush=True)
    boundary = None
    if args.boundary:
        if not h.boundary_rings:
            raise SystemExit(f'--boundary: relation {args.boundary} is not a complete boundary or multipolygon in {pbf.name}')
        boundary = Boundary(h.boundary_rings)

    meta = [('source', f'OpenStreetMap contributors, via {pbf.name} (ODbL 1.0)'), ('data_as_of', as_of),
            ('bounds', ','.join(f'{v:.6f}' for v in box)), ('region', args.id), ('region_name', args.name)]
    if args.boundary:
        meta.append(('boundary', f'OpenStreetMap relation {args.boundary}'))
    count, kinds = write_map(geo, h, box, meta, buildings=not args.no_buildings)
    nplaces, outside = write_places(geo, h, args.name, boundary)

    files = {f'derived/geo/{n}': (geo / n).stat().st_size for n in GEO_NAMES}
    (root / 'map-set.json').write_text(json.dumps({'name': args.id, 'files': files, 'bytes': sum(files.values())}, indent=1),
                                       encoding='utf-8')
    report = {
        'id': args.id, 'name': args.name, 'bbox': box, 'label_names': args.prefer,
        'source': {'file': pbf.name, 'bytes': pbf.stat().st_size, 'sha256': sha256(pbf), 'data_as_of': as_of,
                   'licence': 'ODbL 1.0', 'attribution': '© OpenStreetMap contributors'},
        'features': count, 'help_points': dict(sorted(kinds.items())), 'help_points_total': sum(kinds.values()),
        'place_finder_rows': nplaces,
        'files': {rel: {'bytes': size, 'sha256': sha256(root / rel)} for rel, size in files.items()},
        'not_built': ['addresses', 'terrain', 'crops', 'buildings.sqlite (outlines are in national.sqlite)', 'water.sqlite', 'atlas.sqlite'],
        'built': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'seconds': round(time.time() - t0)}
    if args.boundary:
        report['boundary'] = {'relation': args.boundary, 'place_finder_rows_inside': nplaces - outside,
                              'place_finder_rows_outside': outside}
    return report


def region_id(text):
    """--id becomes a folder name, so it must be exactly one: no separators, no '..', nothing hidden."""
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', text) or text.endswith('.'):
        raise argparse.ArgumentTypeError(
            f'{text!r} is not a single folder name: use letters, digits, "-", "_" and ".", starting with a letter or digit')
    return text


def bbox(text):
    try:
        box = [float(v) for v in text.split(',')]
    except ValueError:
        box = []
    if len(box) != 4 or not (box[0] < box[2] and box[1] < box[3]):
        raise argparse.ArgumentTypeError('must be west,south,east,north in degrees')
    return box


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('pbf', help='an OpenStreetMap extract (.osm.pbf), for example from download.geofabrik.de')
    ap.add_argument('--id', required=True, type=region_id, help='region id, for example TH-10; it names the output folder')
    ap.add_argument('--name', required=True, help='region name in plain words, for example Bangkok')
    ap.add_argument('--bbox', required=True, type=bbox, help='west,south,east,north in degrees')
    ap.add_argument('--out', required=True, help='folder for the output; <out>/<id> must not exist yet')
    ap.add_argument('--boundary', type=int, metavar='RELATION',
                    help="id of the region's OpenStreetMap boundary relation; place-finder rows outside it do not get --name")
    ap.add_argument('--prefer', choices=('local', 'en'), default='local',
                    help='which name is the map label when a feature has both (default: the local name)')
    ap.add_argument('--no-buildings', action='store_true', help='leave building outlines out (a smaller file)')
    args = ap.parse_args(argv)
    out = Path(args.out)
    root, report_path = out / args.id, out / f'{args.id}.build.json'
    if root.exists():
        sys.exit(f'{root} already exists. Choose another --out, or remove it yourself.')
    if not Path(args.pbf).is_file():
        sys.exit(f'{args.pbf} is not a file')
    out.mkdir(parents=True, exist_ok=True)
    # Everything is written to a temporary folder beside the destination (the same disk, so the last step is a
    # rename) and moved into place only after the whole build has succeeded. Whatever stops the build, the
    # temporary folder is removed and <out>/<id> does not exist, so the same command can be run again.
    work = Path(tempfile.mkdtemp(prefix=f'.{args.id}.building-', dir=out))
    try:
        report = build(args, args.bbox, work / 'map')
        (work / 'build.json').write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding='utf-8')
        try:
            os.rename(work / 'map', root)
        except OSError:
            sys.exit(f'{root} appeared while this build was running; it was left as it is.')
        os.replace(work / 'build.json', report_path)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print(json.dumps(report, indent=1, ensure_ascii=False))


if __name__ == '__main__':
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))  # a plain kill also cleans up, as Ctrl-C does
    main()
