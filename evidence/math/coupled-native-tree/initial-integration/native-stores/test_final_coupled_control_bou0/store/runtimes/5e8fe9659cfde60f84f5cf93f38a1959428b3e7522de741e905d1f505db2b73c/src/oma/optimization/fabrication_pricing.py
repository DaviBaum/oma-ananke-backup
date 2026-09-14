"""Exact nominal cost pricing on the declared finite fabrication graph.

The producer uses Dijkstra; the verifier checks a realizing path and a total
dual potential, represented by explicit labels with a constant default. Shared
graph predicates define the model, not the optimization algorithm. No native,
continuous or resource-reduced-cost lower bound follows from this certificate.
"""
from copy import deepcopy
from fractions import Fraction as Q
import heapq
import hashlib
import json
import re

from oma.store import digest
from . import fabrication_search as graph


SCHEMA = "oma.fabrication-grid-pricing-certificate/1"
SCOPE = "EXACT_WEIGHTED_NOMINAL_LENGTH_AND_BENDS_ON_DECLARED_FINITE_GRAPH"
RULE = "NONNEGATIVE_DEFERRED_STRAIGHT_QUARTER_ARC_COST_WITH_TERMINAL_SINK_V1"
SINK = (-2,) * 6
ZERO = (Q(0), Q(0))
COST_BITS = 12000
MAX_CERTIFICATE_BYTES = 16 * 1024 * 1024
LIMITATIONS = {
    "finite_declared_graph_optimality_only": True,
    "source_and_frame_authenticity_checked": False,
    "nonadjacent_self_interference_checked": False,
    "continuous_route_completeness": False,
    "physical_route_infeasibility_claim": False,
    "native_IFC_candidate_acceptance_authority": False,
    "native_numeric_objective_lower_bound": False,
    "general_resource_reduced_cost_pricing": False,
    "all_equal_cost_routes_retained": False,
}


