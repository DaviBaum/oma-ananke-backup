"""Independent arithmetic replay of finite master and dual certificates.

Does not call solver traversal, row construction, or pricing implementation.
Shared immutable schema is not claimed to provide algorithmic independence for
physical geometry, which remains an explicit external checker obligation.
"""
from fractions import Fraction
import itertools
import math

from .master import MasterProblem, MasterResult, DualCertificate


def verify_master_result(problem: MasterProblem, result: MasterResult, *, max_combinations=1_000_000):
    if result.status not in {"FINITE_MASTER_OPTIMAL", "FINITE_MASTER_INFEASIBLE", "FINITE_MASTER_FEASIBLE", "MASTER_UNKNOWN"}:
        return {"verdict": "FAIL", "reason": "UNKNOWN_CLAIM_STATUS"}
    if problem.fingerprint != result.problem_hash:
        return {"verdict": "FAIL", "reason": "STALE_PROBLEM"}
    by_id = {c.id: c for c in problem.columns}
    if any(i not in by_id for i in result.selected) or len(set(result.selected)) != len(result.selected):
        return {"verdict": "FAIL", "reason": "BAD_COLUMN_IDENTITY"}
    selected = [by_id[i] for i in result.selected]

    def check_assignment(columns):
        if sorted(c.net_id for c in columns) != list(problem.net_ids):
            return False
        for resource, capacity in problem.capacities:
            total = sum((v for c in columns for k, v in c.resource_use if k == resource), Fraction(0))
            if total > capacity:
                return False
        chosen = {c.id for c in columns}
        for conflict in problem.conflicts:
            count = sum(1 for c in conflict.columns if c in chosen)
            maximum = 1 if conflict.kind == "pairwise_clique" else len(conflict.columns) - 1
            if count > maximum:
                return False
        return True

    if result.objective is not None:
        if not check_assignment(selected) or sum((c.cost for c in selected), Fraction(0)) != result.objective:
            return {"verdict": "FAIL", "reason": "INVALID_INCUMBENT"}
    elif result.selected:
        return {"verdict": "FAIL", "reason": "INCUMBENT_COST_MISSING"}
    if result.status in {"FINITE_MASTER_OPTIMAL", "FINITE_MASTER_FEASIBLE"} and result.objective is None:
        return {"verdict": "FAIL", "reason": "FEASIBILITY_WITHOUT_INCUMBENT"}
    if result.status in {"FINITE_MASTER_INFEASIBLE", "MASTER_UNKNOWN"} and result.objective is not None:
        return {"verdict": "FAIL", "reason": "INCONSISTENT_INCUMBENT_STATUS"}
    if result.lower_bound is not None and not problem.declared_universe_complete:
        return {"verdict": "FAIL", "reason": "RESTRICTED_BOUND_OVERCLAIM"}
    options = [[c for c in problem.columns if c.net_id == n] for n in problem.net_ids]
    size = math.prod(map(len, options))
    if size > max_combinations:
        return {"verdict": "UNKNOWN", "reason": "CHECKER_BUDGET", "incumbent_checked": result.objective is not None}
    best, best_ids, count = None, (), 0
    for assignment in itertools.product(*options):
        count += 1
        if not check_assignment(assignment):
            continue
        value = sum((c.cost for c in assignment), Fraction(0))
        ids = tuple(sorted(c.id for c in assignment))
        if best is None or (value, ids) < (best, best_ids):
            best, best_ids = value, ids
    if result.status == "FINITE_MASTER_OPTIMAL" and (not result.search_exhausted or result.objective != best or result.selected != best_ids):
        return {"verdict": "FAIL", "reason": "OPTIMALITY_OVERCLAIM"}
    if result.status == "FINITE_MASTER_INFEASIBLE" and (not result.search_exhausted or best is not None):
        return {"verdict": "FAIL", "reason": "INFEASIBILITY_OVERCLAIM"}
    if result.lower_bound is not None and best is not None and result.lower_bound > best:
        return {"verdict": "FAIL", "reason": "INVALID_LOWER_BOUND"}
    return {"verdict": "PASS", "scope": "FINITE_MASTER_ARITHMETIC", "assignments_checked": count,
            "physical_geometry": "NOT_RUN", "finite_optimum": str(best) if best is not None else None}


def verify_dual(problem: MasterProblem, certificate: DualCertificate):
    if certificate.problem_hash != problem.fingerprint:
        return {"verdict": "FAIL", "reason": "STALE_PROBLEM"}
    alpha, prices = dict(certificate.alpha), dict(certificate.prices)
    row_ids = {"capacity:" + k for k, _ in problem.capacities} | {"conflict:" + h.id for h in problem.conflicts}
    if set(alpha) != set(problem.net_ids) or set(prices) != row_ids or len(alpha) != len(certificate.alpha) or len(prices) != len(certificate.prices):
        return {"verdict": "FAIL", "reason": "DUAL_DOMAIN_MISMATCH"}
    if any(p < 0 for p in prices.values()):
        return {"verdict": "FAIL", "reason": "NEGATIVE_DUAL_PRICE"}
    for column in problem.columns:
        left = alpha[column.net_id]
        left -= sum((prices["capacity:" + k] * v for k, v in column.resource_use), Fraction(0))
        left -= sum((prices["conflict:" + h.id] for h in problem.conflicts if column.id in h.columns), Fraction(0))
        if left > column.cost:
            return {"verdict": "FAIL", "reason": "NEGATIVE_REDUCED_COST", "column": column.id}
    expected = sum(alpha.values(), Fraction(0))
    expected -= sum((prices["capacity:" + k] * cap for k, cap in problem.capacities), Fraction(0))
    expected -= sum((prices["conflict:" + h.id] * (1 if h.kind == "pairwise_clique" else len(h.columns) - 1)
                     for h in problem.conflicts), Fraction(0))
    if expected != certificate.lower_bound or certificate.priced_columns != len(problem.columns):
        return {"verdict": "FAIL", "reason": "BOUND_OR_PRICING_COUNT_MISMATCH"}
    return {"verdict": "PASS", "scope": "EXPLICIT_COLUMN_UNIVERSE_ONLY", "lower_bound": str(expected),
            "columns_checked": len(problem.columns), "continuous_space_bound": None}
