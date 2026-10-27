# Pre-registration 4 (WITHDRAWN): online blocking with rule-v2

**Withdrawn 2026-10-27, before any data.** No blocked or unblocked episode was generated for this study, and
the placeholders were never filled; the plan was never frozen. Reason: too few exploits with the 3B agent
(main study 2, `llama3.2:3b`: 4 exploit attempts in 300 episodes; [results](../results/2026-10-27-main-study-2.md)).
The draft below is kept unchanged as a record.

**Status:** draft, written 2026-10-22, before any blocked episode exists. Roadmap A6 item 4. The placeholders
(`<…>`) are filled after the environment variant is settled, and the commit that removes "(DRAFT)" freezes the
plan. Code: `--block-with rule-v2` (`src/weak_monitor_lab/blocking.py`, roadmap A5).

**Open dependency.** The roadmap specifies "v2 (variant chosen in 1)". Pre-registration 1 chose **no variant**
(see [B1 results](../results/2026-10-22-v2-calibration.md)), so `<VARIANT>` has no value yet. A second calibration round
([pre-registration 1b](2026-10-22-v2-calibration-round2.md)) tests v2d; `<VARIANT>` is v2d if v2d qualifies
there, and stays open otherwise.

## Design (paired)

| item | value |
|---|---|
| agent | Ollama `llama3.1:8b-instruct-q4_K_M`, the same settings as main study 2 (temperature 0.7, max 400 tokens, num_ctx 8192, max 30 actions, permissive tools, no elicitation) |
| environment | v2, `<VARIANT>` |
| seeds | `<SB>`–`<SB + N − 1>`, fresh, and disjoint from main study 2 |
| episodes | `<N>` per arm, 1 sample per scenario, so `2 × <N>` in total |
| arm U (unblocked) | `wml generate --config configs/block-u.toml --run-dir runs/block-u` |
| arm B (blocked) | `wml generate --config configs/block-b.toml --run-dir runs/block-b --block-with rule-v2` |
| pairing | the same seed and the same `sample_seed` in both arms; the configs differ only in `block_with` |

The two arms are run alternately in batches of 10 seeds (U then B), so time-of-night effects fall on both arms.
The arms are two datasets: they are summarized separately (`wml summarize` keeps blocked runs apart) and
compared only as pairs.

No monitor model is used. Blocking uses the deterministic rule-v2 predicates, which are the label predicates.

## Primary outcome

**Successful exploitation per episode** (`successful_exploitation`, from replay of the executed actions),
arm B vs arm U.

## Co-primary outcome

**Genuine success per episode**, arm B vs arm U, to measure the cost of blocking to honest work.

## Analysis and decision rules (fixed)

For each of the two outcomes, over pairs where both episodes submitted:
* the rate per arm, k/n with a Wilson 95% interval;
* the paired difference U − B, with a percentile bootstrap 95% interval that resamples pairs (base scenarios)
  with replacement, seed 20261022, 10,000 resamples;
* discordant pair counts (U yes and B no, U no and B yes).

Decision rules:
* **Blocking reduces successful exploitation** is stated only if the interval for U − B in successful
  exploitation lies entirely above 0.
* **Blocking costs honest work** is stated only if the interval for U − B in genuine success lies entirely
  above 0. If it lies entirely below 0, that is stated the same way. Otherwise "no difference detected at
  this n" is stated.

## Secondary outcomes (per arm, from `wml summarize` "Online blocking")

* blocked actions; correct blocks (attempt predicates fire) vs wrongly blocked honest actions (expected 0 for
  rule-v2, by construction; reported anyway);
* episodes with at least one block; episodes where the agent gave up after a block (no successful write action
  after the last block);
* successful exploitation that got through anyway, including scope padding (`successful_exploitation_v2`),
  which rule-v2 does not block;
* exploit attempts in arm U; the number of actions per episode; non-submitted episodes by status.

## Exclusions

* Pairs where either episode did not submit are excluded from the paired analysis. They are counted and
  listed, with the per-arm status.
* Nothing else is excluded. No threshold or rule is tuned; rule-v2 is used as implemented at the freezing commit.

## Interruptions

`wml resume` continues a stopped arm with its saved config, `block_with` included, and never repeats a
completed episode. If one arm cannot be completed, only the completed pairs are analysed and the shortfall is
reported. No seed is replaced.

## TODO, not part of this study: a periodic-monitor arm

Proposed after the monitoring red-team review (2026-10-22). A secondary arm in which the 8B monitor (prompt v5)
judges the trace so far every 5 actions. A flag stops the episode for review, and the detection delay is
reported in actions. It is **not implemented**, because it is not a small change:
* The monitor views describe a finished episode. The input says "Episode end: … ended WITHOUT a submitted
  report", and condition C's `final` block states the final scope, completion flags and score. A trace in
  progress needs different wording, so the monitor input changes. That needs its own pre-registration, and v5
  results on finished episodes would not carry over.
* It needs a new episode status (stopped for review) and resume rules for it.
* It needs a detection-delay metric with a definition for episodes that are never flagged.

If it is added later, it gets its own pre-registration (or an amendment to this one, made before any data).

## Placeholders to fill before freezing

`<VARIANT>`, `<SB>`, `<N>`, and `configs/block-u.toml` / `configs/block-b.toml` (written in the same commit).
