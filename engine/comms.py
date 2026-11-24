"""Offline lookup of bundled emergency-communications reference data.

Used by the lookup_comms chat tool. Data lives in engine/comms_data/, split by
topic. Every returned entry carries the citation fields Session/source_known
expect for kind 'reference'.
"""
from __future__ import annotations

import re
from engine import morse
from engine.comms_data import TOPICS, all_entries
from engine.comms_data.equipment_rows import ROWS as EQUIPMENT_ROWS

TOPIC_ALIASES = {
    'ham': 'ham', 'amateur': 'ham', 'part 97': 'ham', 'part97': 'ham',
    'channel': 'channels', 'channels': 'channels', 'frequency': 'channels',
    'frequencies': 'channels', 'frs': 'channels', 'gmrs': 'channels',
    'murs': 'channels', 'cb': 'channels', 'marine': 'channels', 'noaa': 'channels',
    'emergency': 'emergency', 'distress': 'emergency', 'rules': 'emergency',
    '97.403': 'emergency', '97.405': 'emergency',
    'satellite': 'satellite', 'sat': 'satellite', 'iss': 'satellite',
    'iridium': 'satellite', 'tle': 'satellite',
    'digital': 'digital', 'aprs': 'digital', 'meshtastic': 'digital',
    'lora': 'digital', 'ft8': 'digital',
    'email': 'email', 'winlink': 'email', 'pactor': 'email', 'vara': 'email',
    'ardop': 'email',
    'signaling': 'signaling', 'signal': 'signaling', 'morse': 'signaling',
    'cw': 'signaling',
    'equipment': 'equipment', 'interop': 'equipment', 'interoperate': 'equipment',
    'surplus': 'equipment', 'prc': 'equipment', 'found radio': 'equipment',
    'manual': 'equipment', 'manuals': 'equipment',
}

_TOKEN = re.compile(r"[a-z0-9]+(?:\.[a-z0-9]+)?", re.I)
_FREQ = re.compile(
    r'(?<![0-9])(\d{2,4}(?:\.\d{1,5})?)\s*(mhz|khz)?(?![0-9])',
    re.I,
)
_CH = re.compile(
    r'\b(?:frs|gmrs|cb|murs|marine|wx|channel|ch)\s*-?\s*(\d{1,2}a?)\b',
    re.I,
)


def _tokens(q: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(q or '')]


def _freqs(q: str) -> list[float]:
    out = []
    for num, unit in _FREQ.findall(q or ''):
        val = float(num)
        unit = (unit or '').lower()
        if unit == 'khz':
            val = val / 1000.0
        # Ignore bare numbers that are clearly channel numbers (1–22, 70, 16, 9, 19).
        if not unit and val <= 80 and '.' not in num:
            continue
        out.append(val)
    return out


def close_freq(a: float, b: float) -> bool:
    """True when two MHz values are the same published channel (handles 146.52 vs 146.520)."""
    return abs(a - b) <= 0.0015


def normalize_topic(topic) -> str | None:
    if not topic:
        return None
    t = str(topic).strip().lower()
    if t in ('', 'any', 'all', '*'):
        return None
    if t in TOPICS:
        return t
    return TOPIC_ALIASES.get(t)


def _channel_hits(query: str, entry: dict) -> int:
    """Score only real channel mentions, never bare digits inside a frequency or a rule number."""
    chans = [str(c).lower() for c in entry.get('channels') or []]
    if not chans:
        return 0
    score = 0
    q = query.lower()
    # A named channel in the query, e.g. "FRS 2", "channel 16", "CB 9", "WX1".
    mentioned = []
    for m in _CH.finditer(query):
        mentioned.append((m.group(0).lower(), m.group(1).lower()))
    # "WX1" style already in the list; also accept exact multi-character labels.
    for c in chans:
        cl = c.lower().strip()
        if len(cl) < 3 or cl.isdigit():
            # "1" or "16" alone is not enough — need a service word or "channel".
            continue
        if re.search(r'(?<![0-9a-z])' + re.escape(cl) + r'(?![0-9])', q):
            score += 8
    for raw, num in mentioned:
        service = re.sub(r'[\s\-]*' + re.escape(num) + r'$', '', raw).strip()
        for c in chans:
            cl = c.lower()
            if cl == num or cl.endswith(' ' + num) or cl == raw.replace('channel', 'ch').strip():
                # Prefer a service match (FRS 2 vs a bare "2" on every table).
                score += 14 if service and service in cl else 8
                break
    return score


