#!/usr/bin/env python3
"""The first library search for a message inside a conversation (assistant.turn_hits), the plea, and English search words.

  python -B -m unittest app.tests.test_turn_hits [-v]

No library and no model: hybrid returns canned hits keyed by the query, and the catalogue holds one book, so the previous
answer's "(Title, p. N)" citations come back as carried pages. Checked: every route (first, follow, noise, correct, danger),
noise never becoming the earlier message, a correction dropping the pages already shown, a new danger sign carrying nothing,
one-message conversations searching as before, the bare plea ("911", "help"), the English search words for a question in
another language (which questions need them, what the model's reply must be, what is asked and kept), and chat() with the
routes: noise gets the "Still about" button, a plea gets the emergency buttons first, a conversation without the local AI is
searched message by message as before. Never packaged."""
import os, sys, unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT), str(HERE)]
import fixture  # noqa: E402
os.environ['LASTBOOK_DATA'] = str(fixture.ensure())   # engine.paths reads it once: the made-up library every test module uses


def hit(doc, page):
    # only the "water" book is in the catalogue the tests give (a PDF); the rest are web pages, which chat() reads from the excerpt
    return {'doc_id': doc, 'page': page, 't': None, 'kind': 'pdf' if doc == 'water' else 'html', 'title': doc,
            'excerpt': f'{doc} page {page}', 'found_by': {'keyword': 1}}


CANNED = {
    'how do i purify water': [hit('water', 1), hit('water', 2), hit('boil', 3), hit('bleach', 4)],
    'and if i have no bleach?': [hit('boil', 3), hit('sun', 5), hit('filter', 6), hit('cloth', 7), hit('clay', 8)],
    'how do i purify water and if i have no bleach?': [hit('boil', 3), hit('filter', 6), hit('sand', 9)],
    'THE KITCHEN IS ON FIRE': [hit('grease', 1), hit('escape', 2), hit('exting', 3), hit('smoke', 4), hit('alarm', 5),
                               hit('kids', 6)],
    'how do i purify water THE KITCHEN IS ON FIRE': [hit('water', 1), hit('grease', 1), hit('stove', 7)],
    'burned my hand lighting the fire': [hit('burn', 1), hit('firemake', 2), hit('blister', 3)],
    "the smoke, he can't breathe": [hit('firemake', 2), hit('smokeinh', 1), hit('cpr', 4), hit('burn', 1)],
    "burned my hand lighting the fire the smoke, he can't breathe": [hit('burn', 1), hit('smokeinh', 1), hit('co', 5)],
    'my son is choking': [hit('choke', 1), hit('heimlich', 2), hit('cpr', 3)],
    "he's turning blue": [hit('cyanosis', 1)],
    "my son is choking he's turning blue": [hit('choke', 1), hit('cpr', 3), hit('blue', 4)],
    'hervir agua': [],
    'boil water': [hit('boil', 3), hit('water', 1)],
    'boil water at night': [hit('night', 1), hit('boil', 3)],
    'boil water dark': [hit('night', 1)],
    'Burn': [hit('burn', 1), hit('blister', 3)],
    'how do i purify water Burn': [hit('water', 1)],
    '911': [hit('numbers', 1), hit('firstaid', 2)],
}


def own_assistant(test):
    """A copy of assistant of this test's own: the modules it adds are put back afterwards, and the environment too."""
    before, shared = set(sys.modules), sys.modules.pop('assistant', None)

    def restore():
        for n in set(sys.modules) - before:
            sys.modules.pop(n, None)
        if shared is not None:
            sys.modules['assistant'] = shared
    test.addCleanup(restore)
    env = mock.patch.dict(os.environ)
    env.start()
    test.addCleanup(env.stop)
    for k in [k for k in os.environ if k.startswith(('LASTBOOK_AI_', 'LASTBOOK_CONF', 'LASTBOOK_MEANING_RED', 'LASTBOOK_WIKI'))]:
        del os.environ[k]
    import assistant
    return assistant


