#!/usr/bin/env python3
"""The library's full-text search in scripts whose words carry combining marks: Hindi, Thai, vowelled Arabic, pointed
Hebrew. No real library, no server, no port: small made-up indexes in a temporary folder.

  python3 -B -m unittest app.tests.test_library_search

The index keeps marks inside words (engine/library.py, TOKENIZE) and every search splits its words the same way
(query_terms). English and Latin-accent searches must find exactly what they found before.

Also here, because they guard the same change: build() checks a new index before it replaces the one in use and leaves
that one alone when anything fails (Rebuild), the pack scan fails an index not made as the pack spec says (PackScan),
the old launcher's --check makes and searches the real table (LauncherCheck), and so does the packaged app's own entry
point, app/main.py --self-test (SelfTest).
"""
import contextlib, hashlib, importlib.util, io, json, os, re, shutil, sqlite3, subprocess, sys, tempfile, threading, types, unicodedata, unittest
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT)]
LIBRARY_DIR = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)


def load_library():
    """A private copy of engine/library.py whose library folder is a new, empty temporary one. engine.library itself is left
    alone: it fixes its folder when first imported, and test_bridge needs it to be the data folder it sets up."""
    with mock.patch.dict(os.environ, {'LASTBOOK_LIBRARY': LIBRARY_DIR.name}):
        spec = importlib.util.spec_from_file_location('library_under_test', ROOT / 'engine' / 'library.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


library = load_library()

# The table and the split as they were before marks were kept, to show what changes and what must not.
OLD_TABLE = 'CREATE VIRTUAL TABLE pages USING fts5(doc_id UNINDEXED,title,collection,category,path UNINDEXED,page UNINDEXED,body,tokenize="unicode61")'
SQL = "SELECT doc_id FROM pages WHERE pages MATCH ? ORDER BY bm25(pages,0,5,2,1,0,0,1) LIMIT 25"

HINDI = [('hi-water', 'पानी को उबालें।'),          # boil the water
         ('hi-drink', 'रोज़ दवा पीना।')]            # take (drink) medicine daily: the same consonants प and न as पानी
# Thai is written without spaces between words, and unicode61 does not segment it: a run of Thai letters is one word,
# before this change and after. These pages put a space between words, as the fix is about each word staying whole.
THAI = [('th-water', 'น้ำ สะอาด'),                  # clean water
        ('th-lead', 'นำ ทาง'),                       # lead the way
        ('th-sentence', 'ต้มน้ำให้เดือดก่อนดื่ม')]     # boil water before drinking, written as Thai is: no spaces
ARABIC = [('ar-letter', 'هذا حَرْف'),               # this is a letter (of the alphabet)
          ('ar-joy', 'فَرَحٌ كبير')]                  # great joy: the same three letters, ف ر ح, in another order
HEBREW = [('he-peace', 'שָׁלוֹם עֲלֵיכֶם'),          # peace be upon you
          ('he-name', 'שֵׁם לוֹ')]                    # a name for him: ש, לו and ם again, in other words
LATIN = [('la-creme', 'Crème brûlée'), ('la-cafe', 'Café au lait'), ('la-street', 'Die Straße ist nass')]
ENGLISH = [('en-boil', 'Bring water to a rolling boil for one minute.'),
           ('en-store', 'Store drinking-water in clean, food-grade containers.'),
           ('en-dehydration', 'Signs of dehydration: thirst, dark urine, dizziness.'),
           ('en-flood', "Don't drink flood water; it carries sewage."),
           ('en-bleach', 'Use 2-3 drops of bleach per litre of clear water.'),
           ('en-wound', 'wound_care basics: clean, cover, watch for infection'),
           ('en-cafe', 'A café filter is not a water filter.')]
ENGLISH_QUERIES = ['water', 'rolling boil', 'drinking-water', 'food grade', "don't drink", '2-3 drops', 'wound_care',
                   'bleach litre', 'cafe', 'café', 'CAFÉ', 'dehydration thirst', 'water filter', 'nothing-here', '', '!!!',
                   'Straße', 'strasse', 'creme', 'brulee']


def make_db(path, table, pages):
    con = sqlite3.connect(path)
    try:
        con.execute(table)
        for doc, body in pages:
            con.execute('INSERT INTO pages VALUES (?,?,?,?,?,?,?)', (doc, '', '', '', f'documents/{doc}.pdf', 1, body))
        con.commit()
    finally:
        con.close()        # Windows will not remove an open file
    return path


def old_search(db, q):
    """engine/library.py's search() as it was: words by [\\w-]+, each quoted, all of them required."""
    terms = re.findall(r'[\w-]+', q, flags=re.UNICODE)
    if not terms:
        return []
    con = sqlite3.connect(db)
    try:
        return [r[0] for r in con.execute(SQL, (' AND '.join('"' + t.replace('"', '""') + '"' for t in terms),))]
    finally:
        con.close()


def new_search(db, q):
    with mock.patch.object(library, 'DB', Path(db)):
        return [r['doc_id'] for r in library.search(q)]


def vocabulary(db):
    con = sqlite3.connect(db)
    try:
        con.execute("CREATE VIRTUAL TABLE temp.v USING fts5vocab('main','pages','row')")
        return {r[0] for r in con.execute('SELECT term FROM temp.v')}
    finally:
        con.close()


def load_libq():
    spec = importlib.util.spec_from_file_location('libq_under_test', ROOT / 'tools' / 'libq.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Split(unittest.TestCase):
    """query_terms against the old regular expressions, character by character over the whole of Unicode."""
    @classmethod
    def setUpClass(cls):
        chars = [chr(c) for c in range(0x110000) if not 0xD800 <= c <= 0xDFFF]
        cls.marks = [c for c in chars if unicodedata.category(c)[0] == 'M']
        cls.no_marks = ' '.join(c for c in chars if unicodedata.category(c)[0] != 'M')   # each character on its own
        cls.everything = ' '.join(chars)

    def test_without_marks_nothing_changes(self):
        self.assertEqual(library.query_terms(self.no_marks), re.findall(r'[\w-]+', self.no_marks))
        self.assertEqual(library.query_terms(self.no_marks, keep="'-"), re.findall(r"[\w'-]+", self.no_marks))
        for q in ENGLISH_QUERIES + ["can't breathe", "o'clock", 'snake_bite first-aid kit', 'água  potável', 'İstanbul ıslak']:
            self.assertEqual(library.query_terms(q), re.findall(r'[\w-]+', q), q)
            self.assertEqual(library.query_terms(q, keep="'-"), re.findall(r"[\w'-]+", q), q)

    def test_marks_stay_in_the_word(self):
        self.assertTrue(self.marks)
        self.assertEqual(library.query_terms(' '.join('a' + m for m in self.marks)), ['a' + m for m in self.marks])
        self.assertEqual(library.query_terms('पानी उबालें'), ['पानी', 'उबालें'])
        self.assertEqual(library.query_terms('น้ำ'), ['น้ำ'])
        self.assertEqual(library.query_terms('حَرْف'), ['حَرْف'])
        self.assertEqual(library.query_terms('שָׁלוֹם'), ['שָׁלוֹם'])
        self.assertEqual(library.query_terms('café noir'), ['café', 'noir'])    # a decomposed é stays whole

    def test_a_mark_alone_is_not_a_word(self):
        """A stray accent between spaces has no token in the index; kept as a word it would make the whole search fail."""
        self.assertEqual(library.query_terms('boil \u0301 water'), ['boil', 'water'])
        self.assertEqual(library.query_terms(' '.join(self.marks)), [])
        self.assertEqual(library.query_terms('\u0301\u0301-'), ['\u0301\u0301-'])     # with a '-' it is a word, as '-' was before

    def test_libq_splits_the_same_way(self):
        self.assertEqual(load_libq().query_terms(self.everything), library.query_terms(self.everything))


class Search(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        d = Path(cls.dir.name)
        pages = HINDI + THAI + ARABIC + HEBREW + LATIN + ENGLISH
        cls.new = make_db(d / 'new.sqlite', library.PAGES_TABLE, pages)
        cls.old = make_db(d / 'old.sqlite', OLD_TABLE, pages)

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def test_the_build_makes_the_table_with_marks(self):
        """build() itself, on a made-up catalog in the private library folder: nothing is read from disk to extract."""
        records = [{'id': d, 'title': d, 'collection': 'Hindi', 'category': 'water', 'path': f'documents/{d}.pdf', 'kind': 'pdf',
                    'pages': 1, 'bytes': 1} for d, _ in HINDI]
        text = dict(HINDI)
        with mock.patch.object(library, 'catalog', lambda: (records, [])), \
                mock.patch.object(library, 'extract', lambda r: (r, [text[r['id']]], None)), \
                mock.patch('builtins.print'):
            library.build()
        self.assertTrue(library.DB.is_file())
        self.assertFalse(library.DB.with_suffix('.building.sqlite').exists())
        con = sqlite3.connect(library.DB)
        try:
            sql = con.execute("SELECT sql FROM sqlite_master WHERE name='pages'").fetchone()[0]
        finally:
            con.close()
        self.assertIn("categories 'L* N* Co M*'", sql)
        self.assertNotIn('remove_diacritics', sql)                                      # Latin accents still fold
        self.assertEqual(new_search(library.DB, 'पानी'), ['hi-water'])

    def test_packs_build_the_same_table(self):
        """packaging/build_packs.py makes each pack's index from the pack spec's schema, not from the builder's file."""
        spec = json.loads((ROOT / 'derived' / 'packs' / 'pack-spec.json').read_text(encoding='utf-8'))
        self.assertEqual('CREATE VIRTUAL TABLE pages USING ' + spec['search_index']['schema'], library.PAGES_TABLE)

    def test_a_stray_accent_does_not_empty_the_search(self):
        self.assertEqual(new_search(self.new, 'boil \u0301 water'), new_search(self.new, 'boil water'))
        self.assertEqual(new_search(self.new, 'boil water'), ['en-boil'])

    def test_hindi_words_stay_whole(self):
        self.assertIn('hi-drink', old_search(self.old, 'पानी'))               # the bug: water also found drink
        self.assertEqual(new_search(self.new, 'पानी'), ['hi-water'])
        self.assertEqual(new_search(self.new, 'पीना'), ['hi-drink'])
        self.assertEqual(new_search(self.new, 'उबालें'), ['hi-water'])
        self.assertEqual(new_search(self.new, 'पानी उबालें'), ['hi-water'])
        self.assertTrue({'पानी', 'पीना', 'उबालें'} <= vocabulary(self.new))

    def test_thai(self):
        self.assertEqual(new_search(self.new, 'น้ำ'), ['th-water'])
        self.assertEqual(new_search(self.new, 'นำ'), ['th-lead'])
        self.assertIn('น้ำ', vocabulary(self.new))
        self.assertNotIn('น้ำ', vocabulary(self.old))
        # The limit that stays: a word inside unspaced Thai is not found, before or after. That needs a word segmenter.
        for q in ('น้ำ', 'ดื่ม', 'เดือด'):
            self.assertNotIn('th-sentence', new_search(self.new, q), q)
        self.assertEqual(new_search(self.new, 'ต้มน้ำให้เดือดก่อนดื่ม'), ['th-sentence'])

    def test_vowelled_arabic_and_pointed_hebrew(self):
        self.assertIn('ar-joy', old_search(self.old, 'حَرْف'))              # the bug: any word with ح, ر and ف
        self.assertEqual(new_search(self.new, 'حَرْف'), ['ar-letter'])
        self.assertEqual(new_search(self.new, 'فَرَحٌ'), ['ar-joy'])
        self.assertIn('he-name', old_search(self.old, 'שָׁלוֹם'))
        self.assertEqual(new_search(self.new, 'שָׁלוֹם'), ['he-peace'])
        # Not covered here, and not changed: an unvowelled search (حرفا) does not find vowelled text. That needs the
        # vowel marks removed on both sides, a normalisation step for each language rather than a tokenizer option.

    def test_latin_accents_still_fold(self):
        self.assertEqual(new_search(self.new, 'creme'), ['la-creme'])
        self.assertEqual(new_search(self.new, 'crème'), ['la-creme'])
        self.assertEqual(new_search(self.new, 'café au lait'), ['la-cafe'])        # typed with a separate accent
        self.assertEqual(new_search(self.new, 'Café'), old_search(self.old, 'Café'))
        for q in ('Straße', 'strasse'):                                                 # ß is not folded, before or after
            self.assertEqual(new_search(self.new, q), old_search(self.old, q), q)

    def test_english_finds_what_it_found_before(self):
        for q in ENGLISH_QUERIES:
            self.assertEqual(new_search(self.new, q), old_search(self.old, q), q)
        self.assertEqual(new_search(self.new, 'water'), old_search(self.old, 'water'))
        self.assertGreater(len(new_search(self.new, 'water')), 3)                    # the fixture really is searched

    def test_new_app_with_an_old_index_is_no_worse(self):
        """The app may be updated before its index is rebuilt. Each word is then cut by the old index's own tokenizer and
        matched as a phrase of its pieces, where before the pieces could sit anywhere on the page: the same pages or fewer,
        never losing the page that has the word, and nothing fails."""
        for q in ENGLISH_QUERIES:
            self.assertEqual(new_search(self.old, q), old_search(self.old, q), q)
        for q, page in (('पानी', 'hi-water'), ('पीना', 'hi-drink'), ('उबालें', 'hi-water'), ('पानी उबालें', 'hi-water'),
                        ('น้ำ', 'th-water'), ('حَرْف', 'ar-letter'), ('שָׁלוֹם', 'he-peace'), ('cafe\u0301', 'la-cafe')):
            found = new_search(self.old, q)
            self.assertIn(page, found, q)
            self.assertLessEqual(set(found), set(old_search(self.old, q)), q)
        self.assertEqual(new_search(self.old, 'पानी'), old_search(self.old, 'पानी'))       # still the old wrong match, until rebuilt
        self.assertNotIn('he-name', new_search(self.old, 'שָׁלוֹם'))                       # already one fewer

    def test_the_app_search_splits_the_same_way(self):
        """server.py's query_groups feeds the app's search box and the assistant's retrieval."""
        import server            # here, not at the top, as in test_address_search: test_bridge sets its data folder first
        content, groups = server.query_groups('पानी उबालें')
        self.assertEqual(content, ['पानी', 'उबालें'])
        con = sqlite3.connect(self.new)
        try:
            found = [r[0] for r in con.execute('SELECT doc_id FROM pages WHERE pages MATCH ?', (server.fts_expr(groups),))]
        finally:
            con.close()
        self.assertEqual(found, ['hi-water'])
        for q in ("don't drink flood water", 'drinking-water containers', 'wound_care'):   # English as before
            words = [w.strip("'") for w in re.findall(r"[\w'-]+", q.lower()) if w.strip("'")]
            expected = [w for w in words if w not in server.STOP] or words
            self.assertEqual(server.query_groups(q)[0], expected, q)


class Libq(unittest.TestCase):
    """tools/libq.py, run as a curator runs it, against an index built with the app's own table."""
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls.data = Path(cls.dir.name) / 'data'
        lib = cls.data / 'library-data'
        lib.mkdir(parents=True)
        (lib / 'catalog.json').write_text(json.dumps([{'id': d, 'kind': 'pdf', 'title': d} for d, _ in HINDI]), encoding='utf-8')
        con = sqlite3.connect(lib / 'search.sqlite')
        try:
            con.execute(library.PAGES_TABLE)
            for doc, body in HINDI:
                con.execute('INSERT INTO pages VALUES (?,?,?,?,?,?,?)', (doc, doc, 'Hindi', 'water', f'documents/{doc}.pdf', 1, body))
            con.commit()
        finally:
            con.close()

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def test_hindi_search(self):
        env = {k: v for k, v in os.environ.items() if k != 'LASTBOOK_DATA'}
        r = subprocess.run([sys.executable, '-B', str(ROOT / 'tools' / 'libq.py'), '--data', str(self.data), 'search', 'पानी'],
                           capture_output=True, text=True, encoding='utf-8', errors='replace', env=env, cwd=self.dir.name)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('hi-water | hi-water | Hindi | pages [1]', r.stdout)
        self.assertNotIn('hi-drink', r.stdout)


def load_file(name, path):
    """A module from its file, leaving the environment and the import path as they were (the launcher changes both)."""
    before = list(sys.path)
    try:
        with mock.patch.dict(os.environ):
            spec = importlib.util.spec_from_file_location(name, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
    finally:
        sys.path[:] = before
    return module


def damage(path):
    """Make the file's header claim five free pages it does not have, as a cut-off write can. Every row still counts and
    every search still answers; only SQLite's integrity check says the file is wrong, in words."""
    with open(path, 'r+b') as f:
        f.seek(36)
        f.write((5).to_bytes(4, 'big'))


def damage_page(path, table='pages_idx'):
    """Overwrite the first page of one of the index's own tables, as a bad disk would. pages_idx is the index's list of
    where its words are kept: the rows still count, and the integrity check stops with an error instead of an answer."""
    con = sqlite3.connect(path)
    try:
        size = con.execute('PRAGMA page_size').fetchone()[0]
        page = con.execute('SELECT rootpage FROM sqlite_master WHERE name=?', (table,)).fetchone()[0]
    finally:
        con.close()
    with open(path, 'r+b') as f:
        f.seek((page - 1) * size)
        f.write(b'\xff' * size)


FTS = 'CREATE VIRTUAL TABLE pages USING fts5(doc_id UNINDEXED,title,collection,category,path UNINDEXED,page UNINDEXED,body'
MARKS = '"unicode61 categories \'L* N* Co M*\'"'
# Tables SQLite will make that are not the app's table. Some cut words another way, some the same way but are written
# differently, and two only show the app's tokenizer inside a comment. The checks compare the whole statement, so none passes.
LOOK_ALIKES = [OLD_TABLE,
               FTS + ')',
               FTS + ',tokenize="unicode61 categories \'L* N* Co\'")',
               FTS + ',tokenize="unicode61 categories \'L* N* Co M*\' remove_diacritics 0")',
               FTS + ",tokenize=[unicode61 categories 'L* N* Co M*'])",
               FTS + ', tokenize = ' + MARKS + ')',
               FTS + ',TOKENIZE=' + MARKS + ')',
               FTS + ' /* ,tokenize=' + MARKS + ' , */ ,tokenize="unicode61")',
               FTS.replace(' USING ', ' /* fts5(tokenize=' + MARKS + ') */ USING ') + ')']


class Rebuild(unittest.TestCase):
    """build() puts a new index in place only after checking the finished file, and anything that goes wrong before or
    during the replace leaves the index that was there exactly as it was. Each test has its own folder, with an index
    made the old way already in place."""
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.dir.cleanup)
        self.db = Path(self.dir.name) / 'search.sqlite'
        self.staged = self.db.with_suffix('.building.sqlite')
        patch = mock.patch.object(library, 'DB', self.db)
        patch.start()
        self.addCleanup(patch.stop)
        make_db(self.db, OLD_TABLE, ENGLISH)
        self.before = self.db.read_bytes()
        for name in ('catalog.json', 'summary.json'):
            (library.ROOT / name).write_text('"as it was"', encoding='utf-8')

    def build(self, extract=None, pages=HINDI):
        records = [{'id': d, 'title': d, 'collection': 'Hindi', 'category': 'water', 'path': f'documents/{d}.pdf', 'kind': 'pdf',
                    'pages': 1, 'bytes': 1} for d, _ in pages]
        text = dict(pages)
        with mock.patch.object(library, 'catalog', lambda: (records, [])), \
                mock.patch.object(library, 'extract', extract or (lambda r: (r, [text[r['id']]], None))), \
                mock.patch('builtins.print'):
            library.build()

    def refused(self, pages=HINDI, **patches):
        """A build that must stop with a message, leave the index byte for byte as it was and still searchable, leave no
        file of its own behind, and not write the catalog that goes with a new index."""
        with mock.patch.multiple(library, **patches) if patches else mock.patch.dict({}):
            with self.assertRaises(SystemExit) as stopped:
                self.build(pages=pages)
        self.unchanged()
        self.assertIn('The index already there is unchanged', str(stopped.exception))
        return str(stopped.exception)

    def unchanged(self):
        self.assertEqual(self.db.read_bytes(), self.before)
        self.assertEqual([p.name for p in Path(self.dir.name).iterdir()], ['search.sqlite'])
        self.assertEqual(old_search(self.db, 'rolling boil'), ['en-boil'])
        for name in ('catalog.json', 'summary.json'):
            self.assertEqual((library.ROOT / name).read_text(encoding='utf-8'), '"as it was"', name)

    def test_which_index_is_current(self):
        d = Path(self.dir.name) / 'others'
        d.mkdir()
        self.assertFalse(library.index_is_current(self.db))                                                      # made the old way
        self.assertTrue(library.index_is_current(make_db(d / 'new.sqlite', library.PAGES_TABLE, HINDI)))
        for i, sql in enumerate(LOOK_ALIKES):
            self.assertFalse(library.index_is_current(make_db(d / f'other-{i}.sqlite', sql, HINDI)), sql)
        (d / 'garbage.sqlite').write_bytes(b'not a database at all' * 500)
        self.assertFalse(library.index_is_current(d / 'garbage.sqlite'))
        con = sqlite3.connect(d / 'no-pages.sqlite')
        con.execute('CREATE TABLE other(x)')
        con.commit()
        con.close()
        self.assertFalse(library.index_is_current(d / 'no-pages.sqlite'))
        self.assertFalse(library.index_is_current(d / 'missing.sqlite'))
        self.assertFalse((d / 'missing.sqlite').exists())                                                        # looking does not make one
        self.assertFalse(library.index_is_current(d))                                                            # a folder

    def test_a_good_build_replaces_the_old_index(self):
        self.build()
        self.assertTrue(library.index_is_current(self.db))
        self.assertEqual([p.name for p in Path(self.dir.name).iterdir()], ['search.sqlite'])
        self.assertEqual(new_search(self.db, 'पानी'), ['hi-water'])
        self.assertNotEqual((library.ROOT / 'catalog.json').read_text(encoding='utf-8'), '"as it was"')

    def test_an_empty_build_does_not_wipe_an_index_that_has_pages(self):
        """Nothing to index, as when the library's disk is not there: the pages already indexed stay searchable."""
        self.assertIn('nothing was indexed', self.refused(pages=[]))

    def test_an_empty_library_still_builds(self):
        self.db.unlink()
        self.build(pages=[])                                                 # no index yet
        self.assertTrue(library.index_is_current(self.db))
        self.assertEqual(new_search(self.db, 'water'), [])
        self.build(pages=[])                                                 # and over an index that is empty too
        self.assertTrue(library.index_is_current(self.db))
        self.build()                                                         # and pages replace an empty index
        self.assertEqual(new_search(self.db, 'पानी'), ['hi-water'])

    def test_what_an_interrupted_build_left_is_cleared_first(self):
        self.staged.write_bytes(b'half a file from a build that was killed')
        for extra in ('-journal', '-wal', '-shm'):
            self.staged.with_name(self.staged.name + extra).write_bytes(b'and what SQLite left beside it')
        self.build()
        self.assertTrue(library.index_is_current(self.db))
        self.assertEqual([p.name for p in Path(self.dir.name).iterdir()], ['search.sqlite'])

    def test_a_build_that_stops_partway_changes_nothing(self):
        text = dict(HINDI)

        def extract(r):
            if r['id'] == HINDI[-1][0]:
                raise RuntimeError('the disk went away')
            return r, [text[r['id']]], None
        with self.assertRaises(RuntimeError):
            self.build(extract)
        self.unchanged()

    def test_a_damaged_new_index_is_not_used(self):
        """The file is damaged for real, after it is written and before it is checked, and the real check finds it."""
        check = library.index_fault

        def damaged(path, rows):
            damage(path)
            return check(path, rows)
        self.assertIn('integrity check', self.refused(index_fault=damaged))

    def test_what_the_check_refuses(self):
        d = Path(self.dir.name) / 'others'
        d.mkdir()
        good = make_db(d / 'good.sqlite', library.PAGES_TABLE, HINDI)
        self.assertIsNone(library.index_fault(good, len(HINDI)))
        self.assertIsNone(library.index_fault(make_db(d / 'empty.sqlite', library.PAGES_TABLE, []), 0))  # an empty library has an empty index
        self.assertIn('rows', library.index_fault(good, len(HINDI) + 1))                                 # a row went missing
        self.assertIn('rows', library.index_fault(good, len(HINDI) - 1))
        self.assertIn('tokenizer', library.index_fault(self.db, len(ENGLISH)))                           # sound, complete, made the old way
        self.assertIn('cannot be read', library.index_fault(d / 'missing.sqlite', 0))
        self.assertFalse((d / 'missing.sqlite').exists())
        for kind, (harm, says) in enumerate([(damage, 'integrity check'), (damage_page, 'cannot be read')]):
            broken = Path(shutil.copy(good, d / f'broken-{kind}.sqlite'))
            harm(broken)
            con = sqlite3.connect(broken)
            try:
                self.assertEqual(con.execute('SELECT count(*) FROM pages').fetchone()[0], len(HINDI))   # the rows still count right
            finally:
                con.close()
            self.assertIn(says, library.index_fault(broken, len(HINDI)))                                 # so only the integrity check finds it

    def test_pages_are_counted_as_they_are_indexed(self):
        """The rows expected are the pages that were put in: every page with text, and none of the blank ones."""
        text = {HINDI[0][0]: [HINDI[0][1], '   ', '', 'दूसरा पन्ना'], HINDI[1][0]: [HINDI[1][1]]}
        check, expected = library.index_fault, []

        def watched(path, rows):
            expected.append(rows)
            return check(path, rows)
        with mock.patch.object(library, 'index_fault', watched):
            self.build(lambda r: (r, text[r['id']], None))
        self.assertEqual(expected, [3])
        con = sqlite3.connect(self.db)
        try:
            self.assertEqual(con.execute('SELECT count(*) FROM pages').fetchone()[0], 3)
        finally:
            con.close()

    def test_each_reason_stops_the_build(self):
        for why in ('it fails its integrity check', 'it holds 1 rows, not the 2 that were indexed', 'its table, tokenizer included, is not the one searches expect'):
            self.assertIn(why, self.refused(index_fault=lambda path, rows, why=why: why))

    def test_an_index_that_cannot_be_replaced_is_kept(self):
        def locked(building, dest, **kw):
            raise PermissionError(13, 'The process cannot access the file because it is being used by another process')
        self.assertIn('could not be replaced', self.refused(replace_index=locked))

        def full(building, dest, **kw):
            raise OSError(28, 'No space left on device')
        self.assertIn('could not be replaced', self.refused(replace_index=full))                 # any failure to replace, not only a lock

    def test_a_locked_index_is_tried_again_and_only_so_many_times(self):
        d = Path(self.dir.name)
        new = make_db(d / 'new.sqlite', library.PAGES_TABLE, HINDI)
        replace, calls = os.replace, []

        def busy(times, error=PermissionError):
            def go(a, b):
                calls.append(a)
                if len(calls) <= times:
                    raise error(13, 'in use')
                replace(a, b)
            return go
        with mock.patch.object(library.os, 'replace', busy(2)), mock.patch.object(library.time, 'sleep') as sleep:
            library.replace_index(new, self.db, tries=5)                          # busy twice, free the third time
        self.assertEqual(len(calls), 3)
        self.assertEqual([c.args for c in sleep.call_args_list], [(library.REPLACE_WAIT,)] * 2)   # a wait between tries, none after the last
        self.assertTrue(2 <= library.REPLACE_TRIES * library.REPLACE_WAIT <= 30)                  # seconds: long enough for a search, and bounded
        self.assertTrue(library.index_is_current(self.db))
        self.assertFalse(new.exists())
        self.before = self.db.read_bytes()
        again = make_db(d / 'again.sqlite', library.PAGES_TABLE, HINDI)
        del calls[:]
        with mock.patch.object(library.os, 'replace', busy(99)), self.assertRaises(PermissionError):
            library.replace_index(again, self.db, tries=5, wait=0)           # never free: five tries, then the error
        self.assertEqual(len(calls), 5)
        self.assertEqual(self.db.read_bytes(), self.before)
        del calls[:]
        with mock.patch.object(library.os, 'replace', busy(99, FileNotFoundError)), self.assertRaises(FileNotFoundError):
            library.replace_index(again, self.db, tries=5, wait=0)           # not a lock: no second try
        self.assertEqual(len(calls), 1)
        del calls[:]
        with mock.patch.object(library.os, 'replace', busy(99)), self.assertRaises(PermissionError):
            library.replace_index(again, self.db, wait=0)                    # left to itself: Windows waits, nothing else does
        self.assertEqual(len(calls), library.REPLACE_TRIES if os.name == 'nt' else 1)

    @unittest.skipUnless(os.name == 'nt', 'only Windows refuses to replace a file that is open')
    def test_windows_waits_for_a_search_to_let_go(self):
        """A real open connection, as search() holds for a moment, closed while build() is waiting."""
        holder = sqlite3.connect(self.db, check_same_thread=False)
        holder.execute('SELECT count(*) FROM pages').fetchone()
        with self.assertRaises(PermissionError):
            os.replace(make_db(Path(self.dir.name) / 'probe.sqlite', library.PAGES_TABLE, HINDI), self.db)   # the lock is real
        (Path(self.dir.name) / 'probe.sqlite').unlink()
        replace, tries = os.replace, []

        def counted(a, b):
            tries.append(a)
            replace(a, b)
        timer = threading.Timer(0.7, holder.close)
        timer.start()
        try:
            with mock.patch.object(library.os, 'replace', counted):
                self.build()
        finally:
            timer.join()
        self.assertGreater(len(tries), 1)                                    # it was refused at least once, and tried again
        self.assertTrue(library.index_is_current(self.db))
        self.assertEqual(new_search(self.db, 'पानी'), ['hi-water'])

    @unittest.skipUnless(os.name == 'nt', 'only Windows refuses to replace a file that is open')
    def test_windows_gives_up_and_keeps_the_index(self):
        holder = sqlite3.connect(self.db)
        try:
            holder.execute('SELECT count(*) FROM pages').fetchone()
            with mock.patch.object(library, 'REPLACE_WAIT', 0.01):
                self.assertIn('could not be replaced', self.refused())
        finally:
            holder.close()


class PackScan(unittest.TestCase):
    """packaging/scan_pack.py takes the format a pack is meant to have from the pack spec: the index must have been made
    with the spec's own statement. An index made the old way fails when the spec asks for the new tokenizer, and passes
    against the spec it was built from."""
    OLD_SCHEMA = OLD_TABLE.split(' USING ', 1)[1]

    @classmethod
    def setUpClass(cls):
        cls.scan_pack = load_file('scan_pack_under_test', ROOT / 'packaging' / 'scan_pack.py')
        cls.dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        d = Path(cls.dir.name)
        cls.new = make_db(d / 'new.sqlite', library.PAGES_TABLE, HINDI)
        cls.old = make_db(d / 'old.sqlite', OLD_TABLE, HINDI)

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def rules(self, db, schema=None):
        scan = self.scan_pack.Scan(Path(self.dir.name), [], {}, None)
        with mock.patch.dict(self.scan_pack.SPEC['search_index'], {'schema': schema} if schema else {}):
            scan.inspect_search('library-data/search.sqlite', db)
        return set(scan.fails)

    def test_an_old_index_fails_when_the_new_format_is_expected(self):
        self.assertIn('search.schema_differs', self.rules(self.old))
        self.assertNotIn('search.schema_differs', self.rules(self.new))

    def test_an_old_index_passes_against_the_spec_it_was_built_from(self):
        self.assertNotIn('search.schema_differs', self.rules(self.old, self.OLD_SCHEMA))
        self.assertIn('search.schema_differs', self.rules(self.new, self.OLD_SCHEMA))           # and a new one does not

    def test_an_index_made_as_the_pack_builder_makes_it_passes(self):
        """packaging/build_packs.py build_search: the spec's statement, then optimize, VACUUM and journal mode DELETE."""
        spec = json.loads((ROOT / 'derived' / 'packs' / 'pack-spec.json').read_text(encoding='utf-8'))
        built = make_db(Path(self.dir.name) / 'built.sqlite', 'CREATE VIRTUAL TABLE pages USING ' + spec['search_index']['schema'], HINDI)
        con = sqlite3.connect(built)
        try:
            con.execute("INSERT INTO pages(pages) VALUES('optimize')")
            con.commit()
            con.execute('VACUUM')
            con.execute('PRAGMA journal_mode=DELETE')
        finally:
            con.close()
        self.assertNotIn('search.schema_differs', self.rules(built))
        self.assertTrue(library.index_is_current(built))

    def test_a_table_that_only_looks_right_fails(self):
        for i, sql in enumerate(LOOK_ALIKES):
            self.assertIn('search.schema_differs', self.rules(make_db(Path(self.dir.name) / f'other-{i}.sqlite', sql, HINDI)), sql)

    def test_a_file_with_no_pages_table_does_not_pass(self):
        """The scan stops on such a file, and a scan that stops is a failed scan; it never counts as a pass."""
        con = sqlite3.connect(Path(self.dir.name) / 'no-pages.sqlite')
        con.execute('CREATE TABLE other(x)')
        con.commit()
        con.close()
        with self.assertRaises(sqlite3.Error):
            self.rules(Path(self.dir.name) / 'no-pages.sqlite')


def engine_swapped(lib, run):
    """Run with lib (the private copy of the library, see load_library, or a stand-in) in place of engine.library, and a
    stand-in for engine.paths, which would fix the data folder for every test that runs after this one. Both the module
    table and the package's own attributes are swapped: an import takes whichever it finds."""
    import engine
    stand_in = types.ModuleType('engine.paths')
    server = types.ModuleType('server')    # main's self-test imports server.py, which needs the real engine.paths: whether it
    server.query_groups = lambda q: ([q], [[q]])   # loads would depend on which tests ran first. The real one runs in the
    server.fts_expr = lambda groups: ' AND '.join('(' + ' OR '.join('"' + t + '"' for t in g) + ')' for g in groups)  # process tests
    with mock.patch.dict(sys.modules, {'engine.library': lib, 'engine.paths': stand_in, 'server': server}), \
            mock.patch.object(engine, 'library', lib, create=True), mock.patch.object(engine, 'paths', stand_in, create=True):
        return run()


def snapshot(folder):
    """Every file and folder under folder, with each file's hash."""
    out = {}
    for p in sorted(Path(folder).rglob('*')):
        out[p.relative_to(folder).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else 'dir'
    return out


class LauncherCheck(unittest.TestCase):
    """The packaged app's --check makes the library's real search table and searches it, not a plain fts5(x) one."""
    @classmethod
    def setUpClass(cls):
        cls.launcher = load_file('launcher_under_test', ROOT / 'packaging' / 'lastbook_launcher.py')

    def swapped(self, run):
        return engine_swapped(library, run)

    def check(self, table=None):
        return self.swapped(lambda: self.launcher.search_index_check(table))

    def test_the_library_folder_is_named_before_the_library_loads(self):
        """engine.library fixes its folder when first imported, from what engine.paths has set: paths comes first."""
        order, real = [], __import__

        def spy(name, *args, **kwargs):
            order.append(name)
            return real(name, *args, **kwargs)
        with mock.patch('builtins.__import__', spy):
            self.check()
        self.assertLess(order.index('engine.paths'), order.index('engine.library'))

    def test_the_whole_check_reports_the_search_table(self):
        """--check itself, with every other library it would load made unavailable: those entries fail, and the sqlite
        entry is the real table's."""
        absent = dict.fromkeys(('numpy', 'onnxruntime', 'tokenizers', 'bs4', 'pypdfium2', 'libzim', 'webview', 'clr', 'server', 'retrieval'))
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d, mock.patch.dict(sys.modules, absent):
            code = self.swapped(lambda: self.launcher.check(Path(d) / 'data', Path(d)))
            report = json.loads((Path(d) / 'check.json').read_text(encoding='utf-8'))
        self.assertEqual(code, 1)                                              # the absent libraries
        self.assertTrue(str(report['numpy']).startswith('FAILED'))
        self.assertEqual(report['sqlite'], {'sqlite': sqlite3.sqlite_version, 'fts5': True, 'tokenize': library.TOKENIZE,
                                            'marks_stay_in_words': True, 'searches': ['library.search']})

    def test_it_uses_the_table_the_app_builds(self):
        report = self.check()
        self.assertEqual(report['tokenize'], library.TOKENIZE)
        self.assertTrue(report['fts5'] and report['marks_stay_in_words'])
        self.assertEqual(report['sqlite'], sqlite3.sqlite_version)

    def test_it_fails_on_an_sqlite_that_cuts_words_the_old_way(self):
        with self.assertRaises(ValueError):
            self.check(OLD_TABLE)

    def test_it_fails_on_an_sqlite_that_does_not_know_the_tokenizer(self):
        with self.assertRaises(sqlite3.OperationalError):
            self.check(library.PAGES_TABLE.replace('unicode61', 'no_such_tokenizer'))


class SelfTest(unittest.TestCase):
    """app/main.py --self-test: the entry point every current package starts runs the search check (search_self_test), and
    touches no library, no settings, nothing in the program folder and nothing outside its own temporary folders."""
    EXPECTED = {'sqlite': sqlite3.sqlite_version, 'fts5': True, 'tokenize': library.TOKENIZE, 'marks_stay_in_words': True,
                'searches': ['library.search']}
    FROM_MAIN = dict(EXPECTED, searches=['library.search', 'server.find'])

    def test_every_matcher_must_find_each_words_own_page(self):
        """Another way into the index (the search box's, from main) is held to the same rule, word by word."""
        self.assertEqual(library.search_self_test(matchers={'exact': lambda w: '"' + w + '"'})['searches'], ['library.search', 'exact'])
        for name, build in [('nothing', lambda w: '"x"'), ('both', lambda w: '"पानी" OR "पीना"'),
                            ('split', lambda w: ' AND '.join('"' + p + '"' for p in re.findall(r'\w+', w)))]:
            with self.subTest(name), self.assertRaisesRegex(ValueError, '^' + name + ': '):
                library.search_self_test(matchers={name: build})

    def test_each_word_is_searched_with_the_apps_search_and_finds_its_own_page(self):
        with mock.patch.object(library, 'search', wraps=library.search) as search:
            self.assertEqual(library.search_self_test(), self.EXPECTED)
        self.assertEqual([c.args[0] for c in search.call_args_list], [w for _, w in library.SELF_TEST_PAGES])
        self.assertTrue(all(c.kwargs['db'] != library.DB for c in search.call_args_list))

    def test_it_fails_on_an_sqlite_that_cuts_words_the_old_way(self):
        with self.assertRaisesRegex(ValueError, 'combining marks'):
            library.search_self_test(OLD_TABLE)

    def test_each_word_must_find_only_its_own_page(self):
        """Either word finding the other's page too, or finding nothing, fails the test: the first word and the second."""
        for word, wrong in [(w, rows) for _, w in library.SELF_TEST_PAGES for rows in ([], [{'doc_id': 'water'}, {'doc_id': 'drink'}])]:
            real = library.search
            with self.subTest(word=word, wrong=wrong), \
                    mock.patch.object(library, 'search', side_effect=lambda q, db=None: wrong if q == word else real(q, db=db)):
                with self.assertRaisesRegex(ValueError, word):
                    library.search_self_test()

    def test_it_fails_on_an_sqlite_that_does_not_know_the_tokenizer(self):
        with self.assertRaises(sqlite3.OperationalError):
            library.search_self_test(library.PAGES_TABLE.replace('unicode61', 'no_such_tokenizer'))

    def test_it_fails_on_a_table_that_searches_alike_but_a_rebuild_would_refuse(self):
        """The same tokenizer written another way: both searches pass, and the file check (index_fault) says no."""
        with self.assertRaisesRegex(ValueError, r'build\(\) would not use'):
            library.search_self_test(FTS + ', tokenize = ' + MARKS + ')')

    def test_it_leaves_nothing_in_the_temporary_folder(self):
        """After a pass, a wrong search, and a table SQLite refuses to make."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d, mock.patch('tempfile.tempdir', d):
            library.search_self_test()
            with self.assertRaises(ValueError):
                library.search_self_test(OLD_TABLE)
            with self.assertRaises(sqlite3.OperationalError):
                library.search_self_test(library.PAGES_TABLE.replace('unicode61', 'no_such_tokenizer'))
            self.assertEqual(os.listdir(d), [])

    def run_entry_point(self, extra_env=None, python=None, stdout=subprocess.PIPE, args=()):
        """The real app/main.py --self-test in its own process, as a package starts it, from a sandbox of its own: a home
        folder with settings that name a library, LASTBOOK_DATA naming that library, whose tools/ holds code that would leave a
        mark if anything ran it, and the temporary folder. Returns (process, report or None, sandbox changes, program
        folder changes)."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            d = Path(d)
            home, tmp, data = d / 'home', d / 'tmp', d / 'LastbookData'
            for f in (home / 'roaming' / 'Lastbook', home / 'local' / 'Lastbook', tmp, data / 'library-data' / 'tools'):
                f.mkdir(parents=True)
            (data / 'library-data' / 'catalog.json').write_text('[]', encoding='utf-8')
            (data / 'library-data' / 'search.sqlite').write_bytes(b'not an index: a self-test that opened it would fail')
            (data / 'library-data' / 'tools' / 'remote_storage.py').write_text(
                "from pathlib import Path\n(Path(__file__).parent / 'RAN').write_text('library code ran')\n", encoding='utf-8')
            (home / 'roaming' / 'Lastbook' / 'settings.json').write_text(json.dumps({'library': str(data)}), encoding='utf-8')
            env = dict(os.environ, HOME=str(home), USERPROFILE=str(home), APPDATA=str(home / 'roaming'), LOCALAPPDATA=str(home / 'local'),
                       XDG_CONFIG_HOME=str(home / 'roaming'), XDG_DATA_HOME=str(home / 'local'), XDG_CACHE_HOME=str(home / 'cache'),
                       TMP=str(tmp), TEMP=str(tmp), TMPDIR=str(tmp), LASTBOOK_DATA=str(data), **(extra_env or {}))
            env.pop('LASTBOOK_LIBRARY', None)
            program = {p: p.stat().st_mtime_ns for top in ('app', 'engine') for p in (ROOT / top).rglob('*')}
            before = snapshot(d)
            r = subprocess.run([python or sys.executable, '-B', str(ROOT / 'app' / 'main.py'), '--self-test', *args], env=env, cwd=d,
                               stdin=subprocess.DEVNULL, stdout=stdout, stderr=subprocess.PIPE, timeout=120)
            after = snapshot(d)
            changed = {k for k in before.keys() | after.keys() if before.get(k) != after.get(k)}
            moved = {p for p in program if not p.exists() or p.stat().st_mtime_ns != program[p]}
            moved |= {p for top in ('app', 'engine') for p in (ROOT / top).rglob('*') if p not in program}
        out = (r.stdout or b'').decode('utf-8').strip().splitlines()
        return r, json.loads(out[-1]) if out else None, changed, moved

    def test_the_entry_point_runs_it_and_touches_nothing(self):
        r, report, changed, moved = self.run_entry_point()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(report['ok'])
        self.assertEqual(report['search'], self.FROM_MAIN)       # the search box's way into the index too
        self.assertEqual(changed, set())
        self.assertEqual(moved, set())

    def test_other_arguments_do_not_stop_it(self):
        """Something argparse would refuse (a Mac's -psn_..., a typo) must not exit 2 with nothing said."""
        r, report, changed, moved = self.run_entry_point(args=('-psn_0_12345', '--no-such-flag'))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(report['ok'])
        self.assertEqual(changed, set())
        self.assertEqual(moved, set())

    def test_a_failure_exits_1_with_the_reason_from_the_real_process(self):
        """An SQLite module that will not load, which a package can lack: still one line of JSON, and exit 1, not a
        dialog."""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as fake:
            (Path(fake) / 'sqlite3').mkdir()
            (Path(fake) / 'sqlite3' / '__init__.py').write_text("raise ImportError('no SQLite here')\n", encoding='utf-8')
            r, report, changed, moved = self.run_entry_point({'PYTHONPATH': fake})
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertFalse(report['ok'])
        self.assertEqual(report['error'], 'ImportError: no SQLite here')
        self.assertEqual(changed, set())

    @unittest.skipUnless(sys.platform == 'win32' and (Path(sys.executable).parent / 'pythonw.exe').is_file(), 'Windows, pythonw.exe')
    def test_with_no_console_it_writes_to_the_redirected_output(self):
        """pythonw, like the packaged Windows app, has no sys.stdout: the result goes to the handle it was given."""
        r, report, changed, moved = self.run_entry_point(python=str(Path(sys.executable).parent / 'pythonw.exe'))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(report['ok'])

    def test_output_that_cannot_be_written_never_raises(self):
        main = load_file('main_under_test', ROOT / 'app' / 'main.py')
        for error in (OSError('closed pipe'), ValueError('I/O operation on closed file'), UnicodeEncodeError('cp1252', 'x', 0, 1, 'no')):
            stream = mock.Mock(write=mock.Mock(side_effect=error))
            with self.subTest(error=type(error).__name__), mock.patch.object(sys, 'stdout', stream):
                self.assertFalse(main.say('{}'))

    def test_the_home_folder_is_shown_as_a_tilde(self):
        main = load_file('main_under_test', ROOT / 'app' / 'main.py')
        home = str(Path.home())
        self.assertEqual(main.shareable(f'PermissionError: {home}{os.sep}tmp{os.sep}x'), f'PermissionError: ~{os.sep}tmp{os.sep}x')
        self.assertEqual(main.shareable(home + 'b' + os.sep + 'x'), home + 'b' + os.sep + 'x')   # another user's folder
        self.assertEqual(main.shareable('x' + tempfile.gettempdir()), 'x' + tempfile.gettempdir())   # not the end of a longer one
        tmp = tempfile.gettempdir()
        error = str(PermissionError(13, 'Permission denied', os.path.join(tmp, 'lastbook-self-test-1', 'search.sqlite')))
        self.assertNotIn(tmp.replace('\\', '\\\\'), main.shareable(error))           # as an OSError shows a path: a repr
        self.assertIn('<tmp>', main.shareable(error))
        if sys.platform == 'win32':
            self.assertEqual(main.shareable(home.upper() + '\\x'), '~\\x')          # Windows paths are any case
        with mock.patch.dict(os.environ), mock.patch.object(library, 'search_self_test', side_effect=PermissionError(f'{home}{os.sep}t')), \
                mock.patch.object(main, 'say', return_value=True) as say:
            engine_swapped(library, main.self_test)
        self.assertNotIn(home + os.sep, say.call_args.args[0].replace('\\\\', '\\'))

    @unittest.skipUnless(sys.platform == 'win32', 'Windows')
    def test_with_no_python_stream_it_writes_one_line_to_the_handle_it_was_given(self):
        """The packaged Windows app's case: sys.stdout is None, the output is a pipe. One line, ended once (\\r\\n)."""
        script = ('import importlib.util, sys; sys.stdout = None\n'
                  f'spec = importlib.util.spec_from_file_location("m", {str(ROOT / "app" / "main.py")!r})\n'
                  'm = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n'
                  'sys.exit(0 if m.say("{\\"ok\\": true}") else 3)\n')
        r = subprocess.run([sys.executable, '-B', '-c', script], capture_output=True, timeout=60)
        self.assertEqual((r.returncode, r.stdout), (0, b'{"ok": true}\r\n'), r.stderr)

    @unittest.skipUnless(sys.platform == 'win32', 'Windows')
    def test_it_names_the_sqlite_dll_this_process_loaded(self):
        main = load_file('main_under_test', ROOT / 'app' / 'main.py')
        self.assertTrue(main.sqlite_library().lower().endswith('sqlite3.dll'))

    def test_a_packaged_app_fails_on_an_sqlite_from_outside_it(self):
        main = load_file('main_under_test', ROOT / 'app' / 'main.py')
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as app, mock.patch.dict(os.environ), \
                mock.patch.object(main, 'FROZEN', True), mock.patch.object(sys, '_MEIPASS', app, create=True), \
                mock.patch.object(main, 'sqlite_library', return_value=str(Path(app).parent / 'elsewhere' / 'sqlite3.dll')), \
                mock.patch.object(main, 'say', return_value=True) as say:
            self.assertEqual(engine_swapped(library, main.self_test), 1)
        self.assertIn('is not its own', json.loads(say.call_args.args[0])['error'])

    def test_unwritable_output_is_a_failure(self):
        main = load_file('main_under_test', ROOT / 'app' / 'main.py')
        with mock.patch.dict(os.environ), mock.patch.object(main, 'say', return_value=False):
            self.assertEqual(engine_swapped(library, main.self_test), 1)

    def test_a_failure_is_reported_and_nothing_else_runs(self):
        main = load_file('main_under_test', ROOT / 'app' / 'main.py')
        stand_in = types.ModuleType('engine.library')
        stand_in.search_self_test = mock.Mock(side_effect=ValueError('nothing found'))
        out = io.StringIO()
        with mock.patch.dict(os.environ), mock.patch.object(sys, 'argv', ['main.py', '--self-test']), contextlib.redirect_stdout(out), \
                mock.patch.object(main, 'app_folders', side_effect=AssertionError('main() went on past the self-test')):
            code = engine_swapped(stand_in, main.main)
        self.assertEqual(code, 1)
        report = json.loads(out.getvalue())
        self.assertFalse(report['ok'])
        self.assertEqual(report['error'], 'ValueError: nothing found')

    def test_the_package_scans_pass_the_shipped_files_changed_here(self):
        """Each build ends with its package scan, which refuses a person's folder path and the remote_storage name outside the
        library's own loader, comments included. The first Linux build of this change failed on an example path in a comment."""
        import ast
        patterns = []   # read from each scanner's source: importing them needs the build tools (pefile on Windows)
        for path in ('linux/scan_package_linux.py', 'scan_app_package.py', 'scan_package_macos.py'):
            tree = ast.parse((ROOT / 'packaging' / path).read_text(encoding='utf-8'))
            found = [n.value.args[0] for n in tree.body if isinstance(n, ast.Assign) and getattr(n.targets[0], 'id', '') in ('USER_PATH', 'USER_PATHS')]
            self.assertEqual(len(found), 1, path)
            patterns.append(re.compile(ast.literal_eval(found[0])))
        for path in ('app/main.py', 'engine/library.py'):
            data = (ROOT / path).read_bytes()
            for pattern in patterns:
                self.assertIsNone(pattern.search(data), f'{path}: {pattern.search(data)}')
            if path != 'engine/library.py':
                self.assertNotIn(b'remote_storage', data, path)

    def test_the_packages_start_main_py_and_the_builds_run_it(self):
        """The self-test is worth only as much as the path that reaches it: if a package stops starting app/main.py, the
        flag must move with it (the launcher's check sat in a file no current package starts). Each build runs it on a live
        line, under set -euo pipefail, with nothing after it that would hide a failure."""
        def live(path):
            return '\n'.join(line for line in (ROOT / path).read_text(encoding='utf-8').splitlines() if not line.lstrip().startswith('#'))
        for path, entry in [('packaging/lastbook_macos.spec', r"APP\s*=\s*ROOT\s*/\s*'app'[\s\S]*Analysis\(\s*\[\s*str\(\s*APP\s*/\s*'main\.py'"),
                            ('packaging/linux/lastbook.py', r"run_path\(\s*os\.path\.join\(\s*ROOT\s*,\s*'app'\s*,\s*'main\.py'"),
                            ('packaging/build_app_windows.sh', r'\\\\app\\\\main\.py"\s*$')]:
            self.assertRegex(live(path), re.compile(entry, re.M), f'{path} no longer starts app/main.py')
        for path, app in [('packaging/build_app_macos.sh', '"$BUNDLE/Contents/MacOS/Lastbook"'),
                          ('packaging/build_app_windows.sh', '"$(cygpath -u "$DIST")/Lastbook.exe"'),
                          ('packaging/build_setup_windows.sh', '"$(cygpath -u "$DIST")/Lastbook.exe"'),   # the folder the installer packs
                          ('packaging/linux/build_app_linux.sh', '/usr/bin/python3 -I -B "$OPT/lastbook.py"')]:
            text = live(path)
            self.assertRegex(text, re.compile(r'^set -euo pipefail$', re.M), path)
            self.assertRegex(text, re.compile('^' + re.escape(app) + r' --self-test \| tee [^|&;]*$', re.M),
                             f'{path} does not run the built app\'s self-test so that it can fail the build')


if __name__ == '__main__':
    unittest.main()
