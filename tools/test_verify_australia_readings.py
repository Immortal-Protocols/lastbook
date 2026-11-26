"""Maintenance checks must find source/index damage without changing the library."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import shutil
import socket
import sqlite3
import unittest
from unittest.mock import patch

from tools import verify_australia_readings as v
from tools import compose_au_personal_first_aid as pc
from tools import test_compose_australia_reference as fixtures


class Readings(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.Compose(); self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root, self.base = self.fixture.root, self.fixture.base
        log = self.base / 'derived/logs/lastbook.log'; log.parent.mkdir(parents=True)
        log.write_text('Before app use\n', encoding='utf-8')
        self.cache = self.root / 'cache'; self.cache.mkdir()
        self.private_pdf = b'%PDF-1.7\nSynthetic private original'
        self.nonprofit_pdf = b'%PDF-1.7\nSynthetic nonprofit original'
        self.private_pages = ['Private source quartz\r\nOriginal second line.', 'Private source cobalt']
        self.nonprofit_pages = ['Nonprofit physical page ' + str(n) + ' zircon' for n in range(1, 8)]
        self.private = dict(id='personal-au-fixture', kind='pdf', title='Synthetic private source', pages=2,
            publisher='Example', collection='Personal reference', category='first-aid',
            pdf_url='https://www.anzcor.org/fixture/downloadpdf', distribution='personal-only',
            bytes=len(self.private_pdf), sha256=hashlib.sha256(self.private_pdf).hexdigest())
        self.nonprofit = v.trauma.source_record()
        self.nonprofit.update(bytes=len(self.nonprofit_pdf), sha256=hashlib.sha256(self.nonprofit_pdf).hexdigest())
        (self.cache / 'personal-au-fixture.pdf').write_bytes(self.private_pdf)
        (self.cache / (v.trauma.UID + '.pdf')).write_bytes(self.nonprofit_pdf)
        self.addCleanup(patch.stopall)
        self.network = patch.object(socket, 'socket', side_effect=AssertionError('No network')).start()
        patch.object(v.personal, 'source_records', return_value=[self.private]).start()
        patch.object(v.personal, 'pdf_pages', return_value=self.private_pages).start()
        patch.object(v.trauma, 'source_record', return_value=self.nonprofit).start()
        patch.object(v.trauma, 'pdf_pages', return_value=self.nonprofit_pages).start()
        self.pub, self.pers, self.data = [self.root / n for n in ('public', 'personal', 'mixed')]
        v.common.compose(self.base, self.pub)
        pc.compose(self.pub, self.pers, cache=self.cache, records=[self.private])
        v.trauma.build(self.data, base=self.pers, cache=self.cache, nonprofit_purpose=True)

    def check(self, **kwargs):
        return v.verify(self.data, **kwargs)

    def mutate_catalog(self, uid, **fields):
        p = self.data / 'library-data/catalog.json'
        records = json.loads(p.read_text(encoding='utf-8'))
        next(r for r in records if r['id'] == uid).update(fields)
        p.write_text(json.dumps(records), encoding='utf-8')

    def sql(self, query, args=()):
        with closing(sqlite3.connect(self.data / 'library-data/search.sqlite')) as db:
            db.execute(query, args); db.commit()

    def test_all_sources_after_app_log_change_without_library_writes(self):
        v.trauma.verify(self.data)
        (self.data / 'derived/logs/lastbook.log').write_text('Normal later app activity\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'derived/logs/lastbook.log'):
            v.trauma.verify(self.data)
        before, inventory = self.fixture.hashes(self.data), v.common.inventory(self.data)
        report = self.check(required=['public', 'personal', 'trauma'])
        self.assertEqual((report['readings'], report['search_pages']), (128, 135))
        self.assertEqual({r['collection'] for r in report['collections']}, v.COLLECTIONS)
        self.assertEqual(report['target_writes'], 0)
        self.assertEqual(self.fixture.hashes(self.data), before)
        self.assertEqual(v.common.inventory(self.data), inventory)
        self.assertEqual(self.network.call_count, 0)

    def test_target_database_is_never_opened_by_sqlite(self):
        real = sqlite3.connect; target = str(self.data / 'library-data/search.sqlite')
        def observed(database, *args, **kwargs):
            self.assertNotIn(target, str(database))
            self.assertNotIn((self.data / 'library-data/search.sqlite').as_uri(), str(database))
            return real(database, *args, **kwargs)
        with patch.object(sqlite3, 'connect', side_effect=observed): self.check()

    def test_readonly_library_files_and_directories_are_supported(self):
        paths = list(self.data.rglob('*'))
        try:
            for p in paths: p.chmod(0o555 if p.is_dir() else 0o444)
            self.data.chmod(0o555)
            self.assertEqual(self.check()['target_writes'], 0)
        finally:
            self.data.chmod(0o755)
            for p in paths: p.chmod(0o755 if p.is_dir() else 0o644)

    def test_missing_original_with_intact_catalogue_fails(self):
        (self.data / 'library-data' / v.trauma.PDF).unlink()
        with self.assertRaises(FileNotFoundError): self.check()

    def test_altered_original_fails_even_when_catalogue_is_rehashed(self):
        p = self.data / 'library-data' / v.trauma.PDF; p.write_bytes(self.nonprofit_pdf + b'changed')
        self.mutate_catalog(v.trauma.UID, bytes=p.stat().st_size, sha256=v.common.sha256(p))
        with self.assertRaisesRegex(ValueError, 'changed or is incomplete'): self.check()

    def test_index_body_and_agreeing_flat_text_must_match_original_projection(self):
        changed = self.nonprofit_pages[:]; changed[0] = 'Different source instructions'
        (self.data / 'library-data' / v.trauma.TEXT).write_text('\n\f\n'.join(changed), encoding='utf-8')
        self.sql('UPDATE pages SET body=? WHERE doc_id=? AND page=1', (changed[0], v.trauma.UID))
        with self.assertRaisesRegex(ValueError, 'source text differs'): self.check()

    def test_index_only_body_and_page_boundary_changes_fail(self):
        self.sql('UPDATE pages SET body=? WHERE doc_id=? AND page=1', ('Changed indexed text', v.trauma.UID))
        with self.assertRaisesRegex(ValueError, 'search pages differ'): self.check()
        self.sql('UPDATE pages SET body=?,page=0 WHERE doc_id=? AND page=1', (self.nonprofit_pages[0], v.trauma.UID))
        with self.assertRaisesRegex(ValueError, 'search pages differ'): self.check()

    def test_index_titles_and_duplicate_source_pages_fail(self):
        self.sql('UPDATE pages SET title=? WHERE doc_id=?', ('Wrong source title', v.trauma.UID))
        with self.assertRaisesRegex(ValueError, 'search pages differ'): self.check()
        self.sql('UPDATE pages SET title=? WHERE doc_id=?', (self.nonprofit['title'], v.trauma.UID))
        self.sql('INSERT INTO pages SELECT * FROM pages WHERE doc_id=? AND page=1', (v.trauma.UID,))
        with self.assertRaisesRegex(ValueError, 'search pages differ'): self.check()

    def test_source_flags_and_visible_conditions_are_verified(self):
        self.mutate_catalog(v.trauma.UID, distribution='public')
        with self.assertRaisesRegex(ValueError, 'metadata or restrictions'): self.check()
        self.mutate_catalog(v.trauma.UID, distribution='nonprofit-only', notes='Conditions removed')
        with self.assertRaisesRegex(ValueError, 'metadata or restrictions'): self.check()

    def test_source_notice_acknowledgement_and_nonprofit_declaration_are_verified(self):
        p = self.data / v.trauma.NOTICE; original=p.read_bytes(); notice=json.loads(original)
        notice['source']['attribution']='Removed credit';p.write_text(json.dumps(notice),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'acknowledgement differ'):self.check()
        p.write_bytes(original);p=self.data/v.trauma.RECEIPT;r=json.loads(p.read_text(encoding='utf-8'))
        r['nonprofit_purpose']=False;p.write_text(json.dumps(r),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'nonprofit source declaration'):self.check()

    def test_public_marker_and_original_html_are_pinned(self):
        p=self.data/'AUSTRALIA-REFERENCE.json';data=p.read_bytes();manifest=json.loads(data)
        manifest['sources']=manifest['sources'][:-1];p.write_text(json.dumps(manifest),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'matching tool revision'):self.check()
        p.write_bytes(data);uid=manifest['sources'][0]['id'];record=next(r for r in v.common.read_records(self.data) if r['id']==uid)
        p=self.data/'library-data'/record['path'];p.write_bytes(p.read_bytes()+b'<p>changed</p>')
        with self.assertRaisesRegex(ValueError,'Original reading differs'):self.check()

    def test_personal_notice_and_extra_private_index_ids_fail(self):
        p=self.data/v.PERSONAL_NOTICE;data=p.read_bytes();notice=json.loads(data)
        notice['distribution']='public';p.write_text(json.dumps(notice),encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'Personal source notice differs'):self.check()
        p.write_bytes(data)
        self.sql("UPDATE pages SET doc_id='personal-au-unrecognised' WHERE doc_id='personal-au-fixture'")
        with self.assertRaisesRegex(ValueError,'Personal source ids differ'):self.check()

    def test_entire_removed_collection_is_reported_by_require(self):
        p=self.data/'library-data/catalog.json';records=json.loads(p.read_text(encoding='utf-8'))
        p.write_text(json.dumps([r for r in records if r['id']!=v.trauma.UID]),encoding='utf-8')
        self.sql('DELETE FROM pages WHERE doc_id=?',(v.trauma.UID,))
        shutil.rmtree(self.data/'library-data/documents/au-nonprofit')
        (self.data/'library-data'/v.trauma.TEXT).unlink()
        for name in [v.trauma.NOTICE,v.trauma.RECEIPT]:(self.data/name).unlink()
        self.assertEqual({r['collection'] for r in self.check()['collections']},{'public','personal'})
        with self.assertRaisesRegex(ValueError,'Required collections are absent: trauma'):
            self.check(required=['public','personal','trauma'])

    def test_unrelated_base_edits_are_outside_the_reported_scope(self):
        (self.data/'unknown/user-note.txt').write_text('Later private note',encoding='utf-8')
        report=self.check();self.assertIn('Other base-library files',report['not_checked'])
        self.assertEqual(report['readings'],128)

    def test_source_links_and_hardlinks_are_refused(self):
        p=self.data/'library-data'/v.trauma.PDF;hold=self.root/'held.pdf';p.rename(hold);p.symlink_to(hold)
        with self.assertRaisesRegex(ValueError,'ordinary, non-hardlinked'):self.check()
        p.unlink();p.hardlink_to(hold)
        with self.assertRaisesRegex(ValueError,'ordinary, non-hardlinked'):self.check()

    def test_active_journals_and_damaged_search_structures_fail(self):
        journal=self.data/'library-data/search.sqlite-journal';journal.write_bytes(b'active')
        with self.assertRaisesRegex(ValueError,'checkpoint SQLite'):self.check()
        self.assertEqual(journal.read_bytes(),b'active');journal.unlink()
        self.sql('DROP TABLE pages_idx')
        with self.assertRaises((ValueError,sqlite3.Error)):self.check()

    def test_concurrent_metadata_changes_are_not_reported_as_verified(self):
        real=v.public.build;p=self.data/'library-data/catalog.json'
        def changed(output):
            result=real(output);p.write_bytes(p.read_bytes());return result
        with patch.object(v.public,'build',side_effect=changed),self.assertRaisesRegex(ValueError,'changed during checking'):
            self.check()

    def test_no_collection_and_unknown_requirements_fail(self):
        with self.assertRaisesRegex(ValueError,'No recognised Australian collections'):v.verify(self.base)
        with self.assertRaisesRegex(ValueError,'Unknown required'):self.check(required=['unknown'])

    def test_malformed_source_metadata_and_index_text_fail_clearly(self):
        for name in [v.PERSONAL_NOTICE,v.trauma.RECEIPT]:
            p=self.data/name;original=p.read_bytes();p.write_text('[]',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'source metadata object'):self.check()
            p.write_bytes(original)
        self.sql('UPDATE pages SET body=NULL WHERE doc_id=? AND page=1',(v.trauma.UID,))
        with self.assertRaisesRegex(ValueError,'malformed text'):self.check()

    def test_temporary_files_cannot_be_created_inside_the_library(self):
        before=self.fixture.hashes(self.data);inventory=v.common.inventory(self.data)
        with patch.object(v.tempfile,'gettempdir',return_value=str(self.data/'scratch')):
            with self.assertRaisesRegex(ValueError,'temporary directory outside'):self.check()
        self.assertEqual(self.fixture.hashes(self.data),before)
        self.assertEqual(v.common.inventory(self.data),inventory)


if __name__ == '__main__': unittest.main()
