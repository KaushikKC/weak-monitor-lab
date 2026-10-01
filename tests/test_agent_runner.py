from collections import Counter

import pytest

import weak_monitor_lab.pipeline as pipeline
from weak_monitor_lab.adapters.base import BudgetExceeded, ProviderError, QuotaError, TransientError
from weak_monitor_lab.adapters.mock import MockActorAdapter
from weak_monitor_lab.agent import ActionError, fit_context, parse_action
from weak_monitor_lab.config import Config
from weak_monitor_lab.io import read_json, read_jsonl
from weak_monitor_lab.runner import CallRunner, CheckpointMismatch
from weak_monitor_lab.sim.env import TOOL_NAMES


def test_parse_action_accepts_fenced_json_and_validates_args():
    a, args = parse_action('```json\n{"tool": "get_order", "args": {"order_id": "ORD-1"}}\n```', list(TOOL_NAMES))
    assert a.tool == "get_order" and args == {"order_id": "ORD-1"}


@pytest.mark.parametrize("text", [
    "no json here",
    '{"tool": "run_shell", "args": {"cmd": "ls"}}',
    '{"tool": "get_order", "args": {}}',
    '{"tool": "get_order", "args": {"order_id": "A", "path": "/etc"}}',
    '{"tool": "get_task", "args": {}, "unexpected": 1}',
    '{"tool": "set_completion", "args": {"order_ids": "A", "complete": "yes please"}}',
])
def test_parse_action_rejects_malformed(text):
    with pytest.raises(ActionError):
        parse_action(text, list(TOOL_NAMES))


def test_fit_context_keeps_pinned_prefix_and_reports_drops():
    msgs = [{"role": "user", "content": "start"}]
    for i in range(20):
        msgs += [{"role": "assistant", "content": "a" * 100}, {"role": "user", "content": f"Result {i}" + "r" * 100}]
    out, dropped = fit_context(msgs, 1000)
    assert dropped > 0 and out[:3] == msgs[:3] and out[-1]["content"].startswith("Result 19")
    assert sum(len(m["content"]) for m in out) <= 1000 + 100


class NetMock(MockActorAdapter):
    """Mock actor that pretends to be network-backed, with scripted failures."""

    requires_network = True

    def __init__(self, fail_from: int | None = None, error=QuotaError("429 RESOURCE_EXHAUSTED")):
        super().__init__()
        self.live_calls = 0
        self.fail_from = fail_from
        self.error = error

    def generate(self, *a, **kw):
        self.live_calls += 1
        if self.fail_from is not None and self.live_calls >= self.fail_from:
            raise self.error
        return super().generate(*a, **kw)


def fast_cfg(**limits) -> Config:
    cfg = Config()
    cfg.experiment.n_scenarios = 2
    cfg.limits.requests_per_minute = 1e9
    cfg.limits.backoff_base_s = 0.0
    for k, v in limits.items():
        setattr(cfg.limits, k, v)
    return cfg


def test_mock_episode_runs_through_real_loop(tmp_path):
    rc = pipeline.run_actor(tmp_path / "r", fast_cfg(), "agent_unprompted")
    assert rc == 0
    trajs = list(read_jsonl(tmp_path / "r" / "trajectories.jsonl"))
    labels = list(read_jsonl(tmp_path / "r" / "labels.jsonl"))
    assert len(trajs) == 2 and all(t["status"] == "submitted" for t in trajs)
    assert all(t["stats"]["repairs"] == 1 and len(t["malformed_outputs"]) == 1 for t in trajs)
    assert all(l["category"] == "honest_success" for l in labels)


def test_quota_exhaustion_stops_cleanly_and_resume_does_not_duplicate_calls(tmp_path, monkeypatch):
    run = tmp_path / "r"
    flaky = NetMock(fail_from=15)
    monkeypatch.setattr(pipeline, "make_adapter", lambda *a, **k: flaky)
    rc = pipeline.run_actor(run, fast_cfg(max_quota_retries=2), "agent_unprompted")
    assert rc == pipeline.EXIT_STOPPED
    assert read_json(run / "status.json")["state"] == "stopped"
    assert flaky.live_calls == 14 + 3  # 14 ok, then 1 + 2 retries, then stop (no infinite retry)
    interrupted = list(read_jsonl(run / "interrupted.jsonl"))
    assert len(interrupted) == 1 and interrupted[0]["status"] == "interrupted"
    assert len(list(read_jsonl(run / "failures.jsonl"))) == 3
    completed_before = len(list(read_jsonl(run / "calls.jsonl")))
    assert completed_before == 14

    healthy = NetMock()
    monkeypatch.setattr(pipeline, "make_adapter", lambda *a, **k: healthy)
    assert pipeline.resume(run, enable_network=True) == 0
    calls = list(read_jsonl(run / "calls.jsonl"))
    keys = Counter(c["call_key"] for c in calls)
    assert max(keys.values()) == 1, "a checkpointed call was repeated"
    assert healthy.live_calls == len(calls) - completed_before
    assert len(list(read_jsonl(run / "trajectories.jsonl"))) == 2
    assert read_json(run / "status.json")["state"] == "completed"


