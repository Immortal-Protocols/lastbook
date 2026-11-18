"""Ontario source -> map archive -> checked local install -> offline map and search.

Uses a tiny made-up GeoPackage and address index. No download, socket or real library.
"""
import contextlib
import importlib.util
import io
import json
import os
import shutil
import sqlite3
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from engine.setup import api, download, install, manifest
from tools.build_addresses import convert_row, ONTARIO_ATTRIBUTION

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('build_ontario', ROOT / 'packaging/build_ontario.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def place_area(db, name, rings, *, extra_polygons=()):
    """Write a tiny fictional MultiPolygon in the same format as Geofabrik."""
    polygons = []
    for polygon in (rings, *extra_polygons):
        wkb = struct.pack('<BII', 1, 3, len(polygon))
        for ring in polygon:
            wkb += struct.pack('<I', len(ring))
            wkb += b''.join(struct.pack('<dd', *point) for point in ring)
        polygons.append(wkb)
    geometry = (b'GP\x00\x01' + struct.pack('<i', 4326)
                + struct.pack('<BII', 1, 6, len(polygons)) + b''.join(polygons))
    db.execute('INSERT INTO gis_osm_places_a_free VALUES(?,?,?,?)', (geometry, 'town', 0, name))


def gpkg(path, longitude=-79.38):
    db = sqlite3.connect(path)
    try:
        for table in ('water_a', 'natural_a', 'landuse_a', 'waterways', 'railways', 'buildings_a', 'pois', 'pois_a', 'natural'):
            db.execute(f'CREATE TABLE gis_osm_{table}_free(geom BLOB,fclass TEXT,name TEXT)')
        db.execute('CREATE TABLE gis_osm_protected_areas_a_free(geom BLOB,fclass TEXT)')
        db.execute('CREATE TABLE gis_osm_places_free(geom BLOB,fclass TEXT,population INTEGER,name TEXT)')
        db.execute('CREATE TABLE gis_osm_places_a_free(geom BLOB,fclass TEXT,population INTEGER,name TEXT)')
        db.execute('CREATE TABLE gis_osm_roads_free(geom BLOB,fclass TEXT,name TEXT,ref TEXT)')
        header = b'GP\x00\x01' + struct.pack('<i', 4326)
        point = header + struct.pack('<BIdd', 1, 1, longitude, 43.65)
        line = header + struct.pack('<BII4d', 1, 2, 2, longitude, 43.65, longitude + .01, 43.66)
        db.execute('INSERT INTO gis_osm_roads_free VALUES(?,?,?,?)', (line, 'residential', 'Queen Street West', None))
        db.execute('INSERT INTO gis_osm_places_free VALUES(?,?,?,?)', (point, 'city', 3_000_000, 'Toronto'))
        # These names reproduce the review finding; the small shapes are fictional.
        place_area(db, 'Moosonee', [[(-80.62, 51.28), (-80.60, 51.28), (-80.60, 51.30),
                                    (-80.62, 51.30), (-80.62, 51.28)]])
        place_area(db, 'Fort Severn', [[(-87.66, 56.00), (-87.64, 56.00), (-87.64, 56.02),
                                      (-87.66, 56.02), (-87.66, 56.00)]],
                   extra_polygons=([[(-87.70, 56.00), (-87.69, 56.00), (-87.69, 56.01),
                                     (-87.70, 56.01), (-87.70, 56.00)]],))
        for name, lon, lat in (('ᒨᓱᓂᔾ Moosonee', -80.615, 51.285),
                               ('ᐗᔕᐦᐅᐠ Fort Severn', -87.645, 56.005)):
            centre = header + struct.pack('<BIdd', 1, 1, lon, lat)
            db.execute('INSERT INTO gis_osm_places_free VALUES(?,?,?,?)', (centre, 'town', 0, name))
        db.execute('INSERT INTO gis_osm_pois_free VALUES(?,?,?)', (point, 'hospital', 'Example Hospital'))
        db.commit()
    finally:
        db.close()


class Ontario(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='ontario-test-')
        self.root = Path(self.temp.name)
        self.source = self.root / 'ontario.gpkg'
        gpkg(self.source)
        self.addresses = self.root / 'addresses.sqlite'
        db = sqlite3.connect(self.addresses)
        try:
            db.executescript('CREATE TABLE addr(num TEXT,street TEXT,norm TEXT,city TEXT,state TEXT,zip TEXT,lat REAL,lon REAL); '
                             'CREATE INDEX addr_num_norm ON addr(num,norm); CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT);')
            db.execute('INSERT INTO addr VALUES(?,?,?,?,?,?,?,?)', convert_row(
                ('100', 'Queen Street West', 'Toronto', 'ON', 'M5H 2N2', 43.65, -79.38), 'CA'))
            db.executemany('INSERT INTO meta VALUES (?,?)', [('release','2026-10-21.0'), ('source_licence','Statistics Canada Open Licence'), ('source_attribution',ONTARIO_ATTRIBUTION)])
            db.commit()
        finally:
            db.close()

    def tearDown(self):
        self.temp.cleanup()

    def build(self, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            return builder.build(self.source, self.root / 'output', '2026-01-01', **kwargs)

    def test_manifest_and_safe_archive(self):
        out = self.build(addresses=self.addresses)
        mf = manifest.validate(json.loads((out / 'manifest-v1.json').read_text()))
        self.assertIsNotNone(mf)
        self.assertEqual(mf['maps'][0]['id'], 'CA-ON')
        self.assertEqual(mf['address_indexes'][0]['id'], 'CA-ON')
        with zipfile.ZipFile(out / 'Lastbook-Map-CA-ON.zip') as archive:
            self.assertNotIn('derived/geo/terrain.sqlite', archive.namelist())
            self.assertNotIn('library-data/catalog.json', archive.namelist())
        install.check_zip(out / 'Lastbook-Map-CA-ON.zip', mf['maps'][0]['installed_bytes'], install.map_member)
        self.assertEqual(builder.digest(out / 'Lastbook-Map-CA-ON.zip'), mf['maps'][0]['files'][0]['sha256'])

    def test_build_receipt_records_inputs_and_keeps_paths_private(self):
        out = self.build(addresses=self.addresses)
        receipt = json.loads((out / 'build-receipt.json').read_text())
        self.assertEqual(receipt['inputs'][0]['sha256'], builder.digest(self.source))
        self.assertEqual(receipt['inputs'][1]['sha256'], builder.digest(self.addresses))
        self.assertEqual(receipt['inputs'][1]['release'], '2026-10-21.0')
        self.assertIsNone(receipt['inputs'][1]['data_as_of'])
        self.assertEqual(receipt['inputs'][1]['attribution'], ONTARIO_ATTRIBUTION)
        self.assertNotIn(str(self.root), json.dumps(receipt))
        self.assertEqual(receipt['outputs']['Lastbook-Map-CA-ON.zip']['sha256'],
                         builder.digest(out / 'Lastbook-Map-CA-ON.zip'))
        payload = out / 'LastbookData'
        description = json.loads((payload / 'map-set.json').read_text())
        for name, digest in description['sha256'].items():
            self.assertEqual(builder.digest(payload / name), digest)

    def test_corrupt_local_address_archive_fails_before_activation(self):
        out = self.build(addresses=self.addresses)
        address_zip = out / 'Lastbook-Addresses-CA-ON.zip'
        data = bytearray(address_zip.read_bytes())
        data[0] ^= 1
        address_zip.write_bytes(data)
        library = self.root / 'LastbookData'
        (library / 'library-data').mkdir(parents=True)
        (library / 'library-data/catalog.json').write_text('[]')
        mf = manifest.Manifest(bundled=manifest.validate(json.loads((out / 'manifest-v1.json').read_text())), remote=None)
        setup = api.Setup('manage', self.root / 'settings', self.root,
                          current=library, manifest=mf, home=self.root / 'home')
        with patch.object(download, '_open', side_effect=AssertionError('No network fallback for an explicitly selected file')):
            setup.use(str(out / 'Lastbook-Map-CA-ON.zip'))
            setup.thread.join(timeout=10)
        self.assertEqual(setup.job['state'], 'failed')
        self.assertEqual(setup.job['error']['code'], 'found_mismatch')
        self.assertEqual(install.map_name(library), 'base')

    def test_finished_build_is_not_overwritten(self):
        out = self.build()
        before = (out / 'manifest-v1.json').read_bytes()
        with self.assertRaisesRegex(ValueError, 'already exists'):
            self.build()
        self.assertEqual((out / 'manifest-v1.json').read_bytes(), before)

    def test_ontario_can_replace_all_us_map_and_search_offline(self):
        out = self.build(addresses=self.addresses)
        library = self.root / 'LastbookData'
        (library / 'library-data').mkdir(parents=True)
        (library / 'library-data/catalog.json').write_text('[]')
        (library / 'pack.json').write_text('{"name":"all","map":"us"}')
        (library / 'derived/geo').mkdir(parents=True)
        (library / 'derived/geo/terrain.sqlite').write_bytes(b'old US terrain')
        settings = self.root / 'settings'
        with patch.object(download, '_open', side_effect=AssertionError('A local install must not open a connection')):
            mf = manifest.Manifest(bundled=manifest.validate(json.loads((out / 'manifest-v1.json').read_text())), remote=None)
            setup = api.Setup('manage', settings, self.root, current=library,
                              manifest=mf, home=self.root / 'home')
            job = setup.use(str(out / 'Lastbook-Map-CA-ON.zip'))
            self.assertEqual([item['kind'] for item in job['items']], ['map', 'addresses'])
            setup.thread.join(timeout=10)
            self.assertFalse(setup.thread.is_alive())
            self.assertEqual(setup.job['state'], 'done', setup.job.get('error'))
            # A paused/reloaded job still recognizes a hyphenated region and its sidecar.
            self.assertIsNotNone(setup._checked_job(json.loads(json.dumps(setup.job))))
            installed, note = api.startup(settings)
            self.assertFalse(note.get('error'))
            self.assertEqual(installed, library)
            self.assertEqual(install.map_name(library), 'CA-ON')
            self.assertFalse((library / 'derived/geo/terrain.sqlite').exists())
            self.assertEqual(setup.current_info()['address_indexes'], ['CA-ON'])
        script = """import json,math,server
info = server.map_info()
tile = json.loads(server._map_tile(14,4579,5980,0))
towns = {}
for name in ('Moosonee', 'Fort Severn'):
    hits = server.places(name)
    labels = []
    if hits:
        lon, lat = hits[0]['lon'], hits[0]['lat']
        x = int((lon + 180) / 360 * 2**12)
        y = int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * 2**12)
        labels = json.loads(server._map_tile(12,x,y,0))['layers'].get('place', [])
    towns[name] = {'hits': hits, 'labels': labels}
print(json.dumps({'info':info,'places':server.places('Toronto'),
 'addresses':server.places('100 Queen St W Toronto ON M5H 2N2'),
 'pins':server.pins(-79.5,43.5,-79.2,43.8,14,['hospital']), 'tile':tile, 'towns':towns}))
"""
        process = subprocess.run([sys.executable, '-B', '-c', script], cwd=ROOT,
                                 env={**os.environ, 'LASTBOOK_DATA': str(library)}, capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        result = json.loads(process.stdout)
        self.assertEqual(result['info']['region'], 'CA-ON')
        self.assertIn(ONTARIO_ATTRIBUTION, json.dumps(result['info']['datasets']))
        self.assertEqual(result['info']['data_as_of'], '2026-01-01')
        self.assertEqual(result['places'][0]['name'], 'Toronto')
        for name, town in result['towns'].items():
            with self.subTest(name=name):
                self.assertEqual(sum(hit['name'] == name for hit in town['hits']), 1)
                self.assertEqual(town['hits'][0]['name'], name)
                self.assertEqual(town['hits'][0]['kind'], 'town')
                self.assertTrue(town['hits'][0]['onMap'])
                self.assertIn(name, [label[1] for label in town['labels']])
                if name == 'Moosonee':
                    expected, native = (51.285, -80.615), 'ᒨᓱᓂᔾ Moosonee'
                else:
                    expected, native = (56.005, -87.645), 'ᐗᔕᐦᐅᐠ Fort Severn'
                self.assertEqual((town['hits'][0]['lat'], town['hits'][0]['lon']), expected)
                self.assertIn(native, [label[1] for label in town['labels']])
        self.assertEqual(result['addresses'][0]['detail'], 'Toronto, ON, M5H 2N2')
        self.assertIn('Example Hospital', json.dumps(result['pins']))
        self.assertNotIn('USGS', json.dumps(result['info']['datasets']))

    def test_point_only_extract_still_builds(self):
        with contextlib.closing(sqlite3.connect(self.source)) as db:
            db.execute('DROP TABLE gis_osm_places_a_free')
            db.commit()
        out = self.build()
        with contextlib.closing(sqlite3.connect(out / 'LastbookData/derived/geo/places.sqlite')) as db:
            self.assertEqual(db.execute("SELECT name,lat,lon FROM place WHERE name='Toronto'").fetchall(),
                             [('Toronto', 43.65, -79.38)])

    def test_polygon_keeps_explicit_point_and_distant_namesake(self):
        with contextlib.closing(sqlite3.connect(self.source)) as db:
            db.execute("UPDATE gis_osm_places_free SET fclass='town'")
            place_area(db, 'Toronto', [[(-79.40, 43.60), (-79.30, 43.60), (-79.30, 43.70),
                                       (-79.40, 43.70), (-79.40, 43.60)]])
            place_area(db, 'Toronto', [[(-80.40, 44.60), (-80.30, 44.60), (-80.30, 44.70),
                                       (-80.40, 44.70), (-80.40, 44.60)]])
            db.commit()
        out = self.build()
        with contextlib.closing(sqlite3.connect(out / 'LastbookData/derived/geo/places.sqlite')) as db:
            points = db.execute("SELECT lat,lon FROM place WHERE name='Toronto' ORDER BY lat").fetchall()
            self.assertEqual(len(points), 2)
            self.assertEqual(points[0], (43.65, -79.38))
            self.assertTrue(44.60 < points[1][0] < 44.70)
            self.assertTrue(-80.40 < points[1][1] < -80.30)

    def test_polygon_alias_rejects_outside_point_and_extra_name_words(self):
        with contextlib.closing(sqlite3.connect(self.source)) as db:
            header = b'GP\x00\x01' + struct.pack('<i', 4326)
            outside = header + struct.pack('<BIdd', 1, 1, -81.0, 52.0)
            db.execute("UPDATE gis_osm_places_free SET geom=? WHERE name='ᒨᓱᓂᔾ Moosonee'", (outside,))
            nearby = header + struct.pack('<BIdd', 1, 1, -80.618, 51.282)
            db.execute('INSERT INTO gis_osm_places_free VALUES(?,?,?,?)',
                       (nearby, 'town', 0, 'ᒨᓱᓂᔾ Moosonee North'))
            db.commit()
        out = self.build()
        with contextlib.closing(sqlite3.connect(out / 'LastbookData/derived/geo/places.sqlite')) as db:
            lat, lon = db.execute("SELECT lat,lon FROM place WHERE name='Moosonee'").fetchone()
            self.assertTrue(51.28 < lat < 51.30 and -80.62 < lon < -80.60)
            self.assertNotEqual((lat, lon), (51.282, -80.618))

    def test_rejects_wrong_geography(self):
        self.source.unlink()
        gpkg(self.source, longitude=-118.0)
        with self.assertRaisesRegex(ValueError, 'within Ontario'):
            self.build()
        self.assertFalse((self.root / 'output/CA-ON').exists())

    def test_address_ids_cannot_be_paths(self):
        out = self.build(addresses=self.addresses)
        data = json.loads((out / 'manifest-v1.json').read_text())
        for value in ('../CA-ON', 'CA/ON', 'CA-ON.sqlite', 'CA-ON\n', 'ca-on'):
            with self.subTest(value=value):
                data['address_indexes'][0]['id'] = value
                self.assertIsNone(manifest.validate(data))

    def test_local_map_selection_also_registers_pinned_addresses(self):
        out = self.build(addresses=self.addresses)
        mf = manifest.Manifest(bundled=manifest.validate(json.loads((out / 'manifest-v1.json').read_text())), remote=None)
        setup = api.Setup('first-run', self.root / 'settings', self.root / 'install',
                          manifest=mf, home=self.root / 'home')
        with patch.object(sys, 'frozen', True, create=True):
            result = setup.use(str(out / 'Lastbook-Map-CA-ON.zip'))
            self.assertEqual(result['kind'], 'map')
            self.assertEqual(result['id'], 'CA-ON')
            self.assertTrue(result['noted'])
            self.assertIn('Lastbook-Addresses-CA-ON.zip', setup.sources)

    def test_canadian_addresses_survive_library_upgrade(self):
        old, new = self.root / 'old', self.root / 'new'
        folder = old / 'derived/geo/addresses'
        folder.mkdir(parents=True)
        (folder / 'CA-ON.sqlite').write_bytes(b'Ontario addresses')
        (folder / 'CA-ON.json').write_text('{}')
        install.carry_over(old, new)
        self.assertEqual((new / 'derived/geo/addresses/CA-ON.sqlite').read_bytes(), b'Ontario addresses')
        self.assertTrue((new / 'derived/geo/addresses/CA-ON.json').exists())

    @unittest.skipUnless(shutil.which('node'), 'Node is needed for the setup interface check')
    def test_setup_selection_includes_ontario_download(self):
        process = subprocess.run(['node', str(ROOT / 'app/tests/setup_regions_test.mjs')], capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)


class PolygonPlacePoints(unittest.TestCase):
    def test_point_is_inside_concave_area_instead_of_at_first_vertex_or_box_centre(self):
        ring = [0, 0, 6, 0, 6, 2, 2, 2, 2, 6, 0, 6, 0, 0]
        for outline in (ring, [v for point in reversed(list(zip(ring[::2], ring[1::2]))) for v in point]):
            with self.subTest(outline=outline):
                x, y = builder.build_map.polygon_point([outline])
                self.assertTrue(0 < x < 6 and 0 < y < 6)
                self.assertTrue(x < 2 or y < 2)

    def test_point_avoids_hole_in_either_winding(self):
        outer = [0, 0, 6, 0, 6, 6, 0, 6, 0, 0]
        hole = [2, 2, 4, 2, 4, 4, 2, 4, 2, 2]
        for inner in (hole, [v for point in reversed(list(zip(hole[::2], hole[1::2]))) for v in point]):
            with self.subTest(inner=inner):
                x, y = builder.build_map.polygon_point([outer, inner])
                self.assertTrue(0 < x < 6 and 0 < y < 6)
                self.assertFalse(2 <= x <= 4 and 2 <= y <= 4)

    def test_point_is_on_main_polygon_instead_of_between_islands(self):
        small = [10, 0, 11, 0, 11, 1, 10, 1, 10, 0]
        large = [0, 0, 4, 0, 4, 4, 0, 4, 0, 0]
        x, y = builder.build_map.polygon_point([small, large])
        self.assertTrue(0 < x < 4 and 0 < y < 4)

    def test_empty_or_flat_polygon_has_no_label_point(self):
        for parts in ([], [[]], [[0, 0, 1, 0, 2, 0, 0, 0]]):
            with self.subTest(parts=parts):
                self.assertIsNone(builder.build_map.polygon_point(parts))


if __name__ == '__main__':
    unittest.main()
