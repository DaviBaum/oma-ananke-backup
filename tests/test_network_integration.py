import copy

from oma.routing.engine import route_project_run
from oma.routing.network_checker import verify_network_candidate
from oma.store import Store
from oma.worker import WorkerControl, import_sources
from test_ifc_pipeline import make_fixture
from test_network_scenario import network_scenario


def imported_project(tmp_path, obstacle_position=None):
    source = make_fixture(tmp_path / "obstacle.ifc")
    if obstacle_position is not None:
        import ifcopenshell
        import ifcopenshell.api
        import numpy as np
        model = ifcopenshell.open(str(source))
        transform = np.eye(4)
        transform[:3, 3] = obstacle_position
        ifcopenshell.api.run("geometry.edit_object_placement", model,
            product=model.by_type("IfcBuildingElementProxy")[0], matrix=transform)
        model.write(str(source))
    store = Store(tmp_path / "store")
    project = store.create_project("Shared trunk", {"sources": [], "entities": []})
    run = store.create_run(project["id"], {"operation": "import", "paths": [str(source)]})
    import_sources(store, run, WorkerControl(store, run["id"]))
    state = store.get(store.project(project["id"])["state_root"])
    assert state["sources"][0]["coordinate_scope"] == "SINGLE_SOURCE_LOCAL_IDENTITY"
    assert state["sources"][0]["transform_m"] == [[1., 0., 0., 0.], [0., 1., 0., 0.], [0., 0., 1., 0.], [0., 0., 0., 1.]]
    assert state["derived_artifacts"]["local_coordinate_evidence"]["status"] == "UNRESOLVED"
    return store, project


def test_shared_network_import_check_select_accept_export_and_reopen(tmp_path):
    store, project = imported_project(tmp_path)
    mission = network_scenario()
    run = store.create_run(project["id"], {"operation": "optimize", "mission": mission, "budget_seconds": 90})
    route_project_run(store, run, WorkerControl(store, run["id"]))
    candidates = store.candidates(project["id"])
    assert len(candidates) == 1, store.run(run["id"])
    candidate = candidates[0]
    report = store.get(candidate["report_root"])
    assert candidate["status"] == "CHECKED", report
    assert store.run(run["id"])["status"] == "COMPLETED"
    assert report["objective"] == {"length_m": 3., "fitting_count": 1.}
    calculation = next(r["witness"]["calculation"] for r in report["results"] if r["id"] == "network-demand-conditioned-service")
    assert calculation["source_flow_m3_s"] == "3/1000"
    assert calculation["components"]["junction"]["flow_m3_s"]["branch"] == "1/500"
    assert calculation["unique_physical_components"] == 4
    assert calculation["operating_point_solution"] == "NOT_ESTABLISHED"
    from oma.project_assurance import candidate_assurance
    case = candidate_assurance(store, candidate["id"])
    assert any("fixed_network_boundary_inputs" in a["statement"] for a in case["assumption_ledger"])
    assert any("INLET_VELOCITY_TOTAL_IRREVERSIBLE_LOSS" in a["statement"] for a in case["assumption_ledger"])
    state = store.get(candidate["state_root"])
    assert state["routes"] == []
    assert len(state["physical_networks"]) == 1
    from oma.build_identity import checker_version
    from oma.exporting import export_project
    store.accept(project["id"], candidate["id"], 1, "accept-shared", checker_version=checker_version())
    exported = export_project(store, project["id"], candidate["id"], draft=False)
    assert exported["status"] == "CHECKED_LOCAL_SCOPE", exported
    assert exported["round_trip"] == "PASS"
    import ifcopenshell
    model = ifcopenshell.open(exported["files"][0]["path"])
    assert len(model.by_type("IfcPipeSegment")) == 3
    assert len(model.by_type("IfcPipeFitting")) == 1
    assert len(model.by_type("IfcDistributionPort")) == 9
    assert len(model.by_type("IfcRelConnectsPorts")) == 3
    # Rewriting state metadata cannot erase a branch or change its fixed flow.
    tampered = copy.deepcopy(state)
    tampered["mission"]["demands"][1]["required_flow_m3_s"] = .0001
    forged = store.add_candidate(run["id"], tampered, {"kind": "physical_network", "changed_ids": candidate["changed_ids"]})
    assert verify_network_candidate(store, forged["id"]).status == "FAIL"
    tampered = copy.deepcopy(state)
    tampered["physical_networks"][0]["component_ids"].pop()
    forged = store.add_candidate(run["id"], tampered, {"kind": "physical_network", "changed_ids": candidate["changed_ids"]})
    assert verify_network_candidate(store, forged["id"]).status == "FAIL"
    # A subsequent operation must not silently drop accepted network obligations.
    more = store.create_run(project["id"], {"operation": "optimize", "mission": mission, "budget_seconds": 30})
    route_project_run(store, more, WorkerControl(store, more["id"]))
    assert store.run(more["id"])["status"] == "MISSING_INPUTS"
    # Immutable graph, native part bytes, coordinate sidecars and proof roots
    # survive relocation; authority is reacquired from actual restored bytes.
    from oma.backup import restore_store
    from oma.service import EngineService
    import subprocess
    import sys
    backup = store.backup(tmp_path / "network-backup")
    old_directory = store.directory.resolve()
    assert old_directory.is_relative_to(tmp_path.resolve())
    old_directory.rename(tmp_path / "network-original-unavailable")
    restored = restore_store(backup, tmp_path / "network-restored")
    checked = subprocess.run([sys.executable, "-m", "oma.verification", str(restored.directory), candidate["id"]],
        capture_output=True, text=True, timeout=60)
    assert checked.returncode == 0, checked.stderr
    renewed = restored.candidate(candidate["id"])
    assert renewed["state_root"] == candidate["state_root"]
    assert renewed["status"] == "CHECKED"
    assert restored.get(renewed["report_root"])["objective"] == report["objective"]
    view = EngineService(restored.directory).geometry(project["id"], candidate_id=candidate["id"])
    assert sum(m["entity_id"] in candidate["changed_ids"] for m in view["meshes"]) == 4


