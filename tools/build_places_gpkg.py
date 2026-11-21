#!/usr/bin/env python3
"""Build an offline place finder from Geofabrik GeoPackages already used for a map.

    python3 -B tools/build_places_gpkg.py extract.gpkg --out new/places.sqlite \
        --region 'Australia' --bbox=144.47,-38.32,145.48,-37.31

The box is west,south,east,north (longitude,latitude). Only named POINT places
are included. No street addresses, postcodes, alternate-language tags, polygons
or help-point classifications are inferred from the free GeoPackage schema.
Reads inputs without modifying them; refuses an existing output. No network or
spatial dependency. Output uses server.places()'s place/place_fts contract.
"""
import argparse
from contextlib import closing
import math
from pathlib import Path
import sqlite3
import struct
import tempfile

RANK = {'city': 1, 'national_capital': 1, 'town': 2, 'village': 3, 'hamlet': 4, 'locality': 4,
        'island': 4, 'suburb': 5, 'quarter': 5, 'neighbourhood': 5, 'farm': 5,
        'isolated_dwelling': 5, 'islet': 5}


def point(blob, srs_id):
    """OGC GeoPackageBinary header and 2D WKB Point; reject unsupported geometry."""
    if not blob or len(blob) < 8 or blob[:3] != b'GP\x00':
        raise ValueError('Invalid GeoPackage point header')
    flags = blob[3]
    if flags & 0xe0:
        raise ValueError('Extended or reserved GeoPackage geometry flags')
    if struct.unpack_from(('<' if flags & 1 else '>') + 'i', blob, 4)[0] != srs_id:
        raise ValueError('Point SRS differs from the declared layer SRS')
    if flags & 0x10:
        return None  # Empty geometries have no location to index.
    env = (flags >> 1) & 7
    if env not in {0, 1, 2, 3, 4}:
        raise ValueError('Invalid GeoPackage envelope')
    offset = 8 + {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}[env]
    if len(blob) != offset + 21 or blob[offset] not in (0, 1):
        raise ValueError('Expected a two-dimensional WKB point')
    order = '<' if blob[offset] == 1 else '>'
    if struct.unpack_from(order + 'I', blob, offset + 1)[0] != 1:
        raise ValueError('Expected a WKB point')
    lon, lat = struct.unpack_from(order + 'dd', blob, offset + 5)
    if not (math.isfinite(lon) and math.isfinite(lat) and -180 <= lon <= 180 and -90 <= lat <= 90):
        raise ValueError('Point is not a finite longitude/latitude')
    return lon, lat


def place_rows(path, region, bbox):
    with closing(sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)) as db:
        row = db.execute('''SELECT g.column_name,g.geometry_type_name,g.srs_id,s.organization,
            s.organization_coordsys_id,s.definition FROM gpkg_geometry_columns g
            JOIN gpkg_spatial_ref_sys s ON s.srs_id=g.srs_id
            WHERE g.table_name='gis_osm_places_free' ''').fetchone()
        if not row or row[0:2] != ('geom', 'POINT'):
            raise ValueError('Expected the Geofabrik gis_osm_places_free POINT layer')
        _, _, srs_id, org, code, definition = row
        crs84 = 'GEOGCS["WGS 84 (CRS84)"' in definition and 'AUTHORITY["OGC","CRS84"]' in definition
        if not ((org.upper() == 'EPSG' and code == 4326) or crs84):
            raise ValueError('Unsupported CRS; input must use WGS84 longitude/latitude')
        for name, kind, geom in db.execute('SELECT name,fclass,geom FROM gis_osm_places_free ORDER BY fid'):
            if not name or not name.strip() or kind not in RANK:
                continue
            xy = point(geom, srs_id)
            if xy is None:
                continue
            lon, lat = xy
            if bbox and not (bbox[0] <= lon <= bbox[2] and bbox[1] <= lat <= bbox[3]):
                continue
            yield name.strip(), kind, f'{region} (OpenStreetMap)', lat, lon, RANK[kind], 'OpenStreetMap'


def box(value):
    try:
        b = tuple(float(v) for v in value.split(','))
        if (len(b) != 4 or not all(math.isfinite(v) for v in b)
                or not (-180 <= b[0] < b[2] <= 180 and -90 <= b[1] < b[3] <= 90)):
            raise ValueError
        return b
    except ValueError:
        raise argparse.ArgumentTypeError('bbox must be west,south,east,north in degrees')


def build(inputs, output, region, bbox=None):
    output = Path(output).absolute()
    if output.exists():
        raise ValueError('Output already exists; choose a new file')
    if not region.strip():
        raise ValueError('A public region label is required')
    if bbox is not None:
        bbox = box(','.join(map(str, bbox)))
    output.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.places-', suffix='.sqlite', dir=output.parent)
    import os
    os.close(fd)
    staged = Path(name)
    try:
        with closing(sqlite3.connect(staged)) as db:
            db.executescript('''CREATE TABLE place(id INTEGER PRIMARY KEY,name TEXT,kind TEXT,detail TEXT,
                lat REAL,lon REAL,rank INTEGER,source TEXT,UNIQUE(name,kind,lat,lon));
                CREATE VIRTUAL TABLE place_fts USING fts5(name,detail,content='place',content_rowid='id',tokenize='unicode61');''')
            for source in inputs:
                db.executemany('INSERT OR IGNORE INTO place(name,kind,detail,lat,lon,rank,source) VALUES(?,?,?,?,?,?,?)',
                               place_rows(source, region, bbox))
            count = db.execute('SELECT COUNT(*) FROM place').fetchone()[0]
            if not count:
                raise ValueError('No named places in the requested coverage')
            db.execute("INSERT INTO place_fts(place_fts) VALUES('rebuild')")
            db.execute("INSERT INTO place_fts(place_fts) VALUES('integrity-check')")
            db.commit()
            if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('SQLite integrity check failed')
        staged.rename(output)
    finally:
        staged.unlink(missing_ok=True)
    return count


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('inputs', nargs='+', type=Path)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--region', required=True)
    ap.add_argument('--bbox', type=box)
    a = ap.parse_args()
    try:
        print(f'{build(a.inputs, a.out, a.region, a.bbox)} named places indexed')
    except (OSError, ValueError, sqlite3.Error, struct.error) as e:
        ap.exit(1, str(e) + '\n')


if __name__ == '__main__':
    main()
