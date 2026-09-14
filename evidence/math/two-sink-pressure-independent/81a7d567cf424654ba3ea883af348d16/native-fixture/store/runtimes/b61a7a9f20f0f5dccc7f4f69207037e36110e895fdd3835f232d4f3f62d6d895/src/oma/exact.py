"""Exact predicates over rational coordinates of the represented geometry.

Integration DEF-RTR25/26 and required predicates p4369–4408. Python integers
have no fixed-width overflow. Decimal floats are converted from their exact
binary value: quantization, IFC approximation and as-built uncertainty remain
separate upstream obligations. The functions do not introduce tolerance bands.
"""
from fractions import Fraction
from math import isfinite


def _q(value):
    if isinstance(value, float) and not isfinite(value):
        raise ValueError("Nonfinite coordinate")
    return Fraction(value)


def _point(value, dimension=3):
    if len(value) != dimension:
        raise ValueError(f"Expected {dimension} coordinates")
    return tuple(_q(x) for x in value)


def _sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def _dot(a, b):
    return sum((x * y for x, y in zip(a, b)), Fraction(0))


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _at(a, direction, t):
    return tuple(x + t * d for x, d in zip(a, direction))


def _clamp(value, lo=Fraction(0), hi=Fraction(1)):
    return max(lo, min(hi, value))


def orient2d(a, b, c):
    a, b, c = (_point(p, 2) for p in (a, b, c))
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def orient3d(a, b, c, d):
    a, b, c, d = map(_point, (a, b, c, d))
    return _dot(_sub(b, a), _cross(_sub(c, a), _sub(d, a)))


def point_segment_distance_squared(point, a, b):
    point, a, b = map(_point, (point, a, b))
    direction = _sub(b, a)
    denom = _dot(direction, direction)
    t = _clamp(_dot(_sub(point, a), direction) / denom) if denom else Fraction(0)
    witness = _at(a, direction, t)
    return {"distance_squared": _dot(_sub(point, witness), _sub(point, witness)), "segment_t": t,
            "point": point, "segment_point": witness}


def segment_segment_distance_squared(a, b, c, d):
    a, b, c, d = map(_point, (a, b, c, d))
    u, v, w = _sub(b, a), _sub(d, c), _sub(a, c)
    aa, bb, cc, dd, ee = _dot(u, u), _dot(u, v), _dot(v, v), _dot(u, w), _dot(v, w)
    candidates = []
    for t in (Fraction(0), Fraction(1)):
        s = _clamp((bb * t + ee) / cc) if cc else Fraction(0)
        candidates.append((t, s))
    for s in (Fraction(0), Fraction(1)):
        t = _clamp((bb * s - dd) / aa) if aa else Fraction(0)
        candidates.append((t, s))
    determinant = aa * cc - bb * bb
    if determinant > 0:
        t = (bb * ee - cc * dd) / determinant
        s = (aa * ee - bb * dd) / determinant
        if 0 <= t <= 1 and 0 <= s <= 1:
            candidates.append((t, s))
    evaluated = []
    for t, s in candidates:
        p, q = _at(a, u, t), _at(c, v, s)
        delta = _sub(p, q)
        evaluated.append((_dot(delta, delta), t, s, p, q))
    dist, t, s, p, q = min(evaluated)
    return {"distance_squared": dist, "first_t": t, "second_t": s, "first_point": p, "second_point": q}


def point_in_triangle(point, a, b, c):
    point, a, b, c = map(_point, (point, a, b, c))
    normal = _cross(_sub(b, a), _sub(c, a))
    if _dot(normal, normal) == 0:
        return any(point_segment_distance_squared(point, u, v)["distance_squared"] == 0 for u, v in ((a, b), (b, c), (c, a)))
    if _dot(normal, _sub(point, a)) != 0:
        return False
    signs = [_dot(normal, _cross(_sub(v, u), _sub(point, u))) for u, v in ((a, b), (b, c), (c, a))]
    return all(s >= 0 for s in signs)


def segment_triangle_intersection(start, end, a, b, c):
    """Return NONE, CONTACT or COPLANAR_CONTACT with exact intersection witness.

    Degenerate triangles are interpreted as their union of closed edges, not a
    volumetric obstacle; callers must preserve their source validity status.
    """
    start, end, a, b, c = map(_point, (start, end, a, b, c))
    normal = _cross(_sub(b, a), _sub(c, a))
    denominator = _dot(normal, _sub(end, start))
    start_side = _dot(normal, _sub(start, a))
    if denominator:
        t = -start_side / denominator
        if 0 <= t <= 1:
            witness = _at(start, _sub(end, start), t)
            if point_in_triangle(witness, a, b, c):
                return {"status": "CONTACT", "point": witness, "segment_t": t}
        return {"status": "NONE"}
    if start_side:
        return {"status": "NONE"}
    for t, point in ((Fraction(0), start), (Fraction(1), end)):
        if point_in_triangle(point, a, b, c):
            return {"status": "COPLANAR_CONTACT", "point": point, "segment_t": t}
    for u, v in ((a, b), (b, c), (c, a)):
        nearest = segment_segment_distance_squared(start, end, u, v)
        if nearest["distance_squared"] == 0:
            return {"status": "COPLANAR_CONTACT", "point": nearest["first_point"], "segment_t": nearest["first_t"]}
    return {"status": "NONE"}


