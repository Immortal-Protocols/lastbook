"""The tables of docs/TRIAGE-SEARCH.md §1 (sensitivity to LONG and SECTION, and the index built by this part's indexer),
from score.py --rows files.

    python -B tools/search_eval/sections_sweep/analyse.py --base <main keyword run.json> --runs <folder>
           [--base-hybrid <main hybrid run.json> --hybrid <this part, main's index.json> <this part, own index.json>]
           [--json results.json]

Measures, on the triage set (362 questions): red clean questions whose first page is useful (n = 131), exact McNemar
against the base run; how many triage questions have the long book "Modern Machine-Shop Practice" in their top 8; the
mean number of useful pages of 8. The pages cut are read from each run's summary.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import stats  # noqa: E402  (tools/search_eval/stats.py)

BOOK = 'Machine-Shop'


def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def key(r):
    return r['set'], r.get('id'), r['q']


def measure(run, base):
    rs = [r for r in run['rows'] if r['set'] == 'triage']
    red = [r for r in rs if r.get('colour') == 'red' and not r.get('typo') and not r.get('counter')]
    gained = sum(1 for r in red if r['first_ok'] and not base[key(r)]['first_ok'])
    lost = sum(1 for r in red if not r['first_ok'] and base[key(r)]['first_ok'])
    sec = run['summary'].get('sections')
    return {'pages_cut': sec.get('long_pages') if isinstance(sec, dict) else None,
            'red_first_useful': sum(r['first_ok'] for r in red), 'red_n': len(red), 'gained': gained, 'lost': lost,
            'p_exact_mcnemar': stats.mcnemar_p(gained, lost),
            'book_in_top8': sum(any(BOOK in (t or '') for t in r.get('titles') or []) for r in rs),
            'mean_useful_of_8': round(sum(r['useful'] for r in rs) / len(rs), 2)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--base', required=True)
    ap.add_argument('--runs', required=True)
    ap.add_argument('--base-hybrid')
    ap.add_argument('--hybrid', nargs=2)
    ap.add_argument('--json')
    a = ap.parse_args()
    base_run = load(a.base)
    base = {key(r): r for r in base_run['rows']}
    out = {'base': measure(base_run, base), 'pairs': {}}
    for f in sorted(Path(a.runs).glob('keyword_L*_S*.json'), key=lambda p: [int(x) for x in re.findall(r'\d+', p.stem)]):
        out['pairs'][f.stem] = measure(load(f), base)
    print('| run | pages cut | red, first page useful | vs base: +/-, p | Machine-Shop book in top 8 | useful of 8 |')
    print('|---|---|---|---|---|---|')
    for name, m in [('base', out['base'])] + list(out['pairs'].items()):
        print(f"| {name} | {m['pages_cut'] or '-'} | {m['red_first_useful']}/{m['red_n']} | "
              f"+{m['gained']}/-{m['lost']}, p = {m['p_exact_mcnemar']:.3g} | {m['book_in_top8']} | {m['mean_useful_of_8']} |")
    if a.base_hybrid and a.hybrid:
        hb_run = load(a.base_hybrid)
        hb = {key(r): r for r in hb_run['rows']}
        out['hybrid'] = {'base': measure(hb_run, hb), 'main_index': measure(load(a.hybrid[0]), hb),
                         'own_index': measure(load(a.hybrid[1]), hb)}
        print('\nhybrid:')
        for name, m in out['hybrid'].items():
            print(f"  {name}: red first useful {m['red_first_useful']}/{m['red_n']} (+{m['gained']}/-{m['lost']}, "
                  f"p = {m['p_exact_mcnemar']:.3g}), book {m['book_in_top8']}, useful {m['mean_useful_of_8']}")
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
