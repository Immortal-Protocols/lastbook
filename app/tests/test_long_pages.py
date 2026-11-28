#!/usr/bin/env python3
"""Long saved web pages are searched in sections (engine/sections.py), against a small made-up library.

  python -B -m unittest app.tests.test_long_pages [-v]

A whole book saved as one web page holds nearly every word, so it matched almost any question. The library here has one
such book (about 70,000 characters of machine-shop sentences, with "grease", "fire" and "pan" far apart and one passage
about a tourniquet), a short kitchen-fire page and a PDF page. The engine is run in its own process with LASTBOOK_DATA
pointing at it (paths are read when it is imported), and that process reports what it found as JSON. No model, no
server, no port. Never packaged."""
import json, os, random, sqlite3, subprocess, sys, tempfile, unittest
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
BOOK, KITCHEN, PDF = 'book-machine-shop', 'kitchen-fires', 'water-pdf'
TQ = 'In the shop, a tourniquet is tied above the wound on the limb when bleeding from the limb will not stop.'
KITCHEN_TEXT = ('Grease fire in a pan: turn off the heat and slide a lid over the pan. Never put water on a grease fire. '
                'Leave the lid on the pan until it is cool.')


def book_text():
    rnd = random.Random(7)
    nouns = 'lathe tool spindle chuck carriage gear shaft bearing bolt file drill bit vise cutter collet bench gauge'.split()
    verbs = 'set turn hold cut clamp measure check oil grind true'.split()
    out, n = [], 0
    while n < 70000:
        s = f'The {rnd.choice(nouns)} must be {rnd.choice(verbs)} with care before the {rnd.choice(nouns)} is used on the work, and the {rnd.choice(nouns)} should be kept clean.'
        out.append(s)
        n += len(s) + 1
    for at, extra in ((40, 'Wipe the grease from the ways each evening.'), (300, 'Keep a bucket of sand in case of fire.'),
                      (560, 'Chips fall into the drip pan under the bed.'), (230, TQ)):
        out.insert(at, extra)
    return '\n'.join(out)


def make_library(data):
    lib = data / 'library-data'
    (lib / 'pages').mkdir(parents=True)
    (lib / 'text').mkdir()
    cat = [{'id': BOOK, 'kind': 'html', 'title': 'Modern Shop Practice', 'collection': 'Books', 'category': 'tools', 'path': 'pages/book.html', 'publisher': 'Gutenberg'},
           {'id': KITCHEN, 'kind': 'html', 'title': 'Kitchen fires', 'collection': 'Safety', 'category': 'fire', 'path': 'pages/kitchen.html', 'publisher': 'Fire service'},
           {'id': PDF, 'kind': 'pdf', 'pages': 61, 'title': 'Safe water', 'collection': 'Water', 'category': 'water', 'path': 'documents/w.pdf', 'publisher': 'Health'}]
    (lib / 'catalog.json').write_text(json.dumps(cat), encoding='utf-8')
    (lib / 'pages' / 'book.html').write_text('<p>' + book_text().replace('\n', '</p><p>') + '</p>', encoding='utf-8')
    (lib / 'pages' / 'kitchen.html').write_text('<p>' + KITCHEN_TEXT + '</p>', encoding='utf-8')
    (lib / 'text' / f'{BOOK}.txt').write_text(book_text(), encoding='utf-8')   # the reader's whole page, without sections
    con = sqlite3.connect(lib / 'search.sqlite')
    con.execute('CREATE VIRTUAL TABLE pages USING fts5(doc_id UNINDEXED,title,collection,category,path UNINDEXED,page UNINDEXED,body,tokenize="unicode61")')
    for r, body in ((cat[0], book_text()), (cat[1], KITCHEN_TEXT), (cat[2], 'Bring water to a rolling boil for one minute.')):
        con.execute('INSERT INTO pages VALUES (?,?,?,?,?,?,?)', (r['id'], r['title'], r['collection'], r['category'], r['path'], 1, body))
    for n in range(2, 61):  # more pages, so word weights (bm25) are like a real library's: rare words count most
        con.execute('INSERT INTO pages VALUES (?,?,?,?,?,?,?)', (PDF, 'Safe water', 'Water', 'water', 'documents/w.pdf', n,
                                                                  f'Water page {n}: keep the water container covered and clean.'))
    con.commit()
    con.close()


