"""Checked nonlinear operating-point envelopes for an explicit two-sink model.

Original P6: PO1/PO2/PO7 and native paragraphs 16836--16853; integration
RTR19/20. This is a mathematical interval-box model, not a native IFC adapter.
The producer bisects extremal quadratics; the verifier never calls that search.
"""
from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
import hashlib
import json
from math import isfinite, isqrt
import re


MODEL_SCHEMA = "oma.two-sink-pressure-model/1"
CERTIFICATE_SCHEMA = "oma.two-sink-pressure-certificate/1"
PARAMETERS = ("P1", "P2", "beta", "A1", "A2", "B1", "B2")
MODEL_ASSUMPTIONS = {
    "parameter_domain": "CARTESIAN_INTERVAL_BOX",
    "pressure_quantity": "TOTAL_PRESSURE_PLUS_GRAVITATIONAL_POTENTIAL_DROP_PA",
    "loss_law": "P_i=beta*Q^2*(A_i+B_i*t_i^2)",
    "regime": "Q>0;0<t<1;q1=t*Q;q2=(1-t)*Q",
    "units": {"P1": "Pa", "P2": "Pa", "beta": "Pa*s^2/m^6", "A1": "1", "A2": "1",
        "B1": "1", "B2": "1", "Q": "m^3/s"},
    "physical_applicability": "DECLARED_BY_CALLER_NOT_PROVED_BY_KERNEL",
}
SCOPE = "UNIQUE_FORWARD_TWO_SINK_QUADRATIC_OPERATING_POINT_FOR_EVERY_PARAMETER_IN_DECLARED_BOX"
_RATIONAL = re.compile(r"[+-]?[0-9]+(?:/[0-9]+|\.[0-9]+)?\Z")
_ROOT = re.compile(r"[0-9a-f]{64}\Z")


class _Invalid(ValueError):
    pass


class _Limit(RuntimeError):
    pass


class _Budget:
    def __init__(self, max_work, max_rational_bits, max_input_bytes, max_certificate_bytes, checkpoint):
        for name, value, lower, upper in (
            ("max_work", max_work, 1, 1_000_000),
            ("max_rational_bits", max_rational_bits, 32, 16_384),
            ("max_input_bytes", max_input_bytes, 256, 1_048_576),
            ("max_certificate_bytes", max_certificate_bytes, 256, 4_194_304),
        ):
            if type(value) is not int or not lower <= value <= upper:
                raise _Invalid(f"Invalid {name}")
        if checkpoint is not None and not callable(checkpoint):
            raise _Invalid("checkpoint must be callable")
        self.maximum, self.bits = max_work, max_rational_bits
        self.input_bytes, self.certificate_bytes = max_input_bytes, max_certificate_bytes
        self.work, self.checkpoint, self.external_error = 0, checkpoint, None

    def tick(self, stage="pressure_arithmetic"):
        self.work += 1
        if self.checkpoint is not None:
            try:
                self.checkpoint(stage)
            except BaseException as exc:
                self.external_error = exc
                raise
        if self.work > self.maximum:
            raise _Limit("WORK_BUDGET")

    def check(self, value):
        if max(abs(value.numerator).bit_length(), value.denominator.bit_length()) > self.bits:
            raise _Limit("RATIONAL_BIT_BUDGET")
        return value

    def add(self, a, b):
        self.tick()
        return self.check(a + b)

    def sub(self, a, b):
        self.tick()
        return self.check(a - b)

    def mul(self, a, b):
        self.tick()
        return self.check(a * b)

    def div(self, a, b):
        self.tick()
        if b == 0:
            raise _Invalid("Zero denominator")
        return self.check(a / b)


