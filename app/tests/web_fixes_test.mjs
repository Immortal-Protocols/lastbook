// Regression tests for web/app.js, chat.js, map.js and terrain3d.js. Run: node --test app/tests/web_fixes_test.mjs
// The scripts are browser scripts with no exports, so each test pulls out the function it needs (or the whole file) and runs it
// inside `with (scope)`, where every global the code reaches for that the test did not provide is a do-nothing stand-in.
import fs from 'node:fs';
import test from 'node:test';
import assert from 'node:assert/strict';

const ROOT = new URL('../../', import.meta.url).pathname;
const src = f => fs.readFileSync(ROOT + 'web/' + f, 'utf8');
const sleep = ms => new Promise(r => setTimeout(r, ms));

// Text of the function (or one-line const/let) that starts at the first line matching `start`; a function ends at the first `indent + '}'` line.
function grab(text, start, indent = '') {
  const lines = text.split('\n'), i = lines.findIndex(l => start.test(l));
  assert.ok(i >= 0, 'not found in source: ' + start);
  if (!/\{\s*$/.test(lines[i])) return lines[i];
  let j = i + 1; while (lines[j] !== indent + '}') j++;
  return lines.slice(i, j + 1).join('\n');
}
const any = () => new Proxy(function () { }, {
  get: (t, k) => k === Symbol.toPrimitive ? () => '' : k === 'then' ? undefined : any(),
  apply: () => any(), construct: () => any(), set: () => true, has: () => true,
});
function load(code, over, ret) {
  const own = new Set([...code.matchAll(/(?:function|const|let)\s+([\w$]+)/g)].map(m => m[1]));
  const scope = new Proxy(over, {
    has: (t, k) => typeof k === 'string' && (k in t || (!(k in globalThis) && !own.has(k))),
    get: (t, k) => k === Symbol.unscopables ? undefined : k in t ? t[k] : any(),
    set: (t, k, v) => { t[k] = v; return true },
  });
  return new Function('scope', `with (scope) { ${code}\n return { ${ret} } }`)(scope);
}
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const APP = src('app.js'), CHAT = src('chat.js');

/* 1. routing: addresses with % and ? in a title */
const parseWith = hash => load(
  [grab(APP, /^const dec\b/), grab(APP, /^function parse\(/)].join('\n'), { here: () => hash }, 'parse').parse();
test('parse survives a bad % escape and keeps the raw segment', () => {
  const r = parseWith('#/wiki/mdwiki/100%/a%3Fb%20c?from=%23%2Fx');
  assert.deepEqual(r.parts, ['wiki', 'mdwiki', '100%', 'a?b c']);
  assert.equal(r.q.get('from'), '#/x');
});
test('a wiki address keeps each segment encoded, so a ? in a title does not start the query', () => {
  const f = load(grab(APP, /^const encPath\b/) + '\n' + grab(APP, /^const wikiHref\b/), {}, 'wikiHref').wikiHref;
  assert.equal(f('zim/What? 100%/x y'), '#/wiki/zim/What%3F%20100%25/x%20y');
  const back = parseWith(f('zim/What? 100%/x y'));
  assert.deepEqual(back.parts, ['wiki', 'zim', 'What? 100%', 'x y']);
});

/* 2. a slow earlier route must not touch the page the person has since opened */
function router(views, extra = []) {
  const main = { innerHTML: '', classList: any(), onkeydown: null }, document = { body: { className: '' }, activeElement: null };
  const over = {
    main, document, navStack: [], scrolls: {}, current: null, swapping: false, navAt: 0, navEnd: 0, keepNav() { }, _replace() { }, history: { state: null },
    sessionStorage: { setItem() { } }, here: () => over.hash, parse: () => ({ parts: over.hash.slice(2).split('/'), q: new URLSearchParams() }),
    topics: async () => [], emptyState: (i, t, m) => 'ERR ' + t, setTitle() { }, notFound() { }, startHere() { }, restoreScroll() { },
    requestAnimationFrame() { }, scrollY: 0, ...views,
  };
  const code = [grab(APP, /^let routeSeq\b|^let leaving\b/), grab(APP, /^const stale\b/), grab(APP, /^let searchSeq\b/), grab(APP, /^async function route\(/),
    ...['library', 'videosHome', ...extra].map(n => grab(APP, new RegExp('^(async )?function ' + n + '\\('))) ].join('\n');
  const r = load(code, over, 'route, library, videosHome, ' + extra.join(', '));
  const go = h => { over.hash = h; return r.route() };
  return { main, document, over, go, ...r };
}
test('a stale route that fails shows no error over the new page', async () => {
  let release; const gate = new Promise(r => release = r);
  const t = router({ prepareHub: async () => { await gate; throw new TypeError('gone') }, about: async () => { t.main.innerHTML = 'ABOUT' } });
  const a = t.go('#/prepare'), b = t.go('#/about');
  await b; release(); await a;
  assert.equal(t.main.innerHTML, 'ABOUT');
  assert.notEqual(t.document.body.className, 'v-error');
});
test('a slow view stops writing once the person has gone elsewhere', async () => {
  let release; const gate = new Promise(r => release = r);
  const t = router({ zimsHere: () => gate, api: async () => [], store: { get: () => [] }, about: async () => { t.main.innerHTML = 'ABOUT' } });
  // the real library() runs here: it waits for zimsHere, then would replace main
  const a = t.go('#/library'), b = t.go('#/about');
  await b; release([]); await a;
  assert.equal(t.main.innerHTML, 'ABOUT');
});

// every view that waits before it writes must leave main alone once the person has moved on
for (const [name, hash, gated] of [['home', '#/guides', 'continueItems'], ['savedPage', '#/saved', 'recents'], ['encyclopedias', '#/encyclopedias', 'zimsHere'], ['about', '#/about', 'libInfo']])
  test('stale ' + name + ' does not render over a newer page', async () => {
    let release; const gate = new Promise(r => release = r);
    const t = router({ [gated]: () => gate.then(() => name === 'encyclopedias' ? [] : name === 'about' ? {} : name === 'savedPage' ? [] : []), prepareHub: async () => { t.main.innerHTML = 'NEW' }, store: { get: () => [] }, api: async () => ({}) }, [name]);
    const a = t.go(hash); await sleep(5);   // the view is under way, waiting
    const b = t.go('#/prepare');
    await b; release(); await a; await sleep(5);
    assert.equal(t.main.innerHTML, 'NEW');
  });
test('stale search results and collection pages do not write into the newer page', async () => {
  let release; const gate = new Promise(r => release = r), writes = [];
  const el = () => new Proxy({}, { set: (t, k, v) => (k === 'innerHTML' && writes.push(v), true), get: (t, k) => k === 'insertAdjacentHTML' ? (_, v) => writes.push(v) : any() });
  const t = router({ api: () => gate.then(() => ({ results: [], expanded: [], items: [], more: false })), $: () => el(), $$: () => [], topicMatches: () => [], prepareHub: async () => { } }, ['results', 'collectionPage']);
  const a = t.results('x', 'read'), c = t.collectionPage('n', '#/library');
  await sleep(5); await t.go('#/prepare'); writes.length = 0;
  release(); await a; await c; await sleep(5);
  assert.deepEqual(writes, []);
});

/* 3, 4. chat */
test('md: no stray closing tag when a heading follows a section, or when none is open', () => {
  const md = load(grab(CHAT, /^  function md\(/, '  '), { esc, $: any(), ico: () => '' }, 'md').md;
  const bal = h => (h.match(/<div/g) || []).length - (h.match(/<\/div>/g) || []).length;
  for (const t of ['Not found in the library: x\n\n## Heading\ntext', 'Not found in the library\nSources disagree\ntext', 'intro\nNot found in the library\n\nafter\n\n## H', '## H\ntext', 'text', 'Own reasoning\n- a\n- b'])
    assert.equal(bal(md(t, {})), 0, JSON.stringify(t));
});
const sendWith = (over = {}) => {
  const log = { calls: [], saves: [] }, cur0 = over.cur === undefined ? null : over.cur;
  const sse = e => 'data: ' + JSON.stringify(e) + '\n\n';
  const chunks = [sse({ type: 'error', error: 'model_unavailable', text: 'off' })];
  const scope = {
    cur: cur0, chats: [], live: {}, newId: () => 'c1', persist: () => log.saves.push(!!(all.cur && all.cur.messages[1].fallback)),
    getStatus: async () => ({ online: true }), history_: () => [], throttle: f => f, matchMedia: () => ({ matches: false }), updateBot() { }, setBusy() { }, scrollEnd() { },
    fetch: async () => ({ ok: true, body: { getReader: () => ({ read: async () => chunks.length ? { value: new TextEncoder().encode(chunks.shift()) } : { done: true } }) } }),
    ...over,
  };
  const code = [grab(CHAT, /^  async function send\(/, '  '), grab(CHAT, /^  function onEvent\(/, '  '), 'async function fallback(m, q) { await sleep(20); log.calls.push(q); m.fallback = [{ q }] }'].join('\n');
  const all = { ...scope, log, sleep };
  return { log, ...load(code, all, 'send, onEvent') };
};
test('chat: the library fallback finishes before the answer is saved, using the question that was asked', async () => {
  const t = sendWith();
  await t.send('how do I boil water');
  assert.deepEqual(t.log.calls, ['how do I boil water']);
  assert.equal(t.log.saves.at(-1), true);
});
test('chat: a model_unavailable event no longer needs the open chat', () => {
  const t = sendWith({ cur: null }), m = { steps: [], content: '' };
  assert.doesNotThrow(() => t.onEvent(m, { type: 'error', error: 'model_unavailable', text: 'off' }));
  assert.equal(m.offline, true);
});

/* 5. transcript highlight */
test('transcript highlight escapes the text first-class: entities stay whole', () => {
  const h = load(esc.toString().replace(/^/, 'const esc = ') + '\n' + grab(APP, /^const hilite\b/ ), {}, 'hilite').hilite;
  const rx = q => new RegExp(q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'ig');
  assert.equal(h('a < b & c', rx('lt')), 'a &lt; b &amp; c');
  assert.equal(h('a < b & c', rx('amp')), 'a &lt; b &amp; c');
  assert.equal(h('Tom & Jerry <b>', rx('jerry')), 'Tom &amp; <mark>Jerry</mark> &lt;b&gt;');
  assert.equal(h('x < y', rx('<')), 'x <mark>&lt;</mark> y');
  assert.equal(h('plain', null), 'plain');
});

/* 6. map: entering the map twice must not leave the first visit's listeners and timers behind */
test('map: page() twice leaks nothing, and stop() frees all of it', async () => {
  const keys = new Set(), fulls = new Set(), timers = new Set(), obs = new Set();
  const document = {
    addEventListener: (t, f) => { (t === 'keydown' ? keys : fulls).add(f) }, removeEventListener: (t, f) => { (t === 'keydown' ? keys : fulls).delete(f) },
    getElementById: () => any(), fullscreenElement: null, title: '', querySelector: () => null,
  };
  class RO { constructor() { obs.add(this) } observe() { } disconnect() { obs.delete(this) } }
  let n = 0;
  const { MapView } = load(src('map.js'), {
    document, ResizeObserver: RO, fetch: () => new Promise(() => { }), setInterval: () => { const id = ++n; timers.add(id); return id }, clearInterval: id => timers.delete(id),
    localStorage: { getItem: () => null, setItem() { } }, Terrain3D: { close() { } }, location: { protocol: 'lastbook:' }, main: any(),
  }, 'MapView');
  const mk = () => any();
  await MapView.page(mk(), new URLSearchParams());
  await MapView.page(mk(), new URLSearchParams());
  assert.equal(keys.size, 1, 'keydown handlers'); assert.equal(fulls.size, 1, 'fullscreenchange handlers'); assert.equal(timers.size, 1, 'poll timers');
  MapView.stop();
  assert.equal(keys.size + fulls.size + timers.size, 0);
  assert.equal(obs.size, 0, 'resize observers');
});

test('map: leaving while the home area loads builds nothing', async () => {
  const keys = new Set(), timers = new Set(), raf = [];
  const document = { addEventListener: (t, f) => keys.add(f), removeEventListener: (t, f) => keys.delete(f), getElementById: () => any(), fullscreenElement: null, title: '', querySelector: () => null };
  let n = 0;
  const { MapView } = load(src('map.js'), {
    document, ResizeObserver: class { observe() { } disconnect() { } }, fetch: () => new Promise(() => { }), setInterval: () => { timers.add(++n); return n }, clearInterval: id => timers.delete(id),
    requestAnimationFrame: f => raf.push(f), localStorage: { getItem: () => null, setItem() { } }, Terrain3D: { close() { } }, location: { protocol: 'lastbook:' }, main: any(),
  }, 'MapView');
  let current = true;
  const p = MapView.page(any(), new URLSearchParams(), () => current);
  current = false; await p; await sleep(5);
  assert.equal(keys.size + timers.size + raf.length, 0);
});

/* 7. 3D view: closing while elevation loads must not call back into the closed map */
test('terrain3d: no elevation callbacks after close()', async () => {
  const document = { createElement: () => any(), addEventListener() { }, removeEventListener() { } };
  const { Terrain3D } = load(src('terrain3d.js'), { document }, 'Terrain3D');
  let closed = false, after = 0;
  const geo = { lon2x: (l, z) => (l + 180) / 360 * 2 ** z, lat2y: (l, z) => (90 - l) / 180 * 2 ** z, x2lon: (x, z) => x / 2 ** z * 360 - 180, y2lat: (y, z) => 90 - y / 2 ** z * 180 };
  const call = () => { if (closed) after++ };
  const p = Terrain3D.open(any(), { geo, lat: 40, lon: -100, z: 6, w: 512, h: 512, maxTz: 8, getDem: () => { call() }, demTile: () => { call() }, texture: any(), elev: () => 0 });
  setTimeout(() => { closed = true; Terrain3D.close() }, 40);
  await p.catch(() => { });
  assert.equal(after, 0);
});
