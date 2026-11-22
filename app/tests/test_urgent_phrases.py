#!/usr/bin/env python3
"""The guides' `urgent` phrases read from Python (engine/urgent_phrases.py), and that they agree with the guide search.

  python -B -m unittest app.tests.test_urgent_phrases [-v]

The guide search (web/words.js, rankTopics) and the chat's urgency check (engine/confidence.urgent) read the same
`urgent` fields of content/topics/*.json. This checks the Python word rule against words.js on the same strings, that every
phrase of every guide is named by both (plain, in capitals and with a curly apostrophe), that sentences which only look
like a phrase are named by neither, and that engine/confidence.urgent uses the phrases (and cuts idioms first). The
JavaScript side needs Node on PATH, as test_topic_search does. No library, no model. Never packaged."""
import json, os, re, shutil, subprocess, sys, tempfile, unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT), str(HERE)]
import fixture  # noqa: E402
os.environ['LASTBOOK_DATA'] = str(fixture.ensure())   # engine.paths reads it once: the made-up library every test module uses

from engine import confidence, urgent_phrases  # noqa: E402

NODE = shutil.which('node')
WORDS = ROOT / 'web' / 'words.js'
TOPICS = [json.loads(p.read_text(encoding='utf-8')) for p in sorted((ROOT / 'content' / 'topics').glob('*.json'))]
QSTOP = re.search(r"const QSTOP = new Set\('([^']*)'\.split", (ROOT / 'web' / 'app.js').read_text(encoding='utf-8')).group(1).split(' ')
PHRASES = [(t['id'], c['id'], p) for t in TOPICS for c in t.get('choices', []) if not c.get('goto') for p in c.get('urgent', [])]

SPLIT = ["Isn't breathing!", 'ISN’T BREATHING', 'he is not  breathing,\tat all', 'water.boil first_aid e.coli', 'niño', 'crème brûlée',
         'Straße ΣΟΦΟΣ', 'ｗａｔｅｒ', 'İstanbul', '112 or 911', 'a', '', '!!!', 'co2 alarm', "won't wake up"]

JS_SPLIT = """
const { readFileSync } = require('node:fs'), vm = require('node:vm');
const ctx = vm.createContext({}); vm.runInContext(readFileSync(process.argv[1], 'utf8'), ctx);
process.stdout.write(JSON.stringify(JSON.parse(readFileSync(process.argv[2], 'utf8')).map(s => ctx.SearchWords.splitWords(s))));
"""


def node(args, script=None):
    cmd = [NODE] + (['-e', script] if script else []) + args
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', timeout=60)
    if r.returncode:
        raise AssertionError(r.stderr[-1500:])
    return json.loads(r.stdout)


def js(data, script=None, mjs=None):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / 'in.json'
        p.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        if mjs:
            return node([str(mjs), str(WORDS), str(p)])
        return node([str(WORDS), str(p)], script)


class Rule(unittest.TestCase):
    def test_words_and_folding(self):
        self.assertEqual(urgent_phrases.split_words("Isn't breathing!"), ['isn', 't', 'breathing'])
        self.assertEqual(urgent_phrases.split_words('ISN’T BREATHING'), ['isn', 't', 'breathing'])
        self.assertEqual(urgent_phrases.split_words('crème brûlée'), ['creme', 'brulee'])
        self.assertEqual(urgent_phrases.split_words('ｗａｔｅｒ'), ['water'])
        self.assertEqual(urgent_phrases.split_words('ΣΟΦΟΣ'), ['σοφοσ'])
        self.assertEqual(urgent_phrases.split_words('!!! ??'), [])
        self.assertEqual(urgent_phrases.split_words(''), [])

    def test_whole_words_in_order(self):
        names = urgent_phrases.names
        w = urgent_phrases.split_words
        self.assertTrue(names(w('he is not breathing at all'), w('not breathing')))
        self.assertFalse(names(w('trouble breathing'), w('not breathing')))
        self.assertFalse(names(w('breathing not'), w('not breathing')))
        self.assertFalse(names(w('nothing breathing'), w('not breathing')))
        self.assertFalse(names(w('not breathing'), w('not breathing fast')))

    @unittest.skipUnless(NODE, 'needs node on PATH')
    def test_the_same_words_as_the_guide_search(self):
        self.assertEqual([urgent_phrases.split_words(s) for s in SPLIT], js(SPLIT, JS_SPLIT))


