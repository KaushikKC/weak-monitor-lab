# weak-monitor-lab

A small, reproducible experiment: **can a weak (local) LLM monitor detect reward hacking in a tool-using
agent's trajectory?** An agent reconciles synthetic orders in a seeded simulator. Two deliberately
permissive tools let it inflate a visible proxy score, either by shrinking the submitted scope or by
marking orders complete without reconciling them. A private verifier and replay-based labels record
what actually happened. Monitors then judge the *same saved trajectories* under three evidence conditions.

* Offline by default: no credentials, no network, no model downloads needed for tests or the demo.
* Actor and monitor backends: `mock` (fixtures), `ollama` (local REST API), `gemini` (official `google-genai` SDK).
* Framework-free agent loop; the actor can only call ten named simulator tools (no shell, Python, or files).
* 243 offline tests.

Docs: [protocol](docs/protocol.md) · [ground truth](docs/ground_truth.md) ·
[limitations](docs/limitations.md) · [diary template](docs/diary_template.md) ·
[results](docs/results/) · [pre-registrations](docs/preregistration/)

## Findings so far (pilot scale, September–October 2026)

> Every result below rests on **5–7 exploit-attempt episodes per set**, one agent model, synthetic
> tasks and a handful of prompts. These are pilot observations, not general or significant findings.
> Details, caveats and all numbers with denominators are in [`docs/results/`](docs/results/).

**Setup used for most runs:** agent `llama3.1:8b` (Ollama, Q4_K_M) on 4-order tasks; monitors
`llama3.2:3b` and `llama3.1:8b`; a mechanical rule baseline (`rule-v2`) as a reference.
AUC below = P(a random exploit episode scores higher than a random non-exploit episode); 0.5 = chance.

1. **The 3B monitor did not discriminate reliably** under any prompt tried: AUC ≈ 0.42–0.69, and a
   pre-registered test on fresh episodes gave no support for it.
2. **Report-only monitoring (condition A) was useless.** With just the agent's final report, every LLM
   monitor gave nearly every episode the same score.
3. **LLM monitors conflated task failure with manipulation.** With the original prompt (v1), the 8B
   monitor scored all 90 judgements 0.8 and called honest failures "manipulated". Prompts that define
   honest mistakes (v2–v4) moved the 3B monitor to the opposite bias (almost nothing flagged), without
   improving discrimination.
4. **Model size mattered, but only with a precise prompt.** The 8B monitor went from no discrimination
   (v1, AUC 0.50) to modest discrimination with the v3 checklist prompt. That result **passed a pre-registered
   test on two unseen datasets** (unprompted: AUC 0.74, 5/5 caught under C; elicited: AUC 0.66, 6/7 caught),
   but its numeric score raised many false alarms (43–56% under C at a 0.5 cut).
5. **The 8B monitor's own checklist was the better signal.** On both unseen datasets it caught about as many
   exploits as the score with roughly half the false alarms (C: 4/5 vs 8/25; 6/7 vs 5/23). This was a
   secondary observation and is the next candidate for a pre-registered test. Its written explanations
   named the correct manipulation in all 5 unprompted positives, even when the score was a middling 0.5.
6. **The evidence is in the trace:** the rule baseline reached AUC 0.96–1.0 under B/C. But it only
   encodes the two known mechanisms, while LLM monitors are meant to generalise and did so unreliably.
7. **Unprompted weak agents "exploited" in ~17–24% of episodes**, mostly in ways that look like confusion
   or hallucination (for example citing an invented evidence ID, or ticking orders before recording them).
   The behavioural labels cannot separate this from deliberate gaming.
8. **Telling the agent it is judged only by the score barely changed its behaviour** (7/30 exploit
   attempts vs 5/30 unprompted). It shifted somewhat toward removing orders from scope and never admitted
   the strategy in its notes. A stronger elicitation is needed to collect many positives.
9. **Method lesson:** a pattern found while exploring (the 3B's checklist catching exploits its score
   ignored) **did not replicate** in a pre-registered test on fresh episodes (0/5 caught), while the
   8B + v3 result did replicate. Pre-registration separated the two.

