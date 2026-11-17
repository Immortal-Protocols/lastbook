"""Spain map builds from local OSM extracts; no network or large files required."""
import json
import importlib.util
import hashlib
import os
import shutil
import sqlite3
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import zipfile
from pathlib import Path
from unittest import mock
from app.tests.test_setup import Base as SetupBase, make_pack

ROOT = Path(__file__).resolve().parents[2]
BUILDER = ROOT / 'tools/build_spain.py'
TABLES = ('water_a', 'natural_a', 'landuse_a', 'protected_areas_a', 'waterways', 'railways',
          'roads', 'buildings_a', 'places', 'places_a', 'pois', 'pois_a', 'natural')


def geom(kind, coordinates):
    header = b'GP\x00\x01' + struct.pack('<i', 4326)
    if kind == 'point':
        return header + struct.pack('<BIdd', 1, 1, *coordinates)
    if kind == 'line':
        return header + struct.pack('<BII', 1, 2, len(coordinates)) + b''.join(struct.pack('<dd', *p) for p in coordinates)
    points = coordinates
    return header + struct.pack('<BIII', 1, 3, 1, len(points)) + b''.join(struct.pack('<dd', *p) for p in points)


def make_extract(path, name, lon, lat):
    db = sqlite3.connect(path)
    for table in TABLES:
        db.execute(f'CREATE TABLE gis_osm_{table}_free (geom BLOB, osm_id TEXT, fclass TEXT, name TEXT, ref TEXT, population INTEGER)')
    db.execute('INSERT INTO gis_osm_places_free VALUES (?,?,?,?,?,?)', (geom('point', (lon, lat)), name, 'city', name, None, 50000))
    db.execute('INSERT INTO gis_osm_pois_free VALUES (?,?,?,?,?,?)', (geom('point', (lon, lat)), name, 'hospital', name + ' Hospital', None, None))
    db.execute('INSERT INTO gis_osm_roads_free VALUES (?,?,?,?,?,?)', (geom('line', [(-5.31, 35.90), (-5.30, 35.91)]), 'shared-road', 'residential', 'Calle Ejemplo', None, None))
    db.execute('INSERT INTO gis_osm_buildings_a_free VALUES (?,?,?,?,?,?)', (geom('polygon', [(lon, lat), (lon+.001, lat), (lon+.001, lat+.001), (lon, lat)]), name, 'building', None, None, None))
    db.commit()
    db.close()


