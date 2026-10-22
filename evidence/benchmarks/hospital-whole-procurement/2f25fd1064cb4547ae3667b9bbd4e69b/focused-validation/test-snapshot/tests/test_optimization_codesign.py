from copy import deepcopy
from dataclasses import replace
from fractions import Fraction as Q
import pytest

from oma.optimization.master import MasterProblem,RouteColumn
from oma.optimization.finite import FiniteOutcome
from oma.optimization.codesign import DesignCase,FiniteCoDesignProblem,solve_finite_codesign,verify_finite_codesign_result


def case(name,capacity,capital=0,complete=True,verdict="PASS"):
    root = "candidate-root:"+name
    columns = (RouteColumn("a-primary","a",1,(("shared-zone",1),)),RouteColumn("a-bypass","a",2),
        RouteColumn("b-primary","b",1,(("shared-zone",1),)),RouteColumn("b-bypass","b",100))
    master = MasterProblem(("a","b"),columns,(("shared-zone",capacity),),(),root,declared_universe_complete=complete)
    return DesignCase(name,(("shaft",name),("fire-compartment","A")),root,capital,
        FiniteOutcome("materialization:"+name,verdict,0 if verdict == "PASS" else None,evidence_root="materialization-check:"+name),
        master if verdict == "PASS" else None)


def problem():
    return FiniteCoDesignProblem((case("east",1),case("west",2,Q(1,2))),(("shaft",("east","west")),),
        (("fire-compartment","A"),),"strategic-schema-v1",True)


def test_joint_design_and_shared_capacity_are_optimized_with_candidate_roots():
    p = problem()
    result = solve_finite_codesign(p)
    assert result["status"] == "FINITE_CODESIGN_MASTER_OPTIMAL"
    assert result["selected_design_id"] == "west" and result["cost"] == "5/2"
    assert result["case_results"]["east"]["objective"] == "3"
    assert result["case_results"]["west"]["objective"] == "2"
    assert verify_finite_codesign_result(p,result)["status"] == "PASS"


def test_unknown_materialization_and_incomplete_route_universe_block_optimum():
    p = problem()
    unknown = replace(p,cases=(p.cases[0],case("west",2,verdict="UNKNOWN")))
    result = solve_finite_codesign(unknown)
    assert result["status"] == "FINITE_CODESIGN_MASTER_FEASIBLE" and result["unresolved"] == ["west"]
    assert verify_finite_codesign_result(unknown,result)["status"] == "PASS"
    incomplete = replace(p,cases=(p.cases[0],case("west",2,complete=False)))
    result = solve_finite_codesign(incomplete)
    assert result["status"] == "FINITE_CODESIGN_MASTER_FEASIBLE" and "west:unresolved-routing" in result["unresolved"]
    assert verify_finite_codesign_result(incomplete,result)["status"] == "PASS"


def test_sovereignty_domain_completeness_and_stale_roots_are_enforced():
    p = problem()
    with pytest.raises(ValueError,match="Protected"):
        replace(p,cases=(replace(p.cases[0],assignment=(("shaft","east"),("fire-compartment","B"))),p.cases[1]))
    with pytest.raises(ValueError,match="every assignment"):
        replace(p,cases=(p.cases[0],))
    with pytest.raises(ValueError,match="candidate root"):
        replace(p.cases[0],design_root="wrong")
    result = solve_finite_codesign(p)
    changed = replace(p,context_root="strategic-schema-v2")
    assert verify_finite_codesign_result(changed,result)["reason"] == "STALE_CODESIGN_PROBLEM"


def test_checker_rejects_cheap_fake_incumbent_omitted_case_and_unknown_infeasibility():
    p = problem()
    result = solve_finite_codesign(p)
    bad = deepcopy(result)
    bad["cost"] = "0"
    assert verify_finite_codesign_result(p,bad)["status"] == "FAIL"
    bad = deepcopy(result)
    del bad["case_results"]["east"]
    assert verify_finite_codesign_result(p,bad)["status"] == "FAIL"
    bad = deepcopy(result)
    for route in bad["case_results"].values():
        route.update(status="MASTER_UNKNOWN",selected=(),objective=None,lower_bound=None,search_exhausted=True)
    bad.update(status="FINITE_CODESIGN_MASTER_INFEASIBLE",selected_design_id=None,selected_design_root=None,cost=None,lower_bound=None,unresolved=[])
    assert verify_finite_codesign_result(p,bad)["status"] == "FAIL"


def test_cancellation_and_budget_preserve_unresolved_designs():
    p = problem()
    limited = solve_finite_codesign(p,max_nodes=1)
    assert limited["status"] == "FINITE_CODESIGN_MASTER_UNKNOWN" and limited["unresolved"]
    assert verify_finite_codesign_result(p,limited)["status"] == "PASS"
    cancelled = solve_finite_codesign(p,cancelled=lambda: True)
    assert cancelled["status"] == "FINITE_CODESIGN_MASTER_UNKNOWN"
    assert verify_finite_codesign_result(p,cancelled)["status"] == "PASS"
    assert verify_finite_codesign_result(p,solve_finite_codesign(p),max_combinations=1)["status"] == "UNKNOWN"
