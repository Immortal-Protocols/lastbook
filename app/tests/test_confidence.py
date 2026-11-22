#!/usr/bin/env python3
"""How likely a search's first page is right (engine/confidence.py), and what the chat does with it (assistant).

  python -B -m unittest app.tests.test_confidence [-v]

No library and no model: the library's words are given, hybrid() is a stand-in that fills the trace as the real one does,
and chat() runs with a stand-in model round. Checked: the signals and the probability (plain numbers, strong searches
above weak ones), the thresholds and their environment overrides, the switch, the confidence of a question's first search
(question_hits; none from a stand-in without a trace) and what _fts leaves in the trace, and the chat: sure answers as
before, unsure offers buttons, very unsure asks for more words without the model, always with the pages it found as
sources (urgent or not); when the question may be urgent or names a body sign ("he has no puls", "mybbyisntbreathing")
the model answers from the pages, with buttons, instead. Everyday questions (not urgent): buttons only below the much
lower everyday cut, the same buttons drawn smaller (style 'compact'), and the request to say more never above that cut.
The urgent words in everyday wording, and everyday idioms that are not urgent. Never packaged."""
import os, sqlite3, sys, unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT), str(HERE)]
import fixture  # noqa: E402
os.environ['LASTBOOK_DATA'] = str(fixture.ensure())   # engine.paths reads it once: the made-up library every test module uses

from engine import confidence  # noqa: E402

V = {'the': 100000, 'water': 3000, 'purify': 200, 'boil': 900, 'chlorine': 400, 'tomato': 150, 'plants': 2000,
     'cellar': 60, 'root': 800, 'build': 5000, 'zebra': 5}


def hit(doc, title, excerpt, kind='html', found_by=None):
    return {'doc_id': doc, 'page': 1, 't': None, 'kind': kind, 'title': title, 'excerpt': excerpt,
            'found_by': found_by or {'keyword': 1}}


STRONG = ([hit('w1', 'Purify Water', 'To purify water, boil it for one minute.')] +
          [hit(f'd{i}', f'Book {i}', 'water') for i in range(7)],
          {'groups': [['purify', 'purification'], ['water']], 'strict': 60, 'any_word': False, 'bm25': [-14.0, -12.0, -11.0],
           'semantic': False})
WEAK = ([hit('z1', 'Tools and Their Uses', 'a hammer and a saw')],
        {'groups': [['zebra'], ['cellar'], ['tomato']], 'strict': 0, 'any_word': True, 'bm25': [-1.5], 'semantic': False})


SWITCHES = ('LASTBOOK_CONF', 'LASTBOOK_BODY_', 'LASTBOOK_TYPO_', 'LASTBOOK_AI_', 'LASTBOOK_MEANING_RED', 'LASTBOOK_WIKI_URGENT')


def clean_env(test):
    """Every switch and tuning value of this module unset for this test, as on a fresh install. The environment as it was
    (the shell's own values included) comes back afterwards."""
    p = mock.patch.dict(os.environ)
    p.start()
    test.addCleanup(p.stop)
    for k in [k for k in os.environ if k.startswith(SWITCHES)]:
        del os.environ[k]


def own_assistant(test):
    """A copy of assistant of this test's own. Another test module in the same run may have loaded it and swapped parts
    for stand-ins (test_bridge replaces chat); that copy, and every module this one adds, are put back afterwards."""
    before, shared = set(sys.modules), sys.modules.pop('assistant', None)

    def restore():
        for n in set(sys.modules) - before:
            sys.modules.pop(n, None)
        if shared is not None:
            sys.modules['assistant'] = shared
    test.addCleanup(restore)
    import assistant
    return assistant


