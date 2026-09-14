from dataclasses import replace
from fractions import Fraction as F
import itertools
import random

import pytest

from oma.optimization import Conflict, MasterProblem, RouteColumn, solve_master, price_columns, verify_master_result, verify_dual
from oma.optimization.master import generate_columns


def problem(columns, nets=None, capacities=(), conflicts=(), complete=True):
    return MasterProblem(tuple(nets or sorted({c.net_id for c in columns})), tuple(columns), tuple(capacities),
                         tuple(conflicts), state_root="root-v1", declared_universe_complete=complete)


def test_joint_master_improves_sequential_congestion_choice():
    p = problem([RouteColumn("a-cheap", "a", 1, (("corridor", 1),)), RouteColumn("a-bypass", "a", 2),
                 RouteColumn("b-cheap", "b", 1, (("corridor", 1),)), RouteColumn("b-bypass", "b", 100)], capacities=(("corridor", 1),))
    events = []
    result = solve_master(p, on_candidate=events.append)
    assert result.selected == ("a-bypass", "b-cheap")
    assert result.objective == 3  # Sequential a-first costs 101.
    assert verify_master_result(p, result)["verdict"] == "PASS"
    assert events and result.physical_check_status == "NOT_RUN"
    cg = generate_columns(p)
    assert verify_dual(p, cg["dual"])["verdict"] == "PASS"
    assert cg["dual"].lower_bound == 3


def test_triple_conflict_allows_legal_pair_and_disallows_triple():
    cols = [RouteColumn(f"{n}-primary", n, 1) for n in "abc"] + [RouteColumn(f"{n}-backup", n, 10) for n in "abc"]
    h = Conflict("packing", tuple(f"{n}-primary" for n in "abc"))
    p = problem(cols, conflicts=(h,))
    result = solve_master(p)
    assert result.objective == 12
    assert verify_master_result(p, result)["verdict"] == "PASS"
    clique = replace(p, conflicts=(replace(h, kind="pairwise_clique"),))
    assert solve_master(clique).objective == 21
    assert verify_dual(p, price_columns(p, {"conflict:packing": 9}))["verdict"] == "PASS"


def test_restricted_columns_do_not_publish_full_lower_bound():
    p = problem([RouteColumn("a", "n", 10)], complete=False)
    result = solve_master(p)
    assert result.lower_bound is None
    assert verify_master_result(p, replace(result, lower_bound=F(10)))["reason"] == "RESTRICTED_BOUND_OVERCLAIM"
    full = replace(p, columns=p.columns + (RouteColumn("omitted", "n", 1),), declared_universe_complete=True)
    assert solve_master(full).objective == 1
    assert verify_master_result(full, result)["reason"] == "STALE_PROBLEM"


def test_budget_and_cancellation_do_not_claim_infeasibility():
    p = problem([RouteColumn(str(i), "n", i) for i in range(5)])
    assert solve_master(p, max_nodes=1).status == "MASTER_UNKNOWN"
    cancelled = solve_master(p, cancelled=lambda: True)
    assert cancelled.stop_reason == "CANCELLED" and cancelled.status == "MASTER_UNKNOWN"


def test_exact_threshold_and_immutability():
    p = problem([RouteColumn("a", "a", "1/3", (("r", "1/10"),)), RouteColumn("b", "b", "2/3", (("r", "2/10"),))], capacities=(("r", "3/10"),))
    result = solve_master(p)
    assert result.objective == 1
    assert verify_master_result(p, result)["verdict"] == "PASS"
    failing = replace(p, capacities=(("r", F(3, 10) - F(1, 10**30)),))
    assert solve_master(failing).status == "FINITE_MASTER_INFEASIBLE"
    assert p.capacities == (("r", F(3, 10)),)


def test_dual_checker_rejects_missing_column_and_forgery():
    p = problem([RouteColumn("a", "n", 1), RouteColumn("b", "n", 10)])
    d = price_columns(p)
    assert verify_dual(p, d)["verdict"] == "PASS"
    assert verify_dual(p, replace(d, alpha=(("n", F(10)),), lower_bound=F(10)))["reason"] == "NEGATIVE_REDUCED_COST"
    assert verify_dual(p, replace(d, lower_bound=F(2)))["verdict"] == "FAIL"
    assert verify_dual(p, replace(d, priced_columns=1))["verdict"] == "FAIL"


def test_master_random_cases_against_independent_exhaustive_replay():
    rng = random.Random(48231)
    for trial in range(40):
        columns = [RouteColumn(f"{n}/{j}", n, F(rng.randint(-3, 20), 3), (("r", F(rng.randint(0, 4), 2)),))
                   for n in "abc" for j in range(3)]
        p = problem(columns, capacities=(("r", rng.randint(1, 6)),))
        result = solve_master(p)
        assert verify_master_result(p, result)["verdict"] == "PASS", trial
        dual = price_columns(p, {"capacity:r": F(rng.randint(0, 10), 3)})
        assert verify_dual(p, dual)["verdict"] == "PASS"
        if result.objective is not None:
            assert dual.lower_bound <= result.objective


def test_missing_net_is_accounted_and_inputs_validated():
    p = problem([RouteColumn("only", "a", 1)], nets=("a", "missing"))
    result = solve_master(p)
    assert result.status == "FINITE_MASTER_INFEASIBLE"
    assert verify_master_result(p, result)["verdict"] == "PASS"
    with pytest.raises(ValueError):
        RouteColumn("bad", "a", float("nan"))
    with pytest.raises(ValueError):
        problem([RouteColumn("bad", "a", 1, (("unbound", 1),))])


def test_equal_cost_ties_are_canonical_and_bad_status_rejected():
    p = problem([RouteColumn("b", "n", 1), RouteColumn("a", "n", 1)])
    r = solve_master(p)
    assert r.selected == ("a",)
    assert verify_master_result(p, replace(r, status="GLOBAL_OMA_OPTIMAL"))["verdict"] == "FAIL"
