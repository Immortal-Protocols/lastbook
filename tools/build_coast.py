#!/usr/bin/env python3
"""Add an ocean polygon to the offline map. The Geofabrik "free" GeoPackage has no coastline, so this reads
natural=coastline ways from the SoCal .osm.pbf (read only) with pyosmium, joins them into chains, and closes
the open mainland chain out to sea. Islands are stored as land rings drawn on top of the ocean.

  derived/buildenv/bin/python tools/build_coast.py library-data/geography/openstreetmap/socal-latest.osm.pbf derived/geo/map.sqlite

By default each open chain is closed straight out to longitude -125, which suits a coast facing west.

For any other coast, give a box (--box west,south,east,north): the ocean is the sea inside it. Every open chain is cut at
the box edge, and the pieces are joined by walking the edge clockwise (land lies left of a coastline's direction, so the
sea is on the right), the same way osmcoastline closes a cut coast. Closed rings (islands) are kept whole. Where an
extract's coastline stops inside the box (the coast goes on in a neighbouring extract), there is nothing to cut: give
the way through the sea from that end to the box edge with --end-via (from the chain's end) or --start-via (to the
chain's start), lon,lat points separated by semicolons, the last (or first) one on the edge. Coastlines from several
extracts are read together with --also; ways found in two of them are read once.

  python3 tools/build_coast.py basse-normandie-latest.osm.pbf national.sqlite --also guernsey-jersey-latest.osm.pbf \
    --box=-2.8,48.0,1.13,50.3 --end-via="-1.66,48.68;-1.80,48.75;-2.8,48.75" --start-via="0.0,50.3;0.0,49.47;0.10,49.44;0.22,49.44"

"""
import argparse, sqlite3
import osmium

ap = argparse.ArgumentParser(description='Add ocean and island polygons to an offline map database')
ap.add_argument('pbf', help='.osm.pbf extract (read only)')
ap.add_argument('dst', help='map database written by tools/build_map.py')
ap.add_argument('--also', action='append', default=[], help='another .osm.pbf whose coastline is read too (repeatable)')
ap.add_argument('--box', help='west,south,east,north: close the sea along this box instead of out to longitude -125')
ap.add_argument('--end-via', help='lon,lat;... sea points from the end of a chain that stops inside the box to the box edge')
ap.add_argument('--start-via', help='lon,lat;... sea points from the box edge to the start of a chain that starts inside the box')
ARGS = ap.parse_args()
PBF, DST = ARGS.pbf, ARGS.dst


