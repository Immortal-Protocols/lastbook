"""python3 -B -m unittest app.tests.test_build_region

Run tools/build_region.py on a small made-up Geofabrik free GeoPackage — three of the twelve feature
tables, a few points and lines, some inside a clip box and some outside — as its own process, with no
network and no pyosmium (no --coast), and check the map set the app reads: the five files, the
map-set.json contract, the app's own queries against the output, the clip, the places schema and
idempotence.
"""
import json
import sqlite3
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[2]
TOOL = HERE / 'tools' / 'build_region.py'
BOX = '-50,-30,-40,-20'


def gpkg_geom(kind, *coords):
    """A GeoPackage geometry blob: 8-byte header (endianness 0, no envelope, srid 0) + WKB."""
    if kind == 'point':
        wkb = b'\x01\x01\x00\x00\x00' + struct.pack('<dd', *coords)
    else:
        pts = list(coords)
        wkb = b'\x01\x02\x00\x00\x00' + struct.pack('<I', len(pts)) + b''.join(struct.pack('<dd', *p) for p in pts)
    return bytes((0, 1 if kind == 'point' else 2, 0, 0, 0, 0, 0, 0)) + wkb


def make_extract(path):
    """Three of the twelve tables build_map.py reads; the other nine exercise the stubbing path."""
    db = sqlite3.connect(path)
    db.executescript('''
        CREATE TABLE gpkg_contents(table_name TEXT PRIMARY KEY, data_type TEXT, last_change TEXT);
        INSERT INTO gpkg_contents VALUES ('gpkg_contents', 'metadata', '2026-01-01T00:00:00Z');
        INSERT INTO gpkg_contents VALUES ('gis_osm_roads_free', 'features', '2026-01-02T03:04:05Z');
        INSERT INTO gpkg_contents VALUES ('gis_osm_places_free', 'features', '2026-01-01T00:00:00Z');
        INSERT INTO gpkg_contents VALUES ('gis_osm_pois_free', 'features', '2026-01-01T00:00:00Z');
        CREATE TABLE gis_osm_roads_free(fclass TEXT, name TEXT, ref TEXT, geom BLOB);
        CREATE TABLE gis_osm_places_free(fclass TEXT, population TEXT, name TEXT, geom BLOB);
        CREATE TABLE gis_osm_pois_free(fclass TEXT, name TEXT, geom BLOB);
    ''')
    rows = [
        ('gis_osm_roads_free', ('road', 'Rua da Test', None, gpkg_geom('line', (-49, -29), (-41, -21)))),    # inside
        ('gis_osm_roads_free', ('road', 'Road Outside', None, gpkg_geom('line', (10, 10), (11, 11)))),        # outside
        ('gis_osm_places_free', ('city', '6000000', 'Rio de Janeiro', gpkg_geom('point', -43.2, -22.9))),     # inside
        ('gis_osm_places_free', ('village', '100', 'Village Outside', gpkg_geom('point', 12, 12))),           # outside
        ('gis_osm_pois_free', ('pharmacy', 'Farmacia Test', gpkg_geom('point', -44, -23))),                   # inside
        ('gis_osm_pois_free', ('fuel', 'Fuel Outside', gpkg_geom('point', 13, 13))),                          # outside
    ]
    for table, values in rows:
        db.execute(f'INSERT INTO {table} VALUES (?,?,?,?)' if table != 'gis_osm_pois_free' else f'INSERT INTO {table} VALUES (?,?,?)', values)
    db.commit()
    db.close()


def run_tool(*args):
    return subprocess.run([sys.executable, '-B', str(TOOL), *map(str, args)], capture_output=True, text=True)


