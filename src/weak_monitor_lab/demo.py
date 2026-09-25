"""Offline demo: no model calls, no network, no credentials.

1. Scripted fixture trajectories for all five behaviours (seeds 1-10).
2. Two mock-actor episodes through the real agent loop (exercises parsing, repair, checkpointing).
3. Rule baseline + MOCK monitor over conditions A, B, C.
4. Summary table, CSVs and plots.

Everything produced here is a fixture/sanity check, not an empirical result.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from weak_monitor_lab.analysis import summarize
from weak_monitor_lab.config import Config
from weak_monitor_lab.pipeline import generate_fixtures, run_actor, run_monitors
from weak_monitor_lab.policies import EXPECTED_CATEGORY


def run_demo(out: Path) -> int:
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    cfg = Config()  # all-mock, network disabled
    assert not cfg.network.enabled

    print("[1/4] scripted fixtures")
    labels = generate_fixtures(out / "fixtures", list(range(1, 11)))
    mismatches = [l for l in labels if l["category"] != EXPECTED_CATEGORY[l["fixture_policy"]]]
    print(f"      {len(labels)} trajectories; label/expectation mismatches: {len(mismatches)}")

    print("[2/4] mock actor through the agent loop (FIXTURE actor, not a model)")
    cfg.experiment.n_scenarios = 2
    rc = run_actor(out / "mock-actor", cfg, "agent_unprompted")
    if rc:
        return rc

    print("[3/4] monitors on fixtures: rule baseline + MOCK monitor, conditions A/B/C")
    rc = run_monitors(out / "monitor-fixtures", [out / "fixtures"], cfg, ["A", "B", "C"], ["rule", "llm"])
    if rc:
        return rc

    print("[4/4] summary\n")
    print(summarize([out / "fixtures", out / "mock-actor", out / "monitor-fixtures"], out / "summary"))
    print(f"\nDemo outputs in {out}/ . All numbers above come from scripted or mock fixtures; "
          "they validate the pipeline and say nothing about any model.")
    return 1 if mismatches else 0
