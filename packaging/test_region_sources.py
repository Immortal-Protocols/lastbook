"""From a checkout: python3 -B packaging/test_region_sources.py"""
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import build_packs


class RegionSourceTests(unittest.TestCase):
    def test_multiple_provinces_use_their_own_cached_extract(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(build_packs, 'OUT', Path(tmp) / 'out'):
            cached = {}
            for region in ('ca-ns', 'ca-nb', 'ca-pe'):
                spec = build_packs.REGIONS[region]
                archive = Path(tmp) / Path(spec['extract']).name
                with zipfile.ZipFile(archive, 'w') as z:
                    z.writestr('README', 'test fixture')
                    z.writestr('map.gpkg', region)
                local = dict(spec, extract=archive.as_uri())
                cached[region] = local
                self.assertEqual(build_packs.fetch_region_gpkg(local).read_text(), region)
                archive.unlink()
            for region, local in cached.items():
                self.assertEqual(build_packs.fetch_region_gpkg(local).read_text(), region)

if __name__ == '__main__':
    unittest.main()
