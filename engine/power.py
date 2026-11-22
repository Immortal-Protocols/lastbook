"""Save power: one switch for a computer running on its battery, in an outage. Nothing here reads the battery or goes online.

While it is on, the two things in Lastbook that keep working in the background stop doing so:
  - the local AI stops now (unless it is writing an answer) and from then on stops SAVE_IDLE_S seconds after each answer,
    instead of llm_local.IDLE_STOP: it still answers, it just loads again for the next question;
  - meaning-based search stops embedding new pages (retrieval.Index.paused); the search itself keeps working.
The setting is kept in the data folder (derived/power.json), so it is still on after a restart.

Routes, this computer only (like /api/setup/ and /api/update/): GET /api/power; POST /api/power {save: true|false}.
"""
import json
import threading

from engine import paths

SAVE_IDLE_S = 60
FILE = paths.DATA / 'derived' / 'power.json'
_lock = threading.Lock()
_parts = {'local': None, 'index': None}


def saving():
    try:
        return json.loads(FILE.read_text(encoding='utf-8')).get('save') is True
    except (OSError, ValueError, AttributeError):
        return False


def attach(local=None, index=None):
    """server.init: the local AI (llm_local.Local, or None) and the search index (retrieval.Index); the saved setting applies at once."""
    _parts.update(local=local, index=index)
    apply(saving())


def apply(on):
    local, index = _parts['local'], _parts['index']
    if local is not None and hasattr(local, 'save_power'):
        local.save_power(SAVE_IDLE_S if on else None)
    if index is not None:
        index.paused = on


def set_saving(on):
    with _lock:
        FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = FILE.with_suffix('.tmp')
        tmp.write_text(json.dumps({'save': bool(on)}), encoding='utf-8')
        tmp.replace(FILE)
        apply(bool(on))
    return state()


def state():
    return {'save': saving(), 'ai_stops_after_s': SAVE_IDLE_S if saving() else None}


def handle(h, method):
    """Answers /api/power on a BaseHTTPRequestHandler h. This computer only: a phone the library is shared with gets 403."""
    from engine.setup.api import _send_json
    if h.client_address[0] not in ('127.0.0.1', '::1', '::ffff:127.0.0.1'):
        return _send_json(h, {'error': 'Save power is only open on this computer.'}, 403)
    if method in ('GET', 'HEAD'):
        return _send_json(h, state())
    try:
        n = int(h.headers.get('Content-Length') or 0)
        body = json.loads(h.rfile.read(n) if 0 < n <= 4096 else b'{}')
    except (ValueError, TypeError):
        body = None
    if not isinstance(body, dict) or not isinstance(body.get('save'), bool):
        return _send_json(h, {'error': 'send {"save": true} or {"save": false}'}, 400)
    return _send_json(h, set_saving(body['save']))
