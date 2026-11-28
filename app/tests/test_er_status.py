#!/usr/bin/env python3
"""A hospital keeps its emergency-department status through the map import: yes, no, or unknown.

  python3 -B -m unittest app.tests.test_er_status

Everything here is made up: the town, the hospitals and the coordinates are invented, and nothing is read from or
written to a real data folder. The OSM part runs tools/build_places_region.py on a tiny file and needs pyosmium (skipped
without it). The HIFLD part calls the row logic of tools/build_places_civic.py and needs nothing else.
"""
import importlib.util, os, sqlite3, subprocess, sys, tempfile, types, unittest
from pathlib import Path

sys.dont_write_bytecode = True
TOOLS = Path(__file__).resolve().parents[2] / 'tools'

try:
    import osmium  # noqa: F401
except ImportError:
    osmium = None

# Invented points near 0,0: not a real place.
OSM = '''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6" generator="test">
  <node id="1" lat="0.0010" lon="0.0010">
    <tag k="amenity" v="hospital"/><tag k="name" v="Springfield General"/><tag k="emergency" v="yes"/>
  </node>
  <node id="2" lat="0.0020" lon="0.0020">
    <tag k="amenity" v="hospital"/><tag k="name" v="Springfield Eye Hospital"/><tag k="emergency" v="no"/>
  </node>
  <node id="3" lat="0.0030" lon="0.0030">
    <tag k="amenity" v="hospital"/><tag k="name" v="Shelbyville Hospital"/>
  </node>
  <node id="4" lat="0.0040" lon="0.0040">
    <tag k="amenity" v="hospital"/><tag k="name" v="Capital City Hospital"/><tag k="emergency" v="unsure"/>
  </node>
  <node id="5" lat="0.0050" lon="0.0050">
    <tag k="amenity" v="pharmacy"/><tag k="name" v="Springfield Pharmacy"/><tag k="emergency" v="yes"/>
  </node>
</osm>
'''


def load(name):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f'{name}.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def build(osm, out):
    return subprocess.run([sys.executable, '-B', str(TOOLS / 'build_places_region.py'), str(osm),
                           '--region', 'Springfield', '--out', str(out)], capture_output=True, text=True,
                          encoding='utf-8', env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})  # the tool prints an arrow


@unittest.skipIf(osmium is None, 'pyosmium is not installed')
class OsmEmergencyStatus(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix='lastbook-er-')
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.osm = self.tmp / 'springfield.osm'
        self.osm.write_text(OSM, encoding='utf-8')
        self.out = self.tmp / 'regions' / 'springfield'

    def er(self):
        db = sqlite3.connect(self.out / 'national.sqlite')
        try:
            return dict(db.execute('SELECT name, er FROM poi').fetchall())
        finally:
            db.close()

    def test_three_cases_stay_distinct(self):
        r = build(self.osm, self.out)
        self.assertEqual(r.returncode, 0, r.stderr)
        er = self.er()
        self.assertEqual(er['Springfield General'], 'yes')
        self.assertEqual(er['Springfield Eye Hospital'], 'no')
        self.assertIsNone(er['Shelbyville Hospital'])  # no tag: unknown, which is neither yes nor no
        self.assertIsNone(er['Capital City Hospital'])  # a value that is not yes/no is unknown too
        three = [er['Springfield General'], er['Springfield Eye Hospital'], er['Shelbyville Hospital']]
        self.assertEqual(len(set(three)), 3)

    def test_emergency_no_never_reads_as_an_er(self):
        build(self.osm, self.out)
        db = sqlite3.connect(self.out / 'national.sqlite')
        confirmed = {n for (n,) in db.execute("SELECT name FROM poi WHERE cls='hospital' AND er='yes'")}
        db.close()
        self.assertEqual(confirmed, {'Springfield General'})

    def test_only_hospitals_carry_a_status(self):
        build(self.osm, self.out)
        self.assertIsNone(self.er()['Springfield Pharmacy'])

    def test_rebuild_and_old_files(self):
        # an older national.sqlite has no `er` column and rows without a status; rebuilding must fill it in
        self.out.mkdir(parents=True)
        meta = "CREATE TABLE build_meta(key TEXT PRIMARY KEY, value TEXT); INSERT INTO build_meta VALUES ('builder','build_places_region'), ('region','Springfield');"
        db = sqlite3.connect(self.out / 'national.sqlite')
        db.executescript('CREATE TABLE poi(id INTEGER PRIMARY KEY, cls TEXT, name TEXT, lon REAL, lat REAL);' + meta +
                         "INSERT INTO poi(cls,name,lon,lat) VALUES ('hospital','Springfield General',0.001,0.001);")
        db.commit()
        db.close()
        db = sqlite3.connect(self.out / 'places.sqlite')
        db.executescript(meta)
        db.commit()
        db.close()
        for _ in range(2):
            r = build(self.osm, self.out)
            self.assertEqual(r.returncode, 0, r.stderr)
        db = sqlite3.connect(self.out / 'national.sqlite')
        self.assertEqual(db.execute("SELECT count(*) FROM poi WHERE name='Springfield General'").fetchone()[0], 1)
        db.close()
        self.assertEqual(self.er()['Springfield General'], 'yes')


class HifldEmergencyStatus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if importlib.util.find_spec('duckdb') is None:  # the module needs duckdb only to read parquet, not here
            sys.modules['duckdb'] = types.ModuleType('duckdb')
            cls.addClassCleanup(sys.modules.pop, 'duckdb', None)
        cls.civic = load('build_places_civic')

    def test_confirmed_and_unknown_stay_distinct(self):
        confirmed = self.civic.hospital_detail('GENERAL ACUTE CARE', 120, 'LEVEL II', None)
        unknown = self.civic.hospital_detail('GENERAL ACUTE CARE', 40, 'NOT AVAILABLE', None)
        self.assertEqual(confirmed.get('er'), 'yes')
        self.assertNotIn('er', unknown)  # HIFLD does not say: unknown, never read as an ER
        self.assertNotEqual(confirmed.get('er'), unknown.get('er'))

    def test_critical_access_is_confirmed_and_other_types_are_not(self):
        self.assertEqual(self.civic.hospital_er('CRITICAL ACCESS', None), 'yes')
        for typ in ('PSYCHIATRIC', 'REHABILITATION', 'LONG TERM CARE', 'GENERAL ACUTE CARE', None):
            self.assertIsNone(self.civic.hospital_er(typ, None), typ)

    def test_hifld_never_says_none(self):
        for typ in ('PSYCHIATRIC', 'CRITICAL ACCESS', 'GENERAL ACUTE CARE', None):
            for trauma in (None, 'NOT AVAILABLE', 'LEVEL I'):
                self.assertNotEqual(self.civic.hospital_er(typ, trauma), 'no')

    def test_existing_detail_is_unchanged(self):
        d = self.civic.hospital_detail('GENERAL ACUTE CARE', 120, 'LEVEL II', 'Y')
        self.assertEqual(d, {'type': 'general acute care', 'beds': 120, 'trauma': 'LEVEL II', 'helipad': True, 'er': 'yes'})


if __name__ == '__main__':
    unittest.main(verbosity=2)
