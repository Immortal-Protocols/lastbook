#!/usr/bin/env python3
"""Merge into a NEW staged database, never the installed Medium database.

The caller must supply a SHA256 from an independently trusted pristine base
manifest (not a digest freshly calculated from an Ontario-augmented database).
All checks run against a sibling temporary file. A hard link publishes the fully
closed file atomically without replacing any existing path. The receipt lives in
meta['canada.merge_receipt'] and stdout, avoiding a non-atomic DB/sidecar pair.
"""

import argparse
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import time

SOURCE = 'OpenStreetMap Canada'
COLUMNS = 'id,name,kind,detail,lat,lon,rank,source'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def uri(path):
    require(path.is_file(), f'Input is not a file: {path}')
    wal = Path(str(path) + '-wal')
    require(
        not wal.exists() or wal.stat().st_size == 0,
        f'Input must be a finished standalone SQLite database (nonempty WAL): {path}',
    )
    return path.resolve().as_uri() + '?mode=ro'


def integrity(db, schema='main'):
    require(
        db.execute(f'PRAGMA {schema}.integrity_check').fetchall() == [('ok',)],
        f'{schema}: SQLite integrity check failed',
    )


def has_table(db, schema, name):
    return (
        db.execute(
            f'SELECT 1 FROM {schema}.sqlite_master WHERE type="table" AND name=?',
            (name,),
        ).fetchone()
        is not None
    )


def metadata(db, schema):
    return (
        dict(db.execute(f'SELECT key,value FROM {schema}.meta'))
        if has_table(db, schema, 'meta')
        else {}
    )


def pristine(db):
    # Inspect provenance, NOT names/details: pristine US places may be named Ontario.
    require(
        not db.execute(
            "SELECT 1 FROM place WHERE lower(coalesce(source,'')) "
            "LIKE '%ontario%' OR lower(coalesce(source,'')) LIKE '%canada%' LIMIT 1"
        ).fetchone(),
        'Base is not pristine base: Ontario/Canada place provenance found',
    )
    for key, value in metadata(db, 'main').items():
        require(
            not re.search('ontario|canada', f'{key} {value}', re.I),
            'Base is not pristine base: Ontario/Canada metadata provenance found',
        )
    require(
        not db.execute(
            "SELECT 1 FROM sqlite_master WHERE lower(name) LIKE '%canada%' "
            "OR lower(name) LIKE '%ontario%' LIMIT 1"
        ).fetchone(),
        'Base is not pristine base: Ontario/Canada schema provenance found',
    )


def canada_metadata(meta):
    require(
        'canada' in meta.get('source', '').lower(), 'Missing Canada source provenance'
    )
    require(
        re.fullmatch(r'[a-fA-F0-9]{64}', meta.get('source_sha256', '')),
        'Missing valid Canada extract SHA256',
    )
    try:
        stamp = datetime.datetime.fromisoformat(
            meta.get('data_as_of', '').replace('Z', '+00:00')
        )
        require(stamp.tzinfo is not None, 'Canada data date requires timezone')
    except ValueError as error:
        raise ValueError('Missing valid Canada data_as_of timestamp') from error


