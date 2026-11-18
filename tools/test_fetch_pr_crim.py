"""Check that public lookup checkpoints preserve wording and survive interrupted runs."""
import csv
from pathlib import Path
import sqlite3
import tempfile
import unittest

from tools import fetch_pr_crim as fetch


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
