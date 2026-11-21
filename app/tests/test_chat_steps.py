"""Chat's "How it searched" list shows the model's own tool calls. They are the model's words, not ours: everything in a
step must reach the page escaped, whatever shape the model sent (a list, a single value, text with markup in it).

Runs chat.js's stepText with app.js's esc under Node. Needs Node on PATH; skipped without it. Never packaged."""
import html.parser, json, re, shutil, subprocess, unittest, urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NODE = shutil.which('node')
RUN = r"""
const fs = require('fs');
const chat = fs.readFileSync(process.argv[1], 'utf8'), app = fs.readFileSync(process.argv[2], 'utf8');
const esc = app.split('\n').find(l => /^const esc\s*=/.test(l));
const i = chat.indexOf('function stepText('), j = chat.indexOf('\n  function srcHref');
const stepText = new Function(esc + '\n' + chat.slice(i, j) + '\nreturn stepText;')();
const out = JSON.parse(process.argv[3]).map(s => { try { return stepText(s) } catch (e) { return 'THROW ' + e.message } });
process.stdout.write(JSON.stringify(out));
"""
# srcCards with its helpers from app.js (esc, fileUrl); ico, clock and here are stand-ins.
CARDS = r"""
const fs = require('fs');
const chat = fs.readFileSync(process.argv[1], 'utf8'), app = fs.readFileSync(process.argv[2], 'utf8');
const line = re => app.split('\n').find(l => re.test(l));
const helpers = [line(/^const esc\s*=/), line(/^const fileUrl\s*=/), "const ico = n => '<svg>' + n + '</svg>';",
  'const clock = t => String(t);', "const here = () => '#/ask';"].join('\n');
const i = chat.indexOf('function srcHref('), j = chat.indexOf('\n  /* markdown-lite');
const srcCards = new Function(helpers + '\n' + chat.slice(i, j) + '\nreturn srcCards;')();
process.stdout.write(JSON.stringify(JSON.parse(process.argv[3]).map(s => srcCards([s], false))));
"""


