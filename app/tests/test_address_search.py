"""Offline address lookup must preserve house numbers and geographic qualifiers."""
import sqlite3
from contextlib import closing
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from engine.address_search import find_addresses, is_address_query, normalize


class AddressSearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.geo = Path(self.temp.name)
        (self.geo / 'addresses').mkdir()
        self.write_state('MI', [
            ('18001', 'W Nine Mile Road', 'Novi', 'MI', '48375', 42.45, -83.47),
            ('18002', 'W Nine Mile Road', 'Novi', 'MI', '48375', 42.46, -83.47),
            ('18001', 'Nine Mile Rd', 'Farmington', 'MI', '48335', 42.47, -83.40),
        ])
        self.write_state('CA', [
            ('18001', 'Nine Mile Road', 'Example', 'CA', '90001', 34.0, -118.0),
            ('23001', 'Maple Avenue', 'Kansas City', 'MO', '64105', 39.0997, -94.5786),
            ('21', 'W 9 ST', 'Example', 'CA', '90001', 34.01, -118.01),
            ('12', 'Oak Court', 'Example', 'CA', '90001', 34.02, -118.02),
            ('100', 'Main Street', 'Inglewood', 'CA', '90301', 33.96, -118.35),
            ('100', 'Main Street', 'Newport Beach', 'CA', '92661', 33.60, -117.90),
        ])

    def tearDown(self):
        self.temp.cleanup()

    def write_state(self, state, rows):
        db = sqlite3.connect(self.geo / 'addresses' / f'{state}.sqlite')
        try:
            db.execute('CREATE TABLE addr(num TEXT,street TEXT,norm TEXT,city TEXT,state TEXT,zip TEXT,lat REAL,lon REAL)')
            db.execute('CREATE INDEX addr_num_norm ON addr(num,norm)')
            db.executemany('INSERT INTO addr VALUES(?,?,?,?,?,?,?,?)',
                           [(num, street, normalize(street), city, st, z, lat, lon)
                            for num, street, city, st, z, lat, lon in rows])
            db.commit()
        finally:
            db.close()      # the `with` form commits but does not close, and Windows will not remove an open file

    def test_numeric_words_directions_and_qualifiers(self):
        for query in ('18001 9 mile rd Novi MI', '18001 Nine Mile Road Novi Michigan',
                      '18001 nine mile Novi 48375', '18001 W Nine Mile Road, Novi, MI 48375'):
            with self.subTest(query=query):
                result = find_addresses(query, self.geo)
                self.assertEqual(len(result), 1)
                self.assertEqual(result[0]['name'], '18001 W Nine Mile Road')
                self.assertEqual(result[0]['lat'], 42.45)
                self.assertEqual(result[0]['kind'], 'Street address')

    def test_unknown_number_does_not_return_nearby_house(self):
        self.assertEqual(find_addresses('18003 nine mile Novi MI', self.geo), [])

    def test_city_and_zip_do_not_silently_fall_back(self):
        self.assertEqual(find_addresses('18001 nine mile Wrongtown MI', self.geo), [])
        self.assertEqual(find_addresses('18001 nine mile MI 99999', self.geo), [])

    def test_zip_plus_four_uses_its_five_digit_zip(self):
        for query in ('18001 nine mile Novi MI 48375-1234', '18001 nine mile Novi MI 48375 1234'):
            with self.subTest(query=query):
                result = find_addresses(query, self.geo)
                self.assertEqual(len(result), 1)
                self.assertEqual(result[0]['name'], '18001 W Nine Mile Road')
        self.assertEqual(find_addresses('18001 nine mile Novi MI 99999-1234', self.geo), [])

    def test_state_uses_only_that_index(self):
        result = find_addresses('18001 nine mile CA', self.geo)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['detail'], 'Example, CA, 90001')

    def test_street_ending_that_is_also_a_state_code(self):
        # 'Ct' is Court before it is Connecticut, and 'NE' is northeast before it is Nebraska: neither state is installed here.
        result = find_addresses('12 Oak Ct', self.geo)
        self.assertEqual([r['name'] for r in result], ['12 Oak Court'])
        self.write_state('DC', [
            ('500', '4th Street NE', 'Washington', 'DC', '20002', 38.896, -77.000),
            ('1600', 'Pennsylvania Avenue NW', 'Washington', 'DC', '20500', 38.8977, -77.0365),
        ])
        for query in ('500 4th St NE', '500 4th St NE 20002', '500 4th St NE Washington DC'):
            with self.subTest(query=query):
                self.assertEqual([r['name'] for r in find_addresses(query, self.geo)], ['500 4th Street NE'])

    def test_installed_state_is_still_read_after_a_street_ending(self):
        self.write_state('CT', [('12', 'Oak Street', 'Hartford', 'CT', '06103', 41.76, -72.67)])
        self.assertEqual(find_addresses('12 Oak Ct', self.geo)[0]['detail'], 'Example, CA, 90001')      # the Court, as typed
        self.assertEqual(find_addresses('12 Oak St CT', self.geo)[0]['detail'], 'Hartford, CT, 06103')
        self.assertEqual(find_addresses('12 Oak Connecticut', self.geo)[0]['detail'], 'Hartford, CT, 06103')

    def test_town_named_like_a_state(self):
        self.write_state('DC', [('1600', 'Pennsylvania Avenue NW', 'Washington', 'DC', '20500', 38.8977, -77.0365)])
        for query in ('1600 Pennsylvania Ave NW Washington', '1600 Pennsylvania Ave NW Washington DC'):
            with self.subTest(query=query):
                self.assertEqual([r['detail'] for r in find_addresses(query, self.geo)], ['Washington, DC, 20500'])

    def test_state_that_is_not_installed_is_never_read_as_a_town(self):
        # Indiana, Nebraska and Kansas are not installed. 'IN' must not find Inglewood, 'NE' Newport Beach, or 'Kansas' Kansas City.
        for query in ('100 Main St IN', '100 Main St NE', '100 Main St Indiana', '100 Main St IN 90301', '23001 Maple Ave Kansas'):
            with self.subTest(query=query):
                self.assertEqual(find_addresses(query, self.geo), [])

    def test_ordinal_street(self):
        result = find_addresses('21 ninth st Example CA', self.geo)
        self.assertEqual(result[0]['name'], '21 W 9 ST')

    def test_plain_zip_remains_place_query(self):
        self.assertFalse(is_address_query('48375'))
        self.assertFalse(is_address_query('Novi MI'))
        self.assertTrue(is_address_query('18001 nine mile'))

    def test_missing_indexes_and_legacy_database(self):
        empty = self.geo / 'empty'
        self.assertEqual(find_addresses('23001 Maple Ave', empty), [])
        empty.mkdir()
        db = sqlite3.connect(empty / 'addresses.sqlite')
        try:
            db.execute('CREATE TABLE addr(num TEXT,street TEXT,norm TEXT,city TEXT,state TEXT,zip TEXT,lat REAL,lon REAL)')
            db.execute("INSERT INTO addr VALUES('23001','Maple Avenue','maple ave','Kansas City','MO','64105',39.0997,-94.5786)")
            db.commit()
        finally:
            db.close()      # as in write_state: the `with` form does not close, and Windows will not remove an open file
        self.assertEqual(find_addresses('23001 Maple Ave Kansas City MO', empty)[0]['lat'], 39.0997)

    def test_app_route_preserves_address_number(self):
        import server
        with patch.object(server, 'HERE', self.geo.parent), patch.object(server.address_search, 'find_addresses', return_value=[]) as lookup:
            self.assertEqual(server.places('18003 nine mile'), [])
            lookup.assert_called_once_with('18003 nine mile', self.geo.parent / 'derived' / 'geo', limit=8,
                                         near=None, model=server.assistant.LOCAL, parcel_offset=0, parcel_limit=20)