class Base(unittest.TestCase):
    def setUp(self):
        self.a = assistant = own_assistant(self)
        self.calls = []

        def hybrid(q, k=8, kind='any', doc=None):
            self.calls.append(q)
            return [dict(h) for h in CANNED.get(q, [])][:k]
        cat = {'by_id': {'water': {'id': 'water', 'kind': 'pdf', 'title': 'Water Book'}}}
        S = mock.Mock(catalog=lambda: cat, public=lambda r: {'title': r['title'], 'publisher': '', 'year': None, 'trust': '',
                                                             'pages': 9}, page_texts=lambda r: ['page text'] * 9)
        for name, value in (('hybrid', hybrid), ('S', S)):
            p = mock.patch.object(assistant, name, value)
            p.start()
            self.addCleanup(p.stop)
        # the library's words, as _vocab() would read them from the search database
        p = mock.patch.dict(assistant._VOCAB, words={'water', 'purify', 'bleach', 'kitchen', 'fire', 'smoke', 'breathe', 'son',
                                                     'choking', 'turning', 'blue', 'burned', 'hand', 'lighting', 'boil', 'cpr',
                                                     'stop', 'bleeding', 'shivering'})
        p.start()
        self.addCleanup(p.stop)

    def convo(self, *turns):
        return [{'role': 'user' if n % 2 == 0 else 'assistant', 'content': t} for n, t in enumerate(turns)]

    def keys(self, hits):
        return [(h['doc_id'], h['page']) for h in hits]


