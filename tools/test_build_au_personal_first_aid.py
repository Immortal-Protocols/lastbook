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
        personal = json.loads(b.MANIFEST.read_text(encoding='utf-8'))['sources']
        self.assertTrue({r['id'] for r in personal}.isdisjoint({r['id'] for r, *_ in checked}))
        self.assertFalse(any(r['kind'] == 'pdf' or r.get('distribution') == 'personal-only' for r, *_ in checked))


if __name__ == '__main__': unittest.main()
