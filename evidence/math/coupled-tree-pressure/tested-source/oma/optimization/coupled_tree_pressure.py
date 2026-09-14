"""Uniform rational Banach certificates for declared unequal tree-loss laws.

Original P5 P14530--14546; P6 PO11/12 P16081--16135 and PO2
P17645--17681.  This is uniqueness INSIDE a supplied positive flow box,
not a passive common-head theorem or proof of native model applicability.
"""
from copy import deepcopy
from fractions import Fraction as Q

from . import passive_pressure as p

MODEL_SCHEMA = "oma.coupled-tree-quadratic-pressure-model/1"
CERTIFICATE_SCHEMA = "oma.coupled-tree-positive-box-certificate/1"
SCOPE = "ONE_ROOT_INSIDE_SUPPLIED_POSITIVE_BOX_FOR_EACH_SAME_PARAMETER_TUPLE"
RULE = "RATIONAL_PRECONDITIONED_INTERVAL_BANACH_V1"
MODEL_ASSUMPTIONS = {
    "parameter_domain": "CARTESIAN_BOX_WITH_REUSED_NAMED_COEFFICIENT_IDENTITIES",
    "equation": "SUM_APPLICABLE_A_TIMES_DESCENDANT_FLOW_SUM_SQUARED_MINUS_AVAILABLE_HEAD",
    "head_quantity": "AVAILABLE_TOTAL_PRESSURE_PLUS_GRAVITATIONAL_POTENTIAL_PA",
    "regime": "STRICTLY_POSITIVE_LEAF_FLOWS_FIXED_QUADRATIC_LOSS_LAW",
    "units": {"head": "Pa", "flow": "m^3/s", "coefficient": "Pa*s^2/m^6"},
    "physical_applicability": "DECLARED_BY_CALLER_NOT_PROVED_BY_KERNEL",
}
LIMITATIONS = {
    "global_uniqueness_outside_supplied_box": False,
    "other_equilibria_excluded": False,
    "one_common_solution_for_all_parameter_choices": False,
    "tight_solution_hull": False,
    "native_tree_or_complete_physical_component_coverage_proved": False,
    "physical_model_truth_or_loss_coefficient_applicability_proved": False,
    "minimum_delivery_velocity_or_native_acceptance_authority": False,
    "failed_certificate_is_infeasibility": False,
}


class _NoProof(RuntimeError):
    pass


class _Budget(p._Budget):
    def __init__(self, leaves, terms, entries, work, bits, input_bytes, certificate_bytes, checkpoint):
        if type(leaves) is not int or not 1 <= leaves <= 32:
            raise p._Invalid("Invalid max_leaves")
        if type(terms) is not int or not 1 <= terms <= 512:
            raise p._Invalid("Invalid max_terms")
        if type(entries) is not int or not 1 <= entries <= 1024:
            raise p._Invalid("Invalid max_matrix_entries")
        super().__init__(leaves, terms, work, bits, input_bytes, certificate_bytes, checkpoint)
        self.entries = entries

    def tick(self, stage="coupled_arithmetic"):
        super().tick(stage.replace("passive_", "coupled_"))


def _shape(raw, b):
    if type(raw) is not dict or set(raw) != {"model", "flow_box"} or type(raw["model"]) is not dict:
        raise p._Invalid("Complete model and flow box required")
    m = raw["model"]
    for name, limit, kind in (("leaves", b.nodes, list), ("terms", b.edges, list),
                              ("coefficients", b.edges, dict), ("available_heads", b.nodes, dict)):
        values = m.get(name)
        if type(values) is not kind:
            raise p._Invalid("Explicit " + name + " inventory required")
        if len(values) > limit:
            raise p._Limit("VARIABLE_BUDGET" if name in ("leaves", "available_heads") else "TERM_BUDGET")
    if len(m["leaves"]) ** 2 > b.entries:
        raise p._Limit("MATRIX_ENTRY_BUDGET")
    if type(raw["flow_box"]) is not dict:
        raise p._Invalid("Explicit flow box required")
    if len(raw["flow_box"]) > b.nodes:
        raise p._Limit("VARIABLE_BUDGET")
    for row in m["terms"]:
        if type(row) is not dict:
            raise p._Invalid("Term object required")
        for key in ("descendant_leaves", "applies_to_leaves"):
            if type(row.get(key)) is not list:
                raise p._Invalid("Complete term incidence required")
            if len(row[key]) > b.nodes:
                raise p._Limit("VARIABLE_BUDGET")


