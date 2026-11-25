# Long pages in sections: sensitivity to the cutoffs, and the index built by this part's indexer

These are the scripts behind the two checks in `docs/TRIAGE-SEARCH.md` §1. The full results they produced, one
`score.py --rows` file per run, are on the data branch
[`eval-data/part2-sections`](https://github.com/STAirye/lastbook/tree/eval-data/part2-sections) of STAirye/lastbook,
with `SHA256SUMS`.

| File | What it does |
|---|---|
| `run_cut.py` | Runs this checkout's `tools/search_eval/score.py` with `engine.sections.LONG` and `SECTION` set in its own process. No code is edited. |
| `sweep.py` | Calls `run_cut.py` once for each pair, each pair with its own sections folder (never in the data folder). |
| `build_index_gpu.py` | Builds the meaning index with this checkout's own indexer (`python retrieval.py`), with the model on an NVIDIA GPU (onnxruntime-gpu from a folder you give it). |
| `analyse.py` | Produces the tables in §1 from the run files. |

## Rerun

Use the published Medium pack, with `LASTBOOK_DATA` pointing at its data folder.

```
python -B tools/search_eval/sections_sweep/sweep.py --out sweep --mode keyword --jobs 3
```

This runs the 9 pairs of `LONG` 10,000 / 20,000 / 40,000 and `SECTION` 2,500 / 5,000 / 10,000, about 4 to 5 minutes
each.

For the index built by this part's own indexer, use a data folder whose `derived/index` can be rebuilt:

```
python -B tools/search_eval/sections_sweep/build_index_gpu.py <onnxruntime-gpu folder>
python -B tools/search_eval/sections_sweep/run_cut.py . 20000 5000 --mode hybrid --rows --sections <scratch folder> --out hybrid_own_index_L20000_S5000.json
```

The build took 1 h 07 min on an RTX 3080 Ti. A plain `python retrieval.py` builds the same passages on the CPU, in
about 4 to 5 hours.

Then run the analysis:

```
python -B tools/search_eval/sections_sweep/analyse.py --base main_keyword.json --runs sweep --base-hybrid main_hybrid.json --hybrid hybrid_main_index_L20000_S5000.json hybrid_own_index_L20000_S5000.json
```

`main_keyword.json` and `main_hybrid.json` are `score.py --rows` runs of `main`, the same files as on the data branch.

## What was measured (2026-11-25)

Keyword runs, branch rebased onto `main` d223056.

- **Pages cut, for each `LONG`:** 1,044 at 10,000; 351 at 20,000; 100 at 40,000.
- **Red questions, first page useful (of 131):**
  - `main`: 58.
  - Every pair: 59 or 60.
  - Against `main`, the best pair gains 3 and loses 1 (p = 0.625), and the others gain 1 or 2 and lose none (p ≥ 0.5).
- ***Modern Machine-Shop Practice* in the top 8 (of 362 triage questions):** 25 on `main`, 4 or 5 for every pair.

Hybrid, at the chosen pair 20,000 → 5,000 (red questions, first page useful):

| Index | Red, first page useful (of 131) | Against `main` |
|---|---|---|
| `main` | 88 | |
| This part, on `main`'s index | 90 | +3/−1, p = 0.625 |
| This part, on its own index | 92 | +4/−0, p = 0.125 |

The own index holds 340,532 passages, `text_sha256` c00f64f9…

All the sets used are development sets. These runs show that the result holds across sizes; they do not tune the
sizes.
