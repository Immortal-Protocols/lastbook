"""Exercise the public place finder with invented parcel identifiers, boundaries and directions."""
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from engine import pr_rural, pr_rural_model


class ParcelSearch(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        path = self.root / 'derived/geo/addresses/PR.sqlite'
        path.parent.mkdir(parents=True)
        db = sqlite3.connect(path)
        self.addCleanup(db.close)
        db.executescript("""
            CREATE TABLE pr_parcel(id INTEGER PRIMARY KEY,base,barrio,municipio,zip,lat,lon,area,rings);
            CREATE TABLE pr_account(number TEXT PRIMARY KEY);
            CREATE TABLE pr_parcel_address(base,route,meters,lot,sector,interior,access,postal,landmark,source);
        """)
        for i in range(1, 25):
            lon = 2 + i / 1000
            ring = [[[lon,1],[lon,1.001],[lon+.001,1.001],[lon,1]]]
            key = f'001002003{i:02d}'
            db.execute('INSERT INTO pr_parcel VALUES(?,?,?,?,?,?,?,?,?)',
                       (i,key,'Las Peñas','Villa Ejemplo','00700',1.0005,lon+.0001,1,json.dumps(ring)))
            db.execute('INSERT INTO pr_parcel_address VALUES(?,?,?,?,?,?,?,?,?,?)',
                       (key,19,None if i == 24 else 4400,str(i),'sol' if i < 4 else '',i in (3,4),
                        '7' if i == 3 else '','', '', 'CRIM'))
        db.execute("INSERT INTO pr_account VALUES('00100200303007')")
        db.execute("INSERT INTO pr_parcel_address VALUES('00100200303',19,4400,'8','luna',0,'','','','SIP permit')")
        db.commit()

    def search(self, query, offset=0, model=None):
        import server
        with patch.object(server,'HERE',self.root), patch.object(server.assistant,'LOCAL',model):
            return server.places(query, parcel_offset=offset)

    def test_exact_identifiers_and_leading_zeros(self):
        for q in ['00100200303','001-002-003-03','Número de catastro: 001-002-003-03-00','00100200303000']:
            with self.subTest(q=q):
                hit, = self.search(q)
                self.assertEqual((hit['kind'],hit['parcelNumber']),('CRIM parcel','001-002-003-03'))
                self.assertEqual(len(hit['rings'][0]),4)
        self.assertTrue(self.search('CRIM 001-002-003-03-007'))
        self.assertEqual(self.search('CRIM 001-002-003-03-006'),[])
        self.assertEqual(self.search('099-099-099-99'),[])

    def test_candidate_pages_and_incomplete_kilometer(self):
        query = 'PR-19 km 4.4, Bo. Las Peñas, Villa Ejemplo'
        first, second = self.search(query), self.search(query,20)
        self.assertEqual((len(first),len(second)),(20,4))
        self.assertEqual(len({r['parcelNumber'] for r in first+second}),24)
        self.assertTrue(all(r['kind']=='Possible parcel' and r['parcelCount']==24 and r['rings'] for r in first+second))
        self.assertIn('km unrecorded',second[-1]['detail'])
        self.assertEqual(self.search(query,100),[])
        self.assertEqual(self.search(query.replace('Las Peñas','Otro')),[])
        self.assertEqual(self.search(query + ', 00888'),[])

    def test_qualifiers_must_match_one_source_record(self):
        query = 'Int. 7, Lote 3, Sector Sol, PR-19 km 4.4, Bo Las Penas, Villa Ejemplo'
        for q in (query, query.replace('Lote 3','solar tres'), 'Sector Sol, Solar 3, Bo Las Peñas, PR-19 Int. 7'):
            hit, = self.search(q)
            self.assertEqual(hit['parcelNumber'],'001-002-003-03')
            self.assertEqual(hit['kind'],'Possible parcel')
            for part in ('lot 3','interior 7','sector sol'):
                self.assertIn(part,hit['detail'])
        for q in (query.replace('Sol,','Luna,'),query.replace('Int. 7','Int. 8'),query.replace('Lote 3','Lot 99')):
            self.assertEqual(self.search(q),[])

    @unittest.skipUnless(os.environ.get('LASTBOOK_TEST_PARCEL_MODEL') == '1', 'opt-in test with the pinned local Gemma')
    def test_real_gemma_parcel_directions(self):
        import llm_local
        cases = [
            ('Sector Sol, solar tres, interior 7, por la diecinueve, kilómetro cuatro punto cuatro, barrio Las Peñas', '03', True),
            ('Bo Las Peñas, por la diecinueve, kilómetro cuatro punto cuatro, lote 2, sector Sol', '02', True),
            ('Carr. 19 km 4.4, solar 3, sector Sol, interior 7, Bo Las Peñas', '03', False),
            ('Lot 3, Sector Sol, Interior 8, PR-19 km 4.4, Bo Las Peñas', None, False),
            ('Por la diecinueve, sector Sol, interior 7, solar tres, barrio Las Peñas', '03', True),
        ]
        model = llm_local.LOCAL
        self.addCleanup(model.stop, 'parcel test finished')
        model.discover()
        self.assertIsNone(model.ensure_running())
        for query, suffix, interpreted in cases:
            with self.subTest(query=query):
                rows = self.search(query, model=model)
                expected = ['001-002-003-' + suffix] if suffix else []
                self.assertEqual([row['parcelNumber'] for row in rows], expected)
                self.assertEqual(any(row.get('interpreted') for row in rows), interpreted)

    def test_gemma_preserves_qualifiers_and_never_supplies_geometry(self):
        q = 'Sector Sol, solar tres, interior 7, por la diecinueve, kilómetro cuatro punto cuatro, barrio Las Peñas'
        answer = [19,'4.4','Las Peñas','',True,'Sol','','3','7']
        model = Mock()
        model.gen_lock.locked.return_value = False
        model.ensure_running.return_value = None
        model.generate.side_effect = lambda s,n,c,emit,**kw: emit(json.dumps(answer))
        hit, = self.search(q,model=model)
        self.assertEqual(hit['parcelNumber'],'001-002-003-03')
        self.assertIn('interior 7',hit['interpreted'])
        self.assertIn('lot 3',hit['interpreted'])
        without_km = q.replace('kilómetro cuatro punto cuatro, ', '')
        answer[1] = None
        hit, = self.search(without_km, model=model)
        self.assertEqual(hit['parcelNumber'], '001-002-003-03')
        self.assertIsNone(pr_rural_model.validated(q, pr_rural_model.fields(answer), None))
        answer[1] = '4.4'
        self.assertEqual(self.search(q + ' ' * 400 + 'lote 8', model=model), [])
        for index, wrong in [(4,False),(5,'Luna'),(7,''),(7,'8'),(8,'')]:
            saved, answer[index] = answer[index], wrong
            self.assertIsNone(pr_rural_model.validated(q,pr_rural_model.fields(answer),pr_rural.parse(q)))
            answer[index] = saved
