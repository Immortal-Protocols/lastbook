"""Bundled, sourced emergency-communications reference entries, split by topic."""
from __future__ import annotations

from . import channels, digital, email, emergency, equipment, ham, satellite, signaling

TOPICS = ('ham', 'channels', 'emergency', 'satellite', 'digital', 'email', 'signaling', 'equipment')

MODULES = {
    'ham': ham,
    'channels': channels,
    'emergency': emergency,
    'satellite': satellite,
    'digital': digital,
    'email': email,
    'signaling': signaling,
    'equipment': equipment,
}


def all_entries():
    out = []
    for name in TOPICS:
        for e in MODULES[name].ENTRIES:
            item = dict(e)
            item.setdefault('topic', name)
            out.append(item)
    return out
