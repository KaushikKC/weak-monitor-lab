"""Environment v2 (roadmap A2, 2026-10-21): v1 unchanged; v2a/v2b/v2c/v2d labels and worked examples."""

import hashlib
import json
import re
from types import MappingProxyType

import pytest
from pydantic import ValidationError

from weak_monitor_lab.agent import (WORKED_EXAMPLE, WORKED_EXAMPLE_HARD, WORKED_EXAMPLE_HARD_IDS, WORKED_EXAMPLE_IDS,
                                    actor_system_prompt)
from weak_monitor_lab.config import ENV_VARIANTS, Config, EnvironmentConfig
from weak_monitor_lab.io import read_json, read_jsonl, sha256_text
from weak_monitor_lab.labels import compute_labels
from weak_monitor_lab.pipeline import generate_fixtures, run_actor
from weak_monitor_lab.policies import _is_hard, EXPECTED_CATEGORY, POLICIES
from weak_monitor_lab.sim.env import PERMISSIVE_TOOLS, ReconciliationEnv, state_hash, tool_catalog
from weak_monitor_lab.sim.scenario import DeliveryRecord, Order, Scenario, generate_scenario

# Hashes of the published v1 actor prompts, as recorded in the v1 run manifests
# (hvf-d1-actor, hvf-calib-8b, elicited-actor).
V1_PROMPT_HASHES = {
    (True, "none"): "63b9bf998bad7093f46a2582f48531e5e1afbd2dd39122220fa7412d38551455",
    (False, "none"): "7b0c59b81268a20b1c95e53ec5d1728a3d65813af7efb8926dc200764fb680a5",
    (True, "score_pressure"): "a71ba59000fb82607873f5dca257855f23e9fed4206d6c61106ca49d2d1aac71",
}
# Taken from the code at commit 3aaf93c, before environment v2 existed.
V1_SCENARIO_HASH = "c8d70ac7ac3f60364369d0e9aad7924e6a7e6a0650165b0dd8f5a4dda3f00432"
V1_CATALOG_HASH = "e94a6d662ac72229c98f0363dc426d4ed16bd4df3bb63591bb03e4113e0c5e09"
# Clean-task actor prompts of the B1 runs (runs/v2-calib-*/manifest.json); adding v2d must not change them.
B1_PROMPT_HASHES = {
    "v2a": "661c54a84ec3732e6932c4bcaa660d5e899eaedc8d45b78b9b8f1ce380aa4da2",
    "v2b": "8b66a1e71940d76d6ef31442f147d1965b59858094ceec6812ff7a26e2aae896",
    "v2c": "8b66a1e71940d76d6ef31442f147d1965b59858094ceec6812ff7a26e2aae896",
}


def _env(variant: str) -> EnvironmentConfig:
    return EnvironmentConfig(version=ENV_VARIANTS[variant]["version"], variant=variant)


def _n_required(variant: str) -> int:
    return ENV_VARIANTS[variant]["n_required"] or 4


# ------------------------------------------------------------------ v1 is byte-identical
@pytest.mark.parametrize("key", sorted(V1_PROMPT_HASHES))
def test_v1_actor_prompts_match_published_hashes(key):
    permissive, elicitation = key
    assert sha256_text(actor_system_prompt(permissive, elicitation)) == V1_PROMPT_HASHES[key]
    assert sha256_text(actor_system_prompt(permissive, elicitation, _env("v1"))) == V1_PROMPT_HASHES[key]


def test_v1_tool_catalog_and_scenarios_unchanged():
    cat = json.dumps([tool_catalog(True), tool_catalog(False)]).encode()
    assert hashlib.sha256(cat).hexdigest() == V1_CATALOG_HASH
    acc = hashlib.sha256()
    for seed in list(range(50)) + [6000, 7000]:
        for n in (4, 6):
            s = generate_scenario(seed, n, 2)
            acc.update(hashlib.sha256(repr((s.seed, s.batch_id, s.required_order_ids, dict(s.orders), s.deliveries,
                                            dict(s.order_kinds))).encode()).hexdigest().encode())
    assert acc.hexdigest() == V1_SCENARIO_HASH


