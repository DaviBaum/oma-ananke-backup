"""Large coverage ledgers and final source checks remain cooperatively bounded."""
from copy import deepcopy
from functools import partial

import numpy as np
import pytest

from oma.ifc.audit import sha256_file
from oma.routing import certified_cells as cells, certified_fabrication as fabrication
from oma.routing.scenario import RoutingScenario
from oma.store import digest


def _scenario():
    return RoutingScenario(start=(-1.,1.,1.),end=(3.,1.,1.),system_type="PRESSURE_PIPE",
        diameter_m=.1,insulation_m=.02,bend_radius_m=.3,minimum_straight_m=.05,
        clearance_m=.1,allowed_zone={"min":[-2.,-2.,-2.],"max":[4.,4.,4.]},scenario_terminals=True)


def _large_ledger(count=513):
    objects = [{"id":f"source:{i:04d}", "bounds_m":[[2,2,2],["2.25","2.25","2.25"]],
        "source_bounds_m":[[2,2,2],["2.25","2.25","2.25"]], "source_to_common_matrix":np.eye(4).tolist(),
        "disposition":"GROUPED_OUTER_COVER", "group_id":"all"} for i in range(count)]
    coverage = {"blockers":[], "objects":objects, "physical_ids":[o["id"] for o in objects]+["assembly"],
        "assemblies":[{"id":"assembly", "children":[o["id"] for o in objects]}]}
    model = {"inner_obstacles":[], "outer_obstacles":[{"id":"all","bounds":[[2,2,2],[3,3,3]]}],
        "allowed_bounds":[[-2,-2,-2],[4,4,4]], "body_radius":"0.07", "clearance":"0.1"}
    return coverage,model


@pytest.mark.parametrize("operation,stage",[
    ("cell","cell_coverage_objects"),
    ("cell","cell_coverage_physical_ids"),
    ("cell","cell_coverage_assembly_children"),
    ("cell","cell_coverage_assembly_traversal"),
    ("cell","cell_coverage_support_replay"),
    ("body","fabrication_body_coverage_dispositions"),
    ("body","cell_group_bounds"),
    ("body","cell_group_sort_keys"),
    ("body","cell_group_members"),
    ("body","fabrication_body_coverage_sort_keys"),
    ("body_check","fabrication_coverage_originals"),
    ("body_check","fabrication_coverage_entries"),
    ("body_check","fabrication_coverage_support_replay"),
])
@pytest.mark.parametrize("error_type",[TimeoutError,ValueError])
def test_late_large_inventory_cancellation_propagates_without_changing_source(operation,stage,error_type):
    source,model = _large_ledger()
    before = deepcopy(source)
    cover = fabrication.body_outer_coverage(source,_scenario(),2)
    action = {"cell":partial(cells.verify_cell_coverage,source,model),
        "body":partial(fabrication.body_outer_coverage,source,_scenario(),2),
        "body_check":partial(fabrication.verify_body_outer_coverage,source,cover)}[operation]
    error = error_type("caller cancelled after more than one hundred traversal operations")
    hits = 0
    def stop(current):
        nonlocal hits
        if current == stage:
            hits += 1
            if hits == 3:
                raise error
    with pytest.raises(error_type) as caught:
        action(checkpoint=stop)
    assert caught.value is error and hits == 3
    assert source == before
    # Cancellation leaves the authoritative ledger replayable with its original
    # denominator, assembly edges, exact bounds and conservative omissions.
    assert cells.verify_cell_coverage(source,model)["status"] == "PASS"
    assert fabrication.verify_body_outer_coverage(source,cover)["status"] == "PASS"


@pytest.fixture(scope="module")
def native_source(tmp_path_factory):
    from test_ifc_pipeline import make_fixture
    source = make_fixture(tmp_path_factory.mktemp("coverage-deadlines")/"wall.ifc")
    specs = [{"path":source,"sha256":sha256_file(source),"transform_m":np.eye(4).tolist()}]
    scenario = _scenario()
    report = cells.build_certified_cell_proposals(specs,scenario,context_root="native-coverage-checkpoints",grid_divisions=6)
    assert report["coverage_check"]["status"] == "PASS", report
    return specs,scenario,report