def _certificate_shape(c, b):
    if type(c) is not dict:
        raise p._Invalid("Certificate object required")
    products = c.get("inverse_products")
    if type(products) is not dict or set(products) != {"left", "right"}:
        raise p._Invalid("Both full inverse products required")
    matrices = [(key, c.get(key)) for key in ("preconditioner", "inverse_witness", "jacobian", "derivative_map")]
    matrices += [("inverse_product_" + key, products[key]) for key in ("left", "right")]
    for key, rows in matrices:
        if type(rows) is not list:
            raise p._Invalid("Complete matrix required: " + key)
        if len(rows) > b.nodes:
            raise p._Limit("VARIABLE_BUDGET")
        count = 0
        for row in rows:
            if type(row) is not list:
                raise p._Invalid("Matrix row required")
            if len(row) > b.nodes:
                raise p._Limit("VARIABLE_BUDGET")
            count += len(row)
        if count > b.entries:
            raise p._Limit("MATRIX_ENTRY_BUDGET")
    if type(c.get("term_evidence")) is not list:
        raise p._Invalid("Complete term evidence required")
    if len(c["term_evidence"]) > b.edges:
        raise p._Limit("TERM_BUDGET")
    for key, kind in (("center", dict), ("center_residual", dict), ("center_image", dict),
                      ("root_enclosure", dict), ("inclusion_margins", dict), ("row_norm_upper", list)):
        if type(c.get(key)) is not kind:
            raise p._Invalid("Complete coordinate proof inventory required: " + key)
        if len(c[key]) > b.nodes:
            raise p._Limit("VARIABLE_BUDGET")


