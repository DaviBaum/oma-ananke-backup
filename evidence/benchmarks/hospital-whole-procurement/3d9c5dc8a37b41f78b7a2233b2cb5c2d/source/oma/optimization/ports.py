"""Checked exact rational linear port elimination (original Pages Prompt 6).

PO6/PO31: Schur/Kron elimination; PO14: residual bounds with conditioning.
Singular interiors retain an exact affine relation, not an invented inverse.
The model is a supplied mathematical matrix. Bindings identify its declared
regime, units and domain; they are not proofs of physical applicability.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction as Q
from typing import Mapping

from .finite import _root, _token


@dataclass(frozen=True)
class LinearPortModel:
    matrix: tuple[tuple[object, ...], ...]
    boundary_indices: tuple[int, ...]
    internal_loads: tuple[object, ...]
    model_bindings: Mapping[str, object]


class _Limit(Exception):
    pass


def _q(value):
    if isinstance(value, bool) or not isinstance(value, (int, str, Q)):
        raise ValueError("Use explicit integer or rational strings, not binary floats")
    return Q(value)


def _mat(value, rows, cols):
    value = tuple(tuple(row) for row in value)
    if len(value) != rows or any(len(row) != cols for row in value):
        raise ValueError("Matrix dimensions")
    return [[_q(x) for x in row] for row in value]


def _eye(n):
    return [[Q(i == j) for j in range(n)] for i in range(n)]


def _mm(a, b, columns=None):
    width = len(b[0]) if b else columns
    if width is None:
        raise ValueError("Empty product needs output dimension")
    return [[sum((a[i][k] * b[k][j] for k in range(len(b))), Q(0))
             for j in range(width)] for i in range(len(a))]


def _mv(a, x):
    return [sum((v * w for v, w in zip(row, x)), Q(0)) for row in a]


def _inverse(a):
    n = len(a)
    aug = [list(row) + identity for row, identity in zip(a, _eye(n))]
    for col in range(n):
        pivot = next((i for i in range(col, n) if aug[i][col]), None)
        if pivot is None:
            return None
        aug[col], aug[pivot] = aug[pivot], aug[col]
        scale = aug[col][col]
        aug[col] = [x / scale for x in aug[col]]
        for i in range(n):
            if i != col:
                factor = aug[i][col]
                aug[i] = [x - factor*y for x, y in zip(aug[i], aug[col])]
    return [row[n:] for row in aug]


def _prepare(model, context_root, max_dimension, max_work):
    if type(max_dimension) is not int or not 1 <= max_dimension <= 256:
        raise ValueError("Dimension budget must be in 1..256")
    if type(max_work) is not int or max_work < 0:
        raise ValueError("Nonnegative work budget")
    n = len(model.matrix)
    # The declared conservative bound covers producer/checker matrix work.
    if n > max_dimension or 16*n**3 + 16*n**2 > max_work:
        raise _Limit
    if n == 0:
        raise ValueError("Nonempty mathematical system")
    a = _mat(model.matrix, n, n)
    boundary = tuple(model.boundary_indices)
    if (not boundary or len(set(boundary)) != len(boundary)
            or any(type(i) is not int or not 0 <= i < n for i in boundary)):
        raise ValueError("Distinct valid boundary indices")
    internal = tuple(i for i in range(n) if i not in boundary)
    loads = tuple(_q(x) for x in model.internal_loads)
    if len(loads) != len(internal):
        raise ValueError("One load for every interior coordinate")
    bindings = dict(model.model_bindings)
    required = {"model_id", "units", "regime", "parameter_domain", "scenario_domain", "source_root"}
    if not required <= set(bindings) or any(bindings[k] is None or bindings[k] == "" for k in required):
        raise ValueError("Explicit model, units, regime, domains and source root required")
    binding_token = _token(bindings)
    payload = (a, boundary, loads, binding_token)
    root = _root(context_root, ("oma.linear-port/1", payload))
    return a, boundary, internal, loads, root, binding_token


def _blocks(a, boundary, internal):
    take = lambda rows, cols: [[a[i][j] for j in cols] for i in rows]
    return take(boundary, boundary), take(boundary, internal), take(internal, boundary), take(internal, internal)


def _enc(a):
    return [[str(x) for x in row] for row in a]


def _vec(value, size):
    value = [_q(x) for x in value]
    if len(value) != size:
        raise ValueError("Vector dimensions")
    return value


def _projection_inputs(a, boundary, internal, loads):
    bpos, ipos = {i: j for j, i in enumerate(boundary)}, {i: j for j, i in enumerate(internal)}
    c = [[row[j] for j in internal] for row in a]
    d = [[*([row[j] for j in boundary]), *(-Q(i == j) for j in boundary)] for i, row in enumerate(a)]
    rhs = [Q(0) if i in bpos else loads[ipos[i]] for i in range(len(a))]
    return c, d, rhs


def compile_linear_port(model, *, context_root, max_dimension=64, max_work=5_000_000):
    """Eliminate the interior exactly, retaining singular compatibility relations."""
    try:
        a, boundary, internal, loads, root, bindings = _prepare(model, context_root, max_dimension, max_work)
    except _Limit:
        return {"status": "UNKNOWN", "reason": "LINEAR_PORT_WORK_BUDGET"}
    bb, bi, ib, ii = _blocks(a, boundary, internal)
    inverse = _inverse(ii)
    base = {"schema": "oma.linear-port/1", "status": "EXACT_LINEAR_PORT", "root": root,
            "model_bindings": bindings, "boundary_indices": list(boundary), "internal_indices": list(internal),
            "scope": "SUPPLIED_EXACT_RATIONAL_LINEAR_MODEL", "physical_applicability_verified": False}
    if inverse is not None:
        reconstruction = [[-x for x in row] for row in _mm(inverse, ib, len(boundary))]
        offset = _mv(inverse, loads)
        term = _mm(bi, reconstruction, len(boundary))
        response = [[x+y for x, y in zip(row, delta)] for row, delta in zip(bb, term)]
        force_offset = _mv(bi, offset)
        return {**base, "method": "SCHUR", "internal_inverse": _enc(inverse),
                "response_matrix": _enc(response), "force_offset": list(map(str, force_offset)),
                "reconstruction_matrix": _enc(reconstruction), "reconstruction_offset": list(map(str, offset))}

    # Row elimination of *all* original equations with interior columns first.
    # C ui + D (ub,fb) = rhs. Invertible row operations yield a rank-factorized
    # C whose lower zero rows give exactly the externally realizable relation.
    c, d, rhs = _projection_inputs(a, boundary, internal, loads)
    reduced, transform, rank, pivots = [row[:] for row in c], _eye(len(a)), 0, []
    for col in range(len(internal)):
        pivot = next((i for i in range(rank, len(a)) if reduced[i][col]), None)
        if pivot is None:
            continue
        for rows in (reduced, transform):
            rows[rank], rows[pivot] = rows[pivot], rows[rank]
        divisor = reduced[rank][col]
        reduced[rank] = [x/divisor for x in reduced[rank]]
        transform[rank] = [x/divisor for x in transform[rank]]
        for i in range(len(a)):
            if i != rank:
                factor = reduced[i][col]
                reduced[i] = [x-factor*y for x, y in zip(reduced[i], reduced[rank])]
                transform[i] = [x-factor*y for x, y in zip(transform[i], transform[rank])]
        pivots.append(col)
        rank += 1
    td, trhs = _mm(transform, d), _mv(transform, rhs)
    return {**base, "method": "AFFINE_RELATION", "row_transform": _enc(transform),
            "row_transform_inverse": _enc(_inverse(transform)), "reduced_internal": _enc(reduced),
            "transformed_external": _enc(td), "transformed_rhs": list(map(str, trhs)),
            "internal_pivot_columns": pivots,
            "constraint_matrix": _enc(td[rank:]), "constraint_rhs": list(map(str, trhs[rank:]))}


def verify_linear_port(model, certificate, *, context_root, max_dimension=64, max_work=5_000_000):
    """Check matrix identities; never rerun inverse construction or elimination."""
    try:
        a, boundary, internal, loads, root, bindings = _prepare(model, context_root, max_dimension, max_work)
        n, b, k = len(a), len(boundary), len(internal)
        if (certificate.get("schema") != "oma.linear-port/1" or certificate.get("status") != "EXACT_LINEAR_PORT"
                or certificate.get("root") != root or certificate.get("model_bindings") != bindings
                or certificate.get("boundary_indices") != list(boundary)
                or certificate.get("internal_indices") != list(internal)
                or certificate.get("scope") != "SUPPLIED_EXACT_RATIONAL_LINEAR_MODEL"
                or certificate.get("physical_applicability_verified") is not False):
            raise ValueError("Certificate binding or scope")
        bb, bi, ib, ii = _blocks(a, boundary, internal)
        if certificate["method"] == "SCHUR":
            inverse = _mat(certificate["internal_inverse"], k, k)
            if _mm(ii, inverse, k) != _eye(k) or _mm(inverse, ii, k) != _eye(k):
                raise ValueError("Internal inverse identity")
            reconstruction = _mat(certificate["reconstruction_matrix"], k, b)
            offset = _vec(certificate["reconstruction_offset"], k)
            # Check original equations directly, not the generator's formula.
            if _mm(ii, reconstruction, b) != [[-x for x in row] for row in ib] or _mv(ii, offset) != list(loads):
                raise ValueError("Interior reconstruction identity")
            response = _mat(certificate["response_matrix"], b, b)
            actual = _mm(bi, reconstruction, b)
            if response != [[x+y for x, y in zip(row, delta)] for row, delta in zip(bb, actual)]:
                raise ValueError("Boundary response identity")
            if _vec(certificate["force_offset"], b) != _mv(bi, offset):
                raise ValueError("Boundary load identity")
        elif certificate["method"] == "AFFINE_RELATION":
            transform = _mat(certificate["row_transform"], n, n)
            tinv = _mat(certificate["row_transform_inverse"], n, n)
            if _mm(transform, tinv) != _eye(n) or _mm(tinv, transform) != _eye(n):
                raise ValueError("Row transform not invertible")
            c, d, rhs = _projection_inputs(a, boundary, internal, loads)
            reduced = _mat(certificate["reduced_internal"], n, k)
            td = _mat(certificate["transformed_external"], n, 2*b)
            trhs = _vec(certificate["transformed_rhs"], n)
            if reduced != _mm(transform, c, k) or td != _mm(transform, d) or trhs != _mv(transform, rhs):
                raise ValueError("Transformed original equations")
            pivots = tuple(certificate["internal_pivot_columns"])
            rank = len(pivots)
            if (rank > min(n, k) or len(set(pivots)) != rank
                    or any(type(i) is not int or not 0 <= i < k for i in pivots)):
                raise ValueError("Pivot identities")
            if any(reduced[i][col] != Q(i == j) for j, col in enumerate(pivots) for i in range(n)):
                raise ValueError("Pivot columns are not identity")
            if any(any(row) for row in reduced[rank:]):
                raise ValueError("Uneliminated internal constraint")
            if (_mat(certificate["constraint_matrix"], n-rank, 2*b) != td[rank:]
                    or _vec(certificate["constraint_rhs"], n-rank) != trhs[rank:]):
                raise ValueError("External projected relation")
        else:
            raise ValueError("Unknown method")
        return {"status": "PASS", "root": root, "scope": "SUPPLIED_EXACT_RATIONAL_LINEAR_MODEL",
                "method": certificate["method"], "independent_matrix_identity_check": True}
    except _Limit:
        return {"status": "UNKNOWN", "reason": "LINEAR_PORT_WORK_BUDGET"}
    except (KeyError, TypeError, ValueError, IndexError, ZeroDivisionError):
        return {"status": "FAIL", "reason": "INVALID_LINEAR_PORT_CERTIFICATE"}


def reconstruct_linear_port(model, certificate, boundary_values, boundary_forces=None, *, context_root):
    """Produce and replay an interior witness; omitted force is allowed for Schur."""
    if verify_linear_port(model, certificate, context_root=context_root)["status"] != "PASS":
        return {"status": "UNKNOWN", "reason": "UNCHECKED_LINEAR_PORT"}
    a, boundary, internal, loads, _, _ = _prepare(model, context_root, 64, 5_000_000)
    b, k, n = len(boundary), len(internal), len(a)
    ub = _vec(boundary_values, b)
    if certificate["method"] == "SCHUR":
        ui = [x+y for x, y in zip(_mv(_mat(certificate["reconstruction_matrix"], k, b), ub),
                                  _vec(certificate["reconstruction_offset"], k))]
        fb = [x+y for x, y in zip(_mv(_mat(certificate["response_matrix"], b, b), ub),
                                  _vec(certificate["force_offset"], b))]
        if boundary_forces is not None and fb != _vec(boundary_forces, b):
            return {"status": "NO_REALIZATION", "reason": "BOUNDARY_FORCE_CONSTRAINT"}
    else:
        if boundary_forces is None:
            return {"status": "UNKNOWN", "reason": "RELATIONAL_BOUNDARY_FORCE_REQUIRED"}
        fb = _vec(boundary_forces, b)
        ext = ub + fb
        pivots = certificate["internal_pivot_columns"]
        constraints = _mat(certificate["constraint_matrix"], n-len(pivots), 2*b)
        if _mv(constraints, ext) != _vec(certificate["constraint_rhs"], n-len(pivots)):
            return {"status": "NO_REALIZATION", "reason": "EXACT_AFFINE_COMPATIBILITY"}
        td = _mat(certificate["transformed_external"], n, 2*b)
        trhs = _vec(certificate["transformed_rhs"], n)
        ui = [Q(0)]*k
        for row, pivot in enumerate(pivots):
            ui[pivot] = trhs[row] - sum(x*y for x, y in zip(td[row], ext))
    full = [Q(0)]*n
    for i, value in zip(boundary, ub):
        full[i] = value
    for i, value in zip(internal, ui):
        full[i] = value
    force = _mv(a, full)
    if [force[i] for i in boundary] != fb or [force[i] for i in internal] != list(loads):
        return {"status": "FAIL", "reason": "FULL_ORIGINAL_SYSTEM_REPLAY"}
    return {"status": "REALIZATION_CHECKED", "full_state": list(map(str, full)),
            "boundary_forces": list(map(str, fb)), "internal_state": list(map(str, ui)),
            "scope": "SUPPLIED_EXACT_RATIONAL_LINEAR_MODEL"}


def certify_linear_residual(model, certificate, boundary_values, approximate_interior, *, context_root):
    """Exact residual and inverse-norm error bounds for a checked Schur interior.

    A singular relation has no uniform invertible-interior error bound here.
    This certifies algebraic solve/reduction error, not model discrepancy.
    """
    if verify_linear_port(model, certificate, context_root=context_root)["status"] != "PASS":
        return {"status": "UNKNOWN", "reason": "UNCHECKED_LINEAR_PORT"}
    if certificate["method"] != "SCHUR":
        return {"status": "UNKNOWN", "reason": "SINGULAR_INTERIOR_NEEDS_SEPARATE_STABILITY_THEOREM"}
    a, boundary, internal, loads, root, _ = _prepare(model, context_root, 64, 5_000_000)
    _, bi, ib, ii = _blocks(a, boundary, internal)
    ub = _vec(boundary_values, len(boundary))
    approx = _vec(approximate_interior, len(internal))
    inverse = _mat(certificate["internal_inverse"], len(internal), len(internal))
    residual = [f-g-h for f, g, h in zip(loads, _mv(ib, ub), _mv(ii, approx))]
    component = _mv([[abs(x) for x in row] for row in inverse], [abs(x) for x in residual])
    norm = max((sum(abs(x) for x in row) for row in inverse), default=Q(0))
    residual_norm = max(map(abs, residual), default=Q(0))
    force_error = _mv([[abs(x) for x in row] for row in bi], component)
    return {"status": "ERROR_BOUND_CHECKED", "root": root, "residual": list(map(str, residual)),
            "interior_component_error": list(map(str, component)), "boundary_force_error": list(map(str, force_error)),
            "inverse_infinity_norm": str(norm), "residual_infinity_norm": str(residual_norm),
            "interior_infinity_error": str(norm*residual_norm),
            "stability_lower_infinity": str(1/norm) if norm else None,
            "error_source": "EXACT_LINEAR_SOLVE_OR_REDUCTION_ONLY", "physical_discrepancy_included": False}


def compile_kron_network(nodes, edges, boundary_nodes, *, context_root, model_bindings, max_dimension=64, max_work=5_000_000):
    """Positive undirected conductance graph -> exact boundary response/relation.

    Parallel conductances add. Disconnected internal components remain explicit
    singular modes in AFFINE_RELATION; no numerical grounding is added.
    """
    nodes, edges, boundary_nodes = tuple(nodes), tuple(edges), tuple(boundary_nodes)
    if not nodes or any(not isinstance(x, str) or not x for x in nodes) or len(set(nodes)) != len(nodes):
        raise ValueError("Distinct named network nodes")
    if len(nodes) > max_dimension:
        return {"status": "UNKNOWN", "reason": "LINEAR_PORT_WORK_BUDGET"}
    index = {x: i for i, x in enumerate(nodes)}
    if any(x not in index for x in boundary_nodes):
        raise ValueError("Unknown boundary node")
    a = [[Q(0)]*len(nodes) for _ in nodes]
    canonical_edges = []
    for u, v, raw in edges:
        g = _q(raw)
        if u not in index or v not in index or u == v or g <= 0:
            raise ValueError("Positive conductance between distinct declared nodes")
        i, j = index[u], index[v]
        a[i][i] += g
        a[j][j] += g
        a[i][j] -= g
        a[j][i] -= g
        canonical_edges.append((u, v, str(g)))
    bindings = dict(model_bindings, network_nodes=nodes, network_edges=tuple(canonical_edges))
    model = LinearPortModel(tuple(map(tuple, a)), tuple(index[x] for x in boundary_nodes),
                            (Q(0),)*(len(nodes)-len(boundary_nodes)), bindings)
    certificate = compile_linear_port(model, context_root=context_root, max_dimension=max_dimension, max_work=max_work)
    return {"status": certificate["status"], "model": model, "certificate": certificate,
            "scope": "SUPPLIED_POSITIVE_LINEAR_CONDUCTANCE_NETWORK"}


def verify_kron_network(nodes, edges, boundary_nodes, model, certificate, *, context_root, model_bindings):
    """Independently verify the edge-incidence quadratic form and port proof."""
    try:
        nodes, edges, boundary_nodes = tuple(nodes), tuple(edges), tuple(boundary_nodes)
        if not nodes or len(set(nodes)) != len(nodes) or any(not isinstance(x, str) or not x for x in nodes):
            raise ValueError("Network nodes")
        if len(nodes) > 64:
            return {"status": "UNKNOWN", "reason": "LINEAR_PORT_WORK_BUDGET"}
        if (not boundary_nodes or len(set(boundary_nodes)) != len(boundary_nodes)
                or any(x not in nodes for x in boundary_nodes)):
            raise ValueError("Boundary nodes")
        incidence, canonical_edges = [], []
        for u, v, raw in edges:
            g = _q(raw)
            if u not in nodes or v not in nodes or u == v or g <= 0:
                raise ValueError("Conductance edge")
            incidence.append((g, [Q(x == u)-Q(x == v) for x in nodes]))
            canonical_edges.append((u, v, str(g)))
        expected = [[sum((g*row[i]*row[j] for g, row in incidence), Q(0))
                     for j in range(len(nodes))] for i in range(len(nodes))]
        if (_mat(model.matrix, len(nodes), len(nodes)) != expected
                or tuple(model.boundary_indices) != tuple(nodes.index(x) for x in boundary_nodes)
                or _vec(model.internal_loads, len(nodes)-len(boundary_nodes)) != [Q(0)]*(len(nodes)-len(boundary_nodes))):
            raise ValueError("Original edge-incidence identity")
        expected_bindings = dict(model_bindings, network_nodes=nodes, network_edges=tuple(canonical_edges))
        if _token(dict(model.model_bindings)) != _token(expected_bindings):
            raise ValueError("Network/model binding")
        result = verify_linear_port(model, certificate, context_root=context_root)
        if result["status"] != "PASS":
            return result
        return {**result, "scope": "SUPPLIED_POSITIVE_LINEAR_CONDUCTANCE_NETWORK",
                "positive_edge_energy_identity_checked": True, "exact_row_sum_zero": True,
                "singular_modes_retained": certificate["method"] == "AFFINE_RELATION"}
    except (KeyError, ValueError, TypeError, ZeroDivisionError):
        return {"status": "FAIL", "reason": "INVALID_LINEAR_NETWORK_CERTIFICATE"}