def probe(data):
    """Run in the child process: the engine with LASTBOOK_DATA=data. Prints one JSON object."""
    os.environ['LASTBOOK_DATA'] = str(data)
    sys.path.insert(0, str(ROOT))
    import server, assistant, retrieval
    from engine import sections
    assistant.S = server          # keyword side only: no meaning-based index in this library
    out = {}
    sections.ensure(server.library.DB, server.kind_of)   # the startup build, done (searches never wait for it)
    main = sqlite3.connect(server.library.DB)
    out['plain_fire'] = [d for (d,) in main.execute("SELECT doc_id FROM pages WHERE pages MATCH 'grease AND fire AND pan'")]
    main.close()
    out['find_fire'] = [r['id'] for r in server.find('grease fire pan')['results']]
    out['fts_fire'] = [list(r[:2]) for r in assistant._fts('grease fire pan')]
    out['find_tq'] = [(r['id'], [h['page'] for h in r['hits']]) for r in server.find('tourniquet limb')['results']]
    out['fts_tq'] = [list(r[:2]) for r in assistant._fts('tourniquet limb')]
    out['hybrid_tq'] = [(h['doc_id'], h['page']) for h in assistant.hybrid('tourniquet limb')]
    out['hybrid_fire'] = [(h['doc_id'], h['page']) for h in assistant.hybrid('grease fire pan')]
    out['status'] = {k: str(v) for k, v in sections.status().items()}
    out['nsections'] = sections.sectioned(BOOK)
    out['kitchen_sectioned'] = sections.sectioned(KITCHEN)
    texts = server.doc_texts(server.catalog()['by_id'][BOOK])
    out['tq_section'] = next(i for i, t in enumerate(texts, 1) if 'tourniquet' in t)
    out['texts_rejoin'] = ' '.join(texts) == retrieval.norm_ws(book_text())
    out['files'] = sorted(p.name for p in (data / 'derived' / 'index').glob('sections-*.sqlite'))

    # meaning-based index: passages stored with the whole page's number, relabelled by section without re-embedding
    ix = retrieval.Index(server.catalog, server.trust, server.library.DB)
    db = ix._db()
    spans = retrieval.chunk_spans(retrieval.norm_ws(book_text()))
    rows = [(i + 1, BOOK, 1, None, c, 1) for i, (_, c) in enumerate(spans)]
    rows.append((len(rows) + 1, KITCHEN, 1, None, KITCHEN_TEXT, 1))
    rows.append((len(rows) + 1, BOOK, 1, None, 'a passage that is in no chunk of the book at all, kept as it was', 1))
    db.executemany('INSERT INTO chunk(id,doc_id,page,t,text,active) VALUES (?,?,?,?,?,?)', rows)
    db.executemany('INSERT INTO docstate VALUES (?,?,?,?)', [(BOOK, 'sig-1', len(spans) + 1, 0), (KITCHEN, 'sig-k', 1, 0)])
    first = ix.relabel_sections(db)
    again = ix.relabel_sections(db)
    path = sections.ensure(server.library.DB, server.kind_of)
    starts = sections.starts(path, BOOK)
    want = [sections.section_of(starts, s) for s, _ in spans]
    got = [p for (p,) in db.execute('SELECT page FROM chunk WHERE doc_id=? ORDER BY id', (BOOK,))]
    out['relabel'] = {'first': first, 'again': again, 'pages_right': got[:-1] == want, 'unmatched_kept': got[-1],
                      'kitchen': db.execute('SELECT page FROM chunk WHERE doc_id=?', (KITCHEN,)).fetchone()[0],
                      'max_page': max(got), 'tq_page': got[next(i for i, (_, c) in enumerate(spans) if 'tourniquet' in c)]}
    db.close()
    parts = ix._texts(BOOK, ('pages', server.catalog()['by_id'][BOOK]))
    out['texts_pages'] = sorted({p for p, _, _ in parts})
    out['texts_tq_page'] = next(p for p, _, c in parts if 'tourniquet' in c)
    out['texts_kitchen'] = sorted({p for p, _, _ in ix._texts(KITCHEN, ('pages', server.catalog()['by_id'][KITCHEN]))})

    # the library index changes: a new sections file on the next search, the old one removed
    old = sections.ensure(server.library.DB, server.kind_of)
    main = sqlite3.connect(server.library.DB)
    main.execute('INSERT INTO pages VALUES (?,?,?,?,?,?,?)', (PDF, 'Safe water', 'Water', 'water', 'documents/w.pdf', 61, 'Store boiled water covered.'))
    main.commit()
    main.close()
    os.utime(server.library.DB, ns=(os.stat(server.library.DB).st_atime_ns, os.stat(server.library.DB).st_mtime_ns + 10**9))
    server.find('store boiled water')
    new = sections.ensure(server.library.DB, server.kind_of)
    out['rebuild'] = {'changed': old != new, 'old_gone': not old.exists(), 'new_there': new.exists(),
                      'files': sorted(p.name for p in (data / 'derived' / 'index').glob('sections-*.sqlite')),
                      'same_again': sections.ensure(server.library.DB, server.kind_of) == new}

    # the sections file cannot be built (a read-only data folder, say): whole pages, as before
    def refuse(*a, **k):
        raise OSError('read-only')
    sections.build = refuse
    for f in (data / 'derived' / 'index').glob('sections-*.sqlite'):
        f.unlink()
    os.utime(server.library.DB, ns=(os.stat(server.library.DB).st_atime_ns, os.stat(server.library.DB).st_mtime_ns + 10**9))
    found = server.find('tourniquet  limb')['results']   # another spelling: find() keeps earlier answers
    out['readonly'] = {'ensure': sections.ensure(server.library.DB, server.kind_of), 'error': sections.status()['error'],
                       'find': [(r['id'], [h['page'] for h in r['hits']]) for r in found],
                       'hybrid': [(h['doc_id'], h['page']) for h in assistant.hybrid('tourniquet limb')],
                       'texts': len(server.doc_texts(server.catalog()['by_id'][BOOK])),
                       'files': sorted(p.name for p in (data / 'derived' / 'index').glob('sections-*'))}
    print('PROBE ' + json.dumps(out))


