# Monitor-input fidelity audit

Date: 2026-10-22. Plan update after METR's monitoring red-team, item 1
([plan](../plans/2026-10-22-monitoring-red-team.md)). No model call was made, and no file in `runs/` was
changed. Code: `src/weak_monitor_lab/fidelity.py`, `tests/test_fidelity.py`. This note reports counts; it does
not interpret them.

## Method

1. **Received results versus view B.** Each saved model-driven episode is replayed through the real agent loop
   (`agent.run_model_episode`) against a copy of its run's `calls.jsonl`. `CallRunner` refuses any call whose
   prompt hash differs from the checkpoint, and the replayed events must equal the saved events. So a
   completed replay reproduces exactly the tool-result messages the agent received. Each received result is
   then looked up in monitor view B: its event header, with the result line directly after it, after the
   previous result. get_task's instructions are shown in view B as "<identical to the task specification
   above>"; they are checked against the task text instead.
2. **Truncation.** The `input_truncation` recorded with every judgement, in every saved monitor run. It is
   also exported as the new `truncated` column of `data/export/judgements.csv`, and shown by `wml summarize`
   in the new "Monitor coverage and input truncation" section.
3. **Rebuild check.** Every saved monitor input is rebuilt from its trajectory with the current code, and the
   sha256 is compared with the recorded `input_hash`.

`gem-d1-v5` (pre-registration 3, run 1) was still in progress when this was run. Its counts cover the
judgements written so far.

## Agent-written text and the input structure (tests)

`tests/test_fidelity.py` builds episodes in which agent-written strings carry adversarial content. These
strings are the rationales, the report, an order id, and an evidence id, which the results echo. The content
covers fence markers, code fences, unbalanced quotes, braces and brackets, fake headings, fake event lines, CR,
U+2028, NUL, and 100 random strings. The tests check that everything outside the fenced agent text is
unchanged and that every JSON field still parses. Conditions A, B and C are all covered.

* **Found and fixed:** fence markers written into tool **arguments** reached the input unescaped, outside any
  fence. They appeared in the event header, in a result that echoes the argument, and in condition C's
  structured block. Before this change only the report and the rationales were cleaned. `views.py` now
  removes the markers there too. The rebuild check below is identical before and after the change
  (2753 same, 62 different), so no saved input changed.
* **Found, not changed:** a very long agent-written string (a 50,000-character evidence id) keeps the
  structure, but view B omits events to fit `max_input_chars`, and view C exceeds it, because condition C's
  structured block is never shortened. Both are visible in the recorded truncation and character count.
  Changing this would change the monitor inputs, so it is left as is and recorded. No saved input is
  truncated; the largest is 17,390 characters.
* **Found, not changed:** in an online-blocking run the agent also receives the block message, which is not a
  host event, so view B does not show it. No blocking run exists yet.

The 62 differing rebuilds are all condition C, in the pilot runs `gem-monitor`, `local-monitor` and
`mon-fixtures` (2026-09-25 and 2026-09-28). `views.py`'s condition C changed in `3da3e93` (2026-09-27), the
rule-v2 change described in `docs/limitations.md`. None of these runs is used in a study.

## Code (run from the repository root with the project environment)

