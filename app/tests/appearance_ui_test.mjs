import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const html = fs.readFileSync(new URL('../../web/index.html', import.meta.url), 'utf8');
const bootstrap = fs.readFileSync(new URL('../../web/appearance.js', import.meta.url), 'utf8');
const setup = fs.readFileSync(new URL('../../web/setup.html', import.meta.url), 'utf8');
const app = fs.readFileSync(new URL('../../web/app.js', import.meta.url), 'utf8');
const controller = app.slice(app.indexOf('/* Appearance stays'), app.indexOf('/* ---------------------------------------------------------------- icons'));
function run(saved, dark, blocked = false) {
  const controls = [{ value: '' }, { value: '' }, { value: '' }], metas = [{ content: '' }, { content: '' }], listeners = {}, notices = [];
  const media = { matches: dark, addEventListener: (type, fn) => { listeners.os = fn } };
  const context = { document: { documentElement: { dataset: {} }, querySelectorAll: selector => selector === '[data-appearance]' ? controls : metas, addEventListener: (type, fn) => { listeners[type] = fn } },
    localStorage: { getItem: () => { if (blocked) throw Error('blocked'); return saved }, setItem: (k, v) => { if (blocked) throw Error('blocked'); saved = v } },
    matchMedia: () => media, $$: () => controls, toast: text => notices.push(text) };
  vm.createContext(context); vm.runInContext(bootstrap, context);
  const firstPaint = { ...context.document.documentElement.dataset };
  vm.runInContext(controller, context);
  return { context, firstPaint, controls, media, metas, listeners, notices, saved: () => saved };
}
{
  const h = run('light', true);
  assert.equal(h.firstPaint.theme, 'light'); assert.equal(h.firstPaint.appearance, 'light');
  h.listeners.os(); assert.equal(h.context.document.documentElement.dataset.theme, 'light');
  assert.equal(h.controls[0].value, 'light'); assert.equal(h.metas[0].content, '#ffffff');
  h.listeners.change({ target: { matches: () => true, value: 'dark' } });
  assert.equal(h.saved(), 'dark'); assert.equal(h.controls[1].value, 'dark'); assert.equal(h.controls[2].value, 'dark'); assert.equal(h.context.document.documentElement.dataset.theme, 'dark');
}
{
  const h = run('system', false); assert.equal(h.firstPaint.theme, 'light');
  h.media.matches = true; h.listeners.os(); assert.equal(h.context.document.documentElement.dataset.theme, 'dark');
}
{
  const h = run('invalid choice', true); assert.equal(h.firstPaint.appearance, 'system'); assert.equal(h.firstPaint.theme, 'dark');
}
{
  const h = run(null, true, true); assert.equal(h.firstPaint.theme, 'dark');
  h.listeners.change({ target: { matches: () => true, value: 'light' } });
  assert.equal(h.context.document.documentElement.dataset.theme, 'light'); assert.match(h.notices[0], /could not save/);
}
// Both standalone entry points initialize the same choice before the shared stylesheet.
for (const [entry, markup] of [['library', html], ['setup', setup], ['manage', setup]]) {
  assert(markup.indexOf('/ui/appearance.js') >= 0, entry + ' loads appearance');
  assert(markup.indexOf('/ui/appearance.js') < markup.indexOf('/ui/app.css'), entry + ' resolves before CSS');
  for (const [saved, systemDark, expected] of [[null, true, 'dark'], [null, false, 'light'], ['light', true, 'light'], ['dark', false, 'dark']]) {
    assert.equal(run(saved, systemDark).firstPaint.theme, expected, entry + ' applies saved/system choice');
  }
}
const sw = fs.readFileSync(new URL('../../web/sw.js', import.meta.url), 'utf8');
assert.match(sw, /FILES = \[[^\n]*'\/ui\/appearance.js'/, 'offline shell caches initializer');
// The phone control lives in the shared banner, outside page-specific chat markup.
assert.match(html, /<header[\s\S]*class="top-appearance"[\s\S]*data-appearance aria-label="Appearance"[\s\S]*<\/header>/);
console.log('Appearance passed (first paint, persistence, OS changes, invalid/blocked storage).');
