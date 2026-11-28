"""The guides' `urgent` phrases, read from Python: one list of phrases for the guide search and for the urgency check.

A guide choice that is life-threatening lists phrases in its `urgent` field (content/topics/*.json, content/SCHEMA.md:
"not breathing", "heavy bleeding"). The guide search (web/words.js, rankTopics) uses them to put that choice first. The
chat's urgency check (engine/confidence.urgent, assistant.is_danger) reads the same fields here, so a phrase is written in
one place and both sides agree on it.

Matching is the guide search's own rule, ported: both texts are lower-cased, decomposed, stripped of accent marks on Latin
letters and split wherever there is no letter, mark or digit ("isn't" is "isn" and "t"); a phrase is named when its words
are in the text, whole and in order. Stop words count (it is every word of the search). app/tests/test_urgent_phrases.py
runs both implementations on every phrase and checks that they agree.

Phrases cannot say everything the urgency check needs (words with endings, words with other words in between, typos,
idioms): engine/confidence.py keeps those, as a short residual list, beside this one.
"""
import json
import unicodedata

import engine.paths as lastbook_paths

_cache = {}


def fold(text):
    """The key two texts are compared by (web/words.js fold): lower case, decomposed, accent marks on Latin letters
    removed, composed again; a final sigma is a sigma."""
    s = unicodedata.normalize('NFKD', str(text).lower())
    out, latin = [], False
    for ch in s:
        if unicodedata.category(ch).startswith('M'):
            if latin:
                continue            # a mark straight after a Latin letter (or after one of its marks) goes
        else:
            latin = unicodedata.category(ch).startswith('L') and unicodedata.name(ch, '').startswith('LATIN')
        out.append(ch)
    return unicodedata.normalize('NFC', ''.join(out)).replace('ς', 'σ')


def split_words(text):
    """The words of a text (web/words.js splitWords, without its word segmenter, which only matters for scripts written
    without spaces): split wherever there is no letter, mark or digit."""
    words, cur = [], []
    for ch in str(text):
        if unicodedata.category(ch)[0] in 'LMN':
            cur.append(ch)
        elif cur:
            words.append(''.join(cur))
            cur = []
    if cur:
        words.append(''.join(cur))
    return [w for w in (fold(w) for w in words) if w]


def names(words, phrase):
    """Does the phrase's words appear in order, as whole words, among the words?"""
    n = len(phrase)
    return any(words[i:i + n] == phrase for i in range(len(words) - n + 1))


def topics_folder():
    return lastbook_paths.APP / 'content' / 'topics'


def load(folder=None):
    """[(topic id, choice id, [[word, ...], ...])] for every guide choice with `urgent` phrases. Read once; reload(folder)
    for another folder (tests). Choices that only point somewhere else (goto) are left out, as the guide search leaves them out."""
    folder = folder or topics_folder()
    if folder not in _cache:
        out = []
        for f in sorted(folder.glob('*.json')) if folder.is_dir() else []:
            try:
                t = json.loads(f.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                continue
            for c in (t.get('choices') or []) if isinstance(t, dict) else []:
                if not isinstance(c, dict) or c.get('goto') or not isinstance(c.get('urgent'), list):
                    continue
                phrases = [p for p in (split_words(x) for x in c['urgent'] if isinstance(x, str)) if p]
                if phrases:
                    out.append((t.get('id') or f.stem, c.get('id'), phrases))
        _cache[folder] = out
    return _cache[folder]


def reload(folder=None):
    _cache.pop(folder or topics_folder(), None)
    return load(folder)


def named(*texts, folder=None):
    """The guide choices ('topic/choice') whose `urgent` phrase any of the texts names, sorted."""
    found = set()
    for text in texts:
        words = split_words(text or '')
        if not words:
            continue
        for topic, choice, phrases in load(folder):
            if any(names(words, p) for p in phrases):
                found.add(f'{topic}/{choice}')
    return sorted(found)


def hit(*texts, folder=None):
    """True when any of the texts names an `urgent` phrase of a guide choice."""
    return bool(named(*texts, folder=folder))
