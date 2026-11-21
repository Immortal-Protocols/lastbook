#!/usr/bin/env python3
"""The Guyana region file (packaging/regions/GY.json), the region loader, and the pure parts of
tools/build_region_guyana.py: no network, no library, no numpy.

  python3 -B -m unittest app.tests.test_regions_guyana
"""
import ast, contextlib, io, json, math, re, sqlite3, struct, sys, tempfile, unittest
from array import array
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'packaging'), str(ROOT / 'tools')]
import regions                      # noqa: E402
import build_region_guyana as G     # noqa: E402

GY = ROOT / 'packaging/regions/GY.json'
LAYERS = ('streets', 'pois', 'water', 'terrain', 'crops', 'buildings', 'places')


def us_constant(tool, name):
    """A literal assigned at the top of a US builder, read without running it (tools/build_map.py runs on import)."""
    tree = ast.parse((ROOT / 'tools' / tool).read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, 'id', None) == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise KeyError(name)


def us_columns(tool, table):
    """Column names of `CREATE TABLE [IF NOT EXISTS] table(...)` in a US builder's source."""
    text = (ROOT / 'tools' / tool).read_text(encoding='utf-8')
    m = re.search(r'CREATE (?:VIRTUAL )?TABLE (?:IF NOT EXISTS )?%s(?:\s+USING \w+)?\(([^)]*)\)' % table, text)
    cols = []
    for part in re.split(r',\s*PRIMARY KEY', m[1])[0].split(','):
        word = part.strip().split()[0] if part.strip() else ''
        if word and word.upper() != 'PRIMARY' and '=' not in word:
            cols.append(word)
    return cols


def columns(sql, table):
    db = sqlite3.connect(':memory:')
    db.executescript(sql)
    return [r[1] for r in db.execute(f'PRAGMA table_info("{table}")')]


class RegionFile(unittest.TestCase):
    def test_loader_lists_and_reads_guyana(self):
        self.assertIn('GY', regions.codes())
        self.assertTrue(regions.is_region('GY'))
        self.assertFalse(regions.is_region('CA'))        # California stays a US state code
        self.assertFalse(regions.is_region('gy'))
        r = regions.get('GY')
        self.assertEqual((r['id'], r['name'], r['country'], r['kind']), ('GY', 'Guyana', 'GY', 'country'))

    def test_box_is_the_checked_box_with_the_margin(self):
        self.assertEqual(regions.get('GY')['bbox'], [-61.3939, 1.1714, -56.4808, 8.5576])
        w, s, e, n = regions.box('GY')
        self.assertTrue(-61.6 < w < -61.5 and 1.0 < s < 1.05 and -56.35 < e < -56.3 and 8.7 < n < 8.75, (w, s, e, n))
        self.assertAlmostEqual(w, -61.3939 - .15)
        self.assertAlmostEqual(n, 8.5576 + .15)

    def test_json_has_what_a_build_needs(self):
        r = json.loads(GY.read_text(encoding='utf-8'))
        for k in regions.REQUIRED + ('address', 'attribution'):
            self.assertIn(k, r)
        self.assertIs(r['address']['search'], False)
        self.assertIn('7-digit', r['address']['postcode'])
        self.assertIn('Address search is not included', r['includes'])
        self.assertEqual(set(r['sources']), set(LAYERS))
        for layer, items in r['sources'].items():
            self.assertTrue(items, layer)
            for s in items:
                for k in ('dataset', 'publisher', 'url', 'licence', 'attribution'):
                    self.assertTrue(s.get(k), f'{layer}: {k}')
                self.assertTrue(s['url'].startswith('https://'), s['url'])
        text = ' '.join(r['attribution'])
        for line in ('© OpenStreetMap contributors', 'Copernicus WorldDEM-30 © DLR e.V. 2010-2014', 'do not incur any liability',
                     '© ESA WorldCover project 2021', 'OCHA', 'CC BY-IGO', 'Microsoft'):
            self.assertIn(line, text)
        self.assertEqual(r['builder'], 'tools/build_region_guyana.py')
        self.assertTrue((ROOT / r['builder']).is_file())


