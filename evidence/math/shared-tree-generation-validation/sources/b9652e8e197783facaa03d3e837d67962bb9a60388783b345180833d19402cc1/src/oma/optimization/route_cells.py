"""Certified bounded inner/outer translational geometry, integration RTR12-24.

The body is a closed ball translated along a continuous centre path. Complete
outer obstacle covers certify free space; occupied inner boxes certify blocked
space. These are distinct input contracts. A BIM bounding box is not, by itself,
an occupied inner box. Source applicability, fittings and physics remain external.
"""
from collections import deque
from copy import deepcopy
from fractions import Fraction as Q
from itertools import product
from math import prod

from oma.exact import capsule_box_clearance, capsule_within_box
from .fdqa import _Budget, _BudgetExceeded
from .finite import _root, _token
from .physical import sqrt_interval
from .rectilinear_opening import _q


STATUS = "CERTIFIED_INNER_OUTER_BOX_GEOMETRY"
SCOPE = "CONTINUOUS_TRANSLATING_BALL_IN_DECLARED_OBSTACLE_SANDWICH"
LIMITATIONS = {
    "source_outer_cover_authenticity_checked": False,
    "source_inner_occupancy_authenticity_checked": False,
    "frame_and_units_applicability_checked": False,
    "elbow_fabrication_or_orientation_checked": False,
    "service_physics_checked": False,
    "native_IFC_candidate_acceptance_authority": False,
    "continuous_cost_optimality_claimed": False,
}


def _point(value):
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError("Three coordinates required")
    return tuple(map(_q, value))


