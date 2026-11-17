"""Order-independent Puerto Rico road searches through the normal offline place route."""
import itertools
import json
import sqlite3
import tempfile
import threading
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import Mock, patch

from engine import address_search, pr_rural_model
from engine.pr_rural import parse


class RuralLookup(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.geo = self.root / 'derived/geo'
        folder = self.geo / 'addresses'
        folder.mkdir(parents=True)
        with closing(sqlite3.connect(folder / 'PR.sqlite')) as db:
            db.executescript("""
                CREATE TABLE pr_area(id INTEGER PRIMARY KEY,barrio TEXT,municipio TEXT,zip TEXT);
                CREATE TABLE pr_road(route,bucket,low,high,lat0,lon0,lat1,lon1,area);
                CREATE TABLE pr_school(route,meters,name,street,lat,lon,area,postal,reported_city);
                INSERT INTO pr_area VALUES(1,'Las Peñas','Villa Ejemplo','00700');
                INSERT INTO pr_road VALUES(19,4,4300,4500,1.0,2.0,1.002,2.004,1);
                INSERT INTO pr_road VALUES(19,4,4300,4500,1.0001,2.0001,1.0021,2.0041,1);
                INSERT INTO pr_school VALUES(19,4400,'Escuela de Ejemplo','CARR 19 KM 4 HM 4 BARRIO ALIAS',
                                             1.01,2.01,1,'00701','Ciudad Postal');
            """)

    def lookup(self, query):
        import server
        with patch.object(server, 'HERE', self.root):
            return server.places(query)

    def test_component_order_and_qualifiers(self):
        for parts in itertools.permutations(('Bo. Las Peñas', 'Ctra. PR-19', 'Km 4,4')):
            q = ', '.join(parts) + ', Villa Ejemplo, PR 00700'
            with self.subTest(parts=parts):
                rows = self.lookup(q)
                self.assertEqual(len(rows), 1)
                self.assertEqual((rows[0]['kind'], rows[0]['lat'], rows[0]['lon']), ('Road kilometer', 1.001, 2.002))
                self.assertEqual(rows[0]['name'], 'PR-19 km 4.4')
        for q in ('HM. 4 Bº Las Penas Carr. #19 K.M.4', 'kilómetro 4.400, ruta 19, municipio Villa Ejemplo',
                  '19 KM4HM4 BLVD, Las Penas', 'Bo Las Penas, PR-19, Km 4.4', 'Carr. 19KM4.4, Villa Ejemplo'):
            self.assertEqual(self.lookup(q)[0]['name'], 'PR-19 km 4.4')

    def test_interior_sector_and_landmark_are_only_road_hints(self):
        q = 'Sector Sol, Bo las Peñas, frente a la cancha, KM 4.4 Interior, Carr. 19, Villa Ejemplo'
        row, = self.lookup(q)
        self.assertEqual(row['kind'], 'Road kilometer')
        self.assertIn('Interior access', row['detail'])
        self.assertIn('Sector directions', row['detail'])
        self.assertIn('Landmark directions', row['detail'])
        self.assertEqual(self.lookup(q.replace('las Peñas', 'Otro')), [])

    def test_school_keeps_its_reported_barrio_city_zip_and_coordinates(self):
        rows = self.lookup('Bo. Alias, KM4.4, PR-19, Ciudad Postal, PR 00701')
        self.assertEqual([(r['kind'], r['name'], r['lat']) for r in rows], [('Public school', 'Escuela de Ejemplo', 1.01)])
        self.assertEqual(self.lookup('Bo. Alias PR-19 km 4.4, Otra Ciudad'), [])
        self.assertEqual([r['kind'] for r in self.lookup('PR-19 km 4.4')], ['Road kilometer', 'Public school'])

    def test_missing_data_gaps_and_ambiguous_input(self):
        for q in ('PR-19 km 4.2', 'PR-19 km 4.6', 'PR-18 km 4.4', 'Bo. Otro, PR-19 km 4.4',
                  'PR-19 km 4.4, 00702', 'PR-19 km 4.4, Unknown', 'PR-19 km 4.4, FL'):
            self.assertEqual(self.lookup(q), [])
        for q in ('HC 10 Box 44', 'PR-19 Villa Ejemplo', 'CARR 19 RAMAL 20 KM 4.4',
                  'Carr 19 km 4.4 hm 6', 'Carr 19 km 4 km 5', 'PR-19 km 4.1234'):
            self.assertIsNone(parse(q))
        self.assertEqual(address_search.find_addresses('Carr 19 km 4.4', self.root / 'empty'), [])

    def test_local_model_reads_speech_after_a_miss_and_cannot_move_an_existing_pin(self):
        import server
        model = Mock()
        model.gen_lock.locked.return_value = False
        model.ensure_running.return_value = None
        output = [19, '4.4', 'Las Peñas Villa Ejemplo', '', False, '', '']
        def generate(segments, budget, cancelled, piece, only_if_idle):
            self.assertTrue(only_if_idle)
            piece(json.dumps(output))
        model.generate.side_effect = generate
        with patch.object(server, 'HERE', self.root), patch.object(server.assistant, 'LOCAL', model):
            known = server.places('Ctra 19 km 4.4, Bo Las Peñas, Villa Ejemplo')
            self.assertNotIn('interpreted', known[0])
            model.generate.assert_not_called()
            spoken = 'En Villa Ejemplo, por la diecinueve, kilómetro cuatro punto cuatro, barrio Las Peñas'
            answer = server.places(spoken)
            self.assertEqual(answer[0]['lat'], known[0]['lat'])
            self.assertIn('PR-19 km 4.4', answer[0]['interpreted'])
            for idx, value in [(0,18), (1,'4.5'), (2,'Villa Ejemplo'), (3,'00999'), (4,True), (6,'Las Peñas')]:
                previous, output[idx] = output[idx], value
                self.assertEqual(server.places(spoken), [])
                output[idx] = previous
            model.generate.side_effect = lambda seg,budget,cancel,piece,**kw: piece('unreadable answer')
            self.assertEqual(server.places(spoken), [])
            model.generate.reset_mock()
            model.gen_lock.locked.return_value = True
            self.assertEqual(server.places(spoken), [])
            model.generate.assert_not_called()
            model.gen_lock.locked.return_value = False
            model.enabled.return_value = False
            self.assertEqual(server.places(spoken), [])
            model.generate.assert_not_called()

    def test_unsafe_or_unaccounted_directions_remain_unresolved(self):
        make = pr_rural_model.fields
        answer = make([19, '4.4', 'Las Peñas', '', False, '', ''])
        for query in ('Cuatro kilómetros después del pueblo, PR-19, Las Peñas',
                      'PR-19 km 4.4, Las Peñas, casa #7', 'PR-19 km 4.4, Las Peñas, #7',
                      'PR-19 km 4.4 o km 5.4, Las Peñas', 'PR-19 km 4.4, Bo. Las Peñas, Pueblo Otro',
                      'PR-19 o PR-77, km 4.4, Las Peñas', 'PR-19 km 4.4, Las Peñas 00999',
                      'PR-19 km 4.4, Las Peñas, sector Azul'):
            self.assertFalse(pr_rural_model.grounded(query, answer, parse(query)), query)
        swapped = make([19,'4.4','Sol','',False,'Las Peñas',''])
        q = 'Barrio Las Peñas, PR-19 km 4.4, Sector Sol'
        self.assertFalse(pr_rural_model.grounded(q, swapped, parse(q)))
        self.assertFalse(address_search.is_address_query('KM Market'))

    def test_map_returns_on_timeout_without_stopping_other_model_work(self):
        model, release = Mock(), threading.Event()
        model.gen_lock.locked.return_value = False
        model.ensure_running.side_effect = lambda **kwargs: release.wait(3) and 'stopped'
        capacity = threading.BoundedSemaphore(1)
        try:
            with patch.object(pr_rural_model, 'BUDGET', 0.05), patch.object(pr_rural_model, 'CAPACITY', capacity):
                self.assertIsNone(pr_rural_model.interpret(model, 'Ctra 19 km 4.4', None))
                self.assertIsNone(pr_rural_model.interpret(model, 'Ctra 19 km 4.4', None))
                release.set()
                self.assertTrue(capacity.acquire(timeout=2))
                capacity.release()
        finally:
            release.set()
        model.generate.assert_not_called()
        model.stop.assert_not_called()