class Tiling(unittest.TestCase):
    def test_copernicus_tiles(self):
        names = G.copdem_tiles((-58.35, 6.65, -57.95, 6.95))
        self.assertEqual(names, ['Copernicus_DSM_COG_10_N06_00_W059_00_DEM', 'Copernicus_DSM_COG_10_N06_00_W058_00_DEM'])
        self.assertEqual(G.copdem_cell(names[0]), (7, -59))
        self.assertEqual(G.copdem_cell('Copernicus_DSM_COG_10_S01_00_E012_00_DEM'), (0, 12))
        whole = G.copdem_tiles(G.default_box())
        self.assertEqual(len(whole), 6 * 8)     # 1° tiles from W062 to W057, N01 to N08
        self.assertEqual(len(set(whole)), len(whole))

    def test_worldcover_tiles(self):
        self.assertEqual(G.worldcover_tiles((-58.35, 6.65, -57.95, 6.95)), ['ESA_WorldCover_10m_2021_v200_N06W060_Map'])
        self.assertEqual(G.worldcover_corner('ESA_WorldCover_10m_2021_v200_N06W060_Map'), (-60, 9))
        self.assertEqual(G.worldcover_corner('ESA_WorldCover_10m_2021_v200_S03E012_Map'), (12, 0))
        self.assertEqual(len(G.worldcover_tiles(G.default_box())), 3 * 3)

    def test_quadkeys(self):
        w, s, e, n = G.quadkey_box('0')
        self.assertEqual((w, s, e), (-180, 0, 0))
        self.assertAlmostEqual(n, 85.0511, 3)
        box = G.quadkey_box('032321321')      # a Microsoft file over the coast at Georgetown
        self.assertTrue(G.overlaps(box, (-58.2, 6.8, -58.1, 6.85)))
        self.assertFalse(G.overlaps(box, (-60, 2, -59.9, 2.1)))

    def test_tile_range_and_supertiles(self):
        x0, x1, y0, y1 = G.tile_range((-58.35, 6.65, -57.95, 6.95), 14)
        self.assertTrue(x0 <= x1 and y0 <= y1)
        self.assertEqual(G.tile_range((-180, -85, 179.999, 85), 1), (0, 1, 0, 1))
        keys = G.supertiles({(7, -59): 'a', (7, -58): 'b', (2, -60): 'far'}, (-58.35, 6.65, -57.95, 6.95))
        self.assertTrue(keys)
        self.assertTrue(all(isinstance(k, tuple) and len(k) == 2 for k in keys))
        n = 2 ** 8
        lons = [(x / n * 360 - 180, (x + 1) / n * 360 - 180) for x, _ in keys]
        self.assertTrue(all(a <= -57.95 and b >= -58.35 for a, b in lons))   # nothing from the far cell