def _fraction(value, budget):
    budget.tick("pressure_parse_rational")
    if type(value) is Fraction:
        return budget.check(value)
    if type(value) is int:
        if abs(value).bit_length() > budget.bits:
            raise _Limit("RATIONAL_BIT_BUDGET")
        return Fraction(value)
    if type(value) is not str:
        raise _Invalid("Rationals require integers, Fraction values or explicit rational strings; binary floats are not admitted")
    # Bound the token before integer conversion; no exponential notation.
    if len(value) > 2 * budget.bits + 4:
        raise _Limit("RATIONAL_ENCODING_BUDGET")
    if not _RATIONAL.fullmatch(value):
        raise _Invalid("Malformed rational token")
    try:
        result = Fraction(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise _Invalid("Malformed rational or zero denominator") from exc
    return budget.check(result)


def _interval(value, budget):
    if type(value) is not dict or len(value) != 2 or set(value) != {"lower", "upper"}:
        raise _Invalid("An exact interval requires exactly lower and upper")
    lo, hi = _fraction(value["lower"], budget), _fraction(value["upper"], budget)
    if lo > hi:
        raise _Invalid("Reversed interval")
    return lo, hi


def _encoded(interval):
    return {"lower": str(interval[0]), "upper": str(interval[1])}


def _hash(value, limit, budget, *, retain_snapshot=False):
    # Reject large individual strings/integers/containers before JSON encoding
    # can allocate a correspondingly large quoted token or decimal integer.
    stack, nodes = [(value, 0)], 0
    while stack:
        item, depth = stack.pop()
        budget.tick("pressure_hash_preflight")
        nodes += 1
        if depth > 24 or nodes > 2048:
            raise _Limit("STRUCTURE_BUDGET")
        if type(item) is str:
            if len(item) > limit or len(item.encode("utf-8")) > limit:
                raise _Limit("ENCODING_BYTE_BUDGET")
        elif type(item) is int:
            if abs(item).bit_length() > budget.bits:
                raise _Limit("RATIONAL_BIT_BUDGET")
        elif item is None or type(item) is bool:
            pass
        elif type(item) is float:
            if not isfinite(item):
                raise _Invalid("Nonfinite JSON number")
        elif type(item) in (dict, list, tuple):
            if len(item) > 128:
                raise _Limit("STRUCTURE_BUDGET")
            if type(item) is dict:
                if any(type(key) is not str for key in item):
                    raise _Invalid("JSON object keys must be strings")
                stack.extend((key, depth + 1) for key in item)
                stack.extend((child, depth + 1) for child in item.values())
            else:
                stack.extend((child, depth + 1) for child in item)
        else:
            raise _Invalid("Unsupported certificate encoding")
    hasher, size, chunks = hashlib.sha256(), 0, []
    encoder = json.JSONEncoder(sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    for index, chunk in enumerate(encoder.iterencode(value)):
        if index % 16 == 0:
            budget.tick("pressure_hash_stream")
        raw = chunk.encode("utf-8")
        size += len(raw)
        if size > limit:
            raise _Limit("ENCODING_BYTE_BUDGET")
        hasher.update(raw)
        if retain_snapshot:
            chunks.append(raw)
    budget.tick("pressure_hash_complete")
    if retain_snapshot:
        # Parse exactly the bounded bytes whose root is reported. Later caller
        # mutation cannot relabel a different proof as the checked certificate.
        return hasher.hexdigest(), json.loads(b"".join(chunks))
    return hasher.hexdigest()


def _normalize(model, target_split_width, budget):
    budget.tick("pressure_model")
    keys = {"schema", "branch_ids", "parameters", "context_root", "physical_model_root", "assumptions"}
    if type(model) is not dict or len(model) != len(keys) or set(model) != keys:
        raise _Invalid("Complete two-branch model and bindings required")
    if model["schema"] != MODEL_SCHEMA:
        raise _Invalid("Unsupported model schema")
    ids = model["branch_ids"]
    if type(ids) not in (list, tuple) or len(ids) != 2 or any(type(s) is not str or not 1 <= len(s) <= 128 for s in ids) or ids[0] == ids[1]:
        raise _Invalid("Exactly two distinct bounded branch identities required")
    for key in ("context_root", "physical_model_root"):
        if type(model[key]) is not str or not _ROOT.fullmatch(model[key]):
            raise _Invalid("Complete context and physical model roots required")
    if model["assumptions"] != MODEL_ASSUMPTIONS:
        raise _Invalid("Required unit, loss, regime, domain or applicability declaration missing")
    raw = model["parameters"]
    if type(raw) is not dict or len(raw) != 7 or set(raw) != set(PARAMETERS):
        raise _Invalid("Exactly both pressures, beta, both trunk/tee losses and both branch losses required")
    parameters = {key: _interval(raw[key], budget) for key in PARAMETERS}
    for key, (lo, _) in parameters.items():
        if lo < 0 or (key not in {"A1", "A2"} and lo == 0):
            raise _Invalid("P1/P2/beta/B1/B2 must be strictly positive throughout; A1/A2 nonnegative")
    target = _fraction(target_split_width, budget)
    if not 0 < target <= 1:
        raise _Invalid("Target split width must lie in (0,1]")
    normalized = {**model, "branch_ids": list(ids), "parameters": {k: _encoded(v) for k, v in parameters.items()},
        "assumptions": deepcopy(MODEL_ASSUMPTIONS)}
    root = _hash(normalized, budget.input_bytes, budget)
    query = _hash({"model_root": root, "target_split_width": str(target)}, budget.input_bytes, budget)
    return normalized, parameters, target, root, query


def _g_extrema(parameters, t, budget):
    """Producer's exact extrema at one split; parameter intervals never collapse."""
    p = parameters
    t2 = budget.mul(t, t)
    other = budget.sub(Fraction(1), t)
    other2 = budget.mul(other, other)
    values = []
    for positive, negative in ((0, 1), (1, 0)):
        first = budget.add(p["A1"][positive], budget.mul(p["B1"][positive], t2))
        second = budget.add(p["A2"][negative], budget.mul(p["B2"][negative], other2))
        values.append(budget.sub(budget.mul(p["P2"][positive], first), budget.mul(p["P1"][negative], second)))
    return tuple(values)


def _producer_squared_flow(p, split, budget):
    lower = max(budget.div(p[key][0], budget.mul(p["beta"][1], budget.add(p[a][1], p[b][1])))
        for key, a, b in (("P1", "A1", "B1"), ("P2", "A2", "B2")))
    upper = budget.mul(Fraction(2), budget.add(
        budget.div(p["P1"][1], budget.mul(p["beta"][0], p["B1"][0])),
        budget.div(p["P2"][1], budget.mul(p["beta"][0], p["B2"][0]))))
    tlo, thi = split
    for pressure, a, b, lo, hi in (("P1", "A1", "B1", tlo, thi),
        ("P2", "A2", "B2", budget.sub(Fraction(1), thi), budget.sub(Fraction(1), tlo))):
        dlow = budget.add(p[a][0], budget.mul(p[b][0], budget.mul(lo, lo)))
        dhigh = budget.add(p[a][1], budget.mul(p[b][1], budget.mul(hi, hi)))
        lower = max(lower, budget.div(p[pressure][0], budget.mul(p["beta"][1], dhigh)))
        if dlow > 0:
            upper = min(upper, budget.div(p[pressure][1], budget.mul(p["beta"][0], dlow)))
    if lower <= 0 or lower > upper:
        raise _Invalid("Inconsistent derived positive flow interval")
    return lower, upper


def _sqrt_bounds(interval, bits, budget):
    budget.tick("pressure_sqrt_producer")
    scale = 1 << bits
    values = []
    for endpoint, upper in zip(interval, (False, True)):
        scaled = budget.mul(endpoint, Fraction(scale * scale))
        floor = isqrt(scaled.numerator // scaled.denominator)
        result = budget.check(Fraction(floor, scale))
        if upper and budget.mul(result, result) < endpoint:
            result = budget.check(Fraction(floor + 1, scale))
        values.append(result)
    return tuple(values)


def _accuracy(split, total, branches, target, budget):
    width = budget.sub(split[1], split[0])
    return {"requested_split_width": str(target), "achieved_split_width": str(width),
        "target_split_width_met": width <= target,
        "total_flow_width_m3_s": str(budget.sub(total[1], total[0])),
        "branch_flow_widths_m3_s": {key: str(budget.sub(value[1], value[0])) for key, value in branches.items()},
        "flow_accuracy_target": "NOT_REQUESTED", "includes_parameter_uncertainty": True}


def _correlation(ids):
    return {"branch_ids": list(ids), "parameterization": "q1=t*Q;q2=(1-t)*Q", "conservation": "Q=q1+q2",
        "marginal_intervals_are_independent": False,
        "scope": "Every actual model solution obeys this relation; arbitrary marginal-box points need not solve the model"}


def _failure(exc, budget, verifier=False):
    if budget is not None and budget.external_error is exc:
        raise exc
    if isinstance(exc, _Limit):
        status = "UNKNOWN"
    elif isinstance(exc, (_Invalid, ValueError, TypeError, KeyError, OverflowError, RecursionError)):
        status = "FAIL" if verifier else "INVALID_INPUT"
    else:
        raise exc
    return {"status": status, "reason": str(exc), "scope": SCOPE, "work": budget.work if budget else 0,
        "physical_acceptance_authority": False, "infeasibility_claim": False}


def _final_model_guard(model, target_split_width, expected_root, budget):
    """Bounded final binding after the last externally supplied checkpoint.

    Do not invoke the caller again while reading the final model: a callback
    could otherwise change it after its fields were copied but before return.
    This tail retains work/bit/encoding bounds, but has no cooperative callback.
    It is not an atomic-object guarantee against another concurrent writer.
    """
    checkpoint = budget.checkpoint
    budget.checkpoint = None
    try:
        if _normalize(model, target_split_width, budget)[3] != expected_root:
            raise _Invalid("Input model changed before final publication")
    finally:
        budget.checkpoint = checkpoint


def compile_two_sink_pressure(model, *, target_split_width="1/1000000", max_refinements=64, sqrt_bits=64,
        max_work=100000, max_rational_bits=4096, max_input_bytes=65536, max_certificate_bytes=1048576, checkpoint=None):
    """Compile a uniform enclosure, or explicit UNKNOWN/INVALID_INPUT.

    max_refinements limits accuracy refinement, not proof validity. A complete
    coarse certificate remains CERTIFIED and truthfully reports its width.
    """
    budget = None
    try:
        budget = _Budget(max_work, max_rational_bits, max_input_bytes, max_certificate_bytes, checkpoint)
        if type(max_refinements) is not int or not 0 <= max_refinements <= 512:
            raise _Invalid("Invalid refinement count")
        if type(sqrt_bits) is not int or not 0 <= sqrt_bits <= 512:
            raise _Invalid("Invalid square-root precision")
        normalized, p, target, root, query = _normalize(model, target_split_width, budget)
        zero, one = Fraction(0), Fraction(1)
        g0, g1 = _g_extrema(p, zero, budget), _g_extrema(p, one, budget)
        if not g0[1] < 0 or not g1[0] > 0:
            return {"status": "UNKNOWN", "reason": "FORWARD_REGIME_NOT_UNIFORMLY_ESTABLISHED",
                "model_root": root, "endpoint_g0": _encoded(g0), "endpoint_g1": _encoded(g1),
                "scope": SCOPE, "work": budget.work, "physical_acceptance_authority": False, "infeasibility_claim": False}
        derivative = budget.mul(Fraction(2), min(budget.mul(p["P2"][0], p["B1"][0]), budget.mul(p["P1"][0], p["B2"][0])))
        brackets = [[zero, one], [zero, one]]
        for _ in range(max_refinements):
            if all(budget.sub(hi, lo) <= target / 2 for lo, hi in brackets):
                break
            for index, extrema_index in ((0, 1), (1, 0)):
                lo, hi = brackets[index]
                if lo == hi:
                    continue
                budget.tick("pressure_refine_extreme_root")
                middle = budget.div(budget.add(lo, hi), Fraction(2))
                value = _g_extrema(p, middle, budget)[extrema_index]
                brackets[index] = [middle, middle] if value == 0 else [middle, hi] if value < 0 else [lo, middle]
        split = brackets[0][0], brackets[1][1]
        squared = _producer_squared_flow(p, split, budget)
        total = _sqrt_bounds(squared, sqrt_bits, budget)
        ids = normalized["branch_ids"]
        branches = {ids[0]: (budget.mul(split[0], total[0]), budget.mul(split[1], total[1])),
            ids[1]: (budget.mul(budget.sub(one, split[1]), total[0]), budget.mul(budget.sub(one, split[0]), total[1]))}
        accuracy = _accuracy(split, total, branches, target, budget)
        certificate = {"schema": CERTIFICATE_SCHEMA, "model_root": root, "query_root": query, "branch_ids": ids,
            "regime_proof": {"g_at_zero": _encoded(g0), "g_at_one": _encoded(g1), "strict_derivative_lower_bound": str(derivative)},
            "enclosures": {"split_fraction": _encoded(split), "total_flow_squared_m6_s2": _encoded(squared),
                "total_flow_m3_s": _encoded(total), "branch_flows_m3_s": {k: _encoded(v) for k, v in branches.items()}},
            "accuracy": accuracy, "correlation": _correlation(ids), "scope": SCOPE, "physical_acceptance_authority": False}
        certificate_root, certificate = _hash(certificate, budget.certificate_bytes, budget, retain_snapshot=True)
        budget.tick("pressure_producer_complete")
        _final_model_guard(model, target_split_width, root, budget)
        return {"status": "CERTIFIED", "model_root": root, "certificate": certificate, "certificate_root": certificate_root,
            "scope": SCOPE, "work": budget.work, "physical_acceptance_authority": False, "infeasibility_claim": False}
    except BaseException as exc:
        return _failure(exc, budget)


def verify_two_sink_pressure(model, certificate, *, target_split_width="1/1000000", max_work=100000,
        max_rational_bits=4096, max_input_bytes=65536, max_certificate_bytes=1048576, checkpoint=None):
    """Independently replay domain, root, monotonicity and enclosure inequalities.

    No root search, numerical solve, producer g/flow evaluator or producer sqrt
    routine is invoked. Widened valid enclosures may pass with their real widths.
    """
    budget = None
    try:
        budget = _Budget(max_work, max_rational_bits, max_input_bytes, max_certificate_bytes, checkpoint)
        normalized, p, target, root, query = _normalize(model, target_split_width, budget)
        keys = {"schema", "model_root", "query_root", "branch_ids", "regime_proof", "enclosures", "accuracy",
            "correlation", "scope", "physical_acceptance_authority"}
        if type(certificate) is not dict or len(certificate) != len(keys) or set(certificate) != keys:
            raise _Invalid("Malformed certificate schema")
        # Before any certificate rational is decoded, enforce its encoding bound.
        certificate_root, certificate = _hash(certificate, budget.certificate_bytes, budget, retain_snapshot=True)
        ids = normalized["branch_ids"]
        if (certificate["schema"] != CERTIFICATE_SCHEMA or certificate["model_root"] != root
                or certificate["query_root"] != query or certificate["branch_ids"] != ids
                or certificate["scope"] != SCOPE or certificate["physical_acceptance_authority"] is not False
                or certificate["correlation"] != _correlation(ids)):
            raise _Invalid("Certificate domain, identity, scope or correlation binding changed")
        proof = certificate["regime_proof"]
        if type(proof) is not dict or set(proof) != {"g_at_zero", "g_at_one", "strict_derivative_lower_bound"}:
            raise _Invalid("Complete regime proof required")
        # Endpoint extrema derived directly from g(0) and g(1), independently
        # of the producer's point evaluator.
        g0 = (budget.sub(budget.mul(p["P2"][0], p["A1"][0]), budget.mul(p["P1"][1], budget.add(p["A2"][1], p["B2"][1]))),
            budget.sub(budget.mul(p["P2"][1], p["A1"][1]), budget.mul(p["P1"][0], budget.add(p["A2"][0], p["B2"][0]))))
        g1 = (budget.sub(budget.mul(p["P2"][0], budget.add(p["A1"][0], p["B1"][0])), budget.mul(p["P1"][1], p["A2"][1])),
            budget.sub(budget.mul(p["P2"][1], budget.add(p["A1"][1], p["B1"][1])), budget.mul(p["P1"][0], p["A2"][0])))
        derivative = budget.mul(Fraction(2), min(budget.mul(p["P2"][0], p["B1"][0]), budget.mul(p["P1"][0], p["B2"][0])))
        if not g0[1] < 0 or not g1[0] > 0 or derivative <= 0:
            raise _Invalid("Unique forward regime not established for every parameter")
        if _interval(proof["g_at_zero"], budget) != g0 or _interval(proof["g_at_one"], budget) != g1 or _fraction(proof["strict_derivative_lower_bound"], budget) != derivative:
            raise _Invalid("Forged endpoint or monotonicity proof")
        encoded = certificate["enclosures"]
        if type(encoded) is not dict or set(encoded) != {"split_fraction", "total_flow_squared_m6_s2", "total_flow_m3_s", "branch_flows_m3_s"}:
            raise _Invalid("Complete split and flow enclosures required")
        split = _interval(encoded["split_fraction"], budget)
        squared = _interval(encoded["total_flow_squared_m6_s2"], budget)
        total = _interval(encoded["total_flow_m3_s"], budget)
        raw_branches = encoded["branch_flows_m3_s"]
        if type(raw_branches) is not dict or set(raw_branches) != set(ids):
            raise _Invalid("Both exact branch flow identities required")
        branches = {key: _interval(raw_branches[key], budget) for key in ids}
        lo, hi = split
        if not 0 <= lo <= hi <= 1:
            raise _Invalid("Split bracket lies outside the closed forward domain")
        # Each sign is the adverse parameter corner at this exact endpoint.
        upper_at_lo = budget.sub(
            budget.mul(p["P2"][1], budget.add(p["A1"][1], budget.mul(p["B1"][1], budget.mul(lo, lo)))),
            budget.mul(p["P1"][0], budget.add(p["A2"][0], budget.mul(p["B2"][0], budget.mul(1-lo, 1-lo)))))
        lower_at_hi = budget.sub(
            budget.mul(p["P2"][0], budget.add(p["A1"][0], budget.mul(p["B1"][0], budget.mul(hi, hi)))),
            budget.mul(p["P1"][1], budget.add(p["A2"][1], budget.mul(p["B2"][1], budget.mul(1-hi, 1-hi)))))
        if upper_at_lo > 0 or lower_at_hi < 0:
            raise _Invalid("Bracket omits an admitted parameter's unique root")
        # Independently derive a global finite bound: q_i^2 <= P_i/(beta B_i)
        # and (q1+q2)^2 <= 2(q1^2+q2^2). Both denominators are strictly positive.
        maximum = Fraction(0)
        minimum = Fraction(0)
        for pressure, common, branch, left, right in (("P1", "A1", "B1", lo, hi), ("P2", "A2", "B2", 1-hi, 1-lo)):
            maximum = budget.add(maximum, budget.mul(Fraction(2), budget.div(p[pressure][1], budget.mul(p["beta"][0], p[branch][0]))))
            minimum = max(minimum, budget.div(p[pressure][0], budget.mul(p["beta"][1], budget.add(p[common][1], p[branch][1]))))
        for pressure, common, branch, left, right in (("P1", "A1", "B1", lo, hi), ("P2", "A2", "B2", 1-hi, 1-lo)):
            denominator_lo = budget.mul(p["beta"][0], budget.add(p[common][0], budget.mul(p[branch][0], budget.mul(left, left))))
            denominator_hi = budget.mul(p["beta"][1], budget.add(p[common][1], budget.mul(p[branch][1], budget.mul(right, right))))
            if denominator_hi <= 0:
                raise _Invalid("Positive path denominator missing")
            minimum = max(minimum, budget.div(p[pressure][0], denominator_hi))
            if denominator_lo > 0:
                maximum = min(maximum, budget.div(p[pressure][1], denominator_lo))
        if not 0 <= squared[0] <= minimum <= maximum <= squared[1]:
            raise _Invalid("Squared total-flow interval omits a derived enclosure")
        if total[0] < 0 or total[1] <= 0 or budget.mul(total[0], total[0]) > squared[0] or budget.mul(total[1], total[1]) < squared[1]:
            raise _Invalid("Square-root enclosure inequalities failed")
        for identity, left, right in ((ids[0], lo, hi), (ids[1], 1-hi, 1-lo)):
            lower, upper = branches[identity]
            if lower < 0 or lower > budget.mul(left, total[0]) or upper < budget.mul(right, total[1]):
                raise _Invalid("Branch-flow marginal omits the conserved parametrization")
        accuracy = _accuracy(split, total, branches, target, budget)
        if certificate["accuracy"] != accuracy:
            raise _Invalid("Accuracy or uncertainty claim disagrees with actual enclosures")
        budget.tick("pressure_verifier_complete")
        _final_model_guard(model, target_split_width, root, budget)
        return {"status": "PASS", "model_root": root, "certificate_root": certificate_root,
            "enclosures": deepcopy(encoded), "accuracy": accuracy, "correlation": _correlation(ids), "scope": SCOPE,
            "work": budget.work, "physical_acceptance_authority": False, "infeasibility_claim": False}
    except BaseException as exc:
        return _failure(exc, budget, verifier=True)
