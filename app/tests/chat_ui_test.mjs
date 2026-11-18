import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

// Run the shipped controller with local-only storage/fetch/DOM doubles. No browser dependency.
const source = fs.readFileSync(new URL('../../web/chat.js', import.meta.url), 'utf8').replace('return { page, count };', `return { page, count, send, botHtml, sourceGroup, plain, exportText, exportChat, persist, onEvent, wire,
  select: c => { cur = c }, current: () => cur, storageError: () => storageError, chats: () => chats, live: () => live };`);
function harness({ saved, brokenStorage = false, online = true, events = [], wide = false } = {}) {
  const values = new Map(saved ? [['sg.chats', JSON.stringify(saved)]] : []), downloads = [], calls = [], elements = new Map();
  const context = { console, AbortController, DOMException, TextDecoder, TextEncoder, Blob, Date,
    localStorage: { getItem: k => { if (brokenStorage) throw Error('blocked'); return values.get(k) ?? null }, setItem: (k, v) => { if (brokenStorage) throw Error('quota'); values.set(k, v) } },
    $: (s, el) => el?.querySelector?.(s) || elements.get(s) || null, $$: () => [],
    esc: value => String(value ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('"', '&quot;'),
    ico: () => '', fileUrl: s => '/' + s, clock: n => String(n), here: () => '#/ask/test',
    addEventListener() {}, matchMedia: q => ({ matches: q.includes('min-width') && wide }),
    requestAnimationFrame() {}, setTimeout() {}, clearTimeout() {}, innerHeight: 800, scrollY: 0,
    location: { hash: '#/ask', origin: 'PRIVATE_ORIGIN' }, history: { replaceState() {} },
    document: { body: { scrollHeight: 800, append() {} }, createElement: () => ({ click() {}, remove() {} }) },
    URL: { createObjectURL: blob => { downloads.push(blob); return 'blob:local' }, revokeObjectURL() {} },
    toast() {},
    fetch: async (url, options = {}) => {
      calls.push({ url, options });
      if (url.includes('/status')) return { json: async () => ({ online }) };
      if (options.signal?.aborted) throw new DOMException('Stopped', 'AbortError');
      const encoder = new TextEncoder(); let sent = false;
      return { ok: true, body: { getReader: () => ({ read: async () => sent ? { done: true } : (sent = true, { value: encoder.encode(events.map(e => 'data: ' + JSON.stringify(e) + '\n\n').join('')), done: false }) }) } };
    },
    api: async url => { calls.push({ url }); return { results: [{ kind: 'pdf', doc_id: 'manual', title: 'A manual', page: 3 }] } },
  };
  vm.createContext(context); vm.runInContext(source + '\nthis.testChat = Chat;', context);
  return { chat: context.testChat, context, values, downloads, calls, elements };
}
const reference = { kind: 'pdf', key: 'S1', doc_id: 'manual', title: 'A manual', page: 3 };
const c = { id: 'test', title: 'Question', messages: [{ role: 'user', content: 'Question' }, { role: 'assistant', content: 'Read the manual. [S1]', cited: [reference] }] };
{
  const { chat } = harness(); chat.select(c);
  const html = chat.botHtml(c.messages[1], 1);
  assert.match(html, /<details class="chat-sources/); assert.doesNotMatch(html, /data-source-group="[^"]+" open/);
  assert.match(html, /href="#\/read\/manual\?p=3/); assert.match(html, /data-key="S1"/);
  const failed = chat.botHtml({ content: '', error: 'Failed', fallback: [reference] }, 1);
  assert.match(failed, /fallback-sources.* open>/); assert.match(failed, /data-act="retry"/); assert.match(failed, /data-act="export"/);
}
{
  const { chat } = harness({ wide: true }); chat.select(c);
  assert.match(chat.botHtml(c.messages[1], 1), /data-source-group="[^"]+" open/);
}
{
  const { chat } = harness({ brokenStorage: true });
  assert.match(chat.storageError(), /could not be read/); assert.equal(chat.persist(), false); assert.match(chat.storageError(), /could not be saved/);
}
{
  const { chat } = harness({ saved: [{ ...c, messages: [{ role: 'assistant', content: 'Partial', running: true }] }] });
  assert.equal(chat.chats()[0].messages[0].running, false); assert.match(chat.chats()[0].messages[0].error, /interrupted/);
}
{
  const { chat, downloads } = harness();
  const secret = 'password=DO_NOT_SHARE api_key="PRIVATE_KEY" Bearer PRIVATE_BEARER /Users/you/private.txt';
  chat.exportChat({ ...c, title: secret, messages: [{ role: 'user', content: secret }, { role: 'assistant', content: '', error: 'secret diagnostics /private/path', fallback: [reference] }, { role: 'assistant', content: 'Partial', stopped: true }, c.messages[1]] });
  const text = await downloads[0].text();
  for (const privateValue of ['DO_NOT_SHARE', 'PRIVATE_KEY', 'PRIVATE_BEARER', '/Users/', 'secret diagnostics', 'PRIVATE_ORIGIN']) assert.ok(!text.includes(privateValue), privateValue);
  assert.match(text, /Answer failed/); assert.match(text, /Answer stopped/); assert.match(text, /Matching library pages/); assert.match(text, /#\/read\/manual\?p=3/);
}
{
  const { chat, calls } = harness({ online: false }); await chat.send('Find a manual');
  assert.equal(chat.current().messages[1].fallback[0].title, 'A manual');
  assert.equal(chat.current().messages[1].running, false); assert.ok(calls.some(c => c.url.includes('/retrieve')));
}
{
  const { chat } = harness({ events: [{ type: 'sources', sources: [reference] }, { type: 'delta', text: 'Partial [S1]' }] });
  await chat.send('Question'); const m = chat.current().messages[1];
  assert.match(m.error, /interrupted/); assert.equal(m.cited[0].key, 'S1'); assert.equal(m.running, false);
}
{
  const { chat } = harness({ events: [{ type: 'runtime', phase: 'generation' }, { type: 'done', answer: 'Complete [S1]', sources: [reference] }] });
  await chat.send('Question'); const m = chat.current().messages[1];
  assert.equal(m.complete, true); assert.equal(m.error, undefined); assert.equal(m.content, 'Complete [S1]');
}
{
  const { chat, calls } = harness({ events: [{ type: 'error', error: 'model_unavailable', text: 'AI unavailable' }] });
  await chat.send('Original question');
  assert.ok(calls.some(c => c.url.includes('q=Original%20question'))); assert.equal(chat.current().messages[1].fallback.length, 1);
}
{
  const { chat, context, calls } = harness();
  let reply;
  context.fetch = (url, options = {}) => {
    calls.push({ url, options });
    return new Promise((resolve, reject) => {
      reply = resolve;
      options.signal?.addEventListener('abort', () => reject(new DOMException('Stopped', 'AbortError')));
    });
  };
  const work = chat.send('Cancel this question');
  chat.live()[chat.current().id].abort(); await work;
  assert.equal(chat.current().messages[1].stopped, true); assert.equal(chat.current().messages[1].running, false);
  assert.equal(calls.length, 1); assert.ok(!calls.some(c => c.url.includes('/retrieve')));
}
{
  const { chat, context } = harness(); chat.select(c);
  const group = { open: false }, card = { closest: () => group, scrollIntoView(options) { this.scroll = options }, classList: { add() {}, remove() {} } };
  const message = { querySelector: () => card, closest() { return this } }, chip = { dataset: { key: 'S1' }, closest: () => message };
  context.$$ = selector => selector === 'a.cite' ? [chip] : [];
  chat.wire(message); let prevented = false;
  chip.onclick({ preventDefault() { prevented = true } });
  assert.equal(prevented, true); assert.equal(group.open, true); assert.equal(card.scroll.block, 'center');
}
{
  const { chat } = harness(); chat.select(c); chat.live()[c.id] = { running: true };
  const html = chat.botHtml({ content: '', state: 'reading', steps: [] }, 1);
  assert.match(html, /class="wk-stages"/); assert.match(html, /class="now">Read/); assert.match(html, /data-act="stop"/);
}
console.log('Chat UI behavior passed (sources, export redaction, storage failures, interrupted/complete/offline streams).');
