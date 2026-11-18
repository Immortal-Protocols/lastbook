"""Offline address lookup must preserve house numbers and geographic qualifiers."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from engine.address_search import find_addresses, is_address_query, normalize


class CountingConnection:
    """Wraps a sqlite3 connection and records how many rows each query hands back to Python."""

    def __init__(self, connection, fetched):
        self.connection = connection
        self.fetched = fetched

    def execute(self, sql, parameters=()):
        rows = self.connection.execute(sql, parameters).fetchall()
        self.fetched.append(len(rows))
        return SimpleNamespace(fetchall=lambda: rows)

    def close(self):
        self.connection.close()


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
            ('123', 'Main Street', 'North Hollywood', 'CA', '91601', 34.16, -118.37),
            ('123', 'North Main Street', 'North Hollywood', 'CA', '91601', 34.17, -118.38),
        ])
        self.write_state('MN', [('10', 'Oak Avenue', 'Saint Paul', 'MN', '55101', 44.95, -93.09)])
        self.write_state('MO', [('10', 'Oak Avenue', 'St. Louis', 'MO', '63101', 38.63, -90.20)])

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

    def test_city_with_direction_or_saint_matches_stored_title_case(self):
        result = find_addresses('123 Main St North Hollywood', self.geo)
        self.assertIn('123 Main Street', [row['name'] for row in result])
        result = find_addresses('123 North Main Street North Hollywood CA', self.geo)
        self.assertEqual(result[0]['name'], '123 North Main Street')
        self.assertEqual(find_addresses('123 Main St Hollywood North', self.geo), [])
        for query in ('10 Oak Ave Saint Paul MN', '10 Oak Ave St Paul MN', '10 Oak Ave Saint Paul'):
            with self.subTest(query=query):
                result = find_addresses(query, self.geo)
                self.assertEqual(len(result), 1)
                self.assertEqual(result[0]['name'], '10 Oak Avenue')
                self.assertEqual(result[0]['detail'], 'Saint Paul, MN, 55101')

    def test_city_punctuation_is_ignored(self):
        for query in ('10 Oak Ave St Louis MO', '10 Oak Ave Saint Louis MO', '10 Oak Ave St. Louis MO'):
            with self.subTest(query=query):
                result = find_addresses(query, self.geo)
                self.assertEqual(len(result), 1)
                self.assertEqual(result[0]['detail'], 'St. Louis, MO, 63101')
        self.assertEqual(find_addresses('10 Oak Ave Saint Louis Park MO', self.geo), [])

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

    def test_null_city_row_does_not_break_city_query(self):
        self.write_state('OH', [
            ('5', 'Elm Street', None, 'OH', '43001', 40.0, -83.0),
            ('5', 'Elm Street', 'Columbus', 'OH', '43215', 39.96, -83.0),
        ])
        result = find_addresses('5 elm Columbus OH', self.geo)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['detail'], 'Columbus, OH, 43215')

    def test_city_query_fetches_only_rows_it_can_keep(self):
        # Same number and street in other cities: only the first-letter prefilter should keep them out of Python.
        self.write_state('IL', [('100', 'Main Street', 'Springfield', 'IL', '62701', 39.80, -89.64)])
        self.write_state('NV', [('100', 'Main Street', 'Boston', 'NV', '89501', 39.5, -119.8)] * 300)
        fetched = []
        real_connect = sqlite3.connect
        with patch('engine.address_search.sqlite3.connect',
                   side_effect=lambda *args, **kwargs: CountingConnection(real_connect(*args, **kwargs), fetched)):
            result = find_addresses('100 main springfield', self.geo)
        self.assertEqual(result[0]['detail'], 'Springfield, IL, 62701')
        self.assertLessEqual(sum(fetched), 10)

    def test_city_query_fetch_is_limited_when_first_letter_matches(self):
        self.write_state('IL', [('100', 'Main Street', 'Springfield', 'IL', '62701', 39.80, -89.64)])
        self.write_state('NV', [('100', 'Main Street', 'Sparks', 'NV', '89431', 39.5, -119.7)] * 300)
        fetched = []
        real_connect = sqlite3.connect
        with patch('engine.address_search.sqlite3.connect',
                   side_effect=lambda *args, **kwargs: CountingConnection(real_connect(*args, **kwargs), fetched)):
            result = find_addresses('100 main springfield', self.geo)
        self.assertEqual(result[0]['detail'], 'Springfield, IL, 62701')
        self.assertLessEqual(max(fetched), 8 * 20)

    def test_app_route_preserves_address_number(self):
        import server
        with patch.object(server, 'HERE', self.geo.parent), patch.object(server.address_search, 'find_addresses', return_value=[]) as lookup:
            self.assertEqual(server.places('18003 nine mile'), [])
            lookup.assert_called_once_with('18003 nine mile', self.geo.parent / 'derived' / 'geo', limit=8, near=None)


if __name__ == '__main__':
    unittest.main()
