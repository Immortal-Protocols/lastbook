"""Opt-in sharing of the open library on the local network, from the desktop app.

Off unless the person turns it on (Library and local AI). Reuses server.py's LAN key,
Handler and bind logic. A port is opened only while sharing is on, and it is closed
when sharing is stopped or the app quits. Other devices get a read-only view; setup,
updates and similar stay on this computer.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

# Filled by configure() from the app's settings folder. Not the library folder:
# that can sit on a shared disk, and this preference is this computer's.
_SETTINGS_DIR = None
_LOCK = threading.Lock()
_ERROR = None
FLAG = 'share.json'   # {on: bool} in the settings folder; the access key stays in derived/lan-key


def configure(settings_dir):
    """Remember where to keep the on/off flag. Called once when the desktop app starts."""
    global _SETTINGS_DIR
    _SETTINGS_DIR = Path(settings_dir) if settings_dir else None


def wanted():
    """True only if the person left sharing on last time. Missing or unreadable means off."""
    path = _flag_path()
    if not path:
        return False
    try:
        return json.loads(path.read_text(encoding='utf-8')).get('on') is True
    except (OSError, ValueError, AttributeError, TypeError):
        return False


def _flag_path():
    return (_SETTINGS_DIR / FLAG) if _SETTINGS_DIR else None


def _save_wanted(on):
    path = _flag_path()
    if not path:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'on': bool(on)}), encoding='utf-8')
    except OSError as e:
        print('share: could not save the sharing preference:', e, flush=True)


def start():
    """Bind the existing LAN server on this computer's network addresses. Offers several ports if 8890 is taken."""
    import server
    global _ERROR
    with _LOCK:
        _ERROR = None
        try:
            server.start_lan()
        except OSError as e:
            _ERROR = 'Lastbook could not listen on this network. Another program may already be using the port.'
            print('share: could not start:', type(e).__name__, e, flush=True)
            return False
        _save_wanted(True)
        return True


def stop(forget=True, wait=True):
    """Close the listening port if it is open. Safe to call when sharing is already off.
    forget=True (the Stop button): also remember that sharing should stay off next time.
    forget=False (the app is quitting): close the port but keep the saved preference.
    wait=False when Stop is pressed in the window, so the reply can be sent before the port closes."""
    import server
    global _ERROR
    with _LOCK:
        server.stop_lan(wait=wait)
        _ERROR = None
        if forget:
            _save_wanted(False)


def restore():
    """Start sharing at launch only if the person left it on. A failure leaves the app running, with an error to show."""
    if wanted():
        start()


def status():
    """What the Library and local AI page shows. Never includes the raw key on its own; it is only inside `link`."""
    import server
    on = bool(server.SERVER)
    port = int(server.SERVER.server_address[1]) if on else None
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
        'port': port,
        'ip': ip,
        'link': link,
        'error': _ERROR or (hint if on and not link else None),
    }


def handle(h, method):
    """GET/POST /api/share: this computer only (the app window)."""
    import server
    if not server.is_loopback(h.client_address[0]):
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
        if body.get('on') is True:
            start()
        elif body.get('on') is False:
            # Close the port after this reply is sent: shutdown() from inside a request would wait forever.
            stop(forget=True, wait=False)
            return h.send_json({
                'on': False, 'wanted': False, 'port': None, 'ip': None, 'link': None, 'error': None,
            })
        else:
            return h.send_json({'error': 'Send on: true or on: false.'}, 400)
    return h.send_json(status())
