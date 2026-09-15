"""Finite fabrication graph witnesses against exact constructions and attacks."""
from copy import deepcopy
from fractions import Fraction as Q
import itertools

import pytest

from oma.optimization import fabrication_search as search
from oma.optimization.fabrication import compile_orthogonal_fabrication,verify_orthogonal_fabrication
from oma.routing.scenario import RoutingScenario
from oma.store import digest


def problem(**updates):
    value={"schema":"oma.fabrication-grid-problem/1","context_root":"fixed-synthetic-context",
        "source_roots":{"outer_cover":"complete-declared-box-family","frame":"common-metres"},
        "allowed_bounds":[[-1,-1,-1],[5,5,3]],"grid_axes":[[0,1,2,3,4],[0,1,2,3,4],[0,1,2]],
        "start":[0,0,1],"goal":[4,4,1],"diameter_m":"1/4","insulation_m":"0",
        "bend_radius_m":"1/2","minimum_straight_m":"1/8","clearance_m":"1/8","outer_obstacles":[]}
    value.update(updates)
    return value


def certified(p,**budgets):
    c=search.compile_fabrication_search(p,**budgets)
    v=search.verify_fabrication_search(p,c,**budgets)
    assert c["status"]=="CERTIFIED",c
    assert v["status"]=="PASS",v
    assert v["geometry_outcome"]==c["geometry_outcome"]
    return c,v


def check_path_with_separate_fixed_fabrication_kernel(p,c):
    points=[[float(Q(x)) for x in point] for point in c["points_m"]]
    scenario=RoutingScenario(start=points[0],end=points[-1],system_type="PRESSURE_PIPE",
        diameter_m=float(Q(p["diameter_m"])),insulation_m=float(Q(p["insulation_m"])),
        bend_radius_m=float(Q(p["bend_radius_m"])),minimum_straight_m=float(Q(p["minimum_straight_m"])),
        clearance_m=float(Q(p["clearance_m"])),allowed_zone={"min":p["allowed_bounds"][0],"max":p["allowed_bounds"][1]},scenario_terminals=True)
    kw={"context_root":"separate-full-polyline","outer_obstacles":p["outer_obstacles"],"outer_model_root":"declared-box-family"}
    exact=compile_orthogonal_fabrication(scenario,points,**kw)
    checked=verify_orthogonal_fabrication(scenario,points,exact,**kw)
    assert exact["status"]=="PASS",exact
    assert checked["status"]=="PASS" and checked["fabrication_status"]=="PASS"
    return exact


def test_search_retains_direction_and_bend_debt_then_full_fabrication_verifies():
    p=problem();c,v=certified(p)
    assert c["geometry_outcome"]=="PATH" and len(c["path_states"])>len(c["points_m"])
    exact=check_path_with_separate_fixed_fabrication_kernel(p,c)
    assert any(s[5]==1 for s in c["path_states"]) and exact["transitions"]
    assert not v["limitations"]["length_optimality_claim"]


@pytest.mark.parametrize("axis,sign",list(itertools.product(range(3),(-1,1))))
def test_each_signed_straight_direction_is_supported(axis,sign):
    start=[2,2,1];end=list(start);end[axis]+=sign
    c,_=certified(problem(start=start,goal=end))
    assert len(c["points_m"])==2


def test_blocked_direct_line_finds_a_real_two_bend_detour():
    p=problem(goal=[4,0,1],outer_obstacles=[{"id":"wall","bounds":[[1.75,-.5,-.5],[2.25,1.25,2.5]]}])
    c,_=certified(p)
    assert c["geometry_outcome"]=="PATH"
    assert any(Q(point[1])>=2 for point in c["points_m"])
    exact=check_path_with_separate_fixed_fabrication_kernel(p,c)
    assert len(exact["transitions"])>=2


