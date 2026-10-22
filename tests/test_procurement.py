"""Exact fixed-demand purchasing comparisons and source-bound job publication."""
from collections import Counter
from contextlib import contextmanager
import copy
from fractions import Fraction as Q
import json
from pathlib import Path

import pytest

from oma.procurement import (SCHEMA, build_purchasing_scenarios, fabrication_pieces,
                             optimize_procurement_run, validate_policy)
from oma.store import IntegrityError, Store
from oma.worker import Cancelled
from test_service_takeoff import Source


def policy(**updates):
    return {"stock_lengths_m": ["10"], "kerf_m": "0", "end_trim_m": "0",
            "cut_increment_m": "1/1000", "long_segments": "ASSUME_FABRICATION_SPLITS",
            "unit_price_per_m": {"low": "2", "central": "3", "high": "5"},
            "assumptions": "Cutting and end preparation permitted under this test scenario.",
            "price_basis": "Caller-supplied material price scenario, not a contractor quote.", **updates}


def piece(ident="a", length="3", group="g", batch="n1", source="s", kind="PIPE"):
    return {"id": ident, "length_m": length, "stock_group": group, "network_id": batch,
            "source_id": source, "stock_kind": kind}


def plan(pieces, policies=None, overrides=None):
    return build_purchasing_scenarios([{"source_sha256": "s", "pieces": pieces}],
        {"PIPE": policy()} if policies is None else policies, overrides or {},
        currency="USD", node_budget=5000, checkpoint=lambda stage: None)


@pytest.mark.parametrize("length,required,lengths,allowance,splices", [
    ("1/3", "167/500", ["167/500"], "1/1500", 0),
    ("10", "10", ["999/100", "1/100"], "0", 1),
    ("19981/1000", "19981/1000", ["999/100", "999/100", "1/1000"], "0", 2),
])
def test_fabrication_exact_upward_rounding_and_fixed_splits(length, required, lengths, allowance, splices):
    pol = validate_policy(policy(kerf_m="3/1000", end_trim_m="7/1000"))
    out = fabrication_pieces(piece(length=length), pol)
    assert out["required_length_m"] == required
    assert [p["length_m"] for p in out["pieces"]] == lengths
    assert out["rounding_allowance_m"] == allowance
    assert out["assumed_additional_splices"] == splices
    assert all(p["source_id"] == "s" and p["batch_id"] == "n1" for p in out["pieces"])
    assert len({p["id"] for p in out["pieces"]}) == len(lengths)


def test_oversize_retained_and_split_workload_bounded():
    pol = validate_policy(policy(long_segments="RETAIN_OVERSIZE"))
    assert fabrication_pieces(piece(length="11"), pol)["status"] == "RETAINED_OVERSIZE"
    with pytest.raises(ValueError, match="workload"):
        fabrication_pieces(piece(length="21"), validate_policy(policy()), maximum_pieces=2)


@pytest.mark.parametrize("update", [
    {"stock_lengths_m": []}, {"stock_lengths_m": [0]}, {"stock_lengths_m": [True]},
    {"stock_lengths_m": ["NaN"]}, {"stock_lengths_m": ["inf"]},
    {"kerf_m": "-1"}, {"kerf_m": "10"}, {"end_trim_m": "-1"},
    {"cut_increment_m": "0"}, {"cut_increment_m": "11"},
    {"long_segments": "guess"}, {"assumptions": ""}, {"price_basis": " "},
    {"unit_price_per_m": {"low": 2, "central": 1, "high": 3}},
    {"unit_price_per_m": {"low": 1, "central": 2}},
    {"unit_price_per_m": {"low": -1, "central": 2, "high": 3}},
    {"unexpected": True},
])
def test_invalid_policy_rejected(update):
    with pytest.raises(ValueError):
        validate_policy(policy(**update))


def test_all_three_plans_use_identical_demand_and_exact_material_prices():
    pieces = [piece("a", "6", batch="first"), piece("b", "4", batch="second")]
    out = plan(pieces)
    group, = out["groups"]
    for name, result in group["optimization"]["plans"].items():
        demand = Counter((p["piece_id"], p["source_id"], p["length_m"])
                         for b in result["bins"] for p in b["cuts"])
        assert demand == Counter([("a/fabrication/0", "s", "6"), ("b/fabrication/0", "s", "4")])
        assert result["totals"]["required_length_m"] == "10"
        assert group["optimization"]["verification"][name]["status"] == "PASS"
    comparisons = out["comparisons"]
    assert comparisons["per_batch_scenario"]["purchased_length_m"] == "20"
    assert comparisons["baseline"]["purchased_length_m"] == comparisons["selected"]["purchased_length_m"] == "10"
    assert comparisons["improvement_vs_per_batch_scenario"]["estimated_material_saving"] == {"low": "20", "central": "30", "high": "50"}
    assert comparisons["improvement_vs_baseline"]["estimated_material_saving"] == {"low": "0", "central": "0", "high": "0"}
    assert not out["geometry_or_duty_changes"]


