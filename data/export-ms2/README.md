# data/export-ms2

Raw-data export of main study 2 (pre-registration 2, `docs/preregistration/2026-10-22-main-study-2.md`): the
six E1 batch dirs `runs/ms2-e1-b1` … `b6`, the E3 fixtures `runs/ms2-e3-fixtures`, and the eight monitor runs
`runs/ms2-e{1,3}-mon-{3b,8b}-{v3,v5}`. Written on 2026-10-27 at commit `fd51e92` by
`scripts/export_runs.py`; no model calls, nothing in `runs/` changed. `gap.jsonl` was first written for the
seven trajectory dirs with `wml gap` (the same code as the v1 export).

```
python scripts/export_runs.py --out data/export-ms2 \
  --dataset E1=runs/ms2-e1-b1,runs/ms2-e1-b2,runs/ms2-e1-b3,runs/ms2-e1-b4,runs/ms2-e1-b5,runs/ms2-e1-b6 \
  --dataset E3=runs/ms2-e3-fixtures \
  --monitors runs/ms2-e1-mon-3b-v3,runs/ms2-e1-mon-3b-v5,runs/ms2-e1-mon-8b-v3,runs/ms2-e1-mon-8b-v5,runs/ms2-e3-mon-3b-v3,runs/ms2-e3-mon-3b-v5,runs/ms2-e3-mon-8b-v3,runs/ms2-e3-mon-8b-v5
```

The columns are those of `data/export` (see its README), with these differences:

- **episodes.csv** (345 rows: E1 300, E3 45). `dataset` is `E1` for all six batch dirs (one dataset, as
  pre-registered) and `E3` for the fixtures; `run_id` keeps the batch dir. Added column `status` (submitted,
  aborted_malformed, action_limit, interrupted), so the non-submitted class can be read directly.
- **judgements.csv** (4950 rows, invalid outputs included). Added `repairs` and `repair_finish_reasons`
  (`;`-separated finish reasons of the failed attempts, e.g. `REPEAT_LIMIT`, from commit `1b9e03e`).
  `input_tokens` / `output_tokens` are summed over the result's calls in `calls.jsonl`.
- **manifests.json** (15 entries): each run's own `manifest.json`, plus `run_id`, `dataset` and, for monitor
  runs, `status`. Sessions and the git commit of each session are in `sessions`.
- **summarize.txt**: verbatim stdout of `wml summarize` over the E1 and over the E3 monitor runs, one block each,
  headed by the exact command and followed by its exit code.

`wml intervals --export data/export-ms2 --datasets E1,E3 --resamples 10000 --seed 20261021` reads this
export; its output is `docs/results/2026-10-27-main-study-2-intervals.md` and `.csv`.
