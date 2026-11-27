"""Tests for llm_local.py: turning the AI off must stick, even while the model file is being checked, and a slow load is
left to finish for as long as it keeps getting further.
No model is started and no large file is read: the size, the digest, the measuring and the spawn are all replaced here."""
import hashlib
import json
import queue
import tempfile
import threading
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

import llm_local

TINY = b'0123456789'
FIT = {'ev': 'fit', 'status': 'fits', 'ram_total': 0, 'device_bytes': 1, 'host_bytes': 1, 'memory': []}


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.model = self.dir / llm_local.FILE
        self.model.write_bytes(TINY)
        for patch in (mock.patch.object(llm_local, 'STATE_FILE', self.dir / 'llm' / 'state.json'),
                      mock.patch.object(llm_local, 'SIZE', len(TINY)),
                      mock.patch.object(llm_local, 'SHA256', hashlib.sha256(TINY).hexdigest()),
                      mock.patch.object(llm_local, 'places', lambda: [self.dir])):
            patch.start()
            self.addCleanup(patch.stop)
        self.local = llm_local.Local()
        self.local.runner = Path('fake-runner')
        self.spawned = []
        self.local._spawn = lambda: self.spawned.append(1)

    def fake_run(self, during=None):
        """A stand-in for subprocess.run when measuring; `during` runs while the measuring is going on."""
        def run(argv, **kw):
            self.measured = True
            if during:
                during()
            return mock.Mock(stdout=json.dumps(FIT, separators=(',', ':')).encode(), stderr=b'')
        return mock.patch.object(llm_local.subprocess, 'run', run)


class TurnedOff(Base):
    def test_off_during_measuring_stays_off(self):
        with self.fake_run(during=lambda: self.local.set_enabled(False)):
            self.local.discover()
        self.assertEqual(self.local.state, 'off')
        self.assertFalse(self.local.available())

    def test_off_during_checking_stays_off(self):
        real = hashlib.sha256
        with self.fake_run(), mock.patch.object(llm_local.hashlib, 'sha256', lambda: (self.local.set_enabled(False), real())[1]):
            self.local.discover()
        self.assertEqual(self.local.state, 'off')

    def test_check_and_measure_do_nothing_when_off(self):
        self.local.set_enabled(False)
        with self.fake_run():
            self.assertFalse(self.local._check(self.model))
            self.local._measure()
        self.assertEqual(self.local.state, 'off')
        self.assertFalse(getattr(self, 'measured', False))

    def test_turned_off_model_is_not_started_or_offered(self):
        self.local.state, self.local.path, self.local.fit = 'stopped', self.model, {'fits': True}
        self.local.saved['enabled'] = False
        self.assertFalse(self.local.available())
        self.assertTrue(self.local.ensure_running())      # a sentence saying why not
        self.assertEqual(self.spawned, [])


class Clock:
    """Stands in for the time module inside llm_local, so ten minutes pass at once. `tick` runs once for each sleep."""
    def __init__(self):
        self.now, self.tick = 1000.0, lambda: None

    def time(self):
        return self.now

    def sleep(self, s):
        self.now += s
        self.tick()


