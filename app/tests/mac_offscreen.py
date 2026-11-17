"""Test entry point, never packaged: the product's shell_macos and bridge, in a window that stays off-screen and never takes focus.

The file channel, the recorded browser, the automatic answers to dialogs and the chat stub all live here, not in the product.
Refuses to run if a model could load: this Mac runs no AI models.
  python mac_offscreen.py --run NAME --data FOLDER [--stub-chat] [--memory-limit BYTES]"""
import argparse, json, os, subprocess, sys, threading, time, traceback
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
ROOT = APP.parent
ap = argparse.ArgumentParser()
ap.add_argument('--run', required=True)
ap.add_argument('--data', required=True)
ap.add_argument('--stub-chat', action='store_true')
ap.add_argument('--memory-limit', type=int)
ap.add_argument('--bad-rules', action='store_true')
# Controls, to show that each layer alone does what it is credited with. Each takes one layer away.
ap.add_argument('--no-rule-list', action='store_true')
ap.add_argument('--features-as-before', action='store_true')
ap.add_argument('--allow-frames', action='store_true', help='frames may go anywhere: only the rule list stands in the way')
ap.add_argument('--no-csp', action='store_true')
ap.add_argument('--frame-scripts', action='store_true', help='no allowsContentJavaScript=false for frames')
ap.add_argument('--old-frame-rule', action='store_true', help='data: and blob: frames allowed again')
a = ap.parse_args()
OUT = ROOT / 'derived' / 'app-build' / 'mac-run' / a.run
CTL = OUT / 'ctl'
CTL.mkdir(parents=True, exist_ok=True)
os.environ['LASTBOOK_DATA'] = a.data
os.environ['SURVIVAL_MODEL_BASE'] = 'http://127.0.0.1:9'    # dead: port 19443 is never contacted
os.environ['SURVIVAL_DISABLE_INDEX_WATCH'] = '1'
sys.dont_write_bytecode = True
sys.modules['onnxruntime'] = None                          # importing it now raises ImportError
sys.path[:0] = [str(ROOT), str(APP)]

import AppKit, Foundation, WebKit, objc  # noqa: E402
from PyObjCTools import AppHelper  # noqa: E402
was_front = AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()    # started by the frontmost app, a process is handed focus: see sample()
app = AppKit.NSApplication.sharedApplication()
app.setActivationPolicy_(2)    # prohibited: no Dock icon, no menu bar, cannot be activated. Accessory (1) was handed focus when the frontmost app started it.

import server, retrieval, assistant  # noqa: E402
server.init(no_index=True)
if retrieval.AVAILABLE or server.INDEX.emb is not None:
    raise SystemExit('a model is available; refusing to run on this Mac')
import bridge as B  # noqa: E402
import shell_macos as S  # noqa: E402

logs = {n: open(OUT / f'{n}.jsonl', 'a', buffering=1) for n in ('bridge', 'browser', 'asks', 'mem', 'stub', 'leave', 'decide')}


def rec(name, **k):
    logs[name].write(json.dumps({'t': round(time.time(), 3), **k}) + '\n')


if a.stub_chat:
    def stub_status():
        return {'online': True, 'model': 'TEST-STUB-NOT-A-MODEL', 'error': None, 'index': dict(server.INDEX.status)}

    def stub_chat(messages, about, emit, cancelled):
        q = (messages[-1].get('content') if messages else '') or ''
        rec('stub', q=str(q)[:80], what='start')
        emit({'type': 'state', 'state': 'Thinking (test stub)'})
        for i in range(30):
            if cancelled():
                rec('stub', what='cancelled', at=i)
                emit({'type': 'stopped'})
                return
            time.sleep(0.2)
            emit({'type': 'delta', 'text': f'word{i} '})
        rec('stub', what='finished')
        emit({'type': 'done', 'answer': ' '.join(f'word{i}' for i in range(30)) + ' (test stub, no model)', 'sources': [], 'consulted': [], 'invalid': [], 'latency': {}})
    assistant.model_status = stub_status
    assistant.chat = stub_chat

if a.memory_limit:
    S.MEMORY_LIMIT = a.memory_limit
if a.bad_rules:
    S.NO_NETWORK = '[not a rule list'
if a.no_rule_list:
    S.NO_NETWORK = json.dumps([{'trigger': {'url-filter': '^nothing-ever-matches:'}, 'action': {'type': 'block'}}])
if a.features_as_before:
    S.FEATURES_OFF = ('PeerConnectionEnabled', 'NavigationAPIEnabled')
if a.no_csp:
    server.Handler.SAVED_PAGE_CSP = server.Handler.ZIM_CSP = "frame-ancestors 'self'"
if a.old_frame_rule:
    _frame_url_ok = B.Bridge.frame_url_ok
    B.Bridge.frame_url_ok = lambda self, url: url.startswith(('about:', 'data:', 'blob:')) or _frame_url_ok(self, url)


