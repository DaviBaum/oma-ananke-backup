"""Coordinate enrichment invariants, exact source witnesses and fabrication use."""
from copy import deepcopy
from fractions import Fraction as Q
from itertools import permutations

import pytest

from oma.routing import fabrication_grid as grid
from oma.optimization import fabrication_pricing as pricing
from oma.optimization import fabrication_search as graph
from oma.store import digest


def inputs():
    return {"base_axes":[[0,2,4],[0,2,4],[0,2,4]],"start":[0,2,2],"goal":[4,2,2],
            "allowed_bounds":[[-1,-1,-1],[5,5,5]],"outer_obstacles":[{"id":"wall","bounds":[[1,1,1],[3,3,3]]}],
            "radius_m":"1/8","clearance_m":"1/4"}


def certify(args=None,**kw):
    args=inputs() if args is None else args
    result=grid.enrich_fabrication_grid(**args,**kw)
    checked=grid.verify_fabrication_grid_enrichment(**args,result=result,**kw)
    assert result["status"]=="PROPOSED_GRID",result
    assert checked["status"]=="PASS",checked
    return result,checked


def reroot(result):
    result["result_root"]=digest({k:v for k,v in result.items() if k!="result_root"})
    return result


def test_exact_face_offsets_retain_complete_baseline_and_source_denominator():
    args=inputs();before=deepcopy(args);r,v=certify(args)
    assert args==before and v["source_planes_accounted"]==6
    for old,new in zip(args["base_axes"],r["grid_axes"]):
        assert set(map(Q,old))<=set(map(Q,new))
    assert all(Q("0.624999") in set(map(Q,a)) and Q("3.375001") in set(map(Q,a)) for a in r["grid_axes"])
    assert not v["limitations"]["free_space_or_route_certificate"]


def test_first_and_two_trim_seeds_are_exact_generic_thresholds():
    args=inputs();r,v=certify(args,bend_radius_m="1/2",minimum_straight_m="1/4")
    assert v["source_planes_accounted"]==30
    first=next(x for x in r["plane_records"] if x["key"]==["TERMINAL_FIRST_TURN","start",0,1])
    second=next(x for x in r["plane_records"] if x["key"]==["TERMINAL_TWO_TRIM","start",0,1])
    assert Q(first["value"])==Q("0.750001") and Q(second["value"])==Q("1.250001")


@pytest.mark.parametrize("permutation",list(permutations(range(3))))
def test_axis_permutations_preserve_coordinate_choices_under_default_caps(permutation):
    args=inputs();r,_=certify(args,bend_radius_m="1/2",minimum_straight_m="1/4")
    def permute(point):return [point[i] for i in permutation]
    other=deepcopy(args)
    other["base_axes"]=permute(args["base_axes"])
    for key in ("start","goal"):other[key]=permute(args[key])
    other["allowed_bounds"]=list(map(permute,args["allowed_bounds"]))
    for item in other["outer_obstacles"]:item["bounds"]=list(map(permute,item["bounds"]))
    transformed,_=certify(other,bend_radius_m="1/2",minimum_straight_m="1/4")
    assert transformed["grid_axes"]==permute(r["grid_axes"])


def test_small_global_budget_balances_available_axes_instead_of_filling_first():
    r,_=certify(max_vertices=125,max_axis_values=32)
    assert list(map(len,r["grid_axes"]))==[5,5,5]
    assert r["proposed_vertices"]==125


def test_tight_product_budget_and_axis_budget_have_checked_dispositions():
    r,_=certify(max_vertices=50,max_axis_values=32)
    assert r["proposed_vertices"]<=50
    assert any(row["disposition"]=="GRID_VERTEX_BUDGET" for row in r["plane_records"])
    r,_=certify(max_axis_values=3)
    assert r["proposed_vertices"]==27 and all(row["disposition"]=="AXIS_VALUE_BUDGET" for row in r["plane_records"])


@pytest.mark.parametrize("attack",["drop_baseline","fake_plane","missing_plane","duplicate_plane","phantom_coordinate",
                                   "wrong_guard","false_budget","scope","count","retained_missing"])
def test_forged_coordinate_and_coverage_claims_fail_independent_verifier(attack):
    args=inputs();r,_=certify(args)
    if attack=="drop_baseline":r["grid_axes"][0].remove("2")
    elif attack=="fake_plane":r["plane_records"][0]["value"]="1/3"
    elif attack=="missing_plane":r["plane_records"].pop()
    elif attack=="duplicate_plane":r["plane_records"][-1]=deepcopy(r["plane_records"][0])
    elif attack=="phantom_coordinate":r["grid_axes"][0]=sorted([*r["grid_axes"][0],"1/3"],key=Q)
    elif attack=="wrong_guard":r["input"]["guard_m"]="1/100"
    elif attack=="false_budget":r["plane_records"][0]["disposition"]="GRID_VERTEX_BUDGET"
    elif attack=="scope":r["limitations"]["native_acceptance_authority"]=True
    elif attack=="count":r["proposed_vertices"]+=1
    elif attack=="retained_missing":r["grid_axes"][0].remove(r["plane_records"][0]["value"])
    assert grid.verify_fabrication_grid_enrichment(**args,result=reroot(r))["status"]=="FAIL"


def test_duplicate_boxes_reject_but_duplicate_face_coordinates_are_accounted():
    args=inputs();args["outer_obstacles"].append(deepcopy(args["outer_obstacles"][0]))
    with pytest.raises(ValueError,match="Unique"):
        grid.enrich_fabrication_grid(**args)
    args["outer_obstacles"][-1]["id"]="same-support-another-source"
    r,v=certify(args)
    assert v["source_planes_accounted"]==12
    assert sum(x["disposition"]=="ADDED_COORDINATE" for x in r["plane_records"])==6
    assert sum(x["disposition"]=="RETAINED_COORDINATE" for x in r["plane_records"])==6


@pytest.mark.parametrize("change",[{"guard_m":"0"},{"guard_m":"-1"},{"radius_m":"0"},{"clearance_m":"-1"}])
def test_invalid_physical_or_search_offsets_are_rejected(change):
    args=inputs();args.update(change)
    with pytest.raises(ValueError):grid.enrich_fabrication_grid(**args)


def test_budget_never_silently_drops_baseline_and_cancellation_propagates():
    args=inputs()
    assert grid.enrich_fabrication_grid(**args,max_vertices=8)["status"]=="UNKNOWN"
    assert grid.enrich_fabrication_grid(**args,max_work=1)["status"]=="UNKNOWN"
    r,_=certify(args)
    for function,stage in ((grid.enrich_fabrication_grid,"fabrication_grid_allocate"),
                           (grid.enrich_fabrication_grid,"fabrication_grid_complete"),
                           (grid.verify_fabrication_grid_enrichment,"fabrication_grid_verified")):
        def cancel(current):
            if current==stage:raise ValueError("caller cancelled")
        kw={"result":r} if function==grid.verify_fabrication_grid_enrichment else {}
        with pytest.raises(ValueError,match="caller cancelled"):
            function(**args,**kw,checkpoint=cancel)


def test_checker_does_not_call_producer_or_priority_generation(monkeypatch):
    args=inputs();r,_=certify(args,bend_radius_m="1/2",minimum_straight_m="1/4")
    def forbidden(*a,**k):raise AssertionError("producer used")
    monkeypatch.setattr(grid,"enrich_fabrication_grid",forbidden)
    monkeypatch.setattr(grid,"_candidates",forbidden)
    assert grid.verify_fabrication_grid_enrichment(**args,result=r,bend_radius_m="1/2",minimum_straight_m="1/4")["status"]=="PASS"
