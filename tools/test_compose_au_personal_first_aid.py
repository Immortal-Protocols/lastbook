"""Private originals compose with a full library without replacing base material."""
from contextlib import closing
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import unittest
from unittest.mock import patch

from tools import compose_au_personal_first_aid as pc
from tools import test_compose_australia_reference as fixtures


class PersonalComposition(unittest.TestCase):
    def setUp(self):
        self.base_case = fixtures.Compose()
        self.base_case.setUp()
        self.addCleanup(self.base_case.doCleanups)
        for name in ('root', 'base', 'out', 'lib', 'records'):
            setattr(self, name, getattr(self.base_case, name))
        self.cache = self.root / 'cache'; self.cache.mkdir()
        self.pdf = b'%PDF-1.7\nSynthetic original preservation fixture'
        (self.cache / 'personal-au-test.pdf').write_bytes(self.pdf)
        self.source = dict(id='personal-au-test', kind='pdf', title='Synthetic original', pages=2,
                           publisher='Example authority', collection='Personal reference', category='first-aid',
                           pdf_url='https://www.anzcor.org/example/downloadpdf', distribution='personal-only',
                           bytes=len(self.pdf), sha256=hashlib.sha256(self.pdf).hexdigest())
        self.pages = ['Synthetic first page quartz', 'Synthetic second page cobalt']
        self.addCleanup(patch.stopall)
        patch.object(socket, 'socket', side_effect=AssertionError('Network is not permitted in these fixtures')).start()
        patch.object(pc.personal, 'pdf_pages', return_value=self.pages).start()

    def compose(self, base=None, **kwargs):
        return pc.compose(base or self.base, self.out, cache=self.cache, records=[self.source], **kwargs)

    def hashes(self, root):
        return self.base_case.hashes(root)

    def clean_failure(self, match):
        before, inventory = self.hashes(self.base), pc.common.inventory(self.base)
        with self.assertRaisesRegex((ValueError, OSError, sqlite3.Error), match):
            self.compose()
        self.assertEqual(self.hashes(self.base), before)
        self.assertEqual(pc.common.inventory(self.base), inventory)
        self.assertFalse(self.out.exists())
        self.assertEqual(list(self.root.glob('.au-personal-compose-*')), [])

    def renew_manifest(self, root):
        paths = [p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p != root / 'pack-manifest.tsv']
        (root / 'pack-manifest.tsv').write_text(pc.common.checksums(root, paths))

    def test_multi_page_search_preserves_base_rows_files_maps_and_restrictions(self):
        before, inventory = self.hashes(self.base), pc.common.inventory(self.base)
        report = self.compose()
        self.assertEqual((report['base_records'], report['added_records'], report['records']), (1, 2, 3))
        self.assertEqual((report['original_pdfs'], report['original_pdf_pages'], report['added_search_units']), (1, 2, 3))
        self.assertEqual((report['base_search_units'], report['search_units']), (1, 4))
        self.assertEqual(self.hashes(self.base), before)
        self.assertEqual(pc.common.inventory(self.base), inventory)
        changed = {'library-data/catalog.json', 'library-data/search.sqlite', 'library-data/summary.json', 'pack.json', 'pack-manifest.tsv'}
        for rel, digest in before.items():
            if rel not in changed:
                self.assertEqual(pc.common.sha256(self.out / rel), digest, rel)
                self.assertNotEqual((self.out / rel).stat().st_ino, (self.base / rel).stat().st_ino)
        self.assertEqual((self.out / pc.MARKER).read_bytes(), (self.base / pc.MARKER).read_bytes())
        pdf = self.out / 'library-data/documents/personal-au/personal-au-test.pdf'
        self.assertEqual(pdf.read_bytes(), self.pdf)
        records = pc.common.read_records(self.out)
        self.assertEqual(records[0], self.records[0])
        self.assertTrue(all(r['distribution'] == 'personal-only' for r in records[1:]))
        with closing(pc.common.read_only(self.out / 'library-data/search.sqlite')) as db:
            self.assertEqual(db.execute('SELECT rowid,page,body FROM pages WHERE doc_id=?', ('fixture-original',)).fetchone(),
                             (55, 3, 'Original private searchable material'))
            self.assertEqual(db.execute('SELECT * FROM unrelated').fetchall(), [('keep',)])
            self.assertEqual(db.execute('PRAGMA user_version').fetchone(), (17,))
            for word, page in [('quartz', 1), ('cobalt', 2)]:
                self.assertEqual(db.execute('SELECT doc_id,page FROM pages WHERE pages MATCH ?', (word,)).fetchall(),
                                 [('personal-au-test', page)])
        summary = json.loads((self.out / 'library-data/summary.json').read_text())
        self.assertEqual(summary['extraction_errors'], ['old fixture error'])
        self.assertEqual(summary['other'], 'retain')
        self.assertEqual((summary['resources'], summary['pdf_pages'], summary['indexed_units']), (3, 2, 4))
        self.assertEqual(json.loads((self.out / 'pack.json').read_text())['name'], pc.LOCAL_NAME)
        output_before = self.hashes(self.out)
        self.assertGreater(pc.verify(self.out)['verified_files'], 10)
        self.assertEqual(self.hashes(self.out), output_before)
        self.assertEqual(list(self.root.glob('.au-personal-compose-*')), [])

    def test_existing_public_composition_is_retained_and_matching_verifier_is_clear(self):
        public = self.root / 'public'
        public_count = len(json.loads((pc.common.au.SOURCES / 'manifest.json').read_text())['sources'])
        pc.common.compose(self.base, public)
        prior = {name: (public / name).read_bytes() for name in pc.common.RESERVED}
        before = self.hashes(public)
        report = self.compose(public)
        self.assertEqual((report['base_records'], report['records'], report['search_units']), (public_count + 1, public_count + 3, public_count + 4))
        self.assertEqual(self.hashes(public), before)
        for name, data in prior.items():
            self.assertEqual((self.out / name).read_bytes(), data)
        self.assertEqual(set(report['base_receipts']), set(pc.common.RESERVED))
        self.assertEqual(pc.common.verify(public)['records'], public_count + 1)
        self.assertEqual(pc.verify(self.out)['records'], public_count + 3)
        with self.assertRaisesRegex(ValueError, 'compose_au_personal_first_aid.py --verify'):
            pc.common.verify(self.out)

    def test_personal_marker_is_added_to_a_previously_public_base(self):
        (self.base / pc.MARKER).unlink(); self.renew_manifest(self.base)
        before = self.hashes(self.base)
        result = self.compose()
        self.assertFalse(result['base_personal_marker_preserved'])
        marker = json.loads((self.out / pc.MARKER).read_text())
        self.assertEqual(marker['distribution'], 'personal-only')
        self.assertIn('Do not redistribute', marker['notice'])
        self.assertEqual(self.hashes(self.base), before)

    def test_public_pack_selection_cannot_promote_composed_original_or_hub(self):
        public = self.root / 'public'
        public_count = len(json.loads((pc.common.au.SOURCES / 'manifest.json').read_text())['sources'])
        pc.common.compose(self.base, public)
        self.compose(public)
        records = pc.common.read_records(self.out)
        spec = importlib.util.spec_from_file_location('personal_composition_pack_selection', pc.personal.ROOT / 'packaging/build_packs.py')
        packs = importlib.util.module_from_spec(spec); spec.loader.exec_module(packs)
        snapshot = self.root / 'selection'; snapshot.mkdir()
        (snapshot / 'remote-videos.json').write_text('{}')
        with patch.object(packs, 'video_groups', return_value=({}, {})), \
             patch.object(packs, 'guide_ids', return_value={r['id'] for r in records}), \
             patch.dict(packs.SIZES, {'small': {**packs.SIZES['small'], 'video_include': [], 'video_exclude': []}}):
            for size in ('small', 'medium', 'all'):
                chosen, left, _ = packs.select(size, records, snapshot, 0)
                self.assertIn('au-reference', chosen)
                for uid in ('personal-au-test', 'personal-au-reference'):
                    self.assertNotIn(uid, chosen)
                    self.assertTrue(any(rid == uid and 'not redistributable' in why for rid, _, why in left))

    def test_source_mode_requires_explicit_opt_in_before_building(self):
        with patch.object(pc.personal, 'build', side_effect=AssertionError('Must not fetch/build')):
            for options in ({}, {'cache': self.cache, 'download': True}):
                with self.subTest(options=options), self.assertRaisesRegex(ValueError, 'exactly one'):
                    pc.compose(self.base, self.out, records=[self.source], **options)

    def test_download_mode_is_explicit_and_keeps_the_same_pinned_builder(self):
        def original(record, cache):
            self.assertIsNone(cache)
            self.assertEqual(record['sha256'], self.source['sha256'])
            return self.pdf
        with patch.object(pc.personal, 'source_bytes', side_effect=original) as fetch:
            report = pc.compose(self.base, self.out, download=True, records=[self.source])
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(report['original_pdf_pages'], 2)
        pc.verify(self.out)

    def test_changed_cached_original_leaves_no_output_or_base_changes(self):
        (self.cache / 'personal-au-test.pdf').write_bytes(b'changed')
        self.clean_failure('Source changed')

    def test_local_revision_changes_when_base_search_content_changes(self):
        self.compose()
        first = json.loads((self.out / 'pack.json').read_text())['content_revision']
        with closing(sqlite3.connect(self.lib / 'search.sqlite')) as db:
            db.execute("UPDATE pages SET body='Changed retained base search text' WHERE doc_id='fixture-original'")
            db.commit()
        other = self.root / 'other-composition'
        pc.compose(self.base, other, cache=self.cache, records=[self.source])
        self.assertNotEqual(json.loads((other / 'pack.json').read_text())['content_revision'], first)
        pc.verify(other)

    def test_catalog_collision_is_refused_before_any_source_fetch(self):
        self.records.append({**self.records[0], 'id': 'personal-au-test'})
        self.base_case.save_catalog()
        with patch.object(pc.personal, 'build', side_effect=AssertionError('Must not build')):
            self.clean_failure('Personal ids already exist')

    def test_orphan_search_id_is_not_replaced(self):
        with closing(sqlite3.connect(self.lib / 'search.sqlite')) as db:
            db.execute('INSERT INTO pages VALUES(?,?,?,?,?,?,?)', ('personal-au-test', 'Old', '', '', 'pages/original.html', 1, 'keep'))
            db.commit()
        self.clean_failure('already exist in the base search index')

    def test_uncatalogued_source_path_collision_is_not_replaced(self):
        target = self.lib / 'documents/personal-au/personal-au-test.pdf'
        target.parent.mkdir(parents=True); target.write_bytes(b'keep existing user file')
        self.clean_failure('Personal file path already exists')
        self.assertEqual(target.read_bytes(), b'keep existing user file')

    def test_active_wal_and_links_are_refused_before_copying(self):
        wal = self.lib / 'search.sqlite-wal'; wal.write_bytes(b'not checkpointed')
        before = self.hashes(self.base)
        with self.assertRaisesRegex(ValueError, 'Close Lastbook'):
            self.compose()
        self.assertEqual(self.hashes(self.base), before)
        self.assertFalse(self.out.exists())
        wal.unlink()
        (self.base / 'user-link').symlink_to(self.base / 'unknown/user-note.txt')
        with self.assertRaisesRegex(ValueError, 'link or special'):
            self.compose()
        self.assertFalse(self.out.exists())

    def test_concurrent_destination_and_dangling_link_are_not_replaced(self):
        publish = pc.common.publish
        def competing(staged, output):
            output.mkdir(); (output / 'winner').write_text('first completed output')
            return publish(staged, output)
        with patch.object(pc.common, 'publish', side_effect=competing), self.assertRaises(OSError):
            self.compose()
        self.assertEqual((self.out / 'winner').read_text(), 'first completed output')
        self.assertEqual(list(self.root.glob('.au-personal-compose-*')), [])
        (self.out / 'winner').unlink(); self.out.rmdir(); self.out.symlink_to(self.root / 'absent')
        with self.assertRaisesRegex(ValueError, 'already exists'):
            self.compose()
        self.assertTrue(self.out.is_symlink())

    def test_verifier_rejects_lost_private_flag_even_with_a_refreshed_manifest(self):
        self.compose()
        path = self.out / 'library-data/catalog.json'
        records = json.loads(path.read_text()); records[-1].pop('distribution')
        path.write_text(json.dumps(records)); self.renew_manifest(self.out)
        with self.assertRaisesRegex(ValueError, 'lost its distribution'):
            pc.verify(self.out)

    def test_verifier_rejects_missing_marker_and_shifted_pdf_page_numbers(self):
        self.compose()
        marker = self.out / pc.MARKER; saved = marker.read_bytes(); marker.unlink()
        self.renew_manifest(self.out)
        with self.assertRaisesRegex(ValueError, 'marker'):
            pc.verify(self.out)
        marker.write_bytes(saved)
        with closing(sqlite3.connect(self.out / 'library-data/search.sqlite')) as db:
            db.execute("UPDATE pages SET page=7 WHERE doc_id='personal-au-test' AND page=1"); db.commit()
        self.renew_manifest(self.out)
        with self.assertRaisesRegex(ValueError, 'search pages differ'):
            pc.verify(self.out)

    def test_cli_verifies_offline_and_rejects_implicit_or_mixed_source_modes(self):
        self.compose(); before = self.hashes(self.out)
        command = [sys.executable, '-I', '-B', str(Path(pc.__file__))]
        result = subprocess.run(command + ['--verify', str(self.out)], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('3 personal-use library records', result.stdout)
        self.assertEqual(self.hashes(self.out), before)
        for args in (['--base', str(self.base), '--output', str(self.root / 'other')],
                     ['--verify', str(self.out), '--download'],
                     ['--base', str(self.base), '--output', str(self.root / 'other'), '--download', '--pdf-cache', str(self.cache)]):
            result = subprocess.run(command + args, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 2, result.stderr)
        self.assertFalse((self.root / 'other').exists())


if __name__ == '__main__':
    unittest.main()
