import hashlib
import importlib.util
from pathlib import Path
import socket
import sqlite3
import struct
import tempfile
import unittest
from contextlib import closing
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('builder', Path(__file__).with_name('build_places_gpkg.py'))
b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)


def geometry(lon, lat, srs=4326, header='<', wkb='<', envelope=False):
    flags = int(header == '<') | (2 if envelope else 0)
    env = struct.pack(header + 'dddd', lon, lon, lat, lat) if envelope else b''
    return b'GP\x00' + bytes([flags]) + struct.pack(header + 'i', srs) + env + bytes([int(wkb == '<')]) + struct.pack(wkb + 'Idd', 1, lon, lat)


def fixture(path, projected=False):
    with closing(sqlite3.connect(path)) as db:
        db.executescript('''CREATE TABLE gpkg_geometry_columns(table_name,column_name,geometry_type_name,srs_id);
            CREATE TABLE gpkg_spatial_ref_sys(srs_id,organization,organization_coordsys_id,definition);
            CREATE TABLE gis_osm_places_free(fid INTEGER PRIMARY KEY,name,fclass,geom);''')
        db.execute('INSERT INTO gpkg_geometry_columns VALUES(?,?,?,?)', ('gis_osm_places_free', 'geom', 'POINT', 4326))
        db.execute('INSERT INTO gpkg_spatial_ref_sys VALUES(?,?,?,?)', (4326, 'EPSG', 3857 if projected else 4326, ''))
        rows = [('Melbourne', 'city', geometry(144.96, -37.81)),
                ('Example Capital', 'national_capital', geometry(145.05, -37.75)),
                ('Mélbourne suburb', 'suburb', geometry(145, -37.8, header='>', envelope=True)),
                ('悉尼', 'town', geometry(145.1, -37.7, wkb='>')),
                ('Far away', 'town', geometry(130, -20)),
                ('', 'village', geometry(145, -37.8)),
                ('Not a settlement', 'country', geometry(145, -37.8))]
        db.executemany('INSERT INTO gis_osm_places_free(name,fclass,geom) VALUES(?,?,?)', rows); db.commit()


class Places(unittest.TestCase):
    def test_offline_clip_rank_prefix_unicode_and_overlapping_inputs(self):
        with tempfile.TemporaryDirectory() as d, patch.object(socket, 'socket', side_effect=AssertionError('network')):
            src, out = Path(d) / 'source.gpkg', Path(d) / 'places.sqlite'; fixture(src)
            before = hashlib.sha256(src.read_bytes()).digest()
            self.assertEqual(b.build([src, src], out, 'Public region', (144, -38, 146, -37)), 4)
            self.assertEqual(hashlib.sha256(src.read_bytes()).digest(), before)
            with closing(sqlite3.connect(out)) as db:
                def find(q):
                    return db.execute('SELECT p.name,p.rank FROM place_fts f JOIN place p ON p.id=f.rowid '
                                      'WHERE place_fts MATCH ? ORDER BY p.rank,bm25(place_fts)', (q,)).fetchall()
                self.assertEqual(find('"Melb"*'), [('Melbourne', 1), ('Mélbourne suburb', 5)])
                self.assertEqual(find('"悉尼"*'), [('悉尼', 2)])
                self.assertEqual(find('"Example"*'), [('Example Capital', 1)])
                self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
                self.assertNotIn('source.gpkg', str(db.execute('SELECT * FROM place').fetchall()))

    def test_unsupported_crs_and_empty_coverage_leave_no_output(self):
        with tempfile.TemporaryDirectory() as d:
            src, out = Path(d) / 'source.gpkg', Path(d) / 'places.sqlite'; fixture(src, projected=True)
            with self.assertRaisesRegex(ValueError, 'Unsupported CRS'):
                b.build([src], out, 'Region')
            self.assertFalse(out.exists()); self.assertEqual(list(Path(d).glob('.places-*')), [])
            with closing(sqlite3.connect(src)) as db:
                db.execute('UPDATE gpkg_spatial_ref_sys SET organization_coordsys_id=4326'); db.commit()
            with self.assertRaisesRegex(ValueError, 'No named places'):
                b.build([src], out, 'Region', (1, 1, 2, 2))
            self.assertFalse(out.exists())

    def test_bad_points_and_boxes_are_refused(self):
        for blob in [b'bad', geometry(181, 0), geometry(0, float('nan')), geometry(0, 0, srs=3857), geometry(0, 0)[:-1]]:
            with self.assertRaises(ValueError): b.point(blob, 4326)
        for value in ['1,2,3', '1,2,0,3', '0,-91,1,1', '0,0,nan,1']:
            with self.assertRaises(b.argparse.ArgumentTypeError): b.box(value)

    def test_existing_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / 'places.sqlite'; out.write_bytes(b'keep')
            with self.assertRaisesRegex(ValueError, 'already exists'):
                b.build([], out, 'Region')
            self.assertEqual(out.read_bytes(), b'keep')

    def test_first_completed_overlapping_build_keeps_its_output(self):
        with tempfile.TemporaryDirectory() as d:
            src, out = Path(d) / 'source.gpkg', Path(d) / 'places.sqlite'; fixture(src)
            rows = b.place_rows
            winner = []
            def overlapping(source, region, bbox):
                # The outer build already passed its output check and owns a
                # temporary database. Complete a second build before it places.
                if region == 'Losing region':
                    with patch.object(b, 'place_rows', rows):
                        self.assertEqual(b.build([src], out, 'Winning region'), 5)
                    winner.append(out.read_bytes())
                yield from rows(source, region, bbox)
            with patch.object(b, 'place_rows', overlapping), self.assertRaisesRegex(ValueError, 'already exists'):
                b.build([src], out, 'Losing region')
            self.assertEqual(out.read_bytes(), winner[0])
            with closing(sqlite3.connect(out)) as db:
                self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
                self.assertEqual(db.execute('SELECT DISTINCT detail FROM place').fetchall(), [('Winning region (OpenStreetMap)',)])
            self.assertEqual(out.stat().st_nlink, 1)
            self.assertEqual(list(Path(d).glob('.places-*')), [])

    def test_dangling_output_link_is_preserved_even_if_it_appears_at_final_placement(self):
        with tempfile.TemporaryDirectory() as d:
            src, out = Path(d) / 'source.gpkg', Path(d) / 'places.sqlite'; fixture(src)
            real_link = b.os.link
            def late_link(staged, target):
                out.symlink_to('missing.sqlite')
                return real_link(staged, target)
            with patch.object(b.os, 'link', late_link), self.assertRaisesRegex(ValueError, 'already exists'):
                b.build([src], out, 'Region')
            self.assertTrue(out.is_symlink()); self.assertEqual(out.readlink(), Path('missing.sqlite'))
            self.assertFalse((out.parent / 'missing.sqlite').exists())
            self.assertEqual(list(Path(d).glob('.places-*')), [])
            # An already dangling link is refused before any source is opened.
            with self.assertRaisesRegex(ValueError, 'already exists'):
                b.build([], out, 'Region')
            self.assertTrue(out.is_symlink()); self.assertEqual(list(Path(d).glob('.places-*')), [])


if __name__ == '__main__': unittest.main()
