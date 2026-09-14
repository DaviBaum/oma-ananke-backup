from copy import deepcopy
from dataclasses import replace
from fractions import Fraction as Q

from oma.optimization.finite import FiniteOutcome
from oma.optimization.policy import Scenario, LeafOutcome, FinitePolicyProblem, solve_finite_policy, verify_finite_policy_result


def problem(unknown=False):
    scenarios = (Scenario("hot",("weather-unknown","hot"),Q(1,2)), Scenario("cold",("weather-unknown","cold"),Q(1,2)))
    domains = ((0,("weather-unknown",),("cool-only","heat-only","flexible")),
        (1,("weather-unknown","hot"),("cool",)),(1,("weather-unknown","cold"),("heat",)))
    outcomes = []
    for scenario in scenarios:
        for equipment in domains[0][2]:
            action = "cool" if scenario.id == "hot" else "heat"
            cost = 20 if equipment == "flexible" else 0 if equipment == action+"-only" else 100
            verdict = "UNKNOWN" if unknown and equipment != "flexible" else "PASS"
            outcomes.append(LeafOutcome(scenario.id,(equipment,action),FiniteOutcome(scenario.id+":"+equipment,verdict,cost,evidence_root="checked-finite-table")))
    return FinitePolicyProblem(scenarios,domains,tuple(outcomes),"weather-policy-v1")


def test_policy_search_cannot_take_two_clairvoyant_initial_equipment_choices():
    p = problem()
    result = solve_finite_policy(p)
    assert result["status"] == "FINITE_POLICY_OPTIMAL" and result["cost"] == "20"
    assert result["selected_policy"][0]["action"] == "flexible"
    assert result["policy_count"] == 3
    assert verify_finite_policy_result(p,result)["status"] == "PASS"
    # Per-scenario clairvoyant optima both cost zero, but their first actions conflict.
    assert min(x.outcome.cost for x in p.outcomes if x.scenario_id == "hot") == 0
    assert min(x.outcome.cost for x in p.outcomes if x.scenario_id == "cold") == 0


def test_missing_leaf_and_budget_do_not_close_optimality():
    p = problem()
    incomplete = replace(p,outcomes=tuple(x for x in p.outcomes if x.actions[0] != "cool-only"))
    result = solve_finite_policy(incomplete)
    assert result["status"] == "FINITE_POLICY_FEASIBLE" and result["unresolved_evaluated_policies"]
    assert verify_finite_policy_result(incomplete,result)["status"] == "PASS"
    result["status"] = "FINITE_POLICY_OPTIMAL"
    assert verify_finite_policy_result(incomplete,result)["reason"] == "POLICY_OPTIMALITY_OVERCLAIM"
    limited = solve_finite_policy(p,max_policies=1)
    assert limited["status"] == "FINITE_POLICY_FEASIBLE" and not limited["search_exhausted"]
    assert verify_finite_policy_result(p,limited)["status"] == "PASS"


def test_nonimproving_unknowns_are_preserved_even_when_objective_value_closes():
    p = problem(unknown=True)
    result = solve_finite_policy(p)
    assert result["status"] == "FINITE_POLICY_OPTIMAL" and len(result["unresolved_evaluated_policies"]) == 2
    assert verify_finite_policy_result(p,result)["status"] == "PASS"
    bad = deepcopy(result)
    bad["unresolved_evaluated_policies"] = []
    assert verify_finite_policy_result(p,bad)["status"] == "FAIL"


def test_independent_checker_rejects_mutated_policy_cost_and_scope():
    p = problem()
    result = solve_finite_policy(p)
    bad = deepcopy(result)
    bad["selected_policy"][0]["action"] = "cool-only"
    assert verify_finite_policy_result(p,bad)["status"] == "FAIL"
    bad = deepcopy(result)
    bad["cost"] = "0"
    assert verify_finite_policy_result(p,bad)["status"] == "FAIL"
    assert verify_finite_policy_result(replace(p,context_root="weather-policy-v2"),result)["status"] == "FAIL"
    assert verify_finite_policy_result(p,result,max_policies=1)["status"] == "UNKNOWN"


def test_shared_capacity_scenario_requires_same_upfront_size():
    scenarios = (Scenario("base",("unobserved-load","base"),Q(9,10)), Scenario("peak",("unobserved-load","peak"),Q(1,10)))
    domains = ((0,("unobserved-load",),("capacity6","capacity12")),
        (1,("unobserved-load","base"),("operate",)),(1,("unobserved-load","peak"),("operate",)))
    leaves = tuple(LeafOutcome(s.id,(size,"operate"),FiniteOutcome(s.id+size,
        "FAIL" if s.id == "peak" and size == "capacity6" else "PASS",1 if size == "capacity6" else 5,evidence_root="checked-demand-sum"))
        for s in scenarios for size in ("capacity6","capacity12"))
    p = FinitePolicyProblem(scenarios,domains,leaves,"fixed-upfront-capacity")
    result = solve_finite_policy(p)
    assert result["cost"] == "5" and result["selected_policy"][0]["action"] == "capacity12"
    assert verify_finite_policy_result(p,result)["status"] == "PASS"
    cancelled = solve_finite_policy(p,cancelled=lambda: True)
    assert cancelled["status"] == "FINITE_POLICY_UNKNOWN" and cancelled["stop_reason"] == "CANCELLED"
