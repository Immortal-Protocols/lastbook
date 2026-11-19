"""Check that a nationwide build keeps spatial and search coverage from each extract."""
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from tools import build_map, build_region_es


class NationwideMap(unittest.TestCase):
    def make_extract(self, geo, title, places):
        geo.mkdir()
        with closing(sqlite3.connect(geo / 'national.sqlite')) as db, db:
            db.executescript(build_map.MAP_SCHEMA)
            for fid, (name, lon, lat) in enumerate(places, 1):
                db.execute('INSERT INTO feat VALUES (?, ?, ?, ?, ?, ?)',
                           (fid, 'place', 'city', name, 6, build_map.pack([[lon, lat]])))
                db.execute('INSERT INTO feat_idx VALUES (?, ?, ?, ?, ?, ?, ?)', (fid, lon, lon, lat, lat, 6, 30))
            db.execute("INSERT INTO poi VALUES (1, 'drinking_water', NULL, -3.7, 40.4)")
            build_region_es.build_places(db, geo / 'places.sqlite', title)

    def test_merged_extracts_keep_spatial_matches_and_search_without_boundary_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mainland, islands, country = root / 'mainland', root / 'islands', root / 'country'
            border = ('Boundary town', -3.7, 40.4)
            self.make_extract(mainland, 'Mainland', [border, ('Madrid', -3.7, 40.42)])
            self.make_extract(islands, 'Islands', [('Las Palmas', -15.4, 28.1), border])
            country.mkdir()

            build_region_es.nationwide_databases(country, [('mainland', mainland), ('islands', islands)], {})

            with closing(sqlite3.connect(country / 'national.sqlite')) as db:
                query = ('SELECT f.name FROM feat_idx i JOIN feat f ON f.id=i.id '
                         'WHERE i.maxx BETWEEN ? AND ? AND i.maxy BETWEEN ? AND ? ORDER BY f.name')
                self.assertEqual(db.execute(query, (-3.8, -3.6, 40.3, 40.5)).fetchall(),
                                 [('Boundary town',), ('Madrid',)])
                self.assertEqual(db.execute(query, (-15.5, -15.3, 28, 28.2)).fetchall(), [('Las Palmas',)])
                self.assertEqual(db.execute("SELECT count(*) FROM poi WHERE cls='drinking_water'").fetchone(), (1,))
            with closing(sqlite3.connect(country / 'places.sqlite')) as db:
                query = ("SELECT p.name, p.detail FROM place_fts JOIN place p ON p.id=place_fts.rowid "
                         "WHERE place_fts MATCH ?")
                self.assertEqual(db.execute(query, ('Madrid',)).fetchall(), [('Madrid', 'Mainland')])
                self.assertEqual(db.execute(query, ('Palmas',)).fetchall(), [('Las Palmas', 'Islands')])
                self.assertEqual(db.execute(query, ('Boundary',)).fetchall(), [('Boundary town', 'Mainland')])

    def test_nationwide_exact_search_prefers_a_city_over_a_nearby_namesake(self):
        import server

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            places = root / 'places.sqlite'
            with closing(sqlite3.connect(places)) as db, db:
                db.executescript(build_region_es.PLACE_SCHEMA)
                db.executemany('INSERT INTO place(name,kind,detail,lat,lon,rank,source) VALUES (?,?,?,?,?,?,?)', [
                    ('Madrid', 'locality', 'Andalucía', 37.4, -5.0, 1, 'OpenStreetMap'),
                    ('Madrid', 'national capital', 'Comunidad de Madrid', 40.4168, -3.7038, 1, 'OpenStreetMap'),
                ])
                db.execute("INSERT INTO place_fts(place_fts) VALUES ('rebuild')")
            receipt = {'name': 'ES', 'country': 'ES', 'title': 'All of Spain', 'credit': 'OpenStreetMap',
                       'data_as_of': '2026-11-01', 'bounds': [-18, 27, 5, 44], 'files': {}}
            (root / 'map-set.json').write_text(json.dumps(receipt))
            server.spanish_map.cache_clear()
            self.addCleanup(server.spanish_map.cache_clear)
            with patch.multiple(server, HERE=root, PLACEDB=places, WATERDB=root / 'water.sqlite', _pack={}):
                results = server.places('Madrid', near=(37.4, -5.0))

            self.assertEqual([result['kind'] for result in results], ['national capital', 'locality'])
