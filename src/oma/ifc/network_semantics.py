"""Independent IFC component/port/tree interpretation; no exporter imports."""
from __future__ import annotations

import json
import math
from pathlib import Path
import sys

import numpy as np

from .audit import atomic_json, sha256_file
from .network_contract import endpoint, rigid_frame, validate_network_spec
from .ports import connected_pair_errors, ownership_ledger, port_facts


def _unit(vector):
    vector=np.asarray(vector,dtype=float)
    length=float(np.linalg.norm(vector))
    if vector.shape!=(3,) or not np.isfinite(vector).all() or length <= 0:
        raise ValueError("Invalid geometric direction")
    return vector/length


def _sweep(model, element, solid, scale):
    import ifcopenshell.util.placement
    import ifcopenshell.util.unit
    if not solid.is_a("IfcSweptAreaSolid") or not solid.SweptArea.is_a("IfcCircleProfileDef"):
        raise ValueError("A supported circular swept solid is required")
    profile=solid.SweptArea
    radius=float(profile.Radius)*scale
    if not math.isfinite(radius) or radius<=0 or profile.ProfileType!="AREA":
        raise ValueError("Invalid circular profile")
    frame=ifcopenshell.util.placement.get_local_placement(element.ObjectPlacement) @ ifcopenshell.util.placement.get_axis2placement(solid.Position)
    if not np.isfinite(frame).all():
        raise ValueError("Nonfinite component placement")
    profile_center=np.array([*(profile.Position.Location.Coordinates if profile.Position else (0.,0.)),0.])
    start=(frame[:3,:3] @ profile_center+frame[:3,3])*scale
    if solid.is_a("IfcExtrudedAreaSolid"):
        direction=_unit(solid.ExtrudedDirection.DirectionRatios)
        if np.linalg.norm(direction-[0.,0.,1.])>1e-10:
            raise ValueError("Oblique/reversed extrusion is outside the round network component family")
        length=float(solid.Depth)*scale
        if not math.isfinite(length) or length<=1e-7:
            raise ValueError("Invalid straight component depth")
        axis=_unit(frame[:3,:3] @ direction)
        end=start+length*axis
        return {"kind":"segment","radius_m":radius,"length_m":length,"analytic_volume_m3":math.pi*radius**2*length,
            "path_lengths_m":{"a:b":length},"caps":{"a":{"position_m":start.tolist(),"outward_normal":(-axis).tolist()},
                "b":{"position_m":end.tolist(),"outward_normal":axis.tolist()}},"start_m":start.tolist(),"end_m":end.tolist()}
    if not solid.is_a("IfcRevolvedAreaSolid"):
        raise ValueError("Unsupported round directrix")
    angle_scale=ifcopenshell.util.unit.calculate_unit_scale(model,"PLANEANGLEUNIT")
    angle=float(solid.Angle)*angle_scale
    axis_local=_unit(solid.Axis.Axis.DirectionRatios if solid.Axis.Axis else (0.,0.,1.))
    normal=_unit(frame[:3,:3] @ axis_local)
    axis_origin=(frame[:3,:3] @ np.asarray(solid.Axis.Location.Coordinates)+frame[:3,3])*scale
    center=axis_origin+np.dot(start-axis_origin,normal)*normal
    radial=start-center
    bend=float(np.linalg.norm(radial))
    if not (math.isfinite(angle) and 0<angle<math.pi and bend>radius):
        raise ValueError("Unsupported circular elbow dimensions")
    tangent=_unit(np.cross(normal,radial))
    if abs(abs(np.dot(tangent,_unit(frame[:3,2])))-1)>1e-10:
        raise ValueError("Revolved profile does not form perpendicular circular route sections")
    end=center+radial*math.cos(angle)+np.cross(normal,radial)*math.sin(angle)
    tangent_end=_unit(np.cross(normal,end-center))
    length=bend*angle
    return {"kind":"elbow","radius_m":radius,"length_m":length,"analytic_volume_m3":math.pi*radius**2*length,
        "path_lengths_m":{"a:b":length},"caps":{"a":{"position_m":start.tolist(),"outward_normal":(-tangent).tolist()},
            "b":{"position_m":end.tolist(),"outward_normal":tangent_end.tolist()}},"center_m":center.tolist(),
        "normal":normal.tolist(),"bend_radius_m":bend,"angle_rad":angle,"start_m":start.tolist(),"end_m":end.tolist()}