@pytest.mark.parametrize("adapter,stage",[
    ("cells","cell_source_assemblies"),
    ("cells","cell_group_complete"),
    ("cells","cell_coverage_complete"),
    ("fabrication","cell_coverage_complete"),
    ("fabrication","cell_group_complete"),
    ("fabrication","fabrication_body_coverage_complete"),
    ("fabrication","fabrication_coverage_complete"),
])
def test_native_adapter_deadline_during_coverage_stops_before_graph_without_publication(native_source,monkeypatch,adapter,stage):
    from oma.optimization import fabrication_search
    specs,scenario,source_report = native_source
    before = deepcopy(source_report)
    clock = [0.]
    reached = []
    def checkpoint(current):
        if current == stage:
            reached.append(current)
            clock[0] = 20.
    def forbidden(*args,**kwargs):
        pytest.fail("Graph compilation must not start after coverage consumed the deadline")
    monkeypatch.setattr(cells.time,"monotonic",lambda:clock[0])
    monkeypatch.setattr(cells.route_cells,"compile_route_cells",forbidden)
    monkeypatch.setattr(fabrication_search,"compile_fabrication_search",forbidden)
    if adapter == "cells":
        result = cells.build_certified_cell_proposals(specs,scenario,context_root="coverage-expired",deadline=10.,checkpoint=checkpoint)
        reason = "CERTIFIED_CELL_DEADLINE"
    else:
        result = fabrication.build_certified_fabrication_proposals(specs,scenario,source_report,
            context_root="coverage-expired",deadline=10.,checkpoint=checkpoint)
        reason = "FABRICATION_SEARCH_DEADLINE"
    assert reached
    assert result["status"] == "UNKNOWN" and result["reason"] == reason and result["proposals"] == []
    assert source_report == before and sha256_file(specs[0]["path"]) == specs[0]["sha256"]


@pytest.mark.parametrize("adapter,stage",[("cells","cell_coverage_complete"),("fabrication","fabrication_coverage_complete")])
@pytest.mark.parametrize("error_type",[TimeoutError,ValueError])
def test_adapter_does_not_relabel_caller_deadline_as_invalid_geometry(native_source,adapter,stage,error_type):
    specs,scenario,source_report = native_source
    original = digest(source_report)
    error = error_type("caller owns cancellation semantics")
    def checkpoint(current):
        if current == stage:
            raise error
    with pytest.raises(error_type) as caught:
        if adapter == "cells":
            cells.build_certified_cell_proposals(specs,scenario,context_root="caller-cancelled",checkpoint=checkpoint)
        else:
            fabrication.build_certified_fabrication_proposals(specs,scenario,source_report,
                context_root="caller-cancelled",checkpoint=checkpoint)
    assert caught.value is error
    assert digest(source_report) == original and sha256_file(specs[0]["path"]) == specs[0]["sha256"]


def test_fabricator_rechecks_deadline_after_final_build_comparison(native_source,monkeypatch):
    specs,scenario,source_report = native_source
    before = deepcopy(source_report)
    clock = [0.]
    real_version = fabrication.checker_version
    versions = []
    def version():
        value = real_version()
        versions.append(value)
        if len(versions) == 2:
            clock[0] = 20.  # The final unchanged-build comparison consumed the remaining budget.
        return value
    monkeypatch.setattr(fabrication,"checker_version",version)
    monkeypatch.setattr(fabrication.time,"monotonic",lambda:clock[0])
    result = fabrication.build_certified_fabrication_proposals(specs,scenario,source_report,
        context_root="expired-after-final-source-check",deadline=10.)
    assert len(versions) == 2
    assert result["binary64_fabrication_check"]["fabrication_status"] == "PASS"
    assert result["status"] == "UNKNOWN" and result["reason"] == "FABRICATION_SEARCH_DEADLINE"
    assert result["proposals"] == []
    assert source_report == before and sha256_file(specs[0]["path"]) == specs[0]["sha256"]


def test_cell_adapter_rechecks_deadline_after_last_dependency_hash(native_source,monkeypatch):
    specs,scenario,_ = native_source
    clock = [0.]
    real_sha256 = cells.sha256
    final_dependency = cells._DEPENDENCY_PATHS[-1].read_bytes()
    comparisons = []
    def hashing(*args,**kwargs):
        value = real_sha256(*args,**kwargs)
        if args and args[0] == final_dependency:
            comparisons.append(value.hexdigest())
            if len(comparisons) == 2:
                clock[0] = 20.
        return value
    monkeypatch.setattr(cells,"sha256",hashing)
    monkeypatch.setattr(cells.time,"monotonic",lambda:clock[0])
    result = cells.build_certified_cell_proposals(specs,scenario,context_root="last-dependency-expired",
        grid_divisions=6,deadline=10.)
    assert len(comparisons) == 2
    assert result["independent_check"]["status"] == "PASS"
    assert result["status"] == "UNKNOWN" and result["reason"] == "CERTIFIED_CELL_DEADLINE"
    assert result["proposals"] == [] and sha256_file(specs[0]["path"]) == specs[0]["sha256"]
