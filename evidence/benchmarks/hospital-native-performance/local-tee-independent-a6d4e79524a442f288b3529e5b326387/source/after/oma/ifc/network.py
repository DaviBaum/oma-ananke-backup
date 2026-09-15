"""Export a unique physical component tree with round sweeps and CSG tees."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

from .audit import atomic_json, sha256_file
from .export import _guid
from .network_contract import component_geometry, rigid_frame, validate_network_spec
from .ports import encoded_flow_axis


def export_network(source_path, export_path, spec, fresh_recheck=False):
    import ifcopenshell
    import ifcopenshell.util.unit
    source, destination = Path(source_path).resolve(), Path(export_path).resolve()
    if source == destination or destination.exists():
        raise ValueError("Original or existing immutable network artifact cannot be overwritten")
    facts = validate_network_spec(spec)
    model = ifcopenshell.open(str(source))
    original = {entity.id(): str(entity) for entity in model}
    root = sha256_file(source)
    scale = ifcopenshell.util.unit.calculate_unit_scale(model)
    angle_scale = ifcopenshell.util.unit.calculate_unit_scale(model, "PLANEANGLEUNIT")
    length_units = [u for a in model.by_type("IfcUnitAssignment") for u in a.Units if getattr(u, "UnitType", None) == "LENGTHUNIT"]
    if len(length_units) != 1 or not np.isfinite(scale) or scale <= 0:
        raise ValueError("Unique finite source length units required")
    context = next((c for c in model.by_type("IfcGeometricRepresentationContext") if c.ContextIdentifier == "Body"), None)
    context = context or next(iter(model.by_type("IfcGeometricRepresentationContext")), None)
    if context is None:
        raise ValueError("Source model has no geometric context")
    owner = next(iter(model.by_type("IfcOwnerHistory")), None)
    if model.schema == "IFC2X3" and owner is None:
        raise ValueError("IFC2X3 source has no required owner history")
    inverse = np.linalg.inv(rigid_frame(spec.get("source_to_federation_matrix", np.eye(4))))
    namespace = root + ":network:" + spec["network_id"]
    def rooted(kind, identity, **kwargs):
        guid = _guid(namespace, identity)
        try:
            model.by_guid(guid)
        except RuntimeError:
            return model.create_entity(kind, GlobalId=guid, OwnerHistory=owner, **kwargs)
        raise ValueError("Network physical identity already exists in source")
    def point(value):
        return model.create_entity("IfcCartesianPoint", Coordinates=(np.asarray(value, dtype=float)/scale).tolist())
    def direction(value):
        value = np.asarray(value, dtype=float)
        return model.create_entity("IfcDirection", DirectionRatios=(value/np.linalg.norm(value)).tolist())
    def placement(location, axis=(0.,0.,1.), x=None):
        axis = np.asarray(axis, dtype=float)
        axis /= np.linalg.norm(axis)
        if x is None:
            seed = np.array([1.,0.,0.]) if abs(axis[0]) < .8 else np.array([0.,1.,0.])
            x = seed-axis*np.dot(seed, axis)
        return model.create_entity("IfcAxis2Placement3D", Location=point(location), Axis=direction(axis), RefDirection=direction(x))
    def local(location=(0.,0.,0.), axis=(0.,0.,1.), parent=None):
        return model.create_entity("IfcLocalPlacement", PlacementRelTo=parent, RelativePlacement=placement(location, axis))
    def p(value):
        return inverse[:3,:3] @ np.asarray(value) + inverse[:3,3]
    def v(value):
        return inverse[:3,:3] @ np.asarray(value)
    def circle(radius, center=(0.,0.)):
        position = model.create_entity("IfcAxis2Placement2D", Location=model.create_entity("IfcCartesianPoint", Coordinates=(np.asarray(center)/scale).tolist()))
        return model.create_entity("IfcCircleProfileDef", ProfileType="AREA", Position=position, Radius=radius/scale)
    def cylinder(start, end, radius):
        start, end = np.asarray(start), np.asarray(end)
        return model.create_entity("IfcExtrudedAreaSolid", SweptArea=circle(radius), Position=placement(start, end-start),
            ExtrudedDirection=direction((0.,0.,1.)), Depth=float(np.linalg.norm(end-start))/scale)
    system = rooted("IfcSystem", "system", Name=spec["network_id"], ObjectType=spec["system_type"])
    elements, manifest_parts, port_map = [], [], {}
    for component in spec["components"]:
        identity, kind = component["id"], component["kind"]
        data, expected = component["geometry"], facts["components"][identity]
        radius = expected["radius_m"]
        # Evaluate tee Booleans near their local origin. Keeping building-scale
        # coordinates inside the CSG operands makes native intersection edges
        # sensitive to translation, despite representing the same fitting.
        origin = p(rigid_frame(data["frame_m"])[:3,3]) if kind == "tee" else np.zeros(3)
        fitting = kind != "segment"
        if model.schema == "IFC2X3":
            entity_type = "IfcFlowFitting" if fitting else "IfcFlowSegment"
        else:
            family = "Duct" if component["system_type"] == "ROUND_DUCT" else "Pipe"
            entity_type = "Ifc"+family+("Fitting" if fitting else "Segment")
        element = rooted(entity_type, identity, Name=f"{spec['network_id']}/{identity}", ObjectType="OMA_NETWORK_"+kind.upper(), ObjectPlacement=local(origin))
        if hasattr(element, "PredefinedType"):
            element.PredefinedType = "JUNCTION" if kind == "tee" else "BEND" if kind == "elbow" else "RIGIDSEGMENT"
        elif fitting:
            type_kind = "IfcDuctFittingType" if component["system_type"] == "ROUND_DUCT" else "IfcPipeFittingType"
            fitting_type = rooted(type_kind, identity+":type", Name=f"OMA {kind}", PredefinedType="JUNCTION" if kind == "tee" else "BEND")
            rooted("IfcRelDefinesByType", identity+":type-relation", RelatedObjects=[element], RelatingType=fitting_type)
        if kind == "segment":
            solid = cylinder(p(data["start_m"]), p(data["end_m"]), radius)
        elif kind == "elbow":
            if not any(getattr(u, "UnitType", None) == "PLANEANGLEUNIT" for a in model.by_type("IfcUnitAssignment") for u in a.Units):
                raise ValueError("Elbow requires explicit plane-angle units")
            radial = (np.asarray(data["start_m"])-data["center_m"])/data["bend_radius_m"]
            tangent = np.cross(data["normal"], radial)
            solid = model.create_entity("IfcRevolvedAreaSolid", SweptArea=circle(radius, (data["bend_radius_m"], 0.)),
                Position=placement(p(data["center_m"]), v(tangent), v(radial)),
                Axis=model.create_entity("IfcAxis1Placement", Location=point((0.,0.,0.)), Axis=direction((0.,-1.,0.))),
                Angle=float(data["angle_rad"])/angle_scale)
        else:
            frame = rigid_frame(data["frame_m"])
            trunk, branch = data["trunk_takeout_m"], data["branch_takeout_m"]
            first = cylinder(-trunk*v(frame[:3,0]), trunk*v(frame[:3,0]), radius)
            second = cylinder(np.zeros(3), branch*v(frame[:3,1]), radius)
            solid = model.create_entity("IfcBooleanResult", Operator="UNION", FirstOperand=first, SecondOperand=second)
        representation = model.create_entity("IfcShapeRepresentation", ContextOfItems=context, RepresentationIdentifier="Body",
            RepresentationType="CSG" if kind == "tee" else "SweptSolid", Items=[solid])
        element.Representation = model.create_entity("IfcProductDefinitionShape", Representations=[representation])
        ports = {}
        for slot, cap in expected["caps"].items():
            role = component["ports"][slot]
            port = rooted("IfcDistributionPort", identity+":port:"+slot, Name=f"{identity}/{slot}", FlowDirection=role,
                ObjectPlacement=local(p(cap["position_m"])-origin, encoded_flow_axis(v(cap["outward_normal"]), role), element.ObjectPlacement))
            if model.schema == "IFC2X3":
                rooted("IfcRelConnectsPortToElement", identity+":owns:"+slot, RelatingPort=port, RelatedElement=element)
            else:
                port.PredefinedType = "DUCT" if component["system_type"] == "ROUND_DUCT" else "PIPE"
                rooted("IfcRelNests", identity+":owns:"+slot, RelatingObject=element, RelatedObjects=[port])
            port_map[(identity,slot)] = port
            ports[slot] = port.GlobalId
        elements.append(element)
        manifest_parts.append({"component_id":identity,"kind":kind,"ifc_guid":element.GlobalId,"step_id":element.id(),"ports":ports})
    for index, connection in enumerate(spec["connections"]):
        a, b = connection["source"], connection["sink"]
        rooted("IfcRelConnectsPorts", f"connection:{index}", RelatingPort=port_map[(a["component"],a["port"])],
            RelatedPort=port_map[(b["component"],b["port"])])
    rooted("IfcRelAssignsToGroup", "system-members", RelatedObjects=elements, RelatingGroup=system)
    storeys = model.by_type("IfcBuildingStorey")
    if storeys:
        container = model.by_guid(spec["container_guid"]) if spec.get("container_guid") else storeys[0]
        rooted("IfcRelContainedInSpatialStructure", "containment", RelatedElements=elements, RelatingStructure=container)
    changed = [step for step, text in original.items() if str(model.by_id(step)) != text]
    if changed:
        raise ValueError(f"Original IFC records changed: {changed[:10]}")
    destination.parent.mkdir(parents=True,exist_ok=True)
    temporary=destination.with_suffix(".tmp.ifc")
    model.write(str(temporary)); temporary.replace(destination)
    manifest={"schema":"oma-network-materialization/1","source_path":str(source),"source_sha256":root,
        "export_path":str(destination),"export_sha256":sha256_file(destination),"ifc_schema":model.schema,
        "network_spec":copy.deepcopy(spec),"network_id":spec["network_id"],"added_parts":manifest_parts,
        "source_system_guid":system.GlobalId,"port_axis_convention":"IFC_FLOW_AXIS_V1",
        "original_step_records":len(original),"original_records_changed":changed,"status":"DRAFT",
        "physical_component_count":len(elements),"physical_port_count":len(port_map),"explicit_internal_connections":len(spec["connections"]),
        "unique_length_m":facts["unique_length_m"],"fitting_count":facts["fitting_count"],"demand_path_lengths_m":facts["demand_path_lengths_m"]}
    sidecar=destination.with_suffix(".manifest.json")
    atomic_json(sidecar,manifest)
    if fresh_recheck:
        process=subprocess.run([sys.executable,"-m","oma.ifc.network_semantics",str(sidecar)],capture_output=True,text=True,
            creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
        if process.returncode:
            raise ValueError(f"Fresh network reimport failed: {process.stderr[-3000:]}")
        manifest=json.loads(sidecar.read_text(encoding="utf-8"))
    return manifest


def check_network_semantics(export_path,source_path,manifest):
    from .network_semantics import check_network_semantics as independent
    return independent(export_path,source_path,manifest)
