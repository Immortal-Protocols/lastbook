"""Builds derived/geo/terrain.sqlite from IGN BD ALTI (France): the same elevation tiles as tools/build_terrain.py.

  python -I tools/build_terrain_bdalti.py --src DIR [DIR ...] --out derived/geo/terrain.sqlite [--bbox W,S,E,N] [--workers N]

Source: IGN BD ALTI v2, 25 m grid, ESRI ASCII (.asc) tiles of 1000 x 1000 cells, Lambert-93 (EPSG:2154), heights in
metres above NGF-IGN69. One 7z archive per departement; --src takes the extracted folders (searched recursively).
Licence Ouverte 2.0 (Etalab): name IGN and the edition date of each departement when the data is shown.

Output is identical in form to tools/build_terrain.py: 256 px web-mercator PNG tiles, zoom 4-12, "terrain-RGB"
(height_m = -10000 + (R*65536 + G*256 + B) * 0.1), tables tile / meta / done. Heights are read by bilinear
interpolation in the Lambert-93 grid at each web-mercator pixel centre. BD ALTI stores the sea as exactly 0 m and has
no NODATA cells inside its tiles; both 0 and NODATA are treated as "no source data", like the ocean in the US tool:
a tile with nothing else has no row, and sea pixels inside a coastal tile are written as 0 m.
Departement tiles overlap (a 25 km tile on a border is delivered whole with each departement); overlapping tiles
must hold the same heights and the first one read is kept.
"""
import argparse, math, os, re, sqlite3, sys, tempfile, time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_terrain import png, down, tile_lonlat, MAXZ, SUPERZ, MINZ, PX  # noqa: E402
from lambert93 import from_lonlat, to_lonlat  # noqa: E402

STEP = 25.0
GRID = None  # (heights memmap, centre x of column 0, centre y of row 0)


def read_asc(path):
    """ESRI ASCII grid -> (header dict, float32 array). Header keys are lower case."""
    with open(path, 'rb') as f:
        hdr = {}
        for _ in range(6):
            k, v = f.readline().split()
            hdr[k.decode().lower()] = float(v)
        a = np.array(f.read().split(), dtype=np.float32)
    return hdr, a.reshape(int(hdr['nrows']), int(hdr['ncols']))


def mosaic(srcs, keep_zero=False):
    """All .asc tiles under srcs -> (heights with NaN for no data, x of column 0 centre, y of row 0 centre, stats)."""
    tiles, seen = [], {}
    for root in srcs:
        for p in sorted(Path(root).rglob('*.asc')):
            hdr, a = read_asc(p)
            if hdr['cellsize'] != STEP:
                raise SystemExit(f'{p.name}: cell size {hdr["cellsize"]}, expected {STEP}')
            key = (hdr['xllcorner'], hdr['yllcorner'])
            if key in seen:
                if not np.array_equal(seen[key], a):
                    print(f'warning: {p.name} differs from a tile already read at the same place; keeping the first', flush=True)
                continue
            seen[key] = a
            tiles.append((hdr, a))
    if not tiles:
        raise SystemExit('no .asc tiles found')
    # ESRI "corner" = cell edge; BD ALTI cell centres fall on multiples of 25 m
    x0 = min(h['xllcorner'] for h, _ in tiles) + STEP / 2
    y0 = max(h['yllcorner'] + h['nrows'] * STEP for h, _ in tiles) - STEP / 2
    x1 = max(h['xllcorner'] + h['ncols'] * STEP for h, _ in tiles) - STEP / 2
    y1 = min(h['yllcorner'] for h, _ in tiles) + STEP / 2
    W, H = int(round((x1 - x0) / STEP)) + 1, int(round((y0 - y1) / STEP)) + 1
    out = np.full((H, W), np.nan, np.float32)
    nodata = zero = 0
    for h, a in tiles:
        a = a.copy()
        nd = a == h['nodata_value']
        z = (a == 0) & ~nd
        nodata += int(nd.sum()); zero += int(z.sum())
        a[nd] = np.nan
        if not keep_zero:
            a[z] = np.nan
        c = int(round((h['xllcorner'] + STEP / 2 - x0) / STEP))
        r = int(round((y0 - (h['yllcorner'] + h['nrows'] * STEP - STEP / 2)) / STEP))
        out[r:r + a.shape[0], c:c + a.shape[1]] = a
    return out, x0, y0, {'tiles': len(tiles), 'nodata_cells': nodata, 'zero_cells': zero, 'cols': W, 'rows': H}


