"""LM Studio on this computer as the assistant's model: the saved choice, the model list, and the HTTP path's fixes,
against a small stand-in for LM Studio's server on a loopback port. Needs no library and no model. Never shipped.

Run:  python3 -B -m unittest app.tests.test_lmstudio

The stand-in answers in the shapes LM Studio's documentation gives for GET /api/v0/models, GET /api/v1/models,
GET /v1/models and streamed POST /v1/chat/completions.
"""
import http.server
import io
import json
import socket
import sys
import tempfile
import threading
import time
import types
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parents[1])]
import assistant   # noqa: E402
import llm_local   # noqa: E402
import server      # noqa: E402

TEXT = {'id': 'qwen/qwen3-4b', 'object': 'model', 'type': 'llm', 'publisher': 'qwen', 'arch': 'qwen3', 'compatibility_type': 'gguf',
        'quantization': 'Q4_K_M', 'state': 'loaded', 'max_context_length': 32768, 'loaded_context_length': 4096, 'capabilities': ['tool_use']}
VLM = {'id': 'google/gemma-3-4b', 'object': 'model', 'type': 'vlm', 'publisher': 'google', 'arch': 'gemma3', 'compatibility_type': 'gguf',
       'quantization': 'Q4_K_M', 'state': 'not-loaded', 'max_context_length': 131072}
EMBED = {'id': 'text-embedding-nomic-embed-text-v1.5', 'object': 'model', 'type': 'embeddings', 'state': 'not-loaded', 'max_context_length': 2048}
V1_API = {'models': [{'type': 'llm', 'key': 'openai/gpt-oss-20b', 'display_name': 'gpt-oss 20B',
                      'loaded_instances': [{'id': 'openai/gpt-oss-20b', 'config': {'context_length': 16384}}], 'max_context_length': 131072,
                      'capabilities': {'vision': False, 'trained_for_tool_use': True}},
                     {'type': 'embedding', 'key': 'nomic-embed', 'loaded_instances': []}]}


def sse(*chunks):
    out = b''
    for c in chunks:
        out += b'data: ' + json.dumps(c).encode() + b'\n\n'
    return out + b'data: [DONE]\n\n'


def delta(**d):
    return {'id': 'chatcmpl-1', 'object': 'chat.completion.chunk', 'model': 'x', 'choices': [{'index': 0, 'delta': d, 'finish_reason': None}]}


class Fake(http.server.ThreadingHTTPServer):
    """The stand-in. `routes` maps a path to (status, body bytes), or to a list of them for one answer each time;
    `chats` is what each chat request answers, in turn, after `delay` seconds (LM Studio loading the model)."""
    daemon_threads = True

    def __init__(self):
        super().__init__(('127.0.0.1', 0), FakeHandler)
        self.routes, self.chats, self.seen, self.delay = {}, [], [], 0


class FakeHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def answer(self, status, body, kind='application/json'):
        self.send_response(status)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.server.seen.append(('GET', self.path, None))
        got = self.server.routes.get(self.path, (404, b'{"error":"Unexpected endpoint or method."}'))
        status, body = got.pop(0) if isinstance(got, list) and len(got) > 1 else got[0] if isinstance(got, list) else got   # a list: one answer each time, the last one kept
        self.answer(status, body)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.server.seen.append(('POST', self.path, body))
        status, out = self.server.chats.pop(0) if self.server.chats else (500, b'{"error":"no answer set"}')
        time.sleep(self.server.delay)     # after taking its answer, so a later test's answers are not taken by a late reply
        self.answer(status, out, 'text/event-stream' if status == 200 else 'application/json')


def dead_port():
    """A loopback port nothing listens on."""
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port


def real(name):
    """test_bridge, when it runs in the same process, puts stubs in place of assistant.model_status and chat when imported."""
    for mod in ('test_bridge', 'app.tests.test_bridge'):
        tb = sys.modules.get(mod)
        if tb is not None and hasattr(tb, 'REAL_STATUS'):
            return {'model_status': tb.REAL_STATUS, 'chat': tb.REAL_CHAT}[name]
    return getattr(assistant, name)


