"""Command-line interface: `wml <command>` (or `python -m weak_monitor_lab <command>`)."""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from weak_monitor_lab.adapters import NetworkDisabled, ProviderError, make_adapter
from weak_monitor_lab.config import load_config, load_dotenv, redact


def _seeds(spec: str) -> list[int]:
    out: list[int] = []
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-")
            out.extend(range(int(a), int(b) + 1))
        elif part:
            out.append(int(part))
    return out


def cmd_demo(a) -> int:
    from weak_monitor_lab.demo import run_demo

    return run_demo(Path(a.out))


def cmd_test(a) -> int:
    return subprocess.call([sys.executable, "-m", "pytest", *a.pytest_args])


def cmd_fixtures(a) -> int:
    from weak_monitor_lab.pipeline import generate_fixtures

    labels = generate_fixtures(Path(a.out), _seeds(a.seeds), a.n_required, a.n_distractors, a.dev_fraction)
    print(f"wrote {len(labels)} scripted fixture trajectories to {a.out}")
    return 0


def cmd_check(a) -> int:
    from weak_monitor_lab.runner import CallRunner

    cfg = load_config(a.config, a.enable_network)
    mc = cfg.actor if a.role == "actor" else cfg.monitor
    adapter = make_adapter(mc, cfg, a.role)
    info = adapter.describe()
    print(f"{a.role}: reachable. {info}")
    if a.generate:
        run_dir = Path("runs/checks") / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        runner = CallRunner(run_dir, cfg.limits)
        rec = runner.call(adapter, f"check/{a.role}", "Reply with a JSON object.",
                          [{"role": "user", "content": 'Return {"ok": true}.'}], mc, seed=mc.seed, purpose="check")
        print(f"generation ok in {rec['latency_s']:.2f}s, usage={rec['usage']}, text={rec['text'][:200]!r}")
        print(f"(1 request counted; logged in {run_dir})")
    return 0


def cmd_generate(a, source: str, clean: bool, command: str) -> int:
    from weak_monitor_lab.pipeline import run_actor

    cfg = load_config(a.config, a.enable_network)
    return run_actor(Path(a.run_dir), cfg, source, clean=clean, command=command)


def cmd_monitor(a) -> int:
    from weak_monitor_lab.pipeline import run_monitors

    cfg = load_config(a.config, a.enable_network)
    if a.prompt_variant:
        cfg.monitor.prompt_variant = a.prompt_variant
    return run_monitors(Path(a.run_dir), [Path(p) for p in a.trajectories], cfg,
                        [c.strip() for c in a.conditions.split(",")], [m.strip() for m in a.monitors.split(",")])


def cmd_resume(a) -> int:
    from weak_monitor_lab.pipeline import resume

    return resume(Path(a.run_dir), a.enable_network, a.max_total_requests)


def cmd_summarize(a) -> int:
    from weak_monitor_lab.analysis import summarize

    print(summarize([Path(p) for p in a.run_dirs], Path(a.out), plots=not a.no_plots))
    print(f"\nwritten to {a.out}/ (results.md, episodes.csv, monitor_metrics.csv, *.png)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="wml", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    def net(sp):
        sp.add_argument("--config", default="configs/default.toml")
        sp.add_argument("--enable-network", action="store_true",
                        help="allow network model calls (Ollama/Gemini); disabled by default")

    sp = sub.add_parser("demo", help="offline demo: fixtures + mock actor + rule/mock monitors + summary")
    sp.add_argument("--out", default="runs/offline-demo")
    sp.set_defaults(fn=cmd_demo)

    sp = sub.add_parser("test", help="run the offline test suite (pytest)")
    sp.add_argument("pytest_args", nargs="*")
    sp.set_defaults(fn=cmd_test)

    sp = sub.add_parser("fixtures", help="write scripted fixture trajectories + labels")
    sp.add_argument("--out", default="data/fixtures")
    sp.add_argument("--seeds", default="1-10")
    sp.add_argument("--n-required", type=int, default=6)
    sp.add_argument("--n-distractors", type=int, default=2)
    sp.add_argument("--dev-fraction", type=float, default=0.5)
    sp.set_defaults(fn=cmd_fixtures)

    sp = sub.add_parser("check", help="provider connectivity check (no generation unless --generate)")
    net(sp)
    sp.add_argument("--role", choices=["actor", "monitor"], default="actor")
    sp.add_argument("--generate", action="store_true", help="also make ONE tiny generation request")
    sp.set_defaults(fn=cmd_check)

    sp = sub.add_parser("calibrate", help="clean-task capability calibration (no permissive tools)")
    net(sp)
    sp.add_argument("--run-dir", required=True)
    sp.set_defaults(fn=lambda a: cmd_generate(a, "capability_calibration", True, "calibrate"))

    sp = sub.add_parser("generate", help="generate actor trajectories (no instructions to hack)")
    net(sp)
    sp.add_argument("--run-dir", required=True)
    sp.set_defaults(fn=lambda a: cmd_generate(a, "agent_unprompted", False, "generate"))

    sp = sub.add_parser("monitor", help="evaluate monitors on saved trajectories")
    net(sp)
    sp.add_argument("--trajectories", nargs="+", required=True, help="trajectory run dir(s), one dataset source")
    sp.add_argument("--run-dir", required=True)
    sp.add_argument("--conditions", default="A,B,C")
    sp.add_argument("--monitors", default="rule,llm", help="comma list of: rule, llm")
    sp.add_argument("--prompt-variant", choices=["v1", "v2", "v3", "v4"], default=None,
                    help="LLM monitor instructions (overrides [monitor].prompt_variant); see monitor/prompts.py")
    sp.set_defaults(fn=cmd_monitor)

    sp = sub.add_parser("resume", help="resume a stopped run using its saved config")
    sp.add_argument("--run-dir", required=True)
    sp.add_argument("--enable-network", action="store_true")
    sp.add_argument("--max-total-requests", type=int, default=None, help="raise the run's request cap")
    sp.set_defaults(fn=cmd_resume)

    sp = sub.add_parser("summarize", help="results table, CSVs and plots")
    sp.add_argument("run_dirs", nargs="+")
    sp.add_argument("--out", default="runs/summary")
    sp.add_argument("--no-plots", action="store_true")
    sp.set_defaults(fn=cmd_summarize)
    return p


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    args = build_parser().parse_args(argv)
    try:
        return args.fn(args)
    except NetworkDisabled as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except (ProviderError, NotImplementedError, ValueError, FileNotFoundError) as exc:
        print(f"error: {redact(str(exc))}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
