"""Materialize physical round routes in a copy of an IFC2X3/IFC4 model.

Unedited STEP entities are preserved; new pieces have explicit system/port
connectivity, exact straight/arc swept envelopes, and scenario provenance.
This writer does not attach an engineering PASS label to unverified geometry.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import uuid

import numpy as np

from .audit import atomic_json, sha256_file


def _guid(namespace: str, key: str) -> str:
    import ifcopenshell.guid
    return ifcopenshell.guid.compress(uuid.uuid5(uuid.NAMESPACE_URL, namespace + ":" + key).hex)


def fillet_route(points, bend_radius_m: float, minimum_straight_m: float = 0.0) -> list[dict]:
    """Construct exact tangent lines and circular arcs for a filleted polyline."""
    points = np.asarray(points, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 3 or len(points) < 2 or not np.isfinite(points).all():
        raise ValueError("Route needs at least two finite xyz points")
    vectors = np.diff(points, axis=0)
    lengths = np.linalg.norm(vectors, axis=1)
    if (lengths <= 1e-9).any():
        raise ValueError("Repeated route points / zero length segment")
    unit = vectors / lengths[:, None]
    trims = np.zeros(len(points))
    arcs = {}
    for i in range(1, len(points)-1):
        incoming, outgoing = unit[i-1], unit[i]
        theta = math.acos(float(np.clip(np.dot(incoming, outgoing), -1.0, 1.0)))
        if theta < 1e-8:
            continue
        if math.pi - theta < 1e-6 or bend_radius_m <= 0:
            raise ValueError("U-turn or missing positive bend radius is unsupported")
        trim = bend_radius_m * math.tan(theta / 2)
        trims[i] = trim
        normal = np.cross(incoming, outgoing)
        normal /= np.linalg.norm(normal)
        start, end = points[i] - incoming * trim, points[i] + outgoing * trim
        center = start + np.cross(normal, incoming) * bend_radius_m
        arcs[i] = {"kind": "elbow", "start": start.tolist(), "end": end.tolist(), "center": center.tolist(),
                   "normal": normal.tolist(), "x_axis": ((start-center)/bend_radius_m).tolist(),
                   "bend_radius_m": bend_radius_m, "angle_rad": theta, "length_m": theta*bend_radius_m}
    parts = []
    for i in range(len(vectors)):
        available = lengths[i] - trims[i] - trims[i+1]
        if available <= max(minimum_straight_m, 1e-9):
            raise ValueError("Fittings consume segment or violate minimum straight length")
        start, end = points[i] + unit[i]*trims[i], points[i+1] - unit[i]*trims[i+1]
        parts.append({"kind": "segment", "start": start.tolist(), "end": end.tolist(), "length_m": available})
        if i+1 in arcs:
            parts.append(arcs[i+1])
    return parts


def export_route(source_path: str | Path, destination_path: str | Path, route_spec: dict,
                 fresh_recheck: bool = True) -> dict:
    """Write an added explicit scenario route, preserving the original IFC.

    Required route_spec: route_id, points_m, diameter_m, system_type.
    Bends additionally require bend_radius_m. Optional insulation_m, inner_radius_m,
    minimum_straight_m, source_port_guid/sink_port_guid, assumption_root.
    Export is DRAFT until independent declared engineering checks are supplied.
    """
    import ifcopenshell
    import ifcopenshell.util.unit

    source, destination = Path(source_path).resolve(), Path(destination_path).resolve()
    if source == destination:
        raise ValueError("Original IFC must not be overwritten")
    if destination.exists():
        raise FileExistsError("Export destination already exists; choose a new immutable artifact path")
    route_id = str(route_spec["route_id"])
    if not route_id:
        raise ValueError("Route identity is required")
    diameter = float(route_spec["diameter_m"])
    insulation = float(route_spec.get("insulation_m", 0))
    if not np.isfinite(diameter) or diameter <= 0 or not np.isfinite(insulation) or insulation < 0:
        raise ValueError("Positive diameter and nonnegative insulation required")
    outer_radius = diameter / 2 + insulation
    bend_radius = float(route_spec.get("bend_radius_m", 0))
    local_points = np.asarray(route_spec["points_m"], dtype=float)
    if route_spec.get("source_to_federation_matrix") is not None:
        transform = np.asarray(route_spec["source_to_federation_matrix"], dtype=float)
        if transform.shape != (4,4) or not np.isfinite(transform).all() or not np.allclose(transform[:3,:3].T @ transform[:3,:3], np.eye(3), atol=1e-9) or np.linalg.det(transform[:3,:3]) <= 0:
            raise ValueError("Export federation transform must be rigid and orientation preserving")
        inverse = np.linalg.inv(transform)
        local_points = local_points @ inverse[:3,:3].T + inverse[:3,3]
    parts = fillet_route(local_points, bend_radius, float(route_spec.get("minimum_straight_m", 0)))
    if any(p["kind"] == "elbow" for p in parts) and bend_radius <= outer_radius:
        raise ValueError("Bend radius must exceed physical outer radius")
    system_type = str(route_spec["system_type"]).upper()
    if system_type not in {"PRESSURE_PIPE", "GRAVITY_DRAINAGE", "ROUND_DUCT", "FIRE_PROTECTION"}:
        raise ValueError("Unsupported system family for round swept export")
    root = sha256_file(source)
    namespace = root + ":" + route_id
    model = ifcopenshell.open(str(source))
    if model.schema not in ("IFC2X3", "IFC4", "IFC4X3"):
        raise ValueError(f"Untested export schema {model.schema}")
    scale = ifcopenshell.util.unit.calculate_unit_scale(model)
    angle_scale = ifcopenshell.util.unit.calculate_unit_scale(model, "PLANEANGLEUNIT")
    units = [u for a in model.by_type("IfcUnitAssignment") for u in a.Units if getattr(u, "UnitType", None) == "LENGTHUNIT"]
    angle_units = [u for a in model.by_type("IfcUnitAssignment") for u in a.Units if getattr(u, "UnitType", None) == "PLANEANGLEUNIT"]
    if len(units) != 1:
        raise ValueError("Cannot export into ambiguous or undeclared length units")
    if any(p["kind"] == "elbow" for p in parts) and len(angle_units) != 1:
        raise ValueError("Curved export requires one explicit plane-angle unit; implicit importer angle conventions are unsafe")
    original = {e.id(): str(e) for e in model}
    owner = model.by_type("IfcOwnerHistory")[0] if model.by_type("IfcOwnerHistory") else None
    contexts = model.by_type("IfcGeometricRepresentationContext", include_subtypes=False)
    if not contexts:
        raise ValueError("Source lacks a geometric representation context")
    context = next((c for c in contexts if c.ContextType == "Model"), contexts[0])
    # New geometry is explicitly world coordinates under identity object placement.
    def point(p):
        return model.create_entity("IfcCartesianPoint", Coordinates=[float(x) / scale for x in p])
    def direction(p):
        return model.create_entity("IfcDirection", DirectionRatios=[float(x) for x in p])
    def placement(p=(0.,0.,0.), z=(0.,0.,1.), x=(1.,0.,0.)):
        return model.create_entity("IfcAxis2Placement3D", Location=point(p), Axis=direction(z), RefDirection=direction(x))
    def local(p=(0.,0.,0.), z=(0.,0.,1.)):
        z = np.asarray(z, dtype=float)
        z /= np.linalg.norm(z)
        seed = np.array((1.,0.,0.)) if abs(z[0]) < 0.8 else np.array((0.,1.,0.))
        x = seed - z*np.dot(seed, z)
        x /= np.linalg.norm(x)
        return model.create_entity("IfcLocalPlacement", RelativePlacement=placement(p, z, x))
    def rooted(cls, key, **kwargs):
        guid = _guid(namespace, key)
        try:
            if model.by_guid(guid):
                raise ValueError("Route GUID already exists in source; idempotent export must reuse its prior artifact")
        except RuntimeError:
            pass
        return model.create_entity(cls, GlobalId=guid, OwnerHistory=owner, **kwargs)
    system = rooted("IfcSystem", "system", Name=f"OMA {route_id}", ObjectType=system_type)
    elements, all_ports, correspondences = [], [], []
    previous_out = None
    for index, part in enumerate(parts):
        elbow = part["kind"] == "elbow"
        if model.schema == "IFC2X3":
            cls = "IfcFlowFitting" if elbow else "IfcFlowSegment"
        else:
            cls = ("IfcDuctFitting" if elbow else "IfcDuctSegment") if system_type == "ROUND_DUCT" else ("IfcPipeFitting" if elbow else "IfcPipeSegment")
        element = rooted(cls, f"part:{index}", Name=f"{route_id} {'elbow' if elbow else 'straight'} {index+1}",
                         ObjectType="PARAMETRIC_ELBOW" if elbow else "ROUND_STRAIGHT", ObjectPlacement=local())
        if hasattr(element, "PredefinedType"):
            element.PredefinedType = "BEND" if elbow else "RIGIDSEGMENT"
        if elbow:
            profile_position = model.create_entity("IfcAxis2Placement2D", Location=model.create_entity("IfcCartesianPoint", Coordinates=[bend_radius/scale, 0.]))
            profile = model.create_entity("IfcCircleProfileDef", ProfileType="AREA", Position=profile_position, Radius=outer_radius/scale)
            radial = np.asarray(part["x_axis"])
            tangent = np.cross(part["normal"], radial)
            solid_position = placement(part["center"], tangent, radial)
            axis = model.create_entity("IfcAxis1Placement", Location=point((0.,0.,0.)), Axis=direction((0.,-1.,0.)))
            solid = model.create_entity("IfcRevolvedAreaSolid", SweptArea=profile, Position=solid_position,
                                        Axis=axis, Angle=float(part["angle_rad"])/angle_scale)
        else:
            axis = np.asarray(part["end"])-np.asarray(part["start"])
            axis /= np.linalg.norm(axis)
            seed = np.array((1.,0.,0.)) if abs(axis[0]) < .8 else np.array((0.,1.,0.))
            x_axis = seed-axis*np.dot(seed,axis)
            x_axis /= np.linalg.norm(x_axis)
            profile_position = model.create_entity("IfcAxis2Placement2D", Location=model.create_entity("IfcCartesianPoint", Coordinates=[0.,0.]))
            profile = model.create_entity("IfcCircleProfileDef", ProfileType="AREA", Position=profile_position, Radius=outer_radius/scale)
            solid = model.create_entity("IfcExtrudedAreaSolid", SweptArea=profile,
                                        Position=placement(part["start"], axis, x_axis),
                                        ExtrudedDirection=direction((0.,0.,1.)), Depth=part["length_m"]/scale)
        representation = model.create_entity("IfcShapeRepresentation", ContextOfItems=context,
                                               RepresentationIdentifier="Body", RepresentationType="SweptSolid", Items=[solid])
        element.Representation = model.create_entity("IfcProductDefinitionShape", Representations=[representation])
        ports = []
        for suffix, location, flow in [("in", part["start"], "SINK"), ("out", part["end"], "SOURCE")]:
            if elbow:
                tangent = np.cross(part["normal"], np.asarray(location)-np.asarray(part["center"]))
            else:
                tangent = np.asarray(part["end"])-np.asarray(part["start"])
            tangent /= np.linalg.norm(tangent)
            outward = -tangent if suffix == "in" else tangent
            port = rooted("IfcDistributionPort", f"part:{index}:port:{suffix}", Name=f"{route_id}/{index}/{suffix}",
                          ObjectPlacement=local(location, outward), FlowDirection=flow)
            rooted("IfcRelConnectsPortToElement", f"part:{index}:owner:{suffix}", RelatingPort=port, RelatedElement=element)
            ports.append(port)
        if previous_out:
            rooted("IfcRelConnectsPorts", f"joint:{index}", RelatingPort=previous_out, RelatedPort=ports[0], RealizingElement=element)
        previous_out = ports[1]
        all_ports.extend(ports)
        properties = []
        for key, value in {"RouteId": route_id, "SourceSHA256": root, "AssumptionRoot": route_spec.get("assumption_root", "EXPLICIT_ROUTE_SPEC"),
                           "SystemFamily": system_type, "PhysicalRepresentation": "Outer service envelope including insulation", "EngineeringStatus": "DRAFT"}.items():
            properties.append(model.create_entity("IfcPropertySingleValue", Name=key, NominalValue=model.create_entity("IfcText", str(value))))
        for key, value in {"Diameter_m": diameter, "Insulation_m": insulation, "CenterlineLength_m": part["length_m"]}.items():
            properties.append(model.create_entity("IfcPropertySingleValue", Name=key, NominalValue=model.create_entity("IfcReal", float(value))))
        pset = rooted("IfcPropertySet", f"pset:{index}", Name="OMA_RouteProvenance", HasProperties=properties)
        rooted("IfcRelDefinesByProperties", f"pset-rel:{index}", RelatedObjects=[element], RelatingPropertyDefinition=pset)
        elements.append(element)
        correspondences.append({"route_id": route_id, "part_index": index, "ifc_guid": element.GlobalId, "step_id": element.id(),
                                "kind": part["kind"], "ports": [p.GlobalId for p in ports], "expected": part})
    rooted("IfcRelAssignsToGroup", "system-members", RelatedObjects=elements, RelatingGroup=system)
    storeys = model.by_type("IfcBuildingStorey")
    if storeys:
        # Explicit requested container, or source first storey with disposition recorded.
        requested = route_spec.get("container_guid")
        container = model.by_guid(requested) if requested else storeys[0]
        rooted("IfcRelContainedInSpatialStructure", "containment", RelatedElements=elements, RelatingStructure=container)
    for endpoint, port_index in (("source_port_guid", 0), ("sink_port_guid", -1)):
        if route_spec.get(endpoint):
            existing = model.by_guid(route_spec[endpoint])
            if not existing.is_a("IfcDistributionPort"):
                raise ValueError(f"{endpoint} does not identify an explicit source port")
            if getattr(existing, "ConnectedTo", ()) or getattr(existing, "ConnectedFrom", ()):
                raise ValueError("Existing port already connected; reroute requires explicit relationship replacement")
            rooted("IfcRelConnectsPorts", endpoint, RelatingPort=existing, RelatedPort=all_ports[port_index], RealizingElement=elements[0 if port_index == 0 else -1])
    changed = [step for step, text in original.items() if str(model.by_id(step)) != text]
    if changed:
        raise RuntimeError(f"Unexpected modification of original STEP records: {changed[:10]}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp.ifc")
    model.write(str(temporary))
    temporary.replace(destination)
    result = {"source_path": str(source), "source_sha256": root, "export_path": str(destination),
              "export_sha256": sha256_file(destination), "schema": model.schema, "route_id": route_id,
              "route_spec": route_spec, "status": "DRAFT", "original_step_records": len(original),
              "original_records_changed": changed, "added_parts": correspondences,
              "explicit_internal_connections": len(parts)-1, "source_system_guid": system.GlobalId,
              "geometry_semantics": "Exact circular swept outer envelopes, parametrically defined tangent elbows",
              "length_m": sum(part["length_m"] for part in parts),
              "unresolved": ["Engineering coordination verification is separate", "No material/bore inferred", "No hydraulic adequacy inferred"],
              "reimport": {"status": "NOT_RUN"}}
    manifest_path = destination.with_suffix(".manifest.json")
    atomic_json(manifest_path, result)
    if fresh_recheck:
        command = [sys.executable, "-m", "oma.ifc.recheck", str(manifest_path)]
        process = subprocess.run(command, capture_output=True, text=True, timeout=300,
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if process.returncode:
            result["reimport"] = {"status": "FAIL", "error": process.stderr[-4000:], "stdout": process.stdout[-1000:]}
            atomic_json(manifest_path, result)
            raise RuntimeError(f"Fresh IFC recheck failed: {process.stderr[-1000:]}")
        result = json.loads(manifest_path.read_text(encoding="utf-8"))
    return result