class FakeLocal:
    """The built-in local AI, found and ready, without its program."""
    def __init__(self, saved):
        self.saved, self.stopped, self.on = saved, [], True

    def available(self):
        return True

    def enabled(self):
        return self.on

    def set_enabled(self, on):
        self.on = on

    def stop(self, why=''):
        self.stopped.append(why)

    def status(self):
        return {'name': llm_local.NAME, 'state': 'stopped'}


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fake = Fake()   # started here, not at import: test_bridge's whole-process check, in the same run, must see no socket
        threading.Thread(target=cls.fake.serve_forever, daemon=True).start()
        cls.port = cls.fake.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.fake.shutdown()
        cls.fake.server_close()

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.state_file = self.tmp / 'derived' / 'llm' / 'state.json'
        self.fake.routes = {'/api/v0/models': (200, json.dumps({'object': 'list', 'data': [VLM, TEXT, EMBED]}).encode())}
        self.fake.chats, self.fake.seen, self.fake.delay = [], [], 0
        self.opened = []
        real_open = assistant.model_open

        def counting_open(req, timeout):
            self.opened.append((req if isinstance(req, str) else req.full_url, timeout))
            return real_open(req, timeout)
        for p in (mock.patch.object(llm_local, 'STATE_FILE', self.state_file), mock.patch.object(llm_local.LOCAL, 'saved', {}),
                  mock.patch.object(assistant, 'LOCAL', None), mock.patch.object(assistant, 'model_open', counting_open),
                  mock.patch.object(assistant, 'model_status', real('model_status')), mock.patch.object(assistant, 'chat', real('chat')),
                  mock.patch.dict(assistant._status, at=0), mock.patch.dict(assistant._lm, at=0, info=None)):
            p.start()
            self.addCleanup(p.stop)

    def choose(self, model='qwen/qwen3-4b', port=None):
        assistant.set_provider('lmstudio', self.port if port is None else port, model)


class SavedChoice(Base):
    def test_missing_key_is_the_old_behaviour(self):
        self.assertIsNone(assistant.provider())
        with mock.patch.object(assistant, 'MODELS_URL', f'http://127.0.0.1:{dead_port()}/v1/models'):
            st = assistant.model_status()
        self.assertEqual((st['provider'], st['model'], st['vision']), (None, assistant.MODEL, True))
        self.assertNotIn('lmstudio', st)
        self.assertEqual(len(self.opened), 1)     # the model server at BASE is asked, as before
        self.assertEqual(assistant.endpoint()['base'], assistant.BASE)

    def test_round_trip_keeps_the_local_ai_settings(self):
        llm_local.LOCAL.saved.update(enabled=False, checked=['/path/to/model', 1, 2])
        self.choose()
        on_disk = json.loads(self.state_file.read_text(encoding='utf-8'))
        self.assertEqual(on_disk['provider'], 'lmstudio')
        self.assertEqual(on_disk['lmstudio'], {'port': self.port, 'model': 'qwen/qwen3-4b', 'vision': False, 'context': 4096})
        self.assertEqual((on_disk['enabled'], on_disk['checked']), (False, ['/path/to/model', 1, 2]))
        with mock.patch.object(llm_local.LOCAL, 'saved', llm_local._load()):    # as the next start of Lastbook reads it
            self.assertEqual(assistant.provider(), 'lmstudio')
            self.assertEqual(assistant.lmstudio_settings()['port'], self.port)

    def test_a_vision_model_is_saved_as_one(self):
        self.choose('google/gemma-3-4b')
        self.assertEqual(llm_local.LOCAL.saved['lmstudio'], {'port': self.port, 'model': 'google/gemma-3-4b', 'vision': True, 'context': None})

    def test_damaged_settings_fall_back(self):
        llm_local.LOCAL.saved.update(provider='ollama', lmstudio={'port': '1234@evil', 'model': 5, 'vision': 'yes', 'context': -1})
        self.assertIsNone(assistant.provider())
        self.assertEqual(assistant.lmstudio_settings(), {'port': 1234, 'model': None, 'vision': False, 'context': None})
        llm_local.LOCAL.saved.update(provider='lmstudio', lmstudio='junk')
        self.assertEqual(assistant.endpoint()['base'], 'http://127.0.0.1:1234')

    def test_ports(self):
        for bad in (0, 70000, -1, True, False, '1234', '1234@evil', 1234.0, None, [1234]):
            with self.assertRaises(ValueError, msg=repr(bad)):
                assistant.valid_port(bad)
            if bad is not None:       # None is 'not given': the saved port stays
                with self.assertRaises(ValueError, msg=repr(bad)):
                    assistant.set_provider('lmstudio', bad, 'm')
        self.assertEqual((assistant.valid_port(1), assistant.valid_port(65535)), (1, 65535))
        self.assertEqual(self.opened, [])
        self.assertNotIn('provider', llm_local.LOCAL.saved)     # nothing half-saved

    def test_every_saved_port_stays_on_this_computer(self):
        for port in (1, 1234, 65535):
            llm_local.LOCAL.saved.update(provider='lmstudio', lmstudio={'port': port})
            self.assertTrue(assistant.LOOPBACK.fullmatch(assistant.endpoint()['base'] + '/v1/chat/completions'))

    def test_bad_choices(self):
        for bad in ('ollama', None, 1, 'LMSTUDIO'):
            with self.assertRaises(ValueError):
                assistant.set_provider(bad)
        for bad in ('', 'x' * 201, 'a\nb', 7):
            with self.assertRaises(ValueError):
                assistant.set_provider('lmstudio', self.port, bad)


