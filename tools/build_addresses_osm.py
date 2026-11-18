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
the same number, street and postcode within about 50 m is kept once (the first one read). Addresses mapped only on a
multipolygon building relation are not read. See docs/REGIONS-UK.md. Needs pyosmium (`pip install osmium`) on the build machine
only; the app never imports it.
"""
import argparse, sqlite3, sys, time
from pathlib import Path

import osmium

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from engine.address_search import fold, normalize, uk_postcode  # noqa: E402

NEAR = 0.0005     # degrees, about 35-55 m: the same house number, street and postcode this close together is one address
CITY_KEYS = ('addr:city', 'addr:town', 'addr:village', 'addr:hamlet', 'addr:suburb', 'addr:place')


def postcode(raw):
    words = (raw or '').lower().replace('-', ' ').split()
    found = uk_postcode(words) if words else None
    return found[0] if found and found[1] == len(words) else ''


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
    batch, total, seen, dropped = [], 0, 0, 0
    placed = set()      # hash of (number, street, postcode, grid cell) for every address kept
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
        norm, zip_ = normalize(fold(street)), postcode(tags.get('addr:postcode'))
        who = (num.strip().lower(), norm, zip_)
        cy, cx = round(lat / NEAR), round(lon / NEAR)
        if any(hash((who, cy + dy, cx + dx)) in placed for dy in (-1, 0, 1) for dx in (-1, 0, 1)):
            dropped += 1
            continue
        placed.add(hash((who, cy, cx)))
        batch.append((num.strip(), street.strip(), norm, city.strip(), '', zip_, round(lat, 6), round(lon, 6)))
        if len(batch) >= 200_000:
            db.executemany('INSERT INTO addr VALUES (?,?,?,?,?,?,?,?)', batch)
            total += len(batch)
            batch = []
            print(f'{total:,} addresses ({seen:,} read), {time.time() - t0:.0f}s', flush=True)
    db.executemany('INSERT INTO addr VALUES (?,?,?,?,?,?,?,?)', batch)
    total += len(batch)
    print('indexing', flush=True)
    db.execute('CREATE INDEX addr_norm ON addr(norm, num)')
    with_postcode = db.execute("SELECT count(*) FROM addr WHERE zip != ''").fetchone()[0]
    db.executemany('INSERT INTO meta VALUES (?,?)', [('bbox', a.bbox), ('count', str(total)), ('with_postcode', str(with_postcode)),
                                                    ('built', time.strftime('%Y-%m-%dT%H:%M:%S')), ('source', a.source)])
    db.commit()
    db.close()
    tmp.replace(out)
    print(f'done: {total:,} addresses ({dropped:,} repeats dropped), {with_postcode:,} with a postcode, in {time.time() - t0:.0f}s', flush=True)


if __name__ == '__main__':
    main()
