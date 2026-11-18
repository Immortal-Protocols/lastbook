"""Builds derived/geo/buildings.sqlite for a French region from the IGN BD TOPO (table `batiment`), in the format
tools/build_buildings.py writes for the US, so server.py and the 3D view read it unchanged.

  python3 tools/build_buildings_bdtopo.py --out derived/geo/buildings.sqlite --departments 14,50,61 \
      [--osm basse-normandie-latest.osm.pbf] BDTOPO_D014_folder BDTOPO_D050_folder BDTOPO_D061_folder

Source: IGN BD TOPO v3.5 "tous thèmes" GeoPackage per department (Licence Ouverte 2.0, Lambert-93), extracted from
its .7z into a folder of its own; only read. A department file reaches a few kilometres into its neighbours, so a
building is kept when the centre of its outline lies inside one of --departments (outlines from the `departement`
table) and buildings seen in two files are kept once (same `cleabs`). Buildings recorded as "En projet" are left out.

Table bldg(x, y, part, n, data) as in tools/build_buildings.py: x/y = z14 tile holding the building's centre,
part = number of the source file on the command line, data = zlib(int32 array) of [npts, height_dm, X0, Y0, dX1, dY1,
...] in global z14 pixel coordinates scaled by 65536. Each polygon of a multipolygon becomes its own record (outer
ring only: courtyards are filled, as in the US build). Readers skip a record whose first point they have already
drawn (that is how they drop the copies of a big footprint), and terraced houses share corners, so each outline starts
at a corner no other outline starts at. Height, in decimetres: BD TOPO `hauteur` (metres, measured or
interpolated by IGN); else `nombre_d_etages` x 3.2 m + 1.5 m (the rule tools/build_osm_heights.py uses); else, with
--osm, the height of an OpenStreetMap building (height or building:levels, ODbL) whose outline contains the centre;
else 0, which the 3D view draws one storey tall. No bldg_osm table is written: in the 3D view OpenStreetMap outlines
replace the ones in `bldg`, and here those carry IGN's measured heights.
"""
import argparse, os, sqlite3, sys, time, zlib
from array import array
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gpkg_reader import POLYGON, DepartmentFilter, bdtopo_package, geometry, geometry_column, open_gpkg  # noqa: E402
from lambert93 import from_lonlat, to_lonlat  # noqa: E402

WORLD = 2 ** 30
REACH = 1 << 12  # same as tools/build_buildings.py: footprints reaching ~150 m into a neighbouring bucket are filed there too
STOREY, ROOF = 3.2, 1.5
CHUNK = 50000


def mercator(lon, lat):
    s = np.sin(np.radians(np.clip(lat, -85, 85)))
    X = np.floor((lon + 180) / 360 * WORLD).astype(np.int64)
    Y = np.floor((0.5 - np.log((1 + s) / (1 - s)) / (4 * np.pi)) * WORLD).astype(np.int64)
    return X, Y


