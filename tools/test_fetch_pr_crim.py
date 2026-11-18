"""Check that public lookup checkpoints preserve wording and survive interrupted runs."""
import csv
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from tools import fetch_pr_crim as fetch
from tools.pr_areas import REGIONS


class PublicPrefixResults(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        self.roster = {'00100200301', '00100200302', '00100400303'}
        fetch.checkpoint(self.db, 'Villa Ejemplo', self.roster)

    @staticmethod
    def row(base='001-002-003-01', address='Bo. Peña , SOLAR A-7, PR, Puerto Rico, 00000', town='Villa Ejemplo'):
        return {'Parcela':base, 'Dirección física':address, 'Municipio':town}

    def test_original_wording_and_completed_grids(self):
        rows = [self.row(), self.row('001-002-003-02', ''), self.row('001-002-003-99')]
        fetch.save_prefix(self.db, '001-002', rows, 3, self.roster)
        fetch.save_prefix(self.db, '001-002', rows, 3, self.roster)
        summary = fetch.write_results(self.db, self.directory, 'Villa Ejemplo', self.roster, {'00100200301'})
        with (self.directory / 'addresses.csv').open(newline='', encoding='utf-8') as stream:
            self.assertEqual(list(csv.DictReader(stream)), [dict(catastro='00100200301', address=rows[0]['Dirección física'], municipio='Villa Ejemplo')])
        self.assertEqual(summary['returned_parcels'], 2)
        self.assertEqual(summary['empty_address_parcels'], 1)
        self.assertEqual(summary['missing_parcels'], 0)
        self.assertEqual(summary['unqueried_parcels'], 1)
        self.assertEqual(summary['newly_collected_parcels'], 0)
        fetch.checkpoint(self.db, 'Villa Ejemplo', self.roster)
        self.db.execute("UPDATE meta SET value='another source' WHERE key='source'")
        self.db.commit()
        with self.assertRaisesRegex(ValueError, 'different'):
            fetch.checkpoint(self.db, 'Otro Pueblo', self.roster)

    def test_failed_prefix_is_never_marked_complete(self):
        for rows, count in [([self.row()], 2), ([self.row('001-004-003-03')], 1), ([{'Parcela':'001-002-003-01'}], 1)]:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                fetch.save_prefix(self.db, '001-002', rows, count, self.roster)
        self.assertEqual(self.db.execute('SELECT count(*) FROM prefix').fetchone(), (0,))
        self.assertEqual(self.db.execute('SELECT count(*) FROM record').fetchone(), (0,))

    def test_different_municipio_and_multiple_address_versions(self):
        rows = [self.row(), self.row(address='BO PEÑA, SOLAR B, PR, 00700'), self.row('001-002-003-02', town='Otro Pueblo')]
        fetch.save_prefix(self.db, '001-002', rows, 3, self.roster)
        fetch.save_prefix(self.db, '001-004', [], 0, self.roster)
        summary = fetch.write_results(self.db, self.directory, 'Villa Ejemplo', self.roster, set())
        self.assertEqual((summary['csv_parcels'], summary['municipio_matched_parcels'], summary['csv_wordings']), (2, 1, 3))
        with (self.directory / 'addresses.csv').open(newline='', encoding='utf-8') as stream:
            saved = list(csv.DictReader(stream))
        self.assertEqual(saved[-1]['municipio'], 'Otro Pueblo')
        self.assertEqual((summary['missing_parcels'], summary['unqueried_parcels']), (1, 0))

    def test_expanding_selection_rechecks_a_shared_grid_and_preserves_cached_records(self):
        fetch.save_prefix(self.db, '001-002', [self.row()], 1, self.roster)
        expanded = self.roster | {'00100200303'}
        fetch.checkpoint(self.db, ['Villa Ejemplo', 'Otro Pueblo'], expanded)
        batches = fetch.grid_rosters(base for base, in self.db.execute('SELECT base FROM scope'))
        self.assertNotIn('001-002', fetch.completed_prefixes(self.db, batches))
        summary = fetch.write_results(self.db, self.directory, 'Villa Ejemplo', expanded, set())
        self.assertEqual((summary['returned_parcels'], summary['missing_parcels'], summary['unqueried_parcels']), (1, 0, 3))
        rows = [self.row(), self.row('001-002-003-03', town='Otro Pueblo')]
        fetch.save_prefix(self.db, '001-002', rows, 2, batches['001-002'])
        mapped = {'00100200301': {'villa ejemplo'}, '00100200303': {'otro pueblo'}}
        summary = fetch.write_results(self.db, self.directory, ['Villa Ejemplo', 'Otro Pueblo'], mapped, set())
        self.assertTrue(summary['complete'])
        self.assertEqual((summary['returned_parcels'], summary['municipio_matched_parcels']), (2, 2))
        summary = fetch.write_results(self.db, self.directory, 'Villa Ejemplo', {'00100200301'}, set())
        self.assertEqual(summary['csv_parcels'], 1)
        self.assertTrue(summary['complete'])
        self.assertEqual(self.db.execute('SELECT count(*) FROM record').fetchone(), (2,))

    def test_single_municipio_checkpoint_upgrade(self):
        with sqlite3.connect(':memory:') as old:
            old.executescript('''
                CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT);
                CREATE TABLE prefix(value TEXT PRIMARY KEY,displayed INTEGER,completed TEXT);
                CREATE TABLE record(prefix TEXT,catastro TEXT,address TEXT,municipio TEXT,
                    PRIMARY KEY(prefix,catastro,address,municipio)) WITHOUT ROWID;
                INSERT INTO prefix VALUES ('001-002',1,'earlier');
                INSERT INTO record VALUES ('001-002','00100200301','BO PEÑA, SOLAR 6','Villa Ejemplo');
            ''')
            identity = json.dumps([fetch.VIEWER, 'Villa Ejemplo', sorted(self.roster)], ensure_ascii=False, separators=(',', ':'))
            old.execute('INSERT INTO meta VALUES (?,?)', ('roster', hashlib.sha256(identity.encode()).hexdigest()))
            old.commit()
            fetch.checkpoint(old, ['Villa Ejemplo', 'Otro Pueblo'], self.roster | {'00100200303'}, ('Villa Ejemplo', self.roster))
            self.assertEqual(old.execute('SELECT address FROM record').fetchone(), ('BO PEÑA, SOLAR 6',))
            self.assertEqual(old.execute('SELECT count(*) FROM scope').fetchone(), (4,))
            batches = fetch.grid_rosters(base for base, in old.execute('SELECT base FROM scope'))
            self.assertNotIn('001-002', fetch.completed_prefixes(old, batches))


class AreaSelection(unittest.TestCase):
    def test_plans_custom_regions_and_all_municipios(self):
        with tempfile.TemporaryDirectory() as temp:
            index = Path(temp) / 'PR.sqlite'
            names = sorted({name for group in REGIONS.values() for name in group.split('|')})
            self.assertEqual(len(names), 78)
            with sqlite3.connect(index) as db:
                db.executescript('''CREATE TABLE municipios(name); CREATE TABLE pr_parcel(base,municipio);
                                   CREATE TABLE pr_permit_wording(base,town,source);''')
                db.executemany('INSERT INTO municipios VALUES (?)', ((name,) for name in names))
                db.executemany('INSERT INTO pr_parcel VALUES (?,?)', ((f'001002{i:05d}', name) for i, name in enumerate(names)))
            output = Path(temp) / 'not-created'
            plan = fetch.fetch(index, output, ['Yabucoa', 'YABUCOA', 'Las Piedras'], plan=True)
            self.assertEqual((len(plan['municipios']), plan['roster_parcels']), (2, 2))
            region = fetch.fetch(index, None, ['San Juan'], regions=['metro', 'east'], plan=True)
            self.assertEqual(len(region['municipios']), 23)
            self.assertIn('Vieques', region['municipios'])
            all_towns = fetch.fetch(index, None, whole_island=True, plan=True)
            self.assertEqual((len(all_towns['municipios']), all_towns['roster_parcels']), (78, 78))
            self.assertFalse(output.exists())
            with self.assertRaisesRegex(ValueError, 'absent'):
                fetch.fetch(index, None, ['Unknown'], plan=True)
