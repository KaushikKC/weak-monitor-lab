"""Run manifests record the code version: git HEAD and a dirty-tree flag (2026-10-18)."""

import subprocess

import weak_monitor_lab.io as wio
from weak_monitor_lab.config import Config
from weak_monitor_lab.io import git_state, read_json
from weak_monitor_lab.pipeline import generate_fixtures, run_actor, run_monitors


def _assert_git(d):
    assert len(d["git_commit"]) == 40 and int(d["git_commit"], 16) >= 0
    assert isinstance(d["git_dirty"], bool)


def test_git_state_reads_repo():
    _assert_git(git_state())


def test_git_state_without_git(monkeypatch):
    def boom(*a, **k):
        raise FileNotFoundError("git")

    monkeypatch.setattr(wio.subprocess, "run", boom)
    assert git_state() == {"git_commit": None, "git_dirty": None}


def test_git_state_outside_a_repo(tmp_path):
    assert git_state(tmp_path) == {"git_commit": None, "git_dirty": None}


def test_dirty_flag_tracks_working_tree(tmp_path):
    def git(*a):
        subprocess.run(["git", "-C", str(tmp_path), *a], check=True, capture_output=True)

    git("init", "-q")
    (tmp_path / "f.txt").write_text("a")
    git("add", "f.txt")
    git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "c")
    assert git_state(tmp_path)["git_dirty"] is False
    (tmp_path / "f.txt").write_text("b")
    assert git_state(tmp_path)["git_dirty"] is True


def test_manifests_record_git_per_session_and_for_fixtures(tmp_path):
    cfg = Config()
    cfg.experiment.n_scenarios = 1
    run_actor(tmp_path / "a", cfg, "agent_unprompted")
    m = read_json(tmp_path / "a" / "manifest.json")
    _assert_git(m)
    assert len(m["sessions"]) == 1
    _assert_git(m["sessions"][0])
    generate_fixtures(tmp_path / "fx", [1])
    _assert_git(read_json(tmp_path / "fx" / "manifest.json"))
    run_monitors(tmp_path / "m", [tmp_path / "fx"], cfg, ["B"], ["rule"])
    _assert_git(read_json(tmp_path / "m" / "manifest.json")["sessions"][0])
