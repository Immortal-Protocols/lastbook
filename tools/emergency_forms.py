#!/usr/bin/env python3
"""Two offline web pages for the emergency-number tables in content/emergency/ (format: content/emergency/SCHEMA.md).

  python3 tools/emergency_forms.py [output folder]        (default: build/emergency/, which git ignores)

  review.html  reads every content/emergency/*.json and shows each number as a card. Every field has a selector,
               "approved" or "comment"; a button turns the comments into one block of text to paste into a review.
               Each card also shows what the test says about it.
  coverage.html  a table of countries: the languages each speaks (tools/emergency_languages.json, from Wikipedia's list of
               official languages), the languages the tables cover, and how many numbers. A picker says "for your country we
               have ... in these languages", or that the country is not covered yet.
  submit.html  an empty entry form for a completely new country. It states the rules the test checks, checks the entry
               as it is typed, and gives the finished <CC>.json to copy or download.

The rules are not written twice by hand: the lists and patterns come from app/tests/test_emergency_numbers.py, and
app/tests/test_emergency_forms.py runs the page's checker (in Node, when it is installed) against the real files and
against the test's own checker on broken rows, so the two cannot drift apart. The pages load nothing from the network and
send nothing anywhere; they are plain files you open in a browser."""
import html, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT)]
sys.dont_write_bytecode = True
from app.tests import test_emergency_numbers as rules  # noqa: E402  (the one place the rules live)

DATA = ROOT / 'content' / 'emergency'
e = html.escape
UNKNOWN = '<span class="unk">unknown</span>'


def rules_json():
    """The test's lists and patterns, for the page's own checker."""
    return {
        'kinds': sorted(rules.KINDS), 'how': sorted(rules.HOW), 'worksFrom': sorted(rules.WORKS_FROM),
        'verified': sorted(rules.VERIFIED), 'countryKeys': sorted(rules.COUNTRY_KEYS), 'serviceKeys': sorted(rules.SERVICE_KEYS),
        'number': rules.NUMBER.pattern, 'callingCode': rules.CALLING_CODE.pattern, 'source': rules.SOURCE.pattern,
        'lang': rules.LANG.pattern, 'maxLanguages': rules.MAX_LANGUAGES,
    }


# The page's checker: the same checks as problems() in the test, in JavaScript. Used by submit.html as you type, and by
# app/tests/test_emergency_forms.py in Node to prove it gives the same verdict as the test.
JS_VALIDATOR = r'''
function validate(data, name, latest) {
  const R = RULES, out = [];
  const isStr = x => typeof x === 'string';
  const isObj = x => x !== null && typeof x === 'object' && !Array.isArray(x);
  const src = x => isStr(x) && new RegExp(R.source).test(x);
  const lang = c => isStr(c) && new RegExp('^(?:' + R.lang + ')$').test(c);
  const words = x => Array.isArray(x) && x.length > 0 && x.every(w => isStr(w) && w.trim() !== '' && w === w.toLowerCase());
  const subset = (a, b) => a.every(x => b.includes(x));
  if (!isObj(data)) return [name + ': the file must hold one object'];
  const has = (o, k) => Object.prototype.hasOwnProperty.call(o, k);
  const set = (o, k) => has(o, k) && o[k] !== null && o[k] !== undefined;
  const code = name.endsWith('.json') ? name.slice(0, -5) : name;
  if (!/^[A-Z]{2}$/.test(code)) out.push(name + ': the file name must be the two-letter country code in capitals, such as CL.json');
  for (const k of Object.keys(data).sort()) if (!R.countryKeys.includes(k)) out.push(name + ': unknown key "' + k + '"');
  if (data.code !== code) out.push(name + ': "code" is ' + JSON.stringify(data.code) + ', but the file name says "' + code + '"');
  if (!isStr(data.country) || !data.country.trim()) out.push(name + ': "country" is missing');
  if (!isStr(data.calling_code) || !new RegExp(R.callingCode).test(data.calling_code)) out.push(name + ': "calling_code" must be + and one to three digits, such as +56 (type the digits only: the + is added for you)');
  const langs = data.languages;
  const langsOk = Array.isArray(langs) && langs.length > 0 && langs.every(lang) && new Set(langs).size === langs.length && langs.length <= R.maxLanguages;
  if (!langsOk) out.push(name + ': "languages" is required: each one a two-letter ISO 639-1 code in lower-case letters, such as ["es"], with no region and no 3-letter code, each listed once, at most ' + R.maxLanguages);
  const services = data.services;
  if (!Array.isArray(services) || services.length === 0) return out.concat([name + ': "services" must list at least one number']);
  const numbers = new Set();
  services.forEach((s, i) => {
    const who = name + ' services[' + i + '] (' + (isObj(s) && s.name != null ? s.name : '?') + ')';
    if (!isObj(s)) { out.push(who + ': not an object'); return; }
    if (!R.kinds.includes(s.kind)) out.push(who + ': "kind" is not one of ' + R.kinds.join(', '));
    if (!isStr(s.name) || !s.name.trim()) out.push(who + ': "name" is missing');
    const n = s.number;
    if (!isStr(n) || !new RegExp(R.number).test(n)) out.push(who + ': "number" must be digits and spaces only (a leading + or * is allowed)');
    else if (numbers.has(n)) out.push(who + ': "number" ' + n + ' is listed twice in this file');
    else numbers.add(n);
    if (!Array.isArray(s.how) || s.how.length === 0 || !subset(s.how, R.how)) out.push(who + ': "how" must be a non-empty list from ' + R.how.join(', '));
    if (!Array.isArray(s.works_from) || !subset(s.works_from, R.worksFrom)) out.push(who + ': "works_from" must be a list from ' + R.worksFrom.join(', ') + ', empty if the source does not say');
    const k = s.keywords;
    if (!isObj(k) || Object.keys(k).length === 0 || !Object.entries(k).every(([c, w]) => isStr(c) && words(w))) out.push(who + ': "keywords" must map language codes to non-empty lower-case word lists');
    else if (langsOk) {
      const want = new Set(langs.concat(['en']));
      if (want.size !== Object.keys(k).length || !Object.keys(k).every(c => want.has(c))) out.push(who + ': "keywords" must have exactly the country\'s languages plus "en"');
    }
    for (const key of Object.keys(s).sort()) if (!R.serviceKeys.includes(key)) out.push(who + ': unknown key "' + key + '"');
    if (has(s, 'area_whole_country') && typeof s.area_whole_country !== 'boolean') out.push(who + ': "area_whole_country" must be true or false');
    if (has(s, 'area') && (!isStr(s.area) || !s.area.trim())) out.push(who + ': "area" must be the specific place the number covers');
    else if (has(s, 'area') && s.area_whole_country === true) out.push(who + ': "area_whole_country" is true, so there is no specific "area"');
    if (has(s, 'url') && !src(s.url)) out.push(who + ': "url" must be the web address of the service\'s own page');
    const wf = Array.isArray(s.works_from) ? s.works_from : [];
    if (wf.length > 0 && !src(s.works_from_source)) out.push(who + ': "works_from" is listed, so "works_from_source" must be a web address');
    if (wf.length === 0 && set(s, 'works_from_source')) out.push(who + ': "works_from" is empty (unknown), so leave "works_from_source" out');
    if (!has(s, 'free') || ![true, false, null].includes(s.free)) out.push(who + ': "free" must be true, false or null');
    else if (s.free !== null && !src(s.free_source)) out.push(who + ': "free" is set, so "free_source" must be a web address');
    else if (s.free === null && set(s, 'free_source')) out.push(who + ': "free" is null (unknown), so leave "free_source" out');
    if (!isStr(s.when)) out.push(who + ': "when" must be a string');
    if (!(src(s.source) || (Array.isArray(s.source) && s.source.length > 0 && s.source.every(src)))) out.push(who + ': "source" must be a web address, or a list of them');
    const c = s.checked_on;
    const when = isStr(c) && /^\d{4}-\d{2}-\d{2}$/.test(c) ? new Date(c + 'T00:00:00Z') : null;
    if (!when || isNaN(when.getTime()) || when.toISOString().slice(0, 10) !== c) out.push(who + ': "checked_on" must be a date as YYYY-MM-DD');
    else if (c > latest) out.push(who + ': "checked_on" ' + c + ' is after the last allowed day, ' + latest);
    if (!R.verified.includes(s.verified)) out.push(who + ': "verified" must be one of ' + R.verified.join(', '));
  });
  const g = data.general;
  if (g !== undefined && g !== null && !numbers.has(g)) out.push(name + ': "general" is ' + JSON.stringify(g) + ', which is not the number of any service');
  return out;
}
function latestAllowedDate(now) { return new Date((now == null ? Date.now() : now) + 14 * 3600 * 1000).toISOString().slice(0, 10); }
'''


