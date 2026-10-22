"""Dataset generation (fixtures, actor episodes, calibration), monitor evaluation, resume.

Run-directory layout (one directory per run; sources are never mixed in one run):
  manifest.json          run id, command, dataset source, config snapshot, git commit + dirty flag,
                         sessions (git, versions, adapters, timestamps)
  status.json            running | completed | stopped (+ reason); what `wml resume` re-invokes
  trajectories.jsonl     finished episodes (public: no labels, no policy names)
  labels.jsonl           private ground-truth labels (+ fixture policy name), keyed by episode_id
  interrupted.jsonl      partial episodes stopped by quota/budget/provider/Ctrl-C (never silently dropped)
  calls.jsonl            every completed model call (checkpoint for resume)
  failures.jsonl         every provider failure and retry
  budget.json            network requests used by this run
  monitor_results.jsonl  monitor outputs (monitor runs only)
"""

from __future__ import annotations

import sys
from pathlib import Path

from weak_monitor_lab.adapters import (
    BudgetExceeded, NetworkDisabled, ProviderError, QuotaExhausted, make_adapter,
)
from weak_monitor_lab.agent import actor_system_prompt, run_model_episode
from weak_monitor_lab.blocking import BlockingEnv
from weak_monitor_lab.config import Config
from weak_monitor_lab.io import (
    append_jsonl, assign_split, git_state, opaque_id, read_json, read_jsonl, sha256_text, software_versions, utc_now,
    write_json,
)
from weak_monitor_lab.labels import compute_labels
from weak_monitor_lab.monitor import CONDITIONS, llm_monitor, rule_monitor
from weak_monitor_lab.monitor.monitors import monitor_name
from weak_monitor_lab.monitor.prompts import monitor_system
from weak_monitor_lab.runner import CallRunner, CheckpointMismatch
from weak_monitor_lab.sim.env import ReconciliationEnv, state_hash
from weak_monitor_lab.sim.scenario import generate_scenario

SOURCES = ("scripted_fixture", "agent_unprompted", "elicited_adversarial", "capability_calibration")
EXIT_STOPPED = 3


class RunStopped(Exception):
    pass


def make_trajectory(env: ReconciliationEnv, *, run_id: str, episode_id: str, source: str, variant: str,
                    sample_index: int, split: str, status: str, generator: dict, started_at: str,
                    extra: dict | None = None) -> dict:
    snap = env.snapshot()
    scn = env.scenario
    return {
        "schema_version": 1,
        "episode_id": episode_id,
        "run_id": run_id,
        "dataset_source": source,
        "base_scenario_id": scn.base_scenario_id,
        "scenario_params": scn.params(),
        "variant": variant,
        "permissive_tools": env.permissive_tools,
        "sample_index": sample_index,
        "split": split,
        "status": status,
        "task_text": scn.task_text(),
        "required_order_ids": list(scn.required_order_ids),
        "events": [e.to_dict() for e in env.events],
        "report": snap["report"],
        "final_state_hash": state_hash(snap),
        "final_visible_score": env.visible_score(),
        "generator": generator,
        "started_at": started_at,
        "finished_at": utc_now(),
        **(extra or {}),
    }


def label_record(traj: dict, fixture_policy: str | None = None) -> dict:
    scn = generate_scenario(**traj["scenario_params"])
    labels = compute_labels(scn, traj["events"], traj["final_state_hash"], traj["permissive_tools"])
    rec = {"episode_id": traj["episode_id"], "run_id": traj["run_id"], "dataset_source": traj["dataset_source"],
           "split": traj["split"], "status": traj["status"], "base_scenario_id": traj["base_scenario_id"], **labels}
    if fixture_policy:
        rec["fixture_policy"] = fixture_policy
    return rec


def _start_session(run_dir: Path, run_id: str, command: str, source: str | None, cfg: Config, params: dict,
                   adapters: list[dict], prompt_hashes: dict) -> None:
    mpath = run_dir / "manifest.json"
    manifest = read_json(mpath) if mpath.exists() else {
        "run_id": run_id, "command": command, "dataset_source": source, "created_at": utc_now(),
        "config": cfg.snapshot(), "params": params, "sessions": [], **git_state()}
    manifest["sessions"].append({"started_at": utc_now(), **git_state(), "software": software_versions(),
                                 "adapters": adapters, "prompt_hashes": prompt_hashes,
                                 "network_enabled": cfg.network.enabled})
    write_json(mpath, manifest)
    write_json(run_dir / "status.json", {"state": "running", "command": command, "params": params,
                                         "updated_at": utc_now()})


