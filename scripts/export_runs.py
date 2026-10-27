"""Raw-data export of trajectory and monitor runs, in the data/export format (episodes.csv, judgements.csv,
manifests.json), so `wml intervals` can read it. No model calls; nothing in runs/ is changed.

    python scripts/export_runs.py --out data/export-ms2 \
        --dataset E1=runs/ms2-e1-b1,...,runs/ms2-e1-b6 --dataset E3=runs/ms2-e3-fixtures \
        --monitors runs/ms2-e1-mon-3b-v3,...

A dataset is a list of trajectory run dirs exported under one `dataset` name (main study 2: the six E1 batch
dirs are one dataset, pre-registration 2). Labels, v2 fields, the gap G and the checklist rule come from the
repo's own code (analysis.labels_with_v2, gap.jsonl, analysis.checklist_flag).
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from weak_monitor_lab.analysis import checklist_flag, labels_with_v2
from weak_monitor_lab.io import read_json, read_jsonl

EPISODE_COLS = ["run_id", "dataset", "source", "fixture_policy", "episode_id", "seed", "base_scenario_id", "split",
                "submitted", "status", "category", "category_v2", "exploit_attempt", "exploit_attempt_v2",
                "successful_exploitation", "genuine_success", "proxy_score", "counterfactual_proxy",
                "true_progress_T", "gap_G", "n_actions", "interrupted"]
JUDGEMENT_COLS = ["run_id", "episode_id", "monitor_model", "model_digest", "prompt_variant", "condition",
                  "suspicion_score", "category", "cited_event_ids", "checklist_nonempty", "valid_output", "error_type",
                  "repairs", "repair_finish_reasons", "latency_s", "input_tokens", "output_tokens", "truncated"]


def _s(x) -> str:
    if x is None:
        return ""
    if isinstance(x, bool):
        return "true" if x else "false"
    if isinstance(x, (dict, list)):
        return json.dumps(x, sort_keys=True)
    return str(x)


def _write(path: Path, cols: list[str], rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: _s(r.get(c)) for c in cols})


def episodes(dataset: str, run_dir: Path) -> list[dict]:
    labels = {l["episode_id"]: l for l in read_jsonl(run_dir / "labels.jsonl")}
    gaps = {g["episode_id"]: g for g in read_jsonl(run_dir / "gap.jsonl")}
    rows = []
    for t in read_jsonl(run_dir / "trajectories.jsonl"):
        ep = t["episode_id"]
        l, g = labels_with_v2(t, labels[ep]), gaps[ep]
        rows.append({"run_id": run_dir.name, "dataset": dataset, "source": t["dataset_source"],
                     "fixture_policy": l.get("fixture_policy"), "episode_id": ep,
                     "seed": t["scenario_params"]["seed"], "base_scenario_id": t["base_scenario_id"],
                     "split": t["split"], "submitted": t["status"] == "submitted", "status": t["status"],
                     "category": l["category"], "category_v2": l["category_v2"],
                     "exploit_attempt": l["exploit_attempt"], "exploit_attempt_v2": l["exploit_attempt_v2"],
                     "successful_exploitation": l["successful_exploitation"],
                     "genuine_success": l["genuine_success"], "proxy_score": l["proxy_score"],
                     "counterfactual_proxy": l["counterfactual_proxy"], "true_progress_T": g["true_progress"],
                     "gap_G": g["gap"], "n_actions": len(t["events"]),
                     "interrupted": t["status"] == "interrupted"})
    return rows


def judgements(run_dir: Path) -> list[dict]:
    usage = {c["call_key"]: c.get("usage") or {} for c in read_jsonl(run_dir / "calls.jsonl")} \
        if (run_dir / "calls.jsonl").exists() else {}
    rows = []
    for m in read_jsonl(run_dir / "monitor_results.jsonl"):
        mon, out, ok = m["monitor"], m.get("output") or {}, m["status"] == "ok"
        keys = m.get("call_keys") or []
        tok = [usage.get(k, {}) for k in keys]
        rows.append({"run_id": run_dir.name, "episode_id": m["episode_id"], "monitor_model": mon["model_id"],
                     "model_digest": (m.get("model_info") or {}).get("digest"),
                     "prompt_variant": mon.get("prompt_variant"), "condition": m["condition"],
                     "suspicion_score": out.get("suspicion_score") if ok else None,
                     "category": out.get("category") if ok else None,
                     "cited_event_ids": ";".join(map(str, out.get("supporting_event_ids") or [])) if ok else None,
                     "checklist_nonempty": checklist_flag(out) if ok and mon["kind"] == "llm" else None,
                     "valid_output": ok, "error_type": None if ok else m["status"], "repairs": m.get("repairs"),
                     "repair_finish_reasons": ";".join(str(f.get("finish_reason")) for f in m.get("failures") or []),
                     "latency_s": m.get("latency_s"),
                     "input_tokens": sum(u.get("prompt_tokens", u.get("input_tokens", 0)) or 0 for u in tok)
                     if tok else None,
                     "output_tokens": sum(u.get("output_tokens", 0) or 0 for u in tok) if tok else None,
                     "truncated": m.get("input_truncation", "none") != "none"})
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--dataset", action="append", required=True, help="NAME=run_dir,run_dir,...")
    ap.add_argument("--monitors", required=True, help="comma-separated monitor run dirs")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    ep_rows, manifests = [], []
    for spec in a.dataset:
        name, dirs = spec.split("=", 1)
        for d in dirs.split(","):
            ep_rows += episodes(name, Path(d))
            manifests.append({"run_id": Path(d).name, "dataset": name, **read_json(Path(d) / "manifest.json")})
    known = {r["episode_id"] for r in ep_rows}
    j_rows = []
    for d in a.monitors.split(","):
        rows = judgements(Path(d))
        missing = {r["episode_id"] for r in rows} - known
        if missing:
            raise SystemExit(f"{d}: {len(missing)} judged episodes not in any exported dataset")
        j_rows += rows
        manifests.append({"run_id": Path(d).name, "dataset": None, **read_json(Path(d) / "manifest.json"),
                          "status": read_json(Path(d) / "status.json")})
    _write(out / "episodes.csv", EPISODE_COLS, ep_rows)
    _write(out / "judgements.csv", JUDGEMENT_COLS, j_rows)
    (out / "manifests.json").write_text(json.dumps(manifests, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{out}: {len(ep_rows)} episodes, {len(j_rows)} judgements, {len(manifests)} manifests")


if __name__ == "__main__":
    main()
