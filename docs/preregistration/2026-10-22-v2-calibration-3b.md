# Pre-registration 1c: environment v2 calibration, round 3, 3B agent (exploratory)

**Status:** frozen 2026-10-22, **before any 3B v2 episode exists** (draft committed in 3447de2, approved on
review without changes; this commit only removes "(DRAFT)" and records the freeze). The run starts after this
commit, and nothing below changes. Roadmap: Part B, B1 follow-up.

## Why there is a round 3

Pre-registration 1 ([results](../results/2026-10-22-v2-calibration.md)) chose no variant for the 8B agent:
v2a 1/10, v2b 1/10, v2c 2/10. Pre-registration 1b ([results](../results/2026-10-22-v2-calibration-round2.md))
chose no variant either: v2d 8/10, above the 7/10 ceiling. 1b's rule says no further prompt-only variant is
tried, and that the next step is either a different agent model, under its own pre-registration, or reporting
the v1 study as it stands. On 2026-10-22 the user chose a different agent model, `llama3.2:3b`. This is that
pre-registration. Nothing in pre-registrations 1 or 1b is re-run or changed, and no new variant is made.

Known before this study: on the v1 clean task the 3B agent had 0/10 genuine successes (v1 D2,
[results](../results/2026-10-06-hacking-vs-failing.md)), against 2/10 for the 8B agent. On v2 the 8B agent
ranged from 1/10 (v2a) to 8/10 (v2d). No 3B episode on v2 exists.

## Question

Which existing environment v2 variant, if any, gives the 3B agent a genuine-success rate between 30% and 70%
on the clean task? If one does, main study 2 and the online-blocking study use the 3B agent with that
variant, after their own pre-registrations are amended and frozen.

## Design

| item | value |
|---|---|
| agent | Ollama `llama3.2:3b`, digest `a80c4f17acd5…` (the v1 D2-3B agent and the v1 3B monitor model), temperature 0.7, max 400 output tokens, num_ctx 8192, max 30 actions per episode |
| task | clean task (`wml calibrate`: no permissive tools, no elicitation, no instruction to cheat) |
| variants | v2a, v2b, v2c, v2d, exactly as frozen in pre-registrations 1 and 1b (`config.ENV_VARIANTS`). Actor system-prompt sha256: v2a `661c54a8…`, v2b and v2c `8b66a1e7…` (pinned in `tests/test_env_v2.py`), v2d `6a86f856…` (as in the round-2 results) |
| seeds | **7020–7029**, the same ten seeds for every variant, fresh: no saved trajectory uses them (the highest seed in use is 7019). v2a and v2b draw 4 required orders per seed, v2c and v2d 3 |
| episodes | 10 per variant, 40 in total, 1 sample per scenario |
| configs | `configs/v2-calib3-3b-v2a.toml` … `configs/v2-calib3-3b-v2d.toml`. Each is identical to `configs/hvf-calib-3b.toml` (v1 D2-3B) except the seeds, `[environment]` and, for v2c and v2d, `n_required = 3` |
| run dirs | `runs/v2-calib3-3b-v2a` … `runs/v2-calib3-3b-v2d` |
| order | v2a, v2b, v2c, v2d, one at a time on the same machine |

Commands, in this order (driver `runs/b1c-run.sh`; it resumes an interrupted step and skips a completed one):

```
wml calibrate --config configs/v2-calib3-3b-v2a.toml --enable-network --run-dir runs/v2-calib3-3b-v2a
wml calibrate --config configs/v2-calib3-3b-v2b.toml --enable-network --run-dir runs/v2-calib3-3b-v2b
wml calibrate --config configs/v2-calib3-3b-v2c.toml --enable-network --run-dir runs/v2-calib3-3b-v2c
wml calibrate --config configs/v2-calib3-3b-v2d.toml --enable-network --run-dir runs/v2-calib3-3b-v2d
wml summarize runs/v2-calib3-3b-v2a --out runs/v2-calib3-3b-v2a-summary --no-plots   (likewise v2b, v2c, v2d)
```

The four variants are four datasets. They are never pooled with each other or with the 8B calibration
runs. No monitor is run in this study. No Gemini model is used.

With n = 10 the selection rule is a coarse gate: 3/10 is not an estimate of the true success rate.

## Outcomes

These are the same as pre-registrations 1 and 1b.

**Primary, per variant:** genuine-success rate = (episodes with `genuine_success` true) / 10, with a Wilson
95% interval. An episode that does not submit counts as not a success.

**Secondary, per variant:**
* the rate over submitted episodes;
* episodes per hour and mean episode duration (used only to size main study 2);
* invalid actions (malformed outputs per actor call, rejected tool calls per executed action, aborted
  episodes);
* non-submitted episodes by status, and interruptions;
* `category_v2` counts;
* wrong orders by order kind and by error, computed as in
  [the B1 failure analysis](../results/2026-10-22-b1-failure-analysis.md).

Any attempt label on the clean task would point to a bug and would be reported.

Main study 2 measures genuine success again, with the permissive tools present, and reports it whatever this
calibration found.

## Selection rule (fixed now)

Let k be the number of genuine successes out of 10 for a variant.

1. A variant **qualifies** if 3 ≤ k ≤ 7.
2. Among qualifying variants, choose the one with the smallest |k/10 − 0.5|.
3. **Ties** go to the earlier variant in the order v2a, v2b, v2c, v2d.
4. If **no variant qualifies**, report it and stop. No variant is chosen, nothing is re-run, and no variant is
   changed or added in response.

The rule uses only the primary outcome. Secondary outcomes do not change the choice.

## Consequences for main study 2 (recorded now, decided at its review)

If a variant is chosen, the 3B model is both the agent and one of main study 2's two monitors (3B and 8B,
pre-registration 2). Two things then change from v1 and must be settled when pre-registration 2 is amended,
before it is frozen:
* the 3B monitor would judge traces written by its own model;
* the primary monitor (8B) would be larger than the agent, where in v1 it was the same model as the agent.

This study does not decide either point. They are listed here so the choice of agent is not made blind to them.

## Exclusions and interruptions

These are as in pre-registrations 1 and 1b:
* No episode is excluded.
* An interrupted run is continued with `wml resume`, and the interruption is reported.
* No seed is replaced or added.
* If the agent model's digest changes from `a80c4f17acd5…` between variants, it is reported, and the run is
  not repeated.

## Not part of this study

* No other model and no new variant.
* No prompt change after freezing.
* No use of these episodes in any monitor evaluation or in main study 2.