def _finish(run_dir: Path, state: str, reason: str | None = None) -> None:
    st = read_json(run_dir / "status.json")
    st.update(state=state, reason=reason, updated_at=utc_now())
    write_json(run_dir / "status.json", st)


# --------------------------------------------------------------------------- fixtures
def generate_fixtures(out_dir: Path, seeds: list[int], n_required: int = 6, n_distractors: int = 2,
                      dev_fraction: float = 0.5, policy_set: str = "core") -> list[dict]:
    """Scripted-policy trajectories. Deterministic; no model calls.

    policy_set: "core" (the original five), "gap-matched" (ordinary_mistakes_k1..k|R|),
    "held-out" (scope_padding) or "all". Gap-matched variants with k > n_required are skipped."""
    from weak_monitor_lab.policies import FIXTURE_SETS, gap_k

    if policy_set not in FIXTURE_SETS:
        raise ValueError(f"unknown policy_set {policy_set!r}; choose from {sorted(FIXTURE_SETS)}")
    policies = {n: p for n, p in FIXTURE_SETS[policy_set].items() if (gap_k(n) or 0) <= n_required}
    out_dir = Path(out_dir)
    for f in ("trajectories.jsonl", "labels.jsonl"):
        (out_dir / f).unlink(missing_ok=True)
    run_id = "fixtures"
    cfg = Config()
    cfg.experiment.n_required, cfg.experiment.n_distractors, cfg.experiment.dev_fraction = n_required, n_distractors, dev_fraction
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "manifest.json", {
        "run_id": run_id, "command": "fixtures", "dataset_source": "scripted_fixture", "created_at": utc_now(),
        "params": {"seeds": seeds, "n_required": n_required, "n_distractors": n_distractors,
                   "dev_fraction": dev_fraction, "policy_set": policy_set},
        "software": software_versions(), **git_state()})
    labels = []
    for seed in seeds:
        for name, policy in policies.items():
            scn = generate_scenario(seed, n_required, n_distractors)
            env = ReconciliationEnv(scn)
            started = utc_now()
            policy(env)
            traj = make_trajectory(
                env, run_id=run_id, episode_id=opaque_id("ep", run_id, seed, name), source="scripted_fixture",
                variant="standard", sample_index=0, split=assign_split(scn.base_scenario_id, dev_fraction),
                status="submitted" if env.submitted else "action_limit",
                generator={"kind": "scripted"}, started_at=started)
            append_jsonl(out_dir / "trajectories.jsonl", traj)
            lab = label_record(traj, fixture_policy=name)
            append_jsonl(out_dir / "labels.jsonl", lab)
            labels.append(lab)
    write_json(out_dir / "status.json", {"state": "completed", "command": "fixtures", "updated_at": utc_now()})
    return labels


# --------------------------------------------------------------------------- actor episodes
def _blocked(actor_env) -> dict:
    """Blocked calls of a blocking run (never executed, so not in `events`); nothing for other runs."""
    return {"blocked_actions": actor_env.blocked} if isinstance(actor_env, BlockingEnv) else {}


