#!/usr/bin/env python3
"""Tests for tools/build_region_map.py that need no downloaded map data: cutting the coastline and other features
to a box, closing the sea, choosing a help-point class from raw tags, the region id, and whole builds of a
five-street town written here as OpenStreetMap XML, including builds that fail or are stopped part-way.
Skipped where pyosmium is not installed.

  derived/buildenv/bin/python -B -m unittest tools/test_build_region_map.py
"""
import ast
import argparse
import contextlib
import io
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import build_region_map as b
except ImportError:  # pyosmium is a build-machine package
    b = None

BOX = [0.0, 0.0, 10.0, 10.0]


def area(ring):
    """Signed area: negative for a clockwise ring (y up), which is how a sea polygon must run."""
    return sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(ring, ring[1:])) / 2


@unittest.skipIf(b is None, 'pyosmium is not installed')
class Sea(unittest.TestCase):
    def test_sea_to_the_south(self):
        # the coast runs west to east, so land (left) is north and the sea (right) is south
        pieces = b.clip_line([(-5, 4), (5, 6), (15, 4)], BOX)
        self.assertEqual(len(pieces), 1)
        self.assertEqual(pieces[0][0], (0.0, 5.0))
        self.assertEqual(pieces[0][-1], (10.0, 5.0))
        (ring,) = b.sea_rings(pieces, BOX)
        self.assertEqual(ring[0], ring[-1])
        self.assertIn((10.0, 0.0), ring)
        self.assertIn((0.0, 0.0), ring)
        self.assertNotIn((0.0, 10.0), ring)
        self.assertAlmostEqual(abs(area(ring)), 55.0)
        self.assertLess(area(ring), 0)

    def test_sea_to_the_north(self):
        # the same coast the other way round: the sea is now north
        pieces = b.clip_line([(15, 4), (5, 6), (-5, 4)], BOX)
        (ring,) = b.sea_rings(pieces, BOX)
        self.assertIn((0.0, 10.0), ring)
        self.assertIn((10.0, 10.0), ring)
        self.assertNotIn((0.0, 0.0), ring)
        self.assertAlmostEqual(abs(area(ring)), 45.0)

    def test_two_coasts_make_one_strait(self):
        # land to the north and to the south, sea between them
        north = b.clip_line([(-5, 8), (15, 8)], BOX)   # land on the left: north
        south = b.clip_line([(15, 2), (-5, 2)], BOX)   # land on the left: south
        rings = b.sea_rings(north + south, BOX)
        self.assertEqual(len(rings), 1)
        self.assertAlmostEqual(abs(area(rings[0])), 60.0)

    def test_coast_outside_the_box_is_dropped(self):
        self.assertEqual(b.clip_line([(-5, -5), (-2, -1), (-1, -4)], BOX), [])

    def test_line_crossing_twice_gives_two_pieces(self):
        pieces = b.clip_line([(-1, 5), (5, 5), (5, 12), (7, 12), (7, 5), (12, 5)], BOX)
        self.assertEqual(len(pieces), 2)
        for p in pieces:
            self.assertIsNotNone(b.edge_pos(p[0], BOX))
            self.assertIsNotNone(b.edge_pos(p[-1], BOX))

    def test_chains_join_ways_in_any_order(self):
        ways = [([2, 3], [(1, 0), (2, 0)]), ([1, 2], [(0, 0), (1, 0)]), ([3, 4], [(2, 0), (3, 0)])]
        (chain,) = b.chains(ways)
        self.assertEqual(chain, (False, [(0, 0), (1, 0), (2, 0), (3, 0)]))


@unittest.skipIf(b is None, 'pyosmium is not installed')
class HelpPoints(unittest.TestCase):
    def test_classes(self):
        self.assertEqual(b.poi_class({'amenity': 'hospital'}), 'hospital')
        self.assertEqual(b.poi_class({'amenity': 'toilets'}), 'toilet')
        self.assertEqual(b.poi_class({'amenity': 'townhall'}), 'town_hall')
        self.assertEqual(b.poi_class({'shop': 'bicycle'}), 'bicycle_shop')
        self.assertEqual(b.poi_class({'man_made': 'tower', 'tower:type': 'communication'}), 'comms_tower')
        self.assertIsNone(b.poi_class({'amenity': 'restaurant'}))

    def test_bus_shelters_are_not_shelters(self):
        self.assertIsNone(b.poi_class({'amenity': 'shelter', 'shelter_type': 'public_transport'}))
        self.assertEqual(b.poi_class({'amenity': 'shelter'}), 'shelter')
        self.assertEqual(b.poi_class({'amenity': 'shelter', 'shelter_type': 'weather_shelter'}), 'shelter')

    def test_healthcare_tag_alone(self):
        self.assertEqual(b.poi_class({'healthcare': 'centre'}), 'clinic')
        self.assertEqual(b.poi_class({'healthcare': 'doctor'}), 'doctors')
        self.assertEqual(b.poi_class({'amenity': 'hospital', 'healthcare': 'clinic'}), 'hospital')  # amenity decides
        self.assertIsNone(b.poi_class({'healthcare': 'physiotherapist'}))

    def test_every_class_is_one_build_map_keeps(self):
        text = (Path(__file__).resolve().parent / 'build_map.py').read_text(encoding='utf-8')
        start = text.index('POI_KEEP = {')
        keep = set(ast.literal_eval(text[start + 11:text.index('}', start) + 1]))
        ours = set(b.AMENITY.values()) | set(b.HEALTHCARE.values()) | set(b.SHOP.values()) | set(b.MAN_MADE.values()) | {'comms_tower', 'camp_site', 'spring', 'embassy', 'beach', 'park'}
        self.assertLessEqual(ours, keep)


