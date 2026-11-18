"""Street addresses for address search: derived/geo/addresses.sqlite, from Overture Maps' open address data.

  derived/buildenv/bin/python tools/build_addresses.py [--bbox us | --bbox W,S,E,N] [--release 2026-10-21.0]
  python3 tools/build_addresses.py --region CA-ON --out derived/geo/addresses-CA-ON.sqlite

Overture's address theme gathers official address points (in California from the counties, via OpenAddresses), with
open licences (mostly CDLA-Permissive / public domain; see the 'sources' column). Reads the GeoParquet files straight
from Overture's public S3 bucket with DuckDB, keeping the whole US (default) or a box, and streams them into SQLite.
OpenStreetMap had too few addresses (none at all on many coastal streets).
"""
import argparse, json, re, sqlite3, sys, time
from pathlib import Path


HERE = Path(__file__).resolve().parent.parent
OUT = HERE / 'derived/geo/addresses.sqlite'
sys.path.insert(0, str(HERE))
from engine.address_search import normalize as norm
from engine.regions import ONTARIO, canonical_region

ONTARIO_ATTRIBUTION = ('Adapted from Statistics Canada, National Address Register, 2024. '
                       'This does not constitute an endorsement by Statistics Canada of this product.')


def convert_row(row, country):
    number, street, city, region, postcode, lat, lon = row
    region = canonical_region(region, country)
    postcode = re.sub(r'\s+', '', postcode or '').upper() if country == 'CA' else (postcode or '')[:5]
    return (number.strip(), street.strip(), norm(street, country), city.title(),
            region if country == 'CA' else region[:2], postcode, lat, lon)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bbox', help="'us' for the US, or W,S,E,N; Ontario defaults to its province bounds")
    ap.add_argument('--country', choices=['US', 'CA'], default='US')
    ap.add_argument('--region', help='CA-ON (or ON) for Ontario')
    ap.add_argument('--out', type=Path, help='Output database; Ontario uses a separate file by default')
    ap.add_argument('--extension-directory', type=Path, default=HERE / 'derived/build-cache/duckdb-extensions')
    ap.add_argument('--release', default='2026-10-21.0')
    ap.add_argument('--source-licence', help='Reviewed source licence for a different Ontario release')
    ap.add_argument('--source-attribution', help='Reviewed source attribution for a different Ontario release')
    a = ap.parse_args()
    region = canonical_region(a.region)
    if region == 'CA-ON':
        a.country = 'CA'
    elif region or a.country == 'CA':
        ap.error('Canadian builds currently support --region CA-ON only.')
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}\.\d+', a.release):
        ap.error('Use an Overture release id such as 2026-10-21.0.')
    if region and a.release != '2026-10-21.0' and not (a.source_licence and a.source_attribution):
        ap.error('For a different Ontario release, review its sources and supply --source-licence and --source-attribution.')
    bounds = ONTARIO['bounds'] if region else None
    if a.bbox and a.bbox != 'us':
        bounds = list(map(float, a.bbox.split(',')))
    if region and a.bbox == 'us':
        ap.error('--bbox us cannot be used for Ontario.')
    where, parameters = 'country = ?', [a.country]
    if region:
        where += " AND upper(coalesce(address_levels[1].value, '')) IN ('ON', 'CA-ON', 'ONTARIO')"
    if bounds:
        w, south, e, n = bounds
        where += ' AND bbox.xmin BETWEEN ? AND ? AND bbox.ymin BETWEEN ? AND ?'
        parameters += [w, e, south, n]
    output = a.out or (HERE / 'derived/geo/addresses-CA-ON.sqlite' if region else OUT)
    output.parent.mkdir(parents=True, exist_ok=True)
    import duckdb  # Build dependency only; the app uses SQLite offline.
    t0 = time.time()
    a.extension_directory.mkdir(parents=True, exist_ok=True)
    c = duckdb.connect(config={'extension_directory': str(a.extension_directory.resolve()), 'memory_limit': '1GB', 'threads': 4})
    c.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial; SET s3_region='us-west-2';")
    cur = c.execute(f"""
        SELECT number, street, coalesce(postal_city, address_levels[2].value, ''), coalesce(address_levels[1].value, ''),
               coalesce(postcode, ''), round(ST_Y(geometry), 6), round(ST_X(geometry), 6)
        FROM read_parquet('s3://overturemaps-us-west-2/release/{a.release}/theme=addresses/type=address/*', hive_partitioning=1)
        WHERE {where} AND number IS NOT NULL AND street IS NOT NULL""", parameters)
    tmp = output.with_suffix('.tmp')
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.executescript('PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;'
                     'CREATE TABLE addr(num TEXT, street TEXT, norm TEXT, city TEXT, state TEXT, zip TEXT, lat REAL, lon REAL);'
                     'CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);')
    total = 0
    while rows := cur.fetchmany(500_000):  # streamed: the whole US is over 100 million rows
        db.executemany('INSERT INTO addr VALUES (?,?,?,?,?,?,?,?)',
                       (convert_row(row, a.country) for row in rows))
        total += len(rows)
        print(f'{total:,} addresses, {time.time() - t0:.0f}s', flush=True)
    print('indexing', flush=True)
    db.execute('CREATE INDEX addr_norm ON addr(norm, num)')
    db.executemany('INSERT INTO meta VALUES (?,?)', [('bbox', json.dumps(bounds) if bounds else 'us'), ('country', a.country), ('region', region), ('count', str(total)), ('built', time.strftime('%Y-%m-%dT%H:%M:%S')),
                                                    ('release', a.release),
                                                    ('source', f'Overture Maps addresses {a.release}; Statistics Canada National Address Register' if region else f'Overture Maps addresses {a.release} (open licences, mostly CDLA-Permissive-2.0)')])
    if region:
        db.executemany('INSERT INTO meta VALUES (?,?)', [
            ('source_licence', a.source_licence or 'Statistics Canada Open Licence'),
            ('source_attribution', a.source_attribution or ONTARIO_ATTRIBUTION),
            ('source_url', 'https://docs.overturemaps.org/attribution/'),
        ])
    db.commit(); db.close(); c.close()
    tmp.replace(output)
    print(f'done: {total:,} addresses in {time.time() - t0:.0f}s', flush=True)


if __name__ == '__main__':
    main()
