"""Offline address lookup must preserve house numbers and geographic qualifiers."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from engine.address_search import find_addresses, fold, is_address_query, normalize


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


class UkAddressSearchTests(unittest.TestCase):
    """UK indexes (docs/REGIONS-UK.md): postcode in `zip` as 'SW1A 2AA', the index's own meta 'source', region id 'GB-SE'."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.geo = Path(self.temp.name)
        (self.geo / 'addresses').mkdir()
        self.write_index('GB-SE', 'OpenStreetMap contributors (ODbL)', [
            ('10', 'Downing Street', 'London', '', 'SW1A 2AA', 51.5034, -0.1276),
            ('10', 'Downing Street', 'Leeds', '', 'LS1 4AB', 53.7960, -1.5470),
            ('7', 'Church Lane', 'Washington', '', 'NE37 1AA', 54.9000, -1.5200),
        ])
        self.write_index('GB-WLS', 'OpenStreetMap contributors (ODbL)', [
            ('3', 'Ffordd y Cwn', 'Cardiff', '', 'CF10 1AA', 51.4816, -3.1791),
        ])

    def tearDown(self):
        self.temp.cleanup()

    def write_index(self, region, source, rows):
        db = sqlite3.connect(self.geo / 'addresses' / f'{region}.sqlite')
        try:
            db.execute('CREATE TABLE addr(num TEXT,street TEXT,norm TEXT,city TEXT,state TEXT,zip TEXT,lat REAL,lon REAL)')
            db.execute('CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT)')
            db.execute("INSERT INTO meta VALUES('source', ?)", (source,))
            db.executemany('INSERT INTO addr VALUES(?,?,?,?,?,?,?,?)',
                           [(num, street, normalize(fold(street)), city, st, z, lat, lon) for num, street, city, st, z, lat, lon in rows])
            db.commit()
        finally:
            db.close()

    def test_postcode_with_and_without_space_and_in_any_case(self):
        for query in ('10 Downing Street SW1A 2AA', '10 downing street sw1a2aa', '10 Downing Street, London SW1A 2AA'):
            with self.subTest(query=query):
                result = find_addresses(query, self.geo)
                self.assertEqual(len(result), 1)
                self.assertEqual(result[0]['name'], '10 Downing Street')
                self.assertEqual(result[0]['lat'], 51.5034)
                self.assertEqual(result[0]['detail'], 'London, SW1A 2AA')

    def test_wrong_postcode_does_not_fall_back_to_another_house(self):
        self.assertEqual(find_addresses('10 Downing Street SW1A 9ZZ', self.geo), [])

    def test_town_qualifier_without_postcode(self):
        result = find_addresses('10 Downing Street Leeds', self.geo)
        self.assertEqual([r['detail'] for r in result], ['Leeds, LS1 4AB'])

    def test_result_is_credited_to_the_index_source(self):
        self.assertEqual(find_addresses('10 Downing Street SW1A 2AA', self.geo)[0]['source'], 'OpenStreetMap contributors (ODbL)')

    def test_accented_welsh_letters_fall_back_to_folded_text(self):
        for query in ('3 Ffordd y Cŵn Cardiff', '3 Ffordd y Cwn CF10 1AA'):
            with self.subTest(query=query):
                result = find_addresses(query, self.geo)
                self.assertEqual(len(result), 1)
                self.assertEqual(result[0]['name'], '3 Ffordd y Cwn')

    def test_town_named_like_a_us_state_is_a_town_when_no_such_state_index_is_installed(self):
        # Washington (Tyne and Wear) is also a US state name; no WA index is installed here.
        for query in ('7 Church Lane Washington NE37 1AA', '7 Church Lane Washington'):
            with self.subTest(query=query):
                self.assertEqual(find_addresses(query, self.geo)[0]['detail'], 'Washington, NE37 1AA')

    def test_state_not_installed_still_finds_nothing_when_a_us_index_is_installed(self):
        # The town-not-state reading above applies only when no US state index is installed at all.
        with tempfile.TemporaryDirectory() as directory:
            geo = Path(directory)
            (geo / 'addresses').mkdir()
            db = sqlite3.connect(geo / 'addresses' / 'MI.sqlite')
            try:
                db.execute('CREATE TABLE addr(num TEXT,street TEXT,norm TEXT,city TEXT,state TEXT,zip TEXT,lat REAL,lon REAL)')
                db.execute("INSERT INTO addr VALUES('18001','Nine Mile Road','nine mile rd','Canton','MI','48188',42.3,-83.4)")
                db.commit()
            finally:
                db.close()
            self.assertEqual(len(find_addresses('18001 nine mile Canton MI', geo)), 1)
            self.assertEqual(find_addresses('18001 nine mile CA', geo), [])
            self.assertEqual(find_addresses('18001 nine mile California', geo), [])

    def test_uk_postcode_reading(self):
        from engine.address_search import uk_postcode
        self.assertEqual(uk_postcode(['downing', 'sw1a', '2aa']), ('SW1A 2AA', 2))
        self.assertEqual(uk_postcode(['m11aa']), ('M1 1AA', 1))
        self.assertEqual(uk_postcode(['cr26xh']), ('CR2 6XH', 1))
        for words in (['highway', 'i5'], ['main', 'st'], ['90210'], ['apt', '4b'], []):
            with self.subTest(words=words):
                self.assertIsNone(uk_postcode(words))

    def test_us_five_digit_zip_is_unchanged(self):
        from engine.address_search import _parts
        self.assertEqual(_parts('18001 Nine Mile Novi MI 48375'), ('18001', ['nine', 'mile', 'novi'], 'MI', '48375'))


if __name__ == '__main__':
    unittest.main()
