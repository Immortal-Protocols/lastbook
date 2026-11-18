"""Offline address lookup must preserve house numbers and geographic qualifiers."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from engine.address_search import (find_addresses, is_address_query, is_german_address_query,
                                   normalize, normalize_de)


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
            lookup.assert_called_once_with('18003 nine mile', self.geo.parent / 'derived' / 'geo', limit=8, near=None)


class GermanAddressTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.geo = Path(self.temp.name) / 'root' / 'derived' / 'geo'
        (self.geo / 'addresses').mkdir(parents=True)
        db = sqlite3.connect(self.geo / 'addresses' / 'DE-BW-ST.sqlite')
        try:
            db.executescript(
                'CREATE TABLE addr(num TEXT,street TEXT,norm TEXT,city TEXT,state TEXT,zip TEXT,lat REAL,lon REAL,district TEXT);'
                "CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT);")
            rows = [
                ('5', 'Hauptstraße', 'Stuttgart', '70173', 48.7758, 9.1829, 'Stuttgart-Mitte'),
                ('28', 'Königstraße', 'Stuttgart', '70173', 48.7784, 9.1800, 'Stuttgart-Mitte'),
                ('12A', 'Berliner Straße', 'Stuttgart', '70376', 48.8156, 9.2275, 'Bad Cannstatt'),
                ('5', 'Straße des 17. Juni', 'Stuttgart', '70178', 48.7770, 9.1740, 'Stuttgart-West'),
            ]
            db.executemany('INSERT INTO addr VALUES (?,?,?,?,?,?,?,?,?)',
                           [(num, street, normalize_de(street), city, 'DE-BW-ST', zip_code, lat, lon, district)
                            for num, street, city, zip_code, lat, lon, district in rows])
            db.execute("INSERT INTO meta VALUES ('norm','de-1')")
            db.execute("INSERT INTO meta VALUES ('source','OpenStreetMap (ODbL 1.0)')")
            db.commit()
        finally:
            db.close()

    def tearDown(self):
        self.temp.cleanup()

    def test_street_first_order_and_umlaut_spellings(self):
        for query in ('Königstraße 28', 'Koenigstrasse 28', 'Königstr. 28 Stuttgart', 'Königstraße 28, 70173 Stuttgart'):
            with self.subTest(query=query):
                found = find_addresses(query, self.geo)
                self.assertEqual([hit['name'] for hit in found], ['Königstraße 28'])
                self.assertEqual(found[0]['lat'], 48.7784)

    def test_letter_and_range_house_numbers(self):
        for query in ('Berliner Straße 12a', 'Berliner Str. 12 A'):
            with self.subTest(query=query):
                self.assertEqual([hit['name'] for hit in find_addresses(query, self.geo)],
                                 ['Berliner Straße 12A'])

    def test_range_house_numbers_use_the_first_endpoint(self):
        hit, = find_addresses('Hauptstraße 5-7, 70173 Stuttgart', self.geo)
        self.assertEqual(hit['name'], 'Hauptstraße 5')

    def test_street_name_with_number_is_not_the_house(self):
        hit, = find_addresses('Straße des 17. Juni 5', self.geo)
        self.assertEqual(hit['name'], 'Straße des 17. Juni 5')

    def test_unknown_house_or_city_returns_nothing(self):
        self.assertEqual(find_addresses('Hauptstraße 999 Stuttgart', self.geo), [])
        self.assertEqual(find_addresses('Königstraße 28, 80331 München', self.geo), [])

    def test_postcode_and_city_are_place_queries(self):
        self.assertFalse(is_german_address_query('70173 Stuttgart'))
        self.assertFalse(is_german_address_query('Stuttgart'))
        self.assertTrue(is_german_address_query('Hauptstraße 5'))

    def test_app_route_reaches_the_german_index(self):
        import server
        with patch.object(server, 'HERE', self.geo.parents[1]), \
                patch.object(server, 'PLACEDB', self.geo / 'no-places.sqlite'), \
                patch.object(server, 'WATERDB', self.geo / 'no-water.sqlite'), \
                patch.object(server, 'home_area', return_value=None):
            hit, = server.places('Hauptstraße 5')
            self.assertEqual((hit['name'], hit['kind']), ('Hauptstraße 5', 'Street address'))


if __name__ == '__main__':
    unittest.main()
