"""Real native pressure-tree mission, admission and fresh exported-byte checks."""
import copy
from fractions import Fraction
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from oma.build_identity import checker_version
from oma.exporting import export_project
from oma.ifc.audit import sha256_file
from oma.routing.engine import route_project_run
from oma.routing.network_scenario import SharedNetworkScenario, network_requirements
from oma.routing.selection import _complete_check_obligations, validate_physical_report_admission
from oma.store import IntegrityError
from oma.worker import WorkerControl
from native_three_sink_fixture import three_sink_spec, ZONE
from test_network_integration import imported_project
from test_network_scenario import network_scenario
from test_network_pressure import pressure_scenario


def passive_tree_scenario():
    spec = three_sink_spec()
    boundary = json.loads((Path(__file__).parent / "fixtures/passive-native-tree/new-boundary-declaration.json").read_text(encoding="utf8"))
    components = {c["id"]: c for c in spec["components"]}
    return {"mission_type": "shared_network", "system_type": "PRESSURE_PIPE", "start_m": [-1, 4, 3],
        "sinks": [{"id": s["id"], "demand_id": "demand-" + s["id"][-1],
            "end_m": components[s["endpoint"]["component"]]["geometry"]["end_m"]} for s in spec["sinks"]],
        "diameter_m": .1, "insulation_m": .02, "clearance_m": .1,
        "minimum_straight_m": .05, "minimum_bend_radius_m": .1, "allowed_zone": copy.deepcopy(ZONE),
        "scenario_terminals": True, "target_modality": "ENGINEERING_SERVICE",
        "source_representation_policy": "NATIVE_CAD_WITH_EXACT_PLANAR_ENCLOSURES",
        "network_alternatives": [spec], "passive_tree": boundary}


@pytest.mark.parametrize("kind", ["fixed_flow", "two_sink_pressure"])
def test_passive_optional_contract_does_not_rewrite_old_missions(kind):
    raw = network_scenario() if kind == "fixed_flow" else pressure_scenario()
    actual = SharedNetworkScenario.model_validate(raw)
    assert "passive_tree" not in actual.model_dump(mode="json", by_alias=True)
    assert SharedNetworkScenario.model_validate(actual.model_dump(mode="json", by_alias=True)) == actual


@pytest.mark.parametrize("fault", ["legacy_flow", "static_budget", "fixed_physics", "two_sink", "local_scope", "duct", "missing_sink", "extra_tee"])
def test_passive_mission_rejects_ambiguous_or_incomplete_authority(fault):
    raw = passive_tree_scenario()
    if fault == "legacy_flow": raw["sinks"][0]["required_flow_m3_s"] = .001
    if fault == "static_budget": raw["sinks"][0]["available_static_pressure_pa"] = 10
    if fault == "fixed_physics": raw["physics"] = network_scenario()["physics"]
    if fault == "two_sink": raw["pressure_driven"] = pressure_scenario()["pressure_driven"]
    if fault == "local_scope": raw["target_modality"] = "LOCAL_GEOMETRIC_COORDINATION"
    if fault == "duct": raw["system_type"] = "ROUND_DUCT"
    if fault == "missing_sink": raw["passive_tree"]["sink_total_pressures_pa"].pop("sink-a")
    if fault == "extra_tee": raw["passive_tree"]["tee_common_loss_coefficients"]["fabricated-tee"] = "1/5"
    with pytest.raises(ValidationError):
        SharedNetworkScenario.model_validate(raw)


def test_exact_passive_minimum_is_bound_even_when_float_projection_is_unchanged():
    raw = passive_tree_scenario()
    first = SharedNetworkScenario.model_validate(raw)
    a, _, _ = network_requirements({}, first)
    raw["passive_tree"]["minimum_sink_flows_m3_s"]["sink-a"] = str(Fraction(1, 1000) + Fraction(1, 10**40))
    second = SharedNetworkScenario.model_validate(raw)
    b, _, _ = network_requirements({}, second)
    assert a["demands"][0]["required_flow_m3_s"] == b["demands"][0]["required_flow_m3_s"]
    assert a["rule_hash"] != b["rule_hash"] and a["scenario_hash"] != b["scenario_hash"]


def run_native(tmp_path, raw):
    store, project = imported_project(tmp_path)
    run = store.create_run(project["id"], {"operation": "optimize", "mission": raw, "budget_seconds": 90})
    route_project_run(store, run, WorkerControl(store, run["id"]))
    candidate, = store.candidates(project["id"])
    report = store.get(candidate["report_root"])
    rows = {r["id"]: r for r in report["results"]}
    return store, project, store.run(run["id"]), candidate, report, rows


