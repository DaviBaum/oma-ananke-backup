"""Exact local-box through-cut support, with an independent cell checker.

This kernel proves a represented rational set identity. Source roots are bound
identities, not authenticated authority, frame evidence or native IFC equality.
"""
from copy import deepcopy
from fractions import Fraction
from itertools import combinations, product
from math import isfinite, prod
import re

from .finite import _root, _token


STATUS = "EXACT_RECTILINEAR_THROUGH_OPENING"
SCOPE = "REGULARIZED_LOCAL_RATIONAL_HOST_BOX_DIFFERENCE"
LIMITATIONS = {
    "source_geometry_authenticity_checked": False,
    "frame_and_units_applicability_checked": False,
    "authorization_authenticity_checked": False,
    "native_export_geometry_equality_checked": False,
    "structural_or_fire_approval_checked": False,
    "candidate_acceptance_authority": False,
}
ROOT_FIELDS = {"source", "host", "frame", "authorization"}


def _q(value):
    if type(value) not in (str, int, float, Fraction):
        raise ValueError("Coordinates must be exact rational numbers or finite floats")
    if isinstance(value, float) and not isfinite(value):
        raise ValueError("Nonfinite coordinate")
    if isinstance(value, str):
        if len(value) > 4096:
            raise ValueError("Coordinate text budget exceeded")
        exponent = re.search(r"[eE]([+-]?\d+)\s*$", value)
        if exponent and abs(int(exponent[1])) > 1024:
            raise ValueError("Coordinate exponent budget exceeded")
    try:
        result = Fraction(value)
    except (ValueError, ZeroDivisionError, OverflowError) as exc:
        raise ValueError("Invalid rational coordinate") from exc
    if max(result.numerator.bit_length(), result.denominator.bit_length()) > 4096:
        raise ValueError("Coordinate rational-bit budget exceeded")
    return result


def _box(bounds):
    if not isinstance(bounds, (tuple, list)) or len(bounds) != 2:
        raise ValueError("Box needs min3 and max3")
    if any(not isinstance(row, (tuple, list)) or len(row) != 3 for row in bounds):
        raise ValueError("Box needs three coordinates per endpoint")
    lo, hi = (tuple(map(_q, row)) for row in bounds)
    if any(a >= b for a, b in zip(lo, hi)):
        raise ValueError("Every box extent must be strictly positive")
    return lo, hi


def _json_box(box):
    return [[str(q) for q in row] for row in box]


def _volume(box):
    return prod((b - a for a, b in zip(*box)), start=Fraction(1))


def _prepare(host_bounds_local, opening_bounds_local, through_axis, context_root, source_roots):
    host, opening = _box(host_bounds_local), _box(opening_bounds_local)
    if type(through_axis) is not int or through_axis not in range(3):
        raise ValueError("Through axis must be integer 0, 1 or 2")
    if not isinstance(context_root, str) or not context_root:
        raise ValueError("Explicit immutable context root required")
    if (not isinstance(source_roots, dict) or set(source_roots) != ROOT_FIELDS
            or any(not isinstance(v, str) or not v for v in source_roots.values())):
        raise ValueError("Complete nonempty source, host, frame and authorization identities required")
    transverse = tuple(i for i in range(3) if i != through_axis)
    if any(not host[0][i] < opening[0][i] < opening[1][i] < host[1][i] for i in transverse):
        raise ValueError("Opening footprint must be strictly interior to the host")
    if not opening[0][through_axis] < host[0][through_axis] < host[1][through_axis] < opening[1][through_axis]:
        raise ValueError("Opening must extend strictly beyond both thickness faces")
    removed = (tuple(max(a, b) for a, b in zip(host[0], opening[0])),
               tuple(min(a, b) for a, b in zip(host[1], opening[1])))
    manifest = {"schema": "oma.rectilinear-opening-input/1", "units": "local_m",
        "host_bounds_local": _json_box(host), "opening_bounds_local": _json_box(opening),
        "through_axis": through_axis, "context_root": context_root,
        "source_roots": deepcopy(source_roots),
        "float_interpretation": "EXACT_BINARY_VALUE; SOURCE_DECIMAL_RATIONALS_SHOULD_USE_STRINGS"}
    return host, opening, removed, transverse, manifest, _root(context_root, manifest)


def compile_rectilinear_opening(host_bounds_local, opening_bounds_local, *, through_axis, context_root, source_roots):
    """Construct four closed strips for a strictly interior rectangular through-cut.

    Bounds are [min3,max3] in an already declared common local metre frame.
    Invalid/unsupported inputs raise ValueError; no physical feasibility follows.
    """
    host, opening, removed, transverse, manifest, root = _prepare(
        host_bounds_local, opening_bounds_local, through_axis, context_root, source_roots)
    u, v = transverse
    cells = []
    for axis, side in ((u, 0), (u, 1), (v, 0), (v, 1)):
        lo, hi = list(host[0]), list(host[1])
        if axis == v:
            lo[u], hi[u] = opening[0][u], opening[1][u]
        if side == 0:
            hi[axis] = opening[0][axis]
        else:
            lo[axis] = opening[1][axis]
        box = (tuple(lo), tuple(hi))
        cells.append({"id": f"remaining:{len(cells)}", "bounds_local": _json_box(box), "volume_m3": str(_volume(box))})
    return {"schema": "oma.rectilinear-opening-certificate/1", "status": STATUS, "scope": SCOPE,
        "root": root, "manifest": manifest, "remaining_cells": cells,
        "removed_bounds_local": _json_box(removed), "host_volume_m3": str(_volume(host)),
        "removed_volume_m3": str(_volume(removed)), "remaining_volume_m3": str(sum(Fraction(c["volume_m3"]) for c in cells)),
        "set_semantics": "CLOSED_REGULARIZED_DIFFERENCE; REMOVED_AND_REMAINING_BOUNDARIES_MAY_TOUCH",
        "limitations": deepcopy(LIMITATIONS)}