def validator_script():
    """The checker with its rules, ready to run (browser or Node)."""
    return 'const RULES = ' + json.dumps(rules_json()) + ';\n' + JS_VALIDATOR


CSS = r'''
body{font:15px/1.45 system-ui,sans-serif;max-width:64rem;margin:2rem auto;padding:0 1rem;color:#1b1b1b}
h2 small{font-weight:400;color:#555;font-size:.65em} .card{border:1px solid #ccc;border-radius:8px;margin:1rem 0;padding:.5rem 1rem}
.idx{color:#888} table{border-collapse:collapse;width:100%} th{text-align:left;width:10rem;color:#555;font-weight:500;vertical-align:top;padding:.2rem .5rem .2rem 0}
td{padding:.2rem 0;word-break:break-word;vertical-align:top} td.rv{width:14rem;padding-left:.7rem} td.rv select{font-size:.85em} td.rv textarea{width:100%;box-sizing:border-box;margin-top:.2rem;min-height:3.2rem}
tr.flag{background:#fff6d8} tr.flag th{color:#7a5a00;font-weight:700}
.num{font-size:1.3em} .chip{background:#eef;border-radius:4px;padding:0 .4rem;margin-right:.2rem}
.unk{color:#a60;font-style:italic} tr.src a{font-size:.85em} .v{padding:0 .4rem;border-radius:4px} .official{background:#dfd} .found_online{background:#fed}
.bad{color:#a00} .good{color:#060} ul.problems{margin:.3rem 0;padding-left:1.2rem}
#bar{position:sticky;top:0;background:#fffe;border-bottom:1px solid #ccc;padding:.4rem 0;z-index:2} button{font:inherit;padding:.3rem .8rem;margin-right:.4rem}
#fmt{width:100%;box-sizing:border-box;min-height:14rem;font:13px/1.4 ui-monospace,monospace}
label{display:block;margin:.5rem 0} label small,.fld small{display:block;color:#666} .inl{display:inline-block;margin-right:1rem}
.pre{display:flex;align-items:center;gap:.3rem}.pre b{font-size:1.2em}.pre input{flex:1}
.switch{display:inline-flex;border:1px solid #888;border-radius:999px;overflow:hidden;margin:.2rem 0}
.switch label{margin:0;position:relative}.switch input{position:absolute;opacity:0;pointer-events:none}.switch span{display:block;padding:.2rem .9rem;cursor:pointer;background:#f3f3f3;color:#333}
.switch input:checked+span{background:#1f6f43;color:#fff}.switch input:focus-visible+span{outline:2px solid #06c;outline-offset:-2px}
input[type=text],textarea,select{width:100%;box-sizing:border-box;font:inherit} .fld{margin:.6rem 0}
fieldset{border:1px solid #bbb;border-radius:8px;margin:1rem 0;padding:.5rem 1rem} legend{font-weight:600}
.rules{background:#f6f6fb;border-radius:8px;padding:.5rem 1rem} .rules li{margin:.25rem 0}
#problems{position:sticky;bottom:0;background:#fffe;border-top:1px solid #ccc;padding:.4rem 0}
details.country>summary{cursor:pointer;list-style:none} details.country>summary::-webkit-details-marker{display:none}
details.country>summary h2{display:inline-block;margin:.6rem 0} details.country>summary::before{content:'\25B6';font-size:.8em;margin-right:.4rem;color:#555}
details.country[open]>summary::before{content:'\25BC'}
pre#json{background:#f4f4f4;padding:.7rem;border-radius:6px;overflow:auto;max-height:28rem}
'''


