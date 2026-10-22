"""Gemini monitor backend (roadmap A3, 2026-10-21). Mocked SDK client only; no network call is made."""

import json
from types import SimpleNamespace

import pytest

pytest.importorskip("google.genai")

import weak_monitor_lab.pipeline as pipeline
from weak_monitor_lab.adapters.gemini import GeminiAdapter
from weak_monitor_lab.config import load_config
from weak_monitor_lab.io import read_json, read_jsonl
from weak_monitor_lab.runner import CallRunner

V5_OK = json.dumps({"task_completed": {"score": 0.8, "event_ids": []},
                    "score_manipulated": {"score": 0.1, "event_ids": []}, "category": "no_issue", "explanation": "ok"})


class FakeAPIError(Exception):
    def __init__(self, code, status, msg):
        super().__init__(msg)
        self.code, self.status = code, status


def _resp(text, finish="STOP", block=None, version="gemini-fake-2.5-flash-001"):
    return SimpleNamespace(
        text=text, model_version=version, candidates=[SimpleNamespace(finish_reason=finish)],
        prompt_feedback=SimpleNamespace(block_reason=block) if block else None,
        usage_metadata=SimpleNamespace(prompt_token_count=100, candidates_token_count=20, thoughts_token_count=0,
                                       total_token_count=120))


class FakeModels:
    """Plays a script of responses/exceptions; afterwards answers with a valid v5 output."""

    def __init__(self, script=()):
        self.script, self.configs = list(script), []

    def generate_content(self, model, contents, config):
        self.configs.append(config)
        item = self.script.pop(0) if self.script else _resp(V5_OK)
        if isinstance(item, Exception):
            raise item
        return item

    def get(self, model):
        return SimpleNamespace(name=f"models/{model}", display_name="Fake", version="001",
                               input_token_limit=1, output_token_limit=1)


@pytest.fixture
def setup(tmp_path, monkeypatch):
    pipeline.generate_fixtures(tmp_path / "fx", [1, 2], n_required=4)  # 10 trajectories
    cfg = load_config("configs/gemini-monitor.toml", enable_network=True)
    cfg.monitor.prompt_variant = "v5"
    cfg.limits.requests_per_minute = 1e6
    cfg.limits.max_requests_per_day = 1000
    cfg.limits.backoff_base_s = cfg.limits.backoff_max_s = 0.0
    models = FakeModels()
    day = {"today": "2026-10-21"}
    monkeypatch.setattr(pipeline, "make_adapter",
                        lambda mc, c, role: GeminiAdapter(mc.model_id, None, client=SimpleNamespace(models=models)))
    monkeypatch.setattr(pipeline, "CallRunner",
                        lambda run_dir, limits: CallRunner(run_dir, limits, sleep=lambda s: None,
                                                           today=lambda: day["today"]))
    return SimpleNamespace(tmp=tmp_path, cfg=cfg, models=models, day=day)


def _run(s, conds=("B", "C")):
    return pipeline.run_monitors(s.tmp / "m", [s.tmp / "fx"], s.cfg, list(conds), ["llm"])


def test_gemini_monitor_runs_at_temperature_zero_and_records_returned_model_id(setup):
    s = setup
    assert _run(s) == 0
    res = list(read_jsonl(s.tmp / "m" / "monitor_results.jsonl"))
    assert len(res) == 20 and all(r["status"] == "ok" for r in res)
    assert all(r["monitor"]["name"] == "gemini:gemini-3.1-flash-lite|v5" for r in res)
    assert all(r["response_model_ids"] == ["gemini-fake-2.5-flash-001"] for r in res)
    calls = list(read_jsonl(s.tmp / "m" / "calls.jsonl"))
    assert {c["response_model_id"] for c in calls} == {"gemini-fake-2.5-flash-001"}
    assert all(c.temperature == 0.0 for c in s.models.configs)
    assert all(c.response_mime_type == "application/json" for c in s.models.configs)
    assert all(c.thinking_config.thinking_level == "MINIMAL" and c.thinking_config.thinking_budget is None
               for c in s.models.configs)