def _box(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("Box min/max required")
    lo, hi = map(_point, value)
    if any(a > b for a, b in zip(lo, hi)):
        raise ValueError("Reversed box bounds")
    return lo, hi


def _json(value):
    return [[str(x) for x in row] for row in value]


def _contains(box, point):
    return all(a <= p <= b for p, a, b in zip(point, *box))


def _contained(inner, outer):
    return all(a <= c <= d <= b for a, b, c, d in zip(*outer, *inner))


def _dot(a, b):
    return sum((x * y for x, y in zip(a, b)), Q(0))


def _d2(a, b):
    return sum(((x - y) ** 2 for x, y in zip(a, b)), Q(0))


def _id(index):
    return ":".join(map(str, index))


def _prepare(problem, max_cells, budget):
    fields = {"allowed_bounds", "body_radius", "clearance", "outer_obstacles", "inner_obstacles",
              "grid_axes", "start", "goal", "context_root", "source_roots"}
    if not isinstance(problem, dict) or set(problem) != fields:
        raise ValueError("Complete route-cell problem schema required")
    if type(max_cells) is not int or max_cells < 1:
        raise ValueError("Positive integer cell limit required")
    allowed = _box(problem["allowed_bounds"])
    radius, clearance = _q(problem["body_radius"]), _q(problem["clearance"])
    if radius < 0 or clearance < 0:
        raise ValueError("Nonnegative body radius and clearance required")
    centre_domain = (tuple(x + radius for x in allowed[0]), tuple(x - radius for x in allowed[1]))
    if any(a >= b for a, b in zip(*centre_domain)):
        raise ValueError("Positive three-dimensional eroded centre domain required")
    start, goal = _point(problem["start"]), _point(problem["goal"])
    if not _contains(centre_domain, start) or not _contains(centre_domain, goal):
        raise ValueError("Endpoints must lie in the admitted eroded centre domain")
    axes = problem["grid_axes"]
    if not isinstance(axes, (list, tuple)) or len(axes) != 3:
        raise ValueError("Three complete partition axes required")
    if any(not isinstance(axis, (list, tuple)) or len(axis) < 2 for axis in axes):
        raise ValueError("Finite nonempty partition axes required")
    if any(len(axis) > max_cells + 1 for axis in axes):
        raise _BudgetExceeded
    axes = tuple(tuple(map(_q, axis)) for axis in axes)
    if any(axis[0] != centre_domain[0][i] or axis[-1] != centre_domain[1][i]
           or any(a >= b for a, b in zip(axis, axis[1:])) for i, axis in enumerate(axes)):
        raise ValueError("Strict axes must cover the complete eroded domain exactly")
    count = prod(len(axis) - 1 for axis in axes)
    if count > max_cells:
        raise _BudgetExceeded
    budget.spend(count)
    outer, inner = {}, {}
    for key, target in (("outer_obstacles", outer), ("inner_obstacles", inner)):
        if not isinstance(problem[key], list) or len(problem[key]) > 256:
            raise ValueError("At most 256 explicit boxes per obstacle bound family")
        for item in problem[key]:
            expected = {"id", "bounds"} if key == "outer_obstacles" else {"id", "bounds", "outer_id"}
            if not isinstance(item, dict) or set(item) != expected:
                raise ValueError("Malformed obstacle box")
            if not isinstance(item["id"], str) or not item["id"] or item["id"] in target:
                raise ValueError("Distinct nonempty obstacle identities required")
            box = _box(item["bounds"])
            if key == "inner_obstacles":
                parent = outer.get(item["outer_id"])
                if parent is None or not _contained(box, parent):
                    raise ValueError("Every occupied inner box must fit its named outer box")
            target[item["id"]] = box
    roots = problem["source_roots"]
    if (not isinstance(roots, dict) or set(roots) != {"outer_cover", "inner_occupancy", "frame", "body_model"}
            or any(not isinstance(x, str) or not x for x in roots.values())):
        raise ValueError("Complete nonempty source-bound applicability identities required")
    context = problem["context_root"]
    if not isinstance(context, str) or not context:
        raise ValueError("Immutable context root required")
    normalized = {"schema": "oma.route-cell-input/1", "allowed_bounds": _json(allowed),
        "body_radius": str(radius), "clearance": str(clearance), "grid_axes": [[str(x) for x in axis] for axis in axes],
        "start": [str(x) for x in start], "goal": [str(x) for x in goal], "context_root": context,
        "source_roots": deepcopy(roots), "outer_obstacles": [{"id": k, "bounds": _json(v)} for k, v in sorted(outer.items())],
        "inner_obstacles": sorted([{"id": item["id"], "bounds": _json(inner[item["id"]]), "outer_id": item["outer_id"]}
                                   for item in problem["inner_obstacles"]], key=lambda x: x["id"]),
        "obstacle_contract": "UNION_INNER_BOXES_SUBSET_OCCUPIED_SUPPORT_SUBSET_UNION_OUTER_BOXES",
        "contact_policy": "STRICT_OBSTACLE_CLEARANCE; ALLOWED_REGION_BOUNDARY_CONTACT_PERMITTED",
        "coordinate_interpretation": "EXACT_RATIONAL; FINITE_FLOATS_MEAN_EXACT_BINARY_VALUES"}
    indexed = {index: (tuple(axes[i][index[i]] for i in range(3)), tuple(axes[i][index[i] + 1] for i in range(3)))
               for index in product(*(range(len(a) - 1) for a in axes))}
    return {"manifest": normalized, "root": _root(context, normalized), "allowed": allowed, "radius": radius,
        "clearance": clearance, "threshold2": (radius + clearance) ** 2, "outer": outer, "inner": inner,
        "start": start, "goal": goal, "indexed": indexed, "cells": {_id(i): b for i, b in indexed.items()},
        "indices": {_id(i): i for i in indexed}, "dimensions": tuple(len(a) - 1 for a in axes)}


def _neighbours(model, identifier):
    index = model["indices"][identifier]
    for delta in product((-1, 0, 1), repeat=3):
        other = tuple(x + d for x, d in zip(index, delta))
        if other != index and all(0 <= x < length for x, length in zip(other, model["dimensions"])):
            yield _id(other)


def _find_path(model, allowed, budget):
    sources = sorted(c for c in allowed if _contains(model["cells"][c], model["start"]))
    targets = {c for c in allowed if _contains(model["cells"][c], model["goal"])}
    parents = dict.fromkeys(sources)
    queue = deque(sources)
    while queue:
        cell = queue.popleft()
        if cell in targets:
            path = [cell]
            while parents[path[-1]] is not None:
                path.append(parents[path[-1]])
            return list(reversed(path)), sorted(parents)
        for other in _neighbours(model, cell):
            budget.spend()
            if other in allowed and other not in parents:
                parents[other] = cell
                queue.append(other)
    return None, sorted(parents)


def _embedding_clear(model, points, budget):
    edges = list(zip(points, points[1:])) or [(points[0], points[0])]
    for start, end in edges:
        budget.spend()
        if capsule_within_box(start, end, model["radius"], *model["allowed"])["verdict"] != "PASS":
            return False
        for obstacle in model["outer"].values():
            budget.spend()
            if capsule_box_clearance(start, end, model["radius"], *obstacle,
                                     required_clearance=model["clearance"])["verdict"] != "PASS":
                return False
    return True


def _path_cost(model, points):
    lower = sqrt_interval(_d2(model["start"], model["goal"])).lo
    intervals = [] if points is None else [sqrt_interval(_d2(a, b)) for a, b in zip(points, points[1:])]
    return {"universal_centreline_length_lower_bound_m": str(lower),
            "inner_segment_length_intervals_m": [[str(x.lo), str(x.hi)] for x in intervals],
            "inner_path_length_upper_bound_m": None if points is None else str(sum((x.hi for x in intervals), Q(0))),
            "scope": "EUCLIDEAN_CENTRELINE_LENGTH_ONLY; NO_CONTINUOUS_OPTIMUM_CLAIM"}


def compile_route_cells(problem, *, max_cells=2048, max_work=500_000):
    """Propose and certify a conservative finite cell complex and route outcome."""
    budget = _Budget(max_work)
    try:
        model = _prepare(problem, max_cells, budget)
        classified = []
        for identifier, cell in model["cells"].items():
            planes = []
            for name, obstacle in model["outer"].items():
                budget.spend()
                normal = tuple(obstacle[0][i] - cell[1][i] if cell[1][i] < obstacle[0][i]
                               else obstacle[1][i] - cell[0][i] if obstacle[1][i] < cell[0][i] else Q(0) for i in range(3))
                if _dot(normal, normal) <= model["threshold2"]:
                    break
                planes.append({"outer_id": name, "normal": [str(x) for x in normal]})
            if len(planes) == len(model["outer"]):
                classified.append({"id": identifier, "classification": "FREE", "separating_planes": planes})
                continue
            blocked = None
            for name, obstacle in model["inner"].items():
                budget.spend(8)
                corners = list(product(*zip(*cell)))
                points = [tuple(max(lo, min(x, hi)) for x, lo, hi in zip(corner, *obstacle)) for corner in corners]
                if all(_d2(a, b) <= model["threshold2"] for a, b in zip(corners, points)):
                    blocked = {"inner_id": name, "corner_occupied_points": [[str(x) for x in p] for p in points]}
                    break
            classified.append({"id": identifier, "classification": "BLOCKED", "cover": blocked} if blocked is not None
                              else {"id": identifier, "classification": "MIXED"})
        free = {c["id"] for c in classified if c["classification"] == "FREE"}
        retained = {c["id"] for c in classified if c["classification"] != "BLOCKED"}
        outer_path, reachable = _find_path(model, retained, budget)
        points = [model["start"], model["goal"]]
        if model["start"] == model["goal"]:
            points.pop()
        if not _embedding_clear(model, points, budget):
            path, _ = _find_path(model, free, budget)
            points = None
            if path is not None:
                points = [model["start"]]
                for first, second in zip(path, path[1:]):
                    a, b = model["cells"][first], model["cells"][second]
                    portal = tuple((max(a[0][i], b[0][i]) + min(a[1][i], b[1][i])) / 2 for i in range(3))
                    if portal != points[-1]:
                        points.append(portal)
                if points[-1] != model["goal"]:
                    points.append(model["goal"])
                if not _embedding_clear(model, points, budget):
                    raise RuntimeError("Free-cell portal embedding violated its proved domain")
        outcome = "INNER_PATH_CHECKED" if points is not None else "OUTER_INFEASIBLE" if outer_path is None else "UNKNOWN"
        return {"schema": "oma.route-cell-certificate/1", "status": STATUS, "scope": SCOPE, "root": model["root"],
            "manifest": model["manifest"], "cells": classified,
            "outer_connectivity": {"kind": "PATH", "cells": outer_path} if outer_path is not None else {"kind": "CUT", "reachable": reachable},
            "inner_path": None if points is None else [[str(x) for x in p] for p in points],
            "geometry_outcome": outcome, "length_bounds": _path_cost(model, points),
            "limitations": deepcopy(LIMITATIONS), "work": budget.used}
    except _BudgetExceeded:
        return {"status": "UNKNOWN", "reason": "ROUTE_CELL_BUDGET", "work": budget.used}


def verify_route_cells(problem, certificate, *, max_cells=2048, max_work=750_000):
    """Verify plane/corner witnesses, complete cell inventory and path or cut.

    No cell classification or connectivity search is repeated. An outer CUT is
    checked as an inductive set closed under every retained neighbour; an outer
    PATH is checked directly. Arbitrary conservative MIXED cells are permitted.
    """
    budget = _Budget(max_work)
    try:
        model = _prepare(problem, max_cells, budget)
        c = deepcopy(certificate)
        fields = {"schema", "status", "scope", "root", "manifest", "cells", "outer_connectivity", "inner_path",
                  "geometry_outcome", "length_bounds", "limitations", "work"}
        if not isinstance(c, dict) or set(c) != fields:
            raise ValueError("Complete route-cell certificate required")
        if (c["schema"] != "oma.route-cell-certificate/1" or c["status"] != STATUS or c["scope"] != SCOPE
                or c["root"] != model["root"] or _token(c["manifest"]) != _token(model["manifest"])
                or _token(c["limitations"]) != _token(LIMITATIONS)):
            raise ValueError("Route-cell input, identity or scope changed")
        if not isinstance(c["cells"], list) or len(c["cells"]) != len(model["cells"]):
            raise ValueError("Complete cell denominator required")
        seen, free, retained = set(), set(), set()
        for entry in c["cells"]:
            identifier, kind = entry["id"], entry["classification"]
            if identifier not in model["cells"] or identifier in seen:
                raise ValueError("Missing or duplicate cell identity")
            seen.add(identifier)
            cell = model["cells"][identifier]
            if kind == "FREE":
                if set(entry) != {"id", "classification", "separating_planes"} or not isinstance(entry["separating_planes"], list):
                    raise ValueError("Malformed FREE proof")
                checked = set()
                for plane in entry["separating_planes"]:
                    budget.spend()
                    if set(plane) != {"outer_id", "normal"} or plane["outer_id"] not in model["outer"] or plane["outer_id"] in checked:
                        raise ValueError("Incomplete or duplicate outer obstacle plane")
                    obstacle, normal = model["outer"][plane["outer_id"]], _point(plane["normal"])
                    norm2 = _dot(normal, normal)
                    upper = sum((n * (cell[1][i] if n >= 0 else cell[0][i]) for i, n in enumerate(normal)), Q(0))
                    lower = sum((n * (obstacle[0][i] if n >= 0 else obstacle[1][i]) for i, n in enumerate(normal)), Q(0))
                    gap = lower - upper
                    if norm2 == 0 or gap <= 0 or gap ** 2 <= model["threshold2"] * norm2:
                        raise ValueError("Separating plane does not prove full-cell strict clearance")
                    checked.add(plane["outer_id"])
                if checked != set(model["outer"]):
                    raise ValueError("A FREE cell omits an outer obstacle")
                free.add(identifier)
                retained.add(identifier)
            elif kind == "BLOCKED":
                if set(entry) != {"id", "classification", "cover"} or set(entry["cover"]) != {"inner_id", "corner_occupied_points"}:
                    raise ValueError("Malformed BLOCKED proof")
                cover = entry["cover"]
                obstacle = model["inner"].get(cover["inner_id"])
                points = cover["corner_occupied_points"]
                if obstacle is None or not isinstance(points, list) or len(points) != 8:
                    raise ValueError("BLOCKED needs one occupied inner box and all eight corner witnesses")
                for corner, value in zip(product(*zip(*cell)), points):
                    budget.spend()
                    point = _point(value)
                    if not _contains(obstacle, point) or _d2(corner, point) > model["threshold2"]:
                        raise ValueError("Inner occupancy fails to cover the whole cell")
            elif kind == "MIXED" and set(entry) == {"id", "classification"}:
                retained.add(identifier)
            else:
                raise ValueError("Unknown cell proof classification")
        outer = c["outer_connectivity"]
        sources = {k for k in retained if _contains(model["cells"][k], model["start"])}
        targets = {k for k in retained if _contains(model["cells"][k], model["goal"])}
        if outer["kind"] == "PATH" and set(outer) == {"kind", "cells"}:
            path = outer["cells"]
            if not isinstance(path, list) or not path or len(path) > len(retained) or any(p not in retained for p in path):
                raise ValueError("Invalid retained outer path")
            if path[0] not in sources or path[-1] not in targets:
                raise ValueError("Outer path endpoint membership mismatch")
            for first, second in zip(path, path[1:]):
                budget.spend()
                if second not in set(_neighbours(model, first)):
                    raise ValueError("Outer path skips a cell incidence")
            outer_feasible = True
        elif outer["kind"] == "CUT" and set(outer) == {"kind", "reachable"}:
            listed = outer["reachable"]
            if not isinstance(listed, list) or len(set(listed)) != len(listed):
                raise ValueError("Malformed outer cut")
            cut = set(listed)
            if not cut <= retained or not sources <= cut or cut & targets:
                raise ValueError("Outer cut source/target separation mismatch")
            for cell in cut:
                for neighbour in _neighbours(model, cell):
                    budget.spend()
                    if neighbour in retained and neighbour not in cut:
                        raise ValueError("Outer cut is not closed under every retained incidence")
            outer_feasible = False
        else:
            raise ValueError("Outer path or inductive cut required")
        raw_points = c["inner_path"]
        points = None
        if raw_points is not None:
            if not isinstance(raw_points, list) or not raw_points or len(raw_points) > len(model["cells"]) + 2:
                raise ValueError("Bounded nonempty inner path required")
            points = list(map(_point, raw_points))
            if points[0] != model["start"] or points[-1] != model["goal"] or not _embedding_clear(model, points, budget):
                raise ValueError("Inner path lacks complete capsule-body embedding")
            if not outer_feasible:
                raise ValueError("Inner path contradicts claimed outer impossibility")
        expected = "INNER_PATH_CHECKED" if points is not None else "UNKNOWN" if outer_feasible else "OUTER_INFEASIBLE"
        if c["geometry_outcome"] != expected:
            raise ValueError("Inner search failure was strengthened or outcome changed")
        bounds = c["length_bounds"]
        if set(bounds) != {"universal_centreline_length_lower_bound_m", "inner_segment_length_intervals_m", "inner_path_length_upper_bound_m", "scope"}:
            raise ValueError("Malformed length bounds")
        if bounds["scope"] != "EUCLIDEAN_CENTRELINE_LENGTH_ONLY; NO_CONTINUOUS_OPTIMUM_CLAIM":
            raise ValueError("Length scope changed")
        lower = _q(bounds["universal_centreline_length_lower_bound_m"])
        if lower < 0 or lower ** 2 > _d2(model["start"], model["goal"]):
            raise ValueError("Invalid continuous centreline length lower bound")
        intervals = bounds["inner_segment_length_intervals_m"]
        if points is None:
            if intervals != [] or bounds["inner_path_length_upper_bound_m"] is not None:
                raise ValueError("No inner path permits no finite incumbent length")
        else:
            if not isinstance(intervals, list) or len(intervals) != len(points) - 1:
                raise ValueError("Missing segment length interval")
            upper_sum = Q(0)
            for pair, first, second in zip(intervals, points, points[1:]):
                if not isinstance(pair, list) or len(pair) != 2:
                    raise ValueError("Malformed segment interval")
                lo, hi = map(_q, pair)
                if lo < 0 or hi < lo or not lo ** 2 <= _d2(first, second) <= hi ** 2:
                    raise ValueError("Segment length not enclosed")
                upper_sum += hi
            if bounds["inner_path_length_upper_bound_m"] != str(upper_sum):
                raise ValueError("Inner path upper length sum mismatch")
        return {"status": "PASS", "scope": SCOPE, "root": model["root"], "geometry_outcome": expected,
            "verified_cells": len(seen), "free_cells": len(free), "outer_retained_cells": len(retained),
            "length_bounds": deepcopy(bounds), "limitations": deepcopy(LIMITATIONS), "work": budget.used}
    except _BudgetExceeded:
        return {"status": "UNKNOWN", "reason": "ROUTE_CELL_VERIFICATION_BUDGET", "work": budget.used}
    except (ValueError, KeyError, TypeError, IndexError, AttributeError, OverflowError, ZeroDivisionError) as exc:
        return {"status": "FAIL", "reason": str(exc)}


def verify_route_cell_refinement(coarse_problem, coarse_certificate, fine_problem, fine_certificate,
                                 *, max_cells=2048, max_work=1_500_000):
    """Check fixed-model nested axes and monotone certified free/outer regions.

    This certifies the supplied refinement pair, not termination or the ability
    to resolve every mixed boundary cell. A changed model is not a refinement.
    """
    budget = _Budget(max_work)
    try:
        for problem, certificate in ((coarse_problem, coarse_certificate), (fine_problem, fine_certificate)):
            result = verify_route_cells(problem, certificate, max_cells=max_cells, max_work=max_work - budget.used)
            budget.spend(result.get("work", 0))
            if result["status"] != "PASS":
                return {"status": result["status"], "reason": "REFINEMENT_CONSTITUENT_" + result.get("reason", "UNCHECKED")}
        coarse = _prepare(coarse_problem, max_cells, budget)
        fine = _prepare(fine_problem, max_cells, budget)
        if _token({k: v for k, v in coarse["manifest"].items() if k != "grid_axes"}) != _token(
                {k: v for k, v in fine["manifest"].items() if k != "grid_axes"}):
            raise ValueError("Changed geometry or applicability is not fixed-model refinement")
        coarse_axes = [tuple(map(Q, row)) for row in coarse["manifest"]["grid_axes"]]
        fine_axes = [tuple(map(Q, row)) for row in fine["manifest"]["grid_axes"]]
        if any(not set(a) <= set(b) for a, b in zip(coarse_axes, fine_axes)):
            raise ValueError("Fine axes do not retain every coarse boundary")
        coarse_class = {c["id"]: c["classification"] for c in coarse_certificate["cells"]}
        fine_class = {c["id"]: c["classification"] for c in fine_certificate["cells"]}
        from bisect import bisect_right
        for identifier, box in fine["cells"].items():
            budget.spend()
            midpoint = tuple((a + b) / 2 for a, b in zip(*box))
            parent = _id(tuple(bisect_right(axis, x) - 1 for axis, x in zip(coarse_axes, midpoint)))
            if coarse_class[parent] in {"FREE", "BLOCKED"} and fine_class[identifier] != coarse_class[parent]:
                raise ValueError("Refinement loses a certified inner-free or outer-blocked region")
        return {"status": "PASS", "scope": "FIXED_MODEL_INNER_GROWTH_AND_OUTER_CONTRACTION",
            "coarse_root": coarse["root"], "fine_root": fine["root"], "work": budget.used,
            "termination_or_boundary_resolution_proved": False}
    except _BudgetExceeded:
        return {"status": "UNKNOWN", "reason": "REFINEMENT_VERIFICATION_BUDGET", "work": budget.used}
    except (ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
        return {"status": "FAIL", "reason": str(exc)}
