"""Finite instantiated obligations: quotients, archives, risk and quantity maps.

Canonical ALG-AB5; integration ALG-JCD13/40 and ALG-DYN11/16-19.
All conclusions are relative to complete explicit input tables and their root.
The functions do not infer unknown physical predicates or missing scenarios.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from fractions import Fraction as Q
from itertools import combinations
import json
from typing import Any, Mapping

from oma.dependencies import _json, _hash
from .master import rational
from .physical import Interval


def _token(value):
    return json.dumps(_json(value), sort_keys=True, separators=(",", ":"))


def _root(scope, payload):
    if not isinstance(scope, str) or not scope:
        raise ValueError("Explicit immutable context root required")
    return _hash((scope, payload))


def _observations(observations, experiment_ids):
    experiments = tuple(experiment_ids)
    if len(set(experiments)) != len(experiments) or any(not isinstance(e, str) or not e for e in experiments):
        raise ValueError("Distinct nonempty experiment identifiers required")
    if any(not isinstance(s, str) or not s for s in observations):
        raise ValueError("Nonempty state identifiers required")
    if any(set(row) != set(experiments) for row in observations.values()):
        raise ValueError("Every declared experiment needs a value for every state")
    return experiments, {s: tuple(_token(observations[s][e]) for e in experiments) for s in sorted(observations)}


def contextual_quotient(observations: Mapping[str, Mapping[str, Any]], experiment_ids, *, context_root: str):
    """Partition states by their complete finite observation vector."""
    experiments, vectors = _observations(observations, experiment_ids)
    groups = defaultdict(list)
    for state, vector in vectors.items():
        groups[vector].append(state)
    blocks = sorted(tuple(states) for states in groups.values())
    quotient = {s: block[0] for block in blocks for s in block}
    separation = []
    for first, second in combinations(blocks, 2):
        index = next(i for i, (x,y) in enumerate(zip(vectors[first[0]], vectors[second[0]])) if x != y)
        separation.append({"first": first[0], "second": second[0], "experiment": experiments[index]})
    return {"status": "FINITE_CONTEXTUAL_QUOTIENT", "root": _root(context_root, (experiments, vectors)),
        "blocks": blocks, "quotient_map": quotient, "separation_witnesses": separation,
        "scope": "COMPLETE_SUPPLIED_STATE_EXPERIMENT_TABLE"}


def verify_contextual_quotient(observations, experiment_ids, result, *, context_root: str):
    """Pairwise independent check of equivalence, coverage and separation."""
    try:
        experiments, vectors = _observations(observations, experiment_ids)
        if result.get("root") != _root(context_root, (experiments, vectors)):
            return {"status": "FAIL", "reason": "CONTEXT_OR_OBSERVATIONS_CHANGED"}
        blocks = [tuple(block) for block in result["blocks"]]
        flattened = [s for b in blocks for s in b]
        if sorted(flattened) != sorted(vectors) or len(set(flattened)) != len(flattened) or any(not b for b in blocks):
            return {"status": "FAIL", "reason": "PARTITION_COVERAGE"}
        labels = {s: i for i,b in enumerate(blocks) for s in b}
        for first, second in combinations(vectors, 2):
            if (labels[first] == labels[second]) != (vectors[first] == vectors[second]):
                return {"status": "FAIL", "reason": "NOT_COARSEST_EXACT_PARTITION", "states": [first,second]}
        if result["quotient_map"] != {s:min(b) for b in blocks for s in b}:
            return {"status": "FAIL", "reason": "QUOTIENT_MAP"}
        required = {frozenset((min(a),min(b))) for a,b in combinations(blocks, 2)}
        observed = set()
        for witness in result["separation_witnesses"]:
            first,second,e = witness["first"],witness["second"],witness["experiment"]
            pair = frozenset((first,second))
            if pair not in required or pair in observed or vectors[first][experiments.index(e)] == vectors[second][experiments.index(e)]:
                return {"status": "FAIL", "reason": "INVALID_SEPARATION_WITNESS"}
            observed.add(pair)
        if observed != required:
            return {"status": "FAIL", "reason": "MISSING_SEPARATION_WITNESS"}
        return {"status": "PASS", "scope": "COMPLETE_SUPPLIED_STATE_EXPERIMENT_TABLE"}
    except (KeyError, ValueError, TypeError):
        return {"status": "FAIL", "reason": "MALFORMED_QUOTIENT"}


@dataclass(frozen=True)
class FiniteOutcome:
    id: str
    verdict: str
    cost: Q | None = None
    lower_bound: Q | None = None
    evidence_root: str = ""

    def __post_init__(self):
        if not self.id or self.verdict not in ("PASS", "FAIL", "UNKNOWN"):
            raise ValueError("Candidate identity and three-valued verdict required")
        if self.cost is not None:
            object.__setattr__(self, "cost", rational(self.cost))
        if self.lower_bound is not None:
            object.__setattr__(self, "lower_bound", rational(self.lower_bound))
        if self.verdict == "PASS" and (self.cost is None or not self.evidence_root):
            raise ValueError("Passing outcome needs cost and checked evidence root")
        if self.verdict == "FAIL" and not self.evidence_root:
            raise ValueError("Rejected outcome needs checked evidence root")
        if self.cost is not None and self.lower_bound is not None and self.lower_bound > self.cost:
            raise ValueError("Lower bound exceeds supplied exact cost")


def finite_archive_optimum(outcomes, *, context_root, universe_complete):
    """A007: retain unresolved feasible candidates when disposing finite optima."""
    outcomes = tuple(outcomes)
    if len({o.id for o in outcomes}) != len(outcomes):
        raise ValueError("Duplicate candidate identity")
    root = _root(context_root, (universe_complete, tuple((o.id,o.verdict,o.cost,o.lower_bound,o.evidence_root) for o in outcomes)))
    accepted = sorted((o for o in outcomes if o.verdict == "PASS"), key=lambda o:(o.cost,o.id))
    unresolved = [o for o in outcomes if o.verdict == "UNKNOWN"]
    incumbent = accepted[0] if accepted else None
    floors = [o.cost for o in accepted]
    unknown_unbounded = False
    for o in unresolved:
        floor = o.cost if o.cost is not None else o.lower_bound
        if floor is None:
            unknown_unbounded = True
        else:
            floors.append(floor)
    lower = min(floors) if universe_complete and floors and not unknown_unbounded else None
    if incumbent is not None:
        status = "FINITE_ARCHIVE_OPTIMAL" if lower is not None and lower >= incumbent.cost else "FINITE_ARCHIVE_FEASIBLE"
    elif universe_complete and not unresolved:
        status = "FINITE_ARCHIVE_INFEASIBLE"
    else:
        status = "FINITE_ARCHIVE_UNKNOWN"
    return {"status": status, "root": root, "selected_id": incumbent.id if incumbent else None,
        "cost": str(incumbent.cost) if incumbent else None, "lower_bound": str(lower) if lower is not None else None,
        "unresolved": [o.id for o in unresolved], "candidate_count": len(outcomes),
        "scope": "SUPPLIED_DISPOSED_FINITE_OUTCOME_TABLE", "unknowns_cannot_improve": status == "FINITE_ARCHIVE_OPTIMAL" and bool(unresolved),
        "tie_policy": "LEXICOGRAPHIC_AMONG_ACCEPTED_MINIMIZERS", "physical_witness_checks": "INPUT_EVIDENCE_ROOTS_REQUIRE_DOMAIN_CHECKERS"}


def _law(probabilities):
    values = tuple(rational(p) for p in probabilities)
    if not values or any(p < 0 for p in values) or sum(values) != 1:
        raise ValueError("Finite nonnegative probability law must sum exactly to one")
    return values


def finite_chance_constraint(probabilities, violations, threshold):
    probabilities, violations = _law(probabilities), tuple(violations)
    threshold = rational(threshold)
    if len(probabilities) != len(violations) or not 0 <= threshold <= 1 or any(v not in ("TRUE", "FALSE", "UNKNOWN") for v in violations):
        raise ValueError("Aligned three-valued violation indicators and probability threshold required")
    lower = sum((p for p,v in zip(probabilities,violations) if v == "TRUE"), Q(0))
    upper = sum((p for p,v in zip(probabilities,violations) if v != "FALSE"), Q(0))
    return {"status": "PASS" if upper <= threshold else "FAIL" if lower > threshold else "UNKNOWN",
        "violation_probability": [str(lower),str(upper)], "threshold": str(threshold), "scope": "DECLARED_FINITE_JOINT_LAW"}


def finite_risk(probabilities, losses, *, alpha=Q(95,100)):
    """Exact expectation, worst listed loss and CVaR of a finite supplied law."""
    probabilities, losses, alpha = _law(probabilities), tuple(rational(x) for x in losses), rational(alpha)
    if len(probabilities) != len(losses) or not 0 <= alpha < 1:
        raise ValueError("Aligned finite losses and CVaR alpha in [0,1) required")
    expected = sum((p*x for p,x in zip(probabilities,losses)), Q(0))
    # Convex piecewise-linear CVaR objective attains a minimum at a loss value.
    candidates = [(eta + sum((p*max(x-eta,0) for p,x in zip(probabilities,losses)), Q(0))/(1-alpha), eta) for eta in sorted(set(losses))]
    value, eta = min(candidates)
    return {"expectation": str(expected), "worst_listed_loss": str(max(losses)), "cvar": str(value), "eta": str(eta),
        "alpha": str(alpha), "scope": "DECLARED_FINITE_JOINT_LAW", "breakpoint_count": len(candidates)}


def check_nonanticipativity(histories, actions, *, context_root):
    """Histories list observations available before each stage's action."""
    if set(histories) != set(actions) or not histories:
        raise ValueError("Every scenario needs both history and actions")
    horizons = {len(h) for h in histories.values()} | {len(a) for a in actions.values()}
    if len(horizons) != 1:
        raise ValueError("Scenario histories and actions must share a horizon")
    root = _root(context_root, (histories, actions))
    seen = {}
    for scenario in sorted(histories):
        for stage, action in enumerate(actions[scenario]):
            information = (stage,_token(tuple(histories[scenario][:stage+1])))
            if information in seen:
                other, previous = seen[information]
                if _token(previous) != _token(action):
                    return {"status": "FAIL", "root": root, "reason": "ANTICIPATIVE_ACTION", "stage": stage,
                        "scenarios": [other,scenario], "actions": [previous,action]}
            else:
                seen[information] = (scenario,action)
    return {"status": "PASS", "root": root, "information_nodes": len(seen), "scope": "DECLARED_FINITE_HISTORY_FILTRATION"}