class Switching(Base):
    def test_off_asks_nothing(self):
        assistant.set_provider('off')
        st = assistant.model_status()
        self.assertEqual((st['online'], st['provider'], st['vision']), (False, 'off', False))
        self.assertIn('turned off', st['error'])
        events = []
        assistant.chat([{'role': 'user', 'content': 'water'}], None, events.append, lambda: False)
        self.assertEqual(events, [{'type': 'error', 'error': 'model_unavailable', 'text': assistant.OFF_REASON}])
        self.assertEqual(self.opened, [])      # not LM Studio, not the old model server port
        self.assertEqual(self.fake.seen, [])

    def test_lmstudio_wins_over_the_built_in_model(self):
        local = FakeLocal(llm_local.LOCAL.saved)
        with mock.patch.object(assistant, 'LOCAL', local):
            self.assertTrue(assistant.local_on())          # nothing chosen: the built-in model answers, as before
            st = assistant.model_status()
            self.assertEqual((st['provider'], st['model']), (None, llm_local.NAME))
            self.assertEqual(self.opened, [])
            self.choose()
            self.assertFalse(assistant.local_on())
            self.assertEqual(local.stopped, ['another model was chosen'])
            st = assistant.model_status()
            self.assertEqual((st['provider'], st['model'], st['online'], st['vision']), ('lmstudio', 'qwen/qwen3-4b', True, False))
            self.assertEqual(st['local'], local.status())
            assistant.set_provider('off')
            self.assertFalse(assistant.local_on())
            local.on = False
            assistant.set_provider('builtin')
            self.assertTrue(assistant.local_on() and local.on)    # choosing Built-in turns it back on

    def test_status_fields(self):
        self.choose()
        st = assistant.model_status()
        self.assertEqual(st['lmstudio'], {'port': self.port, 'model': 'qwen/qwen3-4b', 'vision': False, 'context': 4096, 'loaded': True,
                                          'online': True, 'error': None})
        n = len(self.opened)
        assistant.model_status()
        self.assertEqual(len(self.opened), n)          # kept for 15 s, like the old status check
        assistant.set_provider('lmstudio', model='google/gemma-3-4b')
        st = assistant.model_status()
        self.assertEqual((st['vision'], st['lmstudio']['loaded'], st['lmstudio']['context']), (True, False, None))

    def test_status_says_what_is_wrong(self):
        assistant.set_provider('lmstudio', self.port)
        self.assertEqual(assistant.model_status()['error'], 'Choose a model for LM Studio in About.')
        self.choose('gone/model')
        st = assistant.model_status()
        self.assertFalse(st['online'])
        self.assertIn('does not list the model gone/model', st['error'])
        port = dead_port()
        self.choose(port=port)
        st = assistant.model_status()
        self.assertFalse(st['online'])
        self.assertIn(f'not answering on port {port}', st['error'])
        self.assertFalse(any(':19443/' in u or u == assistant.MODELS_URL for u, _ in self.opened))   # the old port is never asked


