// Exercise the real setup page's recovery buttons with controlled engine responses.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const source = readFileSync(process.argv[2], 'utf8');

async function recovery(state, action) {
  const pending = [], calls = [];
  const item = { id: 'ES', kind: 'map', title: 'Spain', state, bytes_done: 5, bytes_total: 10 };
  const job = { state, error: state === 'failed' ? { code: 'network', message: 'Offline' } : null, items: [item] };
  const initial = { mode: 'manage', current: null, recommend: {}, found: [],
                    manifest: { fetching: false, packs: [], models: [], maps: [{ id: 'ES', title: 'Spain' }] }, job };
  const document = { documentElement: { classList: { contains: () => false } }, activeElement: null };
  const heading = { focus() { document.activeElement = this } };
  const live = { textContent: '' }, back = { hidden: false };
  const main = {
    buttons: [],
    set innerHTML(html) {
      this.buttons = Array.from(html.matchAll(/<button\b[^>]*data-act="([^"]+)"/g), match => ({
        dataset: { act: match[1] }, disabled: false,
        focus() { document.activeElement = this },
      }));
    },
    querySelectorAll(selector) { return selector === '[data-act]' ? this.buttons : [] },
    querySelector(selector) {
      if (selector === 'h1') return heading;
      if (selector === '[data-act]') return this.buttons[0] || null;
      const match = selector.match(/^\[data-act="([^"]+)"\]$/);
      return match ? this.buttons.find(b => b.dataset.act === match[1]) || null : null;
    },
  };
  document.querySelector = selector => ({ '#main': main, '#live': live, '#sBack': back })[selector] || null;
  const response = data => ({ ok: true, json: async () => JSON.parse(JSON.stringify(data)) });
  const fetch = async url => {
    const path = url.split('/').pop();
    if (path === 'state') return response(initial);
    calls.push(path);
    return new Promise((resolve, reject) => pending.push({ resolve, reject }));
  };
  vm.runInNewContext(source, { document, fetch, location: { hash: '' }, navigator: {},
    CSS: { escape: s => s }, addEventListener() {}, scrollTo() {}, setTimeout() {}, clearTimeout() {} });
  await new Promise(setImmediate); // load() has rendered the saved job

  async function attempt(result) {
    const button = main.querySelector(`[data-act="${action}"]`);
    assert.ok(button, `${action} is visible`);
    assert.equal(button.disabled, false, `${action} is available before the request`);
    const finished = button.onclick();
    assert.equal(button.disabled, true, `${action} is disabled while the request is pending`);
    const request = pending.shift();
    assert.ok(request, `${action} sent a request`);
    if (result instanceof Error) request.reject(result); else request.resolve(response(result));
    await finished;
  }

  const unavailable = { ...job, error: { code: 'manifest', message: 'Spain map details are unavailable.' } };
  await attempt(unavailable);
  await attempt(unavailable); // the response has the same shape as the previous one
  await attempt(new Error('connection lost'));
  await attempt({ ...job, state: 'waiting', error: null, items: [{ ...item, state: 'waiting' }] });
  assert.deepEqual(calls, [action, action, action, action]);
}

await recovery('paused', 'resume');
await recovery('failed', 'retry');
