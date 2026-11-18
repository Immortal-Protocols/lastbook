#!/usr/bin/env python3
"""The offline place finder (derived/geo/places.sqlite) for places without the US gazetteers, from data already built.

  python3 tools/build_places_osm.py national.sqlite addresses/GB-SW.sqlite places.sqlite --area "South West England"

Reads two files this repository's tools already write, and nothing from the network:
  national.sqlite   the named places (city, town, suburb, village, hamlet, county, island) and the named help points
                    that tools/build_map.py cut from OpenStreetMap
  an address index  tools/build_addresses_osm.py's table; its postcodes give a point per postcode and per postcode district
                    (the part before the space, 'EX4')
and writes the `place` + `place_fts` tables tools/build_places.py writes, so the app reads it unchanged.

A postcode here exists only if some OpenStreetMap address carries it, and its point is the middle of those addresses, not
an official postcode point. Ordnance Survey's Code-Point Open and Open Names would give every postcode and place; their
licence files were not read for this (docs/REGIONS-UK.md), so they are not used.
"""
import argparse, sqlite3, struct, sys, time
from pathlib import Path

ins = 'INSERT INTO place(name,kind,detail,lat,lon,rank,source) VALUES (?,?,?,?,?,?,?)'
SKIP = {'farm', 'locality'}   # tens of thousands of single farms and unnamed-ish localities would bury the towns


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('national')
    ap.add_argument('addresses')
    ap.add_argument('out')
    ap.add_argument('--area', required=True, help="what to show under each place, e.g. 'South West England'")
    a = ap.parse_args()
    t0 = time.time()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)
    db = sqlite3.connect(out)
    db.executescript('''PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;
      CREATE TABLE place(id INTEGER PRIMARY KEY, name TEXT, kind TEXT, detail TEXT, lat REAL, lon REAL, rank INTEGER, source TEXT);
      CREATE VIRTUAL TABLE place_fts USING fts5(name, detail, content='place', content_rowid='id', tokenize='unicode61');''')
    counts = {}
    nat = sqlite3.connect(f'file:{a.national}?mode=ro', uri=True)
    for cls, name, g in nat.execute("SELECT cls,name,geom FROM feat WHERE layer='place' AND name IS NOT NULL AND name<>''"):
        if cls in SKIP:
            continue
        _, _, x, y = struct.unpack_from('<iiii', g)
        db.execute(ins, (name, cls, f'{a.area} (OpenStreetMap)', y / 1e6, x / 1e6, 1, 'OpenStreetMap'))
        counts['places'] = counts.get('places', 0) + 1
    for cls, name, lon, lat in nat.execute("SELECT cls,name,lon,lat FROM poi WHERE name IS NOT NULL AND name<>''"):
        db.execute(ins, (name, cls.replace('_', ' '), f'{a.area} (OpenStreetMap)', lat, lon, 4, 'OpenStreetMap'))
        counts['named points'] = counts.get('named points', 0) + 1
    adr = sqlite3.connect(f'file:{a.addresses}?mode=ro', uri=True)
    districts = {}
    for zip_, lat, lon, n in adr.execute("SELECT zip, AVG(lat), AVG(lon), COUNT(*) FROM addr WHERE zip<>'' GROUP BY zip"):
        db.execute(ins, (zip_, 'postcode', f'{a.area}: from {n} OpenStreetMap address{"es" if n > 1 else ""}', lat, lon, 2, 'OpenStreetMap addresses'))
        counts['postcodes'] = counts.get('postcodes', 0) + 1
        d = districts.setdefault(zip_.split()[0], [0.0, 0.0, 0])
        d[0] += lat; d[1] += lon; d[2] += 1
    for outward, (la, lo, n) in districts.items():
        db.execute(ins, (outward, 'postcode district', f'{a.area}: middle of {n} postcodes found in OpenStreetMap addresses', la / n, lo / n, 1,
                         'OpenStreetMap addresses'))
        counts['postcode districts'] = counts.get('postcode districts', 0) + 1
    db.execute("INSERT INTO place_fts(place_fts) VALUES ('rebuild')")
    db.commit()
    db.close()
    print(f'done: {counts} in {time.time() - t0:.0f}s', flush=True)


if __name__ == '__main__':
    main()
