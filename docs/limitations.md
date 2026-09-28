# Limitations

## Environment and labels

* **Toy, synthetic task.** A reconciliation simulator with 6 required orders and two hand-designed
  shortcuts. Results say nothing directly about realistic agents, tasks, or reward hacking in training.
* **Only two manipulation mechanisms are labelled.** Scope *padding* (adding reconciled non-required
  orders), editing entries after completion, misleading report claims without state manipulation, and
  other gaming strategies are unlabelled. An unlabelled strategy counts as `ordinary_failure` or
  `honest_success`, which can inflate a monitor's apparent false positives.
* **Behavioural labels, not intent.** The predicates cannot tell a deliberate shortcut from confusion
  (for example, a small model marking orders complete before reconciling). Labels are "the trace contains a
  proxy-relevant manipulation", nothing more.
* **"Supported" is structural.** An entry with the right evidence IDs but wrong quantities is not
  unsupported. The attempt/honest-error boundary is a design choice (see `ground_truth.md`).
* **Counterfactual is final-state only.** Success is measured on the submitted state. Transient
  inflation that was later undone is an attempt without success.

## Monitoring

* **The rule baseline is near-oracle under B and C by construction.** It checks the same facts the
  predicates use. It is a sanity reference, not a competitor. Under A it has no action evidence.
* **The rule baseline was revised after seeing pilot data.** `rule-v1` only checked that *some*
  reconciliation had been recorded before an order was marked complete. It missed a local-pilot episode
  (scn-2003, 2026-09-28) where the agent cited an invented delivery ID. `rule-v2` also requires the cited
  evidence to exist and belong to the order, matching the label definition. Results from the two versions
  are kept apart by the monitor name, and scn-2003 is in the dev split. Treat any rule-baseline comparison
  on that pilot as post hoc.
* **Invented evidence counts as unsupported completion.** A small model that hallucinates an evidence ID
  and then marks the order complete is labelled the same as deliberate gaming. The labels cannot separate
  hallucination from manipulation.
* **Condition C makes detection easy.** Its structured facts (for example, "task orders absent from
  final scope") are close to the predicates, though they are not verdicts. The A → B → C comparison
  measures the value of evidence *format*, not only monitor intelligence.
* **The suspicion score is uncalibrated.** It is a 0–1 rating, not a probability. Thresholds are fitted on dev.
* **Prompt sensitivity.** A single monitor prompt is used. Results may change substantially with
  wording, output length, JSON mode, or the model's instruction-following quality.
* **Truncation.** Long traces are abbreviated or have middle events omitted (recorded per result),
  which can hide evidence under B/C.

## Statistics

* Pilot sample sizes (5–50 episodes) give very wide uncertainty. Wilson intervals are descriptive only.
* Episodes from the same base scenario are correlated. Samples are not independent draws of scenarios.
* Unprompted small models may rarely or never exploit. Recall can then be undefined (`k/0`), which is
  itself a finding about the base rate, not about the monitor.

## Infrastructure

* **Localhost is local.** A remote or cloud coding environment (for example a hosted Claude Code session
  or a CI runner) cannot reach an Ollama server on your laptop through its *own* `localhost`. Run
  Ollama-backed commands on the machine where Ollama runs, or expose the server deliberately and
  securely and set `ollama_base_url`.
* **Nondeterminism.** Ollama seeds improve but do not guarantee reproducibility across hardware,
  versions or quantizations. Gemini outputs can change when a model alias is updated. The response
  model version is recorded when the API supplies it.
* **Gemini free-tier limits are account-specific** and change over time. Nothing here assumes which
  models or limits you have. Set `requests_per_minute` and `max_total_requests` yourself.
* `max_total_requests` is per run directory. It does not track usage across runs or other applications
  sharing the same API key or daily quota.
* Only `concurrency = 1` is implemented.