def sample(lon, lat):
    """Bilinear heights (m) on the lon x lat grid; NaN where there is no source data (as in build_terrain.sample)."""
    a, x0, y0 = GRID
    H = np.full((lat.size, lon.size), np.nan, np.float32)
    for r in range(0, lat.size, 256):
        LO, LA = np.meshgrid(lon, lat[r:r + 256])
        x, y = from_lonlat(LO, LA)
        fc, fr = (x - x0) / STEP, (y0 - y) / STEP
        c0, r0 = np.floor(fc).astype(np.int64), np.floor(fr).astype(np.int64)
        ok = (c0 >= 0) & (c0 < a.shape[1] - 1) & (r0 >= 0) & (r0 < a.shape[0] - 1)
        if not ok.any():
            continue
        c0, r0, wc, wr = c0[ok], r0[ok], (fc[ok] - c0[ok]).astype(np.float32), (fr[ok] - r0[ok]).astype(np.float32)
        v = (a[r0, c0] * (1 - wr) * (1 - wc) + a[r0 + 1, c0] * wr * (1 - wc)
             + a[r0, c0 + 1] * (1 - wr) * wc + a[r0 + 1, c0 + 1] * wr * wc)
        blk = H[r:r + 256]
        blk[ok] = v
    return H


def supertile(key):
    """Every z8..z12 tile inside one z8 tile (as build_terrain.supertile). Returns (tiles, z8 heights, key)."""
    x8, y8 = key
    lon, lat = tile_lonlat(SUPERZ, x8, y8, PX)
    H = sample(lon, lat)
    if np.isnan(H).all():
        return [], None, key
    out = []
    for z in range(MAXZ, SUPERZ - 1, -1):
        n = 2 ** (z - SUPERZ)
        for j in range(n):
            for i in range(n):
                h = H[j * 256:(j + 1) * 256, i * 256:(i + 1) * 256]
                if not np.isnan(h).all():
                    out.append((z, x8 * n + i, y8 * n + j, png(h)))
        if z > SUPERZ:
            H = down(H)
    return out, H, key


def init(path, x0, y0):
    global GRID
    GRID = (np.load(path, mmap_mode='r'), x0, y0)


