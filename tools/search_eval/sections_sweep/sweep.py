"""Measure the long-page cutoffs of engine/sections.py: run tools/search_eval/score.py once per (LONG, SECTION) pair.

    set LASTBOOK_DATA=<data folder with the Medium pack>
    python -B tools/search_eval/sections_sweep/sweep.py --out <results folder> [--mode keyword|hybrid]
           [--long 10000,20000,40000] [--section 2500,5000,10000] [--jobs 3]

Nothing in the code is edited: for each pair, run_cut.py sets engine.sections.LONG and SECTION in the scorer's own
process. Each pair gets its own sections folder inside --out (never in the data folder). Output: one
<mode>_L<LONG>_S<SECTION>.json per pair (score.py --rows), with its .log and .err next to it.
"""
import argparse
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--out', required=True)
    ap.add_argument('--mode', choices=('keyword', 'hybrid'), default='keyword')
    ap.add_argument('--long', default='10000,20000,40000')
    ap.add_argument('--section', default='2500,5000,10000')
    ap.add_argument('--jobs', type=int, default=1)
    a = ap.parse_args()
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    pairs = [(int(lo), int(se)) for lo in a.long.split(',') for se in a.section.split(',')]

    def one(pair):
        lo, se = pair
        name = f'{a.mode}_L{lo}_S{se}'
        sec = out / 'sections' / f'L{lo}_S{se}'
        sec.mkdir(parents=True, exist_ok=True)
        cmd = [sys.executable, '-B', str(HERE / 'run_cut.py'), str(ROOT), str(lo), str(se),
               '--mode', a.mode, '--rows', '--sections', str(sec), '--out', str(out / f'{name}.json')]
        with open(out / f'{name}.log', 'w', encoding='utf-8') as lg, open(out / f'{name}.err', 'w', encoding='utf-8') as er:
            rc = subprocess.run(cmd, stdout=lg, stderr=er).returncode
        print(name, 'exit', rc, flush=True)
        return rc

    with ThreadPoolExecutor(max_workers=max(1, a.jobs)) as ex:
        codes = list(ex.map(one, pairs))
    sys.exit(max(codes))


if __name__ == '__main__':
    main()
