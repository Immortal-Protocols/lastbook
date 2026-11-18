#!/usr/bin/env python3
"""Street addresses for address search from OpenStreetMap, for places without an open address-point dataset.

  python3 tools/build_addresses_osm.py england-latest.osm.pbf derived/geo/addresses/GB-SW.sqlite \\
      --bbox=-6.57,49.71,-1.33,52.27 --source "OpenStreetMap contributors (ODbL), via Geofabrik england-latest.osm.pbf"

Keeps every node, and every way with its nodes (a building outline, placed at the middle of its nodes), that has
addr:housenumber and addr:street, inside the box. The table is the one tools/build_addresses.py writes, so
engine/address_search.py reads it unchanged:

  addr(num, street, norm, city, state, zip, lat, lon)   state is '' outside the US; zip holds a UK postcode as 'SW1A 2AA'
  meta(key, value)                                      'source' is shown with each result as its credit

OpenStreetMap has far fewer UK addresses than a government address list, and many have no postcode, so a house missing
here is not proof it does not exist. An entrance node inside a building outline often repeats the building's address, so
the same number and street within about 50 m, with the same postcode or with one of them lacking one, is one address: the row
that has a postcode and a town is kept, and fills a gap from the others. Addresses mapped only on a multipolygon building
relation are not read. See docs/REGIONS-UK.md. Needs pyosmium (`pip install osmium`) on the build machine
only; the app never imports it.
"""
import argparse, sqlite3, sys, time
from pathlib import Path

import osmium

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from engine.address_search import fold, normalize, uk_postcode  # noqa: E402

NEAR = 0.0005     # degrees, about 35-55 m: the same house number and street this close together is one address
CITY_KEYS = ('addr:city', 'addr:town', 'addr:village', 'addr:hamlet', 'addr:suburb', 'addr:place')


def postcode(raw):
    words = (raw or '').lower().replace('-', ' ').split()
    found = uk_postcode(words) if words else None
    return found[0] if found and found[1] == len(words) else ''


def merge_repeats(db):
    """Fold repeats of one address into a single row, in place: same street and number (any case), within NEAR degrees, and a postcode
    that is the same or missing on either side. The row with a postcode, then a town, stays and takes a missing postcode or town from
    the others. Returns how many rows were dropped."""
    drop, fill = [], []

    def compatible(a, b):
        return abs(a[5] - b[5]) < NEAR and abs(a[6] - b[6]) < NEAR and (not a[4] or not b[4] or a[4] == b[4])

    def fold_block(rows):
        by_number = {}
        for r in rows:
            by_number.setdefault(r[1].lower(), []).append(r)
        for same in by_number.values():
            if len(same) < 2:
                continue
            clusters = []
            for r in sorted(same, key=lambda r: (r[5], r[6], r[0])):
                for c in clusters:
                    if all(compatible(r, m) for m in c):
                        c.append(r)
                        break
                else:
                    clusters.append([r])
            for c in clusters:
                if len(c) < 2:
                    continue
                best = max(c, key=lambda r: (bool(r[4]), bool(r[3])))
                zip_ = best[4] or next((r[4] for r in c if r[4]), '')
                city = best[3] or next((r[3] for r in c if r[3]), '')
                if (city, zip_) != (best[3], best[4]):
                    fill.append((city, zip_, best[0]))
                drop.extend(r[0] for r in c if r is not best)

    block, norm = [], None
    # rows are (rowid, num, norm, city, zip, lat, lon); the (norm, num) index puts a street's rows together
    for row in db.execute('SELECT rowid, num, norm, city, zip, lat, lon FROM addr ORDER BY norm, num'):
        if row[2] != norm and block:
            fold_block(block)
            block = []
        norm = row[2]
        block.append(row)
    fold_block(block)
    db.executemany('UPDATE addr SET city = ?, zip = ? WHERE rowid = ?', fill)
    for i in range(0, len(drop), 50_000):
        db.execute(f'DELETE FROM addr WHERE rowid IN ({",".join("?" * len(drop[i:i + 50_000]))})', drop[i:i + 50_000])
    return len(drop)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pbf')
    ap.add_argument('out')
    ap.add_argument('--bbox', required=True, help='W,S,E,N (use --bbox=... when the west value is negative)')
    ap.add_argument('--source', default='OpenStreetMap contributors (ODbL)')
    a = ap.parse_args()
    west, south, east, north = map(float, a.bbox.split(','))
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix('.tmp')
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.executescript('PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;'
                     'CREATE TABLE addr(num TEXT, street TEXT, norm TEXT, city TEXT, state TEXT, zip TEXT, lat REAL, lon REAL);'
                     'CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);')
    t0 = time.time()
    batch, total, seen = [], 0, 0
    # locations first, so ways carry coordinates; the filters then keep only objects that have a house number
    fp = (osmium.FileProcessor(a.pbf, osmium.osm.NODE | osmium.osm.WAY)
          .with_locations()
          .with_filter(osmium.filter.KeyFilter('addr:housenumber')))
    for obj in fp:
        tags = obj.tags
        num, street = tags.get('addr:housenumber'), tags.get('addr:street')
        if not num or not street:
            continue
        if obj.is_node():
            if not obj.location.valid():
                continue
            lon, lat = obj.location.lon, obj.location.lat
        else:
            pts = [(n.lon, n.lat) for n in obj.nodes if n.location.valid()]
            if not pts:
                continue
            lon = sum(p[0] for p in pts) / len(pts)
            lat = sum(p[1] for p in pts) / len(pts)
        seen += 1
        if not (west <= lon <= east and south <= lat <= north):
            continue
        city = next((tags[k] for k in CITY_KEYS if tags.get(k)), '')
        batch.append((num.strip(), street.strip(), normalize(fold(street)), city.strip(), '', postcode(tags.get('addr:postcode')),
                      round(lat, 6), round(lon, 6)))
        if len(batch) >= 200_000:
            db.executemany('INSERT INTO addr VALUES (?,?,?,?,?,?,?,?)', batch)
            total += len(batch)
            batch = []
            print(f'{total:,} addresses ({seen:,} read), {time.time() - t0:.0f}s', flush=True)
    db.executemany('INSERT INTO addr VALUES (?,?,?,?,?,?,?,?)', batch)
    total += len(batch)
    print('indexing', flush=True)
    db.execute('CREATE INDEX addr_norm ON addr(norm, num)')
    print('merging repeats', flush=True)
    dropped = merge_repeats(db)
    total = db.execute('SELECT count(*) FROM addr').fetchone()[0]
    with_postcode = db.execute("SELECT count(*) FROM addr WHERE zip != ''").fetchone()[0]
    db.executemany('INSERT INTO meta VALUES (?,?)', [('bbox', a.bbox), ('count', str(total)), ('with_postcode', str(with_postcode)),
                                                    ('built', time.strftime('%Y-%m-%dT%H:%M:%S')), ('source', a.source)])
    db.commit()
    db.close()
    tmp.replace(out)
    print(f'done: {total:,} addresses ({dropped:,} repeats dropped), {with_postcode:,} with a postcode, in {time.time() - t0:.0f}s', flush=True)


if __name__ == '__main__':
    main()
