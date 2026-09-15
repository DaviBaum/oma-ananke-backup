"""Exact cost frontier by turn count in a bounded fabrication graph.

For a fixed count k the pi coefficient is fixed. The producer optimizes only
rational deferred costs on (fabrication state, k). The independent verifier
checks a grounded complete reachable-state table, all outgoing inequalities,
terminal debt, and one realizing path per reachable exact count.
"""
from copy import deepcopy
from fractions import Fraction as Q
import hashlib
import heapq
import json
import re

from oma.store import digest
from . import fabrication_search as graph


SCHEMA = "oma.fabrication-count-frontier/1"
SCOPE = "EXACT_COUNT_NOMINAL_COST_FRONTIER_ON_DECLARED_FINITE_FABRICATION_GRAPH"
RULE = "EXACT_TURN_COUNT_PRODUCT_NONNEGATIVE_RATIONAL_DEFERRED_COST_V1"
MAX_FITTINGS = 32
COST_BITS = 12000
MAX_CERTIFICATE_BYTES = 16 * 1024 * 1024
LIMITATIONS = {
    "exact_count_not_at_most_count": True,
    "declared_finite_graph_only": True,
    "source_and_frame_authenticity_checked": False,
    "nonadjacent_self_interference_checked": False,
    "continuous_route_completeness": False,
    "physical_route_infeasibility_claim": False,
    "native_numeric_objective_lower_bound": False,
    "native_IFC_candidate_acceptance_authority": False,
    "all_equal_cost_paths_retained": False,
    "joint_resource_or_collision_selection_performed": False,
}


def _budgets(k, states, byte_limit):
    if type(k) is not int or not 0 <= k <= MAX_FITTINGS:
        raise ValueError("Exact fitting-count maximum must be an integer in [0,32]")
    if type(states) is not int or not 1 <= states <= 100000:
        raise ValueError("Product-state budget must be an integer in [1,100000]")
    if type(byte_limit) is not int or not 1024 <= byte_limit <= 64 * 1024 * 1024:
        raise ValueError("Certificate byte budget must be in [1024,67108864]")


def _objective(value):
    if not isinstance(value, dict) or set(value) != {"schema", "length_weight", "fitting_weight"} or value["schema"] != "oma.fabrication-grid-cost/1":
        raise ValueError("Complete fixed nominal length and fitting objective required")
    weights = tuple(graph._rational(value[k]) for k in ("length_weight", "fitting_weight"))
    if min(weights) < 0 or max(weights) <= 0:
        raise ValueError("Nonnegative objective weights, at least one positive, required")
    return {"schema": value["schema"], "length_weight": str(weights[0]), "fitting_weight": str(weights[1])}, weights


def _bounded(value):
    if max(value.numerator.bit_length(), value.denominator.bit_length()) > COST_BITS:
        raise graph._Exhausted("COST_ARITHMETIC_BUDGET")
    return value


def _shape(value):
    if not isinstance(value, str) or len(value) > 10000 or re.fullmatch(r"-?[0-9]+(?:/[1-9][0-9]*)?", value) is None:
        raise ValueError("Bounded rational cost string required")


def _rational_cost(value):
    _shape(value)
    result = _bounded(Q(value))
    if str(result) != value:
        raise ValueError("Canonical rational cost encoding required")
    return result


def _state(m, value, maximum):
    if not isinstance(value, (list, tuple)) or len(value) != 7 or any(type(x) is not int for x in value):
        raise ValueError("Seven integer product-state coordinates required")
    state = graph._valid_state(m, value[:6])
    count = value[6]
    if not 0 <= count <= maximum or (state == m["initial"] and count != 0):
        raise ValueError("State outside declared exact-count domain")
    return (*state, count)