# sha256 of the sorted (seed, policy, final_state_hash) triples of runs/hvf-d3-fixtures (published D3 data:
# policy set "all", seeds 6200-6204, n_required 4, n_distractors 2).
V1_D3_FIXTURE_HASH = "0419c3efd5b88eab16cfa59cde0defa9e411a78f0996ba41f9c3346abe943f68"


def test_v1_d3_fixtures_regenerate_to_the_published_state_hashes(tmp_path):
    labels = generate_fixtures(tmp_path / "fx", list(range(6200, 6205)), 4, 2, 0.5, "all")
    trajs = {t["episode_id"]: t for t in read_jsonl(tmp_path / "fx" / "trajectories.jsonl")}
    triples = sorted((trajs[l["episode_id"]]["scenario_params"]["seed"], l["fixture_policy"],
                      trajs[l["episode_id"]]["final_state_hash"]) for l in labels)
    assert len(triples) == 50 and all(l["replay_verified"] for l in labels)
    assert hashlib.sha256(json.dumps(triples).encode()).hexdigest() == V1_D3_FIXTURE_HASH


def test_v1_runs_record_no_env_fields_and_old_configs_load_as_v1(tmp_path):
    cfg = Config()
    cfg.experiment.n_scenarios = 1
    run_actor(tmp_path / "a", cfg, "agent_unprompted")
    t = next(iter(read_jsonl(tmp_path / "a" / "trajectories.jsonl")))
    assert "env_version" not in t and "env_variant" not in t
    old = Config().snapshot()
    del old["environment"]
    assert Config.model_validate(old).environment.variant == "v1"


# ------------------------------------------------------------------ v2 variants
def test_v2_descriptions_change_only_non_permissive_text():
    v1, v2 = tool_catalog(True, "v1"), tool_catalog(True, "v2")
    assert [t["name"] for t in v1] == [t["name"] for t in v2]
    for a, b in zip(v1, v2):
        assert a["args_schema"] == b["args_schema"]
        if a["name"] in PERMISSIVE_TOOLS or a["name"] == "get_visible_score":
            assert a["description"] == b["description"]
    rec = next(t for t in v2 if t["name"] == "record_reconciliation")["description"]
    assert "non-voided" in rec and "returned" in rec and "failed_attempt" in rec


def test_variant_prompts_differ_as_defined():
    p = {v: actor_system_prompt(True, "none", _env(v)) for v in ENV_VARIANTS}
    assert WORKED_EXAMPLE not in p["v1"] and WORKED_EXAMPLE not in p["v2a"]
    assert p["v2a"] != p["v1"] and p["v2b"] == p["v2a"] + WORKED_EXAMPLE and p["v2c"] == p["v2b"]
    assert p["v2d"] == p["v2c"] + WORKED_EXAMPLE_HARD and all(WORKED_EXAMPLE_HARD not in p[v] for v in p if v != "v2d")
    # elicitation text, if any, still comes last
    assert actor_system_prompt(True, "score_pressure", _env("v2b")).startswith(p["v2b"])


@pytest.mark.parametrize("variant", sorted(B1_PROMPT_HASHES))
def test_b1_variant_prompts_unchanged(variant):
    assert sha256_text(actor_system_prompt(False, "none", _env(variant))) == B1_PROMPT_HASHES[variant]


@pytest.mark.parametrize("variant", sorted(ENV_VARIANTS))
@pytest.mark.parametrize("policy", sorted(POLICIES))
def test_fixture_policies_get_correct_labels_under_each_variant(variant, policy):
    n = _n_required(variant)
    for seed in range(1, 21):
        scn = generate_scenario(seed, n, 2)
        env = ReconciliationEnv(scn)
        POLICIES[policy](env)
        events = [e.to_dict() for e in env.events]
        lab = compute_labels(scn, events, state_hash(env.snapshot()))
        assert lab["replay_verified"] and lab["category"] == EXPECTED_CATEGORY[policy], (variant, seed)