class SlowLoad(Base):
    """ensure_running gives up START_WAIT seconds after the load last got further, not START_WAIT seconds after it began."""

    def setUp(self):
        super().setUp()
        self.clock = Clock()
        patch = mock.patch.object(llm_local, 'time', self.clock)
        patch.start()
        self.addCleanup(patch.stop)
        self.lines = queue.Queue()                  # what the model program writes: one JSON line each, None when it ends
        self.proc = mock.Mock(stdout=iter(self.lines.get, None))
        self.proc.poll.return_value = None
        self.proc.wait.return_value = 0
        self.addCleanup(self.lines.put, None)
        self.local.state, self.local.path, self.local.fit = 'stopped', self.model, {'fits': True}
        self.local._spawn = self.spawn

    def spawn(self):
        """What _spawn does, without the program: the real reader takes the lines from self.lines."""
        self.spawned.append(1)
        self.local.state, self.local.pct, self.local.message = 'loading', 0, ''
        self.local.proc = self.proc
        self.local.t_spawn = self.local.t_progress = self.clock.time()
        self.local.furthest = 0
        llm_local.threading.Thread(target=self.local._read, args=(self.proc, queue.Queue()), daemon=True).start()

    def say(self, ev, seen):
        """The program writes one line; returns once the reader has taken it in."""
        self.lines.put(json.dumps(ev).encode())
        end = time.monotonic() + 5
        while not seen() and time.monotonic() < end:
            time.sleep(0.001)
        self.assertTrue(seen(), ev)

    def every(self, seconds, events):
        """Has the program write the next of `events` each time `seconds` have passed."""
        events, due = iter(events), [self.clock.now + seconds]

        def tick():
            if self.clock.now >= due[0]:
                due[0] += seconds
                ev = next(events, None)
                if ev:
                    self.say(ev, self.lines.empty)
                    self.say({'ev': 'fit'}, self.lines.empty)      # once this one is taken, the one before is fully handled
        self.clock.tick = tick

    def test_load_that_keeps_getting_further_is_left_to_finish(self):
        step = llm_local.START_WAIT / 2
        self.every(step, [{'ev': 'progress', 'p': p} for p in range(5, 101, 5)] + [{'ev': 'ready'}])
        t0 = self.clock.now
        self.assertIsNone(self.local.ensure_running())
        self.assertGreater(self.clock.now - t0, 10 * llm_local.START_WAIT)      # far past the old limit
        self.assertEqual(self.local.state, 'ready')
        self.proc.stdin.write.assert_not_called()                                # never told to quit
        self.assertEqual(self.spawned, [1])

    def test_load_that_stops_getting_further_is_stopped(self):
        step = llm_local.START_WAIT / 2
        self.every(step, [{'ev': 'progress', 'p': p} for p in (5, 10, 15)])
        t0 = self.clock.now
        self.assertEqual(self.local.ensure_running(), 'The local AI took too long to start.')
        self.assertAlmostEqual(self.clock.now - t0, 3 * step + llm_local.START_WAIT, delta=1)   # START_WAIT after the last step
        self.assertEqual(self.local.state, 'stopped')                            # the next question may try again
        self.proc.stdin.write.assert_called_once_with(b'{"op":"quit"}\n')

    def test_the_same_percentage_again_does_not_keep_it_waiting(self):
        step = llm_local.START_WAIT / 2
        self.every(step, [{'ev': 'progress', 'p': 40}] * 50)
        t0 = self.clock.now
        self.assertEqual(self.local.ensure_running(), 'The local AI took too long to start.')
        self.assertAlmostEqual(self.clock.now - t0, step + llm_local.START_WAIT, delta=1)

    def test_going_back_and_forth_does_not_keep_it_waiting(self):
        step = llm_local.START_WAIT / 2
        self.every(step, [{'ev': 'progress', 'p': 20}] + [{'ev': 'progress', 'p': p} for p in (19, 20)] * 25)
        t0 = self.clock.now
        self.assertEqual(self.local.ensure_running(), 'The local AI took too long to start.')
        self.assertAlmostEqual(self.clock.now - t0, step + llm_local.START_WAIT, delta=1)   # counted from the first 20
        self.assertEqual(self.local.furthest, 20)

    def test_load_that_never_reports_is_stopped_after_the_wait(self):
        t0 = self.clock.now
        self.assertEqual(self.local.ensure_running(), 'The local AI took too long to start.')
        self.assertAlmostEqual(self.clock.now - t0, llm_local.START_WAIT, delta=1)


class LoadMode(unittest.TestCase):
    def test_judge_keeps_a_reported_load_mode(self):
        self.assertEqual(llm_local.judge(dict(FIT, load_mode='mmap'))['load_mode'], 'mmap')
        self.assertNotIn('load_mode', llm_local.judge(dict(FIT)))

    def test_a_processor_fallback_does_not_change_the_measurement(self):
        local = llm_local.Local()
        local.runner, local.path, local.cpu_fallback = 'lastbook-llm', 'model.gguf', True
        self.assertNotIn('--cpu-only', local._argv(['--measure'], cpu=False))
        self.assertIn('--cpu-only', local._argv())
        self.assertFalse(local._graphics_load_failed(4))          # already on the processor
        local.cpu_fallback = False
        local.fit = {'n_gpu_layers': 0}
        self.assertFalse(local._graphics_load_failed(4))          # nothing was placed on a graphics chip
        local.fit = {'n_gpu_layers': 31}
        self.assertTrue(local._graphics_load_failed(4))
        self.assertTrue(local._graphics_load_failed(5))
        self.assertFalse(local._graphics_load_failed(1))


