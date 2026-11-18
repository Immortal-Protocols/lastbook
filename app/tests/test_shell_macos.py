#!/usr/bin/env python3
"""The Mac shell's watch on the page's processes, with a stand-in web view: no window, no WebKit process. Mac only (imports AppKit).

  PYTHONDONTWRITEBYTECODE=1 <venv python> -B app/tests/test_shell_macos.py [-v]

Issue #20: Lastbook 1.1.8 died at launch on macOS 15 inside -[WKWebView(WKTesting) _networkProcessIdentifier], which until WebKit
313919@main (May 2026, bug 315599) RELEASE_ASSERTed when there was no network process. Nothing in Python can catch that, so the
shell must never ask it. What the PIDs are for must still work: the memory limit (page and GPU measured, the
Networking process as the fixed NETWORK_SHARE), ending a stuck or too-big page with SIGKILL, and starting again at home. Never packaged."""
import os, re, signal, sys, threading, unittest
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT / 'app')]
S = None


def setUpModule():
    global S
    try:
        import AppKit  # noqa: F401
    except ImportError:   # not a Mac, or no PyObjC (packaging/requirements_macos.txt)
        raise unittest.SkipTest('the Mac shell needs AppKit')
    import shell_macos
    S = shell_macos

TESTING_ONLY = ('_networkProcessIdentifier',)   # declared in WebKit's WKWebViewPrivateForTesting.h; the crash in issue #20


class View:
    """Answers like WKWebView: a PID, or 0 when that process does not exist. Asking a testing-only selector is recorded and fails the test."""

    def __init__(self, web=0, gpu=0):
        self.web, self.gpu, self.asked = web, gpu, []

    def respondsToSelector_(self, name):
        return True    # as on macOS 15: the selector is there, so a respondsToSelector_ guard would not have helped

    def _webProcessIdentifier(self):
        return self.web

    def _gpuProcessIdentifier(self):
        return self.gpu

    def _networkProcessIdentifier(self):
        self.asked.append('_networkProcessIdentifier')
        return 0


class Pulse:
    def __init__(self):
        self.ticks = self.resets = 0
        self.paused = 0

    def tick(self):
        self.ticks += 1

    def reset(self):
        self.resets += 1


class Stop(BaseException):
    """Ends _watch_memory's endless loop from a patched time.sleep (BaseException: the loop catches Exception)."""


def shell(view):
    s = S.Shell(bridge=None)
    s.view, s.pulse = view, Pulse()
    return s


class NoTestingSelectors(unittest.TestCase):
    def test_source_asks_no_testing_only_selector(self):
        """Comments may name it; no string literal or call may."""
        for path in (ROOT / 'app' / 'shell_macos.py', HERE / 'mac_offscreen.py'):
            src = path.read_text(encoding='utf-8')
            for name in TESTING_ONLY:
                code = '\n'.join(line.split('#', 1)[0] for line in src.splitlines())
                self.assertIsNone(re.search(rf"['\"]{name}['\"]|\.{name}\s*\(", code), f'{path.name} asks {name}')

    def test_first_tick_with_no_processes_yet(self):
        """build() ticks once before any page loads: no page, GPU or network process yet. It must not ask the network one."""
        v = View()
        s = shell(v)
        s._each_second()
        self.assertEqual(s.pids, (0, 0))
        self.assertEqual(v.asked, [])
        self.assertEqual(s.pulse.ticks, 1)

    def test_tick_records_page_and_gpu(self):
        v = View(web=4242, gpu=4343)
        s = shell(v)
        for _ in range(3):
            s._each_second()
        self.assertEqual(s.pids, (4242, 4343))
        self.assertEqual(v.asked, [])
        self.assertEqual(s.pulse.ticks, 3)