# ---------------------------------------------------------------- review.html

def link(u):
    return f'<a href="{e(u)}">{e(u)}</a>' if u else UNKNOWN


def chips(items):
    return ' '.join(f'<span class="chip">{e(x)}</span>' for x in items) if items else UNKNOWN


def plain(v):
    if isinstance(v, list):
        return ', '.join(v) if v else '(empty)'
    if isinstance(v, str):
        return v or '(empty)'
    return {True: 'yes', False: 'no', None: 'unknown'}.get(v, str(v))


class Card:
    def __init__(self, code, s):
        self.code, self.s, self.rows = code, s, []

    def row(self, label, value_html, raw, cls=''):
        rid = f'{self.code}|{self.s["number"]}|{label}'
        ctl = (f'<select data-id="{e(rid)}"><option value="ok">approved</option><option value="c">comment</option></select>'
               f'<textarea data-id="{e(rid)}" placeholder="comment" hidden></textarea>')
        self.rows.append(
            f'<tr class="{cls}" data-row="{e(rid)}" data-card="{e(self.code)} {e(self.s["number"])} {e(self.s["name"])}" '
            f'data-label="{e(label)}" data-val="{e(plain(raw))}"><th>{e(label)}</th><td>{value_html}</td><td class="rv">{ctl}</td></tr>')


def card(code, i, s, problems):
    c = Card(code, s)
    free = {True: 'yes', False: 'no', None: None}[s.get('free')]
    c.row('kind', e(s['kind']), s['kind'])
    c.row('number', f'<b class="num">{e(s["number"])}</b>', s['number'])
    c.row('how', chips(s['how']), s['how'])
    c.row('works_from', chips(s['works_from']), s['works_from'])
    c.row('works_from_source', link(s.get('works_from_source')), s.get('works_from_source'), 'src')
    c.row('free', e(free) if free else UNKNOWN, s.get('free'))
    c.row('free_source', link(s.get('free_source')), s.get('free_source'), 'src')
    for lang, words in s['keywords'].items():
        c.row(f'keywords ({lang})', chips(words), words)
    c.row('when', e(s['when']) or UNKNOWN, s['when'])
    srcs = s['source'] if isinstance(s.get('source'), list) else [s.get('source')]
    c.row('source', '<br>'.join(link(x) for x in srcs), ', '.join(x or '' for x in srcs), 'src')
    c.row('url', link(s.get('url')) if s.get('url') else '<span class="unk">not set (optional)</span>', s.get('url') or '(not set)')
    awc = s.get('area_whole_country')
    c.row('area_whole_country', e({True: 'yes', False: 'no'}[awc]) if awc is not None else '<span class="unk">not set (optional)</span>',
          'yes' if awc else 'no' if awc is False else '(not set)')
    c.row('area', e(s['area']) if s.get('area') else '<span class="unk">not set (optional)</span>', s.get('area') or '(not set)')
    c.row('checked_on', e(s['checked_on']), s['checked_on'])
    c.row('verified', f'<span class="v {e(s["verified"])}">{e(s["verified"])}</span>', s['verified'])
    status = ('<p class="good">The test finds nothing wrong with this entry.</p>' if not problems else
              '<p class="bad">The test fails on this entry:</p><ul class="problems">' + ''.join(f'<li>{e(p)}</li>' for p in problems) + '</ul>')
    return (f'<section class="card"><h3><span class="idx">{i}</span> {e(s["name"])}</h3>{status}'
            f'<table>{"".join(c.rows)}</table></section>')


REVIEW_JS = r'''
const KEY = 'emergency-review-v2';
let state = {};
try { state = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) {}
const rows = [...document.querySelectorAll('tr[data-row]')];
function save() { try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) {} }
function paint(tr) {
  const st = state[tr.dataset.row] || { v: 'ok', t: '' };
  const sel = tr.querySelector('select'), ta = tr.querySelector('textarea');
  sel.value = st.v; ta.value = st.t; ta.hidden = st.v !== 'c';
  tr.classList.toggle('flag', st.v === 'c');
}
function count() {
  const n = rows.filter(r => (state[r.dataset.row] || {}).v === 'c').length;
  document.getElementById('count').textContent = n + ' comment' + (n === 1 ? '' : 's') + ' of ' + rows.length + ' rows; the rest approved';
}
rows.forEach(tr => {
  paint(tr);
  tr.querySelector('select').addEventListener('change', ev => {
    const id = tr.dataset.row; state[id] = state[id] || { v: 'ok', t: '' };
    state[id].v = ev.target.value; save(); paint(tr); count();
    if (state[id].v === 'c') tr.querySelector('textarea').focus();
  });
  tr.querySelector('textarea').addEventListener('input', ev => {
    const id = tr.dataset.row; state[id] = state[id] || { v: 'c', t: '' };
    state[id].t = ev.target.value; save();
  });
});
count();
function format() {
  const flagged = rows.filter(r => (state[r.dataset.row] || {}).v === 'c');
  const lines = ['Hand review of content/emergency (from the review page)',
    flagged.length + ' comment(s) on ' + rows.length + ' rows. Every row not listed is APPROVED as it is.', ''];
  let last = '';
  flagged.forEach(r => {
    if (r.dataset.card !== last) { last = r.dataset.card; lines.push('## ' + last); }
    const t = (state[r.dataset.row].t || '').trim() || '(no text: look at this row)';
    lines.push('- ' + r.dataset.label + ' [now: ' + r.dataset.val + ']: ' + t);
  });
  if (!flagged.length) lines.push('Nothing to change: all rows approved.');
  const out = document.getElementById('fmt'); out.value = lines.join('\n'); out.select();
}
document.getElementById('format').onclick = format;
document.getElementById('expand').onclick = () => document.querySelectorAll('details.country').forEach(d => d.open = true);
document.getElementById('collapse').onclick = () => document.querySelectorAll('details.country').forEach(d => d.open = false);
document.getElementById('copy').onclick = () => { format(); try { navigator.clipboard.writeText(document.getElementById('fmt').value); } catch (e) { document.execCommand('copy'); } };
document.getElementById('reset').onclick = () => { if (confirm('Approve every row and clear all comments?')) { state = {}; save(); rows.forEach(paint); count(); } };
'''