class ModelList(Base):
    def test_native_list(self):
        found, why = assistant.lmstudio_models(self.port)
        self.assertIsNone(why)
        self.assertEqual(found, [{'id': 'qwen/qwen3-4b', 'loaded': True, 'vision': False, 'tools': True, 'context': 4096},
                                 {'id': 'google/gemma-3-4b', 'loaded': False, 'vision': True, 'tools': False, 'context': None}])
        self.assertEqual([u for u, _ in self.opened], [f'http://127.0.0.1:{self.port}/api/v0/models'])

    def test_newer_list(self):
        self.fake.routes = {'/api/v1/models': (200, json.dumps(V1_API).encode())}
        found, why = assistant.lmstudio_models(self.port)
        self.assertEqual(found, [{'id': 'openai/gpt-oss-20b', 'loaded': True, 'vision': False, 'tools': True, 'context': 16384}])

    def test_openai_list_only(self):
        self.fake.routes = {'/v1/models': (200, json.dumps({'object': 'list', 'data': [{'id': 'some-model', 'object': 'model'},
                                                                                       {'id': 'text-embedding-x'}, {'object': 'model'}, 'junk']}).encode())}
        found, why = assistant.lmstudio_models(self.port)
        self.assertEqual(found, [{'id': 'some-model', 'loaded': False, 'vision': False, 'tools': False, 'context': None}])

    def test_missing_fields(self):
        self.fake.routes = {'/api/v0/models': (200, json.dumps({'data': [{'id': 'a'}, {'id': 'b', 'state': 'loaded', 'loaded_context_length': 'big'},
                                                                         {'id': 'c', 'type': 'vlm', 'capabilities': None}]}).encode())}
        found, why = assistant.lmstudio_models(self.port)
        self.assertEqual([(m['id'], m['loaded'], m['vision'], m['context']) for m in found], [('b', True, False, None), ('a', False, False, None), ('c', False, True, None)])

    def test_damaged_instance_config(self):
        rows = [{'key': 'a', 'loaded_instances': [{'config': 'big'}]}, {'key': 'b', 'loaded_instances': [{'config': [4096]}]},
                {'key': 'c', 'loaded_instances': [{'config': None}]}]
        self.fake.routes = {'/api/v1/models': (200, json.dumps({'models': rows}).encode())}
        found, why = assistant.lmstudio_models(self.port)     # a list it cannot read in full is still a list, not a crash
        self.assertEqual([(m['id'], m['loaded'], m['context']) for m in found], [('a', True, None), ('b', True, None), ('c', True, None)])
        self.choose('a')
        self.assertTrue(assistant.model_status()['online'])

    def test_plain_errors(self):
        self.fake.routes = {'/api/v0/models': (401, b'{"error":"Unauthorized"}')}
        self.assertIn('API token', assistant.lmstudio_models(self.port)[1])
        self.fake.routes = {'/api/v0/models': (200, b'<html>a router</html>')}
        self.assertEqual(assistant.lmstudio_models(self.port), (None, f'Something answers on port {self.port}, but it is not LM Studio.'))
        self.fake.routes = {}
        self.assertIn('not LM Studio', assistant.lmstudio_models(self.port)[1])
        port = dead_port()
        self.assertIn(f'not answering on port {port}', assistant.lmstudio_models(port)[1])
        self.opened.clear()
        self.assertEqual(assistant.lmstudio_models('1234@evil'), (None, 'The port is a number from 1 to 65535.'))
        self.assertEqual(self.opened, [])


class Handler(server.Handler):
    """The engine's own request handler with no socket under it: the body in, the answer out."""
    def __init__(self, body):
        self.rfile, self.wfile = io.BytesIO(body), io.BytesIO()
        self.headers = {'Content-Length': str(len(body))}
        self.path, self.command, self.request_version, self.requestline = '/api/assistant/local', 'POST', 'HTTP/1.1', 'POST'
        self.client_address = ('127.0.0.1', 0)

    def log_message(self, *a):
        pass

    def host_ok(self):
        return True

    origin_ok = lan_ok = host_ok

    def reply(self):
        self.handle_post()
        head, _, body = self.wfile.getvalue().partition(b'\r\n\r\n')
        return int(head.split()[1]), json.loads(body)