class TestBuildRegion(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory(prefix='lastbook-test-')
        self.addCleanup(self.td.cleanup)
        self.extract = Path(self.td.name) / 'test-free.gpkg'
        make_extract(self.extract)
        self.data = Path(self.td.name) / 'LastbookData'
        (self.data / 'library-data').mkdir(parents=True)    # the app needs it; the tool only needs derived/geo

    def build(self, *extra):
        r = run_tool(self.extract, '--name', 'BR-TEST', '--label', 'Test Region', '--box', BOX, '--data', self.data, *extra)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r

    def open(self, name):
        return sqlite3.connect(self.data / 'derived' / 'geo' / name)

    def test_writes_the_complete_set(self):
        self.build()
        geo = self.data / 'derived' / 'geo'
        for f in ('national.sqlite', 'map.sqlite', 'places.sqlite', 'national-status.json', 'socal-cells.json'):
            self.assertTrue((geo / f).is_file(), f)
        ms = json.loads((self.data / 'map-set.json').read_text())
        self.assertEqual(ms['name'], 'BR-TEST')
        self.assertEqual(set(ms['files']), {f'derived/geo/{f}' for f in
                                            ('national.sqlite', 'map.sqlite', 'places.sqlite', 'national-status.json', 'socal-cells.json')})
        for rel, size in ms['files'].items():
            self.assertEqual((self.data / rel).stat().st_size, size, rel)
        self.assertEqual(ms['bytes'], sum(ms['files'].values()))
        self.assertIsInstance(ms['seconds'], int)

    def test_clip_and_meta(self):
        self.build()
        db = self.open('national.sqlite')
        # the app's vector-tile shape: join through feat_idx, overlap the clip box
        rows = db.execute('SELECT f.name FROM feat_idx i JOIN feat f ON f.id = i.id '
                          'WHERE i.maxx >= ? AND i.minx <= ? AND i.maxy >= ? AND i.miny <= ?',
                          (-50, -40, -30, -20)).fetchall()
        self.assertEqual(sorted(r[0] for r in rows if r[0]), ['Rio de Janeiro', 'Rua da Test'])
        self.assertEqual(db.execute('SELECT count(*) FROM feat').fetchone()[0], 2)
        meta = dict(db.execute('SELECT key, value FROM meta'))
        self.assertIn('test-free.gpkg', meta['source'])    # honest source, not the hardcoded SoCal one
        self.assertNotIn('socal', meta['source'])
        self.assertEqual(meta['data_as_of'], '2026-01-02T03:04:05Z')    # the newest table last_change
        self.assertIsNotNone(meta.get('built'))
        w, s, e, n = map(float, meta['bounds'].split(','))
        self.assertTrue(-50 <= w < e <= -40 and -30 <= s < n <= -20, meta['bounds'])
        status = json.loads((self.data / 'derived' / 'geo' / 'national-status.json').read_text())
        self.assertEqual(status, {'state': 'complete', 'stage': 'ready', 'features': 2})
        self.assertEqual(json.loads((self.data / 'derived' / 'geo' / 'socal-cells.json').read_text()), [])

    def test_places_match_the_app_query(self):
        self.build()
        db = self.open('places.sqlite')
        # the app's exact query (server.py /api/places)
        rows = db.execute("SELECT p.name, p.kind, p.detail, p.lat, p.lon, p.rank, p.source "
                          "FROM place_fts f JOIN place p ON p.id = f.rowid WHERE place_fts MATCH ? "
                          "ORDER BY p.rank, bm25(place_fts) LIMIT 200", ('Rio',)).fetchall()
        self.assertEqual([r[0] for r in rows], ['Rio de Janeiro'])
        self.assertEqual(rows[0][6], 'OpenStreetMap')
        allp = dict((r[0], r) for r in db.execute('SELECT name, kind, rank, source FROM place'))
        self.assertEqual(allp['Rio de Janeiro'][1:], ('city', 1, 'OpenStreetMap'))
        self.assertEqual(allp['Farmacia Test'][1:], ('pharmacy', 4, 'OpenStreetMap'))
        self.assertNotIn('Village Outside', allp)
        self.assertNotIn('Fuel Outside', allp)

    def test_map_placeholder_is_the_shipped_schema(self):
        self.build()
        db = self.open('map.sqlite')
        self.assertEqual(db.execute('SELECT count(*) FROM feat').fetchone()[0], 0)
        cols = [r[1] for r in db.execute('PRAGMA table_info(feat)')]
        self.assertEqual(cols, ['id', 'layer', 'cls', 'name', 'minz', 'geom'])

    def test_idempotent(self):
        self.build()
        self.build()
        self.assertEqual(self.open('national.sqlite').execute('SELECT count(*) FROM feat').fetchone()[0], 2)
        self.assertEqual(self.open('places.sqlite').execute('SELECT count(*) FROM place').fetchone()[0], 2)

    def test_without_box_keeps_everything(self):
        r = run_tool(self.extract, '--name', 'BR-TEST', '--label', 'Test Region', '--data', self.data)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        db = self.open('national.sqlite')
        self.assertEqual(db.execute('SELECT count(*) FROM feat').fetchone()[0], 4)    # 2 roads + 2 places, unclipped
        self.assertEqual(db.execute('SELECT count(*) FROM poi').fetchone()[0], 2)

    def test_rejects_bad_names_and_boxes(self):
        self.assertEqual(run_tool(self.extract, '--name', 'bad name!', '--label', 'X', '--data', self.data).returncode, 1)
        self.assertEqual(run_tool(self.extract, '--name', 'BR-TEST', '--label', 'X', '--box', '5,-50,-40,-20', '--data', self.data).returncode, 1)    # e < w
        self.assertEqual(run_tool(self.extract, '--name', 'BR-TEST', '--label', 'X', '--box', '-50,-30,-40,95', '--data', self.data).returncode, 1)   # n > 90


if __name__ == '__main__':
    unittest.main()
