"""Read-only Han substrings and Arabic words against the existing pages schema."""
import functools
import re
import unicodedata

# unicode61 treats a run of Han characters as one token. Short Chinese terms
# therefore need literal substring matching, without changing the saved text or
# requiring a new tokenizer/index. Arabic words ignore only common vowel marks;
# other terms retain the existing FTS path. Hamza/maddah and letters stay distinct.
HAN = re.compile(r'[\u3400-\u9fff\uf900-\ufaff\U00020000-\U000323af]')
VOWELS = re.compile(r'[\u064b-\u0652\u0670]')
OPTIONAL_VOWELS = r'[\u064b-\u0652\u0670]*'


def arabic_word(term):
    return any(unicodedata.category(c).startswith('L') and
               unicodedata.name(c, '').startswith('ARABIC LETTER ') for c in term)


def query_terms(text, apostrophes=True):
    """Keep Arabic marks inside words; retain legacy token splitting elsewhere.

    Combining hamza/maddah stay literal. libq historically splits apostrophes.
    """
    letters = r"\w'\-" if apostrophes else r'\w\-'
    out = []
    for word in re.findall('[' + letters + r'\u064b-\u065f\u0670]+', text):
        if arabic_word(word):
            out.append(word)
        else:
            out.extend(re.findall('[' + letters + ']+', word))
    return out


def needs_text_search(groups):
    return has_han(groups) or any(arabic_word(t) for g in groups for t in g)


@functools.lru_cache(maxsize=256)
def arabic_pattern(term):
    # Escaped literals separated only by optional vowel marks. Those marks do
    # not consume letters, so this creates no nested wildcard backtracking.
    term = VOWELS.sub('', term)
    return re.compile(''.join(re.escape(c) + OPTIONAL_VOWELS for c in term), re.I) if term else None


def word_character(c):
    return c == '_' or unicodedata.category(c)[0] in 'LNM' or unicodedata.category(c) == 'Co'


def arabic_matches(text, term, start=0, end=None):
    """Original source spans, including marks; never part of another word."""
    pattern = arabic_pattern(term)
    if pattern is None:
        return
    for match in pattern.finditer(text, start, len(text) if end is None else end):
        a, b = match.span()
        if (a == 0 or not word_character(text[a - 1])) and (b == len(text) or not word_character(text[b])):
            yield a, b


def excerpt_for(body, literal, markers):
    body = body or ''
    patterns = [(t, arabic_word(t), re.compile(re.escape(t), re.I)) for t in literal]

    def spans(start=0, end=None):
        for term, arabic, pattern in patterns:
            if arabic:
                yield from arabic_matches(body, term, start, end)
            else:
                yield from (m.span() for m in pattern.finditer(body, start, len(body) if end is None else end))

    first = []
    for term, arabic, pattern in patterns:
        match = next(arabic_matches(body, term), None) if arabic else pattern.search(body)
        if match is not None:
            first.append(match if arabic else match.span())
    start = max(0, min(a for a, _ in first) - 60) if first else 0
    end = min(len(body), max(start + 220, min(first)[1] if first else 0))
    ranges = []
    if any(markers):
        for a, b in sorted(spans(start, end)):
            if ranges and a <= ranges[-1][1]:
                ranges[-1] = (ranges[-1][0], max(b, ranges[-1][1]))
            else:
                ranges.append((a, b))
    parts = []; at = start
    for a, b in ranges:
        parts.extend((body[at:a], markers[0], body[a:b], markers[1])); at = b
    parts.append(body[at:end])
    return ('… ' if start else '') + ''.join(parts) + (' …' if end < len(body) else '')

def has_han(groups):
    return any(HAN.search(term) for group in groups for term in group)

def text_search_rows(con, groups, ids=None, limit=600, any_group=False, markers=('\x01','\x02')):
    """Read-only Han substrings, whole Arabic words and FTS for other terms.

    Return (doc_id,page,excerpt,negative matched-group count). Filter ids before
    LIMIT, including an empty allowed list. All strings remain bound parameters.
    """
    conditions=[];params=[];literal=[]
    if any(arabic_word(t) for g in groups for t in g):
        con.create_function('lastbook_arabic_word', 2,
                            lambda text, term: int(next(arabic_matches(text or '', term), None) is not None))
    for group in groups:
        alternatives=[]
        for term in group:
            if arabic_word(term):
                alternatives.append('(lastbook_arabic_word(title,?) OR lastbook_arabic_word(body,?))')
                params.extend([term,term]);literal.append(term)
            elif HAN.search(term):
                alternatives.append('(instr(lower(title),?)>0 OR instr(lower(body),?)>0)')
                params.extend([term.lower(),term.lower()]);literal.append(term)
            else:
                alternatives.append('rowid IN (SELECT rowid FROM pages WHERE pages MATCH ?)')
                params.append('"'+term.replace('"','""')+'"')
        if alternatives:conditions.append('('+' OR '.join(alternatives)+')')
    if not conditions:return []
    score='-('+'+'.join('CASE WHEN '+c+' THEN 1 ELSE 0 END' for c in conditions)+')'
    sql='SELECT doc_id,page,body,'+score+' AS score FROM pages WHERE ('+(' OR ' if any_group else ' AND ').join(conditions)+')'
    bindings=params+params
    if ids is not None:
        sql += ' AND doc_id IN (SELECT value FROM json_each(?))'
        bindings.append(ids)
    sql+=' ORDER BY score, rowid LIMIT ?';bindings.append(limit)
    rows=con.execute(sql,bindings).fetchall()
    return [(doc,page,excerpt_for(body,literal,markers),rank) for doc,page,body,rank in rows]


# Keep the earlier curator/test entry point while sharing mixed-script matching.
han_search_rows = text_search_rows

