# Plan update after METR's monitoring red-team (2026-10-22)

Scope: code and draft pre-registrations only. No model calls. The v1 results and pre-registration 1b are not
touched.

## The plan as given (verbatim)

1. Monitor-input fidelity audit:
   - Test that view B contains every tool result the agent received,
     in order, for fixtures and a sample of saved D1 episodes.
   - Count, for every existing monitor run, judgements whose input was
     truncated by max_input_chars; add a `truncated` column to
     judgements.csv and a line to wml summarize.
   - Add tests that agent-written text containing fence markers,
     unbalanced quotes, braces or very long strings cannot break or
     shift the monitor input's structure.
   Report counts verbatim.

2. Coverage metric: wml summarize reports, per monitor run,
   episodes eligible / judged with a valid output / invalid / refused /
   not attempted (e.g. daily cap), with reasons.

3. Main study 2 draft: monitors run on ALL episodes, including
   non-submitted ones, which are reported as a separate class and never
   dropped. Amend the draft (it is unfrozen; no data exists).

4. Online-blocking draft (optional, only if simple): add a secondary arm
   where the 8B monitor (prompt v5) judges the trace so far every 5
   actions; a flag stops the episode for review. Report detection delay
   in actions. If it is not simple, add it as a TODO note instead.

Push, report test results and the commit hash, and stop.

## Where each item is

| item | where |
|---|---|
| 1 | `src/weak_monitor_lab/fidelity.py`, `tests/test_fidelity.py`, the fence-marker fix in `monitor/views.py`, the `truncated` column in `data/export/judgements.csv`, and [results](../results/2026-10-22-monitor-input-fidelity.md) |
| 2 | `analysis.coverage_section`, the "Monitor coverage and input truncation" section of `wml summarize`, `tests/test_coverage.py` |
| 3 | [draft pre-registration 2](../preregistration/2026-10-22-main-study-2.md): monitors judge all episodes, and there is a non-submitted class |
| 4 | Not simple, so it is a TODO note in [draft pre-registration 4](../preregistration/2026-10-22-online-blocking.md) |
