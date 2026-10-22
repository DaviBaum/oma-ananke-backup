"""A bounded geometric search has no authority to stop other physical proposals."""
import time

import pytest

from oma.routing.proposals import project_proposals
from oma.routing.scenario import RoutingScenario
from oma.store import Store
from oma.worker import Cancelled


def setup(tmp_path, max_candidates=3):
    store = Store(tmp_path / "store")
    project = store.create_project("Proposal boundaries", {})
    run = store.create_run(project["id"], {"operation": "route"})
    scenario = RoutingScenario(start=(-1., 1., 1.), end=(3., 1., 1.), system_type="PRESSURE_PIPE",
        diameter_m=.1, insulation_m=.02, bend_radius_m=.3, minimum_straight_m=.05,
        clearance_m=.1, allowed_zone={"min": [-2., -2., -2.], "max": [4., 4., 4.]},
        scenario_terminals=True, max_candidates=max_candidates)
    return store, run, scenario


def test_single_candidate_budget_never_starts_second_geometry_search(tmp_path, monkeypatch):
    from oma.routing import certified_cells
    store, run, scenario = setup(tmp_path, max_candidates=1)
    def unexpected(*args, **kwargs):
        pytest.fail("Exhausted candidate budget started another geometry search")
    monkeypatch.setattr(certified_cells, "build_certified_cell_proposals", unexpected)
    result = list(project_proposals(store, run, {"sources": []}, scenario, [],
        deadline=time.monotonic()+30, checkpoint=lambda stage: None, on_search=lambda event: None))
    assert len(result) == 1
    assert result[0]["points_m"] == [list(scenario.start), list(scenario.end)]
    assert not any(e["stage"] == "route_geometry_model" for e in store.events(run["project_id"]))


@pytest.mark.parametrize("status", ["UNKNOWN", "BLOCKED"])
def test_inconclusive_cell_model_is_retained_and_other_routes_remain_available(tmp_path, monkeypatch, status):
    from oma.routing import certified_cells
    store, run, scenario = setup(tmp_path)
    def inconclusive(*args, **kwargs):
        return {"status": status, "reason": "Bounded source model unavailable", "proposals": [], "timing": {"total_seconds": 0.}}
    monkeypatch.setattr(certified_cells, "build_certified_cell_proposals", inconclusive)
    result = list(project_proposals(store, run, {"sources": []}, scenario, [],
        deadline=time.monotonic()+30, checkpoint=lambda stage: None, on_search=lambda event: None))
    assert len(result) == 3
    assert all(not p.get("geometry_evidence") for p in result)
    events = [e for e in store.events(run["project_id"]) if e["stage"] == "route_geometry_model"]
    event = events[-1]
    assert event["status"] == status
    evidence = store.get(event["artifacts"][0])
    assert evidence["report"]["status"] == status
    assert not evidence["route_acceptance"] and not evidence["physical_infeasibility_claim"]


def test_cancellation_during_model_publication_stops_all_proposals(tmp_path, monkeypatch):
    from oma.routing import certified_cells
    store, run, scenario = setup(tmp_path)
    monkeypatch.setattr(certified_cells, "build_certified_cell_proposals", lambda *a, **kw:
        {"status": "UNKNOWN", "proposals": [], "timing": {"total_seconds": 0.}})
    def stop(stage):
        if stage == "route_geometry_model_publish":
            raise Cancelled()
    proposals = project_proposals(store, run, {"sources": []}, scenario, [],
        deadline=time.monotonic()+30, checkpoint=stop, on_search=lambda event: None)
    next(proposals)
    with pytest.raises(Cancelled):
        next(proposals)
    assert not any(e["artifacts"] for e in store.events(run["project_id"]) if e["stage"] == "route_geometry_model")