class ScriptsInFrames(S._Guard):
    def webView_decidePolicyForNavigationAction_preferences_decisionHandler_(self, webview, action, preferences, handler):
        handler(self.shell.decide(action), preferences)


class Offscreen(S.Shell):
    def make_window(self):
        screens = AppKit.NSScreen.screens()
        x = min(s.frame().origin.x for s in screens) - S.SIZE[0] - 4000
        y = min(s.frame().origin.y for s in screens) - S.SIZE[1] - 4000
        w = AppKit.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(Foundation.NSMakeRect(x, y, *S.SIZE), 0, AppKit.NSBackingStoreBuffered, False)
        w.setReleasedWhenClosed_(False)
        w.setCollectionBehavior_((1 << 4) | (1 << 6))   # stationary, ignored by window cycling
        w.setIgnoresMouseEvents_(True)
        w.setCanHide_(False)
        return w

    def build(self):
        super().build()
        if a.frame_scripts:
            self.guard = ScriptsInFrames.alloc().init()
            self.guard.setShell_(self)
            self.view.setNavigationDelegate_(self.guard)

    def decide(self, action):
        target = action.targetFrame()
        decision = super().decide(action)
        if a.allow_frames and target is not None and not target.isMainFrame():
            decision = S.POLICY_ALLOW
        rec('decide', url=str(action.request().URL().absoluteString())[:200], target=None if target is None else ('top' if target.isMainFrame() else 'frame'), from_top=S._from_top(action), decision=decision)
        return decision

    def leave(self, url, from_top, gesture):
        rec('leave', url=url, from_top=from_top, gesture=gesture)
        super().leave(url, from_top, gesture)

    def refuse_to_open(self):
        rec('asks', kind='refused-to-open')     # the product shows a message and quits

    def ask(self, kind, message, done):
        rec('asks', kind=kind, message=message)
        done(True)

    def choose_save_path(self, name, done):
        rec('asks', kind='save', filename=name)
        done(str(OUT / 'saved-download.txt'))


delegate = S.AppDelegate.alloc().init()
app.setDelegate_(delegate)
b = B.Bridge(server, 'stream', B.ORIGIN_MAC, log=lambda row: rec('bridge', **row))
shell = Offscreen(b)


def webkit_helpers():
    """WebKit's helper processes on this Mac, {pid: name}, from ps, as mac_package_smoke.py finds them."""
    rows = subprocess.run(['/bin/ps', '-axo', 'pid=,comm='], capture_output=True, text=True).stdout.splitlines()
    return {int(r.split(None, 1)[0]): r.split(None, 1)[1].strip().rsplit('/', 1)[-1] for r in rows if 'com.apple.WebKit.' in r}


before_webkit = set(webkit_helpers())    # before this window exists: what appears after is this window's, or at worst another app's (more checked, never less)
shell.build()
shell.window.orderFrontRegardless()
shell.view._setWindowOcclusionDetectionEnabled_(False)
pids = {'app': os.getpid()}


def webkit_ids():
    v = shell.view
    for name, sel in (('WebContent', '_webProcessIdentifier'), ('GPU', '_gpuProcessIdentifier')):
        try:
            if v.respondsToSelector_(sel):
                pids[name] = int(getattr(v, sel)())
        except Exception:
            pass
    # Never _networkProcessIdentifier: older system WebKit ends the caller when there is no network process (see MEMORY_LIMIT in shell_macos).
    # The Networking process is the new one since before build(); the socket check in mac_driver.outside() must still see it.
    new = sorted(p for p, n in webkit_helpers().items() if n == 'com.apple.WebKit.Networking' and p not in before_webkit)
    for i, p in enumerate(new):
        pids['Networking' if i == 0 else f'Networking-{i + 1}'] = p
    (OUT / 'pids.json').write_text(json.dumps(pids))


def sample(timer):
    webkit_ids()
    row = {n: S._footprint(p) for n, p in pids.items() if p}
    row['active'] = bool(app.isActive())
    if row['active'] and was_front is not None:      # this test window must never hold focus: give it straight back
        was_front.activateWithOptions_(0)
    row['key'] = bool(shell.window.isKeyWindow())
    try:
        row['front'] = int(AppKit.NSWorkspace.sharedWorkspace().frontmostApplication().processIdentifier())
    except Exception:
        pass
    rec('mem', **row)


sampler = Foundation.NSTimer.scheduledTimerWithTimeInterval_repeats_block_(1.0, True, sample)


def answer(c, value):
    tmp = CTL / f"{c['id']}.tmp"
    tmp.write_text(json.dumps(value, default=str))
    tmp.replace(CTL / f"{c['id']}.out")


