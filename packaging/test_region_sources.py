"""From a checkout: python3 -B packaging/test_region_sources.py"""
import sqlite3
import struct
import subprocess
import sys
import tempfile
import unittest
import zipfile
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import build_packs


class RegionSourceTests(unittest.TestCase):
    def test_multiple_provinces_use_their_own_cached_extract(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(build_packs, 'OUT', Path(tmp) / 'out'):
            cached = {}
            for url in build_packs.REGION_SPECS.REGIONS['ca-maritimes']['extracts']:
                archive = Path(tmp) / Path(url).name
                region = archive.name.removesuffix('-latest-free.gpkg.zip')
                with zipfile.ZipFile(archive, 'w') as z:
                    z.writestr('README', 'test fixture')
                    z.writestr('map.gpkg', region)
                local = archive.as_uri()
                cached[region] = local
                self.assertEqual(build_packs.fetch_region_gpkg(local).read_text(), region)
                archive.unlink()
            for region, local in cached.items():
                self.assertEqual(build_packs.fetch_region_gpkg(local).read_text(), region)

    def test_join_preserves_distinct_places_in_overlapping_extracts(self):
        tables = ('water_a', 'natural_a', 'landuse_a', 'protected_areas_a', 'waterways', 'railways',
                  'roads', 'buildings_a', 'places', 'pois', 'pois_a', 'natural')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inputs = [root / 'west.gpkg', root / 'east.gpkg']
            # ID 1 occurs in both extracts. ID 2 is a separate place at the same point.
            for source, points in zip(inputs, [[('1', -64.)], [('1', -64.), ('2', -64.), ('3', -63.)]]):
                with closing(sqlite3.connect(source)) as db:
                    for name in tables:
                        db.execute(f'CREATE TABLE gis_osm_{name}_free(osm_id,geom,fclass,name,ref,population)')
                    for osm_id, lon in points:
                        point = b'GP' + struct.pack('<BBIBIdd', 0, 1, 4326, 1, 1, lon, 46.)
                        db.execute("INSERT INTO gis_osm_pois_free VALUES(?,?,'pharmacy','Example',NULL,NULL)", (osm_id, point))
                    db.commit()
            dest = root / 'map.sqlite'
            subprocess.run([sys.executable, '-B', str(build_packs.PROJECT / 'tools/build_map.py'),
                            str(inputs[0]), str(dest), '-65,45,-62,47', 'test fixture', str(inputs[1])],
                           check=True, capture_output=True)
            with closing(sqlite3.connect(dest)) as db:
                self.assertEqual(db.execute('SELECT lon FROM poi ORDER BY lon').fetchall(), [(-64.,), (-64.,), (-63.,)])


if __name__ == '__main__':
    unittest.main()