def _freq_hits(needles: list[float], entry: dict) -> int:
    have = [float(x) for x in entry.get('frequencies_mhz') or []]
    score = 0
    for n in needles:
        if any(close_freq(n, h) for h in have):
            score += 20
    return score


def score_entry(query: str, entry: dict, topic: str | None) -> int:
    q = (query or '').strip()
    if not q:
        return 1 if (topic is None or entry.get('topic') == topic) else 0
    words = _tokens(q)
    if not words:
        return 0
    title = (entry.get('title') or '').lower()
    section = (entry.get('section') or '').lower()
    keys = [k.lower() for k in entry.get('keywords') or []]
    body = (entry.get('text') or '').lower()
    eid = (entry.get('id') or '').lower()
    score = 0
    if topic and entry.get('topic') == topic:
        score += 2
    # A dotted section number ("97.403") or a precise frequency string in the
    # query should hit the entry that actually cites it, not every table.
    ql = q.lower()
    if ql in section or ql in (entry.get('id') or '').lower():
        score += 16
    elif re.search(r'(?<![0-9])' + re.escape(ql) + r'(?![0-9])', section):
        score += 16
    if re.search(r'(?<![0-9])' + re.escape(ql) + r'(?![0-9])', (entry.get('text') or '').lower()):
        score += 8
    for w in words:
        if w in keys:
            score += 8
        if w in eid.replace('-', ' ').split() or (len(w) >= 4 and w in eid):
            score += 5
        if re.search(r'\b' + re.escape(w) + r'\b', title):
            score += 6
        elif len(w) >= 3 and w in title:
            score += 3
        if w in section:
            score += 4
        if len(w) >= 3 and re.search(r'\b' + re.escape(w) + r'\b', body):
            score += 1
    # Multi-word title phrase
    if len(words) >= 2 and ' '.join(words) in title:
        score += 10
    score += _channel_hits(q, entry)
    score += _freq_hits(_freqs(q), entry)
    return score


def _morse_request(query: str, encode_text) -> str | None:
    if encode_text is not None and str(encode_text).strip():
        return str(encode_text)
    q = (query or '').strip()
    m = re.match(
        r'(?:please\s+)?(?:encode|morse|cw)\s+(?:this\s+|the\s+text\s+|text\s+)?[:\-]?\s*(.+)$',
        q,
        re.I | re.S,
    )
    if m:
        return m.group(1).strip().strip('"').strip("'")
    return None


def morse_entry(text: str, wpm: float = 20) -> dict:
    """A citable encode result, using the ITU Morse entry as the source."""
    result = morse.timings_for(text, wpm=wpm)
    skipped = result['skipped']
    skip_line = (
        f"\nCharacters with no ITU sign, skipped: {' '.join(skipped)}"
        if skipped else ''
    )
    kind = 'distress prosign (no letter spaces)' if result['prosign'] and text.strip().upper() == 'SOS' else (
        'prosign' if result['prosign'] else 'text'
    )
    body = (
        f"Morse encode ({kind}), ITU-R M.1677-1, {result['wpm']:g} WPM (PARIS), "
        f"unit {result['unit_ms']:.1f} ms.\n\n"
        f"Text: {result['text']}\n"
        f"Morse: {result['morse'] or '(nothing to encode)'}"
        f"{skip_line}\n\n"
        "Play the tones on this device’s Morse practice page (offline). "
        "Decode from a microphone, a recording, or a light is not in this build."
    )
    return {
        'id': 'morse-encode-result',
        'ref_id': 'morse-encode-result',
        'topic': 'signaling',
        'title': 'Morse encode result (ITU-R M.1677-1)',
        'publisher': 'ITU',
        'section': 'ITU-R M.1677-1',
        'edition': 'ITU-R M.1677-1, as implemented in engine/morse.py',
        'year': '2009',
        'license': 'International Morse character set (ITU-R M.1677-1)',
        'trust': 'official',
        'keywords': ['morse', 'encode'],
        'href': '#/morse',
        'text': body,
        'excerpt': f"Morse: {result['morse']}"[:600],
        'morse': result,
    }



