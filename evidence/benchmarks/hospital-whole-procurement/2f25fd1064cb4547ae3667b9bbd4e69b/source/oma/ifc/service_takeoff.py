"""Source-rational straight-stock quantities; installed geometry is never edited.

An eligible piece is one supported constant-section source extrusion, with a
rigid mapping chain. Rectangular prisms need an independently declared length
axis; extrusion Depth alone can instead be a cable tray's height. Quantities
describe authored geometry, not bore, duties, material certification or CAD.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from fractions import Fraction as Q
import hashlib
import json
from math import isqrt
from pathlib import Path
import tempfile

from .enclosure import ExactIfcEncloser, EnclosureUnknown
from .enclosure import _apply as _interval_apply, _compose as _interval_compose, _iv
from .service_networks import extract_service_networks, validate_service_audit_source

SCHEMA = "oma.installed-service-takeoff/1"


def _bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def _root(value):
    return hashlib.sha256(_bytes(value)).hexdigest()


def _sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class Unsupported(ValueError):
    """A retained object lacks a supported, unambiguous linear quantity."""


def _require(condition, reason):
    if not condition:
        raise Unsupported(reason)


def _dot(a, b):
    return sum((x*y for x, y in zip(a, b)), Q(0))


def _cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def _normal(v):
    n = _dot(v, v)
    _require(n > 0, "DEGENERATE_FRAME")
    a, b = isqrt(n.numerator), isqrt(n.denominator)
    _require(a*a == n.numerator and b*b == n.denominator, "AXIS_REQUIRES_NONRATIONAL_FRAME")
    return tuple(x/Q(a, b) for x in v)


_ID = tuple(tuple(Q(int(i == j)) for j in range(4)) for i in range(4))


def _compose(a, b):
    return tuple(tuple(sum((a[i][k]*b[k][j] for k in range(4)), Q(0)) for j in range(4)) for i in range(4))


def _apply(m, p):
    return tuple(_dot(row, (*p, Q(1))) for row in m[:3])


def _inverse(m):
    rows = [tuple(m[j][i] for j in range(3)) for i in range(3)]
    p = tuple(m[i][3] for i in range(3))
    return tuple((*r, -_dot(r, p)) for r in rows) + ((Q(0), Q(0), Q(0), Q(1)),)


class _Reader:
    def __init__(self, path, model, max_mapping_depth):
        self.exact = ExactIfcEncloser(path, model)
        self.g = self.exact.g
        self.model = model
        self.max_depth = max_mapping_depth
        self.scale = self.length_scale()
        self.context_evidence = {}

    def length_scale(self):
        projects = self.model.by_type("IfcProject")
        _require(len(projects) == 1, "AMBIGUOUS_PROJECT_UNITS")
        assignment = self.g(projects[0], "UnitsInContext")
        _require(assignment is not None, "MISSING_PROJECT_UNITS")
        units = [u for u in self.g(assignment, "Units") if self.g(u, "UnitType") == "LENGTHUNIT"]
        _require(len(units) == 1, "AMBIGUOUS_LENGTH_UNIT")
        return self.unit(units[0])

    def unit(self, entity, seen=frozenset()):
        _require(entity.id() not in seen and len(seen) < self.max_depth, "UNIT_CYCLE_OR_DEPTH")
        _require(self.g(entity, "UnitType") == "LENGTHUNIT", "NON_LENGTH_UNIT")
        if entity.is_a() == "IfcConversionBasedUnit":
            dimensions = self.g(entity, "Dimensions")
            fields = ("LengthExponent", "MassExponent", "TimeExponent", "ElectricCurrentExponent", "ThermodynamicTemperatureExponent", "AmountOfSubstanceExponent", "LuminousIntensityExponent")
            _require(tuple(self.g(dimensions, k) for k in fields) == (1, 0, 0, 0, 0, 0, 0), "NON_LENGTH_UNIT_DIMENSIONS")
            factor = self.g(entity, "ConversionFactor"); value = self.g(factor, "ValueComponent")
            _require(isinstance(value, tuple) and len(value) == 2 and value[0] in
                     {"IFCLENGTHMEASURE", "IFCREAL", "IFCRATIOMEASURE", "IFCPOSITIVERATIOMEASURE"}
                     and len(value[1]) == 1 and isinstance(value[1][0], Q) and value[1][0] > 0, "UNSUPPORTED_UNIT_CONVERSION")
            return value[1][0] * self.unit(self.g(factor, "UnitComponent"), seen | {entity.id()})
        return self.exact._unit(entity)

    def number(self, entity, field, positive=False):
        n = self.g(entity, field)
        _require(isinstance(n, Q) and (not positive or n > 0), "INVALID_" + field.upper())
        return n

    def coords(self, entity, field="Coordinates", dimensions=3):
        p = self.g(entity, field)
        _require(isinstance(p, tuple) and len(p) == dimensions and all(isinstance(v, Q) for v in p), "INVALID_COORDINATES")
        return p

    def direction(self, entity, default):
        return self.coords(entity, "DirectionRatios", len(default)) if entity else tuple(map(Q, default))

    def axis(self, entity, *, matrix=False, dimensions=3):
        if entity is None:
            return _ID
        _require(entity.is_a() == f"IfcAxis2Placement{dimensions}D", "UNSUPPORTED_FRAME")
        p = self.coords(self.g(entity, "Location"), dimensions=dimensions)
        x = self.direction(self.g(entity, "RefDirection"), (1, 0) if dimensions == 2 else (1, 0, 0))
        if dimensions == 2:
            p, x, z = (*p, Q(0)), (*x, Q(0)), (Q(0), Q(0), Q(1))
        else:
            z = self.direction(self.g(entity, "Axis"), (0, 0, 1))
        _require(_dot(z, z) > 0 and _dot(_cross(x, z), _cross(x, z)) > 0, "DEGENERATE_FRAME")
        if not matrix:
            return _ID
        if matrix == "interval":
            return self.exact._axis2(entity) if dimensions == 2 else self.exact._axis(entity)
        z = _normal(z)
        x = _normal(tuple(a-_dot(x, z)*b for a, b in zip(x, z)))
        y = _cross(z, x)
        return tuple((x[i], y[i], z[i], p[i]) for i in range(3)) + (_ID[3],)

    def placement(self, placement):
        seen = set()
        while placement:
            _require(placement.id() not in seen and len(seen) < self.max_depth, "PLACEMENT_CYCLE_OR_DEPTH")
            seen.add(placement.id())
            _require(placement.is_a() == "IfcLocalPlacement", "UNSUPPORTED_PRODUCT_PLACEMENT")
            self.axis(self.g(placement, "RelativePlacement"))
            placement = self.g(placement, "PlacementRelTo")

    def operator(self, op, *, matrix=False):
        _require(op and op.is_a("IfcCartesianTransformationOperator3D"), "UNSUPPORTED_MAPPING_OPERATOR")
        scales = [self.g(op, k) for k in ("Scale", "Scale2", "Scale3")]
        s = Q(1) if scales[0] is None else scales[0]
        scales = [s, s if scales[1] is None else scales[1], s if scales[2] is None else scales[2]]
        _require(scales == [Q(1)]*3, "NONRIGID_MAPPING_SCALE")
        x = self.direction(self.g(op, "Axis1"), (1, 0, 0))
        y = self.direction(self.g(op, "Axis2"), (0, 1, 0))
        z = self.direction(self.g(op, "Axis3"), (0, 0, 1))
        _require(all(_dot(v, v) > 0 for v in (x, y, z)) and _dot(_cross(x, z), _cross(x, z)) > 0, "DEGENERATE_MAPPING_FRAME")
        # Conservative explicit orthogonal axes: unsupported shear-like hints
        # never become an assumed rigid transform.
        _require(_dot(x, y) == _dot(x, z) == _dot(y, z) == 0, "AMBIGUOUS_MAPPING_AXES")
        p = self.coords(self.g(op, "LocalOrigin"))
        if not matrix:
            return _ID
        if matrix == "interval":
            return self.exact._operator(op)
        x, y, z = map(_normal, (x, y, z))
        return tuple((x[i], y[i], z[i], p[i]) for i in range(3)) + (_ID[3],)

    def context(self, context):
        seen = set()
        while context and context.is_a("IfcGeometricRepresentationSubContext"):
            _require(context.id() not in seen and len(seen) < self.max_depth, "CONTEXT_CYCLE_OR_DEPTH")
            seen.add(context.id()); context = self.g(context, "ParentContext")
        _require(context and context.is_a("IfcGeometricRepresentationContext"), "MISSING_GEOMETRIC_CONTEXT")
        _require(self.g(context, "CoordinateSpaceDimension") == 3, "NON_3D_GEOMETRIC_CONTEXT")
        precision = self.g(context, "Precision")
        evidence = {"context_step_id": context.id(), "global_frame_status": "DEFINED_RIGID_FRAME_NOT_NATIVE_VERIFIED",
                    "declared_precision_m": str(precision*self.scale) if isinstance(precision, Q) and precision > 0 else None}
        try:
            self.axis(self.g(context, "WorldCoordinateSystem"))
        except (Unsupported, EnclosureUnknown, AttributeError, TypeError) as exc:
            evidence.update(global_frame_status="UNRESOLVED", reason=str(exc))
        self.context_evidence[context.id()] = evidence

    def item(self, item, *, matrix=False, seen=frozenset()):
        _require(item.id() not in seen and len(seen) < self.max_depth, "MAPPING_CYCLE_OR_DEPTH")
        if item.is_a() != "IfcMappedItem":
            return item, _ID, []
        source = self.g(item, "MappingSource"); target = self.g(item, "MappingTarget")
        rep = self.g(source, "MappedRepresentation")
        _require(rep is not None, "MISSING_MAPPED_REPRESENTATION")
        self.context(self.g(rep, "ContextOfItems"))
        items = self.g(rep, "Items")
        _require(isinstance(items, tuple) and len(items) == 1, "MULTI_ITEM_MAPPED_BODY")
        origin = self.axis(self.g(source, "MappingOrigin"), matrix=matrix)
        transform = self.operator(target, matrix=matrix)
        base, nested, chain = self.item(items[0], matrix=matrix, seen=seen | {item.id()})
        # IFC MappingOrigin positions the mapped representation; IfcOpenShell's
        # mapped-item contract composes target @ origin (not origin inverse).
        compose = _interval_compose if matrix == "interval" else _compose
        return base, compose(compose(transform, origin), nested), [item.id(), *chain]

    def endpoints(self, product, axis_reps, port_ids, *, bounded=False):
        if axis_reps:
            _require(len(axis_reps) == 1 and len(axis_reps[0].Items) == 1, "AMBIGUOUS_AXIS_REPRESENTATIONS")
            rep = axis_reps[0]; self.context(rep.ContextOfItems)
            item, transform, chain = self.item(rep.Items[0], matrix="interval" if bounded else True)
            if item.is_a() == "IfcPolyline":
                points = [self.coords(p) for p in self.g(item, "Points")]
            elif item.is_a() == "IfcIndexedPolyCurve":
                _require(self.g(item, "Segments") is None, "CURVED_OR_SEGMENTED_AXIS")
                points = list(self.g(self.g(item, "Points"), "CoordList"))
            else:
                raise Unsupported("UNSUPPORTED_AXIS:" + item.is_a())
            _require(len(points) == 2 and all(len(p) == 3 and all(isinstance(v, Q) for v in p) for p in points), "NON_SINGLE_STRAIGHT_AXIS")
            apply = _interval_apply if bounded else _apply
            return [apply(transform, p) for p in points], {"method": "EXPLICIT_STRAIGHT_AXIS", "axis_step_id": item.id(), "mapping_step_ids": chain}
        _require(len(port_ids) == 2, "RECTANGULAR_LONGITUDINAL_AXIS_UNRESOLVED")
        points = []
        for pid in port_ids:
            port = self.model.by_id(pid); place = port.ObjectPlacement
            _require(place and place.is_a() == "IfcLocalPlacement" and place.PlacementRelTo == product.ObjectPlacement,
                     "PORT_PLACEMENT_NOT_DIRECTLY_OWNER_RELATIVE")
            frame = self.g(place, "RelativePlacement"); self.axis(frame)
            points.append(self.coords(self.g(frame, "Location")))
        return points, {"method": "TWO_EXPLICIT_OWNED_PORTS", "port_step_ids": port_ids}

    def geometry(self, product, port_ids):
        _require(not getattr(product, "HasOpenings", ()), "OPENINGS_REQUIRE_NONLINEAR_FABRICATION")
        _require(not getattr(product, "HasProjections", ()), "PROJECTIONS_REQUIRE_NONLINEAR_FABRICATION")
        _require(not any(child.is_a("IfcElement") for rel in (*getattr(product, "IsDecomposedBy", ()), *getattr(product, "IsNestedBy", ())) for child in rel.RelatedObjects),
                 "COMPOSITE_SEGMENT_REQUIRES_COMPONENT_TAKEOFF")
        placement = {"placement_step_id": product.ObjectPlacement.id() if product.ObjectPlacement else None,
                     "status": "DEFINED_RIGID_FRAME_NOT_NATIVE_VERIFIED", "used_for_stock_length": False}
        try:
            _require(product.ObjectPlacement is not None, "MISSING_PRODUCT_PLACEMENT")
            self.placement(product.ObjectPlacement)
        except (Unsupported, EnclosureUnknown, AttributeError, TypeError) as exc:
            placement.update(status="UNRESOLVED_GLOBAL_PLACEMENT", reason=str(exc))
        self.context_evidence = {}
        reps = list(getattr(product.Representation, "Representations", ()) or ())
        bodies = [r for r in reps if r.RepresentationIdentifier == "Body"]
        axes = [r for r in reps if r.RepresentationIdentifier == "Axis"]
        _require(len(bodies) == 1 and len(bodies[0].Items) == 1, "MISSING_OR_MULTIPLE_BODY_ITEMS")
        self.context(bodies[0].ContextOfItems)
        solid, _, chain = self.item(bodies[0].Items[0])
        _require(solid.is_a() == "IfcExtrudedAreaSolid", "UNSUPPORTED_BODY:" + solid.is_a())
        self.axis(self.g(solid, "Position"))
        direction = self.coords(self.g(solid, "ExtrudedDirection"), "DirectionRatios")
        _require(direction[0] == direction[1] == 0 and direction[2] != 0, "OBLIQUE_EXTRUSION")
        depth = self.number(solid, "Depth", True)
        profile = self.g(solid, "SweptArea"); kind = profile.is_a()
        _require(self.g(profile, "ProfileType") == "AREA", "NON_AREA_PROFILE")
        self.axis(self.g(profile, "Position"), dimensions=2)
        provenance = {"body_representation_step_id": bodies[0].id(), "solid_step_id": solid.id(),
                      "profile_step_id": profile.id(), "mapping_step_ids": chain,
                      "source_unit_to_m": str(self.scale), "source_extrusion_depth": str(depth),
                      "length_arithmetic": "EXACT_DECIMAL_STEP_RATIONAL", "hydraulic_bore_inferred": False,
                      "global_placement": placement, "representation_contexts": list(self.context_evidence.values()),
                      "quantity_authority": "LOCAL_AUTHORED_PARAMETRIC_BODY_ONLY", "global_geometry_verified": False}
        if kind in {"IfcCircleProfileDef", "IfcCircleHollowProfileDef"}:
            radius = self.number(profile, "Radius", True)
            section = {"shape": "CIRCULAR", "authored_profile_type": kind, "outer_diameter_m": str(2*radius*self.scale)}
            if kind == "IfcCircleHollowProfileDef":
                wall = self.number(profile, "WallThickness", True)
                _require(wall < radius, "INVALID_HOLLOW_PROFILE")
                section["authored_wall_thickness_m"] = str(wall*self.scale)
            # The circle's symmetry fixes its longitudinal axis. An additional
            # declared Axis is checked, never allowed to contradict the Body.
            if axes:
                _, declared_axis = self._match_axis(product, bodies[0].Items[0], solid, profile, depth, axes, port_ids, circular=True)
                provenance["declared_axis_validation"] = declared_axis
            provenance["axis_evidence"] = {"method": "NORMAL_CIRCULAR_EXTRUSION", "extruded_direction_step_id": solid.ExtrudedDirection.id()}
            return depth*self.scale, section, provenance
        _require(kind == "IfcRectangleProfileDef", "UNSUPPORTED_PROFILE:" + kind)
        dimensions = (self.number(profile, "XDim", True), self.number(profile, "YDim", True), depth)
        choice, evidence = self._match_axis(product, bodies[0].Items[0], solid, profile, depth, axes, port_ids)
        transverse = [dimensions[i]*self.scale for i in range(3) if i != choice]
        section = {"shape": "RECTANGULAR", "authored_profile_type": kind,
                   "width_m": str(transverse[0]), "height_m": str(transverse[1])}
        provenance["axis_evidence"] = evidence
        provenance["longitudinal_prism_axis"] = choice
        return dimensions[choice]*self.scale, section, provenance

    def _match_axis(self, product, item, solid, profile, depth, axes, port_ids, circular=False):
        try:
            return self._axis_match(product, item, solid, profile, depth, axes, port_ids, circular=circular)
        except Unsupported as exc:
            if str(exc) not in {"AXIS_REQUIRES_NONRATIONAL_FRAME", "AXIS_BODY_LENGTH_OR_ALIGNMENT_AMBIGUOUS"}:
                raise
        return self._axis_match(product, item, solid, profile, depth, axes, port_ids, circular=circular, bounded=True)

    def _axis_match(self, product, item, solid, profile, depth, axes, port_ids, *, circular=False, bounded=False):
        # A rational interval encloses every irrational normalisation/rotation.
        # Only IFC-authored positive Precision can permit an endpoint mismatch;
        # no default epsilon, product-specific snap or inferred axis is used.
        matrix = "interval" if bounded else True
        compose, apply = (_interval_compose, _interval_apply) if bounded else (_compose, _apply)
        _, mapping, _ = self.item(item, matrix=matrix)
        body = compose(mapping, self.axis(self.g(solid, "Position"), matrix=matrix))
        section = self.axis(self.g(profile, "Position"), matrix=matrix, dimensions=2)
        frame = compose(body, section)
        sign = Q(1) if self.coords(solid.ExtrudedDirection, "DirectionRatios")[2] > 0 else Q(-1)
        center = apply(body, (*[section[i][3] for i in range(2)], sign*depth/2))
        points, evidence = self.endpoints(product, axes, port_ids, bounded=bounded)
        dims = (Q(0), Q(0), depth) if circular else (self.number(profile, "XDim", True), self.number(profile, "YDim", True), depth)
        if bounded:
            contexts = list(self.context_evidence.values())
            _require(contexts and all(c["declared_precision_m"] is not None for c in contexts), "AXIS_ENDPOINT_MATCH_NEEDS_DECLARED_PRECISION")
            tolerance_m = min(Q(1, 10_000), *(Q(c["declared_precision_m"]) for c in contexts))
            tolerance2 = (tolerance_m/self.scale)**2
            choices, possible, residuals = [], [], {}
            for axis in ((2,) if circular else range(3)):
                expected = [tuple(_iv(center[i])+s*dims[axis]*_iv(frame[i][axis])/2 for i in range(3)) for s in (-1, 1)]
                orders = []
                for ordered in (points, points[::-1]):
                    distances2 = [sum(((_iv(ordered[j][i]) - expected[j][i]).square() for i in range(3)), _iv(0)) for j in range(2)]
                    orders.append((max(d.lo for d in distances2), max(d.hi for d in distances2)))
                lower, upper = min(o[0] for o in orders), min(o[1] for o in orders)
                if lower <= tolerance2:
                    possible.append(axis)
                if upper <= tolerance2:
                    choices.append(axis); residuals[axis] = upper*self.scale**2
            _require(len(choices) == len(possible) == 1 and choices == possible, "AXIS_BODY_LENGTH_OR_ALIGNMENT_AMBIGUOUS")
            evidence.update(exact_body_endpoints_matched=False, bounded_body_endpoints_matched=True,
                            endpoint_tolerance_m=str(tolerance_m), maximum_endpoint_residual_squared_m2=str(residuals[choices[0]]),
                            endpoint_arithmetic="OUTWARD_RATIONAL_INTERVALS", unique_axis_proven_within_declared_precision=True,
                            body_dimension_adjusted=False, context_precisions=contexts,
                            endpoints_product_units_intervals=[[ _iv(v).encoded() for v in p] for p in points])
            return choices[0], evidence
        choices = []
        for axis in ((2,) if circular else range(3)):
            v = tuple(frame[i][axis] for i in range(3))
            expected = {tuple(center[i]+s*dims[axis]*v[i]/2 for i in range(3)) for s in (-1, 1)}
            if set(points) == expected:
                choices.append(axis)
        _require(len(choices) == 1, "AXIS_BODY_LENGTH_OR_ALIGNMENT_AMBIGUOUS")
        evidence["endpoints_product_units"] = [[str(v) for v in p] for p in points]
        evidence["exact_body_endpoints_matched"] = True
        return choices[0], evidence


def _identity(entity):
    return {"step_id": entity.id(), "ifc_type": entity.is_a(),
            "ifc_guid": getattr(entity, "GlobalId", None), "name": getattr(entity, "Name", None),
            "predefined_type": getattr(entity, "PredefinedType", None)}


def _metadata(product, source, systems):
    types = {r.RelatingType.id(): r.RelatingType for r in (*getattr(product, "IsTypedBy", ()), *getattr(product, "IsDefinedBy", ()))
             if r.is_a("IfcRelDefinesByType")}
    materials, relationships = {}, []
    for owner in (product, *types.values()):
        for relation in getattr(owner, "HasAssociations", ()):
            if relation.is_a("IfcRelAssociatesMaterial"):
                mat = relation.RelatingMaterial
                materials[mat.id()] = {**_identity(mat), "definition_root": _root({"source_sha256": source, "step_id": mat.id()})}
                relationships.append({"relationship_step_id": relation.id(), "owner_step_id": owner.id(), "material_step_id": mat.id()})
    containers = {_identity(r.RelatingStructure)["step_id"]: _identity(r.RelatingStructure)
                  for r in getattr(product, "ContainedInStructure", ())}
    pending = [r.RelatingStructure for r in getattr(product, "ContainedInStructure", ())]
    seen, storeys = set(), {}
    while pending:
        entity = pending.pop()
        if entity.id() in seen:
            continue
        seen.add(entity.id())
        if entity.is_a("IfcBuildingStorey"):
            storeys[entity.id()] = _identity(entity)
        else:
            pending.extend(r.RelatingObject for r in getattr(entity, "Decomposes", ()))
    return {"ifc_types": [_identity(types[k]) for k in sorted(types)],
            "materials": [materials[k] for k in sorted(materials)], "material_relationships": sorted(relationships, key=lambda x: x["relationship_step_id"]),
            "material_status": "AUTHORED_ASSOCIATIONS_NOT_QUALIFIED" if materials else "MISSING_MATERIAL_REQUIRES_COMPATIBILITY_ASSUMPTION",
            "system_step_ids": systems, "spatial_containers": [containers[k] for k in sorted(containers)],
            "storeys": [storeys[k] for k in sorted(storeys)], "storey_step_ids": sorted(storeys),
            "storey_status": "EXPLICIT_UNIQUE" if len(storeys) == 1 else "EXPLICIT_MULTIPLE" if storeys else "MISSING",
            "stock_compatibility_verified": False}


def _stock_kind(product, metadata, profile):
    declared = {product.is_a(), *(t["ifc_type"] for t in metadata["ifc_types"])}
    kinds = set()
    for kind, names in {"PIPE": {"IfcPipeSegment", "IfcPipeSegmentType"},
                        "DUCT": {"IfcDuctSegment", "IfcDuctSegmentType"},
                        "CABLE_CARRIER": {"IfcCableCarrierSegment", "IfcCableCarrierSegmentType"},
                        "CABLE": {"IfcCableSegment", "IfcCableSegmentType"}}.items():
        if declared & names:
            kinds.add(kind)
    if len(kinds) != 1:
        return "UNCLASSIFIED_SEGMENT"
    kind = next(iter(kinds))
    return "DUCT_" + profile["shape"] if kind == "DUCT" else kind


def extract_service_takeoff(audit: dict, source_path, *, source_discipline=None, checkpoint=None,
                            max_source_bytes=512*1024*1024, max_mapping_depth=32) -> dict:
    """Return an exhaustive retained-object ledger and supported stock pieces.

    ``length_m`` is a rational string, ``id`` is ``{sha}:#{STEP}``, and
    ``batch_id`` is the explicit installed component ID. Grouping has no
    cross-source pooling. Same IFC type/profile/material association is only an
    explicit procurement compatibility assumption, never material approval.
    """
    import ifcopenshell
    if type(max_source_bytes) is not int or max_source_bytes <= 0 or type(max_mapping_depth) is not int or not 1 <= max_mapping_depth <= 128:
        raise ValueError("Positive bounded takeoff resource limits required")
    path = Path(source_path).resolve()
    if path.stat().st_size > max_source_bytes:
        raise ValueError("Source byte budget exceeded")
    original_audit_root = _root(audit)
    frozen = json.loads(_bytes(audit))
    source = frozen.get("source_sha256")
    pulse = checkpoint or (lambda stage: None)
    reconciliation = validate_service_audit_source(frozen, path, checkpoint=pulse)
    graph = extract_service_networks(frozen, source_discipline=source_discipline, checkpoint=pulse)
    if graph["missing_audit_collections"] or not graph["accounting"]["declared_audit_denominators_consistent"]:
        raise ValueError("Complete consistent imported audit required")
    product_rows = {p["step_id"]: p for p in graph["products"]}
    membership = {pid: n["id"] for n in graph["networks"] for pid in n["product_step_ids"]}
    owner_ports = defaultdict(list)
    for p in graph["ports"]:
        owners = p.get("owner_step_ids", [])
        if len(owners) == 1:
            owner_ports[owners[0]].append(p["step_id"])
    pieces, retained, groups = [], [], {}
    with tempfile.TemporaryDirectory(prefix="oma-service-takeoff-") as tmp:
        private = Path(tmp)/"source.ifc"
        copied = 0; h = hashlib.sha256()
        with path.open("rb") as stream, private.open("wb") as target:
            while chunk := stream.read(8*1024*1024):
                copied += len(chunk)
                if copied > max_source_bytes:
                    raise ValueError("Source byte budget exceeded")
                pulse("service_takeoff_copy"); h.update(chunk); target.write(chunk)
        if h.hexdigest() != source:
            raise ValueError("Source hash changed before takeoff")
        model = ifcopenshell.open(str(private))
        raw_segments = {p.id() for p in model.by_type("IfcFlowSegment")}
        if not raw_segments <= set(membership):
            raise ValueError("FlowSegment missing from service population")
        reader = None; unit_error = None
        if raw_segments:
            try:
                reader = _Reader(private, model, max_mapping_depth)
                if reader.exact.raw.source_sha256 != source:
                    raise ValueError("Parsed private source changed before exact takeoff")
            except (EnclosureUnknown, Unsupported) as exc:
                unit_error = str(exc)
        for index, pid in enumerate(sorted(membership)):
            if index % 128 == 0:
                pulse("service_takeoff_products")
            p = model.by_id(pid); row = product_rows[pid]
            metadata = _metadata(p, source, sorted(map(int, row.get("system_ids", []))))
            record = {"id": f"{source}:#{pid}", "source_id": source, "source_sha256": source,
                      "step_id": pid, "ifc_guid": p.GlobalId, "ifc_type": p.is_a(), "name": p.Name,
                      "predefined_type": getattr(p, "PredefinedType", None), "object_type": getattr(p, "ObjectType", None),
                      "network_id": membership[pid], "batch_id": membership[pid],
                      "port_step_ids": sorted(owner_ports[pid]), "source_discipline": source_discipline,
                      "source_audit_record_sha256": row["source_record_sha256"], **metadata}
            if pid not in raw_segments:
                record.update(status="RETAINED_UNCHANGED", reason="NOT_A_FLOW_SEGMENT")
            else:
                try:
                    if unit_error:
                        raise Unsupported(unit_error)
                    length, profile, evidence = reader.geometry(p, record["port_step_ids"])
                    kind = _stock_kind(p, metadata, profile)
                    group_definition = {"source_sha256": source, "ifc_occurrence_type": p.is_a(), "stock_kind": kind,
                                        "occurrence_predefined_type": record["predefined_type"], "occurrence_object_type": record["object_type"],
                                        "ifc_types": metadata["ifc_types"], "materials": metadata["materials"],
                                        "material_status": metadata["material_status"], "profile_si": profile}
                    # Missing authored type cannot justify pooling unrelated
                    # unnamed occurrences merely because dimensions coincide.
                    if not metadata["ifc_types"]:
                        group_definition["untyped_occurrence_step_id"] = pid
                    group_id = "service-stock:" + _root(group_definition)
                    piece = {**record, "status": "AUTHORED_STRAIGHT_STOCK_QUANTITY", "length_m": str(length),
                             "profile_si": profile, "stock_kind": kind, "stock_group": group_id,
                             "geometry_evidence": evidence, "installed_geometry_changed": False,
                             "engineering_status": "NOT_VERIFIED"}
                    pieces.append(piece)
                    group = groups.setdefault(group_id, {"id": group_id, "definition": group_definition,
                        "piece_ids": [], "total_length_m": "0", "compatibility_status": "REQUIRES_EXPLICIT_CALLER_ASSUMPTION"})
                    group["piece_ids"].append(piece["id"]); group["total_length_m"] = str(Q(group["total_length_m"])+length)
                    record.update(status="RETAINED_WITH_STRAIGHT_TAKEOFF", reason="SUPPORTED_SOURCE_GEOMETRY", piece_id=piece["id"])
                except (Unsupported, EnclosureUnknown) as exc:
                    record.update(status="RETAINED_UNSUPPORTED_LINEAR_TAKEOFF", reason=str(exc))
                except (AttributeError, TypeError, IndexError) as exc:
                    record.update(status="RETAINED_UNSUPPORTED_LINEAR_TAKEOFF", reason="MALFORMED_GEOMETRY:" + type(exc).__name__)
            retained.append(record)
        if _sha(private) != source:
            raise ValueError("Parsed private source changed during takeoff")
        del reader, model
    result = {"schema": SCHEMA, "status": "SOURCE_BOUND_TAKEOFF_WITH_EXPLICIT_REMAINDERS", "source_sha256": source,
              "source_discipline": source_discipline, "audit_root": original_audit_root, "source_reconciliation": reconciliation,
              "source_graph_root": graph["graph_sha256"], "summary": {"source_product_count": graph["summary"]["source_product_count"],
                  "service_object_count": len(retained), "flow_segment_count": len(raw_segments), "eligible_piece_count": len(pieces),
                  "unsupported_segment_count": len(raw_segments)-len(pieces), "stock_group_count": len(groups),
                  "total_eligible_length_m": str(sum((Q(p["length_m"]) for p in pieces), Q(0))),
                  "retained_reason_counts": dict(sorted(Counter(r["reason"] for r in retained).items())),
                  "stock_kind_counts": dict(sorted(Counter(p["stock_kind"] for p in pieces).items()))},
              "pieces": pieces, "retained_objects": retained, "stock_groups": [groups[k] for k in sorted(groups)],
              "accounting": {"all_service_objects_retained_once": len(retained) == len({r["step_id"] for r in retained}) == len(membership),
                  "all_flow_segments_dispositioned": len(raw_segments) == sum(r["step_id"] in raw_segments for r in retained),
                  "all_other_source_products_accounted_by_category": graph["accounting"]["products_by_category"],
                  "original_source_completeness_verified": True, "source_product_count": graph["summary"]["source_product_count"]},
              "scope": "Exact authored parametric straight-stock quantities only. No geometry edits, hydraulic bore/duty inference, native clearance, material qualification, structural safety or installed connection certification. Unknown material and same-type stock pooling require an explicit procurement scenario assumption."}
    pulse("service_takeoff_complete")
    if _root(audit) != original_audit_root:
        raise ValueError("Audit changed during service takeoff")
    if _sha(path) != source:
        raise ValueError("Source changed during service takeoff")
    result["takeoff_root"] = _root(result)
    return result
