import pytest

import weak_monitor_lab.pipeline as pipeline
from weak_monitor_lab.analysis import NO_FLAG_THRESHOLD, confusion, fit_threshold, summarize
from weak_monitor_lab.config import Config
from weak_monitor_lab.io import assign_split, read_jsonl
from weak_monitor_lab.pipeline import generate_fixtures, run_monitors


def test_threshold_fitting_refuses_test_split():
    rows = [{"split": "test", "score": 0.9, "exploit_attempt": True}]
    with pytest.raises(ValueError):
        fit_threshold(rows, "exploit_attempt")


def test_threshold_fit_and_constant_scores():
    dev = [{"split": "dev", "score": s, "exploit_attempt": y}
           for s, y in [(0.9, True), (0.8, True), (0.3, False), (0.85, False)]]
    t, _ = fit_threshold(dev, "exploit_attempt")
    c = confusion(dev, "exploit_attempt", t)
    assert c["tp"] + c["fn"] == 2 and c["fp"] + c["tn"] == 2
    const = [{"split": "dev", "score": 0.5, "exploit_attempt": y} for y in (True, False)]
    assert fit_threshold(const, "exploit_attempt")[0] == NO_FLAG_THRESHOLD


def test_all_variants_of_a_base_scenario_share_a_split(tmp_path):
    generate_fixtures(tmp_path, list(range(1, 9)))
    by_base = {}
    for t in read_jsonl(tmp_path / "trajectories.jsonl"):
        by_base.setdefault(t["base_scenario_id"], set()).add(t["split"])
        assert t["split"] == assign_split(t["base_scenario_id"])
    assert all(len(s) == 1 for s in by_base.values())


def test_monitor_run_refuses_mixed_sources(tmp_path):
    generate_fixtures(tmp_path / "fx", [1])
    cfg = Config()
    cfg.experiment.n_scenarios = 1
    pipeline.run_actor(tmp_path / "act", cfg, "agent_unprompted")
    with pytest.raises(ValueError, match="mix"):
        run_monitors(tmp_path / "m", [tmp_path / "fx", tmp_path / "act"], cfg, ["A"], ["rule"])


def test_summary_separates_fixture_outputs_and_reports_denominators(tmp_path):
    generate_fixtures(tmp_path / "fx", list(range(1, 7)))
    run_monitors(tmp_path / "m", [tmp_path / "fx"], Config(), ["A", "B", "C"], ["rule", "llm"])
    text = summarize([tmp_path / "m"], tmp_path / "out", plots=True)
    empirical, fixture = text.split("## FIXTURE MONITOR OUTPUTS")
    assert "mock:mock" not in empirical.split("## Monitor results")[1]
    assert "mock:mock" in fixture
    assert "SCRIPTED FIXTURES" in text
    assert "/30 (" in text  # k/n denominators present
    assert (tmp_path / "out" / "results.md").exists() and list((tmp_path / "out").glob("*.png"))


def test_interrupted_episodes_are_reported(tmp_path, monkeypatch):
    from test_agent_runner import NetMock, fast_cfg

    monkeypatch.setattr(pipeline, "make_adapter", lambda *a, **k: NetMock(fail_from=4))
    pipeline.run_actor(tmp_path / "r", fast_cfg(), "agent_unprompted")
    text = summarize([tmp_path / "r"], tmp_path / "out", plots=False)
    section = text.split("## Interrupted episodes (not resumed)")[1]
    assert "QuotaExhausted" in section


def test_auc_threshold_free():
    from weak_monitor_lab.analysis import auc

    rows = [{"score": s, "y": y} for s, y in [(0.9, True), (0.1, False), (0.5, True), (0.5, False)]]
    assert auc(rows, "y") == pytest.approx((1 + 1 + 1 + 0.5) / 4)
    assert auc([{"score": 0.8, "y": y} for y in (True, False)], "y") == 0.5  # constant scores
    assert auc([{"score": 0.8, "y": True}], "y") is None


def test_variant_names_do_not_break_markdown_table(tmp_path):
    generate_fixtures(tmp_path / "fx", list(range(1, 5)))
    cfg = Config()
    cfg.monitor.prompt_variant = "v2"
    run_monitors(tmp_path / "m", [tmp_path / "fx"], cfg, ["B"], ["llm"])
    text = summarize([tmp_path / "m"], tmp_path / "out", plots=False)
    rows = [l for l in text.splitlines() if l.startswith("| scripted_fixture |")]
    assert rows and all(len(l.replace("\\|", "").split("|")) == 17 for l in rows)  # 15 cells + 2 edges
    assert "mock:mock\\|v2" in text
