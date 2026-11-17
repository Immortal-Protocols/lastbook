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


def gpkg(path, longitude=-79.38):
    db = sqlite3.connect(path)
    try:
        for table in ('water_a', 'natural_a', 'landuse_a', 'waterways', 'railways', 'buildings_a', 'pois', 'pois_a', 'natural'):
            db.execute(f'CREATE TABLE gis_osm_{table}_free(geom BLOB,fclass TEXT,name TEXT)')
        db.execute('CREATE TABLE gis_osm_protected_areas_a_free(geom BLOB,fclass TEXT)')
        db.execute('CREATE TABLE gis_osm_places_free(geom BLOB,fclass TEXT,population INTEGER,name TEXT)')
        db.execute('CREATE TABLE gis_osm_roads_free(geom BLOB,fclass TEXT,name TEXT,ref TEXT)')
        header = b'GP\x00\x01' + struct.pack('<i', 4326)
        point = header + struct.pack('<BIdd', 1, 1, longitude, 43.65)
        line = header + struct.pack('<BII4d', 1, 2, 2, longitude, 43.65, longitude + .01, 43.66)
        db.execute('INSERT INTO gis_osm_roads_free VALUES(?,?,?,?)', (line, 'residential', 'Queen Street West', None))
        db.execute('INSERT INTO gis_osm_places_free VALUES(?,?,?,?)', (point, 'city', 3_000_000, 'Toronto'))
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
        script = """import json,server
info = server.map_info()
tile = json.loads(server._map_tile(14,4579,5980,0))
print(json.dumps({'info':info,'places':server.places('Toronto'),
 'addresses':server.places('100 Queen St W Toronto ON M5H 2N2'),
 'pins':server.pins(-79.5,43.5,-79.2,43.8,14,['hospital']), 'tile':tile}))
"""
        process = subprocess.run([sys.executable, '-B', '-c', script], cwd=ROOT,
                                 env={**os.environ, 'LASTBOOK_DATA': str(library)}, capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        result = json.loads(process.stdout)
        self.assertEqual(result['info']['region'], 'CA-ON')
        self.assertIn(ONTARIO_ATTRIBUTION, json.dumps(result['info']['datasets']))
        self.assertEqual(result['info']['data_as_of'], '2026-01-01')
        self.assertEqual(result['places'][0]['name'], 'Toronto')
        self.assertEqual(result['addresses'][0]['detail'], 'Toronto, ON, M5H 2N2')
        self.assertIn('Example Hospital', json.dumps(result['pins']))
        self.assertNotIn('USGS', json.dumps(result['info']['datasets']))

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


if __name__ == '__main__':
    unittest.main()