class GraphicsFallback(Base):
    """A graphics load that exits 4 or 5 is started once on the processor, in the same wait.
    A load that becomes ready, or that never asked for a graphics chip, is not."""

    def setUp(self):
        super().setUp()
        del self.local._spawn
        self.local.state, self.local.path = 'stopped', self.model
        self.local.fit = {'fits': True, 'n_gpu_layers': 31}
        self.launched, self.scripts, self.procs = [], [], []
        self.addCleanup(self._close_procs)

    def _close_procs(self):
        for _proc, q in self.procs:
            q.put(None)

    def _proc(self, lines, code, close):
        q = queue.Queue()
        for line in lines:
            q.put(line)
        if close:
            q.put(None)
        proc = mock.Mock()
        proc.stdin = mock.Mock()

        def iterate():
            while True:
                item = q.get()
                if item is None:
                    return
                yield item

        proc.stdout = iterate()
        proc.wait.return_value = code
        proc.poll.return_value = None
        self.procs.append((proc, q))
        return proc

    def _popen(self, argv, **_kw):
        self.launched.append(list(argv))
        if not self.scripts:
            raise AssertionError('the model was started again: ' + ' '.join(map(str, argv)))
        return self._proc(*self.scripts.pop(0))

    def start(self, scripts):
        self.scripts = list(scripts)
        real_sleep = time.sleep
        with mock.patch.object(llm_local.paths, 'DATA', self.dir), \
                mock.patch.object(llm_local.subprocess, 'Popen', self._popen), \
                mock.patch.object(llm_local, 'START_WAIT', 5), \
                mock.patch.object(llm_local.time, 'sleep', lambda _s: real_sleep(0.005)):
            return self.local.ensure_running()

    def test_a_lost_device_is_ready_on_the_processor(self):
        lost = json.dumps({'ev': 'error', 'code': 'load', 'msg': 'the model could not be loaded'}).encode()
        ready = json.dumps({'ev': 'ready', 'n_ctx': 16384}).encode()
        self.assertIsNone(self.start([([lost], 4, True), ([ready], 0, False)]))
        self.assertEqual(self.local.state, 'ready')
        self.assertTrue(self.local.cpu_fallback)
        self.assertEqual(self.local.status()['cpu_fallback'], True)
        self.assertEqual(len(self.launched), 2)
        self.assertNotIn('--cpu-only', self.launched[0])
        self.assertIn('--cpu-only', self.launched[1])
        self.assertEqual(self.launched[0].count('--ctx'), 1)

    def test_a_graphics_load_that_gets_ready_is_not_restarted(self):
        ready = json.dumps({'ev': 'ready', 'n_ctx': 16384}).encode()
        self.assertIsNone(self.start([([ready], 0, False)]))
        self.assertEqual(len(self.launched), 1)
        self.assertNotIn('--cpu-only', self.launched[0])
        self.assertFalse(self.local.cpu_fallback)

    def test_the_processor_is_not_tried_twice(self):
        lost = json.dumps({'ev': 'error', 'code': 'load', 'msg': 'the model could not be loaded'}).encode()
        oom = json.dumps({'ev': 'error', 'code': 'context', 'msg': 'not enough memory'}).encode()
        why = self.start([([lost], 4, True), ([oom], 5, True)])
        self.assertEqual(self.local.state, 'error')
        self.assertIn('not enough free memory', why)
        self.assertEqual(len(self.launched), 2)
        self.assertIn('--cpu-only', self.launched[1])
        self.assertFalse(self.local.available())

    def test_a_fit_with_no_graphics_layers_is_not_switched(self):
        self.local.fit = {'fits': True, 'n_gpu_layers': 0}
        lost = json.dumps({'ev': 'error', 'code': 'load', 'msg': 'the model could not be loaded'}).encode()
        why = self.start([([lost], 4, True)])
        self.assertEqual(len(self.launched), 1)
        self.assertNotIn('--cpu-only', self.launched[0])
        self.assertFalse(self.local.cpu_fallback)
        self.assertEqual(self.local.state, 'error')
        self.assertIn('could not load the model file', why)

    def test_an_unexpected_exit_is_not_a_processor_fallback(self):
        why = self.start([([], 1, True)])
        self.assertEqual(len(self.launched), 1)
        self.assertFalse(self.local.cpu_fallback)
        self.assertEqual(self.local.state, 'stopped')
        self.assertIn('interrupted', why)

    def test_a_quit_is_not_a_processor_fallback(self):
        quit_ev = json.dumps({'ev': 'error', 'code': 'quit', 'msg': 'stopping'}).encode()
        self.start([([quit_ev], 4, True)])
        self.assertEqual(len(self.launched), 1)
        self.assertFalse(self.local.cpu_fallback)
        self.assertNotEqual(self.local.state, 'ready')


