#!/usr/bin/env python3
"""Validate staged Canada map/place databases without installing or modifying them.

Usage: python3 tools/validate_canada_map.py MAP.sqlite PLACES.sqlite
The full SQLite checks and lineage/index comparisons can take time on a country
extract. Geometry sampling is deterministic; --all-geometry checks every feature.
"""

import argparse
import json
from pathlib import Path
import sqlite3
import struct

try:
    from .merge_canada_places import canada_metadata, require, uri
except ImportError:
    from merge_canada_places import canada_metadata, require, uri


def unpack(blob):
    """Strict little-endian decoder; reject truncation and trailing bytes."""
    offset = 0

    def integer():
        nonlocal offset
        value = struct.unpack_from('<i', blob, offset)[0]
        offset += 4
        return value

    parts = []
    count = integer()
    require(0 < count <= len(blob) // 4, 'Invalid geometry part count')
    for _ in range(count):
        points, x, y = [], 0, 0
        length = integer()
        require(0 < length <= (len(blob) - offset) // 8, 'Invalid geometry point count')
        for _ in range(length):
            x += integer()
            y += integer()
            require(
                -180_000_000 <= x <= 180_000_000 and -90_000_000 <= y <= 90_000_000,
                'Geometry coordinate outside Earth',
            )
            points.append((x / 1e6, y / 1e6))
        parts.append(points)
    require(offset == len(blob), 'Trailing geometry bytes')
    return parts


def validate(map_path, places_path, all_geometry=False):
    db = sqlite3.connect(uri(map_path), uri=True)
    pdb = None
    try:
        pdb = sqlite3.connect(uri(places_path), uri=True)
        for conn in (db, pdb):
            conn.execute('PRAGMA query_only=ON')
            conn.execute('PRAGMA cache_size=-32768')
            require(
                conn.execute('PRAGMA integrity_check').fetchall() == [('ok',)],
                'SQLite integrity failure',
            )
        meta = dict(db.execute('SELECT key,value FROM meta'))
        pmeta = dict(pdb.execute('SELECT key,value FROM meta'))
        canada_metadata(meta)
        canada_metadata(pmeta)
        require(
            all(
                meta.get(k) == pmeta.get(k)
                for k in ('source', 'source_sha256', 'data_as_of')
            ),
            'Map/place source provenance differs',
        )
        for table, index, origin in [
            ('feat', 'feat_idx', 'feature_osm'),
            ('poi', None, 'poi_osm'),
        ]:
            count = db.execute(f'SELECT count(*) FROM {table}').fetchone()[0]
            require(count > 0, f'{table} is empty')
            for other in filter(None, (index, origin)):
                require(
                    db.execute(f'SELECT count(*) FROM {other}').fetchone()[0] == count,
                    f'{table}/{other} count differs',
                )
                require(
                    not db.execute(
                        f'SELECT 1 FROM {table} f LEFT JOIN {other} o USING(id) WHERE o.id IS NULL LIMIT 1'
                    ).fetchone(),
                    f'{other} contains missing IDs',
                )
            require(
                not db.execute(
                    f"SELECT 1 FROM {origin} WHERE osm_type NOT IN ('node','way','relation') "
                    'OR osm_type IS NULL OR osm_id IS NULL OR osm_id<=0 LIMIT 1'
                ).fetchone(),
                f'{origin} invalid lineage',
            )
        require(
            not db.execute(
                'SELECT 1 FROM feat_idx WHERE minx < -180 OR maxx > 180 OR miny < -90 '
                'OR maxy > 90 OR minx > maxx OR miny > maxy LIMIT 1'
            ).fetchone(),
            'Invalid RTree bounds',
        )
        require(
            not db.execute(
                'SELECT 1 FROM poi WHERE lon IS NULL OR lat IS NULL OR lon NOT BETWEEN -180 AND 180 '
                'OR lat NOT BETWEEN -90 AND 90 LIMIT 1'
            ).fetchone(),
            'Invalid POI coordinates',
        )
        require(
            not pdb.execute(
                'SELECT 1 FROM place WHERE name IS NULL OR trim(name)="" OR '
                'lon IS NULL OR lat IS NULL OR lon NOT BETWEEN -180 AND 180 '
                'OR lat NOT BETWEEN -90 AND 90 LIMIT 1'
            ).fetchone(),
            'Invalid place coordinates/name',
        )
        places = pdb.execute('SELECT count(*) FROM place').fetchone()[0]
        require(
            places > 0
            and pdb.execute('SELECT count(*) FROM place_osm').fetchone()[0] == places,
            'Missing place lineage',
        )
        require(
            not pdb.execute(
                'SELECT 1 FROM place p LEFT JOIN place_osm o USING(id) WHERE o.id IS NULL '
                "OR o.osm_type NOT IN ('node','way','relation') OR o.osm_type IS NULL "
                'OR o.osm_id IS NULL OR o.osm_id<=0 LIMIT 1'
            ).fetchone(),
            'Invalid place lineage',
        )
        # MATCH consults the actual FTS index (COUNT(*) alone reads external content).
        name = pdb.execute('SELECT name FROM place ORDER BY id LIMIT 1').fetchone()[0]
        term = '"' + name.replace('"', '""') + '"'
        require(
            pdb.execute(
                'SELECT 1 FROM place_fts WHERE place_fts MATCH ? LIMIT 1', (term,)
            ).fetchone(),
            'Place FTS index cannot find its first record',
        )
        total = db.execute('SELECT count(*) FROM feat').fetchone()[0]
        stride = 1 if all_geometry else max(1, total // 1000)
        checked = 0
        for fid, layer, blob, west, east, south, north in db.execute(
            'SELECT f.id,f.layer,f.geom,b.minx,b.maxx,b.miny,b.maxy FROM feat f JOIN feat_idx b USING(id) '
            'WHERE (f.id-1) % ? = 0 ORDER BY f.id',
            (stride,),
        ):
            parts = unpack(blob)
            for part in parts:
                if layer in ('water', 'wet', 'land', 'beach', 'bldg', 'island'):
                    require(
                        len(part) >= 4 and part[0] == part[-1],
                        f'Feature {fid}: unclosed polygon',
                    )
                for lon, lat in part:
                    # Geometry is quantized to 1e-6 degrees; the RTree stores float32.
                    require(
                        west - 1e-6 <= lon <= east + 1e-6
                        and south - 1e-6 <= lat <= north + 1e-6,
                        f'Feature {fid}: geometry outside RTree',
                    )
            checked += 1
        return {
            'state': 'VALIDATED_NOT_INSTALLED',
            'features': total,
            'pois': db.execute('SELECT count(*) FROM poi').fetchone()[0],
            'places': places,
            'geometry_checked': checked,
            'all_geometry': all_geometry,
            'meta': meta,
        }
    finally:
        db.close()
        if pdb is not None:
            pdb.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('map', type=Path)
    parser.add_argument('places', type=Path)
    parser.add_argument('--all-geometry', action='store_true')
    args = parser.parse_args()
    try:
        receipt = validate(args.map, args.places, args.all_geometry)
    except (ValueError, OSError, sqlite3.Error, struct.error) as error:
        parser.exit(1, f'Validation failed: {error}\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