def _inside(point, box):
    return all(a <= x <= b for x, a, b in zip(point, *box))


def verify_rectilinear_opening(host_bounds_local, opening_bounds_local, certificate, *, through_axis, context_root, source_roots):
    """Check complete closed-set coverage using an exact endpoint arrangement.

    No compiler call or repeated four-strip construction. Every point/interval
    stratum of all box boundaries is checked, including exterior boundary faces.
    Membership is constant on each stratum. This checks set equality as well as
    positive cell extents, disjoint interiors and exact volume accounting.
    """
    try:
        host, opening, removed, transverse, manifest, root = _prepare(
            host_bounds_local, opening_bounds_local, through_axis, context_root, source_roots)
        c = deepcopy(certificate)
        fields = {"schema", "status", "scope", "root", "manifest", "remaining_cells", "removed_bounds_local",
                  "host_volume_m3", "removed_volume_m3", "remaining_volume_m3", "set_semantics", "limitations"}
        if not isinstance(c, dict) or set(c) != fields:
            raise ValueError("Complete opening certificate schema required")
        if (c["schema"] != "oma.rectilinear-opening-certificate/1" or c["status"] != STATUS
                or c["scope"] != SCOPE or c["root"] != root or _token(c["manifest"]) != _token(manifest)):
            raise ValueError("Opening input, source identity or scope mismatch")
        if _token(c["limitations"]) != _token(LIMITATIONS):
            raise ValueError("Opening authority limitations changed")
        if c["set_semantics"] != "CLOSED_REGULARIZED_DIFFERENCE; REMOVED_AND_REMAINING_BOUNDARIES_MAY_TOUCH":
            raise ValueError("Regularized set interpretation changed")
        if not isinstance(c["remaining_cells"], list) or len(c["remaining_cells"]) != 4:
            raise ValueError("Exactly four remaining cells required")
        boxes, ids = [], set()
        for cell in c["remaining_cells"]:
            if not isinstance(cell, dict) or set(cell) != {"id", "bounds_local", "volume_m3"}:
                raise ValueError("Malformed remaining cell")
            if not isinstance(cell["id"], str) or not cell["id"] or cell["id"] in ids:
                raise ValueError("Distinct nonempty cell identities required")
            ids.add(cell["id"])
            box = _box(cell["bounds_local"])
            if not all(host[0][i] <= box[0][i] < box[1][i] <= host[1][i] for i in range(3)):
                raise ValueError("Remaining cell extends outside original host")
            if cell["volume_m3"] != str(_volume(box)):
                raise ValueError("Remaining cell volume mismatch")
            boxes.append(box)
        for first, second in combinations(boxes, 2):
            if all(max(first[0][i], second[0][i]) < min(first[1][i], second[1][i]) for i in range(3)):
                raise ValueError("Remaining cells have overlapping interiors")
        if _token(c["removed_bounds_local"]) != _token(_json_box(removed)):
            raise ValueError("Removed support differs from host/opening intersection")
        if (c["host_volume_m3"] != str(_volume(host)) or c["removed_volume_m3"] != str(_volume(removed))
                or c["remaining_volume_m3"] != str(sum(map(_volume, boxes)))
                or sum(map(_volume, boxes)) + _volume(removed) != _volume(host)):
            raise ValueError("Exact host/removed/remaining volume accounting mismatch")
        # Each coordinate has at most twelve endpoints, so at most 23**3 exact
        # strata. Endpoints outside the host are irrelevant: cells cannot extend
        # there and both the expected support and their union are empty there.
        samples = []
        for axis in range(3):
            edges = sorted({box[end][axis] for box in [host, removed, *boxes] for end in (0, 1)})
            samples.append(sorted(set(edges) | {(a + b) / 2 for a, b in zip(edges, edges[1:])}))
        checked = 0
        for point in product(*samples):
            expected = _inside(point, host) and not all(opening[0][i] < point[i] < opening[1][i] for i in transverse)
            represented = any(_inside(point, box) for box in boxes)
            checked += 1
            if expected != represented:
                return {"status": "FAIL", "reason": "REMAINING_SUPPORT_SET_MISMATCH", "witness_local": [str(x) for x in point]}
        return {"status": "PASS", "scope": SCOPE, "root": root, "verified_cells": 4,
            "arrangement_strata_checked": checked, "removed_volume_m3": str(_volume(removed)),
            "remaining_volume_m3": c["remaining_volume_m3"], "limitations": deepcopy(LIMITATIONS)}
    except (ValueError, TypeError, KeyError, IndexError, AttributeError, OverflowError, ZeroDivisionError) as exc:
        return {"status": "FAIL", "reason": str(exc)}
