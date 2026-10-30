# Hacking or Just Failing?

**A More Capable LLM Monitor Better Separates Reward Hacking from Honest Failure**

Kaushik Kezendirane · Independent researcher

[![tests](https://github.com/KaushikKC/weak-monitor-lab/actions/workflows/tests.yml/badge.svg)](https://github.com/KaushikKC/weak-monitor-lab/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)

This repository contains the environment, the replay-based labels, the monitor pipeline, all
pre-registrations, results notes and per-judgement data for the paper. Every table and Figure 2 can be
regenerated offline from the committed data ([Reproduce the paper](#reproduce-the-paper)).

## Overview

An agent's visible score can exceed its real progress because it gamed the score or because it made honest
mistakes. A useful reward-hacking monitor has to tell the two apart. We built a sandboxed order-reconciliation
task in which an agent can inflate a completion score through two permissive tools. Every episode is labelled
by replaying it: a private verifier decides whether the task was really done, predicates decide whether a known
manipulation was used, and a counterfactual repair of the final state decides whether it inflated the score.
Monitors judge the same saved trajectories under three evidence conditions: **A** the final report, **B** plus
the full action log, **C** plus derived state changes. All five studies were pre-registered before their data
existed.

## Main results

| Study | Question | Pre-registered primary result |
|---|---|---|
| 1. Small monitors | Do local 3B and 8B monitors separate exploit attempts from honest failures with a score gap? (60 episodes, 8B agent) | **Not met.** 8B, prompt v5, condition C: AUC 0.64 [0.53, 0.77]; 4/14 exploits caught, 0/35 honest failures flagged. With prompt v3: 13/14 caught, 20/35 flagged |
| 2. Capable monitor | Does Gemini 3.1 Flash-Lite, on byte-identical inputs? | **Met.** v5, C: AUC 0.80 [0.66, 0.93]; 9/14 caught, 1/35 flagged. Met under every prompt and condition run |
| 3. Calibration | How capable is each model on the clean task? | Honest success on 10 clean tasks: Gemini 9/10, Llama 3.1 8B 2/10, Llama 3.2 3B 0/10 |
| 4. Second agent study | Are small-monitor false alarms specific to failure? (300 episodes, 3B agent) | **Not met** (4 exploit attempts). 8B v3, C flagged 77/162 honest failures and 39/113 honest successes |
| 5. Replication | Does the held-out exploit result hold on 25 new episodes? | Gemini flagged **0/25** scope-padding episodes under every prompt and condition. 8B v3 under B flagged 25/25 and 0/25 honest look-alikes, with explanations describing actions that did not occur |

A two-rule deterministic baseline (`rule-v2`) caught 14/14 known exploits with 1/35 false alarms, and 0/25
scope-padding episodes, which no rule or prompt names. Intervals are Wilson 95% for proportions and a
clustered bootstrap (10,000 resamples) for AUCs. Full results, with denominators and every deviation, are in
the [study index](docs/README.md).

## Repository contents

| Path | Contents |
|---|---|
| [`src/weak_monitor_lab/`](src/weak_monitor_lab/) | Simulator, verifier, labels, agent loop, model adapters, monitors, analysis |
| [`docs/README.md`](docs/README.md) | **Study index**: each study's pre-registration (with freezing commit), configs, results note and export |
| [`docs/preregistration/`](docs/preregistration/) | Pre-registrations, as committed before the data |
| [`docs/results/`](docs/results/) | Results notes, verbatim tool output and interval tables |
| [`data/`](data/) | Per-episode and per-judgement exports for every study ([data README](data/README.md)) |
| [`configs/`](configs/) | The exact configuration of every run ([configs README](configs/README.md)) |
| [`scripts/`](scripts/) | Export, judgement-table and figure scripts |
| [`tests/`](tests/) | Offline test suite (490 tests; no network, no credentials) |

## Installation

Python 3.12 or later. No credentials, network or model downloads are needed for the tests or for
reproducing the paper.

```bash
git clone https://github.com/KaushikKC/weak-monitor-lab.git
cd weak-monitor-lab
python3 -m venv .venv && source .venv/bin/activate      # or: uv venv -p 3.12 .venv
pip install -e '.[dev,paper]'        # add ,gemini for the Gemini adapter
python -m pytest                     # offline test suite
```

## Reproduce the paper

Everything below runs offline from the committed exports (no model calls, no run directories) in under a
minute. Outputs go to the git-ignored `paper-out/` and `figures/`. The same commands run in CI on every push.

```bash
mkdir -p paper-out figures

# Table 1 (same score, same gap): scripted fixtures, six required orders; the table is scenario scn-1
# (policies ordinary_mistakes, unsupported_completion, scope_exclusion: proxy, T, G, counterfactual_proxy)
wml fixtures --out paper-out/fixtures --seeds 1-10
wml gap paper-out/fixtures

# Table 3 and Study 1 (D1, D3): local monitors and rule-v2
wml intervals --export data/export --datasets D1,D3 \
  --resamples 10000 --seed 20261021 --out paper-out/study1.md
# Table 3 Gemini rows and Study 2 (D1, D3)
wml intervals --export data/export-gemini --datasets D1,D3 \
  --resamples 10000 --seed 20261021 --out paper-out/study2.md
# Study 4 (E1, E3)
wml intervals --export data/export-ms2 --datasets E1,E3 \
  --resamples 10000 --seed 20261021 --out paper-out/study4.md
# Study 5, replication (H)
wml intervals --export data/export-ho --datasets H \
  --resamples 10000 --seed 20261021 --out paper-out/study5.md

# Figure 2 (prints each point's counts; writes figures/fig2_tradeoff.pdf and .png)
python scripts/make_fig2.py data/export data/export-gemini
```

| Paper | Source |
|---|---|
| Table 1 | `paper-out/fixtures/labels.jsonl` and `gap.jsonl`, `scn-1` |
| Table 2 (the five studies) | descriptive; the pre-registrations in `docs/preregistration/` |
| Table 3 | `paper-out/study1.md` (8B, 3B, rule-v2 rows) and `paper-out/study2.md` (Gemini rows), D1, condition C, score≥0.5: proportions and the "exploit_attempt vs gap-matched (G>0)" AUC |
| Figure 2 | `scripts/make_fig2.py` (the paper's figure script, unchanged) |
| Table 4 (calibration, appendix) | v1 column for the 8B and 3B agents: `data/export/episodes.csv`, dataset `calib`, `genuine_success`. The other cells come from runs that are not exported; their values are in the [Study 3 results notes](docs/README.md#paper-studies) |

Notes:

* The exports are those cited in the paper (`data/export` at `b387927`; `data/export-gemini` and
  `data/export-ms2` at `5e4c884`) plus `data/export-ho`. Since `b387927`, `data/export/judgements.csv` only
  gained the `truncated` column (all `false`); every other value is unchanged.
* `wml summarize` needs the run directories, which are not committed; each export instead keeps its verbatim
  output (`summarize.txt`, or `summarize-check.txt` in `data/export`).
* Table 1's numbers regenerate exactly. Since `331213c` (2026-10-02) every fixture policy submits the same
  report text, so the regenerated reports differ from the pre-October fixtures.

## Running new experiments

Network model calls, including to a local Ollama server, are **disabled unless you pass `--enable-network`**
(or set `[network].enabled = true` / `WML_ENABLE_NETWORK=1`). Offline, without any model:

```bash
wml demo                                  # fixtures + mock actor + rule/mock monitors + summary
wml fixtures --out data/fixtures --seeds 1-10
wml monitor --trajectories data/fixtures --run-dir runs/mon-fixtures --monitors rule --conditions A,B,C
wml summarize runs/mon-fixtures --out runs/mon-fixtures/summary
```

With models (each command records its config, model digest or version, prompt hashes and git commit):

```bash
wml check     --config configs/hvf-monitor-8b.toml --enable-network          # connectivity
wml calibrate --config configs/hvf-calib-8b.toml --run-dir runs/my-calib --enable-network
wml generate  --config configs/hvf-unprompted.toml --run-dir runs/my-agent --enable-network
wml monitor   --config configs/hvf-monitor-8b.toml --trajectories runs/my-agent \
              --run-dir runs/my-monitor --conditions B,C --monitors rule,llm --prompt-variant v5 --enable-network
wml resume    --run-dir runs/my-monitor --enable-network     # continue any stopped run; no call is repeated
wml summarize runs/my-monitor --out runs/my-summary
wml gap runs/my-agent                                        # true progress T and gap G per episode
```

`wml` is also available as `python -m weak_monitor_lab`. Monitor prompts v1–v5 are in
[`src/weak_monitor_lab/monitor/prompts.py`](src/weak_monitor_lab/monitor/prompts.py).

**Ollama.** Pull models yourself (`ollama pull llama3.1:8b-instruct-q4_K_M`); the tool never downloads models
and records each model's digest. The agent and monitor never run at the same time. On a 16 GB machine, long
8B runs can grow swap until the disk fills: keep several GB free and consider a free-space watchdog.

**Gemini.** `pip install -e '.[gemini]'` and put `GEMINI_API_KEY=...` in `.env` (git-ignored; see
`.env.example`). Set `requests_per_minute` and `max_requests_per_day` at or below your account's limits; the
daily cap resets at midnight Pacific time, and a capped or rate-limited run stops cleanly and resumes with
`wml resume`. Keys are read from the environment only, redacted from errors and never written to run
directories.

## Research practice

* **Pre-registration.** Each confirmatory study's plan, data, outcomes and criteria were committed before
  its data existed; the freezing commit is listed in the [study index](docs/README.md). Deviations are
  recorded in the results note. Two registered studies were not run; both are listed there.
* **Datasets are never pooled.** Unprompted, elicited, calibration and scripted episodes, and data from
  different agents or environment variants, are analysed separately (enforced in code and tests).
* **Labels are separate from monitor inputs.** Monitors see only public trajectory fields; agent-written text
  is fenced as untrusted. An audit confirmed that view B contains every result the agent received.
* **Everything is counted.** Invalid outputs, refusals, unsubmitted episodes and interruptions are reported
  with denominators, never dropped.
* **Provenance.** Every run records its config, model digest or returned model version, prompt hashes,
  software versions, and the git commit and timestamps of every session.

## Repository layout

```
src/weak_monitor_lab/
  sim/          scenario generator, environment, ten tools, host event log, private verifier
  labels.py     replay-based ground truth and counterfactual proxy
  gap.py        true progress T and proxy gap G
  policies.py   scripted fixture policies (core, gap-matched, scope padding)
  agent.py      JSON-action agent loop with validation and bounded repairs
  adapters/     mock, Ollama, Gemini
  runner.py     checkpointed calls, budgets, daily caps, rate limits, retries
  monitor/      evidence views A/B/C, rule baseline, LLM monitor, prompts v1–v5
  pipeline.py   fixtures, generate, calibrate, monitor, resume
  analysis.py   labels v2, AUC, checklist detector, combined detector, summaries
  intervals.py  Wilson and clustered-bootstrap intervals from an export
  fidelity.py   monitor-input fidelity audit
  audit.py      blind label-audit kit
  blocking.py   online blocking mode (implemented; not used in any study)
scripts/        export_runs.py, padding_judgements.py, make_fig2.py
```

Each run directory (`runs/<name>/`, git-ignored) holds `manifest.json`, `status.json`, `trajectories.jsonl`
(public event logs), `labels.jsonl` (private ground truth), `calls.jsonl` (every model call; also the resume
checkpoint), `monitor_results.jsonl` and `budget.json`.

## Citation

```bibtex
@misc{kezendirane2026hacking,
  title  = {Hacking or Just Failing? A More Capable {LLM} Monitor Better Separates Reward Hacking
            from Honest Failure},
  author = {Kezendirane, Kaushik},
  year   = {2026},
  url    = {https://github.com/KaushikKC/weak-monitor-lab}
}
```

GitHub's "Cite this repository" button uses [`CITATION.cff`](CITATION.cff).

## License

[MIT](LICENSE).