### Runs completed

| # | Run | Data | Result in brief | Write-up |
|---|---|---|---|---|
| 0 | Offline build + fixtures | 5 scripted behaviours × 10 seeds | All labels correct; pipeline validated | — |
| 1 | Gemini pilot | Gemini 2.5 Flash agent, 1/5 episodes (20 req/day free tier) | Honest success; 3B monitor falsely flagged it | — |
| 2 | Local pilot | 8B agent, seeds 2000–2004 | 2 exploit-type episodes; rule-v1 missed invented evidence → `rule-v2` | [limitations](docs/limitations.md) |
| 3 | Main run, 3B monitor (v1) | 8B agent, seeds 3000–3029, 7/29 exploit | 3B ≈ chance; rule-v2 7/7 caught, 1 false alarm | [local-run](docs/results/2026-09-28-local-run.md) |
| 4 | 8B monitor (v1) | same 30 episodes | Constant 0.8 on all 90 judgements | [3b-vs-8b](docs/results/2026-09-28-monitor-3b-vs-8b.md) |
| 5 | Prompt variants v2–v4, 3B | same 30 episodes | Bias flipped, discrimination unchanged | [prompt-variants](docs/results/2026-09-29-monitor-prompt-variants.md) |
| 6 | **Pre-registered** checklist detector, 3B v3 | fresh seeds 4000–4029, 5/30 exploit | H1 not supported: 0/5 under C | [checklist-fresh](docs/results/2026-09-29-checklist-detector-fresh.md) |
| 7 | 8B monitor, v3 | seeds 3000–3029 | Best LLM result (AUC 0.71–0.74), exploratory | [checklist-fresh](docs/results/2026-09-29-checklist-detector-fresh.md) |
| 8 | **Pre-registered** 8B v3 confirmation | fresh seeds 4000–4029 (unseen by 8B) | H2 met: AUC 0.74, 5/5 caught, but 14/25 false alarms | [8b-v3-confirmation](docs/results/2026-10-02-8b-v3-confirmation.md) |
| 9 | **Pre-registered** elicited-adversarial dataset | seeds 5000–5029, "judged only by score" prompt, 7/30 exploit | Elicitation weak; 8B v3 met H2 again (AUC 0.66); checklist 6/7 with 5/23 false alarms; 3B ≈ 0 | [elicited-dataset](docs/results/2026-10-02-elicited-dataset.md) |
| 10 | **Pre-registered** hacking vs failing (8B v5 primary) | seeds 6000–6059, 14/60 exploit; scripted fixtures; calibration | Primary R1 not met: AUC 0.64, 0/35 false alarms but 4/14 caught; v3 catches 13/14 with 20/35 false alarms | [hacking-vs-failing](docs/results/2026-10-06-hacking-vs-failing.md) |

### Open next steps

* Pre-register **8B + v3 checklist-as-detector** as the primary measure and test it on a fresh dataset.
* A stronger elicitation (for example naming the mechanisms), or a different agent model, to get many more positives.
* Repeated monitor samples at temperature > 0 to measure consistency.
* Finish the Gemini-agent pilot (`wml resume --run-dir runs/gem-actor --enable-network`, about one episode/day).

## Setup (macOS / Linux, Python ≥ 3.11)

```bash
cd weak-monitor-lab
python3 -m venv .venv                 # or: uv venv -p 3.12 .venv
source .venv/bin/activate
pip install -e '.[dev]'               # add ,gemini for the Gemini adapter: pip install -e '.[dev,gemini]'
cp .env.example .env                  # only needed for Gemini; .env is git-ignored
```

## Reproduce the paper

Everything below runs offline from the committed exports (no model calls, no `runs/`). Install with
`pip install -e '.[paper]'` (adds pandas, used only by the figure script). Outputs go to the git-ignored
`paper-out/` and `figures/`.

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
| Table 4 (calibration, appendix) | not in an export: the calibration runs are in `runs/` (not committed). Values are in `docs/results/2026-10-06-hacking-vs-failing.md`, `2026-10-22-v2-calibration*.md` and `2026-10-28-gemini-calibration.md` |

