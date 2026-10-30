# Documentation and study index

Every confirmatory study was pre-registered: its plan was committed before its data existed, and the commit
that froze it is listed below. Pre-registrations and results notes are kept exactly as written at the time;
later corrections are new commits or new notes, never silent edits.

## Methods

| Document | Contents |
|---|---|
| [ground_truth.md](ground_truth.md) | Label definitions: genuine success, the two attempt predicates, the counterfactual proxy, categories, true progress T and gap G, scope padding, gap-matched negatives |
| [protocol.md](protocol.md) | Pilot-phase protocol (2026-09-25): evidence conditions, dataset sources, splits, integrity rules |
| [label-audit-protocol.md](label-audit-protocol.md) | Blind label-audit kit (`wml audit-sample`, `wml audit-score`) |
| [limitations.md](limitations.md) | Known limitations and post-hoc changes recorded during the pilots |
| [pilot-findings.md](pilot-findings.md) | Pilot results as summarised before the confirmatory studies |
| [diary_template.md](diary_template.md) | Template for the research diary |
| [plans/](plans/) | Plan updates (monitor-input fidelity audit after METR's monitoring red-team) |

## Paper studies

| Paper | Pre-registration (frozen in) | Configs | Results | Export |
|---|---|---|---|---|
| Study 1: small monitors (D1, D2, D3) | [2026-10-02-hacking-vs-failing](preregistration/2026-10-02-hacking-vs-failing.md) (`086d424`) | `hvf-*.toml` | [2026-10-06-hacking-vs-failing](results/2026-10-06-hacking-vs-failing.md), [2026-10-21-clustered-intervals](results/2026-10-21-clustered-intervals.md) | `data/export` |
| Study 2: Gemini as monitor (D1, D3) | [2026-10-22-gemini-monitor-v1](preregistration/2026-10-22-gemini-monitor-v1.md) (`43f8250`) | `gemini-monitor.toml` | [2026-10-27-gemini-monitor](results/2026-10-27-gemini-monitor.md) and [intervals](results/2026-10-27-gemini-monitor-intervals.md); [padding judgements](results/2026-10-27-gemini-padding-judgements.md) | `data/export-gemini` |
| Study 3: calibration, round 1 (8B, v2a–v2c) | [2026-10-21-v2-calibration](preregistration/2026-10-21-v2-calibration.md) (`4ab19e8`) | `v2-calib-v2*.toml` | [2026-10-22-v2-calibration](results/2026-10-22-v2-calibration.md), [failure analysis](results/2026-10-22-b1-failure-analysis.md) | — |
| Study 3: calibration, round 2 (8B, v2d) | [2026-10-22-v2-calibration-round2](preregistration/2026-10-22-v2-calibration-round2.md) (`415d81f`) | `v2-calib2-v2d.toml` | [2026-10-22-v2-calibration-round2](results/2026-10-22-v2-calibration-round2.md) | — |
| Study 3: calibration, round 3 (3B, v2a–v2d) | [2026-10-22-v2-calibration-3b](preregistration/2026-10-22-v2-calibration-3b.md) (`74a78c7`) | `v2-calib3-3b-*.toml` | [2026-10-22-v2-calibration-3b](results/2026-10-22-v2-calibration-3b.md) | — |
| Study 3: Gemini as agent (v1) | [2026-10-27-gemini-calibration](preregistration/2026-10-27-gemini-calibration.md) (`9edb4c0`) | `gemini-calib.toml` | [2026-10-28-gemini-calibration](results/2026-10-28-gemini-calibration.md) | — |
| Study 4: second agent study (E1, E3) | [2026-10-22-main-study-2](preregistration/2026-10-22-main-study-2.md) (`255a950`) | `ms2-e1-b*.toml`, `hvf-monitor-*.toml` | [2026-10-27-main-study-2](results/2026-10-27-main-study-2.md) and [intervals](results/2026-10-27-main-study-2-intervals.md) | `data/export-ms2` |
| Study 5: held-out replication (H) | [2026-10-27-held-out-replication](preregistration/2026-10-27-held-out-replication.md) (`06d9132`) | `hvf-monitor-8b.toml`, `gemini-monitor.toml` | [2026-10-30-held-out-replication](results/2026-10-30-held-out-replication.md) | `data/export-ho` |

Study 1's v1 clean-task calibration (D2: 8B 2/10, 3B 0/10) is reported in the Study 1 results note.

## Pilot and earlier pre-registered studies (paper appendix)

| Pre-registration | Results |
|---|---|
| — (exploratory) | [2026-09-28-local-run](results/2026-09-28-local-run.md), [2026-09-28-monitor-3b-vs-8b](results/2026-09-28-monitor-3b-vs-8b.md), [2026-09-29-monitor-prompt-variants](results/2026-09-29-monitor-prompt-variants.md) |
| [2026-09-29-checklist-detector](preregistration/2026-09-29-checklist-detector.md) (`90fc15e`) | [2026-09-29-checklist-detector-fresh](results/2026-09-29-checklist-detector-fresh.md) |
| [2026-10-01-8b-v3-and-elicited](preregistration/2026-10-01-8b-v3-and-elicited.md) (`0110241`), [disk-threshold amendment](preregistration/2026-10-02-amendment-disk-threshold.md) (`a217315`) | [2026-10-02-8b-v3-confirmation](results/2026-10-02-8b-v3-confirmation.md), [2026-10-02-elicited-dataset](results/2026-10-02-elicited-dataset.md), [negatives by type](results/2026-10-02-stage1-negatives-by-type.md) |

## Registered but not run

| Pre-registration | Status |
|---|---|
| [2026-10-08-combined-detector](preregistration/2026-10-08-combined-detector.md) (`531a8c4`) | Registered; never run, so no data exists. Seeds 7000–7029 from its range were later used by the 2026-10-21 calibration. |
| [2026-10-22-online-blocking](preregistration/2026-10-22-online-blocking.md) | Draft, never frozen; withdrawn before any data on 2026-10-27 (`2621bb9`). |

## Audits

* [Monitor-input fidelity](results/2026-10-22-monitor-input-fidelity.md) (2026-10-22, over the runs saved by
  then): view B contains every tool result the agent received, in order, and no saved monitor input was
  truncated. Later runs record truncation per judgement (`truncated` column in every export: all `false`).
