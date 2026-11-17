#!/usr/bin/env python3
"""Orchards and vineyards for places the USDA Cropland Data Layer does not cover, from OpenStreetMap: derived/geo/crops.sqlite.

  python3 tools/build_crops_osm.py england.gpkg derived/geo/crops.sqlite --bbox=-6.57,49.71,-1.33,52.27

Input is a Geofabrik free GeoPackage (OpenStreetMap, ODbL), the same file tools/build_map.py reads; it keeps the landuse
areas tagged orchard and vineyard inside the box. Writes the tables tools/build_crops.py writes, so the app reads it
unchanged:
  resource + spatial   one clickable point per mapped area: its name if OpenStreetMap has one, its kind, and its size in hectares
  tile                 the colour overlay, RGBA PNG, zoom 7-13, drawn from the outlines
  meta                 'built' with the number of areas and the source

OpenStreetMap does not say what grows in an orchard, so every orchard is simply 'Orchard' (and a vineyard 'Grapes'), and
a person has mapped each one: some are missing, and some are old. Berries and other crops are not mapped here. The
check this needs on the page is in web/map.js ("Mapped in OpenStreetMap"). Needs numpy and Pillow on the build machine.
"""
import argparse, json, math, sqlite3, struct, sys, time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_crops import down, png_rgba          # noqa: E402  the overlay pyramid is shared with the US builder
from build_water import inside_point, ring_area_km2   # noqa: E402

MAXZ, MINZ = 13, 7
KINDS = {'orchard': ('orchard', 'Orchard', 1, (45, 160, 110)), 'vineyard': ('vineyard', 'Grapes', 2, (120, 50, 150))}
PALETTE = np.zeros((3, 4), np.uint8)
for _k, _name, _code, _rgb in KINDS.values():
    PALETTE[_code] = (*_rgb, 190)


