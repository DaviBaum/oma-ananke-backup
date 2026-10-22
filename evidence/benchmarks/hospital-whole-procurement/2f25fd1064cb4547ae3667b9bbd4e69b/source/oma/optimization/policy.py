"""Finite nonanticipative policy search over explicitly disposed leaf outcomes.

Integration ALG-DYN8-19/60 and canonical SOV1/6: scenarios are a declared
family, actions attach to information histories, and UNKNOWN blocks unjustified
optimality. This is an exact finite policy table model, not a dynamics simulator.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction as Q
from itertools import product
import math
import time

from oma.dependencies import _hash
from .finite import FiniteOutcome, finite_archive_optimum, _law
from .master import rational


@dataclass(frozen=True)
class Scenario:
    id: str
    history: tuple[str, ...]
    probability: Q

    def __post_init__(self):
        object.__setattr__(self,"history",tuple(self.history))
        object.__setattr__(self,"probability",rational(self.probability))
        if not self.id or not self.history or any(not isinstance(x,str) or not x for x in self.history):
            raise ValueError("Scenario and pre-action information tokens required")


@dataclass(frozen=True)
class LeafOutcome:
    scenario_id: str
    actions: tuple[str, ...]
    outcome: FiniteOutcome

    def __post_init__(self):
        object.__setattr__(self,"actions",tuple(self.actions))


@dataclass(frozen=True)
class FinitePolicyProblem:
    scenarios: tuple[Scenario, ...]
    # (stage, exact pre-action history prefix, available action identifiers)
    domains: tuple[tuple[int, tuple[str,...], tuple[str,...]], ...]
    outcomes: tuple[LeafOutcome, ...]
    context_root: str
    objective: str = "EXPECTED_COST"

    def __post_init__(self):
        scenarios = tuple(sorted(self.scenarios,key=lambda s:s.id))
        domains = tuple(sorted((stage,tuple(history),tuple(sorted(actions))) for stage,history,actions in self.domains))
        outcomes = tuple(sorted(self.outcomes,key=lambda x:(x.scenario_id,x.actions)))
        object.__setattr__(self,"scenarios",scenarios)
        object.__setattr__(self,"domains",domains)
        object.__setattr__(self,"outcomes",outcomes)
        if not self.context_root or self.objective not in ("EXPECTED_COST","WORST_LISTED_COST"):
            raise ValueError("Explicit context and objective policy required")
        if len({s.id for s in scenarios}) != len(scenarios):
            raise ValueError("Duplicate scenario identity")
        _law(s.probability for s in scenarios)
        if len({len(s.history) for s in scenarios}) != 1:
            raise ValueError("All scenarios need one common finite horizon")
        needed = {(i,s.history[:i+1]) for s in scenarios for i in range(len(s.history))}
        if {(i,h) for i,h,_ in domains} != needed or len(domains) != len(needed):
            raise ValueError("Action domain required exactly once for every information node")
        if any(not actions or len(set(actions)) != len(actions) or any(not isinstance(a,str) or not a for a in actions) for _,_,actions in domains):
            raise ValueError("Distinct nonempty action identifiers required")
        by_id, choices = {s.id:s for s in scenarios}, {(i,h):a for i,h,a in domains}
        seen = set()
        for leaf in outcomes:
            if leaf.scenario_id not in by_id or (leaf.scenario_id,leaf.actions) in seen:
                raise ValueError("Unknown or duplicate leaf outcome")
            scenario = by_id[leaf.scenario_id]
            if len(leaf.actions) != len(scenario.history) or any(a not in choices[(i,scenario.history[:i+1])] for i,a in enumerate(leaf.actions)):
                raise ValueError("Leaf actions outside declared policy class")
            seen.add((leaf.scenario_id,leaf.actions))

    @property
    def fingerprint(self):
        return _hash((self.context_root,self.objective,
            tuple((s.id,s.history,s.probability) for s in self.scenarios),self.domains,
            tuple((x.scenario_id,x.actions,x.outcome.id,x.outcome.verdict,x.outcome.cost,x.outcome.lower_bound,x.outcome.evidence_root) for x in self.outcomes)))


def _policy_rows(problem, selection):
    return [{"stage":i,"history":list(h),"action":a} for (i,h,_),a in zip(problem.domains,selection)]


def _evaluate(problem, selection, table):
    decisions = {(i,h):a for (i,h,_),a in zip(problem.domains,selection)}
    rows = []
    for scenario in problem.scenarios:
        actions = tuple(decisions[(i,scenario.history[:i+1])] for i in range(len(scenario.history)))
        outcome = table.get((scenario.id,actions))
        rows.append(outcome or FiniteOutcome("missing:"+scenario.id,"UNKNOWN"))
    identity = _hash(selection)
    evidence = _hash((problem.fingerprint,identity,tuple(o.evidence_root for o in rows)))
    if any(o.verdict == "FAIL" for o in rows):
        return FiniteOutcome(identity,"FAIL",evidence_root=evidence)
    costs = [o.cost for o in rows]
    floors = [o.cost if o.cost is not None else o.lower_bound for o in rows]
    def aggregate(values):
        if any(v is None for v in values):
            return None
        if problem.objective == "EXPECTED_COST":
            return sum((s.probability*v for s,v in zip(problem.scenarios,values)),Q(0))
        return max(values)
    cost, floor = aggregate(costs), aggregate(floors)
    if all(o.verdict == "PASS" for o in rows):
        return FiniteOutcome(identity,"PASS",cost,evidence_root=evidence)
    return FiniteOutcome(identity,"UNKNOWN",cost,lower_bound=floor,evidence_root=evidence)


def solve_finite_policy(problem: FinitePolicyProblem, *, max_policies=100_000, time_limit_seconds=60, cancelled=None):
    if max_policies < 1 or not math.isfinite(time_limit_seconds) or time_limit_seconds <= 0:
        raise ValueError("Positive finite computation budgets required")
    started = time.monotonic()
    table = {(x.scenario_id,x.actions):x.outcome for x in problem.outcomes}
    outcomes, selections = [], {}
    stack = [()]
    stop = "EXHAUSTED"
    while stack:
        if cancelled and cancelled():
            stop = "CANCELLED"
            break
        if len(outcomes) >= max_policies:
            stop = "POLICY_LIMIT"
            break
        if time.monotonic()-started >= time_limit_seconds:
            stop = "TIME_LIMIT"
            break
        selection = stack.pop()
        if len(selection) != len(problem.domains):
            stack.extend(selection+(a,) for a in reversed(problem.domains[len(selection)][2]))
            continue
        outcome = _evaluate(problem,selection,table)
        outcomes.append(outcome)
        if outcome.verdict == "PASS":
            selections[outcome.id] = selection
    summary = finite_archive_optimum(outcomes,context_root=problem.fingerprint,universe_complete=stop == "EXHAUSTED")
    selected = selections.get(summary["selected_id"])
    return {"problem_hash":problem.fingerprint,"status":summary["status"].replace("ARCHIVE","POLICY"),
        "cost":summary["cost"],"lower_bound":summary["lower_bound"],
        "selected_policy":_policy_rows(problem,selected) if selected is not None else None,
        "evaluated_policies":len(outcomes),"policy_count":math.prod(len(a) for _,_,a in problem.domains),
        "unresolved_evaluated_policies":summary["unresolved"],"search_exhausted":stop == "EXHAUSTED", "stop_reason":stop,
        "scope":"FINITE_NONANTICIPATIVE_POLICY_CLASS_AND_SUPPLIED_LEAF_OUTCOMES", "dynamics_replay":"INPUT_LEAF_EVIDENCE_REQUIRES_DOMAIN_CHECKERS",
        "elapsed_seconds":time.monotonic()-started}


def verify_finite_policy_result(problem, result, *, max_policies=100_000):
    """Independent exhaustive policy-table replay, without solver evaluation helpers."""
    if result.get("problem_hash") != problem.fingerprint:
        return {"status":"FAIL","reason":"STALE_POLICY_PROBLEM"}
    allowed = {"FINITE_POLICY_OPTIMAL","FINITE_POLICY_FEASIBLE","FINITE_POLICY_INFEASIBLE","FINITE_POLICY_UNKNOWN"}
    if result.get("status") not in allowed:
        return {"status":"FAIL","reason":"UNKNOWN_POLICY_CLAIM"}
    count = math.prod(len(a) for _,_,a in problem.domains)
    if count > max_policies:
        return {"status":"UNKNOWN","reason":"CHECKER_BUDGET"}
    table = {(o.scenario_id,o.actions):o.outcome for o in problem.outcomes}
    valid, unresolved, unresolved_ids = {}, [], []
    for selection in product(*(a for _,_,a in problem.domains)):
        row = {(i,h):a for (i,h,_),a in zip(problem.domains,selection)}
        costs, floors, statuses = [], [], []
        for scenario in problem.scenarios:
            sequence = tuple(row[(i,scenario.history[:i+1])] for i in range(len(scenario.history)))
            item = table.get((scenario.id,sequence))
            statuses.append(item.verdict if item else "UNKNOWN")
            costs.append(item.cost if item else None)
            floors.append((item.cost if item.cost is not None else item.lower_bound) if item else None)
        if "FAIL" in statuses:
            continue
        if all(s == "PASS" for s in statuses):
            cost = sum((s.probability*c for s,c in zip(problem.scenarios,costs)),Q(0)) if problem.objective == "EXPECTED_COST" else max(costs)
            valid[selection] = cost
        else:
            lower = None if any(v is None for v in floors) else sum((s.probability*v for s,v in zip(problem.scenarios,floors)),Q(0)) if problem.objective == "EXPECTED_COST" else max(floors)
            unresolved.append(lower)
            unresolved_ids.append(_hash(selection))
    try:
        if result.get("search_exhausted") and (result.get("evaluated_policies") != count or sorted(result.get("unresolved_evaluated_policies",[])) != sorted(unresolved_ids)):
            return {"status":"FAIL","reason":"POLICY_COVERAGE_OR_UNKNOWN_LEDGER"}
        chosen = result.get("selected_policy")
        chosen_tuple = None
        if chosen is not None:
            mapping = {(r["stage"],tuple(r["history"])):r["action"] for r in chosen}
            if len(mapping) != len(chosen) or set(mapping) != {(i,h) for i,h,_ in problem.domains}:
                return {"status":"FAIL","reason":"POLICY_INFORMATION_DOMAIN"}
            chosen_tuple = tuple(mapping[(i,h)] for i,h,_ in problem.domains)
            if chosen_tuple not in valid or Q(result["cost"]) != valid[chosen_tuple]:
                return {"status":"FAIL","reason":"INVALID_POLICY_INCUMBENT"}
        elif result.get("cost") is not None:
            return {"status":"FAIL","reason":"MISSING_POLICY_INCUMBENT"}
        if result["status"] in ("FINITE_POLICY_OPTIMAL","FINITE_POLICY_FEASIBLE") and chosen_tuple is None:
            return {"status":"FAIL","reason":"MISSING_POLICY_INCUMBENT"}
        if result["status"] in ("FINITE_POLICY_UNKNOWN","FINITE_POLICY_INFEASIBLE") and chosen_tuple is not None:
            return {"status":"FAIL","reason":"INCONSISTENT_POLICY_STATUS"}
        if result["status"] == "FINITE_POLICY_OPTIMAL":
            cost = valid[chosen_tuple]
            if not result.get("search_exhausted") or min(valid.values()) != cost or any(v is None or v < cost for v in unresolved):
                return {"status":"FAIL","reason":"POLICY_OPTIMALITY_OVERCLAIM"}
        if result["status"] == "FINITE_POLICY_INFEASIBLE" and (valid or unresolved or not result.get("search_exhausted")):
            return {"status":"FAIL","reason":"POLICY_INFEASIBILITY_OVERCLAIM"}
        if result.get("lower_bound") is not None:
            lower = Q(result["lower_bound"])
            if not result.get("search_exhausted") or any(v is None or v < lower for v in unresolved) or any(v < lower for v in valid.values()):
                return {"status":"FAIL","reason":"POLICY_LOWER_BOUND_OVERCLAIM"}
        return {"status":"PASS","policies_checked":count,"scope":"FINITE_POLICY_TABLE_ARITHMETIC"}
    except (KeyError,ValueError,TypeError):
        return {"status":"FAIL","reason":"MALFORMED_POLICY_RESULT"}
