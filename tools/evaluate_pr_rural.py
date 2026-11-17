"""Compare extraction and offline map hits for the same public queries using the shipped Gemma and runner."""
import argparse
from contextlib import closing
from dataclasses import asdict
from decimal import InvalidOperation
import json
from pathlib import Path
import sqlite3
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine.pr_rural import lookup, parse
from engine import pr_rural_model as model_reader
from engine.pr_rural_model import fields, extract
import llm_local

CASES = Path(__file__).with_name('fixtures') / 'pr_rural_queries.json'
SECOND = CASES.with_name('pr_rural_queries_second.json')
HOLDOUT = CASES.with_name('pr_rural_queries_holdout.json')
FRESH = CASES.with_name('pr_rural_queries_fresh.json')


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
    return signatures(lookup(db, address, 20))


def signatures(items):
    return {(x['kind'], x['name'], x['lat'], x['lon'], x['detail']) for x in items}


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


def decoded(answer):
    try:
        return extract(answer), answer, None
    except (ValueError, TypeError, InvalidOperation) as exc:
        return None, answer, str(exc)


def gemma(query):
    return decoded(model_reader.inference(llm_local.LOCAL, query, lambda: False))


def report(rows):
    keys = ('fields_correct', 'map_correct', 'unexpected_pin', 'missed_pin', 'expected_pin')
    for method in (k for k in ('parser', 'gemma', 'combined') if k in rows[0]):
        for group in ['all', *dict.fromkeys(r['group'] for r in rows)]:
            scores = [r[method] for r in rows if group == 'all' or r['group'] == group]
            totals = {k:sum(s[k] for s in scores) for k in keys}
            print(method, group, len(scores), totals, 'median seconds', round(statistics.median(s['seconds'] for s in scores), 6))
    if 'live_map' in rows[0]:
        scores = [r['live_map'] for r in rows]
        print('live map', len(scores), {k:sum(s[k] for s in scores) for k in ('map_correct','unexpected_pin','missed_pin','interpreted')})


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('database', type=Path)
    p.add_argument('results', type=Path, help='new JSON Lines output')
    p.add_argument('--gemma', action='store_true', help='requires the exact pinned model and Lastbook runner')
    p.add_argument('--live-map', action='store_true', help='exercise the production place finder with its real optional model')
    p.add_argument('--replay', type=Path, help='score saved raw Gemma answers with the same checks, without loading a model')
    p.add_argument('--cases', nargs='+', type=Path, default=[CASES, SECOND, HOLDOUT, FRESH], help='ordered labelled fixture files')
    args = p.parse_args()
    if args.gemma and args.replay:
        p.error('select either --gemma or --replay')
    recorded = {}
    if args.replay:
        recorded = {r['query']:r['gemma'] for line in args.replay.read_text().splitlines() if (r := json.loads(line))}
    rows = []
    try:
        if args.gemma or args.live_map:
            start = time.monotonic()
            llm_local.LOCAL.discover()
            problem = llm_local.LOCAL.ensure_running()
            if problem:
                raise RuntimeError(problem + ' ' + str(llm_local.LOCAL.status()))
            print('Model ready after', round(time.monotonic()-start, 2), 'seconds including discovery.', flush=True)
        if args.live_map:
            import server
            if not (server.HERE / 'derived/geo/addresses/PR.sqlite').samefile(args.database):
                p.error('LASTBOOK_DATA must hold the selected index under derived/geo/addresses/PR.sqlite')
            server.assistant.LOCAL = llm_local.LOCAL
        with closing(sqlite3.connect(args.database.resolve().as_uri() + '?mode=ro', uri=True)) as db, args.results.open('x') as out:
            for group, query, label in (c for path in args.cases for c in json.loads(path.read_text())):
                expected = fields(label)
                row = {'group':group, 'query':query, 'gold':label, 'parser':measure(query, expected, db, deterministic)}
                if args.gemma:
                    row['gemma'] = measure(query, expected, db, gemma)
                elif args.replay:
                    saved = recorded[query]
                    row['gemma'] = measure(query, expected, db, lambda _: decoded(saved['raw']))
                    row['gemma']['seconds'] = saved['seconds']
                if 'gemma' in row:
                    # Evaluate the shipped decision on the very same inference. A replay's time covers validation and lookup only.
                    def combined(q):
                        parsed = parse(q)
                        if pins(db, parsed):
                            return parsed, None, None
                        try:
                            candidate = extract(row['gemma']['raw'])
                        except (ValueError, InvalidOperation, TypeError):
                            candidate = None
                        candidate = model_reader.validated(q, candidate, parsed)
                        if candidate:
                            return candidate, None, None
                        return parsed, None, None
                    row['combined'] = measure(query, expected, db, combined)
                if args.live_map:
                    start = time.perf_counter()
                    results = server.places(query)
                    actual, wanted = signatures(results), pins(db, expected)
                    row['live_map'] = {'map_correct': actual == wanted, 'unexpected_pin': bool(actual - wanted),
                                       'missed_pin': bool(wanted - actual), 'interpreted': any(r.get('interpreted') for r in results),
                                       'seconds': round(time.perf_counter()-start, 6), 'results': results}
                rows.append(row)
                print(json.dumps(row, ensure_ascii=False), file=out, flush=True)
        report(rows)
    finally:
        if args.gemma or args.live_map:
            llm_local.LOCAL.stop('evaluation finished')


if __name__ == '__main__':
    main()
