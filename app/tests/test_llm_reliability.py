"""Pipe lifecycle regressions without loading a model, sleeping or opening a socket."""
import io
import json
import queue
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import assistant
import llm_local


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class Events(queue.Queue):
    def __init__(self, clock):
        super().__init__()
        self.clock = clock
        self.tick = None

    def get(self, block=True, timeout=None):
        if timeout is not None:
            self.clock.advance(timeout)
            if self.tick:
                self.tick()
        return super().get(block=False)


class Process:
    def __init__(self, events, respond=None):
        self.events, self.respond = events, respond
        self.stdin = self
        self.requests = []
        self.killed = False

    def write(self, data):
        request = json.loads(data)
        self.requests.append(request)
        if self.respond:
            self.respond(request, self.events)

    def poll(self):
        return -9 if self.killed else None

    def kill(self):
        self.killed = True

    def wait(self, timeout=None):
        return -9


class HeldLock:
    def __init__(self, clock):
        self.clock = clock

    def acquire(self, timeout):
        self.clock.advance(timeout)
        return False


class GenerationLifecycle(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.patches = [mock.patch.object(llm_local.time, 'monotonic', self.clock),
                        mock.patch.object(llm_local, '_load', return_value={}),
                        mock.patch.object(llm_local, 'runner_path', return_value=None)]
        for patch in self.patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.local = llm_local.Local()
        self.local.path, self.local.fit = Path('/model.gguf'), {'fits': True}
        self.events = Events(self.clock)
        self.proc = self.attach()

    def attach(self, respond=None):
        proc = Process(self.events, respond)
        self.local.proc, self.local.events, self.local.state = proc, self.events, 'ready'
        return proc

    def generate(self, **kwargs):
        return self.local.generate([['private prompt', False]], 10, kwargs.pop('cancelled', lambda: False), kwargs.pop('on_text', lambda text: None), **kwargs)

    def test_cancel_while_queued_does_not_touch_active_runner(self):
        self.local.gen_lock = HeldLock(self.clock)
        events = []
        done = self.generate(cancelled=lambda: self.clock.now >= .2, on_event=events.append)
        self.assertEqual(done['reason'], 'cancel')
        self.assertEqual(self.proc.requests, [])
        self.assertFalse(self.proc.killed)
        self.assertEqual([ev['phase'] for ev in events], ['queued', 'cancelled'])

    def test_queue_has_own_deadline_without_retiring_active_runner(self):
        self.local.gen_lock = HeldLock(self.clock)
        with mock.patch.object(llm_local, 'QUEUE_WAIT', .2), self.assertRaises(llm_local.GenerationError) as error:
            self.generate()
        self.assertEqual(error.exception.code, 'queue_timeout')
        self.assertLessEqual(self.clock.now, .3)
        self.assertFalse(self.proc.killed)

    def test_failed_runner_spawn_closes_log_and_allows_next_request(self):
        self.local.state, self.local.proc, self.local.events = 'stopped', None, None
        logs = []

        def popen(*args, stderr, **kwargs):
            logs.append(stderr)
            if len(logs) == 1:
                raise FileNotFoundError('/private/missing-runner')
            return self.proc

        def respond(request, events):
            if request['op'] == 'gen':
                events.put({'ev': 'done', 'id': request['id'], 'reason': 'eog'})

        with tempfile.TemporaryDirectory() as data, \
                mock.patch.object(llm_local.paths, 'DATA', Path(data)), \
                mock.patch.object(self.local, '_argv', return_value=['/fixture/runner']), \
                mock.patch.object(llm_local.subprocess, 'Popen', side_effect=popen), \
                mock.patch.object(llm_local.threading, 'Thread') as reader:
            reader.return_value.start.side_effect = lambda: self.attach(respond)
            with self.assertRaises(llm_local.GenerationError) as raised:
                self.generate()
            self.assertEqual(raised.exception.code, 'unavailable')
            self.assertNotIn('/private/', str(raised.exception))
            self.assertEqual(self.local.state, 'stopped')
            self.assertIsNone(self.local.proc)
            self.assertIsNone(self.local.events)
            self.assertTrue(logs[0].closed)
            self.assertEqual(self.generate()['reason'], 'eog')
            self.assertTrue(logs[1].closed)
        reader.return_value.start.assert_called_once()

    def test_permission_error_opening_start_log_leaves_no_runner(self):
        self.local.state, self.local.proc, self.local.events = 'stopped', None, None
        with tempfile.TemporaryDirectory() as data, \
                mock.patch.object(llm_local.paths, 'DATA', Path(data)), \
                mock.patch.object(Path, 'open', side_effect=PermissionError('/private/start-log')), \
                mock.patch.object(llm_local.subprocess, 'Popen') as popen:
            with self.assertRaises(llm_local.GenerationError) as raised:
                self.generate()
        self.assertEqual(raised.exception.code, 'unavailable')
        self.assertNotIn('/private/', str(raised.exception))
        self.assertEqual(self.local.state, 'stopped')
        self.assertIsNone(self.local.proc)
        self.assertIsNone(self.local.events)
        popen.assert_not_called()

    def test_reader_start_failure_retires_already_launched_child(self):
        self.local.state, self.local.proc, self.local.events = 'stopped', None, None
        self.proc.stdin, self.proc.stdout = io.BytesIO(), io.BytesIO()
        with tempfile.TemporaryDirectory() as data, \
                mock.patch.object(llm_local.paths, 'DATA', Path(data)), \
                mock.patch.object(self.local, '_argv', return_value=['/fixture/runner']), \
                mock.patch.object(llm_local.subprocess, 'Popen', return_value=self.proc), \
                mock.patch.object(llm_local.threading, 'Thread') as reader:
            reader.return_value.start.side_effect = RuntimeError('cannot start thread')
            with self.assertRaises(llm_local.GenerationError) as raised:
                self.generate()
        self.assertEqual(raised.exception.code, 'unavailable')
        self.assertTrue(self.proc.killed)
        self.assertTrue(self.proc.stdin.closed)
        self.assertTrue(self.proc.stdout.closed)
        self.assertEqual(self.local.state, 'stopped')
        self.assertIsNone(self.local.proc)
        self.assertIsNone(self.local.events)
        self.assertFalse(self.local.gen_lock.locked())

    def test_stalled_runner_is_retired_lock_released_and_next_request_loads_cleanly(self):
        with mock.patch.object(llm_local, 'PROMPT_STALL', .2), mock.patch.object(llm_local, 'CANCEL_GRACE', .2):
            with self.assertRaises(llm_local.GenerationError) as error:
                self.generate()
        self.assertEqual(error.exception.code, 'stall')
        self.assertTrue(self.proc.killed)
        self.assertFalse(self.local.gen_lock.locked())
        self.assertEqual(self.local.state, 'stopped')
        self.assertEqual(self.proc.requests[-1], {'op': 'cancel', 'id': 1})
        self.events = Events(self.clock)
        def respond(req, events):
            if req['op'] == 'gen':
                events.put({'ev': 'tok', 'id': req['id'], 't': 'fresh'})
                events.put({'ev': 'done', 'id': req['id'], 'reason': 'eog', 'prompt_ms': 12, 'gen_ms': 3})
        text = []
        with mock.patch.object(self.local, '_spawn', side_effect=lambda: self.attach(respond)) as spawn:
            done = self.generate(on_text=text.append)
        spawn.assert_called_once()
        self.assertEqual(done['id'], 2)
        self.assertEqual(text, ['fresh'])

    def test_active_cancel_is_correlated_and_acknowledgement_preserves_runner(self):
        def respond(req, events):
            if req['op'] == 'cancel':
                events.put({'ev': 'done', 'id': req['id'], 'reason': 'cancel'})
        self.proc.respond = respond
        done = self.generate(cancelled=lambda: bool(self.proc.requests))
        self.assertEqual(done['reason'], 'cancel')
        self.assertEqual(self.proc.requests[-1], {'op': 'cancel', 'id': 1})
        self.assertFalse(self.proc.killed)
        self.assertFalse(self.local.gen_lock.locked())

    def test_unresponsive_cancel_is_forced_within_grace(self):
        with mock.patch.object(llm_local, 'CANCEL_GRACE', .3):
            done = self.generate(cancelled=lambda: bool(self.proc.requests))
        self.assertEqual(done['reason'], 'cancel')
        self.assertTrue(self.proc.killed)
        self.assertLess(self.clock.now, .5)
        self.assertFalse(self.local.gen_lock.locked())

    def test_whole_deadline_wins_even_with_regular_native_progress(self):
        self.events.tick = lambda: self.events.put({'ev': 'phase', 'id': 1, 'phase': 'prompt', 'n_processed': 100})
        with mock.patch.object(llm_local, 'CANCEL_GRACE', .2), self.assertRaises(llm_local.GenerationError) as error:
            self.generate(deadline=.4)
        self.assertEqual(error.exception.code, 'deadline')
        self.assertTrue(self.proc.killed)
        self.assertLess(self.clock.now, .8)

    def test_unrelated_request_events_do_not_keep_stalled_request_alive(self):
        self.events.tick = lambda: self.events.put({'ev': 'tok', 'id': 999, 't': 'unrelated'})
        with mock.patch.object(llm_local, 'PROMPT_STALL', .2), mock.patch.object(llm_local, 'CANCEL_GRACE', .2):
            with self.assertRaises(llm_local.GenerationError) as error:
                self.generate()
        self.assertEqual(error.exception.code, 'stall')

    def test_native_metrics_pass_through_without_prompt_or_token_text(self):
        def respond(req, events):
            if req['op'] == 'gen':
                events.put({'ev': 'phase', 'id': req['id'], 'phase': 'generation', 'prompt_ms': 42, 'n_prompt': 200, 'n_reused': 100})
                events.put({'ev': 'tok', 'id': req['id'], 't': 'private answer'})
                events.put({'ev': 'done', 'id': req['id'], 'reason': 'eog', 'prompt_ms': 42, 'gen_ms': 7, 'n_gen': 3})
        self.proc.respond = respond
        events = []
        self.generate(on_event=events.append)
        self.assertEqual(events[-1]['phase'], 'complete')
        self.assertEqual(events[-1]['request_id'], 1)
        self.assertEqual(events[-1]['prompt_ms'], 42)
        self.assertEqual(events[-1]['gen_ms'], 7)
        self.assertNotIn('private', json.dumps(events))

    def test_length_limit_is_incomplete_and_preserves_finished_runner(self):
        def respond(request, events):
            if request['op'] == 'gen':
                events.put({'ev': 'tok', 'id': request['id'], 't': 'An unfinished answer'})
                events.put({'ev': 'done', 'id': request['id'], 'reason': 'length' if request['id'] == 1 else 'eog',
                            'prompt_ms': 20, 'gen_ms': 5, 'n_gen': 10})
        self.proc.respond = respond
        runtime = []
        with self.assertRaises(llm_local.GenerationError) as error:
            self.generate(on_event=runtime.append)
        self.assertEqual(error.exception.code, 'output_limit')
        self.assertIn('incomplete', str(error.exception))
        self.assertEqual(runtime[-1]['phase'], 'error')
        self.assertEqual(runtime[-1]['reason'], 'length')
        self.assertEqual(runtime[-1]['n_gen'], 10)
        self.assertNotIn('complete', [event['phase'] for event in runtime])
        self.assertFalse(self.proc.killed)
        self.assertEqual(self.local.state, 'ready')
        self.assertFalse(self.local.gen_lock.locked())
        self.assertEqual(self.generate()['reason'], 'eog')

    def test_opt_in_trace_contains_only_safe_correlated_metadata(self):
        def respond(req, events):
            if req['op'] == 'gen':
                events.put({'ev': 'phase', 'id': req['id'], 'phase': 'generation', 'prompt_ms': 42,
                            'segments': [['secret source /private/path', False]], 'msg': 'private native detail'})
                events.put({'ev': 'done', 'id': req['id'], 'reason': 'eog', 'gen_ms': 7, 't': 'private answer'})
        self.proc.respond = respond
        with mock.patch.dict(llm_local.os.environ, {'LASTBOOK_AI_TRACE_PHASES': '1'}), mock.patch('builtins.print') as output:
            self.generate()
        lines = [call.args[0] for call in output.call_args_list if call.args[0].startswith('local AI phase: ')]
        trace = [json.loads(line.split(': ', 1)[1]) for line in lines]
        self.assertEqual(trace[-1]['phase'], 'complete')
        self.assertEqual(trace[-1]['request_id'], 1)
        self.assertIn('at_monotonic_s', trace[-1])
        self.assertIn('at_unix_s', trace[-1])
        self.assertNotIn('private', ''.join(lines))
        self.assertNotIn('secret', ''.join(lines))
        self.assertNotIn('prompt', trace[-1])

    def test_phase_trace_is_off_unless_explicitly_enabled(self):
        self.proc.respond = lambda req, events: events.put({'ev': 'done', 'id': req['id'], 'reason': 'eog'})
        with mock.patch.dict(llm_local.os.environ, {'LASTBOOK_AI_TRACE_PHASES': '0'}), mock.patch('builtins.print') as output:
            self.generate()
        output.assert_not_called()

    def test_stream_callback_failure_retires_unfinished_runner(self):
        self.proc.respond = lambda req, events: events.put({'ev': 'tok', 'id': req['id'], 't': 'piece'})
        with self.assertRaises(ValueError):
            self.generate(on_text=mock.Mock(side_effect=ValueError('disconnected')))
        self.assertTrue(self.proc.killed)
        self.assertFalse(self.local.gen_lock.locked())


class AssistantDeadline(unittest.TestCase):
    def test_shared_chat_deadline_stops_before_next_tool_and_keeps_sources(self):
        clock, events = Clock(), []
        source = {'kind': 'html', 'doc_id': 'guide', 'page': 1, 'title': 'Guide'}
        fake_local = mock.Mock()
        fake_local.available.return_value = True
        fake_local.ensure_running.return_value = None
        deadlines = []
        def model_round(msgs, tools, cancelled, wrote, set_state, runtime, deadline):
            deadlines.append(deadline)
            return '', {0: {'id': 'call_0', 'name': 'read_pages', 'args': '{}'},
                        1: {'id': 'call_1', 'name': 'read_pages', 'args': '{}'}}
        def context(about, sess):
            sess.add(source)
            return 'Reference page'
        def tool(*args):
            clock.advance(301)
            return 'page text', {'count': 1}
        with mock.patch.object(assistant.time, 'monotonic', clock), mock.patch.object(assistant, 'CHAT_WAIT', 300), \
             mock.patch.object(assistant, 'LOCAL', fake_local), mock.patch.object(assistant, 'context_for', side_effect=context), \
             mock.patch.object(assistant, '_local_round', side_effect=model_round), \
             mock.patch.object(assistant, 'run_tool', side_effect=tool) as run_tool:
            assistant.chat([{'role': 'user', 'content': 'question'}], {'doc_id': 'guide'}, events.append, lambda: False)
        self.assertEqual(deadlines, [300])
        run_tool.assert_called_once()
        self.assertEqual(events[-1]['type'], 'error')
        self.assertEqual(events[-1]['reason'], 'deadline')
        self.assertEqual(events[-1]['sources'][0]['doc_id'], 'guide')
        self.assertIn('Open the source pages', events[-1]['text'])

    def test_output_limit_emits_error_with_sources_instead_of_completed_chat(self):
        events = []
        source = {'kind': 'html', 'doc_id': 'guide', 'page': 1, 'title': 'Guide'}
        local = mock.Mock()
        local.available.return_value = True
        local.ensure_running.return_value = None
        def context(about, sess):
            sess.add(source)
            return 'Reference page'
        def generate(segments, max_tokens, cancelled, on_text, on_event=None, deadline=None):
            on_text('An unfinished answer')
            on_event({'phase': 'error', 'request_id': 7, 'code': 'output_limit', 'reason': 'length'})
            raise llm_local.GenerationError('This answer is incomplete. Open the source pages below.', 'output_limit', 7)
        local.generate.side_effect = generate
        with mock.patch.object(assistant, 'LOCAL', local), mock.patch.object(assistant, 'context_for', side_effect=context):
            assistant.chat([{'role': 'user', 'content': 'question'}], 'doc:guide:1', events.append, lambda: False)
        self.assertEqual(events[-1]['type'], 'error')
        self.assertEqual(events[-1]['error'], 'output_limit')
        self.assertIn('incomplete', events[-1]['text'])
        self.assertEqual(events[-1]['sources'][0]['doc_id'], 'guide')
        self.assertNotIn('done', [event['type'] for event in events])

    def test_local_round_preserves_native_cancellation_reason(self):
        fake_local = mock.Mock()
        fake_local.generate.return_value = {'reason': 'cancel'}
        with mock.patch.object(assistant, 'LOCAL', fake_local):
            self.assertEqual(assistant._local_round([{'role': 'user', 'content': 'question'}], [], lambda: False,
                                                   lambda text: None, lambda state: None), 'stopped')


class HTTPStreamFinalization(unittest.TestCase):
    def chat_with_stream(self, *events):
        body = ''.join('data: ' + (event if isinstance(event, str) else json.dumps({'choices': [event]})) + '\n\n'
                       for event in events)
        response = io.BytesIO(body.encode())
        streamed = []
        with mock.patch.object(assistant, 'LOCAL', None), \
                mock.patch.object(assistant, 'context_for', return_value=None), \
                mock.patch.object(assistant, 'model_open', return_value=response):
            assistant.chat([{'role': 'user', 'content': 'question'}], 'fixture', streamed.append, lambda: False)
        self.assertTrue(response.closed)
        return streamed

    def test_http_stream_with_terminal_marker_completes(self):
        for terminal in ({'finish_reason': 'stop'}, '[DONE]'):
            with self.subTest(terminal=terminal):
                events = self.chat_with_stream({'delta': {'content': 'Complete answer'}}, terminal)
                self.assertEqual(events[-1]['type'], 'done')
                self.assertEqual(events[-1]['answer'], 'Complete answer')

    def test_http_output_limit_does_not_publish_partial_answer_as_done(self):
        events = self.chat_with_stream({'delta': {'content': 'Partial answer'}}, {'finish_reason': 'length'}, '[DONE]')
        self.assertEqual(events[-1]['error'], 'output_limit')
        self.assertNotIn('done', [event['type'] for event in events])

    def test_http_eof_without_terminal_marker_is_incomplete(self):
        events = self.chat_with_stream({'delta': {'content': 'Partial answer'}})
        self.assertEqual(events[-1]['error'], 'incomplete_stream')
        self.assertNotIn('done', [event['type'] for event in events])


if __name__ == '__main__':
    unittest.main()
