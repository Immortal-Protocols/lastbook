"""Builds derived/geo/crops.sqlite for France from the RPG: perennial food crops (orchards, vineyards, nuts, berries).

  python -I tools/build_crops_rpg.py --rpg RPG_Parcelles.gpkg --mask AREAS.gpkg --mask-names Calvados,Manche,Orne \
      --out derived/geo/crops.sqlite [--year 2025] [--report report.json]

Source: IGN / ASP Registre parcellaire graphique (RPG) v4.0, parcels declared for the CAP, one GeoPackage per region,
Lambert-93 (EPSG:2154), Licence Ouverte 2.0. Each parcel has a 3-letter crop code (code_cultu) and an area in hectares
(surf_parc). There is no departement field, so --mask keeps only parcels whose centroid falls inside the named polygons
of a GeoPackage layer (Lambert-93 or longitude/latitude).

Output is identical in form to tools/build_crops.py: clickable blocks (`resource` + `spatial`, 600 m Lambert-93 cells,
dominant crop and acreage; detail JSON {crop, crop_acres, perennial_acres, year}) and a colour overlay (`tile`, RGBA
PNG, zoom 7-13). Areas are summed from the declared hectares of each parcel and written in acres, as the US tool does.
The parcels are aggregated directly rather than rasterised first: block areas are then exact sums of the RPG, and the
overlay is drawn straight into web-mercator pixels (one resampling instead of two).
"""
import argparse, json, math, re, sqlite3, struct, sys, time
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_crops import CROPS as CDL_CROPS, KIND, BLOCK, MAXZ, MINZ, png_rgba, down  # noqa: E402
from lambert93 import from_lonlat, to_lonlat  # noqa: E402

ACRES_PER_HA = 10000 / 4046.8564224
CELL = 30.0 * BLOCK  # 600 m, the size of a US block (20 x 20 CDL pixels of 30 m)
US_MIN_HA = 20 * 900 / 10000  # build_crops keeps a block with at least 20 CDL pixels (1.8 ha) to drop satellite noise
MIN_HA = 0.0  # declared parcels carry no such noise: every block is kept (1,103 of 1,918 in Basse-Normandie 2025 are smaller)
SOURCE = 'https://geoservices.ign.fr/rpg'
# RPG 2025 code -> (Lastbook crop name, group of tools/build_crops.KIND). Names reuse the US list where the crop is the
# same, so the colours and the click lookup in web/map.js (CROP_RGB) still match. Only perennial food crops are kept,
# as in the US tool: annual crops, grassland, fodder, hops, nurseries, energy crops and flowers are left out.
CODES = {
    'VRG': ('Other tree crops', 'fruit'),   # Verger ("other orchard"): in Normandy mostly cider apples and perry pears
    'PWT': ('Pears', 'fruit'),              # Poire Williams pour transformation
    'PRU': ('Prunes', 'fruit'),             # Prune d'Ente pour transformation
    'CBT': ('Cherries', 'fruit'),           # Cerise bigarreau pour transformation
    'PVT': ('Peaches', 'fruit'),            # Pêche Pavie pour transformation
    'AGR': ('Citrus', 'citrus'),            # Agrumes
    'OLI': ('Olives', 'fruit'),             # Oliveraie
    'NOX': ('Walnuts', 'nut'),              # Noix
    'NOS': ('Hazelnuts', 'nut'),            # Noisette
    'CTG': ('Chestnuts', 'nut'),            # Châtaigne
    'VRC': ('Grapes', 'vine'),              # Vigne (except table grapes)
    'RAI': ('Grapes', 'vine'),              # Raisin de table
    'PFR': ('Berries', 'berry'),            # Petits fruits rouges (raspberries, currants, blueberries...)
    'FLP': ('Other perennial fruit & vegetables', 'veg'),  # Autre légume ou fruit pérenne
}
NEW_RGB = {'Hazelnuts': (160, 110, 60), 'Chestnuts': (110, 70, 30), 'Berries': (150, 30, 120),
           'Other perennial fruit & vegetables': (90, 160, 120)}
NAMES = sorted({c for c, _ in CODES.values()})
RGB = {name: rgb for name, _, rgb in CDL_CROPS.values()} | NEW_RGB
PALETTE = np.zeros((len(NAMES) + 1, 4), np.uint8)
for i, n in enumerate(NAMES, 1):
    PALETTE[i] = (*RGB[n], 190)


# ------------------------------------------------------------------ GeoPackage ----
def connect_ro(path):
    return sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro&immutable=1', uri=True)


