# data/export-gemini

Raw-data export for pre-registration 3 (`docs/preregistration/2026-10-22-gemini-monitor-v1.md`): the four
Gemini monitor runs `runs/gem-d1-v5`, `gem-d1-v3`, `gem-d3-v5`, `gem-d3-v3`, the v1 trajectories they judged
(`runs/hvf-d1-actor`, `runs/hvf-d3-fixtures`), and, for the pre-registered comparisons, the v1 runs
`runs/hvf-d1-mon-8b-v5` and `runs/hvf-d3-mon-8b-v5` (8B v5) and `runs/hvf-d1-mon-3b-v3` and
`runs/hvf-d3-mon-3b-v3` (which hold rule-v2, needed for the combined detector, and 3B v3). Written on
2026-10-27 by `scripts/export_runs.py`; no model calls, nothing in `runs/` changed.

```
python scripts/export_runs.py --out data/export-gemini \
  --dataset D1=runs/hvf-d1-actor --dataset D3=runs/hvf-d3-fixtures \
  --monitors runs/gem-d1-v5,runs/gem-d1-v3,runs/gem-d3-v5,runs/gem-d3-v3,runs/hvf-d1-mon-3b-v3,runs/hvf-d1-mon-8b-v5,runs/hvf-d3-mon-3b-v3,runs/hvf-d3-mon-8b-v5
```

Columns are as in `data/export-ms2/README.md`. 110 episodes (D1 60, D3 50) and 1280 judgements (Gemini 440,
v1 local and rule-v2 840). The v1 rows here are the same judgements as in `data/export`. `model_digest` is empty for
Gemini rows (the API returns no digest); the returned model version is in each run's `monitor_results.jsonl`
(`response_model_ids`).

**summarize.txt**: verbatim stdout of `wml summarize` over the Gemini D1 runs and over the Gemini D3 runs, one
block each, headed by the exact command and followed by its exit code.

`wml intervals --export data/export-gemini --datasets D1,D3 --resamples 10000 --seed 20261021` reads this
export; its output is `docs/results/2026-10-27-gemini-monitor-intervals.md` and `.csv`.