class Signals(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(confidence, '_words', lambda: (V, max(V.values())))
        p.start()
        self.addCleanup(p.stop)
        clean_env(self)

    def test_signals_are_plain_numbers_and_the_models_use_only_them(self):
        f = confidence.features(*STRONG)
        self.assertTrue(all(isinstance(v, float) for v in f.values()), f)
        self.assertEqual((f['cover1'], f['all1'], f['title1']), (1.0, 1.0, 1.0))
        hy = confidence.features(STRONG[0], dict(STRONG[1], semantic=True, cos=[0.8, 0.75, 0.7], kw_keys=[('w1', 1, None)],
                                                 sem_keys=[['w1', 1, None]]))
        self.assertEqual(hy['overlap'], 1 / 8)                       # keys from JSON (lists) and from hybrid (tuples) alike
        for name, model in confidence.MODELS.items():
            self.assertTrue(all(isinstance(w, float) for w in model.values()), name)
            self.assertLessEqual(set(model) - {'bias'}, set(hy), name)

    def test_a_strong_search_is_surer_than_a_weak_one(self):
        strong, weak = confidence.estimate(*STRONG), confidence.estimate(*WEAK)
        self.assertEqual((strong['mode'], weak['mode']), ('keyword', 'keyword'))
        self.assertGreater(strong['p'], confidence.BUTTONS)
        self.assertLess(weak['p'], confidence.UNSURE)
        self.assertEqual((strong['level'], weak['level']), ('sure', 'unsure'))
        self.assertEqual(confidence.estimate([], {'groups': [], 'semantic': False})['level'], 'unsure')   # nothing found

    def test_hybrid_uses_its_own_coefficients(self):
        tr = dict(STRONG[1], semantic=True, cos=[0.86] + [0.8] * 7, kw_keys=[('w1', 1, None)], sem_keys=[('w1', 1, None)])
        est = confidence.estimate(STRONG[0], tr)
        self.assertEqual(est['mode'], 'hybrid')
        self.assertAlmostEqual(est['p'], confidence.probability(confidence.features(STRONG[0], tr), confidence.MODELS['hybrid']), 3)

    def test_thresholds_from_the_environment(self):
        self.assertEqual(confidence.thresholds(), (0.6, 0.25))
        self.assertEqual((confidence.BUTTONS, confidence.UNSURE), (0.6, 0.25))
        os.environ.update(LASTBOOK_CONF_BUTTONS='0.75', LASTBOOK_CONF_UNSURE='0.1')
        self.assertEqual(confidence.thresholds(), (0.75, 0.1))
        os.environ.update(LASTBOOK_CONF_BUTTONS='lots', LASTBOOK_CONF_UNSURE='7')    # not a share: the default
        self.assertEqual(confidence.thresholds(), (0.6, 0.25))
        os.environ['LASTBOOK_CONF_UNSURE'] = '0'
        self.assertEqual(confidence.estimate(*WEAK)['level'], 'buttons')      # 0: never "please say more"

    def test_between_the_old_and_new_buttons_cut_is_sure(self):
        with mock.patch.object(confidence, 'probability', lambda f, m: 0.7):
            self.assertEqual(confidence.estimate(*STRONG)['level'], 'sure')     # 0.60 by default (was 0.75)
            os.environ['LASTBOOK_CONF_BUTTONS'] = '0.75'
            self.assertEqual(confidence.estimate(*STRONG)['level'], 'buttons')
        with mock.patch.object(confidence, 'probability', lambda f, m: 0.59):
            os.environ.pop('LASTBOOK_CONF_BUTTONS')
            self.assertEqual(confidence.estimate(*STRONG)['level'], 'buttons')

    def test_everyday_cut_and_its_override(self):
        self.assertEqual((confidence.EVERYDAY_BUTTONS, confidence.everyday_cut()), (0.3, 0.3))
        self.assertLess(confidence.EVERYDAY_BUTTONS, confidence.BUTTONS)
        self.assertEqual([confidence.everyday_level(p) for p in (0.1, 0.24, 0.25, 0.29, 0.3, 0.5, 0.59, 0.9)],
                         ['unsure', 'unsure', 'buttons', 'buttons', 'sure', 'sure', 'sure', 'sure'])
        os.environ['LASTBOOK_CONF_BUTTONS_EVERYDAY'] = '0.15'
        self.assertEqual(confidence.everyday_cut(), 0.15)
        # below the unsure cut: the request to say more only where there are buttons too, never above them
        self.assertEqual([confidence.everyday_level(p) for p in (0.1, 0.15, 0.2)], ['unsure', 'sure', 'sure'])
        os.environ['LASTBOOK_CONF_BUTTONS_EVERYDAY'] = '0.6'
        self.assertEqual([confidence.everyday_level(p) for p in (0.2, 0.5)], ['unsure', 'buttons'])
        os.environ['LASTBOOK_CONF_BUTTONS_EVERYDAY'] = 'many'
        self.assertEqual(confidence.everyday_cut(), 0.3)                       # not a share: the default
        os.environ['LASTBOOK_CONF_BUTTONS_EVERYDAY'] = '0'
        self.assertEqual(confidence.everyday_level(0.01), 'sure')              # 0: never buttons on an everyday question
        self.assertEqual(confidence.thresholds(), (0.6, 0.25))                 # the urgent cuts are untouched

    def test_unknown_words(self):
        self.addCleanup(os.environ.pop, 'LASTBOOK_CONF_UNKNOWN', None)
        for q in ('jdjdk', 'asdfgh', 'heschuokinghelkp', 'zebra jdjdk qqqq', 'help', 'how do i', 'ok', "he's"):
            self.assertTrue(confidence.unknown_words(q), q)      # most content words unknown, or no content word
        for q in ('how do i purify water', 'purify jdjdk', 'boil the water please', 'EU2200i wont start', 'hervir agua',
                  '', None):
            self.assertFalse(confidence.unknown_words(q), q)     # half known is not most; digits; another language
        os.environ['LASTBOOK_CONF_UNKNOWN'] = '0'
        self.assertFalse(confidence.unknown_words('jdjdk'))
        os.environ.pop('LASTBOOK_CONF_UNKNOWN')
        with mock.patch.object(confidence, '_words', lambda: ({}, 0)):
            self.assertFalse(confidence.unknown_words('jdjdk'))   # no library words: nothing to tell by

    def test_unknown_words_make_the_search_unsure_whatever_p(self):
        tr = dict(STRONG[1], q='jdjdk')                           # a strong-looking search for keyboard mash
        est = confidence.estimate(STRONG[0], tr)
        self.assertGreater(est['p_fitted'], confidence.BUTTONS)
        self.assertTrue(est['unknown_words'])
        self.assertEqual(est['level'], 'unsure')
        self.assertLess(est['p'], min(confidence.UNSURE, confidence.everyday_cut()))
        self.assertEqual(confidence.everyday_level(est['p']), 'unsure')        # an everyday question too
        sure = confidence.estimate(STRONG[0], dict(STRONG[1], q='how do i purify water'))
        self.assertEqual((sure['level'], 'unknown_words' in sure), ('sure', False))
        self.assertEqual(confidence.estimate(*STRONG)['level'], 'sure')        # no question in the trace: as before
        os.environ['LASTBOOK_CONF_UNSURE'] = '0'                               # never "please say more": buttons only
        self.assertEqual(confidence.estimate(STRONG[0], tr)['level'], 'buttons')

    def test_urgent_words(self):
        for q in ("my son isn't breathing", 'she cant breath wheezing bad', 'fell off the roof cant move legs',
                  "her face is drooping can't speak", 'chainsaw cut his leg', 'the outlet is sparking and smoking',
                  'i do not want to live anymore', 'water broke i can see the head'):
            self.assertTrue(confidence.urgent(q), q)
        for q in ('how to build a root cellar', 'how do i purify water', 'best way to store rice'):
            self.assertFalse(confidence.urgent(q), q)

    def test_urgent_in_everyday_words(self):
        """The same emergencies in everyday words, where none of the plain urgent words is used."""
        for q in ('the man in the car park slumped over the wheel', 'my uncle is out cold', 'grandad wont respond to me',
                  'she keeled over at work', 'he went down like a sack of potatoes', 'found him face down in the bath',
                  'thunderclap pain in my head', 'worst headache ever', 'his smile looks crooked', 'she is slurring',
                  "can't lift his left arm", 'took a whole packet of ibuprofen', 'she swallowed 30 tablets',
                  'he is siezing', 'i am killing myself tonight', 'my friend said goodbye and wants to die',
                  'his eyes keep rolling back', 'gurgling noise and he wont wake', "SHE CAN'T FEEL HER LEGS",
                  'colour is grey and ashen', 'blood is pouring out'):
            self.assertTrue(confidence.urgent(q), q)

    def test_injury_words(self):
        """INJURY: the injury words of URGENT, for server.PHRASES' how-to phrases (docs/TRIAGE-SEARCH.md, section 8)."""
        for q in ('treat water in the lungs after drowning', 'he is not breathing, start a fire for warmth', 'burned my hand lighting a fire',
                  'carbon monoxide from making a fire in the tent', 'light a fire to keep him warm with hypothermia',
                  'he got an electric shock', 'smoke inhalation from lighting a fire indoors', 'a second degree burn on his arm',
                  'the baby fell off the bed', 'how do i treat water poisoning'):
            self.assertTrue(confidence.injury(q), q)
        for q in ('how do i light a campfire', "how to make the water safe for a baby's formula", 'cut kindling', 'a fire without much smoke',
                  'wood that burns longer', 'start a fire with no matches and no gas', '', None):
            self.assertFalse(confidence.injury(q), q)

    def test_everyday_idioms_are_not_urgent(self):
        for q in ('how to bleed brakes on a bike', 'blood orange marmalade', 'a breath of fresh air', 'feeling blue lately',
                  'stroke of luck', 'two stroke oil', 'drowning in paperwork', 'the tent collapsed in the storm',
                  'he collapsed into laughter', 'my phone is dead', 'this dress doesnt fit', 'cpr certification course',
                  'brush strokes in oil painting', 'the engine is choking', 'pulse lentils soup', 'heartbroken after the match'):
            self.assertFalse(confidence.urgent(q), q)
        for q in ('bad breath and now he cant breathe', 'blood orange juice and now hes bleeding from the nose',
                  'feeling blue and his lips are blue', 'the tent collapsed on him and he is not breathing'):
            self.assertTrue(confidence.urgent(q), q)                         # the rest of the question still counts


class IsDanger(unittest.TestCase):
    """assistant.is_danger: the urgent words (as typed or put right) or a danger button, or else the meaning check; the meaning
    check's own tests are in test_meaning_red."""

    def setUp(self):
        clean_env(self)
        self.a = own_assistant(self)

    def test_words_and_buttons(self):
        for q in ("my son isn't breathing", 'he has been poisoned', 'Poison', 'burn', 'FIRE', 'Heavy bleeding', 'Not breathing'):
            self.assertTrue(self.a.is_danger(q), q)
        for q in ('how do i purify water', 'how to build a root cellar', '', None):
            self.assertFalse(self.a.is_danger(q), q)

    def test_as_typed_or_put_right(self):
        with mock.patch.object(self.a.typos, 'correct', lambda q: q.replace('braething', 'breathing')):
            self.assertTrue(self.a.is_danger('he isnt braething'))

    def test_english_words_count_too(self):
        self.assertFalse(self.a.is_danger('mi hijo no respira'))
        self.assertTrue(self.a.is_danger('mi hijo no respira', 'my son is not breathing'))

    def test_the_meaning_check_only_adds(self):
        info = {}
        self.assertTrue(self.a.is_danger("he isn't breathing", meaning=info))
        self.assertEqual((info['words'], info['fired']), (True, False))        # not started here: the words alone decide
        yes = lambda t: {'score': 0.1, 'fired': True, 'state': 'ready'}
        with mock.patch.object(self.a.meaning_red, 'check', yes):
            info = {}
            self.assertTrue(self.a.is_danger('how do i purify water', meaning=info))
            self.assertEqual((info['words'], info['fired']), (False, True))


class BodySigns(unittest.TestCase):
    """Body signs (confidence.body_signs): named exactly, one or two slips away on a word the library has on fewer
    than BODY_COMMON pages, or inside a glued run; they count as urgent. LASTBOOK_BODY_SIGNS=0 turns them off."""
    BV = dict(V, puls=24, pulse=1577, pulses=560, bloom=259, breeding=581, chore=16, chose=359, bleating=12, fit=900)

    def setUp(self):
        p = mock.patch.object(confidence, '_words', lambda: (self.BV, max(self.BV.values())))
        p.start()
        self.addCleanup(p.stop)
        clean_env(self)

    def test_named_and_misspelled(self):
        for q, want in [('he has no puls what do i do', {'pulse'}), ('he has no pulse', {'pulse'}),
                        ('mybbyisntbreathing', {'breathing'}), ('hescolapsednotbreathin', {'breathing', 'unconscious'}),
                        ('his lips are blue', {'blue'}), ('mybabyisblue', {'blue'}), ('she is unconsious', {'unconscious'}),
                        ('he passed out', {'unconscious'}), ('bledding from the leg', {'bleeding'}),
                        ('chokin on food', {'choking'}), ('she is having a fit', {'seizure'}),
                        ('chest hurts and he is sweating', {'chest pain'}), ('the baby is limp and not moving', {'not moving'}),
                        ('the child is cold and wet', {'cold and clammy'}), ('no heartbeet', {'pulse'}),
                        ('he is out cold', {'unconscious'}), ('she wont respond', {'unconscious'}),
                        ('elephant on my chest', {'chest pain'}), ('tight chest', {'chest pain'}),
                        ('his heart is racing', {'pulse'}), ('her pulse is very slow', {'pulse'}), ('how to do cpr', {'pulse'}),
                        ('blood pouring out of the cut', {'bleeding'}), ('the cut wont stop', {'bleeding'}),
                        ("she's fitting", {'seizure'}), ('his eyes are rolling', {'seizure'}),
                        ('collapsed and gurgling', {'breathing', 'unconscious'})]:
            self.assertEqual(confidence.body_signs(q), want, q)
            self.assertTrue(confidence.urgent(q), q)
        self.assertEqual(confidence.body_signs('', None, 'his lips are blue'), {'blue'})     # any of the texts

    def test_words_of_their_own(self):
        for q in ('how to cook pulses', 'how to make flowers bloom', 'chicken breeding', 'household chore list',
                  'she chose the red one', 'how to fit a pipe', 'the sky is blue', 'how to build a root cellar',
                  'plus size', 'pause', 'how to bleed the brakes', 'a breath of fresh air', 'blood orange cake',
                  'fitting room', 'the plant looks floppy'):
            self.assertEqual(confidence.body_signs(q), set(), q)
        self.assertFalse(confidence.urgent('how to build a root cellar'))

    def test_switch(self):
        self.assertTrue(confidence.urgent('he has no puls'))
        os.environ['LASTBOOK_BODY_SIGNS'] = '0'
        self.assertEqual(confidence.body_signs('he has no puls', 'mybbyisntbreathing'), set())
        self.assertFalse(confidence.urgent('he has no puls'))          # URGENT has pulse, not "puls"
        self.assertTrue(confidence.urgent('he has no pulse'))


class QuestionHits(unittest.TestCase):
    """assistant.question_hits with a hybrid stand-in that fills its trace."""

    def setUp(self):
        clean_env(self)
        self.a = assistant = own_assistant(self)
        self.canned = {'how do i purify water': STRONG, 'zebra cellar tomato': WEAK}

        def hybrid(q, k=8, kind='any', doc=None, trace=None):
            hits, tr = self.canned.get(q, ([], {'groups': [], 'semantic': False}))
            if trace is not None:
                trace.update(tr)
            return [dict(h) for h in hits][:k]
        S = mock.Mock(catalog=lambda: {'by_id': {}})
        for obj, name, value in ((assistant, 'hybrid', hybrid), (assistant, 'S', S),
                                 (confidence, '_words', lambda: (V, max(V.values())))):
            p = mock.patch.object(obj, name, value)
            p.start()
            self.addCleanup(p.stop)

    def test_one_question(self):
        hits, info = self.a.question_hits('how do i purify water')
        self.assertEqual((len(hits), info['confidence']['level'], info['danger'], info['body']), (8, 'sure', False, []))
        _, info = self.a.question_hits('zebra cellar tomato')
        self.assertEqual(info['confidence']['level'], 'unsure')

    def test_unknown_words_in_a_question(self):
        self.canned['qqzx wwvb'] = (STRONG[0], dict(STRONG[1], q='qqzx wwvb'))    # hits that look right, for mash
        _, info = self.a.question_hits('qqzx wwvb')
        self.assertEqual(info['confidence']['level'], 'unsure')             # the chat asks for more words, with buttons
        self.assertTrue(info['confidence']['unknown_words'])

    def test_off_and_without_a_trace(self):
        os.environ['LASTBOOK_CONF'] = '0'
        self.assertIsNone(self.a.question_hits('how do i purify water')[1]['confidence'])
        os.environ.pop('LASTBOOK_CONF')
        with mock.patch.object(self.a, 'hybrid', lambda q, k=8, kind='any', doc=None: list(STRONG[0])):
            self.assertIsNone(self.a.question_hits('how do i purify water')[1]['confidence'])

    def test_body_signs(self):
        """"he has no puls" (the library's word, not corrected) and a glued "mybbyisntbreathing": urgent, the body
        sign in info['body'], and chat_level answers with buttons, never only "help me help you"."""
        for q, sign in (('he has no puls what do i do', 'pulse'), ('mybbyisntbreathing', 'breathing')):
            self.canned[q] = WEAK
            _, info = self.a.question_hits(q)
            self.assertEqual((info['danger'], info['body']), (True, [sign]), q)
            self.assertEqual(info['confidence']['level'], 'unsure', q)
            level, conf, everyday = self.a.chat_level(info)
            self.assertEqual((level, conf['body'], everyday), ('buttons', True, False), q)
        os.environ['LASTBOOK_BODY_SIGNS'] = '0'
        _, info = self.a.question_hits('he has no puls what do i do')
        self.assertEqual((info['danger'], info['body']), (False, []))
        self.assertEqual(self.a.chat_level(info)[0], 'unsure')             # the bare "help me help you"


class SearchTrace(unittest.TestCase):
    """What _fts leaves in its trace for confidence.features, on a small made-up keyword index."""

    def setUp(self):
        clean_env(self)
        self.a = assistant = own_assistant(self)
        con = sqlite3.connect(':memory:')
        con.execute('CREATE VIRTUAL TABLE pages USING fts5(doc_id UNINDEXED, page UNINDEXED, body)')
        for i, body in enumerate(('boil the water to purify it', 'water from a river', 'a hammer and a saw')):
            con.execute('INSERT INTO pages VALUES (?, ?, ?)', (f'd{i}', 1, body))
        self.addCleanup(con.close)

        def query(db, kind_of, select, order, match, limit, ids=None):
            select = select.replace('bm25(pages,0,6,1,1,0,0,1)', 'bm25(pages)').replace("snippet(pages,6,", 'snippet(pages,2,')
            return con.execute(f'SELECT {select} FROM pages WHERE pages MATCH ? ORDER BY bm25(pages) LIMIT ?', (match, limit)).fetchall()
        S = mock.Mock(query_groups=lambda q: (['purify', 'water'], [['purify'], ['water']]),
                      fts_expr=lambda groups: ' AND '.join('(' + ' OR '.join(g) + ')' for g in groups),
                      library=mock.Mock(DB='x'), kind_of=lambda d: 'html')
        for obj, name, value in ((assistant, 'S', S), (assistant.sections, 'query', query)):
            p = mock.patch.object(obj, name, value)
            p.start()
            self.addCleanup(p.stop)

    def test_the_trace_of_the_keyword_search(self):
        tr = {}
        got = self.a._fts('purify water', 10, None, trace=tr)
        self.assertEqual([r[0] for r in got], ['d0', 'd0', 'd1'])   # the page with both words, then the any-word rows as they come
        self.assertEqual(tr['groups'], [['purify'], ['water']])
        self.assertEqual((tr['strict'], tr['any_word']), (1, True))     # one row had every word, so the any-word search ran
        self.assertEqual(len(tr['bm25']), 3)             # one bm25 per row
        self.assertTrue(all(isinstance(x, float) and x < 0 for x in tr['bm25']))   # SQLite's bm25: bigger is better when negated
        self.assertTrue(all(len(r) == 3 for r in got))
        self.assertEqual(self.a._fts('purify water', 10), got)   # without a trace: the same rows

    def test_no_words_leaves_an_empty_trace(self):
        self.a.S.query_groups = lambda q: ([], [])
        tr = {}
        self.assertEqual(self.a._fts('the', 10, None, trace=tr), [])
        self.assertEqual((tr['groups'], tr['strict'], tr['any_word'], tr['bm25']), ([], 0, False, []))


class ChatConfidence(unittest.TestCase):
    """assistant.chat with question_hits and the model round stood in for: which events the browser gets."""

    def setUp(self):
        clean_env(self)
        self.a = assistant = own_assistant(self)
        self.rounds = []
        cat = {'by_id': {'w1': {'id': 'w1', 'kind': 'html', 'title': 'Purify Water'}}}
        S = mock.Mock(catalog=lambda: cat)

        def model_round(msgs, tools, cancelled, wrote, set_state):
            self.rounds.append(msgs)
            wrote('Boil it [S1].')
            return 'Boil it [S1].', {}
        for name, value in (('S', S), ('LOCAL', None), ('_http_round', model_round), ('first_wiki', lambda q, root=None: [])):
            p = mock.patch.object(assistant, name, value)
            p.start()
            self.addCleanup(p.stop)
        self.hits = [hit('w1', 'Purify Water', 'boil it')]

    def run_chat(self, question, level, danger=False, p=None, body=(), unknown=False, messages=None, wiki=False):
        p = {'sure': 0.9, 'buttons': 0.5, 'unsure': 0.1}[level] if p is None else p
        info = {'danger': danger, 'body': list(body),
                'confidence': dict({'p': p, 'mode': 'keyword', 'level': level}, **({'unknown_words': True} if unknown else {}))}
        events = []
        with mock.patch.object(self.a, 'question_hits', lambda *a, **k: (self.hits, dict(info))):
            self.a.chat(messages or [{'role': 'user', 'content': question}], None, events.append, lambda: False, wiki=wiki)
        return {e['type']: e for e in events}, events

    def test_encyclopedia_articles_of_an_urgent_question_are_left_out(self):
        asked = []
        art = {'title': 'Water purification', 'zim': 'appropedia_en_all_maxi_2026-02.zim', 'article': 'Water_purification',
               'zim_key': 'zim/appropedia_en_all_maxi_2026-02.zim/Water_purification', 'excerpt': 'Boil water for one minute.'}

        def wiki(q, **k):
            asked.append(q)
            return [dict(art)]
        with mock.patch.object(self.a, 'first_wiki', wiki):
            ev, _ = self.run_chat('how do i purify water', 'sure')          # an everyday question: searched, as before
            self.assertEqual((len(asked), ev['found']['count']), (1, 2))
            self.assertTrue([m for m in self.rounds[0] if 'Encyclopedia article' in (m['content'] or '')])
            self.assertNotIn('wiki_offer', ev)
            # urgent: the encyclopedias are not searched at all; the manuals have the first results
            asked.clear()
            self.rounds.clear()
            ev, _ = self.run_chat('he is not breathing', 'sure', danger=True)
            self.assertEqual(asked, [])
            self.assertEqual(ev['found']['count'], 1)
            self.assertFalse([m for m in self.rounds[0] if 'Encyclopedia article' in (m['content'] or '')])
            self.assertNotIn('wiki_offer', ev)                              # no encyclopedias installed: nothing to offer
            with mock.patch.object(self.a.encyclopedias, 'list_files', lambda root=None: ['x.zim']):
                ev, _ = self.run_chat('he is not breathing', 'sure', danger=True)
                self.assertIn('wiki_offer', ev)                             # "Not an emergency? Add the encyclopedias"
                ev, _ = self.run_chat('how do i purify water', 'sure')
                self.assertNotIn('wiki_offer', ev)
                # the button, or the chat setting: the same question, and the articles come back; nothing else changes
                asked.clear()
                ev, _ = self.run_chat('he is not breathing', 'sure', danger=True, wiki=True)
                self.assertEqual(len(asked), 1)
                self.assertNotIn('wiki_offer', ev)
                self.assertEqual(ev['found']['count'], 2)
                os.environ['LASTBOOK_WIKI_URGENT'] = '1'                    # the same for every client
                asked.clear()
                ev, _ = self.run_chat('he is not breathing', 'sure', danger=True)
                self.assertEqual((len(asked), ev['found']['count']), (1, 2))

    def test_wiki_skipped(self):
        self.assertTrue(self.a.wiki_skipped(True))
        self.assertFalse(self.a.wiki_skipped(False))
        self.assertFalse(self.a.wiki_skipped(True, wiki=True))
        self.assertFalse(self.a.wiki_skipped(None))

    def test_sure_answers_as_before(self):
        ev, _ = self.run_chat('how do i purify water', 'sure')
        self.assertNotIn('suggest', ev)
        self.assertEqual(len(self.rounds), 1)
        self.assertEqual(ev['done']['answer'], 'Boil it [S1].')
        self.assertNotIn('unsure', ev['done'])

    def test_unsure_offers_buttons_and_answers(self):
        ev, _ = self.run_chat('he is bleeding from the arm', 'buttons', danger=True)      # may be urgent
        self.assertEqual(ev['suggest']['prompt'], self.a.SUGGEST_PROMPT['buttons'])
        self.assertIn('Not breathing', [c['label'] for c in ev['suggest']['choices']])
        self.assertEqual(ev['suggest']['confidence']['level'], 'buttons')
        self.assertNotIn('style', ev['suggest'])                             # the emergency buttons' own look
        self.assertEqual(len(self.rounds), 1)

    def test_urgent_cuts(self):
        for p, buttons in ((0.59, True), (0.3, True), (0.61, False)):
            self.rounds.clear()
            level = 'buttons' if p < 0.6 else 'sure'
            ev, _ = self.run_chat('he is bleeding from the arm', level, danger=True, p=p)
            self.assertEqual('suggest' in ev, buttons, p)
            self.assertEqual(len(self.rounds), 1)

    def test_everyday_unsure_answers_without_buttons(self):
        ev, _ = self.run_chat('how do i build a goat fence', 'buttons', p=0.5)
        self.assertNotIn('suggest', ev)                                     # 0.5 is under 0.60 but over the everyday cut
        self.assertEqual(len(self.rounds), 1)
        self.assertEqual(ev['done']['answer'], 'Boil it [S1].')

    def test_everyday_very_unsure_gets_the_same_buttons_smaller(self):
        ev, _ = self.run_chat('how do i build a goat fence', 'buttons', p=0.27)
        self.assertEqual(ev['suggest']['style'], 'compact')
        self.assertEqual(ev['suggest']['choices'], self.a.suggest_choices())   # the same choices as an urgent question's
        self.assertEqual(ev['suggest']['prompt'], self.a.SUGGEST_PROMPT['buttons'])
        self.assertEqual(ev['suggest']['confidence']['level'], 'buttons')
        self.assertTrue(ev['suggest']['confidence']['everyday'])
        self.assertEqual(len(self.rounds), 1)                               # 0.25-0.30: buttons and the answer

    def test_everyday_cut_from_the_environment(self):
        os.environ['LASTBOOK_CONF_BUTTONS_EVERYDAY'] = '0.55'
        ev, _ = self.run_chat('how do i build a goat fence', 'buttons', p=0.5)
        self.assertEqual(ev['suggest']['style'], 'compact')
        os.environ['LASTBOOK_CONF_BUTTONS_EVERYDAY'] = '0.2'
        self.rounds.clear()
        ev, _ = self.run_chat('how do i build a goat fence', 'unsure', p=0.22)
        self.assertNotIn('suggest', ev)                                     # no request to say more above the buttons cut
        self.assertNotIn('unsure', ev['done'])
        self.assertEqual(len(self.rounds), 1)

    def test_very_unsure_asks_without_the_model(self):
        ev, events = self.run_chat('zebra cellar tomato', 'unsure')
        self.assertEqual(self.rounds, [])                                   # the model is never asked
        self.assertIn('suggest', ev)
        self.assertEqual(ev['done']['answer'], self.a.UNSURE_PAGES)
        self.assertEqual(ev['suggest']['style'], 'compact')                 # everyday: below both cuts, smaller buttons
        self.assertTrue(ev['done']['unsure'])
        self.assertEqual([s['doc_id'] for s in ev['done']['sources']], ['w1'])   # the pages, as pages to open
        self.assertEqual(ev['done']['consulted'], [])
        self.assertLess(events.index(ev['suggest']), events.index(ev['done']))

    def test_very_unsure_with_nothing_found_says_so(self):
        self.hits = []
        ev, _ = self.run_chat('zebra cellar tomato', 'unsure')
        self.assertEqual((ev['done']['answer'], ev['done']['sources']), (self.a.UNSURE_TEXT, []))
        ev, _ = self.run_chat('my son neary drownd', 'unsure', danger=True, unknown=True)
        self.assertEqual((ev['done']['answer'], ev['done']['sources']), (self.a.UNSURE_DANGER_NONE, []))

    def test_very_unsure_but_urgent_answers_from_the_pages(self):
        """"took 20 of her sleeping tablets": answered from its pages with the buttons, as a body sign's is.
        LASTBOOK_CONF_URGENT_ANSWER=0 gives the pages only; so do words that are not the library's (unknown_words)."""
        ev, events = self.run_chat('my son neary drownd', 'unsure', danger=True)
        self.assertEqual(len(self.rounds), 1)
        self.assertEqual(ev['done']['answer'], 'Boil it [S1].')
        self.assertTrue(ev['suggest']['confidence']['urgent'])
        self.assertNotIn('style', ev['suggest'])
        self.assertLess(events.index(ev['suggest']), events.index(ev['done']))
        os.environ['LASTBOOK_CONF_URGENT_ANSWER'] = '0'
        for unknown in (False, True):
            self.rounds.clear()
            if unknown:
                os.environ.pop('LASTBOOK_CONF_URGENT_ANSWER')
            ev, _ = self.run_chat('my son neary drownd', 'unsure', danger=True, unknown=unknown)
            self.assertEqual(self.rounds, [], unknown)
            self.assertEqual(ev['done']['answer'], self.a.UNSURE_DANGER)
            self.assertEqual([s['doc_id'] for s in ev['done']['sources']], ['w1'])
            self.assertIn('suggest', ev)
            self.assertNotIn('style', ev['suggest'])

    def test_chat_reply_actions(self):
        info = lambda **k: dict({'danger': False, 'body': [], 'confidence': {'p': 0.1, 'mode': 'keyword', 'level': 'unsure'}}, **k)
        act = lambda t, n=1: self.a.chat_reply(t, n)['action']
        self.assertEqual(act(info()), 'ask+pages')
        self.assertEqual(act(info(), 0), 'ask (nothing found)')
        self.assertEqual(act(info(danger=True)), 'buttons')
        body = self.a.chat_reply(info(body=['pulse'], danger=True), 1)   # a body sign is always danger
        self.assertEqual((body['action'], body['style'], body['confidence'].get('body')), ('buttons', '', True))
        self.assertEqual(act(info(confidence={'p': 0.9, 'mode': 'keyword', 'level': 'sure'})), 'answer')
        self.assertEqual(act(info(confidence={'p': 0.28, 'mode': 'keyword', 'level': 'buttons'})), 'compact buttons')
        self.assertEqual(act(info(confidence=None)), 'answer')            # confidence off

    def test_very_unsure_with_a_body_sign_answers(self):
        """"he has no puls": never only "help me help you" (nor the pages without an answer): the model answers from
        the pages, with the emergency buttons."""
        ev, events = self.run_chat('he has no puls what do i do', 'unsure', danger=True, p=0.22, body=['pulse'])
        self.assertEqual(len(self.rounds), 1)
        self.assertEqual(ev['done']['answer'], 'Boil it [S1].')
        self.assertNotIn('unsure', ev['done'])
        self.assertEqual(ev['suggest']['prompt'], self.a.SUGGEST_PROMPT['buttons'])
        self.assertTrue(ev['suggest']['confidence']['body'])
        self.assertNotIn('style', ev['suggest'])                             # the emergency buttons full size
        self.assertLess(events.index(ev['suggest']), events.index(ev['done']))
        self.rounds.clear()
        ev, _ = self.run_chat('mybbyisntbreathing', 'unsure', danger=True, body=['breathing'])
        self.assertEqual((len(self.rounds), ev['done']['answer']), (1, 'Boil it [S1].'))

    def test_very_unsure_later_in_a_chat_is_only_buttons(self):
        """A later message is often a follow-up ("and at night?"): it gets the buttons and the answer, not "say more"."""
        msgs = [{'role': 'user', 'content': 'how do i purify water'}, {'role': 'assistant', 'content': 'Boil it.'},
                {'role': 'user', 'content': 'and at night?'}]
        ev, _ = self.run_chat('and at night?', 'unsure', messages=msgs)
        self.assertEqual(len(self.rounds), 1)
        self.assertEqual(ev['suggest']['prompt'], self.a.SUGGEST_PROMPT['buttons'])
        self.assertNotIn('unsure', ev['done'])

    def test_glued_first_message_as_the_chat_sees_it(self):
        ev, _ = self.run_chat('heschuokinghelkp', 'unsure', danger=False)    # split off and not split: unknown words
        self.assertEqual(self.rounds, [])
        self.assertEqual(ev['done']['answer'], self.a.UNSURE_PAGES)
        self.assertIn('suggest', ev)

    def test_chat_from_the_search_to_the_events(self):
        """The whole way, with only hybrid and the model stood in for: a strong search answers, a weak one asks."""
        canned = {'how do i purify water': STRONG, 'zebra cellar tomato': WEAK}

        def hybrid(q, k=8, kind='any', doc=None, trace=None):
            hits, tr = canned[q]
            trace.update(tr, q=q)
            return [dict(h) for h in hits][:k]
        cat = {'by_id': {h['doc_id']: {'id': h['doc_id'], 'kind': 'html', 'title': h['title']} for h in STRONG[0] + WEAK[0]}}
        with mock.patch.object(self.a, 'hybrid', hybrid), mock.patch.object(self.a.S, 'catalog', lambda: cat), \
                mock.patch.object(confidence, '_words', lambda: (V, max(V.values()))):
            events = []
            self.a.chat([{'role': 'user', 'content': 'how do i purify water'}], None, events.append, lambda: False)
            self.assertNotIn('suggest', [e['type'] for e in events])
            self.assertEqual(len(self.rounds), 1)
            self.rounds.clear()
            events = []
            self.a.chat([{'role': 'user', 'content': 'zebra cellar tomato'}], None, events.append, lambda: False)
            ev = {e['type']: e for e in events}
            self.assertEqual(self.rounds, [])
            self.assertTrue(ev['done']['unsure'])
            self.assertEqual(ev['done']['answer'], self.a.UNSURE_PAGES)
            self.assertEqual(ev['suggest']['style'], 'compact')
            self.assertEqual(ev['suggest']['confidence']['level'], 'unsure')
            self.assertEqual([s['doc_id'] for s in ev['done']['sources']], ['z1'])


if __name__ == '__main__':
    unittest.main()