def score_equipment_row(query, row):
    q = (query or '').strip().lower()
    if not q:
        return 0
    words = _tokens(q)
    blob = ' '.join([
        row.get('make') or '', row.get('model') or '', row.get('category') or '',
        row.get('era_years') or '', row.get('bands') or '', row.get('modes') or '',
        row.get('notes') or '',
    ]).lower()
    name = f"{row.get('make') or ''} {row.get('model') or ''}".lower()
    score = 0
    if q and q in name:
        score += 20
    if q and q in blob:
        score += 8
    for w in words:
        if len(w) < 3:
            continue
        if w in name.split() or w in name:
            score += 8
        if re.search(r'(?<![a-z0-9])' + re.escape(w) + r'(?![a-z0-9])', blob):
            score += 3
    return score


def format_equipment_row(row):
    return (
        f"{row.get('make') or ''} {row.get('model') or ''}\n"
        f"Category: {row.get('category') or '—'}  Era: {row.get('era_years') or '—'}\n"
        f"Bands: {row.get('bands') or '—'}\n"
        f"Modes: {row.get('modes') or '—'}\n"
        f"Power: {row.get('power') or '—'}\n"
        f"{row.get('notes') or ''}"
    ).strip()


def looks_like_equipment_query(query):
    """True when the person is asking about a model, a make, or found/surplus gear — not a bare frequency or rule."""
    q = (query or '').strip()
    if not q:
        return False
    if re.fullmatch(r'\d{2,4}(?:\.\d{1,5})?\s*(?:mhz|khz)?', q, re.I):
        return False
    if re.search(
        r'(?i)(prc[- ]?\d|an[/ ]?prc|uv-\d|ic-\d|ft-\d|ts-\d|ee-\d|ta-\d|r-390|'
        r'baofeng|yaesu|kenwood|icom|inreach|iridium|garmin|harris|thales|'
        r'clansman|heathkit|collins|winlink express|surplus|found radio|'
        r'manpack|field telephone|tm[ -]?11)',
        q,
    ):
        return True
    if re.search(r'(?i)\b[a-z]{1,4}-\d{1,4}[a-z0-9]{0,4}\b', q):
        return True
    return False


def equipment_hit(query, limit=4):
    """Bundle the best inventory rows into one citable reference entry."""
    scored = []
    for i, row in enumerate(EQUIPMENT_ROWS):
        s = score_equipment_row(query, row)
        if s > 0:
            scored.append((s, i, row))
    scored.sort(key=lambda x: (-x[0], x[1]))
    # Require a real model/make-ish hit so generic words like "power" do not dump the catalog.
    strong = [x for x in scored if x[0] >= 11]
    if not strong:
        return None
    top = strong[: max(1, min(4, int(limit or 4)))]
    body = (
        "Sourced inventory rows from the November 2026 Lastbook comms equipment survey "
        f"(108 models and families, 1960s–present). Showing {len(top)} match(es) for this query. "
        "Commercial manufacturer manuals are not bundled; see the public-domain manuals entry for U.S. government TMs.\n\n"
        + "\n\n".join(format_equipment_row(r) for _s, _i, r in top)
    )
    first = top[0][2]
    title = f"Equipment inventory: {first.get('make') or ''} {first.get('model') or ''}".strip()
    if len(top) > 1:
        title += f" and {len(top) - 1} other match(es)"
    return {
        'id': 'equipment-inventory-match',
        'ref_id': 'equipment-inventory-match:' + (first.get('model') or first.get('make') or 'hit'),
        'topic': 'equipment',
        'title': title,
        'publisher': 'Lastbook comms equipment survey, November 2026',
        'section': f"Inventory row, category {first.get('category') or '—'}",
        'edition': '108 sourced rows compiled November 2026 from manufacturer specifications, FCC rules, and U.S. military TMs',
        'year': '2026',
        'license': 'Original survey notes. Commercial manuals are cited in the survey, not bundled here.',
        'trust': 'survey',
        'keywords': ['equipment', 'inventory'],
        'text': body,
        'excerpt': re.sub(r'\s+', ' ', body)[:600],
        'score': top[0][0],
    }