def test_turn_envelope_rejects_a_corner_whose_two_straight_legs_are_clear():
    p=problem(grid_axes=[[0,1,2],[0,1,2],[0,1]],start=[0,0,0],goal=[2,2,0],
        diameter_m="1/16",bend_radius_m="3/4",clearance_m="0",
        outer_obstacles=[{"id":"inside-corner","bounds":[["7/4","19/100","-1/10"],["181/100","1/4","1/10"]]}])
    # The rational centre-line point (R*sin(theta),-R*cos(theta)) with
    # sin=20/29, cos=21/29 lies inside the obstacle at the (2,0) bend.
    point=(Q(5,4)+Q(3,4)*Q(20,29),Q(3,4)-Q(3,4)*Q(21,29))
    assert Q(7,4)<point[0]<Q(181,100) and Q(19,100)<point[1]<Q(1,4)
    c,_=certified(p)
    assert ["2","0","0"] not in c["points_m"]
    check_path_with_separate_fixed_fabrication_kernel(p,c)


def cube_simple_paths():
    goal=(1,1,1)
    def visit(path):
        if path[-1]==goal:
            yield path;return
        for axis in range(3):
            successor=tuple(1-x if i==axis else x for i,x in enumerate(path[-1]))
            if successor not in path:yield from visit([*path,successor])
    return list(visit([(0,0,0)]))


@pytest.mark.parametrize("radius",["1/8","1/4","3/8","7/16","1/2","3/4","1"])
def test_small_cube_exhaustive_polyline_oracle_matches_graph_reachability(radius):
    p=problem(grid_axes=[[0,1],[0,1],[0,1]],start=[0,0,0],goal=[1,1,1],
        diameter_m="1/16",bend_radius_m=radius,minimum_straight_m="1/8")
    scenario=RoutingScenario(start=(0,0,0),end=(1,1,1),system_type="PRESSURE_PIPE",diameter_m=1/16,
        insulation_m=0,bend_radius_m=float(Q(radius)),minimum_straight_m=1/8,clearance_m=1/8,
        allowed_zone={"min":[-1,-1,-1],"max":[5,5,3]},scenario_terminals=True)
    paths=cube_simple_paths()
    statuses=[compile_orthogonal_fabrication(scenario,path,context_root="exhaustive-cube-oracle")["status"] for path in paths]
    exists="PASS" in statuses
    # Every route to the opposite cube corner needs at least two turns; a run
    # is at most one unit, so cycles cannot rescue an unpaid middle-leg debt.
    assert exists==(1-2*Q(radius)>Q(1,8))
    c,_=certified(p)
    assert (c["geometry_outcome"]=="PATH")==exists


def tiny_impossible():
    return problem(grid_axes=[[0,"1/2"],[0,"1/2"],[0,"1/2"]],start=[0,0,0],goal=["1/2","1/2",0],bend_radius_m="1")


def test_zero_width_grid_path_exists_but_no_fabrication_state_can_pay_turn_debt():
    p=tiny_impossible();c,v=certified(p)
    assert c["geometry_outcome"]=="NO_PATH_IN_DECLARED_GRAPH"
    # All eight geometric vertices and cube edges are unobstructed. Each leg is
    # only 1/2 m, so no turn can pay even the first one-metre trim plus minimum.
    assert c["vertex_count"]==8 and len(c["closed_states"])==4
    assert not v["limitations"]["physical_route_infeasibility_claim"]


def test_exact_threshold_and_insulation_have_observable_search_effects():
    p=problem(grid_axes=[[0,"3/4"],[0,"3/4"],[0,"3/4"]],start=[0,0,0],goal=["3/4","3/4",0],minimum_straight_m="1/4")
    c,_=certified(p);assert c["geometry_outcome"]=="NO_PATH_IN_DECLARED_GRAPH"
    p["minimum_straight_m"]="1/8"
    c,_=certified(p);assert c["geometry_outcome"]=="PATH"
    check_path_with_separate_fixed_fabrication_kernel(p,c)
    p["insulation_m"]="1/2"
    with pytest.raises(ValueError,match="bend greater"):
        search.compile_fabrication_search(p)