def engine(data):
    os.environ['LASTBOOK_DATA'] = str(data)
    sys.path.insert(0, str(ROOT))
    import server, assistant
    from engine import sections
    assistant.S = server
    return server, assistant, sections


def answers(server, assistant, q='grease fire pan'):
    """What Library search, the Chat's keyword retrieval and its hybrid search give for q, and how the book reads."""
    book = server.catalog()['by_id'][BOOK]
    return {'find': [(r['id'], [h['page'] for h in r['hits']]) for r in server.find(q)['results']],
            'fts': [list(r[:2]) for r in assistant._fts(q)],
            'hybrid': [[h['doc_id'], h['page']] for h in assistant.hybrid(q)],
            'tq_find': [(r['id'], [h['page'] for h in r['hits']]) for r in server.find('tourniquet limb')['results']],
            'book_pages': len(server.doc_texts(book))}


def probe_delayed(data):
    """The sections build is held back: searches answer at once from whole pages, then read sections when it is done."""
    import threading, time
    server, assistant, sections = engine(data)
    go, real = threading.Event(), sections.build

    def slow(*a, **k):
        go.wait(60)
        return real(*a, **k)
    sections.build = slow
    sections.ready(server.library.DB, server.kind_of)   # as server.init does
    t0 = time.time()
    out = {'during': answers(server, assistant)}
    out['during']['seconds'] = round(time.time() - t0, 2)
    out['during']['ready'] = sections.ready(server.library.DB, server.kind_of) is not None
    go.set()
    sections._bg['thread'].join(60)
    out['after'] = answers(server, assistant)
    out['after']['ready'] = sections.ready(server.library.DB, server.kind_of) is not None
    out['tq_section'] = next(i for i, t in enumerate(server.doc_texts(server.catalog()['by_id'][BOOK]), 1) if 'tourniquet' in t)
    print('PROBE ' + json.dumps(out))


def damage(path, how):
    """Leave the sections file's metadata (long, section) readable and make its search table unusable."""
    con = sqlite3.connect(path)
    if how == 'dropped':
        con.execute('DROP TABLE pages')
    else:   # 'garbled': the full-text index's own blocks overwritten
        con.execute("UPDATE pages_data SET block = randomblob(length(block)) WHERE id > 10")
    con.commit()
    con.close()


def probe_damaged(data, how):
    """Run 1 builds the sections file; it is damaged; run 2 (this process, reopening it) must still find the pages."""
    server, assistant, sections = engine(data)
    out = {}
    path = sections.ensure(server.library.DB, server.kind_of)
    out['good'] = answers(server, assistant)
    damage(path, how)                                   # in the middle of use: searches fall back at once
    server.find.cache_clear()
    out['in_use'] = answers(server, assistant)
    out['in_use']['error'] = sections.status()['error']
    print('PROBE ' + json.dumps(out))


def probe_reopened(data, how, rebuild):
    """A later start with a damaged sections file already there: rebuilt if it can be, else whole pages."""
    server, assistant, sections = engine(data)
    path = next((data / 'derived' / 'index').glob('sections-*.sqlite'))
    damage(path, how)
    if rebuild == 'refused':
        def refuse(*a, **k):
            raise OSError('read-only')
        sections.build = refuse
    sections.ensure(server.library.DB, server.kind_of)
    out = answers(server, assistant)
    out['ready'] = sections.ready(server.library.DB, server.kind_of) is not None
    out['error'] = sections.status()['error']
    print('PROBE ' + json.dumps(out))