def read_component_geometry(model,element):
    """Recover full round/tee geometry from actual IFC Body structure and units."""
    import ifcopenshell.util.unit
    scale=ifcopenshell.util.unit.calculate_unit_scale(model)
    if element.Representation is None or element.ObjectPlacement is None:
        raise ValueError("Component geometry or placement missing")
    bodies=[rep for rep in element.Representation.Representations if rep.RepresentationIdentifier in ("Body","Facetation",None)]
    if len(element.Representation.Representations)!=1 or len(bodies)!=1 or len(bodies[0].Items)!=1:
        raise ValueError("Complete component Body must contain exactly one supported item")
    solid=bodies[0].Items[0]
    if solid.is_a("IfcSweptAreaSolid"):
        return _sweep(model,element,solid,scale)
    if not solid.is_a("IfcBooleanResult") or solid.Operator!="UNION":
        raise ValueError("Unsupported network CSG body")
    first,second=(_sweep(model,element,item,scale) for item in (solid.FirstOperand,solid.SecondOperand))
    if first["kind"]!="segment" or second["kind"]!="segment":
        raise ValueError("Tee union requires two direct circular extrusions")
    radius=first["radius_m"]
    start,end=np.asarray(first["start_m"]),np.asarray(first["end_m"])
    center=(start+end)/2
    branch_start,branch_end=np.asarray(second["start_m"]),np.asarray(second["end_m"])
    x,y=_unit(end-start),_unit(branch_end-branch_start)
    takeout,branch=first["length_m"]/2,second["length_m"]
    if (abs(radius-second["radius_m"])>1e-10 or np.linalg.norm(center-branch_start)>1e-8 or abs(np.dot(x,y))>1e-10
            or min(takeout,branch)<=radius+1e-6):
        raise ValueError("CSG operands do not form the bounded equal-round orthogonal tee")
    length=2*takeout+branch
    return {"kind":"tee","radius_m":radius,"length_m":length,
        "analytic_volume_m3":math.pi*radius**2*length-8*radius**3/3,"path_lengths_m":{"a:b":2*takeout,"a:branch":takeout+branch},
        "caps":{"a":{"position_m":start.tolist(),"outward_normal":(-x).tolist()},
            "b":{"position_m":end.tolist(),"outward_normal":x.tolist()},
            "branch":{"position_m":branch_end.tolist(),"outward_normal":y.tolist()}},
        "center_m":center.tolist(),"x_axis":x.tolist(),"y_axis":y.tolist(),"trunk_takeout_m":takeout,"branch_takeout_m":branch}


