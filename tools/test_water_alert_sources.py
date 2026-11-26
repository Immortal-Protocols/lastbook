"""Complete source conditions, historical guide preservation and real availability."""
import copy
import hashlib
import json
from pathlib import Path
import socket
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from tools import build_australia_reference as b
from tools.test_build_australia_reference import before_water_alert_extension
from tools.validate_topics import items


class WaterAlerts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audit = json.loads((b.SOURCES / 'WATER-ALERTS-SOURCE-AUDIT-20261127.json').read_text(encoding='utf-8'))
        cls.uids = {s['id'] for s in cls.audit['selections']}

    def test_complete_source_blocks_conditions_rights_and_prior_readings(self):
        manifest, sources = b.checked_sources()
        records = {r['id']: r for r, _, _, _ in sources}
        self.assertEqual(len(self.audit['base_sources_sha256']) + len(self.uids), 127)
        self.assertEqual(len(self.uids), 2)
        for source in self.audit['selections']:
            record = records[source['id']]
            html = (b.SOURCES / record['snapshot']).read_text(encoding='utf-8')
            body = html.split('<hr>\n', 1)[1].split('<hr>', 1)[0]
            title, body = body.split('</h2>\n', 1)
            self.assertEqual(b.source_text(title), source['source_title'])
            self.assertEqual(b.digest(body.encode('utf-8')), source['reader_body_sha256'])
            self.assertEqual(b.source_text(body), source['source_text'])
            self.assertEqual(record['raw_sha256'], source['raw']['raw_sha256'])
            self.assertEqual(record['source_updated'], source['source_updated'])
            self.assertEqual(record['retrieved_at'], '2026-11-27')
            self.assertEqual(record['license'], 'CC-BY-4.0')
            self.assertIn('not a notice that an alert currently exists or has been lifted', html)
            self.assertIn(self.audit['rights']['credit'], html)
            self.assertNotIn('href="https://', html)
            for resource in source['linked_resources_excluded']:
                self.assertIn(resource['url'], html)
            projected = ' '.join(block['text'] for block in source['ordered_blocks'])
            self.assertEqual(projected, source['source_text'])
        alert = next(s['source_text'] for s in self.audit['selections'] if s['id'] == 'nsw-boil-water-alert')
        for phrase in ['Follow the boil water alert advice issued by your water utility.',
                       'If you cannot boil the water', '4% – 5% available chlorine',
                       '2 drops of bleach to 1 litre', '4 drops if the water is cloudy',
                       '30 minutes', '25°C', '1 hour', '15°C', '2 hours', '5°C',
                       'avoid scalding', 'swallowed during washing and bathing',
                       'Infant formula should be made with cooled boiled water.',
                       'Chlorine water purification tablets']:
            self.assertIn(phrase, alert)
        tank = next(s['source_text'] for s in self.audit['selections'] if s['id'] == 'nsw-water-header-tanks')
        for phrase in ['when your water supplier has issued a boil water alert',
                       'When a boil water alert is lifted', 'building owners/managers',
                       "hasn't been cleaned in the previous 12 months", 'has been cleaned in the previous 12 months',
                       'Australian Standard 3500 TITLE', 'The tank should drained and refilled',
                       'at least 2 minutes', 'up to 5 minutes', 'about 10 seconds']:
            self.assertIn(phrase, tank)
        self.assertTrue(self.audit['rights']['policy_matches_existing_bundled_body'])
        for uid, digest in self.audit['base_sources_sha256'].items():
            if uid != 'au-reference':
                self.assertEqual(records[uid]['sha256'], digest, uid)
        hub = (b.SOURCES / 'sources/au-reference.html').read_bytes()
        later = hub.index(b'<h2>Household and rural scenario plans</h2>')
        hub = hub[:later] + hub[hub.index(b'</body>', later):]
        start = hub.index(b'<h2>Water-supplier alerts and building header tanks</h2>')
        restored = hub[:start] + hub[hub.index(b'</body>', start):]
        self.assertEqual(b.digest(restored), self.audit['base_hub_sha256'])

    def test_new_links_preserve_guides_gaps_and_equal_household_rural_access(self):
        for gid, digest in self.audit['baseline_guides'].items():
            guide = json.loads((b.ROOT / 'content/topics' / (gid + '.json')).read_text(encoding='utf-8'))
            restored = before_water_alert_extension(copy.deepcopy(guide))
            self.assertEqual(b.digest(json.dumps(restored, sort_keys=True).encode()), digest, gid)
        household = [x for x in self.audit['guide_placements'] if x['guide'] == 'au-household']
        rural = [x for x in self.audit['guide_placements'] if x['guide'] == 'au-rural']
        self.assertEqual([{k:v for k,v in x.items() if k != 'guide'} for x in household],
                         [{k:v for k,v in x.items() if k != 'guide'} for x in rural])
        self.assertEqual(len(self.audit['guide_placements']), 14)
        gaps = json.loads((b.ROOT / 'content/gaps.json').read_text(encoding='utf-8'))
        for change in self.audit['gap_updates']:
            self.assertEqual(gaps[change['guide']]['missing'][change['index']], change['after'])
        self.assertIn('No current local water-utility notice', gaps['water']['missing'][2])
        self.assertIn('not pump/roof-tank operation', gaps['water']['missing'][4])

    def test_real_offline_build_search_and_individual_source_move_restore(self):
        import server
        with tempfile.TemporaryDirectory() as d, patch.object(socket, 'socket', side_effect=AssertionError('network')):
            data = Path(d) / 'LastbookData'; b.build(data); lib = data / 'library-data'
            cat = lib / 'catalog.json'; saved, mtime = cat.read_bytes(), cat.stat().st_mtime_ns
            with sqlite3.connect(lib / 'search.sqlite') as db:
                for query, uid in [('"available chlorine"', 'nsw-boil-water-alert'),
                                   ('"building owners"', 'nsw-water-header-tanks')]:
                    found = {r[0] for r in db.execute('SELECT doc_id FROM pages WHERE pages MATCH ?', (query,))}
                    self.assertIn(uid, found)
            with patch.object(server, 'APP', b.ROOT), patch.object(server, 'LIB', lib), \
                 patch.object(server, '_cat', {'mtime': None}), patch.object(server, 'zim_names', return_value=[]):
                def resolve():
                    return server.topics_resolved()
                def refs():
                    return [r for t in resolve() for _, r in items(t) if r.get('doc') in self.uids]
                initial = resolve()
                self.assertEqual(len(refs()), 14)
                for uid in self.uids:
                    source = lib / 'pages/au' / (uid + '.html'); held = Path(d) / (uid + '.html')
                    source.rename(held)
                    self.assertEqual(len(refs()), 7)
                    self.assertFalse(any(r['doc'] == uid for r in refs()))
                    held.rename(source)
                    self.assertEqual(resolve(), initial)
                self.assertEqual(cat.read_bytes(), saved)
                self.assertEqual(cat.stat().st_mtime_ns, mtime)


if __name__ == '__main__':
    unittest.main()
