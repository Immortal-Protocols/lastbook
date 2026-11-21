"""Build and install a synthetic Puerto Rico sidecar using the optional builder dependencies."""
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import osmium

from engine.address_search import find_addresses
from engine.setup import api, download, manifest
from tools import build_pr_addresses as builder


class BuildPuertoRico(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.osm = self.root / 'example.osm.pbf'
        self.boundaries = self.root / 'regions.geojson'
        self.output = self.root / 'output'
        features = []
        for i in range(78):
            ring = [[i, 0], [i + 1, 0], [i + 1, 1], [i, 1], [i, 0]]
            features.append({'type': 'Feature', 'properties': {'GEOID': f'72{i:03}', 'NAME': f'Región {i} Municipio'},
                             'geometry': {'type': 'Polygon', 'coordinates': [ring]}})
        self.boundaries.write_text(json.dumps({'type': 'FeatureCollection', 'features': features}))
        header = osmium.io.Header()
        header.set('osmosis_replication_timestamp', '2026-01-01T00:00:00Z')
        tags = {'addr:housenumber': 'A-12', 'addr:street': 'Calle Ámbar', 'addr:city': 'Pueblo',
                'addr:place': 'Urbanización Sol', 'addr:postcode': '00901'}
        with osmium.SimpleWriter(self.osm, header=header) as writer:
            for idx, pos in enumerate([(0.2, 0.2), (0.7, 0.2), (0.7, 0.7), (0.2, 0.7)], 1):
                writer.add_node(osmium.osm.mutable.Node(id=idx, location=pos, tags=tags if idx == 1 else {}))
            for idx, number, way in ((10, '3', [1, 2, 3, 4, 1]), (11, '4', [1, 2, 3])):
                writer.add_way(osmium.osm.mutable.Way(id=idx, nodes=way, tags={'addr:housenumber': number, 'addr:street': 'Camino Azul'}))

    def test_archive_installs_and_searches(self):
        entry = builder.build(self.osm, self.boundaries, self.output)
        self.assertEqual(entry['records'], 2)
        self.assertEqual(builder.build(self.osm, self.boundaries, self.output), entry)
        self.assertIsNotNone(manifest.validate({'version': 1, 'packs': [], 'address_indexes': [entry]}))
        archive = self.output / builder.ARCHIVE
        self.assertEqual(builder.sha(archive), entry['files'][0]['sha256'])
        setup = api.Setup('first-run', self.root / 'settings', self.root)
        item = {'state': 'waiting'}
        work = self.root / 'work'
        with patch.object(setup, '_get_file', return_value=(archive, False)), patch.object(setup, '_set'):
            setup._do_addresses(item, {'addresses': entry, 'switch': True}, work, download.Control())
        geo = work / 'unpack' / api.DATA_NAME / 'derived' / 'geo'
        index = geo / 'addresses' / 'PR.sqlite'
        self.assertEqual(index.stat().st_size, entry['installed_bytes'])
        self.assertEqual(json.loads(index.with_suffix('.json').read_text())['files'][archive.name], builder.sha(archive))
        self.assertEqual(find_addresses('Urb Sol, A-12 Cll Ambar, Region 0 PR', geo)[0]['lat'], 0.2)
        self.assertEqual(find_addresses('3 Cam. Azul Region 0 PR', geo)[0]['lat'], 0.45)
        self.assertEqual(find_addresses('4 Camino Azul PR', geo), [])
        coverage = json.loads((self.output / 'PR.coverage.json').read_text())
        self.assertEqual(coverage['skipped']['no_point_or_valid_closed_way'], 1)
        self.assertEqual(coverage['municipios']['Región 0'], 2)
        with closing(sqlite3.connect(index)) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM municipios WHERE records=0').fetchone(), (77,))

    def test_incomplete_boundary_input_preserves_previous_output(self):
        self.output.mkdir()
        previous = self.output / builder.ARCHIVE
        previous.write_bytes(b'previous')
        self.boundaries.write_text('{"features": []}')
        with self.assertRaisesRegex(ValueError, '78'):
            builder.build(self.osm, self.boundaries, self.output)
        self.assertEqual(previous.read_bytes(), b'previous')