class SpainMapBuild(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.sources = self.root / 'sources'
        self.sources.mkdir()
        make_extract(self.sources / 'ceuta.gpkg', 'Ceuta', -5.30, 35.90)
        make_extract(self.sources / 'canary-islands.gpkg', 'Las Palmas', -15.43, 28.13)

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, *args):
        return subprocess.run([sys.executable, '-B', str(BUILDER), '--input-dir', str(self.sources),
                               '--output-dir', str(self.root / 'output'), *args], capture_output=True, text=True)

    def test_complete_release_rejects_missing_extracts(self):
        result = self.build()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('missing', result.stderr.lower())
        self.assertFalse((self.root / 'output/Lastbook-Map-ES.zip').exists())

    def test_build_accepts_source_paths_with_uri_characters(self):
        renamed = self.root / 'source #1?'
        self.sources.rename(renamed)
        self.sources = renamed
        result = self.build('--sample')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_exclave_context_shows_land_without_filling_nearby_sea(self):
        context = json.loads((ROOT / 'web/spain-context.json').read_text())
        def ring_contains(ring, lon, lat):
            inside = False
            for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
                if (y1 > lat) != (y2 > lat) and lon < (x2-x1)*(lat-y1)/(y2-y1)+x1:
                    inside = not inside
            return inside
        def on_land(lon, lat):
            for feature in context['features']:
                geometry = feature['geometry']
                polygons = [geometry['coordinates']] if geometry['type'] == 'Polygon' else geometry['coordinates']
                for poly in polygons:
                    if ring_contains(poly[0], lon, lat) and not any(ring_contains(hole, lon, lat) for hole in poly[1:]):
                        return True
            return False
        self.assertTrue(on_land(-5.32, 35.89))
        self.assertTrue(on_land(-2.94, 35.29))
        self.assertFalse(on_land(-5.32, 35.98))
        self.assertFalse(on_land(-2.90, 35.36))

    def test_existing_single_extract_converter_still_builds(self):
        destination = self.root / 'legacy.sqlite'
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'tools/build_map.py'),
                                 str(self.sources / 'ceuta.gpkg'), str(destination)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        db = sqlite3.connect(destination)
        self.assertEqual(db.execute("SELECT name FROM feat WHERE layer='road'").fetchone()[0], 'Calle Ejemplo')
        self.assertEqual(db.execute("SELECT name FROM poi WHERE cls='hospital'").fetchone()[0], 'Ceuta Hospital')
        db.close()

    def test_distinct_geometries_with_the_same_osm_id_are_not_discarded(self):
        db = sqlite3.connect(self.sources / 'ceuta.gpkg')
        db.execute('INSERT INTO gis_osm_roads_free VALUES (?,?,?,?,?,?)',
                   (geom('line', [(-5.32, 35.92), (-5.31, 35.93)]), 'shared-road', 'residential', 'Calle Ejemplo', None, None))
        db.commit()
        db.close()
        result = self.build('--sample')
        self.assertEqual(result.returncode, 0, result.stderr)
        db = sqlite3.connect(self.root / 'output/ES-SAMPLE/derived/geo/national.sqlite')
        self.assertEqual(db.execute("SELECT count(*) FROM feat WHERE layer='road' AND name='Calle Ejemplo'").fetchone()[0], 2)
        db.close()

    def test_island_land_and_capital_are_visible_at_country_zoom(self):
        db = sqlite3.connect(self.sources / 'canary-islands.gpkg')
        ring = [(-15.5, 28.0), (-15.3, 28.0), (-15.3, 28.2), (-15.5, 28.0)]
        db.execute('INSERT INTO gis_osm_places_a_free VALUES (?,?,?,?,?,?)',
                   (geom('polygon', ring), 'island-1', 'island', 'Island', None, None))
        db.execute('INSERT INTO gis_osm_places_free VALUES (?,?,?,?,?,?)',
                   (geom('point', (-3.7, 40.4)), 'capital-1', 'national_capital', 'Madrid', None, 3000000))
        db.commit()
        db.close()
        result = self.build('--sample')
        self.assertEqual(result.returncode, 0, result.stderr)
        db = sqlite3.connect(self.root / 'output/ES-SAMPLE/derived/geo/national.sqlite')
        self.assertEqual(db.execute("SELECT count(*) FROM feat WHERE layer='island'").fetchone()[0], 1)
        self.assertEqual(db.execute("SELECT cls,minz FROM feat WHERE name='Madrid'").fetchone(), ('city', 5))
        db.close()

    def test_sample_combines_regions_and_installs_without_claiming_full_spain(self):
        result = self.build('--sample')
        self.assertEqual(result.returncode, 0, result.stderr)
        archive = self.root / 'output/Lastbook-Map-ES-SAMPLE.zip'
        self.assertTrue(archive.exists())
        from engine.setup import install
        class Control:
            def check(self):
                pass
        with zipfile.ZipFile(archive) as z:
            size = sum(i.file_size for i in z.infolist())
        unpacked = install.unpack(archive, self.root / 'unpacked', size, Control(), lambda *_: None, allowed=install.map_member)
        self.assertEqual(install.map_name(unpacked), 'ES-SAMPLE')
        self.assertEqual(install.check_map(unpacked)['name'], 'ES-SAMPLE')
        db = sqlite3.connect(unpacked / 'derived/geo/national.sqlite')
        self.assertEqual(db.execute("SELECT count(*) FROM feat WHERE layer='road' AND name='Calle Ejemplo'").fetchone()[0], 1)
        self.assertEqual(db.execute("SELECT count(*) FROM feat WHERE layer='bldg'").fetchone()[0], 2)
        self.assertEqual(db.execute("SELECT count(*) FROM poi WHERE cls='hospital'").fetchone()[0], 2)
        self.assertEqual(db.execute("SELECT value FROM meta WHERE key='license_url'").fetchone()[0],
                         'https://opendatacommons.org/licenses/odbl/1-0/')
        db.close()
        db = sqlite3.connect(unpacked / 'derived/geo/places.sqlite')
        self.assertEqual({r[0] for r in db.execute('SELECT name FROM place WHERE kind=\'city\'')}, {'Ceuta', 'Las Palmas'})
        db.close()

    def test_installed_sample_serves_spain_tiles_pins_and_places_offline(self):
        result = self.build('--sample')
        self.assertEqual(result.returncode, 0, result.stderr)
        from engine.setup import install
        class Control:
            def check(self):
                pass
        archive = self.root / 'output/Lastbook-Map-ES-SAMPLE.zip'
        with zipfile.ZipFile(archive) as z:
            size = sum(i.file_size for i in z.infolist())
        lib = install.unpack(archive, self.root / 'unpacked', size, Control(), lambda *_: None, allowed=install.map_member)
        (lib / 'pack.json').write_text('{"name":"small"}')
        (lib / 'library-data').mkdir()
        (lib / 'library-data/catalog.json').write_text('{"records": []}')
        addresses = lib / 'derived/geo/addresses'
        addresses.mkdir()
        db = sqlite3.connect(addresses / 'CA.sqlite')
        db.execute('CREATE TABLE addr(num TEXT,street TEXT,norm TEXT,city TEXT,state TEXT,zip TEXT,lat REAL,lon REAL)')
        db.execute("INSERT INTO addr VALUES('123','Main Street','main st','Example','CA','90001',34,-118)")
        db.commit()
        db.close()
        script = '''import json, math, server
z=15; lon=-5.30; lat=35.90
x=int((lon+180)/360*(2**z))
y=int((1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*(2**z))
print(json.dumps({'info':server.map_info(), 'places':server.places('Ceuta'),
                  'old_index':server.address_search.find_addresses('123 Main Street',server.HERE / 'derived/geo'),
                  'address':server.places('123 Main Street'),
                  'pins':server.pins(-5.4,35.8,-5.2,36.0,15,['hospital']),
                  'tile':json.loads(server.map_tile(z,x,y))}))'''
        env = {**os.environ, 'LASTBOOK_DATA': str(lib)}
        ran = subprocess.run([sys.executable, '-B', '-c', script], cwd=ROOT, env=env, capture_output=True, text=True)
        self.assertEqual(ran.returncode, 0, ran.stderr)
        data = json.loads(ran.stdout)
        self.assertEqual(data['info']['map_region'], 'ES-SAMPLE')
        self.assertFalse(data['info']['street_addresses'])
        self.assertTrue(data['old_index'])
        self.assertEqual(data['address'], [])
        self.assertEqual(data['places'][0]['name'], 'Ceuta')
        self.assertTrue(data['places'][0]['onMap'])
        self.assertTrue(data['pins']['points'])
        self.assertIn('road', data['tile']['layers'])

    @unittest.skipUnless(shutil.which('node'), 'needs Node')
    def test_us_all_library_does_not_claim_to_include_spain(self):
        result = subprocess.run([shutil.which('node'), str(ROOT / 'app/tests/setup_map_test.mjs'),
                                 str(ROOT / 'web/setup-map.js')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_release_manifest_offers_unpublished_spain_and_keeps_a_published_entry(self):
        source = self.root / 'manifest.json'
        output = self.root / 'bundled.json'
        pack = {'id': 'small', 'title': 'Small', 'available': False, 'files': []}
        source.write_text(json.dumps({'version': 1, 'packs': [pack]}))
        command = [sys.executable, '-B', str(ROOT / 'packaging/release_manifest.py'), '--packs', str(source), '--out', str(output)]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        spain = next(x for x in json.loads(output.read_text())['maps'] if x['id'] == 'ES')
        self.assertEqual(spain['kind'], 'country')
        self.assertFalse(spain['available'])
        published = {'id': 'ES', 'title': 'Spain', 'kind': 'country', 'available': True, 'installed_bytes': 12,
                     'files': [{'name': 'Lastbook-Map-ES.zip', 'size': 10, 'sha256': 'a' * 64, 'kind': 'zip',
                                'url': 'https://downloads.lastbook.org/maps/Lastbook-Map-ES.zip'}]}
        source.write_text(json.dumps({'version': 1, 'packs': [pack], 'maps': [published]}))
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(output.read_text())['maps'], [published])

    def test_release_zip_uses_the_spain_map_contract(self):
        result = self.build('--sample')
        self.assertEqual(result.returncode, 0, result.stderr)
        spec = importlib.util.spec_from_file_location('state_maps', ROOT / 'packaging/state_maps.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        archive = self.root / 'release.zip'
        module.make_zip(self.root / 'output/ES-SAMPLE', archive, module.SPAIN_ALLOWED)
        with zipfile.ZipFile(archive) as z:
            self.assertEqual(set(z.namelist()), {'map-set.json', 'derived/geo/map.sqlite', 'derived/geo/national.sqlite',
                                                 'derived/geo/places.sqlite', 'derived/geo/national-status.json',
                                                 'derived/geo/socal-cells.json'})

    def test_country_release_keeps_the_legacy_manifest_untouched(self):
        spec = importlib.util.spec_from_file_location('state_maps_publish', ROOT / 'packaging/state_maps.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        legacy = self.root / 'manifest-v1.json'
        legacy.write_text('{"version":1,"packs":[],"maps":[]}')
        before = legacy.read_bytes()
        module.MANIFEST = legacy
        module.MANIFEST_SPAIN = self.root / 'manifest-spain-v1.json'
        uploaded = {}
        class Publisher:
            @staticmethod
            def s3(ctx, method, key, body, headers):
                uploaded[key] = body
                return 200, {}, b''
        module.R = Publisher
        module.public_sha = lambda url: (hashlib.sha256(uploaded[url.rsplit('/', 1)[-1]]).hexdigest(), 0)
        module.list_in_manifest(None, {'id': 'ES', 'title': 'Spain', 'kind': 'country'})
        self.assertEqual(legacy.read_bytes(), before)
        self.assertEqual(json.loads(module.MANIFEST_SPAIN.read_text())['maps'][0]['id'], 'ES')
        self.assertEqual(set(uploaded), {'manifest-spain-v1.json'})

    def test_release_scan_rejects_a_sample_relabelled_as_complete(self):
        result = self.build('--sample')
        self.assertEqual(result.returncode, 0, result.stderr)
        fixture = self.root / 'output/ES-SAMPLE'
        info = json.loads((fixture / 'map-set.json').read_text())
        info['name'] = 'ES'
        (fixture / 'map-set.json').write_text(json.dumps(info))
        terms = self.root / 'derived/packs/private-terms.txt'
        terms.parent.mkdir(parents=True)
        terms.write_text('a-forbidden-fixture-word\n')
        spec = importlib.util.spec_from_file_location('state_maps_scan', ROOT / 'packaging/state_maps.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.ROOT = self.root
        failures, _ = module.scan(fixture, 'ES')
        self.assertTrue(any('Spain input' in failure for failure in failures), failures)

    def test_complete_map_passes_release_scan(self):
        # Distinct files stand in for every required input; this is not geographic coverage evidence.
        for name in ('andalucia', 'aragon', 'asturias', 'cantabria', 'castilla-la-mancha', 'castilla-y-leon',
                     'cataluna', 'extremadura', 'galicia', 'islas-baleares', 'la-rioja', 'madrid',
                     'melilla', 'murcia', 'navarra', 'pais-vasco', 'valencia'):
            shutil.copyfile(self.sources / 'ceuta.gpkg', self.sources / (name + '.gpkg'))
        result = self.build()
        self.assertEqual(result.returncode, 0, result.stderr)
        terms = self.root / 'derived/packs/private-terms.txt'
        terms.parent.mkdir(parents=True)
        terms.write_text('a-forbidden-fixture-word\n')
        spec = importlib.util.spec_from_file_location('state_maps_scan_full', ROOT / 'packaging/state_maps.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.ROOT = self.root
        failures, _ = module.scan(self.root / 'output/ES', 'ES')
        self.assertEqual(failures, [])


class SpainSetupDownload(SetupBase):
    def test_picker_can_refresh_after_initial_country_manifest_fetch_fails(self):
        from app.tests.test_setup import ALLOWED
        from engine.setup import manifest
        base = self.manifest().current
        base['maps'] = [{'id': 'ES', 'title': 'Spain', 'kind': 'country', 'available': False,
                         'installed_bytes': None, 'files': []}]
        self.files.data['manifest-v1.json'] = json.dumps(base).encode()
        mf = manifest.Manifest(bundled=base, remote=f'{self.base}/manifest-v1.json',
                               spain_remote=f'{self.base}/manifest-spain-v1.json', allowed=ALLOWED, context=self.ctx)
        setup = self.setup(manifest=mf)
        setup.state()
        mf.fetching.join(5)
        self.assertFalse(mf.map('ES')['available'])
        country = {'id': 'ES', 'title': 'Spain', 'kind': 'country', 'available': True, 'installed_bytes': 12,
                   'files': [{'name': 'Lastbook-Map-ES.zip', 'url': f'{self.base}/Lastbook-Map-ES.zip',
                              'size': 10, 'sha256': 'a' * 64, 'kind': 'zip'}]}
        self.files.data['manifest-spain-v1.json'] = json.dumps({'version': 1, 'maps': [country]}).encode()
        setup.refresh_manifest()
        mf.fetching.join(5)
        self.assertTrue(next(m for m in setup.state()['manifest']['maps'] if m['id'] == 'ES')['available'])

    def test_manifest_reports_when_its_background_fetch_is_in_progress(self):
        from engine.setup import download
        started, release = threading.Event(), threading.Event()
        mf = self.manifest()
        mf.remote = f'{self.base}/manifest-v1.json'
        def blocked(*args, **kwargs):
            started.set()
            release.wait(5)
            return None
        with mock.patch.object(download, 'fetch_small', blocked):
            mf.fetch_once()
            self.assertTrue(started.wait(2))
            try:
                self.assertTrue(mf.public()['fetching'])
            finally:
                release.set()
                mf.fetching.join(5)
            self.assertFalse(mf.public()['fetching'])

    def test_paused_spain_download_resumes_after_country_manifest_loads(self):
        self._resume_spain_after_restart(True)

    def test_paused_spain_download_survives_without_a_bundled_placeholder(self):
        self._resume_spain_after_restart(False)

    def test_failed_spain_download_retries_after_country_manifest_loads(self):
        self._resume_spain_after_restart(True, failed=True)

    def test_restart_does_not_reuse_an_older_same_size_archive_or_extraction(self):
        self._restart_with_new_country_archive()

    def test_retry_after_staging_cleanup_failure_does_not_reuse_old_files(self):
        self._restart_with_new_country_archive(cleanup_failure=True)

    def _restart_with_new_country_archive(self, cleanup_failure=False):
        from app.tests.test_setup import ALLOWED, make_map
        from engine.setup import api, manifest
        library = self.parent / 'LastbookData'
        (library / 'library-data').mkdir(parents=True)
        (library / 'library-data/catalog.json').write_text('{}')
        (library / 'pack.json').write_text('{"name":"small","map":"base"}')
        old_zip, new_zip = self.tmp / 'old.zip', self.tmp / 'new.zip'
        old_files = make_map(old_zip, state='ES')
        new_files = make_map(new_zip, state='ES')
        old_data, new_data = old_zip.read_bytes(), new_zip.read_bytes()
        self.assertEqual(len(old_data), len(new_data))
        self.assertNotEqual(old_data, new_data)
        name = 'Lastbook-Map-ES.zip'
        def entry(data):
            return {'id': 'ES', 'title': 'Spain', 'kind': 'country', 'available': True,
                    'installed_bytes': sum(map(len, new_files.values())),
                    'files': [{'name': name, 'url': f'{self.base}/{name}', 'size': len(data),
                               'sha256': hashlib.sha256(data).hexdigest(), 'kind': 'zip'}]}
        old = self.manifest()
        old.current['maps'] = manifest.validate({'version': 1, 'maps': [entry(old_data)]}, ALLOWED)['maps']
        self.files.data[name] = old_data
        self.files.pace = 0.03
        original = self.setup('manage', current=library, manifest=old)
        original.start(map_id='ES')
        time.sleep(0.06)
        self.assertEqual(original.pause()['state'], 'paused')
        work = self.parent / 'LastbookData.setup'
        for part in (work / 'downloads' / (name + '.part'), work / 'downloads' / (name + '.part.json')):
            part.unlink(missing_ok=True)
        (work / 'downloads' / name).write_bytes(old_data)
        staged = work / 'unpack-map/LastbookData/derived/geo/map.sqlite'
        staged.parent.mkdir(parents=True)
        staged.write_bytes(old_files['derived/geo/map.sqlite'])
        base = self.manifest().current
        base['maps'] = [{'id': 'ES', 'title': 'Spain', 'kind': 'country', 'available': False,
                         'installed_bytes': None, 'files': []}]
        self.files.data['manifest-v1.json'] = json.dumps(base).encode()
        self.files.data['manifest-spain-v1.json'] = json.dumps({'version': 1, 'maps': [entry(new_data)]}).encode()
        self.files.data[name] = new_data
        self.files.pace = 0
        fresh = manifest.Manifest(bundled=base, remote=f'{self.base}/manifest-v1.json',
                                  spain_remote=f'{self.base}/manifest-spain-v1.json', allowed=ALLOWED, context=self.ctx)
        resumed = self.setup('manage', current=library, manifest=fresh)
        fresh._fetch()
        if cleanup_failure:
            remove, failed = shutil.rmtree, []
            def flaky(path, *args, **kwargs):
                if Path(path) == work / 'unpack-map' and not failed:
                    failed.append(True)
                    raise PermissionError('staging temporarily locked')
                return remove(path, *args, **kwargs)
            with mock.patch.object(api.shutil, 'rmtree', side_effect=flaky):
                resumed.resume()
                self.assertEqual(self.wait(resumed)['state'], 'failed')
                resumed.retry()
                self.assertEqual(self.wait(resumed)['state'], 'done')
        else:
            resumed.resume()
            self.assertEqual(self.wait(resumed)['state'], 'done')
        lib, note = api.startup(self.settings)
        self.assertFalse(note.get('error'))
        self.assertEqual(hashlib.sha256((lib / 'derived/geo/map.sqlite').read_bytes()).digest(),
                         hashlib.sha256(new_files['derived/geo/map.sqlite']).digest())

    def _resume_spain_after_restart(self, placeholder, failed=False):
        from app.tests.test_setup import ALLOWED, make_map
        from engine.setup import api, install, manifest
        library = self.parent / 'LastbookData'
        (library / 'library-data').mkdir(parents=True)
        (library / 'library-data/catalog.json').write_text('{}')
        (library / 'pack.json').write_text('{"name":"small","map":"base"}')
        archive = self.tmp / 'Lastbook-Map-ES.zip'
        files = make_map(archive, state='ES')
        data = archive.read_bytes()
        self.files.data[archive.name] = data
        country = {'id': 'ES', 'title': 'Spain', 'kind': 'country', 'available': True,
                   'installed_bytes': sum(map(len, files.values())),
                   'files': [{'name': archive.name, 'url': f'{self.base}/{archive.name}', 'size': len(data),
                              'sha256': hashlib.sha256(data).hexdigest(), 'kind': 'zip'}]}
        current = self.manifest()
        current.current['maps'] = manifest.validate({'version': 1, 'maps': [country]}, ALLOWED)['maps']
        s = self.setup('manage', current=library, manifest=current)
        self.files.pace = 0.03
        s.start(map_id='ES')
        time.sleep(0.06)
        self.assertEqual(s.pause()['state'], 'paused')
        if failed:
            saved_job = json.loads(api._job_file(self.settings).read_text())
            saved_job['state'] = 'failed'
            saved_job['error'] = {'code': 'network', 'message': 'Connection stopped.'}
            saved_job['items'][0]['state'] = 'failed'
            install._write_json(api._job_file(self.settings), saved_job)
        saved = api._job_file(self.settings).read_bytes()
        base = self.manifest().current
        base['maps'] = [{'id': 'ES', 'title': 'Spain', 'kind': 'country', 'available': False,
                         'installed_bytes': None, 'files': []}] if placeholder else []
        self.files.data['manifest-v1.json'] = json.dumps(base).encode()
        country_manifest = json.dumps({'version': 1, 'maps': [country]}).encode()
        fresh = manifest.Manifest(bundled=base, remote=f'{self.base}/manifest-v1.json',
                                  spain_remote=f'{self.base}/manifest-spain-v1.json', allowed=ALLOWED, context=self.ctx)
        resumed = self.setup('manage', current=library, manifest=fresh)
        self.assertEqual(resumed.public_job()['state'], 'failed' if failed else 'paused')
        fresh.fetch_once()  # Simulate opening setup while the country manifest is unavailable.
        fresh.fetching.join(5)
        self.assertFalse(fresh.map('ES') and fresh.map('ES')['available'])
        self.files.data['manifest-spain-v1.json'] = country_manifest
        action = resumed.retry if failed else resumed.resume
        not_ready = action()
        self.assertEqual(not_ready['state'], 'failed' if failed else 'paused')
        self.assertEqual(not_ready['error']['code'], 'manifest')
        self.assertEqual(api._job_file(self.settings).read_bytes(), saved)
        self.files.pace = 0
        fresh.fetching.join(5)
        action()
        self.assertEqual(self.wait(resumed)['state'], 'done')
        lib, note = api.startup(self.settings)
        self.assertFalse(note.get('error'))
        self.assertEqual(install.map_name(lib), 'ES')

    def test_country_manifest_adds_spain_without_changing_us_options(self):
        from engine.setup import manifest
        from app.tests.test_setup import ALLOWED
        base = self.manifest().current
        base['maps'] = [{'id': 'CA', 'title': 'California', 'kind': 'state', 'available': False, 'files': []}]
        self.files.data['manifest-v1.json'] = json.dumps(base).encode()
        country = {'id': 'ES', 'title': 'Spain', 'kind': 'country', 'available': True, 'installed_bytes': 12,
                   'files': [{'name': 'Lastbook-Map-ES.zip', 'url': f'{self.base}/Lastbook-Map-ES.zip',
                              'size': 10, 'sha256': 'a' * 64, 'kind': 'zip'}]}
        self.files.data['manifest-spain-v1.json'] = json.dumps({'version': 1, 'maps': [country]}).encode()
        mf = manifest.Manifest(bundled=base, remote=f'{self.base}/manifest-v1.json',
                               spain_remote=f'{self.base}/manifest-spain-v1.json', allowed=ALLOWED, context=self.ctx)
        mf._fetch()
        self.assertEqual([m['id'] for m in mf.current['maps']], ['ES', 'CA'])
        self.assertTrue(mf.map('ES')['available'])
        self.assertEqual([p['id'] for p in mf.current['packs']], ['small', 'all'])

    def test_country_manifest_cannot_replace_library_or_us_state_entries(self):
        from engine.setup import manifest
        from app.tests.test_setup import ALLOWED
        base = self.manifest().current
        base['maps'] = [{'id': 'CA', 'title': 'California', 'kind': 'state', 'available': False, 'files': []}]
        self.files.data['manifest-v1.json'] = json.dumps(base).encode()
        self.files.data['manifest-spain-v1.json'] = json.dumps({'version': 1, 'maps': [{'id': 'CA', 'title': 'Wrong', 'files': []}]}).encode()
        mf = manifest.Manifest(bundled=base, remote=f'{self.base}/manifest-v1.json',
                               spain_remote=f'{self.base}/manifest-spain-v1.json', allowed=ALLOWED, context=self.ctx)
        mf._fetch()
        self.assertEqual(mf.current['maps'][0]['title'], 'California')
        self.assertIsNone(mf.map('ES'))

    def test_restore_all_downloads_its_original_us_map_and_keeps_addresses(self):
        from engine.setup import api, install
        library = self.parent / 'LastbookData'
        (library / 'library-data').mkdir(parents=True)
        (library / 'library-data/catalog.json').write_text('{}')
        (library / 'pack.json').write_text('{"name":"all","map":"us"}')
        geo = library / 'derived/geo'
        geo.mkdir(parents=True)
        (geo / 'map.sqlite').write_bytes(b'Spain map')
        (geo / 'addresses').mkdir()
        (geo / 'addresses/CA.sqlite').write_bytes(b'address index')
        (library / 'map-set.json').write_text(json.dumps({'name': 'ES', 'files': {'derived/geo/map.sqlite': 9}}))
        archive = self.tmp / 'Lastbook-All.zip'
        installed = make_pack(archive, {'library-data/catalog.json': b'{}', 'pack.json': b'{"name":"all","map":"us"}',
                                         'derived/geo/map.sqlite': b'US map', 'derived/geo/national.sqlite': b'US national map',
                                         'library-data/big.bin': os.urandom(4 * 1024 * 1024)})
        data = archive.read_bytes()
        self.files.data[archive.name] = data
        mf = self.manifest()
        mf.current['packs'][1].update(available=True, map='us', installed_bytes=installed, download_bytes=len(data),
            files=[{'name': archive.name, 'url': f'{self.base}/{archive.name}', 'size': len(data),
                    'sha256': hashlib.sha256(data).hexdigest(), 'kind': 'zip'}])
        s = self.setup('manage', current=library, manifest=mf)
        self.files.pace = 0.01
        job = s.start('all', restore_map=True)
        self.assertEqual([item['kind'] for item in job['items']], ['pack'])
        time.sleep(0.15)
        self.assertEqual(s.pause()['state'], 'paused')
        resumed = self.setup('manage', current=library, manifest=mf)
        self.assertTrue(resumed.job['plan']['restore_map'])
        resumed.resume()
        self.assertEqual(self.wait(resumed)['state'], 'done')
        lib, note = api.startup(self.settings)
        self.assertFalse(note.get('error'))
        self.assertEqual(install.map_name(lib), 'us')
        self.assertEqual((lib / 'derived/geo/map.sqlite').read_bytes(), b'US map')
        self.assertEqual((lib / 'derived/geo/addresses/CA.sqlite').read_bytes(), b'address index')

    def test_restore_rejects_an_all_archive_without_a_us_map(self):
        self._restore_rejects_bad_all('base')

    def test_restore_rejects_an_all_archive_missing_national_data(self):
        self._restore_rejects_bad_all('us')

    def _restore_rejects_bad_all(self, map_name):
        from engine.setup import install
        library = self.parent / 'LastbookData'
        (library / 'library-data').mkdir(parents=True)
        (library / 'library-data/catalog.json').write_text('{}')
        (library / 'pack.json').write_text('{"name":"all","map":"us"}')
        geo = library / 'derived/geo'
        geo.mkdir(parents=True)
        (geo / 'map.sqlite').write_bytes(b'Spain map')
        (library / 'map-set.json').write_text(json.dumps({'name': 'ES', 'files': {'derived/geo/map.sqlite': 9}}))
        archive = self.tmp / 'Lastbook-All.zip'
        installed = make_pack(archive, {'library-data/catalog.json': b'{}',
                                         'pack.json': json.dumps({'name': 'all', 'map': map_name}).encode()})
        data = archive.read_bytes()
        self.files.data[archive.name] = data
        mf = self.manifest()
        mf.current['packs'][1].update(available=True, map='us', installed_bytes=installed, download_bytes=len(data),
            files=[{'name': archive.name, 'url': f'{self.base}/{archive.name}', 'size': len(data),
                    'sha256': hashlib.sha256(data).hexdigest(), 'kind': 'zip'}])
        s = self.setup('manage', current=library, manifest=mf)
        s.start('all', restore_map=True)
        job = self.wait(s)
        self.assertEqual(job['state'], 'failed')
        self.assertEqual(job['error']['code'], 'unpack')
        self.assertEqual(install.map_name(library), 'ES')
        self.assertEqual((geo / 'map.sqlite').read_bytes(), b'Spain map')

    def test_first_run_recognizes_a_local_country_map_without_selecting_ai(self):
        sources = self.tmp / 'sources'
        sources.mkdir()
        make_extract(sources / 'ceuta.gpkg', 'Ceuta', -5.30, 35.90)
        output = self.tmp / 'country'
        result = subprocess.run([sys.executable, '-B', str(BUILDER), '--input-dir', str(sources),
                                 '--output-dir', str(output), '--sample'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        archive = output / 'Lastbook-Map-ES-SAMPLE.zip'
        data = archive.read_bytes()
        with zipfile.ZipFile(archive) as z:
            installed = sum(i.file_size for i in z.infolist())
        mf = self.manifest()
        mf.current['maps'] = [{'id': 'ES-SAMPLE', 'title': 'Spain sample', 'kind': 'country', 'available': True,
            'installed_bytes': installed, 'download_bytes': len(data), 'includes': 'sample',
            'files': [{'name': archive.name, 'url': f'{self.base}/{archive.name}', 'size': len(data),
                       'sha256': hashlib.sha256(data).hexdigest(), 'kind': 'zip'}]}]
        s = self.setup(manifest=mf)
        noted = s.use(str(archive))
        self.assertEqual((noted['kind'], noted['id']), ('map', 'ES-SAMPLE'))
        job = s.start('small', map_id=noted['id'])
        self.assertEqual([i['kind'] for i in job['items']], ['pack', 'map'])
        self.assertEqual(self.wait(s)['state'], 'done')
        self.assertEqual(job['items'][1]['source'], 'found')

    def test_country_archive_downloads_with_a_library_and_is_activated(self):
        sources = self.tmp / 'sources'
        sources.mkdir()
        make_extract(sources / 'ceuta.gpkg', 'Ceuta', -5.30, 35.90)
        output = self.tmp / 'country'
        result = subprocess.run([sys.executable, '-B', str(BUILDER), '--input-dir', str(sources),
                                 '--output-dir', str(output), '--sample'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        archive = output / 'Lastbook-Map-ES-SAMPLE.zip'
        data = archive.read_bytes()
        with zipfile.ZipFile(archive) as z:
            installed = sum(i.file_size for i in z.infolist())
        self.files.data[archive.name] = data
        mf = self.manifest()
        mf.current['maps'] = [{'id': 'ES-SAMPLE', 'title': 'Spain sample', 'kind': 'country', 'available': True,
            'installed_bytes': installed, 'download_bytes': len(data), 'includes': 'sample',
            'files': [{'name': archive.name, 'url': f'{self.base}/{archive.name}', 'size': len(data),
                       'sha256': hashlib.sha256(data).hexdigest(), 'kind': 'zip'}]}]
        s = self.setup(manifest=mf)
        job = s.start('small', map_id='ES-SAMPLE')
        self.assertEqual([i['kind'] for i in job['items']], ['pack', 'map'])
        self.assertEqual(self.wait(s)['state'], 'done')
        from engine.setup import api, install
        lib, note = api.startup(self.settings)
        self.assertFalse(note.get('error'))
        self.assertEqual(install.map_name(lib), 'ES-SAMPLE')
        self.assertIn('Ceuta', sqlite3.connect(lib / 'derived/geo/places.sqlite').execute('SELECT name FROM place').fetchone())
        self.assertFalse((lib / 'derived/geo/addresses/ES-SAMPLE.sqlite').exists())


if __name__ == '__main__':
    unittest.main()
