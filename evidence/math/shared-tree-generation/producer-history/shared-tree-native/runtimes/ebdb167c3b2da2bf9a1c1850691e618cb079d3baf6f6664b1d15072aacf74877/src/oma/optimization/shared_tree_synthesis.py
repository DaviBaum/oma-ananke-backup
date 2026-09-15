"""Exact finite 2/3-sink tee/connector catalogue synthesis (bounded RTR17/18).

This module proves cap/section correspondence and finite combinatorial ranking.
Caller-authored geometry/fabrication/loss roots are identities, not native proof.
No native objective bound, physical feasibility or continuous closure is implied.
"""
from __future__ import annotations

from fractions import Fraction as Q
from functools import cmp_to_key
import hashlib
import itertools
import json
import re

MODEL_SCHEMA = "oma.shared-tree-catalogue/1"
CERTIFICATE_SCHEMA = "oma.shared-tree-synthesis-certificate/1"
SCOPE = "EXACT_CAP_SECTION_TOPOLOGY_AND_NOMINAL_RANK_WITHIN_COMPLETE_FROZEN_FINITE_CATALOGUE"
LIMITATIONS = [
    "Geometry, fabrication and loss roots bind identities; their physical truth is external.",
    "Nominal catalogue cost is not an independently measured native objective or lower bound.",
    "Every proposed complete tree still requires current native geometry and applicable service checks.",
    "No physical infeasibility, unrestricted connector/placement completeness or continuous optimum.",
]
_ID = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}\Z")
_ROOT = re.compile(r"[0-9a-f]{64}\Z")
_RAT = re.compile(r"-?[0-9]+(?:/[1-9][0-9]*)?\Z")


class _Exhausted(Exception):
    pass


class _Caller(BaseException):
    def __init__(self, error):
        self.error = error


class _Control:
    def __init__(self, max_work, checkpoint):
        self.limit, self.used, self.checkpoint, self.since = max_work, 0, checkpoint, 0

    def pulse(self, stage):
        if self.checkpoint is not None:
            try:
                self.checkpoint(stage)
            except BaseException as error:
                raise _Caller(error) from error

    def tick(self, amount=1, *, callbacks=True):
        self.used += amount
        if self.used > self.limit:
            raise _Exhausted("WORK_BUDGET")
        self.since += amount
        if callbacks and self.since >= 128:
            self.since = 0
            self.pulse("shared_tree_work")


def _budgets(max_tee_instances, max_connectors, max_assignments, max_results,
             max_work, max_bytes, max_rational_bits, max_pi_terms):
    values = dict(max_tee_instances=max_tee_instances, max_connectors=max_connectors,
                  max_assignments=max_assignments, max_results=max_results,
                  max_work=max_work, max_bytes=max_bytes,
                  max_rational_bits=max_rational_bits, max_pi_terms=max_pi_terms)
    ranges = {"max_tee_instances": (1, 64), "max_connectors": (1, 4096),
              "max_assignments": (1, 100000), "max_results": (1, 256),
              "max_work": (1, 20000000), "max_bytes": (256, 67108864),
              "max_rational_bits": (16, 4096), "max_pi_terms": (1, 256)}
    for name, (lo, hi) in ranges.items():
        if type(values[name]) is not int or not lo <= values[name] <= hi:
            raise ValueError("Invalid " + name)
    return values


def _keys(value, keys):
    if type(value) is not dict or set(value) != set(keys):
        raise ValueError("Exact schema fields required: " + ",".join(sorted(keys)))


def _shape(problem, limits):
    _keys(problem, {"schema", "context_root", "source_roots", "cost_policy_root", "section",
                    "source", "sinks", "tee_instances", "connectors"})
    for key, limit, reason in (("tee_instances", limits["max_tee_instances"], "TEE_BUDGET"),
                               ("connectors", limits["max_connectors"], "CONNECTOR_BUDGET"),
                               ("sinks", 3, "SINK_DOMAIN")):
        if type(problem[key]) is not list:
            raise ValueError("Lists required for catalogue inventories")
        if len(problem[key]) > limit:
            raise _Exhausted(reason)
    if not 2 <= len(problem["sinks"]) <= 3:
        raise ValueError("Exactly two or three sinks required")