class RegionalFallbackTests(unittest.TestCase):
    """Rural-looking words must not hide an ordinary installed address."""
    write_state = AddressSearchTests.write_state

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.geo = self.root / 'derived' / 'geo'
        (self.geo / 'addresses').mkdir(parents=True)
        self.write_state('TX', [
            ('200', 'County Road 5 Exit', 'Exampleville', 'TX', '75000', 1, 2),
            ('300', 'Old Highway 2 Salida Rd', 'Exampleville', 'TX', '75000', 3, 4),
            ('19', 'KM4HM4 Boulevard', 'Las Penas', 'TX', '75000', 5, 6),
        ])

    def assert_route_finds_texas(self):
        import server
        with patch.object(server, 'HERE', self.root), patch.object(server.assistant, 'LOCAL', None):
            for query, name, city in (
                    ('200 County Road 5 Exit', '200 County Road 5 Exit', 'Exampleville'),
                    ('300 Old Highway 2 Salida Rd', '300 Old Highway 2 Salida Rd', 'Exampleville'),
                    ('19 KM4HM4 BLVD, Las Penas', '19 KM4HM4 Boulevard', 'Las Penas')):
                with self.subTest(query=query):
                    rows = server.places(query)
                    self.assertEqual([r['name'] for r in rows], [name])
                    self.assertEqual(rows[0]['detail'], f'{city}, TX, 75000')
                    self.assertEqual(rows[0]['kind'], 'Street address')

    def test_rural_looking_place_names_fall_through_to_installed_gazetteer(self):
        import server
        gazetteer = self.geo / 'places.sqlite'
        names = ('Highway 1 Exit', 'Route 9 Parking Lot')
        with closing(sqlite3.connect(gazetteer)) as db, db:
            db.executescript('CREATE TABLE place(id INTEGER PRIMARY KEY,name,kind,detail,lat,lon,rank,source);'
                             'CREATE VIRTUAL TABLE place_fts USING fts5(name,detail);')
            for i, name in enumerate(names, 1):
                db.execute('INSERT INTO place VALUES(?,?,?,?,?,?,?,?)', (i,name,'Place','Texas',i,2,1,'invented fixture'))
                db.execute('INSERT INTO place_fts(rowid,name,detail) VALUES(?,?,?)', (i,name,'Texas'))
        with patch.object(server, 'HERE', self.root), patch.object(server, 'PLACEDB', gazetteer), \
                patch.object(server.assistant, 'LOCAL', None), patch.object(server, 'home_area', return_value=None), \
                patch.object(server, 'national_mapdb', return_value=None), patch.object(server, 'pack_info', return_value=None), \
                patch.object(server, 'water_places', return_value=[]):
            for with_pr in (False, True):
                if with_pr:
                    with closing(sqlite3.connect(self.geo / 'addresses/PR.sqlite')) as db, db:
                        db.execute('CREATE TABLE pr_road(route,bucket,low,high,lat0,lon0,lat1,lon1,area)')
                for name in names:
                    with self.subTest(pr_installed=with_pr, query=name):
                        rows = server.places(name)
                        self.assertEqual([r['name'] for r in rows], [name])
                        self.assertFalse(any(r.get('parcelNumber') for r in rows))
                        self.assertEqual(server.places(name, parcel_offset=1), [])

    def test_offset_never_restarts_an_unavailable_pr_lookup_as_a_street(self):
        import server
        query = '200 County Road 5 Exit'
        with patch.object(server, 'HERE', self.root), patch.object(server.assistant, 'LOCAL', None):
            self.assertEqual(server.places(query, parcel_offset=1), [])
            (self.geo / 'addresses/PR.sqlite').write_bytes(b'not a database')
            self.assertEqual(server.places(query, parcel_offset=1), [])
            self.assertEqual(server.places('099-099-099-99'), [])

    def test_texas_only_index_with_rural_looking_street_names(self):
        self.assert_route_finds_texas()

    def test_pr_index_without_rural_tables_does_not_consume_query(self):
        self.write_state('PR', [])
        self.assert_route_finds_texas()

    def test_empty_pr_rural_lookup_does_not_consume_query(self):
        with closing(sqlite3.connect(self.geo / 'addresses' / 'PR.sqlite')) as db, db:
            db.executescript("""
                CREATE TABLE pr_area(id,barrio,municipio,zip);
                CREATE TABLE pr_road(route,bucket,low,high,lat0,lon0,lat1,lon1,area);
                CREATE TABLE pr_school(route,meters,name,street,lat,lon,area,postal,reported_city);
            """)
        self.assert_route_finds_texas()

    def test_unreadable_pr_index_does_not_hide_other_installed_addresses(self):
        (self.geo / 'addresses' / 'PR.sqlite').write_bytes(b'not a SQLite database')
        self.assert_route_finds_texas()


if __name__ == '__main__':
    unittest.main()