def test_unpriced_groups_remain_quantified_without_fictitious_money():
    out = plan([piece()], {"PIPE": policy(unit_price_per_m=None)})
    group, = out["groups"]
    assert all(v["material_price_scenarios"] is None for v in group["plans"].values())
    assert group["optimization"]["inputs"]["currency"] is None
    assert out["comparisons"]["selected"]["unpriced_group_count"] == 1
    assert out["comparisons"]["selected"]["priced_group_count"] == 0


def test_missing_policy_and_oversize_are_retained_and_accounting_closes():
    out = plan([piece("a", "5"), piece("b", "11"), piece("c", "1", group="duct", kind="DUCT_CIRCULAR")],
               {"PIPE": policy(long_segments="RETAIN_OVERSIZE")})
    assert out["measured_piece_count"] == 3 and out["planned_original_piece_count"] == 1
    assert {p["piece_id"]: p["reason"] for p in out["excluded_measured_pieces"]} == {
        "b": "OVERSIZE_SPAN_RETAINED", "c": "NO_DECLARED_STOCK_POLICY"}


def test_empty_policy_never_implies_complete_optimized_quantities():
    out = plan([piece()], {})
    assert out["groups"] == [] and out["planned_original_piece_count"] == 0
    assert out["comparisons"]["improvement_vs_baseline"]["purchased_length_reduction_percent"] is None


def test_explicit_group_policy_overrides_kind_policy():
    out = plan([piece()], overrides={"g": policy(stock_lengths_m=["6"])})
    assert out["groups"][0]["plans"]["selected"]["purchased_length_m"] == "6"


@pytest.mark.parametrize("attack", ["duplicate", "source", "group_source", "group_kind", "absent_override"])
def test_corrupt_piece_or_group_bindings_rejected(attack):
    pieces = [piece()]
    overrides = {}
    if attack == "duplicate": pieces.append(piece())
    if attack == "source": pieces[0]["source_id"] = "other"
    if attack == "group_kind": pieces.append(piece("b", kind="OTHER"))
    if attack == "absent_override": overrides["absent"] = policy()
    if attack == "group_source":
        takeoffs = [{"source_sha256": "s", "pieces": pieces}, {"source_sha256": "other", "pieces": [piece("b", source="other")]}]
    else:
        takeoffs = [{"source_sha256": "s", "pieces": pieces}]
    with pytest.raises((ValueError, IntegrityError)):
        build_purchasing_scenarios(takeoffs, {"PIPE": policy(), "OTHER": policy()}, overrides,
            currency="USD", node_budget=10, checkpoint=lambda stage: None)


class Control:
    def checkpoint(self, stage):
        pass


def project(tmp_path):
    store = Store(tmp_path / "store")
    sources = []
    for name, kind in [("mechanical", "IfcPipeSegment"), ("electrical", "IfcCableSegment")]:
        directory = tmp_path / name
        directory.mkdir()
        model = Source(directory)
        for length in (6, 4): model.segment(depth=length, kind=kind)
        audit = model.write()
        sha = audit["source_sha256"]
        sources.append({"id": sha, "sha256": sha, "name": name + ".ifc", "immutable_path": str(model.path), "audit_root": store.put(audit)})
    state = {"sources": sources, "entities": []}
    p = store.create_project("whole building", state)
    state["project_id"] = p["id"]
    return store, p, state


def request(state):
    return {"operation": "optimize_procurement", "budget_seconds": 30, "mission": {
        "schema": SCHEMA, "source_disciplines": {s["id"]: "HVAC" if i == 0 else "ELECTRICAL" for i, s in enumerate(state["sources"])},
        "stock_policies": {"PIPE": policy(), "CABLE": policy()}, "group_policies": {},
        "currency": "USD", "search_node_budget": 1000}}


def test_actual_ifc_whole_project_job_preserves_sources_revision_and_every_quantity(tmp_path):
    store, p, state = project(tmp_path)
    before = store.project(p["id"])
    bytes_before = {s["id"]: Path(s["immutable_path"]).read_bytes() for s in state["sources"]}
    run = store.create_run(p["id"], request(state))
    out = optimize_procurement_run(store, run, Control())
    assert out["summary"]["source_count"] == 2 and out["summary"]["flow_segment_count"] == 4
    assert out["summary"]["planned_original_piece_count"] == 4
    assert out["comparisons"]["selected"]["required_length_m"] == "20"
    assert out["comparisons"]["improvement_vs_per_batch_scenario"]["purchased_length_reduction_m"] == "20"
    assert store.project(p["id"]) == before and not store.candidates(p["id"])
    assert store.run(run["id"])["status"] == "COMPLETED"
    assert out["network_engineering_verdict"] == "NOT_RUN" and not out["construction_approval"]
    assert not out["original_installed_geometry_changed"] and not out["whole_building_networks_redesigned"]
    assert bytes_before == {s["id"]: Path(s["immutable_path"]).read_bytes() for s in state["sources"]}
    events = [e for e in store.events(p["id"]) if e["stage"] == "procurement_complete"]
    assert len(events) == 1
    assert store.get(events[0]["payload"]["procurement_artifact_root"]) == out