def test_early_short_grid_steps_can_accumulate_sufficient_straight_before_turning():
    p=problem(grid_axes=[["0","1/4","1/2"],["0","1/4","1/2"],["0","1/4"]],
        start=[0,0,0],goal=["1/2","1/2",0],diameter_m="1/16",bend_radius_m="1/4",minimum_straight_m="1/16")
    c,_=certified(p)
    assert len(c["path_states"])==5 and len(c["points_m"])==3
    check_path_with_separate_fixed_fabrication_kernel(p,c)


def resign(c):
    c.pop("certificate_root",None);c["certificate_root"]=digest(c)


@pytest.mark.parametrize("fault",["remove_state","wrong_direction","erase_trim","move_origin","false_goal",
    "change_points","physical_claim","numeric_scope","boolean_state","false_rule"])
def test_forged_path_and_scope_witnesses_are_rejected(fault):
    p=problem();c,_=certified(p)
    if fault=="remove_state":c["path_states"].pop(1)
    elif fault=="wrong_direction":c["path_states"][1][3]=(c["path_states"][1][3]+2)%6
    elif fault=="erase_trim":next(s for s in c["path_states"] if s[5]==1)[5]=0
    elif fault=="move_origin":c["path_states"][1][4]=1
    elif fault=="false_goal":c["path_states"].pop()
    elif fault=="change_points":c["points_m"][0][0]="1/16"
    elif fault=="physical_claim":c["limitations"]["physical_route_infeasibility_claim"]=True
    elif fault=="numeric_scope":c["limitations"]["length_optimality_claim"]=0
    elif fault=="boolean_state":c["path_states"][0][0]=False
    elif fault=="false_rule":c["rule"]="UNVERIFIED_SHORTCUT"
    resign(c)
    assert search.verify_fabrication_search(p,c)["status"]=="FAIL"


def test_cut_closure_cannot_omit_an_admissible_successor_or_duplicate_states():
    p=tiny_impossible();original,_=certified(p)
    for mode in ("omit","duplicate","source"):
        c=deepcopy(original)
        if mode=="omit":c["closed_states"].pop()
        elif mode=="duplicate":c["closed_states"].append(c["closed_states"][-1])
        else:c["closed_states"]=[s for s in c["closed_states"] if s[3]!=-1]
        resign(c)
        assert search.verify_fabrication_search(p,c)["status"]=="FAIL"


def test_input_model_and_source_root_changes_invalidate_certificate():
    p=problem();c,_=certified(p)
    for key,value in (("clearance_m","1/4"),("context_root","different"),("source_roots",{"outer":"different"})):
        changed=deepcopy(p);changed[key]=value
        assert search.verify_fabrication_search(changed,c)["status"]=="FAIL"


@pytest.mark.parametrize("limits",[{"max_states":1},{"max_work":1},{"max_work":100}])
def test_budget_limits_are_unknown_without_false_exhaustion_proof(limits):
    c=search.compile_fabrication_search(problem(),**limits)
    assert c["status"]=="UNKNOWN" and not c["proof_complete"]
    assert "physical_route_infeasibility_claim" in c["limitations"] and not c["limitations"]["physical_route_infeasibility_claim"]


def test_independent_verifier_has_its_own_work_and_state_budget():
    p=problem();c,_=certified(p)
    assert search.verify_fabrication_search(p,c,max_work=1)["status"]=="UNKNOWN"
    assert search.verify_fabrication_search(p,c,max_states=1)["status"]=="UNKNOWN"


def test_verifier_does_not_invoke_producer_search_or_geometry(monkeypatch):
    p=problem();c,_=certified(p)
    def forbidden(*args,**kwargs):raise AssertionError("producer invoked by checker")
    for name in ("compile_fabrication_search","_producer_successors","_producer_straight_bounds","_producer_bend_bounds"):
        monkeypatch.setattr(search,name,forbidden)
    assert search.verify_fabrication_search(p,c)["status"]=="PASS"


@pytest.mark.parametrize("verify",[False,True])
def test_checkpoint_interruptions_propagate_even_when_they_are_value_errors(verify):
    p=problem();c,_=certified(p);calls=[];interruption=ValueError("caller cancellation")
    def callback(stage):
        calls.append(stage)
        if len(calls)==3:raise interruption
    with pytest.raises(ValueError) as error:
        if verify:search.verify_fabrication_search(p,c,checkpoint=callback)
        else:search.compile_fabrication_search(p,checkpoint=callback)
    assert error.value is interruption