def merge(args):
    base, incoming, dest = args.base, args.incoming, args.dest
    require(
        re.fullmatch(r'[a-fA-F0-9]{64}', args.base_sha256),
        'Invalid trusted base SHA256',
    )
    require(not os.path.lexists(dest), f'Destination already exists: {dest}')
    base_uri, incoming_uri = uri(base), uri(incoming)
    require(
        digest(base) == args.base_sha256.lower(),
        'Base SHA256 does not match trusted pristine base digest',
    )
    # Validate provenance before even creating the private staging file.
    source = sqlite3.connect(base_uri, uri=True)
    try:
        pristine(source)
    finally:
        source.close()
    fd, temporary = tempfile.mkstemp(
        prefix=f'.{dest.name}.', suffix='.staging', dir=dest.parent
    )
    os.close(fd)
    stage = Path(temporary)
    out = None
    try:
        out = sqlite3.connect(stage, uri=True)
        source = sqlite3.connect(base_uri, uri=True)
        try:
            source.backup(out)
        finally:
            source.close()
        out.execute('PRAGMA journal_mode=DELETE')
        out.execute('PRAGMA synchronous=FULL')
        pristine(out)
        integrity(out)
        out.execute('ATTACH DATABASE ? AS baseline', (base_uri,))
        out.execute('ATTACH DATABASE ? AS ca', (incoming_uri,))
        out.execute('BEGIN')
        integrity(out, 'ca')
        meta = metadata(out, 'ca')
        canada_metadata(meta)
        expected = out.execute('SELECT count(*) FROM ca.place').fetchone()[0]
        require(expected > 0, 'Canada places database is empty')
        require(
            not out.execute(
                'SELECT 1 FROM ca.place WHERE id<=0 OR source IS NOT ? OR '
                'name IS NULL OR trim(name)="" OR lat IS NULL OR lon IS NULL OR '
                'lat NOT BETWEEN -90 AND 90 OR lon NOT BETWEEN -180 AND 180 LIMIT 1',
                (SOURCE,),
            ).fetchone(),
            'Invalid Canada place row/source',
        )
        require(
            out.execute('SELECT count(*) FROM ca.place_osm').fetchone()[0] == expected
            and not out.execute(
                'SELECT 1 FROM ca.place p LEFT JOIN ca.place_osm o ON o.id=p.id '
                "WHERE o.id IS NULL OR o.osm_type NOT IN ('node','way','relation') "
                'OR o.osm_type IS NULL OR o.osm_id IS NULL OR o.osm_id<=0 LIMIT 1'
            ).fetchone(),
            'Canada place_osm lineage missing or invalid',
        )
        old = out.execute('SELECT count(*) FROM place').fetchone()[0]
        offset = max(
            0, out.execute('SELECT coalesce(max(id),0) FROM place').fetchone()[0]
        )
        out.execute(
            'CREATE TABLE IF NOT EXISTS place_osm(id INTEGER PRIMARY KEY,osm_type TEXT,osm_id INTEGER)'
        )
        out.execute('CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT)')
        out.execute(
            'CREATE TABLE canada_place_origin(id INTEGER PRIMARY KEY,place_id INTEGER,feature_id INTEGER)'
        )
        out.execute(
            f'INSERT INTO place({COLUMNS}) SELECT id+?,name,kind,detail,lat,lon,rank,source FROM ca.place',
            (offset,),
        )
        out.execute(
            'INSERT INTO place_osm SELECT id+?,osm_type,osm_id FROM ca.place_osm',
            (offset,),
        )
        out.execute(
            'INSERT INTO canada_place_origin SELECT id+?,id,NULL FROM ca.place',
            (offset,),
        )
        out.executemany(
            'INSERT INTO meta VALUES(?,?)',
            [('canada.' + k, v) for k, v in meta.items()],
        )
        out.execute(
            'CREATE INDEX IF NOT EXISTS place_osm_object ON place_osm(osm_type,osm_id)'
        )
        water_count = 0
        if args.canada_map:
            require(
                not args.canada_map.name.endswith(('.building', '.staging')),
                'Canada map must be finished',
            )
            out.execute('ATTACH DATABASE ? AS camap', (uri(args.canada_map),))
            integrity(out, 'camap')
            map_meta = metadata(out, 'camap')
            canada_metadata(map_meta)
            require(
                all(
                    map_meta.get(k) == meta.get(k)
                    for k in ('source_sha256', 'data_as_of', 'source')
                ),
                'Canada map provenance does not match Canada places',
            )
            out.executemany(
                'INSERT INTO meta VALUES(?,?)',
                [('canada.map.' + k, v) for k, v in map_meta.items()],
            )
            candidates = """SELECT f.id,f.name,f.cls,b.minx,b.maxx,b.miny,b.maxy,o.osm_type,o.osm_id
                FROM camap.feat f LEFT JOIN camap.feat_idx b ON b.id=f.id
                LEFT JOIN camap.feature_osm o ON o.id=f.id
                WHERE (f.layer='water' OR (f.layer='waterway' AND f.cls!='coastline'))
                AND f.name IS NOT NULL AND trim(f.name)!='' ORDER BY f.id"""
            for fid, name, cls, x1, x2, y1, y2, osm_type, osm_id in out.execute(
                candidates
            ):
                require(
                    osm_type in ('node', 'way', 'relation')
                    and isinstance(osm_id, int)
                    and osm_id > 0,
                    f'Invalid named-water lineage: feature {fid}',
                )
                require(
                    all(
                        isinstance(v, (int, float)) and math.isfinite(v)
                        for v in (x1, x2, y1, y2)
                    )
                    and -180 <= x1 <= x2 <= 180
                    and -90 <= y1 <= y2 <= 90,
                    f'Invalid named-water bounding box: feature {fid}',
                )
                if out.execute(
                    'SELECT 1 FROM place_osm WHERE osm_type=? AND osm_id=? LIMIT 1',
                    (osm_type, osm_id),
                ).fetchone():
                    continue
                row = out.execute(
                    'INSERT INTO place(name,kind,detail,lat,lon,rank,source) VALUES(?,?,?,?,?,?,?)',
                    (
                        name,
                        cls or 'water',
                        'Canada (OpenStreetMap); approximate bbox center, not a shoreline/access point',
                        (y1 + y2) / 2,
                        (x1 + x2) / 2,
                        4,
                        SOURCE,
                    ),
                )
                out.execute(
                    'INSERT INTO place_osm VALUES(?,?,?)',
                    (row.lastrowid, osm_type, osm_id),
                )
                out.execute(
                    'INSERT INTO canada_place_origin VALUES(?,NULL,?)',
                    (row.lastrowid, fid),
                )
                water_count += 1
        out.execute("INSERT INTO place_fts(place_fts) VALUES('rebuild')")
        out.execute("INSERT INTO place_fts(place_fts,rank) VALUES('integrity-check',1)")
        require(
            out.execute('SELECT count(*) FROM place').fetchone()[0]
            == old + expected + water_count,
            'Merged row count mismatch',
        )
        require(
            out.execute(
                'SELECT count(*) FROM place WHERE source=?', (SOURCE,)
            ).fetchone()[0]
            == expected + water_count,
            'Canada source count mismatch',
        )
        require(
            not out.execute(
                f'SELECT {COLUMNS} FROM baseline.place EXCEPT SELECT {COLUMNS} FROM place LIMIT 1'
            ).fetchone(),
            'Original base places changed',
        )
        for table, columns in [
            ('place_osm', 'id,osm_type,osm_id'),
            ('meta', 'key,value'),
        ]:
            if has_table(out, 'baseline', table):
                require(
                    not out.execute(
                        f'SELECT {columns} FROM baseline.{table} EXCEPT SELECT {columns} FROM {table} LIMIT 1'
                    ).fetchone(),
                    f'Original base {table} changed',
                )
        require(
            not out.execute(
                'SELECT id+?,osm_type,osm_id FROM ca.place_osm EXCEPT '
                'SELECT id,osm_type,osm_id FROM place_osm LIMIT 1',
                (offset,),
            ).fetchone(),
            'Remapped Canada lineage mismatch',
        )
        require(
            not out.execute(
                'SELECT 1 FROM place_osm o LEFT JOIN place p ON p.id=o.id WHERE p.id IS NULL LIMIT 1'
            ).fetchone(),
            'Orphaned lineage',
        )
        receipt = {
            'status': 'MERGED_STAGED',
            'original_records': old,
            'canada_records': expected,
            'named_water_records': water_count,
            'total': old + expected + water_count,
            'path': str(dest),
            'base_sha256': args.base_sha256.lower(),
            'canada_source_sha256': meta['source_sha256'],
            'at': time.time(),
        }
        out.execute(
            'INSERT INTO meta VALUES(?,?)',
            ('canada.merge_receipt', json.dumps(receipt, sort_keys=True)),
        )
        out.commit()
        integrity(out)
        out.close()
        out = None
        require(digest(base) == args.base_sha256.lower(), 'Base changed during merge')
        uri(base)  # Recheck that a WAL has not appeared since the digest check.
        stage.chmod(base.stat().st_mode & 0o666)
        with stage.open('rb') as stream:
            os.fsync(stream.fileno())
        # Same-filesystem hard link is atomic and fails for ANY existing destination,
        # including dangling symlinks. Never use replace()/rename() here.
        os.link(stage, dest)
        return receipt
    finally:
        if out is not None:
            out.close()
        for path in (
            stage,
            Path(str(stage) + '-journal'),
            Path(str(stage) + '-wal'),
            Path(str(stage) + '-shm'),
        ):
            path.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('base', type=Path, help='pristine base places database')
    parser.add_argument('incoming', type=Path, help='validated Canada places database')
    parser.add_argument(
        'dest', type=Path, help='new staged output path (must not exist)'
    )
    parser.add_argument(
        '--base-sha256',
        required=True,
        help='independently trusted pristine base SHA256',
    )
    parser.add_argument(
        '--canada-map',
        type=Path,
        help='finished Canada map; add named water at approximate bbox centers',
    )
    args = parser.parse_args()
    try:
        receipt = merge(args)
    except (ValueError, sqlite3.Error, OSError) as error:
        parser.exit(1, f'Merge rejected: {error}\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