def _certificate_shape(certificate, limits):
    _keys(certificate, {"schema", "input_root", "problem_root", "scope", "limitations",
                        "max_results", "assignment_count", "assignments", "ranked_prefix",
                        "certificate_root"})
    for name, maximum in (("assignments", limits["max_assignments"]), ("ranked_prefix", 256)):
        if type(certificate[name]) is not list:
            raise ValueError("Complete certificate lists required")
        if len(certificate[name]) > maximum:
            raise _Exhausted("CERTIFICATE_ASSIGNMENT_BUDGET")


def _snapshot(value, control, max_bytes, *, callbacks=True):
    """Strict bounded JSON copy/hash. Byte accounting precedes output allocation."""
    consumed = 0

    def atom_bytes(v):
        return len(json.dumps(v, ensure_ascii=False, allow_nan=False,
                              separators=(",", ":")).encode("utf-8"))

    def take(n):
        nonlocal consumed
        consumed += n
        if consumed > max_bytes:
            raise _Exhausted("BYTE_BUDGET")

    def copy(v, depth):
        control.tick(callbacks=callbacks)
        if depth > 16:
            raise ValueError("JSON nesting limit")
        if type(v) is dict:
            if len(v) > 4096 or any(type(k) is not str or len(k) > 256 for k in v):
                raise ValueError("Bounded string-key dictionaries required")
            take(2 + max(0, len(v)-1))
            result = {}
            for key in sorted(v):
                take(atom_bytes(key) + 1)
                result[key] = copy(v[key], depth+1)
            return result
        if type(v) is list:
            if len(v) > 100000:
                raise _Exhausted("LIST_BUDGET")
            take(2 + max(0, len(v)-1))
            return [copy(x, depth+1) for x in v]
        if type(v) is str:
            if len(v) > 4096:
                raise _Exhausted("STRING_BUDGET")
        elif type(v) is int:
            if v.bit_length() > 64:
                raise ValueError("Only bounded schema integers accepted; rationals must be strings")
        elif v is not None and type(v) is not bool:
            raise ValueError("Strict JSON types required; floats and custom objects are unsupported")
        take(atom_bytes(v))
        return v

    result = copy(value, 0)
    hasher = hashlib.sha256()
    encoder = json.JSONEncoder(sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    size = 0
    for chunk in encoder.iterencode(result):
        control.tick(callbacks=callbacks)
        data = chunk.encode("utf-8")
        size += len(data)
        if size > max_bytes:
            raise _Exhausted("BYTE_BUDGET")
        hasher.update(data)
    if size != consumed:
        raise ValueError("Canonical JSON size mismatch")
    return result, hasher.hexdigest()


def _hash(value, control, limits, *, callbacks=True):
    return _snapshot(value, control, limits["max_bytes"], callbacks=callbacks)[1]


def _id(value):
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise ValueError("Bounded ASCII identifier required")
    return value


def _root(value):
    if type(value) is not str or _ROOT.fullmatch(value) is None:
        raise ValueError("Canonical SHA256 identity required")
    return value


def _checked_q(value, limits):
    if max(value.numerator.bit_length(), value.denominator.bit_length()) > limits["max_rational_bits"]:
        raise _Exhausted("RATIONAL_BIT_BUDGET")
    return value


def _q(value, limits):
    if type(value) is not str or _RAT.fullmatch(value) is None:
        raise ValueError("Exact rational strings required")
    digits = (limits["max_rational_bits"] * 30103) // 100000 + 2
    if any(len(x.lstrip("-")) > digits for x in value.split("/")):
        raise _Exhausted("RATIONAL_BIT_BUDGET")
    return _checked_q(Q(value), limits)


def _vector(value, limits):
    if type(value) is not list or len(value) != 3:
        raise ValueError("Three exact coordinates required")
    return tuple(_q(x, limits) for x in value)


def _axis(value):
    if (type(value) is not list or len(value) != 3 or any(type(x) is not int for x in value)
            or sum(abs(x) for x in value) != 1):
        raise ValueError("Signed coordinate unit direction required")
    return tuple(value)


def _section(value, limits):
    _keys(value, {"diameter_m", "insulation_m"})
    diameter, insulation = (_q(value[k], limits) for k in ("diameter_m", "insulation_m"))
    if diameter <= 0 or insulation < 0:
        raise ValueError("Positive diameter and nonnegative insulation required")
    return {"diameter_m": str(diameter), "insulation_m": str(insulation)}


def _cap(value, limits):
    _keys(value, {"position_m", "flow_direction"})
    return {"position_m": list(map(str, _vector(value["position_m"], limits))),
            "flow_direction": list(_axis(value["flow_direction"]))}


def _endpoint(value):
    _keys(value, {"node", "port"})
    node = _id(value["node"])
    if type(value["port"]) is not str or value["port"] not in {"a", "b", "branch", "in", "out"}:
        raise ValueError("Unknown physical cap slot")
    return node, value["port"]


def _cost(value, limits):
    if type(value) is not list or len(value) != 2:
        raise ValueError("Nominal cost must be [rational, pi coefficient]")
    result = tuple(_q(x, limits) for x in value)
    if min(result) < 0:
        raise ValueError("Nonnegative nominal cost coefficients required")
    return result


def _normalize(raw, control, limits):
    # Recheck captured shape: callbacks may have changed caller input before copying.
    _shape(raw, limits)
    if raw["schema"] != MODEL_SCHEMA:
        raise ValueError("Unsupported catalogue schema")
    roots = raw["source_roots"]
    if type(roots) is not dict or not 1 <= len(roots) <= 64:
        raise ValueError("Nonempty bounded source identity map required")
    roots = {_id(k): _root(v) for k, v in sorted(roots.items())}
    section = _section(raw["section"], limits)
    _keys(raw["source"], {"id", "cap"})
    source = {"id": _id(raw["source"]["id"]), "cap": _cap(raw["source"]["cap"], limits)}
    nodes = {source["id"]: "source"}
    caps = {(source["id"], "out"): source["cap"]}
    sinks, demands = [], set()
    for item in raw["sinks"]:
        control.tick()
        _keys(item, {"id", "demand_id", "cap"})
        name, demand = _id(item["id"]), _id(item["demand_id"])
        if name in nodes or demand in demands:
            raise ValueError("Unique terminal and demand identities required")
        nodes[name] = "sink"
        demands.add(demand)
        cap = _cap(item["cap"], limits)
        sinks.append({"id": name, "demand_id": demand, "cap": cap})
        caps[name, "in"] = cap
    tees, tee_costs = [], {}
    radius = _checked_q(Q(section["diameter_m"])/2 + Q(section["insulation_m"]), limits)
    for item in raw["tee_instances"]:
        control.tick()
        _keys(item, {"id", "catalogue_root", "loss_contract_root", "center_m", "axis_x", "axis_y",
                     "trunk_takeout_m", "branch_takeout_m", "nominal_cost"})
        name = _id(item["id"])
        if name in nodes:
            raise ValueError("Globally unique physical node identities required")
        center = _vector(item["center_m"], limits)
        x, y = _axis(item["axis_x"]), _axis(item["axis_y"])
        if sum(a*b for a, b in zip(x, y)) != 0:
            raise ValueError("Orthogonal tee axes required")
        trunk, branch = _q(item["trunk_takeout_m"], limits), _q(item["branch_takeout_m"], limits)
        if min(trunk, branch) <= radius:
            raise ValueError("Tee takeouts must exceed full nominal outer radius")
        cost = _cost(item["nominal_cost"], limits)
        for port, axis, offset in (("a", x, -trunk), ("b", x, trunk), ("branch", y, branch)):
            caps[name, port] = {"position_m": [str(_checked_q(c+offset*d, limits)) for c, d in zip(center, axis)],
                                "flow_direction": list(axis)}
        nodes[name] = "tee"
        tee_costs[name] = cost
        tees.append({"id": name, "catalogue_root": _root(item["catalogue_root"]),
                     "loss_contract_root": _root(item["loss_contract_root"]),
                     "center_m": list(map(str, center)), "axis_x": list(x), "axis_y": list(y),
                     "trunk_takeout_m": str(trunk), "branch_takeout_m": str(branch),
                     "nominal_cost": list(map(str, cost))})
    connectors, by_id, pairs, outgoing = [], {}, {}, {}
    for item in raw["connectors"]:
        control.tick()
        _keys(item, {"id", "from", "to", "start_cap", "end_cap", "section",
                     "geometry_root", "fabrication_root", "nominal_cost"})
        name, start, end = _id(item["id"]), _endpoint(item["from"]), _endpoint(item["to"])
        if name in by_id:
            raise ValueError("Unique connector identities required")
        if start not in caps or end not in caps or start[0] == end[0]:
            raise ValueError("Unknown or self-connected cap")
        if not ((nodes[start[0]] == "source" and start[1] == "out" and nodes[end[0]] == "tee" and end[1] == "a")
                or (nodes[start[0]] == "tee" and start[1] in {"b", "branch"}
                    and ((nodes[end[0]] == "tee" and end[1] == "a")
                         or (nodes[end[0]] == "sink" and end[1] == "in")))):
            raise ValueError("Connector must follow a supported source/tee/sink direction")
        if _cap(item["start_cap"], limits) != caps[start] or _cap(item["end_cap"], limits) != caps[end]:
            raise ValueError("Exact connector cap/direction correspondence failed")
        if _section(item["section"], limits) != section:
            raise ValueError("Exact connector section correspondence failed")
        cost = _cost(item["nominal_cost"], limits)
        record = {"id": name, "from": {"node": start[0], "port": start[1]},
                  "to": {"node": end[0], "port": end[1]}, "start_cap": caps[start], "end_cap": caps[end],
                  "section": section, "geometry_root": _root(item["geometry_root"]),
                  "fabrication_root": _root(item["fabrication_root"]), "nominal_cost": list(map(str, cost))}
        connectors.append(record)
        by_id[name] = (start, end, cost, record)
        pairs.setdefault((start, end), []).append(name)
        outgoing.setdefault(start, []).append(name)
    normalized = {"schema": MODEL_SCHEMA, "context_root": _root(raw["context_root"]),
                  "source_roots": roots, "cost_policy_root": _root(raw["cost_policy_root"]),
                  "section": section, "source": source, "sinks": sorted(sinks, key=lambda x: x["id"]),
                  "tee_instances": sorted(tees, key=lambda x: x["id"]),
                  "connectors": sorted(connectors, key=lambda x: x["id"])}
    for values in itertools.chain(pairs.values(), outgoing.values()):
        values.sort()
    return {"normalized": normalized, "root": _hash(normalized, control, limits), "source": source["id"],
            "sinks": {x["id"]: x for x in sinks}, "nodes": nodes, "tee_costs": tee_costs,
            "by_id": by_id, "pairs": pairs, "outgoing": outgoing}


def _sum_cost(m, tee_ids, connector_ids, limits):
    a, b = Q(0), Q(0)
    for x, y in itertools.chain((m["tee_costs"][t] for t in tee_ids),
                                (m["by_id"][c][2] for c in connector_ids)):
        a, b = _checked_q(a+x, limits), _checked_q(b+y, limits)
    return a, b


def _row(m, tee_ids, connector_ids, control, limits):
    body = {"tee_ids": sorted(tee_ids), "connector_ids": sorted(connector_ids),
            "nominal_cost": list(map(str, _sum_cost(m, tee_ids, connector_ids, limits)))}
    return {**body, "assignment_root": _hash({"problem_root": m["root"], **body}, control, limits)}


def _producer_assignments(m, control, limits):
    sinks, tees = sorted(m["sinks"]), sorted(m["tee_costs"])
    rows = []
    templates = 0

    def emit(selected, edges):
        nonlocal templates
        templates += 1
        control.tick()
        choices = [m["pairs"].get(edge, ()) for edge in edges]
        if any(not values for values in choices):
            return
        count = 1
        for values in choices:
            count *= len(values)
            if count + len(rows) > limits["max_assignments"]:
                raise _Exhausted("ASSIGNMENT_BUDGET")
        for selected_connectors in itertools.product(*choices):
            control.tick()
            rows.append(_row(m, selected, selected_connectors, control, limits))

    if len(sinks) == 2:
        for root in tees:
            for left, right in itertools.permutations(sinks):
                emit((root,), [((m["source"], "out"), (root, "a")),
                               ((root, "b"), (left, "in")), ((root, "branch"), (right, "in"))])
    else:
        for root, child in itertools.permutations(tees, 2):
            for child_port in ("b", "branch"):
                leaf_port = "branch" if child_port == "b" else "b"
                for leaf, left, right in itertools.permutations(sinks):
                    emit((root, child), [((m["source"], "out"), (root, "a")),
                                        ((root, child_port), (child, "a")),
                                        ((root, leaf_port), (leaf, "in")),
                                        ((child, "b"), (left, "in")),
                                        ((child, "branch"), (right, "in"))])
    rows.sort(key=lambda row: tuple(row["connector_ids"]))
    return rows, templates


def _checked_assignments(m, control, limits):
    """Independent rooted open-slot expansion; does not use producer templates."""
    rows, visited = [], 0
    target_tees = len(m["sinks"])-1

    def walk(frontier, used_tees, used_sinks, chosen):
        nonlocal visited
        control.tick()
        visited += 1
        if not frontier:
            if len(used_tees) == target_tees and used_sinks == set(m["sinks"]):
                if len(rows) >= limits["max_assignments"]:
                    raise _Exhausted("ASSIGNMENT_BUDGET")
                rows.append(_row(m, used_tees, chosen, control, limits))
            return
        current, rest = frontier[0], frontier[1:]
        for identity in m["outgoing"].get(current, ()):
            control.tick()
            _, target, _, _ = m["by_id"][identity]
            node = target[0]
            if m["nodes"][node] == "sink":
                if node in used_sinks:
                    continue
                walk(rest, used_tees, used_sinks | {node}, chosen+(identity,))
            else:
                if node in used_tees or len(used_tees) >= target_tees:
                    continue
                walk(rest+((node, "b"), (node, "branch")), used_tees | {node}, used_sinks,
                     chosen+(identity,))

    walk(((m["source"], "out"),), set(), set(), ())
    rows.sort(key=lambda row: tuple(row["connector_ids"]))
    return rows, visited


def _pi_producer(n, control, limits):
    bounds = []
    for d in (5, 239):
        term, total = Q(1, d), Q(0)
        for k in range(n):
            control.tick()
            total = _checked_q(total + term/(2*k+1), limits)
            term = _checked_q(-term/(d*d), limits)
        adjacent = _checked_q(total + term/(2*n+1), limits)
        bounds.append((min(total, adjacent), max(total, adjacent)))
    return tuple(_checked_q(x, limits) for x in (16*bounds[0][0]-4*bounds[1][1],
                                                 16*bounds[0][1]-4*bounds[1][0]))


def _pi_checker(n, control, limits):
    boxes = []
    for d in (5, 239):
        total = Q(0)
        for k in range(n):
            control.tick()
            total = _checked_q(total + Q((-1)**k, (2*k+1)*d**(2*k+1)), limits)
        residual = _checked_q(Q(1, (2*n+1)*d**(2*n+1)), limits)
        boxes.append((total, total+residual) if n % 2 == 0 else (total-residual, total))
    return tuple(_checked_q(x, limits) for x in (16*boxes[0][0]-4*boxes[1][1],
                                                 16*boxes[0][1]-4*boxes[1][0]))


class _Compare:
    def __init__(self, control, limits, checker):
        self.control, self.limits, self.box, self.terms = control, limits, None, 0
        self.pi = _pi_checker if checker else _pi_producer

    def __call__(self, row1, row2):
        self.control.tick()
        a, b = (Q(x)-Q(y) for x, y in zip(row1["nominal_cost"], row2["nominal_cost"]))
        _checked_q(a, self.limits)
        _checked_q(b, self.limits)
        if not a and not b:
            x, y = tuple(row1["connector_ids"]), tuple(row2["connector_ids"])
            return (x > y)-(x < y)
        if min(a, b) >= 0:
            return 1
        if max(a, b) <= 0:
            return -1
        while True:
            if self.box is not None:
                lo, hi = self.box
                lower, upper = (a+b*lo, a+b*hi) if b > 0 else (a+b*hi, a+b*lo)
                _checked_q(lower, self.limits)
                _checked_q(upper, self.limits)
                if lower > 0:
                    return 1
                if upper < 0:
                    return -1
            if self.terms >= self.limits["max_pi_terms"]:
                raise _Exhausted("PI_COMPARISON_PRECISION_BUDGET")
            self.terms = min(self.limits["max_pi_terms"], max(1, self.terms*2))
            self.box = self.pi(self.terms, self.control, self.limits)


def _proposal(m, row):
    incoming = {m["by_id"][identity][1][0]: identity for identity in row["connector_ids"]}
    sinks = []
    for name, item in sorted(m["sinks"].items()):
        path, node = [], name
        while node != m["source"]:
            identity = incoming[node]
            path.append(identity)
            node = m["by_id"][identity][0][0]
        sinks.append({"id": name, "demand_id": item["demand_id"], "endpoint": {"node": name, "port": "in"},
                      "connector_path": list(reversed(path))})
    return {**row, "source": {"node": m["source"], "port": "out"}, "sinks": sinks,
            "connections": [{"connector_id": name, "from": m["by_id"][name][3]["from"],
                             "to": m["by_id"][name][3]["to"]} for name in row["connector_ids"]]}


def _final_inputs(problem, raw_root, certificate, certificate_raw_root, control, limits):
    # No caller callback after this point. Check current original input and supplied proof bytes.
    _shape(problem, limits)
    if _hash(problem, control, limits, callbacks=False) != raw_root:
        raise ValueError("Caller catalogue mutated during computation")
    if certificate is not None:
        _certificate_shape(certificate, limits)
        if _hash(certificate, control, limits, callbacks=False) != certificate_raw_root:
            raise ValueError("Caller certificate mutated during verification")


def _failure(status, error, control):
    return {"status": status, "reason": str(error), "proof_complete": False,
            "proposals": [], "scope": SCOPE, "work": control.used if control else 0}


def compile_shared_tree_catalogue(problem, *, max_tee_instances=16, max_connectors=256,
        max_assignments=100000, max_results=32, max_work=2000000, max_bytes=16777216,
        max_rational_bits=4096, max_pi_terms=128, checkpoint=None):
    control = None
    try:
        limits = _budgets(max_tee_instances, max_connectors, max_assignments, max_results,
                          max_work, max_bytes, max_rational_bits, max_pi_terms)
        control = _Control(max_work, checkpoint)
        _shape(problem, limits)
        control.pulse("shared_tree_input")
        raw, input_root = _snapshot(problem, control, max_bytes)
        m = _normalize(raw, control, limits)
        rows, templates = _producer_assignments(m, control, limits)
        comparison = _Compare(control, limits, False)
        ranked = sorted(rows, key=cmp_to_key(comparison))[:max_results]
        certificate = {"schema": CERTIFICATE_SCHEMA, "input_root": input_root, "problem_root": m["root"],
                       "scope": SCOPE, "limitations": list(LIMITATIONS), "max_results": max_results,
                       "assignment_count": len(rows), "assignments": rows,
                       "ranked_prefix": [row["assignment_root"] for row in ranked]}
        certificate["certificate_root"] = _hash(certificate, control, limits)
        # The advertised certificate byte limit includes its own digest field.
        _hash(certificate, control, limits)
        proposals = [_proposal(m, row) for row in ranked]
        control.pulse("shared_tree_producer_complete")
        _final_inputs(problem, input_root, None, None, control, limits)
        return {"status": "CERTIFIED", "proof_complete": True, "certificate": certificate,
                "certificate_root": certificate["certificate_root"], "input_root": input_root,
                "problem_root": m["root"], "proposals": proposals, "scope": SCOPE,
                "counts": {"tee_instances": len(m["tee_costs"]), "connectors": len(m["by_id"]),
                           "topology_templates": templates, "complete_assignments": len(rows),
                           "returned_proposals": len(proposals)}, "work": control.used}
    except _Caller as error:
        raise error.error
    except _Exhausted as error:
        return _failure("UNKNOWN", error, control)
    except (ValueError, TypeError, KeyError, RuntimeError, RecursionError, OverflowError) as error:
        return _failure("INVALID_INPUT", error, control)


def verify_shared_tree_catalogue(problem, certificate, *, max_tee_instances=16, max_connectors=256,
        max_assignments=100000, max_results=32, max_work=2000000, max_bytes=16777216,
        max_rational_bits=4096, max_pi_terms=128, checkpoint=None):
    control = None
    try:
        limits = _budgets(max_tee_instances, max_connectors, max_assignments, max_results,
                          max_work, max_bytes, max_rational_bits, max_pi_terms)
        control = _Control(max_work, checkpoint)
        _shape(problem, limits)
        _certificate_shape(certificate, limits)
        control.pulse("shared_tree_input")
        raw, input_root = _snapshot(problem, control, max_bytes)
        proof, proof_raw_root = _snapshot(certificate, control, max_bytes)
        _certificate_shape(proof, limits)
        m = _normalize(raw, control, limits)
        root = proof.pop("certificate_root")
        if _root(root) != _hash(proof, control, limits):
            raise ValueError("Certificate digest mismatch")
        if (proof["schema"] != CERTIFICATE_SCHEMA or proof["input_root"] != input_root
                or proof["problem_root"] != m["root"] or proof["scope"] != SCOPE
                or proof["limitations"] != LIMITATIONS or type(proof["max_results"]) is not int
                or proof["max_results"] != max_results or type(proof["assignment_count"]) is not int):
            raise ValueError("Exact input/header/scope/output-limit binding failed")
        expected, visited = _checked_assignments(m, control, limits)
        # Complete equality covers omitted/duplicate/forged rows, costs, roots and ordering.
        if proof["assignment_count"] != len(expected) or proof["assignments"] != expected:
            raise ValueError("Complete assignment incidence/cost/coverage ledger mismatch")
        comparison = _Compare(control, limits, True)
        ranked = sorted(expected, key=cmp_to_key(comparison))[:max_results]
        if proof["ranked_prefix"] != [row["assignment_root"] for row in ranked]:
            raise ValueError("Ranked finite prefix mismatch")
        proposals = [_proposal(m, row) for row in ranked]
        control.pulse("shared_tree_verifier_complete")
        _final_inputs(problem, input_root, certificate, proof_raw_root, control, limits)
        return {"status": "PASS", "proof_complete": True, "certificate_root": root,
                "input_root": input_root, "problem_root": m["root"], "scope": SCOPE,
                "proposals": proposals, "counts": {"tee_instances": len(m["tee_costs"]),
                    "connectors": len(m["by_id"]), "complete_assignments": len(expected),
                    "returned_proposals": len(proposals), "checked_partial_incidence_states": visited},
                "work": control.used}
    except _Caller as error:
        raise error.error
    except _Exhausted as error:
        return _failure("UNKNOWN", error, control)
    except (ValueError, TypeError, KeyError, RuntimeError, RecursionError, OverflowError) as error:
        return _failure("FAIL", error, control)
