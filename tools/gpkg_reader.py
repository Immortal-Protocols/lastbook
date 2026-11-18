"""Minimal GeoPackage reader for the IGN BD TOPO tools (tools/build_*_bdtopo.py), with no dependency beyond numpy.

A GeoPackage is a SQLite file; each geometry is a GeoPackage header followed by WKB. This module opens a package
read-only, decodes the header and the WKB (2D, Z, M and ZM; ISO and EWKB type codes) and keeps only x/y.
It also knows which BD TOPO file holds which department and can tell whether Lambert-93 points fall inside a
department outline, because the per-department BD TOPO files reach a few kilometres into their neighbours.

    from gpkg_reader import open_gpkg, geometry, DepartmentFilter
"""
import sqlite3, struct
from pathlib import Path

import numpy as np

# WKB base type -> name
POINT, LINESTRING, POLYGON, MULTIPOINT, MULTILINESTRING, MULTIPOLYGON, COLLECTION = 1, 2, 3, 4, 5, 6, 7


def open_gpkg(path):
    """Read-only connection to a GeoPackage (the file is never written)."""
    path = Path(path).resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    return sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)   # a plain f'file:{path}' breaks on '#', '%' and '?'


def geometry_column(db, table):
    return db.execute('SELECT column_name FROM gpkg_geometry_columns WHERE lower(table_name)=lower(?)', (table,)).fetchone()[0]


def columns(db, table):
    return [r[1] for r in db.execute(f'PRAGMA table_info("{table}")')]


def header(blob):
    """GeoPackage header -> (offset of the WKB, srs_id, envelope (minx, maxx, miny, maxy) or None, empty)."""
    if blob[:2] != b'GP':
        raise ValueError('not a GeoPackage geometry')
    flags = blob[3]
    bo = '<' if flags & 1 else '>'
    srs = struct.unpack_from(bo + 'i', blob, 4)[0]
    kind = (flags >> 1) & 7
    size = (0, 32, 48, 48, 64)[kind]
    env = struct.unpack_from(bo + '4d', blob, 8) if kind else None
    return 8 + size, srs, env, bool(flags & 0x10)