class TurnHits(Base):
    # ------------------------------------------------------------------ unchanged
    def test_one_message_is_its_own_search(self):
        hits, info = self.a.turn_hits(self.convo('how do i purify water'))
        self.assertEqual(self.calls, ['how do i purify water'])
        self.assertEqual(self.keys(hits), self.keys(CANNED['how do i purify water']))
        self.assertEqual((info['route'], info['buttons']), ('first', False))

    def test_one_noise_message_is_still_searched(self):
        hits, info = self.a.turn_hits(self.convo('jdjdjdk'))
        self.assertEqual((self.calls, hits, info['route'], info['buttons']), (['jdjdjdk'], [], 'first', False))
        # (its words are not the library's: engine.confidence.unknown_words makes it unsure, test_confidence)

    def test_one_stock_noise_message(self):
        for msg in ('ok', 'sorry wrong chat', '😭😭😭'):
            self.calls.clear()
            hits, info = self.a.turn_hits(self.convo(msg))
            # nothing before it to fall back on: searched, with buttons, as noise later on; the chat then asks for more words
            self.assertEqual((self.calls, info['route'], info['buttons'], info['still']), ([msg], 'noise', True, ''), msg)

    def test_glued_message_is_not_noise(self):
        with mock.patch.object(self.a.typos, 'correct', lambda q: "he's choking help" if q == 'heschuokinghelkp' else q):
            self.assertFalse(self.a.is_noise('heschuokinghelkp'))       # as searched, its words are the library's
        with mock.patch.object(self.a.typos, 'correct', lambda q: q):
            self.assertTrue(self.a.is_noise('heschuokinghelkp'))         # not split (LASTBOOK_TYPO_SPLIT=0): noise

    def test_followup_off_searches_the_message_alone(self):
        hits, info = self.a.turn_hits(self.convo('how do i purify water', '', 'THE KITCHEN IS ON FIRE'), followup=False)
        self.assertEqual(self.calls, ['THE KITCHEN IS ON FIRE'])
        self.assertEqual(info['route'], 'first')

    def test_a_long_message_is_cut_before_it_is_labelled(self):
        with mock.patch.object(self.a, 'is_danger', lambda msg, *a, **k: self.calls.append(len(msg)) or False):
            self.a.turn_hits(self.convo('x' * 1000))
        self.assertEqual(self.calls[0], 300)

    # ------------------------------------------------------------------ follow
    def test_follow_up_carries_the_cited_pages_first(self):
        hits, info = self.a.turn_hits(self.convo('how do i purify water', 'Boil it (Water Book, p. 2).', 'and if i have no bleach?'))
        self.assertEqual(info['route'], 'follow')
        self.assertEqual(self.calls, ['and if i have no bleach?', 'how do i purify water and if i have no bleach?'])
        # carried page, this message's best 4, the joined search's new ones, the rest
        self.assertEqual(self.keys(hits), [('water', 2), ('boil', 3), ('sun', 5), ('filter', 6), ('cloth', 7), ('sand', 9),
                                           ('clay', 8)])
        self.assertEqual(hits[0]['found_by'], {'earlier answer': 1})

    def test_followup_hits_order(self):
        own = [{'doc_id': d, 'page': 1} for d in 'abcdef']
        joined = [{'doc_id': d, 'page': 1} for d in 'xaybz']
        self.assertEqual([h['doc_id'] for h in self.a.followup_hits(own, joined)], list('abcdexyz'))

    def test_cited_before_reads_what_the_browser_sends(self):
        """web/chat.js history_() sends an earlier answer with [S2] written as "(Title, p. 2)": found again as pages. A title
        holding parentheses works, a page past the end of the book and a title that is not a book do not."""
        cat = {'by_id': {'c1': {'id': 'c1', 'kind': 'pdf', 'title': 'CERT Manual (2019)'},
                         'v1': {'id': 'v1', 'kind': 'video', 'title': 'Boiling Video'}}}
        pub = lambda r: {'title': r['title'], 'publisher': 'P', 'year': '2019', 'trust': 't', 'pages': 3}
        fake = mock.Mock(catalog=lambda: cat, public=pub, page_texts=lambda r: ['one', 'two  words', 'three'])
        with mock.patch.object(self.a, 'S', fake):
            h = [{'role': 'assistant', 'content': 'Bleach (CERT Manual (2019), p. 2). Again [CERT Manual (2019), p. 2]. '
                                                  'Far (CERT Manual (2019), p. 9). Watch (Boiling Video, 1:15).'},
                 {'role': 'user', 'content': 'and?'}]
            got = self.a.cited_before(h)
        self.assertEqual([(g['doc_id'], g['page'], g['excerpt']) for g in got], [('c1', 2, 'two words')])
        self.assertEqual(self.a.cited_before([{'role': 'user', 'content': 'hi'}]), [])

    # ------------------------------------------------------------------ noise
    def test_noise_keeps_the_last_sensible_results_and_asks(self):
        for noise in ('jdjdjdk', 'sorry wrong chat', 'ok', '😭😭😭', 'hhhhhhh', 'ignore that'):
            self.calls.clear()
            hits, info = self.a.turn_hits(self.convo('how do i purify water', 'Boil it.', noise))
            self.assertNotIn(noise, ' '.join(self.calls), noise)
            self.assertEqual(self.keys(hits), self.keys(CANNED['how do i purify water']), noise)
            self.assertEqual((info['route'], info['buttons'], info['still']), ('noise', True, 'how do i purify water'), noise)

    def test_noise_never_becomes_the_earlier_message(self):
        hits, info = self.a.turn_hits(self.convo('my son is choking', 'Back blows.', 'sorry wrong chat', 'Okay.', "he's turning blue"))
        self.assertEqual(self.calls[-1], "my son is choking he's turning blue")
        self.assertEqual(info['still'], 'my son is choking')
        self.assertEqual(self.a.earlier_question(self.convo('my son is choking', '', 'jdjdjdk', '', 'x')), 'my son is choking')
        self.assertTrue(info['buttons'])        # its own search found 1 page

    def test_sensible_messages_are_not_noise(self):
        for msg in ("no no the smoke he cant breathe", 'what do i not do', 'it wont stop bleeding', "he's shivering",
                    '¿y si le sale una ampolla?', 'mi hijo se quemó', 'cpr'):
            self.assertFalse(self.a.is_noise(msg), msg)

    def test_without_the_library_words_it_goes_by_how_words_look(self):
        with mock.patch.dict(self.a._VOCAB, words=set()):
            for msg in ('jdjdjdk', 'asdfgh', 'kkkkk', 'jfjfjfjf'):
                self.assertTrue(self.a.is_noise(msg), msg)
            self.assertFalse(self.a.is_noise('the kitchen is on fire'))

    # ------------------------------------------------------------------ correct
    def test_correction_drops_the_pages_already_shown(self):
        hits, info = self.a.turn_hits(self.convo('burned my hand lighting the fire', 'Cool it (Water Book, p. 1).',
                                                 "no no i mean the smoke, he can't breathe"))
        self.assertEqual(info['route'], 'correct')
        self.assertIn("the smoke, he can't breathe", self.calls)          # correction words stripped
        # shown: the cited page and the earlier message's own pages (burn 1, firemake 2, blister 3); they go last
        self.assertEqual(self.keys(hits), [('smokeinh', 1), ('cpr', 4), ('co', 5), ('firemake', 2), ('burn', 1)])
        self.assertNotIn(('water', 1), self.keys(hits))                    # nothing carried

    # ------------------------------------------------------------------ danger
    def test_new_danger_sign_is_a_new_emergency(self):
        hits, info = self.a.turn_hits(self.convo('how do i purify water', 'Boil it (Water Book, p. 2).', 'THE KITCHEN IS ON FIRE'))
        self.assertEqual(info['route'], 'danger')
        self.assertEqual(self.keys(hits)[:5], self.keys(CANNED['THE KITCHEN IS ON FIRE'])[:5])
        self.assertNotIn(('water', 2), self.keys(hits))                    # the cited water page is not carried
        self.assertEqual(self.keys(hits)[5:], [('water', 1), ('stove', 7), ('kids', 6)])

    def test_a_danger_sign_already_there_is_a_follow_up(self):
        _, info = self.a.turn_hits(self.convo('my son is choking', '', 'he is still choking'))
        self.assertEqual(info['route'], 'follow')

    def test_danger_signs_skip_idioms_and_the_danger_label_has_them(self):
        self.assertEqual(self.a.danger_signs('THE KITCHEN IS ON FIRE'), {'on fire'})
        self.assertEqual(self.a.danger_signs('I am drowning in homework'), set())
        self.assertTrue(self.a.is_danger('the pan caught fire'))
        self.assertTrue(self.a.is_danger('the pan', english='caught fire'))     # the English words count too
        self.assertFalse(self.a.is_danger('how do i purify water'))

    def test_buttons_and_a_button_label(self):
        info = {'still': 'how do i purify water', 'buttons': True}
        choices = self.a.suggest_choices(info)
        self.assertEqual(choices[0], {'label': 'Still about: how do i purify water', 'text': 'Still about: how do i purify water'})
        self.assertEqual([c['label'] for c in choices[1:]], ['Not breathing', 'Heavy bleeding', 'Burn', 'Poison', 'Fire',
                                                              'Something else'])
        self.assertEqual(choices[-1]['text'], '')
        self.assertEqual(self.a.suggest_choices(), choices[1:])              # no last question: the emergencies alone
        _, info = self.a.turn_hits(self.convo('how do i purify water', '', 'Burn'))
        self.assertEqual(info['route'], 'danger')                            # a danger button is a new emergency
        self.calls.clear()
        hits, info = self.a.turn_hits(self.convo('how do i purify water', '', 'ok', '', choices[0]['text']))
        self.assertEqual(self.calls[0], 'how do i purify water')            # "Still about:" is not searched for

    # ------------------------------------------------------------------ plea
    def test_a_bare_plea(self):
        for msg in ('911', 'help', 'HELP ME', 'hlep', 'helppp please', 'sos', 'emergency', '999', 'please help me now', 'Still about: 911'):
            self.assertTrue(self.a.plea(msg), msg)
        for msg in ('', 'how do i call 911 from a mobile', 'help me boil water', 'my son is choking help', 'ok', '1234', 'a'):
            self.assertFalse(self.a.plea(msg), msg)

    def test_a_plea_is_danger_but_only_as_a_first_message(self):
        hits, info = self.a.turn_hits(self.convo('911'))
        self.assertEqual((info['plea'], info['danger']), (True, True))
        _, info = self.a.turn_hits(self.convo('how do i purify water', 'Boil it.', '911'))
        self.assertFalse(info['plea'])

    def test_chat_level_and_reply_for_a_plea(self):
        _, info = self.a.turn_hits(self.convo('911'))
        reply = self.a.chat_reply(info, 2)
        self.assertEqual((reply['level'], reply['action'], reply['style'], reply['text']), ('unsure', 'plea', 'urgent', self.a.PLEA_TEXT))
        self.assertEqual(self.a.SUGGEST_PROMPT['plea'], 'What is happening?')

    # ------------------------------------------------------------------ what chat does with a route
    def test_levels_inside_a_conversation(self):
        unsure = {'p': 0.1, 'mode': 'keyword', 'level': 'unsure'}
        info = lambda **k: dict({'route': 'first', 'buttons': False, 'still': '', 'danger': True, 'body': [], 'confidence': unsure}, **k)
        level = lambda t, followup=True, asked=1: self.a.chat_level(t, followup, asked)[0]
        self.assertEqual(level(info(confidence=dict(unsure, unknown_words=True))), 'unsure')   # a first question: asked
        self.assertEqual(level(info(route='follow')), 'buttons')            # a later message only gets the buttons
        self.assertEqual(level(info(route='correct')), 'buttons')
        self.assertEqual(level(info(route='danger', confidence=dict(unsure, unknown_words=True))), 'unsure')   # a new emergency
        self.assertEqual(level(info(), followup=False, asked=2), 'buttons')   # no routes: any later message, as before
        self.assertEqual(level(info(route='noise', still='how do i purify water')), 'sure')   # noise: the earlier answer stands
        self.assertEqual(level(info(route='noise', still='', danger=False)), 'unsure')        # "ok" first: asked what it is
        noise = self.a.chat_reply(info(route='noise', still='x', confidence=None, buttons=True), 1, True, 3)
        self.assertEqual(noise['action'], 'buttons')                          # noise: the answer stands, with buttons over it

    # ------------------------------------------------------------------ English search words
    def test_english_words_replace_the_question(self):
        hits, _ = self.a.turn_hits(self.convo('hervir agua'), english='boil water')
        self.assertEqual((self.calls, self.keys(hits)), (['boil water'], [('boil', 3), ('water', 1)]))
        self.calls.clear()
        self.a.turn_hits(self.convo('hervir agua'), english='no results here')
        self.assertEqual(self.calls, ['no results here', 'hervir agua'])    # nothing in English: the question itself

    def test_english_follow_up_joins_the_earlier_english_words(self):
        with mock.patch.dict(self.a._ENGLISH_OF, {'hervir agua': 'boil water'}):
            hits, info = self.a.turn_hits(self.convo('hervir agua', '', '¿y de noche?'), english='dark')
        self.assertEqual(info['route'], 'follow')
        self.assertEqual(self.calls, ['dark', '¿y de noche?', 'boil water dark'])
        self.assertEqual(self.keys(hits), [('night', 1)])


