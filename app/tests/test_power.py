"""Save power (engine/power.py): the switch, what it does to the local AI and to meaning-based indexing, and that only this
computer may use it. No library, no model and no port: the parts are stood in for where they would start real work.

  python3 -B -m unittest app.tests.test_power
"""
import io, json, sys, tempfile, threading, unittest
from pathlib import Path
from unittest import mock

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT)]
from engine import power  # noqa: E402
import llm_local  # noqa: E402
import retrieval  # noqa: E402


class FakeHandler:
    def __init__(self, ip='127.0.0.1', body=None, command='POST'):
        raw = b'' if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
        self.client_address, self.command = (ip, 1234), command
        self.headers = {'Content-Length': str(len(raw))}
        self.rfile, self.wfile = io.BytesIO(raw), io.BytesIO()
        self.status = None

    def send_response(self, s): self.status = s
    def send_header(self, *a): pass
    def end_headers(self): pass
    def answer(self): return json.loads(self.wfile.getvalue() or b'null')


class Switch(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.file = mock.patch.object(power, 'FILE', Path(self.dir.name) / 'derived' / 'power.json')
        self.file.start()
        self.local, self.index = mock.Mock(), mock.Mock(paused=False)
        power.attach(self.local, self.index)

    def tearDown(self):
        self.file.stop()
        power._parts.update(local=None, index=None)
        self.dir.cleanup()

    def test_off_until_switched_on_and_kept_on_disk(self):
        self.assertFalse(power.saving())
        self.local.save_power.assert_called_with(None)
        self.assertEqual(power.set_saving(True), {'save': True, 'ai_stops_after_s': 60})
        self.local.save_power.assert_called_with(60)
        self.assertTrue(self.index.paused)
        other_local, other_index = mock.Mock(), mock.Mock(paused=False)
        power.attach(other_local, other_index)          # the next start finds it still on
        other_local.save_power.assert_called_with(60)
        self.assertTrue(other_index.paused)
        power.set_saving(False)
        self.assertFalse(other_index.paused)
        other_local.save_power.assert_called_with(None)

    def test_a_damaged_file_means_off(self):
        power.FILE.parent.mkdir(parents=True)
        for text in ('not json', '[]', '{"save": "yes"}'):
            power.FILE.write_text(text, encoding='utf-8')
            self.assertFalse(power.saving(), text)

    def test_only_this_computer(self):
        h = FakeHandler('192.168.1.20', {'save': True})
        power.handle(h, 'POST')
        self.assertEqual(h.status, 403)
        self.assertFalse(power.saving())
        g = FakeHandler('192.168.1.20', command='GET')
        power.handle(g, 'GET')
        self.assertEqual(g.status, 403)

    def test_routes(self):
        h = FakeHandler('127.0.0.1', {'save': True})
        power.handle(h, 'POST')
        self.assertEqual((h.status, h.answer()), (200, {'save': True, 'ai_stops_after_s': 60}))
        g = FakeHandler('::1', command='GET')
        power.handle(g, 'GET')
        self.assertEqual(g.answer()['save'], True)
        for bad in ({'save': 'on'}, {}, b'not json', [True]):
            b = FakeHandler('127.0.0.1', bad)
            power.handle(b, 'POST')
            self.assertEqual(b.status, 400, bad)
        self.assertTrue(power.saving())                  # a bad request changes nothing


class LocalAI(unittest.TestCase):
    def make(self, state='ready'):
        ai = llm_local.Local.__new__(llm_local.Local)   # no file lookup, no runner, no threads
        ai.lock, ai.gen_lock = threading.RLock(), threading.Lock()
        ai.state, ai.last_used, ai.idle_stop = state, 0, llm_local.IDLE_STOP
        ai.stop = mock.Mock()
        return ai

    def test_idle_model_stops_now_and_then_after_a_minute(self):
        ai = self.make()
        ai.save_power(60)
        ai.stop.assert_called_once()
        self.assertEqual(ai.idle_stop, 60)
        ai.save_power(None)
        self.assertEqual(ai.idle_stop, llm_local.IDLE_STOP)

    def test_an_answer_being_written_is_not_cut_off(self):
        ai = self.make()
        with ai.gen_lock:
            ai.save_power(60)
        ai.stop.assert_not_called()
        self.assertEqual(ai.idle_stop, 60)               # it stops after the answer instead

    def test_nothing_to_stop(self):
        for state in ('stopped', 'loading', 'off', 'absent'):
            ai = self.make(state)
            ai.save_power(60)
            ai.stop.assert_not_called()

    def test_idle_stop_counts_from_the_last_answer(self):
        ai = self.make()
        with mock.patch.object(llm_local.time, 'time', return_value=1000):
            ai.last_used = 1000 - 59
            self.assertFalse(ai.stop_if_idle(60))
            ai.last_used = 1000 - 60
            self.assertTrue(ai.stop_if_idle(60))


class Indexing(unittest.TestCase):
    def test_paused_indexer_does_no_work(self):
        fake = mock.Mock(paused=True, status={})
        sleeps = []

        def sleep(s):
            sleeps.append(s)
            if len(sleeps) == 3:
                raise StopIteration
        with mock.patch.object(retrieval.time, 'sleep', sleep), self.assertRaises(StopIteration):
            retrieval.Index.run_forever(fake)
        fake.update.assert_not_called()
        self.assertEqual(fake.status['state'], 'paused to save power')


if __name__ == '__main__':
    unittest.main()