def probe_build(data):
    server, assistant, sections = engine(data)
    ok = sections.ensure(server.library.DB, server.kind_of) is not None
    sec = next(i for i, t in enumerate(server.doc_texts(server.catalog()['by_id'][BOOK]), 1) if 'tourniquet' in t)
    print('PROBE ' + json.dumps({'ready': ok, 'tq_section': sec}))


def run_probe(dirname, *args, data=None):
    if data is None:
        data = Path(dirname) / 'Lastbook Data #1'
        make_library(data)
    e = {k: v for k, v in os.environ.items() if k not in ('LASTBOOK_DATA', 'LASTBOOK_LOCAL_AI')}
    r = subprocess.run([sys.executable, '-B', __file__, '--probe', *args, str(data)], capture_output=True, text=True,
                       encoding='utf-8', errors='replace', env=e, cwd=dirname, timeout=300)
    line = next((l for l in r.stdout.splitlines() if l.startswith('PROBE ')), None)
    if r.returncode or not line:
        raise AssertionError(f'probe failed ({r.returncode}):\n{r.stdout[-3000:]}\n{r.stderr[-3000:]}')
    return json.loads(line[6:])


class LongPages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls.o = run_probe(cls.dir.name, 'main')

    @classmethod
    def tearDownClass(cls):
        cls.dir.cleanup()

    def test_sections_built(self):
        self.assertGreaterEqual(self.o['nsections'], 12)
        self.assertEqual(self.o['kitchen_sectioned'], 0)               # short pages stay whole
        self.assertTrue(self.o['texts_rejoin'])                        # nothing lost between sections
        self.assertEqual(len(self.o['files']), 1)

    def test_scattered_words_no_longer_find_the_book(self):
        self.assertIn(BOOK, self.o['plain_fire'])                       # the problem: the whole page has all three words
        self.assertEqual(self.o['find_fire'][0], KITCHEN)
        self.assertEqual(self.o['fts_fire'][0][0], KITCHEN)
        self.assertEqual(self.o['hybrid_fire'][0][0], KITCHEN)
        self.assertNotIn(BOOK, self.o['find_fire'][:1])

    def test_one_section_is_found_as_its_section(self):
        sec = self.o['tq_section']
        self.assertGreater(sec, 1)
        self.assertEqual(self.o['find_tq'][0], [BOOK, [sec]])           # Library search: the hit names the section
        self.assertEqual(self.o['fts_tq'][0], [BOOK, sec])              # the assistant's keyword side
        self.assertEqual(self.o['hybrid_tq'][0], [BOOK, sec])           # hybrid keeps the section for html

    def test_semantic_relabel(self):
        rl = self.o['relabel']
        self.assertTrue(rl['pages_right'])
        self.assertIn(rl['tq_page'], (self.o['tq_section'] - 1, self.o['tq_section']))   # labelled by where the passage starts
        self.assertEqual(rl['unmatched_kept'], 1)
        self.assertEqual(rl['kitchen'], 1)
        self.assertGreater(rl['max_page'], 10)
        self.assertEqual(rl['first']['documents'], 1)
        self.assertEqual(rl['first']['unmatched'], 1)
        self.assertEqual(rl['again']['documents'], 0)                   # once per document and signature

    def test_new_passages_are_chunked_by_section(self):
        self.assertEqual(self.o['texts_pages'], list(range(1, self.o['nsections'] + 1)))
        self.assertEqual(self.o['texts_tq_page'], self.o['tq_section'])
        self.assertEqual(self.o['texts_kitchen'], [1])

    def test_falls_back_to_whole_pages_when_it_cannot_be_built(self):
        ro = self.o['readonly']
        self.assertIsNone(ro['ensure'])
        self.assertIn('read-only', ro['error'])
        self.assertEqual(ro['find'][0][0], BOOK)                        # the whole page again, cited without a section
        self.assertEqual(set(ro['find'][0][1]), {None})
        self.assertEqual(ro['hybrid'][0], [BOOK, None])
        self.assertEqual(ro['texts'], 1)                                # the reader shows the one whole page
        self.assertEqual(ro['files'], [])                               # nothing half-written left behind

    def test_rebuilt_when_the_library_index_changes(self):
        rb = self.o['rebuild']
        self.assertTrue(rb['changed'])
        self.assertTrue(rb['old_gone'])
        self.assertTrue(rb['new_there'])
        self.assertEqual(len(rb['files']), 1)
        self.assertTrue(rb['same_again'])