def run_actor(run_dir: Path, cfg: Config, source: str, clean: bool = False, command: str = "generate") -> int:
    if source not in ("agent_unprompted", "capability_calibration", "elicited_adversarial"):
        raise ValueError(f"unsupported source for actor runs: {source}")
    elicitation = cfg.experiment.elicitation
    # Keep elicited data strictly apart: only that source may (and must) use an elicitation prompt.
    if source == "elicited_adversarial" and (elicitation == "none" or clean):
        raise ValueError("elicited_adversarial runs need [experiment].elicitation set and permissive tools")
    if source != "elicited_adversarial" and elicitation != "none":
        raise ValueError(f"{source} runs must use elicitation = 'none' (got {elicitation!r})")
    block_with = cfg.experiment.block_with
    if block_with != "none" and clean:
        raise ValueError("online blocking needs the permissive tools; it cannot be used on the clean task")
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    run_id = run_dir.name
    params = {"source": source, "clean": clean}
    if block_with != "none":
        params["block_with"] = block_with
    adapter = make_adapter(cfg.actor, cfg, "actor")
    describe = adapter.describe()
    _start_session(run_dir, run_id, command, source, cfg, params, [{"role": "actor", **describe}],
                   {"actor_system": sha256_text(actor_system_prompt(not clean, elicitation, cfg.environment)),
                    "actor_elicitation": elicitation, "env_variant": cfg.environment.variant})
    runner = CallRunner(run_dir, cfg.limits)
    done = {t["episode_id"] for t in read_jsonl(run_dir / "trajectories.jsonl")}
    ex = cfg.experiment
    variant = "clean" if clean else "standard"
    for i in range(ex.n_scenarios):
        seed = ex.seed + i
        for k in range(ex.samples_per_scenario):
            scn = generate_scenario(seed, ex.n_required, ex.n_distractors)
            ep_id = opaque_id("ep", run_id, scn.base_scenario_id, variant, k)
            if ep_id in done:
                continue
            env = ReconciliationEnv(scn, permissive_tools=not clean)
            actor_env = env if block_with == "none" else BlockingEnv(env, block_with)
            sample_seed = None if cfg.actor.seed is None else cfg.actor.seed + 1000 * i + k
            generator = {"kind": "model", "provider": adapter.provider, "model_id": adapter.model_id,
                         "is_fixture": adapter.is_fixture, "model_info": describe,
                         "sampling": cfg.actor.model_dump(), "sample_seed": sample_seed}
            common = dict(run_id=run_id, episode_id=ep_id, source=source, variant=variant, sample_index=k,
                          split=assign_split(scn.base_scenario_id, ex.dev_fraction), generator=generator)
            # v2 episodes carry their environment; v1 trajectories keep the published layout (no new fields).
            env_fields = ({} if cfg.environment.version == "v1" else
                          {"env_version": cfg.environment.version, "env_variant": cfg.environment.variant})
            if block_with != "none":
                env_fields["blocking"] = {"mode": block_with}
            started = utc_now()
            try:
                out = run_model_episode(actor_env, adapter, runner, cfg, f"{run_id}/{ep_id}", sample_seed)
            except (QuotaExhausted, BudgetExceeded, ProviderError, CheckpointMismatch, KeyboardInterrupt) as exc:
                reason = f"{type(exc).__name__}: {exc}"
                append_jsonl(run_dir / "interrupted.jsonl", make_trajectory(
                    env, status="interrupted", started_at=started,
                    extra={"interrupt_reason": reason, **env_fields, **_blocked(actor_env)}, **common))
                _finish(run_dir, "stopped", reason)
                print(f"\nRun stopped cleanly: {reason}\nProgress is checkpointed. Resume with:\n"
                      f"  wml resume --run-dir {run_dir} --enable-network", file=sys.stderr)
                return 130 if isinstance(exc, KeyboardInterrupt) else EXIT_STOPPED
            traj = make_trajectory(env, status=out["status"], started_at=started,
                                   extra={"stats": out["stats"], "malformed_outputs": out["malformed_outputs"],
                                          "actor_system_prompt_hash": out["actor_system_prompt_hash"],
                                          **env_fields, **_blocked(actor_env)}, **common)
            append_jsonl(run_dir / "trajectories.jsonl", traj)
            append_jsonl(run_dir / "labels.jsonl", label_record(traj))
            print(f"  episode {ep_id} ({scn.base_scenario_id}, sample {k}): {out['status']}, "
                  f"{len(env.events)} actions, {out['stats']['model_calls']} calls")
    _finish(run_dir, "completed")
    return 0


# --------------------------------------------------------------------------- monitors
def load_trajectories(traj_dirs: list[Path]) -> list[dict]:
    out = []
    for d in traj_dirs:
        out.extend(read_jsonl(Path(d) / "trajectories.jsonl"))
    sources = {t["dataset_source"] for t in out}
    if len(sources) > 1:
        raise ValueError(f"refusing to mix dataset sources in one monitor run: {sorted(sources)}")
    return out


