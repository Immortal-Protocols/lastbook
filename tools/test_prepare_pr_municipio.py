"""Prepare a portable municipio index from synthetic records and search it through the reader."""
from contextlib import closing
import csv
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from engine import pr_permit
from tools import prepare_pr_municipio as municipal


def municipality_list(*names):
    return {'features': [{'attributes': {'MUNICIPIO': name}} for name in names]}


class MunicipalIndex(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.original = self.root / 'input.sqlite'
        self.output = self.root / 'derived/geo/addresses/PR.sqlite'
        with closing(sqlite3.connect(self.original)) as db, db:
            db.executescript("""
                CREATE TABLE municipios(name);
                INSERT INTO municipios VALUES ('San Sebastián'), ('Aguada');
                CREATE TABLE pr_parcel(id,base,barrio,municipio,zip,lat,lon,area,rings);
                CREATE TABLE pr_account(number PRIMARY KEY);
                CREATE TABLE pr_parcel_address(base,route,meters,lot,sector,interior,access,postal,landmark,source);
            """)
            db.execute(pr_permit.SCHEMA)
            for i, town in enumerate(('San Sebastián', 'San Sebastián', 'Aguada'), 1):
                db.execute('INSERT INTO pr_parcel VALUES(?,?,?,?,?,?,?,?,?)',
                           (i, f'0010020030{i}', 'Peña', town, '', 1, 2, 1, '[[[2,1],[2,2],[3,1],[2,1]]]'))

    def test_offline_search_ambiguity_boundaries_and_source_text(self):
        import server
        path = self.root / 'parcels.csv'
        address = 'Bo. Peña, Solar 6, PR, Puerto Rico, 00000'
        with path.open('w', encoding='utf-8', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(['Número de catastro', 'Dirección física', 'municipio', 'owner'])
            for num in ('30-001-002-003-01', '00100200302', '00100200302', '00100200303', '26-001-002-003-03'):
                writer.writerow([num, address, 'San Sebastian', 'unused-field'])
            writer.writerow(['00100200303', address, 'Aguada', 'unused-field'])
            for placeholder in ('PR, 00000', 'San Sebastián, PR, 00000', '---', 'N/A'):
                writer.writerow(['00100200301', placeholder, 'San Sebastián', 'unused-field'])
        with patch.object(municipal, 'query', side_effect=AssertionError('unexpected network use')):
            result = municipal.prepare(self.original, self.output, 'san sebastian', csv_paths=[path])
        self.assertEqual((result['new_wordings'], result['new_parcels_with_wording']), (2, 2))
        with patch.object(server, 'HERE', self.root):
            pasted = server.places(address + ', San Sebastián')
            self.assertEqual(len(pasted), 2)
            query = 'Lote 6, Barrio Pena, San Sebastián'
            first, = server.places(query, limit=1)
            second, = server.places(query, limit=1, parcel_offset=1)
            self.assertEqual([first['parcelNumber'], second['parcelNumber']], ['001-002-003-01','001-002-003-02'])
            self.assertTrue(first['rings'])
            self.assertIn(address, first['name'])
            self.assertEqual(first['parcelCount'], 2)
            self.assertEqual(server.places(query, parcel_offset=2), [])
            self.assertFalse(any(r.get('parcelNumber') for r in server.places(query.replace('6', '9'))))
        with self.assertRaises(FileExistsError):
            municipal.prepare(self.original, self.output, 'San Sebastián', csv_paths=[path])
        with closing(sqlite3.connect(self.original)) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM pr_permit_wording').fetchone()[0], 0)
        self.assertNotIn(b'unused-field', self.output.read_bytes())
        with closing(sqlite3.connect(self.output)) as db, db:
            db.execute("UPDATE pr_permit_wording SET signature='literal from older reader'")
        repeat = municipal.prepare(self.output, self.root / 'again.sqlite', 'San Sebastián', csv_paths=[path])
        self.assertEqual((repeat['new_wordings'], repeat['parcels_with_wording']), (0, 2))

    def test_interrupted_fetch_keeps_original_and_publishes_no_output(self):
        with patch.object(municipal, 'query', side_effect=[municipality_list('Aguada'), {'objectIds':[1,2]}, {'features':[]}]):
            with self.assertRaisesRegex(ValueError, 'Incomplete'):
                municipal.prepare(self.original, self.output, 'Aguada', planning=True)
        self.assertFalse(self.output.exists())

    def test_public_record_fields_and_empty_town(self):
        record = dict(OBJECTID=3, NUMERO_CAT='00100200301', DIRECCION1='Bo. Peña', DIRECCION2='Solar 6', MUNICIPIO='Aguada')
        with patch.object(municipal, 'query', side_effect=[municipality_list('Aguada'), {'objectIds':[3]}, {'features':[{'attributes':record}]}]) as fetch:
            self.assertEqual(list(municipal.planning_records('Aguada')), [
                {'catastro':'00100200301', 'address':'Bo. Peña, Solar 6', 'municipio':'Aguada'}])
            self.assertEqual(set(fetch.call_args.kwargs['outFields'].split(',')), set(record))
        with patch.object(municipal, 'query', side_effect=[municipality_list('Aguada'), {'objectIds':[]}]):
            self.assertEqual(list(municipal.planning_records('Aguada')), [])

    def test_district_codes_and_accented_municipios(self):
        def attributes(number, name):
            return {'attributes': dict(OBJECTID=1, NUMERO_CAT=number, DIRECCION1='Calle Luna', DIRECCION2=None, MUNICIPIO=name)}
        for town, name, number in [('San Juan','SAN JUAN (17)','17-001-002-003-01'), ('Rincón','RINCON','001-002-003-01')]:
            with self.subTest(town=town), patch.object(municipal, 'query', side_effect=[
                    municipality_list('SAN JUAN (17)','SAN JUAN (79)','RINCON'), {'objectIds':[1]},
                    {'features':[attributes(number, name)]}]) as request:
                row, = municipal.planning_records(town)
                self.assertEqual(row, {'catastro':'001-002-003-01', 'address':'Calle Luna', 'municipio':town})
                self.assertIn(name, request.call_args.kwargs['where'])

    def test_import_selected_municipios_together(self):
        import server
        path = self.root / 'several.csv'
        with path.open('w', newline='', encoding='utf-8') as stream:
            writer = csv.writer(stream)
            writer.writerow(['catastro', 'address', 'municipio'])
            writer.writerow(['00100200301', 'Bo. Peña, solar 1', 'San Sebastián'])
            writer.writerow(['00100200303', 'Bo. Peña, solar 1', 'Aguada'])
            writer.writerow(['00100200302', 'Bo. Peña, solar 1', 'Other Town'])
        result = municipal.prepare(self.original, self.output, whole_island=True, csv_paths=[path])
        self.assertEqual(result['municipios'], ['Aguada', 'San Sebastián'])
        self.assertEqual(result['new_parcels_with_wording'], 2)
        with patch.object(server, 'HERE', self.root):
            first, = server.places('Bo Peña, solar 1, San Sebastián')
            second, = server.places('Bo Peña, solar 1, Aguada')
            self.assertEqual((first['parcelNumber'], second['parcelNumber']), ('001-002-003-01', '001-002-003-03'))
