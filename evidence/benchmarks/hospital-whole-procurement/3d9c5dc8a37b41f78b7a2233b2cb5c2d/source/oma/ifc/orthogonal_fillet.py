"""Exact tangent construction for source-axis polylines before IFC conversion.

This is a writer, separate from optimization.fabrication's witness checker.
Returned coordinates are binary64 for IFC/native consumption. Exact predicates
describe the nominal input construction, not native solid equality.
"""
from fractions import Fraction as Q
import math


def orthogonal_fillet_parts(points, bend_radius_m, minimum_straight_m):
    """Return nominal axis-aligned parts, or None for the numerical fallback."""
    if len(points) > 1024:
        return None
    p = [tuple(Q(float(x)) for x in point) for point in points]
    vectors = [tuple(b-a for a,b in zip(first,second)) for first,second in zip(p,p[1:])]
    if any(sum(x != 0 for x in vector) != 1 for vector in vectors):
        return None
    lengths = [sum(abs(x) for x in vector) for vector in vectors]
    epsilon, radius = Q(1e-9), Q(float(bend_radius_m))
    minimum = max(Q(float(minimum_straight_m)), epsilon)
    if any(length <= epsilon for length in lengths):
        raise ValueError("Repeated route points / zero length segment")
    unit = [tuple(x/length for x in vector) for vector,length in zip(vectors,lengths)]
    trims, turns = [Q(0)]*len(p), set()
    for i,(incoming,outgoing) in enumerate(zip(unit,unit[1:]),1):
        dot = sum(a*b for a,b in zip(incoming,outgoing))
        if dot == -1 or (dot == 0 and radius <= 0):
            raise ValueError("U-turn or missing positive bend radius is unsupported")
        if dot == 0:
            trims[i] = radius
            turns.add(i)
    available = [length-trims[i]-trims[i+1] for i,length in enumerate(lengths)]
    if any(length <= minimum for length in available):
        raise ValueError("Fittings consume segment or violate minimum straight length (exact orthogonal construction)")

    def moved(point,direction,distance):
        return tuple(x+distance*d for x,d in zip(point,direction))

    def cross(a,b):
        return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])

    def scalar(value):
        try:
            result = float(value)
        except OverflowError as error:
            raise ValueError("Nominal route geometry exceeds finite native coordinate range") from error
        if not math.isfinite(result):
            raise ValueError("Nominal route geometry exceeds finite native coordinate range")
        return result

    def coordinates(point):
        return [scalar(x) for x in point]

    parts = []
    for i,direction in enumerate(unit):
        start = moved(p[i],direction,trims[i])
        end = moved(p[i+1],direction,-trims[i+1])
        parts.append({"kind":"segment", "start":coordinates(start), "end":coordinates(end),
                      "length_m":scalar(available[i])})
        corner = i+1
        if corner in turns:
            outgoing = unit[corner]
            arc_start = moved(p[corner],direction,-radius)
            arc_end = moved(p[corner],outgoing,radius)
            center = moved(arc_start,outgoing,radius)
            parts.append({"kind":"elbow", "start":coordinates(arc_start), "end":coordinates(arc_end),
                "center":coordinates(center), "normal":coordinates(cross(direction,outgoing)),
                "x_axis":coordinates(tuple(-x for x in outgoing)), "bend_radius_m":scalar(radius),
                "angle_rad":math.pi/2, "length_m":scalar(radius)*math.pi/2})
    return parts
