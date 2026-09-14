"""Actual native unequal-tree mission admission, service and fresh export."""
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
from test_network_scenario import network_scenario
from test_network_pressure import pressure_scenario
from test_network_integration import imported_project
from test_passive_tree_integration import passive_tree_scenario


def coupled_tree_scenario():
    # A separately authored boundary on the same analytic physical fixture.
    raw = passive_tree_scenario()
    raw.pop("passive_tree")
    raw["coupled_tree"] = json.loads((Path(__file__).parent / "fixtures/coupled-native-tree/boundary.json").read_text(encoding="utf8"))
    return raw


@pytest.mark.parametrize("kind", ["fixed_flow", "two_sink", "common_tee"])
def test_new_coupled_mode_preserves_older_serialized_missions(kind):
    raw = {"fixed_flow": network_scenario, "two_sink": pressure_scenario, "common_tee": passive_tree_scenario}[kind]()
    scenario = SharedNetworkScenario.model_validate(raw)
    normalized = scenario.model_dump(mode="json", by_alias=True)
    assert "coupled_tree" not in normalized
    assert SharedNetworkScenario.model_validate(normalized).model_dump(mode="json", by_alias=True) == normalized
    previous = json.loads((Path(__file__).parent / "fixtures/coupled-native-tree/legacy-contracts.json").read_text(encoding="utf8"))["cases"][kind]
    assert normalized == previous["scenario"]
    assert list(network_requirements({}, scenario)) == previous["requirements"]


@pytest.mark.parametrize("fault", ["legacy_flow", "static_budget", "fixed_physics", "two_sink", "common_tee", "local_scope", "duct", "missing_sink", "extra_tee", "missing_box"])
def test_coupled_boundary_rejects_ambiguous_or_incomplete_authority(fault):
    raw = coupled_tree_scenario()
    if fault == "legacy_flow": raw["sinks"][0]["required_flow_m3_s"] = .001
    if fault == "static_budget": raw["sinks"][0]["available_static_pressure_pa"] = 10
    if fault == "fixed_physics": raw["physics"] = network_scenario()["physics"]
    if fault == "two_sink": raw["pressure_driven"] = pressure_scenario()["pressure_driven"]
    if fault == "common_tee": raw["passive_tree"] = passive_tree_scenario()["passive_tree"]
    if fault == "local_scope": raw["target_modality"] = "LOCAL_GEOMETRIC_COORDINATION"
    if fault == "duct": raw["system_type"] = "ROUND_DUCT"
    if fault == "missing_sink": raw["coupled_tree"]["sink_total_pressures_pa"].pop("sink-a")
    if fault == "extra_tee": raw["coupled_tree"]["tee_outlet_loss_coefficients"]["fabricated"] = {"b":"1/5","branch":"1/3"}
    if fault == "missing_box": raw["coupled_tree"]["flow_search_box_m3_s"].pop("sink-a")
    with pytest.raises(ValidationError):
        SharedNetworkScenario.model_validate(raw)


def test_exact_coupled_minimum_and_search_box_bind_the_mission():
    raw = coupled_tree_scenario()
    first, _, _ = network_requirements({}, SharedNetworkScenario.model_validate(raw))
    raw["coupled_tree"]["minimum_sink_flows_m3_s"]["sink-a"] = str(Fraction(raw["coupled_tree"]["minimum_sink_flows_m3_s"]["sink-a"])+Fraction(1,10**40))
    second, _, _ = network_requirements({}, SharedNetworkScenario.model_validate(raw))
    assert first["demands"][0]["required_flow_m3_s"] == second["demands"][0]["required_flow_m3_s"]
    assert first["rule_hash"] != second["rule_hash"]
    raw["coupled_tree"]["flow_search_box_m3_s"]["sink-a"]["lower"] = "1/1000"
    third, _, _ = network_requirements({}, SharedNetworkScenario.model_validate(raw))
    assert third["rule_hash"] != second["rule_hash"] and third["scenario_hash"] != second["scenario_hash"]


def run_native(tmp_path, raw):
    store, project = imported_project(tmp_path)
    run = store.create_run(project["id"], {"operation":"optimize","mission":raw,"budget_seconds":90})
    route_project_run(store, run, WorkerControl(store,run["id"]))
    candidate, = store.candidates(project["id"])
    assert candidate["report_root"] is not None, store.run(run["id"])
    report = store.get(candidate["report_root"])
    return store, project, store.run(run["id"]), candidate, report, {r["id"]:r for r in report["results"]}


