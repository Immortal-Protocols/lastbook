"""Chinese terms inside unsegmented source text reach readers, retrieval and libq."""
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import assistant
import server
from engine import search_text


class HanSearch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        lib = self.root / 'library-data'; lib.mkdir()
        self.db = lib / 'search.sqlite'
        self.con = sqlite3.connect(self.db)
        self.addCleanup(self.con.close)
        self.con.execute('CREATE VIRTUAL TABLE pages USING fts5(doc_id UNINDEXED,title,collection,category,path UNINDEXED,page UNINDEXED,body,tokenize="unicode61")')
        rows = [('simplified', '测试资料', '准备洪水资料和饮水记录。 water'),
                ('traditional', '測試資料', '準備洪水資料和飲水記錄。 water'),
                ('english', 'English notes', 'waterproof material only'),
                ('video-tx', 'Test video transcript', '测试洪水影像'),
                ('markup', 'Escaped text', '<img src=x onerror=x>测试火灾资料')]
        self.con.executemany('INSERT INTO pages VALUES(?,?,?,?,?,?,?)',
                             [(uid, title, 'Test', 'test', uid+'.html', 1, body) for uid, title, body in rows])
        self.con.commit()
        recs = [dict(id=uid, title=title, collection='Test', category='test', publisher='Test',
                     path=uid+'.html', kind='transcript' if uid=='video-tx' else 'html') for uid, title, _ in rows]
        video = dict(id='video', title='Test video', collection='Test', category='test', publisher='Test', path='test.mp4', kind='video')
        recs[3]['video_path'] = video['path']; recs.append(video)
        self.cat = {'by_id': {r['id']: r for r in recs}, 'by_path': {r['path']: r for r in recs}, 'video_tx': {}, 'thumbs': {}}
        (lib / 'catalog.json').write_text(json.dumps(recs), encoding='utf-8')
        for p in [patch.object(server.library, 'DB', self.db), patch.object(server, 'catalog', return_value=self.cat),
                  patch.object(assistant, 'S', server)]:
            p.start(); self.addCleanup(p.stop)
        server.find.cache_clear(); self.addCleanup(server.find.cache_clear)

    def ids(self, groups, **kwargs):
        return [r[0] for r in search_text.han_search_rows(self.con, groups, **kwargs)]

    def test_han_substring_that_unicode61_misses(self):
        self.assertEqual(self.con.execute('SELECT doc_id FROM pages WHERE pages MATCH ?', ('洪水',)).fetchall(), [])
        self.assertEqual(set(self.ids([['洪水']])), {'simplified', 'traditional', 'video-tx'})
        self.assertEqual(self.ids([['饮水']]), ['simplified'])
        self.assertEqual(self.ids([['飲水']]), ['traditional'])

    def test_mixed_script_keeps_fts_word_boundaries(self):
        self.assertEqual(set(self.ids([['洪水'], ['water']])), {'simplified', 'traditional'})
        self.assertNotIn('english', self.ids([['資料'], ['water']], any_group=True))
        self.assertEqual(self.ids([['洪水'], ['waterproof']]), [])

    def test_literal_parameters_and_empty_query(self):
        self.assertEqual(self.ids([["洪水' OR 1=1--"]]), [])
        self.assertEqual(self.ids([['洪水%']]), [])
        self.assertEqual(self.ids([]), [])
        self.assertEqual(self.con.execute('SELECT count(*) FROM pages').fetchone()[0], 5)

    def test_filter_before_limit_and_disjunction(self):
        self.assertEqual(self.ids([['洪水']], ids='["video-tx"]', limit=1), ['video-tx'])
        self.assertEqual(self.ids([['洪水'], ['water']], ids='["video-tx"]', limit=1, any_group=True), ['video-tx'])
        self.assertEqual(self.ids([['洪水']], ids='[]'), [])

    def test_reader_search_retrieval_and_video_filter(self):
        found = server.find('洪水')['results']
        self.assertTrue({'simplified', 'traditional'} <= {r['id'] for r in found})
        self.assertIn('<mark>洪水</mark>', next(r for r in found if r['id']=='simplified')['hits'][0]['snippet'])
        self.assertEqual([r['id'] for r in server.find('洪水', 'video')['results']], ['video'])
        self.assertEqual({r[0] for r in assistant._fts('飲水')}, {'traditional'})
        self.assertEqual({r[0] for r in assistant._fts('洪水', ids='["video-tx"]')}, {'video-tx'})

    def test_snippets_escape_source_markup(self):
        hit = next(r for r in server.find('火灾')['results'] if r['id']=='markup')
        self.assertIn('&lt;img', hit['hits'][0]['snippet'])
        self.assertNotIn('<img', hit['hits'][0]['snippet'])

    def test_latin_search_retains_existing_fts_path(self):
        with patch.object(server.library, 'han_search_rows', side_effect=AssertionError('Latin query used Han path')):
            self.assertEqual({r['id'] for r in server.find('water')['results']}, {'simplified', 'traditional'})
            self.assertEqual({r[0] for r in assistant._fts('water')}, {'simplified', 'traditional'})

    def test_cli_uses_same_existing_schema_without_index_rebuild(self):
        tool = Path(__file__).resolve().parents[2] / 'tools/libq.py'
        result = subprocess.run([sys.executable, str(tool), '--data', str(self.root), 'search', '飲水'],
                                capture_output=True, text=True, encoding='utf-8', check=True)
        self.assertIn('traditional |', result.stdout)
        self.assertNotIn('simplified |', result.stdout)


if __name__ == '__main__':
    unittest.main()
