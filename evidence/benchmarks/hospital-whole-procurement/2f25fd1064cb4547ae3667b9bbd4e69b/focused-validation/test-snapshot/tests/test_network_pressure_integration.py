"""Actual native IFC and managed report/accept/export use the operating solver."""
import copy

import pytest

from oma.build_identity import checker_version
from oma.exporting import export_project
from oma.routing.engine import route_project_run
from oma.routing.selection import _complete_check_obligations
from oma.store import IntegrityError
from oma.worker import WorkerControl
from test_network_integration import imported_project
from test_network_pressure import pressure_scenario


def test_native_pressure_network_select_accept_export_recomputes_complete_operating_relation(tmp_path):
    store, project = imported_project(tmp_path)
    raw = pressure_scenario()
    run = store.create_run(project["id"], {"operation": "optimize", "mission": raw, "budget_seconds": 90})
    route_project_run(store, run, WorkerControl(store, run["id"]))
    candidate, = store.candidates(project["id"])
    report = store.get(candidate["report_root"])
    assert candidate["status"] == "CHECKED" and report["status"] == "PASS", report
    assert store.run(run["id"])["status"] == "COMPLETED"
    by_id = {r["id"]: r for r in report["results"]}
    assert by_id["network-pressure-operating-point"]["status"] == "PASS"
    calculation = by_id["network-demand-conditioned-service"]["witness"]["calculation"]
    assert calculation["independent_check"]["status"] == calculation["operating_point_status"] == "PASS"
    assert len(calculation["derivation"]["partition"]["component_ids"]) == 4
    assert sum(len(p) for p in calculation["component_velocities"].values()) == 9
    state = store.get(candidate["state_root"])
    expected = _complete_check_obligations(store, state, store.get(run["base_root"]), "physical_network")
    assert expected["network-pressure-operating-point"] == "PASS"
    from oma.project_assurance import candidate_assurance
    case = candidate_assurance(store, candidate["id"])
    assert any("pressure_driven_network_boundary_inputs" in a["statement"] for a in case["assumption_ledger"])
    accepted = store.accept(project["id"], candidate["id"], 1, "accept-operating-point", checker_version=checker_version())
    assert accepted["revision"] == 2
    exported = export_project(store, project["id"], candidate["id"], draft=False, budget_seconds=90)
    assert exported["status"] == "CHECKED_LOCAL_SCOPE" and exported["round_trip"] == "PASS", exported
    manifest = store.get(exported["artifact_root"])
    fresh = store.get(manifest["verification_root"])
    assert fresh["candidate_root"] != report["candidate_root"]
    assert fresh["status"] == "PASS"
    fresh_by_id = {r["id"]: r for r in fresh["results"]}
    assert fresh_by_id["network-pressure-operating-point"]["status"] == "PASS"
    fresh_calculation = fresh_by_id["network-demand-conditioned-service"]["witness"]["calculation"]
    assert fresh_calculation["independent_check"]["model_root"] != calculation["independent_check"]["model_root"]
    assert fresh_calculation["deliveries"] == calculation["deliveries"]


def test_actual_native_network_can_pass_geometry_but_fail_required_operating_delivery(tmp_path):
    store, project = imported_project(tmp_path)
    raw = pressure_scenario()
    raw["sinks"][0]["required_flow_m3_s"] = .004
    run = store.create_run(project["id"], {"operation": "optimize", "mission": raw, "budget_seconds": 90})
    route_project_run(store, run, WorkerControl(store, run["id"]))
    candidate, = store.candidates(project["id"])
    report = store.get(candidate["report_root"])
    by_id = {r["id"]: r for r in report["results"]}
    assert by_id["network-all-source-clearance"]["status"] == "PASS"
    assert by_id["network-all-component-pairs"]["status"] == "PASS"
    assert by_id["network-pressure-operating-point"]["status"] == "PASS"
    assert by_id["network-demand-conditioned-service"]["status"] == "FAIL"
    assert candidate["status"] == "REJECTED"
    assert store.run(run["id"])["status"] == "NO_INCUMBENT_FOUND"
    with pytest.raises(IntegrityError):
        store.accept(project["id"], candidate["id"], 1, "reject-under-delivery", checker_version=checker_version())