def check_quantity_transport(source, target, allocation, *, source_unit, target_unit, context_root):
    """Check conservative split/merge quantity maps, separately from geometry.

    ``allocation`` contains (source_id,target_id,nonnegative quantity) triples.
    Row sums equal every source quantity; column sums equal every target quantity.
    This does not preserve pressure, geometry, stiffness, costs or certificates.
    """
    if not source_unit or source_unit != target_unit:
        return {"status": "FAIL", "reason": "UNIT_TRANSPORT_NOT_ESTABLISHED"}
    source, target = {k:rational(v) for k,v in source.items()}, {k:rational(v) for k,v in target.items()}
    if any(v < 0 for v in tuple(source.values())+tuple(target.values())):
        raise ValueError("Conserved quantities must be nonnegative")
    rows, columns = dict.fromkeys(source,Q(0)), dict.fromkeys(target,Q(0))
    normalized, seen = [], set()
    for s,t,value in allocation:
        value = rational(value)
        if s not in source or t not in target or value < 0 or (s,t) in seen:
            return {"status": "FAIL", "reason": "INVALID_CORRESPONDENCE_ALLOCATION"}
        rows[s] += value
        columns[t] += value
        normalized.append((s,t,value))
        seen.add((s,t))
    root = _root(context_root, (source,target,tuple(normalized),source_unit))
    defects = {"source": {s:str(rows[s]-source[s]) for s in source if rows[s] != source[s]},
        "target": {t:str(columns[t]-target[t]) for t in target if columns[t] != target[t]}}
    return {"status": "PASS" if not any(defects.values()) else "FAIL", "root": root, "residuals": defects,
        "scope": "CONSERVATIVE_DECLARED_QUANTITY_SPLIT_MERGE", "unit": source_unit,
        "certificate_reuse": "NOT_ESTABLISHED", "geometry_transport": "NOT_ESTABLISHED"}
