"""Original-byte, nonprofit-boundary and out-of-place composition controls."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import socket
import sqlite3
import unittest
from unittest.mock import patch

from tools import build_au_trauma_reference as b
from tools import test_compose_australia_reference as fixtures


class TraumaReference(unittest.TestCase):
    def test_guides_preserve_existing_content_and_follow_actual_source_availability(self):
        import copy
        import server
        from tools.validate_topics import items
        audit=json.loads((b.ROOT/'content/regions/au/TRAUMA-SOURCE-AUDIT-20261127.json').read_text(encoding='utf-8'))
        self.assertEqual(len(audit['guide_placements']),10)
        gaps=json.loads((b.ROOT/'content/gaps.json').read_text(encoding='utf-8'));change=audit['gap_update']
        self.assertEqual(gaps[change['guide']]['missing'][change['index']],change['after'])
        gaps[change['guide']]['missing'][change['index']]=change['before']
        self.assertEqual(hashlib.sha256(json.dumps(gaps,sort_keys=True).encode()).hexdigest(),audit['gaps_baseline_sha256'])
        for gid,digest in audit['guide_baseline_sha256'].items():
            guide=json.loads((b.ROOT/'content/topics'/(gid+'.json')).read_text(encoding='utf-8'))
            restored=copy.deepcopy(guide)
            restored['choices']=[c for c in restored['choices'] if c['id']!='adult-traumatic-events']
            for c in restored['choices']:c['read']=[r for r in c['read'] if r.get('doc')!=b.UID]
            for key in ['prepare','learn']:restored[key]=[r for r in restored[key] if r.get('doc')!=b.UID]
            self.assertEqual(hashlib.sha256(json.dumps(restored,sort_keys=True).encode()).hexdigest(),digest)
            with self.subTest(guide=gid),patch.object(server,'topics',return_value=[guide]), \
                    patch.object(server,'catalog',return_value={'by_id':{b.UID:{**self.source,'path':b.PDF}}}), \
                    patch.object(server,'LIB',self.root/'availability'),patch.object(server,'zim_names',return_value=[]):
                target=server.LIB/b.PDF;target.parent.mkdir(parents=True,exist_ok=True)
                guide.pop('requires_docs',None)
                absent=server.topics_resolved()[0]
                self.assertFalse(any(r.get('doc')==b.UID for _,r in items(absent)))
                target.write_bytes(self.pdf);present=server.topics_resolved()[0]
                refs=[r for _,r in items(present) if r.get('doc')==b.UID]
                self.assertEqual(len(refs),1 if gid=='health' else 3)
                self.assertTrue(all(r['page']==1 and 'Nonprofit' in r['note'] for r in refs))
                target.unlink();self.assertEqual(server.topics_resolved()[0],absent)

    def setUp(self):
        self.fixture = fixtures.Compose(); self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root, self.base, self.out = self.fixture.root, self.fixture.base, self.fixture.out
        self.source = b.source_record()
        self.pdf = b'%PDF-1.7\nSynthetic nonprofit original fixture'
        self.source.update(bytes=len(self.pdf), sha256=hashlib.sha256(self.pdf).hexdigest())
        self.pages = ['Synthetic source page ' + str(n) + ' quartz' for n in range(1, 8)]
        self.cache = self.root / 'cache'; self.cache.mkdir()
        (self.cache / (b.UID + '.pdf')).write_bytes(self.pdf)
        self.addCleanup(patch.stopall)
        patch.object(b, 'source_record', return_value=self.source).start()
        patch.object(b, 'pdf_pages', return_value=self.pages).start()
        self.socket = patch.object(socket, 'socket', side_effect=AssertionError('No fixture network')).start()

    def build(self, **kwargs):
        return b.build(self.out, cache=self.cache, nonprofit_purpose=True, **kwargs)

    def fail_clean(self, message, **kwargs):
        before = self.fixture.hashes(self.base); inventory = b.common.inventory(self.base)
        with self.assertRaisesRegex((ValueError, OSError, sqlite3.Error), message):
            self.build(base=self.base, **kwargs)
        self.assertFalse(self.out.exists())
        self.assertEqual(self.fixture.hashes(self.base), before)
        self.assertEqual(b.common.inventory(self.base), inventory)
        self.assertEqual(list(self.root.glob('.au-trauma-*')), [])

    def test_standalone_preserves_original_and_every_physical_search_page(self):
        self.pages[0] += '\r\nSecond source line with preserved PDF extraction endings.'
        report = self.build(); self.assertEqual((report['records'], report['search_units']), (1, 7))
        self.assertEqual((self.out / 'library-data' / b.PDF).read_bytes(), self.pdf)
        record = b.common.read_records(self.out)[0]
        self.assertEqual(record['distribution'], 'nonprofit-only')
        self.assertEqual(record['attribution'], self.source['attribution'])
        with closing(b.common.read_only(self.out / 'library-data/search.sqlite')) as db:
            self.assertEqual(db.execute('SELECT page,path,body FROM pages ORDER BY rowid').fetchall(),
                [(n, b.PDF, text) for n, text in enumerate(self.pages, 1)])
        inventory = b.common.inventory(self.out); b.verify(self.out)
        self.assertEqual(inventory, b.common.inventory(self.out)); self.assertEqual(self.socket.call_count, 0)

    def test_full_composition_keeps_base_bytes_rows_and_personal_marker(self):
        marker = self.base / 'PERSONAL-USE-ONLY.json'; marker.write_text('{"distribution":"personal-only"}', encoding='utf-8')
        before = self.fixture.hashes(self.base); inventory = b.common.inventory(self.base)
        with closing(b.common.read_only(self.base / 'library-data/search.sqlite')) as db:
            old_rows = db.execute('SELECT rowid,* FROM pages ORDER BY rowid').fetchall()
        report = self.build(base=self.base)
        self.assertTrue(report['base_personal_marker_preserved'])
        self.assertEqual((report['base_records'], report['records']), (1, 2))
        self.assertEqual(report['search_units'], report['base_search_units'] + 7)
        self.assertEqual((self.out / marker.name).read_bytes(), marker.read_bytes())
        with closing(b.common.read_only(self.out / 'library-data/search.sqlite')) as db:
            self.assertEqual(db.execute('SELECT rowid,* FROM pages WHERE doc_id!=? ORDER BY rowid', (b.UID,)).fetchall(), old_rows)
        changed = {'pack.json','pack-manifest.tsv','pack-contents.tsv','library-data/catalog.json','library-data/search.sqlite','library-data/summary.json'}
        for rel, digest in before.items():
            if rel not in changed:
                self.assertEqual(b.common.sha256(self.out / rel), digest, rel)
        self.assertEqual(self.fixture.hashes(self.base), before)
        self.assertEqual(b.common.inventory(self.base), inventory)
        self.assertEqual(self.socket.call_count, 0)
        b.verify(self.out)

    def test_explicit_nonprofit_and_exactly_one_source_mode_required(self):
        for kw in [{}, {'cache': self.cache}, {'nonprofit_purpose': True},
                {'cache': self.cache, 'download': True, 'nonprofit_purpose': True}]:
            with self.assertRaises(ValueError): b.build(self.out, **kw)
        self.assertFalse(self.out.exists()); self.assertEqual(self.socket.call_count, 0)

    def test_existing_and_dangling_output_are_preserved(self):
        self.out.mkdir(); sentinel=self.out/'keep';sentinel.write_text('unchanged',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'already exists'): self.build()
        self.assertEqual(sentinel.read_text(encoding='utf-8'),'unchanged')
        sentinel.unlink();self.out.rmdir();self.out.symlink_to(self.root/'absent')
        with self.assertRaisesRegex(ValueError,'already exists'): self.build()
        self.assertTrue(self.out.is_symlink())

    def test_wrong_original_and_page_shape_fail_without_publishing(self):
        (self.cache / (b.UID+'.pdf')).write_bytes(self.pdf+b'changed');self.fail_clean('changed')
        (self.cache / (b.UID+'.pdf')).write_bytes(self.pdf)
        for pages in [self.pages[:-1],self.pages[:-1]+[' ']]:
            with patch.object(b,'pdf_pages',return_value=pages): self.fail_clean('page count or text')

    def test_exact_official_host_and_redirect_boundary(self):
        b.allowed_url(self.source['pdf_url'])
        for url in ['http://mhfainternational.org/x','https://mhfainternational.org.evil.invalid/x',
                'https://example.org/x','https://user@mhfainternational.org/x','https://mhfainternational.org:443/x',
                'file:///tmp/source.pdf']:
            with self.assertRaises(ValueError): b.allowed_url(url)
        with self.assertRaises(ValueError):
            b.Redirect().redirect_request(None,None,302,'redirect',{},'https://example.org/source.pdf')

    def test_base_collision_unsafe_tree_and_overlap_are_refused(self):
        target=self.base/'library-data'/b.PDF;target.parent.mkdir(parents=True);target.write_bytes(b'existing')
        self.fail_clean('already exists');target.unlink()
        link=self.base/'unsafe';link.symlink_to(self.root/'absent')
        with self.assertRaisesRegex(ValueError,'link or special'):self.build(base=self.base)
        self.assertTrue(link.is_symlink());self.assertFalse(self.out.exists());link.unlink()
        with self.assertRaisesRegex(ValueError,'separate directory'):
            b.build(self.base/'nested',cache=self.cache,nonprofit_purpose=True,base=self.base)
        with self.assertRaisesRegex(ValueError,'ordinary library'):
            pointer=self.root/'base-link';pointer.symlink_to(self.base)
            b.build(self.out,cache=self.cache,nonprofit_purpose=True,base=pointer)

    def test_existing_source_id_and_index_collision_are_refused(self):
        p=self.base/'library-data/catalog.json';records=json.loads(p.read_text(encoding='utf-8'));records[0]['id']=b.UID
        p.write_text(json.dumps(records),encoding='utf-8');self.fail_clean('already exists')
        records[0]['id']='fixture-restored';p.write_text(json.dumps(records),encoding='utf-8')
        with closing(sqlite3.connect(self.base/'library-data/search.sqlite')) as db:
            db.execute('UPDATE pages SET doc_id=?',(b.UID,));db.commit()
        self.fail_clean('ids already exist')

    def test_live_journal_and_concurrent_base_mutation_are_refused(self):
        journal=self.base/'library-data/search.sqlite-journal';journal.write_bytes(b'active')
        with self.assertRaisesRegex(ValueError,'Close Lastbook'):self.build(base=self.base)
        self.assertFalse(self.out.exists());self.assertEqual(journal.read_bytes(),b'active');journal.unlink()
        original=b.common.clone_or_copy
        def changed(src,dst):
            result=original(src,dst)
            (self.base/'concurrent-note').write_text('external change',encoding='utf-8')
            return result
        with patch.object(b.common,'clone_or_copy',side_effect=changed),self.assertRaisesRegex(ValueError,'Base changed'):
            self.build(base=self.base)
        self.assertEqual((self.base/'concurrent-note').read_text(encoding='utf-8'),'external change')
        self.assertFalse(self.out.exists());self.assertEqual(list(self.root.glob('.au-trauma-*')),[])

    def test_failure_after_copy_and_publication_race_preserve_base(self):
        with patch.object(b,'verify',side_effect=ValueError('forced validation failure')):
            self.fail_clean('forced validation')
        original=b.common.publish
        def race(staged,output):
            output.mkdir();(output/'keep').write_text('raced',encoding='utf-8');original(staged,output)
        before=self.fixture.hashes(self.base)
        with patch.object(b.common,'publish',side_effect=race),self.assertRaises(OSError):self.build(base=self.base)
        self.assertEqual((self.out/'keep').read_text(encoding='utf-8'),'raced')
        self.assertEqual(self.fixture.hashes(self.base),before)

    def test_verifier_detects_source_notice_original_and_index_tampering(self):
        self.build()
        for rel in [b.NOTICE,'library-data/'+b.PDF,'library-data/'+b.TEXT]:
            p=self.out/rel;data=p.read_bytes();p.write_bytes(data+b'changed')
            with self.assertRaises(ValueError):b.verify(self.out)
            p.write_bytes(data)
        b.verify(self.out)


if __name__ == '__main__': unittest.main()