def polygons(g):
    """GeoPackage geometry -> list of polygons, each a list of rings (the first is the outline, the rest are holes) of (lon, lat)."""
    start = 8 + {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}[(g[3] >> 1) & 7]

    def polygon(o):
        e = '<' if g[o] == 1 else '>'
        nr = struct.unpack_from(e + 'I', g, o + 5)[0]
        o += 9
        rings = []
        for _ in range(nr):
            n = struct.unpack_from(e + 'I', g, o)[0]
            vals = struct.unpack_from(e + '%dd' % (2 * n), g, o + 4)
            rings.append(list(zip(vals[0::2], vals[1::2])))
            o += 4 + 16 * n
        return rings, o

    e = '<' if g[start] == 1 else '>'
    kind = struct.unpack_from(e + 'I', g, start + 1)[0] % 1000
    if kind == 3:
        return [polygon(start)[0]]
    out = []
    if kind == 6:
        o = start + 9
        for _ in range(struct.unpack_from(e + 'I', g, start + 5)[0]):
            rings, o = polygon(o)
            out.append(rings)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('out')
    ap.add_argument('--bbox', required=True, help='W,S,E,N (use --bbox=... when the west value is negative)')
    ap.add_argument('--source', default='OpenStreetMap contributors (ODbL)')
    a = ap.parse_args()
    west, south, east, north = map(float, a.bbox.split(','))
    t0 = time.time()
    src = sqlite3.connect(f'file:{a.src}?mode=ro', uri=True)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)
    db = sqlite3.connect(out)
    db.executescript('''PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;
      CREATE TABLE resource(id INTEGER PRIMARY KEY, source_id TEXT, kind TEXT, name TEXT, lat REAL, lon REAL, detail TEXT, source TEXT);
      CREATE INDEX resource_kind ON resource(kind);
      CREATE VIRTUAL TABLE spatial USING rtree(id, minx, maxx, miny, maxy);
      CREATE TABLE tile(z INT, x INT, y INT, png BLOB, PRIMARY KEY(z,x,y)) WITHOUT ROWID;
      CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);''')
    nz = 2 ** MAXZ
    tiles, count = {}, 0
    for osm_id, fclass, name, g in src.execute("SELECT osm_id, fclass, name, geom FROM gis_osm_landuse_a_free WHERE fclass IN ('orchard','vineyard')"):
        if g is None:
            continue
        if (g[3] >> 1) & 7 == 1:
            minx, maxx, miny, maxy = struct.unpack_from('<4d' if g[3] & 1 else '>4d', g, 8)
            if maxx < west or minx > east or maxy < south or miny > north:
                continue
        kind, crop, code, _ = KINDS[fclass]
        try:
            polys = polygons(g)
        except Exception:
            continue
        hectares = 0.0
        biggest = None
        for rings in polys:
            hectares += (ring_area_km2(rings[0]) - sum(ring_area_km2(r) for r in rings[1:])) * 100
            if biggest is None or ring_area_km2(rings[0]) > ring_area_km2(biggest):
                biggest = rings[0]
        if not biggest or len(biggest) < 4:
            continue
        lon, lat = inside_point(biggest)
        if not (west <= lon <= east and south <= lat <= north):
            continue
        count += 1
        cur = db.execute('INSERT INTO resource(source_id,kind,name,lat,lon,detail,source) VALUES (?,?,?,?,?,?,?)',
                         (f'osm:{osm_id}', kind, name or crop, round(lat, 6), round(lon, 6),
                          json.dumps({'crop': crop, 'crop_ha': round(max(hectares, 0.01), 2), 'source_map': 'OpenStreetMap'}),
                          f'https://www.openstreetmap.org/way/{osm_id}'))
        db.execute('INSERT INTO spatial VALUES (?,?,?,?,?)', (cur.lastrowid, lon, lon, lat, lat))
        # the overlay: draw this area on every zoom-13 tile its box touches
        px = lambda lo: (lo + 180) / 360 * nz
        py = lambda la: (1 - math.asinh(math.tan(math.radians(la))) / math.pi) / 2 * nz
        for rings in polys:
            xs = [px(p[0]) for p in rings[0]]
            ys = [py(p[1]) for p in rings[0]]
            for tx in range(int(min(xs)), int(max(xs)) + 1):
                for ty in range(int(min(ys)), int(max(ys)) + 1):
                    mask = Image.new('L', (256, 256), 0)
                    d = ImageDraw.Draw(mask)
                    for i, ring in enumerate(rings):
                        pts = [((px(p[0]) - tx) * 256, (py(p[1]) - ty) * 256) for p in ring]
                        if len(pts) >= 3:
                            d.polygon(pts, fill=255 if i == 0 else 0)
                    m = np.asarray(mask) > 0
                    if m.any():
                        t = tiles.setdefault((tx, ty), np.zeros((256, 256), np.uint8))
                        t[m] = code
    db.commit()
    level = tiles
    for z in range(MAXZ, MINZ - 1, -1):
        for (x, y), v in level.items():
            db.execute('INSERT OR REPLACE INTO tile VALUES (?,?,?,?)', (z, x, y, png_rgba(PALETTE[v])))
        if z > MINZ:
            nxt = {}
            for (x, y) in {(x // 2, y // 2) for x, y in level}:
                q = np.zeros((512, 512), np.uint8)
                for dy in (0, 1):
                    for dx in (0, 1):
                        v = level.get((2 * x + dx, 2 * y + dy))
                        if v is not None:
                            q[dy * 256:(dy + 1) * 256, dx * 256:(dx + 1) * 256] = v
                nxt[(x, y)] = down(q)
            level = nxt
        db.commit()
    db.execute('INSERT INTO meta VALUES (?,?)', ('built', json.dumps({'cells': count, 'source': a.source, 'at': time.strftime('%Y-%m-%dT%H:%M:%S')})))
    db.commit()
    db.close()
    print(f'done: {count:,} orchards and vineyards, {len(tiles):,} detailed tiles, {time.time() - t0:.0f}s', flush=True)


if __name__ == '__main__':
    main()
