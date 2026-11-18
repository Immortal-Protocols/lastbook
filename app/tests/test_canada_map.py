"""Portable, offline Canada map regressions; all fixture objects are invented.

python3 -B -m unittest app.tests.test_canada_map
The real OSM parser fixture additionally needs build-only osmium==4.3.2.
"""

from contextlib import ExitStack, closing, redirect_stdout
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import server
from engine.map_regions import CANADA_BOUNDS, CANADA_REGIONS, canada_info
from tools import build_canada_map as builder
from tools.merge_canada_places import digest, merge
from tools.validate_canada_map import validate

ROOT = Path(__file__).resolve().parents[2]
META = {
    'source': 'OpenStreetMap contributors via Geofabrik Canada (ODbL 1.0)',
    'source_sha256': 'a' * 64,
    'data_as_of': '2025-01-02T00:00:00Z',
    'bounds': '-141,41,-52,84',
}


def make_databases(root):
    mpath, ppath = root / 'canada.sqlite', root / 'canada-places.sqlite'
    db, pdb = sqlite3.connect(mpath), sqlite3.connect(ppath)
    db.executescript(builder.SCHEMA)
    pdb.executescript(builder.PSCHEMA)
    parts = [[(-80.1, 45.0), (-80.0, 45.1)]]
    db.execute(
        'INSERT INTO feat VALUES(1,?,?,?,?,?)',
        ('road', 'primary', 'Fixture Road', 8, builder.pack(parts)),
    )
    db.execute('INSERT INTO feat_idx VALUES(1,?,?,?,?,8,30)', builder.bbox(parts))
    db.execute("INSERT INTO feature_osm VALUES(1,'way',1)")
    db.execute("INSERT INTO poi VALUES(1,'hospital','Fixture Hospital',-80,45)")
    db.execute("INSERT INTO poi_osm VALUES(1,'node',2)")
    db.execute('CREATE INDEX poi_cls ON poi(cls,lon,lat)')
    pdb.execute(
        "INSERT INTO place VALUES(1,'Fixture Town','town','Canada',45,-80,1,'OpenStreetMap Canada')"
    )
    pdb.execute("INSERT INTO place_osm VALUES(1,'node',3)")
    pdb.execute("INSERT INTO place_fts(place_fts) VALUES('rebuild')")
    for conn in (db, pdb):
        conn.executemany('INSERT INTO meta VALUES(?,?)', META.items())
        conn.commit()
        conn.close()
    return mpath, ppath


class CanadaRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        geo = self.root / 'derived' / 'geo'
        geo.mkdir(parents=True)
        self.map, self.places = make_databases(geo)
        self.stack = ExitStack()
        for key, value in {
            'HERE': self.root,
            'LIB': self.root / 'library-data',
            'CANADADB': self.map,
            'MAPDB': geo / 'map.sqlite',
            'PLACEDB': self.places,
            '_tls': __import__('threading').local(),
        }.items():
            self.stack.enter_context(patch.object(server, key, value))
        for name in ('map_contents', '_map_tile', '_pins', 'socal_classes'):
            getattr(server, name).cache_clear()

    def tearDown(self):
        for value in vars(server._tls).values():
            if isinstance(value, sqlite3.Connection):
                value.close()
        self.stack.close()
        self.temp.cleanup()

    def tile(self, lat, lon, zoom=12):
        x = int((lon + 180) / 360 * 2**zoom)
        y = int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * 2**zoom)
        return json.loads(server._map_tile(zoom, x, y, 'fixture'))

    def test_canada_only_tiles_metadata_pins_near_and_place_search(self):
        self.assertTrue(self.tile(45.02, -80.08)['layers']['road'])
        info = server.map_info()
        self.assertTrue(info['detail'])
        self.assertEqual(len(info['canada']['regions']), 13)
        self.assertEqual(info['canada']['data_as_of'], META['data_as_of'])
        self.assertEqual(
            server.places('Fixture Town')[0]['source'], 'OpenStreetMap Canada'
        )
        self.assertTrue(server.places('Fixture Town')[0]['onMap'])
        pins = server.pins(-81, 44, -79, 46, 14, ['hospital'])
        self.assertEqual(pins['sites'], 1)
        self.assertIn(META['data_as_of'], pins['points'][0]['source'])
        near = server.near(45, -80, ['hospital'], 1)
        self.assertEqual(near[0]['km'], 0)
        self.assertIn(META['data_as_of'], near[0]['source'])

    def test_metadata_missing_fields_and_invalid_bounds(self):
        for raw in ({}, {'bounds': 'nan,41,-52,84'}, {'bounds': 'bad'}):
            result = canada_info(raw)
            self.assertIsNone(result['bounds'])
            self.assertEqual(result['data_as_of'], 'unknown')
            self.assertGreater(result['overview_bounds'][3], 83)
        self.assertEqual(len({key for key, _, _ in CANADA_REGIONS}), 13)

    def test_canada_overview_bounds_clamp_single_province_and_full_country(self):
        ontario = canada_info({'bounds': '-95.1596,41.6601,-74.31,57.5083'})
        self.assertEqual(ontario['overview_bounds'], [-95.1596, 41.6601, -74.31, 57.5083])
        pei = canada_info({'bounds': '-64.6024,45.825,-61.2488,47.6857'})
        self.assertEqual(pei['overview_bounds'], [-64.6024, 45.825, -61.2488, 47.6857])
        full_overshoot = canada_info({'bounds': '-145.0,40.5,-50.0,85.0'})
        self.assertEqual(full_overshoot['overview_bounds'], list(CANADA_BOUNDS))
        bc_overshoot = canada_info({'bounds': '-145.0,48.0,-114.0,60.5'})
        self.assertEqual(bc_overshoot['overview_bounds'], [CANADA_BOUNDS[0], 48.0, -114.0, 60.5])
        for raw in ({'bounds': '10,10,20,20'}, {'bounds': '-80,45,-80,45'}):
            self.assertEqual(canada_info(raw)['overview_bounds'], list(CANADA_BOUNDS))

    def test_unrestricted_library_without_pack_or_canada_keeps_legacy_layers_contract(
        self,
    ):
        with patch.object(server, 'pack_info', return_value=None), patch.object(
            server, 'canada_mapdb', return_value=None
        ):
            self.assertNotIn('layers', server.map_info())

    def test_country_view_padding_beyond_mercator_extent_is_bounded(self):
        # Mobile full-country fitting includes ocean far south of Canada and
        # padding above the projection's latitude limit. It is a valid view.
        with patch.object(server, 'resource_dbs', return_value=[]):
            result = server.pins(
                -173,
                -29,
                -21,
                89,
                2,
                ['hospital', 'clinic', 'reservoir', 'lake', 'fish_stocking'],
            )
        self.assertEqual(result['sites'], 1)
        self.assertTrue(result['points'])
        self.assertTrue(
            all(math.isfinite(value) and value > 0 for value in result['cell'])
        )

    def test_standalone_and_mixed_place_sources_are_reported_from_records(self):
        standalone = server.map_info()['datasets']
        labels = [item['label'] for item in standalone]
        self.assertTrue(any('OpenStreetMap Canada' in label for label in labels))
        self.assertFalse(any('GNIS' in label or 'Census' in label for label in labels))
        pack_labels = [
            item['label'] for item in server.pack_datasets(server.map_contents())
        ]
        self.assertFalse(
            any('GNIS' in label or 'Census' in label for label in pack_labels)
        )
        with closing(sqlite3.connect(self.places)) as db, db:
            db.execute(
                "INSERT INTO place VALUES(2,'Fixture US Town','town','US',40,-90,1,'USGS GNIS')"
            )
        server._place_dataset.cache_clear()
        mixed = server.place_dataset()['label']
        self.assertIn('OpenStreetMap Canada', mixed)
        self.assertIn('USGS GNIS', mixed)
        self.assertNotIn('Census', mixed)

    def test_country_resource_plan_uses_kind_index_with_identical_counts_and_sources(
        self,
    ):
        atlas = self.root / 'atlas.sqlite'
        with closing(sqlite3.connect(atlas)) as db, db:
            db.executescript(
                '''CREATE TABLE resource(id INTEGER PRIMARY KEY,kind TEXT,name TEXT,
                lat REAL,lon REAL,detail TEXT,source TEXT,source_id TEXT);
                CREATE INDEX resource_kind ON resource(kind);
                CREATE VIRTUAL TABLE spatial USING rtree(id,minx,maxx,miny,maxy);'''
            )
            rows = [
                (
                    1,
                    'fish_stocking',
                    'Fixture Lake',
                    45,
                    -80,
                    '{}',
                    'Fixture fish records',
                    'f1',
                ),
                (
                    2,
                    'fish_stocking',
                    'Fixture Lake',
                    45,
                    -80,
                    '{}',
                    'Fixture fish records',
                    'f2',
                ),
                (
                    3,
                    'boat_launch',
                    'Fixture Launch',
                    48,
                    -125,
                    '{}',
                    'Fixture boat records',
                    'b1',
                ),
                (
                    4,
                    'boat_launch',
                    'Outside View',
                    20,
                    30,
                    '{}',
                    'Fixture boat records',
                    'b2',
                ),
            ] + [
                (
                    i,
                    'mineral',
                    'Other kind',
                    45,
                    -80,
                    '{}',
                    'Fixture mineral records',
                    str(i),
                )
                for i in range(5, 505)
            ]
            db.executemany('INSERT INTO resource VALUES(?,?,?,?,?,?,?,?)', rows)
            db.executemany(
                'INSERT INTO spatial VALUES(?,?,?,?,?)',
                [(r[0], r[4], r[4], r[3], r[3]) for r in rows],
            )
        args = (
            -173,
            -29,
            -21,
            85,
            20,
            15,
            ('boat_launch', 'fish_stocking'),
            'resource-plan-fixture',
        )
        original_connect = sqlite3.connect
        queries = []

        def connect(*a, **kw):
            db = original_connect(*a, **kw)
            db.set_trace_callback(queries.append)
            return db

        with patch.object(server, 'resource_dbs', return_value=[atlas]):
            with patch.object(
                server,
                '_resource_pin_from',
                return_value='spatial s CROSS JOIN resource r ON r.id=s.id',
            ):
                before = server._pins(*args)
            server._pins.cache_clear()
            with patch.object(server.sqlite3, 'connect', side_effect=connect):
                after = server._pins(*args)
        self.assertEqual(after, before)
        self.assertEqual(after['sites'], 2)  # two stocking records remain one site
        self.assertEqual(sum(p['records'] for p in after['points']), 3)
        query = next(q for q in queries if q.startswith('SELECT r.kind,COUNT'))
        with closing(original_connect(atlas)) as db:
            plan = [row[3] for row in db.execute('EXPLAIN QUERY PLAN ' + query)]
        self.assertTrue(
            any('SEARCH r USING INDEX resource_kind' in line for line in plan), plan
        )
        self.assertEqual(
            server._resource_pin_from(0.01),
            'spatial s CROSS JOIN resource r ON r.id=s.id',
        )

    def test_us_remains_available_alongside_canada(self):
        national = self.map.parent / 'national.sqlite'
        shutil.copyfile(self.map, national)
        with closing(sqlite3.connect(national)) as db, db:
            db.execute("UPDATE feat SET name='US Fixture Road'")
        names = [row[1] for row in self.tile(45.02, -80.08)['layers']['road']]
        self.assertIn('Fixture Road', names)
        self.assertIn('US Fixture Road', names)
        # Exact cross-extract duplicates must not double the service count.
        self.assertEqual(server.pins(-81, 44, -79, 46, 14, ['hospital'])['sites'], 1)

    def test_date_line_segments_do_not_cross_the_world(self):
        parts = [[(179.9, 60), (-179.9, 60)]]
        with closing(sqlite3.connect(self.map)) as db, db:
            db.execute('UPDATE feat SET geom=?', (builder.pack(parts),))
            db.execute('UPDATE feat_idx SET minx=-179.9,maxx=179.9,miny=60,maxy=60')
        for lon in (179.95, -179.95, 0):
            road = self.tile(60, lon, 10)['layers']['road'][0][2][0]
            self.assertLess(abs(road[-2] - road[0]), 512)

    def test_arctic_nearest_search_and_date_line_distance_caps(self):
        # No arbitrary 140 km cutoff: sparse northern records remain findable.
        near = server.near(75, -100, ['hospital'], 1)
        self.assertEqual(near[0]['name'], 'Fixture Hospital')
        self.assertGreater(near[0]['km'], 140)
        for lon in (-179.9, 179.9):
            boxes = server._distance_boxes(70, lon, 100)
            self.assertEqual(len(boxes), 2)
            self.assertTrue(all(-180 <= b[0] <= b[2] <= 180 for b in boxes))

    def test_geographic_place_candidates_survive_rank_limit(self):
        with closing(sqlite3.connect(self.places)) as db, db:
            db.executemany(
                'INSERT INTO place(name,kind,detail,lat,lon,rank,source) VALUES(?,?,?,?,?,?,?)',
                [('Fixture Clinic', 'clinic', 'US', 30, -110, 1, 'OSM')] * 250
                + [
                    (
                        'Fixture Clinic',
                        'clinic',
                        'Canada',
                        45,
                        -80,
                        4,
                        'OpenStreetMap Canada',
                    )
                ],
            )
            db.execute("INSERT INTO place_fts(place_fts) VALUES('rebuild')")
        result = server.places('Fixture Clinic', near=(45, -80))
        self.assertEqual(result[0]['source'], 'OpenStreetMap Canada')

    def test_unaccented_montreal_and_quebec_rank_by_diacritic_fold_and_proximity(self):
        with closing(sqlite3.connect(self.places)) as db, db:
            db.executemany(
                'INSERT INTO place(name,kind,detail,lat,lon,rank,source) VALUES(?,?,?,?,?,?,?)',
                [
                    ('Montréal', 'city', 'Quebec, Canada (OpenStreetMap)', 45.5017, -73.5673, 1, 'OpenStreetMap Canada'),
                    ('Montreal', 'city', 'Quebec, Canada (OpenStreetMap)', 45.5019, -73.5671, 4, 'OpenStreetMap Canada'),
                    ('Montreal', 'town', 'Missouri', 37.967, -92.676, 3, 'USGS GNIS'),
                    ('Montreal', 'city', 'Wisconsin', 46.428, -90.243, 3, 'USGS GNIS'),
                    ('Montreal River', 'river', 'Canada', 47.2, -84.6, 4, 'OpenStreetMap Canada'),
                    ('Québec', 'city', 'Quebec, Canada (OpenStreetMap)', 46.8139, -71.2080, 1, 'OpenStreetMap Canada'),
                    ('Quebec', 'town', 'Louisiana', 32.429, -91.326, 3, 'USGS GNIS'),
                    ('Lake Louise', 'water', 'Alberta, Canada (OpenStreetMap)', 51.4254, -116.1773, 4, 'OpenStreetMap Canada'),
                ],
            )
            db.execute("INSERT INTO place_fts(place_fts) VALUES('rebuild')")
        with patch.object(server, 'home_area', return_value=None):
            near_qc = server.places('Montreal', near=(45.502, -73.567))
            self.assertEqual(near_qc[0]['name'], 'Montréal')
            self.assertEqual(near_qc[0]['source'], 'OpenStreetMap Canada')
            # Folded dedup collapses accented/unaccented variants at the same spot without dropping US homonyms.
            qc_spot = [p for p in near_qc if round(p['lat'], 2) == 45.50 and round(p['lon'], 2) == -73.57]
            self.assertEqual(len(qc_spot), 1)
            near_mo = server.places('Montreal', near=(37.967, -92.676))
            self.assertEqual(near_mo[0]['detail'], 'Missouri')
            self.assertEqual(near_mo[0]['source'], 'USGS GNIS')
            near_wi = server.places('Montreal', near=(46.428, -90.243))
            self.assertEqual(near_wi[0]['detail'], 'Wisconsin')
            self.assertEqual(near_wi[0]['source'], 'USGS GNIS')
            no_near = server.places('Montreal', near=None)
            self.assertEqual(no_near[0]['name'], 'Montréal')
            self.assertEqual(no_near[0]['source'], 'OpenStreetMap Canada')
            self.assertEqual(server.places('Quebec', near=(46.814, -71.208))[0]['name'], 'Québec')
            self.assertEqual(server.places('Quebec', near=(32.429, -91.326))[0]['detail'], 'Louisiana')
            self.assertEqual(server.places('---'), [])
            water_db = self.root / 'derived' / 'geo' / 'water.sqlite'
            with closing(sqlite3.connect(water_db)) as wdb, wdb:
                wdb.executescript(
                    '''CREATE TABLE resource(id INTEGER PRIMARY KEY,kind TEXT,name TEXT,lat REAL,lon REAL,detail TEXT);
                    CREATE VIRTUAL TABLE water_fts USING fts5(name,detail,content='resource',content_rowid='id',tokenize='unicode61');'''
                )
                wdb.execute(
                    "INSERT INTO resource VALUES(1,'lake','Lake Louise',30.8,-83.2,'{\"state\":\"GA\"}')"
                )
                wdb.execute(
                    "INSERT INTO resource VALUES(2,'dam','Lake Louise Dam',34.0,-118.0,'{\"state\":\"CA\"}')"
                )
                wdb.execute("INSERT INTO water_fts(water_fts) VALUES('rebuild')")
            with patch.object(server, 'WATERDB', water_db):
                self.assertEqual(
                    server.places('Lake Louise', near=(51.425, -116.177))[0]['source'],
                    'OpenStreetMap Canada',
                )
                self.assertEqual(
                    server.places('Lake Louise', near=(30.8, -83.2))[0]['source'],
                    'water',
                )


class CanadaBuildToolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.map, self.places = make_databases(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_validator_is_read_only_and_rejects_broken_lineage(self):
        before = digest(self.map), digest(self.places)
        self.assertEqual(validate(self.map, self.places, True)['geometry_checked'], 1)
        self.assertEqual(before, (digest(self.map), digest(self.places)))
        with closing(sqlite3.connect(self.map)) as db, db:
            db.execute('DELETE FROM feature_osm')
        with self.assertRaisesRegex(ValueError, 'count differs'):
            validate(self.map, self.places)

    def test_owned_sqlite_scratch_precedes_connections_and_restores_environment(self):
        original_connect = sqlite3.connect
        out = self.root / 'scratch-fixture'
        out.mkdir()
        scratch = (out / 'sqlite-tmp').resolve()
        with patch.dict(
            os.environ,
            {
                'SQLITE_TMPDIR': '/unused-caller-scratch',
                'TMPDIR': '/unused-caller-temp',
            },
        ):
            with builder.sqlite_scratch(out):
                self.assertEqual(os.environ['SQLITE_TMPDIR'], str(scratch))
                self.assertEqual(os.environ['TMPDIR'], str(scratch))
                with closing(original_connect(out / 'fixture.sqlite')) as db, db:
                    db.execute('PRAGMA temp_store=FILE')
                    self.assertEqual(db.execute('PRAGMA temp_store').fetchone(), (1,))
                    db.execute('CREATE TEMP TABLE spill(payload BLOB)')
                    db.execute('INSERT INTO spill VALUES(randomblob(4000000))')
                    self.assertEqual(
                        db.execute('SELECT length(payload) FROM spill').fetchone(),
                        (4000000,),
                    )
                if os.name != 'nt':
                    self.assertEqual(scratch.stat().st_mode & 0o777, 0o700)
            self.assertEqual(os.environ['SQLITE_TMPDIR'], '/unused-caller-scratch')
            self.assertEqual(os.environ['TMPDIR'], '/unused-caller-temp')

    def test_disk_preflight_and_exhausted_temp_error_are_explicit(self):
        source = self.root / 'source.osm.pbf'
        source.write_bytes(b'fixture')
        with patch.object(
            builder.shutil, 'disk_usage', return_value=SimpleNamespace(free=0)
        ):
            with self.assertRaisesRegex(
                ValueError, 'Insufficient output/SQLite temporary disk space'
            ):
                builder.disk_preflight(source, self.root, 'sparse_file_array')
        with patch.object(
            builder.shutil,
            'disk_usage',
            return_value=SimpleNamespace(free=10 * builder.GIB),
        ):
            self.assertEqual(
                builder.disk_preflight(source, self.root, 'sparse_mem_array'),
                builder.GIB,
            )
            self.assertEqual(
                builder.disk_preflight(source, self.root, 'sparse_file_array', 3),
                3 * builder.GIB,
            )
        message = builder.storage_error(
            OSError(28, 'No space left on device'), self.root / 'new-build'
        )
        self.assertIn('sqlite-tmp', message)
        self.assertIn('NEW staging directory', message)

    def test_merge_preserves_base_and_refuses_rerun_overwrite_or_augmented_base(self):
        base = self.root / 'base.sqlite'
        shutil.copyfile(self.places, base)
        with closing(sqlite3.connect(base)) as db, db:
            db.execute("UPDATE place SET source='USGS GNIS',detail='Example State'")
            db.execute('DELETE FROM meta')
            db.execute("INSERT INTO place_fts(place_fts) VALUES('rebuild')")
        trusted = digest(base)
        args = SimpleNamespace(
            base=base,
            incoming=self.places,
            dest=self.root / 'merged.sqlite',
            base_sha256=trusted,
            canada_map=None,
        )
        self.assertEqual(merge(args)['total'], 2)
        self.assertEqual(digest(base), trusted)
        with self.assertRaisesRegex(ValueError, 'already exists'):
            merge(args)
        args.base, args.dest = args.dest, self.root / 'again.sqlite'
        args.base_sha256 = digest(args.base)
        with self.assertRaisesRegex(ValueError, 'not pristine'):
            merge(args)
        self.assertFalse(args.dest.exists())

    def test_optional_canada_pack_file_keeps_scanner_protections(self):
        spec = importlib.util.spec_from_file_location(
            'canada_pack_scan', ROOT / 'packaging/scan_pack.py'
        )
        scan_pack = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(scan_pack)
        scan = scan_pack.Scan(self.root, ['private-fixture-token'], {}, None)
        rel = 'derived/geo/canada.sqlite'
        scan.name_rules(rel, self.map.stat(), False)
        scan.inspect_map(rel, self.map)
        self.assertFalse(scan.fails)
        with closing(sqlite3.connect(self.map)) as db, db:
            db.execute("INSERT INTO meta VALUES('control','private-fixture-token')")
        scan.inspect_map(rel, self.map)
        self.assertIn('term.map', scan.fails)
        scan.name_rules(rel + '-wal', self.map.stat(), False)
        self.assertIn('file.excluded_name', scan.fails)
        scan.name_rules(rel + '.building', self.map.stat(), False)
        self.assertIn('file.not_allowed_here', scan.fails)

    @unittest.skipUnless(
        importlib.util.find_spec('osmium'), 'build-only osmium is not installed'
    )
    def test_real_parser_multipolygon_hole_unicode_fts_and_source_hash(self):
        # Coordinates are invented fixture geometry, not household data.
        xml = '''<osm version="0.6" generator="lastbook-test">
<node id="1" lat="45" lon="-80"><tag k="place" v="town"/><tag k="name" v="Fixture Town"/><tag k="addr:province" v="Ontario"/></node>
<node id="2" lat="45.1" lon="-80"/><node id="3" lat="45.1" lon="-79.9"/><node id="4" lat="45" lon="-79.9"/>
<node id="5" lat="45.02" lon="-79.98"/><node id="6" lat="45.08" lon="-79.98"/><node id="7" lat="45.08" lon="-79.92"/><node id="8" lat="45.02" lon="-79.92"/>
<node id="9" lat="45.01" lon="-79.99"><tag k="amenity" v="hospital"/><tag k="name" v="École Fixture"/></node>
<way id="1"><nd ref="1"/><nd ref="2"/><tag k="highway" v="primary_link"/></way>
<way id="10"><nd ref="1"/><nd ref="2"/><nd ref="3"/></way>
<way id="11"><nd ref="3"/><nd ref="4"/><nd ref="1"/></way>
<way id="12"><nd ref="5"/><nd ref="6"/><nd ref="7"/><nd ref="8"/><nd ref="5"/></way>
<relation id="20"><member type="way" ref="10" role="outer"/><member type="way" ref="11" role="outer"/><member type="way" ref="12" role="inner"/><tag k="type" v="multipolygon"/><tag k="natural" v="water"/><tag k="name" v="Fixture Lake"/></relation></osm>'''
        source = self.root / 'fixture.osm'
        source.write_text(xml, encoding='utf-8')
        import osmium

        pbf = self.root / 'fixture.osm.pbf'
        with osmium.SimpleWriter(str(pbf)) as writer:

            class Copy(osmium.SimpleHandler):
                def node(self, obj):
                    writer.add_node(obj)

                def way(self, obj):
                    writer.add_way(obj)

                def relation(self, obj):
                    writer.add_relation(obj)

            Copy().apply_file(str(source))
        source = pbf
        target = self.root / 'built'
        command = [
            sys.executable,
            str(ROOT / 'tools/build_canada_map.py'),
            str(source),
            str(target),
            '--source-sha256',
            digest(source),
            '--data-date',
            META['data_as_of'],
            '--node-index',
            'sparse_mem_array',
        ]
        subprocess.run(command, check=True, capture_output=True, text=True, encoding='utf-8')
        mpath, ppath = (
            target / 'canada-map.sqlite.building',
            target / 'canada-places.sqlite.building',
        )
        self.assertEqual(validate(mpath, ppath, True)['pois'], 1)
        with closing(sqlite3.connect(mpath)) as db, db:
            rings = server.unpack(
                db.execute("SELECT geom FROM feat WHERE layer='water'").fetchone()[0]
            )
            self.assertEqual(len(rings), 2)
            self.assertTrue(
                all(len(ring) == 5 and ring[0] == ring[-1] for ring in rings)
            )
            self.assertEqual(
                db.execute("SELECT minz FROM feat WHERE cls='primary_link'").fetchone()[
                    0
                ],
                12,
            )
        with closing(sqlite3.connect(ppath)) as db, db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) FROM place_fts WHERE place_fts MATCH 'ecole'"
                ).fetchone()[0],
                1,
            )
        with closing(sqlite3.connect(mpath)) as db:
            meta = dict(db.execute('SELECT key,value FROM meta'))
        self.assertEqual(meta['node_index'], 'sparse_mem_array')
        self.assertEqual(meta['sqlite_temp'], 'staging/sqlite-tmp')
        self.assertTrue((target / 'sqlite-tmp').is_dir())
        file_target = self.root / 'built-file-index'
        command[3] = str(file_target)
        command[-1] = 'sparse_file_array'
        connections = []
        original_connect = sqlite3.connect

        def connect(*a, **kw):
            scratch = str((file_target / 'sqlite-tmp').resolve())
            self.assertEqual(os.environ.get('SQLITE_TMPDIR'), scratch)
            self.assertEqual(os.environ.get('TMPDIR'), scratch)
            connections.append(a[0])
            return original_connect(*a, **kw)

        with patch.object(sys, 'argv', command[1:]), patch.object(
            builder.sqlite3, 'connect', side_effect=connect
        ), redirect_stdout(io.StringIO()):
            builder.main()
        self.assertEqual(len(connections), 2)
        other_map = file_target / 'canada-map.sqlite.building'
        other_places = file_target / 'canada-places.sqlite.building'
        self.assertEqual(validate(other_map, other_places, True)['pois'], 1)
        self.assertTrue((file_target / 'node-locations.idx').is_file())
        with closing(sqlite3.connect(mpath)) as first, closing(
            sqlite3.connect(other_map)
        ) as second:
            for table in ('feat', 'feat_idx', 'feature_osm', 'poi', 'poi_osm'):
                self.assertEqual(
                    first.execute(f'SELECT * FROM {table}').fetchall(),
                    second.execute(f'SELECT * FROM {table}').fetchall(),
                )
        with closing(sqlite3.connect(ppath)) as first, closing(
            sqlite3.connect(other_places)
        ) as second:
            for table in ('place', 'place_osm'):
                self.assertEqual(
                    first.execute(f'SELECT * FROM {table}').fetchall(),
                    second.execute(f'SELECT * FROM {table}').fetchall(),
                )
        command[3] = str(self.root / 'missing-index-mode')
        no_mode = subprocess.run(command[:-2], capture_output=True, text=True, encoding='utf-8')
        self.assertNotEqual(no_mode.returncode, 0)
        self.assertIn('--node-index', no_mode.stderr)
        self.assertFalse((self.root / 'missing-index-mode').exists())
        command[3] = str(self.root / 'bad-hash')
        command[5] = '0' * 64
        self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
        self.assertFalse((self.root / 'bad-hash').exists())

    def test_windows_portability_resource_fsync_and_utf8(self):
        with patch.object(builder, 'resource', None):
            self.assertIsNone(builder.peak_rss_kib())
        sample = self.root / 'utf8-progress.json'
        builder.atomic_json(sample, {'place': 'Montréal', 'school': 'École Fixture'})
        self.assertEqual(
            json.loads(sample.read_text(encoding='utf-8')),
            {'place': 'Montréal', 'school': 'École Fixture'},
        )
        base = self.root / 'win-base.sqlite'
        shutil.copyfile(self.places, base)
        with closing(sqlite3.connect(base)) as db, db:
            db.execute("UPDATE place SET source='USGS GNIS',detail='Example State'")
            db.execute('DELETE FROM meta')
            db.execute("INSERT INTO place_fts(place_fts) VALUES('rebuild')")
        trusted = digest(base)
        building_map = self.root / 'canada-map.sqlite.building'
        shutil.copyfile(self.map, building_map)
        with self.assertRaisesRegex(ValueError, 'Canada map must be finished'):
            merge(
                SimpleNamespace(
                    base=base,
                    incoming=self.places,
                    dest=self.root / 'reject-building.sqlite',
                    base_sha256=trusted,
                    canada_map=building_map,
                )
            )
        fsync_modes = []
        original_open = Path.open

        def tracking_open(path_self, mode='r', *a, **kw):
            handle = original_open(path_self, mode, *a, **kw)
            if path_self.name.endswith('.staging'):
                fsync_modes.append(mode)
            return handle

        with patch.object(Path, 'open', tracking_open):
            receipt = merge(
                SimpleNamespace(
                    base=base,
                    incoming=self.places,
                    dest=self.root / 'win-merged.sqlite',
                    base_sha256=trusted,
                    canada_map=None,
                )
            )
        self.assertEqual(receipt['total'], 2)
        self.assertEqual(fsync_modes, ['r+b'])

    @unittest.skipUnless(shutil.which('node'), 'node is not installed')
    def test_map_js_nearby_refresh_and_canadian_empty_state(self):
        script = r'''
const fs = require('fs');
const vm = require('vm');
const mapSrc = fs.readFileSync(process.argv[1], 'utf8');

function makeClassList() {
  const s = new Set();
  return {
    add: (...a) => a.forEach(x => s.add(x)),
    remove: (...a) => a.forEach(x => s.delete(x)),
    toggle: (x, f) => (f === undefined ? (s.has(x) ? s.delete(x) : s.add(x)) : (f ? s.add(x) : s.delete(x))),
    contains: x => s.has(x),
  };
}

function makeEl(id = '', tag = 'div') {
  const el = {
    id, tagName: tag.toUpperCase(), hidden: false, value: '', textContent: '', _innerHTML: '',
    style: { setProperty() {} }, dataset: {}, children: [],
    classList: makeClassList(),
    _listeners: {},
    addEventListener(ev, fn) { (this._listeners[ev] ||= []).push(fn); },
    removeEventListener() {},
    setAttribute() {},
    focus() {},
    scrollIntoView() {},
    remove() {},
    append() {},
    insertBefore() {},
    closest() { return makeEl('sec', 'section'); },
    getBoundingClientRect() { return { left: 0, top: 0, right: 800, bottom: 600, width: 800, height: 600 }; },
    clientWidth: 800, clientHeight: 600, offsetWidth: 100, offsetHeight: 40, scrollHeight: 100, scrollTop: 0,
    getContext() {
      return {
        setTransform() {}, fillRect() {}, beginPath() {}, moveTo() {}, lineTo() {}, closePath() {},
        fill() {}, stroke() {}, save() {}, restore() {}, translate() {}, rotate() {}, arc() {},
        bezierCurveTo() {}, setLineDash() {}, drawImage() {}, strokeText() {}, fillText() {},
        measureText: t => ({ width: String(t).length * 7 }),
      };
    },
    querySelector(sel) {
      if (sel === '.maptools') return makeEl('tools');
      if (sel === '.x') return (this._xBtn ||= makeEl('x', 'button'));
      if (sel === '[data-a=zoom]') return (this._zoomBtn ||= makeEl('zoom', 'button'));
      if (sel === '[data-a=copy]') return (this._copyBtn ||= makeEl('copy', 'button'));
      if (sel === '[data-a=clear]') return (this._clearBtn ||= makeEl('clear', 'button'));
      if (sel === '.map-area') return makeEl('area-wrap');
      if (sel === '.map-top') return makeEl('map-top');
      if (sel === '.mapattr') return makeEl('mapattr');
      return null;
    },
    querySelectorAll(sel) {
      if (sel === 'button') return this._buttons || [];
      return [];
    },
  };
  Object.defineProperty(el, 'innerHTML', {
    get() { return this._innerHTML; },
    set(v) {
      this._innerHTML = String(v);
      const matches = [...this._innerHTML.matchAll(/<button[^>]*data-i="(\d+)"/g)];
      this._buttons = matches.map(m => {
        const b = makeEl('btn-' + m[1], 'button');
        b.dataset.i = m[1];
        return b;
      });
    },
  });
  return el;
}

const byId = {};
for (const id of ['mapwrap','mapc','pf','pq','pres','layers','layers-btn','layer-count','zin','zout','zhome','map-full','map-3d','map-photo','card','tip','mstatus','melev','mscale','near','sethome','mdata','map-area','map-date','main']) {
  byId[id] = makeEl(id);
}
byId.card.getBoundingClientRect = () => ({ left: 0, top: 0, right: 500, bottom: 600, width: 500, height: 600 });

const nearCalls = [];
let abortCount = 0;
let failNextNear = false;
let holdFirstNear = false;
let resolveHeldNear = null;
let mockInfo = {
  layers: ['hospital'],
  bounds: null,
  aerial: false,
  contours: false,
  datasets: [],
  national: {},
  version: 'v1',
  canada: {
    overview_bounds: [-95.1596, 41.6601, -74.31, 57.5083],
    bounds: [-95.1596, 41.6601, -74.31, 57.5083],
    regions: [{ id: 'ontario', label: 'Ontario', bounds: [-95.1596, 41.6601, -74.31, 57.5083] }],
    data_as_of: '2025-01-02T00:00:00Z',
  },
};
let placeResults = [];

const timers = [];
const sandbox = {
  console, URLSearchParams, AbortController, Set, Map, Math, JSON, Object, Array, Number, String, RegExp, Date, Error, Float32Array,
  encodeURIComponent, isFinite, parseFloat,
  devicePixelRatio: 1, innerWidth: 1200, scrollY: 0,
  location: { protocol: 'http:', hostname: '127.0.0.1' },
  navigator: {}, isSecureContext: false,
  localStorage: { getItem: () => null, setItem() {} },
  history: { replaceState() {} },
  getComputedStyle: () => ({ paddingBottom: '0', display: 'none' }),
  ResizeObserver: class { observe() {} disconnect() {} },
  requestAnimationFrame: () => 1,
  cancelAnimationFrame() {},
  setInterval: () => 1,
  clearInterval() {},
  setTimeout: (fn, ms) => { const id = timers.length + 1; timers.push({ id, fn, ms, cleared: false }); return id; },
  clearTimeout: id => { const t = timers.find(x => x.id === id); if (t) t.cleared = true; },
  document: {
    title: '',
    body: makeEl('body', 'body'),
    fullscreenElement: null,
    getElementById: id => byId[id] || null,
    querySelector: () => null,
    querySelectorAll: () => [],
    addEventListener() {},
    removeEventListener() {},
    createElement: () => makeEl('c', 'canvas'),
  },
  fetch: (url, opts) => {
    if (url === '/api/map/info') return Promise.resolve({ ok: true, json: () => Promise.resolve(mockInfo) });
    if (url.startsWith('/api/map/pins')) return Promise.resolve({ ok: true, json: () => Promise.resolve({ points: [] }) });
    if (url.startsWith('/api/places')) return Promise.resolve({ ok: true, json: () => Promise.resolve(placeResults) });
    if (url.startsWith('/api/map/near')) {
      nearCalls.push(url);
      if (opts && opts.signal) opts.signal.addEventListener('abort', () => { abortCount++; });
      if (failNextNear) { failNextNear = false; return Promise.reject(new Error('boom')); }
      if (holdFirstNear) {
        holdFirstNear = false;
        return new Promise((res, rej) => {
          resolveHeldNear = res;
          if (opts && opts.signal) opts.signal.addEventListener('abort', () => rej(Object.assign(new Error('Aborted'), { name: 'AbortError' })));
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve([{ cls: 'hospital', name: 'Local Hospital', lat: 45.5, lon: -73.57, km: 0.4, dir: 'north', detail: 'OpenStreetMap Canada' }]) });
    }
    return Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve({}) });
  },
};
sandbox.window = sandbox;
vm.runInNewContext(mapSrc + '\nthis.MapView = MapView;', sandbox);

async function flush() {
  for (let i = 0; i < 6; i++) await Promise.resolve();
}
function runTimers() {
  const pending = timers.splice(0, timers.length);
  for (const t of pending) if (!t.cleared) t.fn();
}

(async () => {
  await sandbox.MapView.page(byId.main, new URLSearchParams());
  await flush();
  // 1. Ontario-only extract labels dropdown "Canada — installed" and schedules initial nearby()
  if (!byId['map-area'].innerHTML.includes('Canada — installed')) throw new Error('expected Canada — installed label');
  holdFirstNear = true;
  runTimers();
  await flush();
  if (nearCalls.length !== 1) throw new Error('expected initial near call');

  // 2. Picking a place aborts the in-flight slow /api/map/near and triggers a fresh /api/map/near at the picked coords
  placeResults = [{ name: 'Montréal', kind: 'city', detail: 'Quebec, Canada', lat: 45.5017, lon: -73.5673 }];
  byId.pq.value = 'Montreal';
  byId.pf.onsubmit({ preventDefault() {} });
  await flush();
  if (abortCount < 1) throw new Error('expected superseded near request to be aborted');
  runTimers();
  await flush();
  if (nearCalls.length !== 2 || !nearCalls[1].includes('lat=45.5017')) throw new Error('expected fresh near call at Montreal: ' + JSON.stringify(nearCalls));
  if (byId.near.classList.contains('busy')) throw new Error('busy should clear after near resolves');

  // 3. Clicking a #near item keeps list steady, then Zoom here (go + reveal) refreshes nearby()
  byId.near._buttons[0].onclick();
  runTimers();
  await flush();
  if (nearCalls.length !== 2) throw new Error('clicking #near item should keep list steady');
  byId.card._zoomBtn._listeners.click[0]();
  runTimers();
  await flush();
  if (nearCalls.length !== 3) throw new Error('Zoom here (go + reveal) must refresh nearby: ' + nearCalls.length);

  // 4. Error during nearby clears .busy cleanly
  failNextNear = true;
  byId['map-area'].onchange({ target: { value: 'ontario' } });
  runTimers();
  await flush();
  if (byId.near.classList.contains('busy')) throw new Error('busy stayed stuck after nearby error');
  if (!byId.near.innerHTML.includes('Nearby search is unavailable')) throw new Error('missing error fallback');

  // 5. Canadian empty-state search copy avoids US state/ZIP wording
  placeResults = [];
  byId.pq.value = '1470 Pinetree Cres';
  byId.pf.onsubmit({ preventDefault() {} });
  await flush();
  if (byId.pres.innerHTML.includes('state') || !byId.pres.innerHTML.includes('places, services and named water')) {
    throw new Error('unexpected Canadian address empty state: ' + byId.pres.innerHTML);
  }
  byId.pq.value = 'K1A 0B1';
  byId.pf.onsubmit({ preventDefault() {} });
  await flush();
  if (byId.pres.innerHTML.includes('5-digit ZIP') || !byId.pres.innerHTML.includes('postal codes')) {
    throw new Error('unexpected Canadian place empty state: ' + byId.pres.innerHTML);
  }

  // 6. US-only map keeps upstream empty-state copy
  sandbox.MapView.stop();
  mockInfo = { layers: ['hospital'], bounds: [-120, 32, -115, 36], aerial: false, contours: false, datasets: [], national: {}, version: 'v2' };
  await sandbox.MapView.page(byId.main, new URLSearchParams());
  await flush();
  byId.pq.value = 'UnknownPlaceXYZ';
  byId.pf.onsubmit({ preventDefault() {} });
  await flush();
  if (!byId.pres.innerHTML.includes('5-digit ZIP')) {
    throw new Error('US empty state regressed: ' + byId.pres.innerHTML);
  }
  sandbox.MapView.stop();
  console.log('MAP_JS_OK');
})().catch(e => { console.error(e); process.exit(1); });
'''
        res = subprocess.run(
            ['node', '-e', script, str(ROOT / 'web' / 'map.js')],
            capture_output=True,
            text=True,
            encoding='utf-8',
        )
        self.assertEqual(res.returncode, 0, res.stderr + res.stdout)
        self.assertIn('MAP_JS_OK', res.stdout)


if __name__ == '__main__':
    unittest.main()