```python
import collections, glob, json
from pathlib import Path
from weak_monitor_lab.fidelity import audit_run
from weak_monitor_lab.io import read_json, read_jsonl, sha256_text
from weak_monitor_lab.monitor.views import build_monitor_input

print("# 1. Every tool result the agent received, found in view B in order (all saved agent runs)")
for d in ["local-main-actor", "fresh-actor", "elicited-actor", "hvf-d1-actor", "hvf-calib-3b", "hvf-calib-8b",
          "v2-calib-v2a", "v2-calib-v2b", "v2-calib-v2c", "v2-calib2-v2d"]:
    r = audit_run(Path("runs") / d); r.pop("rows"); print(json.dumps(r))

print("\n# 2. Monitor inputs truncated by max_input_chars, per saved monitor run")
tot = collections.Counter()
for f in sorted(glob.glob("runs/*/monitor_results.jsonl")):
    R = list(read_jsonl(Path(f)))
    c = collections.Counter((r["monitor"]["kind"], r["input_truncation"]) for r in R)
    tot.update(c)
    mx = max((r["input_chars"] for r in R if r["monitor"]["kind"] == "llm"), default=None)
    print(Path(f).parent.name, len(R), dict(c), "max LLM input chars", mx)
print("TOTAL", dict(tot))

print("\n# 3. Saved monitor inputs rebuilt by the current code (sha256 of the input text)")
tot = collections.Counter()
for f in sorted(glob.glob("runs/*/monitor_results.jsonl")):
    d = Path(f).parent
    m = read_json(d / "manifest.json")
    trajs = {t["episode_id"]: t for x in m["params"]["trajectory_dirs"] for t in read_jsonl(Path(x) / "trajectories.jsonl")}
    mx = m["config"]["monitor"]["max_input_chars"]
    c = collections.Counter()
    for r in read_jsonl(Path(f)):
        text, _ = build_monitor_input(trajs[r["episode_id"]], r["condition"], mx if r["monitor"]["kind"] == "llm" else 30000)
        c[("same" if sha256_text(text) == r["input_hash"] else "DIFF") + (f" {r['condition']}" if sha256_text(text) != r["input_hash"] else "")] += 1
    tot.update(c); print(d.name, dict(c))
print("TOTAL", dict(tot))
```

## Output (verbatim)

