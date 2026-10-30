# data/export-ho

Raw-data export for pre-registration 6 (`docs/preregistration/2026-10-27-held-out-replication.md`): the
fixtures `runs/ho-fixtures` (dataset `H`: 25 `scope_padding` and 25 `ordinary_mistakes_k2` fixtures, seeds
9100–9124) and the monitor runs `runs/ho-mon-8b-v3`, `runs/ho-gem-v5`, `runs/ho-gem-v3` and `runs/ho-rule-v2`
(rule-v2 is a reference row, not pre-registered). Written on 2026-10-30 by `scripts/export_runs.py`; no model
calls, nothing in `runs/` changed.

```
python scripts/export_runs.py --out data/export-ho --dataset H=runs/ho-fixtures \
  --monitors runs/ho-mon-8b-v3,runs/ho-gem-v5,runs/ho-gem-v3,runs/ho-rule-v2
```

Columns are as in `data/export-ms2/README.md`; `fixture_policy` is filled for every episode. 50 episodes and 400
judgements (100 per run, all valid). `model_digest` is empty for Gemini rows (the API returns no digest); the
returned model version is in each run's `monitor_results.jsonl` (`response_model_ids`): `gemini-3.1-flash-lite`
on all 200 Gemini results.

**summarize.txt**: verbatim stdout of `wml summarize` over the four monitor runs, headed by the exact command
and followed by its exit code.
