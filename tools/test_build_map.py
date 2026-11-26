"""Regional CLI clipping must preserve the callable builder used by Spain."""
from contextlib import closing, redirect_stdout
import hashlib
import importlib.util
import io
from pathlib import Path
import sqlite3
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

TOOL = Path(__file__).with_name('build_map.py')


def source(db):
    tables = ('water_a', 'natural_a', 'landuse_a', 'protected_areas_a', 'waterways',
              'railways', 'roads', 'buildings_a', 'places', 'pois', 'pois_a', 'natural')
    for name in tables:
        db.execute(f'CREATE TABLE gis_osm_{name}_free (geom BLOB, fclass TEXT, name TEXT, population INTEGER, ref TEXT)')
    for name, kind, lon, lat in [('Melbourne', 'city', 144.96, -37.81), ('Canberra', 'national_capital', 149.13, -35.28)]:
        point = b'GP\x00\x01' + struct.pack('<iBIdd', 4326, 1, 1, lon, lat)
        db.execute('INSERT INTO gis_osm_places_free VALUES (?, ?, ?, ?, ?)', (point, kind, name, 0, None))
    db.commit()


class MapBuilder(unittest.TestCase):
    def test_import_and_existing_callable_api_keep_unclipped_coverage_and_metadata(self):
        spec = importlib.util.spec_from_file_location('map_fixture', TOOL)
        module = importlib.util.module_from_spec(spec)
        with patch.object(sys, 'argv', ['caller', 'a', 'b', '--unrelated-option']):
            spec.loader.exec_module(module)
        metadata = {'source': 'Example map', 'data_as_of': '2026-11-15', 'bounds': '140,-40,154,-30'}
        with closing(sqlite3.connect(':memory:')) as src, closing(sqlite3.connect(':memory:')) as dst:
            source(src)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(module.build(src, dst, metadata), 2)
            self.assertEqual(dst.execute('SELECT name FROM feat ORDER BY name').fetchall(), [('Canberra',), ('Melbourne',)])
            self.assertEqual(dict(dst.execute('SELECT name,minz FROM feat')), {'Canberra': 6, 'Melbourne': 6})
            self.assertEqual(dict(dst.execute('SELECT key,value FROM meta')), metadata)

    def test_regional_cli_clips_without_changing_source_and_keeps_explicit_snapshot_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); src = root / 'source.gpkg'; dst = root / 'map.sqlite'
            with closing(sqlite3.connect(src)) as db:
                source(db)
            before = hashlib.sha256(src.read_bytes()).digest()
            subprocess.run([sys.executable, '-B', str(TOOL), str(src), str(dst), '144,-39,146,-37',
                            'Example map', '2026-11-15'], check=True, capture_output=True)
            self.assertEqual(hashlib.sha256(src.read_bytes()).digest(), before)
            with closing(sqlite3.connect(dst)) as db:
                self.assertEqual(db.execute('SELECT name FROM feat').fetchall(), [('Melbourne',)])
                self.assertEqual(dict(db.execute('SELECT key,value FROM meta'))['data_as_of'], '2026-11-15')


if __name__ == '__main__':
    unittest.main()