def _normalize(raw, b):
    _shape(raw, b)  # Recheck frozen objects after caller checkpoints.
    m = raw["model"]
    if set(m) != {"schema", "leaves", "coefficients", "terms", "available_heads",
                  "context_root", "physical_model_root", "assumptions"}:
        raise p._Invalid("Incomplete or extra model fields")
    if m["schema"] != MODEL_SCHEMA or m["assumptions"] != MODEL_ASSUMPTIONS:
        raise p._Invalid("Unsupported model law, units or applicability")
    for key in ("context_root", "physical_model_root"):
        if type(m[key]) is not str or not p._ROOT.fullmatch(m[key]):
            raise p._Invalid("Explicit context and physical model roots required")
    leaves = sorted(p._identity(x) for x in m["leaves"])
    if not leaves or len(set(leaves)) != len(leaves):
        raise p._Invalid("Nonempty unique leaf identities required")
    leafset = set(leaves)
    if set(m["available_heads"]) != leafset or set(raw["flow_box"]) != leafset:
        raise p._Invalid("Every leaf requires exactly one head and box coordinate")
    heads = {x: p._interval(m["available_heads"][x], b) for x in leaves}
    box = {x: p._interval(raw["flow_box"][x], b) for x in leaves}
    if any(lo <= 0 or lo >= hi for lo, hi in box.values()):
        raise p._Invalid("Nondegenerate strictly positive flow box required")
    coeff = {p._identity(k): p._interval(v, b) for k, v in sorted(m["coefficients"].items())}
    if not coeff or any(v[0] < 0 for v in coeff.values()):
        raise p._Invalid("Named nonnegative coefficient intervals required")
    terms, ids, used, covered, sets = [], set(), set(), set(), []
    for row in m["terms"]:
        b.tick("coupled_term_inventory")
        if set(row) != {"id", "coefficient_id", "descendant_leaves", "applies_to_leaves"}:
            raise p._Invalid("Exact term identity, coefficient and incidence required")
        name, a = p._identity(row["id"]), p._identity(row["coefficient_id"])
        d = sorted(p._identity(x) for x in row["descendant_leaves"])
        app = sorted(p._identity(x) for x in row["applies_to_leaves"])
        if name in ids or a not in coeff or not app or not d or len(set(d)) != len(d) or len(set(app)) != len(app):
            raise p._Invalid("Duplicate or missing term/coefficient/incidence")
        if not set(app) <= set(d) <= leafset:
            raise p._Invalid("Applicable leaves must be descendants in the declared inventory")
        ids.add(name); used.add(a); covered.update(app)
        sets.extend((set(d), set(app)))
        terms.append({"id": name, "coefficient_id": a, "descendant_leaves": d, "applies_to_leaves": app})
    if used != set(coeff) or covered != leafset:
        raise p._Invalid("Unused coefficient or leaf equation without a declared term")
    for i, first in enumerate(sets):
        for second in sets[i+1:]:
            b.tick("coupled_laminar_inventory")
            if first & second and not (first <= second or second <= first):
                raise p._Invalid("Declared tree subsets must be laminar")
    terms.sort(key=lambda row: row["id"])
    normalized = {**m, "leaves": leaves, "coefficients": {k: p._enc(v) for k, v in coeff.items()},
                  "available_heads": {k: p._enc(v) for k, v in heads.items()}, "terms": terms,
                  "assumptions": deepcopy(MODEL_ASSUMPTIONS)}
    encoded_box = {k: p._enc(v) for k, v in box.items()}
    model_root = p._hash(normalized, b)
    topology = {"leaves": leaves, "terms": terms, "coefficient_ids": sorted(coeff)}
    header = {"schema": CERTIFICATE_SCHEMA, "status": "CERTIFIED_BOX", "scope": SCOPE, "rule": RULE,
              "model_root": model_root, "topology_root": p._hash(topology, b),
              "parameter_root": p._hash({"coefficients": normalized["coefficients"], "available_heads": normalized["available_heads"]}, b),
              "box_root": p._hash(encoded_box, b),
              "query_root": p._hash({"model_root": model_root, "flow_box": encoded_box}, b),
              "context_root": m["context_root"], "physical_model_root": m["physical_model_root"],
              "assumptions": deepcopy(MODEL_ASSUMPTIONS), "limitations": deepcopy(LIMITATIONS),
              "counts": {"variables": len(leaves), "equations": len(leaves), "terms": len(terms),
                         "coefficients": len(coeff), "entries_per_matrix": len(leaves)**2},
              "inventories": {**topology, "equation_terms": {i: [t["id"] for t in terms if i in t["applies_to_leaves"]] for i in leaves}},
              "flow_box": encoded_box}
    return {"leaves": leaves, "coefficients": coeff, "heads": heads, "box": box, "terms": terms, "header": header}


def _plus(a, c, b):
    return b.add(a[0], c[0]), b.add(a[1], c[1])


def _minus(a, c, b):
    return b.sub(a[0], c[1]), b.sub(a[1], c[0])


def _times(a, c, b):
    products = [b.mul(x, y) for x in a for y in c]
    return min(products), max(products)


def _sum(values, b):
    answer = Q(0)
    for v in values:
        answer = b.add(answer, v)
    return answer


def _isum(values, b):
    answer = (Q(0), Q(0))
    for v in values:
        answer = _plus(answer, v, b)
    return answer


def _term_values(m, center, t, b):
    total = _sum((center[j] for j in t["descendant_leaves"]), b)
    span = _isum((m["box"][j] for j in t["descendant_leaves"]), b)
    a = m["coefficients"][t["coefficient_id"]]
    square = b.mul(total, total)
    loss = _times(a, (square, square), b)
    derivative = _times((Q(2), Q(2)), _times(a, span, b), b)
    return total, span, loss, derivative


def _produce_polynomial(m, center, b):
    names = m["leaves"]; n = len(names)
    f = {i: (-m["heads"][i][1], -m["heads"][i][0]) for i in names}
    j = [[(Q(0), Q(0)) for _ in names] for _ in names]
    rows = []
    for t in m["terms"]:
        b.tick("coupled_producer_term")
        total, span, loss, derivative = _term_values(m, center, t, b)
        rows.append({"id": t["id"], "subtree_at_center": str(total), "subtree_in_box": p._enc(span),
                     "loss_at_center": p._enc(loss), "derivative_in_box": p._enc(derivative)})
        for row in range(n):
            if names[row] in t["applies_to_leaves"]:
                f[names[row]] = _plus(f[names[row]], loss, b)
                for col in range(n):
                    if names[col] in t["descendant_leaves"]:
                        j[row][col] = _plus(j[row][col], derivative, b)
    return rows, f, j