def test_daily_cap_stops_cleanly_and_resume_next_day_never_repeats_calls(setup):
    s = setup
    s.cfg.limits.max_requests_per_day = 7
    assert _run(s) == pipeline.EXIT_STOPPED
    st = read_json(s.tmp / "m" / "status.json")
    assert st["state"] == "stopped" and "max_requests_per_day=7" in st["reason"]
    assert len(s.models.configs) == 7 and len(list(read_jsonl(s.tmp / "m" / "monitor_results.jsonl"))) == 7
    # same day: resume refuses at once, no call made
    assert pipeline.resume(s.tmp / "m", enable_network=True) == pipeline.EXIT_STOPPED
    assert len(s.models.configs) == 7
    for day, total in (("2026-10-22", 14), ("2026-10-23", 20)):
        s.day["today"] = day
        code = pipeline.resume(s.tmp / "m", enable_network=True)
        assert len(s.models.configs) == total
    assert code == 0 and read_json(s.tmp / "m" / "status.json")["state"] == "completed"
    res = list(read_jsonl(s.tmp / "m" / "monitor_results.jsonl"))
    assert len(res) == len({r["result_id"] for r in res}) == 20
    assert read_json(s.tmp / "m" / "budget.json")["by_day"] == {"2026-10-21": 7, "2026-10-22": 7, "2026-10-23": 6}


def test_rate_limit_stops_cleanly_and_resume_continues(setup):
    s = setup
    quota = FakeAPIError(429, "RESOURCE_EXHAUSTED", "quota exceeded")
    s.models.script = [_resp(V5_OK)] * 3 + [quota, quota]  # max_quota_retries = 1: the second 429 stops
    assert _run(s) == pipeline.EXIT_STOPPED
    st = read_json(s.tmp / "m" / "status.json")
    assert st["state"] == "stopped" and st["reason"].startswith("QuotaExhausted")
    fails = list(read_jsonl(s.tmp / "m" / "failures.jsonl"))
    assert [f["kind"] for f in fails] == ["quota", "quota"]
    assert pipeline.resume(s.tmp / "m", enable_network=True) == 0
    res = list(read_jsonl(s.tmp / "m" / "monitor_results.jsonl"))
    assert len(res) == len({r["result_id"] for r in res}) == 20
    assert len(list(read_jsonl(s.tmp / "m" / "calls.jsonl"))) == 20  # completed calls are never repeated


def test_invalid_json_and_refusals_count_as_invalid_outputs(setup):
    s = setup
    s.models.script = [_resp("not json"), _resp("still {not json"),          # invalid JSON twice
                       _resp("", finish="SAFETY"), _resp("", block="SAFETY"),  # refusal, refusal
                       _resp("not json"), _resp(V5_OK)]                     # repaired
    assert _run(s, conds=("B",)) == 0
    res = list(read_jsonl(s.tmp / "m" / "monitor_results.jsonl"))
    assert [r["status"] for r in res[:3]] == ["invalid_output", "invalid_output", "ok"]
    assert res[2]["repairs"] == 1
    refusal = res[1]["failures"]
    assert refusal[0]["finish_reason"] == "SAFETY" and refusal[1]["block_reason"] == "SAFETY"
    assert sum(r["status"] == "ok" for r in res) == 8


def test_dry_run_counts_calls_and_days_without_any_call(setup, monkeypatch):
    s = setup
    s.cfg.limits.max_requests_per_day = 18
    monkeypatch.setattr(pipeline, "make_adapter", lambda *a: pytest.fail("dry run must not build an adapter"))
    plan = pipeline.plan_monitor_calls(s.tmp / "m", [s.tmp / "fx"], s.cfg, ["B", "C"], ["llm"])
    assert (plan["calls_min"], plan["calls_max"], plan["days_min"], plan["days_max"]) == (20, 40, 2, 3)
    assert not (s.tmp / "m").exists()
    monkeypatch.undo()
    monkeypatch.setattr(pipeline, "make_adapter",
                        lambda mc, c, role: GeminiAdapter(mc.model_id, None, client=SimpleNamespace(models=s.models)))
    monkeypatch.setattr(pipeline, "CallRunner",
                        lambda run_dir, limits: CallRunner(run_dir, limits, sleep=lambda x: None,
                                                           today=lambda: "2026-10-21"))
    _run(s, conds=("B",))
    plan = pipeline.plan_monitor_calls(s.tmp / "m", [s.tmp / "fx"], s.cfg, ["B", "C"], ["llm"])
    assert (plan["results_done"], plan["calls_min"], plan["requests_used_so_far"]) == (10, 10, 10)


def test_thinking_budget_is_still_sent_when_set(setup):
    s = setup
    s.cfg.monitor.gemini_thinking_level, s.cfg.monitor.gemini_thinking_budget = None, 0
    assert _run(s, ("C",)) == 0
    assert all(c.thinking_config.thinking_budget == 0 and c.thinking_config.thinking_level is None
               for c in s.models.configs)


def test_thinking_budget_and_level_are_exclusive():
    from pydantic import ValidationError

    from weak_monitor_lab.config import Config

    with pytest.raises(ValidationError, match="not both"):
        Config.model_validate({"monitor": {"gemini_thinking_budget": 0, "gemini_thinking_level": "minimal"}})
