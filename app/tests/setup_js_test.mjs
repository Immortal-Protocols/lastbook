// Runs web/setup.js in a vm with a tiny fake page, to check what the screen does with the engine's answers.
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
    classList: { contains: () => false, add() { }, remove() { } }, focus() { }, setAttribute() { }, removeAttribute() { },
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
      const d = typeof a === 'function' ? a(body, calls) : a;
      return { ok: true, status: 200, json: async () => JSON.parse(JSON.stringify(d === undefined ? null : d)) };
    },
  });
  vm.runInContext(src, ctx, { filename: 'setup.js' });
  return { el, timers, calls, ctx, acts: () => acts };
}
const pack = { id: 'small', title: 'Small', available: true, summary: 's', installed_bytes: 1e9, download_bytes: 5e8, files: [] };
const state = (extra = {}) => ({ mode: 'first-run', hardware: { disks: [], ai: { fits: false } }, manifest: { packs: [pack], models: [], maps: [] }, current: null, found: [], recommend: { folder: '/x' }, job: null, ...extra });
const failed = (code, message) => ({ id: 'j', state: 'failed', folder: '/x/LastbookData', error: { code, message }, items: [{ id: 'small', kind: 'pack', title: 'Small', state: 'failed', bytes_done: 0, bytes_total: 5, error: { code, message } }] });

let bad = 0;
const check = (name, ok) => { if (!ok) { bad++; console.log('FAIL', name) } else console.log('ok  ', name) };

{   // 7: the engine's message shows under the canned headline; new codes have headlines of their own
  const p = page({ state: state({ job: failed('folder', 'Lastbook could not write a file (PermissionError: Permission denied).') }) });
  await flush();
  const h = p.el('#main').innerHTML;
  check('folder code: headline', h.includes('could not read or write a file'));
  check('folder code: engine message shown', h.includes('PermissionError: Permission denied'));
  const q = page({ state: state({ job: failed('internal', 'Setup stopped on an internal error (ValueError).') }) });
  await flush();
  check('internal code: headline and message', q.el('#main').innerHTML.includes('unexpected problem') && q.el('#main').innerHTML.includes('ValueError'));
}

{   // 9: map steps, Pause while checking
  const job = { id: 'j', state: 'verifying', folder: '/x', error: null, items: [{ id: 'CA', kind: 'map', title: 'California', state: 'verifying', bytes_done: 1, bytes_total: 5 }] };
  const p = page({ state: state({ job }) });
  await flush();
  const h = p.el('#main').innerHTML;
  check('map has Check and Finish steps', h.includes('>Check<') && h.includes('>Finish<'));
  check('Pause is offered while verifying', h.includes('data-act="pause"'));
}

{   // 10: an empty manifest is asked for again
  let n = 0;
  const p = page({ state: () => (++n === 1 ? state({ manifest: { packs: [], models: [], maps: [] } }) : state()) });
  await flush();
  check('empty list schedules another ask', p.timers.length === 1);
  p.timers[0](); await flush();
  check('second state fills the list', p.el('#main').innerHTML.includes('Small'));
  check('and stops asking', p.timers.length === 1);
}

{   // 9: a later normal install is not shown as a repair
  const cur = { folder: '/x/LastbookData', pack: 'small', model: null, map: 'CA', content_revision: '', old: [], address_indexes: ['CA'], map_bytes: 0 };
  const run = { id: 'j', state: 'downloading', folder: '/x', error: null, items: [{ id: 'small', kind: 'pack', title: 'Small', state: 'downloading', bytes_done: 1, bytes_total: 5 }] };
  let jobNow = failed('network', 'x');
  const p = page({ state: state({ mode: 'manage', current: cur, job: null }), start: () => run, job: () => (jobNow) });
  await flush();
  p.el('#repair').onclick(); await flush();
  check('repair job is called a check', p.el('#main').innerHTML.includes('Checking the library'));
  p.timers.at(-1)(); await flush();                        // the poll finds it stopped
  await p.acts().back.onclick(); await flush();            // "Choose again"
  check('back from a repair leaves choose view', p.el('#start') && typeof p.el('#start').onclick === 'function');
  await p.el('#start').onclick(); await flush();
  const h = p.el('#main').innerHTML;
  check('a later install is Installing, not a repair', h.includes('<h1>Installing</h1>'));
}

{   // 3, 4: a file used from the picker goes with the folder chosen; a noted map does not tick the AI
  const model = { id: 'gemma', title: 'Gemma', file: 'm.gguf', size: 100, available: true };
  const st = state({ hardware: { disks: [], ai: { fits: true } }, manifest: { packs: [pack], models: [model], maps: [] }, recommend: { folder: '/x', ai: false } });
  const p = page({ state: st, pick: { path: '/d/Lastbook-Map-CA.zip' }, use: { noted: true, kind: 'map', job: null } });
  await flush();
  await p.el('#haveFile').onclick(); await flush();
  const use = p.calls.find(c => c[0] === 'use');
  check('use sends the path and the chosen folder', use && use[1].path === '/d/Lastbook-Map-CA.zip' && use[1].folder === '/x/LastbookData' && 'ai' in use[1]);
  check('a noted map is not the AI file', p.el('#haveNote').textContent.includes('map file') && !p.el('#haveNote').textContent.includes('AI'));
}

process.exit(bad ? 1 : 0);