def post(obj):
    return Handler(obj if isinstance(obj, bytes) else json.dumps(obj).encode()).reply()


class Route(Base):
    def setUp(self):
        super().setUp()
        p = mock.patch.object(server, 'coverage', lambda: {})
        p.start()
        self.addCleanup(p.stop)

    def test_models_without_the_built_in_runner(self):
        status, out = post({'action': 'models', 'port': self.port})
        self.assertEqual(status, 200)
        self.assertEqual((out['ok'], [m['id'] for m in out['models']]), (True, ['qwen/qwen3-4b', 'google/gemma-3-4b']))
        self.assertEqual(post({'action': 'models', 'port': '1234@evil'}), (200, {'ok': False, 'error': 'The port is a number from 1 to 65535.'}))
        self.assertEqual(post({'action': 'models', 'port': dead_port()})[1]['ok'], False)

    def test_provider(self):
        status, out = post({'action': 'provider', 'provider': 'lmstudio', 'port': self.port, 'model': 'qwen/qwen3-4b'})
        self.assertEqual(status, 200)
        self.assertEqual((out['provider'], out['online'], out['vision'], out['lmstudio']['model']), ('lmstudio', True, False, 'qwen/qwen3-4b'))
        self.assertIn('coverage', out)
        for bad in ({'action': 'provider', 'provider': 'lmstudio', 'port': 70000}, {'action': 'provider', 'provider': 'cloud'},
                    {'action': 'provider', 'provider': 'lmstudio', 'port': True}):
            self.assertEqual(post(bad)[0], 400)
        self.assertEqual(llm_local.LOCAL.saved['lmstudio']['port'], self.port)
        status, out = post({'action': 'provider', 'provider': 'off'})
        self.assertEqual((status, out['provider'], out['online']), (200, 'off', False))

    def test_only_this_computer_chooses(self):
        for body in ({'action': 'models', 'port': self.port}, {'action': 'provider', 'provider': 'lmstudio', 'port': self.port, 'model': 'qwen/qwen3-4b'},
                     {'action': 'provider', 'provider': 'off'}):
            h = Handler(json.dumps(body).encode())
            h.client_address = ('192.0.2.7', 50000)       # a phone the guide is shared with (--lan)
            status, out = h.reply()
            self.assertEqual(status, 403)
        self.assertEqual(self.opened, [])                  # it cannot make this computer try a port
        self.assertNotIn('provider', llm_local.LOCAL.saved)
        h = Handler(json.dumps({'action': 'models', 'port': self.port}).encode())
        h.client_address = ('::ffff:127.0.0.1', 50000)
        self.assertEqual(h.reply()[0], 200)

    def test_old_actions_and_limits(self):
        self.assertEqual(post({'action': 'rescan'})[0], 404)          # no built-in runner in this version
        big = json.dumps({'action': 'provider', 'provider': 'off', 'pad': 'x' * 3000}).encode()
        self.assertNotEqual(post(big)[0], 200)                        # past 2000 bytes the body is not read whole, so not acted on
        self.assertNotIn('provider', llm_local.LOCAL.saved)
        self.assertEqual(post(b'[1, 2]')[0], 404)

    def test_chat_refusal_names_the_reason(self):
        assistant.set_provider('lmstudio', dead_port(), 'm')
        h = Handler(b'{"messages": []}')
        h.path = '/api/chat'
        h.handle_post()
        self.assertIn(b'LM Studio is not answering on port', h.wfile.getvalue())


