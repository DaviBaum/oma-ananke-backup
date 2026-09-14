"""Finite strategic design enumeration with candidate-rooted routing masters.

Integration ALG-JCD9/17/18/39/43/44, ADD-RTR3.2. Every strategic assignment
is materialized as explicit cases; route masters retain candidate roots, shared
capacity and higher-order conflicts. This kernel proves finite-table arithmetic,
while physical/materialization evidence is independently supplied upstream.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction as Q
from itertools import product
import math
import time

from oma.dependencies import _hash
from .finite import FiniteOutcome, finite_archive_optimum
from .master import MasterProblem, MasterResult, solve_master, rational
from .checker import verify_master_result


@dataclass(frozen=True)
class DesignCase:
    id: str
    assignment: tuple[tuple[str,str], ...]
    design_root: str
    capital_cost: Q
    materialization: FiniteOutcome
    routing: MasterProblem | None

    def __post_init__(self):
        object.__setattr__(self,"assignment",tuple(sorted(tuple(p) for p in self.assignment)))
        object.__setattr__(self,"capital_cost",rational(self.capital_cost))
        if not self.id or not self.design_root or len(dict(self.assignment)) != len(self.assignment):
            raise ValueError("Distinct assignment fields and case/design identities required")
        if self.materialization.verdict == "PASS" and self.routing is None:
            raise ValueError("Materialized case needs routing master")
        if self.routing and self.routing.state_root != self.design_root:
            raise ValueError("Routing master must bind its materialized candidate root")


@dataclass(frozen=True)
class FiniteCoDesignProblem:
    cases: tuple[DesignCase, ...]
    domains: tuple[tuple[str, tuple[str,...]], ...]
    protected_values: tuple[tuple[str,str], ...]
    context_root: str
    declared_design_universe_complete: bool = False

    def __post_init__(self):
        cases = tuple(sorted(self.cases,key=lambda c:c.id))
        domains = tuple(sorted((k,tuple(sorted(v))) for k,v in self.domains))
        protected = tuple(sorted(self.protected_values))
        object.__setattr__(self,"cases",cases)
        object.__setattr__(self,"domains",domains)
        object.__setattr__(self,"protected_values",protected)
        if not self.context_root or len({c.id for c in cases}) != len(cases):
            raise ValueError("Explicit context and unique case identities required")
        if len(dict(domains)) != len(domains) or len(dict(protected)) != len(protected) or set(dict(domains)) & set(dict(protected)):
            raise ValueError("Variable and protected field ownership must be disjoint")
        if any(not k or not values or len(set(values)) != len(values) for k,values in domains):
            raise ValueError("Finite nonempty distinct variable domains required")
        keys = set(dict(domains)) | set(dict(protected))
        represented = set()
        policies = set()
        for case in cases:
            assignment = dict(case.assignment)
            if set(assignment) != keys or any(assignment[k] != v for k,v in protected):
                raise ValueError("Protected assignment changed or assignment coverage incomplete")
            if any(assignment[k] not in domain for k,domain in domains):
                raise ValueError("Candidate outside strategic domain")
            represented.add(tuple(assignment[k] for k,_ in domains))
            if case.routing:
                policies.add((case.routing.objective_policy,case.routing.theory_version))
        if len(policies) > 1:
            raise ValueError("Co-design route objectives and theories must be compatible")
        if self.declared_design_universe_complete and len(represented) != math.prod(len(v) for _,v in domains):
            raise ValueError("Complete design universe needs every assignment, including unresolved/rejected materializations")

    @property
    def fingerprint(self):
        return _hash((self.context_root,self.domains,self.protected_values,self.declared_design_universe_complete,
            tuple((c.id,c.assignment,c.design_root,c.capital_cost,c.materialization.verdict,c.materialization.evidence_root,
                   c.routing.fingerprint if c.routing else None) for c in self.cases)))


def _row_outcomes(case, result):
    if case.materialization.verdict == "FAIL":
        return [FiniteOutcome(case.id,"FAIL",evidence_root=case.materialization.evidence_root)]
    if case.materialization.verdict != "PASS" or result is None:
        return [FiniteOutcome(case.id,"UNKNOWN")]
    root = _hash((case.design_root,result.problem_hash,result.status,result.selected,result.objective,result.lower_bound,result.search_exhausted))
    if result.status == "FINITE_MASTER_INFEASIBLE" and case.routing.declared_universe_complete:
        return [FiniteOutcome(case.id,"FAIL",evidence_root=root)]
    outcomes = []
    if result.objective is not None:
        outcomes.append(FiniteOutcome(case.id,"PASS",case.capital_cost+result.objective,evidence_root=root))
    unresolved = (not result.search_exhausted or not case.routing.declared_universe_complete
                  or result.status not in ("FINITE_MASTER_OPTIMAL","FINITE_MASTER_INFEASIBLE"))
    if unresolved or not outcomes:
        floor = case.capital_cost+result.lower_bound if result.lower_bound is not None else None
        outcomes.append(FiniteOutcome(case.id+":unresolved-routing","UNKNOWN",lower_bound=floor))
    return outcomes


def solve_finite_codesign(problem, *, max_nodes=1_000_000, time_limit_seconds=60, cancelled=None):
    if max_nodes < 1 or not math.isfinite(time_limit_seconds) or time_limit_seconds <= 0:
        raise ValueError("Positive finite computation budget required")
    started = time.monotonic()
    results, outcomes = {}, []
    used = 0
    for case in problem.cases:
        remaining = time_limit_seconds-(time.monotonic()-started)
        result = None
        if case.materialization.verdict == "PASS" and used < max_nodes and remaining > 0 and not (cancelled and cancelled()):
            result = solve_master(case.routing,max_nodes=max_nodes-used,time_limit_seconds=remaining,cancelled=cancelled)
            used += result.visited_nodes
        results[case.id] = result
        outcomes.extend(_row_outcomes(case,result))
    summary = finite_archive_optimum(outcomes,context_root=problem.fingerprint,universe_complete=problem.declared_design_universe_complete)
    selected = next((c for c in problem.cases if c.id == summary["selected_id"]),None)
    return {"problem_hash":problem.fingerprint,"status":summary["status"].replace("ARCHIVE","CODESIGN_MASTER"),
        "selected_design_id":selected.id if selected else None,"selected_design_root":selected.design_root if selected else None,
        "cost":summary["cost"],"lower_bound":summary["lower_bound"],"unresolved":summary["unresolved"],
        "case_results":{k:v.to_dict() if v else None for k,v in results.items()},"visited_nodes":used,
        "scope":"EXPLICIT_STRATEGIC_ASSIGNMENTS_AND_CANDIDATE_ROOTED_ROUTE_MASTERS",
        "materialization_and_physical_checks":"UPSTREAM_DOMAIN_EVIDENCE_REQUIRED",
        "protected_state_scope":"DECLARED_PROTECTED_ASSIGNMENT_TOKENS", "elapsed_seconds":time.monotonic()-started}


def _decode_master(value):
    return MasterResult(value["problem_hash"],value["status"],tuple(value["selected"]),
        Q(value["objective"]) if value["objective"] is not None else None,
        Q(value["lower_bound"]) if value["lower_bound"] is not None else None,
        value["search_exhausted"],value["visited_nodes"],value["combinations"],value["elapsed_seconds"],value["stop_reason"],
        value.get("bound_scope","EXPLICIT_COLUMN_UNIVERSE_ONLY"),value.get("physical_check_status","NOT_RUN"))


def verify_finite_codesign_result(problem, result, *, max_combinations=1_000_000):
    """Replay each candidate master and independently compare full design values."""
    if result.get("problem_hash") != problem.fingerprint:
        return {"status":"FAIL","reason":"STALE_CODESIGN_PROBLEM"}
    if result.get("status") not in {"FINITE_CODESIGN_MASTER_OPTIMAL","FINITE_CODESIGN_MASTER_FEASIBLE","FINITE_CODESIGN_MASTER_INFEASIBLE","FINITE_CODESIGN_MASTER_UNKNOWN"}:
        return {"status":"FAIL","reason":"UNKNOWN_CODESIGN_CLAIM"}
    try:
        if set(result["case_results"]) != {c.id for c in problem.cases}:
            return {"status":"FAIL","reason":"DESIGN_CASE_COVERAGE"}
        possible_floors, actual_feasible, unresolved_ids = [], {}, []
        used = 0
        for case in problem.cases:
            raw = result["case_results"][case.id]
            if case.materialization.verdict != "PASS":
                if raw is not None:
                    return {"status":"FAIL","reason":"UNACCEPTED_MATERIALIZATION_ROUTED"}
                if case.materialization.verdict == "UNKNOWN":
                    possible_floors.append(None)
                    unresolved_ids.append(case.id)
                continue
            if raw is None:
                possible_floors.append(None)
                unresolved_ids.append(case.id)
                continue
            route = _decode_master(raw)
            replay = verify_master_result(case.routing,route,max_combinations=max_combinations-used)
            if replay["verdict"] != "PASS":
                return {"status":replay["verdict"],"reason":"ROUTE_MASTER_REPLAY","case":case.id,"detail":replay}
            used += replay["assignments_checked"]
            if route.objective is not None:
                actual_feasible[case.id] = case.capital_cost+route.objective
                possible_floors.append(case.capital_cost+route.objective)
            if (not route.search_exhausted or not case.routing.declared_universe_complete
                    or route.status not in ("FINITE_MASTER_OPTIMAL","FINITE_MASTER_INFEASIBLE")):
                unresolved_ids.append(case.id+":unresolved-routing")
                possible_floors.append(case.capital_cost+route.lower_bound if route.lower_bound is not None else None)
            elif route.status == "FINITE_MASTER_INFEASIBLE":
                continue
        if sorted(result["unresolved"]) != sorted(unresolved_ids):
            return {"status":"FAIL","reason":"UNRESOLVED_DESIGN_LEDGER"}
        selected = result.get("selected_design_id")
        if selected is None and (result.get("cost") is not None or result.get("selected_design_root") is not None):
            return {"status":"FAIL","reason":"MISSING_CODESIGN_INCUMBENT"}
        if selected is not None:
            selected_case = next(c for c in problem.cases if c.id == selected)
            if selected not in actual_feasible or Q(result["cost"]) != actual_feasible[selected] or result.get("selected_design_root") != selected_case.design_root:
                return {"status":"FAIL","reason":"INVALID_CODESIGN_INCUMBENT"}
        if result["status"] in ("FINITE_CODESIGN_MASTER_OPTIMAL","FINITE_CODESIGN_MASTER_FEASIBLE") and selected is None:
            return {"status":"FAIL","reason":"MISSING_CODESIGN_INCUMBENT"}
        if result["status"] in ("FINITE_CODESIGN_MASTER_UNKNOWN","FINITE_CODESIGN_MASTER_INFEASIBLE") and selected is not None:
            return {"status":"FAIL","reason":"INCONSISTENT_CODESIGN_STATUS"}
        if result["status"] == "FINITE_CODESIGN_MASTER_OPTIMAL":
            if not problem.declared_design_universe_complete or any(v is None or v < actual_feasible[selected] for v in possible_floors):
                return {"status":"FAIL","reason":"CODESIGN_OPTIMALITY_OVERCLAIM"}
        if result["status"] == "FINITE_CODESIGN_MASTER_INFEASIBLE":
            if actual_feasible or unresolved_ids or not problem.declared_design_universe_complete:
                return {"status":"FAIL","reason":"CODESIGN_INFEASIBILITY_OVERCLAIM"}
        if result.get("lower_bound") is not None:
            lower = Q(result["lower_bound"])
            if not problem.declared_design_universe_complete or any(v is None or v < lower for v in possible_floors):
                return {"status":"FAIL","reason":"CODESIGN_LOWER_BOUND_OVERCLAIM"}
        return {"status":"PASS","assignments_checked":used,"scope":"FINITE_CODESIGN_AND_ROUTE_MASTER_ARITHMETIC"}
    except (KeyError,ValueError,TypeError,StopIteration):
        return {"status":"FAIL","reason":"MALFORMED_CODESIGN_RESULT"}
