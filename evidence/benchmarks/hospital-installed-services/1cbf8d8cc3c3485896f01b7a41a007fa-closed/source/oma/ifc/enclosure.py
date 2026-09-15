"""Certified outer boxes for an explicitly supported IFC geometry subset.

Decimal STEP coordinates are read as rationals from the immutable source bytes.
Affine axes are normalized with rational interval square roots. No OpenCASCADE
box or display tessellation is an input. The claim is containment of represented
planar support, not shell validity, hidden physical extent or building fitness.
"""
from __future__ import annotations

from fractions import Fraction as Q
from hashlib import sha256
from pathlib import Path
from copy import deepcopy
import re
from threading import RLock

from oma.optimization.physical import Interval as I, sqrt_interval
from oma.exact import orient2d, orient3d

CODE_SHA256 = sha256(Path(__file__).read_bytes()).hexdigest()


class EnclosureUnknown(ValueError):
    pass


_TOKEN = re.compile(r"\s+|/\*.*?\*/|'(?:[^']|'')*'|#[0-9]+|\.[A-Za-z_][A-Za-z_0-9]*\.|[+-]?(?:\d+\.?\d*|\.\d+)(?:[Ee][+-]?\d+)?|[A-Za-z_][A-Za-z_0-9]*|[(),$*=;]", re.S)
_INDEX = re.compile(r"'(?:[^']|'')*'|/\*.*?\*/|#(?P<id>\d+)\s*=\s*(?P<kind>[A-Za-z_][A-Za-z_0-9]*)\s*\(", re.S)


class _Ref:
    def __init__(self, number):
        self.number = number


class StepRationals:
    """Lazy lossless numeric STEP reader; strings/comments cannot forge records."""
    def __init__(self, path, model):
        raw = Path(path).read_bytes()
        self.source_sha256 = sha256(raw).hexdigest()
        self.text = raw.decode("latin-1")
        self.model = model
        self.index = {}
        self.cache = {}
        for match in _INDEX.finditer(self.text):
            if match.group("id") is not None:
                number = int(match.group("id"))
                if number in self.index:
                    raise EnclosureUnknown("DUPLICATE_STEP_ENTITY")
                self.index[number] = (match.group("kind"), match.end() - 1)

    def _parse(self, start):
        position = start

        def token():
            nonlocal position
            while True:
                m = _TOKEN.match(self.text, position)
                if not m:
                    raise EnclosureUnknown("UNSUPPORTED_STEP_TOKEN")
                position = m.end()
                value = m.group()
                if not (value.isspace() or value.startswith("/*")):
                    return value

        def value(t):
            if t == "(":
                output = []
                t = token()
                if t == ")":
                    return tuple(output)
                while True:
                    output.append(value(t))
                    separator = token()
                    if separator == ")":
                        return tuple(output)
                    if separator != ",":
                        raise EnclosureUnknown("MALFORMED_STEP_LIST")
                    t = token()
            if t.startswith("#"):
                return _Ref(int(t[1:]))
            if t in ("$", "*"):
                return None
            if t.startswith("'"):
                return t[1:-1].replace("''", "'")
            if t.startswith(".") and t.endswith(".") and not t[1:2].isdigit():
                return t[1:-1].upper()
            if t[0].isalpha():
                if token() != "(":
                    raise EnclosureUnknown("MALFORMED_STEP_TYPED_VALUE")
                contents = value("(")
                return (t.upper(), contents)
            try:
                return Q(t)
            except ValueError as exc:
                raise EnclosureUnknown("NONRATIONAL_STEP_VALUE") from exc

        parsed = value(token())
        if token() != ";":
            raise EnclosureUnknown("MALFORMED_STEP_RECORD")
        return parsed

    def args(self, entity):
        number = entity.id()
        if number not in self.index:
            raise EnclosureUnknown("SOURCE_ENTITY_MISSING")
        kind, start = self.index[number]
        if kind.upper() != entity.is_a().upper():
            raise EnclosureUnknown("SOURCE_SCHEMA_TYPE_MISMATCH")
        if number not in self.cache:
            self.cache[number] = self._parse(start)
        args = self.cache[number]
        if len(args) != len(entity):
            raise EnclosureUnknown("SOURCE_SCHEMA_ARITY_MISMATCH")
        return args

    def get(self, entity, name, default=None):
        for n in range(len(entity)):
            if entity.attribute_name(n) == name:
                return self._resolve(self.args(entity)[n])
        return default

    def _resolve(self, value):
        if isinstance(value, _Ref):
            try:
                entity = self.model.by_id(value.number)
            except Exception as exc:
                raise EnclosureUnknown("SOURCE_REFERENCE_MISSING") from exc
            self.args(entity)
            return entity
        if isinstance(value, tuple):
            return tuple(self._resolve(x) for x in value)
        return value