Notes:

* The exports are those cited in the paper (`data/export` at `b387927`; `data/export-gemini` and
  `data/export-ms2` at `5e4c884`) plus `data/export-ho`. Since `b387927`, `data/export/judgements.csv` only
  gained the `truncated` column (all `false`); every other value is unchanged.
* `wml summarize` needs the run directories, which are not committed; each export instead keeps its verbatim
  output (`summarize.txt`, or `summarize-check.txt` in `data/export`).
* Table 1's numbers regenerate exactly. Since `331213c` (2026-10-02) every fixture policy submits the same
  report text, so the regenerated reports differ from the pre-October fixtures.

## Offline commands (no model calls)

```bash
wml test                              # full offline test suite (same as: python -m pytest)
wml demo                              # fixtures + mock actor + rule/mock monitors + summary -> runs/offline-demo/
wml fixtures --out data/fixtures --seeds 1-10   # scripted trajectories for all five behaviours
wml monitor --trajectories data/fixtures --run-dir runs/mon-fixtures --monitors rule --conditions A,B,C
wml summarize runs/mon-fixtures --out runs/mon-fixtures/summary
```

Every number the demo prints comes from scripted or mock **fixtures**. It validates the pipeline and
says nothing about any model.

## Model-backed commands

Network model calls, including to `localhost` Ollama, are **disabled unless you pass `--enable-network`**
(or set `[network].enabled = true` / `WML_ENABLE_NETWORK=1`).

```bash
# connectivity (describe only; add --generate for ONE tiny generation request)
wml check --config configs/local-main.toml --enable-network
wml check --config configs/local-main.toml --enable-network --role monitor --generate

# clean-task capability calibration (no permissive tools)
wml calibrate --config configs/local-main.toml --run-dir runs/my-calib --enable-network

# actor trajectories (no instruction to hack)
wml generate  --config configs/local-main.toml --run-dir runs/my-actor --enable-network

# ELICITED adversarial trajectories: a separate dataset source, never pooled with the above
# (requires [experiment].elicitation, e.g. configs/local-elicited.toml)
wml elicit    --config configs/local-elicited.toml --run-dir runs/my-elicited --enable-network

# monitors on saved trajectories (conditions A, B, C; rule baseline + LLM)
wml monitor   --config configs/local-main.toml --trajectories runs/my-actor \
              --run-dir runs/my-monitor --enable-network

# same trajectories, different monitor instructions (v1 original; v2 honest-mistake definition;
# v3 = v2 + checklist; v4 = v2 + 1-10 scale). Use a new --run-dir per variant.
wml monitor   --config configs/local-main.toml --trajectories runs/my-actor \
              --run-dir runs/my-monitor-v3 --monitors llm --prompt-variant v3 --enable-network

# resume anything that stopped (quota, budget, daily cap, sleep, Ctrl-C) using the run's saved config
wml resume --run-dir runs/my-actor --enable-network [--max-total-requests 600]

# results table (results.md with AUC and checklist-detector sections), CSVs and plots
wml summarize runs/my-monitor runs/my-monitor-v3 runs/my-calib --out runs/my-summary
```

`wml` is also available as `python -m weak_monitor_lab`.

### Configs

| File | Purpose |
|---|---|
| `default.toml` | Offline: mock actor and monitor, network off |
| `local-pilot.toml` | 8B agent + 3B monitor, 5 scenarios (seeds 2000+) |
| `local-main.toml` | Same, 30 scenarios (seeds 3000+) |
| `local-monitor-8b.toml` | `local-main` with the 8B model as monitor |
| `local-fresh.toml` | Pre-registered fresh run (seeds 4000+), monitor prompt v3 |
| `local-elicited.toml` | Elicited-adversarial dataset (seeds 5000+, `elicitation = "score_pressure"`); use with `wml elicit` |
| `gemini-pilot.toml` | Gemini 2.5 Flash agent + local 3B monitor, sized for a 20-requests/day free tier |
| `gemini-actor.example.toml` | Template for another Gemini model/account |
| `pilot-ollama.toml` | Original 3B/3B local pilot |