@unittest.skipIf(b is None, 'pyosmium is not installed')
class Cutting(unittest.TestCase):
    def test_outline_is_cut_to_the_box(self):
        square = [-5, 2, 5, 2, 5, 8, -5, 8, -5, 2]
        (ring,) = b.cut([square], BOX, ring=True)
        self.assertEqual(ring[:2], ring[-2:])
        self.assertEqual((min(ring[0::2]), max(ring[0::2]), min(ring[1::2]), max(ring[1::2])), (0, 5, 2, 8))

    def test_line_is_cut_into_the_pieces_inside(self):
        parts = b.cut([[-1, 5, 5, 5, 5, 12, 7, 12, 7, 5, 12, 5]], BOX, ring=False)
        self.assertEqual(parts, [[0.0, 5.0, 5, 5, 5.0, 10.0], [7.0, 10.0, 7, 5, 10.0, 5.0]])

    def test_feature_inside_is_left_alone(self):
        parts = [[1, 1, 2, 2, 3, 1]]
        self.assertIs(b.cut(parts, BOX, ring=False), parts)

    def test_outline_outside_is_dropped(self):
        self.assertEqual(b.cut([[11, 1, 12, 1, 12, 2, 11, 2, 11, 1]], BOX, ring=True), [])


@unittest.skipIf(b is None, 'pyosmium is not installed')
class BoundaryTest(unittest.TestCase):
    def test_inside_outside_and_hole(self):
        outer = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
        hole = [(4, 4), (4, 6), (6, 6), (6, 4), (4, 4)]
        bd = b.Boundary([outer, hole])
        self.assertTrue(bd.holds(1, 1))
        self.assertTrue(bd.holds(9.5, 9.5))
        self.assertFalse(bd.holds(5, 5))
        self.assertFalse(bd.holds(11, 5))
        self.assertFalse(bd.holds(5, -1))


@unittest.skipIf(b is None, 'pyosmium is not installed')
class RegionId(unittest.TestCase):
    def test_one_folder_name(self):
        for good in ('TH-10', 'BO-L', 'GY', 'CL-RM', 'ca_on.2'):
            self.assertEqual(b.region_id(good), good)

    def test_anything_else_is_refused(self):
        for bad in ('', '.', '..', '../TH-10', 'TH/10', 'TH\\10', '/tmp/x', '.hidden', 'TH-10.', 'TH 10', 'a\0b'):
            with self.assertRaises(argparse.ArgumentTypeError, msg=bad):
                b.region_id(bad)


# A town small enough to read: a boundary relation round the west half of the box, a town label and a hospital inside
# it, a clinic (healthcare=* only) outside it, a road that runs out of the box, a funicular and a cable car.
TOWN = '''<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6" generator="test">
 <node id="1" version="1" lon="1" lat="1"/><node id="2" version="1" lon="5" lat="1"/>
 <node id="3" version="1" lon="5" lat="9"/><node id="4" version="1" lon="1" lat="9"/>
 <node id="10" version="1" lon="3" lat="5"><tag k="place" v="town"/><tag k="name" v="Alder"/></node>
 <node id="11" version="1" lon="3" lat="6"><tag k="amenity" v="hospital"/><tag k="name" v="Alder Hospital"/></node>
 <node id="12" version="1" lon="8" lat="6"><tag k="healthcare" v="centre"/><tag k="name" v="Birch Health Post"/></node>
 <node id="20" version="1" lon="2" lat="5"/><node id="21" version="1" lon="14" lat="5"/>
 <node id="22" version="1" lon="2" lat="3"/><node id="23" version="1" lon="3" lat="3"/>
 <node id="24" version="1" lon="6" lat="3"/><node id="25" version="1" lon="7" lat="4"/>
 <way id="100" version="1"><nd ref="1"/><nd ref="2"/><nd ref="3"/><nd ref="4"/><nd ref="1"/></way>
 <way id="101" version="1"><nd ref="20"/><nd ref="21"/><tag k="highway" v="primary"/><tag k="name" v="Long Road"/></way>
 <way id="102" version="1"><nd ref="22"/><nd ref="23"/><tag k="railway" v="funicular"/></way>
 <way id="103" version="1"><nd ref="24"/><nd ref="25"/><tag k="aerialway" v="gondola"/></way>
 <relation id="500" version="1"><member type="way" ref="100" role="outer"/>
  <tag k="type" v="boundary"/><tag k="boundary" v="administrative"/><tag k="name" v="Alder District"/></relation>
</osm>
'''