def _equal(a, c, b, message):
    if p._hash(a, b) != p._hash(c, b):
        raise p._Invalid(message)


def _check_polynomial(m, center, rows, b):
    # Independent row/column reconstruction, not the producer accumulation loop.
    if len(rows) != len(m["terms"]):
        raise p._Invalid("Incomplete term denominator")
    loss, derivative = {}, {}
    for t, row in zip(m["terms"], rows):
        b.tick("coupled_check_term")
        total = Q(0); lower = Q(0); upper = Q(0)
        for name in m["leaves"]:
            if name in t["descendant_leaves"]:
                total = b.add(total, center[name])
                lower = b.add(lower, m["box"][name][0]); upper = b.add(upper, m["box"][name][1])
        a = m["coefficients"][t["coefficient_id"]]
        sq = b.mul(total, total)
        loss[t["id"]] = (b.mul(a[0], sq), b.mul(a[1], sq))
        derivative[t["id"]] = (b.mul(b.mul(Q(2), a[0]), lower), b.mul(b.mul(Q(2), a[1]), upper))
        expected = {"id": t["id"], "subtree_at_center": str(total), "subtree_in_box": p._enc((lower, upper)),
                    "loss_at_center": p._enc(loss[t["id"]]), "derivative_in_box": p._enc(derivative[t["id"]])}
        _equal(row, expected, b, "Forged term identity, descendant sum, loss or derivative")
    f, j = {}, []
    for i in m["leaves"]:
        f[i] = _minus(_isum((loss[t["id"]] for t in m["terms"] if i in t["applies_to_leaves"]), b), m["heads"][i], b)
        j.append([_isum((derivative[t["id"]] for t in m["terms"]
                        if i in t["applies_to_leaves"] and col in t["descendant_leaves"]), b) for col in m["leaves"]])
    return f, j


def _inverse(matrix, b):
    n = len(matrix)
    rows = [list(row) + [Q(int(i == j)) for j in range(n)] for i, row in enumerate(matrix)]
    for col in range(n):
        b.tick("coupled_producer_inverse")
        pivot = next((i for i in range(col, n) if rows[i][col]), None)
        if pivot is None:
            raise _NoProof("SINGULAR_MIDPOINT_PRECONDITIONER")
        rows[col], rows[pivot] = rows[pivot], rows[col]
        divisor = rows[col][col]
        rows[col] = [b.div(v, divisor) for v in rows[col]]
        for i in range(n):
            if i != col:
                factor = rows[i][col]
                rows[i] = [b.sub(v, b.mul(factor, other)) for v, other in zip(rows[i], rows[col])]
    return [row[n:] for row in rows]


def _mm(a, c, b):
    n = len(a)
    return [[_sum((b.mul(a[i][k], c[k][j]) for k in range(n)), b) for j in range(n)] for i in range(n)]


def _encode_matrix(matrix, interval=False):
    return [[p._enc(v) if interval else str(v) for v in row] for row in matrix]


def _read_matrix(raw, n, b):
    if type(raw) is not list or len(raw) != n or any(type(row) is not list or len(row) != n for row in raw):
        raise p._Invalid("Exact full square matrix inventory required")
    return [[p._q(v, b) for v in row] for row in raw]