def test_callbacks_do_not_change_deterministic_certificate():
    p=problem();first=search.compile_fabrication_search(p)
    stages=[];second=search.compile_fabrication_search(p,checkpoint=stages.append)
    assert first==second and stages


def native_wall_case(directory,*,millimeters=False):
    from oma.ifc.audit import sha256_file
    from oma.ifc.cad import cad_check_routes
    from oma.ifc.export import export_route
    from oma.routing.checker import _semantics
    from test_ifc_pipeline import make_fixture
    from test_optimization_fabrication import actual_ifc_correspondence
    directory.mkdir(parents=True,exist_ok=True)
    source=make_fixture(directory/"source.ifc",millimeters=millimeters)
    before=sha256_file(source)
    p=problem(allowed_bounds=[[-2,-2,-1],[4,4,3]],grid_axes=[[-1,0,1,2,3],[-1,0,1,2,3],["1/2",1]],
        start=[-1,1,1],goal=[3,1,1],source_roots={"source_bytes":before,"outer_cover":"ANALYTIC_INTEGER_BOX_0_TO_2_METRES"},
        outer_obstacles=[{"id":"actual-analytic-wall","bounds":[[0,0,0],[2,2,2]]}])
    c,v=certified(p)
    exact=check_path_with_separate_fixed_fabrication_kernel(p,c)
    points=[[float(Q(x)) for x in point] for point in c["points_m"]]
    scenario=RoutingScenario(start=points[0],end=points[-1],system_type="PRESSURE_PIPE",diameter_m=.25,
        insulation_m=0,bend_radius_m=.5,minimum_straight_m=.125,clearance_m=.125,
        allowed_zone={"min":p["allowed_bounds"][0],"max":p["allowed_bounds"][1]},scenario_terminals=True)
    spec={"route_id":"fabrication-graph-native-wall","points_m":points,"system_type":scenario.system_type,
        "diameter_m":scenario.diameter_m,"insulation_m":scenario.insulation_m,"bend_radius_m":scenario.bend_radius_m,
        "minimum_straight_m":scenario.minimum_straight_m,"assumption_root":digest(scenario.model_dump(mode="json"))}
    output=directory/"route.ifc"
    manifest=export_route(source,output,spec,fresh_recheck=False)
    correspondence=actual_ifc_correspondence(output,manifest,exact)
    physical=cad_check_routes([source],output,{p["ifc_guid"] for p in manifest["added_parts"]},clearance_m=scenario.clearance_m)
    assert physical["coordination_status"]=="PASS" and physical["self_interference_status"]=="PASS",physical
    assert physical["obstacle_count"]==1 and physical["pairs_accounted"]==len(manifest["added_parts"])
    semantics=_semantics(output,source,manifest,scenario)
    assert semantics["errors"]==[],semantics
    assert sha256_file(source)==before
    return {"scope":"EXACT_FINITE_FABRICATION_SEARCH_AND_SEPARATE_ACTUAL_NATIVE_WALL_COORDINATION",
        "source_sha256":before,"export_sha256":sha256_file(output),"source_units":"MILLIMETRES" if millimeters else "METRES",
        "model":p,"certificate":c,"independent_check":v,"fixed_polyline_certificate":exact,
        "actual_native_correspondence":correspondence,"actual_native_coordination":physical,"actual_semantics":semantics,
        "original_source_unchanged":True,"candidate_accepted":False,"physical_route_universe_complete":False}


@pytest.mark.parametrize("millimeters",[False,True])
def test_actual_ifc_wall_detour_constructs_checked_fittings_and_complete_clearance(tmp_path,millimeters):
    result=native_wall_case(tmp_path,millimeters=millimeters)
    assert result["independent_check"]["geometry_outcome"]=="PATH"
    assert result["actual_native_coordination"]["pairs_accounted"]>=5