def test_shared_network_missing_flow_is_blocked_despite_clear_geometry(tmp_path):
    store, project = imported_project(tmp_path)
    mission = network_scenario()
    mission["sinks"][1].pop("required_flow_m3_s")
    run = store.create_run(project["id"], {"operation": "route", "mission": mission, "budget_seconds": 60})
    route_project_run(store, run, WorkerControl(store, run["id"]))
    candidate = store.candidates(project["id"])[0]
    report = store.get(candidate["report_root"])
    assert report["status"] == "BLOCKED"
    assert store.run(run["id"])["status"] == "NO_INCUMBENT_FOUND"
    assert next(r["status"] for r in report["results"] if r["id"] == "network-all-source-clearance") == "PASS"
    assert next(r["status"] for r in report["results"] if r["id"] == "network-demand-conditioned-service") == "BLOCKED"


def test_shared_network_native_counterexample_leaves_full_denominator_not_run(tmp_path):
    store, project = imported_project(tmp_path, obstacle_position=[-1, 3, 2])
    run = store.create_run(project["id"], {"operation": "route", "mission": network_scenario(), "budget_seconds": 60})
    route_project_run(store, run, WorkerControl(store, run["id"]))
    candidate = store.candidates(project["id"])[0]
    report = store.get(candidate["report_root"])
    assert candidate["status"] == "REJECTED"
    witness = next(r for r in report["results"] if r["id"] == "network-native-counterexample")
    native = store.get(witness["witness"]["artifact"])
    assert native["status"] == "FAIL"
    assert native["witness"]["native_pair_result"]["common_volume_m3"] > 0
    assert native["full_source_denominator"] == "NOT_RUN"
    assert next(r["status"] for r in report["results"] if r["id"] == "network-all-source-clearance") == "NOT_RUN"


def test_unresolved_multiple_source_alignment_cannot_use_single_source_identity(tmp_path):
    store = Store(tmp_path / "store")
    project = store.create_project("Unresolved federation", {"sources": [], "entities": []})
    paths = [make_fixture(tmp_path / f"discipline-{i}.ifc") for i in range(2)]
    run = store.create_run(project["id"], {"operation": "import", "paths": [str(p) for p in paths]})
    import_sources(store, run, WorkerControl(store, run["id"]))
    state = store.get(store.project(project["id"])["state_root"])
    assert all(s.get("transform_m") is None for s in state["sources"])
    route = store.create_run(project["id"], {"operation": "route", "mission": network_scenario(), "budget_seconds": 60})
    route_project_run(store, route, WorkerControl(store, route["id"]))
    assert store.run(route["id"])["status"] == "MISSING_INPUTS"
    assert not store.candidates(project["id"])