def _proof_map(m, center, f, j, r, inverse, b):
    n = len(m["leaves"])
    left, right = _mm(r, inverse, b), _mm(inverse, r, b)
    identity = [[Q(int(i == k)) for k in range(n)] for i in range(n)]
    if left != identity or right != identity:
        raise p._Invalid("Preconditioner is not backed by an exact inverse witness")
    derivative = []
    for i in range(n):
        row = []
        for col in range(n):
            product = _isum((_times((r[i][k], r[i][k]), j[k][col], b) for k in range(n)), b)
            delta = Q(int(i == col))
            row.append(_minus((delta, delta), product, b))
        derivative.append(row)
    row_norms = [_sum((max(abs(v[0]), abs(v[1])) for v in row), b) for row in derivative]
    norm = max(row_norms)
    images, krawczyk, margins = {}, {}, {}
    for i, name in enumerate(m["leaves"]):
        b.tick("coupled_fixed_point_image")
        rf = _isum((_times((r[i][k], r[i][k]), f[node], b) for k, node in enumerate(m["leaves"])), b)
        image = _minus((center[name], center[name]), rf, b)
        error = _isum((_times(derivative[i][k], _minus(m["box"][node], (center[node], center[node]), b), b)
                      for k, node in enumerate(m["leaves"])), b)
        enclosure = _plus(image, error, b)
        images[name] = p._enc(image); krawczyk[name] = p._enc(enclosure)
        margins[name] = {"lower": str(b.sub(enclosure[0], m["box"][name][0])),
                         "upper": str(b.sub(m["box"][name][1], enclosure[1]))}
    return {"inverse_products": {"left": _encode_matrix(left), "right": _encode_matrix(right)},
            "derivative_map": _encode_matrix(derivative, True), "center_image": images,
            "root_enclosure": krawczyk, "inclusion_margins": margins,
            "row_norm_upper": [str(x) for x in row_norms], "contraction_norm_upper": str(norm)}


def _admissible(proof, b):
    if p._q(proof["contraction_norm_upper"], b) >= 1:
        raise _NoProof("CONTRACTION_NOT_ESTABLISHED")
    for pair in proof["inclusion_margins"].values():
        if p._q(pair["lower"], b) <= 0 or p._q(pair["upper"], b) <= 0:
            raise _NoProof("STRICT_BOX_INCLUSION_NOT_ESTABLISHED")


def _final(model, box, input_root, b, certificate=None, certificate_hash=None):
    b.callback = None  # No caller code after this point.
    if p._snapshot({"model": model, "flow_box": box}, b.input_bytes, b, "passive_input", retain=False)[0] != input_root:
        raise p._Invalid("Caller model or flow box changed before completion")
    if certificate is not None and p._snapshot(certificate, b.certificate_bytes, b, "coupled_certificate", retain=False)[0] != certificate_hash:
        raise p._Invalid("Caller certificate changed before completion")


def _failure(exc, b, verify=False):
    if b is not None and exc is b.external_error:
        raise exc
    return {"status": "UNKNOWN" if isinstance(exc, (p._Limit, _NoProof)) else "FAIL" if verify else "INVALID_INPUT",
            "reason": str(exc), "scope": SCOPE, "proof_complete": False,
            "work": 0 if b is None else b.used, "limitations": deepcopy(LIMITATIONS)}


def compile_coupled_tree_pressure(model, flow_box, *, max_leaves=16, max_terms=128, max_matrix_entries=256,
        max_work=2_000_000, max_rational_bits=4096, max_input_bytes=1_048_576,
        max_certificate_bytes=16_777_216, checkpoint=None):
    b = None
    try:
        b = _Budget(max_leaves, max_terms, max_matrix_entries, max_work, max_rational_bits, max_input_bytes, max_certificate_bytes, checkpoint)
        raw = {"model": model, "flow_box": flow_box}; _shape(raw, b)
        input_root, frozen = p._snapshot(raw, b.input_bytes, b, "passive_input")
        m = _normalize(frozen, b)
        center = {i: b.div(b.add(*m["box"][i]), Q(2)) for i in m["leaves"]}
        rows, f, j = _produce_polynomial(m, center, b)
        # The exact midpoint derivative is only a proposed inverse witness.
        mid = deepcopy(m)
        mid["coefficients"] = {a: (b.div(b.add(*v), Q(2)),)*2 for a, v in m["coefficients"].items()}
        mid["box"] = {i: (center[i], center[i]) for i in m["leaves"]}
        _, _, point_j = _produce_polynomial(mid, center, b)
        inverse = [[v[0] for v in row] for row in point_j]
        r = _inverse(inverse, b)
        proof = _proof_map(m, center, f, j, r, inverse, b)
        _admissible(proof, b)
        certificate = {**m["header"], "center": {i: str(v) for i, v in center.items()},
                       "term_evidence": rows, "center_residual": {i: p._enc(v) for i, v in f.items()},
                       "jacobian": _encode_matrix(j, True), "preconditioner": _encode_matrix(r),
                       "inverse_witness": _encode_matrix(inverse), **proof}
        certificate["certificate_root"] = p._hash(certificate, b)
        _certificate_shape(certificate, b)
        b.tick("coupled_producer_complete")
        _final(model, flow_box, input_root, b)
        return certificate
    except (p._Invalid, p._Limit, _NoProof, ValueError, TypeError, KeyError, OverflowError) as exc:
        return _failure(exc, b)


