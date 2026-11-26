"""Read-only Han substring search against the existing pages FTS schema."""
import re

# unicode61 treats a run of Han characters as one token. Short Chinese terms
# therefore need literal substring matching, without changing the saved text or
# requiring a new tokenizer/index. Other scripts retain the existing FTS path.
HAN = re.compile(r'[\u3400-\u9fff\uf900-\ufaff\U00020000-\U000323af]')

def has_han(groups):
    return any(HAN.search(term) for group in groups for term in group)

def han_search_rows(con, groups, ids=None, limit=600, any_group=False, markers=('\x01','\x02')):
    """Read-only existing-schema search: literal Han substrings, FTS for other words.

    Return (doc_id,page,excerpt,negative matched-group count). Filter ids before
    LIMIT, including an empty allowed list. All strings remain bound parameters.
    """
    conditions=[];params=[];han=[]
    for group in groups:
        alternatives=[]
        for term in group:
            if HAN.search(term):
                alternatives.append('(instr(lower(title),?)>0 OR instr(lower(body),?)>0)')
                params.extend([term.lower(),term.lower()]);han.append(term)
            else:
                alternatives.append('rowid IN (SELECT rowid FROM pages WHERE pages MATCH ?)')
                params.append('"'+term.replace('"','""')+'"')
        conditions.append('('+' OR '.join(alternatives)+')')
    if not conditions:return []
    score='-('+'+'.join('CASE WHEN '+c+' THEN 1 ELSE 0 END' for c in conditions)+')'
    sql='SELECT doc_id,page,body,'+score+' AS score FROM pages WHERE ('+(' OR ' if any_group else ' AND ').join(conditions)+')'
    bindings=params+params
    if ids is not None:
        sql += ' AND doc_id IN (SELECT value FROM json_each(?))'
        bindings.append(ids)
    sql+=' ORDER BY score, rowid LIMIT ?';bindings.append(limit)
    rows=con.execute(sql,bindings).fetchall()
    out=[]
    for doc,page,body,rank in rows:
        body=body or '';positions=[body.lower().find(t.lower()) for t in han]
        positions=[p for p in positions if p>=0];start=max(0,min(positions)-60) if positions else 0
        excerpt=('… ' if start else '')+body[start:start+220]+(' …' if start+220<len(body) else '')
        if han and any(markers):
            rx=re.compile('|'.join(re.escape(t) for t in sorted(set(han),key=len,reverse=True)),re.I)
            excerpt=rx.sub(lambda m:markers[0]+m.group()+markers[1],excerpt)
        out.append((doc,page,excerpt,rank))
    return out