def build_review(data_dir=DATA):
    parts = []
    files = sorted(Path(data_dir).glob('*.json'))
    for p in files:
        d = json.loads(p.read_text(encoding='utf-8'))
        found = rules.problems(d, p.name, latest=rules.REFERENCE_DATE)
        country = [x for x in found if ' services[' not in x]
        bad = f' · <span class="bad">{len(found)} problem(s)</span>' if found else ''
        inner = []
        if country:
            inner.append('<p class="bad">The test fails on this country:</p><ul class="problems">' + ''.join(f'<li>{e(x)}</li>' for x in country) + '</ul>')
        for i, s in enumerate(d['services']):
            mine = [x for x in found if f' services[{i}] (' in x]
            inner.append(card(d['code'], i, s, mine))
        # A country is a section you can fold away. Open by default while the list is short; a long list starts folded
        # (a country with a problem is always open, so it is not missed).
        opened = ' open' if len(files) <= 3 or found else ''
        parts.append(f'<details class="country"{opened}><summary><h2>{e(d["country"])} <small>{e(d["code"])} · {e(d["calling_code"])} · '
                     f'languages: {e(", ".join(d.get("languages", [])))} · general: {e(str(d["general"])) if d["general"] else "none recorded"} · '
                     f'{len(d["services"])} numbers{bad}</small></h2></summary>{"".join(inner)}</details>')
    return f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Emergency numbers: review</title>
