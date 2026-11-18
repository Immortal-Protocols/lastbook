import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const html = fs.readFileSync(new URL('../../web/index.html', import.meta.url), 'utf8');
const bootstrap = fs.readFileSync(new URL('../../web/appearance.js', import.meta.url), 'utf8');
const setup = fs.readFileSync(new URL('../../web/setup.html', import.meta.url), 'utf8');
const app = fs.readFileSync(new URL('../../web/app.js', import.meta.url), 'utf8');
const css = fs.readFileSync(new URL('../../web/app.css', import.meta.url), 'utf8');
const controller = app.slice(app.indexOf('/* Appearance stays'), app.indexOf('/* ---------------------------------------------------------------- icons'));
const lookOfSrc = app.slice(app.indexOf('function lookOf('), app.indexOf('const ZIMS ='));
const TOKENS = {
  light: { '--ink': '#1d1d1f', '--ink2': '#55555a', '--line2': '#e6e6e9', '--accent': 'rgb(16, 128, 92)', '--font': 'sans-serif', '--display': 'sans-serif' },
  dark: { '--ink': '#f2f2f3', '--ink2': '#c2c2c7', '--line2': '#313134', '--accent': 'rgb(60, 198, 144)', '--font': 'sans-serif', '--display': 'sans-serif' },
};
function run(saved, dark, blocked = false, withFrame = false) {
  const controls = [{ value: '' }, { value: '' }, { value: '' }], metas = [{ content: '' }, { content: '' }], listeners = {}, notices = [], frameProps = {};
  let reloads = 0;
  const frameStyle = {
    colorScheme: '',
    setProperty(k, v) { frameProps[k] = v },
    removeProperty(k) { delete frameProps[k]; if (k === 'color-scheme') this.colorScheme = '' },
  };
  const frame = withFrame ? {
    src: '/zim/demo.zim/Water',
    contentDocument: { documentElement: { style: frameStyle } },
    contentWindow: { scrollY: 420, location: { reload() { reloads++ } } },
  } : null;
  const media = { matches: dark, addEventListener: (type, fn) => { listeners.os = fn } };
  const htmlEl = { dataset: {} };
  const context = {
    html: htmlEl,
    document: {
      documentElement: htmlEl,
      body: { append() {} },
      createElement: () => ({ style: {}, hidden: false, remove() {} }),
      querySelector: selector => selector === '#wframe' ? frame : null,
      querySelectorAll: selector => selector === '[data-appearance]' ? controls : metas,
      addEventListener: (type, fn) => { listeners[type] = fn },
    },
    getComputedStyle: el => {
      const theme = htmlEl.dataset.theme === 'dark' ? 'dark' : 'light';
      const tok = TOKENS[theme];
      return { color: tok['--accent'], getPropertyValue: name => tok[name] || '' };
    },
    localStorage: { getItem: () => { if (blocked) throw Error('blocked'); return saved }, setItem: (k, v) => { if (blocked) throw Error('blocked'); saved = v } },
    matchMedia: () => media,
    $: selector => selector === '#wframe' ? frame : null,
    $$: () => controls,
    toast: text => notices.push(text),
  };
  vm.createContext(context);
  vm.runInContext(bootstrap, context);
  const firstPaint = { ...context.document.documentElement.dataset };
  vm.runInContext(lookOfSrc + '\n' + controller, context);
  return { context, firstPaint, controls, media, metas, listeners, notices, frame, frameProps, frameStyle, reloads: () => reloads, saved: () => saved };
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
  // Open encyclopedia frame refreshes copied look tokens on both explicit selection and system changes, without reloading or losing scroll position.
  const h = run('system', false, false, true);
  h.context.lookOf(h.frame.contentDocument);
  assert.equal(h.frameProps['--lb-ink'], TOKENS.light['--ink']);
  assert.equal(h.frameProps['--lb-link'], TOKENS.light['--accent']);
  assert.equal(h.frameStyle.colorScheme, 'light');
  // Explicit Dark while OS is light: frame updates immediately, scrollY and src stay untouched.
  h.listeners.change({ target: { matches: () => true, value: 'dark' } });
  assert.equal(h.frameProps['--lb-ink'], TOKENS.dark['--ink']);
  assert.equal(h.frameProps['--lb-link'], TOKENS.dark['--accent']);
  assert.equal(h.frameStyle.colorScheme, 'dark');
  assert.equal(h.reloads(), 0);
  assert.equal(h.frame.src, '/zim/demo.zim/Water');
  assert.equal(h.frame.contentWindow.scrollY, 420);
  // OS changes while explicit Dark is active: stays dark.
  h.media.matches = true; h.listeners.os();
  assert.equal(h.frameStyle.colorScheme, 'dark');
  // Switch back to System (OS is dark), then OS changes to light: frame refreshes automatically without reload.
  h.listeners.change({ target: { matches: () => true, value: 'system' } });
  assert.equal(h.frameProps['--lb-ink'], TOKENS.dark['--ink']);
  h.media.matches = false; h.listeners.os();
  assert.equal(h.frameProps['--lb-ink'], TOKENS.light['--ink']);
  assert.equal(h.frameProps['--lb-link'], TOKENS.light['--accent']);
  assert.equal(h.frameStyle.colorScheme, 'light');
  assert.equal(h.reloads(), 0);
  assert.equal(h.frame.contentWindow.scrollY, 420);
  // Explicit Light while OS is dark: stays light even after OS change.
  h.listeners.change({ target: { matches: () => true, value: 'light' } });
  h.media.matches = true; h.listeners.os();
  assert.equal(h.context.document.documentElement.dataset.theme, 'light');
  assert.equal(h.frameProps['--lb-ink'], TOKENS.light['--ink']);
  assert.equal(h.frameStyle.colorScheme, 'light');
}
{
  const h = run('invalid choice', true); assert.equal(h.firstPaint.appearance, 'system'); assert.equal(h.firstPaint.theme, 'dark');
}
{
  const h = run(null, true, true); assert.equal(h.firstPaint.theme, 'dark');
  h.listeners.change({ target: { matches: () => true, value: 'light' } });
  assert.equal(h.context.document.documentElement.dataset.theme, 'light'); assert.match(h.notices[0], /could not save/);
}
// Dark-mode semantic colour cascade and chevron styling in app.css.
assert.equal(css.includes(':root[data-theme="dark"]'), false, 'dark tokens must not outweigh .plat-mac');
assert(css.indexOf('\n[data-theme="dark"]{') < css.indexOf('@supports (color:-apple-system-label){.plat-mac{'), 'Mac semantic tokens follow dark defaults');
assert(css.indexOf('\n[data-theme="dark"]{') < css.indexOf('html.plat-win{'), 'Windows tokens follow dark defaults');
assert(css.indexOf('html.plat-win{') < css.indexOf('html.plat-win[data-theme="dark"]{'), 'Windows dark tokens follow Windows light');
assert.match(css, /label\.appearance\{/, 'label.appearance beats .cs-privacy label alignment');
assert.match(css, /@media \(forced-colors:none\)\{[\s\S]*:is\(\.appearance,\.top-appearance\)::after/, 'custom chevron preserves forced-colors fallback');
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
console.log('Appearance passed (first paint, persistence, OS changes, live iframe sync, semantic cascade, chevron, invalid/blocked storage).');