def gpkg_polygons(g):
    """GeoPackage geometry blob -> list of polygons, each a list of (n, 2) float64 rings: the outline, then any holes.
    Polygons and multipolygons only; Z and M values are dropped."""
    if g is None or g[:2] != b'GP' or g[3] & 16:
        return []
    off = 8 + {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}[(g[3] >> 1) & 7]
    polys = []

    def walk(o):
        e = '<' if g[o] == 1 else '>'
        t = struct.unpack_from(e + 'I', g, o + 1)[0]
        base, dims = t % 1000, 2 + (t // 1000 in (1, 2)) + (t // 1000 == 3) * 2
        o += 5
        if base == 3:
            nr = struct.unpack_from(e + 'I', g, o)[0]; o += 4
            rings = []
            for _ in range(nr):
                n = struct.unpack_from(e + 'I', g, o)[0]
                a = np.frombuffer(g, np.dtype(e + 'f8'), n * dims, o + 4).reshape(n, dims)[:, :2]
                rings.append(a.astype(np.float64)); o += 4 + 8 * dims * n
            if rings:
                polys.append(rings)
            return o
        if base in (6, 7):
            n = struct.unpack_from(e + 'I', g, o)[0]; o += 4
            for _ in range(n):
                o = walk(o)
            return o
        raise ValueError(f'geometry type {t}')
    walk(off)
    return polys


def area_centroid(polys):
    """Area and area-weighted centroid of polygons: outlines count positive and holes negative, whatever the direction
    their vertices run in."""
    A = cx = cy = 0.0
    for rings in polys:
        for i, r in enumerate(rings):
            x, y = r[:, 0], r[:, 1]
            x1, y1 = np.roll(x, -1), np.roll(y, -1)
            c = x * y1 - x1 * y
            a = c.sum() / 2
            if a == 0:
                continue
            k = (1 if i == 0 else -1) * (1 if a > 0 else -1)
            A += k * a; cx += k * ((x + x1) * c).sum() / 6; cy += k * ((y + y1) * c).sum() / 6
    if A == 0:
        r = np.concatenate([r for rings in polys for r in rings])
        return 0.0, float(r[:, 0].mean()), float(r[:, 1].mean())
    return abs(A), cx / A, cy / A


def fill(rings, x0, y0, step, w, h, flip=True):
    """Even-odd scanline fill of rings into a (h, w) bool grid whose cell (r, c) has its centre at
    (x0 + (c + .5) * step, y0 - (r + .5) * step) if flip (north-up map grid), else y0 + (r + .5) * step (pixel grid)."""
    out = np.zeros((h, w), bool)
    xa = np.concatenate([r[:-1, 0] for r in rings]); ya = np.concatenate([r[:-1, 1] for r in rings])
    xb = np.concatenate([r[1:, 0] for r in rings]); yb = np.concatenate([r[1:, 1] for r in rings])
    lo, hi = np.minimum(ya, yb), np.maximum(ya, yb)
    for row in range(h):
        yc = y0 - (row + .5) * step if flip else y0 + (row + .5) * step
        m = (lo <= yc) & (hi > yc)
        if not m.any():
            continue
        t = (yc - ya[m]) / (yb[m] - ya[m])
        xs = np.sort(xa[m] + t * (xb[m] - xa[m]))
        for a, b in zip(xs[0::2], xs[1::2]):
            c0, c1 = max(0, math.ceil((a - x0) / step - .5)), min(w, math.ceil((b - x0) / step - .5))
            if c1 > c0:
                out[row, c0:c1] ^= True
    return out


# ------------------------------------------------------------------- the mask ----
MASK_STEP = 50.0


def load_mask(path, layer, names, name_col):
    """Polygons named `names` in a GeoPackage layer -> (label grid of 1..len(names), x0, y0) on a 50 m Lambert-93 grid."""
    db = connect_ro(path)
    srs = db.execute('SELECT srs_id FROM gpkg_geometry_columns WHERE table_name=?', (layer,)).fetchone()[0]
    defn = db.execute('SELECT organization, organization_coordsys_id, definition FROM gpkg_spatial_ref_sys WHERE srs_id=?', (srs,)).fetchone()
    lambert = defn[1] == 2154 or ('Lambert' in (defn[2] or '') and '93' in (defn[2] or ''))
    polys = {}
    for n in names:
        rows = db.execute(f'SELECT geom FROM "{layer}" WHERE "{name_col}"=?', (n,)).fetchall()
        if len(rows) != 1:
            raise SystemExit(f'mask: {len(rows)} polygons named {n!r} in {layer}')
        rings = [r for p in gpkg_polygons(rows[0][0]) for r in p]
        if not lambert:
            rings = [np.column_stack(from_lonlat(r[:, 0], r[:, 1])) for r in rings]
        polys[n] = rings
    allr = np.concatenate([r for rs in polys.values() for r in rs])
    x0 = math.floor(allr[:, 0].min() / MASK_STEP) * MASK_STEP
    y0 = math.ceil(allr[:, 1].max() / MASK_STEP) * MASK_STEP
    w = int(math.ceil((allr[:, 0].max() - x0) / MASK_STEP))
    h = int(math.ceil((y0 - allr[:, 1].min()) / MASK_STEP))
    lab = np.zeros((h, w), np.uint8)
    for i, n in enumerate(names, 1):
        lab[fill(polys[n], x0, y0, MASK_STEP, w, h) & (lab == 0)] = i
    return lab, x0, y0


def mask_label(mask, x, y):
    lab, x0, y0 = mask
    c = np.floor((np.asarray(x) - x0) / MASK_STEP).astype(int)
    r = np.floor((y0 - np.asarray(y)) / MASK_STEP).astype(int)
    ok = (c >= 0) & (c < lab.shape[1]) & (r >= 0) & (r < lab.shape[0])
    out = np.zeros(np.shape(x), np.uint8)
    out[ok] = lab[r[ok], c[ok]]
    return out


# ----------------------------------------------------------------- the parcels ----
def parcels(rpg, codes=None):
    """Yield (fid, code, group, declared ha, polygons) for RPG parcels, optionally only some crop codes."""
    db = connect_ro(rpg)
    q = 'SELECT fid, code_cultu, code_group, surf_parc, geom FROM RPG_Parcelles'
    args = ()
    if codes:
        q += ' WHERE code_cultu IN (%s)' % ','.join('?' * len(codes)); args = tuple(codes)
    for fid, code, group, ha, g in db.execute(q, args):
        yield fid, code, group, ha or 0.0, gpkg_polygons(g)


def merc_px(lon, lat, z):
    n = 256 * 2 ** z
    return (lon + 180) / 360 * n, (1 - np.log(np.tan(np.radians(lat)) + 1 / np.cos(np.radians(lat))) / math.pi) / 2 * n


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--rpg', required=True, help='RPG_Parcelles.gpkg')
    ap.add_argument('--mask', required=True, help='GeoPackage with the polygons of the area to keep')
    ap.add_argument('--mask-layer', default='gis_osm_adminareas_a_free')
    ap.add_argument('--mask-name-col', default='name')
    ap.add_argument('--mask-names', default='Calvados,Manche,Orne')
    ap.add_argument('--out', required=True)
    ap.add_argument('--year', type=int, default=2025)
    ap.add_argument('--min-ha', type=float, default=MIN_HA, help=f'smallest perennial area for a clickable block (default every block; the US tool uses {US_MIN_HA} ha)')
    ap.add_argument('--report', help='write per-code and per-area statistics (JSON) here')
    a = ap.parse_args()
    t0 = time.time()
    names = a.mask_names.split(',')
    mask = load_mask(a.mask, a.mask_layer, names, a.mask_name_col)
    print(f'mask: {mask[0].shape[1]} x {mask[0].shape[0]} cells of {MASK_STEP:.0f} m, {time.time() - t0:.0f}s', flush=True)

    # 1. every parcel: area by code inside and outside the mask (the report), and the kept perennial parcels
    stats = defaultdict(lambda: {'parcels': 0, 'ha': 0.0, 'ha_geom': 0.0})
    kept = []
    for fid, code, group, ha, polys in parcels(a.rpg):
        if not polys:
            continue
        area, cx, cy = area_centroid(polys)
        lab = int(mask_label(mask, cx, cy))
        where = names[lab - 1] if lab else 'outside'
        s = stats[(where, code, group)]
        s['parcels'] += 1; s['ha'] += ha; s['ha_geom'] += area / 1e4
        if where != 'outside' and code in CODES:
            kept.append((fid, code, ha, cx, cy, [r for p in polys for r in p]))
    print(f'{sum(s["parcels"] for s in stats.values()):,} parcels read, {len(kept):,} perennial food parcels kept, {time.time() - t0:.0f}s', flush=True)

    # 2. clickable blocks: declared hectares summed per 600 m cell (by parcel centroid), dominant crop by area
    cells = defaultdict(lambda: defaultdict(float))
    for fid, code, ha, cx, cy, rings in kept:
        cells[(int(cx // CELL), int(cy // CELL))][CODES[code][0]] += ha
    pts = []
    for (ix, iy), crops in cells.items():
        tot = sum(crops.values())
        if tot < a.min_ha:
            continue
        crop, ha = max(crops.items(), key=lambda kv: (kv[1], kv[0]))
        lon, lat = to_lonlat((ix + .5) * CELL, (iy + .5) * CELL)
        pts.append((crop, round(ha * ACRES_PER_HA, 1), round(tot * ACRES_PER_HA, 1), float(lon), float(lat), iy * 100000 + ix))

    # 3. overlay: parcels drawn into z13 web-mercator pixels (pixel centre inside the parcel; tiny parcels get the pixel
    # under their centroid so that none disappears)
    tiles = {}
    for fid, code, ha, cx, cy, rings in kept:
        v = NAMES.index(CODES[code][0]) + 1
        px = []
        for r in rings:
            lon, lat = to_lonlat(r[:, 0], r[:, 1])
            px.append(np.column_stack(merc_px(lon, lat, MAXZ)))
        allp = np.concatenate(px)
        c0, r0 = int(math.floor(allp[:, 0].min())), int(math.floor(allp[:, 1].min()))
        w, h = int(math.ceil(allp[:, 0].max())) - c0 + 1, int(math.ceil(allp[:, 1].max())) - r0 + 1
        m = fill([p - (c0, r0) for p in px], 0.0, 0.0, 1.0, w, h, flip=False)
        rr, cc = np.nonzero(m)
        if not rr.size:
            lon, lat = to_lonlat(cx, cy)
            gx, gy = merc_px(lon, lat, MAXZ)
            rr, cc = np.array([int(gy) - r0]), np.array([int(gx) - c0])
        gx, gy = cc + c0, rr + r0
        for tx, ty in set(zip((gx // 256).tolist(), (gy // 256).tolist())):
            sel = (gx // 256 == tx) & (gy // 256 == ty)
            t = tiles.setdefault((tx, ty), np.zeros((256, 256), np.uint8))
            t[gy[sel] % 256, gx[sel] % 256] = v
    print(f'{len(pts):,} clickable cells, {len(tiles):,} z{MAXZ} tiles, {time.time() - t0:.0f}s', flush=True)

    db = sqlite3.connect(a.out)
    db.executescript('''PRAGMA journal_mode=WAL; DROP TABLE IF EXISTS resource; DROP TABLE IF EXISTS spatial; DROP TABLE IF EXISTS tile;
      CREATE TABLE resource(id INTEGER PRIMARY KEY, source_id TEXT, kind TEXT, name TEXT, lat REAL, lon REAL, detail TEXT, source TEXT);
      CREATE INDEX resource_kind ON resource(kind);
      CREATE VIRTUAL TABLE spatial USING rtree(id, minx, maxx, miny, maxy);
      CREATE TABLE tile(z INT, x INT, y INT, png BLOB, PRIMARY KEY(z,x,y)) WITHOUT ROWID;
      CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);''')
    group = {n: g for n, g in CODES.values()}
    name = Path(a.rpg).name
    for crop, acres, total, lon, lat, cell in pts:
        cur = db.execute('INSERT INTO resource(source_id,kind,name,lat,lon,detail,source) VALUES (?,?,?,?,?,?,?)',
                         (f'{name}:{cell}', KIND[group[crop]], crop, lat, lon,
                          json.dumps({'crop': crop, 'crop_acres': acres, 'perennial_acres': total, 'year': a.year}), SOURCE))
        db.execute('INSERT INTO spatial VALUES (?,?,?,?,?)', (cur.lastrowid, lon, lon, lat, lat))
    db.commit()
    level = tiles
    count = {}
    for z in range(MAXZ, MINZ - 1, -1):
        for (x, y), v in level.items():
            db.execute('INSERT OR REPLACE INTO tile VALUES (?,?,?,?)', (z, x, y, png_rgba(PALETTE[v])))
        count[z] = len(level)
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
    db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', ('built', json.dumps({'cells': len(pts), 'year': a.year, 'states': len(names), 'at': time.strftime('%Y-%m-%dT%H:%M:%S')})))
    edition = re.search(r'_(\d{4}-\d\d-\d\d)', str(Path(a.rpg).resolve()))
    edition = f' (edition {edition[1]})' if edition else ''
    db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', ('source', f'IGN/ASP Registre parcellaire graphique {a.year}{edition}, Licence Ouverte 2.0'))
    db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', ('attribution', f'IGN/ASP, RPG {a.year}{edition}'))
    db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', ('area', f'{", ".join(names)} ({a.mask_layer} in {Path(a.mask).name})'))
    db.commit()
    print(f'done: {len(pts):,} clickable cells, tiles per zoom {count}, {time.time() - t0:.0f}s', flush=True)
    if a.report:
        out = [{'area': w, 'code': c, 'group': g, **{k: round(v, 4) if isinstance(v, float) else v for k, v in s.items()}}
               for (w, c, g), s in sorted(stats.items(), key=lambda kv: (kv[0][0], str(kv[0][2]), kv[0][1]))]
        Path(a.report).write_text(json.dumps({'mask': names, 'codes': {k: list(v) for k, v in CODES.items()},
                                              'stats': out, 'tiles': count, 'cells': len(pts)}, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
