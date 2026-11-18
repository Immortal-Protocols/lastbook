"""A real source-to-archive place index follows its map through switches and rollback."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'packaging')]
import build_packs
import region_maps
from engine.setup import install
from tools.test_build_places_gpkg import fixture


class Control:
    def check(self): pass


def source(path):
    fixture(path)
    with closing(sqlite3.connect(path)) as db:
        db.execute('ALTER TABLE gis_osm_places_free ADD COLUMN population INTEGER DEFAULT 1000')
        db.execute('ALTER TABLE gis_osm_places_free ADD COLUMN osm_id TEXT')
        db.execute('UPDATE gis_osm_places_free SET osm_id=CAST(fid AS TEXT)')
        for name in ('water_a','natural_a','landuse_a','protected_areas_a','waterways','railways','roads','buildings_a','pois','pois_a','natural'):
            db.execute(f'CREATE TABLE gis_osm_{name}_free(osm_id,geom,fclass,name,ref,population)')
        db.commit()


class RegionPlaces(unittest.TestCase):
    def built(self, root, source_date=None):
        gpkg = root/'source.gpkg'; source(gpkg)
        if source_date:
            (root/'source-receipt.json').write_text(json.dumps({'snapshot_date':source_date,'gpkg_bytes':gpkg.stat().st_size}))
        with patch.object(build_packs,'OUT',root/'out'), patch.object(build_packs,'fetch_region_gpkg',return_value=gpkg):
            build_packs.build_map('au-vic')
        return root/'out/maps/au-vic'

    def test_real_build_scan_zip_unpack_and_map_switch_keep_place_search_together(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); built=self.built(root)
            with patch.object(region_maps.S,'read_terms',return_value=['synthetic-private-canary']):
                failures,_=region_maps.scan(built,'au-vic')
            self.assertEqual(failures,[])
            self.assertEqual(region_maps.contract_files(built),region_maps.ALLOWED)
            with closing(sqlite3.connect(built/'derived/geo/map.sqlite')) as db:
                self.assertEqual(db.execute("SELECT value FROM meta WHERE key='data_as_of'").fetchone()[0],'not recorded')
            archive=root/'region.zip';region_maps.make_zip(built,archive)
            with zipfile.ZipFile(archive) as z:self.assertIsNone(z.testzip())
            staged=root/'unpack'
            install.unpack(archive,staged,10_000_000,Control(),lambda done,total:None,allowed=install.map_member)
            new=staged/'LastbookData'
            current=root/'current';(current/'derived/geo').mkdir(parents=True)
            (current/'derived/geo/places.sqlite').write_bytes(b'old place index')
            (current/'library-data').mkdir();(current/'library-data/catalog.json').write_text('[]')
            install.swap_map(current,new,root/'old')
            self.assertEqual(install.check_map(current)['name'],'au-vic')
            with closing(sqlite3.connect(current/'derived/geo/places.sqlite')) as db:
                self.assertEqual(db.execute("SELECT p.name FROM place_fts f JOIN place p ON p.id=f.rowid WHERE place_fts MATCH '\"Melb\"*' ORDER BY p.rank").fetchall(),[('Melbourne',),('Mélbourne suburb',)])
            self.assertEqual((root/'old/derived/geo/places.sqlite').read_bytes(),b'old place index')
            self.assertEqual((current/'library-data/catalog.json').read_text(),'[]')
            self.assertIn('derived/geo/places.sqlite',install.map_files(current))
            self.assertGreater(install.map_bytes(current),(current/'derived/geo/places.sqlite').stat().st_size)
            refresh=root/'refreshed';(refresh/'derived/geo').mkdir(parents=True)
            (refresh/'derived/geo/places.sqlite').write_bytes(b'base pack places')
            install.copy_map(current,refresh)
            install.check_map(refresh,verify_hashes=True)
            self.assertEqual((refresh/'derived/geo/places.sqlite').read_bytes(),(current/'derived/geo/places.sqlite').read_bytes())

    def test_four_file_legacy_archives_still_work_and_inventory_cannot_hide_an_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);built=self.built(root)
            p=built/'map-set.json';meta=json.loads(p.read_text());del meta['files']['derived/geo/places.sqlite'];meta['bytes']=sum(meta['files'].values());p.write_text(json.dumps(meta))
            with self.assertRaisesRegex(ValueError,'inventory'):region_maps.make_zip(built,root/'bad.zip')
            (built/'derived/geo/places.sqlite').unlink()
            meta.pop('sha256',None);p.write_text(json.dumps(meta))
            self.assertEqual(region_maps.contract_files(built),region_maps.REQUIRED)
            region_maps.make_zip(built,root/'legacy.zip')
            with zipfile.ZipFile(root/'legacy.zip') as z:self.assertEqual(set(z.namelist()),region_maps.REQUIRED)

    def test_out_of_box_places_and_symlinked_payload_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);built=self.built(root);index=built/'derived/geo/places.sqlite'
            with closing(sqlite3.connect(index)) as db:db.execute('UPDATE place SET lon=0');db.commit()
            with self.assertRaisesRegex(ValueError,'outside'):region_maps.check_places(built)
            target=root/'outside.sqlite';index.rename(target);index.symlink_to(target)
            with self.assertRaisesRegex(ValueError,'links'):region_maps.make_zip(built,root/'bad.zip')

    def test_failed_switch_restores_old_places_and_keeps_new_index_staged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);new=self.built(root);cur=root/'current';(cur/'derived/geo').mkdir(parents=True)
            (cur/'derived/geo/places.sqlite').write_bytes(b'old places')
            replace=install.os.replace;failed=False
            def move(src,dest):
                nonlocal failed
                if Path(src)==new/'map-set.json' and not failed:
                    failed=True;raise OSError('simulated disk failure')
                return replace(src,dest)
            with patch.object(install.os,'replace',side_effect=move),self.assertRaises(install.Refused):install.swap_map(cur,new,root/'old')
            self.assertEqual((cur/'derived/geo/places.sqlite').read_bytes(),b'old places')
            self.assertTrue((new/'derived/geo/places.sqlite').is_file())
            install.check_map(new)

    def test_snapshot_date_is_taken_from_a_matching_receipt_and_hash_metadata_must_be_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);built=self.built(root,source_date='2026-11-15')
            with closing(sqlite3.connect(built/'derived/geo/map.sqlite')) as db:
                self.assertEqual(db.execute("SELECT value FROM meta WHERE key='data_as_of'").fetchone()[0],'2026-11-15')
            install.check_map(built,verify_hashes=True)
            p=built/'map-set.json';meta=json.loads(p.read_text());meta['sha256'].pop('derived/geo/places.sqlite');p.write_text(json.dumps(meta))
            with self.assertRaisesRegex(install.Refused,'checksum list'):install.check_map(built)
            (root/'source-receipt.json').write_text(json.dumps({'snapshot_date':'2026-11-15','gpkg_bytes':1}))
            self.assertEqual(build_packs.region_source_date([root/'source.gpkg']),'not recorded')


if __name__=='__main__':unittest.main()
