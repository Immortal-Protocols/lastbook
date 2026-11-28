import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

// Run the shipped controller with local-only storage/fetch/DOM doubles. No browser dependency.
const source = fs.readFileSync(new URL('../../web/chat.js', import.meta.url), 'utf8').replace('return { page, count };', `return { page, count, send, botHtml, updateBot, patchStream, sourceGroup, plain, exportText, exportChat, persist, onEvent, wire,
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
{
  // Streaming Stop button keeps its DOM node and keyboard focus across updates, and expanded Search progress stays open per message.
  const VOID = new Set(['br', 'img', 'hr', 'input', 'meta', 'link']);
  class TextN { constructor(v) { this.nodeType = 3; this.nodeValue = v; this.parent = null } }
  function makeDoc() {
    const doc = { activeElement: null, body: { scrollHeight: 800, append() {} }, createElement: t => new El(t) };
    const contains = (root, target) => {
      if (!root || !target) return false;
      if (root === target) return true;
      return (root.childNodes || []).some(n => contains(n, target));
    };
    function parseAttrs(s, el) {
      const re = /([^\s=]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|(\S+)))?/g;
      let m; while ((m = re.exec(s))) el.setAttribute(m[1], m[2] ?? m[3] ?? m[4] ?? '');
    }
    function parseHTML(html) {
      const root = new El('div'), stack = [root];
      const re = /<!--[\s\S]*?-->|<\/[a-zA-Z][\w:-]*\s*>|<([a-zA-Z][\w:-]*)([^>]*)>|[^<]+/g;
      let m;
      while ((m = re.exec(html))) {
        const tok = m[0], parent = stack[stack.length - 1];
        if (tok.startsWith('<!--')) continue;
        if (tok.startsWith('</')) { if (stack.length > 1) stack.pop(); continue }
        if (tok.startsWith('<')) {
          const el = new El(m[1]);
          parseAttrs(m[2].replace(/\/\s*$/, ''), el);
          parent.appendChild(el);
          if (!VOID.has(m[1].toLowerCase()) && !/\/\s*$/.test(m[2])) stack.push(el);
          continue;
        }
        parent.appendChild(new TextN(tok));
      }
      return [...root.childNodes];
    }
    function serialize(el) {
      if (el.nodeType === 3) return el.nodeValue;
      const name = el.tag.toLowerCase();
      let out = '<' + name;
      for (const [k, v] of Object.entries(el.attrs)) out += ' ' + k + '="' + String(v).replace(/&/g, '&amp;').replace(/"/g, '&quot;') + '"';
      if (VOID.has(name)) return out + '>';
      return out + '>' + el.childNodes.map(serialize).join('') + '</' + name + '>';
    }
    function walk(root, fn) {
      for (const n of root.childNodes || []) { if (n.nodeType === 1) { fn(n); walk(n, fn) } }
    }
    function matchOne(el, sel) {
      if (sel === '[data-act]') return el.hasAttribute('data-act');
      if (sel === '[data-act="stop"]') return el.getAttribute('data-act') === 'stop';
      if (sel === '[data-source-group]') return el.hasAttribute('data-source-group');
      if (sel === '[data-progress-group]') return el.hasAttribute('data-progress-group');
      if (sel === '.srcfilter') return el.classList.contains('srcfilter');
      if (sel === '.srcfilter button') return el.tagName === 'BUTTON' && el.parent?.classList.contains('srcfilter');
      if (sel === 'a.cite') return el.tagName === 'A' && el.classList.contains('cite');
      if (sel === 'details') return el.tagName === 'DETAILS';
      if (sel === 'button') return el.tagName === 'BUTTON';
      if (sel === '.srccard') return el.classList.contains('srccard');
      if (sel.startsWith('#')) return el.getAttribute('id') === sel.slice(1);
      if (sel.startsWith('.')) return el.classList.contains(sel.slice(1));
      return el.tag.toLowerCase() === sel.toLowerCase();
    }
    class El {
      constructor(tag) {
        this.tag = tag; this.nodeType = 1; this.childNodes = []; this.parent = null;
        this._class = ''; this.style = {}; this.attrs = {}; this._open = false;
      }
      get tagName() { return this.tag.toUpperCase() }
      get ownerDocument() { return doc }
      get parentNode() { return this.parent }
      get children() { return this.childNodes.filter(n => n.nodeType === 1) }
      get firstChild() { return this.childNodes[0] || null }
      get lastChild() { return this.childNodes[this.childNodes.length - 1] || null }
      get nextElementSibling() { if (!this.parent) return null; const els = this.parent.children; return els[els.indexOf(this) + 1] || null }
      get previousElementSibling() { if (!this.parent) return null; const els = this.parent.children; return els[els.indexOf(this) - 1] || null }
      get className() { return this._class }
      set className(v) { this._class = v; if (v) this.attrs.class = v; else delete this.attrs.class }
      get classList() {
        const el = this, has = c => el.className.split(/\s+/).includes(c);
        const set = (c, on) => { const k = el.className.split(/\s+/).filter(x => x && x !== c); if (on) k.push(c); el.className = k.join(' ') };
        return { contains: has, add: c => set(c, true), remove: c => set(c, false), toggle(c, on) { if (on === undefined) on = !has(c); set(c, on) } };
      }
      get dataset() {
        const el = this;
        return new Proxy({}, {
          get(_, k) { return el.getAttribute('data-' + k.replace(/[A-Z]/g, ch => '-' + ch.toLowerCase())) ?? '' },
          set(_, k, v) { el.setAttribute('data-' + k.replace(/[A-Z]/g, ch => '-' + ch.toLowerCase()), v); return true },
        });
      }
      get open() { return this._open }
      set open(v) { this._open = !!v; if (v) this.attrs.open = ''; else delete this.attrs.open }
      get hidden() { return this.hasAttribute('hidden') }
      set hidden(v) { if (v) this.setAttribute('hidden', ''); else this.removeAttribute('hidden') }
      get attributes() { return Object.entries(this.attrs).map(([name, value]) => ({ name, value })) }
      setAttribute(k, v) { this.attrs[k] = String(v); if (k === 'class') this._class = String(v); if (k === 'open') this._open = true }
      getAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attrs, k) ? this.attrs[k] : null }
      hasAttribute(k) { return Object.prototype.hasOwnProperty.call(this.attrs, k) }
      removeAttribute(k) { delete this.attrs[k]; if (k === 'class') this._class = ''; if (k === 'open') this._open = false }
      set innerHTML(h) {
        if (this.childNodes.some(n => contains(n, doc.activeElement))) doc.activeElement = null;
        this.childNodes.slice().forEach(n => this.removeChild(n));
        for (const n of parseHTML(h)) this.appendChild(n);
      }
      get innerHTML() { return this.childNodes.map(serialize).join('') }
      get outerHTML() { return serialize(this) }
      set textContent(t) {
        if (this.childNodes.some(n => contains(n, doc.activeElement))) doc.activeElement = null;
        this.childNodes.slice().forEach(n => this.removeChild(n));
        if (t !== '') this.appendChild(new TextN(String(t)));
      }
      get textContent() { return this.childNodes.map(n => n.nodeType === 3 ? n.nodeValue : n.textContent).join('') }
      appendChild(n) { if (n.parent) n.parent.removeChild(n); n.parent = this; this.childNodes.push(n); return n }
      removeChild(n) {
        if (contains(n, doc.activeElement)) doc.activeElement = null;
        const i = this.childNodes.indexOf(n); if (i < 0) throw new Error('not a child');
        this.childNodes.splice(i, 1); n.parent = null; return n;
      }
      append(...ns) { for (const n of ns) this.appendChild(n) }
      prepend(n) { if (n.parent) n.parent.removeChild(n); n.parent = this; this.childNodes.unshift(n) }
      after(n) { if (n.parent) n.parent.removeChild(n); const s = this.parent.childNodes; n.parent = this.parent; s.splice(s.indexOf(this) + 1, 0, n) }
      remove() { this.parent.removeChild(this) }
      focus() { doc.activeElement = this }
      matches(sel) { return matchOne(this, sel) }
      closest(sel) { for (let n = this; n && n.nodeType === 1; n = n.parent) if (matchOne(n, sel)) return n; return null }
      querySelector(sel) { return this.querySelectorAll(sel)[0] || null }
      querySelectorAll(sel) { const res = []; walk(this, n => { if (matchOne(n, sel)) res.push(n) }); return res }
      scrollIntoView(opts) { this.scroll = opts }
    }
    return { doc, El };
  }
  const { chat, context, elements } = harness();
  const { doc, El } = makeDoc();
  context.document = doc;
  context.$ = (s, root) => root ? root.querySelector(s) : elements.get(s) || null;
  context.$$ = (s, root) => root ? root.querySelectorAll(s) : [];
  let aborted = 0;
  const streamingChat = {
    id: 'stream1', title: 'Water',
    messages: [
      { role: 'user', content: 'How do I boil water?' },
      { role: 'assistant', content: '', state: 'thinking', steps: [], sources: [], running: true },
    ],
  };
  chat.select(streamingChat);
  chat.live()[streamingChat.id] = { running: true, abort() { aborted++ } };
  const msg = new El('div'); msg.className = 'msg bot'; msg.setAttribute('id', 'm1');
  elements.set('#m1', msg);
  msg.innerHTML = chat.botHtml(streamingChat.messages[1], 1);
  chat.wire(msg);
  const initialStop = msg.querySelector('[data-act="stop"]');
  assert.ok(initialStop, 'initial streaming Stop button rendered');
  initialStop.focus();
  assert.equal(doc.activeElement, initialStop);

  // First step arrives -> Stop button stays the exact same node and keeps focus.
  const m = streamingChat.messages[1];
  await chat.onEvent(m, { type: 'state', state: 'searching' });
  await chat.onEvent(m, { type: 'found', count: 2 });
  chat.updateBot(1);
  assert.equal(msg.querySelector('[data-act="stop"]'), initialStop, 'Stop DOM node preserved on first update');
  assert.equal(doc.activeElement, initialStop, 'Stop focus preserved on first update');
  const details = msg.querySelector('.work-details');
  assert.ok(details, 'Search progress disclosure created');
  assert.equal(details.open, false, 'Search progress starts collapsed');
  assert.equal(details.children[0].textContent, 'Search progress (1)');

  // User expands Search progress, then multiple stream events arrive.
  details.open = true;
  details.ontoggle();
  for (const ev of [
    { type: 'tool', phase: 'start', name: 'search_library', args: { query: 'boil water' } },
    { type: 'tool', phase: 'end', name: 'search_library', summary: { count: 4 } },
    { type: 'sources', sources: [reference] },
    { type: 'state', state: 'writing' },
    { type: 'delta', text: 'Bring water ' },
    { type: 'delta', text: 'to a rolling boil [S1].' },
  ]) {
    await chat.onEvent(m, ev);
    chat.updateBot(1);
    assert.equal(msg.querySelector('[data-act="stop"]'), initialStop, 'Stop DOM node preserved across ' + ev.type);
    assert.equal(doc.activeElement, initialStop, 'Stop focus preserved across ' + ev.type);
    assert.equal(msg.querySelector('.work-details'), details, 'Search progress node preserved across ' + ev.type);
    assert.equal(details.open, true, 'Search progress remains open across ' + ev.type);
  }
  assert.equal(details.children[0].textContent, 'Search progress (2)');
  assert.match(details.innerHTML, /Searched “boil water” — 4 passages/);
  // Full HTML rebuild (e.g. returning to the chat route) preserves expanded state for message 1 only.
  assert.match(chat.botHtml(m, 1), /class="also work-details" data-progress-group="stream1:1" open>/);
  streamingChat.messages.push({ role: 'user', content: 'Next?' }, { role: 'assistant', content: '', state: 'searching', steps: [{ name: 'found', count: 1 }], sources: [], running: true });
  assert.doesNotMatch(chat.botHtml(streamingChat.messages[3], 3), /data-progress-group="stream1:3" open/);
  // Clicking the preserved Stop button still aborts the stream.
  initialStop.onclick();
  assert.equal(aborted, 1);

  // Citation click inside a collapsed, filtered source group opens the disclosure and clears the filter.
  const videoRef = { kind: 'video', key: 'S2', doc_id: 'vid', title: 'Boiling clip', t: 15 };
  const multiChat = {
    id: 'multi1', title: 'Mixed',
    messages: [
      { role: 'user', content: 'Question' },
      { role: 'assistant', content: 'Read [S1] or watch [S2].', cited: [reference, videoRef], srcType: 'video' },
    ],
  };
  chat.select(multiChat);
  const mEl = new El('div'); mEl.className = 'msg bot'; mEl.setAttribute('id', 'm1');
  mEl.innerHTML = chat.botHtml(multiChat.messages[1], 1);
  chat.wire(mEl);
  const srcGroup = mEl.querySelector('details');
  assert.equal(srcGroup.open, false);
  assert.equal(mEl.querySelector('#src-S1').hidden, true);
  const cite1 = mEl.querySelector('a.cite');
  cite1.onclick({ preventDefault() {} });
  assert.equal(srcGroup.open, true, 'citation opens collapsed source group');
  assert.equal(mEl.querySelector('#src-S1').hidden, false, 'citation clears active filter hiding its source');
  assert.equal(multiChat.messages[1].srcType, '');

  // Storage status live region stays in the accessibility tree (no hidden attribute).
  const rawChatJs = fs.readFileSync(new URL('../../web/chat.js', import.meta.url), 'utf8');
  assert.match(rawChatJs, /id="chatStorage" role="status"><\/p>/);
}
console.log('Chat UI behavior passed (sources, filters, stable Stop/focus, progress disclosure, export redaction, storage failures, streams).');
