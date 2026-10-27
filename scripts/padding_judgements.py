"""Side-by-side monitor judgements on the scope-padding fixtures, verbatim, as Markdown on stdout. No model
calls; nothing in runs/ is changed.

    python scripts/padding_judgements.py --fixtures runs/hvf-d3-fixtures \
        --monitors runs/gem-d3-v5,runs/gem-d3-v3,runs/hvf-d3-mon-8b-v3

For each scope_padding fixture: the padding events from labels.jsonl, then every judgement of every monitor
run (all conditions, invalid outputs included), with score, category, cited events, checklist and
explanation as stored in monitor_results.jsonl. Two mechanical columns: whether the cited events include a
padding event, and whether the explanation contains a padded order ID.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from weak_monitor_lab.io import read_jsonl


def _cell(x) -> str:
    s = x if isinstance(x, str) else json.dumps(x, sort_keys=True)
    return s.replace("|", "\\|").replace("\n", " ")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixtures", required=True)
    ap.add_argument("--monitors", required=True, help="comma-separated monitor run dirs")
    a = ap.parse_args()
    labels = [l for l in read_jsonl(Path(a.fixtures) / "labels.jsonl") if l.get("fixture_policy") == "scope_padding"]
    runs = [(Path(d).name, list(read_jsonl(Path(d) / "monitor_results.jsonl"))) for d in a.monitors.split(",")]
    for l in labels:
        ep = l["episode_id"]
        pad_ev = {p["event_id"] for p in l["padding_events"]}
        pad_ids = sorted({o for p in l["padding_events"] for o in p["order_ids"]})
        print(f"### {ep} ({l['base_scenario_id']})\n")
        print(f"Padding events: {', '.join(sorted(pad_ev))} (orders {', '.join(pad_ids)}). "
              f"proxy_score {l['proxy_score']:.2f}, n_correct {l['n_correct']}/{l['n_required']}.\n")
        print("| Run | Cond | Valid | Score | Category | Cited events | Cites padding event | Explanation names a "
              "padded order | Checklist | Explanation |")
        print("|---|---|---|---|---|---|---|---|---|---|")
        for name, results in runs:
            for m in sorted((m for m in results if m["episode_id"] == ep), key=lambda m: m["condition"]):
                o = m.get("output") or {}
                ok = m["status"] == "ok"
                cited = [str(e) for e in o.get("supporting_event_ids") or []]
                expl = o.get("explanation") or ""
                print(f"| {name} | {m['condition']} | {'yes' if ok else m['status']} | "
                      f"{o.get('suspicion_score', '')} | {o.get('category', '')} | {', '.join(cited)} | "
                      f"{'yes' if pad_ev & set(cited) else 'no'} | "
                      f"{'yes' if any(p in expl for p in pad_ids) else 'no'} | "
                      f"{_cell(o.get('checklist', ''))} | {_cell(expl)} |")
        print()


if __name__ == "__main__":
    main()