class Anchors(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.anchors = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.anchors.append(dict(attrs))


@unittest.skipUnless(NODE, 'needs Node')
class Steps(unittest.TestCase):
    def text(self, steps):
        r = subprocess.run([NODE, '-e', RUN, str(ROOT / 'web/chat.js'), str(ROOT / 'web/app.js'), json.dumps(steps)],
                           capture_output=True, text=True, check=True,
                           encoding='utf-8')  # Node writes UTF-8; Windows would read cp1252
        return json.loads(r.stdout)

    def test_read_pages_is_escaped_whatever_the_model_sent(self):
        got = self.text([
            {'name': 'read_pages', 'args': {'doc_id': 'x', 'pages': [3, 4]}, 'summary': {'title': 'FEMA'}},
            {'name': 'read_pages', 'args': {'doc_id': 'x', 'pages': ['<img src=x onerror=alert(1)>']}, 'summary': {'title': 'T'}},
            {'name': 'read_pages', 'args': {'doc_id': 'x', 'pages': '"><svg onload=alert(1)>'}, 'summary': {'title': 'T'}},
            {'name': 'read_pages', 'args': {'doc_id': 'x', 'pages': 7}, 'summary': {'title': 'T'}},
        ])
        self.assertEqual(got[0], 'Read FEMA, pages 3, 4')
        self.assertEqual(got[1], 'Read T, page &lt;img src=x onerror=alert(1)&gt;')
        self.assertEqual(got[2], 'Read T, page &quot;&gt;&lt;svg onload=alert(1)&gt;')
        self.assertEqual(got[3], 'Read T, page 7')
        for t in got:
            self.assertNotIn('<', t)

    def test_odd_shapes_neither_throw_nor_leak(self):
        # JSON can carry objects whose toString is not a function; converting them would throw and blank the answer.
        odd = [{'toString': 'x'}, {'a': 1}, [1, 2], None, True]
        got = self.text([
            {'name': 'read_pages', 'args': {'doc_id': 'x', 'pages': odd + [5, '6']}, 'summary': {'title': 'T'}},
            {'name': 'read_pages', 'args': {'doc_id': 'x', 'pages': {'toString': 'x'}}, 'summary': {'title': 'T'}},
            {'name': 'lookup_place', 'args': {'query': 'clinic', 'pages': {'toString': 'x'}}, 'summary': {}},
            {'name': 'search_library', 'args': {'query': 'water', 'pages': {'toString': 'x'}}, 'summary': {'count': 1}},
            {'name': 'view_page', 'args': {'doc_id': 'x', 'page': 3, 'pages': {'toString': 'x'}}, 'summary': {'title': 'T'}},
        ])
        for t in got:
            self.assertFalse(t.startswith('THROW'), t)
            self.assertNotIn('<', t)
        self.assertEqual(got[0], 'Read T, pages 5, 6')
        self.assertEqual(got[1], 'Read T, page ')
        self.assertEqual(got[2], 'Looked up “clinic” on the offline map')
        self.assertEqual(got[3], 'Searched “water” — 1 passage')
        self.assertEqual(got[4], 'Looked at the picture of T, page 3')

    def test_odd_values_in_other_arguments(self):
        bad = {'toString': 'x'}
        got = self.text([
            {'name': 'search_library', 'args': {'query': bad, 'kind': bad}, 'summary': {'count': 2}},
            {'name': 'lookup_place', 'args': {'query': bad}, 'summary': {}},
            {'name': 'view_page', 'args': {'doc_id': bad, 'page': bad}, 'summary': {'title': 'T'}},
            {'name': 'read_pages', 'args': {'doc_id': bad, 'pages': [2]}, 'summary': {}},
            {'name': 'search_library', 'args': 'not an object', 'summary': {'count': 0}},
            {'name': 'search_library', 'args': {'query': '<b>x</b>', 'kind': 'video'}, 'summary': {'count': 1}},
        ])
        for t in got:
            self.assertFalse(t.startswith('THROW'), t)
            self.assertNotIn('<', t)
        self.assertEqual(got[0], 'Searched “” — 2 passages')
        self.assertEqual(got[2], 'Looked at the picture of T, page ')
        self.assertEqual(got[3], 'Read , page 2')
        self.assertEqual(got[5], 'Searched “&lt;b&gt;x&lt;/b&gt;” (videos) — 1 passage')

    def test_encyclopedia_steps_are_escaped(self):
        got = self.text([
            {'name': 'search_encyclopedia', 'args': {'query': 'cholera'}, 'summary': {'count': 2}},
            {'name': 'search_encyclopedia', 'args': {'query': '<b>x</b>'}, 'summary': {'count': 1}},
            {'name': 'read_encyclopedia', 'args': {'article': 'zim/mdwiki.zim/Cholera'}, 'summary': {'title': 'Cholera'}},
            {'name': 'read_encyclopedia', 'args': {'article': '<img src=x>'}, 'summary': {'error': 'unknown'}},
            {'name': 'read_encyclopedia', 'args': {'article': '"><svg onload=alert(1)>'}, 'summary': {'title': '"><svg onload=alert(1)>'}},
        ])
        for t in got:
            self.assertFalse(t.startswith('THROW'), t)
            self.assertNotIn('<', t)
        self.assertEqual(got[0], 'Searched the encyclopedias for “cholera” — 2 articles')
        self.assertEqual(got[1], 'Searched the encyclopedias for “&lt;b&gt;x&lt;/b&gt;” — 1 article')
        self.assertEqual(got[2], 'Read the encyclopedia article “Cholera”')
        self.assertEqual(got[3], 'Tried to read an unknown encyclopedia article')
        self.assertEqual(got[4], 'Read the encyclopedia article “&quot;&gt;&lt;svg onload=alert(1)&gt;”')

    def test_encyclopedia_odd_argument_shapes(self):
        bad = {'toString': 'x'}
        got = self.text([
            {'name': 'search_encyclopedia', 'args': {'query': bad}, 'summary': {'count': 0}},
            {'name': 'read_encyclopedia', 'args': {'article': bad}, 'summary': {}},
            {'name': 'search_encyclopedia', 'args': 'not an object', 'summary': {'count': 0}},
        ])
        for t in got:
            self.assertFalse(t.startswith('THROW'), t)
            self.assertNotIn('<', t)
        self.assertEqual(got[0], 'Searched the encyclopedias for “” — 0 articles')
        self.assertEqual(got[1], 'Read the encyclopedia article “”')
        self.assertEqual(got[2], 'Searched the encyclopedias for “” — 0 articles')


# patchStream, which keeps a message's parts in place while its answer is written. The whole of chat.js runs, with app.js's
# helpers and a DOM made of just the calls patchStream uses. Every innerHTML write is counted, and every element made gets
# a number, so a test can tell an element that stayed from one put back in its place.
STREAM = r"""
const fs = require('fs');
const chat = fs.readFileSync(process.argv[1], 'utf8'), app = fs.readFileSync(process.argv[2], 'utf8');
const line = re => app.split('\n').find(l => re.test(l));
let made = 0;
class El {
  constructor(tag) { this.tag = tag; this.id = ++made; this.children = []; this.parent = null; this.className = ''; this.style = {}; this.attrs = {}; this.html = ''; this.writes = 0; this.text = '' }
  get ownerDocument() { return doc }
  get classList() { const el = this, has = c => el.className.split(' ').includes(c);
    return { contains: has, toggle(c, on) { if (on === undefined) on = !has(c); const k = el.className.split(' ').filter(x => x && x !== c); if (on) k.push(c); el.className = k.join(' ') } } }
  set innerHTML(h) { this.html = h; this.writes++ } get innerHTML() { return this.html }
  set textContent(t) { this.text = t }
  setAttribute(k, v) { this.attrs[k] = v }
  append(...ns) { for (const n of ns) { n.parent = this; this.children.push(n) } }
  prepend(n) { n.parent = this; this.children.unshift(n) }
  after(n) { const s = this.parent.children; n.parent = this.parent; s.splice(s.indexOf(this) + 1, 0, n) }
  remove() { const s = this.parent.children; s.splice(s.indexOf(this), 1); this.parent = null }
}
const doc = { createElement: t => new El(t) };
const stubs = [line(/^const esc\s*=/), line(/^const fileUrl\s*=/), "const ico = n => '<svg>' + n + '</svg>';", 'const clock = t => String(t);',
  "const here = () => '#/ask';", 'const localStorage = { getItem: () => null, setItem() {} };', 'const addEventListener = () => {};'].join('\n');
const src = chat.replace('return { page, count };', 'return { page, count, patchStream };');
if (src === chat) throw new Error('chat.js no longer ends with return { page, count }');
const { patchStream } = new Function(stubs + '\n' + src + '\nreturn Chat;')();
// Each step: a change to the message, then one patch, then what the message holds.
const el = new El('div'), m = { role: 'assistant', content: '', state: 'thinking', steps: [], sources: [], running: true };
const seen = [];
for (const change of JSON.parse(process.argv[3])) {
  Object.assign(m, change);
  patchStream(el, m);
  const part = c => el.children.find(n => n.classList.contains(c));
  const work = part('working'), stages = work.children.find(n => n.classList.contains('wk-stages')), bar = work.children.find(n => n.classList.contains('wk-bar'));
  const steps = work.children.find(n => n.classList.contains('steps'));
  seen.push({ order: el.children.map(n => n.className), label: work.children[0].html, stages: stages.children.map(li => li.className),
    stageIds: [stages.id, ...stages.children.map(li => li.id)], bar: [bar.id, bar.className, bar.children[0].style.width],
    steps: steps ? steps.html : null, answer: part('answer') ? part('answer').html : null,
    found: part('prefound') ? [part('prefound').id, part('prefound').writes, part('prefound').html] : null });
}
process.stdout.write(JSON.stringify(seen));
"""


@unittest.skipUnless(NODE, 'needs Node')
class Streaming(unittest.TestCase):
    def run_steps(self, changes):
        r = subprocess.run([NODE, '-e', STREAM, str(ROOT / 'web/chat.js'), str(ROOT / 'web/app.js'), json.dumps(changes)],
                           capture_output=True, text=True, check=True, encoding='utf-8')
        return json.loads(r.stdout)

    PAGE = {'kind': 'pdf', 'key': 'S1', 'title': 'Water treatment', 'doc_id': 'w', 'page': 12}
    VIDEO = {'kind': 'video', 'key': 'S2', 'title': 'Boiling water', 'doc_id': 'v', 't': 30}

    def test_sources_stay_put_while_the_answer_is_written(self):
        steps = [{'state': 'searching', 'steps': [{'name': 'found', 'count': 2}]},
                 {'sources': [self.PAGE, self.VIDEO]},
                 {'state': 'writing', 'content': 'Boil'}]
        steps += [{'content': 'Boil water ' + 'for one minute ' * n + '[S1].'} for n in range(1, 30)]
        seen = self.run_steps(steps)
        first = seen[1]['found']
        self.assertIsNotNone(first)
        for s in seen[1:]:
            self.assertEqual(s['found'], first)   # the same element, written once: its thumbnails never load again
        self.assertIn('/api/page/w/12.png', first[2])
        self.assertIn('for one minute ' * 29, seen[-1]['answer'])
        self.assertIn('class="cite"', seen[-1]['answer'])
        self.assertEqual(seen[-1]['order'], ['working', 'answer', 'prefound'])

    def test_the_progress_parts_are_kept_and_only_their_classes_change(self):
        seen = self.run_steps([{'state': 'thinking'}, {'state': 'searching'}, {'state': 'reading'}, {'state': 'writing', 'content': 'x'},
                               {'content': 'xy'}, {'content': 'xyz'}])
        self.assertEqual(len({json.dumps(s['stageIds']) for s in seen}), 1)   # the list and its three steps are never replaced
        self.assertEqual(len({s['bar'][0] for s in seen}), 1)
        self.assertEqual([s['stages'] for s in seen[:4]], [['now', '', ''], ['now', '', ''], ['done', 'now', ''], ['done', 'done', 'now']])
        self.assertEqual([s['label'] for s in seen[:4]], ['Thinking…', 'Searching the library…', 'Reading the pages it found…', 'Writing the answer…'])
        for s in seen:
            self.assertEqual(s['bar'][1:], ['wk-bar run', ''])   # no figure: the bar keeps sweeping

    def test_loading_the_local_ai_shows_how_far(self):
        seen = self.run_steps([{'state': 'starting', 'pct': 40}, {'pct': 75}, {'state': 'thinking', 'pct': None}])
        self.assertEqual([s['bar'][1:] for s in seen], [['wk-bar', '40%'], ['wk-bar', '75%'], ['wk-bar run', '']])
        self.assertEqual(seen[0]['label'], 'Starting the local AI… 40%')
        self.assertEqual(seen[0]['stages'], ['', '', ''])

    def test_a_reset_clears_the_draft_and_keeps_the_sources(self):
        # The model writes a little, then calls a tool: the server sends reset, and the draft must go while the tool runs.
        seen = self.run_steps([
            {'sources': [self.PAGE]},
            {'state': 'writing', 'content': 'Let me check the library first.'},
            {'content': ''},                                                                        # reset
            {'state': 'searching', 'steps': [{'name': 'search_library', 'args': {'query': 'boil'}}]},  # waiting for the tool
            {'steps': [{'name': 'search_library', 'args': {'query': 'boil'}, 'summary': {'count': 4}}]},
            {'sources': [self.PAGE, self.VIDEO]},
            {'state': 'writing', 'content': 'Boil it [S2].'},
        ])
        self.assertIn('Let me check', seen[1]['answer'])
        for s in seen[2:6]:
            self.assertIsNone(s['answer'], s)
            self.assertEqual(s['order'], ['working', 'prefound'])
        self.assertIn('Searched “boil” — …', seen[3]['steps'])
        self.assertIn('Searched “boil” — 4 passages', seen[4]['steps'])
        self.assertEqual(seen[4]['found'], seen[0]['found'])            # nothing new found yet: untouched
        self.assertEqual(seen[5]['found'][0], seen[0]['found'][0])      # a new page: the same element, written again
        self.assertEqual(seen[5]['found'][1], 2)
        self.assertIn('Boiling water', seen[5]['found'][2])
        self.assertEqual(seen[6]['order'], ['working', 'answer', 'prefound'])   # the answer comes back above the sources
        self.assertNotIn('Let me check', seen[6]['answer'])

    def test_model_text_is_escaped(self):
        seen = self.run_steps([{'state': 'writing', 'content': '<img src=x onerror=alert(1)> **bold**',
                                'steps': [{'name': 'search_library', 'args': {'query': '<b>q</b>'}}]}])
        self.assertNotIn('<img', seen[0]['answer'])
        self.assertIn('<strong>bold</strong>', seen[0]['answer'])
        self.assertNotIn('<b>q', seen[0]['steps'])


# Article names straight from a ZIM file: a ? would cut the address, a bare % makes decodeURIComponent throw, a " would end the attribute.
ODD_ARTICLES = ('Why?', '100%_Juice', 'X"onmouseover="alert(1)')
ZIM = 'appropedia_en_all_maxi_2026-02.zim'


@unittest.skipUnless(NODE, 'needs Node')
class SourceCards(unittest.TestCase):
    def cards(self, rows):
        r = subprocess.run([NODE, '-e', CARDS, str(ROOT / 'web/chat.js'), str(ROOT / 'web/app.js'), json.dumps(rows)],
                           capture_output=True, text=True, check=True, encoding='utf-8')
        return json.loads(r.stdout)

    def check_link(self, card, article):
        p = Anchors()
        p.feed(card)
        self.assertEqual(len(p.anchors), 1, card)
        a = p.anchors[0]
        self.assertEqual(set(a), {'class', 'href', 'id'}, card)   # nothing like onmouseover got in
        href = a['href']
        self.assertTrue(href.startswith('#/wiki/'), href)
        # As app.js parse() reads it: the address ends at the first ?, then each part is decoded.
        path, _, qs = href[1:].partition('?')
        self.assertTrue(qs.startswith('from='), href)
        self.assertIsNone(re.search(r'%(?![0-9A-Fa-f]{2})', path), href)   # decodeURIComponent would throw
        parts = [urllib.parse.unquote(x, errors='strict') for x in path.split('/') if x]
        self.assertEqual(parts, ['wiki', ZIM, article])

    def test_encyclopedia_card_links_use_the_encoded_path(self):
        rows = [{'kind': 'zim', 'key': f'S{n}', 'title': t, 'zim': f'zim/{ZIM}/{t}', 'doc_id': f'zim/{ZIM}/{t}',
                 # as encyclopedias.ui_path makes it, which the search hit and wiki_row carry
                 'path': 'zim/' + urllib.parse.quote(ZIM) + '/' + urllib.parse.quote(t, safe='/'),
                 'publisher': 'Appropedia', 'trust': 'Community-written encyclopedia', 'excerpt': 'x'}
                for n, t in enumerate(ODD_ARTICLES, 1)]
        for card, t in zip(self.cards(rows), ODD_ARTICLES):
            self.check_link(card, t)
            self.assertNotIn('onmouseover="', card)

    def test_a_row_without_a_path_is_encoded_from_its_key(self):
        rows = [{'kind': 'zim', 'key': 'S1', 'title': t, 'zim': f'zim/{ZIM}/{t}', 'doc_id': f'zim/{ZIM}/{t}'} for t in ODD_ARTICLES]
        for card, t in zip(self.cards(rows), ODD_ARTICLES):
            self.check_link(card, t)

    def test_other_cards_keep_their_links(self):
        got = self.cards([{'kind': 'pdf', 'key': 'S1', 'title': 'FEMA', 'doc_id': 'fema water', 'page': 3},
                          {'kind': 'place', 'key': 'M1', 'title': 'Clinic "A"', 'lat': 1.5, 'lon': 2.5}])
        p = Anchors()
        p.feed(got[0] + got[1])
        self.assertEqual(p.anchors[0]['href'], '#/read/fema%20water?p=3&from=%23%2Fask')
        self.assertEqual(p.anchors[1]['href'], '#/map?lat=1.5&lon=2.5&z=16&pin=Clinic%20%22A%22')


if __name__ == '__main__':
    unittest.main()
