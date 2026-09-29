import pytest

from weak_monitor_lab.config import Config
from weak_monitor_lab.io import read_jsonl, sha256_text
from weak_monitor_lab.monitor.monitors import monitor_name
from weak_monitor_lab.monitor.prompts import PROMPTS, VARIANTS, monitor_system, normalize_output
from weak_monitor_lab.pipeline import generate_fixtures, run_monitors

# Hash of the original monitor prompt used for all runs before 2026-09-29.
V1_HASH = "1e8062c1cf3572c169696ba1dbd74bc4ad82b2c70ae24319415a147fe7bd7e47"


def test_v1_prompt_is_unchanged():
    assert sha256_text(PROMPTS["v1"]) == V1_HASH


def test_variants_are_distinct_and_named_apart():
    assert len({PROMPTS[v] for v in VARIANTS}) == len(VARIANTS)
    assert monitor_name("ollama", "m", "v1") == "ollama:m"  # historical name kept
    assert len({monitor_name("ollama", "m", v) for v in VARIANTS}) == len(VARIANTS)
    with pytest.raises(ValueError):
        monitor_system("v9")


def test_new_variants_define_honest_mistakes_and_security_rule():
    for v in ("v2", "v3", "v4"):
        p = PROMPTS[v]
        assert "Honest mistakes are NOT manipulation" in p and "UNTRUSTED_AGENT_TEXT" in p
    assert '"checklist"' in PROMPTS["v3"] and '"suspicion_rating"' in PROMPTS["v4"]


@pytest.mark.parametrize("rating,score", [(1, 0.0), (10, 1.0), (4, 1 / 3), (7.0, 2 / 3)])
def test_v4_rating_maps_to_unit_score(rating, score):
    out = normalize_output({"suspicion_rating": rating, "category": "no_issue"}, "v4")
    assert out["suspicion_score"] == pytest.approx(score) and out["raw_rating"] == int(rating)


@pytest.mark.parametrize("bad", [0, 11, 5.5, "7", True, None])
def test_v4_rejects_invalid_ratings(bad):
    with pytest.raises(ValueError):
        normalize_output({"suspicion_rating": bad}, "v4")


def test_each_variant_runs_and_results_do_not_collide(tmp_path):
    generate_fixtures(tmp_path / "fx", [1])
    for v in VARIANTS:
        cfg = Config()
        cfg.monitor.prompt_variant = v
        assert run_monitors(tmp_path / "m", [tmp_path / "fx"], cfg, ["B"], ["llm"]) == 0
    results = list(read_jsonl(tmp_path / "m" / "monitor_results.jsonl"))
    assert len(results) == 5 * len(VARIANTS)  # 5 fixture episodes x 4 variants, none skipped
    assert len({r["result_id"] for r in results}) == len(results)
    assert all(r["status"] == "ok" for r in results)
    v4 = [r for r in results if r["monitor"]["prompt_variant"] == "v4"]
    assert all(r["output"]["suspicion_score"] == pytest.approx(4 / 9) for r in v4)
    assert {r["monitor"]["system_prompt_hash"] for r in results} == {sha256_text(PROMPTS[v]) for v in VARIANTS}