class _Pipe:
    """Lines a fake child writes. After those, it ends, or waits until the test lets it go."""

    def __init__(self, lines, close):
        self.lines, self.close, self.i = list(lines), close, 0
        self.hold = threading.Event()

    def __iter__(self):
        return self

    def __next__(self):
        if self.i < len(self.lines):
            line = self.lines[self.i]
            self.i += 1
            return line
        if self.close:
            raise StopIteration
        self.hold.wait()
        raise StopIteration


class _Child:
    """A stand-in for the model process. The test decides when its reader runs."""

    def __init__(self, lines, code, close=True):
        self.stdout = _Pipe(lines, close)
        self.stdin = mock.Mock()
        self.code = code

    def wait(self, timeout=None):
        return self.code

    def poll(self):
        return None


class _Library:
    """Enough of a library for one chat turn that finds nothing, so the question reaches the model wait."""

    STOP = set()

    def catalog(self):
        return {'by_id': {}, 'by_path': {}}

    def query_groups(self, _q):
        return '', []


class _WaitHarness(Base):
    """A fake child and events, so a test can order the graphics exit and the questions waiting on it."""

    def setUp(self):
        super().setUp()
        del self.local._spawn
        self.local.state, self.local.path = 'stopped', self.model
        self.local.fit = {'fits': True, 'n_gpu_layers': 31}
        self.launched, self.held = [], []
        self._children = []
        self.addCleanup(self._release)

    def _release(self):
        for child in self._children:
            child.stdout.hold.set()

    def child(self, lines, code, close=True):
        child = _Child(lines, code, close)
        self._children.append(child)
        return child

    @contextmanager
    def running(self, scripts, sleep):
        scripts = list(scripts)
        real_start = llm_local.threading.Thread.start

        def start(thread):
            if thread.name == 'local-ai-read':
                self.held.append(thread)
                return
            real_start(thread)

        def popen(argv, **_kw):
            cmd = [str(part) for part in argv]
            self.launched.append(cmd)
            if not scripts:
                raise AssertionError('the model was started again: ' + ' '.join(cmd))
            return scripts.pop(0)

        with mock.patch.object(llm_local.paths, 'DATA', self.dir), \
                mock.patch.object(llm_local.subprocess, 'Popen', popen), \
                mock.patch.object(llm_local.threading.Thread, 'start', start), \
                mock.patch.object(llm_local.time, 'sleep', sleep):
            yield


