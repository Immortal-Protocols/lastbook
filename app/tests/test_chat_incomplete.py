"""An answer that did not finish must say so: first aid cut off halfway reads like the whole of it.

Three ways it happens: the token limit, a stream that ends with no `done`, and a local AI that is running but silent.
No model is started: the model server, the local AI and its program are stand-ins. The page's part runs chat.js under Node
and is skipped without it. Never packaged."""
import json
import queue
import shutil
import subprocess
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

import assistant
import llm_local

ROOT = Path(__file__).resolve().parents[2]
NODE = shutil.which('node')
TEXT = '1. Press hard on the wound.\n2. Do not'


def real_chat():
    """test_bridge leaves a stand-in in assistant.chat when it is loaded in the same run; this is the real one."""
    return getattr(sys.modules.get('app.tests.test_bridge'), 'REAL_CHAT', assistant.chat)


class Response(list):
    def close(self):
        pass


def sse(finish=None, end=True):
    chunks = [{'choices': [{'delta': {'content': TEXT}}]}]
    if finish:
        chunks.append({'choices': [{'delta': {}, 'finish_reason': finish}]})
    return Response([f'data: {json.dumps(c)}\n'.encode() for c in chunks] + ([b'data: [DONE]\n'] if end else []))


class Turn(unittest.TestCase):
    """What assistant.chat() tells the page."""

    def chat(self, local, cancelled=lambda: False, events=None):
        events = [] if events is None else events
        with mock.patch.object(assistant, 'local_on', lambda: local), mock.patch.object(assistant, 'hybrid', lambda *a, **k: []), \
                mock.patch.object(assistant, 'encyclopedia_hits', lambda *a, **k: []):
            real_chat()([{'role': 'user', 'content': 'deep cut'}], None, events.append, cancelled)
        return events

    def local(self, generate):
        model = mock.Mock(ensure_running=mock.Mock(return_value=None), generate=generate)
        return mock.patch.object(assistant, 'LOCAL', model)

    def test_local_ai_at_the_token_limit(self):
        for reason, expected in (('length', 'length'), ('eog', None)):
            def generate(segments, max_tokens, cancelled, on_text):
                on_text(TEXT)
                return {'ev': 'done', 'reason': reason}
            with self.local(generate):
                last = self.chat(True)[-1]
            self.assertEqual((last['type'], last['answer'], last.get('incomplete')), ('done', TEXT, expected))

    def test_model_server(self):
        for stream, expected in ((sse('length'), 'length'), (sse(end=False), 'interrupted'), (sse('stop'), None),
                                 (sse('stop', end=False), None), (sse(), None)):
            with mock.patch.object(assistant, 'model_open', return_value=stream):
                last = self.chat(False)[-1]
            self.assertEqual((last['type'], last['answer'], last.get('incomplete')), ('done', TEXT, expected))

    def test_stop_is_noticed_while_the_local_ai_says_nothing(self):
        # The page's Stop only shows as a failed write, so something must be written while the model is silent.
        events = []

        def generate(segments, max_tokens, cancelled, on_text):
            for _ in range(200):
                if cancelled():
                    return {'ev': 'done', 'reason': 'cancel'}
                time.sleep(0.01)
            raise RuntimeError('never noticed')

        def gone():
            return any(e['type'] == 'ping' for e in events)
        with self.local(generate), mock.patch.object(assistant, 'PING_S', 0.05):
            self.chat(True, gone, events)
        self.assertEqual(events[-1], {'type': 'stopped'})


class Program:
    """A stand-in for the running lastbook-llm: it keeps what is written to it and answers only what the test puts in."""

    def __init__(self):
        self.written, self.killed = [], False
        self.stdin = self

    def write(self, data):
        self.written.append(json.loads(data))

    def poll(self):
        return -9 if self.killed else None

    def kill(self):
        self.killed = True

    def wait(self, timeout=None):
        return -9