class Classes(unittest.TestCase):
    def test_lists_match_build_map(self):
        for name in ('POI_KEEP', 'ROAD_Z', 'LANDUSE_KEEP', 'PLACE_Z'):
            self.assertEqual(getattr(G, name), us_constant('build_map.py', name), name)

    def test_place_zoom(self):
        self.assertEqual(G.place_zoom('town'), 9)
        self.assertEqual(G.place_zoom('city', '400000'), 5)
        self.assertEqual(G.place_zoom('city', 'n/a'), 6)
        self.assertEqual(G.place_zoom('national_capital'), 5)
        self.assertEqual(G.place_zoom('something_new'), 14)
        self.assertEqual(G.PLACE_CLS['national_capital'], 'city')

    def test_water(self):
        self.assertEqual(G.water_layer('wetland'), ('wet', 'wet'))
        self.assertEqual(G.water_layer('reservoir'), ('water', 'reservoir'))
        self.assertEqual(G.water_layer('river'), ('water', 'river'))
        self.assertEqual(G.water_layer('water'), ('water', 'water'))
        self.assertEqual(G.water_point_kind('water', True, 0.001), 'lake')
        self.assertEqual(G.water_point_kind('water', False, 0.01), 'pond')
        self.assertEqual(G.water_point_kind('water', False, 0.001), None)
        self.assertEqual(G.water_point_kind('reservoir', False, 1), 'reservoir')
        self.assertEqual(G.water_point_kind('river', True, 50), None)
        self.assertEqual(G.water_minz(1e-9), 14)
        self.assertEqual(G.water_minz(10000), 5)

    def test_land_cover(self):
        lut = G.crop_lut()
        self.assertEqual(len(lut), 256)
        self.assertEqual(lut[40], 1)                                  # WorldCover 40 = cropland
        self.assertEqual(sum(1 for v in lut if v), len(G.WORLDCOVER))
        self.assertEqual(lut[10], 0)                                  # tree cover is not a crop
        self.assertEqual(G.WORLDCOVER[40][1], 'cropland')
        self.assertAlmostEqual(G.acres_per_px(0, 3 / 9000), 37.1 * 36.9 / 4046.86, 1)
        self.assertLess(G.acres_per_px(8, 1e-3), G.acres_per_px(0, 1e-3))


