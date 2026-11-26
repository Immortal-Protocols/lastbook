import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import sqlite3
import tempfile
import unittest
from contextlib import closing
from unittest.mock import patch

HERE = Path(__file__).parent
def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod

b = module('personal_au', HERE / 'build_au_personal_first_aid.py')


class Personal(unittest.TestCase):
    def test_ordinary_first_aid_links_preserve_sources_and_existing_choice_fields(self):
        audit = json.loads((b.ROOT / 'docs/AUSTRALIA-FIRST-AID-SELECTION-20261127.json').read_text())
        guide = json.loads((b.ROOT / 'content/topics/hurt.json').read_text())
        # Later public bat guidance has its own pre-change baseline and availability tests.
        for c in guide['choices']:
            c['read'] = [r for r in c.get('read', []) if r.get('doc') != 'nsw-bat-lyssavirus']
        personal = {r['id']: r for r in json.loads(b.MANIFEST.read_text())['sources']}
        self.assertEqual(audit['counts'], dict(choices=6, links=9, existing_public_links=2,
                                             personal_only_links=7, unique_personal_originals=6))
        for choice in guide['choices']:
            added = [p for p in audit['placements'] if p['choice'] == choice['id']]
            self.assertEqual(choice['read'][:len(added)], [p['reference'] for p in added])
            for p in added:
                ref = p['reference']
                if p['distribution'] == 'personal-only':
                    record = personal[ref['doc']]
                    self.assertEqual(record['sha256'], p['source_sha256'])
                    self.assertLessEqual(ref['page'], record['pages'])
                    self.assertIn('personal use only', ref['note'])
            choice['read'] = choice['read'][len(added):]
        changed = audit['changed_existing_reference']
        ref = next(r for c in guide['choices'] for r in c['read']
                   if r.get('doc') == changed['doc'] and r.get('page') == changed['page'])
        self.assertEqual(ref['note'], changed['new_note'])
        self.assertIn('differs from ANZCOR', ref['note'])
        ref['note'] = changed['old_note']
        self.assertEqual(b.digest(json.dumps(guide, sort_keys=True).encode()), audit['baseline_guide_sha256'])
        self.assertEqual(len(audit['public_candidates']), 4)
        self.assertIn('technical medium/format changes', audit['public_candidates'][0]['technical_modifications'])

    def test_first_aid_cards_follow_individual_source_availability(self):
        import server
        audit = json.loads((b.ROOT / 'docs/AUSTRALIA-FIRST-AID-SELECTION-20261127.json').read_text())
        guide = json.loads((b.ROOT / 'content/topics/hurt.json').read_text())
        public = module('first_aid_public', HERE / 'build_australia_reference.py').checked_sources()[0]['sources']
        personal = json.loads(b.MANIFEST.read_text())['sources']
        sources = {r['id']: r for r in public + personal}
        added_ids = {p['reference']['doc'] for p in audit['placements']}
        base = {r['doc']: dict(id=r['doc'], title='Baseline source', path='pages/baseline.html', kind='html')
                for c in guide['choices'] for r in c['read'] if r['doc'] not in added_ids}
        cases = [({}, 0), ({r['id']: r for r in public}, 2),
                 ({r['id']: r for r in personal}, 7),
                 ({'personal-au-snakebite': sources['personal-au-snakebite']}, 1), (sources, 9)]
        for available, expected in cases:
            with self.subTest(available=len(available)), \
                 tempfile.TemporaryDirectory() as d, patch.object(server, 'LIB', Path(d)), \
                 patch.object(server, 'APP', b.ROOT), patch.object(server, 'topics', return_value=[guide]), \
                 patch.object(server, 'zim_names', return_value=[]), \
                 patch.object(server, 'catalog', return_value={'by_id': {**base, **available}}), \
                 patch.object(socket, 'socket', side_effect=AssertionError('network')):
                for record in {**base, **available}.values():
                    path = Path(d) / record['path']; path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text('Source fixture', encoding='utf-8')
                resolved = server.topics_resolved()[0]
            refs = [r for c in resolved['choices'] for r in c['read'] if r['doc'] in added_ids]
            self.assertEqual(len(refs), expected)
            for ref in refs:
                self.assertEqual(ref['src']['id'], ref['doc'])
                self.assertEqual(ref['src']['path'], available[ref['doc']]['path'])

    def test_expanded_metadata_covers_both_indexes_and_preserves_the_default(self):
        audit = json.loads((b.ROOT / 'content/regions/au/PERSONAL-EXTENDED-SOURCE-AUDIT-20261127.json').read_text())
        default = b.source_records()
        expanded = b.source_records('bls-first-aid')
        self.assertEqual((len(expanded), sum(r['pages'] for r in expanded)), (35, 263))
        self.assertEqual(b.digest(b.MANIFEST.read_bytes()), audit['basic_default']['manifest_sha256'])
        by_id = {r['id']: r for r in expanded}
        self.assertEqual([by_id[r['id']] for r in default], default)
        self.assertTrue(all(r['distribution'] == 'personal-only' for r in expanded))
        self.assertEqual({s['number'] for s in audit['sources'] if s['section'] == 'bls'},
                         {'2', '3', '4', '5', '6', '7', '8'})
        self.assertEqual(len([s for s in audit['sources'] if s['section'] == 'first-aid']), 28)
        seizure = next(s for s in audit['sources'] if s['number'] == '9.2.4')
        self.assertIn('/first-aid/9-2-4-', seizure['page']['url'])
        for source in audit['sources']:
            record = by_id[source['id']]
            self.assertEqual((record['sha256'], record['bytes'], record['pages']),
                             (source['pdf']['raw_sha256'], source['pdf']['bytes'], source['pages']))
        with self.assertRaisesRegex(ValueError, 'Unknown personal source collection'):
            b.source_records('unknown')

    def test_expanded_guide_preserves_basic_routes_and_follows_individual_files(self):
        import copy
        import server
        from tools.validate_topics import items
        audit = json.loads((b.ROOT / 'content/regions/au/PERSONAL-EXTENDED-SOURCE-AUDIT-20261127.json').read_text())
        guide = json.loads((b.ROOT / 'content/topics/au-personal-first-aid.json').read_text())
        restored = copy.deepcopy(guide)
        restored['choices'] = [c for c in restored['choices'] if not c['id'].startswith('extended-')]
        additions = {r['id'] for r in b.source_records('bls-first-aid')} - {r['id'] for r in b.source_records()}
        for key in ['prepare', 'learn']:
            restored[key] = [r for r in restored[key] if r.get('doc') not in additions]
        self.assertEqual(b.digest(json.dumps(restored, sort_keys=True).encode()), audit['guide_baseline_sha256'])
        for selection, expected in [('basic', 21), ('bls-first-aid', 108)]:
            records = {r['id']:r for r in b.source_records(selection)}
            records['personal-au-reference'] = dict(id='personal-au-reference',kind='html',path='pages/personal-au/index.html',title='Source directory')
            with tempfile.TemporaryDirectory() as d, patch.object(server, 'LIB', Path(d)), \
                 patch.object(server, 'topics', return_value=[guide]), patch.object(server, 'zim_names', return_value=[]), \
                 patch.object(server, 'catalog', return_value={'by_id': records}), \
                 patch.object(socket, 'socket', side_effect=AssertionError('network')):
                for record in records.values():
                    path = Path(d) / record['path'];path.parent.mkdir(parents=True,exist_ok=True);path.write_text('fixture')
                resolved = server.topics_resolved()[0]
                self.assertEqual(len(list(items(resolved))), expected)
                if selection == 'bls-first-aid':
                    path = Path(d) / records['personal-au-guideline-4']['path']
                    held = Path(d) / 'held';path.rename(held)
                    missing = server.topics_resolved()[0]
                    self.assertEqual(len(list(items(missing))), 105)
                    self.assertFalse(any(r.get('doc') == 'personal-au-guideline-4' for _,r in items(missing)))
                    held.rename(path)
                    self.assertEqual(server.topics_resolved()[0], resolved)

    def test_collection_selection_reaches_the_builder_without_changing_basic_hub(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);record,data=self.source(root)
            for name in ['basic','bls-first-aid']:
                with patch.object(b, 'source_records', return_value=[record]) as selected, \
                     patch.object(b, 'pdf_pages', return_value=['Synthetic source body']), \
                     patch.object(socket, 'socket', side_effect=AssertionError('network')):
                    self.assertEqual(b.build(root/name,root,collection=name),(1,1))
                    selected.assert_called_once_with(name)
                notice=json.loads((root/name/'PERSONAL-USE-ONLY.json').read_text())
                self.assertEqual(notice.get('source_collection'),None if name=='basic' else name)
                body=(root/name/'library-data/pages/personal-au/index.html').read_text()
                self.assertEqual('Optional Basic Life Support' in body,name=='bls-first-aid')
                self.assertEqual((root/name/'library-data/documents/personal-au/personal-au-test.pdf').read_bytes(),data)

    def source(self, cache):
        data = b'%PDF-1.7\nsynthetic preservation fixture'
        (cache / 'personal-au-test.pdf').write_bytes(data)
        return {'id': 'personal-au-test', 'kind': 'pdf', 'title': 'Synthetic guideline', 'pages': 1,
                'publisher': 'Example authority', 'collection': 'Personal reference', 'category': 'first-aid',
                'pdf_url': 'https://www.anzcor.org/example/downloadpdf', 'distribution': 'personal-only',
                'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}, data

    def test_cache_build_is_offline_preserves_bytes_and_marks_all_records_personal(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); r, data = self.source(root); out = root / 'LastbookData'
            with patch.object(socket, 'socket', side_effect=AssertionError('network')), \
                    patch.object(b, 'pdf_pages', return_value=['Synthetic source body']):
                self.assertEqual(b.build(out, root, [r]), (1, 1))
            lib = out / 'library-data'; cat = json.loads((lib / 'catalog.json').read_text(encoding='utf-8'))
            self.assertEqual((lib / cat[0]['path']).read_bytes(), data)
            self.assertTrue(all(x['distribution'] == 'personal-only' for x in cat))
            self.assertTrue((out / 'PERSONAL-USE-ONLY.json').is_file())
            with closing(sqlite3.connect(lib / 'search.sqlite')) as db:
                self.assertEqual(db.execute("SELECT doc_id,page FROM pages WHERE pages MATCH 'body'").fetchall(),
                                 [('personal-au-test', 1)])

    def test_changed_source_cannot_leave_a_usable_library(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); r, _ = self.source(root); (root / 'personal-au-test.pdf').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'Source changed'):
                b.build(root / 'LastbookData', root, [r])
            self.assertFalse((root / 'LastbookData').exists())
            self.assertEqual(list(root.glob('.personal-au-*')), [])

    def test_existing_library_and_unapproved_hosts_are_refused(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d); (out / 'keep').write_text('keep', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'already exists'): b.build(out, records=[])
            self.assertEqual((out / 'keep').read_text(encoding='utf-8'), 'keep')
        for url in ['http://www.anzcor.org/x', 'https://example.invalid/x', 'https://user@www.anzcor.org/x',
                    'https://www.anzcor.org:444/x']:
            with self.assertRaises(ValueError): b.allowed_url(url)

    def test_public_reference_builder_excludes_personal_sources(self):
        public = module('public_au', HERE / 'build_australia_reference.py')
        _, checked = public.checked_sources()
        personal = b.source_records('bls-first-aid')
        self.assertTrue({r['id'] for r in personal}.isdisjoint({r['id'] for r, *_ in checked}))
        self.assertFalse(any(r['kind'] == 'pdf' or r.get('distribution') == 'personal-only' for r, *_ in checked))


if __name__ == '__main__': unittest.main()