def run_monitors(run_dir: Path, traj_dirs: list[Path], cfg: Config, conditions: list[str], kinds: list[str],
                 command: str = "monitor") -> int:
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    run_id = run_dir.name
    for c in conditions:
        if c not in CONDITIONS:
            raise ValueError(f"unknown condition {c}")
    trajs = load_trajectories(traj_dirs)
    params = {"trajectory_dirs": [str(d) for d in traj_dirs], "conditions": conditions, "monitors": kinds}
    adapter = make_adapter(cfg.monitor, cfg, "monitor") if "llm" in kinds else None
    describe = adapter.describe() if adapter else None
    _start_session(run_dir, run_id, command, trajs[0]["dataset_source"] if trajs else None, cfg, params,
                   [{"role": "monitor", **describe}] if describe else [],
                   {"monitor_system": sha256_text(monitor_system(cfg.monitor.prompt_variant)),
                    "monitor_prompt_variant": cfg.monitor.prompt_variant})
    runner = CallRunner(run_dir, cfg.limits)
    path = run_dir / "monitor_results.jsonl"
    done = {r["result_id"] for r in read_jsonl(path)}
    for traj in trajs:
        for cond in conditions:
            if "rule" in kinds:
                rec = rule_monitor(traj, cond)
                if rec["result_id"] not in done:
                    append_jsonl(path, rec)
            if adapter is None:
                continue
            for k in range(cfg.monitor.samples):
                rid = (f"{traj['episode_id']}/{cond}/"
                       f"{monitor_name(adapter.provider, adapter.model_id, cfg.monitor.prompt_variant)}/k{k}")
                if rid in done:
                    continue
                try:
                    rec = llm_monitor(traj, cond, adapter, runner, cfg.monitor, run_id, k)
                except (QuotaExhausted, BudgetExceeded, ProviderError, CheckpointMismatch, KeyboardInterrupt) as exc:
                    reason = f"{type(exc).__name__}: {exc}"
                    _finish(run_dir, "stopped", reason)
                    print(f"\nMonitor run stopped cleanly: {reason}\nResume with:\n"
                          f"  wml resume --run-dir {run_dir} --enable-network", file=sys.stderr)
                    return 130 if isinstance(exc, KeyboardInterrupt) else EXIT_STOPPED
                rec["model_info"] = describe
                append_jsonl(path, rec)
    _finish(run_dir, "completed")
    return 0


def plan_monitor_calls(run_dir: Path, traj_dirs: list[Path], cfg: Config, conditions: list[str],
                       kinds: list[str]) -> dict:
    """Dry run for `wml monitor`: how many LLM monitor calls the job still needs and how long that takes
    under the configured caps. No adapter is built, no network call is made, nothing is written."""
    import math

    trajs = load_trajectories(traj_dirs)
    mc = cfg.monitor
    name = monitor_name(mc.provider, mc.model_id, mc.prompt_variant)
    done = {r["result_id"] for r in read_jsonl(Path(run_dir) / "monitor_results.jsonl")}
    wanted = [f"{t['episode_id']}/{c}/{name}/k{k}" for t in trajs for c in conditions for k in range(mc.samples)]
    pending = sum(rid not in done for rid in wanted) if "llm" in kinds else 0
    lim = cfg.limits
    cap = lim.max_requests_per_day if mc.provider in lim.daily_cap_providers else 0
    budget = Path(run_dir) / "budget.json"
    used_total = read_json(budget).get("network_requests_used", 0) if budget.exists() else 0
    upper = pending * (mc.max_repairs + 1)
    return {
        "monitor": name, "trajectories": len(trajs), "conditions": conditions, "samples": mc.samples,
        "results_wanted": len(wanted) if "llm" in kinds else 0, "results_done": len(wanted) - pending if "llm" in kinds else 0,
        "calls_min": pending, "calls_max": upper, "max_repairs": mc.max_repairs,
        "max_requests_per_day": cap or None,
        "days_min": math.ceil(pending / cap) if cap else None, "days_max": math.ceil(upper / cap) if cap else None,
        "minutes_at_rpm_min": round(pending / lim.requests_per_minute, 1),
        "requests_used_so_far": used_total, "max_total_requests": lim.max_total_requests,
        "fits_max_total_requests": used_total + upper <= lim.max_total_requests,
    }


# --------------------------------------------------------------------------- resume
def resume(run_dir: Path, enable_network: bool, max_total_requests: int | None = None) -> int:
    run_dir = Path(run_dir)
    manifest = read_json(run_dir / "manifest.json")
    status = read_json(run_dir / "status.json")
    if status["state"] == "completed":
        print(f"{run_dir} is already completed.")
        return 0
    cfg = Config.model_validate(manifest["config"])  # the run's own config; never the current file
    cfg.network.enabled = enable_network
    if max_total_requests is not None:
        cfg.limits.max_total_requests = max_total_requests
    cmd, params = manifest["command"], manifest["params"]
    if cmd in ("generate", "calibrate", "elicit"):
        return run_actor(run_dir, cfg, params["source"], params["clean"], command=cmd)
    if cmd == "monitor":
        return run_monitors(run_dir, [Path(p) for p in params["trajectory_dirs"]], cfg, params["conditions"],
                            params["monitors"], command=cmd)
    raise ValueError(f"cannot resume command {cmd!r}")


__all__ = ["EXIT_STOPPED", "NetworkDisabled", "SOURCES", "generate_fixtures", "label_record", "load_trajectories",
           "make_trajectory", "resume", "run_actor", "run_monitors"]