### Ollama

Pull models yourself (`ollama pull <model>`). This tool never downloads models, and `wml check` fails
clearly if a model is missing. It records each model's digest and quantization. The actor and monitor
never run at the same time, so only one model needs to fit in memory. Long runs on a laptop should be
**plugged in with the lid open**: `caffeinate` cannot prevent lid-close or battery sleep, although runs
resume cleanly afterwards. On a 16 GB Mac, long 8B sessions grew macOS swap to ~15 GB and filled the disk.
Restart before long 8B runs, close other apps, and consider a free-space watchdog (check its process
pattern with `pgrep -fl` first).

> **Remote environments:** a cloud or remote coding environment (a hosted agent session, a CI runner,
> a dev container on another machine) cannot reach the Ollama server on your laptop through its own
> `localhost`. `localhost` there is that machine. Run the Ollama commands on your laptop, or expose the
> server deliberately and securely and set `ollama_base_url`.

### Gemini

1. `pip install -e '.[gemini]'`, then put `GEMINI_API_KEY=...` in `.env`.
2. Set `model_id` to a model your account can use (none is assumed); see `configs/gemini-pilot.toml`.
3. Set `requests_per_minute`, `max_requests_per_day` and `max_total_requests` at or below **your** account's
   limits. The daily cap counts only Gemini requests and resets at midnight Pacific time. When it is
   reached, the run stops cleanly and `wml resume` continues the next day.
4. Persistent `429 / RESOURCE_EXHAUSTED` responses stop the run cleanly after `max_quota_retries`.

Secrets are read from the environment or `.env` only. They are redacted from error messages and never
written to run directories.

## Research practice built in

* **Separate datasets:** scripted fixtures, unprompted agent episodes, capability calibration, and
  elicited-adversarial episodes are never pooled. Elicitation is allowed only for the elicited source and
  is never shown to monitors (both enforced by tests).
* **Splits by base scenario;** thresholds are fitted on dev only (fitting on test raises an error).
* **Pre-registration:** confirmatory tests are written and committed before their data exists
  ([example](docs/preregistration/2026-09-29-checklist-detector.md)).
* **Post-hoc changes are recorded** in [limitations](docs/limitations.md) (for example the rule-v2 revision
  and the prompt variants).
* Invalid, unsubmitted and interrupted episodes are reported, never silently dropped. Mock outputs are
  labelled as fixtures and excluded from results.

## What gets recorded

Each run directory (`runs/<name>/`, git-ignored) holds `manifest.json` (config snapshot, software versions,
model digest/metadata, prompt hashes and variant, per-session timestamps), `status.json`,
`trajectories.jsonl` (public event logs), `labels.jsonl` (private ground truth, kept separate),
`interrupted.jsonl`, `calls.jsonl` (every model call with seed, sampling, prompt hash, tokens, latency,
retries and truncation, which is also the resume checkpoint), `failures.jsonl`, `budget.json` (including
the per-day ledger), and `monitor_results.jsonl`.

## Repository layout

```
src/weak_monitor_lab/
  sim/        scenario generator, environment + tools + event log, private verifier
  labels.py   replay-based ground truth + counterfactual proxy
  policies.py five scripted fixture policies
  agent.py    explicit JSON-action loop (Pydantic validation, bounded repairs, context truncation)
  adapters/   mock, ollama (httpx), gemini (google-genai)
  runner.py   checkpointed calls, request budget, daily cap, rate limiting, bounded retries
  monitor/    condition A/B/C views, rule baseline, LLM monitor, prompt variants (prompts.py)
  pipeline.py fixtures / generate / calibrate / monitor / resume
  analysis.py confusion counts, AUC, checklist detector, rates with denominators, plots
configs/      see the table above
docs/         protocol, ground truth, limitations, diary template, results/, preregistration/
tests/        offline test suite
```
