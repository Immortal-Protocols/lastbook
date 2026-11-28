"""Opt-in sharing of the open library on the local network, from the desktop app.

Off unless the person turns it on (Library and local AI). The share listener is a
dedicated handler with a read-only allowlist; the in-memory bridge remains the path
to settings and private state. A port is opened only while sharing is on, and it is
closed — including in-progress streams — when sharing is stopped or the app quits.

Library browsing is the default share scope. Chat with this computer's local AI is a
separate option, off unless the person turns it on.
"""
from __future__ import annotations

import atexit
import json
import os
import signal
import threading
from pathlib import Path

_SETTINGS_DIR = None
_LOCK = threading.Lock()
_ERROR = None
_HOOKS = False
FLAG = 'share.json'   # {on: bool, ai: bool} in the settings folder; the access key stays in derived/lan-key


def configure(settings_dir):
    """Remember where to keep the on/off flags. Called once when the desktop app starts."""
    global _SETTINGS_DIR
    _SETTINGS_DIR = Path(settings_dir) if settings_dir else None


def _flag_path():
    return (_SETTINGS_DIR / FLAG) if _SETTINGS_DIR else None


def _load_flag():
    path = _flag_path()
    if not path:
        return {'on': False, 'ai': False}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(data, dict):
            return {'on': False, 'ai': False}
        return {'on': data.get('on') is True, 'ai': data.get('ai') is True}
    except (OSError, ValueError, AttributeError, TypeError):
        return {'on': False, 'ai': False}


def _save_flag(**updates):
    path = _flag_path()
    if not path:
        return
    data = _load_flag()
    data.update({k: bool(v) for k, v in updates.items()})
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding='utf-8')
    except OSError as e:
        print('share: could not save the sharing preference:', e, flush=True)


def wanted():
    """True only if the person left library sharing on last time. Missing or unreadable means off."""
    return _load_flag()['on']


def wanted_ai():
    """True only if the person also left Chat with this computer's local AI on. Off by default."""
    return _load_flag()['ai']


def start():
    """Bind the share listener on this computer's network addresses. Offers several ports if 8890 is taken."""
    import server
    global _ERROR
    with _LOCK:
        _ERROR = None
        try:
            server.start_lan()
        except server.KeyNotPrivate as e:
            _ERROR = str(e)   # no listener was started and no preference is saved; the words are for the person
            print('share: not started: the access key file cannot be kept private', flush=True)
            return False
        except OSError as e:
            _ERROR = 'Lastbook could not listen on this network. Another program may already be using the port.'
            print('share: could not start:', type(e).__name__, e, flush=True)
            return False
        _save_flag(on=True)
        return True


def stop(forget=True, wait=True):
    """Close the listening port and every in-progress stream. Safe to call when sharing is already off.
    forget=True (the Stop button): also remember that sharing should stay off next time.
    forget=False (the app is quitting): close the port but keep the saved preference."""
    import server
    global _ERROR
    with _LOCK:
        server.stop_lan(wait=wait)
        _ERROR = None
        if forget:
            _save_flag(on=False)


def restore():
    """Start sharing at launch only if the person left it on. A failure leaves the app running, with an error to show."""
    if wanted():
        start()


def set_ai(on):
    """Turn Chat-with-host-AI on or off. Does not start or stop the listener."""
    _save_flag(ai=bool(on))


def status():
    """What the Library and local AI page and the sharing indicator show.
    Never includes the raw key on its own; it is only inside `link`."""
    import server
    on = bool(server.SHARE_SERVER)
    port = int(server.SHARE_SERVER.server_address[1]) if on else None
    ip = server.lan_address() if on else None
    key = server.LAN_KEY if on else None
    link = None
    if on and ip and key and port:
        link = f'http://{ip}:{port}/?key={key}'
    elif on and key and port:
        link = None
        hint = "Lastbook is sharing, but it could not find this computer's address on the network."
    else:
        hint = None
    return {
        'on': on,
        'wanted': wanted(),
        'ai': wanted_ai(),
        'port': port,
        'ip': ip,
        'link': link,
        'error': _ERROR or (hint if on and not link else None),
    }


def handle(h, method):
    """GET/POST /api/share: the in-memory desktop bridge (and loopback server.py) only."""
    import server
    if getattr(h, 'SHARE_LISTENER', False) or not server.is_loopback(h.client_address[0]):
        return h.send_json({'error': 'Sharing is only turned on or off on this computer.'}, 403)
    if method == 'POST':
        try:
            n = int(h.headers.get('Content-Length') or 0)
            if n < 0 or n > 2000:
                return h.send_json({'error': 'request too large'}, 413)
            body = json.loads(h.rfile.read(n) or b'{}') if n else {}
            if not isinstance(body, dict):
                raise ValueError
        except ValueError:
            return h.send_json({'error': 'bad request'}, 400)
        if 'ai' in body:
            set_ai(body.get('ai') is True)
        if body.get('on') is True:
            start()
        elif body.get('on') is False:
            # Stop is called from the bridge, not from the share listener, so we can wait for the port.
            stop(forget=True, wait=True)
        elif 'ai' not in body:
            return h.send_json({'error': 'Send on: true or on: false, or ai: true or false.'}, 400)
    return h.send_json(status())


def install_shutdown_hooks():
    """Close the share listener on process exit and on SIGINT/SIGTERM. Safe to call more than once.
    Native shells that leave with os._exit must also call stop() themselves, because that skips atexit."""
    global _HOOKS
    if _HOOKS:
        return
    _HOOKS = True
    atexit.register(lambda: stop(forget=False, wait=True))
    if os.name == 'nt':
        return

    def _on_signal(signum, frame, previous=None):
        try:
            stop(forget=False, wait=True)
        except Exception:
            pass
        if callable(previous) and previous not in (signal.SIG_DFL, signal.SIG_IGN):
            previous(signum, frame)
        elif previous == signal.SIG_DFL:
            signal.signal(signum, signal.SIG_DFL)
            os.kill(os.getpid(), signum)

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            prev = signal.getsignal(sig)
            signal.signal(sig, lambda s, f, p=prev: _on_signal(s, f, p))
        except Exception:
            pass