def _wkb(b, i, out):
    """Decode one WKB geometry at offset i into out as (base_type, parts); returns the new offset.
    Points and lines give an (n, 2) array; polygons give a list of rings, each an (n, 2) array (first ring outer)."""
    bo = '<' if b[i] == 1 else '>'
    t = struct.unpack_from(bo + 'I', b, i + 1)[0]
    i += 5
    if t & 0xE0000000:  # EWKB flags: Z 0x80000000, M 0x40000000, SRID 0x20000000
        dims = 2 + bool(t & 0x80000000) + bool(t & 0x40000000)
        if t & 0x20000000:
            i += 4
        base = t & 0xFF
    else:  # ISO: 1000 Z, 2000 M, 3000 ZM
        base, dims = t % 1000, 2 + (0, 1, 1, 2)[t // 1000]
    dt = np.dtype(bo + 'f8')
    if base == POINT:
        v = np.frombuffer(b, dt, dims, i)
        out.append((POINT, v[:2].reshape(1, 2).copy()))
        return i + 8 * dims
    if base == LINESTRING:
        n = struct.unpack_from(bo + 'I', b, i)[0]; i += 4
        v = np.frombuffer(b, dt, n * dims, i).reshape(n, dims)[:, :2]
        out.append((LINESTRING, v.copy()))
        return i + 8 * dims * n
    if base == POLYGON:
        nr = struct.unpack_from(bo + 'I', b, i)[0]; i += 4
        rings = []
        for _ in range(nr):
            n = struct.unpack_from(bo + 'I', b, i)[0]; i += 4
            rings.append(np.frombuffer(b, dt, n * dims, i).reshape(n, dims)[:, :2].copy())
            i += 8 * dims * n
        out.append((POLYGON, rings))
        return i
    if base in (MULTIPOINT, MULTILINESTRING, MULTIPOLYGON, COLLECTION):
        n = struct.unpack_from(bo + 'I', b, i)[0]; i += 4
        for _ in range(n):
            i = _wkb(b, i, out)
        return i
    raise ValueError(f'unsupported WKB geometry type {t}')


def geometry(blob):
    """GeoPackage blob -> list of (base_type, parts) for each simple part; [] for an empty or missing geometry."""
    if blob is None:
        return []
    off, _, _, empty = header(blob)
    if empty:
        return []
    out = []
    _wkb(blob, off, out)
    return out


def polygons(blob):
    """Every polygon in the blob as a list of rings (outer ring first)."""
    return [p for t, p in geometry(blob) if t == POLYGON]


def lines(blob):
    return [p for t, p in geometry(blob) if t == LINESTRING]


def point(blob):
    """First point of the geometry as (x, y), or None."""
    for t, p in geometry(blob):
        if t == POINT:
            return float(p[0, 0]), float(p[0, 1])
    return None


def ring_area(r):
    """Signed area of a ring in the units of its coordinates squared (positive when counter-clockwise)."""
    x, y = r[:, 0], r[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def bdtopo_package(folder):
    """The .gpkg inside an extracted BD TOPO archive folder (or the path itself if it is the .gpkg)."""
    p = Path(folder)
    if p.is_file():
        return p
    found = sorted(p.rglob('*.gpkg'))
    if len(found) != 1:
        raise SystemExit(f'{folder}: expected one .gpkg, found {len(found)}')
    return found[0]


class DepartmentFilter:
    """Tests whether Lambert-93 points fall inside the outlines of chosen departments.

    The outlines come from the `departement` table of the BD TOPO packages themselves. Edges are bucketed into
    horizontal bands so each point is tested by ray casting against only the edges that cross its band."""
    BAND = 200.0  # metres

    def __init__(self, packages, codes):
        self.codes = list(codes)
        edges = {c: [] for c in self.codes}
        seen = set()
        for path in packages:
            db = open_gpkg(path)
            gcol = geometry_column(db, 'departement')
            for code, blob in db.execute(f'SELECT code_insee, {gcol} FROM departement'):
                if code not in edges or code in seen:
                    continue
                seen.add(code)
                for rings in polygons(blob):
                    for r in rings:
                        edges[code].append(np.hstack([r[:-1], r[1:]]))
            db.close()
        missing = set(self.codes) - seen
        if missing:
            raise SystemExit(f'department outline not found for {sorted(missing)}')
        self.tables = {}
        for code, parts in edges.items():
            e = np.vstack(parts)
            e = e[e[:, 1] != e[:, 3]]  # horizontal edges never cross a horizontal ray
            y0, y1 = np.minimum(e[:, 1], e[:, 3]), np.maximum(e[:, 1], e[:, 3])
            b0 = np.floor(y0 / self.BAND).astype(np.int64); b1 = np.floor(y1 / self.BAND).astype(np.int64)
            reps = (b1 - b0 + 1)
            band = np.repeat(b0, reps) + (np.arange(reps.sum()) - np.repeat(np.cumsum(reps) - reps, reps))
            idx = np.repeat(np.arange(len(e)), reps)
            order = np.argsort(band, kind='stable')
            band, idx = band[order], idx[order]
            keys, starts = np.unique(band, return_index=True)
            ends = np.append(starts[1:], len(band))
            self.tables[code] = (e, {int(k): idx[s:t] for k, s, t in zip(keys, starts, ends)})
        self.bbox = {c: (t[0][:, [0, 2]].min(), t[0][:, [0, 2]].max(), t[0][:, [1, 3]].min(), t[0][:, [1, 3]].max())
                     for c, t in self.tables.items()}

    def _inside(self, code, x, y):
        e, bands = self.tables[code]
        res = np.zeros(len(x), bool)
        bx = np.floor(y / self.BAND).astype(np.int64)
        order = np.argsort(bx, kind='stable')
        keys, starts = np.unique(bx[order], return_index=True)
        ends = np.append(starts[1:], len(order))
        for k, s, t in zip(keys, starts, ends):
            ids = bands.get(int(k))
            if ids is None:
                continue
            ex0, ey0, ex1, ey1 = (e[ids, j][None, :] for j in range(4))
            step = max(1, 20_000_000 // len(ids))  # bound the points x edges matrix
            for c in range(s, t, step):
                sel = order[c:min(t, c + step)]
                px, py = x[sel][:, None], y[sel][:, None]
                cross = (ey0 > py) != (ey1 > py)
                with np.errstate(divide='ignore', invalid='ignore'):
                    xi = ex0 + (py - ey0) * (ex1 - ex0) / (ey1 - ey0)
                res[sel] = ((cross & (px < xi)).sum(axis=1) & 1).astype(bool)
        return res

    def which(self, x, y):
        """Department code for each point (empty string when outside all chosen departments)."""
        x = np.asarray(x, dtype='float64'); y = np.asarray(y, dtype='float64')
        out = np.full(len(x), '', dtype=object)
        for code in self.codes:
            x0, x1, y0, y1 = self.bbox[code]
            cand = np.flatnonzero((out == '') & (x >= x0) & (x <= x1) & (y >= y0) & (y <= y1))
            if len(cand):
                hit = self._inside(code, x[cand], y[cand])
                out[cand[hit]] = code
        return out
