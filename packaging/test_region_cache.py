"""Region-source cache checks, without network access or a sample library.

  python3 -B -m unittest discover -s packaging -p test_region_cache.py -v
"""
import importlib.util
import shutil
import sqlite3
import tempfile
import unittest
import zipfile
import zlib
from pathlib import Path
from unittest.mock import patch


spec = importlib.util.spec_from_file_location('build_packs', Path(__file__).with_name('build_packs.py'))
build_packs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build_packs)


class RegionCache(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.spec = {'extract': 'https://example.invalid/region.zip'}
        self.folder = self.root / 'out/maps/region-source/region'
        self.folder.mkdir(parents=True)
        self.zipped = self.folder / 'region.zip'
        self.gpkg = self.folder / 'region.gpkg'
        good = self.root / 'good.gpkg'
        db = sqlite3.connect(good)
        for table in ('gpkg_contents', 'gpkg_geometry_columns', 'gpkg_spatial_ref_sys'):
            db.execute(f'CREATE TABLE {table} (id INTEGER)')
        db.commit()
        db.close()
        self.good = good.read_bytes()
        self.source = self.root / 'source.zip'
        self.archive(self.source, self.good)
        out = patch.object(build_packs, 'OUT', self.root / 'out')
        out.start()
        self.addCleanup(out.stop)
        download = patch.object(build_packs.urllib.request, 'urlretrieve',
                                side_effect=lambda url, dest: shutil.copyfile(self.source, dest))
        self.download = download.start()
        self.addCleanup(download.stop)

    def archive(self, path, data, name='region.gpkg'):
        with zipfile.ZipFile(path, 'w') as z:
            z.writestr(name, data)

    def fetch(self):
        return build_packs.fetch_region_gpkg(self.spec)

    def test_valid_gpkg_cache_needs_no_download(self):
        self.gpkg.write_bytes(self.good)
        self.assertEqual(self.fetch(), self.gpkg)
        self.download.assert_not_called()

    def test_invalid_gpkg_cache_is_rebuilt_from_valid_zip(self):
        self.archive(self.zipped, self.good)
        for payload in (b'', b'not a database', b'SQLite format 3\0'):
            with self.subTest(payload=payload):
                self.gpkg.write_bytes(payload)
                self.assertEqual(self.fetch().read_bytes(), self.good)
        self.download.assert_not_called()

    def test_plain_sqlite_cache_is_not_a_geopackage(self):
        db = sqlite3.connect(self.gpkg)
        db.execute('CREATE TABLE unrelated (id INTEGER)')
        db.close()
        self.archive(self.zipped, self.good)
        self.assertEqual(self.fetch().read_bytes(), self.good)
        self.download.assert_not_called()

    def test_partial_zip_is_downloaded_again(self):
        self.zipped.write_bytes(b'PK partial')
        self.assertEqual(self.fetch().read_bytes(), self.good)
        self.download.assert_called_once()

    def test_damaged_deflate_member_is_downloaded_again(self):
        with zipfile.ZipFile(self.zipped, 'w', compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr('region.gpkg', self.good)
        with zipfile.ZipFile(self.zipped) as z:
            self.assertIsNone(z.testzip())
            info = z.getinfo('region.gpkg')
        data = bytearray(self.zipped.read_bytes())
        header = info.header_offset
        name_len = int.from_bytes(data[header + 26:header + 28], 'little')
        extra_len = int.from_bytes(data[header + 28:header + 30], 'little')
        offset = header + 30 + name_len + extra_len
        data[offset] |= 0x06   # reserved DEFLATE block type, leaving the ZIP headers intact
        self.zipped.write_bytes(data)
        with zipfile.ZipFile(self.zipped) as z:
            with self.assertRaises(zlib.error):
                z.testzip()
        self.assertEqual(self.fetch().read_bytes(), self.good)
        self.download.assert_called_once()
        with zipfile.ZipFile(self.zipped) as z:
            self.assertIsNone(z.testzip())

    def test_damaged_deflate_download_leaves_no_tmp(self):
        with zipfile.ZipFile(self.source, 'w', compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr('region.gpkg', self.good)
        with zipfile.ZipFile(self.source) as z:
            self.assertIsNone(z.testzip())
            info = z.getinfo('region.gpkg')
        data = bytearray(self.source.read_bytes())
        header = info.header_offset
        name_len = int.from_bytes(data[header + 26:header + 28], 'little')
        extra_len = int.from_bytes(data[header + 28:header + 30], 'little')
        offset = header + 30 + name_len + extra_len
        data[offset] |= 0x06   # reserved DEFLATE block type, leaving the ZIP headers intact
        self.source.write_bytes(data)
        with zipfile.ZipFile(self.source) as z:
            with self.assertRaises(zlib.error):
                z.testzip()
        with self.assertRaises(SystemExit):
            self.fetch()
        self.download.assert_called_once()
        self.assertFalse(list(self.folder.glob(f'{self.zipped.name}.tmp*')))

    def test_interrupted_download_cleans_tmp(self):
        def interrupted(url, dest):
            Path(dest).write_bytes(b'PK partial')
            raise build_packs.urllib.error.URLError('connection reset')
        self.download.side_effect = interrupted
        with self.assertRaises(build_packs.urllib.error.URLError):
            self.fetch()
        self.assertFalse(list(self.folder.glob(f'{self.zipped.name}.tmp*')))

    def test_interrupted_extraction_cleans_scratch(self):
        self.archive(self.zipped, self.good)
        with patch.object(zipfile.ZipFile, 'extractall', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.fetch()
        self.assertFalse(list(self.folder.glob('extract.tmp*')))
        self.assertTrue(self.zipped.exists())

    def invalid_archive_retry(self, payload, name='region.gpkg'):
        self.archive(self.zipped, payload, name)
        with self.assertRaises(SystemExit):
            self.fetch()
        self.assertFalse(self.zipped.exists())
        self.assertFalse(self.gpkg.exists())
        self.assertFalse(list(self.folder.glob('extract.tmp*')))
        self.assertEqual(self.fetch().read_bytes(), self.good)
        self.download.assert_called_once()

    def test_empty_archive_payload_is_invalidated_before_retry(self):
        self.invalid_archive_retry(b'')

    def test_corrupt_archive_payload_is_invalidated_before_retry(self):
        self.invalid_archive_retry(b'not a database')

    def test_missing_archive_payload_is_invalidated_before_retry(self):
        self.invalid_archive_retry(b'no GeoPackage here', 'readme.txt')


if __name__ == '__main__':
    unittest.main()
