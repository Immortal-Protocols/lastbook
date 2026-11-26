"""Source integrity, offline build, local links and protection of existing libraries."""
import importlib.util
import json
from pathlib import Path
import shutil
import socket
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

TOOL = Path(__file__).with_name('build_australia_reference.py')
spec = importlib.util.spec_from_file_location('au_builder', TOOL)
au = importlib.util.module_from_spec(spec); spec.loader.exec_module(au)


class Reference(unittest.TestCase):
    def test_real_sources_build_without_network_and_search_opens_the_same_text(self):
        with tempfile.TemporaryDirectory() as d, patch.object(socket, 'socket', side_effect=AssertionError('network')):
            out = Path(d) / 'LastbookData'
            count = au.build(out)
            lib = out / 'library-data'
            cat = {r['id']: r for r in json.loads((lib / 'catalog.json').read_text(encoding='utf-8'))}
            self.assertEqual(count, len(cat))
            with sqlite3.connect(lib / 'search.sqlite') as db:
                self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
                for query, expected in [('"Triple Zero"', 'au-emergency-calls'),
                                        ('livestock', 'nsw-rural-flood'), ('chemicals', 'qld-water'),
                                        ('"carbon monoxide"', 'vic-generator'),
                                        ('"fuel and rest stops"', 'au-remote-travel'),
                                        ('"No Rating"', 'au-fire-danger-ratings'),
                                        ('"cell broadcast"', 'au-ausalert'),
                                        ('"Critical Alerts"', 'au-ausalert-operational'),
                                        ('"heightened level"', 'nsw-warning-levels'),
                                        ('"downed powerline"', 'sa-storm-during'),
                                        ('"qualified electrician"', 'sa-flood-after'),
                                        ('"small animals"', 'sa-animal-planning'),
                                        ('"seasonal preparation"', 'sa-property-preparation'),
                                        ('"short range devices"', 'au-locating-devices')]:
                    ids = {r[0] for r in db.execute('SELECT doc_id FROM pages WHERE pages MATCH ?', (query,))}
                    self.assertIn(expected, ids)
                for uid, path, body in db.execute('SELECT doc_id,path,body FROM pages'):
                    self.assertEqual(path, cat[uid]['path'])
                    self.assertEqual(body, (lib / cat[uid]['text_path']).read_text(encoding='utf-8'))
                    self.assertEqual(au.digest((lib / path).read_bytes()), cat[uid]['sha256'])
            directory = json.loads((au.SOURCES / 'jurisdictions.json').read_text(encoding='utf-8'))
            self.assertEqual({r['id'] for r in directory['jurisdictions']},
                             {'AU-ACT', 'AU-NSW', 'AU-NT', 'AU-QLD', 'AU-SA', 'AU-TAS', 'AU-VIC', 'AU-WA'})
            self.assertEqual(cat['au-remote-travel']['license'], 'CC-BY-3.0-AU')
            self.assertEqual(cat['vic-generator']['license'], 'CC-BY-4.0')

    def test_existing_output_is_untouched(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d); sentinel = out / 'catalog.json'; sentinel.write_text('keep me', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'already exists'):
                au.build(out)
            self.assertEqual(sentinel.read_text(encoding='utf-8'), 'keep me')

    def test_changed_source_cannot_be_built(self):
        with tempfile.TemporaryDirectory() as d:
            sources = Path(d) / 'sources'; shutil.copytree(au.SOURCES, sources)
            (sources / 'sources/au-emergency-calls.html').write_text('changed source', encoding='utf-8')
            out = Path(d) / 'LastbookData'
            with self.assertRaisesRegex(ValueError, 'Snapshot changed'):
                au.build(out, sources)
            self.assertFalse(out.exists())

    def test_active_content_and_external_or_broken_links_are_refused(self):
        for bad in ['<script>x</script>', '<img src="https://example.invalid/x">',
                    '<a href="https://example.invalid">x</a>', '<p onclick="x()">x</p>']:
            with self.assertRaises(ValueError):
                au.Page().feed(bad)
        with tempfile.TemporaryDirectory() as d:
            sources = Path(d) / 'sources'; shutil.copytree(au.SOURCES, sources)
            m = json.loads((sources / 'manifest.json').read_text(encoding='utf-8'))
            r = m['sources'][0]; file = sources / r['snapshot']
            data = file.read_bytes() + b'<a href="/pages/au/missing.html">missing</a>'
            file.write_bytes(data); r.update(bytes=len(data), sha256=au.digest(data))
            (sources / 'manifest.json').write_text(json.dumps(m), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Unbundled local link'):
                au.checked_sources(sources)


if __name__ == '__main__':
    unittest.main()
