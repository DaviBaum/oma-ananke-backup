"""Exact comparison envelopes for bounded grounded passive pressure networks.

Original P6 PO1/PO2/PO7, P16069--16203, P16836--16853; RTR19/20.
The signed quadratic, ideal-junction model is explicit and is not the native
upstream-flow tee model. The verifier checks inequalities, never a solver run.
"""
from copy import deepcopy
from fractions import Fraction as Q
import hashlib
import json
from math import isqrt
import re

MODEL_SCHEMA = "oma.passive-quadratic-pressure-model/1"
CERTIFICATE_SCHEMA = "oma.passive-quadratic-pressure-envelope/1"
SCOPE = "UNIQUE_GROUNDED_PASSIVE_EQUILIBRIUM_ENCLOSURE_FOR_EVERY_PARAMETER_IN_DECLARED_BOX"
RULE = "GROUNDED_COMPARISON_SIGNED_QUADRATIC_V1"
MODEL_ASSUMPTIONS = {
    "parameter_domain": "CARTESIAN_INTERVAL_BOX",
    "head_quantity": "TOTAL_PRESSURE_PLUS_GRAVITATIONAL_POTENTIAL_PA",
    "edge_law": "HEAD_U_MINUS_HEAD_V=K*Q*ABS(Q)",
    "junction_law": "SINGLE_SCALAR_HEAD_AND_ZERO_INTERNAL_NET_INJECTION",
    "regime": "SIGNED_BIDIRECTIONAL_INCLUDING_ZERO",
    "units": {"head": "Pa", "flow": "m^3/s", "K": "Pa*s^2/m^6"},
    "physical_applicability": "DECLARED_BY_CALLER_NOT_PROVED_BY_KERNEL",
}
LIMITATIONS = {
    "native_geometry_or_interface_authority": False,
    "current_upstream_flow_tee_loss_applicability": False,
    "physical_model_truth_proved": False,
    "minimum_delivery_or_velocity_requirements_checked": False,
    "all_box_coordinates_simultaneously_feasible": False,
    "tight_solution_hull": False,
    "one_common_equilibrium_for_all_parameter_choices": False,
    "zero_resistance_or_ungrounded_components_supported": False,
    "parameter_correlation_retained_as_exact_relation": False,
}
_ROOT = re.compile(r"[0-9a-f]{64}\Z")
_RATIONAL = re.compile(r"[+-]?[0-9]+(?:/[0-9]+|\.[0-9]+)?\Z")


class _Invalid(ValueError):
    pass


class _Limit(RuntimeError):
    pass


class _RefinementLimit(RuntimeError):
    pass


class _Budget:
    def __init__(self, max_nodes, max_edges, max_work, max_rational_bits,
                 max_input_bytes, max_certificate_bytes, checkpoint):
        for name, value, lo, hi in (
            ("max_nodes", max_nodes, 1, 1024), ("max_edges", max_edges, 0, 2048),
            ("max_work", max_work, 1, 10_000_000),
            ("max_rational_bits", max_rational_bits, 32, 4096),
            ("max_input_bytes", max_input_bytes, 256, 8_388_608),
            ("max_certificate_bytes", max_certificate_bytes, 256, 33_554_432),
        ):
            if type(value) is not int or not lo <= value <= hi:
                raise _Invalid("Invalid " + name)
        if checkpoint is not None and not callable(checkpoint):
            raise _Invalid("checkpoint must be callable")
        self.nodes, self.edges, self.maximum = max_nodes, max_edges, max_work
        self.bits, self.input_bytes, self.certificate_bytes = max_rational_bits, max_input_bytes, max_certificate_bytes
        self.used, self.callback, self.external_error, self.refine_stop = 0, checkpoint, None, None

    def tick(self, stage="passive_arithmetic"):
        self.used += 1
        if self.callback is not None:
            try:
                self.callback(stage)
            except BaseException as exc:
                self.external_error = exc
                raise
        if self.used > self.maximum:
            raise _Limit("WORK_BUDGET")
        if self.refine_stop is not None and self.used > self.refine_stop:
            raise _RefinementLimit("REFINEMENT_WORK_BUDGET")

    def check(self, value):
        if max(abs(value.numerator).bit_length(), value.denominator.bit_length()) > self.bits:
            raise _Limit("RATIONAL_BIT_BUDGET")
        return value

    def add(self, a, b):
        self.tick()
        return self.check(a+b)

    def sub(self, a, b):
        self.tick()
        return self.check(a-b)

    def mul(self, a, b):
        self.tick()
        return self.check(a*b)

    def div(self, a, b):
        self.tick()
        if not b:
            raise _Invalid("Zero denominator")
        return self.check(a/b)


