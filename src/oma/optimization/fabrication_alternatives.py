"""Bounded exact-count residual graph frontier after whole-word exclusions.

The exclusions enumerate proposals, not infeasible geometry. Original RTR15,
RTR22, RTR26/27 support the bounded lift, independent checking and domain scope;
this finite prefix-trie construction is a new specialization of those duties.
"""
from copy import deepcopy
from fractions import Fraction as Q
import hashlib
import heapq
import json
from math import isfinite

from oma.store import digest
from . import fabrication_search as graph
from . import fabrication_frontier as count_graph

SCHEMA = "oma.fabrication-residual-frontier/1"
SCOPE = "EXACT_COUNT_NOMINAL_OPTIMUM_IN_DECLARED_RESIDUAL_GRAPH_WORD_LANGUAGE"
RULE = "WHOLE_WORD_TERMINAL_EXCLUSION_TRIE_EXACT_COUNT_V1"
EXCLUSION_POLICY = "ALREADY_GENERATED_COMPLETE_GRAPH_WORDS_ONLY"
SAFE = -1
LIMITATIONS = {
    **count_graph.LIMITATIONS,
    "original_graph_infeasibility_claim": False,
    "excluded_words_physically_infeasible": False,
    "prefix_or_edge_exclusions": False,
    "original_count_optimality": False,
    "sequential_rank_without_independent_round_chain": False,
    "physical_unique_path_completeness": False,
}


def _budgets(k, states, words, steps, input_bytes, certificate_bytes):
    count_graph._budgets(k, states, certificate_bytes)
    for name, value, lower, upper in (
        ("max_excluded_words", words, 0, 128),
        ("max_excluded_steps", steps, 0, 65536),
        ("max_input_bytes", input_bytes, 256, 8388608),
    ):
        if type(value) is not int or not lower <= value <= upper:
            raise ValueError("Invalid " + name)


def _word_shape(words, maximum_words, maximum_steps, work):
    if type(words) is not list:
        raise ValueError("Explicit list of complete seven-coordinate graph words required")
    if len(words) > maximum_words:
        raise graph._Exhausted("EXCLUSION_WORD_BUDGET")
    steps = 0
    for word in words:
        work.tick()
        if type(word) is not list or len(word) < 2:
            raise ValueError("Excluded words require source, transitions and an accepting terminal")
        steps += len(word) - 1
        if steps > maximum_steps:
            raise graph._Exhausted("EXCLUSION_STEP_BUDGET")
        for state in word:
            work.tick()
            if type(state) is not list or len(state) != 7 or any(type(x) is not int for x in state):
                raise ValueError("Excluded word symbols must be seven strict integers")
            if any(abs(x).bit_length() > 32 for x in state):
                raise ValueError("Excluded state integer exceeds structural domain")
    return steps