def test_three_order_scenarios_have_two_simple_and_one_hard_order():
    for seed in range(200):
        scn = generate_scenario(seed, 3, 2)
        assert len(scn.required_order_ids) == 3
        kinds = [scn.order_kinds[o] for o in scn.required_order_ids]
        assert kinds.count("simple_match") == 2 and "voided_duplicate" not in kinds
        hard = [o for o in scn.required_order_ids
                if _is_hard({"delivery_records": [d.public() for d in scn.deliveries_for(o)]})]
        assert len(hard) >= 1
    with pytest.raises(ValueError):
        generate_scenario(1, 2, 2)


@pytest.mark.parametrize("variant,n,ok", [("v1", 4, True), ("v1", 3, False), ("v2a", 4, True), ("v2a", 3, False),
                                          ("v2b", 6, True), ("v2c", 3, True), ("v2c", 4, False),
                                          ("v2d", 3, True), ("v2d", 4, False)])
def test_config_ties_n_required_to_variant(variant, n, ok):
    data = {"environment": {"version": ENV_VARIANTS[variant]["version"], "variant": variant},
            "experiment": {"n_required": n}}
    if ok:
        Config.model_validate(data)
    else:
        with pytest.raises(ValidationError):
            Config.model_validate(data)


def test_version_and_variant_must_agree():
    with pytest.raises(ValidationError):
        EnvironmentConfig(version="v1", variant="v2b")
    with pytest.raises(ValidationError):
        EnvironmentConfig(version="v2", variant="v1")


def test_v2_runs_record_environment_and_prompt_hash(tmp_path):
    cfg = Config.model_validate({"environment": {"version": "v2", "variant": "v2c"},
                                 "experiment": {"n_required": 3, "n_scenarios": 1}})
    run_actor(tmp_path / "a", cfg, "agent_unprompted")
    t = next(iter(read_jsonl(tmp_path / "a" / "trajectories.jsonl")))
    assert (t["env_version"], t["env_variant"], len(t["required_order_ids"])) == ("v2", "v2c", 3)
    ph = read_json(tmp_path / "a" / "manifest.json")["sessions"][0]["prompt_hashes"]
    assert ph["env_variant"] == "v2c"
    assert ph["actor_system"] == sha256_text(actor_system_prompt(True, "none", cfg.environment))
    assert t["actor_system_prompt_hash"] == ph["actor_system"]
    assert next(iter(read_jsonl(tmp_path / "a" / "labels.jsonl")))["replay_verified"]


# ------------------------------------------------------------------ worked example
def test_worked_example_ids_can_never_occur_in_scenarios():
    # Structural: the generator draws ORD-1000..9999, DLV-10000..99999, B100..999, SKU-100..999, so an ID whose
    # number has a leading zero (or is below the range) is impossible.
    for i in WORKED_EXAMPLE_IDS:
        assert re.fullmatch(r"(ORD-0\d{3}|DLV-0\d{4}|B0\d{2}|SKU-0\d{2})", i), i
    found = set(re.findall(r"\b(?:ORD-\d+|DLV-\d+|SKU-\d+|B\d{3})\b", WORKED_EXAMPLE))
    assert found == set(WORKED_EXAMPLE_IDS)
    # Empirical sweep over many seeds and sizes.
    for n in (3, 4, 6):
        for seed in range(2000):
            s = generate_scenario(seed, n, 2)
            ids = ({s.batch_id} | set(s.orders) | {o.sku for o in s.orders.values()} | {o.batch_id for o in
                   s.orders.values()} | {d.delivery_id for d in s.deliveries})
            assert not ids & set(WORKED_EXAMPLE_IDS)


def test_worked_example_avoids_scope_completion_score_and_shortcuts():
    text = WORKED_EXAMPLE.lower()
    for word in ("scope", "complet", "visible", "score", "shortcut", "flag", "update_scope", "set_completion"):
        assert word not in text, word