def _q(value, budget):
    budget.tick("passive_parse_rational")
    if type(value) is int:
        if value.bit_length() > budget.bits:
            raise _Limit("RATIONAL_BIT_BUDGET")
        return Q(value)
    if type(value) is not str:
        raise _Invalid("Exact rationals require integers or explicit rational strings")
    digits = budget.bits * 30103 // 100000 + 2
    if len(value) > 2*digits+4:
        raise _Limit("RATIONAL_TOKEN_BUDGET")
    if not _RATIONAL.fullmatch(value):
        raise _Invalid("Malformed rational token")
    parts = value.lstrip("+-").replace(".", "").split("/")
    if any(len(part) > digits for part in parts):
        raise _Limit("RATIONAL_TOKEN_BUDGET")
    try:
        return budget.check(Q(value))
    except (ValueError, ZeroDivisionError) as exc:
        raise _Invalid("Malformed rational or zero denominator") from exc


def _interval(value, budget):
    if type(value) is not dict or set(value) != {"lower", "upper"}:
        raise _Invalid("Interval requires exactly lower and upper")
    lo, hi = _q(value["lower"], budget), _q(value["upper"], budget)
    if lo > hi:
        raise _Invalid("Reversed interval")
    return lo, hi


def _enc(value):
    return {"lower": str(value[0]), "upper": str(value[1])}


