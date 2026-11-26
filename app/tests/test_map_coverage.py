"""Missing regional coverage must not become Southern California coverage."""
from contextlib import ExitStack, closing
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

from app.tests import fixture

os.environ['LASTBOOK_DATA'] = str(fixture.ensure())
os.environ['SURVIVAL_DISABLE_INDEX_WATCH'] = '1'
sys.modules['onnxruntime'] = None
import server


class MapCoverage(unittest.TestCase):
    BOX = [148.7, -35.95, 149.5, -35.1]

    def setUp(self):
        self.stack = ExitStack(); self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.geo = self.root / 'derived/geo'; self.geo.mkdir(parents=True)
        self.detail = self.geo / 'detail-cells.json'
        (self.root / 'map-set.json').write_text(json.dumps({'name': 'au-act', 'files': {}}))
        (self.root / 'pack.json').write_text(json.dumps({'map': 'CA'}))  # Separate map wins.
        (self.geo / 'socal-cells.json').write_text('[123]')
        self.stack.enter_context(patch.object(server, 'HERE', self.root))
        self.stack.enter_context(patch.object(server, 'LIB', self.root / 'library-data'))
        for name in ('WATERDB', 'TERRAINDB', 'CROPDB', 'BLDGDB', 'AERIAL_DETAIL', 'AERIAL_COAST', 'TERRAIN_DETAIL', 'AERIALDB'):
            self.stack.enter_context(patch.object(server, name, self.root / ('missing-' + name)))
        self.stack.enter_context(patch.object(server, '_socal', {'cells': None}))
        self.db = self.stack.enter_context(closing(sqlite3.connect(':memory:')))
        self.db.execute('CREATE TABLE meta(key,value)')
        self.db.execute("INSERT INTO meta VALUES('source','OpenStreetMap contributors')")
        self.stack.enter_context(patch.object(server, 'mapdb', return_value=self.db))
        self.stack.enter_context(patch.object(server, 'pack_info', return_value={'map': 'CA'}))
        self.contents = self.stack.enter_context(patch.object(server, 'map_contents', return_value={
            'layers': ['hospital'], 'bounds': self.BOX, 'detail': True, 'contours': False}))
        self.stack.enter_context(patch.object(server, 'national_status', return_value={'state': 'complete'}))
        self.stack.enter_context(patch.object(server, 'data_version', return_value='fixture'))
        server.detail_cells.cache_clear()
        self.addCleanup(server.detail_cells.cache_clear)

    def write_detail(self):
        self.detail.write_text(json.dumps({'name': 'au-act', 'bbox': self.BOX, 'cells': [456]}))

    def assert_unavailable(self):
        self.assertIsNone(server.detail_bbox())
        self.assertEqual(server.socal_cells(), set())
        info = server.map_info()
        self.assertEqual(info['region'], 'au-act')
        self.assertIsNone(info['bounds']); self.assertFalse(info['detail'])
        self.assertIn('Detail coverage unavailable', info['datasets'][0]['status'])
        self.assertNotIn('whole US', str(info['datasets']))
        # Nearby search can still query actual local points, without deduping
        # against an unavailable coverage mask or dropping the regional DB.
        national = object()
        with patch.object(server, 'national_mapdb', return_value=national):
            self.assertEqual(server._poi_sources(*self.BOX), [(self.db, False), (national, False)])

    def test_missing_regional_file_after_cache_warm_and_restoration(self):
        self.write_detail()
        self.assertEqual(server.detail_bbox(), tuple(self.BOX))
        cells = server.socal_cells()
        self.assertEqual(cells, {456}); self.assertIs(server.socal_cells(), cells)
        self.detail.unlink()
        self.assert_unavailable()
        self.write_detail()
        self.assertEqual(server.detail_bbox(), tuple(self.BOX))
        self.assertEqual(server.socal_cells(), {456})
        self.assertTrue(server.map_info()['detail'])
        self.assertNotIn('unavailable', str(server.map_info()['datasets']))

    def test_unreadable_or_invalid_regional_file_is_not_a_socal_fallback(self):
        for body in ('not json', '{}', '{"bbox":[0,0,"bad",1],"cells":[]}',
                     '{"bbox":[1,0,0,1],"cells":[]}', '{"bbox":[0,0,1,1],"cells":["bad"]}', json.dumps({'bbox':[0,0,10**1000,1],'cells':[]})):
            with self.subTest(body=body):
                self.detail.write_text(body)
                self.assert_unavailable()
        self.detail.unlink(); self.detail.mkdir()  # A real read error, independent of uid/permissions.
        self.assert_unavailable()

    def test_southern_california_keeps_legacy_box_and_mask(self):
        (self.root / 'map-set.json').write_text(json.dumps({'name': 'CA', 'files': {}}))
        self.contents.return_value = {'layers': ['hospital'], 'bounds': list(server.SOCAL_BBOX), 'detail': True, 'contours': False}
        self.assertEqual(server.detail_bbox(), server.SOCAL_BBOX)
        self.assertEqual(server.socal_cells(), {123})
        info = server.map_info()
        self.assertNotIn('region', info)
        self.assertEqual(info['bounds'], list(server.SOCAL_BBOX)); self.assertTrue(info['detail'])
        self.assertNotIn('unavailable', str(info['datasets']))

    def test_pack_regional_identity_also_survives_missing_coverage(self):
        (self.root / 'map-set.json').unlink()
        (self.root / 'pack.json').write_text(json.dumps({'map': 'au-act'}))
        self.assert_unavailable()


if __name__ == '__main__':
    unittest.main()
