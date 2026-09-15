"""Actual source-bound proposals retain cost priorities and feasible fallbacks."""
from copy import deepcopy
from fractions import Fraction
import time

import numpy as np
import pytest

from oma.ifc.audit import sha256_file
from oma.routing import certified_cells, certified_fabrication
from oma.routing.scenario import RoutingScenario
from oma.store import digest
from test_ifc_pipeline import make_fixture


@pytest.fixture(scope="module")
def source(tmp_path_factory):
    path = make_fixture(tmp_path_factory.mktemp("priced-native-source")/"wall.ifc")
    return [{"path":path,"sha256":sha256_file(path),"transform_m":np.eye(4).tolist()}]


def scenario(weights=None):
    # The real source box at [0,2]^3 remains in the denominator, with a checked
    # complete-body omission. The open grid isolates the actual cost tradeoff.
    return RoutingScenario(start=(10.,10.,1.),end=(14.,14.,1.),system_type="PRESSURE_PIPE",
        diameter_m=.25,insulation_m=0.,bend_radius_m=.5,minimum_straight_m=.125,
        clearance_m=.125,allowed_zone={"min":[9.75,9.75,-.25],"max":[14.25,14.25,2.25]},
        scenario_terminals=True,objective_weights=weights or {"length_m":1.,"fitting_count":0.})


def proposals(source, s, **kwargs):
    cells = certified_cells.build_certified_cell_proposals(source,s,context_root="priced-native-input",grid_divisions=4)
    assert cells["coverage_check"]["status"] == "PASS", cells
    before = digest(cells)
    result = certified_fabrication.build_certified_fabrication_proposals(source,s,cells,
        context_root=digest({"source":source[0]["sha256"],"mission":s.model_dump(mode="json")}),**kwargs)
    assert digest(cells) == before
    assert sha256_file(source[0]["path"]) == source[0]["sha256"]
    return result


def test_mission_weights_change_independently_priced_and_native_checked_routes(source,tmp_path):
    from oma.ifc.cad import cad_check_routes
    from oma.ifc.export import export_route
    answers = []
    for fitting in (0.,1.):
        s = scenario({"length_m":1.,"fitting_count":fitting})
        report = proposals(source,s,deadline=time.monotonic()+30)
        assert report["status"] == "CHECKED_FABRICATION_PROPOSALS", report.get("reason")
        assert report["pricing_check"]["status"] == "PASS", report["pricing_check"]
        assert report["pricing_objective_binding"]["scenario_root"] == digest(s.model_dump(mode="json"))
        assert report["coverage_check"]["loaded_obstacles"] == 1
        assert report["coverage_check"]["omitted_with_full_body_region_proof"] == 1
        proposal = report["proposals"][0]
        assert proposal["nominal_graph_optimality"] and not proposal["binary64_objective_optimality"]
        assert proposal["path_certificate_kind"] == "FABRICATION_PRICING"
        assert proposal["path_certificate_root"] == digest(report["pricing_certificate"])
        assert proposal["binary64_fabrication_certificate_root"] == digest(report["priced_binary64_fabrication_certificate"])
        assert report["priced_binary64_fabrication_check"]["fabrication_status"] == "PASS"
        bends = len(proposal["points_m"])-2
        assert bends >= 2 if fitting == 0. else bends == 1
        exact_points = [[Fraction(x) for x in p] for p in report["pricing_certificate"]["points_m"]]
        manhattan = sum(sum(abs(a-b) for a,b in zip(p,q)) for p,q in zip(exact_points,exact_points[1:]))
        assert report["pricing_certificate"]["cost"] == [str(manhattan-bends+Fraction(fitting)*bends),str(Fraction(bends,4))]
        output = tmp_path/f"fittings-{int(fitting)}.ifc"
        material = export_route(source[0]["path"],output,{"route_id":f"priced-{int(fitting)}",
            "points_m":proposal["points_m"],"system_type":s.system_type,"diameter_m":s.diameter_m,
            "insulation_m":s.insulation_m,"bend_radius_m":s.bend_radius_m,
            "minimum_straight_m":s.minimum_straight_m},fresh_recheck=False)
        native = cad_check_routes([source[0]["path"]],output,
            {p["ifc_guid"] for p in material["added_parts"]},clearance_m=s.clearance_m)
        assert native["status"] == "PASS", native
        from oma.ifc.cad import load_cad
        from oma.routing.native_zone import check_native_zone
        solids, errors = load_cad(output,guids={p["ifc_guid"] for p in material["added_parts"]})
        assert check_native_zone(solids,s.allowed_zone,expected_count=len(material["added_parts"]),errors=errors)["status"] == "PASS"
        answers.append(proposal["points_m"])
    assert answers[0] != answers[1]
    assert sha256_file(source[0]["path"]) == source[0]["sha256"]


def test_pricing_work_exhaustion_retains_original_checked_feasible_route(source):
    report = proposals(source,scenario(),max_pricing_work=1)
    assert report["status"] == "CHECKED_FABRICATION_PROPOSALS"
    assert report["pricing_check"]["status"] == "UNKNOWN"
    assert len(report["proposals"]) == 1
    proposal = report["proposals"][0]
    assert proposal["path_certificate_kind"] == "FABRICATION_SEARCH"
    assert proposal["path_certificate_root"] == digest(report["certificate"])
    assert not proposal["nominal_graph_optimality"]
    assert proposal["points_m"] == [[float(Fraction(x)) for x in p] for p in report["certificate"]["points_m"]]


def test_pricing_local_deadline_retains_feasible_path_but_global_deadline_does_not(source,monkeypatch):
    clock = [0.]
    monkeypatch.setattr(certified_fabrication.time,"monotonic",lambda:clock[0])
    for elapsed, expected in ((7.,"CHECKED_FABRICATION_PROPOSALS"),(31.,"UNKNOWN")):
        clock[0] = 0.
        stages = []
        def checkpoint(stage):
            if stage == "fabrication_pricing_expand":
                stages.append(stage)
                clock[0] = elapsed
        report = proposals(source,scenario(),deadline=30.,checkpoint=checkpoint)
        assert stages and report["status"] == expected
        if elapsed < 30:
            assert report["pricing_check"]["reason"] == "FABRICATION_PRICING_DEADLINE"
            assert len(report["proposals"]) == 1 and not report["proposals"][0]["nominal_graph_optimality"]
        else:
            assert report["reason"] == "FABRICATION_SEARCH_DEADLINE" and not report["proposals"]


@pytest.mark.parametrize("error_type",[ValueError,TimeoutError])
def test_caller_cancellation_during_pricing_is_never_converted_into_a_fallback(source,error_type):
    error = error_type("caller stopped optional optimization")
    def stop(stage):
        if stage == "fabrication_pricing_expand":
            raise error
    with pytest.raises(error_type) as caught:
        proposals(source,scenario(),checkpoint=stop)
    assert caught.value is error


def test_decimal_objective_policy_and_missing_dimension_are_bound(source):
    s = scenario({"fitting_count":.2})
    report = proposals(source,s)
    assert report["pricing_check"]["status"] == "PASS"
    assert report["pricing_objective"] == {"schema":"oma.fabrication-grid-cost/1","length_weight":"0","fitting_weight":"1/5"}
    assert report["pricing_certificate"]["cost"] == ["1/5","0"]
    changed = deepcopy(report["pricing_objective"])
    changed["fitting_weight"] = "1/4"
    from oma.optimization.fabrication_pricing import verify_fabrication_pricing
    assert verify_fabrication_pricing(report["model"],changed,report["pricing_certificate"])["status"] == "FAIL"
