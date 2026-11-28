"""Offline rebuild checks for build_map, without network access or a sample library.

  python3 -B -m unittest discover -s packaging -p test_map_rebuild.py -v

A failed rebuild must leave the last completed map and its manifest in place, and an interrupted swap
followed by a failed retry must recover the previous map. These checks plant a good previous output, fail
the next build, and assert the previous files and map-set.json survive untouched.
"""
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


spec = importlib.util.spec_from_file_location('build_packs', Path(__file__).with_name('build_packs.py'))
build_packs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_packs)


class MapRebuild(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        out = patch.object(build_packs, 'OUT', self.root / 'out')
        out.start()
        self.addCleanup(out.stop)

    def test_failed_region_rebuild_keeps_last_map_and_manifest(self):
        dest = build_packs.OUT / 'maps' / 've-car'
        (dest / 'derived/geo').mkdir(parents=True)
        map_bytes = b'previous map bytes'
        (dest / 'derived/geo/map.sqlite').write_bytes(map_bytes)
        manifest = {'name': 've-car', 'files': {'derived/geo/map.sqlite': len(map_bytes)}, 'bytes': len(map_bytes), 'seconds': 1}
        manifest_text = json.dumps(manifest)
        (dest / 'map-set.json').write_text(manifest_text)
        with patch.object(build_packs, 'region_set', side_effect=SystemExit('source unavailable')):
            with self.assertRaises(SystemExit):
                build_packs.build_map('ve-car')
        self.assertEqual((dest / 'derived/geo/map.sqlite').read_bytes(), map_bytes)
        self.assertEqual((dest / 'map-set.json').read_text(), manifest_text)
        self.assertEqual(sorted(p.relative_to(dest).as_posix() for p in dest.rglob('*') if p.is_file()),
                         ['derived/geo/map.sqlite', 'map-set.json'])
        self.assertFalse(list(dest.parent.glob(dest.name + '.prev*')))

    def test_interrupted_swap_then_failed_retry_keeps_last_map(self):
        dest = build_packs.OUT / 'maps' / 've-car'
        (dest / 'derived/geo').mkdir(parents=True)
        map_bytes = b'previous map bytes'
        (dest / 'derived/geo/map.sqlite').write_bytes(map_bytes)
        manifest = {'name': 've-car', 'files': {'derived/geo/map.sqlite': len(map_bytes)}, 'bytes': len(map_bytes), 'seconds': 1}
        manifest_text = json.dumps(manifest)
        (dest / 'map-set.json').write_text(manifest_text)
        # Simulate a swap interrupted after the complete map moved aside: only .prev remains.
        previous = dest.with_name(dest.name + '.prev')
        os.replace(dest, previous)
        self.assertFalse(dest.exists())
        self.assertTrue((previous / 'map-set.json').exists())
        # A failed retry must recover the previous map, not leave the build empty.
        with patch.object(build_packs, 'region_set', side_effect=SystemExit('source unavailable')):
            with self.assertRaises(SystemExit):
                build_packs.build_map('ve-car')
        self.assertEqual((dest / 'derived/geo/map.sqlite').read_bytes(), map_bytes)
        self.assertEqual((dest / 'map-set.json').read_text(), manifest_text)
        self.assertEqual(sorted(p.relative_to(dest).as_posix() for p in dest.rglob('*') if p.is_file()),
                         ['derived/geo/map.sqlite', 'map-set.json'])
        self.assertFalse(list(dest.parent.glob(dest.name + '.prev*')))
        self.assertFalse(list(dest.parent.glob(dest.name + '.building*')))


if __name__ == '__main__':
    unittest.main()
