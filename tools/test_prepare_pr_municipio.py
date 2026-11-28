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
        import server
        gazetteer = patch.object(server, 'PLACEDB', self.root / 'places.sqlite')
        gazetteer.start()
        self.addCleanup(gazetteer.stop)
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

    def test_reordered_fields_ignore_final_periods_and_keep_qualifiers(self):
        import server
        path = self.root / 'punctuation.csv'
        locality = 'BO. PEÑA ., SECT. EL SOL ., SOLAR A-7 ., 00700'
        road = 'CARR 19 KM 4.4, BO. PEÑA ., SECT. EL SOL ., SOLAR A-7 ., 00700'
        relative = 'CARR 19 KM 4.4, FRENTE AL PUENTE, BO. PEÑA ., 00700'
        with path.open('w', encoding='utf-8', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(['catastro', 'address', 'municipio'])
            for base in ('00100200301', '00100200302'):
                for text in (locality, road, relative):
                    writer.writerow([base, text, 'San Sebastián'])
        municipal.prepare(self.original, self.output, 'San Sebastián', csv_paths=[path])
        expected = {'00100200301', '00100200302'}
        queries = [
            'Lote A-7, Sector El Sol, Barrio Pena ., San Sebastián, 00700',
            'Bo. Peña, Lote A-7, Sect. El Sol ., San Sebastián, 00700',
            'Bo. Peña ., Lote A-7, Sect. El Sol, San Sebastián, 00700',
            'PR-19 km 4.400, Lote A-7, Sect. El Sol, Barrio Pena ., San Sebastián, 00700',
            'Sect. El Sol, Bo. Pena, Lote A-7, PR-19 km 4.4, San Sebastián, 00700',
        ]
        with closing(sqlite3.connect(self.output)) as db:
            for query in queries:
                with self.subTest(query=query):
                    self.assertEqual(set(pr_permit.matches(db, query)), expected)
            for original, changed in [('A-7', 'A-8'), ('El Sol', 'El Río'), ('00700', '00701'),
                                      ('San Sebastián', 'Aguada'), ('Peña', 'Otro')]:
                self.assertEqual(pr_permit.matches(db, queries[1].replace(original, changed)), {})
            self.assertEqual(pr_permit.matches(db, queries[3].replace('4.400', '4.04')), {})
            self.assertEqual(pr_permit.matches(db, relative.replace('FRENTE', 'DETRÁS') + ', San Sebastián'), {})
            self.assertEqual(set(pr_permit.matches(db, relative + ', San Sebastián')), expected)
            # The expression lookup uses an index, and keeps old readers' signatures intact.
            plan = db.execute('EXPLAIN QUERY PLAN SELECT base FROM pr_permit_wording WHERE town=? AND '
                + pr_permit.FIELDS_WHERE + ' AND ' + pr_permit.FIELDS_VALUE
                + "=? AND (?='' OR substr(postal,1,length(?))=?) ORDER BY base,source,wording",
                ('san sebastian', pr_permit.field_key(pr_permit.key(queries[3], 'san sebastian')[0]),
                 '00700', '00700', '00700')).fetchall()
            self.assertIn('pr_permit_fields', str(plan))
            for signature, wording in db.execute('SELECT signature,wording FROM pr_permit_wording'):
                self.assertEqual(signature, pr_permit.key(wording, 'san sebastian', source=True, locality=True)[0])
        with patch.object(server, 'HERE', self.root):
            first, = server.places(queries[0], limit=1)
            second, = server.places(queries[0], limit=1, parcel_offset=1)
            self.assertEqual([first['parcelNumber'], second['parcelNumber']],
                             ['001-002-003-01', '001-002-003-02'])
            self.assertEqual((first['parcelCount'], second['parcelCount']), (2, 2))
            self.assertEqual(first['name'], locality)
            self.assertTrue(first['rings'])
        with closing(sqlite3.connect(self.output)) as db, db:
            db.execute('DROP INDEX pr_permit_fields')
            for text in (locality, road, relative):
                self.assertEqual(set(pr_permit.matches(db, text + ', San Sebastián')), expected)

    def test_unrecognized_wording_remains_searchable_without_inventing_fields(self):
        import server
        wording = 'BO. PEÑA | SECTOR EL SOL, SOLAR A-7, 00600, 00700'
        self.assertIsNone(pr_permit.key(wording, 'san sebastian', source=True, locality=True))
        path = self.root / 'unrecognized.csv'
        with path.open('w', encoding='utf-8', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(['catastro', 'address', 'municipio'])
            for base in ('00100200301', '00100200302'):
                writer.writerow([base, wording, 'San Sebastián'])
            for address in ('San Sebastián, PR, 00600', '00600', 'PR, Puerto Rico, 00000'):
                writer.writerow(['00100200303', address, 'Aguada'])
                writer.writerow(['00100200301', address, 'San Sebastián'])
        result = municipal.prepare(self.original, self.output, 'San Sebastián', csv_paths=[path])
        self.assertEqual((result['new_wordings'], result['new_parcels_with_wording']), (2, 2))
        with closing(sqlite3.connect(self.output)) as db:
            self.assertEqual(db.execute('SELECT DISTINCT signature,postal FROM pr_permit_wording').fetchall(), [('verbatim','')])
        with patch.object(server, 'HERE', self.root):
            rows = server.places(wording + ', San Sebastián')
            self.assertEqual([r['parcelNumber'] for r in rows], ['001-002-003-01', '001-002-003-02'])
            self.assertTrue(all(r['name'] == wording and r['rings'] for r in rows))
            self.assertEqual(server.places(wording.replace('A-7','A-8') + ', San Sebastián'), [])
            self.assertEqual(server.places(wording + ', Aguada'), [])

    def test_sparse_aliases_handle_repeated_periods_and_empty_fields_without_changing_evidence(self):
        import server
        path = self.root / 'aliases.csv'
        road = 'BO. PEÑA ........, CARR 19 KM.HM 4.2, SOLAR A-7.., 00700'
        street = '42 CLL INVENTADA, , BO PEÑA, 00700'
        relative = 'CARR 19 KM 4.2,, FRENTE AL PUENTE, BO PEÑA, 00700'
        numeric = 'CARR 19 KM 4,,4, FRENTE AL PUENTE, BO PEÑA, 00700'
        decimal = 'CARR 19 KM 4,4, BO PEÑA, SOLAR B-8, 00700'
        with closing(sqlite3.connect(self.original)) as db, db:
            db.execute("UPDATE pr_parcel SET barrio='Otro' WHERE base='00100200302'")
            signature, postal = pr_permit.key(street, 'aguada', source=True, locality=True)
            db.execute('INSERT INTO pr_permit_wording VALUES(?,?,?,?,?,?)',
                       ('aguada', signature, postal, '00100200303', 'CRIM', street))
        with path.open('w', encoding='utf-8', newline='') as stream:
            writer = csv.writer(stream); writer.writerow(['catastro', 'address', 'municipio'])
            for text in (road, street, relative, numeric, decimal):
                for base in ('00100200301', '00100200302'):
                    writer.writerow([base, text, 'San Sebastián'])
        originals = []
        build_aliases = pr_permit.build_aliases
        def preserve(db):
            originals.extend(db.execute('SELECT * FROM pr_permit_wording'))
            build_aliases(db)
        with patch.object(pr_permit, 'build_aliases', side_effect=preserve):
            municipal.prepare(self.original, self.output, 'San Sebastián', csv_paths=[path])
        expected = {'00100200301', '00100200302'}
        queries = ['PR-19 km 4.2, Lote A-7, Barrio Pena, San Sebastián, 00700',
                   '42 CLL INVENTADA, BO PEÑA, San Sebastián, 00700',
                   relative.replace(',,', ',') + ', San Sebastián']
        with closing(sqlite3.connect(self.output)) as db:
            for query in queries:
                self.assertEqual(set(pr_permit.matches(db, query)), expected)
            self.assertEqual(set(db.execute('SELECT * FROM pr_permit_wording')), set(originals))
            decimal_query = 'Lote B-8, Barrio Pena, PR-19 km 4.4, San Sebastián, 00700'
            self.assertEqual(set(pr_permit.matches(db, decimal_query)), expected)
            self.assertEqual(db.execute('SELECT count(*) FROM pr_permit_alias').fetchone(), (7,))
            self.assertEqual(set(pr_permit.matches(db, queries[1].replace('San Sebastián', 'Aguada'))), {'00100200303'})
            self.assertEqual(pr_permit.matches(db, numeric.replace('4,,4', '4,4') + ', San Sebastián'), {})
            self.assertEqual(pr_permit.matches(db, queries[2].replace('FRENTE', 'DETRÁS')), {})
            self.assertEqual(pr_permit.matches(db, 'BO PEÑA, FRENTE AL PUENTE, CARR 19 KM 4.2, San Sebastián, 00700'), {})
            for before, after in [('A-7', 'A-8'), ('4.2', '4.02'), ('00700', '00701'), ('San Sebastián', 'Aguada')]:
                self.assertEqual(pr_permit.matches(db, queries[0].replace(before, after)), {})
            plan = db.execute("EXPLAIN QUERY PLAN SELECT base FROM pr_permit_alias WHERE town=? AND signature=?",
                              ('san sebastian', pr_permit.alias_key(pr_permit.key(queries[0], 'san sebastian')[0]))).fetchall()
            self.assertIn('PRIMARY KEY', str(plan))
        with patch.object(server, 'HERE', self.root):
            for query in queries:
                first, = server.places(query, limit=1)
                second, = server.places(query, limit=1, parcel_offset=1)
                self.assertEqual([first['parcelNumber'], second['parcelNumber']], ['001-002-003-01', '001-002-003-02'])
                self.assertTrue(first['rings'] and second['rings'])
                self.assertEqual((first['parcelCount'], second['parcelCount']), (2, 2))
                self.assertEqual(server.places(query, parcel_offset=2), [])
        # A canonical older signature also accepts repeated dots in a new query.
        with closing(sqlite3.connect(self.output)) as db, db:
            db.execute('DELETE FROM pr_permit_alias')
            db.execute("UPDATE pr_permit_wording SET signature=? WHERE wording=?",
                       (pr_permit.key(queries[0], 'san sebastian')[0], road))
            self.assertEqual(set(pr_permit.matches(db, queries[0].replace('Barrio Pena', 'Barrio Pena ....'))), expected)
            db.execute('DROP TABLE pr_permit_alias')
            self.assertEqual(set(pr_permit.matches(db, street + ', San Sebastián')), expected)

    def test_literal_numeric_comma_spacing_keeps_existing_queries(self):
        rows = [('42 CLL SOL APT 4,5 FRENTE AL PUENTE',
                 '42 Cll Sol Apt 4, 5 frente al puente'),
                ('BO PEÑA SOLAR 4,5 FRENTE A LA ESCUELA',
                 'Bo Pena Solar 4, 5 frente a la escuela'),
                ('CARR 19 KM 4,4 FRENTE AL PUENTE',
                 'Carr 19 km 4, 4 frente al puente')]
        path = self.root / 'literal-commas.csv'
        with path.open('w', encoding='utf-8', newline='') as stream:
            writer = csv.writer(stream); writer.writerow(['catastro', 'address', 'municipio'])
            for source, _ in rows:
                writer.writerow(['00100200301', source, 'San Sebastián'])
            writer.writerow(['00100200301', 'CARR 3,2 KM 1.0, BO PEÑA', 'San Sebastián'])
        municipal.prepare(self.original, self.output, 'San Sebastián', csv_paths=[path])
        with closing(sqlite3.connect(self.output)) as db:
            for source, query in rows:
                for text in (source, query):
                    self.assertEqual(set(pr_permit.matches(db, text + ', San Sebastián')), {'00100200301'})
            self.assertEqual(pr_permit.matches(db, 'PR-3.2 km 1, Barrio Pena, San Sebastián'), {})

    def test_barrio_only_wording_does_not_override_gazetteer(self):
        import server
        with closing(sqlite3.connect(self.original)) as db, db:
            db.execute("UPDATE municipios SET name='Villa Ejemplo' WHERE name='San Sebastián'")
            db.execute("UPDATE pr_parcel SET barrio='Las Peñas',municipio='Villa Ejemplo' WHERE municipio='San Sebastián'")
        path = self.root / 'barrio.csv'
        wording = 'BO. LAS PEÑAS'
        suffix = wording + ', PR, Puerto Rico, 00000'
        names = ('Las Peñas', 'Camino Viejo', 'Calle Luna', 'El Frente', 'Barrio Verde')
        with path.open('w', newline='', encoding='utf-8') as stream:
            writer = csv.writer(stream)
            writer.writerow(['catastro', 'address', 'municipio'])
            for address in (suffix, 'LAS PEÑAS', *['BO. ' + name.removeprefix('Barrio ').upper() for name in names]):
                writer.writerow(['00100200301', address, 'Villa Ejemplo'])
            for number in ('00100200301', '00100200302'):
                for detail in ('SOLAR 6', 'SECTOR EL CERRO', 'URB. EL SOL', 'COMUNIDAD EL RÍO'):
                    writer.writerow([number, wording + ', ' + detail, 'Villa Ejemplo'])
            writer.writerow(['00100200303', 'LAS PEÑAS', 'Aguada'])
        municipal.prepare(self.original, self.output, whole_island=True, csv_paths=[path])
        places = self.root / 'places.sqlite'
        with closing(sqlite3.connect(places)) as db, db:
            db.executescript('''
                CREATE TABLE place(id INTEGER PRIMARY KEY,name,kind,detail,lat,lon,rank,source);
                CREATE VIRTUAL TABLE place_fts USING fts5(name,detail);
            ''')
            for i, name in enumerate(names, 1):
                db.execute('INSERT INTO place VALUES(?,?,?,?,?,?,?,?)',
                           (i, name, 'Barrio', 'Villa Ejemplo', 1, 2, 1, 'invented fixture'))
                db.execute('INSERT INTO place_fts(rowid,name,detail) VALUES(?,?,?)', (i, name, 'Villa Ejemplo'))
        with patch.object(server, 'HERE', self.root), patch.object(server, 'PLACEDB', places), \
                patch.object(server, 'national_mapdb', return_value=None), \
                patch.object(server, 'home_area', return_value=None), \
                patch.object(server, 'pack_info', return_value=None), \
                patch.object(server, 'water_places', return_value=[]), \
                patch.object(server.assistant, 'LOCAL', None):
            for name in names:
                value = name.removeprefix('Barrio ')
                for query in dict.fromkeys(('Barrio ' + value, 'Bo. ' + value, 'BO. ' + value.upper(), value, name)):
                    with self.subTest(query=query):
                        rows = server.places(query + ', Villa Ejemplo')
                        self.assertEqual([(r['name'], r['kind']) for r in rows], [(name, 'Barrio')])
            # Qualifiers still identify parcels; the barrio alone must not consume their result pages.
            for query in ('Lote 6, Barrio Las Penas', wording + ', SOLAR 6',
                          'Sector El Cerro, Barrio Las Peñas', 'Urb. El Sol, Barrio Las Peñas',
                          'Comunidad El Río, Barrio Las Peñas'):
                with self.subTest(query=query):
                    query += ', Villa Ejemplo'
                    first, = server.places(query, limit=1)
                    second, = server.places(query, limit=1, parcel_offset=1)
                    self.assertEqual([first['parcelNumber'], second['parcelNumber']],
                                     ['001-002-003-01', '001-002-003-02'])
                    self.assertEqual((first['parcelCount'], second['parcelCount']), (2, 2))
                    self.assertEqual(server.places(query, parcel_offset=2), [])
            self.assertEqual(server.places('Barrio Las Peñas, Aguada'), [])
            self.assertEqual(server.places('Lote 99, Barrio Las Peñas, Villa Ejemplo'), [])
            # Dropping Aguada from the FTS query can find Villa Ejemplo's same-named barrio.
            # That row must not hide the recorded Aguada parcel.
            row, = server.places('Las Peñas, Aguada')
            self.assertEqual(row['parcelNumber'], '001-002-003-03')
            with closing(sqlite3.connect(places)) as db, db:
                db.execute("INSERT INTO place VALUES(99,'Las Peñas','town','Aguada County, Texas',1,2,1,'invented fixture')")
                db.execute("INSERT INTO place_fts(rowid,name,detail) VALUES(99,'Las Peñas','Aguada County, Texas')")
            row, = server.places('Las Peñas, Aguada')
            self.assertEqual(row['parcelNumber'], '001-002-003-03')
            # An original suffix paste still finds its parcel when no gazetteer name resolves the full query.
            row, = server.places(suffix + ', Villa Ejemplo')
            self.assertEqual(row['parcelNumber'], '001-002-003-01')
            # A reader without this gazetteer can still use the recorded wording.
            with patch.object(server, 'PLACEDB', self.root / 'missing.sqlite'):
                row, = server.places('Barrio Las Peñas, Villa Ejemplo')
                self.assertEqual(row['parcelNumber'], '001-002-003-01')
            broken = self.root / 'broken.sqlite'
            broken.write_bytes(b'not a SQLite database')
            with patch.object(server, 'PLACEDB', broken):
                first, = server.places('Lote 6, Barrio Las Peñas, Villa Ejemplo', limit=1)
                self.assertEqual((first['parcelNumber'], first['parcelCount']), ('001-002-003-01', 2))

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
