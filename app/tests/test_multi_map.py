#!/usr/bin/env python3
"""Multi-map storage model (engine/setup/install.py): the registry, namespaced map folders, add / switch / migrate.

  derived/app-build/mac-venv/bin/python -B app/tests/test_multi_map.py [-v] [Class.test_name]

Offline: no network, no real library, no real map data. Every map is a tiny made-up unit (a map-set.json plus one
small file) in a temporary folder. The model under test is the storage contract the server and the install flow rely
on: several maps coexist under derived/geo/maps/<name>/, a registry (derived/geo/maps.json) names the active one, a
legacy flat library keeps working, and adding a map never removes a different one. Never packaged.
"""
import json, sys, unittest
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE.parent), str(ROOT)]
from engine.setup import install  # noqa: E402
from app.tests import shorttemp  # noqa: E402


# ------------------------------------------------------------------------------------------------------------ fixtures --
def make_map_unit(root, name, marker=b'national-bytes'):
    """A tiny map unit (a mini-library) at `root`: a map-set.json and one small file under derived/geo/."""
    root = Path(root)
    (root / 'derived' / 'geo').mkdir(parents=True, exist_ok=True)
    (root / 'derived' / 'geo' / 'national.sqlite').write_bytes(marker)
    (root / 'map-set.json').write_text(
        json.dumps({'name': name, 'files': {'derived/geo/national.sqlite': len(marker)},
                    'bytes': len(marker), 'seconds': 1}))
    return root


