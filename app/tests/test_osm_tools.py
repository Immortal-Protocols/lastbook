"""The OpenStreetMap map-set builders (tools/build_*_osm.py, build_region.py), run on a few hand-made objects around Westminster.

They need pyosmium, numpy and Pillow, which only a build machine has, so each group is skipped where they are missing.
"""
import json
import os
import sqlite3
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
TOOLS = REPO / 'tools'
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(REPO))

try:
    import osmium
    from osmium.osm import mutable
    HAVE_OSMIUM = True
except ImportError:
    HAVE_OSMIUM = False
try:
    import numpy       # noqa: F401
    import PIL         # noqa: F401
    HAVE_IMAGING = True
except ImportError:
    HAVE_IMAGING = False

BOX = '-0.30,51.40,0.10,51.60'          # W,S,E,N: Westminster and its surroundings (the west value is negative on purpose)
WESTMINSTER = (-0.1276, 51.5034)
EXETER = (-3.5339, 50.7236)


def square(lon, lat, size=0.0004):
    return [(lon, lat), (lon + size, lat), (lon + size, lat + size), (lon, lat + size), (lon, lat)]


def write_pbf(path, nodes=(), ways=()):
    """nodes: (id, lon, lat, tags); ways: (id, [node ids], tags)."""
    w = osmium.SimpleWriter(str(path))
    for nid, lon, lat, tags in sorted(nodes):
        w.add_node(mutable.Node(id=nid, location=(lon, lat), tags=tags))
    for wid, refs, tags in sorted(ways, key=lambda x: x[0]):
        w.add_way(mutable.Way(id=wid, nodes=refs, tags=tags))
    w.close()


def ring_way(first_id, wid, lon, lat, tags, size=0.0004):
    """A closed way and its nodes: (nodes, way)."""
    pts = square(lon, lat, size)
    ids = list(range(first_id, first_id + 4))
    nodes = [(i, p[0], p[1], {}) for i, p in zip(ids, pts)]
    return nodes, (wid, ids + [ids[0]], tags)


def run(script, *args, env=None):
    r = subprocess.run([sys.executable, '-B', str(TOOLS / script), *map(str, args)], cwd=REPO, capture_output=True, text=True,
                       env=dict(os.environ, **{k: str(v) for k, v in (env or {}).items()}))
    if r.returncode:
        raise AssertionError(f'{script} failed:\n{r.stdout[-800:]}\n{r.stderr[-1500:]}')
    return r.stdout