def _cost_shape(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("Cost must be the pair [rational, pi coefficient]")
    for x in value:
        if not isinstance(x, str) or len(x) > 10000 or re.fullmatch(r"-?[0-9]+(?:/[1-9][0-9]*)?", x) is None:
            raise ValueError("Bounded exact rational cost strings required")


def _cost(value):
    _cost_shape(value)
    result = []
    for x in value:
        q = Q(x)
        if max(q.numerator.bit_length(), q.denominator.bit_length()) > COST_BITS:
            raise graph._Exhausted("COST_ARITHMETIC_BUDGET")
        result.append(q)
    return tuple(result)


def _encoded(value):
    if any(max(x.numerator.bit_length(), x.denominator.bit_length()) > COST_BITS for x in value):
        raise graph._Exhausted("COST_ARITHMETIC_BUDGET")
    return [str(x) for x in value]


def _plus(a, b):
    result = (a[0] + b[0], a[1] + b[1])
    _encoded(result)
    return result


def _objective(value):
    if not isinstance(value, dict) or set(value) != {"schema", "length_weight", "fitting_weight"} or value["schema"] != "oma.fabrication-grid-cost/1":
        raise ValueError("Complete fixed length and fitting objective required")
    length = graph._rational(value["length_weight"])
    fitting = graph._rational(value["fitting_weight"])
    if min(length, fitting) < 0 or max(length, fitting) <= 0:
        raise ValueError("Nonnegative weights, at least one positive, required")
    normalized = {"schema": value["schema"], "length_weight": str(length), "fitting_weight": str(fitting)}
    return normalized, (length, fitting)


def _producer_pi_interval(terms, work):
    bounds = []
    for denominator in (5, 239):
        total, power = Q(0), Q(1, denominator)
        for k in range(terms):
            work.tick()
            total += power / (2 * k + 1)
            power /= -denominator * denominator
        adjacent = total + power / (2 * terms + 1)
        bounds.append((min(total, adjacent), max(total, adjacent)))
    return 16 * bounds[0][0] - 4 * bounds[1][1], 16 * bounds[0][1] - 4 * bounds[1][0]


def _checker_pi_interval(terms, work):
    # Independent powers/sums and alternating-remainder orientation. Neither
    # producer interval nor its stored endpoints are trusted by the verifier.
    def enclosure(q):
        s = Q(0)
        for k in range(terms):
            work.tick()
            s += Q((-1) ** k, (2 * k + 1) * q ** (2 * k + 1))
        error = Q(1, (2 * terms + 1) * q ** (2 * terms + 1))
        return (s, s + error) if terms % 2 == 0 else (s - error, s)
    low5, high5 = enclosure(5)
    low239, high239 = enclosure(239)
    return 16 * low5 - 4 * high239, 16 * high5 - 4 * low239


class _Comparison:
    def __init__(self, limit, work, *, checker=False):
        if type(limit) is not int or not 1 <= limit <= 512:
            raise ValueError("Pi series budget must be 1..512 terms per arctangent")
        self.limit, self.work, self.terms, self.bounds = limit, work, 0, None
        self.interval = _checker_pi_interval if checker else _producer_pi_interval

    def compare(self, a, b):
        self.work.tick()
        x, y = a[0] - b[0], a[1] - b[1]
        if x == 0 and y == 0:
            return 0
        # pi > 0 suffices for coefficientwise ordering.
        if x >= 0 and y >= 0:
            return 1
        if x <= 0 and y <= 0:
            return -1
        while True:
            if self.bounds is not None:
                p, q = self.bounds
                low, high = (x + y * p, x + y * q) if y > 0 else (x + y * q, x + y * p)
                if low > 0:
                    return 1
                if high < 0:
                    return -1
            if self.terms >= self.limit:
                raise graph._Exhausted("PI_COMPARISON_PRECISION_BUDGET")
            self.terms = min(self.limit, max(1, self.terms * 2))
            self.bounds = self.interval(self.terms, self.work)


class _Priority:
    def __init__(self, cost, state, compare):
        self.cost, self.state, self.compare = cost, state, compare

    def __lt__(self, other):
        order = self.compare(self.cost, other.cost)
        return order < 0 or (order == 0 and self.state < other.state)


def _producer_edge_cost(m, weights, state, target):
    length, fitting = weights
    if target == SINK:
        return (length * (graph._run_length(m, state) - state[5] * m["R"]), Q(0))
    if state[3] < 0 or state[3] == target[3]:
        return ZERO
    straight = graph._run_length(m, state) - (state[5] + 1) * m["R"]
    return length * straight + fitting, length * m["R"] / 2


def _checked_edges(m, weights, state, work, cache):
    """Reconstruct admitted edges and cost coefficients without producer code."""
    length_weight, fitting_weight = weights
    for target in graph._checked_successors(m, state, work, cache):
        if state[3] < 0 or state[3] == target[3]:
            cost = ZERO
        else:
            axis = state[3] // 2
            travel = abs(m["axes"][axis][state[axis]] - m["axes"][axis][state[4]])
            remaining = travel - m["R"] - (m["R"] if state[5] else 0)
            if remaining <= m["minimum"]:
                raise ValueError("Admitted turn did not discharge positive straight debt")
            cost = length_weight * remaining + fitting_weight, length_weight * m["R"] / 2
        if min(cost) < 0:
            raise ValueError("Negative cost violates the total default-potential proof")
        yield target, cost
    if graph._goal(m, state):
        axis = state[3] // 2
        travel = abs(m["axes"][axis][state[axis]] - m["axes"][axis][state[4]])
        remaining = travel - (m["R"] if state[5] else 0)
        if remaining <= m["minimum"]:
            raise ValueError("Terminal does not discharge positive final straight debt")
        yield SINK, (length_weight * remaining, Q(0))


def _base(m, objective):
    return {"schema": SCHEMA, "status": "CERTIFIED", "scope": SCOPE, "rule": RULE,
            "limitations": deepcopy(LIMITATIONS), "input_root": m["root"], "graph_root": m["graph_root"],
            "objective": objective, "objective_root": digest(objective),
            "pricing_root": digest({"graph_root": m["graph_root"], "objective": objective, "rule": RULE})}


def _certificate_digest(value, work):
    """Store-compatible canonical hashing with a byte budget and checkpoints."""
    hasher, size = hashlib.sha256(), 0
    encoder = json.JSONEncoder(sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    work.pulse("fabrication_pricing_hash_start")
    for index, chunk in enumerate(encoder.iterencode(value)):
        if index % 256 == 0:
            work.pulse("fabrication_pricing_hash")
        data = chunk.encode("utf-8")
        size += len(data)
        if size > MAX_CERTIFICATE_BYTES:
            raise graph._Exhausted("CERTIFICATE_BYTE_BUDGET")
        hasher.update(data)
    work.pulse("fabrication_pricing_hash_complete")
    return hasher.hexdigest()


def _certificate_lists(m, path, settled, closed, work):
    # Conservative preallocation accounting bounds memory before canonical
    # hashing establishes the exact byte count. Coordinates are ASCII rationals.
    remaining = MAX_CERTIFICATE_BYTES - 4096
    def charge(size):
        nonlocal remaining
        remaining -= size
        if remaining < 0:
            raise graph._Exhausted("CERTIFICATE_BYTE_BUDGET")
    output = {"path_states": [], "points_m": [], "potentials": [], "closed_states": []}
    for field, states in (("path_states", path), ("closed_states", sorted(closed))):
        for index, state in enumerate(states):
            if index % 128 == 0:
                work.pulse("fabrication_pricing_serialize")
            charge(64)
            output[field].append(list(state))
    work.pulse("fabrication_pricing_serialize")
    for index, (state, cost) in enumerate(sorted(settled.items())):
        if index % 128 == 0:
            work.pulse("fabrication_pricing_serialize")
        encoded = _encoded(cost)
        charge(128 + sum(map(len, encoded)))
        output["potentials"].append({"state": list(state), "cost": encoded})
    if path:
        corners = [m["start"]]
        for index, (before, after) in enumerate(zip(path, path[1:])):
            if index % 128 == 0:
                work.pulse("fabrication_pricing_serialize")
            if before[3] >= 0 and before[3] != after[3]:
                corners.append(before[:3])
        corners.append(m["goal"])
        for index, vertex in enumerate(corners):
            if index % 128 == 0:
                work.pulse("fabrication_pricing_serialize")
            point = graph._pj(graph._position(m, vertex))
            charge(16 + sum(map(len, point)))
            output["points_m"].append(point)
    return output


def _finish(result, work, comparison):
    result.update(producer_work=work.used, pi_terms_used=comparison.terms)
    result["certificate_root"] = _certificate_digest(result, work)
    work.pulse("fabrication_pricing_complete")
    return result


def compile_fabrication_pricing(problem, objective, *, max_states=12000, max_work=500000,
                                max_pi_terms=256, checkpoint=None):
    """Produce a finite-graph optimum, a finite cut, or budgeted UNKNOWN."""
    work = graph._Work(max_work, checkpoint)
    m = None
    try:
        m = graph._prepare(problem, max_states, work)
        normalized, weights = _objective(objective)
        comparison = _Comparison(max_pi_terms, work)
        initial = m["initial"]
        distances, parents, settled, cache = {initial: ZERO}, {initial: None}, {}, {}
        queue = [_Priority(ZERO, initial, comparison.compare)]
        while queue:
            work.pulse("fabrication_pricing_expand")
            entry = heapq.heappop(queue)
            state, cost = entry.state, entry.cost
            if state in settled or distances[state] != cost:
                continue
            if state == SINK:
                path = []
                current = parents[SINK]
                while current is not None:
                    work.tick()
                    path.append(current)
                    current = parents[current]
                path.reverse()
                result = _base(m, normalized)
                result.update(pricing_outcome="OPTIMAL_PATH", geometry_outcome="PATH", cost=_encoded(cost),
                              default_potential=_encoded(cost), **_certificate_lists(m, path, settled, [], work))
                return _finish(result, work, comparison)
            settled[state] = cost
            targets = list(graph._producer_successors(m, state, work, cache))
            if graph._goal(m, state):
                targets.append(SINK)
            for target in targets:
                if target in settled:
                    continue
                candidate = _plus(cost, _producer_edge_cost(m, weights, state, target))
                if target not in distances or comparison.compare(candidate, distances[target]) < 0:
                    if target not in distances and len(distances) >= max_states:
                        raise graph._Exhausted("STATE_BUDGET")
                    distances[target], parents[target] = candidate, state
                    heapq.heappush(queue, _Priority(candidate, target, comparison.compare))
        result = _base(m, normalized)
        result.update(pricing_outcome="NO_PATH_IN_DECLARED_GRAPH", geometry_outcome="NO_PATH_IN_DECLARED_GRAPH",
                      cost=None, default_potential=None, **_certificate_lists(m, [], {}, settled, work))
        return _finish(result, work, comparison)
    except graph._Exhausted as exc:
        if work.callback_error is exc:
            raise
        return {"status": "UNKNOWN", "reason": str(exc), "input_root": m["root"] if m else None,
                "scope": SCOPE, "limitations": deepcopy(LIMITATIONS), "proof_complete": False, "work": work.used}


def verify_fabrication_pricing(problem, objective, certificate, *, max_states=12000, max_work=500000,
                               max_pi_terms=256, checkpoint=None):
    """Check the path plus total sparse dual, without trusting Dijkstra labels."""
    work = graph._Work(max_work, checkpoint)
    try:
        m = graph._prepare(problem, max_states, work)
        normalized, weights = _objective(objective)
        comparison = _Comparison(max_pi_terms, work, checker=True)
        if not isinstance(certificate, dict):
            raise ValueError("Pricing certificate object required")
        if certificate.get("status") == "UNKNOWN":
            return {"status": "UNKNOWN", "reason": "NO_COMPLETE_CERTIFICATE", "scope": SCOPE}
        base = _base(m, normalized)
        fields = set(base) | {"pricing_outcome", "geometry_outcome", "cost", "path_states", "points_m", "potentials",
                             "default_potential", "closed_states", "producer_work", "pi_terms_used", "certificate_root"}
        if set(certificate) != fields:
            raise ValueError("Complete pricing certificate schema required")
        for key, value in base.items():
            if certificate[key] != value:
                raise ValueError("Input, graph, objective, scope or pricing identity differs")
        for key in ("path_states", "points_m", "potentials", "closed_states"):
            if not isinstance(certificate[key], list):
                raise ValueError("Bounded proof lists required")
            if len(certificate[key]) > max_states:
                raise graph._Exhausted("CERTIFICATE_STATE_BUDGET")
        path, closed = [], []
        for field, destination in (("path_states", path), ("closed_states", closed)):
            for state in certificate[field]:
                work.tick()
                destination.append(graph._valid_state(m, state))
        for point in certificate["points_m"]:
            work.tick()
            if not isinstance(point, list) or len(point) != 3 or any(not isinstance(x, str) or len(x) > 2500 for x in point):
                raise ValueError("Bounded normalized path coordinates required")
        encoded_potentials = {}
        for row in certificate["potentials"]:
            work.tick()
            if not isinstance(row, dict) or set(row) != {"state", "cost"}:
                raise ValueError("Explicit state and potential pair required")
            state = graph._valid_state(m, row["state"])
            _cost_shape(row["cost"])
            if state in encoded_potentials:
                raise ValueError("Duplicate explicit potential state")
            encoded_potentials[state] = row["cost"]
        for field in ("cost", "default_potential"):
            if certificate[field] is not None:
                _cost_shape(certificate[field])
        if type(certificate["producer_work"]) is not int or not 0 <= certificate["producer_work"] <= 10000000:
            raise ValueError("Invalid producer work metadata")
        if type(certificate["pi_terms_used"]) is not int or not 0 <= certificate["pi_terms_used"] <= 512:
            raise ValueError("Invalid producer precision metadata")
        if (certificate["pricing_outcome"] not in ("OPTIMAL_PATH", "NO_PATH_IN_DECLARED_GRAPH")
                or certificate["geometry_outcome"] not in ("PATH", "NO_PATH_IN_DECLARED_GRAPH")
                or not isinstance(certificate["certificate_root"], str) or len(certificate["certificate_root"]) != 64):
            raise ValueError("Bounded pricing disposition and certificate root required")
        if _certificate_digest({k: v for k, v in certificate.items() if k != "certificate_root"}, work) != certificate["certificate_root"]:
            raise ValueError("Certificate content root differs")
        # The complete bounded encoding is checked before allocating all large
        # rational labels. Producer precision metadata does not affect replay.
        potentials = {}
        for state, encoded in encoded_potentials.items():
            work.tick()
            potentials[state] = _cost(encoded)
        cost = _cost(certificate["cost"]) if certificate["cost"] is not None else None
        default = _cost(certificate["default_potential"]) if certificate["default_potential"] is not None else None
        cache, transitions = {}, 0
        if certificate["pricing_outcome"] == "OPTIMAL_PATH":
            if certificate["geometry_outcome"] != "PATH" or closed or cost is None or default != cost:
                raise ValueError("Optimal path requires its finite cost as total default potential")
            if not path or path[0] != m["initial"] or not graph._goal(m, path[-1]):
                raise ValueError("Realizing path does not bind the source and accepting goal")
            if potentials.get(m["initial"]) != ZERO or comparison.compare(cost, ZERO) < 0:
                raise ValueError("Source potential must be zero and terminal cost nonnegative")
            for value in potentials.values():
                if comparison.compare(value, ZERO) < 0 or comparison.compare(value, cost) > 0:
                    raise ValueError("Explicit potential is outside the default cap")
            # Default-state outgoing edges are discharged universally: all
            # targets have potential <= C and every model edge cost >= 0.
            for state, value in potentials.items():
                work.pulse("fabrication_pricing_dual_verify")
                for target, edge_cost in _checked_edges(m, weights, state, work, cache):
                    transitions += 1
                    target_value = cost if target == SINK else potentials.get(target, cost)
                    if comparison.compare(target_value, _plus(value, edge_cost)) > 0:
                        raise ValueError("A complete outgoing dual-edge inequality fails")
            total = ZERO
            for before, after in zip(path, [*path[1:], SINK]):
                work.pulse("fabrication_pricing_path_verify")
                admitted = dict(_checked_edges(m, weights, before, work, cache))
                transitions += len(admitted)
                if after not in admitted:
                    raise ValueError("Realizing path uses an inadmissible fabrication transition")
                total = _plus(total, admitted[after])
            if total != cost or certificate["points_m"] != graph._path_points(m, path):
                raise ValueError("Claimed exact objective or returned polyline differs from the realizing path")
        elif certificate["pricing_outcome"] == "NO_PATH_IN_DECLARED_GRAPH":
            if (certificate["geometry_outcome"] != "NO_PATH_IN_DECLARED_GRAPH" or path or certificate["points_m"]
                    or potentials or cost is not None or default is not None):
                raise ValueError("Finite cut cannot carry a path or objective optimum")
            states = set(closed)
            if len(states) != len(closed) or m["initial"] not in states:
                raise ValueError("Unique complete closed set containing the source required")
            for state in states:
                work.pulse("fabrication_pricing_cut_verify")
                successors = set(graph._checked_successors(m, state, work, cache))
                transitions += len(successors)
                if graph._goal(m, state) or not successors <= states:
                    raise ValueError("Finite cut omits a successor or contains an accepting goal")
        else:
            raise ValueError("Unknown pricing outcome")
        work.pulse("fabrication_pricing_verified")
        return {"status": "PASS", "pricing_outcome": certificate["pricing_outcome"],
                "geometry_outcome": certificate["geometry_outcome"], "cost": certificate["cost"], "scope": SCOPE,
                "input_root": m["root"], "graph_root": m["graph_root"], "pricing_root": base["pricing_root"],
                "certificate_root": certificate["certificate_root"], "explicit_potentials_checked": len(potentials),
                "transitions_reconstructed": transitions, "pi_terms_used": comparison.terms,
                "work": work.used, "limitations": deepcopy(LIMITATIONS)}
    except graph._Exhausted as exc:
        if work.callback_error is exc:
            raise
        return {"status": "UNKNOWN", "reason": str(exc), "scope": SCOPE, "work": work.used}
    except (ValueError, TypeError, KeyError, IndexError, OverflowError, ZeroDivisionError) as exc:
        if work.callback_error is exc:
            raise
        return {"status": "FAIL", "reason": str(exc), "scope": SCOPE}