def verify_coupled_tree_pressure(model, flow_box, certificate, *, max_leaves=16, max_terms=128, max_matrix_entries=256,
        max_work=2_000_000, max_rational_bits=4096, max_input_bytes=1_048_576,
        max_certificate_bytes=16_777_216, checkpoint=None):
    b = None
    try:
        b = _Budget(max_leaves, max_terms, max_matrix_entries, max_work, max_rational_bits, max_input_bytes, max_certificate_bytes, checkpoint)
        raw = {"model": model, "flow_box": flow_box}; _shape(raw, b); _certificate_shape(certificate, b)
        input_root, frozen = p._snapshot(raw, b.input_bytes, b, "passive_input")
        certificate_hash, packet = p._snapshot(certificate, b.certificate_bytes, b, "coupled_certificate")
        _certificate_shape(packet, b)
        m = _normalize(frozen, b)
        fields = {"center", "term_evidence", "center_residual", "jacobian", "preconditioner", "inverse_witness",
                  "inverse_products", "derivative_map", "center_image", "root_enclosure", "inclusion_margins",
                  "row_norm_upper", "contraction_norm_upper", "certificate_root"}
        if set(packet) != set(m["header"]) | fields:
            raise p._Invalid("Incomplete or extra certificate fields")
        _equal({k: packet[k] for k in m["header"]}, m["header"], b, "Wrong model, domain, incidence, box, scope or root")
        if type(packet["certificate_root"]) is not str or not p._ROOT.fullmatch(packet["certificate_root"]):
            raise p._Invalid("Malformed certificate content root")
        if p._hash({k: v for k, v in packet.items() if k != "certificate_root"}, b) != packet["certificate_root"]:
            raise p._Invalid("Certificate content root mismatch")
        if type(packet["center"]) is not dict or set(packet["center"]) != set(m["leaves"]):
            raise p._Invalid("Complete center coordinate inventory required")
        center = {i: p._q(packet["center"][i], b) for i in m["leaves"]}
        if any(not m["box"][i][0] < v < m["box"][i][1] for i, v in center.items()):
            raise p._Invalid("Center must lie strictly within the supplied box")
        f, j = _check_polynomial(m, center, packet["term_evidence"], b)
        _equal(packet["center_residual"], {i: p._enc(v) for i, v in f.items()}, b, "Wrong full center residual")
        _equal(packet["jacobian"], _encode_matrix(j, True), b, "Wrong full nonsymmetric Jacobian")
        r = _read_matrix(packet["preconditioner"], len(m["leaves"]), b)
        inverse = _read_matrix(packet["inverse_witness"], len(m["leaves"]), b)
        proof = _proof_map(m, center, f, j, r, inverse, b)
        for key, value in proof.items():
            _equal(packet[key], value, b, "Forged fixed-point proof field: " + key)
        _admissible(proof, b)
        b.tick("coupled_verifier_complete")
        _final(model, flow_box, input_root, b, certificate, certificate_hash)
        return {"status": "PASS", "scope": SCOPE, "proof_complete": True,
                "certificate_root": packet["certificate_root"], "model_root": m["header"]["model_root"],
                "query_root": m["header"]["query_root"], "counts": deepcopy(m["header"]["counts"]),
                "root_enclosure": deepcopy(proof["root_enclosure"]), "contraction_norm_upper": proof["contraction_norm_upper"],
                "limitations": deepcopy(LIMITATIONS), "work": b.used}
    except (p._Invalid, p._Limit, _NoProof, ValueError, TypeError, KeyError, OverflowError) as exc:
        return _failure(exc, b, True)