def check_network_semantics(export_path,source_path,manifest):
    import ifcopenshell
    import ifcopenshell.util.unit
    from .cad import load_cad,_subshapes
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.gp import gp_Pnt
    from OCP.TopAbs import TopAbs_IN,TopAbs_ON,TopAbs_OUT,TopAbs_SOLID
    model,source=ifcopenshell.open(str(export_path)),ifcopenshell.open(str(source_path))
    errors=[]
    spec=manifest["network_spec"]
    try:
        expected=validate_network_spec(spec)
    except (ValueError,KeyError,TypeError) as exc:
        return {"status":"FAIL","errors":[f"Invalid declared network contract: {exc}"],"parts":[],"ports":[],"connectivity":[]}
    transform=rigid_frame(spec.get("source_to_federation_matrix",np.eye(4)))
    if manifest["source_sha256"]!=sha256_file(source_path) or manifest["export_sha256"]!=sha256_file(export_path):
        errors.append("Immutable network source/export hash mismatch")
    original_ids={e.id() for e in source}
    for entity in source:
        try:
            if str(entity)!=str(model.by_id(entity.id())):
                errors.append(f"Original STEP record changed:{entity.id()}")
        except RuntimeError:
            errors.append(f"Original STEP record missing:{entity.id()}")
    parts=manifest["added_parts"]
    guids={part["ifc_guid"] for part in parts}
    ids={part["component_id"] for part in parts}
    if len(guids)!=len(parts) or len(ids)!=len(parts) or ids!=set(expected["components"]):
        errors.append("Component manifest duplicates or omits physical identities")
    added=[e for e in model.by_type("IfcElement") if e.id() not in original_ids]
    if {e.GlobalId for e in added}!=guids:
        errors.append("Actual added physical entities differ from the complete component inventory")
    native,native_errors=load_cad(export_path,guids=guids)
    errors.extend(f"Native geometry:{error}" for error in native_errors)
    native_map={obj.guid:obj for obj in native}
    if set(native_map)!=guids:
        errors.append("Missing native component geometry")
    ledger=ownership_ledger(model)
    actual_parts,actual_ports,slot_map=[],[],{}
    owned_port_ids=set()
    by_component={c["id"]:c for c in spec["components"]}
    for part in parts:
        cid=part["component_id"]
        try:
            element=model.by_guid(part["ifc_guid"])
            facts=read_component_geometry(model,element)
            prescribed=expected["components"][cid]
            if model.schema=="IFC2X3":
                required_class="IfcFlowSegment" if facts["kind"]=="segment" else "IfcFlowFitting"
            else:
                family="Duct" if by_component[cid]["system_type"]=="ROUND_DUCT" else "Pipe"
                required_class="Ifc"+family+("Segment" if facts["kind"]=="segment" else "Fitting")
            if element.is_a()!=required_class:
                errors.append(f"Actual IFC component class differs from physical service family:{cid}")
            required_type="RIGIDSEGMENT" if facts["kind"]=="segment" else "BEND" if facts["kind"]=="elbow" else "JUNCTION"
            if model.schema!="IFC2X3" and element.PredefinedType!=required_type:
                errors.append(f"Actual fitting/segment PredefinedType differs:{cid}")
            elif model.schema=="IFC2X3" and facts["kind"]!="segment":
                assigned=[rel.RelatingType for rel in element.IsDefinedBy if rel.is_a("IfcRelDefinesByType")]
                expected_type="IfcDuctFittingType" if by_component[cid]["system_type"]=="ROUND_DUCT" else "IfcPipeFittingType"
                if len(assigned)!=1 or assigned[0].is_a()!=expected_type or assigned[0].PredefinedType!=required_type:
                    errors.append(f"IFC2X3 fitting type is missing or incompatible:{cid}")
            if facts["kind"]!=prescribed["kind"] or abs(facts["radius_m"]-prescribed["radius_m"])>1e-10:
                errors.append(f"Component family or physical section differs:{cid}")
            if abs(facts["length_m"]-prescribed["length_m"])>1e-8:
                errors.append(f"Component skeleton length differs:{cid}")
            if set(part["ports"])!=set(facts["caps"]):
                errors.append(f"Component port arity differs:{cid}")
            own=[r for r in ledger.values() if element.id() in r["owners"]]
            if {r["port"].GlobalId for r in own}!=set(part["ports"].values()) or len(own)!=len(facts["caps"]):
                errors.append(f"Actual port ownership differs from all component slots:{cid}")
            shape=native_map.get(element.GlobalId)
            volume_error=None
            solid_count=0 if shape is None else len(_subshapes(shape.shape,TopAbs_SOLID))
            if shape is None or not shape.valid:
                errors.append(f"Component is not a completely represented valid native solid:{cid}")
            else:
                if solid_count!=1:
                    errors.append(f"Physical component must form exactly one connected native solid:{cid}")
                volume_error=abs(shape.volume_m3-facts["analytic_volume_m3"])
                if volume_error>max(1e-9,abs(facts["analytic_volume_m3"])*1e-7):
                    errors.append(f"Native volume disagrees with independent analytic component:{cid}")
            for slot,cap in facts["caps"].items():
                point=transform[:3,:3] @ np.asarray(cap["position_m"])+transform[:3,3]
                normal=transform[:3,:3] @ np.asarray(cap["outward_normal"])
                required=prescribed["caps"][slot]
                if np.linalg.norm(point-required["position_m"])>1e-7 or np.linalg.norm(normal-required["outward_normal"])>1e-7:
                    errors.append(f"Actual component cap differs from declared geometry:{cid}:{slot}")
                port=model.by_guid(part["ports"][slot])
                owned_port_ids.add(port.id());slot_map[(cid,slot)]=port
                port_data=port_facts(port,ledger[port.id()],scale=ifcopenshell.util.unit.calculate_unit_scale(model))
                problems=list(port_data["errors"])
                if port_data["owner_guids"]!=[element.GlobalId] or port.FlowDirection!=by_component[cid]["ports"][slot]:
                    problems.append("Port owner or flow role differs from component slot")
                if port_data["position_m"] is None or np.linalg.norm(np.asarray(port_data["position_m"])-cap["position_m"])>1e-7:
                    problems.append("Port center differs from actual physical component cap")
                if port_data["physical_outward_normal"] is None or np.linalg.norm(np.asarray(port_data["physical_outward_normal"])-cap["outward_normal"])>1e-7:
                    problems.append("Port flow Axis differs from actual cap outward normal")
                if shape is not None and shape.valid and port_data["position_m"] is not None and port_data["physical_outward_normal"] is not None:
                    tolerance=max(1e-7,shape.kernel_tolerance_m);probe=max(1e-4,20*tolerance)
                    p,n=np.asarray(port_data["position_m"]),np.asarray(port_data["physical_outward_normal"])
                    states=[BRepClass3d_SolidClassifier(shape.shape,gp_Pnt(*q),tolerance).State() for q in (p,p+probe*n,p-probe*n)]
                    if states!=[TopAbs_ON,TopAbs_OUT,TopAbs_IN]:
                        problems.append("Port is not on an exterior native cap with the derived physical normal")
                errors.extend(f"{cid}:{slot}:{problem}" for problem in problems)
                actual_ports.append({**port_data,"component_id":cid,"slot":slot,"status":"FAIL" if problems else "PASS"})
            actual_parts.append({"component_id":cid,"ifc_guid":element.GlobalId,**facts,
                "native_volume_m3":shape.volume_m3 if shape is not None else None,"volume_error_m3":volume_error,
                "native_solid_count":solid_count,
                "fitting_count":int(facts["kind"]!="segment")})
        except (ValueError,KeyError,RuntimeError,AttributeError,TypeError) as exc:
            errors.append(f"Unsupported or invalid complete component {cid}:{type(exc).__name__}:{exc}")
    wanted=[]
    for connection in spec["connections"]:
        try:
            wanted.append((slot_map[endpoint(connection["source"])].id(),slot_map[endpoint(connection["sink"])].id()))
        except KeyError:
            errors.append("Declared connection has no actual physical port")
    actual=[]
    for relation in model.by_type("IfcRelConnectsPorts"):
        if relation.RelatingPort.id() in owned_port_ids or relation.RelatedPort.id() in owned_port_ids:
            actual.append((relation.RelatingPort.id(),relation.RelatedPort.id()))
            errors.extend(connected_pair_errors(relation.RelatingPort,relation.RelatedPort,ledger,ifcopenshell.util.unit.calculate_unit_scale(model)))
    if len(actual)!=len(wanted) or set(actual)!=set(wanted):
        errors.append("Actual complete port connectivity differs from the declared directed tree")
    try:
        system=model.by_guid(manifest["source_system_guid"])
        memberships=[o.GlobalId for rel in system.IsGroupedBy for o in rel.RelatedObjects]
        if len(memberships)!=len(guids) or set(memberships)!=guids or system.ObjectType!=spec["system_type"]:
            errors.append("Actual network system membership or declared service differs")
    except (RuntimeError,AttributeError):
        errors.append("Network system membership missing")
    measured={p["component_id"]:p for p in actual_parts}
    lengths={}
    for demand in spec["demand_paths"]:
        try:
            lengths[demand["demand_id"]]=sum(measured[s["component"]]["path_lengths_m"][s["entry_port"]+":"+s["exit_port"]] for s in demand["steps"])
        except KeyError:
            errors.append("Cannot independently measure complete demand path")
    return {"status":"FAIL" if errors else "PASS","errors":errors,"parts":actual_parts,"ports":actual_ports,"connectivity":actual,
        "unique_length_m":sum(p["length_m"] for p in actual_parts),"fitting_count":sum(p["fitting_count"] for p in actual_parts),
        "demand_path_lengths_m":lengths,"original_records_checked":len(original_ids),"physical_components":len(added),
        "physical_ports":len(owned_port_ids),"connections":len(actual),"coordination_status":"NOT_RUN",
        "scope":"Actual IFC component geometry, analytic/native volume, port caps, directed tree and unique inventory; full obstacle clearance is a separate check"}


if __name__=="__main__":
    path=Path(sys.argv[1]);manifest=json.loads(path.read_text(encoding="utf-8"))
    checked=check_network_semantics(manifest["export_path"],manifest["source_path"],manifest)
    manifest["reimport"]={**checked,"fresh_process":True}
    atomic_json(path,manifest)
    print(json.dumps({"status":checked["status"],"errors":checked["errors"],"physical_components":checked["physical_components"]}))
    raise SystemExit(0 if checked["status"]=="PASS" else 1)