def test_native_unequal_tree_local_global_service_accept_and_fresh_export(tmp_path):
    store, project, run, candidate, report, rows = run_native(tmp_path,coupled_tree_scenario())
    assert candidate["status"] == "CHECKED" and report["status"] == "PASS", report
    assert run["status"] == "COMPLETED"
    calc = rows["network-demand-conditioned-service"]["witness"]["calculation"]
    check = calc["independent_check"]
    assert calc["status"] == "CERTIFIED_ENVELOPE" and calc["proof_complete"] is True
    assert rows["network-pressure-operating-point"]["status"] == "PASS"
    assert check["status"] == check["local_check"]["status"] == check["global_check"]["status"] == check["verdict"] == "PASS"
    service = check["service"]
    assert len(service["physical_ports"]) == 16 and len(service["deliveries"]) == 3
    assert len(service["conservation_identities"]) == 17
    assert all(p["forward_status"] == p["maximum_velocity_status"] == "PASS" for p in service["physical_ports"])
    state = store.get(candidate["state_root"])
    original = store.resolve_path(state["sources"][0]["immutable_path"])
    original_sha = sha256_file(original)
    expected = _complete_check_obligations(store,state,store.get(run["base_root"]),"physical_network")
    assert expected["network-pressure-operating-point"] == expected["network-demand-conditioned-service"] == "PASS"
    cad = store.get(rows["network-all-component-pairs"]["witness"]["artifact"])
    assert cad["route_count"] == cad["pairs_accounted"] == 7
    assert len(cad["self_pair_results"]) == 21
    from oma.project_assurance import candidate_assurance
    assurance = candidate_assurance(store,candidate["id"])
    assert any("coupled_tree_network_boundary_inputs" in x["statement"] for x in assurance["assumption_ledger"])
    for fault in ("missing_operating", "service_na"):
        forged = copy.deepcopy(report)
        if fault == "missing_operating": forged["results"] = [r for r in forged["results"] if r["id"]!="network-pressure-operating-point"]
        else: next(r for r in forged["results"] if r["id"]=="network-demand-conditioned-service")["status"]="NOT_APPLICABLE"
        with pytest.raises(IntegrityError):
            validate_physical_report_admission(store,candidate,run,state,store.get(run["base_root"]),forged)
    accepted = store.accept(project["id"],candidate["id"],1,"accept-coupled-tree",checker_version=checker_version())
    assert accepted["revision"] == 2
    exported = export_project(store,project["id"],candidate["id"],draft=False,budget_seconds=90)
    assert exported["status"] == "CHECKED_LOCAL_SCOPE" and exported["round_trip"] == "PASS", exported
    manifest = store.get(exported["artifact_root"])
    fresh = store.get(manifest["verification_root"])
    assert fresh["status"] == "PASS" and fresh["candidate_root"] != report["candidate_root"]
    fresh_rows = {r["id"]:r for r in fresh["results"]}
    fresh_check = fresh_rows["network-demand-conditioned-service"]["witness"]["calculation"]["independent_check"]
    assert fresh_check["model_root"] != check["model_root"]
    assert fresh_check["service"]["deliveries"] == service["deliveries"]
    assert sha256_file(original) == original_sha


@pytest.mark.parametrize("fault", ["delivery", "velocity", "wrong_search_box", "reverse_pressure"])
def test_native_geometry_cannot_override_bad_or_uncertified_coupled_service(tmp_path,fault):
    raw = coupled_tree_scenario()
    boundary = raw["coupled_tree"]
    if fault == "delivery": boundary["minimum_sink_flows_m3_s"]["sink-a"]="1"
    if fault == "velocity": boundary["maximum_velocity_m_s"]="1/1000"
    if fault == "wrong_search_box": boundary["flow_search_box_m3_s"]={k:{"lower":"1","upper":"2"} for k in boundary["flow_search_box_m3_s"]}
    if fault == "reverse_pressure": boundary["source_total_pressure_pa"]={"lower":"-100","upper":"-100"}
    store,project,run,candidate,report,rows = run_native(tmp_path,raw)
    assert rows["network-all-source-clearance"]["status"] == rows["network-all-component-pairs"]["status"] == "PASS"
    if fault in ("delivery","velocity"):
        assert rows["network-pressure-operating-point"]["status"] == "PASS",report
        assert rows["network-demand-conditioned-service"]["status"] == "FAIL",report
    else:
        assert rows["network-pressure-operating-point"]["status"] == "UNKNOWN",report
        assert rows["network-demand-conditioned-service"]["status"] == "UNKNOWN",report
    assert candidate["status"] == "REJECTED" and run["status"] == "NO_INCUMBENT_FOUND"
    with pytest.raises(IntegrityError):
        store.accept(project["id"],candidate["id"],1,"reject-coupled-service",checker_version=checker_version())


def test_final_coupled_control_boundary_rejects_cancellation_before_publication(tmp_path,monkeypatch):
    from oma.routing import network_checker
    from oma.worker import Cancelled
    store,project,run,candidate,report,rows = run_native(tmp_path,coupled_tree_scenario())
    assert report["status"] == "PASS"
    fresh=store.create_run(project["id"],{"operation":"recheck","candidate_id":candidate["id"],"budget_seconds":90})
    control=WorkerControl(store,fresh["id"])
    forced=control.checkpoint
    reached=[]
    def cancel(stage="compute"):
        if stage=="network_coupled_envelope_complete":
            reached.append(stage); store.control(fresh["id"],"cancel")
        forced(stage)
    monkeypatch.setattr(control,"checkpoint",cancel)
    monkeypatch.setattr(network_checker,"candidate_control",lambda *_:control)
    with pytest.raises(Cancelled):
        network_checker.verify_network_candidate(store,candidate["id"])
    assert reached==["network_coupled_envelope_complete"]
    assert store.candidate(candidate["id"])["report_root"]==candidate["report_root"]