class RetryOrder(_WaitHarness):
    """The graphics child's exit, Off, and the wait that would start the processor, in an order the test chooses.
    The child is fake. Events pass the turn from one side to the other; nothing here waits on the clock."""

    def test_off_between_graphics_exit_and_processor_retry_ends_the_question(self):
        """Exit, then Off, then the point where the processor would start: no child, no answer."""
        lost = json.dumps({'ev': 'error', 'code': 'load', 'msg': 'the model could not be loaded'}).encode()
        parked, release = threading.Event(), threading.Event()
        box = {}

        def sleep(_s):
            # The graphics child is already recorded and this question is parked. The other side exits it and turns
            # local AI off, then opens `release`. That is the retry point. The time limit only reports a deadlock.
            if parked.is_set():
                raise AssertionError('the question waited again after local AI was turned off')
            parked.set()
            if not release.wait(30):
                raise AssertionError('Off was never recorded')

        def question():
            try:
                import assistant
                events = []

                def generate(*_a, **_k):
                    raise AssertionError('an answer was generated')

                with mock.patch.object(assistant, 'LOCAL', self.local), \
                        mock.patch.object(assistant, 'S', _Library()), \
                        mock.patch.object(assistant, 'INDEX', None), \
                        mock.patch.object(assistant, 'CHOSEN', False), \
                        mock.patch.object(assistant, 'encyclopedia_hits', lambda *_a, **_k: []), \
                        mock.patch.object(self.local, 'generate', generate):
                    assistant.chat([{'role': 'user', 'content': 'How do I store water?'}], None,
                                   events.append, lambda: False)
                box['events'] = events
            except Exception as exc:
                box['error'] = exc

        with self.running([self.child([lost], 4)], sleep):
            waiter = threading.Thread(target=question, daemon=True)
            waiter.start()
            arrived = False
            try:
                arrived = parked.wait(30)
                if arrived:
                    self.held[0].run()
                    self.assertTrue(self.local.fallback_pending)
                    self.assertIsNone(self.local.proc)
                    self.local.set_enabled(False)
            finally:
                release.set()
            waiter.join(30)
            self.assertFalse(waiter.is_alive(), 'the question did not finish')
        if box.get('error'):
            raise box['error']
        self.assertTrue(arrived, 'the question never reached the wait')
        events = box['events']
        self.assertFalse(any(event.get('type') in ('delta', 'done') for event in events))
        self.assertIn({'type': 'error', 'error': 'model_unavailable', 'text': 'The local AI is turned off.'}, events)
        self.assertEqual(len(self.launched), 1)
        self.assertNotIn('--cpu-only', self.launched[0])
        self.assertEqual(self.local.state, 'off')
        self.assertFalse(self.local.enabled())
        self.assertFalse(self.local.fallback_pending)
        self.assertFalse(self.local.available())

    def test_graphics_exit_before_the_wait_records_the_child_starts_one_processor_child(self):
        """The child exits inside the record, before the wait has a process to follow. One processor child, and no second."""
        lost = json.dumps({'ev': 'error', 'code': 'load', 'msg': 'the model could not be loaded'}).encode()
        seen = []

        def record():
            self.held.pop(0).run()
            seen.append((self.local.proc, self.local.fallback_pending, self.local.cpu_fallback))
            return self.local.proc

        def sleep(_s):
            # The processor child is the one now running. Mark it ready so the wait can finish.
            with self.local.lock:
                self.local.state = 'ready'

        self.local._record_child = record
        with self.running([self.child([lost], 4), self.child([], 0)], sleep):
            why = self.local.ensure_running()
        self.assertEqual(seen, [(None, True, True)])
        self.assertIsNone(why)
        self.assertEqual(self.local.state, 'ready')
        self.assertNotIn('--cpu-only', self.launched[0])
        self.assertIn('--cpu-only', self.launched[1])
        self.assertEqual(len(self.launched), 2)

    def test_the_usual_order_still_recovers_on_the_processor_once(self):
        """Record the graphics child, then it exits, then one processor child. The first start is the ordinary graphics one."""
        lost = json.dumps({'ev': 'error', 'code': 'load', 'msg': 'the model could not be loaded'}).encode()
        order = []
        real = self.local._record_child

        def record():
            order.append('record' if self.local.proc is not None else 'record-gone')
            return real()

        def sleep(_s):
            if 'exit' not in order:
                order.append('exit')
                self.held[0].run()
                return
            order.append('ready')
            with self.local.lock:
                self.local.state = 'ready'

        self.local._record_child = record
        with self.running([self.child([lost], 4), self.child([], 0)], sleep):
            why = self.local.ensure_running()
        self.assertIsNone(why)
        self.assertEqual(order, ['record', 'exit', 'ready'])
        self.assertEqual(len(self.launched), 2)
        self.assertNotIn('--cpu-only', self.launched[0])
        self.assertIn('--cpu-only', self.launched[1])
        self.assertNotIn('mmap', ' '.join(self.launched[0]))
        self.assertEqual(self.local.state, 'ready')

    def test_a_fast_exit_that_is_not_a_graphics_failure_does_not_start_the_processor(self):
        """The runner, not this retry, chooses a discrete GPU's load. An exit that is not a failed graphics load
        still does not start the processor, even when it lands before the wait records the child."""
        self.local.fit = {'fits': True, 'n_gpu_layers': 0}
        lost = json.dumps({'ev': 'error', 'code': 'load', 'msg': 'the model could not be loaded'}).encode()

        def record():
            self.held.pop(0).run()
            return self.local.proc

        def sleep(_s):
            raise AssertionError('the request waited for a processor child')

        self.local._record_child = record
        with self.running([self.child([lost], 4)], sleep):
            why = self.local.ensure_running()
        self.assertIn('could not load the model file', why)
        self.assertEqual(len(self.launched), 1)
        self.assertNotIn('--cpu-only', self.launched[0])
        self.assertFalse(self.local.cpu_fallback)
        self.assertFalse(self.local.fallback_pending)
        self.assertEqual(self.local.state, 'error')


