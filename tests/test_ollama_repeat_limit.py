"""Ollama's "token repeat limit reached" HTTP 500 is an invalid output, not an outage (added 2026-10-25, B2)."""

import json

import httpx
import pytest

from weak_monitor_lab.adapters.base import TransientError
from weak_monitor_lab.adapters.ollama import OllamaAdapter
from weak_monitor_lab.analysis import is_refusal
from weak_monitor_lab.config import Config, ModelConfig
from weak_monitor_lab.io import read_jsonl
from weak_monitor_lab.monitor.monitors import llm_monitor
from weak_monitor_lab.pipeline import generate_fixtures
from weak_monitor_lab.runner import CallRunner, ProviderUnavailable

REPEAT = '{"error":"prediction aborted, token repeat limit reached"}'
GOOD = {"suspicion_score": 0.2, "category": "no_issue", "supporting_event_ids": [], "explanation": "ok"}


def _adapter(handler):
    return OllamaAdapter("llama-test:3b", "http://ollama.test", transport=httpx.MockTransport(handler))


def _ok(text):
    return httpx.Response(200, json={"model": "llama-test:3b", "message": {"role": "assistant", "content": text},
                                     "prompt_eval_count": 5, "eval_count": 2, "done_reason": "stop"})


def test_repeat_limit_is_an_empty_output_with_finish_reason():
    comp = _adapter(lambda req: httpx.Response(500, text=REPEAT)).generate(
        "s", [{"role": "user", "content": "x"}], ModelConfig(provider="ollama", model_id="m"))
    assert comp.text == "" and comp.meta["finish_reason"] == "REPEAT_LIMIT" and "repeat limit" in comp.meta["error"]


def test_other_http_500_is_still_transient():
    with pytest.raises(TransientError):
        _adapter(lambda req: httpx.Response(500, text='{"error":"model runner crashed"}')).generate(
            "s", [{"role": "user", "content": "x"}], ModelConfig(provider="ollama", model_id="m"))


def _setup(tmp_path):
    generate_fixtures(tmp_path / "fx", [1], n_required=3)
    traj = next(iter(read_jsonl(tmp_path / "fx" / "trajectories.jsonl")))
    cfg = Config.model_validate({"monitor": {"provider": "ollama", "model_id": "llama-test:3b", "temperature": 0.0,
                                             "seed": 0}})
    return traj, cfg, CallRunner(tmp_path / "run", cfg.limits)


def test_monitor_records_invalid_output_without_retrying(tmp_path):
    traj, cfg, runner = _setup(tmp_path)
    n = []

    def handler(req):
        n.append(1)
        return httpx.Response(500, text=REPEAT)

    rec = llm_monitor(traj, "B", _adapter(handler), runner, cfg.monitor, "r", 0)
    assert rec["status"] == "invalid_output" and rec["output"] is None
    assert len(n) == cfg.monitor.max_repairs + 1  # one call per repair, no transient retries
    assert all(f["finish_reason"] == "REPEAT_LIMIT" for f in rec["failures"])
    assert not is_refusal(rec)
    calls = list(read_jsonl(tmp_path / "run" / "calls.jsonl"))
    assert len(calls) == len(n) and all(c["meta"]["finish_reason"] == "REPEAT_LIMIT" for c in calls)


def test_monitor_repair_after_repeat_limit_can_succeed(tmp_path):
    traj, cfg, runner = _setup(tmp_path)
    replies = iter([httpx.Response(500, text=REPEAT), _ok(json.dumps(GOOD))])
    rec = llm_monitor(traj, "B", _adapter(lambda req: next(replies)), runner, cfg.monitor, "r", 0)
    assert rec["status"] == "ok" and rec["repairs"] == 1 and rec["failures"][0]["finish_reason"] == "REPEAT_LIMIT"


def test_genuine_outage_still_stops_the_run(tmp_path):
    traj, cfg, runner = _setup(tmp_path)
    runner.sleep = lambda s: None
    with pytest.raises(ProviderUnavailable):
        llm_monitor(traj, "B", _adapter(lambda req: httpx.Response(503, text="down")), runner, cfg.monitor, "r", 0)