class MemoryWatch(unittest.TestCase):
    GB = 1024 ** 3

    def setUp(self):
        self.saved = (S.MEMORY_LIMIT, S.MEMORY_FLOOR, S._footprint, S.time.sleep)
        S.MEMORY_LIMIT, S.MEMORY_FLOOR = 4 * self.GB, int(1.5 * self.GB)

    def tearDown(self):
        S.MEMORY_LIMIT, S.MEMORY_FLOOR, S._footprint, S.time.sleep = self.saved

    def watch(self, sizes, rounds=3, ended_at=0.0):
        """Runs the real _watch_memory for a few rounds with these footprints by PID; returns the end_page calls."""
        s = shell(View(web=101, gpu=202))
        s._each_second()
        s.ended_at = ended_at
        ended = []
        s.end_page = lambda why, detail: ended.append(why)
        S._footprint = lambda pid: sizes.get(pid)
        left = [rounds]

        def sleep(_):
            if left[0] == 0:
                raise Stop
            left[0] -= 1
        S.time.sleep = sleep
        with self.assertRaises(Stop):
            s._watch_memory()
        return ended

    def test_under_the_limit_nothing_ends(self):
        self.assertEqual(self.watch({101: 1 * self.GB, 202: int(0.5 * self.GB), os.getpid(): int(0.2 * self.GB)}), [])

    def test_over_the_limit_the_page_ends(self):
        ended = self.watch({101: 3 * self.GB, 202: int(0.6 * self.GB), os.getpid(): int(0.5 * self.GB)}, rounds=1)
        self.assertEqual(ended, [S.TOO_BIG])

    def test_the_gpu_share_still_counts(self):
        """Page 3.2 + app 0.4 = 3.6 GB, under 4. The GPU's 0.6 takes it over: the GPU process is still measured."""
        app = int(0.4 * self.GB)
        self.assertEqual(self.watch({101: int(3.2 * self.GB), os.getpid(): app}, rounds=1), [])
        self.assertEqual(self.watch({101: int(3.2 * self.GB), 202: int(0.6 * self.GB), os.getpid(): app}, rounds=1), [S.TOO_BIG])

    def test_the_network_share_is_counted_as_a_fixed_amount(self):
        """Page and GPU 3 GB, app just under what is left: NETWORK_SHARE alone decides. 16 MB short of the limit is over with it;
        48 MB short is under. Before issue #20 the measured Networking footprint (about 7 MB) stood here instead."""
        MB = 1024 ** 2
        self.assertEqual(S.NETWORK_SHARE, 32 * MB)
        page, gpu = int(2.5 * self.GB), int(0.5 * self.GB)
        just_under = lambda short: {101: page, 202: gpu, os.getpid(): S.MEMORY_LIMIT - page - gpu - short}
        self.assertEqual(self.watch(just_under(16 * MB), rounds=1), [S.TOO_BIG])
        self.assertEqual(self.watch(just_under(48 * MB), rounds=1), [])

    def test_a_small_page_is_not_ended(self):
        """Over the limit because of the app itself: ending a 0.5 GB page would give nothing back."""
        self.assertEqual(self.watch({101: int(0.5 * self.GB), 202: int(0.3 * self.GB), os.getpid(): 5 * self.GB}, rounds=1), [])

    def test_quiet_after_ending(self):
        ended = self.watch({101: 5 * self.GB, os.getpid(): 0}, rounds=1, ended_at=S.time.monotonic())
        self.assertEqual(ended, [])


class EndingAPage(unittest.TestCase):
    def setUp(self):
        self.kills = []
        self.saved = S.os.kill
        S.os.kill = lambda pid, sig: self.kills.append((pid, sig))

    def tearDown(self):
        S.os.kill = self.saved

    def test_stuck_page_is_killed_once_and_the_app_starts_again(self):
        s = shell(View(web=5150, gpu=5151))
        s._each_second()
        homes, alerts = [], []
        s.go_home = lambda: homes.append(1)
        s.ask = lambda kind, message, done: alerts.append(message)
        s.end_page(S.STUCK, 'not answering')
        s.end_page(S.STUCK, 'not answering')                 # until WebKit says it has gone, no second kill
        self.assertEqual(self.kills, [(5150, signal.SIGKILL)])  # the page only: never the GPU process
        s.page_process_ended()                                 # WebKit's webViewWebContentProcessDidTerminate:
        self.assertEqual((homes, alerts, s.ended_why, s.pulse.resets), ([1], [S.STUCK], None, 1))

    def test_from_the_memory_thread_it_uses_the_last_tick(self):
        s = shell(View(web=6160, gpu=6161))
        s._each_second()
        s.view.web = 9999                                       # the view is asked on the main thread only
        t = threading.Thread(target=s.end_page, args=(S.TOO_BIG, 'over'))
        t.start()
        t.join()
        self.assertEqual(self.kills, [(6160, signal.SIGKILL)])

    def test_no_page_process_no_kill(self):
        s = shell(View())
        s._each_second()
        s.end_page(S.STUCK, 'not answering')
        self.assertEqual(self.kills, [])


if __name__ == '__main__':
    unittest.main()