def _snapshot(value, limit, budget, stage, *, retain=True):
    # Bound individual tokens/containers and total structure before encoding or
    # constructing rational values. Only builtin JSON types are admitted.
    stack, count = [(value, 0)], 0
    while stack:
        item, depth = stack.pop()
        budget.tick(stage + "_shape")
        count += 1
        if depth > 20 or count > 500_000:
            raise _Limit("ENCODING_STRUCTURE_BUDGET")
        if type(item) is str:
            if len(item) > 4096:
                raise _Limit("ENCODING_TOKEN_BUDGET")
        elif type(item) is int:
            if item.bit_length() > budget.bits:
                raise _Limit("ENCODING_INTEGER_BUDGET")
        elif item is None or type(item) is bool:
            pass
        elif type(item) in (dict, list):
            if len(item) > 16384:
                raise _Limit("ENCODING_CONTAINER_BUDGET")
            if type(item) is dict:
                if any(type(k) is not str for k in item):
                    raise _Invalid("Object keys must be strings")
                stack.extend((k, depth+1) for k in item)
                stack.extend((v, depth+1) for v in item.values())
            else:
                stack.extend((v, depth+1) for v in item)
        else:
            raise _Invalid("Only bounded JSON values with exact rational encodings are admitted")
    hasher, size, chunks = hashlib.sha256(), 0, []
    encoder = json.JSONEncoder(sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    for chunk in encoder.iterencode(value):
        budget.tick(stage + "_stream")
        raw = chunk.encode("utf-8")
        size += len(raw)
        if size > limit:
            raise _Limit("INPUT_BYTE_BUDGET" if stage.startswith("passive_input") else "CERTIFICATE_BYTE_BUDGET")
        hasher.update(raw)
        if retain:
            chunks.append(raw)
    budget.tick(stage + "_complete")
    return hasher.hexdigest(), json.loads(b"".join(chunks)) if retain else None


def _hash(value, budget):
    return _snapshot(value, budget.certificate_bytes, budget, "passive_binding", retain=False)[0]


def _model_shape(model, budget):
    if type(model) is not dict:
        raise _Invalid("Explicit complete model required")
    for key, limit in (("nodes", budget.nodes), ("internal_nodes", budget.nodes), ("edges", budget.edges)):
        value = model.get(key)
        if type(value) is not list:
            raise _Invalid("Explicit " + key + " list required")
        if len(value) > limit:
            raise _Limit("NODE_BUDGET" if key != "edges" else "EDGE_BUDGET")
    if type(model.get("boundary_heads")) is not dict:
        raise _Invalid("Explicit boundary heads required")
    if len(model["boundary_heads"]) > budget.nodes:
        raise _Limit("NODE_BUDGET")


def _identity(value):
    if type(value) is not str or not 1 <= len(value) <= 128:
        raise _Invalid("Nonempty bounded string identities required")
    return value


def _normalize(raw, target_raw, budget):
    budget.tick("passive_model_normalization")
    _model_shape(raw, budget)
    if set(raw) != {"schema", "nodes", "internal_nodes", "boundary_heads", "edges", "context_root", "physical_model_root", "assumptions"}:
        raise _Invalid("Complete exact passive model fields required")
    if raw["schema"] != MODEL_SCHEMA or raw["assumptions"] != MODEL_ASSUMPTIONS:
        raise _Invalid("Unsupported model schema, regime, units or applicability assumptions")
    for name in ("context_root", "physical_model_root"):
        if type(raw[name]) is not str or not _ROOT.fullmatch(raw[name]):
            raise _Invalid("Declared context and physical model roots required")
    nodes = sorted(_identity(v) for v in raw["nodes"])
    internal = sorted(_identity(v) for v in raw["internal_nodes"])
    boundary = {_identity(v): _interval(p, budget) for v, p in sorted(raw["boundary_heads"].items())}
    if not nodes or len(set(nodes)) != len(nodes) or len(set(internal)) != len(internal):
        raise _Invalid("Nodes/internal identities must be nonempty and unique")
    if set(internal) & set(boundary) or set(internal) | set(boundary) != set(nodes):
        raise _Invalid("Internal and boundary vertices must exactly partition the full graph")
    edges, seen, adjacency = [], set(), {v: [] for v in nodes}
    for row in raw["edges"]:
        budget.tick("passive_edge_inventory")
        if type(row) is not dict or set(row) != {"id", "source", "target", "resistance"}:
            raise _Invalid("Every edge requires identity, orientation and resistance")
        name, u, v = (_identity(row[k]) for k in ("id", "source", "target"))
        if name in seen or u not in adjacency or v not in adjacency or u == v:
            raise _Invalid("Duplicate edge, absent endpoint or unsupported self-loop")
        r = _interval(row["resistance"], budget)
        if r[0] <= 0:
            raise _Invalid("Every resistance must be finite and strictly positive throughout")
        seen.add(name)
        edges.append((name, u, v, r))
        adjacency[u].append((name, v)); adjacency[v].append((name, u))
    edges.sort()
    components, assigned, spans = [], set(), {}
    for start in nodes:
        if start in assigned:
            continue
        stack, members = [start], set()
        while stack:
            budget.tick("passive_grounding")
            v = stack.pop()
            if v in members:
                continue
            members.add(v)
            stack.extend(w for _, w in adjacency[v] if w not in members)
        bd = sorted(set(boundary) & members)
        if not bd:
            raise _Invalid("Every graph component must contain a Dirichlet boundary")
        lo, hi = min(boundary[v][0] for v in bd), max(boundary[v][1] for v in bd)
        for v in members:
            spans[v] = (lo, hi)
        components.append({"nodes": sorted(members), "boundary_nodes": bd, "global_head": _enc((lo, hi))})
        assigned.update(members)
    normalized = {"schema": MODEL_SCHEMA, "nodes": nodes, "internal_nodes": internal,
        "boundary_heads": {v: _enc(p) for v, p in boundary.items()},
        "edges": [{"id": n, "source": u, "target": v, "resistance": _enc(r)} for n, u, v, r in edges],
        "context_root": raw["context_root"], "physical_model_root": raw["physical_model_root"],
        "assumptions": deepcopy(MODEL_ASSUMPTIONS)}
    target = None if target_raw is None else _q(target_raw, budget)
    if target is not None and target < 0:
        raise _Invalid("Target pressure width cannot be negative")
    topology = {"nodes": nodes, "internal_nodes": internal, "boundary_nodes": sorted(boundary),
        "edges": [{"id": n, "source": u, "target": v} for n, u, v, _ in edges]}
    domain = {"boundary_heads": normalized["boundary_heads"],
        "resistance": {n: _enc(r) for n, _, _, r in edges}, "parameter_domain": "CARTESIAN_INTERVAL_BOX"}
    model_root = _hash(normalized, budget)
    header = {"schema": CERTIFICATE_SCHEMA, "status": "CERTIFIED_ENCLOSURE", "scope": SCOPE, "rule": RULE,
        "model_root": model_root, "query_root": _hash({"model_root": model_root, "pressure_width_target": None if target is None else str(target)}, budget),
        "topology_root": _hash(topology, budget), "domain_root": _hash(domain, budget),
        "context_root": raw["context_root"], "physical_model_root": raw["physical_model_root"],
        "assumptions": deepcopy(MODEL_ASSUMPTIONS), "limitations": deepcopy(LIMITATIONS),
        "counts": {"nodes": len(nodes), "edges": len(edges), "internal_nodes": len(internal),
            "boundary_nodes": len(boundary), "components": len(components)}, "components": components,
        "pressure_width_target": None if target is None else str(target)}
    return {"nodes": nodes, "internal": internal, "boundary": boundary, "edges": edges,
        "adjacency": adjacency, "spans": spans, "header": header, "target": target}


def _sqrt(value, bits, budget):
    budget.tick("passive_producer_sqrt")
    if value < 0:
        raise _Invalid("Negative radicand")
    scale = 1 << bits
    n = isqrt((value.numerator << (2*bits)) // value.denominator)
    lo = budget.check(Q(n, scale))
    hi = lo if budget.mul(lo, lo) == value else budget.check(Q(n+1, scale))
    return lo, hi


def _producer_flow(drop, resistance, bits, budget):
    a, b = drop
    klo, khi = resistance
    rlo = khi if a >= 0 else klo
    rhi = klo if b >= 0 else khi
    first = _sqrt(budget.div(abs(a), rlo), bits, budget)
    last = _sqrt(budget.div(abs(b), rhi), bits, budget)
    lo = -first[1] if a < 0 else first[0]
    hi = -last[0] if b < 0 else last[1]
    return {"lower_endpoint_sqrt": _enc(first), "upper_endpoint_sqrt": _enc(last), "flow": _enc((lo, hi))}, (lo, hi)


def _pressures(m, values):
    return {**m["boundary"], **{v: (values[v], values[v]) for v in m["internal"]}}


def _producer_edges(m, pressures, bits, budget):
    proofs, flows = [], {}
    for name, u, v, r in m["edges"]:
        budget.tick("passive_producer_edge")
        drop = (budget.sub(pressures[u][0], pressures[v][1]), budget.sub(pressures[u][1], pressures[v][0]))
        proof, flow = _producer_flow(drop, r, bits, budget)
        proofs.append({"edge": name, **proof}); flows[name] = flow
    return proofs, flows


def _producer_residual(m, flows, vertex, budget):
    lo = hi = Q(0)
    for name, u, v, _ in m["edges"]:
        budget.tick("passive_producer_incidence")
        if u == vertex:
            lo, hi = budget.add(lo, flows[name][0]), budget.add(hi, flows[name][1])
        elif v == vertex:
            lo, hi = budget.sub(lo, flows[name][1]), budget.sub(hi, flows[name][0])
    return lo, hi


def _coordinate_residual(m, values, vertex, bits, budget):
    # Evaluate only incident edges; each proof-producing final pass still covers
    # every declared edge, regardless of this search optimization.
    p = _pressures(m, values)
    lo = hi = Q(0)
    for _, u, v, r in m["edges"]:
        budget.tick("passive_coordinate_incidence")
        if vertex not in (u, v):
            continue
        other = v if vertex == u else u
        drop = (budget.sub(values[vertex], p[other][1]), budget.sub(values[vertex], p[other][0]))
        _, flow = _producer_flow(drop, r, bits, budget)
        lo, hi = budget.add(lo, flow[0]), budget.add(hi, flow[1])
    return lo, hi


def _refine(m, lower, upper, passes, bits, budget):
    completed, reason = 0, "PASS_LIMIT"
    budget.refine_stop = budget.used + max(0, (budget.maximum-budget.used)//2)
    try:
        for _ in range(passes):
            budget.tick("passive_refinement_pass")
            previous = {v: budget.sub(upper[v], lower[v]) for v in m["internal"]}
            if not previous or all(x == 0 for x in previous.values()):
                reason = "EXACT_OR_BOUNDARY_ONLY"; break
            if m["target"] is not None and all(x <= m["target"] for x in previous.values()):
                reason = "TARGET_MET"; break
            # A simultaneous trial avoids slow coordinate convergence near a
            # zero-flow internal edge. It has no authority unless all node
            # signs are established; the final checker independently repeats
            # the complete barrier proof.
            trial = {v: budget.div(budget.add(lower[v], upper[v]), Q(2)) for v in m["internal"]}
            _, trial_flow = _producer_edges(m, _pressures(m, trial), bits, budget)
            residual = {v: _producer_residual(m, trial_flow, v, budget) for v in m["internal"]}
            if all(x[1] <= 0 for x in residual.values()):
                lower.update(trial)
            if all(x[0] >= 0 for x in residual.values()):
                upper.update(trial)
            for v in m["internal"]:
                if lower[v] == upper[v]:
                    continue
                lo, hi = lower[v], upper[v]
                for _ in range(8):
                    trial = budget.div(budget.add(lo, hi), Q(2))
                    value = {**lower, v: trial}
                    if _coordinate_residual(m, value, v, bits, budget)[1] <= 0:
                        lo = trial; lower[v] = trial
                    else:
                        hi = trial
                lo, hi = lower[v], upper[v]
                for _ in range(8):
                    trial = budget.div(budget.add(lo, hi), Q(2))
                    value = {**upper, v: trial}
                    if _coordinate_residual(m, value, v, bits, budget)[0] >= 0:
                        hi = trial; upper[v] = trial
                    else:
                        lo = trial
            completed += 1
            # Search stopping is not a proof or target-accuracy claim. Retain
            # the latest safe barriers if uncertainty or arithmetic stalls.
            if all(budget.sub(previous[v], budget.sub(upper[v], lower[v])) <=
                   budget.div(budget.sub(m["spans"][v][1], m["spans"][v][0]), Q(1 << 20))
                   for v in m["internal"]):
                reason = "REFINEMENT_STALLED"; break
    except _RefinementLimit as exc:
        if budget.external_error is exc:
            raise
        reason = "REFINEMENT_WORK_BUDGET"
    except _Limit as exc:
        if budget.external_error is exc or str(exc) != "RATIONAL_BIT_BUDGET":
            raise
        reason = "REFINEMENT_ARITHMETIC_BUDGET"
    finally:
        budget.refine_stop = None
    return completed, reason


def _widths(m, pressure, budget):
    widths = {v: budget.sub(pressure[v][1], pressure[v][0]) for v in m["internal"]}
    maximum = max(widths.values(), default=Q(0))
    return {"internal_widths": {v: str(x) for v, x in widths.items()}, "maximum_internal_width": str(maximum),
        "target_accuracy_met": None if m["target"] is None else maximum <= m["target"]}


def _final_guard(model, target, input_hash, budget, certificate=None, certificate_hash=None):
    # No callback may relabel the input after this final bounded read.
    callback = budget.callback
    budget.callback = None
    try:
        current = _snapshot({"model": model, "pressure_width_target": target}, budget.input_bytes,
            budget, "passive_input_final", retain=False)[0]
        if current != input_hash:
            raise _Invalid("Caller model or target changed before publication")
        if certificate is not None:
            current = _snapshot(certificate, budget.certificate_bytes, budget,
                "passive_certificate_final", retain=False)[0]
            if current != certificate_hash:
                raise _Invalid("Caller certificate changed before verification completed")
    finally:
        budget.callback = callback


def _failure(exc, budget, verifier=False):
    if budget is not None and budget.external_error is exc:
        raise exc
    return {"status": "UNKNOWN" if isinstance(exc, _Limit) else "FAIL" if verifier else "INVALID_INPUT",
        "reason": str(exc), "scope": SCOPE, "proof_complete": False,
        "work": budget.used if budget is not None else 0, "limitations": deepcopy(LIMITATIONS)}


def compile_passive_pressure(model, *, pressure_width_target=None, max_nodes=64, max_edges=128,
        max_work=2_000_000, max_refinement_passes=128, sqrt_bits=96, max_rational_bits=4096,
        max_input_bytes=1_048_576, max_certificate_bytes=16_777_216, checkpoint=None):
    """Produce a complete uniform comparison enclosure, possibly coarse."""
    budget = None
    try:
        budget = _Budget(max_nodes, max_edges, max_work, max_rational_bits, max_input_bytes, max_certificate_bytes, checkpoint)
        if type(max_refinement_passes) is not int or not 0 <= max_refinement_passes <= 1024:
            raise _Invalid("Invalid max_refinement_passes")
        if type(sqrt_bits) is not int or not 8 <= sqrt_bits <= 512 or 2*sqrt_bits > max_rational_bits:
            raise _Invalid("Invalid square-root precision")
        _model_shape(model, budget)
        input_hash, frozen = _snapshot({"model": model, "pressure_width_target": pressure_width_target},
            budget.input_bytes, budget, "passive_input")
        m = _normalize(frozen["model"], frozen["pressure_width_target"], budget)
        lower = {v: m["spans"][v][0] for v in m["internal"]}
        upper = {v: m["spans"][v][1] for v in m["internal"]}
        passes, reason = _refine(m, lower, upper, max_refinement_passes, sqrt_bits, budget)
        low_proof, low_flow = _producer_edges(m, _pressures(m, lower), sqrt_bits, budget)
        high_proof, high_flow = _producer_edges(m, _pressures(m, upper), sqrt_bits, budget)
        residuals = []
        for v in m["internal"]:
            lo, hi = _producer_residual(m, low_flow, v, budget), _producer_residual(m, high_flow, v, budget)
            if lo[1] > 0 or hi[0] < 0:
                raise _Invalid("Producer failed complete barrier sign checks")
            residuals.append({"node": v, "lower_barrier": _enc(lo), "upper_barrier": _enc(hi)})
        pressure = {**m["boundary"], **{v: (lower[v], upper[v]) for v in m["internal"]}}
        final_proof, final_flow = _producer_edges(m, pressure, sqrt_bits, budget)
        net = [{"node": v, "net_outgoing_flow": _enc(_producer_residual(m, final_flow, v, budget))}
               for v in sorted(m["boundary"])]
        certificate = {**m["header"], "pressure_bounds": [{"node": v, **_enc(pressure[v])} for v in m["nodes"]],
            "lower_barrier_edges": low_proof, "upper_barrier_edges": high_proof, "barrier_residuals": residuals,
            "flow_edges": final_proof, "boundary_net_injections": net, "widths": _widths(m, pressure, budget),
            "producer_diagnostics": {"sqrt_bits": sqrt_bits, "completed_refinement_passes": passes,
                "stop_reason": reason, "work_before_sealing": budget.used}}
        certificate["certificate_root"] = _hash(certificate, budget)
        _snapshot(certificate, budget.certificate_bytes, budget, "passive_certificate_output", retain=False)
        budget.tick("passive_producer_complete")
        _final_guard(model, pressure_width_target, input_hash, budget)
        return certificate
    except (_Invalid, _Limit, ValueError, TypeError, KeyError, OverflowError) as exc:
        return _failure(exc, budget)


def _certificate_shape(certificate, budget):
    if type(certificate) is not dict:
        raise _Invalid("Explicit certificate object required")
    for key, limit in (("pressure_bounds", budget.nodes), ("barrier_residuals", budget.nodes),
                     ("boundary_net_injections", budget.nodes), ("components", budget.nodes),
                     ("lower_barrier_edges", budget.edges), ("upper_barrier_edges", budget.edges), ("flow_edges", budget.edges)):
        rows = certificate.get(key)
        if type(rows) is not list:
            raise _Invalid("Missing complete certificate array " + key)
        if len(rows) > limit:
            raise _Limit("CERTIFICATE_COUNT_BUDGET")


def _check_sqrt(encoded, radicand, budget):
    lo, hi = _interval(encoded, budget)
    if lo < 0 or budget.mul(lo, lo) > radicand or budget.mul(hi, hi) < radicand:
        raise _Invalid("Invalid nonnegative rational square-root enclosure")
    return lo, hi


def _checked_edges(m, pressures, rows, budget):
    # Reconstruct radicands/signs directly. No producer sqrt, flow, residual or
    # refinement function is called by this independent certificate path.
    if len(rows) != len(m["edges"]):
        raise _Invalid("Incomplete edge proof denominator")
    flows = {}
    for edge, row in zip(m["edges"], rows):
        budget.tick("passive_check_edge")
        name, source, target, resistance = edge
        if type(row) is not dict or set(row) != {"edge", "lower_endpoint_sqrt", "upper_endpoint_sqrt", "flow"} or row["edge"] != name:
            raise _Invalid("Missing, duplicate, extra or reordered edge proof")
        low_drop = budget.sub(pressures[source][0], pressures[target][1])
        high_drop = budget.sub(pressures[source][1], pressures[target][0])
        minimum_r = resistance[0] if low_drop < 0 else resistance[1]
        maximum_r = resistance[1] if high_drop < 0 else resistance[0]
        first = _check_sqrt(row["lower_endpoint_sqrt"], budget.div(abs(low_drop), minimum_r), budget)
        last = _check_sqrt(row["upper_endpoint_sqrt"], budget.div(abs(high_drop), maximum_r), budget)
        expected = (-first[1] if low_drop < 0 else first[0], -last[0] if high_drop < 0 else last[1])
        if _interval(row["flow"], budget) != expected:
            raise _Invalid("Signed edge enclosure differs from checked radicals")
        flows[name] = expected
    return flows


def _checked_divergences(m, flows, budget):
    # Accumulate the entire declared incidence once, independently of the
    # producer's per-vertex scans. Boundary and internal denominators remain.
    sums = {v: [Q(0), Q(0)] for v in m["nodes"]}
    for name, u, v, _ in m["edges"]:
        budget.tick("passive_check_incidence")
        a, b = flows[name]
        sums[u][0] = budget.add(sums[u][0], a)
        sums[u][1] = budget.add(sums[u][1], b)
        sums[v][0] = budget.sub(sums[v][0], b)
        sums[v][1] = budget.sub(sums[v][1], a)
    return {v: tuple(x) for v, x in sums.items()}


def verify_passive_pressure(model, certificate, *, pressure_width_target=None, max_nodes=64, max_edges=128,
        max_work=2_000_000, max_rational_bits=4096, max_input_bytes=1_048_576,
        max_certificate_bytes=16_777_216, checkpoint=None):
    """Independently prove complete box enclosure, without invoking search."""
    budget = None
    try:
        budget = _Budget(max_nodes, max_edges, max_work, max_rational_bits, max_input_bytes, max_certificate_bytes, checkpoint)
        _model_shape(model, budget); _certificate_shape(certificate, budget)
        input_hash, frozen = _snapshot({"model": model, "pressure_width_target": pressure_width_target},
            budget.input_bytes, budget, "passive_input")
        certificate_hash, supplied = _snapshot(certificate, budget.certificate_bytes, budget, "passive_certificate")
        _certificate_shape(supplied, budget)
        m = _normalize(frozen["model"], frozen["pressure_width_target"], budget)
        extras = {"pressure_bounds", "lower_barrier_edges", "upper_barrier_edges", "barrier_residuals",
            "flow_edges", "boundary_net_injections", "widths", "producer_diagnostics", "certificate_root"}
        if set(supplied) != set(m["header"]) | extras:
            raise _Invalid("Complete exact certificate fields required")
        for key, expected in m["header"].items():
            if supplied[key] != expected:
                raise _Invalid("Certificate header/model/domain/coverage mismatch: " + key)
        if _hash({k: supplied[k] for k in m["header"]}, budget) != _hash(m["header"], budget):
            raise _Invalid("Certificate header encoding/type mismatch")
        root = supplied["certificate_root"]
        if type(root) is not str or not _ROOT.fullmatch(root) or _hash({k: v for k, v in supplied.items() if k != "certificate_root"}, budget) != root:
            raise _Invalid("Certificate content root mismatch")
        rows = supplied["pressure_bounds"]
        if len(rows) != len(m["nodes"]):
            raise _Invalid("Incomplete pressure-node denominator")
        pressure = {}
        for v, row in zip(m["nodes"], rows):
            budget.tick("passive_check_pressure")
            if type(row) is not dict or set(row) != {"node", "lower", "upper"} or row["node"] != v:
                raise _Invalid("Missing, duplicate, extra or reordered pressure node")
            interval = _interval({k: row[k] for k in ("lower", "upper")}, budget)
            if v in m["boundary"]:
                if interval != m["boundary"][v]:
                    raise _Invalid("Dirichlet boundary domain narrowed or changed")
            elif not m["spans"][v][0] <= interval[0] <= interval[1] <= m["spans"][v][1]:
                raise _Invalid("Internal barrier outside global pressure range")
            pressure[v] = interval
        lower = {v: pressure[v][0] for v in m["internal"]}
        upper = {v: pressure[v][1] for v in m["internal"]}
        low = _checked_divergences(m, _checked_edges(m, _pressures(m, lower), supplied["lower_barrier_edges"], budget), budget)
        high = _checked_divergences(m, _checked_edges(m, _pressures(m, upper), supplied["upper_barrier_edges"], budget), budget)
        rows = supplied["barrier_residuals"]
        if len(rows) != len(m["internal"]):
            raise _Invalid("Incomplete internal conservation/barrier denominator")
        for v, row in zip(m["internal"], rows):
            budget.tick("passive_check_barrier_sign")
            if type(row) is not dict or set(row) != {"node", "lower_barrier", "upper_barrier"} or row["node"] != v:
                raise _Invalid("Missing, duplicate or extra internal residual")
            if _interval(row["lower_barrier"], budget) != low[v] or _interval(row["upper_barrier"], budget) != high[v]:
                raise _Invalid("Forged complete node residual sum")
            if low[v][1] > 0 or high[v][0] < 0:
                raise _Invalid("Required universal sub/supersolution signs not established")
        final_flows = _checked_edges(m, pressure, supplied["flow_edges"], budget)
        net = _checked_divergences(m, final_flows, budget)
        rows = supplied["boundary_net_injections"]
        if len(rows) != len(m["boundary"]):
            raise _Invalid("Incomplete boundary-injection denominator")
        for v, row in zip(sorted(m["boundary"]), rows):
            if type(row) is not dict or set(row) != {"node", "net_outgoing_flow"} or row["node"] != v or _interval(row["net_outgoing_flow"], budget) != net[v]:
                raise _Invalid("Boundary injection differs from full incidence enclosure")
        widths = _widths(m, pressure, budget)
        if supplied["widths"] != widths or _hash(supplied["widths"], budget) != _hash(widths, budget):
            raise _Invalid("Wrong pressure width or requested accuracy claim")
        diagnostic = supplied["producer_diagnostics"]
        if type(diagnostic) is not dict or set(diagnostic) != {"sqrt_bits", "completed_refinement_passes", "stop_reason", "work_before_sealing"}:
            raise _Invalid("Malformed nonauthoritative producer diagnostics")
        for name, lo, hi in (("sqrt_bits", 8, 512), ("completed_refinement_passes", 0, 1024), ("work_before_sealing", 0, 10_000_000)):
            if type(diagnostic[name]) is not int or not lo <= diagnostic[name] <= hi:
                raise _Invalid("Invalid producer diagnostic integer")
        if diagnostic["stop_reason"] not in {"PASS_LIMIT", "EXACT_OR_BOUNDARY_ONLY", "TARGET_MET", "REFINEMENT_STALLED", "REFINEMENT_WORK_BUDGET", "REFINEMENT_ARITHMETIC_BUDGET"}:
            raise _Invalid("Unknown producer diagnostic reason")
        budget.tick("passive_verifier_complete")
        _final_guard(model, pressure_width_target, input_hash, budget, certificate, certificate_hash)
        return {"status": "PASS", "scope": SCOPE, "proof_complete": True, "rule": RULE,
            "model_root": m["header"]["model_root"], "query_root": m["header"]["query_root"],
            "topology_root": m["header"]["topology_root"], "domain_root": m["header"]["domain_root"],
            "certificate_root": root, "counts": deepcopy(m["header"]["counts"]),
            "edge_enclosures_checked": 3*len(m["edges"]), "internal_barriers_checked": 2*len(m["internal"]),
            "pressure_bounds": deepcopy(supplied["pressure_bounds"]),
            "flow_bounds": [{"edge": name, **_enc(final_flows[name])} for name, _, _, _ in m["edges"]],
            "boundary_net_injections": deepcopy(supplied["boundary_net_injections"]), "widths": widths,
            "existence_and_uniqueness": "ONE_EQUILIBRIUM_FOR_EACH_ADMITTED_PARAMETER_TUPLE",
            "producer_search_reused": False, "work": budget.used, "limitations": deepcopy(LIMITATIONS)}
    except (_Invalid, _Limit, ValueError, TypeError, KeyError, OverflowError) as exc:
        return _failure(exc, budget, verifier=True)
