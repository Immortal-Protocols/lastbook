#!/usr/bin/env python3
"""Quick release check: Videos, Map and the local AI runner answer from a build.

  python3 -B packaging/smoke_library.py
  python3 -B packaging/smoke_library.py --packaged --app /opt/lastbook --data /path/to/LastbookData

Without --data a made-up library is built under derived/app-build/testdata (app/tests/fixture.py). --packaged imports the
installed tree instead of the checkout, as /opt/lastbook/lastbook.py does. The local AI check starts the bundled runner with
a missing model: it must load and answer with its model_file error, never a socket or a model download.
"""
import argparse
import json
import os
import subprocess
import sys
import threading
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser()
ap.add_argument('--app', help='program folder (default: the checkout, or the installed tree with --packaged)')
ap.add_argument('--packaged', action='store_true', help='import the installed app tree, as the packaged launcher does')
ap.add_argument('--data', help='library folder; default: build the made-up test library')
ap.add_argument('--require-ai', action='store_true', help='fail when the local AI runner is not bundled (release builds use this)')
a = ap.parse_args()

if a.data:
    DATA = Path(a.data).resolve()
else:
    sys.path.insert(0, str(ROOT / 'app' / 'tests'))
    import fixture  # noqa: E402
    DATA = fixture.ensure()

if a.packaged:
    APP = Path(a.app or '/opt/lastbook').resolve()
    sys.frozen = True
    sys._MEIPASS = str(APP)
    sys.path[:0] = [str(APP / 'app'), str(APP), str(APP / 'lib')]
else:
    APP = Path(a.app or ROOT).resolve()
    sys.path[:0] = [str(APP / 'app'), str(APP)]

os.environ['LASTBOOK_DATA'] = str(DATA)
os.environ.setdefault('SURVIVAL_MODEL_BASE', 'http://127.0.0.1:9')
os.environ.setdefault('SURVIVAL_DISABLE_INDEX_WATCH', '1')

import bridge as B  # noqa: E402
import llm_local  # noqa: E402
import server  # noqa: E402

results = []


def check(name, ok, detail=''):
    ok = bool(ok)
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f'  {detail}' if detail else ''), flush=True)


class Rec(B.Sink):
    def __init__(self):
        self.status, self.headers, self.parts = None, {}, []
        self.done, self.ok = threading.Event(), None

    def head(self, status, reason, headers):
        self.status, self.headers = status, {k.lower(): v for k, v in headers}

    def data(self, chunk, ack):
        self.parts.append(chunk)
        ack()

    def finish(self, ok):
        self.ok = ok
        self.done.set()


def get(b, target, headers=None, timeout=120):
    r = Rec()
    b.start('GET', b.origin + target, headers or {}, None, r)
    if not r.done.wait(timeout):
        raise TimeoutError(target)
    return r.status, r.headers, b''.join(r.parts)


def main():
    server.init(no_index=True)
    b = B.Bridge(server, 'stream', B.ORIGIN_MAC, tmpdir=str(DATA / 'tmp'))

    cat = server.catalog()
    videos = [r for r in cat['by_id'].values() if r.get('kind') == 'video']
    check('Videos: the library has a video', videos, videos[0]['path'] if videos else 'none')
    s, h, body = get(b, '/api/videos')
    rows = json.loads(body) if s == 200 else []
    check('Videos: /api/videos answers with rows', s == 200 and any(r.get('items') for r in rows), f'{s}, {len(rows)} rows')
    s, h, body = get(b, '/api/videos/all')
    listing = json.loads(body) if s == 200 else {}
    check('Videos: the all row lists videos', s == 200 and listing.get('total', 0) > 0, f"{s}, total {listing.get('total')}")
    if videos:
        path = videos[0]['path']
        size = (server.LIB / path).stat().st_size
        want = (server.LIB / path).read_bytes()[:min(1024 * 1024, size)]
        s, h, body = get(b, '/' + urllib.parse.quote(path, safe='/'), {'Range': f'bytes=0-{len(want) - 1}'})
        check('Videos: a Range answers with the file bytes', s == 206 and body == want, f'{s}, {len(body)} bytes')

    s, h, body = get(b, '/api/map/info')
    info = json.loads(body) if s == 200 else {}
    check('Map: /api/map/info answers', s == 200 and isinstance(info.get('national'), dict), f'{s}')
    check('Map: the national map is complete', (info.get('national') or {}).get('state') == 'complete',
          json.dumps(info.get('national')))

    runner = llm_local.runner_path()
    if runner and Path(runner).is_file():
        check('local AI: the runner is bundled', True, str(runner))
        check('local AI: llm_local finds its runtime', llm_local.Local().status()['runtime'] is True)
        missing = DATA / 'missing-model.gguf'
        try:
            out = subprocess.run([str(runner), '--model', str(missing), '--cpu-only'], cwd=str(Path(runner).parent),
                                 capture_output=True, timeout=180)
            check('local AI: the runner starts and refuses a missing model', out.returncode == 3 and b'"ev":"error"' in out.stdout,
                  f'exit {out.returncode}, {out.stdout[:120]!r}')
        except (OSError, subprocess.SubprocessError) as e:
            check('local AI: the runner starts and refuses a missing model', False, f'{type(e).__name__}: {e}')
    elif a.require_ai:
        check('local AI: the runner is bundled', False, 'missing')
    else:
        print('SKIP  local AI: the runner is not built (use --require-ai for a release check)', flush=True)

    print(f'{sum(results)} of {len(results)} passed', flush=True)
    return 0 if all(results) else 1


if __name__ == '__main__':
    sys.exit(main())
