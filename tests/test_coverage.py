"""Monitor coverage and input-truncation reporting in `wml summarize` (added 2026-10-22)."""

import json

from weak_monitor_lab.analysis import coverage_section, is_refusal, summarize
from weak_monitor_lab.config import Config
from weak_monitor_lab.io import append_jsonl, read_jsonl, write_json
from weak_monitor_lab.pipeline import generate_fixtures, run_monitors


def _monitor_run(tmp_path, name="m"):
    generate_fixtures(tmp_path / "fx", [1, 2], n_required=4)  # 10 trajectories
    cfg = Config.model_validate({"monitor": {"provider": "mock", "model_id": "mock"}})
    assert run_monitors(tmp_path / name, [tmp_path / "fx"], cfg, ["B", "C"], ["rule", "llm"]) == 0
    return tmp_path / name


def _table(text):
    sec = text.split("## Monitor coverage and input truncation", 1)[1].split("\n## ", 1)[0]
    return [l for l in sec.splitlines() if l.startswith("| ") and not l.startswith("| run ")]


def test_complete_run_has_full_coverage(tmp_path):
    d = _monitor_run(tmp_path)
    rows = _table(summarize([d], tmp_path / "s", plots=False))
    assert rows == ["| m | mock:mock | 20 | 20 | 20 | 0 | 0 | 0 | - | 0 |",
                    "| m | rule-v2 | 20 | 20 | 20 | 0 | 0 | 0 | - | n/a |"]


def test_invalid_refused_and_not_attempted_are_counted_with_reasons(tmp_path):
    d = _monitor_run(tmp_path)
    res = list(read_jsonl(d / "monitor_results.jsonl"))
    llm = [r for r in res if r["monitor"]["kind"] == "llm"]
    keep = [r for r in res if r["monitor"]["kind"] == "rule"] + llm[:15]  # 5 LLM judgements never attempted
    keep[-1] = {**keep[-1], "status": "invalid_output", "output": None,
                "failures": [{"repair": 0, "error": "bad json", "finish_reason": "STOP", "block_reason": None}]}
    keep[-2] = {**keep[-2], "status": "invalid_output", "output": None,
                "failures": [{"repair": 0, "error": "empty", "finish_reason": "FinishReason.SAFETY",
                              "block_reason": None}]}
    keep[-3] = {**keep[-3], "status": "invalid_output", "output": None,
                "failures": [{"repair": 0, "error": "empty", "finish_reason": None, "block_reason": "SAFETY"}]}
    keep[-4] = {**keep[-4], "input_truncation": "results_abbreviated"}
    (d / "monitor_results.jsonl").unlink()
    for r in keep:
        append_jsonl(d / "monitor_results.jsonl", r)
    write_json(d / "status.json", {"state": "stopped", "reason": "BudgetExceeded: max_requests_per_day=18 reached"})
    text = summarize([d], tmp_path / "s", plots=False)
    assert ("| m | mock:mock | 20 | 15 | 12 | 1 | 2 | 5 | run stopped: BudgetExceeded: max_requests_per_day=18 "
            "reached | 1 |") in _table(text)
    assert "- LLM monitor inputs truncated by max_input_chars: 1/15 judgements" in text


def test_non_submitted_episodes_are_eligible_and_judged(tmp_path):
    generate_fixtures(tmp_path / "fx", [1, 2], n_required=4)
    trajs = list(read_jsonl(tmp_path / "fx" / "trajectories.jsonl"))
    trajs[0]["status"], trajs[0]["report"] = "action_limit", None
    (tmp_path / "fx" / "trajectories.jsonl").unlink()
    for t in trajs:
        append_jsonl(tmp_path / "fx" / "trajectories.jsonl", t)
    cfg = Config.model_validate({"monitor": {"provider": "mock", "model_id": "mock"}})
    assert run_monitors(tmp_path / "m", [tmp_path / "fx"], cfg, ["B", "C"], ["rule", "llm"]) == 0
    judged = {r["episode_id"] for r in read_jsonl(tmp_path / "m" / "monitor_results.jsonl")}
    assert trajs[0]["episode_id"] in judged
    run = {"dir": tmp_path / "m", "manifest": json.loads((tmp_path / "m" / "manifest.json").read_text()),
           "status": {"state": "completed"},
           "monitor_results": list(read_jsonl(tmp_path / "m" / "monitor_results.jsonl"))}
    rows = [l for l in coverage_section([run]) if l.startswith("| m |")]
    assert len(rows) == 2 and all(l.split(" | ")[2:4] == ["20", "20"] for l in rows)


def test_is_refusal():
    base = {"status": "invalid_output"}
    assert is_refusal({**base, "failures": [{"finish_reason": "SAFETY"}]})
    assert is_refusal({**base, "failures": [{"finish_reason": "FinishReason.PROHIBITED_CONTENT"}]})
    assert is_refusal({**base, "failures": [{"block_reason": "BlockedReason.OTHER"}]})
    assert not is_refusal({**base, "failures": [{"finish_reason": "MAX_TOKENS", "block_reason": None}]})
    assert not is_refusal({**base, "failures": []})
    assert not is_refusal({"status": "ok", "failures": [{"finish_reason": "SAFETY"}]})
