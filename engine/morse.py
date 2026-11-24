"""ITU International Morse: encode text, produce tone timings, and leave a decode hook.

The character set and spacing follow ITU-R Recommendation M.1677-1 (International Morse
code). Timing uses the standard word PARIS (50 units): a unit is 1.2 / WPM seconds.
The distress signal SOS is a single prosign with no letter spaces (...---...).

decode() is the stable interface for a later PR (mic, audio file, or light). This
build does not implement it.
"""
from __future__ import annotations

# Letter, figure and punctuation signs from ITU-R M.1677-1. Values are strings of
# '.' (dit) and '-' (dah) only.
LETTERS = {
    'A': '.-', 'B': '-...', 'C': '-.-.', 'D': '-..', 'E': '.', 'F': '..-.',
    'G': '--.', 'H': '....', 'I': '..', 'J': '.---', 'K': '-.-', 'L': '.-..',
    'M': '--', 'N': '-.', 'O': '---', 'P': '.--.', 'Q': '--.-', 'R': '.-.',
    'S': '...', 'T': '-', 'U': '..-', 'V': '...-', 'W': '.--', 'X': '-..-',
    'Y': '-.--', 'Z': '--..',
    '0': '-----', '1': '.----', '2': '..---', '3': '...--', '4': '....-',
    '5': '.....', '6': '-....', '7': '--...', '8': '---..', '9': '----.',
    '.': '.-.-.-', ',': '--..--', '?': '..--..', "'": '.----.',
    '/': '-..-.', '(': '-.--.', ')': '-.--.-', ':': '---...',
    ';': '-.-.-.', '=': '-...-', '+': '.-.-.', '-': '-....-',
    '"': '.-..-.', '@': '.--.-.',
}

# Official sign for '&' in M.1677-1 is the same as the procedure sign AS (wait).
LETTERS['&'] = '.-...'

# Common procedure signs, sent as one character (no inter-letter space).
PROSIGNS = {
    'SOS': '...---...',   # distress, ITU Radio Regulations / M.1677 practice
    'AR': '.-.-.',        # end of message (same as '+')
    'SK': '...-.-',       # end of work
    'BT': '-...-',        # break / separator (same as '=')
    'KN': '-.--.',        # invitation to a particular station (same as '(')
    'AS': '.-...',        # wait
    'HH': '........',     # error (eight dits)
}

# Characters we accept but map first (smart punctuation, typography).
_NORMALIZE = {
    '\u2018': "'", '\u2019': "'", '\u201c': '"', '\u201d': '"',
    '\u2010': '-', '\u2011': '-', '\u2012': '-', '\u2013': '-', '\u2014': '-',
    '\u2212': '-', '\uff0f': '/',
}


def unit_seconds(wpm: float = 20) -> float:
    """Duration of one Morse unit at the given words-per-minute (PARIS standard)."""
    wpm = float(wpm)
    if wpm <= 0:
        raise ValueError('wpm must be positive')
    return 1.2 / wpm


def normalize_char(ch: str) -> str:
    ch = _NORMALIZE.get(ch, ch)
    return ch.upper()


def _tokens(text: str) -> list[str]:
    """Split text into prosigns, words and characters. Unknown characters are kept as-is."""
    if text is None:
        return []
    raw = str(text)
    out: list[str] = []
    i = 0
    upper = raw.upper()
    # Longest prosign first, only at a letter boundary (not inside a word).
    names = sorted(PROSIGNS, key=len, reverse=True)
    while i < len(raw):
        ch = raw[i]
        if ch.isspace():
            if not out or out[-1] != ' ':
                out.append(' ')
            i += 1
            continue
        matched = None
        for name in names:
            if upper.startswith(name, i):
                end = i + len(name)
                # Treat as a prosign when it is a whole token (edges are start, end, or space).
                before_ok = i == 0 or raw[i - 1].isspace()
                after_ok = end == len(raw) or raw[end].isspace()
                if before_ok and after_ok:
                    matched = name
                    break
        if matched:
            out.append(matched)
            i += len(matched)
            continue
        out.append(raw[i])
        i += 1
    return out


