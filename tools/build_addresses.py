"""Street addresses for address search: derived/geo/addresses.sqlite, from Overture Maps' open address data.

  derived/buildenv/bin/python tools/build_addresses.py [--bbox br | us | W,S,E,N] [--release 2026-10-21.0]

Overture's address theme gathers official address points (in Brazil including CNEFE/IBGE and municipal open data), with
open licences (mostly CDLA-Permissive / public domain; see the 'sources' column). Reads the GeoParquet files straight
from Overture's public S3 bucket with DuckDB, keeping Brazil (default), the US, or a box, and streams them into SQLite.
"""
import argparse, re, sqlite3, time, unicodedata
from pathlib import Path

import duckdb

HERE = Path(__file__).resolve().parent.parent
OUT = HERE / 'derived/geo/addresses.sqlite'
WORDS = {'boulevard': 'blvd', 'avenue': 'ave', 'av': 'ave', 'street': 'st', 'drive': 'dr', 'road': 'rd', 'place': 'pl', 'court': 'ct',
         'lane': 'ln', 'terrace': 'ter', 'circle': 'cir', 'highway': 'hwy', 'parkway': 'pkwy', 'square': 'sq', 'north': 'n', 'south': 's',
         'east': 'e', 'west': 'w', 'mount': 'mt', 'saint': 'st',
         'rua': 'r', 'avenida': 'av', 'travessa': 'tv', 'alameda': 'al', 'praca': 'pc', 'rodovia': 'rod', 'estrada': 'estr',
         'beco': 'bc', 'largo': 'lg', 'viaduto': 'vd', 'passagem': 'psg', 'servidao': 'srv', 'quadra': 'qd', 'lote': 'lt',
         'bloco': 'bl', 'conjunto': 'cj', 'norte': 'n', 'sul': 's', 'leste': 'e', 'oeste': 'w', 'sao': 's', 'santa': 'sta',
         'santo': 'sto', 'doutor': 'dr', 'professor': 'prof', 'general': 'gal', 'coronel': 'cel', 'presidente': 'pres',
         'governador': 'gov', 'senador': 'sen', 'deputado': 'dep', 'brigadeiro': 'brig', 'marechal': 'mal'}


def _strip_accents(text):
    return ''.join(ch for ch in unicodedata.normalize('NFKD', text or '') if not unicodedata.combining(ch))


def norm(street):
    """'Avenida São João' -> 'av s joao' (engine/address_search.py uses the same rules on what people type)."""
    clean = _strip_accents(street).lower()
    return ' '.join(WORDS.get(w, w) for w in re.sub(r'[^a-z0-9 ]+', ' ', clean).split())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bbox', default='br', help="'br' for Brazil, 'us' for the US, or W,S,E,N")
    ap.add_argument('--release', default='2026-10-21.0')
    a = ap.parse_args()
    if a.bbox == 'br':
        where = "country = 'BR'"
        postcode_sql = "coalesce(left(regexp_replace(postcode, '[^0-9]', '', 'g'), 8), '')"
    elif a.bbox == 'us':
        where = "country = 'US'"
        postcode_sql = "coalesce(left(postcode, 5), '')"
    else:
        w, s_, e, n = map(float, a.bbox.split(','))
        where = f'bbox.xmin BETWEEN {w} AND {e} AND bbox.ymin BETWEEN {s_} AND {n}'
        postcode_sql = "coalesce(left(regexp_replace(postcode, '[^0-9]', '', 'g'), 8), '')"
    t0 = time.time()
    c = duckdb.connect()
    c.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial; SET s3_region='us-west-2';")
    cur = c.execute(f"""
        SELECT number, street, coalesce(postal_city, address_levels[2].value, ''), coalesce(address_levels[1].value, ''),
               {postcode_sql}, round(ST_Y(geometry), 6), round(ST_X(geometry), 6)
        FROM read_parquet('s3://overturemaps-us-west-2/release/{a.release}/theme=addresses/type=address/*', hive_partitioning=1)
        WHERE {where} AND number IS NOT NULL AND street IS NOT NULL""")
    tmp = OUT.with_suffix('.tmp')
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.executescript('PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;'
                     'CREATE TABLE addr(num TEXT, street TEXT, norm TEXT, city TEXT, state TEXT, zip TEXT, lat REAL, lon REAL);'
                     'CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);')
    total = 0
    while rows := cur.fetchmany(500_000):  # streamed: the whole US is over 100 million rows
        db.executemany('INSERT INTO addr VALUES (?,?,?,?,?,?,?,?)',
                       ((num.strip(), st.strip(), norm(st), city.title(), state.upper()[:2], z, la, lo) for num, st, city, state, z, la, lo in rows))
        total += len(rows)
        print(f'{total:,} addresses, {time.time() - t0:.0f}s', flush=True)
    print('indexing', flush=True)
    db.execute('CREATE INDEX addr_norm ON addr(norm, num)')
    db.executemany('INSERT INTO meta VALUES (?,?)', [('bbox', a.bbox), ('count', str(total)), ('built', time.strftime('%Y-%m-%dT%H:%M:%S')),
                                                    ('source', f'Overture Maps addresses {a.release} (open licences, mostly CDLA-Permissive-2.0)')])
    db.commit(); db.close()
    tmp.replace(OUT)
    print(f'done: {total:,} addresses in {time.time() - t0:.0f}s', flush=True)


if __name__ == '__main__':
    main()
