"""The Greater London map builder (tools/build_region_gb.py) and British postcodes in the place finder."""
import importlib.util
import sqlite3
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location('build_region_gb', ROOT / 'tools' / 'build_region_gb.py')
gb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gb)

HEADER = ('ID,NAMES_URI,NAME1,NAME1_LANG,NAME2,NAME2_LANG,TYPE,LOCAL_TYPE,GEOMETRY_X,GEOMETRY_Y,MOST_DETAIL_VIEW_RES,'
          'LEAST_DETAIL_VIEW_RES,MBR_XMIN,MBR_YMIN,MBR_XMAX,MBR_YMAX,POSTCODE_DISTRICT,POSTCODE_DISTRICT_URI,POPULATED_PLACE,'
          'POPULATED_PLACE_URI,POPULATED_PLACE_TYPE,DISTRICT_BOROUGH,DISTRICT_BOROUGH_URI,DISTRICT_BOROUGH_TYPE,COUNTY_UNITARY,'
          'COUNTY_UNITARY_URI,COUNTY_UNITARY_TYPE,REGION,REGION_URI,COUNTRY,COUNTRY_URI,RELATED_SPATIAL_OBJECT,SAME_AS_DBPEDIA,'
          'SAME_AS_GEONAMES')


def dms(d, m, s):
    return d + m / 60 + s / 3600


def names_row(name, local, east, north, place='', borough='', county='', district='', name2=''):
    cols = dict.fromkeys(HEADER.split(','), '')
    cols.update(NAME1=name, NAME2=name2, LOCAL_TYPE=local, GEOMETRY_X=str(east), GEOMETRY_Y=str(north), POSTCODE_DISTRICT=district,
                POPULATED_PLACE=place, DISTRICT_BOROUGH=borough, COUNTY_UNITARY=county)
    return ','.join('"%s"' % v for v in cols.values())


class GridConversionTests(unittest.TestCase):
    """OS's worked example (A guide to coordinate systems in Great Britain, annex C) and the datum shift's size."""

    def test_grid_to_osgb36_matches_the_os_worked_example(self):
        lat, lon = gb.grid_to_osgb36(651409.903, 313177.270)
        self.assertAlmostEqual(lat, dms(52, 39, 27.2531), delta=1e-7)
        self.assertAlmostEqual(lon, dms(1, 43, 4.5177), delta=1e-7)

    def test_osgb36_to_grid_matches_the_os_worked_example(self):
        east, north = gb.osgb36_to_grid(dms(52, 39, 27.2531), dms(1, 43, 4.5177))
        self.assertAlmostEqual(east, 651409.903, delta=0.002)
        self.assertAlmostEqual(north, 313177.270, delta=0.002)

    def test_round_trip_through_wgs84_keeps_the_point(self):
        for east, north in ((530034, 180381), (651409.903, 313177.270), (325000, 674000), (400000, 1000000)):
            back = gb.wgs84_to_bng(*gb.bng_to_wgs84(east, north))
            self.assertAlmostEqual(back[0], east, delta=0.05)
            self.assertAlmostEqual(back[1], north, delta=0.05)

    def test_the_datum_shift_in_london_is_about_a_hundred_metres(self):
        # OSGB36 and WGS 84 differ by roughly 100 m around London; a sign error would double it, a missing shift remove it.
        lat36, lon36 = gb.grid_to_osgb36(530034, 180381)
        lat, lon = gb.bng_to_wgs84(530034, 180381)
        shift = gb.metres(lat36, lon36, lat, lon)
        self.assertGreater(shift, 60)
        self.assertLess(shift, 160)
        self.assertLess(lon, lon36)          # WGS 84 longitudes are smaller (further west) than OSGB36 ones here


class AreaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.poly = Path(self.temp.name) / 'square.poly'
        self.poly.write_text('square\n1\n  0.0 0.0\n  1.0 0.0\n  1.0 1.0\n  0.0 1.0\nEND\n!2\n  0.4 0.4\n  0.6 0.4\n  0.6 0.6\n'
                             '  0.4 0.6\nEND\nEND\n', encoding='utf-8')

    def tearDown(self):
        self.temp.cleanup()

    def test_outline_with_a_hole(self):
        rings = gb.read_poly(self.poly)
        self.assertEqual([hole for hole, _ in rings], [False, True])
        area = gb.Area(rings, cells=16)
        for lon, lat, inside in ((0.1, 0.1, True), (0.5, 0.5, False), (0.39, 0.5, True), (1.01, 0.5, False), (0.999, 0.999, True),
                                 (-0.001, 0.5, False), (0.61, 0.61, True)):
            self.assertEqual(area.contains(lon, lat), inside, (lon, lat))
            self.assertEqual(area.exact(lon, lat), inside, (lon, lat))


