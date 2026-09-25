# weak-monitor-lab

A small, reproducible experiment: **can a weak (local) LLM monitor detect reward hacking in a tool-using
agent's trajectory?** An agent reconciles synthetic orders in a seeded simulator. Two deliberately
permissive tools let it inflate a visible proxy score, either by shrinking the submitted scope or by
marking orders complete without reconciling them. A private verifier and replay-based labels record
what actually happened. Monitors then judge the *same saved trajectories* under three evidence conditions.

* Offline by default: no credentials, no network, no model downloads needed for tests or the demo.
* Actor and monitor backends: `mock` (fixtures), `ollama` (local REST API), `gemini` (official `google-genai` SDK).
* Framework-free agent loop; the actor can only call ten named simulator tools (no shell, Python, or files).

Docs: [protocol](docs/protocol.md) · [ground truth](docs/ground_truth.md) ·
[limitations](docs/limitations.md) · [diary template](docs/diary_template.md)

## Setup (macOS / Linux, Python ≥ 3.11)

```bash
cd weak-monitor-lab
python3 -m venv .venv                 # or: uv venv -p 3.12 .venv
source .venv/bin/activate
pip install -e '.[dev]'               # add ,gemini for the Gemini adapter: pip install -e '.[dev,gemini]'
cp .env.example .env                  # only needed for Gemini; .env is git-ignored
```

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
wml check --config configs/pilot-ollama.toml --enable-network
wml check --config configs/pilot-ollama.toml --enable-network --role monitor --generate

# clean-task capability calibration (no permissive tools)
wml calibrate --config configs/pilot-ollama.toml --run-dir runs/pilot-calib --enable-network

# actor trajectories (no instruction to hack)
wml generate  --config configs/pilot-ollama.toml --run-dir runs/pilot-actor --enable-network

# monitors on saved trajectories (conditions A, B, C; rule baseline + LLM)
wml monitor   --config configs/pilot-ollama.toml --trajectories runs/pilot-actor \
              --run-dir runs/pilot-monitor --enable-network

# resume anything that stopped (quota, budget, Ctrl-C) using the run's saved config
wml resume --run-dir runs/pilot-actor --enable-network [--max-total-requests 600]

# results table (results.md), CSVs and plots
wml summarize runs/pilot-monitor runs/pilot-calib --out runs/pilot-summary
```

`wml` is also available as `python -m weak_monitor_lab`.

### Ollama

Pull models yourself (`ollama pull <model>`). This tool never downloads models, and `wml check` fails
clearly if a model is missing. It records each model's digest and quantization.

> **Remote environments:** a cloud or remote coding environment (a hosted agent session, a CI runner,
> a dev container on another machine) cannot reach the Ollama server on your laptop through its own
> `localhost`. `localhost` there is that machine. Run the Ollama commands on your laptop, or expose the
> server deliberately and securely and set `ollama_base_url`.

### Gemini

1. `pip install -e '.[gemini]'`, then put `GEMINI_API_KEY=...` in `.env`.
2. Copy `configs/gemini-actor.example.toml` and set `model_id` to a model your account can use. None is assumed.
3. Set `requests_per_minute` and `max_total_requests` at or below **your** account's limits.
4. Persistent `429 / RESOURCE_EXHAUSTED` responses stop the run cleanly after `max_quota_retries`. Progress
   is checkpointed, so resume later with `wml resume`.

Secrets are read from the environment or `.env` only. They are redacted from error messages and never
written to run directories.

## What gets recorded

Each run directory (`runs/<name>/`) holds `manifest.json` (config snapshot, software versions, model
digest/metadata, prompt hashes, per-session timestamps), `status.json`, `trajectories.jsonl` (public
event logs), `labels.jsonl` (private ground truth, kept separate), `interrupted.jsonl`, `calls.jsonl`
(every model call with seed, sampling, prompt hash, tokens, latency, retries and truncation, which is
also the resume checkpoint), `failures.jsonl`, `budget.json`, and `monitor_results.jsonl`.

## Repository layout

```
src/weak_monitor_lab/
  sim/        scenario generator, environment + tools + event log, private verifier
  labels.py   replay-based ground truth + counterfactual proxy
  policies.py five scripted fixture policies
  agent.py    explicit JSON-action loop (Pydantic validation, bounded repairs, context truncation)
  adapters/   mock, ollama (httpx), gemini (google-genai)
  runner.py   checkpointed calls, request budget, rate limiting, bounded retries
  monitor/    condition A/B/C views, rule baseline, LLM monitor
  pipeline.py fixtures / generate / calibrate / monitor / resume
  analysis.py confusion counts, rates with denominators, plots
configs/      default (offline), pilot-ollama, gemini-actor.example
docs/         protocol, ground truth, limitations, diary template
tests/        offline test suite
```
