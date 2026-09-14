import copy

from oma.routing.engine import route_project_run
from oma.store import Store
from oma.worker import WorkerControl, import_sources
from test_ifc_pipeline import make_fixture


def test_joint_search_consumes_checked_cell_path_and_rechecks_complete_route_set(tmp_path):
    from oma.build_identity import checker_version
    from oma.exporting import export_project
    from oma.store import digest
    source = make_fixture(tmp_path / "obstacle.ifc")
    store = Store(tmp_path / "store")
    project = store.create_project("Source-cell simultaneous repair", {"sources": [], "entities": []})
    imp = store.create_run(project["id"], {"operation": "import", "paths": [str(source)]})
    import_sources(store, imp, WorkerControl(store, imp["id"]))
    first = {"start": [-1., 1., 1.], "end": [3., 1., 1.], "system_type": "PRESSURE_PIPE",
        "diameter_m": .1, "insulation_m": .02, "bend_radius_m": .3, "minimum_straight_m": .05,
        "clearance_m": .1, "allowed_zone": {"min": [-2., -2., -2.], "max": [4., 4., 4.]},
        "scenario_terminals": True, "max_candidates": 2}
    second = {**first, "start": [-1., 3.5, 3.5], "end": [3., 3.5, 3.5], "max_candidates": 1}
    mission = {"route_demands": [{"id": "obstructed", "alternatives": [first]},
                               {"id": "clear", "alternatives": [second]}],
               "max_joint_candidates": 2, "max_paths_per_alternative": 2}
    run = store.create_run(project["id"], {"operation": "optimize", "mission": mission, "budget_seconds": 90})
    route_project_run(store, run, WorkerControl(store, run["id"]))
    candidates = store.candidates(project["id"])
    assert len(candidates) == 2
    assert candidates[0]["status"] == "REJECTED"
    checked = candidates[1]
    assert checked["status"] == "CHECKED", store.get(checked["report_root"])
    assert len(checked["proposal_evidence"]) == 1
    route_id, evidence = next(iter(checked["proposal_evidence"].items()))
    artifact = store.get(evidence["report_root"])
    assert artifact["context"]["request_demand_id"] == "obstructed"
    assert artifact["context"]["request_root"] == digest(run["request"])
    assert artifact["context"]["base_root"] == run["base_root"]
    assert evidence["method"] == "SOURCE_BOUND_FABRICATION_GRAPH"
    assert artifact["report"]["source_coverage_check"]["physical_elements"] == 1
    assert artifact["report"]["binary64_fabrication_check"]["fabrication_status"] == "PASS"
    assert not artifact["route_acceptance"] and not artifact["physical_infeasibility_claim"]
    state = store.get(checked["state_root"])
    assert state["derived_artifacts"]["route_proposal_evidence_by_route"][route_id] == evidence
    assert len(state["routes"]) == 2
    report = store.get(checked["report_root"])
    references = state["derived_artifacts"]["fabrication_evidence_by_route"]
    assert set(references) == {r["id"] for r in state["routes"]}
    for route in state["routes"]:
        proof = next(r for r in report["results"] if r["id"] == route["id"] + ":nominal-fabrication-witness-integrity")
        assert proof["status"] == "PASS"
        assert proof["witness"]["artifact_root"] == references[route["id"]]["artifact_root"]
        assert proof["witness"]["origin_run_id"] == run["id"]
        assert proof["witness"]["producer_check_reused"] is False
        assert proof["witness"]["candidate_acceptance_authority"] is False
    assert next(r for r in report["results"] if r["id"] == "cross-route-interference")["status"] == "PASS"
    store.accept(project["id"], checked["id"], 1, "accept-joint-cell-repair", checker_version=checker_version())
    exported = export_project(store, project["id"], checked["id"], draft=False)
    assert exported["status"] == "CHECKED_LOCAL_SCOPE" and exported["round_trip"] == "PASS"
    assert len(exported["files"]) == 1 and exported["files"][0]["changed"]


