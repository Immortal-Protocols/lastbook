"""Composition must preserve the full base and fail without a partial library."""
from contextlib import closing
import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from tools import compose_australia_reference as compose
from engine.setup import install


class Compose(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.base, self.out = self.root / 'base', self.root / 'combined'
        self.lib = self.base / 'library-data'
        (self.lib / 'pages').mkdir(parents=True)
        (self.lib / 'text').mkdir()
        (self.lib / 'pages/original.html').write_text('<p>Original private fixture source</p>')
        (self.lib / 'text/original.txt').write_text('Original private fixture source')
        self.records = [dict(id='fixture-original', title='Original', kind='html', path='pages/original.html',
                             text_path='text/original.txt', bytes=37, distribution='personal-only')]
        self.save_catalog()
        (self.lib / 'summary.json').write_text(json.dumps(dict(resources=1, extraction_errors=['old fixture error'], other='retain')))
        (self.base / 'pack.json').write_text(json.dumps(dict(name='small', content_revision='original-revision', map='base', custom='retain')))
        (self.base / 'PERSONAL-USE-ONLY.json').write_text('{"fixture": "Do not redistribute"}\n')
        (self.base / 'maps').mkdir()
        (self.base / 'maps/fixture.bin').write_bytes(b'map fixture\x00\xff')
        (self.base / 'map-set.json').write_text('{"name":"au-vic","files":[]}\n')
        (self.base / 'unknown').mkdir()
        (self.base / 'unknown/pack-manifest.tsv').write_bytes(b'opaque nested manifest\x00')
        (self.base / 'unknown/user-note.txt').write_text('Private fixture note')
        with closing(sqlite3.connect(self.lib / 'search.sqlite')) as db:
            db.execute('CREATE VIRTUAL TABLE pages USING ' + compose.au.SCHEMA)
            db.execute('INSERT INTO pages(rowid,doc_id,title,collection,category,path,page,body) VALUES(55,?,?,?,?,?,?,?)',
                       ('fixture-original', 'Original', 'Fixture', 'other', 'pages/original.html', 3, 'Original private searchable material'))
            db.execute('CREATE TABLE unrelated(value TEXT)')
            db.execute("INSERT INTO unrelated VALUES('keep')")
            db.execute('PRAGMA user_version=17')
            db.commit()
        (self.base / 'pack-manifest.tsv').write_text(compose.checksums(self.base,
            [p.relative_to(self.base).as_posix() for p in self.base.rglob('*') if p.is_file()]))

    def save_catalog(self):
        (self.lib / 'catalog.json').write_text(json.dumps(self.records))

    def hashes(self, root):
        return {p.relative_to(root).as_posix(): compose.sha256(p) for p in root.rglob('*') if p.is_file()}

    def run_compose(self):
        with patch.object(socket, 'socket', side_effect=AssertionError('Network access')):
            return compose.compose(self.base, self.out)

    def refuses(self, match='.'):
        with self.assertRaisesRegex((ValueError, OSError, sqlite3.Error), match):
            self.run_compose()
        self.assertFalse(self.out.exists())
        self.assertEqual(list(self.root.glob('.au-compose-*')), [])

    def test_real_supplement_preserves_private_base_maps_rows_and_full_checksums(self):
        original, meta = self.hashes(self.base), compose.inventory(self.base)
        r = self.run_compose()
        self.assertEqual((r['base_records'], r['added_records'], r['records']), (1, 124, 125))
        self.assertEqual(self.hashes(self.base), original)
        self.assertEqual(compose.inventory(self.base), meta)
        changed = {'library-data/catalog.json', 'library-data/search.sqlite', 'library-data/summary.json', 'pack.json', 'pack-manifest.tsv'}
        for rel, digest in original.items():
            if rel not in changed:
                self.assertEqual(compose.sha256(self.out / rel), digest, rel)
                self.assertNotEqual((self.out / rel).stat().st_ino, (self.base / rel).stat().st_ino)
        catalog = json.loads((self.out / 'library-data/catalog.json').read_text())
        self.assertEqual(catalog[0], self.records[0])
        self.assertEqual(sum(x.get('distribution') == 'personal-only' for x in catalog), 1)
        with closing(sqlite3.connect(self.out / 'library-data/search.sqlite')) as db:
            self.assertEqual(db.execute('SELECT rowid,page,body FROM pages WHERE doc_id=?', ('fixture-original',)).fetchone(),
                             (55, 3, 'Original private searchable material'))
            self.assertEqual(db.execute('SELECT * FROM unrelated').fetchall(), [('keep',)])
            self.assertEqual(db.execute('PRAGMA user_version').fetchone(), (17,))
            self.assertEqual(db.execute('SELECT count(*) FROM pages').fetchone(), (125,))
            self.assertGreater(db.execute("SELECT count(*) FROM pages WHERE pages MATCH 'livestock'").fetchone()[0], 0)
        pack = json.loads((self.out / 'pack.json').read_text())
        self.assertEqual(pack['name'], 'local-australia-reference')
        self.assertEqual(pack['map'], 'base')
        self.assertEqual(pack['custom'], 'retain')
        self.assertEqual(pack['australia_composition']['base_name'], 'small')
        self.assertNotEqual(pack['content_revision'], 'original-revision')
        summary = json.loads((self.out / 'library-data/summary.json').read_text())
        self.assertEqual(summary['extraction_errors'], ['old fixture error'])
        self.assertEqual(summary['other'], 'retain')
        self.assertEqual(summary['indexed_units'], 125)
        manifest = install.read_pack_manifest(self.out / 'pack-manifest.tsv')
        self.assertEqual({x[0] for x in manifest}, set(self.hashes(self.out)) - {'pack-manifest.tsv'})
        for rel, size, digest in manifest:
            self.assertEqual((size, digest), ((self.out / rel).stat().st_size, compose.sha256(self.out / rel)))
        for rel, size, digest in install.read_pack_manifest(self.out / 'AUSTRALIA-SHA256SUMS.tsv'):
            self.assertEqual((size, digest), ((self.out / rel).stat().st_size, compose.sha256(self.out / rel)))
        contents = (self.out / 'pack-contents.tsv').read_text().splitlines()
        self.assertEqual(len(contents), 126)
        before_verify = self.hashes(self.out)
        proof = compose.verify(self.out)
        self.assertEqual(proof['verified_files'], len(manifest))
        self.assertEqual(before_verify, self.hashes(self.out))

    def test_existing_output_is_untouched(self):
        self.out.mkdir()
        (self.out / 'keep').write_text('keep')
        with self.assertRaisesRegex(ValueError, 'already exists'):
            self.run_compose()
        self.assertEqual((self.out / 'keep').read_text(), 'keep')

    def test_nested_or_same_paths_refused(self):
        for output in (self.base, self.base / 'nested', self.root):
            with self.subTest(output=output), self.assertRaises(ValueError):
                compose.compose(self.base, output)

    def test_links_are_refused_without_following(self):
        (self.base / 'link').symlink_to(self.root / 'missing')
        self.refuses('link or special')

    @unittest.skipUnless(hasattr(os, 'mkfifo'), 'needs FIFO support')
    def test_special_files_are_refused(self):
        os.mkfifo(self.base / 'fifo')
        self.refuses('link or special')

    def test_nonempty_journals_and_unpaired_shared_memory_are_refused(self):
        for ending in ('-wal', '-shm', '-journal'):
            p = self.lib / ('search.sqlite' + ending)
            p.write_bytes(b'not an empty checkpointed sidecar')
            self.refuses('Close Lastbook')
            p.unlink()

    def test_existing_australian_manifest_is_not_an_update(self):
        (self.base / 'AUSTRALIA-REFERENCE.json').write_text('{}')
        self.refuses('only adds it once')

    def test_duplicate_base_ids_refused(self):
        self.records.append(self.records[0].copy())
        self.save_catalog()
        self.refuses('duplicate')

    def test_catalog_id_collision_refused(self):
        self.records[0]['id'] = 'au-reference'
        self.save_catalog()
        self.refuses('ids already exist')

    def test_unlisted_file_collision_refused(self):
        (self.lib / 'text/au-reference.txt').write_text('unrelated existing file')
        before = self.hashes(self.base)
        self.refuses('file path already exists')
        self.assertEqual(self.hashes(self.base), before)

    def test_catalog_paths_cannot_escape_or_be_missing(self):
        for rel in ('../outside', '/absolute', 'C:/drive', 'pages\\outside', '.', 'missing.html'):
            with self.subTest(path=rel):
                self.records[0]['path'] = rel
                self.save_catalog()
                self.refuses('path|missing')

    def test_fts_id_collision_refused(self):
        with closing(sqlite3.connect(self.lib / 'search.sqlite')) as db:
            db.execute("UPDATE pages SET doc_id='au-reference'")
            db.commit()
        before = self.hashes(self.base)
        self.refuses('ids already exist')
        self.assertEqual(self.hashes(self.base), before)

    def test_wrong_index_schema_refused(self):
        with closing(sqlite3.connect(self.lib / 'search.sqlite')) as db:
            db.execute('DROP TABLE pages')
            db.execute('CREATE TABLE pages(body TEXT)')
            db.commit()
        self.refuses('seven-column')

    def test_closed_wal_database_becomes_self_contained_snapshot(self):
        with closing(sqlite3.connect(self.lib / 'search.sqlite')) as db:
            self.assertEqual(db.execute('PRAGMA journal_mode=WAL').fetchone(), ('wal',))
        self.assertFalse(list(self.lib.glob('search.sqlite-*')))
        before = self.hashes(self.base)
        self.run_compose()
        self.assertEqual(self.hashes(self.base), before)
        with closing(compose.read_only(self.out / 'library-data/search.sqlite')) as db:
            self.assertEqual(db.execute('PRAGMA journal_mode').fetchone(), ('delete',))
        self.assertFalse(list((self.out / 'library-data').glob('search.sqlite-*')))
        compose.verify(self.out)

    def test_checkpointed_empty_sidecars_are_safe_without_modifying_base(self):
        # A realistic stale read-only WAL/SHM pair, unrelated to the search index.
        cached = self.base / 'unknown/cache.sqlite'
        with closing(sqlite3.connect(cached)) as db:
            db.execute('CREATE TABLE cached(value TEXT)')
            db.execute('PRAGMA journal_mode=WAL')
        with closing(compose.read_only(cached)) as db:
            db.execute('SELECT * FROM cached').fetchall()
        wal, shm = cached.with_name(cached.name + '-wal'), cached.with_name(cached.name + '-shm')
        self.assertEqual(wal.stat().st_size, 0)
        self.assertGreater(shm.stat().st_size, 0)
        # Same harmless pair on the index that is rebuilt, rather than retained.
        with closing(sqlite3.connect(self.lib / 'search.sqlite')) as db:
            db.execute('PRAGMA journal_mode=WAL')
        with closing(compose.read_only(self.lib / 'search.sqlite')) as db:
            db.execute('SELECT count(*) FROM pages').fetchone()
        before = self.hashes(self.base)
        self.run_compose()
        self.assertEqual(self.hashes(self.base), before)
        for p in (cached, wal, shm):
            self.assertEqual(compose.sha256(p), compose.sha256(self.out / p.relative_to(self.base)))
        self.assertFalse(list((self.out / 'library-data').glob('search.sqlite-*')))
        compose.verify(self.out)

    def test_copy_failure_cleans_output_and_preserves_base(self):
        before = self.hashes(self.base)
        with patch.object(compose, 'clone_or_copy', side_effect=OSError('fixture full disk')):
            self.refuses('full disk')
        self.assertEqual(self.hashes(self.base), before)

    def test_concurrent_base_edit_refused(self):
        actual = compose.clone_or_copy
        def copying(src, dst):
            result = actual(src, dst)
            (self.base / 'unknown/user-note.txt').write_text('edited concurrently')
            return result
        with patch.object(compose, 'clone_or_copy', side_effect=copying):
            self.refuses('Base changed')

    def test_output_appearing_during_build_is_preserved(self):
        actual = compose.merge_index
        def merging(*args):
            result = actual(*args)
            self.out.mkdir()
            (self.out / 'keep').write_text('concurrent output')
            return result
        with patch.object(compose, 'merge_index', side_effect=merging), self.assertRaisesRegex(ValueError, 'Output appeared'):
            self.run_compose()
        self.assertEqual((self.out / 'keep').read_text(), 'concurrent output')
        self.assertEqual(list(self.root.glob('.au-compose-*')), [])

    def test_portable_copy_fallback_does_not_link_base(self):
        copied = self.root / 'copied-note.txt'
        with patch.object(compose.sys, 'platform', 'darwin'), patch.object(compose.ctypes, 'CDLL', return_value=object()):
            compose.clone_or_copy(self.base / 'unknown/user-note.txt', copied)
        copied.write_text('edit copy')
        self.assertEqual((self.base / 'unknown/user-note.txt').read_text(), 'Private fixture note')

    def test_exclusive_publish_preserves_even_empty_existing_directory(self):
        staged = self.root / 'staged'
        staged.mkdir()
        (staged / 'new').write_text('new')
        self.out.mkdir()
        original_inode = self.out.stat().st_ino
        with self.assertRaises(OSError):
            compose.publish(staged, self.out)
        self.assertEqual(self.out.stat().st_ino, original_inode)
        self.assertEqual(list(self.out.iterdir()), [])
        self.assertTrue((staged / 'new').is_file())

    def test_verify_detects_changed_or_extra_files_without_writing(self):
        self.run_compose()
        note = self.out / 'unknown/user-note.txt'
        note.write_text('changed after composition')
        before = self.hashes(self.out)
        with self.assertRaisesRegex(ValueError, 'differs'):
            compose.verify(self.out)
        self.assertEqual(before, self.hashes(self.out))
        note.write_text('Private fixture note')
        (self.out / 'extra').write_text('unlisted')
        with self.assertRaisesRegex(ValueError, 'every file'):
            compose.verify(self.out)

    def test_verify_rejects_escaping_manifest_path(self):
        self.run_compose()
        (self.out / 'pack-manifest.tsv').write_text('path\tbytes\tsha256\n../outside\t1\t' + '0' * 64 + '\n')
        with self.assertRaisesRegex(ValueError, 'relative library path'):
            compose.verify(self.out)


if __name__ == '__main__':
    unittest.main()
