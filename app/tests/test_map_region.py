"""A map set may say how it wants heights shown, which country it is and what to credit (map-set.json); a US one says nothing."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import server


class MapSetMetaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.lib = Path(self.temp.name)
        patcher = patch.object(server, 'HERE', self.lib)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.temp.cleanup)

    def write(self, data):
        (self.lib / 'map-set.json').write_text(data if isinstance(data, str) else json.dumps(data), encoding='utf-8')

    def test_no_map_set_says_nothing(self):
        self.assertEqual(server.map_set_meta(), {})

    def test_us_map_set_keeps_feet_and_us_wording(self):
        self.write({'name': 'CA', 'files': {}})
        self.assertEqual(server.map_set_meta(), {'units': 'imperial', 'country': None, 'credit': None, 'as_of': None})

    def test_uk_map_set(self):
        credit = 'Contains OS data © Crown copyright and database right 2026'
        self.write({'name': 'GB-SE', 'files': {}, 'units': 'metric', 'country': 'GB', 'credit': f'  {credit}  ', 'as_of': ' 17 Nov 2026 '})
        self.assertEqual(server.map_set_meta(), {'units': 'metric', 'country': 'GB', 'credit': credit, 'as_of': '17 Nov 2026'})

    def test_bad_values_are_ignored(self):
        self.write({'name': 'X', 'files': {}, 'units': 'furlongs', 'country': 'gb', 'credit': 7})
        self.assertEqual(server.map_set_meta(), {'units': 'imperial', 'country': None, 'credit': None, 'as_of': None})
        self.write({'name': 'X', 'files': {}, 'country': 'GBR', 'credit': '   '})
        self.assertEqual(server.map_set_meta(), {'units': 'imperial', 'country': None, 'credit': None, 'as_of': None})

    def test_credit_is_capped(self):
        self.write({'name': 'X', 'files': {}, 'credit': 'a' * 900})
        self.assertEqual(len(server.map_set_meta()['credit']), 400)

    def test_unreadable_map_set(self):
        self.write('not json')
        self.assertEqual(server.map_set_meta(), {})
        self.write('[1, 2]')
        self.assertEqual(server.map_set_meta(), {})

    def test_map_contents_carries_it(self):
        self.write({'name': 'GB-SE', 'files': {}, 'units': 'metric', 'country': 'GB'})
        server.map_contents.cache_clear()
        self.addCleanup(server.map_contents.cache_clear)
        contents = server.map_contents()
        self.assertEqual((contents['units'], contents['country']), ('metric', 'GB'))


if __name__ == '__main__':
    unittest.main()