class PlaceFinderBuildTests(unittest.TestCase):
    """The place finder from small OS-shaped files: postcodes, their districts and boroughs, Code-Point's extras."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        poly = root / 'london.poly'
        poly.write_text('london\n1\n  -0.30 51.40\n  0.10 51.40\n  0.10 51.60\n  -0.30 51.60\nEND\nEND\n', encoding='utf-8')
        self.names = root / 'opname.zip'
        with zipfile.ZipFile(self.names, 'w') as z:
            z.writestr('Doc/OS_Open_Names_Header.csv', '﻿' + HEADER + '\n')
            z.writestr('Data/TQ28.csv', '\n'.join([
                names_row('SW1A 2AA', 'Postcode', 530047, 179951, 'City of Westminster', 'City of Westminster', 'Greater London'),
                names_row('SW1A 2AB', 'Postcode', 530035, 179935, 'City of Westminster', 'City of Westminster', 'Greater London'),
                names_row('Downing Street', 'Named Road', 530094, 179914, 'London', 'City of Westminster', 'Greater London', 'SW1A'),
                names_row('Hampstead', 'Suburban Area', 526500, 185800, '', 'Camden', 'Greater London', 'NW3'),
                names_row('Ysgol Example', 'Primary Education', 526600, 185900, 'London', 'Camden', 'Greater London', 'NW3', 'Example School'),
                names_row('BN1 1AA', 'Postcode', 531000, 104000, 'Brighton', 'Brighton and Hove', 'Brighton and Hove'),   # outside
            ]) + '\n')
        self.codepoint = root / 'codepo.zip'
        with zipfile.ZipFile(self.codepoint, 'w') as z:
            z.writestr('Data/CSV/sw.csv', '\n'.join([
                '"SW1A 2AA",10,530047,179951,"E92000001","","","","E09000033",""',     # already in Open Names
                '"SW1A 2ZZ",10,530100,179990,"E92000001","","","","E09000033",""',     # only here: named from its sector
                '"SW1A 9ZZ",90,0,0,"E92000001","","","","",""',                          # no coordinates
            ]) + '\n')
        self.places = gb.Places(gb.Area(gb.read_poly(poly)))
        self.places.open_names(self.names)
        self.places.code_point(self.codepoint)
        self.by_name = {row[0]: row for row in self.places.rows}

    def tearDown(self):
        self.temp.cleanup()

    def test_rows(self):
        name, kind, detail, lat, lon, rank, source = self.by_name['SW1A 2AA']
        self.assertEqual((kind, detail, rank, source), ('postcode', 'City of Westminster', 5, 'OS Open Names'))
        # OS's grid reference for SW1A 2AA lands on 10 Downing Street (51.50344 N, 0.12770 W in WGS 84) to within ~30 m
        self.assertAlmostEqual(lat, 51.50344, delta=0.0003)
        self.assertAlmostEqual(lon, -0.12770, delta=0.0004)
        self.assertEqual(self.by_name['Downing Street'][1:3], ('road', 'London, City of Westminster, SW1A'))
        self.assertEqual(self.by_name['Hampstead'][1:3], ('suburb', 'Camden, Greater London'))
        self.assertEqual(self.by_name['Ysgol Example'][1:3], ('school', 'London, Camden, NW3, also called Example School'))
        self.assertNotIn('BN1 1AA', self.by_name)

    def test_districts_and_boroughs_sit_among_their_postcodes(self):
        district = self.by_name['SW1A']
        self.assertEqual(district[1:3], ('postcode district', 'City of Westminster'))
        self.assertAlmostEqual(district[3], (self.by_name['SW1A 2AA'][3] + self.by_name['SW1A 2AB'][3]) / 2, delta=1e-5)
        self.assertEqual(self.by_name['City of Westminster'][1:3], ('borough', 'Greater London'))
        self.assertNotIn('Camden', self.by_name)    # a borough comes from its postcodes; this fixture has none in Camden

    def test_code_point_adds_only_missing_postcodes(self):
        self.assertEqual([r[0] for r in self.places.rows].count('SW1A 2AA'), 1)
        extra = self.by_name['SW1A 2ZZ']
        self.assertEqual(extra[1:3], ('postcode', 'City of Westminster'))
        self.assertEqual(extra[6], 'OS Code-Point Open')
        self.assertNotIn('SW1A 9ZZ', self.by_name)


class PostcodeSearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        geo = self.root / 'derived' / 'geo'
        geo.mkdir(parents=True)
        db = sqlite3.connect(geo / 'places.sqlite')
        db.executescript('''CREATE TABLE place(id INTEGER PRIMARY KEY, name TEXT, kind TEXT, detail TEXT, lat REAL, lon REAL, rank INTEGER, source TEXT);
          CREATE VIRTUAL TABLE place_fts USING fts5(name, detail, content='place', content_rowid='id', tokenize='unicode61');''')
        db.executemany('INSERT INTO place(name,kind,detail,lat,lon,rank,source) VALUES (?,?,?,?,?,?,?)', [
            ('SW1A 2AA', 'postcode', 'City of Westminster', 51.5034, -0.1276, 5, 'OS Open Names'),
            ('SW1A 2AB', 'postcode', 'City of Westminster', 51.5036, -0.1272, 5, 'OS Open Names'),
            ('SW1A', 'postcode district', 'City of Westminster', 51.502, -0.135, 1, 'OS Open Names'),
            ('Paddington', 'suburb', 'City of Westminster, Greater London', 51.517, -0.178, 1, 'OS Open Names'),
            ('Paddington', 'railway station', 'London, City of Westminster, W2', 51.531, -0.176, 4, 'OS Open Names'),   # another 0.01° cell: places() merges same-name hits within one
            ('Tower Hamlets', 'borough', 'Greater London', 51.515, -0.035, 1, 'OS Open Names'),
            *[(f'W2 {i}AA', 'postcode', 'Paddington, City of Westminster', 51.516, -0.18, 5, 'OS Open Names') for i in range(250)],
            *[(f'E1 {i}AA', 'postcode', 'Stepney, Tower Hamlets', 51.517, -0.05, 5, 'OS Open Names') for i in range(250)],
            ('90210', 'ZIP code area', 'Census 2025 ZIP code tabulation area', 34.10, -118.41, 2, 'US Census Bureau'),
            ('Springfield', 'town or neighborhood', 'Sangamon County, Illinois', 39.80, -89.64, 3, 'USGS GNIS'),
        ])
        db.execute("INSERT INTO place_fts(place_fts) VALUES ('rebuild')")
        db.commit()
        db.close()
        import server
        self.server = server
        self.patches = [patch.object(server, 'HERE', self.root), patch.object(server, 'PLACEDB', geo / 'places.sqlite'),
                        patch.object(server, 'WATERDB', self.root / 'no-water.sqlite'),
                        patch.object(server, 'home_area', return_value=None), patch.object(server, 'pack_info', return_value=None)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.temp.cleanup()

    def names(self, q):
        return [hit['name'] for hit in self.server.places(q)]

    def test_postcode_query(self):
        q = self.server.postcode_query
        for typed, looked_up in (('sw1a2aa', 'SW1A 2AA'), (' SW1A  2AA ', 'SW1A 2AA'), ('w1a0ax', 'W1A 0AX'), ('m11ae', 'M1 1AE'),
                                 ('ec1a1bb', 'EC1A 1BB')):
            self.assertEqual(q(typed), looked_up)
        for other in ('Springfield', '90210', 'Route 66', 'SW1A', 'Main Street 12', '123 Main St'):
            self.assertEqual(q(other), other)

    def test_a_postcode_is_found_with_or_without_its_space(self):
        self.assertEqual(self.names('SW1A 2AA')[0], 'SW1A 2AA')
        self.assertEqual(self.names('sw1a2aa')[0], 'SW1A 2AA')
        self.assertEqual(self.names('sw1a 2aa')[0], 'SW1A 2AA')
        self.assertEqual(self.names('SW1A')[0], 'SW1A')

    def test_postcodes_do_not_crowd_out_the_place_they_are_in(self):
        # Each postcode's detail names its locality and borough. There are hundreds per name: they must not push the
        # station or the borough out of the engine's first 200 matches.
        self.assertEqual([(h['name'], h['kind']) for h in self.server.places('Paddington')[:2]],
                         [('Paddington', 'suburb'), ('Paddington', 'railway station')])
        self.assertEqual(self.server.places('Tower Hamlets')[0]['kind'], 'borough')
        self.assertEqual(self.names('W2 7AA')[0], 'W2 7AA')

    def test_us_places_answer_as_before(self):
        self.assertEqual(self.names('90210'), ['90210'])
        self.assertEqual(self.names('Springfield'), ['Springfield'])
        self.assertEqual(self.names('springfield illinois'), ['Springfield'])
        with patch.object(self.server.address_search, 'find_addresses', return_value=[]) as lookup:
            self.assertEqual(self.server.places('18003 nine mile'), [])
            lookup.assert_called_once()


if __name__ == '__main__':
    unittest.main()
