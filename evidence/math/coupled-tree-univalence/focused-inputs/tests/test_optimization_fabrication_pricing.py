"""Finite pricing against complete small examples and altered proof objects."""
from copy import deepcopy
from decimal import Decimal, localcontext
from fractions import Fraction as Q
import itertools

import pytest

from oma.optimization import fabrication_pricing as pricing
from oma.optimization import fabrication_search as graph
from oma.store import digest
from test_optimization_fabrication_search import (
    problem, cube_simple_paths, tiny_impossible,
    check_path_with_separate_fixed_fabrication_kernel,
)


PI = Decimal("3.14159265358979323846264338327950288419716939937510582097494459230781640628620899")


def objective(length="1", fitting="0"):
    return {"schema": "oma.fabrication-grid-cost/1", "length_weight": length, "fitting_weight": fitting}


def certified(p=None, o=None, **budgets):
    p = problem() if p is None else p
    o = objective() if o is None else o
    c = pricing.compile_fabrication_pricing(p, o, **budgets)
    v = pricing.verify_fabrication_pricing(p, o, c, **budgets)
    assert c["status"] == "CERTIFIED", c
    assert v["status"] == "PASS", v
    return c, v


def reroot(c):
    c["certificate_root"] = digest({k: v for k, v in c.items() if k != "certificate_root"})
    return c


def decimal_cost(pair):
    def d(q):
        q = Q(q)
        return Decimal(q.numerator) / Decimal(q.denominator)
    return d(pair[0]) + d(pair[1]) * PI


def polyline_cost(points, radius, length_weight, fitting_weight):
    # Whole-polyline accounting, independently of deferred graph-edge charges.
    points = [tuple(Q(x) for x in p) for p in points]
    total = sum(sum(abs(a-b) for a,b in zip(p,q)) for p,q in zip(points,points[1:]))
    bends = len(points)-2
    return (length_weight*(total-2*radius*bends)+fitting_weight*bends,
            length_weight*radius*bends/2)


def test_full_polyline_cost_and_fitting_tradeoff_are_observable():
    p = problem()
    length_only, _ = certified(p, objective())
    fewer_fittings, _ = certified(p, objective(fitting="1"))
    assert length_only["cost"] == ["4", "1"]
    assert len(length_only["points_m"])-2 == 4
    assert fewer_fittings["cost"] == ["8", "1/4"]
    assert len(fewer_fittings["points_m"])-2 == 1
    for c, penalty in ((length_only,Q(0)), (fewer_fittings,Q(1))):
        assert tuple(map(Q,c["cost"])) == polyline_cost(c["points_m"],Q(1,2),Q(1),penalty)
        check_path_with_separate_fixed_fabrication_kernel(p,c)


@pytest.mark.parametrize("radius,weights",list(itertools.product(["1/8","1/4","3/8"],[("1","0"),("0","1"),("3/2","2/7")])))
def test_complete_small_cube_polyline_oracle(radius,weights):
    p=problem(grid_axes=[[0,1],[0,1],[0,1]],start=[0,0,0],goal=[1,1,1],diameter_m="1/16",bend_radius_m=radius)
    c,_=certified(p,objective(*weights))
    R=Q(radius);wL,wF=map(Q,weights)
    # All simple cube paths, with exact first/intermediate/final trim guards.
    costs=[]
    for path in cube_simple_paths():
        vectors=[tuple(b-a for a,b in zip(x,y)) for x,y in zip(path,path[1:])]
        corners=[path[0]]+[path[i] for i in range(1,len(path)-1) if vectors[i-1]!=vectors[i]]+[path[-1]]
        runs=[sum(abs(a-b) for a,b in zip(x,y)) for x,y in zip(corners,corners[1:])]
        if all(Q(run)-R*int(i>0)-R*int(i<len(runs)-1)>Q(1,8) for i,run in enumerate(runs)):
            costs.append(polyline_cost(corners,R,wL,wF))
    with localcontext() as context:
        context.prec=70
        assert costs
        oracle=min(costs,key=decimal_cost)
    assert tuple(map(Q,c["cost"])) == oracle
    # A cube run is exactly one leg, so every turn-only walk of n legs has n-1
    # bends. Its length increment per additional leg is 1-2R+pi*R/2>0 for
    # R<1/2. Thus cyclic walks cannot improve on a shortest three-leg walk.