def tile_xy(lon, lat, z):
    n = 2 ** z
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n)
    return x, y


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--src', nargs='+', required=True, help='extracted BD ALTI folders (searched for *.asc)')
    ap.add_argument('--out', required=True, help='terrain.sqlite to create or resume')
    ap.add_argument('--bbox', help='W,S,E,N limit in degrees (default: every source tile)')
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--keep-zero', action='store_true', help='keep 0 m cells as land instead of treating them as sea')
    a = ap.parse_args()
    t0 = time.time()
    # edition dates from the delivery folder names (BDALTIV2_2-0_25M_ASC_LAMB93-IGN69_D014_2022-12-21)
    names = [p.name for s in a.src for p in [Path(s), *Path(s).iterdir()]]
    editions = sorted({m.groups() for m in (re.search(r'_D(\w{3})_(\d{4}-\d\d-\d\d)$', n) for n in names) if m})
    label ='IGN BD ALTI v2 25 m, Licence Ouverte 2.0' + (' (' + ', '.join(f'D{d} {e}' for d, e in editions) + ')' if editions else '')
    grid, x0, y0, stats = mosaic(a.src, a.keep_zero)
    print(f"{stats['tiles']} source tiles, grid {stats['cols']} x {stats['rows']} cells, "
          f"{stats['nodata_cells']:,} NODATA and {stats['zero_cells']:,} zero cells, {time.time() - t0:.0f}s", flush=True)
    # z8 supertiles touched by the grid: walk its outline in lon/lat (Lambert edges are not parallels or meridians)
    xs = x0 + np.linspace(0, (grid.shape[1] - 1) * STEP, 200)
    ys = y0 - np.linspace(0, (grid.shape[0] - 1) * STEP, 200)
    lon, lat = to_lonlat(np.r_[xs, xs, np.full(200, xs[0]), np.full(200, xs[-1])],
                         np.r_[np.full(200, ys[0]), np.full(200, ys[-1]), ys, ys])
    W, S, E, N = float(lon.min()), float(lat.min()), float(lon.max()), float(lat.max())
    if a.bbox:
        bw, bs, be, bn = map(float, a.bbox.split(','))
        W, S, E, N = max(W, bw), max(S, bs), min(E, be), min(N, bn)
    (xa, ya), (xb, yb) = tile_xy(W, N, SUPERZ), tile_xy(E, S, SUPERZ)
    keys = [(x, y) for y in range(ya, yb + 1) for x in range(xa, xb + 1)]
    if a.bbox:  # blank out what lies outside the box so tiles stop at it
        gx = x0 + np.arange(grid.shape[1]) * STEP
        for r in range(0, grid.shape[0], 500):
            LO, LA = to_lonlat(*np.meshgrid(gx, y0 - np.arange(r, min(r + 500, grid.shape[0])) * STEP))
            grid[r:r + 500][(LO < W) | (LO > E) | (LA < S) | (LA > N)] = np.nan
    work = tempfile.mkdtemp(prefix='bdalti-')
    path = os.path.join(work, 'grid.npy')
    np.save(path, grid)
    del grid
    db = sqlite3.connect(a.out)
    db.executescript('PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; CREATE TABLE IF NOT EXISTS tile(z INT, x INT, y INT, png BLOB, PRIMARY KEY(z,x,y)) WITHOUT ROWID;'
                     'CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);'
                     'CREATE TABLE IF NOT EXISTS done(x INT, y INT, h8 BLOB, PRIMARY KEY(x,y)) WITHOUT ROWID;')
    finished = {(x, y) for x, y in db.execute('SELECT x,y FROM done')}
    low = {(x, y): np.frombuffer(b, np.float32).reshape(256, 256) for x, y, b in db.execute('SELECT x,y,h8 FROM done WHERE h8 IS NOT NULL')}
    todo = [k for k in keys if k not in finished]
    print(f'{len(finished)} supertiles already built, {len(todo)} to go', flush=True)
    t1, done, ntiles = time.time(), 0, 0
    try:
        with ProcessPoolExecutor(a.workers, initializer=init, initargs=(path, x0, y0)) as pool:
            for f in as_completed([pool.submit(supertile, k) for k in todo]):
                tiles, h8, key = f.result()
                db.executemany('INSERT OR REPLACE INTO tile VALUES (?,?,?,?)', tiles)
                db.execute('INSERT OR REPLACE INTO done VALUES (?,?,?)', (*key, None if h8 is None else h8.astype(np.float32).tobytes()))
                ntiles += len(tiles); done += 1
                if h8 is not None:
                    low[key] = h8
                db.commit()
                print(f'{done + len(finished)}/{len(keys)} supertiles, {ntiles:,} tiles, {time.time() - t1:.0f}s', flush=True)
    finally:
        os.remove(path); os.rmdir(work)
    # zoom 7..4 from the z8 heights, as build_terrain.main
    level = low
    for z in range(SUPERZ - 1, MINZ - 1, -1):
        nxt = {}
        for (x, y) in {(x // 2, y // 2) for x, y in level}:
            q = np.full((512, 512), np.nan, np.float32)
            for dy in (0, 1):
                for dx in (0, 1):
                    h = level.get((2 * x + dx, 2 * y + dy))
                    if h is not None:
                        q[dy * 256:(dy + 1) * 256, dx * 256:(dx + 1) * 256] = h
            h = down(q)
            nxt[(x, y)] = h
            db.execute('INSERT OR REPLACE INTO tile VALUES (?,?,?,?)', (z, x, y, png(h)))
        level = nxt
    db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', ('built', time.strftime('%Y-%m-%dT%H:%M:%S')))
    db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', ('source', label))
    db.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', ('attribution', 'IGN, BD ALTI 25 m' + (' (' + ', '.join(f'D{d} {e}' for d, e in editions) + ')' if editions else '')))
    db.commit()
    print(f'done: {done} supertiles, {ntiles:,} tiles in {time.time() - t0:.0f}s', flush=True)


if __name__ == '__main__':
    main()