class Guides(unittest.TestCase):
    def test_the_guides_name_phrases(self):
        self.assertGreater(len(PHRASES), 50)
        self.assertEqual({(t, c) for t, c, _ in PHRASES}, {(t, c) for t, c, _ in urgent_phrases.load()})
        for topic, choice, phrase in PHRASES:
            self.assertEqual(phrase, phrase.strip(), phrase)
            self.assertTrue(urgent_phrases.split_words(phrase), phrase)

    def test_every_phrase_is_named_in_python(self):
        for topic, choice, phrase in PHRASES:
            for text in (phrase, phrase.upper(), phrase.replace("'", '’'), f'my friend says {phrase} right now'):
                with self.subTest(text=text):
                    self.assertIn(f'{topic}/{choice}', urgent_phrases.named(text))

    @unittest.skipUnless(NODE, 'needs node on PATH')
    def test_the_guide_search_picks_the_same_choice(self):
        """A phrase picks its choice for its guide when the search names it; it does not bring a guide in (a guide is found by
        its own words, as before). So: where the guide is among the results, its choice is the one that lists the phrase,
        in the three spellings, and for some phrases the guide is found."""
        texts = [x for _, _, p in PHRASES for x in (p, p.upper(), p.replace("'", '’'))]
        ranked = js({'stop': QSTOP, 'topics': TOPICS, 'questions': texts}, mjs=HERE / 'topic_search_emergency.mjs')
        it = iter(ranked)
        found = 0
        for topic, choice, phrase in PHRASES:
            for text in (phrase, phrase.upper(), phrase.replace("'", '’')):
                got = {g[0]: g[1] for g in next(it)}
                with self.subTest(text=text):
                    if topic in got:
                        found += 1
                        self.assertEqual(got[topic], choice)
        self.assertGreater(found, 3 * 30)

    @unittest.skipUnless(NODE, 'needs node on PATH')
    def test_these_open_their_choice_first(self):
        want = {'not breathing': ('hurt', 'breathing'), 'heavy bleeding': ('hurt', 'bleeding'), 'snake bit my dog': ('hurt', 'snakebite'),
                'heat stroke': ('hurt', 'heatcold'), 'swallowed bleach': ('hurt', 'poison'), 'having a seizure': ('hurt', 'sudden'),
                'throat swelling after a sting': ('hurt', 'allergy'), 'gas leak': ('power', 'gas'),
                'carbon monoxide poisoning from the generator': ('shelter', 'co')}
        ranked = js({'stop': QSTOP, 'topics': TOPICS, 'questions': list(want)}, mjs=HERE / 'topic_search_emergency.mjs')
        for (q, (topic, choice)), got in zip(want.items(), ranked):
            with self.subTest(q=q):
                self.assertEqual(got[0][:2], [topic, choice])
                self.assertIn(f'{topic}/{choice}', urgent_phrases.named(q))

    def test_what_only_looks_like_a_phrase_is_not_one(self):
        """#167 left some words out of `urgent` on purpose: they also mean a wound or a machine."""
        for q in ('trouble breathing', 'not responding to antibiotics', 'the pump is not responding', 'choking on smoke',
                  'allergic reaction choking', 'carbon monoxide detector battery', 'how do i bake bread',
                  'the tent collapsed', 'heat on my tomato plants', 'house fire insurance claim form'):
            self.assertEqual(urgent_phrases.named(q), [], q)
        # main gave the stroke choice the bare phrase "stroke" ("Guides: send "stroke" to the stroke signs"), so that "stroke"
        # alone opens it and not heat stroke. The urgency check reads the same field, so "a stroke of luck" now names it too.
        # It was in the list above before; the guide search needs the bare word, so the test records what happens instead.
        self.assertEqual(urgent_phrases.named('a stroke of luck'), ['hurt/sudden'])

    def test_a_folder_of_guides(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            (folder / 'a.json').write_text(json.dumps({'id': 'a', 'choices': [
                {'id': 'x', 'urgent': ['zebra stampede', 'Café fire']}, {'id': 'y', 'goto': 'b', 'urgent': ['ignored']},
                {'id': 'z'}, {'id': 'w', 'urgent': 'not a list'}]}), encoding='utf-8')
            (folder / 'broken.json').write_text('{', encoding='utf-8')
            (folder / 'b.json').write_text(json.dumps({'id': 'b', 'choices': [{'id': 'q', 'urgent': ['a zebra']}]}), encoding='utf-8')
            self.assertEqual(urgent_phrases.named('a zebra stampede in the cafe fire', folder=folder), ['a/x', 'b/q'])
            self.assertEqual(urgent_phrases.named('ignored', folder=folder), [])
            self.assertEqual(urgent_phrases.named('', None, folder=folder), [])
            self.assertEqual(urgent_phrases.named('x', folder=Path(d) / 'missing'), [])


class Urgent(unittest.TestCase):
    """engine/confidence.urgent uses the guides' phrases."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        (Path(self.folder.name) / 'a.json').write_text(json.dumps({'id': 'a', 'choices': [
            {'id': 'x', 'urgent': ['zebra stampede', 'drowning']}]}), encoding='utf-8')
        p = mock.patch.object(urgent_phrases, 'topics_folder', lambda: Path(self.folder.name))
        p.start()
        self.addCleanup(p.stop)
        self.addCleanup(lambda: urgent_phrases._cache.pop(Path(self.folder.name), None))

    def test_a_phrase_of_a_guide_is_urgent(self):
        self.assertFalse(confidence.URGENT.search('a zebra stampede in the yard'))     # no word of the wide list is in it
        self.assertTrue(confidence.urgent('a zebra stampede in the yard'))
        self.assertFalse(confidence.urgent('a zebra in the yard'))

    def test_as_typed_or_put_right(self):
        self.assertFalse(confidence.urgent('a zebra stampde in the yard'))
        self.assertTrue(confidence.urgent('a zebra stampde in the yard', 'a zebra stampede in the yard'))

    def test_idioms_are_cut_first(self):
        self.assertTrue(confidence.urgent('he is drowning near the pier'))
        self.assertFalse(confidence.urgent('i am drowning in homework'))      # NOT_URGENT: the phrase is cut out first

    def test_the_real_guides(self):
        urgent_phrases._cache.clear()
        with mock.patch.object(urgent_phrases, 'topics_folder', lambda: ROOT / 'content' / 'topics'):
            for q in ('he is bleeding badly', 'his throat is closing after peanuts', 'she has no pulse', 'took too many pills',
                      'i want to die', 'snake bit my dog', 'the gas leak in the kitchen'):
                self.assertTrue(confidence.urgent(q), q)
            for q in ('how do i bake bread', 'how to build a root cellar'):
                self.assertFalse(confidence.urgent(q), q)


if __name__ == '__main__':
    unittest.main()
