"""Puerto Rico lookup through the map route. All addresses in this fixture are invented."""
import sqlite3
import tempfile
import unicodedata
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from engine import pr_addresses as pr
from engine.address_search import find_addresses, is_address_query, normalize


class PuertoRicoAddresses(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.geo = self.root / 'derived' / 'geo'
        self.indexes = self.geo / 'addresses'
        self.indexes.mkdir(parents=True)
        with closing(sqlite3.connect(self.indexes / 'PR.sqlite')) as db:
            db.executescript('CREATE TABLE meta(key TEXT,value TEXT); '
                             'CREATE TABLE addr(num TEXT,street TEXT,norm TEXT,city TEXT,state TEXT,zip TEXT,lat REAL,lon REAL,'
                             'street_key TEXT,city_key TEXT,municipio_key TEXT,urbanization TEXT,urb_key TEXT);')
            db.execute('INSERT INTO meta VALUES (?,?)', ('search_profile', pr.PROFILE))
            for number, street, city, municipio, postal, urb, lat in (
                    ('A-12', 'Avenida del Ñandú', 'Villa Ámbar', 'Ejemplo', '00901', 'Luz', 1),
                    ('A-12', 'Avenida del Ñandú', 'Villa Ámbar', 'Ejemplo', '00901', 'Sol', 2),
                    ('9B', 'Calle del Camino', 'Ejemplo', 'Ejemplo', '', '', 3),
                    ('I-12', 'Carretera PR-3', 'Ejemplo', 'Ejemplo', '', '', 4),
                    ('B(1)-2', 'Cam. Río', 'Ejemplo', 'Ejemplo', '', '', 5),
                    ('3/2A', 'Bulevar Sol', 'Ejemplo', 'Ejemplo', '', '', 6)):
                db.execute('INSERT INTO addr VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                           (number, street, normalize(street), city, 'PR', postal, lat, 1, pr.street_key(street),
                            pr.fold(city), pr.fold(municipio), urb, pr.fold(urb)))
            db.commit()

    def test_map_route_accents_abbreviations_and_geographic_qualifiers(self):
        import server
        with patch.object(server, 'HERE', self.root):
            for query in ('a-12 Ave. del Nandu, Villa Ambar, PR 00901', '#A-12 Avda del Ñandú, Ejemplo, Puerto Rico',
                          unicodedata.normalize('NFD', 'A-12 Av. del Ñandú, Villa Ámbar, PR')):
                with self.subTest(query=query):
                    result = server.places(query, near=(2, 1))
                    self.assertEqual([r['lat'] for r in result], [2, 1])
                    self.assertEqual(result[0]['name'], 'A-12 Avenida del Ñandú')
                    self.assertEqual(result[0]['detail'], 'Urb. Sol, Villa Ámbar, PR, 00901')
                    self.assertEqual(result[0]['source'], pr.SOURCE)

    def test_urbanization_disambiguation_and_strict_misses(self):
        for query in ('Urb. Luz, A-12 Avenida del Nandu, PR 00901-1234',
                      'A-12 Ave del Nandu, Urbanización Luz, Villa Ambar, PR',
                      unicodedata.normalize('NFD', 'Urbanización Luz, A-12 Ave del Ñandú, PR')):
            self.assertEqual([r['lat'] for r in find_addresses(query, self.geo)], [1])
        for query in ('Urb. Mar, A-12 Ave del Nandu PR', 'A-13 Ave del Nandu PR', 'A-12 Ave del Nandu Otro PR',
                      'A-12 Ave del Nandu PR 00902', '9B Cll del Camino PR 00901', 'A-12 Ave del Nandu FL'):
            with self.subTest(query=query):
                self.assertEqual(find_addresses(query, self.geo), [])

    def test_other_street_forms_and_numbers(self):
        for name, query in (('9B Calle del Camino', '9b Cll. del Camino, PR'),
                            ('I-12 Carretera PR-3', 'I-12 Carr. PR-3, PR'),
                            ('I-12 Carretera PR-3', 'I-12 Ctra PR 3'),
                            ('B(1)-2 Cam. Río', 'B(1)-2 Camino Rio'),
                            ('3/2A Bulevar Sol', '3/2a Blvd. Sol')):
            self.assertEqual(find_addresses(query, self.geo)[0]['name'], name)
        for query in ('00901', 'PR-3 Humacao', 'I-95 Rest Area', 'B52 Museum', 'Urb. Luz, Ejemplo'):
            self.assertFalse(is_address_query(query))

    def test_legacy_state_and_pr_indexes(self):
        with closing(sqlite3.connect(self.indexes / 'MI.sqlite')) as db:
            db.execute('CREATE TABLE addr(num TEXT,street TEXT,norm TEXT,city TEXT,state TEXT,zip TEXT,lat REAL,lon REAL)')
            db.execute("INSERT INTO addr VALUES ('9B','Calle del Camino','calle del camino','Test','MI','',5,5)")
            db.commit()
        results = find_addresses('9B Calle del Camino', self.geo, near=(5, 5))
        self.assertEqual([r['source'] for r in results], ['Overture Maps', pr.SOURCE])
        self.assertEqual(len(find_addresses('9B Calle del Camino', self.geo, limit=1)), 1)
        with closing(sqlite3.connect(self.indexes / 'PR.sqlite')) as db:
            db.execute('DROP TABLE meta')
            db.commit()
        self.assertEqual(find_addresses('9B Calle del Camino PR', self.geo)[0]['source'], 'Overture Maps')