def lookup(query: str, topic: str | None = 'any', encode: str | None = None, limit: int = 8) -> dict:
    """Search bundled reference data. Returns hits, optional Morse encode, and a miss note."""
    topic_n = normalize_topic(topic)
    q = (query or '').strip()
    limit = max(1, min(12, int(limit or 8)))
    entries = all_entries()
    if topic_n:
        entries = [e for e in entries if e.get('topic') == topic_n]
    to_encode = _morse_request(q, encode)
    scored = []
    for e in entries:
        # The encode result is added separately; don't let "morse SOS" drown in the table only.
        s = score_entry(q, e, topic_n)
        if s > 0:
            scored.append((s, e['id'], e))
    scored.sort(key=lambda x: (-x[0], x[1]))
    # With an empty query and a topic, list that topic's entries (a table of contents).
    if not q and topic_n:
        scored = [(1, e['id'], e) for e in entries]
    hits = []
    for s, _id, e in scored[:limit]:
        item = dict(e)
        item['ref_id'] = e['id']
        item['score'] = s
        item['excerpt'] = re.sub(r'\s+', ' ', e.get('text') or '')[:600]
        hits.append(item)
    # Inventory rows (108 sourced models). Shown when the query looks like a make/model,
    # or when the topic is equipment. Not used to flood a generic frequency lookup.
    want_equip = (topic_n == 'equipment' or (topic_n is None and looks_like_equipment_query(q))) and q
    if want_equip:
        eh = equipment_hit(q)
        if eh:
            hits = [h for h in hits if h.get('id') != 'equipment-inventory-match']
            if topic_n == 'equipment' or looks_like_equipment_query(q):
                hits = [eh] + hits
            else:
                hits.insert(min(1, len(hits)), eh)
            hits = hits[:limit]
    result = {
        'query': q,
        'topic': topic_n or 'any',
        'count': len(hits),
        'hits': hits,
        'encode': None,
    }
    if to_encode:
        result['encode'] = morse_entry(to_encode)
    if not hits and result['encode'] is None:
        result['miss'] = (
            'No bundled comms reference matched. Try a frequency (for example 146.520), '
            'a service (FRS, GMRS, marine, NOAA, Winlink), a rule (97.403), or a topic '
            '(ham, channels, emergency, satellite, digital, email, signaling, equipment).'
        )
    return result


def reference_source(entry: dict) -> dict:
    """Session.add payload for a hit or a Morse encode result."""
    return {
        'kind': 'reference',
        'ref_id': entry.get('ref_id') or entry.get('id'),
        'title': entry['title'],
        'publisher': entry.get('publisher') or '',
        'section': entry.get('section') or '',
        'edition': entry.get('edition') or '',
        'year': entry.get('year') or '',
        'license': entry.get('license') or '',
        'trust': entry.get('trust') or 'official',
        'href': entry.get('href') or '',
        'excerpt': entry.get('excerpt') or re.sub(r'\s+', ' ', entry.get('text') or '')[:600],
        'page': None,
        't': None,
        'doc_id': None,
    }