class EnglishWords(Base):
    """A question in another language is searched with English words the local model writes, thinking off."""

    def test_which_questions_need_them(self):
        ne = self.a.needs_english
        for q in ('¿cómo hiervo agua?', 'necesito hacer fuego sin fósforos', 'mi bebé tiene fiebre', 'qué es la RCP',
                  'como purificar água', "comment purifier l'eau", '怎么生火', 'y si es de noche?',
                  '¡AUXILIO! ÉL ESTÁ HERIDO', 'el pingüino y el ñandú', 'agüita de güemul', 'NIÑO CON DIARREA',
                  'ñ', '¿¡qué!?', 'quemadura en la cara',
                  'niño con fiebre',       # "niño" decomposed, as a phone or Mac may send it
                  'pingüino herido'):       # "pingüino", decomposed
            self.assertTrue(ne(q), ascii(q))
        for q in ('how do i boil water', 'start a fire without matches', 'jalapeño burns on my hand', 'CPR', '',
                  'what is the piñata safety rule', 'no pulse', 'how to make a café latte without power',
                  'is my naïve résumé safe', 'the jalapeño burned my hand', '¿?¡!', '12 34'):
            self.assertFalse(ne(q), ascii(q))

    def test_what_the_models_reply_must_be(self):
        ew = self.a.english_words
        self.assertEqual(ew('start a fire without matches\n'), 'start a fire without matches')
        self.assertIsNone(ew('cómo hacer fuego sin fósforos'))
        self.assertIsNone(ew('niño con fiebre'))
        self.assertEqual(ew('“fever in a child from Ñuble”'), 'fever in a child from Ñuble')    # an odd word in English is kept
        self.assertEqual(ew('English: "boil water safely."<turn|>'), 'boil water safely')
        self.assertEqual(ew('<|channel>thought\nhmm<channel|>\n\nbaby fever'), 'baby fever')
        self.assertIsNone(ew('<|channel>thought\nbaby fever'))           # an open thought channel hides the rest
        self.assertIsNone(ew('¿cómo hiervo agua?'))
        self.assertIsNone(ew('  \n'))
        # the question's own words without its function words are still not English
        self.assertIsNone(ew('respirar humo incendio'))
        self.assertIsNone(ew('respirando esfuerzo costillas'))
        self.assertEqual(ew('empanadas dough filling'), 'empanadas dough filling')    # a dish among English words is kept

    def test_without_the_word_list_every_line_passes(self):
        with mock.patch.object(self.a.typos, 'english_words', lambda: frozenset()):
            self.assertEqual(self.a._mostly_english('respirar humo incendio'), True)

    def test_the_model_is_asked_once_and_the_words_kept(self):
        sent = []

        def gen(segs, n, cancelled, on_text):
            sent.append((segs, n))
            on_text('purify ')
            on_text('water\n')
            return {'reason': 'eos'}
        with mock.patch.object(self.a, 'LOCAL', mock.Mock(generate=gen)), mock.patch.dict(self.a._ENGLISH, clear=True), \
                mock.patch.dict(self.a._ENGLISH_OF, clear=True):
            self.assertEqual(self.a.english_query('¿cómo purifico agua?', 'tengo sed', lambda: False), 'purify water')
            self.assertEqual(self.a.english_query('¿cómo purifico agua?', 'tengo sed', lambda: False), 'purify water')   # kept
            self.assertEqual(len(sent), 1)
            self.assertEqual(self.a._ENGLISH_OF['¿cómo purifico agua?'], 'purify water')   # for the next follow-up's joined search
            prompt = ''.join(s[0] for s in sent[0][0])
            self.assertNotIn('<|think|>', prompt)
            self.assertTrue(prompt.rstrip().endswith('<channel|>'))         # thinking off: the empty thought channel
            self.assertIn('Earlier question: tengo sed\nLatest question: ¿cómo purifico agua?', prompt)
            self.assertIn('every word', prompt)         # the rules (assistant.REWRITE) go first
            self.assertEqual(sent[0][1], self.a.REWRITE_TOKENS)
            # the same follow-up after another question is asked again: "¿y si es de noche?" after fire is not after water
            self.a.english_query('¿y si es de noche?', '¿cómo hago fuego?', lambda: False)
            self.a.english_query('¿y si es de noche?', '¿cómo purifico agua?', lambda: False)
            self.assertEqual(len(sent), 3)
            self.assertIn('Earlier question: ¿cómo purifico agua?', ''.join(s[0] for s in sent[2][0]))

    def test_an_answer_in_the_questions_own_language_is_asked_for_once_more(self):
        replies = iter(['respirar humo incendio\n', 'smoke inhalation breathing\n'])
        asked = []

        def spanish_first(segs, n, cancelled, on_text):
            asked.append(''.join(s[0] for s in segs))
            on_text(next(replies))
            return {'reason': 'eos'}
        with mock.patch.object(self.a, 'LOCAL', mock.Mock(generate=spanish_first)), mock.patch.dict(self.a._ENGLISH, clear=True), \
                mock.patch.dict(self.a._ENGLISH_OF, clear=True):
            self.assertEqual(self.a.english_query('no puedo respirar, inhalé humo', '', lambda: False), 'smoke inhalation breathing')
        self.assertEqual(len(asked), 2)
        self.assertIn('Write the words in English', asked[1])

    def test_a_reply_that_is_still_not_english_gives_nothing(self):
        def always_spanish(segs, n, cancelled, on_text):
            on_text('respirar humo incendio\n')
            return {'reason': 'eos'}
        with mock.patch.object(self.a, 'LOCAL', mock.Mock(generate=always_spanish)), mock.patch.dict(self.a._ENGLISH, clear=True):
            self.assertIsNone(self.a.english_query('no puedo respirar, inhalé humo', '', lambda: False))
            self.assertEqual(self.a._ENGLISH, {})                            # nothing kept: the next try asks again

    def test_a_failing_or_stopped_model_gives_nothing(self):
        failing = mock.Mock(generate=mock.Mock(side_effect=RuntimeError('down')))
        with mock.patch.object(self.a, 'LOCAL', failing), mock.patch.dict(self.a._ENGLISH, clear=True):
            self.assertIsNone(self.a.english_query('¿y el fuego?', '', lambda: False))
        stopped = mock.Mock(generate=lambda segs, n, cancelled, on_text: {'reason': 'cancel'})
        with mock.patch.object(self.a, 'LOCAL', stopped), mock.patch.dict(self.a._ENGLISH, clear=True):
            self.assertIsNone(self.a.english_query('¿y el fuego?', '', lambda: False))