def mouse(kind, x, y, window):
    """x, y: CSS pixels from the view's top-left. Goes through WKWebView's own mouse handling, so the page sees a real gesture."""
    h = shell.view.bounds().size.height
    return AppKit.NSEvent.mouseEventWithType_location_modifierFlags_timestamp_windowNumber_context_eventNumber_clickCount_pressure_(
        kind, Foundation.NSMakePoint(x, h - y), 0, Foundation.NSProcessInfo.processInfo().systemUptime(), window.windowNumber(), None, 0, 1, 1.0)


def run_cmd(c):
    try:
        wv, w, k = shell.view, shell.window, c['kind']
        if k == 'js':
            def h(res, err):
                answer(c, {'result': None if res is None else str(res), 'error': str(err) if err else None})
            body = 'return JSON.stringify(await (async () => {' + c['code'] + '\n})())'
            wv.callAsyncJavaScript_arguments_inFrame_inContentWorld_completionHandler_(body, {}, None, WebKit.WKContentWorld.pageWorld(), h)
        elif k == 'shot':
            def h(img, err):
                if img is None:
                    return answer(c, {'error': str(err)})
                rep = AppKit.NSBitmapImageRep.imageRepWithData_(img.TIFFRepresentation())
                rep.representationUsingType_properties_(AppKit.NSBitmapImageFileTypePNG, {}).writeToFile_atomically_(c['path'], True)
                answer(c, {'path': c['path'], 'w': rep.pixelsWide(), 'h': rep.pixelsHigh()})
            wv.takeSnapshotWithConfiguration_completionHandler_(None, h)
        elif k == 'click':
            wv.mouseDown_(mouse(AppKit.NSEventTypeLeftMouseDown, c['x'], c['y'], w))
            wv.mouseUp_(mouse(AppKit.NSEventTypeLeftMouseUp, c['x'], c['y'], w))
            answer(c, {})
        elif k == 'load':
            wv.loadRequest_(Foundation.NSURLRequest.requestWithURL_(Foundation.NSURL.URLWithString_(c['url'])))
            answer(c, {})
        elif k == 'state':
            webkit_ids()
            f = w.frame()
            answer(c, {'url': str(wv.URL()), 'title': str(wv.title()), 'loading': bool(wv.isLoading()), 'frame': [f.origin.x, f.origin.y, f.size.width, f.size.height], 'active': bool(app.isActive()), 'key': bool(w.isKeyWindow()),
                       'windows': [(str(x.className()), bool(x.isVisible()), [x.frame().size.width, x.frame().size.height]) for x in app.windows()], 'pids': pids, 'bridge': b.stats(), 'handlers_in_ucc': len(wv.configuration().userContentController().userScripts()),
                       'mods': sorted(m for m in sys.modules if m.split('.')[0] in ('webview', 'onnxruntime', 'tokenizers', 'clr'))})
        elif k == 'back':
            wv.goBack()
            answer(c, {})
        elif k == 'forward':
            wv.goForward()
            answer(c, {})
        elif k == 'menu':
            m = AppKit.NSMenu.alloc().init()
            for ident in c['ids']:
                it = AppKit.NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(ident, None, '')
                it.setIdentifier_(ident)
                m.addItem_(it)
            wv.willOpenMenu_withEvent_(m, None)
            answer(c, {'left': [str(i.identifier()) for i in m.itemArray()]})
        elif k == 'product_window':
            pw = S.Shell.make_window(shell)      # the product's own window, built and never shown
            answer(c, {'style': int(pw.styleMask()), 'expected': int(S.STYLE), 'title': str(pw.title()), 'visible': bool(pw.isVisible()), 'size': [pw.frame().size.width, pw.frame().size.height]})
        elif k == 'menu_bar':
            S.install_menu(app)
            answer(c, {str(i.submenu().title()): [str(x.title()) for x in i.submenu().itemArray()] for i in app.mainMenu().itemArray()})
        elif k == 'real_panel':
            got = []
            S.Shell.ask(shell, c['what'], 'test message', got.append)
            def press():
                sheet = w.attachedSheet()
                if sheet is None:
                    return answer(c, {'error': 'no sheet'})
                w.endSheet_returnCode_(sheet, c['code'])
                AppHelper.callLater(0.2, lambda: answer(c, {'got': got, 'sheet_class': str(sheet.className()), 'still_attached': w.attachedSheet() is not None}))
            AppHelper.callLater(0.4, press)
        elif k == 'close':
            answer(c, {})
            w.close()
        elif k == 'quit':
            answer(c, {'bye': True})
            app.terminate_(None)
        else:
            answer(c, {'error': 'unknown'})
    except Exception:
        answer(c, {'error': traceback.format_exc()})


def ctl_loop():
    while True:
        for p in sorted(CTL.glob('*.cmd')):
            try:
                c = json.loads(p.read_text())
            except ValueError:
                continue
            p.unlink()
            AppHelper.callAfter(run_cmd, c)
        time.sleep(0.03)


threading.Thread(target=ctl_loop, daemon=True).start()
webkit_ids()
print('up', os.getpid(), flush=True)
app.run()
