import pytest

from weak_monitor_lab.policies import POLICIES
from weak_monitor_lab.sim.env import ReconciliationEnv
from weak_monitor_lab.sim.scenario import generate_scenario


def run_policy(name: str, seed: int = 7) -> ReconciliationEnv:
    env = ReconciliationEnv(generate_scenario(seed))
    POLICIES[name](env)
    return env


def events_of(env: ReconciliationEnv) -> list[dict]:
    return [e.to_dict() for e in env.events]


@pytest.fixture
def scenario():
    return generate_scenario(7)
