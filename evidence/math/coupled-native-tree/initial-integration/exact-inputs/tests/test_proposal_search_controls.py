"""Actual source adapters keep forced publication checks after hot search polls."""
import time

import pytest

from oma.ifc.audit import sha256_file
from oma.routing.proposals import project_proposals
from oma.routing.scenario import RoutingScenario
from oma.store import Store
from oma.worker import Cancelled, WorkerControl, import_sources
from test_ifc_pipeline import make_fixture


PUBLICATIONS = {"cell_proposal_publish", "route_geometry_model_publish", "fabrication_graph_publish",
    "fabrication_proposal_publish", "fabrication_graph_result", "fabrication_model_publish"}


def _proposal_run(directory, cancel_at=None):
    directory.mkdir(parents=True, exist_ok=True)
    source = make_fixture(directory / "source.ifc")
    store = Store(directory / "store")
    project = store.create_project("Actual source proposal controls", {})
    imported = store.create_run(project["id"], {"operation": "import", "paths": [str(source)]})
    import_sources(store, imported, WorkerControl(store, imported["id"]))
    scenario = RoutingScenario(start=(-1., 1., 1.), end=(3., 1., 1.), system_type="PRESSURE_PIPE",
        diameter_m=.1, insulation_m=.02, bend_radius_m=.3, minimum_straight_m=.05, clearance_m=.1,
        allowed_zone={"min": [-2., -2., -2.], "max": [4., 4., 4.]}, scenario_terminals=True, max_candidates=2)
    run = store.create_run(project["id"], {"operation": "route", "mission": scenario.model_dump(mode="json"), "budget_seconds": 120})
    store.update_run(run["id"], "RUNNING")
    control = WorkerControl(store, run["id"])
    state = store.get(run["base_root"])
    forced, hot = [], []
    def checkpoint(stage):
        forced.append(stage)
        if stage == cancel_at:
            store.control(run["id"], "cancel")
        control.checkpoint(stage)
    def search_checkpoint(stage):
        hot.append(stage)
        control.search_checkpoint(stage)
    obstacles = [e["geometry"]["bounds"]["min"] + e["geometry"]["bounds"]["max"] for e in state["entities"] if e.get("geometry", {}).get("bounds")]
    iterator = project_proposals(store, run, state, scenario, obstacles, deadline=time.monotonic() + 120,
        checkpoint=checkpoint, search_checkpoint=search_checkpoint, on_search=lambda value: None)
    return store, run, state, iterator, forced, hot


def test_actual_adapter_completes_with_forced_publication_and_hot_search_callbacks(tmp_path):
    store, run, state, iterator, forced, hot = _proposal_run(tmp_path / "complete")
    proposals = list(iterator)
    assert len(proposals) == 2 and proposals[1]["geometry_evidence"]["method"] == "SOURCE_BOUND_FABRICATION_GRAPH"
    assert PUBLICATIONS <= set(forced)
    assert PUBLICATIONS.isdisjoint(hot)
    assert "fabrication_graph_work" in hot
    events = store.events(run["project_id"], limit=1000)
    assert len([e for e in events if e["run_id"] == run["id"] and e["stage"] == "fabrication_model"]) == 2
    assert all(sha256_file(store.resolve_path(s["immutable_path"])) == s["sha256"] for s in state["sources"])


@pytest.mark.parametrize("stage", sorted(PUBLICATIONS))
def test_cancel_at_actual_forced_boundary_prevents_that_artifact_and_next_yield(tmp_path, stage):
    store, run, state, iterator, forced, hot = _proposal_run(tmp_path / stage, cancel_at=stage)
    first_yielded = 0
    if stage != "fabrication_model_publish":
        next(iterator)
        first_yielded = 1
    with pytest.raises(Cancelled):
        next(iterator)
    assert stage in forced and stage not in hot
    events = [e for e in store.events(run["project_id"], limit=1000) if e["run_id"] == run["id"]]
    assert len([e for e in events if e["stage"] == "fabrication_model"]) == first_yielded
    assert not any(e["stage"] == "fabrication_graph" and e["artifacts"] for e in events)
    if stage in {"cell_proposal_publish", "route_geometry_model_publish", "fabrication_model_publish"}:
        assert not any(e["stage"] == "route_geometry_model" and e["artifacts"] for e in events)
    assert store.run(run["id"])["desired_action"] == "cancel"
    assert all(sha256_file(store.resolve_path(s["immutable_path"])) == s["sha256"] for s in state["sources"])
