import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const file = new URL('../../web/chat.js', import.meta.url);
const script = fs.readFileSync(file, 'utf8').replace('return { page, count };',
  'return { onEvent, botHtml, plain, history_, exportChat, persist, select: c => { cur = c }, saved: () => chats };');

function controller(initial) {
  let stored = initial;
  const downloads = [];
  const context = { Blob,
    localStorage: { getItem: key => key === 'sg.chats' ? stored : null, setItem: (key, value) => { stored = value } },
    location: { origin: 'http://localhost' },
    addEventListener() {}, $: () => null, $$: () => [], fileUrl: path => '/' + path,
    esc: value => String(value ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('"', '&quot;'),
    ico: () => '', clock: n => String(n), here: () => '#/ask/test',
    document: { body: { append() {} }, createElement: () => ({ click() {}, remove() {} }) },
    URL: { createObjectURL: blob => { downloads.push(blob); return 'blob:fixture' }, revokeObjectURL() {} },
    toast() {}, setTimeout() {},
  };
  vm.createContext(context);
  vm.runInContext(script + '\nthis.chat = Chat;', context);
  return { chat: context.chat, downloads, saved: () => stored };
}

const source = (key, title) => ({ key, title, doc_id: key, kind: 'pdf', page: 3 });
const [noticePage, usedPage, consultedPage] = [source('S1', 'Comparison'), source('S2', 'Used'), source('S3', 'Consulted')];
const notice = 'Checked comparison [S1] [S2].';
const body = 'Draft includes the withheld key [S1] and a valid source [S2].';
const event = { type: 'error', error: 'invalid_citations', answer: notice + '\n\n---\n\n' + body,
  invalid: ['S1'], verified_notice: notice, verified_sources: [noticePage, usedPage], consulted: [consultedPage] };
const started = controller(JSON.stringify([{ id: 'test', title: 'Sources', messages: [
  { role: 'user', content: 'Question' },
  { role: 'assistant', content: 'Legacy accepted reply [S2].', cited: [usedPage], consulted: [] },
  { role: 'assistant', content: '', sources: [noticePage, usedPage, consultedPage] },
] }]));
const original = started.chat.saved()[0];
started.chat.onEvent(original.messages[2], event);
assert.equal(original.messages[2].complete, false);
started.chat.persist();

const reopened = controller(started.saved());
const chat = reopened.chat.saved()[0];
reopened.chat.select(chat);
const html = reopened.chat.botHtml(chat.messages[2], 2);
const noticeHtml = /class="verified-notice">(.*?)<\/div><hr>/s.exec(html)[1];
const bodyHtml = /class="answer-body">(.*?)<\/div>/s.exec(html)[1];
assert.match(noticeHtml, /data-key="S1"/);
assert.match(bodyHtml, /\[S1\]/);
assert.doesNotMatch(bodyHtml, /data-key="S1"/);
assert.match(bodyHtml, /data-key="S2"/);
assert.match(html, /Consulted/);
reopened.chat.exportChat(chat);
for (const text of [reopened.chat.plain(chat.messages[2]), await reopened.downloads[0].text()]) {
  assert.match(text, /This answer is unverified.*unavailable: S1/);
  assert.match(text, /withheld key \[S1\] and a valid source \[2\]/);
}
const history = JSON.parse(JSON.stringify(reopened.chat.history_(chat)));
assert.deepEqual(history, [{ role: 'user', content: 'Question' }, { role: 'assistant', content: 'Legacy accepted reply (Used, p. 3).' }]);
// Two consecutive completed answers citing different S1 sources keep distinct original-page links.
const docA = { key: 'S1', title: 'Water Field Manual', doc_id: 'water-manual', kind: 'pdf', page: 2 };
const docB = { key: 'S1', title: 'Camp Stove Guide', doc_id: 'stove-guide', kind: 'pdf', page: 5 };
const twoTurn = { id: 'two-turn', title: 'Two turns', messages: [
  { role: 'user', content: 'Question one' },
  { role: 'assistant', content: 'Answer one [S1].', cited: [docA], consulted: [], complete: true },
  { role: 'user', content: 'Question two' },
  { role: 'assistant', content: 'Answer two [S1].', cited: [docB], consulted: [], complete: true },
] };
reopened.chat.select(twoTurn);
const html1 = reopened.chat.botHtml(twoTurn.messages[1], 1);
const html2 = reopened.chat.botHtml(twoTurn.messages[3], 3);
assert.match(html1, /href="#\/read\/water-manual\?p=2&amp;from=/);
assert.doesNotMatch(html1, /stove-guide/);
assert.match(html2, /href="#\/read\/stove-guide\?p=5&amp;from=/);
assert.doesNotMatch(html2, /water-manual/);
console.log('Verified notice links, incomplete draft persistence, copy/export text, two-turn links and later history passed.');
