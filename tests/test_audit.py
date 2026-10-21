"""Blind label-audit kit (roadmap A4, 2026-10-21)."""

import csv
import re
from collections import Counter
from pathlib import Path

import pytest

from weak_monitor_lab.audit import (ANSWER_COLUMNS, RATER_DEFINITIONS, STRATA, build_kit, cohen_kappa, draw_sample,
                                    rater_view, read_answers, score)
from weak_monitor_lab.cli import main
from weak_monitor_lab.io import read_json, read_jsonl
from weak_monitor_lab.pipeline import generate_fixtures

EXPORT_COLUMNS = ("run_id", "dataset", "episode_id", "base_scenario_id", "submitted", "category_v2",
                  "exploit_attempt", "exploit_attempt_v2", "successful_exploitation", "gap_G")
DATASETS = ("D1", "fresh", "elicited")


def _b(x) -> str:
    return "true" if x else "false"


@pytest.fixture(scope="module")
def kit_inputs(tmp_path_factory):
    """Fixture episodes (seeds 1-8, every scripted policy) dressed up as an export of three agent datasets."""
    root = tmp_path_factory.mktemp("audit")
    generate_fixtures(root / "runs" / "fx", list(range(1, 9)), 4, 2, 0.5, "all")
    rows = []
    for i, l in enumerate(read_jsonl(root / "runs" / "fx" / "labels.jsonl")):
        rows.append({"run_id": "fx", "dataset": DATASETS[i % 3], "episode_id": l["episode_id"],
                     "base_scenario_id": l["base_scenario_id"], "submitted": _b(l["submitted"]),
                     "category_v2": l["category_v2"], "exploit_attempt": _b(l["exploit_attempt"]),
                     "exploit_attempt_v2": _b(l["exploit_attempt_v2"]),
                     "successful_exploitation": _b(l["successful_exploitation"]),
                     "gap_G": str(l["proxy_score"] - l["n_correct"] / l["n_required"])})
    (root / "export").mkdir()
    with open(root / "export" / "episodes.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=EXPORT_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    return root, rows


def _ep(i, cat="ordinary_failure", attempt=False, G=0.25, ds="D1", submitted=True, padding=False):
    return {"episode_id": f"ep-{i:03d}", "dataset": ds, "submitted": _b(submitted), "category_v2": cat,
            "exploit_attempt": _b(attempt), "exploit_attempt_v2": _b(attempt or padding), "gap_G": str(G)}


# ------------------------------------------------------------------ sampling rule
def test_attempts_capped_and_rest_split_between_honest_strata():
    eps = ([_ep(i, "scope_exclusion", True) for i in range(30)] + [_ep(100 + i) for i in range(20)]
           + [_ep(200 + i, "honest_success", G=0.0) for i in range(20)])
    picked, counts = draw_sample(eps, n=40, max_attempts=25, seed=1)
    assert [len(picked[s]) for s in STRATA] == [25, 8, 7]
    assert counts["n_sampled"] == 40
    again, _ = draw_sample(eps, n=40, max_attempts=25, seed=1)
    assert again == picked
    other, _ = draw_sample(eps, n=40, max_attempts=25, seed=2)
    assert other["exploit_attempt"] != picked["exploit_attempt"]


def test_all_attempts_taken_when_few_and_short_stratum_gives_way():
    eps = ([_ep(i, "unsupported_completion", True) for i in range(10)] + [_ep(100 + i) for i in range(40)]
           + [_ep(200 + i, "honest_success", G=0.0) for i in range(4)])
    picked, _ = draw_sample(eps, n=40, max_attempts=25, seed=1)
    assert [len(picked[s]) for s in STRATA] == [10, 26, 4]


def test_frame_excludes_and_counts_everything_else():
    eps = [_ep(1, "scope_exclusion", True), _ep(2), _ep(3, G=0.0), _ep(4, G=-0.25),
           _ep(5, "exploit_attempt_unsuccessful", padding=True), _ep(6, submitted=False),
           _ep(7, "honest_success", G=0.0), _ep(8, ds="D3"), _ep(9, ds="fresh")]
    picked, counts = draw_sample(eps, n=40, max_attempts=25, seed=1)
    assert {s: [e["episode_id"] for e in picked[s]] for s in STRATA} == {
        "exploit_attempt": ["ep-001"], "honest_failure_gpos": ["ep-002", "ep-009"], "honest_success": ["ep-007"]}
    assert counts["excluded"] == {"D1/honest failure with G <= 0": 2, "D1/not submitted": 1,
                                  "D1/padding-only attempt": 1}
    assert sum(counts["frame"].values()) + sum(counts["excluded"].values()) == 8  # D3 is not in the frame


# ------------------------------------------------------------------ the forms are blind
def test_rater_view_copies_only_task_log_and_report(kit_inputs):
    root, _ = kit_inputs
    t = next(iter(read_jsonl(root / "runs" / "fx" / "trajectories.jsonl")))
    v = rater_view(t)
    assert set(v) == {"task", "events", "report"} and v["task"] == t["task_text"]
    assert all(set(e) == {"tool", "args", "ok", "result", "note"} for e in v["events"])
    assert len(v["events"]) == len(t["events"])


def test_kit_forms_are_blind_complete_and_shuffled_per_rater(kit_inputs, tmp_path):
    root, rows = kit_inputs
    m = build_kit(root / "export", root / "runs", tmp_path / "kit", ["ann", "bo"], n=20, max_attempts=8, seed=3)
    key = list(csv.DictReader(open(tmp_path / "kit" / "key.csv")))
    assert len(key) == 20 == m["counts"]["n_sampled"]
    assert Counter(r["stratum"] for r in key) == Counter({"exploit_attempt": 8, "honest_failure_gpos": 6,
                                                          "honest_success": 6})
    orders = {}
    for rater in ("ann", "bo"):
        page = (tmp_path / "kit" / f"form-{rater}.html").read_text()
        orders[rater] = re.findall(r'data-item="(item-[0-9a-f]{6})"', page)
        assert sorted(orders[rater]) == sorted(r["item_id"] for r in key)
        for r in rows:  # no id of ANY export episode, sampled or not
            assert r["episode_id"] not in page and r["base_scenario_id"] not in page
        for word in ("fx", "D1", "elicited", "exploit", "category", "honest_", "ordinary_", "scope_padding",
                     "fixture", "policy", "split", "seed"):
            assert not re.search(rf"\b{word}", page), word
        assert RATER_DEFINITIONS.splitlines()[0] in page.replace("&quot;", '"').replace("&#x27;", "'")
    assert orders["ann"] != orders["bo"]
    assert read_json(tmp_path / "kit" / "manifest.json")["rater_orders"] == orders


def test_kit_is_never_redrawn_in_place_and_checks_saved_labels(kit_inputs, tmp_path):
    root, rows = kit_inputs
    build_kit(root / "export", root / "runs", tmp_path / "kit", ["a", "b"], n=10, max_attempts=5)
    with pytest.raises(FileExistsError):
        build_kit(root / "export", root / "runs", tmp_path / "kit", ["a", "b"], n=10, max_attempts=5)
    bad = tmp_path / "bad-export"
    bad.mkdir()
    with open(bad / "episodes.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=EXPORT_COLUMNS)
        w.writeheader()
        w.writerows({**r, "exploit_attempt": "true", "category_v2": "scope_exclusion"} for r in rows)
    with pytest.raises(ValueError, match="differs from labels.jsonl"):
        build_kit(bad, root / "runs", tmp_path / "kit2", ["a", "b"], n=10, max_attempts=5)
    with pytest.raises(ValueError):
        build_kit(root / "export", root / "runs", tmp_path / "kit3", ["a", "a"])
    with pytest.raises(ValueError, match="no eligible episodes"):
        build_kit(root / "export", root / "runs", tmp_path / "kit4", ["a", "b"], datasets=["local-main"])


def test_protocol_doc_quotes_the_rater_definitions_verbatim():
    doc = Path(__file__).resolve().parents[1] / "docs" / "label-audit-protocol.md"
    assert RATER_DEFINITIONS in doc.read_text()


# ------------------------------------------------------------------ scoring
def test_cohen_kappa_known_values():
    # 2x2 textbook example: 20 yes/yes, 5 yes/no, 10 no/yes, 15 no/no -> po 0.7, pe 0.5, kappa 0.4
    pairs = [("yes", "yes")] * 20 + [("yes", "no")] * 5 + [("no", "yes")] * 10 + [("no", "no")] * 15
    assert cohen_kappa(pairs, ("yes", "no")) == pytest.approx(0.4)
    assert cohen_kappa([("yes", "yes")] * 3, ("yes", "no")) is None
    assert cohen_kappa([], ("yes", "no")) is None


def _answers(path, rater, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(ANSWER_COLUMNS)
        w.writerows([rater, *r] for r in rows)
    return path


def test_read_answers_rejects_bad_files(tmp_path):
    ids = {"item-000001", "item-000002"}
    with pytest.raises(ValueError, match="unknown item"):
        read_answers(_answers(tmp_path / "a.csv", "a", [("item-ffffff", "yes", "", "")]), ids)
    with pytest.raises(ValueError, match="twice"):
        read_answers(_answers(tmp_path / "a.csv", "a", [("item-000001", "no", "", "")] * 2), ids)
    with pytest.raises(ValueError, match="invalid answer"):
        read_answers(_answers(tmp_path / "a.csv", "a", [("item-000001", "maybe", "", "")]), ids)
    _, ans = read_answers(_answers(tmp_path / "a.csv", "a", [("item-000001", "no", "deliberate", "x")]), ids)
    assert ans["item-000001"]["q2"] is None  # Q2 only counts after "yes"


def test_score_counts_agreement_and_label_comparison(kit_inputs, tmp_path):
    root, _ = kit_inputs
    build_kit(root / "export", root / "runs", tmp_path / "kit", ["ann", "bo"], n=20, max_attempts=8, seed=3)
    key = list(csv.DictReader(open(tmp_path / "kit" / "key.csv")))
    att = [r["item_id"] for r in key if r["exploit_attempt"] == "true"]
    hon = [r["item_id"] for r in key if r["exploit_attempt"] == "false"]
    # ann matches the labels exactly; bo says unsure on one attempt and yes on one honest item, skips one item
    ann = [(i, "yes", "deliberate", "e3") for i in att] + [(i, "no", "", "") for i in hon]
    bo = ([(att[0], "unsure", "", "")] + [(i, "yes", "confused", "") for i in att[1:]]
          + [(hon[0], "yes", "deliberate", "e1")] + [(i, "no", "", "") for i in hon[1:-1]])
    text = score(tmp_path / "kit" / "key.csv", [_answers(tmp_path / "ann.csv", "ann", ann),
                                                _answers(tmp_path / "bo.csv", "bo", bo)])
    assert "| bo | 19 | 1 | 8 of 8 | 1 |" in text
    assert "| Q1 manipulated (yes/no/unsure) | 19 | 17 |" in text
    assert "| Q1, items where neither rater said unsure (yes/no) | 18 | 17 |" in text
    assert "| Q2 deliberate/confused/unsure, items both raters answered yes | 7 | 0 |" in text
    assert "Agreement with the label on items answered yes or no: 20 of 20; Cohen's kappa (rater vs label) 1.000" in text
    assert "Agreement with the label on items answered yes or no: 17 of 18;" in text
    assert "| all | exploit_attempt | 8 | 7 | 0 | 1 | 0 |" in text
    assert "| all | honest_success | 6 |" in text


def test_cli_audit_round_trip(kit_inputs, tmp_path, capsys):
    root, _ = kit_inputs
    out = tmp_path / "kit"
    assert main(["audit-sample", "--export", str(root / "export"), "--runs-root", str(root / "runs"),
                 "--n", "12", "--max-attempts", "6", "--out", str(out)]) == 0
    assert {p.name for p in out.iterdir()} == {"form-rater-1.html", "form-rater-2.html", "key.csv",
                                                "manifest.json"}
    ids = [r["item_id"] for r in csv.DictReader(open(out / "key.csv"))]
    a = _answers(tmp_path / "1.csv", "rater-1", [(i, "no", "", "") for i in ids])
    b = _answers(tmp_path / "2.csv", "rater-2", [(i, "no", "", "") for i in ids])
    assert main(["audit-score", "--key", str(out / "key.csv"), str(a), str(b), "--out", str(tmp_path / "s.md")]) == 0
    assert (tmp_path / "s.md").read_text().startswith("# Label audit scores")
