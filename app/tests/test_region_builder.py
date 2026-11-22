"""Region maps outside the US, built from an OpenStreetMap extract: tools/build_osm_region.py and tools/finish_region_map.py on a
small made-up Costa Brava sample (fixtures/es_ct_sample.osm), then the map zip through setup's own unpacker and checks; and the
region catalogue (tools/regions/europe.json) against the Spain proposal's codes.

The builder needs pyosmium (`pip install osmium`, a build tool like tools/build_coast.py); those tests are skipped without it.
Never packaged."""
import importlib.util
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from engine.setup import download, install     # noqa: E402

SAMPLE = HERE / 'fixtures' / 'es_ct_sample.osm'
HAS_OSMIUM = importlib.util.find_spec('osmium') is not None


def run(*argv):
    subprocess.run([sys.executable, '-I', '-B', *map(str, argv)], check=True, capture_output=True, text=True)


@unittest.skipUnless(HAS_OSMIUM, 'pyosmium is not installed')
class BuildSample(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.temp.name) / 'ES-CT'
        run(ROOT / 'tools' / 'build_osm_region.py', SAMPLE, cls.out, '--name', 'Catalonia', '--credit', 'OpenStreetMap contributors (ODbL 1.0)')
        run(ROOT / 'tools' / 'finish_region_map.py', cls.out, 'ES-CT', '--title', 'Catalonia',
            '--credit', '© OpenStreetMap contributors', '--zip', Path(cls.temp.name) / 'zips')
        cls.geo = cls.out / 'derived' / 'geo'
        cls.zip = Path(cls.temp.name) / 'zips' / 'Lastbook-Map-ES-CT.zip'

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def db(self, name):
        c = sqlite3.connect(f'file:{self.geo / name}?mode=ro', uri=True)
        self.addCleanup(c.close)
        return c

    def test_streets_places_and_help_points(self):
        n = self.db('national.sqlite')
        layers = {(layer, cls) for layer, cls in n.execute('SELECT layer, cls FROM feat')}
        self.assertLessEqual({('road', 'residential'), ('place', 'town'), ('place', 'village')}, layers)
        self.assertEqual(sorted(c for c, in n.execute('SELECT cls FROM poi')), ['drinking_water', 'hospital', 'pharmacy'])

    def test_the_sea_is_on_the_right_of_the_coastline(self):
        """OpenStreetMap draws coastlines with the land on the left: this one runs north, so the sea is east of it and the
        land polygon west of it."""
        n = self.db('national.sqlite')
        box = {cls: n.execute('SELECT min(i.minx), max(i.maxx) FROM feat f JOIN feat_idx i ON i.id = f.id WHERE f.cls = ?', (cls,)).fetchone()
               for cls in ('ocean', 'mainland')}
        self.assertGreaterEqual(box['ocean'][1], 3.12)        # reaches past the coast's easternmost point
        self.assertLessEqual(box['mainland'][0], 3.10)        # and the land reaches west of it
        self.assertLess(box['mainland'][0], box['ocean'][0])

    def test_buildings_and_place_finder(self):
        self.assertEqual(self.db('buildings.sqlite').execute("SELECT value FROM meta WHERE key = 'buildings'").fetchone(), ('1',))
        p = self.db('places.sqlite')
        self.assertEqual(p.execute("SELECT kind FROM place WHERE name = 'Vila de Mar'").fetchone(), ('town',))
        self.assertEqual(p.execute("SELECT kind FROM place WHERE name = 'Puig Alt'").fetchone(), ('mountain peak (303 m)',))
        # accents fold: "farmacia" finds "Farmàcia del Port"
        self.assertEqual(p.execute("SELECT name FROM place_fts WHERE place_fts MATCH 'farmacia'").fetchone(), ('Farmàcia del Port',))

    def test_meta_carries_credit_date_and_units(self):
        meta = dict(self.db('national.sqlite').execute('SELECT key, value FROM meta'))
        self.assertEqual((meta['region'], meta['title'], meta['units'], meta['credit']), ('ES-CT', 'Catalonia', 'metric', '© OpenStreetMap contributors'))
        self.assertEqual(meta['data_as_of'], '2026-11-05T00:00:00Z')     # the newest object in the extract
        self.assertTrue(json.loads(meta['datasets']))

    def test_setup_unpacks_and_accepts_the_map_zip(self):
        """Through setup's own path for a map: only map files, sizes as map-set.json lists them, the name it installs under."""
        with tempfile.TemporaryDirectory() as into:
            install.unpack(self.zip, into, None, download.Control(), lambda done, total: None,
                           allowed=install.map_member, verify=install.check_map)
            lib = Path(into) / install.DATA_NAME
            self.assertEqual(install.map_name(lib), 'ES-CT')
            self.assertTrue((lib / 'derived' / 'geo' / 'national.sqlite').is_file())
            self.assertEqual(install.map_set(lib)['files'], {r: (lib / r).stat().st_size for r in install.map_set(lib)['files']})


class Catalogue(unittest.TestCase):
    regions = json.loads((ROOT / 'tools' / 'regions' / 'europe.json').read_text(encoding='utf-8'))['regions']

    def test_ids_are_unique_and_never_a_bare_us_state_code(self):
        ids = [r['id'] for r in self.regions]
        self.assertEqual(len(ids), len(set(ids)))
        for r in self.regions:
            with self.subTest(id=r['id']):
                self.assertTrue(r['id'] == r['country'] or r['id'].startswith(r['country'] + '-'))
                self.assertRegex(r['id'], r'^[A-Z]{2}(-[A-Za-z0-9_]{1,48})?$')
                self.assertEqual(len(r['bbox']), 4)

    def test_spain_matches_the_proposal(self):
        """The 19 Spanish regions carry the ISO 3166-2 codes docs/regions-es-proposed.json gives, and each catalogue box (from the
        OSM extract's boundary) overlaps the proposal's (from IGN's boundaries)."""
        proposed = {r['code']: r['bbox'] for r in json.loads((ROOT / 'docs' / 'regions-es-proposed.json').read_text(encoding='utf-8'))['regions']}
        ours = {r['id']: r['bbox'] for r in self.regions if r['country'] == 'ES'}
        self.assertEqual(set(ours), set(proposed))
        for code, (w, s, e, n) in ours.items():
            p = proposed[code]
            with self.subTest(code=code):
                self.assertTrue(w < p['east'] and e > p['west'] and s < p['north'] and n > p['south'])


if __name__ == '__main__':
    unittest.main()