class Geometry(unittest.TestCase):
    def test_pack_round_trip(self):
        parts = [[-58.1, 6.8, -58.05, 6.81, -58.0, 6.79]]
        a = array('i')
        a.frombytes(G.pack_flat(parts))
        self.assertEqual(a[0], 1)
        self.assertEqual(a[1], 3)
        x = y = 0
        pts = []
        for i in range(3):
            x += a[2 + 2 * i]; y += a[3 + 2 * i]
            pts.append((x / 1e6, y / 1e6))
        self.assertEqual(pts, [(-58.1, 6.8), (-58.05, 6.81), (-58.0, 6.79)])
        self.assertEqual(G.flat_bbox(parts), (-58.1, -58.0, 6.79, 6.81))

    def test_gpkg_geometry(self):
        head = b'GP\x00\x01' + struct.pack('<i', 4326)                  # no envelope
        point = head + struct.pack('<BIdd', 1, 1, -58.15, 6.8)
        self.assertEqual(G.gpkg_parts(point), [[-58.15, 6.8]])
        line = head + struct.pack('<BII4d', 1, 2, 2, 0, 0, 1, 1)
        self.assertEqual(G.gpkg_parts(line), [[0, 0, 1, 1]])
        env = b'GP\x00\x03' + struct.pack('<i4d', 4326, 0, 1, 0, 1)      # xy envelope
        self.assertEqual(G.gpkg_parts(env + struct.pack('<BII4d', 1, 2, 2, 0, 0, 1, 1)), [[0, 0, 1, 1]])

    def test_thin_and_zoom(self):
        flat = [0, 0, 0.000001, 0, 0.5, 0, 1, 0]
        self.assertEqual(G.thin(flat, 0.00001), [0, 0, 0.5, 0, 1, 0])
        self.assertEqual(G.area_z(0, 0, 0, 0, 9), 17)
        self.assertEqual(G.area_z(0, 10, 0, 10, 9), 9)
        self.assertTrue(G.in_box((0, 1, 0, 1), (0.5, 0.5, 2, 2)))
        self.assertFalse(G.in_box((0, 1, 0, 1), (1.5, 1.5, 2, 2)))

    def test_inside_point_and_area(self):
        sq = [(0, 0), (1, 0), (1, 1), (0, 1)]
        x, y = G.inside_point(sq)
        self.assertTrue(0 < x < 1 and 0 < y < 1)
        self.assertAlmostEqual(G.ring_area_km2(sq), 111.32 ** 2 * math.cos(math.radians(0.5)), 3)

    def test_shapefile_reader(self):
        with tempfile.TemporaryDirectory() as d:
            ring = [(0, 0), (0, 1), (1, 1), (1, 0), (0, 0)]
            body = struct.pack('<i4d', 5, 0, 0, 1, 1) + struct.pack('<ii', 1, len(ring)) + struct.pack('<i', 0)
            body += b''.join(struct.pack('<2d', *p) for p in ring)
            rec = struct.pack('>ii', 1, len(body) // 2) + body
            head = struct.pack('>i', 9994) + b'\0' * 20 + struct.pack('>i', (100 + len(rec)) // 2) + struct.pack('<ii4d4d', 1000, 5, 0, 0, 1, 1, 0, 0, 0, 0)
            (Path(d) / 'a.shp').write_bytes(head + rec)
            self.assertEqual(G.read_shp_polygons(Path(d) / 'a.shp'), [[ring]])
            name = b'ADM1_EN'.ljust(11, b'\0')
            dbf = struct.pack('<4BIHH20x', 3, 126, 11, 16, 1, 32 + 32 + 1, 1 + 12)
            dbf += name + b'C' + b'\0' * 4 + bytes([12]) + b'\0' * 15 + b'\x0d'
            dbf += b' ' + 'Région'.encode('utf-8').ljust(12) + b'\x1a'
            (Path(d) / 'a.dbf').write_bytes(dbf)
            self.assertEqual(G.read_dbf(Path(d) / 'a.dbf'), [{'ADM1_EN': 'Région'}])


class Tiles(unittest.TestCase):
    def up_filtered(self, rows):
        """An RGB PNG with filter Up on every row, as tools/build_terrain.py writes."""
        import zlib
        raw, prev = b'', bytes(len(rows[0]))
        for r in rows:
            raw += b'\x02' + bytes((a - b) & 255 for a, b in zip(r, prev))
            prev = r
        chunk = lambda t, d: struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
        return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', len(rows[0]) // 3, len(rows), 8, 2, 0, 0, 0))
                + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))

    def test_low_zoom_tiles_keep_both(self):
        land = bytes((0x01, 0x87, 0x00))                # 9.6 m
        old = self.up_filtered([land * 2, land * 2])
        new = self.up_filtered([G.SEA + bytes((0x01, 0x90, 0x00)), G.SEA * 2])
        w, h, ch, rows = G.png_pixels(G.combine_tiles(old, new))
        self.assertEqual((w, h, ch), (2, 2, 3))
        self.assertEqual(bytes(rows[0]), land + bytes((0x01, 0x90, 0x00)))
        self.assertEqual(bytes(rows[1]), land * 2)

    def test_crop_tiles_keep_both(self):
        a = G.png_write(2, 1, 4, [bytes((1, 2, 3, 190)) + bytes(4)])
        b = G.png_write(2, 1, 4, [bytes(4) + bytes((9, 9, 9, 190))])
        self.assertEqual(bytes(G.png_pixels(G.combine_tiles(a, b))[3][0]), bytes((1, 2, 3, 190, 9, 9, 9, 190)))
        self.assertEqual(G.combine_tiles(b'not a png', b), b)