class Chat(Base):
    """assistant.chat against the stand-in, with an empty library: the search finds nothing and every tool says so."""
    def setUp(self):
        super().setUp()
        lib = types.SimpleNamespace(catalog=lambda: {'by_id': {}})
        for p in (mock.patch.object(assistant, 'S', lib), mock.patch.object(assistant, 'hybrid', lambda *a, **k: [])):
            p.start()
            self.addCleanup(p.stop)

    def ask(self, *answers, history=()):
        self.fake.chats = [a if isinstance(a, tuple) else (200, a) for a in answers]
        events = []
        assistant.model_status()     # as /api/chat does first
        assistant.chat(list(history) + [{'role': 'user', 'content': 'How do I make water safe to drink?'}], None, events.append, lambda: False)
        return events, [b for m, p, b in self.fake.seen if m == 'POST']

    def test_text_only_model(self):
        self.choose()
        events, sent = self.ask(sse(delta(role='assistant'), delta(content='Boil it.')))
        self.assertEqual(events[-1]['type'], 'done')
        self.assertEqual(events[-1]['answer'], 'Boil it.')
        body = sent[0]
        self.assertEqual(body['model'], 'qwen/qwen3-4b')
        self.assertNotIn('view_page', [t['function']['name'] for t in body['tools']])
        self.assertEqual(body['messages'][0]['content'], assistant.SYSTEM_TEXT_ONLY)
        self.assertNotIn('reasoning_effort', body)

    def test_vision_model(self):
        self.choose('google/gemma-3-4b')
        events, sent = self.ask(sse(delta(content='Boil it.')))
        self.assertIn('view_page', [t['function']['name'] for t in sent[0]['tools']])
        self.assertEqual(sent[0]['messages'][0]['content'], assistant.SYSTEM)
        self.assertNotIn('reasoning_effort', sent[0])

    def test_the_old_target_still_gets_its_setting(self):
        ep = {'lmstudio': False, 'base': f'http://127.0.0.1:{self.port}', 'model': assistant.MODEL, 'vision': True, 'context': None, 'loaded': None}
        self.fake.chats = [(200, sse(delta(content='ok')))]
        got = assistant._http_round([{'role': 'user', 'content': 'hi'}], None, lambda: False, lambda t: None, lambda s: None, ep)
        self.assertEqual(got, ('ok', {}))
        self.assertEqual(self.fake.seen[-1][2]['reasoning_effort'], 'low')

    def test_not_loaded_yet(self):
        self.choose('google/gemma-3-4b')
        events, sent = self.ask(sse(delta(content='Boil it.')))
        states = [e for e in events if e['type'] == 'state']
        self.assertEqual(states[0], {'type': 'state', 'state': 'starting', 'provider': 'lmstudio'})
        self.assertEqual([e['state'] for e in states[1:]], ['writing'])
        chat_waits = [t for u, t in self.opened if u.endswith('/v1/chat/completions')]
        self.assertEqual(chat_waits, [assistant.FIRST_WAIT])

    def test_context_is_asked_again_once_loaded(self):
        self.choose('google/gemma-3-4b')
        now = dict(VLM, state='loaded', loaded_context_length=5000)
        self.fake.routes['/api/v0/models'] = [self.fake.routes['/api/v0/models'], (200, json.dumps({'data': [now]}).encode())]   # before, then after the first round
        call = delta(tool_calls=[{'index': 0, 'id': 'c1', 'function': {'name': 'search_library', 'arguments': '{"query": "boil"}'}}])
        history = [{'role': r, 'content': f'{r} {i} ' + 'word ' * 1100} for i in range(3) for r in ('user', 'assistant')]
        events, sent = self.ask(sse(call), sse(delta(content='Boil it.')), history=history)
        self.assertEqual(events[-1]['type'], 'done', events[-1])
        self.assertEqual([m for m, p, b in self.fake.seen], ['GET', 'GET', 'POST', 'GET', 'POST'])   # chosen, status, round, status, round
        self.assertEqual(assistant.endpoint()['context'], 5000)
        self.assertGreater(assistant._tokens(sent[0]['messages'], sent[0]['tools']), 5000 - assistant.ROUND_TOKENS)   # the first round could only guess 8192
        self.assertLessEqual(assistant._tokens(sent[1]['messages'], sent[1]['tools']), 5000 - assistant.ROUND_TOKENS)
        self.assertEqual([t for u, t in self.opened if u.endswith('/completions')], [assistant.FIRST_WAIT, 180])

    def test_reasoning_is_thinking_not_answer(self):
        self.choose()
        events, _ = self.ask(sse(delta(reasoning='The person needs '), delta(reasoning='water steps.'), delta(content='Boil it [S1].')))
        self.assertIn({'type': 'state', 'state': 'thinking'}, events)
        self.assertEqual(''.join(e['text'] for e in events if e['type'] == 'delta'), 'Boil it [S1].')
        self.assertEqual(events[-1]['invalid'], ['S1'])       # still checked like any other answer

    def test_think_tags_left_in_the_answer(self):
        self.choose()
        events, _ = self.ask(sse(delta(content='<think>water'), delta(content=' steps</think>\n\n'), delta(content='Boil it.')))
        self.assertEqual(''.join(e['text'] for e in events if e['type'] == 'delta'), 'Boil it.')
        self.assertEqual(events[-1]['answer'], 'Boil it.')

    def test_think_tag_in_pieces(self):
        self.choose()
        events, _ = self.ask(sse(delta(content='<'), delta(content='think>'), delta(content='water</think>'), delta(content='Boil it.')))
        self.assertEqual(''.join(e['text'] for e in events if e['type'] == 'delta'), 'Boil it.')

    def test_stop_while_lm_studio_loads(self):
        """As in server.py: Stop is seen only when a write to the page fails. LM Studio says nothing while it loads the model."""
        self.choose('google/gemma-3-4b')
        self.fake.delay, self.fake.chats = 4, [(200, sse(delta(content='Boil it.')))]
        gone, t0 = [False], time.time()

        def emit(ev):
            if time.time() - t0 > 0.3:      # the person pressed Stop: the next write fails
                gone[0] = True
        assistant.model_status()
        assistant.chat([{'role': 'user', 'content': 'water'}], None, emit, lambda: gone[0])
        self.assertLess(time.time() - t0, 2.5)
        self.assertTrue(gone[0])

    def test_switching_during_an_answer(self):
        self.choose('google/gemma-3-4b')     # not loaded: after the first round the status is asked again
        call = delta(tool_calls=[{'index': 0, 'id': 'c1', 'function': {'name': 'search_library', 'arguments': '{"query": "boil"}'}}])
        real_tool = assistant.run_tool

        def tool(*a):
            assistant.set_provider('builtin')     # chosen in About while this answer is being written
            return real_tool(*a)
        with mock.patch.object(assistant, 'run_tool', tool):
            events, sent = self.ask(sse(call), sse(delta(content='Boil it.')))
        self.assertEqual((len(sent), events[-1]['type']), (2, 'done'))     # this answer ends where it began
        self.assertFalse(any(u.startswith(assistant.BASE) for u, _ in self.opened))

    def test_tool_call_in_pieces(self):
        self.choose()
        call = [delta(tool_calls=[{'index': 0, 'id': 'call_1', 'type': 'function', 'function': {'name': 'search_', 'arguments': ''}}]),
                delta(tool_calls=[{'index': 0, 'function': {'name': 'library', 'arguments': '{"query": "boil'}}]),
                delta(tool_calls=[{'index': 0, 'function': {'arguments': ' water"}'}}])]
        events, sent = self.ask(sse(*call), sse(delta(content='The library does not cover it.')))
        tools = [e for e in events if e['type'] == 'tool' and e['phase'] == 'done']
        self.assertEqual([(t['name'], t['args']) for t in tools], [('search_library', {'query': 'boil water'})])
        self.assertEqual(sent[1]['messages'][-1]['role'], 'tool')
        self.assertEqual(sent[1]['messages'][-2]['tool_calls'][0]['function'], {'name': 'search_library', 'arguments': '{"query": "boil water"}'})
        self.assertEqual(events[-1]['answer'], 'The library does not cover it.')

    def test_http_errors_are_sentences(self):
        self.choose()
        events, _ = self.ask((401, b'{"error":"Unauthorized"}'))
        self.assertEqual(events[-1]['text'], "LM Studio asks for an API token. Turn off Require Authentication in LM Studio's server settings.")
        events, _ = self.ask((400, b'{"error":"Trying to keep the first 9000 tokens when context the overflows."}'))
        self.assertEqual(events[-1]['text'], 'LM Studio could not answer (error 400: Trying to keep the first 9000 tokens when context the overflows.).')
        events, _ = self.ask(b'data: {"error": {"message": "Model unloaded."}}\n\n')
        self.assertEqual(events[-1]['text'], 'LM Studio could not answer (Model unloaded.).')

    def test_prompt_fits_the_loaded_context(self):
        self.choose()      # loaded with 4096 tokens
        history = [{'role': r, 'content': f'{r} {i} ' + 'word ' * 1100} for i in range(5) for r in ('user', 'assistant')]
        events, sent = self.ask(sse(delta(content='Boil it.')), history=history)
        self.assertEqual(events[-1]['type'], 'done')
        msgs = sent[0]['messages']
        self.assertLessEqual(assistant._tokens(msgs, sent[0]['tools']), 4096 - assistant.ROUND_TOKENS)
        self.assertEqual(msgs[-2]['content'], 'How do I make water safe to drink?')   # the question itself is never dropped
        self.assertNotIn('user 0 ', json.dumps(msgs))                                # the oldest went first

    def test_too_long_even_trimmed(self):
        llm_local.LOCAL.saved.update(provider='lmstudio', lmstudio={'port': self.port, 'model': 'x', 'context': 2048})
        with mock.patch.object(assistant, '_lm', {'at': 9e99, 'port': self.port, 'online': True, 'error': None, 'info': None}):
            events = []
            assistant.chat([{'role': 'user', 'content': 'water'}], None, events.append, lambda: False)
        self.assertIn('too long for the model as LM Studio loaded it', events[-1]['text'])
        self.assertEqual(self.fake.seen, [])


