"""IFC4 and IFC2X3 CV2.0 flow axes, ownership and physical port normals.

IFC4 ADD2 TC1 IfcDistributionPort / Product Local Placement and official
implementation agreement CV-2x3-176 define the same flow-dependent Axis rule.
The encoded SINK Axis points into its owner; its physical outward normal does
not. No geometry validity or intended connectivity is inferred by this module.
"""
from __future__ import annotations

import numpy as np

AXIS_CONVENTION = "IFC4_AND_IFC2X3_CV2_FLOW_DIRECTION"


def physical_normal(axis, flow_direction):
    axis = np.asarray(axis, dtype=float)
    if axis.shape != (3,) or not np.isfinite(axis).all() or np.linalg.norm(axis) <= 0:
        raise ValueError("Port Axis must be a finite nonzero vector")
    if flow_direction not in ("SOURCE", "SINK", "SOURCEANDSINK", "NOTDEFINED"):
        raise ValueError("Explicit supported IFC FlowDirection required")
    return axis / np.linalg.norm(axis) * (-1. if flow_direction == "SINK" else 1.)


def encoded_flow_axis(outward_normal, flow_direction):
    # The sign conversion is its own inverse.
    return physical_normal(outward_normal, flow_direction)


def ownership_ledger(model):
    """Keep every relationship, including duplicate and conflicting owners."""
    records = {p.id(): {"port": p, "owners": {}, "relationships": []}
               for p in model.by_type("IfcDistributionPort")}
    for relation in model.by_type("IfcRelConnectsPortToElement"):
        port, owner = relation.RelatingPort, relation.RelatedElement
        if port.id() in records:
            records[port.id()]["owners"][owner.id()] = owner
            records[port.id()]["relationships"].append(relation)
    for relation in model.by_type("IfcRelNests"):
        for port in relation.RelatedObjects:
            if port.id() in records:
                records[port.id()]["owners"][relation.RelatingObject.id()] = relation.RelatingObject
                records[port.id()]["relationships"].append(relation)
    return records


def port_facts(port, record, scale, transform=None):
    """Read schema direction and owner-relative placement without a cap claim."""
    import ifcopenshell.util.placement
    errors = []
    owners = record["owners"]
    owner = next(iter(owners.values())) if len(owners) == 1 else None
    if owner is None:
        errors.append("PORT_OWNER_MISSING_OR_AMBIGUOUS")
    if len(record["relationships"]) != 1:
        errors.append("PORT_OWNER_RELATIONSHIP_MULTIPLICITY")
    placement = port.ObjectPlacement
    relative = bool(owner is not None and placement is not None and placement.is_a("IfcLocalPlacement")
                    and getattr(owner, "ObjectPlacement", None) is not None and placement.PlacementRelTo == owner.ObjectPlacement)
    if not relative:
        errors.append("PORT_PLACEMENT_NOT_RELATIVE_TO_OWNER")
    position, axis, outward = None, None, None
    try:
        if placement is None or not placement.is_a("IfcLocalPlacement"):
            raise ValueError("Missing or unsupported port placement")
        matrix = np.asarray(ifcopenshell.util.placement.get_local_placement(placement), dtype=float)
        frame = np.eye(4) if transform is None else np.asarray(transform, dtype=float)
        if matrix.shape != (4, 4) or frame.shape != (4, 4) or not np.isfinite(matrix).all() or not np.isfinite(frame).all():
            raise ValueError("Invalid port frame")
        position = (frame[:3, :3] @ (matrix[:3, 3] * scale) + frame[:3, 3]).tolist()
        direction = frame[:3, :3] @ matrix[:3, 2]
        if not np.isfinite(direction).all() or np.linalg.norm(direction) <= 0:
            raise ValueError("Invalid port Axis")
        axis = (direction / np.linalg.norm(direction)).tolist()
        outward = physical_normal(axis, port.FlowDirection).tolist()
    except Exception as exc:
        errors.append(f"INVALID_PORT_FRAME_OR_FLOW:{type(exc).__name__}:{exc}")
    return {"port_guid": port.GlobalId, "port_step_id": port.id(),
            "owner_guids": [o.GlobalId for o in owners.values()], "owner_step_ids": sorted(owners),
            "owner_relationship_step_ids": sorted(r.id() for r in record["relationships"]),
            "owner_placement_status": "OWNER_RELATIVE" if relative else "INVALID",
            "flow_direction": port.FlowDirection, "axis_convention": AXIS_CONVENTION,
            "position_m": position, "flow_axis": axis, "physical_outward_normal": outward, "errors": errors}


def connected_pair_errors(source_port, sink_port, ledger, scale, tolerance=1e-7):
    """Validate an ordered SOURCE-to-SINK interface, never infer a connection."""
    errors = []
    if source_port.id() not in ledger or sink_port.id() not in ledger:
        return ["CONNECTION_REQUIRES_SUPPORTED_DISTRIBUTION_PORTS"]
    a = port_facts(source_port, ledger[source_port.id()], scale)
    b = port_facts(sink_port, ledger[sink_port.id()], scale)
    errors.extend(a["errors"] + b["errors"])
    if source_port.FlowDirection != "SOURCE" or sink_port.FlowDirection != "SINK":
        errors.append("CONNECTION_MUST_BE_SOURCE_TO_SINK")
    if source_port.id() == sink_port.id() or set(a["owner_step_ids"]) & set(b["owner_step_ids"]):
        errors.append("CONNECTION_REQUIRES_DISTINCT_PORTS_AND_OWNERS")
    for field in ("SystemType", "PredefinedType"):
        av, bv = getattr(source_port, field, None), getattr(sink_port, field, None)
        if av not in (None, "NOTDEFINED") and bv not in (None, "NOTDEFINED") and av != bv:
            errors.append(f"CONNECTION_{field.upper()}_MISMATCH")
    if a["position_m"] is not None and b["position_m"] is not None:
        if np.linalg.norm(np.asarray(a["position_m"])-b["position_m"]) > tolerance:
            errors.append("CONNECTED_PORT_POSITIONS_DIFFER")
        if a["flow_axis"] is None or b["flow_axis"] is None or np.linalg.norm(np.asarray(a["flow_axis"])-b["flow_axis"]) > tolerance:
            errors.append("CONNECTED_FLOW_AXES_NOT_ALIGNED")
    return errors


def circular_owner_radius(owner, scale):
    """Recover the bounded round-sweep section; unsupported owners stay unknown."""
    representation = getattr(owner, "Representation", None)
    if representation is None:
        return None
    items = [item for rep in representation.Representations
             if rep.RepresentationIdentifier in ("Body", "Facetation", None) for item in rep.Items]
    if len(items) != 1 or not items[0].is_a("IfcSweptAreaSolid") or not items[0].SweptArea.is_a("IfcCircleProfileDef"):
        return None
    radius = float(items[0].SweptArea.Radius) * scale
    return radius if np.isfinite(radius) and radius > 0 else None