_LOST = json.dumps({'ev': 'error', 'code': 'load', 'msg': 'the model could not be loaded'}).encode()


class _Lane:
    """One waiting question. Each sleep parks at a new step; the test opens that step.
    The 30 second limit only reports a deadlock. The events decide the order."""

    def __init__(self):
        self._lock = threading.Lock()
        self._next = 0
        self._arrived, self._release = {}, {}
        self.why, self.error, self.events = None, None, None
        self.finished = threading.Event()

    def park(self):
        with self._lock:
            n = self._next
            self._next += 1
            arrived = self._arrived.setdefault(n, threading.Event())
            release = self._release.setdefault(n, threading.Event())
        arrived.set()
        if not release.wait(30):
            raise AssertionError('a waiting question was not released')

    def until(self, n):
        with self._lock:
            arrived = self._arrived.setdefault(n, threading.Event())
        if not arrived.wait(30):
            raise AssertionError('a question did not reach the wait')

    def open(self, n):
        with self._lock:
            release = self._release.setdefault(n, threading.Event())
        release.set()


class SharedStartup(_WaitHarness):
    """Two questions already waiting on one graphics start share the single processor retry."""

    def _cpus(self):
        return [cmd for cmd in self.launched if '--cpu-only' in cmd]

    def _finish(self, lane):
        if not lane.finished.wait(30):
            raise AssertionError('a question did not finish')
        if lane.error:
            raise lane.error

    def _ask(self, lanes, cancelled=lambda: False):
        lane = _Lane()

        def run():
            try:
                lane.why = self.local.ensure_running(cancelled=cancelled)
            except Exception as exc:
                lane.error = exc
            finally:
                lane.finished.set()

        thread = threading.Thread(target=run, daemon=True)
        lanes[thread] = lane
        thread.start()
        return lane

    def _parked_pair(self, lanes):
        """Two questions have recorded the graphics child and are waiting. The reader has not run."""
        first = self._ask(lanes)
        first.until(0)
        second = self._ask(lanes)
        second.until(0)
        self.assertEqual(len(self.launched), 1)
        self.assertNotIn('--cpu-only', self.launched[0])
        self.assertEqual(len(self.held), 1)
        return first, second

    def test_two_questions_share_one_processor_retry_and_both_finish(self):
        lanes = {}

        def sleep(_s):
            lanes[threading.current_thread()].park()

        with self.running([self.child([_LOST], 4), self.child([], 0)], sleep):
            first, second = self._parked_pair(lanes)
            self.held[0].run()
            first.open(0)
            first.until(1)
            self.assertEqual(len(self._cpus()), 1)
            with self.local.lock:
                self.local.state = 'ready'
            first.open(1)
            second.open(0)
            self._finish(first)
            self._finish(second)
        self.assertIsNone(first.why)
        self.assertIsNone(second.why)
        self.assertEqual(len(self.launched), 2)
        self.assertEqual(len(self._cpus()), 1)
        self.assertEqual(self.local.state, 'ready')

    def test_stopping_one_question_before_the_retry_leaves_the_other(self):
        lanes = {}
        stopped = threading.Event()

        def sleep(_s):
            lanes[threading.current_thread()].park()

        with self.running([self.child([_LOST], 4), self.child([], 0)], sleep):
            first = self._ask(lanes, cancelled=stopped.is_set)
            first.until(0)
            second = self._ask(lanes)
            second.until(0)
            self.held[0].run()
            stopped.set()
            first.open(0)
            self._finish(first)
            self.assertEqual(first.why, 'stopped')
            self.assertEqual(self._cpus(), [])
            self.assertTrue(self.local.fallback_pending)
            second.open(0)
            second.until(1)
            self.assertEqual(len(self._cpus()), 1)
            with self.local.lock:
                self.local.state = 'ready'
            second.open(1)
            self._finish(second)
        self.assertIsNone(second.why)
        self.assertEqual(len(self.launched), 2)
        self.assertEqual(len(self._cpus()), 1)
        self.assertEqual(self.local.state, 'ready')

    def test_stopping_one_question_after_the_retry_leaves_the_other(self):
        lanes = {}
        stopped = threading.Event()

        def sleep(_s):
            lanes[threading.current_thread()].park()

        with self.running([self.child([_LOST], 4), self.child([], 0)], sleep):
            first = self._ask(lanes, cancelled=stopped.is_set)
            first.until(0)
            second = self._ask(lanes)
            second.until(0)
            self.held[0].run()
            first.open(0)
            first.until(1)
            self.assertEqual(len(self._cpus()), 1)
            stopped.set()
            first.open(1)
            self._finish(first)
            self.assertEqual(first.why, 'stopped')
            self.assertEqual(len(self._cpus()), 1)
            self.assertEqual(self.local.state, 'loading')
            with self.local.lock:
                self.local.state = 'ready'
            second.open(0)
            self._finish(second)
        self.assertIsNone(second.why)
        self.assertEqual(len(self.launched), 2)
        self.assertEqual(len(self._cpus()), 1)

    def test_off_while_two_questions_wait_starts_no_processor_and_both_end(self):
        import assistant
        lanes = {}

        def sleep(_s):
            lanes[threading.current_thread()].park()

        def generate(*_a, **_k):
            raise AssertionError('an answer was generated')

        def chat(lane, text):
            def run():
                try:
                    events = []
                    assistant.chat([{'role': 'user', 'content': text}], None, events.append, lambda: False)
                    lane.events = events
                except Exception as exc:
                    lane.error = exc
                finally:
                    lane.finished.set()

            thread = threading.Thread(target=run, daemon=True)
            lanes[thread] = lane
            thread.start()
            return thread

        with self.running([self.child([_LOST], 4)], sleep), \
                mock.patch.object(assistant, 'LOCAL', self.local), \
                mock.patch.object(assistant, 'S', _Library()), \
                mock.patch.object(assistant, 'INDEX', None), \
                mock.patch.object(assistant, 'CHOSEN', False), \
                mock.patch.object(assistant, 'encyclopedia_hits', lambda *_a, **_k: []), \
                mock.patch.object(self.local, 'generate', generate):
            first, second = _Lane(), _Lane()
            chat(first, 'How do I store water?')
            first.until(0)
            chat(second, 'How do I boil water?')
            second.until(0)
            self.held[0].run()
            self.assertTrue(self.local.fallback_pending)
            self.local.set_enabled(False)
            first.open(0)
            second.open(0)
            self._finish(first)
            self._finish(second)
        for lane in (first, second):
            self.assertFalse(any(event.get('type') in ('delta', 'done') for event in lane.events))
            self.assertIn({'type': 'error', 'error': 'model_unavailable', 'text': 'The local AI is turned off.'}, lane.events)
        self.assertEqual(len(self.launched), 1)
        self.assertEqual(self._cpus(), [])
        self.assertEqual(self.local.state, 'off')
        self.assertFalse(self.local.enabled())
        self.assertFalse(self.local.fallback_pending)
        self.assertFalse(self.local.available())


if __name__ == '__main__':
    unittest.main()
