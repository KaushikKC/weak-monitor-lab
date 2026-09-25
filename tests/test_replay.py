import copy

import pytest

from conftest import events_of, run_policy
from weak_monitor_lab.labels import ReplayMismatch, compute_labels, replay
from weak_monitor_lab.policies import POLICIES
from weak_monitor_lab.sim.env import state_hash


@pytest.mark.parametrize("policy", sorted(POLICIES))
def test_replay_reproduces_final_state_and_score(policy):
    env = run_policy(policy, 11)
    actions = [{"tool": e["tool"], "args": e["args"], "actor_note": e["actor_note"]} for e in events_of(env)]
    env2, _ = replay(env.scenario, actions)
    assert env2.snapshot() == env.snapshot()
    assert env2.visible_score() == env.visible_score()
    assert [e.to_dict() for e in env2.events] == events_of(env)
    lab = compute_labels(env.scenario, events_of(env), state_hash(env.snapshot()))
    assert lab["replay_verified"] and lab["proxy_score"] == env.visible_score()


def test_tampered_trajectory_is_detected():
    env = run_policy("unsupported_completion", 11)
    events = copy.deepcopy(events_of(env))
    events[-2]["result"]["visible_score"] = 0.123  # doctor a recorded result
    with pytest.raises(ReplayMismatch):
        compute_labels(env.scenario, events)
    with pytest.raises(ReplayMismatch):
        compute_labels(env.scenario, events_of(env), recorded_final_hash="0" * 64)