def test_simultaneous_routes_reject_crossing_and_select_authorized_option(tmp_path, monkeypatch):
    source = make_fixture(tmp_path / "obstacle.ifc")
    store = Store(tmp_path / "store")
    project = store.create_project("Simultaneous route design", {"sources": [], "entities": []})
    imp = store.create_run(project["id"], {"operation": "import", "paths": [str(source)]})
    import_sources(store, imp, WorkerControl(store, imp["id"]))
    first = {"start": [-1., 4., 1.], "end": [3., 4., 1.], "system_type": "PRESSURE_PIPE",
        "diameter_m": .1, "insulation_m": .02, "bend_radius_m": .3, "minimum_straight_m": .05,
        "clearance_m": .1, "allowed_zone": {"min": [-2., -2., -2.], "max": [6., 6., 6.]},
        "scenario_terminals": True, "max_candidates": 1}
    crossing = {**first, "start": [1., 3., 1.], "end": [1., 5., 1.]}
    separated = {**crossing, "start": [1., 3., 2.], "end": [1., 5., 2.]}
    mission = {"route_demands": [{"id": "main", "alternatives": [first]}, {"id": "branch", "alternatives": [crossing, separated]}],
        "max_joint_candidates": 2, "max_paths_per_alternative": 1}
    run = store.create_run(project["id"], {"operation": "optimize", "mission": mission, "budget_seconds": 90})
    route_project_run(store, run, WorkerControl(store, run["id"]))
    candidates = store.candidates(project["id"])
    assert len(candidates) == 2
    assert candidates[0]["status"] == "REJECTED"
    rejected = store.get(candidates[0]["report_root"])
    assert next(r for r in rejected["results"] if r["id"] == "cross-route-interference")["status"] == "FAIL"
    assert candidates[1]["status"] == "CHECKED", store.get(candidates[1]["report_root"])
    report = store.get(candidates[1]["report_root"])
    assert report["objective"] == {"length_m": 6., "fitting_count": 0.}
    assert store.run(run["id"])["status"] == "COMPLETED"
    from oma.routing.physical_archive import assemble_route_menu_problem, compile_route_archive
    from oma.optimization.physical_menu import verify_physical_menu
    from oma.store import IntegrityError
    import pytest
    import time
    event = next(e for e in store.events(project["id"], limit=1000) if e["stage"] == "physical_menu_compilation")
    archive = store.get(event["artifacts"][0])
    problem, certificate = store.get(archive["problem_root"]), store.get(archive["certificate_root"])
    assert archive["independent_check"]["status"] == "PASS"
    assert archive["summary"]["assignment_count"] == 2
    assert archive["summary"]["verdict_counts"] == {"FAIL": 1, "PASS": 1}
    assert {r["candidate_id"] for r in problem["examined"]} == {c["id"] for c in candidates}
    assert verify_physical_menu(problem, certificate)["status"] == "PASS"
    frozen_root = candidates[0]["physical_menu_root"]
    partial = store.get(compile_route_archive(store, frozen_root, [candidates[0]["id"]], deadline=time.monotonic() + 10))
    assert partial["summary"]["verdict_counts"] == {"FAIL": 1, "UNKNOWN": 1}
    assert partial["candidate_acceptance_authority"] is False
    import oma.routing.physical_archive as archive_module
    with monkeypatch.context() as patch:
        patch.setattr(archive_module, "verify_physical_menu", lambda *a, **kw: {"status": "UNKNOWN", "reason": "WORK_BUDGET"})
        bounded = store.get(compile_route_archive(store, frozen_root, [candidates[0]["id"]], deadline=time.monotonic() + 10))
        assert bounded["status"] == "UNKNOWN" and bounded["summary"] is None
    with monkeypatch.context() as patch:
        patch.setattr(archive_module, "_byte_hash", lambda *a: (_ for _ in ()).throw(archive_module.ArchiveBudgetExceeded()))
        bounded = store.get(compile_route_archive(store, frozen_root, [candidates[0]["id"]], deadline=time.monotonic() + 10))
        assert bounded["status"] == "UNKNOWN" and bounded["reason"] == "RUN_TIME_BUDGET"
    # A real PASS cannot be relabeled as the crossing choice or rebound to a
    # different report. These gates check actual persisted definitions/bytes.
    original_candidate = store.candidate
    for field, value, expected in (
        ("physical_menu_assignment", candidates[0]["physical_menu_assignment"], "realization differs"),
        ("report_root", candidates[0]["report_root"], "stale, misbound"),
        ("status", "REJECTED", "flag and independently"),
    ):
        with monkeypatch.context() as patch:
            patch.setattr(store, "candidate", lambda cid, field=field, value=value: {**original_candidate(cid), field: value})
            with pytest.raises(IntegrityError, match=expected):
                assemble_route_menu_problem(store, frozen_root, [candidates[1]["id"]])
    actual_file = store.resolve_path(store.get(store.get(candidates[1]["state_root"])["routes"][0]["geometry_artifact"])["export_path"])
    original_bytes = actual_file.read_bytes()
    try:
        actual_file.write_bytes(original_bytes + b"\n")
        with pytest.raises(IntegrityError, match="candidate bytes changed"):
            assemble_route_menu_problem(store, frozen_root, [candidates[1]["id"]])
    finally:
        actual_file.write_bytes(original_bytes)
    from oma.verification import CHECKER_VERSION
    from oma.exporting import export_project
    store.accept(project["id"], candidates[1]["id"], 1, "accept-joint", checker_version=CHECKER_VERSION)
    bundle = export_project(store, project["id"], candidates[1]["id"], draft=False)
    assert bundle["status"] == "CHECKED_LOCAL_SCOPE", bundle
    assert len(bundle["files"]) == 1 and bundle["files"][0]["changed"]
    assert bundle["round_trip"] == "PASS"
    import ifcopenshell
    model = ifcopenshell.open(bundle["files"][0]["path"])
    assert len(model.by_type("IfcPipeSegment")) == 2
    from oma.routing.joint_checker import verify_joint_candidate
    tampered = store.get(candidates[1]["state_root"])
    tampered["routes"].pop()
    missing = store.add_candidate(run["id"], tampered, {"kind": "physical_route_set", "changed_ids": candidates[1]["changed_ids"]})
    assert verify_joint_candidate(store, missing["id"]).status == "FAIL"

    # Adding another demand retains all existing native STEP records and missions.
    extra = {**first, "start": [-1., 4., 4.], "end": [3., 4., 4.]}
    run2 = store.create_run(project["id"], {"operation": "route", "mission": extra, "budget_seconds": 90})
    route_project_run(store, run2, WorkerControl(store, run2["id"]))
    added = [c for c in store.candidates(project["id"]) if c["run_id"] == run2["id"] and c["status"] == "CHECKED"]
    assert len(added) == 1, [(c["status"], store.get(c["report_root"]) if c["report_root"] else None) for c in store.candidates(project["id"]) if c["run_id"] == run2["id"]]
    previous_state = store.get(candidates[1]["state_root"])
    added_state = store.get(added[0]["state_root"])
    old_refs = previous_state["derived_artifacts"]["fabrication_evidence_by_route"]
    new_refs = added_state["derived_artifacts"]["fabrication_evidence_by_route"]
    assert len(new_refs) == 3
    assert all(new_refs[rid] == ref for rid, ref in old_refs.items())
    added_report = store.get(added[0]["report_root"])
    for route in added_state["routes"]:
        proof = next(r for r in added_report["results"] if r["id"] == route["id"] + ":nominal-fabrication-witness-integrity")
        assert proof["status"] == "PASS"
        assert proof["witness"]["origin_run_id"] == (run["id"] if route["id"] in old_refs else run2["id"])
        assert proof["witness"]["producer_check_reused"] is False
    store.accept(project["id"], added[0]["id"], 2, "accept-additional", checker_version=CHECKER_VERSION)
    full = export_project(store, project["id"], added[0]["id"], draft=False)
    assert full["status"] == "CHECKED_LOCAL_SCOPE"
    assert len(ifcopenshell.open(full["files"][0]["path"]).by_type("IfcPipeSegment")) == 3
    from oma.verification import recheck_candidate_run
    before = store.project(project["id"])
    original_request = store.run(run2["id"])["request"]
    recheck = store.create_run(project["id"], {"operation": "recheck", "candidate_id": added[0]["id"], "budget_seconds": 90})
    recheck_candidate_run(store, recheck, WorkerControl(store, recheck["id"]))
    assert store.run(recheck["id"])["status"] == "COMPLETED"
    assert store.candidate(added[0]["id"])["status"] == "CHECKED"
    assert store.project(project["id"])["state_root"] == before["state_root"]
    assert store.project(project["id"])["revision"] == before["revision"]
    assert store.run(run2["id"])["request"] == original_request