class Chat(Base):
    """assistant.chat with the model's round stood in for: the events the browser gets."""

    def setUp(self):
        super().setUp()
        self.rounds, self.started = [], []

        def model_round(msgs, tools, cancelled, wrote, set_state):
            self.rounds.append(msgs)
            wrote('Boil it [S1].')
            return 'Boil it [S1].', {}
        local = mock.Mock(ensure_running=lambda loading, cancelled: self.started.append(len(self.calls)))
        for name, value in (('LOCAL', local), ('_http_round', model_round), ('_local_round', model_round),
                            ('first_wiki', lambda q, root=None: [])):
            p = mock.patch.object(self.a, name, value)
            p.start()
            self.addCleanup(p.stop)

    def run_chat(self, *turns, local=True, english=None):
        events = []
        with mock.patch.object(self.a, 'local_on', lambda: local), \
                mock.patch.object(self.a, 'english_query', lambda q, earlier, cancelled: english):
            self.a.chat(self.convo(*turns), None, events.append, lambda: False)
        return {e['type']: e for e in events}, events

    def test_a_first_question_is_as_before(self):
        ev, _ = self.run_chat('how do i purify water')
        self.assertEqual(self.calls, ['how do i purify water'])
        self.assertNotIn('suggest', ev)
        self.assertEqual(ev['done']['answer'], 'Boil it [S1].')

    def test_noise_inside_a_conversation_keeps_the_answer_and_offers_the_last_question(self):
        ev, _ = self.run_chat('how do i purify water', 'Boil it (Water Book, p. 2).', 'ok')
        self.assertEqual(self.calls, ['how do i purify water'])              # no new search
        self.assertEqual(ev['suggest']['choices'][0]['label'], 'Still about: how do i purify water')
        self.assertEqual(len(self.rounds), 1)                                # the model still answers
        self.assertNotIn('unsure', ev['done'])

    def test_a_first_message_that_is_only_noise_asks_for_more(self):
        ev, _ = self.run_chat('😭')
        self.assertEqual(self.rounds, [])
        self.assertTrue(ev['done']['unsure'])
        self.assertIn('suggest', ev)

    def test_a_plea_gets_the_emergency_buttons_first(self):
        ev, events = self.run_chat('911')
        self.assertEqual(self.rounds, [])                                    # no model: nothing to search for
        self.assertEqual((ev['suggest']['style'], ev['suggest']['prompt']), ('urgent', 'What is happening?'))
        self.assertEqual([c['label'] for c in ev['suggest']['choices']],
                         ['Not breathing', 'Heavy bleeding', 'Burn', 'Poison', 'Fire', 'Something else'])
        self.assertEqual((ev['done']['answer'], ev['done']['unsure']), (self.a.PLEA_TEXT, True))
        self.assertEqual([s['doc_id'] for s in ev['done']['sources']], ['numbers', 'firstaid'])   # the pages found, all the same
        self.assertLess(events.index(ev['suggest']), events.index(ev['done']))

    def test_a_new_emergency_is_searched_first(self):
        ev, _ = self.run_chat('how do i purify water', 'Boil it.', 'THE KITCHEN IS ON FIRE')
        self.assertEqual(self.calls[0], 'THE KITCHEN IS ON FIRE')
        self.assertEqual(len(self.rounds), 1)

    def test_without_the_local_ai_a_message_is_searched_alone_as_before(self):
        ev, _ = self.run_chat('how do i purify water', 'Boil it.', 'and if i have no bleach?', local=False)
        self.assertEqual(self.calls, ['and if i have no bleach?'])
        ev, _ = self.run_chat('how do i purify water', 'Boil it.', 'ok', local=False)
        self.assertEqual(self.calls[-1], 'ok')                               # no routes: noise is searched like any message

    def test_switches(self):
        os.environ['LASTBOOK_AI_FOLLOWUP'] = '0'
        self.run_chat('how do i purify water', 'Boil it.', 'and if i have no bleach?')
        self.assertEqual(self.calls, ['and if i have no bleach?'])
        del os.environ['LASTBOOK_AI_FOLLOWUP']
        self.calls.clear()
        os.environ['LASTBOOK_AI_ENGLISH_SEARCH'] = '0'
        self.run_chat('hervir agua', english='boil water')
        self.assertEqual(self.calls, ['hervir agua'])

    def test_a_question_in_another_language_is_searched_in_english_and_answered_in_its_own(self):
        ev, _ = self.run_chat('hervir agua', english='boil water')
        self.assertEqual(self.calls, ['boil water'])
        self.assertEqual(self.started[0], 0)                                  # the model was started before the search
        notes = [m['content'] for m in self.rounds[0] if m['role'] == 'system' and 'not in English' in (m['content'] or '')]
        self.assertEqual(len(notes), 1)
        self.assertIn('was searched with: boil water', notes[0])
        self.assertIn('Answer in the language of the question', notes[0])

    def test_when_the_english_words_fail_the_question_is_searched_as_typed(self):
        self.run_chat('hervir agua', english=None)
        self.assertEqual(self.calls, ['hervir agua'])
        self.assertFalse([m for m in self.rounds[0] if 'not in English' in (m['content'] or '')])

    def test_an_english_question_never_asks_for_english_words(self):
        asked = []
        events = []
        with mock.patch.object(self.a, 'local_on', lambda: True), \
                mock.patch.object(self.a, 'english_query', lambda *a: asked.append(a)):
            self.a.chat(self.convo('how do i purify water'), None, events.append, lambda: False)
        self.assertEqual(asked, [])
        self.assertEqual(self.started, [1])                                  # the model started after the search, as before

    def test_the_encyclopedias_use_the_english_words(self):
        wiki = []
        with mock.patch.object(self.a, 'first_wiki', lambda q, root=None: wiki.append(q) or []):
            self.run_chat('hervir agua', english='boil water')
            self.run_chat('how do i purify water', 'Boil it (Water Book, p. 2).', 'and at night?')
        self.assertEqual(wiki, ['boil water', 'how do i purify water and at night?'])      # a follow-up: the joined words


if __name__ == '__main__':
    unittest.main()