def segment_box_distance_squared(start, end, box_min, box_max):
    """Global exact segment/AABB distance via piecewise quadratic minimization.

    Every axis boundary supplies a rational break point. On each interval, the
    set of active nearest box faces is fixed and the squared distance is convex
    quadratic; its clipped stationary point plus boundaries contains a minimizer.
    Handles solid containment, zero-length segments and arbitrarily thin boxes.
    """
    start, end, lo, hi = map(_point, (start, end, box_min, box_max))
    if any(a > b for a, b in zip(lo, hi)):
        raise ValueError("Reversed box bounds")
    direction = _sub(end, start)
    breaks = {Fraction(0), Fraction(1)}
    for origin, delta, lower, upper in zip(start, direction, lo, hi):
        if delta:
            for face in (lower, upper):
                t = (face - origin) / delta
                if 0 < t < 1:
                    breaks.add(t)
    cuts = sorted(breaks)
    candidates = set(cuts)
    for left, right in zip(cuts, cuts[1:]):
        middle = (left + right) / 2
        aa = bb = Fraction(0)
        for origin, delta, lower, upper in zip(start, direction, lo, hi):
            value = origin + middle * delta
            face = lower if value < lower else upper if value > upper else None
            if face is not None:
                aa += delta * delta
                bb += delta * (origin - face)
        if aa:
            candidates.add(_clamp(-bb / aa, left, right))
    evaluated = []
    for t in candidates:
        point = _at(start, direction, t)
        witness = tuple(_clamp(x, a, b) for x, a, b in zip(point, lo, hi))
        delta = _sub(point, witness)
        evaluated.append((_dot(delta, delta), t, point, witness))
    dist, t, point, witness = min(evaluated)
    return {"distance_squared": dist, "segment_t": t, "segment_point": point, "box_point": witness}


def capsule_box_clearance(start, end, radius, box_min, box_max, *, required_clearance=0, contact_allowed=False):
    radius, clearance = _q(radius), _q(required_clearance)
    if radius < 0 or clearance < 0:
        raise ValueError("Radius and clearance must be nonnegative")
    witness = segment_box_distance_squared(start, end, box_min, box_max)
    threshold_squared = (radius + clearance)**2
    distance_squared = witness["distance_squared"]
    relation = "SEPARATED" if distance_squared > threshold_squared else "CONTACT" if distance_squared == threshold_squared else "OVERLAP"
    if distance_squared == threshold_squared == 0:
        # Distance alone cannot distinguish a zero-radius centerline lying in
        # the solid interior from legal boundary tangency.
        start_q, end_q, lo_q, hi_q = map(_point, (start, end, box_min, box_max))
        lower, upper, possible = Fraction(0), Fraction(1), True
        for origin, target, lo, hi in zip(start_q, end_q, lo_q, hi_q):
            delta = target - origin
            if lo == hi or (not delta and not lo < origin < hi):
                possible = False
                break
            if delta:
                cuts = sorted(((lo - origin) / delta, (hi - origin) / delta))
                lower, upper = max(lower, cuts[0]), min(upper, cuts[1])
        if possible and lower < upper:
            relation = "OVERLAP"
    return {**witness, "threshold_squared": threshold_squared, "relation": relation,
            "verdict": "PASS" if relation == "SEPARATED" or (relation == "CONTACT" and contact_allowed) else "FAIL",
            "scope": "EXACT_RATIONAL_CAPSULE_AABB"}


def capsule_within_box(start, end, radius, box_min, box_max, *, contact_allowed=True):
    """A004: test the entire capsule against the eroded allowed box."""
    start, end, lo, hi = map(_point, (start, end, box_min, box_max))
    radius = _q(radius)
    if radius < 0 or any(a > b for a, b in zip(lo, hi)):
        raise ValueError("Invalid envelope radius or allowed box")
    margins = tuple(min(min(a, b) - radius - lower, upper - max(a, b) - radius)
                    for a, b, lower, upper in zip(start, end, lo, hi))
    margin = min(margins)
    return {"verdict": "PASS" if margin > 0 or (margin == 0 and contact_allowed) else "FAIL",
            "minimum_axis_margin": margin, "axis_margins": margins,
            "scope": "EXACT_CAPSULE_WITHIN_AABB", "amendment": "OMA-MATH-A004"}