def make_library(folder, name=None):
    """A library folder; if `name` is given it holds that map flat (the legacy layout), else it is empty."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    if name is not None:
        make_map_unit(folder, name)
    return folder


class MultiMapTest(unittest.TestCase):
    def setUp(self):
        self.tmp = shorttemp.mkdtemp('lastbook-multimap-')
        self.lib = self.tmp / 'LastbookData'

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    # -- map_unit / active_map / map_dirs --------------------------------------------------------------
    def test_map_unit_flat_is_the_library(self):
        make_library(self.lib, 'CA')     # no registry: the legacy flat layout
        self.assertEqual(install.map_unit(self.lib, 'RJ'), self.lib.resolve())

    def test_map_unit_namespaced(self):
        make_library(self.lib, 'CA')
        install.migrate_flat(self.lib)
        self.assertEqual(install.map_unit(self.lib, 'RJ'),
                         (self.lib / 'derived' / 'geo' / 'maps' / 'RJ').resolve())

    def test_active_map_legacy_from_map_set(self):
        make_library(self.lib, 'CA')
        self.assertEqual(install.active_map(self.lib), 'CA')
        self.assertEqual(install.map_name(self.lib), 'CA')

    def test_active_map_empty_library_is_base(self):
        make_library(self.lib)
        self.assertEqual(install.active_map(self.lib), 'base')
        self.assertEqual(install.map_dirs(self.lib), set())

    def test_active_map_prefers_registry(self):
        make_library(self.lib, 'CA')
        install.migrate_flat(self.lib)
        install.add_map(self.lib, 'RJ', self._src('RJ', b'x'), label='Rio')
        self.assertEqual(install.active_map(self.lib), 'RJ')

    def test_map_dirs_flat_and_namespaced(self):
        make_library(self.lib, 'CA')
        self.assertEqual(install.map_dirs(self.lib), {'CA'})
        install.migrate_flat(self.lib)
        self.assertEqual(install.map_dirs(self.lib), {'CA'})

    # -- migrate_flat -----------------------------------------------------------------------------------
    def test_migrate_flat_namespaces_and_is_idempotent(self):
        make_library(self.lib, 'CA')
        install.migrate_flat(self.lib)
        # the flat files are gone; the map now lives in its own folder
        self.assertFalse((self.lib / 'derived' / 'geo' / 'national.sqlite').exists())
        self.assertFalse((self.lib / 'map-set.json').exists())
        self.assertTrue((self.lib / 'derived' / 'geo' / 'maps' / 'CA' / 'derived' / 'geo' / 'national.sqlite').exists())
        self.assertTrue((self.lib / 'derived' / 'geo' / 'maps' / 'CA' / 'map-set.json').exists())
        self.assertEqual(install.active_map(self.lib), 'CA')
        before = (self.lib / install.REGISTRY).read_text()
        install.migrate_flat(self.lib)     # a second time: a namespaced library is left alone
        self.assertEqual((self.lib / install.REGISTRY).read_text(), before)

    def test_migrate_flat_base_library_is_left_alone(self):
        make_library(self.lib)             # no map at all
        install.migrate_flat(self.lib)
        self.assertIsNone(install._registry(self.lib))
        self.assertEqual(install.active_map(self.lib), 'base')

    # -- add_map ----------------------------------------------------------------------------------------
    def _src(self, name, marker):
        src = self.tmp / f'src-{name}'
        make_map_unit(src, name, marker)
        return src

    def test_add_map_new_becomes_active_and_keeps_the_other(self):
        make_library(self.lib, 'CA')
        src = self._src('RJ', b'rio-bytes')
        install.add_map(self.lib, 'RJ', src, label='Rio de Janeiro')
        self.assertEqual(install.active_map(self.lib), 'RJ')
        self.assertEqual(install.map_dirs(self.lib), {'CA', 'RJ'})
        # the new map is in its own folder; the old one survived the migration, untouched
        self.assertTrue((self.lib / 'derived' / 'geo' / 'maps' / 'RJ' / 'derived' / 'geo' / 'national.sqlite').exists())
        self.assertEqual((self.lib / 'derived' / 'geo' / 'maps' / 'RJ' / 'derived' / 'geo' / 'national.sqlite').read_bytes(), b'rio-bytes')
        self.assertTrue((self.lib / 'derived' / 'geo' / 'maps' / 'CA' / 'derived' / 'geo' / 'national.sqlite').exists())
        reg = install._registry(self.lib)
        self.assertEqual(reg['active'], 'RJ')
        self.assertEqual(reg['maps']['RJ']['label'], 'Rio de Janeiro')

    def test_add_map_upgrade_replaces_files_in_place(self):
        make_library(self.lib, 'CA')
        install.add_map(self.lib, 'RJ', self._src('RJ', b'v1'))
        install.add_map(self.lib, 'RJ', self._src('RJ', b'v2-upgraded'))
        self.assertEqual(install.active_map(self.lib), 'RJ')
        self.assertEqual(install.map_dirs(self.lib), {'CA', 'RJ'})
        p = self.lib / 'derived' / 'geo' / 'maps' / 'RJ' / 'derived' / 'geo' / 'national.sqlite'
        self.assertEqual(p.read_bytes(), b'v2-upgraded')

    def test_add_map_name_mismatch_is_refused(self):
        make_library(self.lib, 'CA')
        src = self._src('CA', b'x')     # the unit says it is CA
        with self.assertRaises(install.Refused):
            install.add_map(self.lib, 'RJ', src)

    def test_add_map_unsafe_name_is_refused(self):
        make_library(self.lib, 'CA')
        with self.assertRaises(install.Refused):
            install.add_map(self.lib, '../evil', self._src('RJ', b'x'))

    # -- set_active -------------------------------------------------------------------------------------
    def test_set_active_switches(self):
        make_library(self.lib, 'CA')
        install.add_map(self.lib, 'RJ', self._src('RJ', b'x'))
        self.assertEqual(install.active_map(self.lib), 'RJ')
        install.set_active(self.lib, 'CA')
        self.assertEqual(install.active_map(self.lib), 'CA')
        self.assertEqual(install.map_dirs(self.lib), {'CA', 'RJ'})

    def test_set_active_uninstalled_is_refused(self):
        make_library(self.lib, 'CA')
        with self.assertRaises(install.Refused):
            install.set_active(self.lib, 'XX')

    def test_add_from_zip(self):
        # the add-from-file path: unpack a map .zip with the map guards, then add it (adds, never replaces)
        import zipfile
        lib = shorttemp.mkdtemp('multi-map-zip-')
        make_library(lib, 'alpha')
        src = shorttemp.mkdtemp('multi-map-zipsrc-')
        unit = src / 'LastbookData'
        make_library(unit, 'gama')
        zpath = Path(lib) / 'gama.zip'
        with zipfile.ZipFile(zpath, 'w') as z:
            for p in sorted(unit.rglob('*')):
                if p.is_file():
                    z.write(p, Path('LastbookData') / p.relative_to(unit))
        work = shorttemp.mkdtemp('multi-map-zipwork-')

        class C:
            def check(self):
                pass
        un = install.unpack(zpath, work, None, C(), lambda d, t: None, allowed=install.map_member)
        install.add_map(lib, 'gama', un)
        self.assertEqual(install.active_map(lib), 'gama')   # the new map becomes active; the old one stays installed
        self.assertIn('alpha', install.map_dirs(lib))
        self.assertEqual((install.map_unit(lib, 'gama') / 'derived' / 'geo' / 'national.sqlite').read_bytes(), b'national-bytes')

    # -- map_set_for ------------------------------------------------------------------------------------
    def test_map_set_for_reads_the_map_folder(self):
        make_library(self.lib, 'CA')
        install.add_map(self.lib, 'RJ', self._src('RJ', b'rio-bytes'))
        s = install.map_set_for(self.lib, 'RJ')
        self.assertEqual(s['name'], 'RJ')
        self.assertIn('derived/geo/national.sqlite', s['files'])


class ServerMultiMapTest(unittest.TestCase):
    """The server's active-map helpers (server.py): maps_public lists the installed maps, geo_dir follows the
    active one, and geo_dir_for reaches a specific map. LASTBOOK_DATA is pointed at a temporary folder before
    server.py is imported, so its LIB (and every map path) is the test library, never the real one."""

    @classmethod
    def setUpClass(cls):
        import os
        cls._old_data = os.environ.get('LASTBOOK_DATA')
        cls.data = shorttemp.mkdtemp('server-multimap-')
        os.environ['LASTBOOK_DATA'] = str(cls.data)
        import server  # noqa: E402  imported with LASTBOOK_DATA set, so LIB is the temporary library
        cls.server = server
        lib = cls.server.LIB
        install.add_map(lib, 'alpha', make_map_unit(cls.data / 'srcA', 'alpha', b'alpha-bytes'), label='Alpha')
        install.add_map(lib, 'beta', make_map_unit(cls.data / 'srcB', 'beta', b'beta-bytes'), label='Beta')

    @classmethod
    def tearDownClass(cls):
        import os, shutil
        if cls._old_data is None:
            os.environ.pop('LASTBOOK_DATA', None)
        else:
            os.environ['LASTBOOK_DATA'] = cls._old_data
        shutil.rmtree(cls.data, ignore_errors=True)

    def _geo(self, name):
        return self.server.LIB / 'derived' / 'geo' / 'maps' / name / 'derived' / 'geo'

    def test_maps_public_lists_both_with_labels(self):
        maps = self.server.maps_public()
        self.assertEqual({m['name'] for m in maps}, {'alpha', 'beta'})
        self.assertEqual({m['name']: m['label'] for m in maps}, {'alpha': 'Alpha', 'beta': 'Beta'})

    def test_geo_dir_follows_the_active_map(self):
        self.server.setup_install.set_active(self.server.LIB, 'beta')
        self.assertEqual(self.server.geo_dir(), self._geo('beta'))
        self.server.setup_install.set_active(self.server.LIB, 'alpha')
        self.assertEqual(self.server.geo_dir(), self._geo('alpha'))

    def test_geo_dir_for_reaches_a_specific_map(self):
        self.server.setup_install.set_active(self.server.LIB, 'alpha')
        self.assertEqual(self.server.geo_dir_for('beta'), self._geo('beta'))
        self.assertEqual(self.server.geo_dir_for('alpha'), self._geo('alpha'))

    def test_active_map_is_reflected(self):
        self.server.setup_install.set_active(self.server.LIB, 'beta')
        self.assertEqual(self.server.setup_install.active_map(self.server.LIB), 'beta')
        self.assertEqual(self.server.maps_public()[0]['name'] in ('alpha', 'beta'), True)


if __name__ == '__main__':
    unittest.main()