@pytest.mark.parametrize("axis,sign",list(itertools.product(range(3),(-1,1))))
def test_straight_terminal_cost_is_charged_once(axis,sign):
    start=[2,2,1];goal=list(start);goal[axis]+=sign
    c,_=certified(problem(start=start,goal=goal),objective("7/3","100"))
    assert c["cost"]==["7/3","0"] and len(c["points_m"])==2


def test_fitting_only_zero_cost_edges_and_zero_cost_terminal():
    p=problem(goal=[4,0,1]);c,v=certified(p,objective("0","1"))
    assert c["cost"]==["0","0"] and v["pi_terms_used"]==0
    assert all(row["cost"]==["0","0"] for row in c["potentials"])


def test_no_path_proof_remains_a_complete_finite_cut_only():
    p=tiny_impossible();c,v=certified(p)
    assert c["pricing_outcome"]=="NO_PATH_IN_DECLARED_GRAPH"
    assert c["cost"] is None and not v["limitations"]["physical_route_infeasibility_claim"]
    c["closed_states"].pop()
    assert pricing.verify_fabrication_pricing(p,objective(),reroot(c))["status"]=="FAIL"


def test_sparse_dual_really_covers_omitted_valid_states():
    p=problem();c,_=certified(p)
    m=graph._prepare(p,12000,graph._Work(500000,None))
    explicit={tuple(row["state"]):tuple(map(Q,row["cost"])) for row in c["potentials"]}
    valid=[]
    for vertex in itertools.product(*(range(len(a)) for a in m["axes"])):
        for direction in range(6):
            for origin in range(len(m["axes"][direction//2])):
                for trim in (0,1):
                    try: valid.append(graph._valid_state(m,(*vertex,direction,origin,trim)))
                    except ValueError: pass
    omitted=set(valid)-set(explicit)
    assert len(omitted)>100 and explicit
    C=tuple(map(Q,c["cost"]));work=graph._Work(500000,None)
    comparison=pricing._Comparison(64,work,checker=True);cache={}
    # Exhaustively audit the theorem's default-region case on this small model.
    for state in omitted:
        for target,cost in pricing._checked_edges(m,(Q(1),Q(0)),state,work,cache):
            potential=explicit.get(target,C)
            assert min(cost)>=0 and comparison.compare(potential,pricing._plus(C,cost))<=0


@pytest.mark.parametrize("attack",["delete_source","delete_zero_successor","duplicate_label","raise_label","lower_label",
                                   "default","cost","path","points","scope","objective","graph"])
def test_rerooted_forgery_does_not_become_a_shortest_path_proof(attack):
    p=problem();o=objective();c,_=certified(p,o)
    if attack=="delete_source":c["potentials"]=[r for r in c["potentials"] if r["state"][3]!=-1]
    elif attack=="delete_zero_successor":
        index=next(i for i,r in enumerate(c["potentials"]) if r["state"][3]>=0 and r["cost"]==["0","0"])
        c["potentials"].pop(index)
    elif attack=="duplicate_label":c["potentials"].append(deepcopy(c["potentials"][0]))
    elif attack=="raise_label":c["potentials"][0]["cost"]=["10000","0"]
    elif attack=="lower_label":c["potentials"][0]["cost"]=["-1","0"]
    elif attack=="default":c["default_potential"]=["0","0"]
    elif attack=="cost":c["cost"]=c["default_potential"]=["5","1"]
    elif attack=="path":c["path_states"].pop(1)
    elif attack=="points":c["points_m"][0][0]="99"
    elif attack=="scope":c["limitations"]["continuous_route_completeness"]=True
    elif attack=="objective":c["objective"]["fitting_weight"]="99"
    elif attack=="graph":c["graph_root"]="another-graph"
    assert pricing.verify_fabrication_pricing(p,o,reroot(c))["status"]=="FAIL"


def test_real_admissible_but_more_expensive_route_cannot_claim_optimality():
    p=problem();o=objective();c,_=certified(p,o)
    other=graph.compile_fabrication_search(p)
    assert graph.verify_fabrication_search(p,other)["status"]=="PASS"
    cost=polyline_cost(other["points_m"],Q(1,2),Q(1),Q(0))
    assert decimal_cost(cost)>decimal_cost(c["cost"])
    c.update(path_states=other["path_states"],points_m=other["points_m"],cost=list(map(str,cost)),default_potential=list(map(str,cost)))
    v=pricing.verify_fabrication_pricing(p,o,reroot(c))
    assert v["status"]=="FAIL" and "dual-edge" in v["reason"]


def test_pi_interval_independent_formulas_and_known_enclosure():
    for terms in (1,2,4,8,32):
        a=pricing._producer_pi_interval(terms,graph._Work(10000,None))
        b=pricing._checker_pi_interval(terms,graph._Work(10000,None))
        assert a==b and a[0]<Q(PI)<a[1]
    assert Q(103993,33102)<Q(PI)<Q(104348,33215)


def test_pi_precision_is_unknown_instead_of_an_uncertified_tie():
    cmp=pricing._Comparison(1,graph._Work(10000,None))
    with pytest.raises(graph._Exhausted,match="PRECISION"):
        cmp.compare((Q(355,113),Q(0)),(Q(0),Q(1)))
    cmp=pricing._Comparison(64,graph._Work(10000,None),checker=True)
    assert cmp.compare((Q(355,113),Q(0)),(Q(0),Q(1)))==1
    assert cmp.terms>1
    assert cmp.compare((Q(1),Q(2)),(Q(1),Q(2)))==0


def test_public_search_and_checker_keep_near_equal_pi_costs_unknown_when_budgeted():
    p=problem();o=objective(fitting="97/452")
    # This rational fitting penalty is extremely close to 1-pi/4, the cost
    # tradeoff per added R=1/2 quarter bend on equal Manhattan-length paths.
    c,v=certified(p,o,max_pi_terms=64)
    assert c["pi_terms_used"]>1 and v["pi_terms_used"]>1
    for result in (pricing.compile_fabrication_pricing(p,o,max_pi_terms=1),
                   pricing.verify_fabrication_pricing(p,o,c,max_pi_terms=1)):
        assert result["status"]=="UNKNOWN" and result["reason"]=="PI_COMPARISON_PRECISION_BUDGET"


@pytest.mark.parametrize("limits",[{"max_states":1},{"max_work":5}])
def test_search_and_verifier_budgets_are_not_proofs(limits):
    p=problem();o=objective();c,_=certified(p,o)
    assert pricing.compile_fabrication_pricing(p,o,**limits)["status"]=="UNKNOWN"
    assert pricing.verify_fabrication_pricing(p,o,c,**limits)["status"]=="UNKNOWN"


@pytest.mark.parametrize("weights",[("-1","1"),("1","-1"),("0","0"),(float("inf"),"0"),(True,"1")])
def test_negative_zero_or_nonfinite_objective_is_rejected(weights):
    with pytest.raises(ValueError):
        pricing.compile_fabrication_pricing(problem(),objective(*weights))


def test_checker_never_calls_solver_producer_edges_or_pi(monkeypatch):
    p=problem();o=objective();c,_=certified(p,o)
    def forbidden(*args,**kwargs):raise AssertionError("Producer used during verification")
    for name in ("compile_fabrication_pricing","_producer_edge_cost","_producer_pi_interval"):
        monkeypatch.setattr(pricing,name,forbidden)
    monkeypatch.setattr(graph,"_producer_successors",forbidden)
    assert pricing.verify_fabrication_pricing(p,o,c)["status"]=="PASS"


def test_checkpoint_exception_propagates_during_each_phase_and_does_not_change_certificate():
    p=problem();o=objective();c,_=certified(p,o)
    phases=[]
    assert pricing.compile_fabrication_pricing(p,o,checkpoint=phases.append)==c
    for function,stage in ((pricing.compile_fabrication_pricing,"fabrication_pricing_expand"),
                           (pricing.verify_fabrication_pricing,"fabrication_pricing_dual_verify"),
                           (pricing.verify_fabrication_pricing,"fabrication_pricing_verified")):
        def cancel(value):
            if value==stage:raise ValueError("caller cancelled")
        args=(p,o,c) if function==pricing.verify_fabrication_pricing else (p,o)
        with pytest.raises(ValueError,match="caller cancelled"):
            function(*args,checkpoint=cancel)
    assert "fabrication_pricing_complete" in phases


def test_cost_encoding_cannot_expand_a_huge_decimal_exponent():
    p=problem();o=objective();c,_=certified(p,o)
    c["cost"]=["1e999999999","0"]
    assert pricing.verify_fabrication_pricing(p,o,reroot(c))["status"]=="FAIL"


def native_priced_wall_case(directory):
    from oma.ifc.audit import sha256_file
    from oma.ifc.cad import cad_check_routes
    from oma.ifc.export import export_route
    from oma.routing.checker import _semantics
    from oma.routing.scenario import RoutingScenario
    from test_ifc_pipeline import make_fixture
    from test_optimization_fabrication import actual_ifc_correspondence
    directory.mkdir(parents=True,exist_ok=True)
    source=make_fixture(directory/"source.ifc")
    before=sha256_file(source)
    p=problem(allowed_bounds=[[-2,-2,-1],[4,4,3]],grid_axes=[[-1,0,1,2,3],[-1,0,1,2,3],["1/2",1]],
              start=[-1,1,1],goal=[3,1,1],source_roots={"source_bytes":before,"outer_cover":"ANALYTIC_INTEGER_BOX_0_TO_2_METRES"},
              outer_obstacles=[{"id":"actual-analytic-wall","bounds":[[0,0,0],[2,2,2]]}])
    o=objective("1","1/5")
    c,v=certified(p,o)
    exact=check_path_with_separate_fixed_fabrication_kernel(p,c)
    points=[[float(Q(x)) for x in point] for point in c["points_m"]]
    scenario=RoutingScenario(start=points[0],end=points[-1],system_type="PRESSURE_PIPE",diameter_m=.25,
        insulation_m=0,bend_radius_m=.5,minimum_straight_m=.125,clearance_m=.125,
        allowed_zone={"min":p["allowed_bounds"][0],"max":p["allowed_bounds"][1]},scenario_terminals=True)
    spec={"route_id":"priced-fabrication-native-wall","points_m":points,"system_type":scenario.system_type,
        "diameter_m":scenario.diameter_m,"insulation_m":scenario.insulation_m,"bend_radius_m":scenario.bend_radius_m,
        "minimum_straight_m":scenario.minimum_straight_m,"assumption_root":digest(scenario.model_dump(mode="json"))}
    output=directory/"route.ifc"
    manifest=export_route(source,output,spec,fresh_recheck=False)
    correspondence=actual_ifc_correspondence(output,manifest,exact)
    physical=cad_check_routes([source],output,{part["ifc_guid"] for part in manifest["added_parts"]},clearance_m=scenario.clearance_m)
    assert physical["coordination_status"]=="PASS" and physical["self_interference_status"]=="PASS",physical
    assert physical["obstacle_count"]==1 and physical["pairs_accounted"]==len(manifest["added_parts"])
    semantics=_semantics(output,source,manifest,scenario)
    assert semantics["errors"]==[],semantics
    assert sha256_file(source)==before
    assert tuple(map(Q,c["cost"]))==polyline_cost(c["points_m"],Q(1,2),Q(1),Q(1,5))
    return {"scope":"FINITE_GRAPH_NOMINAL_COST_OPTIMUM_AND_SEPARATE_ACTUAL_NATIVE_WALL_CHECK",
            "source_sha256":before,"export_sha256":sha256_file(output),"model":p,"objective":o,
            "certificate":c,"independent_check":v,"fixed_polyline_certificate":exact,
            "actual_native_correspondence":correspondence,"actual_native_coordination":physical,
            "actual_semantics":semantics,"original_source_unchanged":True,
            "native_objective_optimality":False,"candidate_accepted":False,"continuous_optimality":False}


def test_actual_ifc_priced_wall_path_has_independent_native_correspondence(tmp_path):
    result=native_priced_wall_case(tmp_path)
    assert result["independent_check"]["pricing_outcome"]=="OPTIMAL_PATH"
    assert result["actual_native_coordination"]["pairs_accounted"]>=5