class Temp(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(t.cleanup)
        self.dir = Path(t.name)

    def db(self, path):
        """A connection that is closed before the folder is removed (Windows will not delete an open file)."""
        c = sqlite3.connect(path)
        self.addCleanup(c.close)
        return c


@unittest.skipUnless(HAVE_OSMIUM, 'pyosmium is not installed')
class AddressTests(Temp):
    def build(self):
        pbf = self.dir / 'x.osm.pbf'
        nodes = [
            (1, *WESTMINSTER, {'addr:housenumber': '10', 'addr:street': 'Downing Street', 'addr:postcode': 'sw1a2aa', 'addr:city': 'London'}),
            (2, *EXETER, {'addr:housenumber': '5', 'addr:street': 'High Street', 'addr:postcode': 'EX4 3LS'}),     # outside the box
            (3, -0.12, 51.50, {'addr:housenumber': '7'}),                                                          # no street
            (4, -0.11, 51.51, {'addr:housenumber': '9', 'addr:street': "St James's Road", 'addr:postcode': 'not one', 'addr:hamlet': 'Soho'}),
        ]
        ring, way = ring_way(100, 1000, -0.2, 51.45, {'addr:housenumber': '22b', 'addr:street': 'Marsh Lane', 'addr:postcode': 'E1 6AN',
                                                       'building': 'yes'})
        write_pbf(pbf, nodes + ring, [way])
        out = self.dir / 'addr' / 'GB-LON.sqlite'
        text = run('build_addresses_osm.py', pbf, out, f'--bbox={BOX}', '--source', 'test source')
        return self.db(out), text

    def test_keeps_addresses_inside_the_box_with_a_street(self):
        db, _ = self.build()
        rows = {r[0]: r for r in db.execute('SELECT num, street, norm, city, state, zip, lat, lon FROM addr')}
        self.assertEqual(sorted(rows), ['10', '22b', '9'])       # Exeter and the street-less one are gone

    def test_postcodes_are_written_in_the_canonical_form_or_left_empty(self):
        db, _ = self.build()
        zips = dict(db.execute('SELECT num, zip FROM addr'))
        self.assertEqual(zips, {'10': 'SW1A 2AA', '22b': 'E1 6AN', '9': ''})

    def test_city_falls_back_to_other_place_keys_and_state_is_empty(self):
        db, _ = self.build()
        city = dict(db.execute('SELECT num, city FROM addr'))
        self.assertEqual((city['10'], city['9'], city['22b']), ('London', 'Soho', ''))
        self.assertEqual({s for (s,) in db.execute('SELECT state FROM addr')}, {''})

    def test_a_building_outline_is_placed_at_the_middle_of_its_nodes(self):
        db, _ = self.build()
        lat, lon = db.execute("SELECT lat, lon FROM addr WHERE num='22b'").fetchone()
        # the mean of the way's five node positions (the first corner is listed twice to close the ring)
        self.assertAlmostEqual(lon, -0.2 + 0.0004 * 2 / 5, places=5)
        self.assertAlmostEqual(lat, 51.45 + 0.0004 * 2 / 5, places=5)

    def test_the_same_address_on_a_node_and_its_building_is_kept_once(self):
        pbf = self.dir / 'dup.osm.pbf'
        tags = {'addr:housenumber': '12', 'addr:street': 'Baker Street', 'addr:postcode': 'NW1 6XE'}
        ring, way = ring_way(100, 1000, -0.1580, 51.5200, {**tags, 'building': 'yes'})
        nodes = [(1, -0.15785, 51.52015, dict(tags)),                                    # an entrance node inside that outline
                 (2, -0.1580, 51.5300, dict(tags)),                                      # the same address text 1 km away: a different house
                 (3, -0.15790, 51.52010, {**tags, 'addr:housenumber': '14'})]             # a neighbour: different number
        write_pbf(pbf, nodes + ring, [way])
        out = self.dir / 'dup.sqlite'
        text = run('build_addresses_osm.py', pbf, out, f'--bbox={BOX}')
        rows = self.db(out).execute('SELECT num, lat FROM addr ORDER BY num, lat').fetchall()
        self.assertEqual([r[0] for r in rows], ['12', '12', '14'])
        self.assertEqual([round(r[1], 2) for r in rows if r[0] == '12'], [51.52, 51.53])
        self.assertIn('1 repeats dropped', text)

    def test_meta_and_index_the_address_search_reads(self):
        db, text = self.build()
        meta = dict(db.execute('SELECT key, value FROM meta'))
        self.assertEqual((meta['source'], meta['count'], meta['with_postcode'], meta['bbox']), ('test source', '3', '2', BOX))
        self.assertIn('addr_norm', {r[1] for r in db.execute("PRAGMA index_list('addr')")})
        self.assertIn('3 addresses', text)

    def test_the_address_search_finds_what_was_built(self):
        db, _ = self.build()
        self.assertEqual(db.execute("SELECT num FROM addr WHERE norm='downing st'").fetchall(), [('10',)])


@unittest.skipUnless(HAVE_OSMIUM, 'pyosmium is not installed')
class AtlasTests(Temp):
    def test_mines_quarries_slipways_and_marinas(self):
        pbf = self.dir / 'x.osm.pbf'
        quarry, quarry_way = ring_way(100, 1000, -0.2, 51.45, {'landuse': 'quarry', 'name': 'Big Pit', 'resource': 'gravel', 'operator': 'Acme'})
        nodes = [(1, -0.10, 51.50, {'leisure': 'slipway', 'name': 'Thames Slip'}),
                 (2, -0.09, 51.50, {'historic': 'mine', 'disused': 'yes'}),
                 (3, -0.08, 51.50, {'man_made': 'mineshaft'}),
                 (4, -0.07, 51.50, {'leisure': 'marina'}),
                 (5, *EXETER, {'leisure': 'slipway', 'name': 'Far Slip'}),                  # outside the box
                 (6, -0.06, 51.50, {'amenity': 'bench'})]
        write_pbf(pbf, nodes + quarry, [quarry_way])
        out = self.dir / 'atlas.sqlite'
        run('build_atlas_osm.py', pbf, out, f'--bbox={BOX}', '--source', 'test source')
        db = self.db(out)
        rows = {r[0]: r for r in db.execute('SELECT name, kind, detail, source_id, origin FROM resource')}
        self.assertEqual(sorted(rows), ['Big Pit', 'Marina', 'Mine', 'Mine shaft', 'Thames Slip'])
        self.assertEqual({n: r[1] for n, r in rows.items()},
                         {'Big Pit': 'mineral', 'Mine': 'mineral', 'Mine shaft': 'mineral', 'Marina': 'boat_launch', 'Thames Slip': 'boat_launch'})
        quarry_detail = json.loads(rows['Big Pit'][2])
        self.assertEqual((quarry_detail['commodity'], quarry_detail['owner'], quarry_detail['feature']), ('gravel', 'Acme', 'Quarry'))
        self.assertEqual(json.loads(rows['Mine'][2])['status'], 'Disused')
        self.assertTrue(rows['Big Pit'][3].startswith('osm:w'))
        self.assertEqual({r[4] for r in rows.values()}, {'osm'})
        self.assertEqual(db.execute('SELECT count(*) FROM spatial').fetchone()[0], 5)
        self.assertEqual(json.loads(db.execute("SELECT value FROM meta WHERE key='built'").fetchone()[0])['source'], 'test source')


@unittest.skipUnless(HAVE_OSMIUM, 'pyosmium is not installed')
class BuildingHeightTests(Temp):
    def build(self, box=BOX):
        pbf = self.dir / 'x.osm.pbf'
        nodes, ways = [], []
        for i, (lon, lat, tags) in enumerate([
                (-0.20, 51.45, {'building': 'yes', 'height': '45'}),
                (-0.19, 51.45, {'building': 'yes', 'building:levels': '4'}),
                (-0.18, 51.45, {'building': 'yes'}),                                       # no height, not kept
                (-0.17, 51.45, {'building': 'yes', 'building:levels': '300'}),             # a typo, not kept
                (-0.16, 51.45, {'building': 'yes', 'height': '1'}),                        # too low to be a building
                (*EXETER, {'building': 'yes', 'height': '30'})]):                          # outside the box
            n, w = ring_way(100 + i * 10, 1000 + i, lon, lat, tags)
            nodes += n
            ways.append(w)
        write_pbf(pbf, nodes, ways)
        out = self.dir / 'b.sqlite'
        run('build_osm_heights.py', pbf, env={'BUILDINGS_OUT': out, 'LASTBOOK_BBOX': box, 'LASTBOOK_BUILDINGS_SOURCE': 'test source'})
        return self.db(out)

    def test_keeps_only_buildings_with_a_height_inside_the_box(self):
        db = self.build()
        meta = dict(db.execute('SELECT key, value FROM meta'))
        self.assertEqual(meta['osm_heights'], '2')
        self.assertEqual(meta['source'], 'test source')       # the new meta table exists on a fresh file
        self.assertIn('built', meta)

    def test_a_storey_count_becomes_a_height(self):
        import zlib
        from array import array
        db = self.build()
        heights = []
        for (blob,) in db.execute('SELECT data FROM bldg_osm'):
            a = array('i')
            a.frombytes(zlib.decompress(blob))
            i = 0
            while i < len(a):
                heights.append(a[i + 1] / 10)
                i += 6 + 2 * (a[i] - 1)
        self.assertEqual(sorted(heights), [14.3, 45.0])         # 4 storeys: 4 x 3.2 m + 1.5 m

    def test_a_box_that_holds_nothing_keeps_nothing(self):
        db = self.build('10,10,11,11')
        self.assertEqual(dict(db.execute('SELECT key, value FROM meta'))['osm_heights'], '0')


class HeightParsingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not HAVE_OSMIUM:
            raise unittest.SkipTest('pyosmium is not installed')
        with patch.object(sys, 'argv', ['build_osm_heights.py']):
            import build_osm_heights
        cls.metres = staticmethod(build_osm_heights.metres)

    def test_units(self):
        self.assertEqual(self.metres('45'), 45)
        self.assertEqual(self.metres('45 m'), 45)
        self.assertAlmostEqual(self.metres('150 ft'), 45.72)
        self.assertAlmostEqual(self.metres("150'"), 45.72)
        self.assertEqual(self.metres('12,5'), 12.5)

    def test_nonsense_is_none(self):
        for v in (None, '', 'tall', '5000', '-3'):
            with self.subTest(v=v):
                self.assertIsNone(self.metres(v))


@unittest.skipUnless(HAVE_OSMIUM, 'pyosmium is not installed')
class WaterTests(Temp):
    def test_dams_inside_the_box_become_points_and_a_rerun_replaces_them(self):
        pbf = self.dir / 'x.osm.pbf'
        nodes = [(1, -0.20, 51.45, {}), (2, -0.19, 51.45, {}), (3, *EXETER, {}), (4, -3.52, 50.72, {}),
                 (5, -0.15, 51.50, {'man_made': 'dam', 'name': 'Node Dam'})]
        ways = [(1000, [1, 2], {'waterway': 'dam', 'name': 'Long Dam', 'operator': 'Thames Water', 'height': '12'}),
                (1001, [3, 4], {'waterway': 'dam', 'name': 'Far Dam'})]
        write_pbf(pbf, nodes, ways)
        env = {'LASTBOOK_GEO': self.dir, 'LASTBOOK_UNITS': 'metric'}
        for _ in range(2):
            run('build_water.py', 'dams-osm', pbf, BOX, env=env)
        db = self.db(self.dir / 'water.sqlite')
        rows = {r[0]: r for r in db.execute("SELECT name, kind, detail, origin FROM resource")}
        self.assertEqual(sorted(rows), ['Long Dam', 'Node Dam'])
        self.assertEqual({r[1] for r in rows.values()}, {'dam'})
        detail = json.loads(rows['Long Dam'][2])
        self.assertEqual((detail['owner'], detail['height']), ('Thames Water', '12'))
        self.assertEqual(db.execute('SELECT count(*) FROM spatial').fetchone()[0], 2)

    def test_ring_area_and_inside_point(self):
        import build_water
        lon, lat, d = -2.0, 51.0, 0.01
        ring = [(lon, lat), (lon + d, lat), (lon + d, lat + d), (lon, lat + d)]
        # 0.01 degrees of latitude is 1.113 km, and a degree of longitude is shorter by cos(latitude)
        self.assertAlmostEqual(build_water.ring_area_km2(ring), 1.1132 ** 2 * 0.629, delta=0.02)
        # a "U" shape: the middle of its box is in the gap, so the point must be found on one of the arms
        u = [(0, 0), (3, 0), (3, 3), (2, 3), (2, 1), (1, 1), (1, 3), (0, 3)]
        x, y = build_water.inside_point(u)
        self.assertTrue(x < 1 or x > 2 or y < 1, (x, y))


def gpkg_polygon(lon, lat, size):
    """A GeoPackage geometry blob for one square polygon: 8-byte header with an envelope, then WKB."""
    ring = square(lon, lat, size)
    wkb = struct.pack('<BII', 1, 3, 1) + struct.pack('<I', len(ring)) + b''.join(struct.pack('<2d', *p) for p in ring)
    header = b'GP' + bytes([0, 0b011]) + struct.pack('<i', 4326) + struct.pack('<4d', lon, lon + size, lat, lat + size)
    return header + wkb


@unittest.skipUnless(HAVE_OSMIUM and HAVE_IMAGING, 'numpy and Pillow are not installed')
class CropTests(Temp):
    def test_orchards_and_vineyards_inside_the_box(self):
        gpkg = self.dir / 'x.gpkg'
        db = sqlite3.connect(gpkg)
        db.execute('CREATE TABLE gis_osm_landuse_a_free(osm_id TEXT, fclass TEXT, name TEXT, geom BLOB)')
        db.executemany('INSERT INTO gis_osm_landuse_a_free VALUES (?,?,?,?)', [
            ('1', 'orchard', 'Apple Farm', gpkg_polygon(-0.20, 51.45, 0.002)),
            ('2', 'vineyard', None, gpkg_polygon(-0.18, 51.46, 0.002)),
            ('3', 'orchard', 'Far Orchard', gpkg_polygon(*EXETER, 0.002)),            # outside the box
            ('4', 'forest', 'Wood', gpkg_polygon(-0.17, 51.46, 0.002)),               # not a crop
            ('5', 'orchard', 'No Shape', None)])
        db.commit()
        db.close()
        out = self.dir / 'crops.sqlite'
        run('build_crops_osm.py', gpkg, out, f'--bbox={BOX}', '--source', 'test source')
        c = self.db(out)
        rows = {r[0]: r for r in c.execute('SELECT name, kind, detail, source FROM resource')}
        self.assertEqual(sorted(rows), ['Apple Farm', 'Grapes'])          # a vineyard with no name is called Grapes
        self.assertEqual((rows['Apple Farm'][1], rows['Grapes'][1]), ('orchard', 'vineyard'))
        detail = json.loads(rows['Apple Farm'][2])
        self.assertEqual(detail['crop'], 'Orchard')
        self.assertTrue(2.5 < detail['crop_ha'] < 3.7, detail)           # 0.002 degrees square at 51 N is about 139 m by 222 m, 3.1 ha
        self.assertEqual(rows['Apple Farm'][3], 'https://www.openstreetmap.org/way/1')
        zooms = {z for (z,) in c.execute('SELECT DISTINCT z FROM tile')}
        self.assertEqual(zooms, set(range(7, 14)))
        self.assertEqual(json.loads(c.execute("SELECT value FROM meta WHERE key='built'").fetchone()[0])['cells'], 2)

    def test_polygons_reads_single_and_multi_polygons_and_holes(self):
        import build_crops_osm
        single = build_crops_osm.polygons(gpkg_polygon(0, 0, 1))
        self.assertEqual(len(single), 1)
        self.assertEqual(len(single[0]), 1)
        self.assertEqual(len(single[0][0]), 5)
        self.assertEqual(build_crops_osm.polygons(b'GP' + bytes([0, 0b011]) + b'\0' * 38 + struct.pack('<BI', 1, 1)), [])   # a point is no area


class PlaceFinderTests(Temp):
    def national(self):
        path = self.dir / 'national.sqlite'
        db = sqlite3.connect(path)
        db.executescript('''CREATE TABLE feat(id INTEGER PRIMARY KEY, layer TEXT, cls TEXT, name TEXT, geom BLOB);
                            CREATE TABLE poi(id INTEGER PRIMARY KEY, cls TEXT, name TEXT, lon REAL, lat REAL);''')
        point = lambda lon, lat: struct.pack('<iiii', 0, 0, round(lon * 1e6), round(lat * 1e6))
        db.executemany('INSERT INTO feat(layer, cls, name, geom) VALUES (?,?,?,?)', [
            ('place', 'town', 'Camden Town', point(-0.1428, 51.5393)),
            ('place', 'farm', 'Rose Farm', point(-0.2, 51.4)),                     # farms and localities would bury the towns
            ('place', 'locality', 'The Heath', point(-0.2, 51.45)),
            ('place', 'village', None, point(-0.3, 51.5)),                         # no name
            ('road', 'primary', 'High Road', point(0, 51.5))])
        db.executemany('INSERT INTO poi(cls, name, lon, lat) VALUES (?,?,?,?)', [
            ('police_station', 'Holborn Police Station', -0.12, 51.52), ('hospital', None, -0.1, 51.5)])
        db.commit()
        db.close()
        return path

    def addresses(self):
        path = self.dir / 'addr.sqlite'
        db = sqlite3.connect(path)
        db.execute('CREATE TABLE addr(num TEXT, street TEXT, norm TEXT, city TEXT, state TEXT, zip TEXT, lat REAL, lon REAL)')
        db.executemany('INSERT INTO addr VALUES (?,?,?,?,?,?,?,?)', [
            ('1', 'A St', 'a st', '', '', 'NW1 8AA', 51.50, -0.10), ('2', 'A St', 'a st', '', '', 'NW1 8AA', 51.52, -0.12),
            ('3', 'B St', 'b st', '', '', 'NW1 9ZZ', 51.60, -0.20), ('4', 'C St', 'c st', '', '', '', 51.0, 0.0)])
        db.commit()
        db.close()
        return path

    def build(self):
        out = self.dir / 'places.sqlite'
        text = run('build_places_osm.py', self.national(), self.addresses(), out, '--area', 'London')
        return self.db(out), text

    def test_towns_and_named_points_but_not_farms_localities_or_unnamed(self):
        db, _ = self.build()
        names = {r[0] for r in db.execute("SELECT name FROM place WHERE kind NOT LIKE 'postcode%'")}
        self.assertEqual(names, {'Camden Town', 'Holborn Police Station'})
        self.assertEqual(db.execute("SELECT kind FROM place WHERE name='Holborn Police Station'").fetchone()[0], 'police station')

    def test_a_point_per_postcode_in_the_middle_of_its_addresses(self):
        db, _ = self.build()
        lat, lon, detail = db.execute("SELECT lat, lon, detail FROM place WHERE name='NW1 8AA'").fetchone()
        self.assertEqual((round(lat, 3), round(lon, 3)), (51.51, -0.11))
        self.assertIn('2 OpenStreetMap addresses', detail)
        self.assertIn('1 OpenStreetMap address', db.execute("SELECT detail FROM place WHERE name='NW1 9ZZ'").fetchone()[0])
        self.assertEqual(db.execute("SELECT count(*) FROM place WHERE kind='postcode'").fetchone()[0], 2)     # the address with no postcode adds none

    def test_a_point_per_postcode_district(self):
        db, _ = self.build()
        lat, lon, detail = db.execute("SELECT lat, lon, detail FROM place WHERE kind='postcode district' AND name='NW1'").fetchone()
        self.assertEqual((round(lat, 3), round(lon, 3)), (51.555, -0.155))             # the middle of the two postcode points
        self.assertIn('2 postcodes', detail)

    def test_the_names_can_be_searched(self):
        db, _ = self.build()
        hits = db.execute("SELECT p.name FROM place_fts JOIN place p ON p.id = place_fts.rowid WHERE place_fts MATCH 'camden'").fetchall()
        self.assertEqual(hits, [('Camden Town',)])

    def test_the_whole_chain_from_the_addresses_built_on_the_openstreetmap_tool(self):
        if not HAVE_OSMIUM:
            self.skipTest('pyosmium is not installed')
        pbf = self.dir / 'x.osm.pbf'
        write_pbf(pbf, [(1, *WESTMINSTER, {'addr:housenumber': '10', 'addr:street': 'Downing Street', 'addr:postcode': 'SW1A 2AA'})])
        addr = self.dir / 'real-addr.sqlite'
        run('build_addresses_osm.py', pbf, addr, f'--bbox={BOX}')
        out = self.dir / 'chain.sqlite'
        run('build_places_osm.py', self.national(), addr, out, '--area', 'London')
        self.assertEqual(self.db(out).execute("SELECT count(*) FROM place WHERE name IN ('SW1A 2AA','SW1A')").fetchone()[0], 2)


class ToolDocsTests(unittest.TestCase):
    def test_no_tool_documents_a_negative_bbox_with_a_space(self):
        # argparse reads '--bbox -6.57,...' as a flag and fails; '--bbox=-6.57,...' is the form that works
        for path in sorted(TOOLS.glob('*.py')):
            with self.subTest(tool=path.name):
                self.assertIsNone(__import__('re').search(r'--bbox\s+-\d', path.read_text(encoding='utf-8')))

    def test_build_map_accepts_the_documented_negative_box(self):
        r = subprocess.run([sys.executable, '-B', str(TOOLS / 'build_map.py'), 'missing.gpkg', 'out.sqlite', f'--bbox={BOX}'],
                           cwd=tempfile.gettempdir(), capture_output=True, text=True)
        self.assertNotIn('expected one argument', r.stderr)     # it fails later, on the missing file, not on the box


class RegionDriverTests(Temp):
    """build_region.py is run with its sub-builders replaced by a recorder, so it checks order, arguments and the map-set file."""
    FILES = {'map': 'derived/geo/national.sqlite', 'terrain': 'derived/geo/terrain.sqlite', 'water': 'derived/geo/water.sqlite',
             'crops': 'derived/geo/crops.sqlite', 'atlas': 'library-data/geography/resources/atlas.sqlite',
             'heights': 'derived/geo/buildings.sqlite', 'places': 'derived/geo/places.sqlite'}

    def build(self, code='GB-SW'):
        import build_region
        calls = []
        out = self.dir / 'regions' / code

        def fake(label, args, env=None):
            calls.append((label, [str(a) for a in args], env or {}))
            if label in self.FILES:
                f = out / self.FILES[label]
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_bytes(b'x' * 10)

        with patch.object(build_region, 'run', fake):
            build_region.build(code, self.dir / 'src', self.dir / 'regions', '2026-11-17T02:05:48Z', '17 Nov 2026', '4')
        return calls, out

    def test_the_builders_run_in_order(self):
        calls, _ = self.build()
        self.assertEqual([c[0] for c in calls], ['map', 'addresses', 'terrain', 'water', 'dams', 'crops', 'atlas', 'heights', 'places'])

    def test_the_box_comes_from_the_proposal_and_a_negative_west_stays_attached_to_its_flag(self):
        calls, _ = self.build('GB-SW')
        boxes = {r['code']: r['bbox']['padded_0_15'] for r in json.loads((REPO / 'docs/regions-uk-proposed.json').read_text(encoding='utf-8'))['regions']}
        want = ','.join(str(v) for v in boxes['GB-SW'])
        self.assertLess(boxes['GB-SW'][0], 0)
        self.assertIn(f'--bbox={want}', calls[0][1])
        self.assertIn(f'--bbox={want}', calls[1][1])

    def test_each_builder_is_pointed_at_this_regions_folder(self):
        calls, out = self.build('GB-LON')
        by = {c[0]: c for c in calls}
        self.assertEqual(by['terrain'][2]['LASTBOOK_TERRAIN_OUT'], str(out / 'derived/geo/terrain.sqlite'))
        self.assertEqual(by['terrain'][2]['LASTBOOK_TERRAIN_SRC'], str(self.dir / 'src' / 'dem'))
        self.assertIn('4', by['terrain'][1])                                    # the worker count
        self.assertEqual(by['water'][2], {'LASTBOOK_GEO': str(out / 'derived/geo'), 'LASTBOOK_UNITS': 'metric'})
        self.assertEqual(by['addresses'][1][2], str(out / 'derived/geo/addresses/GB-LON.sqlite'))
        self.assertEqual(by['places'][1][-2:], ['--area', 'London'])

    def test_the_map_set_file_says_metric_gb_and_lists_every_file_with_its_size(self):
        _, out = self.build()
        m = json.loads((out / 'map-set.json').read_text(encoding='utf-8'))
        self.assertEqual((m['name'], m['units'], m['country'], m['as_of']), ('GB-SW', 'metric', 'GB', '17 Nov 2026'))
        self.assertIn('Copernicus', m['credit'])
        self.assertEqual(len(m['files']), 9)
        self.assertEqual(m['bytes'], sum(m['files'].values()))
        self.assertEqual(m['files']['derived/geo/water.sqlite'], 10)
        self.assertEqual(self.db(out / 'derived/geo/map.sqlite').execute('SELECT count(*) FROM feat').fetchone()[0], 0)
        self.assertEqual((out / 'derived/geo/national-status.json').read_text(encoding='utf-8'), '{"state":"complete"}')

    def test_an_unknown_region_code_is_refused_before_anything_runs(self):
        r = subprocess.run([sys.executable, '-B', str(TOOLS / 'build_region.py'), 'GB-XX', '--src', str(self.dir), '--out', str(self.dir / 'o'),
                            '--as-of', '2026-11-17T02:05:48Z'], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('unknown region code GB-XX', r.stderr)
        self.assertFalse((self.dir / 'o').exists())

    def test_every_code_has_a_box_and_a_name(self):
        import build_region
        codes = {r['code'] for r in json.loads((REPO / 'docs/regions-uk-proposed.json').read_text(encoding='utf-8'))['regions']}
        self.assertTrue(set(build_region.NAMES) <= codes)


if __name__ == '__main__':
    unittest.main()
