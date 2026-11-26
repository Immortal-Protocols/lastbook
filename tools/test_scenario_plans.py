"""Scenario coverage, old-source preservation and actual offline availability."""
import copy
import json
import re
import socket
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tools import build_australia_reference as b
from tools.test_build_australia_reference import before_scenario_extension
from tools.validate_topics import items


class ScenarioPlans(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audit=json.loads((b.SOURCES/'SCENARIO-PLANS-AUDIT-20261127.json').read_text())
        cls.ids={x['id'] for x in cls.audit['plans']}

    def test_closed_source_graph_and_preserved_prior_collection(self):
        manifest, sources=b.checked_sources()
        records={r['id']:r for r,_,_,_ in sources}
        self.assertEqual(len(records),129)
        for uid,digest in self.audit['base_sources_sha256'].items():
            if uid!='au-reference':
                self.assertEqual(records[uid]['sha256'],digest,uid)
        hub=(b.SOURCES/'sources/au-reference.html').read_bytes()
        start=hub.index(b'<h2>Household and rural scenario plans</h2>')
        restored=hub[:start]+hub[hub.index(b'</body>',start):]
        self.assertEqual(b.digest(restored),self.audit['base_hub_sha256'])
        for plan in self.audit['plans']:
            record=records[plan['id']]
            self.assertEqual(record['publisher'],'Lastbook Australia contributors')
            self.assertEqual(record['license'],'CC-BY-4.0')
            self.assertEqual(record['source_url'],'')
            page=(b.SOURCES/record['snapshot']).read_text()
            self.assertEqual(record['sha256'],plan['sha256'])
            linked=set(re.findall(r'href="/pages/au/([^"]+)\.html"',page))
            self.assertTrue(set(plan['source_ids'])<=linked)
            self.assertTrue(linked<=set(records))
            self.assertNotIn('href="https://',page)
            self.assertNotIn('DAY_ROWS',page)
        home=(b.SOURCES/records['au-seven-day-power']['snapshot']).read_text()
        rows=re.findall(r'<tr><td>([1-7])</td>',home)
        self.assertEqual(rows,list('1234567'))
        self.assertIn('not an official prediction, a safe waiting period',home)
        rural=(b.SOURCES/records['au-flood-isolated-property']['snapshot']).read_text()
        self.assertIn('it may exceed a week',rural)
        self.assertIn('Never drive, walk or swim through floodwater',rural)

    def test_equal_first_choices_and_previous_guide_content_preserved(self):
        guides={}
        for gid,digest in self.audit['baseline_guides'].items():
            guide=json.loads((b.ROOT/'content/topics'/(gid+'.json')).read_text())
            self.assertEqual([c['id'] for c in guide['choices'][:2]],
                             ['seven-day-power','flood-isolated-property'])
            restored=before_scenario_extension(copy.deepcopy(guide))
            # The local combined checkout independently adds optional personal sources.
            from tools import test_build_australia_reference as historical
            if hasattr(historical,'before_later_trauma_extension'):
                restored=historical.before_later_trauma_extension(restored)
            self.assertEqual(b.digest(json.dumps(restored,sort_keys=True).encode()),digest,gid)
            guides[gid]=[ref for _,ref in items(guide) if ref.get('doc') in self.ids]
        self.assertEqual(guides['au-household'],guides['au-rural'])
        self.assertEqual(len(guides['au-household']),6)

    def test_actual_offline_search_reader_paths_and_loss_restore(self):
        import server
        with tempfile.TemporaryDirectory() as d, patch.object(socket,'socket',side_effect=AssertionError('network')):
            data=Path(d)/'LastbookData';b.build(data);lib=data/'library-data'
            cat=lib/'catalog.json';saved=(cat.read_bytes(),cat.stat().st_mtime_ns)
            with sqlite3.connect(lib/'search.sqlite') as db:
                for uid,query in [('au-seven-day-power','"seven consecutive days"'),
                                  ('au-flood-isolated-property','"longer than planned"')]:
                    found={r[0] for r in db.execute('SELECT doc_id FROM pages WHERE pages MATCH ?',(query,))}
                    self.assertIn(uid,found)
            with patch.object(server,'APP',b.ROOT),patch.object(server,'LIB',lib),\
                 patch.object(server,'_cat',{'mtime':None}),patch.object(server,'zim_names',return_value=[]):
                def resolve():return server.topics_resolved()
                def refs():return [r for g in resolve() for _,r in items(g) if r.get('doc') in self.ids]
                original=resolve();self.assertEqual(len(refs()),12)
                for uid in self.ids:
                    source=lib/'pages/au'/(uid+'.html');held=Path(d)/(uid+'.html');source.rename(held)
                    try:
                        self.assertEqual(len(refs()),6)
                        self.assertFalse(any(r['doc']==uid for r in refs()))
                    finally:held.rename(source)
                    self.assertEqual(resolve(),original)
                self.assertEqual((cat.read_bytes(),cat.stat().st_mtime_ns),saved)


if __name__=='__main__':unittest.main()