@unittest.skipIf(b is None, 'pyosmium is not installed')
class Build(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.src = self.dir / 'town.osm'
        self.src.write_text(TOWN, encoding='utf-8')
        self.out = self.dir / 'regions'

    def run_build(self, *extra, region='XX-1'):
        argv = [str(self.src), '--id', region, '--name', 'Alder District', '--bbox', '0,0,10,10', '--out', str(self.out), *extra]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            b.main(argv)

    def left_in_out(self):
        return sorted(p.name for p in self.out.iterdir()) if self.out.exists() else []

    def test_build_publishes_the_map_and_its_report(self):
        self.run_build('--boundary', '500')
        self.assertEqual(self.left_in_out(), ['XX-1', 'XX-1.build.json'])
        root = self.out / 'XX-1'
        info = json.loads((root / 'map-set.json').read_text(encoding='utf-8'))
        self.assertEqual(info['name'], 'XX-1')
        for rel, size in info['files'].items():
            self.assertEqual((root / rel).stat().st_size, size)
        report = json.loads((self.out / 'XX-1.build.json').read_text(encoding='utf-8'))
        self.assertEqual(report['features'], {'rail': 2, 'road': 1, 'place': 1})
        self.assertEqual(report['help_points'], {'clinic': 1, 'hospital': 1})
        self.assertEqual(report['boundary'], {'relation': 500, 'place_finder_rows_inside': 2, 'place_finder_rows_outside': 1})
        db = sqlite3.connect(root / 'derived' / 'geo' / 'national.sqlite')
        self.assertEqual(db.execute("SELECT MAX(maxx) FROM feat_idx").fetchone()[0], 10.0)  # Long Road stops at the box
        self.assertEqual({r[0] for r in db.execute("SELECT cls FROM feat WHERE layer='rail'")}, {'funicular', 'gondola'})
        pl = sqlite3.connect(root / 'derived' / 'geo' / 'places.sqlite')
        detail = dict(pl.execute('SELECT name, detail FROM place'))
        self.assertEqual(detail['Alder Hospital'], 'Alder District (OpenStreetMap)')
        self.assertEqual(detail['Birch Health Post'], 'OpenStreetMap')  # outside the boundary: not named as in it

    def test_without_a_boundary_every_row_names_the_region(self):
        self.run_build()
        pl = sqlite3.connect(self.out / 'XX-1' / 'derived' / 'geo' / 'places.sqlite')
        self.assertEqual({r[0] for r in pl.execute('SELECT detail FROM place')}, {'Alder District (OpenStreetMap)'})

    def test_same_input_gives_the_same_bytes(self):
        self.run_build()
        first, self.out = self.out, self.dir / 'again'
        self.run_build()
        one = json.loads((first / 'XX-1.build.json').read_text(encoding='utf-8'))['files']
        two = json.loads((self.out / 'XX-1.build.json').read_text(encoding='utf-8'))['files']
        self.assertEqual(one, two)

    def test_failed_build_leaves_nothing_and_can_be_retried(self):
        # the map file is already written when the place finder fails
        with mock.patch.object(b, 'write_places', side_effect=RuntimeError('disk full')):
            with self.assertRaises(RuntimeError):
                self.run_build()
        self.assertEqual(self.left_in_out(), [])
        self.run_build()
        self.assertEqual(self.left_in_out(), ['XX-1', 'XX-1.build.json'])

    def test_interrupted_build_leaves_nothing_and_can_be_retried(self):
        for stop in (KeyboardInterrupt, SystemExit(143)):  # Ctrl-C, and kill (the SIGTERM handler exits)
            with mock.patch.object(b, 'write_places', side_effect=stop):
                with self.assertRaises((KeyboardInterrupt, SystemExit)):
                    self.run_build()
            self.assertEqual(self.left_in_out(), [])
        self.run_build()
        self.assertEqual(self.left_in_out(), ['XX-1', 'XX-1.build.json'])

    def test_missing_boundary_stops_the_build_and_leaves_nothing(self):
        with self.assertRaises(SystemExit):
            self.run_build('--boundary', '999')  # no such relation: the build stops after reading
        self.assertEqual(self.left_in_out(), [])

    def test_existing_map_is_refused_and_left_alone(self):
        self.run_build()
        before = {p: p.stat().st_mtime_ns for p in (self.out / 'XX-1').rglob('*') if p.is_file()}
        with self.assertRaises(SystemExit):
            self.run_build()
        self.assertEqual(before, {p: p.stat().st_mtime_ns for p in (self.out / 'XX-1').rglob('*') if p.is_file()})
        self.assertEqual(self.left_in_out(), ['XX-1', 'XX-1.build.json'])

    def test_id_that_is_a_path_is_refused_before_anything_is_written(self):
        with self.assertRaises(SystemExit):
            self.run_build(region='../escape')
        self.assertFalse(self.out.exists())
        self.assertFalse((self.dir / 'escape').exists())


if __name__ == '__main__':
    unittest.main()