class Schemas(unittest.TestCase):
    """The region files carry the same tables and columns as the US builders write, so build_packs cuts them alike."""
    def test_same_columns_as_the_us_builders(self):
        cases = [('national', 'feat', 'build_map.py'), ('national', 'poi', 'build_map.py'), ('national', 'feat_idx', 'build_map.py'),
                 ('water', 'resource', 'build_water.py'), ('water', 'feat', 'build_water.py'), ('water', 'feat_idx', 'build_water.py'),
                 ('water', 'spatial', 'build_water.py'), ('water', 'water_fts', 'build_water.py'),
                 ('terrain', 'tile', 'build_terrain.py'), ('crops', 'resource', 'build_crops.py'), ('crops', 'tile', 'build_crops.py'),
                 ('crops', 'spatial', 'build_crops.py'), ('buildings', 'bldg', 'build_buildings.py'),
                 ('buildings', 'bldg_socal', 'build_buildings.py'), ('buildings', 'bldg_osm', 'build_osm_heights.py'),
                 ('places', 'place', 'build_places.py'), ('places', 'place_fts', 'build_places.py')]
        for name, table, tool in cases:
            with self.subTest(file=name, table=table):
                self.assertEqual(columns(G.SCHEMA[name], table), us_columns(tool, table))

    def test_merge_twice_replaces(self):
        saved = G.OUT, G.GEO
        self.addCleanup(lambda: setattr(G, 'OUT', saved[0]) or setattr(G, 'GEO', saved[1]))
        with tempfile.TemporaryDirectory() as d:
            G.OUT, G.GEO = Path(d) / 'regions/GY', Path(d) / 'geo'
            G.GEO.mkdir()
            us = sqlite3.connect(G.GEO / 'national.sqlite')       # a US file with a row of its own
            us.executescript(G.NATIONAL_SQL)
            us.execute("INSERT INTO feat VALUES (1,'road','primary','US road',8,x'00')")
            us.execute('INSERT INTO feat_idx VALUES (1,-100,-99,40,41,8,30)')
            us.commit(); us.close()
            db = G.fresh('national')
            db.execute("INSERT INTO feat VALUES (1,'road','primary','Main Road',8,x'00')")
            db.execute('INSERT INTO feat_idx VALUES (1,-58.2,-58.1,6.7,6.8,8,30)')
            db.execute("INSERT INTO poi VALUES (1,'hospital','Hospital',-58.15,6.8)")
            db.commit(); db.close()
            db = G.fresh('water')
            cur = db.execute("INSERT INTO resource(source_id,kind,name,lat,lon,detail,source,origin) VALUES ('osm:1','lake','A',6.8,-58.1,'{}','x','osm:GY')")
            db.execute('INSERT INTO spatial VALUES (?,?,?,?,?)', (cur.lastrowid, -58.1, -58.1, 6.8, 6.8))
            db.execute("INSERT INTO meta VALUES ('osm:GY','{}')")
            db.commit(); db.close()
            db = G.fresh('places')
            db.execute("INSERT INTO place(name,kind,detail,lat,lon,rank,source) VALUES ('Georgetown','city','Guyana (OpenStreetMap)',6.8,-58.15,1,'OpenStreetMap')")
            db.commit(); db.close()
            db = G.fresh('buildings')
            db.execute('INSERT INTO bldg VALUES (1,2,?,3,x\'00\')', (G.PART_BASE,))
            db.commit(); db.close()
            with contextlib.redirect_stdout(io.StringIO()):
                for _ in range(2):
                    G.merge(G.default_box())
            n = sqlite3.connect(G.GEO / 'national.sqlite')
            self.assertEqual(n.execute('SELECT count(*) FROM feat').fetchone()[0], 2)
            self.assertEqual(n.execute('SELECT count(*) FROM feat_idx').fetchone()[0], 2)
            self.assertEqual(n.execute('SELECT name FROM feat WHERE id=1').fetchone()[0], 'US road')
            self.assertEqual(n.execute('SELECT count(*) FROM poi').fetchone()[0], 1)
            w = sqlite3.connect(G.GEO / 'water.sqlite')
            self.assertEqual(w.execute('SELECT count(*) FROM resource').fetchone()[0], 1)
            self.assertEqual(w.execute('SELECT count(*) FROM spatial').fetchone()[0], 1)
            self.assertEqual(w.execute("SELECT count(*) FROM water_fts WHERE water_fts MATCH 'A'").fetchone()[0], 1)
            p = sqlite3.connect(G.GEO / 'places.sqlite')
            self.assertEqual(p.execute("SELECT count(*) FROM place_fts WHERE place_fts MATCH 'Georgetown'").fetchone()[0], 1)
            b = sqlite3.connect(G.GEO / 'buildings.sqlite')
            self.assertEqual(b.execute('SELECT count(*) FROM bldg').fetchone()[0], 1)

    def test_unknown_layer_is_refused(self):
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            G.main(['build', 'roads'])


if __name__ == '__main__':
    unittest.main()