class NeverInTheWay(unittest.TestCase):
    """The sections file is optional: while it is built, and when it cannot be searched, Library search and the Chat
    answer from the whole pages of the library index (#403 review)."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.dir.cleanup)

    def whole_pages(self, a):
        self.assertEqual(a['find'][0][0], KITCHEN)              # the kitchen-fires page is still found
        self.assertIn(BOOK, [d for d, _ in a['find']])          # and the book, whole, as before sections
        self.assertEqual(set(dict(a['find'])[BOOK]), {None})
        self.assertEqual(a['fts'][0][0], KITCHEN)               # the Chat's keyword retrieval too
        self.assertEqual(a['hybrid'][0][0], KITCHEN)
        self.assertEqual(a['tq_find'][0][0], BOOK)               # the tourniquet passage: the whole book, no section
        self.assertEqual(set(a['tq_find'][0][1]), {None})
        self.assertEqual(a['book_pages'], 1)                    # the reader shows the one whole page

    def in_sections(self, a, sec):
        self.assertEqual(a['find'][0][0], KITCHEN)
        self.assertEqual(a['fts'][0][0], KITCHEN)
        self.assertEqual(a['tq_find'][0], [BOOK, [sec]])
        self.assertGreater(a['book_pages'], 10)

    def test_a_search_does_not_wait_for_the_build(self):
        o = run_probe(self.dir.name, 'delayed')
        self.assertLess(o['during']['seconds'], 10)             # the build is held for up to 60 s
        self.assertFalse(o['during']['ready'])
        self.whole_pages(o['during'])
        self.assertTrue(o['after']['ready'])                    # then sections, without a restart
        self.in_sections(o['after'], o['tq_section'])

    def test_a_file_that_breaks_in_use(self):
        for how in ('dropped', 'garbled'):
            with self.subTest(how=how):
                o = run_probe(tempfile.mkdtemp(dir=self.dir.name), 'damaged', how)
                self.assertGreater(o['good']['book_pages'], 10)
                self.whole_pages(o['in_use'])
                self.assertIn('Error', o['in_use']['error'])

    def test_a_damaged_file_found_at_start(self):
        for how in ('dropped', 'garbled'):
            for rebuild in ('allowed', 'refused'):
                with self.subTest(how=how, rebuild=rebuild):
                    d = tempfile.mkdtemp(dir=self.dir.name)
                    data = Path(d) / 'Lastbook Data #1'
                    make_library(data)
                    first = run_probe(d, 'build', data=data)
                    self.assertTrue(first['ready'])
                    o = run_probe(d, 'reopened', how, rebuild, data=data)
                    if rebuild == 'allowed':                    # built again, once
                        self.assertTrue(o['ready'])
                        self.assertIsNone(o['error'])
                        self.in_sections(o, first['tq_section'])
                    else:                                       # cannot be: whole pages
                        self.assertFalse(o['ready'])
                        self.whole_pages(o)


class Cut(unittest.TestCase):
    def test_cut_after_sentences(self):
        sys.path[:0] = [str(ROOT), str(ROOT / 'app' / 'tests')]
        import fixture
        os.environ['LASTBOOK_DATA'] = str(fixture.ensure())   # engine.paths reads it once: the made-up library every test module uses
        from engine import sections
        text = ' '.join(f'Sentence number {i} is here.' for i in range(1500))
        secs = sections.cut(text)
        self.assertTrue(all(t.endswith('.') for _, t in secs))
        self.assertTrue(all(len(t) <= sections.SECTION for _, t in secs))
        self.assertTrue(all(len(t) >= sections.SECTION // 2 - 1 for _, t in secs[:-1]))
        starts = [s for s, _ in secs]
        self.assertEqual([sections.section_of(starts, s) for s in starts], list(range(1, len(secs) + 1)))
        self.assertEqual(sections.section_of(starts, starts[3] + 5), 4)
        self.assertEqual(sections.cut('x' * (sections.SECTION * 3))[0][1], 'x' * sections.SECTION)   # no space at all: a hard cut


if __name__ == '__main__':
    if len(sys.argv) >= 4 and sys.argv[1] == '--probe':
        what, args, data = sys.argv[2], sys.argv[3:-1], Path(sys.argv[-1])
        {'main': probe, 'delayed': probe_delayed, 'damaged': probe_damaged, 'reopened': probe_reopened,
         'build': probe_build}[what](data, *args)
    else:
        unittest.main()