def _snapshot(value, limit, work, stage, *, retain=True):
    """Bounded JSON snapshot before arithmetic; exact bytes bind caller mutation."""
    stack = [(value, 0)]
    while stack:
        item, depth = stack.pop()
        work.tick()
        if depth > 24:
            raise graph._Exhausted("ENCODING_STRUCTURE_BUDGET")
        if type(item) is str:
            if len(item) > 10000:
                raise graph._Exhausted("ENCODING_TOKEN_BUDGET")
        elif type(item) is int:
            if item.bit_length() > 4096:
                raise graph._Exhausted("ENCODING_INTEGER_BUDGET")
        elif type(item) is float:
            if not isfinite(item):
                raise ValueError("Nonfinite JSON input")
        elif item is None or type(item) is bool:
            pass
        elif type(item) in (list, tuple, dict):
            if len(item) > 100000:
                raise graph._Exhausted("ENCODING_CONTAINER_BUDGET")
            if type(item) is dict:
                if any(type(k) is not str for k in item):
                    raise ValueError("JSON object keys must be strings")
                stack.extend((k, depth + 1) for k in item)
                stack.extend((child, depth + 1) for child in item.values())
            else:
                stack.extend((child, depth + 1) for child in item)
        else:
            raise ValueError("Only bounded JSON-compatible values are supported")
    encoder = json.JSONEncoder(sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    hasher, size, chunks = hashlib.sha256(), 0, []
    work.pulse(stage + "_start")
    for index, chunk in enumerate(encoder.iterencode(value)):
        work.tick()
        if index % 256 == 0:
            work.pulse(stage + "_stream")
        data = chunk.encode("utf8")
        size += len(data)
        if size > limit:
            raise graph._Exhausted("INPUT_BYTE_BUDGET" if stage.startswith("residual_input") else "CERTIFICATE_BYTE_BUDGET")
        hasher.update(data)
        if retain:
            chunks.append(data)
    work.pulse(stage + "_complete")
    return hasher.hexdigest(), json.loads(b"".join(chunks)) if retain else None


def _inputs(problem, objective, k, words):
    return {"problem": problem, "objective": objective, "max_fittings": k, "excluded_words": words}


def _prepare(inputs, max_states, work):
    m = graph._prepare(inputs["problem"], max_states, work)
    objective, weights = count_graph._objective(inputs["objective"])
    maximum = inputs["max_fittings"]
    initial = (*m["initial"], 0)
    word_bound = (maximum + 1) * (max(map(len, m["axes"])) - 1)
    words, seen, cache = [], set(), {}
    for supplied in inputs["excluded_words"]:
        work.pulse("residual_exclusion_validate")
        word = tuple(count_graph._state(m, state, maximum) for state in supplied)
        if len(word) - 1 > word_bound:
            raise ValueError("Excluded word exceeds proved monotone-run length bound")
        if word[0] != initial or not graph._goal(m, word[-1][:6]):
            raise ValueError("Excluded word must start at the source and terminate at a valid goal")
        if word in seen:
            raise ValueError("Duplicate excluded complete word")
        for source, target in zip(word, word[1:]):
            work.tick()
            if target not in dict(count_graph._checked_edges(m, weights, source, maximum, work, cache)):
                raise ValueError("Excluded word has an inadmissible fabrication/count transition")
        seen.add(word); words.append(word)
    words.sort()
    # Store each prefix once as parent+symbol, never a full prefix tuple.
    # This is linear in total excluded steps, including very long words.
    nodes = [{"parent": None, "symbol": None, "terminal": False}]
    edges, children = {}, {0: []}
    for word in words:
        parent = 0
        for symbol in word[1:]:
            work.tick()
            key = (parent, symbol)
            node = edges.get(key)
            if node is None:
                node = len(nodes)
                nodes.append({"parent": parent, "symbol": list(symbol), "terminal": False})
                edges[key] = node
                children[parent].append(node)
                children[node] = []
            parent = node
        nodes[parent]["terminal"] = True
    trie = {"nodes": nodes, "edges": edges, "children": children}
    normalized_words = [[list(s) for s in word] for word in words]
    exclusion_root = digest({"graph_root": m["graph_root"], "policy": EXCLUSION_POLICY, "words": normalized_words})
    automaton_root = digest({"rule": RULE, "exclusion_root": exclusion_root, "nodes": nodes, "diverged_state": SAFE})
    count_domain = {"minimum": 0, "maximum": maximum, "meaning": "EXACT_NUMBER_OF_NINETY_DEGREE_TURNS"}
    model = {"graph_root": m["graph_root"], "objective": objective, "count_domain": count_domain,
             "exclusion_root": exclusion_root, "automaton_root": automaton_root, "rule": RULE}
    base = {"schema": SCHEMA, "status": "CERTIFIED", "scope": SCOPE, "rule": RULE,
        "input_root": m["root"], "graph_root": m["graph_root"], "objective": objective,
        "objective_root": digest(objective), "count_domain": count_domain, "count_domain_root": digest(count_domain),
        "exclusion_policy": EXCLUSION_POLICY, "exclusion_root": exclusion_root, "automaton_root": automaton_root,
        "residual_model_root": digest(model), "excluded_word_count": len(words),
        "excluded_step_count": sum(len(w)-1 for w in words), "automaton_nodes": len(nodes),
        "finite_word_step_bound": word_bound, "limitations": deepcopy(LIMITATIONS)}
    return m, weights, trie, base


def _state(m, trie, value, maximum):
    if type(value) is not list or len(value) != 8 or any(type(x) is not int for x in value):
        raise ValueError("Eight strict integer product-state coordinates required")
    base = count_graph._state(m, value[:7], maximum)
    node = value[7]
    if node != SAFE:
        if not 0 <= node < len(trie["nodes"]):
            raise ValueError("Unknown trie state")
        expected = tuple(trie["nodes"][node]["symbol"]) if node else (*m["initial"], 0)
        if base != expected:
            raise ValueError("Trie prefix does not reach the claimed graph/count state")
    return (*base, node)


def _producer_edges(m, weights, trie, state, maximum, work, cache):
    for target, cost in count_graph._producer_edges(m, weights, state[:7], maximum, work, cache):
        node = SAFE if state[7] == SAFE else trie["edges"].get((state[7], target), SAFE)
        yield (*target, node), cost


def _checked_trie_step(trie, current, target, work):
    if current == SAFE:
        return SAFE
    # Independent child-symbol scan, not the producer's edge lookup table.
    for child in trie["children"][current]:
        work.tick()
        if tuple(trie["nodes"][child]["symbol"]) == target:
            return child
    return SAFE


def _checked_edges(m, weights, trie, state, maximum, work, cache):
    for target, cost in count_graph._checked_edges(m, weights, state[:7], maximum, work, cache):
        node = _checked_trie_step(trie, state[7], target, work)
        yield (*target, node), cost


def _accept(m, trie, state):
    return graph._goal(m, state[:6]) and (state[7] == SAFE or not trie["nodes"][state[7]]["terminal"])


def _unknown(reason, work, m=None):
    return {"status": "UNKNOWN", "reason": reason, "scope": SCOPE, "proof_complete": False,
        "input_root": m["root"] if m else None, "work": work.used, "limitations": deepcopy(LIMITATIONS)}


def _final_guard(raw_inputs, input_hash, byte_limit, work, certificate=None, certificate_hash=None, certificate_limit=None):
    """No caller callbacks occur during the final bounded identity checks."""
    callback = work.callback
    work.callback = None
    try:
        if _snapshot(raw_inputs, byte_limit, work, "residual_input_final", retain=False)[0] != input_hash:
            raise ValueError("Caller input changed before final result")
        if certificate is not None and _snapshot(certificate, certificate_limit, work, "residual_certificate_final", retain=False)[0] != certificate_hash:
            raise ValueError("Caller certificate changed before final result")
    finally:
        work.callback = callback


def compile_fabrication_alternatives(problem, objective, max_fittings, excluded_words, *, max_states=24000,
        max_work=1000000, max_excluded_words=16, max_excluded_steps=8192,
        max_input_bytes=1048576, max_certificate_bytes=16777216, checkpoint=None):
    """Complete residual exact-count frontier, or UNKNOWN with no partial claims."""
    work = graph._Work(max_work, checkpoint)
    m = None
    try:
        _budgets(max_fittings, max_states, max_excluded_words, max_excluded_steps, max_input_bytes, max_certificate_bytes)
        _word_shape(excluded_words, max_excluded_words, max_excluded_steps, work)
        raw_inputs = _inputs(problem, objective, max_fittings, excluded_words)
        input_hash, inputs = _snapshot(raw_inputs, max_input_bytes, work, "residual_input")
        m, weights, trie, base = _prepare(inputs, max_states, work)
        initial = (*m["initial"], 0, 0)
        distances, parents, settled, cache = {initial: Q(0)}, {initial: None}, {}, {}
        queue, terminal = [(Q(0), initial)], {}
        while queue:
            work.pulse("residual_expand")
            cost, state = heapq.heappop(queue)
            if state in settled or distances[state] != cost:
                continue
            settled[state] = cost
            if _accept(m, trie, state):
                value = count_graph._bounded(cost + weights[0] * (graph._run_length(m, state[:6]) - state[5] * m["R"]))
                if state[6] not in terminal or value < terminal[state[6]][0]:
                    terminal[state[6]] = (value, state)
            # Even excluded/accepted terminal states retain all outgoing edges.
            for target, edge in _producer_edges(m, weights, trie, state, max_fittings, work, cache):
                candidate = count_graph._bounded(cost + edge)
                if target not in settled and (target not in distances or candidate < distances[target]):
                    if target not in distances and len(distances) >= max_states:
                        raise graph._Exhausted("PRODUCT_STATE_BUDGET")
                    distances[target], parents[target] = candidate, state
                    heapq.heappush(queue, (candidate, target))
        rows, indexes, frontier, allocated = [], {}, [], 4096
        for state, cost in settled.items():
            work.tick()
            if len(rows) % 128 == 0:
                work.pulse("residual_serialize")
            encoded = str(count_graph._bounded(cost))
            allocated += 208 + len(encoded)
            if allocated > max_certificate_bytes:
                raise graph._Exhausted("CERTIFICATE_BYTE_BUDGET")
            parent = parents[state]
            rows.append({"state": list(state), "potential": encoded, "parent": indexes[parent] if parent is not None else None})
            indexes[state] = len(rows) - 1
        for count in range(max_fittings + 1):
            work.pulse("residual_count_serialize")
            item = {"fittings": count, "status": "NO_PATH_IN_DECLARED_RESIDUAL_LANGUAGE_AT_EXACT_COUNT", "cost": None,
                    "path_states": [], "points_m": []}
            allocated += 256
            if count in terminal:
                cost, current = terminal[count]
                path = []
                while current is not None:
                    work.tick()
                    allocated += 112
                    if allocated > max_certificate_bytes:
                        raise graph._Exhausted("CERTIFICATE_BYTE_BUDGET")
                    path.append(current); current = parents[current]
                path.reverse()
                points = count_graph._points(m, [s[:7] for s in path], work)
                pi = count_graph._bounded(weights[0] * m["R"] * count / 2)
                item.update(status="RESIDUAL_OPTIMAL_PATH", cost=[str(cost), str(pi)], path_states=[list(s) for s in path], points_m=points)
            frontier.append(item)
        result = {**base, "states": rows, "frontier": frontier, "producer_work": work.used}
        result["certificate_root"] = _snapshot(result, max_certificate_bytes, work, "residual_certificate", retain=False)[0]
        work.pulse("residual_producer_complete")
        _final_guard(raw_inputs, input_hash, max_input_bytes, work)
        return result
    except graph._Exhausted as exc:
        if work.callback_error is exc:
            raise
        return _unknown(str(exc), work, m)
    except (ValueError, TypeError, KeyError, IndexError, OverflowError, RecursionError) as exc:
        if work.callback_error is exc:
            raise
        return {"status": "INVALID_INPUT", "reason": str(exc), "scope": SCOPE, "proof_complete": False}


def verify_fabrication_alternatives(problem, objective, max_fittings, excluded_words, certificate, *, max_states=24000,
        max_work=1000000, max_excluded_words=16, max_excluded_steps=8192,
        max_input_bytes=1048576, max_certificate_bytes=16777216, checkpoint=None):
    """Independent reachable closure, residual acceptance, dual and path replay."""
    work = graph._Work(max_work, checkpoint)
    m = None
    try:
        _budgets(max_fittings, max_states, max_excluded_words, max_excluded_steps, max_input_bytes, max_certificate_bytes)
        _word_shape(excluded_words, max_excluded_words, max_excluded_steps, work)
        raw_inputs = _inputs(problem, objective, max_fittings, excluded_words)
        input_hash, inputs = _snapshot(raw_inputs, max_input_bytes, work, "residual_input")
        m, weights, trie, base = _prepare(inputs, max_states, work)
        if type(certificate) is not dict:
            raise ValueError("Complete residual certificate object required")
        if certificate.get("status") == "UNKNOWN":
            return _unknown("NO_COMPLETE_RESIDUAL_CERTIFICATE", work, m)
        if set(certificate) != set(base) | {"states", "frontier", "producer_work", "certificate_root"}:
            raise ValueError("Complete residual certificate schema required")
        if type(certificate["states"]) is not list or len(certificate["states"]) > max_states:
            raise graph._Exhausted("CERTIFICATE_STATE_BUDGET")
        if type(certificate["frontier"]) is not list or len(certificate["frontier"]) != max_fittings + 1:
            raise ValueError("Complete exact-count denominator required")
        received_hash, proof = _snapshot(certificate, max_certificate_bytes, work, "residual_certificate")
        if any(proof[k] != v for k, v in base.items()):
            raise ValueError("Graph, objective, count, exclusion, automaton or scope differs")
        if type(proof["producer_work"]) is not int or not 0 <= proof["producer_work"] <= 10000000:
            raise ValueError("Invalid producer work metadata")
        expected_hash = _snapshot({k: v for k, v in proof.items() if k != "certificate_root"}, max_certificate_bytes, work,
                                  "residual_certificate_payload", retain=False)[0]
        if proof["certificate_root"] != expected_hash:
            raise ValueError("Certificate content root differs")
        states, potentials, indexes, children = [], [], {}, {}
        rows = proof["states"]
        if not rows:
            raise ValueError("Nonempty source-grounded state table required")
        for index, row in enumerate(rows):
            work.tick()
            if type(row) is not dict or set(row) != {"state", "potential", "parent"}:
                raise ValueError("Complete residual state row required")
            state = _state(m, trie, row["state"], max_fittings)
            value = count_graph._rational_cost(row["potential"])
            if state in indexes or value < 0:
                raise ValueError("Unique residual states and nonnegative potentials required")
            parent = row["parent"]
            if (index == 0 and parent is not None) or (index > 0 and (type(parent) is not int or not 0 <= parent < index)):
                raise ValueError("Strictly earlier source-grounded predecessor required")
            states.append(state); potentials.append(value); indexes[state] = index
            if parent is not None:
                children.setdefault(parent, set()).add(state)
        initial = (*m["initial"], 0, 0)
        if states[0] != initial or potentials[0] != 0:
            raise ValueError("Exact source with zero potential required")
        costs = []
        for count, item in enumerate(proof["frontier"]):
            work.tick()
            if type(item) is not dict or set(item) != {"fittings", "status", "cost", "path_states", "points_m"}:
                raise ValueError("Complete residual count entry required")
            if type(item["fittings"]) is not int or item["fittings"] != count:
                raise ValueError("Every exact count appears once in order")
            if item["status"] not in {"RESIDUAL_OPTIMAL_PATH", "NO_PATH_IN_DECLARED_RESIDUAL_LANGUAGE_AT_EXACT_COUNT"}:
                raise ValueError("Residual disposition required")
            if type(item["path_states"]) is not list or type(item["points_m"]) is not list:
                raise ValueError("Bounded residual realizing path required")
            if len(item["path_states"]) > base["finite_word_step_bound"] + 1 or len(item["points_m"]) > max_fittings + 2:
                raise graph._Exhausted("CERTIFICATE_PATH_BUDGET")
            if item["cost"] is None:
                costs.append(None)
            else:
                if type(item["cost"]) is not list or len(item["cost"]) != 2:
                    raise ValueError("Rational and fixed pi coefficients required")
                costs.append(tuple(count_graph._rational_cost(v) for v in item["cost"]))
        checked_forbidden_terminals = set()
        for word in inputs["excluded_words"]:
            node = 0
            for symbol in word[1:]:
                work.tick()
                node = _checked_trie_step(trie, node, tuple(symbol), work)
            if node == SAFE:
                raise ValueError("Reconstructed trie omits an excluded word")
            checked_forbidden_terminals.add(node)
        accepting, cache, transitions = set(), {}, 0
        for index, state in enumerate(states):
            work.pulse("residual_closure_verify")
            edges = dict(_checked_edges(m, weights, trie, state, max_fittings, work, cache))
            transitions += len(edges)
            if not children.get(index, set()) <= edges.keys():
                raise ValueError("Grounding predecessor transition does not exist")
            for target, cost in edges.items():
                if target not in indexes:
                    raise ValueError("Reachable residual closure omits an allowed successor")
                if potentials[indexes[target]] > count_graph._bounded(potentials[index] + cost):
                    raise ValueError("Rational product-edge potential inequality fails")
            # Reconstructed terminal eligibility differs from merely reaching a goal.
            eligible = graph._goal(m, state[:6])
            if state[7] in checked_forbidden_terminals:
                eligible = False
            if eligible:
                count = state[6]; accepting.add(count)
                terminal = count_graph._terminal(m, weights[0], state[:7])
                if costs[count] is None or costs[count][0] > count_graph._bounded(potentials[index] + terminal):
                    raise ValueError("Residual terminal inequality or terminal debt fails")
        for count, item in enumerate(proof["frontier"]):
            work.pulse("residual_path_verify")
            cost = costs[count]
            if count not in accepting:
                if item["status"] != "NO_PATH_IN_DECLARED_RESIDUAL_LANGUAGE_AT_EXACT_COUNT" or cost is not None or item["path_states"] or item["points_m"]:
                    raise ValueError("No residual terminal permits no realizing cost or path")
                continue
            if item["status"] != "RESIDUAL_OPTIMAL_PATH" or cost is None or min(cost) < 0:
                raise ValueError("Reachable residual count requires a realizing optimum")
            if cost[1] != count_graph._bounded(weights[0] * m["R"] * count / 2):
                raise ValueError("Wrong fixed exact-count pi coefficient")
            path = [_state(m, trie, s, max_fittings) for s in item["path_states"]]
            if not path or path[0] != initial or path[-1][6] != count or not graph._goal(m, path[-1][:6]):
                raise ValueError("Residual path has wrong source, count or goal")
            if any(s not in indexes for s in path):
                raise ValueError("Residual path is outside the verified state table")
            base_word = [list(s[:7]) for s in path]
            if base_word in inputs["excluded_words"]:
                raise ValueError("Realizing path is a forbidden complete graph word")
            total = Q(0)
            for source, target in zip(path, path[1:]):
                work.tick()
                edges = dict(_checked_edges(m, weights, trie, source, max_fittings, work, cache))
                transitions += len(edges)
                if target not in edges:
                    raise ValueError("Residual realizing path has an inadmissible transition")
                total = count_graph._bounded(total + edges[target])
            total = count_graph._bounded(total + count_graph._terminal(m, weights[0], path[-1][:7]))
            if total != cost[0] or item["points_m"] != count_graph._checked_points(m, [s[:7] for s in path], work) or len(item["points_m"]) != count + 2:
                raise ValueError("Residual exact cost, debt, count or contracted points differ")
        work.pulse("residual_verifier_complete")
        _final_guard(raw_inputs, input_hash, max_input_bytes, work, certificate, received_hash, max_certificate_bytes)
        return {"status": "PASS", "scope": SCOPE, "proof_complete": True,
            **{key: base[key] for key in ("input_root", "graph_root", "objective_root", "count_domain_root", "exclusion_root", "automaton_root", "residual_model_root")},
            "certificate_root": proof["certificate_root"], "counts_checked": max_fittings + 1,
            "reachable_counts": sorted(accepting), "states_checked": len(states), "transitions_reconstructed": transitions,
            "work": work.used, "limitations": deepcopy(LIMITATIONS)}
    except graph._Exhausted as exc:
        if work.callback_error is exc:
            raise
        return _unknown(str(exc), work, m)
    except (ValueError, TypeError, KeyError, IndexError, OverflowError, RecursionError, ZeroDivisionError) as exc:
        if work.callback_error is exc:
            raise
        return {"status": "FAIL", "reason": str(exc), "scope": SCOPE, "proof_complete": False}