<style>{CSS}</style>
<div id="bar"><b>Review</b> &nbsp; <span id="count"></span> &nbsp; <button id="expand">Expand all</button><button id="collapse">Collapse all</button> <a href="#end">go to the format button</a></div>
<h1>Emergency numbers: check what is already there</h1>
<p>Built from <code>content/emergency/*.json</code>. Every row starts as <b>approved</b>; pick <b>comment</b> to write what is wrong. Your choices stay in this browser. Orange italic <span class="unk">unknown</span> = empty or null by design. The line under each title is what <code>app/tests/test_emergency_numbers.py</code> says about that entry. For a new country, use <code>submit.html</code>. This page loads nothing from the network.</p>
{''.join(parts)}
<h2 id="end">Format the review</h2>
<p><button id="format">Format for Claude</button><button id="copy">Format and copy</button><button id="reset">Approve all / clear</button></p>
<textarea id="fmt" placeholder="The formatted review appears here: paste it back to the session."></textarea>
<script>{REVIEW_JS}</script>
</html>'''


# ---------------------------------------------------------------- submit.html

def rule_list():
    r = rules_json()
    q = lambda xs: ', '.join(f'<code>{e(x)}</code>' for x in xs)
    return [
        'One file per country, named with the ISO 3166-1 alpha-2 code in capitals (<code>CL.json</code>); <code>code</code> is the same two letters.',
        'The calling code is <code>+</code> and 1 to 3 digits (digits only: the page adds the <code>+</code>).',
        '<code>languages</code> is required: the country\'s main languages as two-letter ISO 639-1 codes (<code>es</code>, <code>qu</code>; never <code>es-cl</code>, never a three-letter code, letters only), each once, up to 4 main languages.',
        'At least one service. <code>general</code> is the number of one of the services, or the box "no general number" is ticked.',
        f'<code>kind</code> is one of {q(r["kinds"])}. <code>name</code> is not empty.',
        '<code>number</code> is digits and spaces, with an optional leading <code>+</code> or <code>*</code>, and is not listed twice in the file.',
        f'<code>how</code>: one or more of {q(r["how"])}. <code>works_from</code>: any of {q(r["worksFrom"])}, or none when no source says.',
        'Each claim has its own source: if <code>works_from</code> is not empty, <code>works_from_source</code> is a web address; if it is empty, there is none. The same for <code>free</code> and <code>free_source</code> (yes or no needs one, unknown has none).',
        '<code>keywords</code>: one non-empty, lower-case list for every language in <code>languages</code>, plus <code>en</code>, no more and no fewer.',
        '<code>when</code> is text (it may be empty) and says only what the cited pages say.',
        '<code>source</code> is a web address, or several, of the page the number and name were read from. <code>url</code> is optional: the service\'s own page.',
        '<code>area_whole_country</code> (yes or no) and <code>area</code> (a specific place) are optional; <code>area</code> is not set when the whole country is yes.',
        f'<code>checked_on</code> is <code>YYYY-MM-DD</code>, the day you read it, and not after the last allowed day (today in UTC+14). <code>verified</code> is {q(r["verified"])}.',
        'Any other key fails, so a typo such as <code>works_form</code> is caught.',
    ]


SUBMIT_JS = r'''
const $ = (s, el) => (el || document).querySelector(s);
const K = JSON.parse(document.getElementById('known').textContent);
const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;');
const $$ = (s, el) => [...(el || document).querySelectorAll(s)];
const todayLocal = () => { const d = new Date(); return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0'); };
const ORDER = ['kind', 'name', 'number', 'how', 'works_from', 'works_from_source', 'free', 'free_source', 'keywords', 'when', 'source', 'url', 'area_whole_country', 'area', 'checked_on', 'verified'];
const checks = (list, name, opts, cls) => opts.map(o => '<label class="inl"><input type="checkbox" class="' + cls + '" value="' + o + '"> ' + o + '</label>').join('');
// A switch of 2 or 3 positions with none selected: the person must pick one, and an unanswered switch is a problem.
const radios = (name, opts) => '<span class="switch" role="radiogroup">' + opts.map(o => '<label><input type="radio" name="' + name + '" value="' + o[0] + '"><span>' + o[1] + '</span></label>').join('') + '</span>';
const picked = (b, prefix) => { const r = $$('input[type=radio]', b).find(x => x.name.startsWith(prefix) && x.checked); return r ? r.value : null; };
let counter = 0;

function languages() { return $('#languages').value.split(',').map(s => s.trim()).filter(Boolean); }
function keywordLangs() { const l = languages(); return l.includes('en') ? l : l.concat(['en']); }

function addService() {
  const id = ++counter, box = document.createElement('fieldset');
  box.className = 'svc';
  box.innerHTML =
    '<legend>Service <span class="n"></span> <button type="button" class="rm">remove</button></legend>' +
    '<label>kind<select class="kind"><option value="" selected>choose one…</option>' + RULES.kinds.map(k => '<option>' + k + '</option>').join('') + '</select></label>' +
    '<label>name <small>what it is called locally</small><input type="text" class="name"></label>' +
    '<label>number <small>digits and spaces; a leading + or * is allowed</small><input type="text" class="number"></label>' +
    '<div class="fld"><b>how</b> <small>one or more</small>' + checks(0, 0, RULES.how, 'how') + '</div>' +
    '<div class="fld"><b>works_from</b> <small>tick what a source says, or tick "unknown" when none does</small>' + checks(0, 0, ['mobile', 'landline', 'voip'].filter(x => RULES.worksFrom.includes(x)).concat(RULES.worksFrom.filter(x => !['mobile', 'landline', 'voip'].includes(x))), 'wf') + '<label class="inl"><input type="checkbox" class="wfunk"> unknown (no source says)</label></div>' +
    '<label class="wfs">works_from_source <small>the page that says it (only when works_from is not empty)</small><input type="text" class="wfsrc"></label>' +
    '<div class="fld"><b>free</b> <small>does it cost money, both the call and the service? Free only if both are free; only if a source says</small>' + radios('free' + id, [['yes', 'free'], ['no', 'not free'], ['unknown', 'unknown']]) + '</div>' +
    '<label class="frs">free_source <small>the page that says it (only when free is set)</small><input type="text" class="frsrc"></label>' +
    '<div class="fld kw"><b>keywords</b> <small>one box for every language of the country, plus en; separated by commas, lower case</small><div class="kwbox"></div></div>' +
    '<label>when <small>only what the cited pages say; may be empty</small><textarea class="when"></textarea></label>' +
    '<label>source <small>the page(s) the number and name were read from, one address per line</small><textarea class="source"></textarea></label>' +
    '<label>url <small>optional: the service\'s own page</small><input type="text" class="url"></label>' +
    '<div class="fld"><b>area_whole_country</b> <small>optional, only if a source says</small>' + radios('awc' + id, [['yes', 'yes'], ['no', 'no'], ['', 'not stated']]) + '</div>' +
    '<label>area <small>optional: the specific place it covers (not when the whole country is yes)</small><input type="text" class="area"></label>' +
    '<label>checked_on <small>YYYY-MM-DD, the day you read the pages</small><input type="text" class="checked" placeholder="' + todayLocal() + '"></label>' +
    '<label>verified <small>official = seen on an official page; choose it yourself</small><select class="verified"><option value="" selected>choose one…</option>' + RULES.verified.map(k => '<option>' + k + '</option>').join('') + '</select></label>';
  box._kw = {};
  box.querySelector('.rm').onclick = () => { box.remove(); renumber(); refresh(); };
  $('#services').appendChild(box);
  renumber(); renderKeywords(box); refresh();
}
function renumber() { $$('.svc').forEach((b, i) => $('.n', b).textContent = i + 1); }
function renderKeywords(box) {
  const wrap = $('.kwbox', box);
  $$('textarea', wrap).forEach(t => box._kw[t.dataset.lang] = t.value);
  wrap.innerHTML = '';
  keywordLangs().forEach(c => {
    const l = document.createElement('label');
    l.innerHTML = c + '<textarea data-lang="' + c + '"></textarea>';
    const t = $('textarea', l); t.value = box._kw[c] || '';
    wrap.appendChild(l);
  });
}
function pick(b, prefix, v) { const r = $$('input[type=radio]', b).find(x => x.name.startsWith(prefix) && x.value === v); if (r) r.checked = true; }
function loadTable(code) {
  const t = K.tables[code]; if (!t) return;
  $('#country').value = t.country; $('#code').value = t.code; $('#calling').value = t.calling_code.replace(/^\+/, '');
  $('#languages').value = t.languages.join(', ');
  $('#nogeneral').checked = t.general === null; $('#general').value = t.general || '';
  $('#services').innerHTML = '';
  t.services.forEach(s => {
    addService(); const b = $$('.svc').pop();
    $('.kind', b).value = s.kind; $('.name', b).value = s.name; $('.number', b).value = s.number;
    $$('.how', b).forEach(x => { x.checked = s.how.includes(x.value); });
    if (s.works_from.length) $$('.wf', b).forEach(x => { x.checked = s.works_from.includes(x.value); }); else $('.wfunk', b).checked = true;
    $('.wfsrc', b).value = s.works_from_source || '';
    pick(b, 'free', s.free === true ? 'yes' : s.free === false ? 'no' : 'unknown'); $('.frsrc', b).value = s.free_source || '';
    renderKeywords(b); $$('.kwbox textarea', b).forEach(x => { x.value = (s.keywords[x.dataset.lang] || []).join(', '); });
    $('.when', b).value = s.when; $('.source', b).value = [].concat(s.source).join('\n'); $('.url', b).value = s.url || '';
    pick(b, 'awc', s.area_whole_country === true ? 'yes' : s.area_whole_country === false ? 'no' : ''); $('.area', b).value = s.area || '';
    $('.checked', b).value = s.checked_on; $('.verified', b).value = s.verified;
  });
  renumber(); refresh();
}
document.addEventListener('click', ev => { if (ev.target.id === 'loadtable') loadTable($('#code').value.trim()); });
const list = s => s.split(/[,\n]/).map(x => x.trim()).filter(Boolean);

function collect() {
  const langs = languages();
  const data = {
    country: $('#country').value.trim(), code: $('#code').value.trim(), calling_code: '+' + $('#calling').value.trim(),
    languages: langs, general: $('#nogeneral').checked ? null : ($('#general').value.trim() || null), services: []
  };
  $$('.svc').forEach(b => {
    const s = {};
    s.kind = $('.kind', b).value; s.name = $('.name', b).value.trim(); s.number = $('.number', b).value.trim();
    s.how = $$('.how:checked', b).map(x => x.value);
    s.works_from = $$('.wf:checked', b).map(x => x.value);
    if (s.works_from.length) s.works_from_source = $('.wfsrc', b).value.trim();
    const free = picked(b, 'free');
    if (free !== null) s.free = free === 'yes' ? true : free === 'no' ? false : null;
    if (s.free === true || s.free === false) s.free_source = $('.frsrc', b).value.trim();
    s.keywords = {};
    $$('.kwbox textarea', b).forEach(t => { s.keywords[t.dataset.lang] = list(t.value); });
    s.when = $('.when', b).value.trim();
    const srcs = $('.source', b).value.split('\n').map(x => x.trim()).filter(Boolean);
    s.source = srcs.length === 1 ? srcs[0] : srcs;
    const url = $('.url', b).value.trim(); if (url) s.url = url;
    const awc = picked(b, 'awc');
    if (awc === 'yes' || awc === 'no') s.area_whole_country = awc === 'yes';
    const area = $('.area', b).value.trim(); if (area) s.area = area;
    s.checked_on = $('.checked', b).value.trim(); s.verified = $('.verified', b).value;
    data.services.push(Object.fromEntries(ORDER.filter(k => k in s).map(k => [k, s[k]])));
  });
  return data;
}
function refresh() {
  $$('.svc').forEach(b => {
    const unk = $('.wfunk', b).checked;
    $$('.wf', b).forEach(x => { if (unk) x.checked = false; x.disabled = unk; });
    $('.wfs', b).style.display = $$('.wf:checked', b).length ? '' : 'none';
    const free = picked(b, 'free');
    $('.frs', b).style.display = free === 'yes' || free === 'no' ? '' : 'none';
  });
  const data = collect(), name = (data.code || 'XX') + '.json', latest = latestAllowedDate();
  const found = validate(data, name, latest);
  $$('.svc').forEach((b, i) => {
    const who = name + ' services[' + i + ']';
    if (!$('.kind', b).value) found.push(who + ': "kind" is not answered: choose one');
    if (!$('.verified', b).value) found.push(who + ': "verified" is not answered: choose official or found_online');
    if (!$('.wf:checked', b) && !$('.wfunk', b).checked) found.push(who + ': "works_from" is not answered: tick what a source says, or tick "unknown"');
    if (!$('.checked', b).value.trim()) found.push(who + ': "checked_on" is not answered: type the day you read the pages (YYYY-MM-DD)');
    if (picked(b, 'free') === null) found.push(who + ': "free" is not answered: switch it to free, not free or unknown');
    if (picked(b, 'awc') === null) found.push(who + ': "area_whole_country" is not answered: switch it to yes, no or not stated');
  });
  if (!$('#nogeneral').checked && !$('#general').value.trim()) found.push(name + ': "general" is not answered: type the number of the service that answers any emergency, or tick "no general number"');
  $('#general').disabled = $('#nogeneral').checked;
  const warn = [], code = data.code;
  const table = K.tables[code], ex = $('#existing');
  if (table) {
    const mine = new Set(data.services.map(s => s.number)), lost = table.services.map(s => s.number).filter(n => !mine.has(n));
    if (lost.length) found.push(name + ': this file would drop ' + lost.join(', ') + ' from the table that already exists for ' + code + ': load that table first, then add what is new');
    const html = 'A table for <b>' + esc(table.country) + '</b> (' + code + ') already exists, with ' + table.services.length + ' numbers. To add a number or a language, load it, add what is new, and submit the whole file. <button type="button" id="loadtable">Load the existing ' + code + ' table</button>';
    if (ex.dataset.code !== code) { ex.innerHTML = html; ex.dataset.code = code; }
  } else if (ex.dataset.code) { ex.innerHTML = ''; ex.dataset.code = ''; }
  if (/^[A-Z]{2}$/.test(code)) {
    const k = K.known[code];
    if (!k) warn.push(code + ' is not in our list of countries and territories: check that it is the ISO 3166-1 alpha-2 code of the place (it is the file name).');
    else {
      if (data.country && data.country.toLowerCase() !== k.name.toLowerCase()) warn.push('In our list, ' + code + ' is ' + k.name + ', not ' + data.country + '.');
      const want = k.languages.map(l => l.code).filter(Boolean), have = data.languages;
      if (want.length && (want.some(c => !have.includes(c)) || have.some(c => !want.includes(c))))
        warn.push('Wikipedia lists for ' + k.name + ': ' + k.languages.map(l => l.name + (l.code ? ' (' + l.code + ')' : ' (no two-letter code)')).join(', ') + '. You typed: ' + (have.join(', ') || 'nothing') + '. Only languages you have keywords for belong in the list.');
    }
  }
  $('#warnings').innerHTML = warn.length ? '<b>Check, but these do not stop the file:</b><ul class="problems">' + warn.map(x => '<li>' + esc(x) + '</li>').join('') + '</ul>' : '';
  $('#problems').innerHTML = found.length
    ? '<b class="bad">' + found.length + ' thing(s) to fix before this passes the test:</b><ul class="problems">' + found.map(x => '<li>' + x.replace(/&/g, '&amp;').replace(/</g, '&lt;') + '</li>').join('') + '</ul>'
    : '<b class="good">All checks pass.</b> Save it as content/emergency/' + name + ', set REFERENCE_DATE in app/tests/test_emergency_numbers.py to the day you checked, and run the test.';
  $('#json').textContent = JSON.stringify(data, null, 2) + '\n';
  $('#dl').disabled = found.length > 0; $('#cp').disabled = found.length > 0;
  $('#dl').dataset.name = name;
}
document.addEventListener('input', ev => { if (ev.target.id === 'languages') $$('.svc').forEach(renderKeywords); refresh(); });
document.addEventListener('change', refresh);
$('#add').onclick = addService;
$('#cp').onclick = () => { try { navigator.clipboard.writeText($('#json').textContent); } catch (e) { } };
$('#dl').onclick = () => {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([$('#json').textContent], { type: 'application/json' }));
  a.download = $('#dl').dataset.name; a.click(); URL.revokeObjectURL(a.href);
};
addService();
'''


def build_submit():
    rl = ''.join(f'<li>{x}</li>' for x in rule_list())
    cd = coverage_data()
    known = {c: {'name': d['name'], 'languages': d['want']} for c, d in cd.items()}
    tables = {}
    for f in sorted(DATA.glob('*.json')):
        d = json.loads(f.read_text(encoding='utf-8'))
        tables[d['code']] = d
    known_blob = json.dumps({'known': known, 'tables': tables}, ensure_ascii=False).replace('</', '<\\/')
    return f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Emergency numbers: add a country</title>
<style>{CSS}</style>
<h1>Emergency numbers: add a country</h1>
<p>An empty entry for a new country. To add a number or a language to a country that already has a file, type its code and load the existing table first. Fill it in; the checks below run as you type, and the finished file appears at the bottom. To check what is already in a file, use <code>review.html</code>. This page loads nothing from the network and sends nothing anywhere.</p>
<h2>The rules</h2>
<p>These are what <code>app/tests/test_emergency_numbers.py</code> checks; the test is the authority, and this page runs the same checks. See <code>content/emergency/SCHEMA.md</code> for what each field means.</p>
<ul class="rules">{rl}</ul>
<h2>The country</h2>
<div id="existing" class="note"></div>
<label>country <small>its name in English</small><input type="text" id="country"></label>
<label>code <small>ISO 3166-1 alpha-2, capitals (this is the file name)</small><input type="text" id="code" maxlength="2"></label>
<label>calling_code <small>one to three digits, such as 56; the + is added for you</small><span class="pre"><b>+</b><input type="text" id="calling" inputmode="numeric" autocomplete="off"></span></label>
<label>languages <small>the main languages as two-letter ISO 639-1 codes (es, qu, ay), lower case, separated by commas; no region (es-cl) and no three-letter codes</small><input type="text" id="languages"></label>
<label>general <small>the number of the service that answers any emergency, written as in its row</small><input type="text" id="general"></label>
<label class="inl"><input type="checkbox" id="nogeneral"> no general number (none is recorded; this switches the box above off)</label>
<h2>The services</h2>
<div id="services"></div>
<p><button type="button" id="add">Add another service</button></p>
<h2>The file</h2>
<pre id="json"></pre>
<p><button type="button" id="cp">Copy</button><button type="button" id="dl">Download</button></p>
<div id="warnings"></div>
<div id="problems"></div>
<script type="application/json" id="known">{known_blob}</script>
<script>{validator_script()}</script>
<script>{SUBMIT_JS}</script>
</html>'''


LANGUAGES_FILE = ROOT / 'tools' / 'emergency_languages.json'
COVERAGE_CSS = '''
.cov{border-collapse:collapse;width:100%;font-size:.95em} .cov th,.cov td{border-bottom:1px solid #ddd;padding:.3rem .5rem;text-align:left;vertical-align:top}
.cov th{background:#f3f3f3;position:sticky;top:0} .st{padding:0 .5rem;border-radius:4px;white-space:nowrap} .st.covered{background:#dfd} .st.partly{background:#fed} .st.none{background:#eee;color:#555}
#where{font-size:1.1em;padding:.3rem;max-width:100%} #answer{border:2px solid #999;border-radius:8px;padding:.8rem 1rem;margin:1rem 0;min-height:2.5rem}
'''
COVERAGE_JS = r'''
const D = JSON.parse(document.getElementById('data').textContent);
const NS = JSON.parse(document.getElementById('nocode').textContent);
const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;');
const names = l => l.map(x => esc(x)).join(', ');
const sel = document.getElementById('where'), box = document.getElementById('answer');
Object.keys(D).sort((a, b) => D[a].name.localeCompare(D[b].name)).forEach(c => {
  const o = document.createElement('option'); o.value = c; o.textContent = D[c].name + ' (' + c + ')' + (D[c].territory ? ', territory' : ''); sel.appendChild(o);
});
NS.forEach((n, i) => { const o = document.createElement('option'); o.value = 'ns' + i; o.textContent = n + ' (no ISO code)'; sel.appendChild(o); });
{ const o = document.createElement('option'); o.value = 'other'; o.textContent = 'My country is not in this list'; sel.appendChild(o); }
function show() {
  const c = sel.value, d = D[c];
  if (c === 'other') { box.innerHTML = '<b>Your country is not in our list, so it is not covered yet. We would appreciate if you helped us:</b> tell us which country or territory is missing, and see <a href="submit.html">submit.html</a> to add its numbers.'; return; }
  if (/^ns\d+$/.test(c)) { box.innerHTML = '<b>' + esc(NS[+c.slice(2)]) + '</b> has no ISO 3166-1 country code, and the tables are one file per two-letter code, so it cannot be added yet. It is not covered; we would appreciate if you helped us decide how to list it.'; return; }
  if (!d) { box.textContent = 'Choose your country above.'; return; }
  if (!d.services) {
    box.innerHTML = '<b>Your country is not covered yet, we would appreciate if you helped us.</b> The page <a href="submit.html">submit.html</a> is an empty entry for a new country.';
    return;
  }
  let t = '<b>' + esc(d.name) + '</b>: we have ' + d.services + ' number' + (d.services === 1 ? '' : 's') + ', with search words in ' + names(d.covered) + '.';
  if (d.missing.length) t += ' <b>Not yet in:</b> ' + names(d.missing) + '. If you speak ' + (d.missing.length === 1 ? 'it' : 'one of them') + ' and can supply and check the words, you can help us.';
  else t += ' Every main language of the country is covered.';
  if (d.nocode.length) t += ' (' + names(d.nocode) + ' ' + (d.nocode.length === 1 ? 'has' : 'have') + ' no two-letter ISO 639-1 code, so ' + (d.nocode.length === 1 ? 'it cannot' : 'they cannot') + ' be added yet.)';
  if (d.more) t += ' The country has more than 4 languages; only the main ones are listed.';
  box.innerHTML = t;
}
sel.onchange = show; show();
'''


def coverage_data(data_dir=DATA, languages_file=LANGUAGES_FILE):
    """{ISO code: {...}} for every country in the languages file or with a table: what the country speaks (the languages
    file), what the table covers, what is missing."""
    doc = json.loads(Path(languages_file).read_text(encoding='utf-8'))['countries']
    have = {}
    for p in sorted(Path(data_dir).glob('*.json')):
        d = json.loads(p.read_text(encoding='utf-8'))
        have[d['code']] = d
    out = {}
    for code in sorted(set(doc) | set(have)):
        wiki = doc.get(code, {})
        want = wiki.get('official', [])
        name_of = {x['code']: x['name'] for x in want if x['code']}
        row = {'name': wiki.get('name') or have[code]['country'], 'want': want, 'more': bool(wiki.get('more_than_4')),
               'territory': bool(wiki.get('territory'))}
        if code in have:
            covered = have[code]['languages']
            row.update(services=len(have[code]['services']), covered=[name_of.get(c, c) for c in covered],
                       covered_codes=covered,
                       missing=[x['name'] for x in want if x['code'] and x['code'] not in covered],
                       nocode=[x['name'] for x in want if not x['code']])
        out[code] = row
    return out


def states_without_iso(languages_file=LANGUAGES_FILE):
    return json.loads(Path(languages_file).read_text(encoding='utf-8')).get('states_without_iso_code', [])


def build_coverage(data_dir=DATA, languages_file=LANGUAGES_FILE):
    data = coverage_data(data_dir, languages_file)
    nocode = states_without_iso(languages_file)
    rows = []
    for code, d in data.items():
        wants = ', '.join(f'{e(x["name"])}{" (" + x["code"] + ")" if x["code"] else ""}' for x in d['want']) or '<span class="unk">not listed</span>'
        if 'services' not in d:
            status, label, cov, n = 'none', 'not yet', '<span class="unk">none</span>', 0
        else:
            status, label = ('partly', 'partly') if d['missing'] or d['nocode'] else ('covered', 'covered')
            cov, n = e(', '.join(d['covered'])), d['services']
        rows.append(f'<tr><td>{e(d["name"])} <small>{e(code)}{", territory" if d["territory"] else ""}</small></td><td>{wants}{" <small>(more than 4 exist)</small>" if d["more"] else ""}</td>'
                    f'<td>{cov}</td><td>{n}</td><td><span class="st {status}">{label}</span></td></tr>')
    rows += [f'<tr><td>{e(n)} <small>no ISO code</small></td><td><span class="unk">not listed</span></td><td><span class="unk">none</span></td><td>0</td>'
             f'<td><span class="st none">not yet</span></td></tr>' for n in nocode]
    have = sum(1 for d in data.values() if 'services' in d)
    nocode_blob = json.dumps(nocode, ensure_ascii=False).replace('</', '<\\/')
    blob = json.dumps({c: {k: v for k, v in d.items() if k in ('name', 'services', 'covered', 'missing', 'nocode', 'more', 'territory')} for c, d in data.items()},
                      ensure_ascii=False).replace('</', '<\\/')
    return f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Emergency numbers: coverage</title>
<style>{CSS}{COVERAGE_CSS}</style>
<h1>Emergency numbers: coverage</h1>
<p>Which countries have a table in <code>content/emergency/</code>, and in which of their languages it can be searched. {have} of {len(data)} countries and territories have one, and {len(nocode)} more states have no ISO code to name a file with (the list of countries is Wikipedia's list of official languages plus its list of sovereign states). The languages of each country come from Wikipedia's list of official languages (<code>tools/emergency_languages.json</code>; for a country with more than 4 languages, only the main ones). This page loads nothing from the network and sends nothing anywhere.</p>
<h2>Where are you?</h2>
<select id="where"><option value="">choose your country…</option></select>
<div id="answer" aria-live="polite"></div>
<h2>All countries</h2>
<table class="cov"><tr><th>Country</th><th>Languages of the country</th><th>Languages we cover</th><th>Numbers</th><th>Status</th></tr>{"".join(rows)}</table>
<script type="application/json" id="data">{blob}</script>
<script type="application/json" id="nocode">{nocode_blob}</script>
<script>{COVERAGE_JS}</script>
</html>'''


def main(argv):
    out = Path(argv[1]) if len(argv) > 1 else ROOT / 'build' / 'emergency'
    out.mkdir(parents=True, exist_ok=True)
    for name, text in (('review.html', build_review()), ('submit.html', build_submit()), ('coverage.html', build_coverage())):
        (out / name).write_text(text, encoding='utf-8')
        print(out / name)


if __name__ == '__main__':
    main(sys.argv)