def encode(text: str) -> dict:
    """Encode text to Morse.

    Returns a dict:
      morse:   printable form, letters separated by a space, words by ' / '
      prosign: True when the whole input was a single prosign (including SOS)
      skipped: characters with no ITU sign, in order, unique-preserving
      text:    the input as encoded (original string)
    """
    skipped = []
    words: list[list[str]] = []
    current: list[str] = []

    def flush():
        nonlocal current
        if current:
            words.append(current)
            current = []

    for tok in _tokens(text or ''):
        if tok == ' ':
            flush()
            continue
        if tok in PROSIGNS:
            current.append(PROSIGNS[tok])
            continue
        ch = normalize_char(tok)
        sign = LETTERS.get(ch)
        if sign is None:
            skipped.append(tok)
            continue
        current.append(sign)
    flush()
    morse = ' / '.join(' '.join(w) for w in words if w)
    whole = (text or '').strip().upper()
    return {
        'text': text or '',
        'morse': morse,
        'prosign': whole in PROSIGNS and not skipped and len(words) == 1 and len(words[0]) == 1,
        'skipped': skipped,
    }


def timings(text: str, wpm: float = 20, freq_hz: float = 600) -> list[dict]:
    """Return a playable sequence of tones and gaps for Web Audio or tests.

    Each item is {'kind': 'tone'|'gap', 'ms': int, 'units': int} and, for tones,
    {'mark': '.'|'-'}. freq_hz is carried on the result wrapper in timings_for().
    """
    unit_ms = unit_seconds(wpm) * 1000.0
    marks = encode(text)['morse']
    seq: list[dict] = []

    def add(kind: str, units: int, mark: str | None = None):
        if units <= 0:
            return
        item = {'kind': kind, 'units': units, 'ms': int(round(unit_ms * units))}
        if mark is not None:
            item['mark'] = mark
        # Merge consecutive gaps (should not usually happen).
        if seq and kind == 'gap' and seq[-1]['kind'] == 'gap':
            seq[-1]['units'] += units
            seq[-1]['ms'] = int(round(unit_ms * seq[-1]['units']))
            return
        seq.append(item)

    if not marks:
        return seq
    parts = marks.split(' / ')
    for wi, word in enumerate(parts):
        letters = word.split(' ')
        for li, letter in enumerate(letters):
            for mi, mark in enumerate(letter):
                if mark == '.':
                    add('tone', 1, '.')
                elif mark == '-':
                    add('tone', 3, '-')
                else:
                    continue
                if mi < len(letter) - 1:
                    add('gap', 1)
            if li < len(letters) - 1:
                add('gap', 3)
        if wi < len(parts) - 1:
            add('gap', 7)
    return seq


def timings_for(text: str, wpm: float = 20, freq_hz: float = 600) -> dict:
    """Encode plus timings, with the playback parameters attached."""
    wpm = float(wpm)
    if wpm < 5 or wpm > 40:
        # Practice range; still encode outside it, but clamp playback speed.
        play_wpm = min(40, max(5, wpm))
    else:
        play_wpm = wpm
    freq = float(freq_hz)
    if freq < 300 or freq > 1200:
        freq = 600.0
    coded = encode(text)
    return {
        **coded,
        'wpm': play_wpm,
        'freq_hz': freq,
        'unit_ms': unit_seconds(play_wpm) * 1000.0,
        'timings': timings(text, wpm=play_wpm),
    }


def decode(samples=None, sample_rate=None, source=None, **kwargs):
    """Reserved hook for Morse decode from mic, audio file, or light.

    Not implemented in this build. A later PR should keep this name and
    these argument names (samples, sample_rate, source).
    """
    raise NotImplementedError('Morse decode from audio or light is not in this build')


def letters_table() -> dict:
    """ITU letters and figures only, for the practice page and tests."""
    keys = [c for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789']
    return {c: LETTERS[c] for c in keys}
