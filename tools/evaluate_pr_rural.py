"""Compare extraction and offline map hits for the same public queries using the shipped Gemma and runner."""
import argparse
from contextlib import closing
from dataclasses import asdict
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
import sqlite3
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine.pr_addresses import fold
from engine.pr_rural import RuralAddress, lookup, parse
import llm_local

CASES = Path(__file__).with_name('fixtures') / 'pr_rural_queries.json'
SECOND = CASES.with_name('pr_rural_queries_second.json')
PROMPT = """Read one Puerto Rico physical address. Output only JSON. Use null if there is no single
numbered road and single kilometer, if the kilometer figures conflict, or if the address requests a
house or lot number. An explicit cross street is a landmark, not a second possible main road.
In a physical address like '3.5 Carr 100', the decimal is the kilometer. An unmarked whole number
beside a road can be a house number: do not assume it is a kilometer. Hectometers are tenths of
a kilometer. Read spoken Spanish numbers and English or Spanish address abbreviations.
Return the array [road, kilometer, locality, ZIP, interior, sector, landmark]. Road is an integer;
kilometer is a decimal string. Locality contains the supplied barrio and municipio names in that order,
separated by a space, without labels. Keep a supplied place even when it seems wrong. Keep the five ZIP
digits including leading zeros. Interior is a boolean. Put sector or community names in sector without
the label, and other named sites, cross streets and directions in landmark, preserving the direction.
Use an empty string for each absent text field. Never add a place, coordinate or number from memory.
Example: 'Km 3 hm 2 Interior, Ctra 81, Bo. Azul, Villa Ejemplo' -> [81,"3.2","Azul Villa Ejemplo","",true,"",""]."""


def fields(value):
    if value is None:
        return None
    if not isinstance(value, list) or len(value) != 7:
        raise ValueError('expected seven fields')
    road, km, area, postal, interior, sector, landmark = value
    if type(road) is not int or not 1 <= road <= 9999 or type(interior) is not bool:
        raise ValueError('invalid route or interior')
    if not all(isinstance(s, str) for s in (area, postal, sector, landmark)) or not re.fullmatch(r'(?:\d{5})?', postal):
        raise ValueError('invalid qualifier')
    if isinstance(km, bool) or not re.fullmatch(r'\d{1,3}(?:[.]\d{1,3})?', str(km)):
        raise ValueError('invalid kilometer')
    return RuralAddress(road, int(Decimal(str(km)) * 1000), fold(area), postal, interior, fold(sector), fold(landmark))


def extract(text):
    # Accept both bare JSON and a single Markdown-wrapped JSON answer.
    raw = re.fullmatch(r'\s*\x60\x60\x60(?:json)?\s*(.*?)\s*\x60\x60\x60\s*', text, re.S | re.I)
    return fields(json.loads(raw[1] if raw else text.strip(), parse_float=Decimal))


def equivalent(a, b):
    if a is None or b is None:
        return a == b
    def components(addr):
        words = [w for w in addr.locality.split() if w not in ('barrio', 'municipio')]
        return addr.route, addr.meters, sorted(words), addr.postal, addr.interior, addr.sector, addr.landmark
    return components(a) == components(b)


def pins(db, address):
    if address is None:
        return set()
    return {(x['kind'], x['name'], x['lat'], x['lon'], x['detail']) for x in lookup(db, address, 20)}


def measure(query, expected, db, producer):
    start = time.perf_counter()
    address, raw, error = producer(query)
    actual = pins(db, address)
    elapsed = time.perf_counter() - start
    wanted = pins(db, expected)
    return {'fields_correct': not error and equivalent(expected, address),
            'map_correct': actual == wanted, 'unexpected_pin': bool(actual - wanted),
            'missed_pin': bool(wanted - actual), 'expected_pin': bool(wanted),
            'seconds': round(elapsed, 6), 'fields': asdict(address) if address else None,
            'raw': raw, 'error': error}


def deterministic(query):
    return parse(query), None, None


def gemma(query):
    messages = [{'role': 'system', 'content': PROMPT}, {'role': 'user', 'content': query}]
    pieces = []
    llm_local.LOCAL.generate(llm_local.render(messages, []), 144, lambda: False, pieces.append)
    answer = llm_local._strip_thinking(''.join(pieces))
    try:
        return extract(answer), answer, None
    except (ValueError, TypeError, InvalidOperation) as exc:
        return None, answer, str(exc)


def report(rows):
    keys = ('fields_correct', 'map_correct', 'unexpected_pin', 'missed_pin', 'expected_pin')
    for method in (k for k in ('parser', 'gemma') if k in rows[0]):
        for group in ['all', *dict.fromkeys(r['group'] for r in rows)]:
            scores = [r[method] for r in rows if group == 'all' or r['group'] == group]
            totals = {k:sum(s[k] for s in scores) for k in keys}
            print(method, group, len(scores), totals, 'median seconds', round(statistics.median(s['seconds'] for s in scores), 6))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('database', type=Path)
    p.add_argument('results', type=Path, help='new JSON Lines output')
    p.add_argument('--gemma', action='store_true', help='requires the exact pinned model and Lastbook runner')
    args = p.parse_args()
    rows = []
    try:
        if args.gemma:
            start = time.monotonic()
            llm_local.LOCAL.discover()
            problem = llm_local.LOCAL.ensure_running()
            if problem:
                raise RuntimeError(problem + ' ' + str(llm_local.LOCAL.status()))
            print('Model ready after', round(time.monotonic()-start, 2), 'seconds including discovery.', flush=True)
        with closing(sqlite3.connect(args.database.resolve().as_uri() + '?mode=ro', uri=True)) as db, args.results.open('x') as out:
            for group, query, label in [*json.loads(CASES.read_text()), *json.loads(SECOND.read_text())]:
                expected = fields(label)
                row = {'group':group, 'query':query, 'gold':label, 'parser':measure(query, expected, db, deterministic)}
                if args.gemma:
                    row['gemma'] = measure(query, expected, db, gemma)
                rows.append(row)
                print(json.dumps(row, ensure_ascii=False), file=out, flush=True)
        report(rows)
    finally:
        if args.gemma:
            llm_local.LOCAL.stop('evaluation finished')


if __name__ == '__main__':
    main()
