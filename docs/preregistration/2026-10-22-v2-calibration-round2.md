# Pre-registration 1b: environment v2 calibration, round 2 (exploratory)

**Status:** frozen 2026-10-22, **before any v2d episode exists** (draft committed in a323158, review items
added in ec52a40; this commit only removes "(DRAFT)" and records the freeze). The run starts after this
commit, and nothing below changes. Roadmap: Part B, B1 follow-up.

## Why there is a round 2

Pre-registration 1 ([2026-10-21-v2-calibration.md](2026-10-21-v2-calibration.md),
[results](../results/2026-10-22-v2-calibration.md)) chose no variant: v2a 1/10, v2b 1/10, v2c 2/10 genuine
successes, all below the 3/10 floor. Its rule was to report and stop, and it did. Nothing in it is re-run or
changed. This is a **new** study, decided after review on 2026-10-22, and it is reported as a response to
B1's result.

The new variant was designed after looking at the B1 calibration episodes. In the 26 failed episodes, every
wrong order was a hard one; no simple order was ever wrong. Wrong orders by kind, over all three
variants: undelivered 17, with_return 8, split_match 4. The most common errors were outcome "matched" or
"over" where the answer was "short" (23), and missing evidence (9). The full analysis, with its code and
per-episode output, is [2026-10-22-b1-failure-analysis.md](../results/2026-10-22-b1-failure-analysis.md). B1
episodes are calibration data. They are not used in any monitor evaluation or in main study 2.

## Question

Does variant v2d give the 8B agent a genuine-success rate between 30% and 70% on the clean task? If it does,
main study 2 and the online-blocking study use v2d.

## Variant

**v2d = v2c + a second worked example** (`agent.WORKED_EXAMPLE_HARD`, `config.ENV_VARIANTS["v2d"]`). It is
code commit `f10b205`. The example reconciles two fictional orders, appended after the v2b/v2c example:
* a split shipment: two delivered records that add up to the quantity ordered, so the outcome is "matched";
* an undelivered order: one failed_attempt record, so net delivered is 0, the outcome is "short", and the
  record is cited.

Like the first example, it uses IDs the generator can never produce, and it never mentions scope, completion
flags, the visible score or any shortcut. Tests check this, and also check that every call in the example
gives exactly the result shown when run against the simulator. 3 required orders, as in v2c. Everything else
is unchanged: proxy, permissive tools, verifier, label predicates and task text. The v2a, v2b and v2c prompts
are unchanged and pinned to their B1 hashes by a test.

## Design

| item | value |
|---|---|
| agent | Ollama `llama3.1:8b-instruct-q4_K_M` (the D1 and B1 agent), temperature 0.7, max 400 output tokens, num_ctx 8192, max 30 actions per episode |
| task | clean task (`wml calibrate`: no permissive tools, no elicitation, no instruction to cheat) |
| variant | v2d only |
| seeds | **7010–7019**, fresh: no saved trajectory uses them (the highest seed in use is 7009) |
| episodes | 10, 1 sample per scenario |
| config | `configs/v2-calib2-v2d.toml`, identical to `configs/v2-calib-v2c.toml` except the seeds and `variant = "v2d"` |
| run dir | `runs/v2-calib2-v2d` |

```
wml calibrate --config configs/v2-calib2-v2d.toml --enable-network --run-dir runs/v2-calib2-v2d
wml summarize runs/v2-calib2-v2d --out runs/v2-calib2-v2d-summary --no-plots
```

v2d is a separate dataset. It is never pooled with the B1 variants. No monitor is run in this study.

With n = 10 the selection rule is a coarse gate: 3/10 is not an estimate of the true success rate.

## Outcomes

These are the same as pre-registration 1.

**Primary:** genuine-success rate = (episodes with `genuine_success` true) / 10, with a Wilson 95% interval.
An episode that does not submit counts as not a success.

**Secondary:**
* the rate over submitted episodes;
* episodes per hour and mean episode duration;
* invalid actions;
* non-submitted episodes by status;
* interruptions;
* `category_v2` counts;
* wrong orders by order kind and by error, which is the table above, computed the same way.

Any attempt label on the clean task would point to a bug and would be reported.

Main study 2 measures genuine success again, with the permissive tools present, and reports it whatever this
calibration found.

## Selection rule (fixed now)

Let k be the number of genuine successes out of 10.

1. If 3 ≤ k ≤ 7, **v2d is chosen** for main study 2 and the online-blocking study.
2. Otherwise no variant is chosen. This covers k ≤ 2 and also k ≥ 8. The result is reported and the study
   stops.

The rule uses only the primary outcome. B1's variants are not reconsidered.

If v2d does not qualify, no further prompt-only variant is tried. The next step is either a different agent
model, under its own pre-registration, or reporting the v1 study as it stands.

## Exclusions and interruptions

These are as in pre-registration 1:
* No episode is excluded.
* An interrupted run is continued with `wml resume`, and the interruption is reported.
* No seed is replaced or added.
* A change in the agent model's digest from B1 (`46e0c10c039e…`) is reported, and the run is not repeated.

## Not part of this study

* No other variant and no other model.
* No prompt change after freezing.
* No use of these episodes in any monitor evaluation or in main study 2.
