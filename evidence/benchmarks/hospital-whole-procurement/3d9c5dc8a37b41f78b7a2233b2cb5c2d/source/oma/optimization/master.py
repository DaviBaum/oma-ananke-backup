"""Exact finite route selection and column pricing.

Source: integration DEF-RTR62/68/70/71/72; THM-RTR67–86; ANANKE THM-F7.
The supplied columns are a finite domain. Geometry/fiber validity is a separate
obligation; this module does not turn a claimed proof reference into a physical
certificate. A caller must run the independent physical checker before release.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
import hashlib
import json
import math
import time
from typing import Callable


def rational(value) -> Fraction:
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Nonfinite engineering value")
        return Fraction(str(value))
    return Fraction(value)


@dataclass(frozen=True)
class RouteColumn:
    id: str
    net_id: str
    cost: Fraction
    resource_use: tuple[tuple[str, Fraction], ...] = ()
    artifact_ref: str = ""

    def __post_init__(self):
        object.__setattr__(self, "cost", rational(self.cost))
        uses = tuple(sorted((str(k), rational(v)) for k, v in self.resource_use))
        if not self.id or not self.net_id or len({k for k, _ in uses}) != len(uses):
            raise ValueError("Column requires unique identity and resource entries")
        if any(v < 0 for _, v in uses):
            raise ValueError("Resource consumption must be nonnegative")
        object.__setattr__(self, "resource_use", uses)


@dataclass(frozen=True)
class Conflict:
    id: str
    columns: tuple[str, ...]
    kind: str = "forbidden_joint"

    def __post_init__(self):
        object.__setattr__(self, "columns", tuple(sorted(self.columns)))
        if not self.id or len(self.columns) < 2 or len(set(self.columns)) != len(self.columns):
            raise ValueError("Conflict needs at least two distinct columns")
        if self.kind not in ("forbidden_joint", "pairwise_clique"):
            raise ValueError("Unknown conflict semantics")

    @property
    def limit(self) -> int:
        # Amendment OMA-MATH-A002: general hyperedge is not a clique.
        return 1 if self.kind == "pairwise_clique" else len(self.columns) - 1


@dataclass(frozen=True)
class MasterProblem:
    net_ids: tuple[str, ...]
    columns: tuple[RouteColumn, ...]
    capacities: tuple[tuple[str, Fraction], ...] = ()
    conflicts: tuple[Conflict, ...] = ()
    state_root: str = ""
    objective_policy: str = "route_cost"
    theory_version: str = "oma-finite-master/1+A002"
    declared_universe_complete: bool = False

    def __post_init__(self):
        object.__setattr__(self, "net_ids", tuple(sorted(self.net_ids)))
        object.__setattr__(self, "columns", tuple(sorted(self.columns, key=lambda c: c.id)))
        object.__setattr__(self, "capacities", tuple(sorted((k, rational(v)) for k, v in self.capacities)))
        object.__setattr__(self, "conflicts", tuple(sorted(self.conflicts, key=lambda c: c.id)))
        if not self.net_ids or len(set(self.net_ids)) != len(self.net_ids):
            raise ValueError("Required net obligations must be nonempty and unique")
        if not self.state_root or not self.objective_policy:
            raise ValueError("State root and explicit objective policy required")
        if len({c.id for c in self.columns}) != len(self.columns):
            raise ValueError("Duplicate column identity")
        if any(c.net_id not in self.net_ids for c in self.columns):
            raise ValueError("Column net absent from obligation list")
        caps = dict(self.capacities)
        if len(caps) != len(self.capacities) or any(v < 0 for v in caps.values()):
            raise ValueError("Invalid resource capacity")
        if any(k not in caps for c in self.columns for k, _ in c.resource_use):
            raise ValueError("Every resource must have explicit capacity")
        ids = {c.id for c in self.columns}
        if len({h.id for h in self.conflicts}) != len(self.conflicts):
            raise ValueError("Duplicate conflict identity")
        if any(c not in ids for h in self.conflicts for c in h.columns):
            raise ValueError("Conflict references unknown column")

    def payload(self):
        return {"nets": self.net_ids, "columns": [{"id": c.id, "net": c.net_id, "cost": str(c.cost),
                "use": [(k, str(v)) for k, v in c.resource_use], "artifact": c.artifact_ref} for c in self.columns],
                "capacities": [(k, str(v)) for k, v in self.capacities],
                "conflicts": [{"id": h.id, "columns": h.columns, "kind": h.kind} for h in self.conflicts],
                "root": self.state_root, "objective": self.objective_policy, "version": self.theory_version,
                "declared_universe_complete": self.declared_universe_complete}

    @property
    def fingerprint(self):
        return hashlib.sha256(json.dumps(self.payload(), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True)
class MasterResult:
    problem_hash: str
    status: str
    selected: tuple[str, ...]
    objective: Fraction | None
    lower_bound: Fraction | None
    search_exhausted: bool
    visited_nodes: int
    combinations: int
    elapsed_seconds: float
    stop_reason: str
    bound_scope: str = "EXPLICIT_COLUMN_UNIVERSE_ONLY"
    physical_check_status: str = "NOT_RUN"

    def to_dict(self):
        return {**self.__dict__, "objective": str(self.objective) if self.objective is not None else None,
                "lower_bound": str(self.lower_bound) if self.lower_bound is not None else None}


def solve_master(problem: MasterProblem, *, max_nodes: int = 1_000_000,
                 time_limit_seconds: float = 60, cancelled: Callable[[], bool] | None = None,
                 on_candidate: Callable[[dict], None] | None = None) -> MasterResult:
    """Branch over net choices with exact resource/conflict and optimistic-cost pruning.

    Completeness is only over serialized columns. At a limit the incumbent is
    retained, with no exact optimum/infeasibility claim. All quantities are SI or
    explicit policy units at the adapter boundary; scalar cost is policy-bound.
    """
    if max_nodes < 1 or not math.isfinite(time_limit_seconds) or time_limit_seconds <= 0:
        raise ValueError("Positive finite computation budget required")
    started = time.monotonic()
    choices = {n: sorted((c for c in problem.columns if c.net_id == n), key=lambda c: (c.cost, c.id)) for n in problem.net_ids}
    order = sorted(problem.net_ids, key=lambda n: (len(choices[n]), n))
    combinations = math.prod(len(choices[n]) for n in order)
    capacities = dict(problem.capacities)
    minimum = [min((c.cost for c in choices[n]), default=Fraction(0)) for n in order]
    suffix = [Fraction(0)] * (len(order) + 1)
    for i in range(len(order) - 1, -1, -1):
        suffix[i] = suffix[i + 1] + minimum[i]
    incumbent, optimum, visited, stop = (), None, 0, "EXHAUSTED"
    stack = [(0, (), Fraction(0), {})]
    while stack:
        if cancelled and cancelled():
            stop = "CANCELLED"
            break
        if visited >= max_nodes:
            stop = "NODE_LIMIT"
            break
        if time.monotonic() - started >= time_limit_seconds:
            stop = "TIME_LIMIT"
            break
        depth, selected, cost, used = stack.pop()
        visited += 1
        if optimum is not None and cost + suffix[depth] > optimum:
            continue
        if depth == len(order):
            canonical = tuple(sorted(selected))
            if optimum is None or (cost, canonical) < (optimum, incumbent):
                incumbent, optimum = canonical, cost
                if on_candidate:
                    on_candidate({"kind": "master_incumbent", "selected": canonical,
                                  "objective": str(cost), "problem_hash": problem.fingerprint,
                                  "physical_check_status": "NOT_RUN"})
            continue
        for column in reversed(choices[order[depth]]):
            proposed = selected + (column.id,)
            ids = set(proposed)
            if any(len(ids.intersection(h.columns)) > h.limit for h in problem.conflicts):
                continue
            next_use = dict(used)
            for resource, demand in column.resource_use:
                next_use[resource] = next_use.get(resource, Fraction(0)) + demand
            if any(value > capacities[k] for k, value in next_use.items()):
                continue
            stack.append((depth + 1, proposed, cost + column.cost, next_use))
    exhausted = stop == "EXHAUSTED"
    if exhausted:
        status = "FINITE_MASTER_OPTIMAL" if optimum is not None else "FINITE_MASTER_INFEASIBLE"
    else:
        status = "FINITE_MASTER_FEASIBLE" if optimum is not None else "MASTER_UNKNOWN"
    # A restricted universe does not license a bound on the intended full master.
    bound = (optimum if exhausted else suffix[0]) if problem.declared_universe_complete and combinations else None
    return MasterResult(problem.fingerprint, status, incumbent, optimum, bound, exhausted, visited,
                        combinations, time.monotonic() - started, stop)


@dataclass(frozen=True)
class DualCertificate:
    problem_hash: str
    alpha: tuple[tuple[str, Fraction], ...]
    prices: tuple[tuple[str, Fraction], ...]
    lower_bound: Fraction
    priced_columns: int
    scope: str = "EXPLICIT_COLUMN_UNIVERSE_ONLY"


def constraint_rows(problem: MasterProblem):
    rows = [("capacity:" + k, v, {c.id: dict(c.resource_use).get(k, Fraction(0)) for c in problem.columns})
            for k, v in problem.capacities]
    rows += [("conflict:" + h.id, Fraction(h.limit), {c.id: Fraction(c.id in h.columns) for c in problem.columns})
             for h in problem.conflicts]
    return rows


def price_columns(problem: MasterProblem, proposed_prices: dict[str, object] | None = None) -> DualCertificate:
    """Exact finite-domain pricing repairs alpha for arbitrary nonnegative prices.

    alpha_n=min_r(c_r+sum_j price_j*a_jr) makes every serialized column's
    reduced cost nonnegative. Weak duality proves the returned lower bound for
    this explicit domain, regardless of floating solver quality or provenance.
    """
    rows = constraint_rows(problem)
    proposed_prices = proposed_prices or {}
    if any(k not in {row[0] for row in rows} for k in proposed_prices):
        raise ValueError("Multiplier references a different primal")
    prices = {k: rational(proposed_prices.get(k, 0)) for k, _, _ in rows}
    if any(v < 0 for v in prices.values()):
        raise ValueError("Capacity/conflict dual multipliers must be nonnegative")
    alpha = {}
    for net in problem.net_ids:
        costs = [c.cost + sum((prices[k] * a[c.id] for k, _, a in rows), Fraction(0))
                 for c in problem.columns if c.net_id == net]
        if not costs:
            raise ValueError("No column for required net; finite pricing domain is empty")
        alpha[net] = min(costs)
    lower = sum(alpha.values(), Fraction(0)) - sum((rhs * prices[k] for k, rhs, _ in rows), Fraction(0))
    return DualCertificate(problem.fingerprint, tuple(sorted(alpha.items())), tuple(sorted(prices.items())), lower, len(problem.columns))


def generate_columns(problem: MasterProblem, *, max_rounds: int = 50, time_limit_seconds: float = 30):
    """HiGHS restricted LP proposals followed by exact finite pricing.

    This is finite-column generation, not continuous-space branch-and-price.
    Infeasible numeric restricted LPs trigger enrichment, never an infeasibility
    certificate. The rational dual repair remains independently checkable.
    """
    from scipy.optimize import linprog
    rows = constraint_rows(problem)
    pool = {min((c for c in problem.columns if c.net_id == n), key=lambda c: (c.cost, c.id)).id
            for n in problem.net_ids}
    rounds = []
    certificate = price_columns(problem)
    started = time.monotonic()
    for iteration in range(max_rounds):
        remaining = time_limit_seconds - (time.monotonic() - started)
        if remaining <= 0:
            break
        current = [c for c in problem.columns if c.id in pool]
        result = linprog([float(c.cost) for c in current],
                         A_ub=[[float(a[c.id]) for c in current] for _, _, a in rows] or None,
                         b_ub=[float(rhs) for _, rhs, _ in rows] or None,
                         A_eq=[[int(c.net_id == n) for c in current] for n in problem.net_ids],
                         b_eq=[1] * len(problem.net_ids), bounds=(0, None), method="highs",
                         options={"time_limit": max(0.001, remaining)})
        entry = {"iteration": iteration, "pool_size": len(pool), "numeric_status": int(result.status)}
        rounds.append(entry)
        if result.status != 0:
            if len(pool) == len(problem.columns):
                entry["disposition"] = "NUMERIC_RESULT_UNCERTIFIED"
                break
            pool.update(c.id for c in problem.columns)
            entry["disposition"] = "ENRICH_FOR_PHASE_I"
            continue
        prices = {k: max(Fraction(0), rational(float(-value)))
                  for (k, _, _), value in zip(rows, result.ineqlin.marginals)}
        certificate = price_columns(problem, prices)
        raw_alpha = {n: rational(float(v)) for n, v in zip(problem.net_ids, result.eqlin.marginals)}
        added = []
        for net in problem.net_ids:
            candidates = [(c.cost - raw_alpha[net] + sum((prices[k] * a[c.id] for k, _, a in rows), Fraction(0)), c.id)
                          for c in problem.columns if c.net_id == net and c.id not in pool]
            if candidates and min(candidates)[0] < 0:
                added.append(min(candidates)[1])
        entry.update(added=added, rational_lower_bound=str(certificate.lower_bound))
        if not added:
            entry["disposition"] = "FINITE_PRICING_CLOSED_DUAL_REPAIRED"
            break
        pool.update(added)
    return {"problem_hash": problem.fingerprint, "pool": tuple(sorted(pool)), "rounds": rounds,
            "dual": certificate, "scope": "EXPLICIT_COLUMN_UNIVERSE_ONLY"}