def test_native_three_sink_pressure_select_accept_export_and_current_certificate(tmp_path):
    store, project, run, candidate, report, rows = run_native(tmp_path, passive_tree_scenario())
    assert candidate["status"] == "CHECKED" and report["status"] == "PASS", report
    assert run["status"] == "COMPLETED"
    state = store.get(candidate["state_root"])
    original = store.resolve_path(state["sources"][0]["immutable_path"])
    original_sha = sha256_file(original)
    assert rows["network-pressure-operating-point"]["status"] == "PASS"
    calc = rows["network-demand-conditioned-service"]["witness"]["calculation"]
    assert calc["status"] == "CERTIFIED_ENVELOPE" and calc["proof_complete"] is True
    independent = calc["independent_check"]
    assert independent["status"] == independent["verdict"] == "PASS"
    service = independent["service"]
    assert len(service["physical_ports"]) == 16 and len(service["deliveries"]) == 3
    assert len(service["conservation_identities"]) == 17
    assert all(p["forward_status"] == p["maximum_velocity_status"] == "PASS" for p in service["physical_ports"])
    cad = store.get(rows["network-all-component-pairs"]["witness"]["artifact"])
    pairs = cad["self_pair_results"]
    assert cad["route_count"] == cad["pairs_accounted"] == 7
    assert len(pairs) == len({tuple(sorted(p["participants"])) for p in pairs}) == 21
    expected = _complete_check_obligations(store, state, store.get(run["base_root"]), "physical_network")
    assert expected["network-pressure-operating-point"] == expected["network-demand-conditioned-service"] == "PASS"
    from oma.project_assurance import candidate_assurance
    assurance = candidate_assurance(store, candidate["id"])
    assert any("passive_tree_network_boundary_inputs" in x["statement"] for x in assurance["assumption_ledger"])
    for fault in ("missing_pressure", "service_na"):
        forged = copy.deepcopy(report)
        if fault == "missing_pressure": forged["results"] = [r for r in forged["results"] if r["id"] != "network-pressure-operating-point"]
        else: next(r for r in forged["results"] if r["id"] == "network-demand-conditioned-service")["status"] = "NOT_APPLICABLE"
        with pytest.raises(IntegrityError):
            validate_physical_report_admission(store, candidate, run, state, store.get(run["base_root"]), forged)
    accepted = store.accept(project["id"], candidate["id"], 1, "accept-passive-tree", checker_version=checker_version())
    assert accepted["revision"] == 2
    exported = export_project(store, project["id"], candidate["id"], draft=False, budget_seconds=90)
    assert exported["status"] == "CHECKED_LOCAL_SCOPE" and exported["round_trip"] == "PASS", exported
    manifest = store.get(exported["artifact_root"])
    fresh = store.get(manifest["verification_root"])
    assert fresh["status"] == "PASS" and fresh["candidate_root"] != report["candidate_root"]
    fresh_rows = {r["id"]: r for r in fresh["results"]}
    fresh_calc = fresh_rows["network-demand-conditioned-service"]["witness"]["calculation"]
    assert fresh_calc["independent_check"]["model_root"] != independent["model_root"]
    assert fresh_calc["independent_check"]["service"]["deliveries"] == service["deliveries"]
    assert sha256_file(original) == original_sha


@pytest.mark.parametrize("fault", ["delivery", "velocity", "reverse_pressure"])
def test_valid_native_geometry_and_pressure_proof_cannot_override_failed_service(tmp_path, fault):
    raw = passive_tree_scenario()
    if fault == "delivery": raw["passive_tree"]["minimum_sink_flows_m3_s"]["sink-a"] = "1"
    if fault == "velocity": raw["passive_tree"]["maximum_velocity_m_s"] = "1/1000"
    if fault == "reverse_pressure": raw["passive_tree"]["source_total_pressure_pa"] = "-100"
    store, project, run, candidate, report, rows = run_native(tmp_path, raw)
    assert rows["network-all-source-clearance"]["status"] == rows["network-all-component-pairs"]["status"] == "PASS"
    assert rows["network-pressure-operating-point"]["status"] == "PASS", report
    assert rows["network-demand-conditioned-service"]["status"] == "FAIL", report
    assert candidate["status"] == "REJECTED" and run["status"] == "NO_INCUMBENT_FOUND"
    with pytest.raises(IntegrityError):
        store.accept(project["id"], candidate["id"], 1, "reject-passive-service", checker_version=checker_version())