class Coast(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.ways = []
        self.seen = set()

    def way(self, w):
        if w.tags.get('natural') == 'coastline' and w.id not in self.seen:
            try:
                self.ways.append(([n.ref for n in w.nodes], [(n.lon, n.lat) for n in w.nodes]))
                self.seen.add(w.id)
            except osmium.InvalidLocationError:
                pass


def chains(ways):
    by_start = {}
    for refs, pts in ways:
        by_start.setdefault(refs[0], []).append((refs, pts))
    used = set()
    out = []
    for refs, pts in ways:
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
    # join open chains whose start is another chain's end (pieces processed out of order)
    merged = True
    while merged:
        merged = False
        opens = [c for c in out if not c[0]]
        for a in opens:
            for b in opens:
                if a is not b and a[1][-1] == b[1][0]:
                    out.remove(a); out.remove(b)
                    out.append((a[1][0] == b[1][-1], a[1] + b[1][1:]))
                    merged = True
                    break
            if merged:
                break
    return out


def pack(parts):
    from array import array
    a = array('i', [len(parts)])
    for p in parts:
        a.append(len(p))
        lx = ly = 0
        for x, y in p:
            x, y = int(round(x * 1e6)), int(round(y * 1e6))
            a.append(x - lx); a.append(y - ly)
            lx, ly = x, y
    return a.tobytes()


def points(text):
    return [tuple(float(v) for v in pt.split(',')) for pt in (text or '').split(';') if pt.strip()]


def clip(chain, box):
    """Pieces of a line inside the box; a piece that leaves the box ends on its edge, one that enters starts on it."""
    w, s, e, n = box
    pieces, cur = [], None
    for (x0, y0), (x1, y1) in zip(chain, chain[1:]):
        t0, t1, dx, dy = 0.0, 1.0, x1 - x0, y1 - y0
        ok = True
        for p, q in ((-dx, x0 - w), (dx, e - x0), (-dy, y0 - s), (dy, n - y0)):   # Liang-Barsky
            if p == 0:
                ok = ok and q >= 0
            elif p < 0:
                t0 = max(t0, q / p)
            else:
                t1 = min(t1, q / p)
        if not ok or t0 > t1:
            cur = None
            continue
        a = (x0 + t0 * dx, y0 + t0 * dy) if t0 > 0 else (x0, y0)
        b = (x0 + t1 * dx, y0 + t1 * dy) if t1 < 1 else (x1, y1)
        if cur is None or cur[-1] != a:
            cur = [a]
            pieces.append(cur)
        cur.append(b)
        if t1 < 1:
            cur = None
    return pieces


def edge_t(pt, box):
    """Distance along the box edge, clockwise from the south-west corner (west edge up, north east, east down, south west)."""
    w, s, e, n = box
    x, y = pt
    d = [abs(x - w), abs(y - n), abs(x - e), abs(y - s)]
    side = d.index(min(d))
    if min(d) > 1e-6:
        raise SystemExit(f'{pt} is not on the edge of the box: give --end-via / --start-via to reach it')
    return [y - s, (n - s) + (x - w), (n - s) + (e - w) + (n - y), 2 * (n - s) + (e - w) + (e - x)][side]


def close_in_box(opened, box):
    """Ocean rings: coastline pieces inside the box, joined along its edge clockwise."""
    w, s, e, n = box
    per = 2 * ((n - s) + (e - w))
    corners = [(0.0, (w, s)), (n - s, (w, n)), ((n - s) + (e - w), (e, n)), (2 * (n - s) + (e - w), (e, s))]
    pieces = [p for c in opened for p in clip(c, box) if len(p) > 1]
    starts = [edge_t(p[0], box) for p in pieces]
    rings, left = [], set(range(len(pieces)))
    while left:
        i = min(left)
        ring = []
        while i in left:
            left.discard(i)
            ring += pieces[i]
            t = edge_t(pieces[i][-1], box)
            j = min(range(len(pieces)), key=lambda k: (starts[k] - t) % per)   # next coast entering the box, clockwise
            gap = (starts[j] - t) % per
            ring += [pt for ct, pt in sorted(corners, key=lambda c: (c[0] - t) % per) if 0 < (ct - t) % per < gap]
            i = j
        rings.append(ring + [ring[0]])
    return rings


h = Coast()
h.apply_file(PBF, locations=True, idx='flex_mem')
for extra in ARGS.also:
    h.apply_file(extra, locations=True, idx='flex_mem')
cs = chains(h.ways)
closed = [p for c, p in cs if c]
opened = sorted([p for c, p in cs if not c], key=len, reverse=True)
print('coast ways', len(h.ways), 'closed rings', len(closed), 'open chains', [len(p) for p in opened[:5]])
db = sqlite3.connect(DST)
db.execute("DELETE FROM feat_idx WHERE id IN (SELECT id FROM feat WHERE layer IN ('ocean','island'))")
db.execute("DELETE FROM feat WHERE layer IN ('ocean','island')")
nid = db.execute('SELECT max(id) FROM feat').fetchone()[0] + 1
W = -125.0  # well out to sea
rings = []
if ARGS.box:
    box = [float(v) for v in ARGS.box.split(',')]
    # the spurs belong to the longest open chain (the mainland), the one whose ends may stop inside the box
    ends = [points(ARGS.start_via) + p + points(ARGS.end_via) if i == 0 else p for i, p in enumerate(opened)]
    rings = close_in_box(ends, box)
else:
    for p in opened:
        # land is on the left of coastline direction; close each open chain through the sea to the west.
        rings.append(p + [(W, p[-1][1]), (W, p[0][1]), p[0]])
for ring in rings:
    xs = [x for x, _ in ring]; ys = [y for _, y in ring]
    db.execute('INSERT INTO feat VALUES (?,?,?,?,?,?)', (nid, 'ocean', 'ocean', None, 0, pack([ring])))
    db.execute('INSERT INTO feat_idx VALUES (?,?,?,?,?,?,?)', (nid, min(xs), max(xs), min(ys), max(ys), 0, 30))
    nid += 1
for ring in closed:
    xs = [x for x, _ in ring]; ys = [y for _, y in ring]
    # OSM closed coastline rings around land run counter-clockwise; water "holes" (lakes on islands) are rare here.
    db.execute('INSERT INTO feat VALUES (?,?,?,?,?,?)', (nid, 'island', 'island', None, 0, pack([ring])))
    db.execute('INSERT INTO feat_idx VALUES (?,?,?,?,?,?,?)', (nid, min(xs), max(xs), min(ys), max(ys), 0, 30))
    nid += 1
db.commit()
print('stored', len(rings), 'ocean rings', len(closed), 'islands')