def _iv(value):
    return value if isinstance(value, I) else I(Q(value), Q(value))


def _outward(value, digits=32):
    """Keep interval endpoints compact with exact directed rational rounding."""
    scale = 10 ** digits
    lower = value.lo * scale
    upper = value.hi * scale
    return I(Q(lower.numerator // lower.denominator, scale),
             Q(-((-upper.numerator) // upper.denominator), scale))


def _sum(values):
    return sum(values, I(Q(0), Q(0)))


def _dot(a, b):
    return _sum(x * y for x, y in zip(a, b))


def _cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def _normalise(vector):
    vector = tuple(map(_iv, vector))
    norm2 = _sum(x.square() for x in vector)
    if norm2.lo <= 0:
        raise EnclosureUnknown("DEGENERATE_OR_UNRESOLVED_DIRECTION")
    norm = I(sqrt_interval(norm2.lo, 40).lo, sqrt_interval(norm2.hi, 40).hi)
    return tuple(_outward(x / norm) for x in vector)


def _identity():
    return tuple(tuple(_iv(int(i == j)) for j in range(4)) for i in range(4))


def _compose(a, b):
    return tuple(tuple(_outward(_sum(a[i][k] * b[k][j] for k in range(4))) for j in range(4)) for i in range(4))


def _is_identity(matrix):
    return matrix == _identity()


def _apply(matrix, point):
    p = tuple(map(_iv, point)) + (_iv(1),)
    return tuple(_outward(_dot(row, p)) for row in matrix[:3])


def _axis_matrix(origin, x, z, y_hint=None, scales=(1, 1, 1)):
    z = _normalise(z)
    x = tuple(map(_iv, x))
    projection = _dot(x, z)
    x = _normalise(tuple(a - projection*b for a, b in zip(x, z)))
    y = _cross(z, x)
    if y_hint is not None:
        sign = _dot(y, tuple(map(_iv, y_hint)))
        if sign.hi < 0:
            y = tuple(-a for a in y)
        elif sign.lo <= 0:
            raise EnclosureUnknown("UNRESOLVED_MAPPING_HANDEDNESS")
    columns = (x, y, z)
    return tuple(tuple(columns[j][i] * scales[j] for j in range(3)) + (_iv(origin[i]),) for i in range(3)) + ((_iv(0), _iv(0), _iv(0), _iv(1)),)


def _on_segment2(a, b, p):
    return orient2d(a,b,p) == 0 and all(min(a[i],b[i]) <= p[i] <= max(a[i],b[i]) for i in range(2))


def _segments_meet2(a, b, c, d):
    u,v,w,z = orient2d(a,b,c),orient2d(a,b,d),orient2d(c,d,a),orient2d(c,d,b)
    return (u*v < 0 and w*z < 0) or any((
        u == 0 and _on_segment2(a,b,c), v == 0 and _on_segment2(a,b,d),
        w == 0 and _on_segment2(c,d,a), z == 0 and _on_segment2(c,d,b)))


def _inside_polygon2(point, loop):
    """Exact even-odd test, returning False for a boundary point."""
    parity = False
    for a,b in zip(loop,loop[1:]):
        if _on_segment2(a,b,point):
            return False
        if (a[1] > point[1]) != (b[1] > point[1]):
            cross_x = a[0] + (point[1]-a[1])*(b[0]-a[0])/(b[1]-a[1])
            if cross_x > point[0]:
                parity = not parity
    return parity


def _box(points):
    return tuple(min(p[i].lo for p in points) for i in range(3)), tuple(max(p[i].hi for p in points) for i in range(3))


def _box_corners(lo, hi):
    return [tuple(_iv(hi[i] if mask & (1 << i) else lo[i]) for i in range(3)) for mask in range(8)]


class ExactIfcEncloser:
    def __init__(self, source_path, model, *, vertex_hull_completion=False, memoize_item_support=True):
        self.raw = StepRationals(source_path, model)
        # The raw reader captures one immutable source. Find project identities
        # once: rescanning every STEP record for every product is quadratic in
        # large models. Unit values and schema checks still use the raw reader
        # on each request, and ambiguous/missing projects remain UNKNOWN.
        self._source_project_ids = tuple(number for number, (kind, _) in self.raw.index.items()
                                         if kind.upper() == "IFCPROJECT")
        self.model = model
        self.g = self.raw.get
        self.vertex_hull_completion = bool(vertex_hull_completion)
        self.nonplanar_polygons = 0
        self._lock = RLock()
        self.memoize_item_support = bool(memoize_item_support)
        self._support_cache = {}
        self.support_cache_hits = 0
        self.support_cache_misses = 0

    def _coords(self, entity, name="Coordinates"):
        value = self.g(entity, name)
        if not isinstance(value, tuple) or len(value) != 3 or not all(isinstance(x, Q) for x in value):
            raise EnclosureUnknown("EXPECTED_THREE_SOURCE_RATIONAL_COORDINATES")
        return value

    def _coords2(self, entity, name="Coordinates"):
        value = self.g(entity, name)
        if not isinstance(value, tuple) or len(value) != 2 or not all(isinstance(x,Q) for x in value):
            raise EnclosureUnknown("EXPECTED_TWO_SOURCE_RATIONAL_COORDINATES")
        return value

    def _positive(self, entity, attribute):
        value = self.g(entity, attribute)
        if not isinstance(value,Q) or value <= 0:
            raise EnclosureUnknown("NONPOSITIVE_OR_INVALID_" + attribute.upper())
        return value

    def _axis2(self, entity):
        if entity is None:
            return _identity()
        if not entity.is_a("IfcAxis2Placement2D"):
            raise EnclosureUnknown("UNSUPPORTED_PROFILE_PLACEMENT")
        origin = self._coords2(self.g(entity,"Location"))
        direction = self.g(entity,"RefDirection")
        x = self._coords2(direction,"DirectionRatios") if direction else (Q(1),Q(0))
        return _axis_matrix((*origin,Q(0)), (*x,Q(0)), (0,0,1))

    def _polyline2(self, curve):
        if curve.is_a() == "IfcPolyline":
            points = tuple(self._coords2(p) for p in self.g(curve,"Points"))
        elif curve.is_a() == "IfcIndexedPolyCurve":
            point_list = self.g(curve,"Points")
            if point_list.is_a() != "IfcCartesianPointList2D":
                raise EnclosureUnknown("NON_2D_PROFILE_POINT_LIST")
            points = self.g(point_list,"CoordList")
            if not points or any(len(p) != 2 or any(not isinstance(v,Q) for v in p) for p in points):
                raise EnclosureUnknown("INVALID_PROFILE_POINT_LIST")
            segments = self.g(curve,"Segments")
            if segments is not None:
                ordered = []
                for segment in segments:
                    if not (isinstance(segment,tuple) and len(segment)==2 and segment[0]=="IFCLINEINDEX"
                            and len(segment[1])==1 and isinstance(segment[1][0],tuple) and len(segment[1][0])>=2):
                        raise EnclosureUnknown("UNSUPPORTED_PROFILE_ARC_OR_SEGMENT")
                    indices = segment[1][0]
                    if any(not isinstance(i,Q) or i.denominator != 1 or not 1 <= i <= len(points) for i in indices):
                        raise EnclosureUnknown("PROFILE_INDEX_OUT_OF_RANGE")
                    part = [points[int(i)-1] for i in indices]
                    if ordered and ordered[-1] != part[0]:
                        raise EnclosureUnknown("DISCONNECTED_PROFILE_SEGMENTS")
                    ordered.extend(part if not ordered else part[1:])
                points = tuple(ordered)
        else:
            raise EnclosureUnknown("UNSUPPORTED_PROFILE_CURVE:" + curve.is_a())
        if len(points) < 4 or points[0] != points[-1]:
            raise EnclosureUnknown("OPEN_OR_SHORT_PROFILE_CURVE")
        # Bounded exact work; exhaustion is not evidence of malformed geometry.
        if len(points) > 2048:
            raise EnclosureUnknown("PROFILE_VALIDATION_BUDGET")
        if any(a==b for a,b in zip(points,points[1:])):
            raise EnclosureUnknown("ZERO_LENGTH_PROFILE_SEGMENT")
        if sum(a[0]*b[1]-a[1]*b[0] for a,b in zip(points,points[1:])) == 0:
            raise EnclosureUnknown("ZERO_AREA_PROFILE")
        edges = list(zip(points,points[1:]))
        for i,(a,b) in enumerate(edges):
            for j in range(i+1,len(edges)):
                c,d = edges[j]
                if j == i+1 or (i==0 and j==len(edges)-1):
                    # Adjacent segments may share exactly their endpoint, but
                    # collinear backtracking has overlapping interiors.
                    common = b if j == i+1 else a
                    other_a = a if j == i+1 else b
                    other_b = d if j == i+1 else c
                    if orient2d(other_a,common,other_b)==0 and (
                            _on_segment2(other_a,common,other_b) or _on_segment2(common,other_b,other_a)):
                        raise EnclosureUnknown("OVERLAPPING_PROFILE_SEGMENTS")
                elif _segments_meet2(a,b,c,d):
                    raise EnclosureUnknown("SELF_INTERSECTING_PROFILE")
        return points

    def _profile(self, profile):
        if self.g(profile,"ProfileType") != "AREA":
            raise EnclosureUnknown("NON_AREA_EXTRUSION_PROFILE")
        kind = profile.is_a()
        if kind == "IfcRectangleProfileDef":
            x,y = self._positive(profile,"XDim")/2,self._positive(profile,"YDim")/2
            points = ((-x,-y),(x,-y),(x,y),(-x,y))
        elif kind == "IfcCircleProfileDef":
            radius = self._positive(profile,"Radius")
            # The entire disk is contained in this square. Corners are an
            # enclosure witness, not a tessellation of the circular boundary.
            points = ((-radius,-radius),(radius,-radius),(radius,radius),(-radius,radius))
        elif kind in ("IfcArbitraryClosedProfileDef","IfcArbitraryProfileDefWithVoids"):
            outer = self._polyline2(self.g(profile,"OuterCurve"))
            inners = [self._polyline2(c) for c in self.g(profile,"InnerCurves",()) or ()]
            if kind == "IfcArbitraryProfileDefWithVoids" and not inners:
                raise EnclosureUnknown("MISSING_PROFILE_INNER_CURVES")
            loops = [outer]+inners
            for i,loop in enumerate(loops):
                for other in loops[i+1:]:
                    if any(_segments_meet2(a,b,c,d) for a,b in zip(loop,loop[1:]) for c,d in zip(other,other[1:])):
                        raise EnclosureUnknown("INTERSECTING_PROFILE_BOUNDARIES")
            if any(not _inside_polygon2(h[0],outer) for h in inners):
                raise EnclosureUnknown("PROFILE_VOID_OUTSIDE_OUTER")
            if any(_inside_polygon2(a[0],b) or _inside_polygon2(b[0],a) for i,a in enumerate(inners) for b in inners[i+1:]):
                raise EnclosureUnknown("NESTED_PROFILE_VOIDS")
            points = outer[:-1]
        else:
            # In particular, tapered/hollow/filleted subclasses are not silently
            # interpreted as their simpler parent profile.
            raise EnclosureUnknown("UNSUPPORTED_EXTRUSION_PROFILE:"+kind)
        matrix = self._axis2(self.g(profile,"Position"))
        return [_apply(matrix,(*p,Q(0))) for p in points]

    def _direction(self, entity, default):
        return self._coords(entity, "DirectionRatios") if entity else default

    def _axis(self, entity):
        if entity is None:
            return _identity()
        if not entity.is_a("IfcAxis2Placement3D"):
            raise EnclosureUnknown("UNSUPPORTED_PLACEMENT_TYPE")
        origin = self._coords(self.g(entity, "Location"))
        z = self._direction(self.g(entity, "Axis"), (0, 0, 1))
        x = self._direction(self.g(entity, "RefDirection"), (1, 0, 0))
        return _axis_matrix(origin, x, z)

    def _placement(self, entity, seen=frozenset()):
        if entity is None:
            return _identity()
        if entity.id() in seen:
            raise EnclosureUnknown("CYCLIC_PLACEMENT")
        if not entity.is_a("IfcLocalPlacement"):
            raise EnclosureUnknown("UNSUPPORTED_PRODUCT_PLACEMENT")
        return _compose(self._placement(self.g(entity, "PlacementRelTo"), seen | {entity.id()}), self._axis(self.g(entity, "RelativePlacement")))

    def _operator(self, entity):
        if not entity.is_a("IfcCartesianTransformationOperator3D"):
            raise EnclosureUnknown("UNSUPPORTED_MAPPING_OPERATOR")
        scale = self.g(entity, "Scale")
        scale = Q(1) if scale is None else scale
        scale2, scale3 = self.g(entity, "Scale2"), self.g(entity, "Scale3")
        scales = (scale, scale if scale2 is None else scale2, scale if scale3 is None else scale3)
        if any(s <= 0 for s in scales):
            raise EnclosureUnknown("NONPOSITIVE_MAPPING_SCALE")
        return _axis_matrix(self._coords(self.g(entity, "LocalOrigin")),
            self._direction(self.g(entity, "Axis1"), (1, 0, 0)),
            self._direction(self.g(entity, "Axis3"), (0, 0, 1)),
            self._direction(self.g(entity, "Axis2"), (0, 1, 0)), scales)

    def _unit(self, entity, seen=frozenset()):
        if entity.id() in seen:
            raise EnclosureUnknown("CYCLIC_UNIT")
        if self.g(entity, "UnitType") != "LENGTHUNIT":
            raise EnclosureUnknown("NON_LENGTH_UNIT")
        if entity.is_a("IfcSIUnit"):
            if self.g(entity, "Name") != "METRE":
                raise EnclosureUnknown("UNSUPPORTED_SI_LENGTH_UNIT")
            powers = {None: 0, "EXA": 18, "PETA": 15, "TERA": 12, "GIGA": 9, "MEGA": 6, "KILO": 3,
                "HECTO": 2, "DECA": 1, "DECI": -1, "CENTI": -2, "MILLI": -3, "MICRO": -6, "NANO": -9,
                "PICO": -12, "FEMTO": -15, "ATTO": -18}
            prefix = self.g(entity, "Prefix")
            if prefix not in powers:
                raise EnclosureUnknown("UNKNOWN_SI_PREFIX")
            return Q(10) ** powers[prefix]
        if entity.is_a() == "IfcConversionBasedUnit":
            factor = self.g(entity, "ConversionFactor")
            value = self.g(factor, "ValueComponent")
            if not (isinstance(value, tuple) and len(value) == 2 and value[0] in ("IFCLENGTHMEASURE", "IFCREAL")
                    and len(value[1]) == 1 and isinstance(value[1][0], Q) and value[1][0] > 0):
                raise EnclosureUnknown("UNSUPPORTED_UNIT_CONVERSION")
            return value[1][0] * self._unit(self.g(factor, "UnitComponent"), seen | {entity.id()})
        raise EnclosureUnknown("UNSUPPORTED_LENGTH_UNIT")

    def _length_scale(self):
        projects = [self.model.by_id(number) for number in self._source_project_ids]
        if len(projects) != 1:
            raise EnclosureUnknown("AMBIGUOUS_PROJECT_UNITS")
        assignment = self.g(projects[0], "UnitsInContext")
        if assignment is None:
            raise EnclosureUnknown("MISSING_PROJECT_UNITS")
        units = [u for u in self.g(assignment, "Units") if self.g(u, "UnitType") == "LENGTHUNIT"]
        if len(units) != 1:
            raise EnclosureUnknown("AMBIGUOUS_LENGTH_UNIT")
        return self._unit(units[0])

    def _context(self, context):
        seen = set()
        while context and context.is_a("IfcGeometricRepresentationSubContext"):
            if context.id() in seen:
                raise EnclosureUnknown("CYCLIC_REPRESENTATION_CONTEXT")
            seen.add(context.id())
            context = self.g(context, "ParentContext")
        if not context or not context.is_a("IfcGeometricRepresentationContext"):
            raise EnclosureUnknown("MISSING_GEOMETRIC_CONTEXT")
        if not _is_identity(self._axis(self.g(context, "WorldCoordinateSystem"))):
            raise EnclosureUnknown("NONIDENTITY_CONTEXT_FRAME")

    def _planar(self, points):
        if len(points) < 3:
            raise EnclosureUnknown("INVALID_POLYGON_ARITY")
        # Every polygon interior is contained in the convex hull of its vertices.
        # Exact planarity excludes a CAD kernel choosing an undeclared projection.
        a = points[0]
        normal_pair = None
        for b, c in zip(points[1:], points[2:]):
            u, v = tuple(b[i]-a[i] for i in range(3)), tuple(c[i]-a[i] for i in range(3))
            if any(_cross(u, v)):
                normal_pair = (b, c)
                break
        if normal_pair and any(orient3d(a, *normal_pair, p) != 0 for p in points):
            if not self.vertex_hull_completion:
                raise EnclosureUnknown("NONPLANAR_SOURCE_POLYGON")
            self.nonplanar_polygons += 1

    def _points(self, item):
        if item.is_a("IfcPolygonalFaceSet") or item.is_a("IfcTriangulatedFaceSet"):
            coordinates = self.g(item, "Coordinates")
            points = self.g(coordinates, "CoordList")
            if not points or any(len(p) != 3 or any(not isinstance(v, Q) for v in p) for p in points):
                raise EnclosureUnknown("INVALID_SOURCE_POINT_LIST")
            pn = self.g(item, "PnIndex")

            def resolve(indices):
                result = []
                for index in indices:
                    if not isinstance(index, Q) or index.denominator != 1:
                        raise EnclosureUnknown("NONINTEGER_FACE_INDEX")
                    index = int(index)
                    if pn is not None:
                        if not 1 <= index <= len(pn):
                            raise EnclosureUnknown("FACE_INDEX_OUT_OF_RANGE")
                        index = pn[index-1]
                        if not isinstance(index, Q) or index.denominator != 1:
                            raise EnclosureUnknown("NONINTEGER_PN_INDEX")
                        index = int(index)
                    if not 1 <= index <= len(points):
                        raise EnclosureUnknown("POINT_INDEX_OUT_OF_RANGE")
                    result.append(points[index-1])
                self._planar(result)
                return result

            result = []
            if item.is_a("IfcTriangulatedFaceSet"):
                faces = self.g(item, "CoordIndex")
                for face in faces:
                    if len(face) != 3:
                        raise EnclosureUnknown("NONTRIANGULAR_SOURCE_FACE")
                    result.extend(resolve(face))
            else:
                faces = self.g(item, "Faces")
                for face in faces:
                    if not face.is_a("IfcIndexedPolygonalFace"):
                        raise EnclosureUnknown("UNSUPPORTED_INDEXED_FACE")
                    result.extend(resolve(self.g(face, "CoordIndex")))
                    for loop in self.g(face, "InnerCoordIndices", ()) or ():
                        result.extend(resolve(loop))
            if not result:
                raise EnclosureUnknown("EMPTY_SOURCE_FACE_SET")
            return result, len(faces)
        if item.is_a("IfcFacetedBrep"):
            shells = [self.g(item, "Outer")] + list(self.g(item, "Voids", ()) or ())
        elif item.is_a("IfcShellBasedSurfaceModel"):
            shells = self.g(item, "SbsmBoundary")
        elif item.is_a("IfcFaceBasedSurfaceModel"):
            shells = self.g(item, "FbsmFaces")
        else:
            raise EnclosureUnknown("UNSUPPORTED_REPRESENTATION_ITEM:" + item.is_a())
        result, face_count = [], 0
        for shell in shells:
            for face in self.g(shell, "CfsFaces"):
                if face.is_a() != "IfcFace":
                    raise EnclosureUnknown("UNSUPPORTED_NONPLANAR_FACE")
                all_points = []
                for bound in self.g(face, "Bounds"):
                    loop = self.g(bound, "Bound")
                    if not loop.is_a("IfcPolyLoop"):
                        raise EnclosureUnknown("UNSUPPORTED_FACE_LOOP")
                    all_points.extend(self._coords(p) for p in self.g(loop, "Polygon"))
                self._planar(all_points)
                result.extend(all_points)
                face_count += 1
        if not result:
            raise EnclosureUnknown("EMPTY_SOURCE_FACE_SET")
        return result, face_count

    def _support(self, item, transform, coverage, seen=frozenset()):
        if not self.memoize_item_support:
            return self._support_uncached(item, transform, coverage, seen)
        if item.id() in seen:
            raise EnclosureUnknown("CYCLIC_GEOMETRIC_OPERAND")
        # Source bytes are captured by StepRationals. Numeric values and entity
        # references come from those bytes, never later mutable model values.
        key = (self.raw.source_sha256, CODE_SHA256, self.vertex_hull_completion, item.id())
        cached = self._support_cache.get(key)
        if cached is None:
            self.support_cache_misses += 1
            local_coverage = []
            before = self.nonplanar_polygons
            local_points = self._support_uncached(item, _identity(), local_coverage, seen)
            lo, hi = _box(local_points)
            nonplanar = self.nonplanar_polygons - before
            # Only complete successful item trees enter the cache. Failed
            # operands and unsupported siblings never acquire a bound.
            cached = (lo, hi, deepcopy(local_coverage), nonplanar)
            self._support_cache[key] = cached
        else:
            self.support_cache_hits += 1
            self.nonplanar_polygons += cached[3]
        lo, hi, local_coverage, _ = cached
        coverage.extend(deepcopy(local_coverage))
        # Affine images preserve containment. Rotating an item-local AABB may
        # enlarge the result; it cannot justify inferring collision or solidity.
        return [_apply(transform, point) for point in _box_corners(lo, hi)]

    def _support_uncached(self, item, transform, coverage, seen=frozenset()):
        if item.id() in seen:
            raise EnclosureUnknown("CYCLIC_GEOMETRIC_OPERAND")
        seen = seen | {item.id()}
        if item.is_a() == "IfcExtrudedAreaSolid":
            depth = self._positive(item,"Depth")
            direction = self._coords(self.g(item,"ExtrudedDirection"),"DirectionRatios")
            if direction[2] == 0:
                raise EnclosureUnknown("EXTRUSION_DIRECTION_PARALLEL_TO_PROFILE")
            delta = tuple(v*depth for v in _normalise(direction))
            profile = self.g(item,"SweptArea")
            base = self._profile(profile)
            local = base + [tuple(p[i]+delta[i] for i in range(3)) for p in base]
            position = _compose(transform,self._axis(self.g(item,"Position")))
            result = [_apply(position,p) for p in local]
            coverage.append({"step_id":item.id(),"type":item.is_a(),
                "profile_step_id":profile.id(),"profile_type":profile.is_a(),
                "source_depth":str(depth),"source_direction":[str(v) for v in direction],
                "support":"COMPLETE_LINEAR_EXTRUSION_OF_EXACT_PROFILE_ENCLOSURE",
                "profile_semantics":"EXACT_SIMPLE_POLYGON_OR_POSITIVE_RECTANGLE_OR_CIRCLE",
                "source_holes_checked":len(self.g(profile,"InnerCurves",()) or ())})
            return result
        if item.is_a("IfcBooleanResult"):
            operator = self.g(item,"Operator")
            if operator not in ("DIFFERENCE","UNION","INTERSECTION"):
                raise EnclosureUnknown("UNSUPPORTED_BOOLEAN_OPERATOR")
            if item.is_a("IfcBooleanClippingResult") and operator != "DIFFERENCE":
                raise EnclosureUnknown("INVALID_CLIPPING_OPERATOR")
            first, second = self.g(item,"FirstOperand"),self.g(item,"SecondOperand")
            # Both operand definitions must be interpretable. A malformed or
            # unsupported sibling is not rescued merely because A\B subset A.
            first_box = _box(self._support(first,transform,coverage,seen))
            second_box = _box(self._support(second,transform,coverage,seen))
            if operator == "DIFFERENCE":
                lo,hi = first_box
            elif operator == "UNION":
                lo = tuple(min(first_box[0][i],second_box[0][i]) for i in range(3))
                hi = tuple(max(first_box[1][i],second_box[1][i]) for i in range(3))
            else:
                lo = tuple(max(first_box[0][i],second_box[0][i]) for i in range(3))
                hi = tuple(min(first_box[1][i],second_box[1][i]) for i in range(3))
                if any(a>=b for a,b in zip(lo,hi)):
                    raise EnclosureUnknown("EMPTY_OR_DEGENERATE_BOOLEAN_SOLID_BOUND")
            coverage.append({"step_id":item.id(),"type":item.is_a(),"operator":operator,
                "operand_step_ids":[first.id(),second.id()],
                "support":"REGULARIZED_BOOLEAN_CONTAINMENT_IN_CLOSED_OUTER_BOXES",
                "exact_result_topology":"NOT_ESTABLISHED"})
            return _box_corners(lo,hi)
        previous_nonplanar = self.nonplanar_polygons
        local,count = self._points(item)
        # Item-local caching evaluates many face vertices in the exact identity
        # frame. Keep the same directed rounding as _apply while avoiding twelve
        # interval products per vertex. This is exact equality, not a near-identity
        # tolerance; nonidentity affine transforms still take the full path.
        result = ([tuple(_outward(_iv(v)) for v in p) for p in local] if _is_identity(transform)
                  else [_apply(transform,p) for p in local])
        coverage.append({"step_id":item.id(),"type":item.is_a(),"source_faces":count,
            "source_vertex_occurrences":len(local),"nonplanar_polygon_checks":self.nonplanar_polygons-previous_nonplanar,
            "support":"VERTEX_HULL_COMPLETION_FAMILY" if self.vertex_hull_completion else "PLANAR_VERTEX_CONVEX_HULL_ENCLOSURE"})
        return result

    def _representation(self, representation, transform, points, coverage, seen=frozenset()):
        if representation.id() in seen:
            raise EnclosureUnknown("CYCLIC_MAPPED_REPRESENTATION")
        self._context(self.g(representation, "ContextOfItems"))
        items = self.g(representation, "Items")
        if not items:
            raise EnclosureUnknown("EMPTY_REPRESENTATION")
        for item in items:
            if item.is_a("IfcMappedItem"):
                source = self.g(item, "MappingSource")
                origin = self._axis(self.g(source, "MappingOrigin"))
                if not _is_identity(origin):
                    raise EnclosureUnknown("NONIDENTITY_MAPPING_ORIGIN_REQUIRES_SEMANTIC_AUDIT")
                mapping = self._operator(self.g(item, "MappingTarget"))
                self._representation(self.g(source, "MappedRepresentation"), _compose(transform, mapping), points, coverage, seen | {representation.id()})
                coverage.append({"step_id": item.id(), "type": item.is_a(), "support": "COMPLETE_MAPPED_CHILDREN"})
            else:
                points.extend(self._support(item,transform,coverage))

    def enclose_product(self, product):
        with self._lock:
            return self._enclose_product(product)

    def _enclose_product(self, product):
        self.nonplanar_polygons = 0
        base = {"schema": "oma.ifc.source-enclosure/2", "source_sha256": self.raw.source_sha256,
            "checker_code_sha256": CODE_SHA256,
            "support_evaluation": "COMPLETE_ITEM_LOCAL_BOX_THEN_OUTWARD_AFFINE" if self.memoize_item_support else "DIRECT_OUTWARD_AFFINE_SUPPORT",
            "product_step_id": product.id(), "frame": "IFC_LOCAL_ENGINEERING_METRES",
            "claim": "ALL_SELECTED_BODY_SUPPORTED_REPRESENTED_SUPPORT_IS_SUBSET_OF_OUTER_BOX",
            "analytic_support": "POSITIVE_LINEAR_EXTRUSIONS_AND_SUPPORTED_REGULARIZED_BOOLEANS",
            "whole_product_solid_validity": "NOT_ESTABLISHED", "unrepresented_physical_extent": "UNKNOWN"}
        if self.vertex_hull_completion:
            base.update({"claim": "ALL_SOURCE_VERTEX_HULL_COMPLETIONS_SUBSET_OF_OUTER_BOX",
                "geometry_interpretation": "EACH_FACE_SUPPORT_IS_ANY_SUBSET_OF_ITS_DECLARED_VERTEX_CONVEX_HULL",
                "applicability_condition": "Authoritative represented support must use only those affine vertex interpolants/completions; arbitrary CAD projection or physical extent outside the hull is not covered",
                "original_nonplanar_face_validity": "NOT_ESTABLISHED"})
        coverage = []
        try:
            scale = self._length_scale()
            definition = self.g(product, "Representation")
            if definition is None:
                raise EnclosureUnknown("MISSING_PRODUCT_REPRESENTATION")
            representations = self.g(definition, "Representations")
            bodies = [r for r in representations if self.g(r, "RepresentationIdentifier") == "Body"]
            if not bodies:
                raise EnclosureUnknown("MISSING_AUTHORITATIVE_BODY")
            transform = self._placement(self.g(product, "ObjectPlacement"))
            points = []
            for representation in bodies:
                self._representation(representation, transform, points, coverage)
            if not points:
                raise EnclosureUnknown("EMPTY_BODY_SUPPORT")
            lo = tuple(min(p[i].lo * scale for p in points) for i in range(3))
            hi = tuple(max(p[i].hi * scale for p in points) for i in range(3))
            return {**base, "status": "ENCLOSURE_CHECKED", "bounds_m": [[str(v) for v in lo], [str(v) for v in hi]],
                "source_length_scale_m": str(scale), "body_representation_ids": [r.id() for r in bodies],
                "item_coverage": coverage, "arithmetic": "SOURCE_DECIMAL_RATIONAL_AND_OUTWARD_RATIONAL_INTERVAL",
                "nonplanar_polygon_checks": self.nonplanar_polygons,
                "ignored_nonbody_representations": [r.id() for r in representations if r not in bodies]}
        except (EnclosureUnknown, ValueError, TypeError, AttributeError, ZeroDivisionError, RecursionError) as exc:
            return {**base, "status": "UNKNOWN", "reason": str(exc), "item_coverage": coverage}