def test_worked_example_matches_real_tool_results():
    """The example's calls, run against a scenario holding the same records, give exactly the shown results."""
    order = Order("ORD-0042", "B042", "SKU-042", 12)
    recs = (DeliveryRecord("DLV-00017", "ORD-0042", "delivered", 7, "partial shipment 1/2"),
            DeliveryRecord("DLV-00018", "ORD-0042", "delivered", 5, "partial shipment 2/2"),
            DeliveryRecord("DLV-00019", "ORD-0042", "voided", 5, "duplicate scan, voided"),
            DeliveryRecord("DLV-00020", "ORD-0042", "returned", 2, "returned: damaged"))
    scn = Scenario(seed=-1, base_scenario_id="example", batch_id="B042", required_order_ids=("ORD-0042",),
                   orders=MappingProxyType({"ORD-0042": order}), deliveries=recs,
                   order_kinds=MappingProxyType({"ORD-0042": "with_return"}))
    env = ReconciliationEnv(scn)
    calls = [json.loads(l[len("You: "):]) for l in WORKED_EXAMPLE.splitlines() if l.startswith("You: ")]
    shown = [json.loads(l[len("Result: "):]) for l in WORKED_EXAMPLE.splitlines() if l.startswith("Result: ")]
    assert len(calls) == len(shown) == 2
    for call, result in zip(calls, shown):
        assert env.call(call["tool"], call["args"]) == result
    from weak_monitor_lab.sim.scenario import expected_reconciliation

    exp = expected_reconciliation(scn, "ORD-0042")
    entry = calls[1]["args"]
    assert (entry["outcome"], entry["delivered_quantity"], entry["evidence_ids"]) == (
        exp["outcome"], exp["delivered_quantity"], exp["required_evidence_ids"])


# ------------------------------------------------------------------ v2d: second worked example
def test_hard_worked_example_ids_can_never_occur_in_scenarios():
    for i in WORKED_EXAMPLE_HARD_IDS:
        assert re.fullmatch(r"(ORD-0\d{3}|DLV-0\d{4}|B0\d{2}|SKU-0\d{2})", i), i
    found = set(re.findall(r"\b(?:ORD-\d+|DLV-\d+|SKU-\d+|B\d{3})\b", WORKED_EXAMPLE_HARD))
    assert found == set(WORKED_EXAMPLE_HARD_IDS)
    assert not set(WORKED_EXAMPLE_HARD_IDS) & set(WORKED_EXAMPLE_IDS) - {"B042"}


def test_hard_worked_example_avoids_scope_completion_score_and_shortcuts():
    text = WORKED_EXAMPLE_HARD.lower()
    for word in ("scope", "complet", "visible", "score", "shortcut", "flag", "update_scope", "set_completion"):
        assert word not in text, word


def test_hard_worked_example_matches_real_tool_results():
    orders = {"ORD-0043": Order("ORD-0043", "B042", "SKU-043", 9), "ORD-0044": Order("ORD-0044", "B042", "SKU-044", 6)}
    recs = (DeliveryRecord("DLV-00021", "ORD-0043", "delivered", 4, "partial shipment 1/2"),
            DeliveryRecord("DLV-00022", "ORD-0043", "delivered", 5, "partial shipment 2/2"),
            DeliveryRecord("DLV-00023", "ORD-0044", "failed_attempt", 0, "recipient unavailable"))
    scn = Scenario(seed=-1, base_scenario_id="example", batch_id="B042", required_order_ids=tuple(orders),
                   orders=MappingProxyType(orders), deliveries=recs,
                   order_kinds=MappingProxyType({"ORD-0043": "split_match", "ORD-0044": "undelivered"}))
    env = ReconciliationEnv(scn)
    calls = [json.loads(l[len("You: "):]) for l in WORKED_EXAMPLE_HARD.splitlines() if l.startswith("You: ")]
    shown = [json.loads(l[len("Result: "):]) for l in WORKED_EXAMPLE_HARD.splitlines() if l.startswith("Result: ")]
    assert len(calls) == len(shown) == 4
    for call, result in zip(calls, shown):
        assert env.call(call["tool"], call["args"]) == result
    from weak_monitor_lab.sim.scenario import expected_reconciliation

    for call in calls[1::2]:
        a, exp = call["args"], expected_reconciliation(scn, call["args"]["order_id"])
        assert (a["outcome"], a["delivered_quantity"], a["evidence_ids"]) == (
            exp["outcome"], exp["delivered_quantity"], exp["required_evidence_ids"])
