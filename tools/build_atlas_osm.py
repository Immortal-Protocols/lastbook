#!/usr/bin/env python3
"""Natural resource records for places without the US atlas sources, from OpenStreetMap: library-data/geography/resources/atlas.sqlite.

  python3 tools/build_atlas_osm.py england-latest.osm.pbf atlas.sqlite --bbox=-6.57,49.71,-1.33,52.27 \\
      --source "OpenStreetMap contributors (ODbL), via Geofabrik england-latest.osm.pbf"

Writes the tables the app reads (`resource` + `spatial`), with two kinds:
  mineral       mines, quarries, mine shafts and adits: historic=mine, landuse=quarry, man_made=mineshaft, man_made=adit
                (a closed way or a node; a quarry mapped only as a multipolygon relation is not read)
  boat_launch   slipways and marinas: leisure=slipway, leisure=marina

Fish-stocking and oil-and-gas-well records have no counterpart here and are not written, so the app does not offer those
layers for this map. OpenStreetMap says what a place is, not whether it is safe, open or in use: the map's note for these kinds
says so. Needs pyosmium (`pip install osmium`) on the build machine only.
"""
import argparse, json, sqlite3, sys, time
from pathlib import Path

import osmium

KINDS = [  # (key, value, kind, what it is called in the detail)
    ('historic', 'mine', 'mineral', 'Mine (historic)'),
    ('landuse', 'quarry', 'mineral', 'Quarry'),
    ('man_made', 'mineshaft', 'mineral', 'Mine shaft'),
    ('man_made', 'adit', 'mineral', 'Adit (mine entrance)'),
    ('leisure', 'slipway', 'boat_launch', 'Slipway'),
    ('leisure', 'marina', 'boat_launch', 'Marina'),
]
DEFAULT_NAME = {'Mine (historic)': 'Mine', 'Quarry': 'Quarry', 'Mine shaft': 'Mine shaft', 'Adit (mine entrance)': 'Adit',
                'Slipway': 'Slipway', 'Marina': 'Marina'}


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
    out.unlink(missing_ok=True)
    db = sqlite3.connect(out)
    db.executescript('''PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;
      CREATE TABLE resource(id INTEGER PRIMARY KEY, source_id TEXT, kind TEXT, name TEXT, lat REAL, lon REAL, detail TEXT, source TEXT, origin TEXT);
      CREATE INDEX resource_kind ON resource(kind);
      CREATE INDEX resource_origin ON resource(origin);
      CREATE VIRTUAL TABLE spatial USING rtree(id, minx, maxx, miny, maxy);
      CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);''')
    t0 = time.time()
    counts = {}
    fp = (osmium.FileProcessor(a.pbf, osmium.osm.NODE | osmium.osm.WAY).with_locations()
          .with_filter(osmium.filter.TagFilter(*[(k, v) for k, v, _, _ in KINDS])))
    for obj in fp:
        tags = obj.tags
        hit = next(((kind, what) for k, v, kind, what in KINDS if tags.get(k) == v), None)
        if not hit:
            continue
        if obj.is_node():
            if not obj.location.valid():
                continue
            lon, lat = obj.location.lon, obj.location.lat
        else:
            pts = [(c.lon, c.lat) for c in obj.nodes if c.location.valid()]
            if not pts:
                continue
            lon = sum(p[0] for p in pts) / len(pts)
            lat = sum(p[1] for p in pts) / len(pts)
        if not (west <= lon <= east and south <= lat <= north):
            continue
        kind, what = hit
        detail = {'feature': what, 'source_map': 'OpenStreetMap'}
        for tag, key in (('resource', 'commodity'), ('operator', 'owner'), ('disused', 'status'), ('abandoned', 'status')):
            if tags.get(tag):
                detail[key] = 'Disused' if tag in ('disused', 'abandoned') and tags[tag] == 'yes' else tags[tag]
        if tags.get('disused:landuse') or tags.get('disused:historic') or tags.get('abandoned:landuse'):
            detail.setdefault('status', 'Disused')
        cur = db.execute('INSERT INTO resource(source_id,kind,name,lat,lon,detail,source,origin) VALUES (?,?,?,?,?,?,?,?)',
                         (f'osm:{"n" if obj.is_node() else "w"}{obj.id}', kind, tags.get('name') or DEFAULT_NAME[what], round(lat, 6),
                          round(lon, 6), json.dumps(detail, separators=(',', ':')), 'https://www.openstreetmap.org/', 'osm'))
        db.execute('INSERT INTO spatial VALUES (?,?,?,?,?)', (cur.lastrowid, lon, lon, lat, lat))
        counts[what] = counts.get(what, 0) + 1
    db.execute('INSERT INTO meta VALUES (?,?)', ('built', json.dumps({'counts': counts, 'source': a.source, 'at': time.strftime('%Y-%m-%dT%H:%M:%S')})))
    db.commit()
    db.close()
    print(f'done: {sum(counts.values()):,} records {counts} in {time.time() - t0:.0f}s', flush=True)


if __name__ == '__main__':
    main()