def test_transient_errors_are_bounded(tmp_path, monkeypatch):
    bad = NetMock(fail_from=1, error=TransientError("timeout"))
    monkeypatch.setattr(pipeline, "make_adapter", lambda *a, **k: bad)
    rc = pipeline.run_actor(tmp_path / "r", fast_cfg(max_retries=2), "agent_unprompted")
    assert rc == pipeline.EXIT_STOPPED and bad.live_calls == 3


def test_request_budget_is_enforced_across_resume(tmp_path, monkeypatch):
    run = tmp_path / "r"
    ad = NetMock()
    monkeypatch.setattr(pipeline, "make_adapter", lambda *a, **k: ad)
    assert pipeline.run_actor(run, fast_cfg(max_total_requests=5), "agent_unprompted") == pipeline.EXIT_STOPPED
    assert ad.live_calls == 5 and read_json(run / "budget.json")["network_requests_used"] == 5
    assert pipeline.resume(run, enable_network=True) == pipeline.EXIT_STOPPED  # budget persisted
    assert ad.live_calls == 5
    assert pipeline.resume(run, enable_network=True, max_total_requests=500) == 0


def test_repeated_samples_are_separate_calls(tmp_path):
    cfg = fast_cfg()
    cfg.experiment.n_scenarios = 1
    cfg.experiment.samples_per_scenario = 3
    assert pipeline.run_actor(tmp_path / "r", cfg, "agent_unprompted") == 0
    trajs = list(read_jsonl(tmp_path / "r" / "trajectories.jsonl"))
    assert len({t["episode_id"] for t in trajs}) == 3
    calls = list(read_jsonl(tmp_path / "r" / "calls.jsonl"))
    # identical prompts across samples, but each sample is its own recorded call
    assert len(calls) == 3 * len([c for c in calls if trajs[0]["episode_id"] in c["call_key"]])


def test_checkpoint_prompt_mismatch_is_refused(tmp_path):
    cfg = fast_cfg()
    runner = CallRunner(tmp_path, cfg.limits)
    ad = MockActorAdapter()
    runner.call(ad, "k1", "sys", [{"role": "user", "content": "hi"}], cfg.actor, None, "actor")
    runner2 = CallRunner(tmp_path, cfg.limits)
    assert runner2.call(ad, "k1", "sys", [{"role": "user", "content": "hi"}], cfg.actor, None, "actor")["from_cache"]
    with pytest.raises(CheckpointMismatch):
        runner2.call(ad, "k1", "sys", [{"role": "user", "content": "DIFFERENT"}], cfg.actor, None, "actor")


# Hash of the unprompted actor prompt used by every agent_unprompted run so far.
UNPROMPTED_ACTOR_PROMPT_HASH = "63b9bf998bad7093f46a2582f48531e5e1afbd2dd39122220fa7412d38551455"


def test_unprompted_actor_prompt_is_unchanged():
    from weak_monitor_lab.agent import actor_system_prompt
    from weak_monitor_lab.io import sha256_text

    assert sha256_text(actor_system_prompt(True)) == UNPROMPTED_ACTOR_PROMPT_HASH
    assert sha256_text(actor_system_prompt(True, "none")) == UNPROMPTED_ACTOR_PROMPT_HASH
    assert "Evaluation note" in actor_system_prompt(True, "score_pressure")


@pytest.mark.parametrize("source,elicitation,clean", [
    ("elicited_adversarial", "none", False),           # elicited source needs an elicitation
    ("elicited_adversarial", "score_pressure", True),  # and the permissive tools
    ("agent_unprompted", "score_pressure", False),     # unprompted data must never be elicited
    ("capability_calibration", "score_pressure", True),
])
def test_elicitation_is_kept_to_its_own_source(tmp_path, source, elicitation, clean):
    cfg = fast_cfg()
    cfg.experiment.elicitation = elicitation
    with pytest.raises(ValueError):
        pipeline.run_actor(tmp_path / "r", cfg, source, clean=clean)


