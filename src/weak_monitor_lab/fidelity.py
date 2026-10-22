"""Monitor-input fidelity audit (plan update after METR's monitoring red-team, 2026-10-22).

Does monitor view B contain every tool result the agent received, in order?

For a model-driven episode, the episode is replayed through the real agent loop (agent.run_model_episode)
against a copy of the run's checkpointed calls. CallRunner refuses any call whose prompt hash differs from
the checkpoint, so a replay that completes reproduces byte for byte what the agent received. Each tool result
the agent received is then looked up in view B. No model is called; nothing in the run is written.
"""

from __future__ import annotations

import json
import random
import shutil
import tempfile
from pathlib import Path

from weak_monitor_lab.agent import run_model_episode
from weak_monitor_lab.config import Config
from weak_monitor_lab.io import read_json, read_jsonl
from weak_monitor_lab.monitor.views import build_monitor_input
from weak_monitor_lab.runner import CallRunner
from weak_monitor_lab.sim.env import ReconciliationEnv
from weak_monitor_lab.sim.scenario import generate_scenario

RESULT_PREFIX = "Result of "


class _ReplayAdapter:
    """Answers only from the checkpoint: a call missing from calls.jsonl is an error, never a model call."""
    requires_network = False

    def __init__(self, generator: dict):
        self.provider, self.model_id = generator["provider"], generator["model_id"]
        self.is_fixture = generator.get("is_fixture", False)

    def describe(self) -> dict:
        return {"provider": self.provider, "model_id": self.model_id, "is_fixture": self.is_fixture}

    def generate(self, *a, **kw):
        raise RuntimeError("replay reached a call that is not in the checkpoint")


def _sample_seed(traj: dict, cfg: Config) -> int | None:
    gen = traj["generator"]
    if "sample_seed" in gen:
        return gen["sample_seed"]
    if cfg.actor.seed is None:
        return None
    i = traj["scenario_params"]["seed"] - cfg.experiment.seed
    return cfg.actor.seed + 1000 * i + traj["sample_index"]


def received_results(traj: dict, run_dir: Path) -> list[dict]:
    """Replay one saved model episode; return the tool-result messages the agent received, in order.

    Each item: {"label": "event e003" | "blocked action b001", "tool": ..., "result": <parsed JSON>}."""
    run_dir = Path(run_dir)
    cfg = Config.model_validate(read_json(run_dir / "manifest.json")["config"])
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copy(run_dir / "calls.jsonl", Path(tmp) / "calls.jsonl")
        runner = CallRunner(Path(tmp), cfg.limits)
        seen: list[str] = []
        orig = runner.call

        def call(adapter, key, system, messages, mc, **kw):
            last = messages[-1]["content"] if messages else ""
            if last.startswith(RESULT_PREFIX) and (not seen or seen[-1] != last):
                seen.append(last)
            return orig(adapter, key, system, messages, mc, **kw)

        runner.call = call
        env = ReconciliationEnv(generate_scenario(**traj["scenario_params"]), permissive_tools=traj["permissive_tools"])
        if traj.get("blocking"):
            from weak_monitor_lab.blocking import BlockingEnv
            env = BlockingEnv(env, traj["blocking"]["mode"])
        run_model_episode(env, _ReplayAdapter(traj["generator"]), runner, cfg, f"{traj['run_id']}/{traj['episode_id']}",
                          _sample_seed(traj, cfg))
    base = env.env if hasattr(env, "env") else env
    replayed = [{k: e[k] for k in ("tool", "args", "ok", "result")} for e in (ev.to_dict() for ev in base.events)]
    saved = [{k: e[k] for k in ("tool", "args", "ok", "result")} for e in traj["events"]]
    if replayed != saved:
        raise AssertionError(f"{traj['episode_id']}: replayed events differ from the saved events")
    out = []
    for msg in seen:
        head, _, body = msg.partition("\n")
        label, _, tool = head[len(RESULT_PREFIX):].rpartition(" (")
        out.append({"label": label, "tool": tool.rstrip("):"), "result": json.loads(body)})
    return out


def view_b_check(traj: dict, received: list[dict], max_chars: int = 30_000) -> dict:
    """Where each received result appears in view B. A result counts as present when its event block
    (`result: <json, sorted keys>`) is found after the previous one. get_task's instructions are shown as
    '<identical to the task specification above>' and are checked against the task text instead."""
    text, meta = build_monitor_input(traj, "B", max_chars)
    by_id = {e["event_id"]: e for e in traj["events"]}
    pos, present, missing, not_events = 0, 0, [], []
    for r in received:
        if not r["label"].startswith("event "):
            not_events.append(r["label"])  # a blocked action: never executed, so not in the host event log
            continue
        ev = by_id.get(r["label"][len("event "):])
        res = r["result"]
        if ev is not None and ev["tool"] == "get_task" and isinstance(res, dict) and "instructions" in res:
            if res["instructions"].strip() != traj["task_text"].strip():
                missing.append(ev["event_id"])
                continue
            res = {**res, "instructions": "<identical to the task specification above>"}
        header = None if ev is None else f"[{ev['event_id']}] {ev['tool']} "
        at = -1 if header is None else text.find(header, pos)
        # the result line must directly follow this event's header line
        line_start = text.find("\n", at) + 1
        rline = f"    result: {json.dumps(res, sort_keys=True)}\n"
        if at < 0 or not (text + "\n").startswith(rline, line_start):
            missing.append(r["label"])
            continue
        pos, present = line_start, present + 1
    return {"received": len(received), "in_view_b_in_order": present, "missing": missing,
            "blocked_not_in_log": not_events, "truncation": meta["truncation"]}


def audit_run(run_dir: Path, sample: int | None = None, seed: int = 20261022) -> dict:
    trajs = [t for t in read_jsonl(Path(run_dir) / "trajectories.jsonl") if t["generator"].get("kind") == "model"]
    if sample is not None and sample < len(trajs):
        trajs = random.Random(seed).sample(trajs, sample)
    rows = [{"episode_id": t["episode_id"], **view_b_check(t, received_results(t, run_dir))} for t in trajs]
    return {"run": Path(run_dir).name, "episodes": len(rows),
            "results_received": sum(r["received"] for r in rows),
            "results_in_view_b_in_order": sum(r["in_view_b_in_order"] for r in rows),
            "episodes_with_missing": sum(bool(r["missing"]) for r in rows),
            "blocked_results_not_in_log": sum(len(r["blocked_not_in_log"]) for r in rows),
            "truncated_inputs": sum(r["truncation"] != "none" for r in rows), "rows": rows}