@pytest.mark.parametrize("attack", ["scope", "source_bytes", "audit_source", "source_alias", "source_duplicate", "unknown_label", "stale_project", "run_argument", "empty_sources"])
def test_invalid_source_request_or_project_binding_does_not_publish(tmp_path, attack):
    store, p, state = project(tmp_path)
    req = request(state)
    if attack == "scope": req["scope"] = [state["sources"][0]["id"]]
    if attack == "source_bytes": Path(state["sources"][0]["immutable_path"]).write_text("changed")
    if attack == "audit_source":
        audit = store.get(state["sources"][0]["audit_root"])
        audit["source_sha256"] = "0" * 64
        state["sources"][0]["audit_root"] = store.put(audit)
    if attack == "source_alias": state["sources"][0]["id"] = "alias"
    if attack == "source_duplicate": state["sources"].append(copy.deepcopy(state["sources"][0]))
    if attack == "empty_sources": state["sources"] = []; req["mission"]["source_disciplines"] = {}
    if attack in {"audit_source", "source_alias", "source_duplicate", "empty_sources"}:
        store.publish(p["id"], state, 0, "altered state")
    if attack == "unknown_label": req["mission"]["source_disciplines"] = {"missing": "HVAC"}
    run = store.create_run(p["id"], req)
    if attack == "stale_project": store.publish(p["id"], state, 0, "changed before run")
    if attack == "run_argument": run["request"]["seed"] = 123
    with pytest.raises((ValueError, IntegrityError)):
        optimize_procurement_run(store, run, Control())
    assert store.run(run["id"])["status"] != "COMPLETED"
    assert not any(e["stage"] == "procurement_complete" for e in store.events(p["id"]))


@pytest.mark.parametrize("attack", ["cancel_callback", "cancel_db", "pause_db", "late_ifc", "request", "project", "time_budget"])
def test_late_mutation_cancellation_or_deadline_cannot_publish(tmp_path, monkeypatch, attack):
    store, p, state = project(tmp_path)
    run = store.create_run(p["id"], request(state))
    class Mutate:
        def checkpoint(self, stage):
            if stage != "procurement_complete": return
            if attack == "cancel_callback": raise Cancelled()
            if attack == "cancel_db": store.control(run["id"], "cancel")
            if attack == "pause_db": store.control(run["id"], "pause")
            if attack == "late_ifc": Path(state["sources"][0]["immutable_path"]).write_text("changed at final callback")
            if attack == "request":
                altered = copy.deepcopy(run["request"]); altered["seed"] = 22
                with store.transaction() as db:
                    db.execute("UPDATE runs SET request=? WHERE id=?", (json.dumps(altered), run["id"]))
            if attack == "project": store.publish(p["id"], state, 0, "changed during run")
            if attack == "time_budget": monkeypatch.setattr("oma.procurement.time.monotonic", lambda: float("inf"))
    import subprocess
    with pytest.raises((Cancelled, IntegrityError, subprocess.TimeoutExpired)):
        optimize_procurement_run(store, run, Mutate())
    assert store.run(run["id"])["status"] != "COMPLETED"
    assert not any(e["stage"] == "procurement_complete" for e in store.events(p["id"]))
    assert not store.candidates(p["id"])


@pytest.mark.parametrize("attack", ["project", "request", "operation", "cancel", "pause"])
def test_publication_rechecks_project_request_and_control_inside_atomic_transaction(tmp_path, monkeypatch, attack):
    store, p, state = project(tmp_path)
    run = store.create_run(p["id"], request(state))
    transaction = store.transaction
    armed = False

    @contextmanager
    def racing_transaction():
        with transaction() as db:
            if armed:
                if attack == "project":
                    db.execute("UPDATE projects SET revision=revision+1 WHERE id=?", (p["id"],))
                if attack == "request":
                    db.execute("UPDATE runs SET request=? WHERE id=?", (json.dumps({**run["request"], "seed": 777}), run["id"]))
                if attack == "operation":
                    db.execute("UPDATE runs SET operation='check' WHERE id=?", (run["id"],))
                if attack in {"cancel", "pause"}:
                    db.execute("UPDATE runs SET desired_action=? WHERE id=?", (attack, run["id"]))
            yield db

    class Arm:
        def checkpoint(self, stage):
            nonlocal armed
            if stage == "procurement_complete": armed = True

    monkeypatch.setattr(store, "transaction", racing_transaction)
    with pytest.raises((IntegrityError, Cancelled)):
        optimize_procurement_run(store, run, Arm())
    assert store.run(run["id"])["status"] != "COMPLETED"
    assert not any(e["stage"] == "procurement_complete" for e in store.events(p["id"]))


def test_api_accepts_procurement_operation(tmp_path):
    from fastapi.testclient import TestClient
    from oma.api import create_app
    app = create_app(tmp_path / "api", recover=False)
    app.state.engine.schedule = lambda run_id: None
    p = app.state.engine.store.create_project("request", {"sources": []})
    with TestClient(app) as client:
        response = client.post(f"/api/projects/{p['id']}/runs", json={"operation": "optimize_procurement", "mission": {"schema": SCHEMA}})
    assert response.status_code == 202 and response.json()["operation"] == "optimize_procurement"
