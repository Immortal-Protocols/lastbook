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
    def test_sources_geometry_and_address_join(self):
        with tempfile.TemporaryDirectory() as temp, sqlite3.connect(':memory:') as db:
            folder = Path(temp)
            outer = [[1,1],[3,1],[3,3],[1,3],[1,1]]
            hole = [[1.8,1.8],[2.2,1.8],[2.2,2.2],[1.8,2.2],[1.8,1.8]]
            boundary = {'type':'Polygon','coordinates':[outer]}
            for name, fields in [('barrios',{'GEOID':'7200100000','NAME':'Sol barrio','BASENAME':'Sol'}),
                                 ('zctas',{'ZCTA5':'00700'})]:
                (folder/(name+'.json')).write_text(json.dumps({'features':[{'geometry':boundary,'properties':fields}]}))
            db.executescript("CREATE TABLE municipios(geoid,name);INSERT INTO municipios VALUES('72001','Villa Ejemplo');")
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
            csv.write_text('catastro,dirección física,municipio,owner\n001-002-003-04,"Carr 19, Bo Sol",Villa Ejemplo,omit-me\n')
            stats = build.build(db,folder,folder,[csv])
            self.assertEqual(stats['parcels'],1)
            self.assertEqual(stats['address_sources'],{'CRIM':1,'SIP permit':1})
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
