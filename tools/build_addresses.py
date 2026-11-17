"""Street addresses for address search: derived/geo/addresses.sqlite, from Overture Maps' open address data.

  derived/buildenv/bin/python tools/build_addresses.py [--bbox us | --bbox W,S,E,N] [--release 2026-10-21.0]
  derived/buildenv/bin/python tools/build_addresses.py --country CA --bbox W,S,E,N     # writes derived/geo/addresses-CA.sqlite

Overture's address theme gathers official address points (in California from the counties, via OpenAddresses), with
open licences (mostly CDLA-Permissive / public domain; see the 'sources' column). Reads the GeoParquet files straight
from Overture's public S3 bucket with DuckDB, keeping the whole US (default) or a box, and streams them into SQLite.
OpenStreetMap had too few addresses (none at all on many coastal streets).

--country (default US, which works exactly as before) keeps another country's rows instead. Outside the US the
`state` column holds the region code of packaging/regions (CA-ON, CA-BC) and `zip` the whole postcode (K2G 0P7,
not five characters of it). Canada's rows are Statistics Canada's National Address Register (Statistics Canada Open
Licence): "Adapted from Statistics Canada, National Address Register. This does not constitute an endorsement by
Statistics Canada of this product." packaging/address_indexes.py --source then splits the file by region.
"""
import argparse, re, sqlite3, time
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
OUT = HERE / 'derived/geo/addresses.sqlite'
WORDS = {'boulevard': 'blvd', 'avenue': 'ave', 'av': 'ave', 'street': 'st', 'drive': 'dr', 'road': 'rd', 'place': 'pl', 'court': 'ct',
         'lane': 'ln', 'terrace': 'ter', 'circle': 'cir', 'highway': 'hwy', 'parkway': 'pkwy', 'square': 'sq', 'north': 'n', 'south': 's',
         'east': 'e', 'west': 'w', 'mount': 'mt', 'saint': 'st'}
# Canada's provinces and territories (Canada Post abbreviations), so a row says CA-ON whether Overture gives "ON" or "Ontario"
CA_PROVINCES = {'alberta': 'AB', 'british columbia': 'BC', 'manitoba': 'MB', 'new brunswick': 'NB', 'newfoundland and labrador': 'NL',
                'nova scotia': 'NS', 'northwest territories': 'NT', 'nunavut': 'NU', 'ontario': 'ON', 'prince edward island': 'PE',
                'quebec': 'QC', 'québec': 'QC', 'saskatchewan': 'SK', 'yukon': 'YT'}


def norm(street):
    """'Saint Mary Boulevard' -> 'st mary blvd' (game/serve.py uses the same rules on what people type)."""
    return ' '.join(WORDS.get(w, w) for w in re.sub(r'[^a-z0-9 ]+', ' ', street.lower()).split())


def region_code(country, level):
    """The `state` column. US: the two-letter state, as always. Elsewhere: a packaging/regions code such as CA-ON, or ''."""
    if country == 'US':
        return level.upper()[:2]
    level = (level or '').strip()
    if country == 'CA':
        abbr = CA_PROVINCES.get(level.lower()) or (level.upper() if level.upper() in CA_PROVINCES.values() else '')
        return f'CA-{abbr}' if abbr else ''
    return country       # a country mapped as one region (GY)


def postcode(country, code):
    """US: the five-digit ZIP (the query already cut it). Canada: the whole code as Canada Post writes it, A1A 1A1. Elsewhere: as given."""
    code = (code or '').strip()
    if country == 'US':
        return code
    if country == 'CA':
        c = re.sub(r'[^A-Za-z0-9]', '', code).upper()
        return f'{c[:3]} {c[3:]}' if len(c) == 6 else c
    return code


def row(country, num, street, city, level, code, lat, lon):
    """One Overture address -> one addr row (num, street, norm, city, state, zip, lat, lon)."""
    return (num.strip(), street.strip(), norm(street), city.title(), region_code(country, level), postcode(country, code), lat, lon)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bbox', default='us', help="'us' for the whole country, or W,S,E,N")
    ap.add_argument('--release', default='2026-10-21.0')
    ap.add_argument('--country', default='US', help='ISO country code to keep (default US)')
    ap.add_argument('--out', help='default derived/geo/addresses.sqlite for the US, derived/geo/addresses-<country>.sqlite otherwise')
    a = ap.parse_args()
    country = a.country.upper()
    if not re.fullmatch(r'[A-Z]{2}', country):
        raise SystemExit('--country takes a two-letter code')
    out = Path(a.out) if a.out else OUT if country == 'US' else OUT.with_name(f'addresses-{country}.sqlite')
    where = f"country = '{country}'"
    if a.bbox != 'us':
        w, s_, e, n = map(float, a.bbox.split(','))
        where += f' AND bbox.xmin BETWEEN {w} AND {e} AND bbox.ymin BETWEEN {s_} AND {n}'
    zip_sql = "coalesce(left(postcode, 5), '')" if country == 'US' else "coalesce(postcode, '')"
    import duckdb
    t0 = time.time()
    c = duckdb.connect()
    c.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial; SET s3_region='us-west-2';")
    cur = c.execute(f"""
        SELECT number, street, coalesce(postal_city, address_levels[2].value, ''), coalesce(address_levels[1].value, ''),
               {zip_sql}, round(ST_Y(geometry), 6), round(ST_X(geometry), 6)
        FROM read_parquet('s3://overturemaps-us-west-2/release/{a.release}/theme=addresses/type=address/*', hive_partitioning=1)
        WHERE {where} AND number IS NOT NULL AND street IS NOT NULL""")
    tmp = out.with_suffix('.tmp')
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.executescript('PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;'
                     'CREATE TABLE addr(num TEXT, street TEXT, norm TEXT, city TEXT, state TEXT, zip TEXT, lat REAL, lon REAL);'
                     'CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);')
    total = 0
    while rows := cur.fetchmany(500_000):  # streamed: the whole US is over 100 million rows
        db.executemany('INSERT INTO addr VALUES (?,?,?,?,?,?,?,?)', (row(country, *r) for r in rows))
        total += len(rows)
        print(f'{total:,} addresses, {time.time() - t0:.0f}s', flush=True)
    print('indexing', flush=True)
    db.execute('CREATE INDEX addr_norm ON addr(norm, num)')
    source = (f'Overture Maps addresses {a.release} (open licences, mostly CDLA-Permissive-2.0)' if country == 'US' else
              f'Overture Maps addresses {a.release}, {country} rows' + (' (Statistics Canada National Address Register, Statistics Canada Open Licence)' if country == 'CA' else ''))
    db.executemany('INSERT INTO meta VALUES (?,?)', [('bbox', a.bbox), ('count', str(total)), ('built', time.strftime('%Y-%m-%dT%H:%M:%S')),
                                                    ('source', source)] + ([('country', country)] if country != 'US' else []))
    db.commit(); db.close()
    tmp.replace(out)
    print(f'done: {total:,} addresses in {time.time() - t0:.0f}s', flush=True)


if __name__ == '__main__':
    main()
