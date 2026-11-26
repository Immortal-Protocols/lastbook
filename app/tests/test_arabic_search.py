"""Marked/unmarked Arabic words reach search, source snippets, retrieval and libq."""
import hashlib
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


class ArabicSearch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); lib = self.root / 'library-data'; lib.mkdir()
        self.db = lib / 'search.sqlite'; self.con = sqlite3.connect(self.db); self.addCleanup(self.con.close)
        self.con.execute('CREATE VIRTUAL TABLE pages USING fts5(doc_id UNINDEXED,title,collection,category,path UNINDEXED,page UNINDEXED,body,tokenize="unicode61")')
        self.rows = [
            ('marked', 'Arabic notes', 'غادر مبكرًا. تعرّف وجهّز. قوي دوّار. water 洪水資料'),
            ('bare', 'Plain Arabic notes', 'غادر مبكرا. تعرف وجهز. waterproof'),
            ('prefix', 'Different words', 'بمبكرًا ومبكرًا مبكرات أعرضة'),
            ('hamza', 'Letters are distinct', 'أمان آمن علي سأل'),
            ('english', 'English notes', 'water cafe café'),
            ('markup', 'Escaped source', '<img src=x onerror=x> دوّار'),
            ('video-tx', 'Video source', 'تعرّف مبكرًا'),
            ('title', 'مُبَكِّرًا', 'A title-only match with its original body.'),
        ]
        self.con.executemany('INSERT INTO pages VALUES(?,?,?,?,?,?,?)',
                             [(uid, title, 'Test', 'test', uid + '.html', 1, body) for uid, title, body in self.rows])
        self.con.commit()
        recs = [dict(id=uid, title=title, collection='Test', category='test', publisher='Test',
                     path=uid+'.html', kind='transcript' if uid=='video-tx' else 'html') for uid, title, _ in self.rows]
        video = dict(id='video', title='Video', collection='Test', category='test', publisher='Test', path='test.mp4', kind='video')
        recs[6]['video_path'] = video['path']; recs.append(video)
        cat = {'by_id': {r['id']: r for r in recs}, 'by_path': {r['path']: r for r in recs}, 'video_tx': {}, 'thumbs': {}}
        (lib / 'catalog.json').write_text(json.dumps(recs), encoding='utf-8')
        for p in [patch.object(server.library, 'DB', self.db), patch.object(server, 'catalog', return_value=cat), patch.object(assistant, 'S', server)]:
            p.start(); self.addCleanup(p.stop)
        server.find.cache_clear(); self.addCleanup(server.find.cache_clear)

    def ids(self, groups, **kwargs):
        return {r[0] for r in search_text.text_search_rows(self.con, groups, **kwargs)}

    def test_query_keeps_arabic_marks_without_changing_latin_tokenization(self):
        self.assertEqual(server.query_groups('مبكرًا تعرّف سأل')[0], ['مبكرًا', 'تعرّف', 'سأل'])
        self.assertEqual(search_text.query_terms("water's café waterَ waterٰ"), ["water's", 'café', 'water', 'water'])
        self.assertEqual(search_text.query_terms("water's", apostrophes=False), ['water', 's'])
        self.assertEqual(server.query_groups('ًُّٰ')[1], [])

    def test_marked_and_unmarked_queries_have_same_whole_word_matches(self):
        self.assertNotIn(('marked',), self.con.execute('SELECT doc_id FROM pages WHERE pages MATCH ?', ('مبكرا',)).fetchall())
        expected = {'marked', 'bare', 'video-tx', 'title'}
        self.assertEqual(self.ids([['مبكرا']]), expected)
        self.assertEqual(self.ids([['مُبَكِّرًا']]), expected)

    def test_shadda_tanwin_and_superscript_alef_are_optional(self):
        self.assertEqual(self.ids([['دوار']]), {'marked', 'markup'})
        self.assertEqual(self.ids([['مبكرا']]), self.ids([['مبكراً']]))
        self.assertEqual(list(search_text.arabic_matches('هٰذا هذا', 'هذا')), [(0, 4), (5, 8)])

    def test_word_boundaries_do_not_accept_prefixes_suffixes_or_partial_marked_words(self):
        self.assertNotIn('prefix', self.ids([['مبكرا']]))
        self.assertEqual(self.ids([['عر']]), set())
        self.assertEqual(self.ids([['بكرا']]), set())
        self.assertEqual(list(search_text.arabic_matches('سَأل', 'سا')), [])

    def test_hamza_maddah_yeh_and_other_accents_are_not_folded(self):
        self.assertEqual(self.ids([['أمان']]), {'hamza'})
        for term in ['امان', 'امن', 'على', 'سال']:
            self.assertEqual(self.ids([[term]]), set(), term)
        self.assertEqual(self.ids([['سأل']]), {'hamza'})

    def test_mixed_han_arabic_and_latin_keep_fts_word_boundaries(self):
        self.assertEqual(self.ids([['تعرف'], ['water']]), {'marked'})
        self.assertEqual(self.ids([['تعرف'], ['waterproof']]), {'bare'})
        self.assertEqual(self.ids([['تعرف'], ['洪水']]), {'marked'})
        self.assertNotIn('bare', self.ids([['water'], ['دوار']], any_group=True))

    def test_group_alternatives_relaxation_and_id_filter_apply_before_limit(self):
        self.assertEqual(self.ids([['دوار', 'تعرف']], ids='["video-tx"]', limit=1), {'video-tx'})
        self.assertEqual(self.ids([['مبكرا'], ['دوار']], ids='["video-tx"]', limit=1, any_group=True), {'video-tx'})
        self.assertEqual(self.ids([['مبكرا']], ids='[]'), set())
        rows = search_text.text_search_rows(self.con, [['مبكرا'], ['دوار']], any_group=True)
        self.assertEqual(rows[0][0], 'marked')
        self.assertEqual(rows[0][3], -2)

    def test_sql_wildcards_quotes_and_regex_characters_remain_literal(self):
        for term in ["دوار' OR 1=1--", 'دوار%', 'دوار_', 'دوار.*', 'دوار|مبكرا', 'دوار(?=x)']:
            self.assertEqual(self.ids([[term]]), set(), term)
        self.assertEqual(self.ids([]), set())
        self.assertEqual(self.con.execute('SELECT count(*) FROM pages').fetchone()[0], len(self.rows))

    def test_reader_snippet_marks_original_word_and_escapes_source_markup(self):
        found = server.find('دوار')['results']; self.assertEqual({r['id'] for r in found}, {'marked', 'markup'})
        snippet = next(r for r in found if r['id']=='markup')['hits'][0]['snippet']
        self.assertIn('<mark>دوّار</mark>', snippet)
        self.assertIn('&lt;img', snippet); self.assertNotIn('<img', snippet)
        marked = server.find('مبكرًا')['results']
        self.assertEqual({r['id'] for r in marked}, {'marked', 'bare', 'video', 'title'})

    def test_original_late_snippet_and_overlapping_query_spans_stay_intact(self):
        body = 'x ' * 200 + 'دوّار مبكرًا'
        snippet = search_text.excerpt_for(body, ['دوار', 'دوّار', 'مبكرا'], ('[', ']'))
        self.assertIn('[دوّار] [مبكرًا]', snippet)
        self.assertNotIn('[[', snippet)
        self.assertIn('… ', snippet)

    def test_assistant_scope_and_video_filter_keep_correct_source(self):
        self.assertEqual([r['id'] for r in server.find('مبكرا', 'video')['results']], ['video'])
        self.assertEqual({r[0] for r in assistant._fts('مبكرًا', ids='["video-tx"]')}, {'video-tx'})
        self.assertEqual(assistant._fts('مبكرا', ids='[]'), [])
        self.assertIn('مبكرًا', assistant._fts('مبكرا', ids='["marked"]')[0][2])

    def test_latin_queries_keep_existing_fts_and_accents(self):
        with patch.object(server.library, 'text_search_rows', side_effect=AssertionError('Latin query took script path')):
            self.assertEqual({r['id'] for r in server.find('water')['results']}, {'marked', 'english'})
            self.assertEqual({r[0] for r in assistant._fts('cafe')}, {'english'})

    def test_cli_marked_and_unmarked_queries_match_without_database_writes(self):
        before = hashlib.sha256(self.db.read_bytes()).hexdigest()
        tool = Path(__file__).resolve().parents[2] / 'tools/libq.py'
        results = []
        for query in ['مبكرا', 'مبكرًا']:
            p = subprocess.run([sys.executable, str(tool), '--data', str(self.root), 'search', query], capture_output=True, text=True, encoding='utf-8', check=True)
            self.assertIn('marked |', p.stdout); self.assertNotIn('prefix |', p.stdout)
            results.append(p.stdout)
        self.assertEqual(results[0], results[1])
        self.assertEqual(hashlib.sha256(self.db.read_bytes()).hexdigest(), before)

    def test_long_mark_runs_match_without_treating_query_as_regex(self):
        body = 'ق' + 'ّ' * 2000 + 'و' + 'َ' * 2000 + 'ي'
        self.assertEqual(list(search_text.arabic_matches(body, 'قوي')), [(0, len(body))])
        self.assertEqual(list(search_text.arabic_matches(body, 'قوي.*')), [])


if __name__ == '__main__':
    unittest.main()