class Silent(unittest.TestCase):
    def setUp(self):
        for name, value in (('FIRST_WAIT', 0.6), ('NEXT_WAIT', 0.6), ('CANCEL_WAIT', 0.4), ('SLOWEST_READ', 1e9)):
            patch = mock.patch.object(llm_local, name, value)
            patch.start()
            self.addCleanup(patch.stop)
        self.local = llm_local.Local.__new__(llm_local.Local)
        self.local.lock, self.local.gen_lock = threading.RLock(), threading.Lock()
        self.local.next_id, self.local.last_used, self.local.message = 0, 0, ''
        self.program = Program()
        self.local.proc, self.local.events, self.local.state, self.local.pct = self.program, queue.Queue(), 'ready', None

    def ask(self, cancelled=lambda: False, segments=(('q', False),)):
        """Starts one question on a thread: (thread, where its result lands, the text received)."""
        result, text = [], []

        def run():
            try:
                result.append(self.local.generate(list(segments), 10, cancelled, text.append))
            except RuntimeError as e:
                result.append(str(e))
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        return thread, result, text

    def say(self, kind, **more):
        # generate() throws away what is queued before it writes its request, so answer only after that.
        end = time.time() + 5
        while not self.program.written and time.time() < end:
            time.sleep(0.01)
        self.local.events.put({'ev': kind, 'id': 1, **more})

    def assert_dropped(self):
        self.assertTrue(self.program.killed)
        self.assertEqual((self.local.state, self.local.proc), ('stopped', None))   # the next question starts a new one
        self.assertFalse(self.local.gen_lock.locked())

    def test_a_silent_program_is_shut_down(self):
        thread, result, _ = self.ask()
        thread.join(10)
        self.assertIn('stopped responding', result[0])
        self.assert_dropped()

    def test_silence_after_part_of_an_answer(self):
        thread, result, text = self.ask()
        self.say('tok', t='1. Press')
        thread.join(10)
        self.assertEqual(text, ['1. Press'])
        self.assertIn('stopped responding', result[0])
        self.assert_dropped()

    def test_a_slow_program_that_keeps_writing_is_left_alone(self):
        thread, result, text = self.ask()
        for _ in range(5):
            self.say('tok', t='a')
            time.sleep(0.25)           # the whole answer takes far longer than one wait
        self.say('done', reason='eog')
        thread.join(10)
        self.assertEqual((result[0]['reason'], len(text), self.program.killed), ('eog', 5, False))

    def test_a_long_question_is_given_longer_to_be_read(self):
        with mock.patch.object(llm_local, 'SLOWEST_READ', 1000):
            thread, result, _ = self.ask(segments=[('x' * 6400, False)])    # about 2000 tokens: two more seconds
            time.sleep(1.2)
            self.say('done', reason='eog')
            thread.join(10)
        self.assertEqual((result[0]['reason'], self.program.killed), ('eog', False))

    def test_stop_unanswered(self):
        thread, result, _ = self.ask(cancelled=lambda: True)
        thread.join(10)
        self.assertEqual(result, [{'ev': 'done', 'reason': 'cancel'}])
        self.assertEqual(self.program.written[-1], {'op': 'cancel'})
        self.assert_dropped()

    def test_stop_answered_keeps_the_program(self):
        thread, result, _ = self.ask(cancelled=lambda: True)
        self.say('done', reason='cancel')
        thread.join(10)
        self.assertEqual((result[0]['reason'], self.program.killed), ('cancel', False))

    def test_stop_while_waiting_behind_another_answer(self):
        self.local.gen_lock.acquire()
        thread, result, _ = self.ask(cancelled=lambda: True)
        thread.join(5)
        self.assertEqual(result, [{'ev': 'done', 'reason': 'cancel'}])
        self.assertEqual(self.program.written, [])
        self.local.gen_lock.release()