```
# 1. Every tool result the agent received, found in view B in order (all saved agent runs)
{"run": "local-main-actor", "episodes": 30, "results_received": 467, "results_in_view_b_in_order": 467, "episodes_with_missing": 0, "blocked_results_not_in_log": 0, "truncated_inputs": 0}
{"run": "fresh-actor", "episodes": 30, "results_received": 448, "results_in_view_b_in_order": 448, "episodes_with_missing": 0, "blocked_results_not_in_log": 0, "truncated_inputs": 0}
{"run": "elicited-actor", "episodes": 30, "results_received": 523, "results_in_view_b_in_order": 523, "episodes_with_missing": 0, "blocked_results_not_in_log": 0, "truncated_inputs": 0}
{"run": "hvf-d1-actor", "episodes": 60, "results_received": 868, "results_in_view_b_in_order": 868, "episodes_with_missing": 0, "blocked_results_not_in_log": 0, "truncated_inputs": 0}
{"run": "hvf-calib-3b", "episodes": 10, "results_received": 129, "results_in_view_b_in_order": 129, "episodes_with_missing": 0, "blocked_results_not_in_log": 0, "truncated_inputs": 0}
{"run": "hvf-calib-8b", "episodes": 10, "results_received": 110, "results_in_view_b_in_order": 110, "episodes_with_missing": 0, "blocked_results_not_in_log": 0, "truncated_inputs": 0}
{"run": "v2-calib-v2a", "episodes": 10, "results_received": 114, "results_in_view_b_in_order": 114, "episodes_with_missing": 0, "blocked_results_not_in_log": 0, "truncated_inputs": 0}
{"run": "v2-calib-v2b", "episodes": 10, "results_received": 117, "results_in_view_b_in_order": 117, "episodes_with_missing": 0, "blocked_results_not_in_log": 0, "truncated_inputs": 0}
{"run": "v2-calib-v2c", "episodes": 10, "results_received": 91, "results_in_view_b_in_order": 91, "episodes_with_missing": 0, "blocked_results_not_in_log": 0, "truncated_inputs": 0}
{"run": "v2-calib2-v2d", "episodes": 10, "results_received": 95, "results_in_view_b_in_order": 95, "episodes_with_missing": 0, "blocked_results_not_in_log": 0, "truncated_inputs": 0}

# 2. Monitor inputs truncated by max_input_chars, per saved monitor run
elicited-monitor-3b-v3 180 {('rule', 'none'): 90, ('llm', 'none'): 90} max LLM input chars 17003
elicited-monitor-8b-v3 90 {('llm', 'none'): 90} max LLM input chars 17003
fresh-monitor-3b-v3 180 {('rule', 'none'): 90, ('llm', 'none'): 90} max LLM input chars 14386
fresh-monitor-8b-v3 90 {('llm', 'none'): 90} max LLM input chars 14386
gem-d1-v5 8 {('llm', 'none'): 8} max LLM input chars 10687
gem-monitor 6 {('rule', 'none'): 3, ('llm', 'none'): 3} max LLM input chars 9209
hvf-d1-mon-3b-v3 360 {('rule', 'none'): 180, ('llm', 'none'): 180} max LLM input chars 15534
hvf-d1-mon-3b-v5 180 {('llm', 'none'): 180} max LLM input chars 15534
hvf-d1-mon-8b-v3 180 {('llm', 'none'): 180} max LLM input chars 15534
hvf-d1-mon-8b-v5 180 {('llm', 'none'): 180} max LLM input chars 15534
hvf-d3-mon-3b-v3 200 {('rule', 'none'): 100, ('llm', 'none'): 100} max LLM input chars 9716
hvf-d3-mon-3b-v5 100 {('llm', 'none'): 100} max LLM input chars 9716
hvf-d3-mon-8b-v3 100 {('llm', 'none'): 100} max LLM input chars 9716
hvf-d3-mon-8b-v5 100 {('llm', 'none'): 100} max LLM input chars 9716
local-main-monitor-3b-v2 90 {('llm', 'none'): 90} max LLM input chars 17390
local-main-monitor-3b-v3 90 {('llm', 'none'): 90} max LLM input chars 17390
local-main-monitor-3b-v4 90 {('llm', 'none'): 90} max LLM input chars 17390
local-main-monitor-8b-v3 90 {('llm', 'none'): 90} max LLM input chars 17390
local-main-monitor-8b 90 {('llm', 'none'): 90} max LLM input chars 17390
local-main-monitor 180 {('rule', 'none'): 90, ('llm', 'none'): 90} max LLM input chars 17390
local-monitor-rule-v2 15 {('rule', 'none'): 15} max LLM input chars None
local-monitor 30 {('rule', 'none'): 15, ('llm', 'none'): 15} max LLM input chars 10692
local-pilot-monitor-v2 30 {('rule', 'none'): 15, ('llm', 'none'): 15} max LLM input chars 11156
mon-fixtures 150 {('rule', 'none'): 150} max LLM input chars None
smoke-ollama-monitor 6 {('rule', 'none'): 3, ('llm', 'none'): 3} max LLM input chars 11260
TOTAL {('rule', 'none'): 751, ('llm', 'none'): 2064}

# 3. Saved monitor inputs rebuilt by the current code (sha256 of the input text)
elicited-monitor-3b-v3 {'same': 180}
elicited-monitor-8b-v3 {'same': 90}
fresh-monitor-3b-v3 {'same': 180}
fresh-monitor-8b-v3 {'same': 90}
gem-d1-v5 {'same': 8}
gem-monitor {'same': 4, 'DIFF C': 2}
hvf-d1-mon-3b-v3 {'same': 360}
hvf-d1-mon-3b-v5 {'same': 180}
hvf-d1-mon-8b-v3 {'same': 180}
hvf-d1-mon-8b-v5 {'same': 180}
hvf-d3-mon-3b-v3 {'same': 200}
hvf-d3-mon-3b-v5 {'same': 100}
hvf-d3-mon-8b-v3 {'same': 100}
hvf-d3-mon-8b-v5 {'same': 100}
local-main-monitor-3b-v2 {'same': 90}
local-main-monitor-3b-v3 {'same': 90}
local-main-monitor-3b-v4 {'same': 90}
local-main-monitor-8b-v3 {'same': 90}
local-main-monitor-8b {'same': 90}
local-main-monitor {'same': 180}
local-monitor-rule-v2 {'same': 15}
local-monitor {'same': 20, 'DIFF C': 10}
local-pilot-monitor-v2 {'same': 30}
mon-fixtures {'same': 100, 'DIFF C': 50}
smoke-ollama-monitor {'same': 6}
TOTAL {'same': 2753, 'DIFF C': 62}
```