class Budget(unittest.TestCase):
    def test_trims_old_turns_then_long_results(self):
        msgs = [{'role': 'system', 'content': 's' * 2000}, {'role': 'user', 'content': 'old ' * 3000}, {'role': 'assistant', 'content': 'a' * 9000},
                {'role': 'user', 'content': 'now'}, {'role': 'system', 'content': 'r' * 20000},
                {'role': 'user', 'content': [{'type': 'text', 'text': 'page'}, {'type': 'image_url', 'image_url': {'url': 'data:x'}}]}]
        out = assistant._fit_http(msgs, None, 8192)
        self.assertEqual([m['role'] for m in out], ['system', 'user', 'system', 'user'])
        self.assertEqual(out[1]['content'], 'now')            # an image message is not mistaken for the latest question
        self.assertIn('[…shortened to fit]', out[2]['content'])
        self.assertEqual(out[0]['content'], 's' * 2000)       # the instructions stay whole
        self.assertEqual(len(msgs[4]['content']), 20000)      # the conversation itself is not changed
        self.assertIsNone(assistant._fit_http(msgs, None, 1900))
        self.assertEqual(len(assistant._fit_http(msgs, None, None)), 4)     # unknown context: 8192

    def test_turns_still_alternate(self):
        msgs = [{'role': 'system', 'content': 's'}, {'role': 'user', 'content': 'old ' * 3000}, {'role': 'assistant', 'content': 'a' * 300},
                {'role': 'user', 'content': 'q2'}, {'role': 'assistant', 'content': 'a2'}, {'role': 'user', 'content': 'now'}]
        self.assertEqual([m['role'] for m in assistant._fit_http(msgs, None, 4096)], ['system', 'user', 'assistant', 'user'])
        cut = msgs[:1] + [{'role': 'assistant', 'content': 'a' * 9000}] + msgs[3:]    # the history began with an answer: it goes alone
        self.assertEqual([m['role'] for m in assistant._fit_http(cut, None, 4096)], ['system', 'user', 'assistant', 'user'])

    def test_counts_images_and_calls(self):
        img = [{'role': 'user', 'content': [{'type': 'image_url', 'image_url': {'url': 'data:' + 'A' * 100000}}]}]
        self.assertLess(assistant._tokens(img, None), assistant.IMAGE_TOKENS + 10)
        call = [{'role': 'assistant', 'content': '', 'tool_calls': [{'id': 'c', 'function': {'name': 'n', 'arguments': 'x' * 350}}]}]
        self.assertGreater(assistant._tokens(call, None), 100)


if __name__ == '__main__':
    unittest.main()
