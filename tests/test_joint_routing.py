import copy

from oma.routing.engine import route_project_run
from oma.store import Store
from oma.worker import WorkerControl, import_sources
from test_ifc_pipeline import make_fixture


def test_simultaneous_routes_reject_crossing_and_select_authorized_option(tmp_path):
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
