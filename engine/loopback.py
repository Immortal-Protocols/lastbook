"""Where the assistant may send a conversation: a model server on this computer, over plain http, and nowhere else.

No network module here, so first-run setup can check the address a person types with the same rule the assistant uses."""
import re

LOOPBACK = re.compile(r'http://(127\.0\.0\.1|\[::1\]):\d+(/[^\s]*)?')


def loopback_base(value):
    """The model server's address, or ValueError for anything off this computer. 'localhost' becomes 127.0.0.1: a hosts file could point the name anywhere."""
    base = re.sub(r'^http://localhost:', 'http://127.0.0.1:', value.rstrip('/'))
    if not re.fullmatch(r'http://(127\.0\.0\.1|\[::1\]):\d+', base):
        raise ValueError('not a loopback http address')
    return base
