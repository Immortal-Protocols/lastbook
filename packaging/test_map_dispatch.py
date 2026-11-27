"""Offline map-name dispatch checks, without network access, a sample library or a build.

  python3 -B -m unittest discover -s packaging -p test_map_dispatch.py -v

A country code (eu-<iso>) must go through the country builder, and a sovereign-state capital code
(ve-car) must go through the region builder. These checks mock the builders so they verify the route
build_map takes, not the files each route would produce.
"""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


spec = importlib.util.spec_from_file_location('build_packs', Path(__file__).with_name('build_packs.py'))
build_packs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_packs)


class MapDispatch(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        out = patch.object(build_packs, 'OUT', self.root / 'out')
        out.start()
        self.addCleanup(out.stop)

    def test_european_country_code_uses_country_builder(self):
        with patch.object(build_packs, 'state_set') as state_set, \
             patch.object(build_packs, 'region_set') as region_set, \
             patch.object(build_packs, 'geo_source', return_value=self.root / 'src'):
            build_packs.build_map('eu-at')
        region_set.assert_not_called()
        state_set.assert_called_once()
        self.assertEqual(state_set.call_args.args[1], build_packs.OUT / 'maps' / 'eu-at')
        self.assertEqual(state_set.call_args.args[2], 'eu-at')
        self.assertEqual(state_set.call_args.args[3], build_packs.country_box('eu-at'))

    def test_capital_region_code_uses_region_builder(self):
        with patch.object(build_packs, 'state_set') as state_set, \
             patch.object(build_packs, 'region_set') as region_set:
            build_packs.build_map('ve-car')
        state_set.assert_not_called()
        region_set.assert_called_once()
        self.assertEqual(region_set.call_args.args, (build_packs.OUT / 'maps' / 've-car', 've-car'))


if __name__ == '__main__':
    unittest.main()