class OsmHeights:
    """OpenStreetMap buildings with a height or storey count, indexed on a 100 m Lambert-93 grid."""
    CELL = 100.0

    def __init__(self, pbf):
        import osmium
        from build_osm_heights import metres
        self.grid, self.polys = {}, []
        fp = (osmium.FileProcessor(str(pbf), osmium.osm.NODE | osmium.osm.WAY).with_locations('flex_mem')
              .with_filter(osmium.filter.EntityFilter(osmium.osm.WAY))
              .with_filter(osmium.filter.KeyFilter('height', 'building:levels')))
        for w in fp:
            t = w.tags
            if 'building' not in t or 'building:part' in t:
                continue
            h, lv = metres(t.get('height')), metres(t.get('building:levels'))
            if h is None and lv is not None and 0 < lv <= 60:
                h = lv * STOREY + ROOF
            if h is None or not 2 <= h <= 200:
                continue
            nodes = w.nodes
            if len(nodes) < 4 or nodes[0].ref != nodes[-1].ref:
                continue
            try:
                ll = np.array([(n.lon, n.lat) for n in nodes])
            except osmium.InvalidLocationError:
                continue
            x, y = from_lonlat(ll[:, 0], ll[:, 1])
            k = len(self.polys)
            self.polys.append((np.asarray(x), np.asarray(y), h))
            for i in range(int(x.min() // self.CELL), int(x.max() // self.CELL) + 1):
                for j in range(int(y.min() // self.CELL), int(y.max() // self.CELL) + 1):
                    self.grid.setdefault((i, j), []).append(k)

    def height(self, px, py):
        for k in self.grid.get((int(px // self.CELL), int(py // self.CELL)), ()):
            x, y, h = self.polys[k]
            x1, y1 = np.roll(x, 1), np.roll(y, 1)
            c = (y > py) != (y1 > py)
            if c.any():
                xi = x + (py - y) * (x1 - x) / np.where(c, y1 - y, 1)
                if (c & (px < xi)).sum() & 1:
                    return h
        return None


def flush(chunk, depts, tiles, part, stats, osm, firsts):
    """chunk: list of (height_dm or None, storeys, ring (n,2) Lambert-93, centre x, centre y, first part of its building)."""
    cx = np.array([c[3] for c in chunk]); cy = np.array([c[4] for c in chunk])
    dep = depts.which(cx, cy)
    keep = [i for i in range(len(chunk)) if dep[i]]
    stats['outside'] += sum(1 for i in range(len(chunk)) if chunk[i][5] and not dep[i])
    if not keep:
        return
    rings = [chunk[i][2] for i in keep]
    sizes = np.array([len(r) for r in rings])
    starts = np.concatenate(([0], np.cumsum(sizes)[:-1]))
    allp = np.vstack(rings)
    lon, lat = to_lonlat(allp[:, 0], allp[:, 1])
    X, Y = mercator(lon, lat)
    minx, maxx = np.minimum.reduceat(X, starts), np.maximum.reduceat(X, starts)
    miny, maxy = np.minimum.reduceat(Y, starts), np.maximum.reduceat(Y, starts)
    bx, by = np.add.reduceat(X, starts) // sizes >> 16, np.add.reduceat(Y, starts) // sizes >> 16
    stats['records'] += len(keep)
    for k, i in enumerate(keep):
        h, storeys, _, px, py, first = chunk[i]
        src = 'hauteur'
        if h is None and storeys:
            h, src = int(round((storeys * STOREY + ROOF) * 10)), 'etages'
        if h is None and osm is not None:
            oh = osm.height(px, py)
            if oh is not None:
                h, src = int(round(oh * 10)), 'osm'
        if h is None:
            h, src = 0, 'none'
        if first:
            stats[src] += 1
            stats['dep:' + dep[i]] += 1
        s, n = starts[k], sizes[k]
        # readers drop a record whose first point they have already drawn (that is how they skip the copies of a big
        # footprint), and terraced houses share corners: start each outline at a corner no other outline starts at
        r = 0
        while r < n and (int(X[s + r]), int(Y[s + r])) in firsts:
            r += 1
        if r == n:  # every corner taken: start one unit (about 4 cm) off the first corner
            x0, y0 = int(X[s]) + 1, int(Y[s])
            while (x0, y0) in firsts:
                x0 += 1
            xs = [x0] + X[s + 1:s + n].tolist(); ys = [y0] + Y[s + 1:s + n].tolist()
            stats['nudged'] += 1
        else:
            xs = X[s + r:s + n].tolist() + X[s:s + r].tolist(); ys = Y[s + r:s + n].tolist() + Y[s:s + r].tolist()
            stats['rotated'] += r > 0
        firsts.add((xs[0], ys[0]))
        rec = array('i', (n, h, xs[0], ys[0]))
        for j in range(1, n):
            rec.append(xs[j] - xs[j - 1]); rec.append(ys[j] - ys[j - 1])
        keys = {(a, b) for a in range((minx[k] + REACH) >> 16, ((maxx[k] - REACH) >> 16) + 1)
                for b in range((miny[k] + REACH) >> 16, ((maxy[k] - REACH) >> 16) + 1)} | {(int(bx[k]), int(by[k]))}
        stats['copies'] += len(keys) - 1
        for key in keys:  # readers drop the copies of a big footprint by its first point
            t = tiles.get((key[0], key[1], part))
            if t is None:
                t = tiles[(key[0], key[1], part)] = [array('i'), 0]
            t[0].extend(rec); t[1] += 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('packages', nargs='+', help='extracted BD TOPO folders (or .gpkg files)')
    ap.add_argument('--out', required=True)
    ap.add_argument('--departments', default='14,50,61')
    ap.add_argument('--osm', help='OpenStreetMap .osm.pbf for heights the BD TOPO lacks')
    a = ap.parse_args()
    t0 = time.time()
    pkgs = [bdtopo_package(p) for p in a.packages]
    depts = DepartmentFilter(pkgs, a.departments.split(','))
    osm = None
    if a.osm:
        osm = OsmHeights(a.osm)
        print(f'OpenStreetMap: {len(osm.polys):,} buildings with a height, {time.time() - t0:.0f}s', flush=True)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix('.tmp')
    tmp.unlink(missing_ok=True)
    stats = {k: 0 for k in ('read', 'duplicate', 'project', 'empty', 'outside', 'hauteur', 'etages', 'osm', 'none', 'copies', 'records', 'rotated', 'nudged')}
    for d in depts.codes:
        stats['dep:' + d] = 0
    seen, tiles, editions, firsts = set(), {}, [], set()
    for part, pkg in enumerate(pkgs):
        db = open_gpkg(pkg)
        editions.append(pkg.stem)
        g = geometry_column(db, 'batiment')
        chunk = []
        for cleabs, etat, hauteur, etages, blob in db.execute(
                f'SELECT cleabs, etat_de_l_objet, hauteur, nombre_d_etages, {g} FROM batiment'):
            stats['read'] += 1
            if cleabs in seen:
                stats['duplicate'] += 1
                continue
            seen.add(cleabs)
            if etat == 'En projet':
                stats['project'] += 1
                continue
            h = int(round(hauteur * 10)) if isinstance(hauteur, (int, float)) and hauteur > 0 else None
            st = etages if isinstance(etages, int) and 0 < etages < 60 else 0
            polys = [p for t, p in geometry(blob) if t == POLYGON]
            outer = [p[0][:-1] if len(p[0]) > 1 and (p[0][0] == p[0][-1]).all() else p[0] for p in polys]
            outer = [r for r in outer if len(r) >= 3]
            if not outer:
                stats['empty'] += 1
                continue
            main_ring = max(outer, key=len)
            px, py = float(main_ring[:, 0].mean()), float(main_ring[:, 1].mean())
            for k, r in enumerate(outer):  # every part of a multipolygon, kept or dropped with the building's centre
                chunk.append((h, st, r, px, py, k == 0))
            if len(chunk) >= CHUNK:
                flush(chunk, depts, tiles, part, stats, osm, firsts); chunk = []
                if stats['read'] % 200000 < CHUNK:
                    print(f"{stats['read']:,} read, {time.time() - t0:.0f}s", flush=True)
        if chunk:
            flush(chunk, depts, tiles, part, stats, osm, firsts)
        db.close()
    db = sqlite3.connect(tmp)
    db.executescript('PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;'
                     'CREATE TABLE bldg(x INT, y INT, part INT, n INT, data BLOB, PRIMARY KEY(x,y,part)) WITHOUT ROWID;'
                     'CREATE TABLE done(file TEXT PRIMARY KEY, n INT);'
                     'CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);')
    db.executemany('INSERT INTO bldg VALUES (?,?,?,?,?)',
                   ((x, y, p, c, zlib.compress(buf.tobytes(), 6)) for (x, y, p), (buf, c) in sorted(tiles.items())))
    kept = sum(stats['dep:' + d] for d in depts.codes)
    db.executemany('INSERT INTO done VALUES (?,?)', [(Path(p).name, 0) for p in pkgs])   # the name only: a path names a machine and an account
    meta = {'buildings': str(kept), 'built': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'source': 'IGN BD TOPO v3.5 (Licence Ouverte 2.0): ' + ', '.join(editions)
                      + ('; heights the BD TOPO lacks from OpenStreetMap (ODbL)' if osm else ''),
            'height_sources': ', '.join(f'{k} {stats[k]}' for k in ('hauteur', 'etages', 'osm', 'none')),
            'departments': a.departments}
    db.executemany('INSERT INTO meta VALUES (?,?)', meta.items())
    db.commit()
    db.close()
    os.replace(tmp, out)
    print(' '.join(f'{k}={v:,}' for k, v in stats.items()))
    print(f'done: {kept:,} buildings ({stats["records"]:,} outlines) in {len(tiles):,} buckets, {time.time() - t0:.0f}s')


if __name__ == '__main__':
    main()
