"""The builder keeps parcel identity, source fields and holes without requiring a network."""
import gzip
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from engine import pr_parcels, pr_rural
from tools import build_pr_parcels as build


class ParcelBuild(unittest.TestCase):
    def test_arpe_municipio_prefix(self):
        with sqlite3.connect(':memory:') as db:
            db.executescript("""
                CREATE TABLE pr_parcel(base,municipio);
                CREATE TABLE pr_account(number PRIMARY KEY);
                CREATE TABLE pr_parcel_address(base,route,meters,lot,sector,interior,access,postal,landmark,source);
                INSERT INTO pr_parcel VALUES ('00100200304','San Sebastián'), ('00100200305','Aguada'),
                    ('00100200306','San Sebastián'), ('00100200306','Aguada');
            """)
            def record(number, town='SAN SEBASTIAN'):
                return {'catastro': number, 'municipio': town, 'address': 'CARR 19 KM 4.4 SOLAR A-7'}

            build.labels(db, [
                record('30-001-002-003-04-007'),                  # all three municipio checks agree
                record('26-001-002-003-04-008'),                  # prefix disagrees with permit
                record('26-001-002-003-04-009', 'Aguada'),        # disagrees with the land boundary
                record('17-001-002-003-04-010'),                  # unmapped code
                record('30-001-002-003-04-011', ''),              # missing municipio
                record('30-001-002-003-04-012', 'San Sebastián|Aguada'),
                record('30-001-002-003-04-013|26-001-002-003-05-000'),
                record('30-001-002-003-06-014'),                  # land number spans municipios
            ], 'ARPE permit')
            self.assertEqual(db.execute('SELECT * FROM pr_account').fetchall(), [('00100200304007',)])
            self.assertEqual(db.execute('SELECT base,route,meters,lot,source FROM pr_parcel_address').fetchall(),
                             [('00100200304', 19, 4400, 'a7', 'ARPE permit')])

    def test_sources_geometry_and_address_join(self):
        with tempfile.TemporaryDirectory() as temp, sqlite3.connect(':memory:') as db:
            folder = Path(temp)
            outer = [[1,1],[3,1],[3,3],[1,3],[1,1]]
            hole = [[1.8,1.8],[2.2,1.8],[2.2,2.2],[1.8,2.2],[1.8,1.8]]
            boundary = {'type':'Polygon','coordinates':[outer]}
            for name, fields in [('barrios',{'GEOID':'7200100000','NAME':'Sol barrio','BASENAME':'Sol'}),
                                 ('zctas',{'ZCTA5':'00700'})]:
                (folder/(name+'.json')).write_text(json.dumps({'features':[{'geometry':boundary,'properties':fields}]}))
            db.executescript("""CREATE TABLE municipios(geoid,name);
                INSERT INTO municipios VALUES ('72001','Villa Ejemplo'), ('72003','Otro Pueblo');""")
            parcel = {'id':1,'catastro':'001-002-003-04','geometry':{'type':'Polygon','coordinates':[outer,hole]}}
            label = {'id':5,'catastro':'001-002-003-04-007','municipio':'Villa Ejemplo',
                     'address':'BO SOL, SOLAR A-7, CARR 19 KM.HM 4.4 INT 7, SECTOR JARDÍN'}
            wrong = dict(label,municipio='Elsewhere',address='CARR 22 KM 1')
            manifest = {}
            for name, rows in [('parcels',[parcel]),('sip',[label,dict(label,id=6),wrong]),('arpe',[])]:
                sub=folder/name; sub.mkdir()
                with gzip.open(sub/'page.gz','wt') as stream:
                    for row in rows: stream.write(json.dumps(row)+'\n')
                manifest[name]={'folder':name,'source':name,'records':len(rows),'pages':['page.gz']}
            (folder/'sources.json').write_text(json.dumps(manifest))
            csv=folder/'extra.csv'
            csv.write_text('Número de catastro,Dirección física,municipio,owner\n001-002-003-04,"Carr 19, Bo Sol",Villa Ejemplo,omit-me\n')
            stats = build.build(db,folder,folder,[csv])
            self.assertEqual(stats['parcels'],1)
            self.assertEqual(stats['address_sources'],{'CRIM':1,'SIP permit':1})
            self.assertEqual(stats['address_coverage_by_municipio'], {
                'Villa Ejemplo': {'addressed_parcels': 1, 'permit_parcels': 1, 'crim_address_parcels': 1},
                'Otro Pueblo': {'addressed_parcels': 0, 'permit_parcels': 0, 'crim_address_parcels': 0},
            })
            item,=pr_parcels.by_number(db,'00100200304007')
            self.assertEqual(len(item['rings']),2)
            self.assertFalse(1.8 < item['lon'] < 2.2 and 1.8 < item['lat'] < 2.2)
            q=pr_rural.parse('sector Jardin, lote A-7, Int 7, PR-19 km 4.4, Bo Sol')
            hit,=pr_parcels.candidates(db,q)
            self.assertEqual(hit['parcelNumber'],'001-002-003-04')
            self.assertIn('SIP permit',hit['detail'])
            self.assertNotIn('omit-me',''.join(db.iterdump()))
            self.assertFalse(pr_parcels.candidates(db,pr_rural.parse('PR-22 km 1')))
            self.assertIsNone(build.address_fields('CARR 19/20 KM 1'))
            self.assertIsNone(build.address_fields('CARR 19 KM 4.4-5'))