# chat.js's send() and onEvent against a stream the test makes up, then the finished message as the page, Copy and the next
# question see it. The whole of chat.js runs, with app.js's esc and stand-ins for what talks to the page.
PAGE = r"""
const fs = require('fs');
const chat = fs.readFileSync(process.argv[1], 'utf8'), app = fs.readFileSync(process.argv[2], 'utf8');
const line = re => app.split('\n').find(l => re.test(l));
const { events, breaks } = JSON.parse(process.argv[3]);
const stubs = [line(/^const esc\s*=/), line(/^const fileUrl\s*=/), "const ico = () => '';", 'const clock = t => String(t);',
  "const here = () => '#/ask';", 'const localStorage = { getItem: () => null, setItem() {} };', 'const addEventListener = () => {};',
  "const history = { replaceState() {} };", "const $ = () => null, $$ = () => [];", 'const matchMedia = () => ({});',
  'const requestAnimationFrame = () => {};', "const location = { origin: '' };","const api = async url => url.includes('status') ? { online: true } : { results: [] };"].join('\n');
// send() redraws the page as it goes; here only what it keeps in the message matters.
const src = chat.replace(/function (renderSide|renderCtx|renderLog|setBusy|scrollEnd|updateBot)\(([^)]*)\) \{/g, 'function $1($2) { return;')
  .replace(/async function getStatus\(\) \{/, '$& return { online: true };')
  .replace('return { page, count };', 'return { page, count, send, botHtml, plain, history_, now: () => cur };');
const bytes = events.map(e => new TextEncoder().encode('data: ' + JSON.stringify(e) + '\n\n'));
const fetch = async () => ({ ok: true, body: { getReader: () => ({ read: async () => {
  if (bytes.length) return { value: bytes.shift(), done: false };
  if (breaks) throw new TypeError('network error');
  return { done: true };
} }) } });
const C = new Function('fetch', stubs + '\n' + src + '\nreturn Chat;')(fetch);
(async () => {
  await C.send('deep cut');
  const c = C.now(), m = c.messages[1];
  process.stdout.write(JSON.stringify({ m, html: C.botHtml(m, 1), copy: C.plain(m), history: C.history_(c)[1] || null }));
})();
"""


@unittest.skipUnless(NODE, 'needs Node')
class Shown(unittest.TestCase):
    SOURCE = {'key': 'S1', 'kind': 'pdf', 'title': 'First aid', 'doc_id': 'f', 'page': 3}
    SOURCES = {'type': 'sources', 'sources': [SOURCE]}
    DELTA = {'type': 'delta', 'text': '1. Press hard on the wound.'}

    def run_page(self, *events, breaks=False):
        r = subprocess.run([NODE, '-e', PAGE, str(ROOT / 'web/chat.js'), str(ROOT / 'web/app.js'),
                            json.dumps({'events': list(events), 'breaks': breaks})],
                           capture_output=True, text=True, check=True, encoding='utf-8')
        return json.loads(r.stdout)

    def done(self, **more):
        return {'type': 'done', 'answer': self.DELTA['text'], 'sources': [], 'consulted': [], 'invalid': [], **more}

    def assert_incomplete(self, got, why='stopped before it finished'):
        for part in ('html', 'copy'):
            self.assertIn('This answer is incomplete.', got[part])
            self.assertIn(why, got[part])
            self.assertIn('breaks off here', got[part])
        self.assertIn('This answer is incomplete.', got['history']['content'])

    def test_a_finished_answer_has_no_notice(self):
        got = self.run_page(self.DELTA, self.done())
        for part in (got['html'], got['copy'], got['history']['content']):
            self.assertNotIn('incomplete', part)
        self.assertNotIn('error', got['m'])

    def test_the_token_limit(self):
        self.assert_incomplete(self.run_page(self.DELTA, self.done(incomplete='length')), 'length limit')

    def test_a_stream_that_just_ends(self):
        got = self.run_page(self.SOURCES, self.DELTA)
        self.assert_incomplete(got)
        self.assertEqual(got['m']['cited'], [self.SOURCE])            # the pages found stay, to check the answer against
        self.assertNotIn('no linked sources', got['html'])

    def test_a_connection_that_breaks(self):
        got = self.run_page(self.DELTA, breaks=True)
        self.assert_incomplete(got)
        self.assertNotIn('network error', got['html'])

    def test_an_error_after_part_of_an_answer(self):
        got = self.run_page(self.DELTA, {'type': 'error', 'error': 'model_unavailable', 'text': 'The local AI stopped responding.'})
        self.assert_incomplete(got)
        self.assertIn('The local AI stopped responding.', got['html'])

    def test_nothing_written(self):
        got = self.run_page({'type': 'state', 'state': 'thinking'})
        self.assertEqual(got['m']['error'], 'The answer stopped unexpectedly.')
        self.assertNotIn('breaks off', got['html'])

    def test_the_persons_own_stop(self):
        got = self.run_page(self.DELTA, {'type': 'stopped'})
        self.assertTrue(got['m']['content'].endswith('(Stopped.)'))
        self.assertNotIn('incomplete', got['m'])


if __name__ == '__main__':
    unittest.main()
