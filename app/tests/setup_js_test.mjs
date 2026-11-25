// Runs web/setup.js in a vm with a tiny fake page, to check that the screen asks again while the library list is empty.
// Usage: node app/tests/setup_js_test.mjs   (exit code 1 on a failed check)
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const src = readFileSync(process.env.SETUP_JS || path.join(path.dirname(fileURLToPath(import.meta.url)), '../../web/setup.js'), 'utf8');   // SETUP_JS: another copy to try

const flush = () => new Promise(r => setTimeout(r, 5));
function page(answers) {
  const els = {}, timers = [], calls = [];
  let acts = {};
  const el = sel => els[sel] || (els[sel] = {
    sel, innerHTML: '', textContent: '', hidden: false, disabled: false, dataset: {}, style: {}, firstChild: { style: {} },
    classList: { contains: () => false, add() { }, remove() { } }, focus() { }, contains: () => false, setAttribute() { }, removeAttribute() { },
    querySelector: q => q === 'h1' ? { focus() { } } : null,
    querySelectorAll(q) {   // buttons with a data-act in what the screen drew, so a click can be sent to them
      if (q !== '[data-act]') return [];
      acts = {};
      return [...this.innerHTML.matchAll(/data-act="([^"]+)"/g)].map(m => (acts[m[1]] = { dataset: { act: m[1] }, disabled: false }));
    }, get offsetWidth() { return 0 } });
  const ctx = vm.createContext({
    document: { querySelector: el, documentElement: { classList: { contains: () => false } } },
    location: { hash: '' }, navigator: { platform: 'MacIntel' }, CSS: { escape: s => s }, Object, JSON, Promise, Set, Math, Number, String, Array, Error, Boolean, RegExp, isFinite,
    scrollTo() { }, addEventListener() { }, clearTimeout() { },
    setTimeout: (f, ms) => { timers.push(f); return timers.length },
    fetch: async (url, opts) => {
      const name = url.replace('/api/setup/', ''), body = opts && opts.body ? JSON.parse(opts.body) : undefined;
      calls.push([name, body]);
      const a = answers[name];
      const d = await (typeof a === 'function' ? a(body, calls) : a);   // an answer can be a promise, to hold it back
      return { ok: true, status: 200, json: async () => JSON.parse(JSON.stringify(d === undefined ? null : d)) };
    },
  });
  vm.runInContext(src, ctx, { filename: 'setup.js' });
  return { el, timers, calls, ctx, acts: () => acts };
}
const pack = { id: 'small', title: 'Small', available: true, summary: 's', installed_bytes: 1e9, download_bytes: 5e8, files: [] };
const state = (extra = {}) => ({ mode: 'first-run', hardware: { disks: [], ai: { fits: false } }, manifest: { packs: [pack], models: [], maps: [] }, current: null, found: [], recommend: { folder: '/x' }, job: null, ...extra });

let bad = 0;
const check = (name, ok) => { if (!ok) { bad++; console.log('FAIL', name) } else console.log('ok  ', name) };

{   // an empty manifest is asked for again
  let n = 0;
  const p = page({ state: () => (++n === 1 ? state({ manifest: { packs: [], models: [], maps: [] } }) : state()) });
  await flush();
  check('empty list schedules another ask', p.timers.length === 1);
  p.timers[0](); await flush();
  check('second state fills the list', p.el('#main').innerHTML.includes('Small'));
  check('and stops asking', p.timers.length === 1);
}

{   // an install starts while the second ask is on its way: its answer must not stop the progress polling
  let n = 0;
  const running = { state: 'downloading', items: [{ kind: 'pack', id: 'small', state: 'downloading' }], overall: {} };
  const p = page({ state: () => (++n === 1 ? state({ manifest: { packs: [], models: [], maps: [] } }) : state({ job: running })), job: running });
  await flush();
  p.timers[0](); await flush();
  const before = p.calls.filter(c => c[0] === 'job').length;
  p.timers[p.timers.length - 1](); await flush();
  check('a running job is still polled after the second ask', p.calls.filter(c => c[0] === 'job').length > before);
}

{   // a library file is chosen while the second ask is on its way: that older answer must not replace the install screen
  let n = 0, release;
  const running = { state: 'downloading', items: [{ kind: 'pack', id: 'small', state: 'downloading' }], overall: {} };
  const empty = () => state({ manifest: { packs: [], models: [], maps: [] } });
  const p = page({ state: () => (++n === 1 ? empty() : new Promise(r => { release = () => r(empty()) })), pick: { path: '/x/lib.zip' }, use: running, job: running });
  await flush();
  p.timers[0](); await flush();                   // the second ask is held back
  p.el('#haveFile').onclick(); await flush();     // the install starts and draws its progress
  const shown = p.el('#main').innerHTML;
  release(); await flush();                       // the older answer arrives
  check('an older answer leaves the install screen alone', p.el('#main').innerHTML === shown);
  const before = p.calls.filter(c => c[0] === 'job').length;
  p.timers[p.timers.length - 1](); await flush();
  check('and the install is still polled', p.calls.filter(c => c[0] === 'job').length > before);
}

{   // asking again in the background must not move focus to the heading or scroll to the top
  let n = 0;
  const p = page({ state: () => (++n <= 9 ? state({ manifest: { packs: [], models: [], maps: [] } }) : state()) });
  let focuses = 0, scrolls = 0;
  p.el('#main').querySelector = q => q === 'h1' ? { focus() { focuses++ } } : null;
  p.ctx.scrollTo = () => { scrolls++ };
  await flush();
  for (let i = 0; i < 8 && p.timers.length; i++) { p.timers.shift()(); await flush() }
  console.log(`     (focus ${focuses}, scroll ${scrolls})`);
  check('background asks leave focus alone', focuses === 1);
  check('and leave the scroll position alone', scrolls === 1);
}

{   // a kept checksum failure (#122): Download again is asked once more, Keep it goes back, and yes sends download-again, not retry
  const error = { code: 'checksum', message: 'm', kept: true, name: 'Lastbook-Small.zip', size: 8.2e9 };
  const item = { kind: 'pack', id: 'small', title: 'Small', state: 'failed', error, bytes_done: 8.2e9, bytes_total: 8.2e9 };
  const failed = { state: 'failed', error, items: [item], overall: {} };
  const again = { state: 'waiting', error: null, items: [{ ...item, state: 'waiting', error: null, bytes_done: 0 }], overall: {} };
  const p = page({ state: () => state({ job: failed }), job: again, 'download-again': again });
  await flush();
  const html = () => p.el('#main').innerHTML, sent = name => p.calls.some(c => c[0] === name), click = a => p.acts()[a] && p.acts()[a].onclick();
  check('kept: Retry and Download again are offered', !!p.acts().retry && !!p.acts().again && html().includes('downloads all 8.2 GB of it again'));
  click('again'); await flush();
  check('Download again asks once more first', html().includes('Delete what was downloaded and download all 8.2 GB again?') && !!p.acts()['again-yes'] && !p.acts().retry);
  check('and sends nothing yet', !sent('download-again') && !sent('retry'));
  click('again-no'); await flush();
  check('Keep it goes back to the choices', !!p.acts().again && !!p.acts().retry && !html().includes('Delete what was downloaded'));
  click('again'); await flush();
  click('again-yes'); await flush();
  check('yes sends download-again, not retry', sent('download-again') && !sent('retry'));
  check('and the download is shown going again', !html().includes('s-err'));
}

process.exit(bad ? 1 : 0);