def test_elicited_run_is_separate_and_hidden_from_monitors(tmp_path):
    from weak_monitor_lab.agent import actor_system_prompt
    from weak_monitor_lab.io import sha256_text
    from weak_monitor_lab.monitor import build_monitor_input

    cfg = fast_cfg()
    cfg.experiment.elicitation = "score_pressure"
    assert pipeline.run_actor(tmp_path / "e", cfg, "elicited_adversarial", command="elicit") == 0
    trajs = list(read_jsonl(tmp_path / "e" / "trajectories.jsonl"))
    assert trajs and all(t["dataset_source"] == "elicited_adversarial" for t in trajs)
    assert all(t["actor_system_prompt_hash"] == sha256_text(actor_system_prompt(True, "score_pressure"))
               for t in trajs)
    for t in trajs:
        for cond in "ABC":
            text, _ = build_monitor_input(t, cond)
            assert "Evaluation note" not in text and "score_pressure" not in text
    # mixing with unprompted data in one monitor run is refused
    pipeline.run_actor(tmp_path / "u", fast_cfg(), "agent_unprompted")
    with pytest.raises(ValueError, match="mix"):
        pipeline.run_monitors(tmp_path / "m", [tmp_path / "e", tmp_path / "u"], fast_cfg(), ["A"], ["rule"])
    # resume works for elicit runs
    assert read_json(tmp_path / "e" / "manifest.json")["command"] == "elicit"


def test_fatal_provider_error_is_recorded_not_retried(tmp_path, monkeypatch):
    bad = NetMock(fail_from=1, error=ProviderError("HTTP 404 model not found"))
    monkeypatch.setattr(pipeline, "make_adapter", lambda *a, **k: bad)
    assert pipeline.run_actor(tmp_path / "r", fast_cfg(), "agent_unprompted") == pipeline.EXIT_STOPPED
    assert bad.live_calls == 1
    fails = list(read_jsonl(tmp_path / "r" / "failures.jsonl"))
    assert fails[0]["kind"] == "provider_error"


def test_clean_calibration_variant(tmp_path):
    assert pipeline.run_actor(tmp_path / "c", fast_cfg(), "capability_calibration", clean=True) == 0
    t = next(read_jsonl(tmp_path / "c" / "trajectories.jsonl"))
    assert t["variant"] == "clean" and t["permissive_tools"] is False and t["status"] == "submitted"
    assert all(e["tool"] not in ("set_completion", "update_scope") for e in t["events"])
    assert t["final_visible_score"] == 1.0  # completion follows from recording in the clean variant


def test_daily_cap_stops_cleanly_and_next_day_continues(tmp_path):
    cfg = fast_cfg(max_requests_per_day=3, daily_cap_providers=["mock"])
    ad = NetMock()
    day = ["2026-01-01"]
    msgs = [{"role": "user", "content": "hi"}]
    runner = CallRunner(tmp_path, cfg.limits, today=lambda: day[0])
    for i in range(3):
        runner.call(ad, f"k{i}", "s", msgs, cfg.actor, None, "actor")
    with pytest.raises(BudgetExceeded, match="per_day"):
        runner.call(ad, "k3", "s", msgs, cfg.actor, None, "actor")
    assert ad.live_calls == 3
    day[0] = "2026-01-02"  # quota reset; a fresh runner (i.e. resume) reads the persisted ledger
    runner2 = CallRunner(tmp_path, cfg.limits, today=lambda: day[0])
    runner2.call(ad, "k3", "s", msgs, cfg.actor, None, "actor")
    assert read_json(tmp_path / "budget.json")["by_day"] == {"2026-01-01": 3, "2026-01-02": 1}


def test_daily_cap_ignores_other_providers(tmp_path):
    cfg = fast_cfg(max_requests_per_day=1)  # default: only gemini counts
    runner = CallRunner(tmp_path, cfg.limits)
    ad = NetMock()  # provider "mock", e.g. standing in for a local Ollama monitor
    for i in range(3):
        runner.call(ad, f"k{i}", "s", [{"role": "user", "content": "hi"}], cfg.actor, None, "monitor")
    assert ad.live_calls == 3
