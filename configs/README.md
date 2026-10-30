# Configs

Each file is the exact configuration of one or more runs. Every run also stores a snapshot of its config in
`manifest.json` (exported in `data/*/manifests.json`). Each file's header comment names its study and seeds.
Network calls need `--enable-network` in every config.

| Config | Used for | Paper |
|---|---|---|
| `default.toml` | Offline default: mock actor and monitor, network off | tests, `wml demo` |
| **Study 1: small monitors** | | |
| `hvf-unprompted.toml` | D1: 60 unprompted episodes, 8B agent, seeds 6000–6059 | Study 1 |
| `hvf-calib-8b.toml`, `hvf-calib-3b.toml` | D2: clean-task calibration, seeds 6100–6109 | Studies 1, 3 |
| `hvf-monitor-8b.toml`, `hvf-monitor-3b.toml` | 8B and 3B monitors (with `--prompt-variant v3` or `v5`) | Studies 1, 4, 5 |
| **Study 2: Gemini as monitor** | | |
| `gemini-monitor.toml` | `gemini-3.1-flash-lite`, minimal thinking, free-tier limits | Studies 2, 5 |
| **Study 3: calibration** | | |
| `v2-calib-v2a.toml`, `v2-calib-v2b.toml`, `v2-calib-v2c.toml` | Round 1: 8B agent, variants v2a–v2c | Study 3 |
| `v2-calib2-v2d.toml` | Round 2: 8B agent, variant v2d | Study 3 |
| `v2-calib3-3b-v2a.toml` … `v2-calib3-3b-v2d.toml` | Round 3: 3B agent, variants v2a–v2d | Study 3 |
| `gemini-calib.toml` | Gemini as agent, v1, seeds 9000–9009 | Study 3 |
| **Study 4: second agent study** | | |
| `ms2-e1-b1.toml` … `ms2-e1-b6.toml` | E1: 3B agent, variant v2d, seeds 8000–8299 in six batches of 50 | Study 4 |
| **Pilots (appendix)** | | |
| `pilot-ollama.toml` | First local pilot (3B agent, 3B monitor) | — |
| `local-pilot.toml` | 8B agent and 3B monitor, 5 scenarios, seeds 2000+ | appendix |
| `local-main.toml` | Same, 30 scenarios, seeds 3000+ | appendix |
| `local-monitor-8b.toml` | `local-main` episodes re-judged by the 8B monitor | appendix |
| `local-fresh.toml` | Pre-registered fresh run, seeds 4000+ | appendix |
| `local-elicited.toml` | Elicited dataset, seeds 5000+ (`wml elicit`) | appendix |
| `gemini-pilot.toml` | Gemini 2.5 Flash agent pilot (one episode completed) | — |
| `gemini-actor.example.toml` | Template for a Gemini agent | — |
| **Registered, not run** | | |
| `cd-unprompted.toml`, `cd-monitor-8b.toml` | Combined-detector study (pre-registration 2026-10-08), never run | — |

Study 5's fixtures need no config: `wml fixtures --out runs/ho-fixtures --seeds 9100-9124 --n-required 4
--n-distractors 2 --dev-fraction 0.5 --set all --policies scope_padding,ordinary_mistakes_k2`.