def _base(m, objective, maximum):
    domain = {"minimum": 0, "maximum": maximum, "meaning": "EXACT_NUMBER_OF_NINETY_DEGREE_TURNS"}
    model = {"graph_root": m["graph_root"], "objective": objective, "count_domain": domain, "rule": RULE}
    return {"schema": SCHEMA, "status": "CERTIFIED", "scope": SCOPE, "rule": RULE,
        "input_root": m["root"], "graph_root": m["graph_root"], "objective": objective,
        "objective_root": digest(objective), "count_domain": domain, "count_domain_root": digest(domain),
        "frontier_model_root": digest(model), "limitations": deepcopy(LIMITATIONS)}


def _producer_edges(m, weights, state, maximum, work, cache):
    source = state[:6]
    for target in graph._producer_successors(m, source, work, cache):
        turn = int(source[3] >= 0 and source[3] != target[3])
        count = state[6] + turn
        if count > maximum:
            continue
        cost = Q(0)
        if turn:
            cost = weights[0] * (graph._run_length(m, source) - (source[5] + 1) * m["R"]) + weights[1]
        yield (*target, count), _bounded(cost)


def _checked_edges(m, weights, state, maximum, work, cache):
    """Independent cost and count construction over the checker graph model."""
    source = state[:6]
    for target in graph._checked_successors(m, source, work, cache):
        changed_axis = source[3] >= 0 and source[3] // 2 != target[3] // 2
        count = state[6] + int(changed_axis)
        if count > maximum:
            continue
        cost = Q(0)
        if changed_axis:
            axis = source[3] // 2
            travel = abs(m["axes"][axis][source[axis]] - m["axes"][axis][source[4]])
            remaining = travel - m["R"] - (m["R"] if source[5] else 0)
            if remaining <= m["minimum"]:
                raise ValueError("Turn did not discharge its strict straight debt")
            cost = weights[0] * remaining + weights[1]
        if cost < 0:
            raise ValueError("Negative rational edge cost")
        yield (*target, count), _bounded(cost)


def _terminal(m, weight, state):
    axis = state[3] // 2
    travel = abs(m["axes"][axis][state[axis]] - m["axes"][axis][state[4]])
    remaining = travel - (m["R"] if state[5] else 0)
    if remaining <= m["minimum"]:
        raise ValueError("Terminal did not discharge its strict final straight debt")
    return _bounded(weight * remaining)


def _points(m, path, work):
    vertices = [m["start"]]
    for first, second in zip(path, path[1:]):
        work.tick()
        if first[3] >= 0 and first[3] != second[3]:
            vertices.append(first[:3])
    vertices.append(m["goal"])
    return [graph._pj(graph._position(m, vertex)) for vertex in vertices]


def _checked_points(m, path, work):
    """Recover corners from verified count increases, independently of producer contraction."""
    points = [[str(m["axes"][axis][m["start"][axis]]) for axis in range(3)]]
    for index in range(1, len(path)):
        work.tick()
        if path[index][6] > path[index - 1][6]:
            points.append([str(m["axes"][axis][path[index - 1][axis]]) for axis in range(3)])
    points.append([str(m["axes"][axis][m["goal"][axis]]) for axis in range(3)])
    return points


