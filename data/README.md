# Released data

Per-episode and per-judgement exports of every run used in the paper. They are written from the run
directories (not committed; see "Run directories" below) by `scripts/export_runs.py` or, for `data/export`,
by the export code at its commit. No export involved a model call.

| Export | Paper | Datasets (episodes) | Judgements | Monitors |
|---|---|---|---|---|
| [`export/`](export/) | Study 1, pilots | D1 (60), D3 (50), calib (20), local-main (30), fresh (30), elicited (30) | 2570 | llama3.2:3b, llama3.1:8b-instruct-q4_K_M, rule-v2 |
| [`export-gemini/`](export-gemini/) | Study 2 | D1 (60), D3 (50) | 1280 | gemini-3.1-flash-lite (440); the v1 3B, 8B and rule-v2 rows needed for the pre-registered comparisons (840) |
| [`export-ms2/`](export-ms2/) | Study 4 | E1 (300), E3 (45) | 4950 | llama3.2:3b, llama3.1:8b-instruct-q4_K_M, rule-v2 |
| [`export-ho/`](export-ho/) | Study 5 | H (50) | 400 | llama3.1:8b-instruct-q4_K_M, gemini-3.1-flash-lite, rule-v2 |

Each export holds:

* `episodes.csv`: one row per episode, with labels (`category`, `category_v2`, `exploit_attempt`,
  `successful_exploitation`, `genuine_success`), the visible `proxy_score`, the `counterfactual_proxy`, true
  progress `true_progress_T`, the gap `gap_G`, the split and, for scripted episodes, `fixture_policy`.
* `judgements.csv`: one row per monitor judgement, invalid outputs included (`valid_output`, `error_type`),
  with suspicion score, category, cited event IDs, the checklist flag, model digest, prompt variant,
  condition, tokens, latency and `truncated`.
* `manifests.json`: each run's manifest (config snapshot, model digests or version strings, prompt hashes,
  software versions, sessions and their git commits).
* `summarize.txt` (`summarize-check.txt` in `export/`): verbatim `wml summarize` output over the runs.
* `README.md`: the exact export command and any export-specific columns.

Labels and definitions: [`docs/ground_truth.md`](../docs/ground_truth.md). Column-level documentation:
[`export/README.md`](export/README.md) and [`export-ms2/README.md`](export-ms2/README.md).

## Rules for use

* **Never pool datasets.** D1, D3, E1, E3, H and the pilot datasets come from different agents, environment
  variants or scripted policies. `wml intervals --datasets` analyses each separately.
* **The v1 rows in `export-gemini/` duplicate rows in `export/`** (same run IDs); they are included only so
  that the Gemini comparisons can be computed from one export. Do not count them twice.
* **Scripted fixtures (D3, E3, H) are not evidence about agents.** They test monitors on known behaviours.
* **Scope padding** is labelled only in the `_v2` fields and is excluded from both sides of the primary
  analyses (see the pre-registrations).

## Run directories

The full run directories (`runs/<name>/`: trajectories with every event, labels, every model call, monitor
inputs and outputs, budgets and status) are not in git because of their size. The exports contain every
quantity reported in the paper. The trajectories and monitor outputs quoted verbatim in the results notes
come from these directories.