def _hash(value, byte_limit, work):
    hasher, size = hashlib.sha256(), 0
    encoder = json.JSONEncoder(sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    work.pulse("fabrication_frontier_hash_start")
    for index, chunk in enumerate(encoder.iterencode(value)):
        if index % 256 == 0:
            work.pulse("fabrication_frontier_hash")
        data = chunk.encode("utf-8")
        size += len(data)
        if size > byte_limit:
            raise graph._Exhausted("CERTIFICATE_BYTE_BUDGET")
        hasher.update(data)
    work.pulse("fabrication_frontier_hash_complete")
    return hasher.hexdigest()


def _unknown(reason, work, m=None):
    return {"status": "UNKNOWN", "reason": reason, "scope": SCOPE, "proof_complete": False,
        "input_root": m["root"] if m else None, "work": work.used, "limitations": deepcopy(LIMITATIONS)}


def compile_fabrication_frontier(problem, objective, max_fittings, *, max_states=24000, max_work=1000000,
                                 max_certificate_bytes=MAX_CERTIFICATE_BYTES, checkpoint=None):
    """Certify every exact count 0..K, or return UNKNOWN without partial claims."""
    _budgets(max_fittings, max_states, max_certificate_bytes)
    work = graph._Work(max_work, checkpoint)
    m = None
    try:
        m = graph._prepare(problem, max_states, work)
        normalized, weights = _objective(objective)
        initial = (*m["initial"], 0)
        distances, parents, settled, cache = {initial: Q(0)}, {initial: None}, {}, {}
        queue, terminal = [(Q(0), initial)], {}
        while queue:
            work.pulse("fabrication_frontier_expand")
            cost, state = heapq.heappop(queue)
            if state in settled or distances[state] != cost:
                continue
            settled[state] = cost
            if graph._goal(m, state[:6]):
                value = _bounded(cost + weights[0] * (graph._run_length(m, state[:6]) - state[5] * m["R"]))
                if state[6] not in terminal or value < terminal[state[6]][0]:
                    terminal[state[6]] = (value, state)
            for target, edge in _producer_edges(m, weights, state, max_fittings, work, cache):
                candidate = _bounded(cost + edge)
                if target not in settled and (target not in distances or candidate < distances[target]):
                    if target not in distances and len(distances) >= max_states:
                        raise graph._Exhausted("PRODUCT_STATE_BUDGET")
                    distances[target], parents[target] = candidate, state
                    heapq.heappush(queue, (candidate, target))
        # No partial table can confer count-specific optimality/unreachability.
        result = _base(m, normalized, max_fittings)
        rows, indexes, frontier = [], {}, []
        allocated = 4096
        def charge(size):
            nonlocal allocated
            allocated += size
            if allocated > max_certificate_bytes:
                raise graph._Exhausted("CERTIFICATE_BYTE_BUDGET")
        for state, cost in settled.items():
            work.tick()
            if len(rows) % 128 == 0:
                work.pulse("fabrication_frontier_serialize")
            encoded = str(_bounded(cost))
            charge(192 + len(encoded))
            parent = parents[state]
            rows.append({"state": list(state), "potential": encoded,
                "parent": indexes[parent] if parent is not None else None})
            indexes[state] = len(rows) - 1
        for count in range(max_fittings + 1):
            work.pulse("fabrication_frontier_count_serialize")
            item = {"fittings": count, "status": "NO_PATH_AT_EXACT_COUNT", "cost": None, "path_states": [], "points_m": []}
            charge(256)
            if count in terminal:
                cost, current = terminal[count]
                path = []
                while current is not None:
                    work.tick()
                    charge(96)
                    path.append(current)
                    current = parents[current]
                path.reverse()
                points = _points(m, path, work)
                pi = _bounded(weights[0] * m["R"] * count / 2)
                charge(sum(len(x) for point in points for x in point) + len(str(cost)) + len(str(pi)) + 16 * len(points))
                item.update(status="OPTIMAL_PATH", cost=[str(cost), str(pi)], path_states=[list(s) for s in path], points_m=points)
            frontier.append(item)
        result.update(states=rows, frontier=frontier, producer_work=work.used)
        result["certificate_root"] = _hash(result, max_certificate_bytes, work)
        work.pulse("fabrication_frontier_complete")
        return result
    except graph._Exhausted as exc:
        if work.callback_error is exc:
            raise
        return _unknown(str(exc), work, m)


def verify_fabrication_frontier(problem, objective, max_fittings, certificate, *, max_states=24000, max_work=1000000,
                                max_certificate_bytes=MAX_CERTIFICATE_BYTES, checkpoint=None):
    """Replay complete closure, grounded reachability, duals and exact-count paths."""
    work = graph._Work(max_work, checkpoint)
    m = None
    try:
        _budgets(max_fittings, max_states, max_certificate_bytes)
        m = graph._prepare(problem, max_states, work)
        normalized, weights = _objective(objective)
        if not isinstance(certificate, dict):
            raise ValueError("Frontier certificate object required")
        if certificate.get("status") == "UNKNOWN":
            return _unknown("NO_COMPLETE_FRONTIER_CERTIFICATE", work, m)
        base = _base(m, normalized, max_fittings)
        if set(certificate) != set(base) | {"states", "frontier", "producer_work", "certificate_root"}:
            raise ValueError("Complete frontier certificate schema required")
        if any(certificate[key] != value for key, value in base.items()):
            raise ValueError("Input, graph, objective, exact-count domain or scope differs")
        rows, frontier = certificate["states"], certificate["frontier"]
        if not isinstance(rows, list) or not rows or not isinstance(frontier, list) or len(frontier) != max_fittings + 1:
            raise ValueError("Complete state table and exact-count denominator required")
        if len(rows) > max_states:
            raise graph._Exhausted("CERTIFICATE_STATE_BUDGET")
        if type(certificate["producer_work"]) is not int or not 0 <= certificate["producer_work"] <= 10000000:
            raise ValueError("Invalid producer work metadata")
        if not isinstance(certificate["certificate_root"], str) or len(certificate["certificate_root"]) != 64:
            raise ValueError("Bounded certificate content root required")
        # Validate shallow bounded shapes and exact byte count BEFORE parsing
        # potentially large cost Fractions or allocating adjacency structures.
        for index, row in enumerate(rows):
            work.tick()
            if not isinstance(row, dict) or set(row) != {"state", "potential", "parent"}:
                raise ValueError("Complete product state, potential and parent required")
            _state(m, row["state"], max_fittings)
            _shape(row["potential"])
            if (index == 0 and row["parent"] is not None) or (index > 0 and (type(row["parent"]) is not int or not 0 <= row["parent"] < index)):
                raise ValueError("Source-grounded predecessor order required")
        for count, item in enumerate(frontier):
            work.tick()
            if not isinstance(item, dict) or set(item) != {"fittings", "status", "cost", "path_states", "points_m"}:
                raise ValueError("Complete exact-count disposition required")
            if type(item["fittings"]) is not int or item["fittings"] != count or item["status"] not in {"OPTIMAL_PATH", "NO_PATH_AT_EXACT_COUNT"}:
                raise ValueError("Every exact count must occur once in order")
            if not isinstance(item["path_states"], list) or not isinstance(item["points_m"], list):
                raise ValueError("Bounded realizing path lists required")
            if len(item["path_states"]) > max_states or len(item["points_m"]) > max_fittings + 2:
                raise graph._Exhausted("CERTIFICATE_PATH_BUDGET")
            if item["cost"] is not None:
                if not isinstance(item["cost"], list) or len(item["cost"]) != 2:
                    raise ValueError("Exact rational and pi cost coefficients required")
                for value in item["cost"]:
                    _shape(value)
            for state in item["path_states"]:
                work.tick()
                _state(m, state, max_fittings)
            for point in item["points_m"]:
                work.tick()
                if not isinstance(point, list) or len(point) != 3 or any(not isinstance(x, str) or len(x) > 2500 for x in point):
                    raise ValueError("Bounded normalized point strings required")
        if _hash({k: v for k, v in certificate.items() if k != "certificate_root"}, max_certificate_bytes, work) != certificate["certificate_root"]:
            raise ValueError("Certificate content root differs")
        states, potentials, indexes, children = [], [], {}, {}
        for index, row in enumerate(rows):
            work.tick()
            state, value = tuple(row["state"]), _rational_cost(row["potential"])
            if state in indexes or value < 0:
                raise ValueError("Unique states and nonnegative rational potentials required")
            states.append(state); potentials.append(value); indexes[state] = index
            if row["parent"] is not None:
                children.setdefault(row["parent"], set()).add(state)
        initial = (*m["initial"], 0)
        if states[0] != initial or potentials[0] != 0:
            raise ValueError("The exact source has zero potential and no predecessor")
        costs = []
        for item in frontier:
            costs.append(tuple(_rational_cost(x) for x in item["cost"]) if item["cost"] is not None else None)
        accepting, cache, transitions = set(), {}, 0
        for index, state in enumerate(states):
            work.pulse("fabrication_frontier_closure_verify")
            edges = dict(_checked_edges(m, weights, state, max_fittings, work, cache))
            transitions += len(edges)
            if not children.get(index, set()) <= edges.keys():
                raise ValueError("A claimed reachable state's predecessor edge does not exist")
            for target, edge in edges.items():
                if target not in indexes:
                    raise ValueError("Reachable-state closure omits an admitted successor")
                if potentials[indexes[target]] > _bounded(potentials[index] + edge):
                    raise ValueError("Rational edge potential inequality fails")
            if graph._goal(m, state[:6]):
                count = state[6]
                accepting.add(count)
                terminal = _terminal(m, weights[0], state)
                if costs[count] is None or costs[count][0] > _bounded(potentials[index] + terminal):
                    raise ValueError("Exact-count terminal potential inequality or final debt fails")
        for count, item in enumerate(frontier):
            work.pulse("fabrication_frontier_path_verify")
            cost = costs[count]
            if count not in accepting:
                if item["status"] != "NO_PATH_AT_EXACT_COUNT" or cost is not None or item["path_states"] or item["points_m"]:
                    raise ValueError("Unreachable count must have no path or optimum cost")
                continue
            if item["status"] != "OPTIMAL_PATH" or cost is None:
                raise ValueError("Reachable exact count requires a realizing optimum path")
            if cost[1] != _bounded(weights[0] * m["R"] * count / 2) or min(cost) < 0:
                raise ValueError("Wrong fixed-count pi coefficient or negative objective")
            path = [tuple(s) for s in item["path_states"]]
            if not path or path[0] != initial or path[-1][6] != count or not graph._goal(m, path[-1][:6]):
                raise ValueError("Path does not realize its exact count and accepting terminals")
            if any(state not in indexes for state in path):
                raise ValueError("Realizing path lies outside the checked reachable-state table")
            total = Q(0)
            for source, target in zip(path, path[1:]):
                work.tick()
                edges = dict(_checked_edges(m, weights, source, max_fittings, work, cache))
                transitions += len(edges)
                if target not in edges:
                    raise ValueError("Realizing path uses an inadmissible count/fabrication transition")
                total = _bounded(total + edges[target])
            total = _bounded(total + _terminal(m, weights[0], path[-1]))
            if total != cost[0] or item["points_m"] != _checked_points(m, path, work) or len(item["points_m"]) != count + 2:
                raise ValueError("Realizing exact cost, terminal debt, turn count or polyline differs")
        work.pulse("fabrication_frontier_verified")
        return {"status": "PASS", "scope": SCOPE, "proof_complete": True, "input_root": m["root"], "graph_root": m["graph_root"],
            "frontier_model_root": base["frontier_model_root"], "count_domain_root": base["count_domain_root"],
            "certificate_root": certificate["certificate_root"], "counts_checked": max_fittings + 1,
            "reachable_counts": sorted(accepting), "states_checked": len(states), "transitions_reconstructed": transitions,
            "work": work.used, "limitations": deepcopy(LIMITATIONS)}
    except graph._Exhausted as exc:
        if work.callback_error is exc:
            raise
        return _unknown(str(exc), work, m)
    except (ValueError, TypeError, KeyError, IndexError, OverflowError, ZeroDivisionError) as exc:
        if work.callback_error is exc:
            raise
        return {"status": "FAIL", "reason": str(exc), "scope": SCOPE}
