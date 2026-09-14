"""Native BRep fidelity and independent numerical coordination checking.

Uses IfcOpenShell's serialized OpenCASCADE shape representation, never display
triangles. OCP recomputes Boolean intersection volume and minimum shape distance.
This is a declared floating-point CAD checking contract, not an exact-arithmetic
or interval proof. Near-contact and kernel failures remain UNKNOWN.
"""
from __future__ import annotations

from dataclasses import dataclass
import io
import importlib.metadata
import json
from pathlib import Path
import re
import sys
import time
from typing import Any, Callable

import numpy as np

from .audit import atomic_json, sha256_file

CODE_SHA256 = sha256_file(__file__)
DEFAULT_SOURCE_REPRESENTATION_POLICY = "NATIVE_CAD_WITH_EXACT_PLANAR_ENCLOSURES"
VERTEX_HULL_SOURCE_REPRESENTATION_POLICY = "NATIVE_CAD_WITH_SOURCE_VERTEX_HULL_ENCLOSURES"


def _representation_interpretation(policy):
    if policy not in (DEFAULT_SOURCE_REPRESENTATION_POLICY, VERTEX_HULL_SOURCE_REPRESENTATION_POLICY):
        raise ValueError("Unsupported source representation interpretation")
    return {"policy":policy, "native_solid_geometry":"INDEPENDENT_NUMERICAL_CAD_VALIDATION",
            "invalid_native_fallback": "EXACT_SUPPORTED_ANALYTIC_SUPPORT_AND_DECLARED_FACE_VERTEX_HULL_COMPLETIONS_SUBSET_OF_OUTER_BOX" if policy == VERTEX_HULL_SOURCE_REPRESENTATION_POLICY else "EXACT_SUPPORTED_REPRESENTED_SUPPORT_SUBSET_OF_OUTER_BOX",
            "source_support_details":"Each independently rebuilt source certificate binds its supported analytic items and face interpretation",
            "source_native_validity":"UNRESOLVED_WHERE_REPORTED_INVALID",
            "scope_exclusion":"No assertion about arbitrary outside-vertex-hull projection or undocumented physical extent"}


@dataclass
class CadObject:
    entity_id: str
    guid: str
    step_id: int
    source_sha256: str
    ifc_type: str
    shape: Any
    bounds: tuple
    volume_m3: float
    kernel_tolerance_m: float
    valid: bool
    reason: str | None = None
    support_kind: str = "native_solid"
    support_evidence: dict | None = None


def _subshapes(shape, kind):
    from OCP.TopExp import TopExp_Explorer
    items = {}
    iterator = TopExp_Explorer(shape, kind)
    while iterator.More():
        item = iterator.Current()
        items[hash(item)] = item
        iterator.Next()
    return items


def _inspect_shape(shape):
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    from OCP.TopAbs import TopAbs_SOLID, TopAbs_VERTEX, TopAbs_EDGE, TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    from OCP.BRep import BRep_Tool

    if shape.IsNull():
        return None, 0., 0., False, "NULL_CAD_SHAPE"
    box = Bnd_Box()
    BRepBndLib.Add_s(shape, box, False)
    bounds = None
    if not box.IsVoid() and not box.IsOpen():
        lower, upper = box.CornerMin(), box.CornerMax()
        bounds = (lower.X(), lower.Y(), lower.Z(), upper.X(), upper.Y(), upper.Z())
    valid = BRepCheck_Analyzer(shape, True).IsValid()
    solids = TopExp_Explorer(shape, TopAbs_SOLID)
    if not solids.More():
        return bounds, 0., 0., False, "NO_CLOSED_CAD_SOLID"
    all_faces = set(_subshapes(shape, TopAbs_FACE))
    solid_faces = set()
    solid_edges = set()
    solid_vertices = set()
    while solids.More():
        solid_faces.update(_subshapes(solids.Current(), TopAbs_FACE))
        solid_edges.update(_subshapes(solids.Current(), TopAbs_EDGE))
        solid_vertices.update(_subshapes(solids.Current(), TopAbs_VERTEX))
        solids.Next()
    if (all_faces != solid_faces or set(_subshapes(shape,TopAbs_EDGE)) != solid_edges
            or set(_subshapes(shape,TopAbs_VERTEX)) != solid_vertices):
        return bounds, 0., 0., False, "PARTIALLY_NON_SOLID_TOPOLOGY"
    props = GProp_GProps()
    BRepGProp.VolumeProperties_s(shape, props)
    volume = props.Mass()
    tolerance = 0.
    for kind, cast in ((TopAbs_VERTEX, TopoDS.Vertex), (TopAbs_EDGE, TopoDS.Edge), (TopAbs_FACE, TopoDS.Face)):
        explorer = TopExp_Explorer(shape, kind)
        while explorer.More():
            tolerance = max(tolerance, BRep_Tool.Tolerance_s(cast(explorer.Current())))
            explorer.Next()
    if not valid:
        return bounds, volume, tolerance, False, "INVALID_CAD_TOPOLOGY"
    if not np.isfinite(volume) or volume <= 0:
        return bounds, volume, tolerance, False, "NONPOSITIVE_CAD_SOLID_VOLUME"
    return bounds, volume, tolerance, True, None


def _promote_closed_surfaces(shape):
    """Sew original faces without adding caps, then orient-preserving solidify.

    All face support is retained. Missing/open/nonmanifold components and negative
    (possible void) shells are rejected, never filled by a generated hull.
    """
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Sewing, BRepBuilderAPI_MakeSolid
    from OCP.TopAbs import TopAbs_FACE, TopAbs_SHELL, TopAbs_EDGE, TopAbs_VERTEX
    from OCP.TopoDS import TopoDS, TopoDS_Compound
    from OCP.BRep import BRep_Builder, BRep_Tool
    from OCP.BRepCheck import BRepCheck_Analyzer

    before_faces = _subshapes(shape, TopAbs_FACE)
    if not before_faces:
        return None, {"reason": "NO_SOURCE_FACES"}
    for kind in (TopAbs_EDGE,TopAbs_VERTEX):
        accounted=set()
        for face in before_faces.values():
            accounted.update(_subshapes(face,kind))
        if accounted != set(_subshapes(shape,kind)):
            return None,{"reason":"LOOSE_SOURCE_EDGES_OR_VERTICES_CANNOT_BE_DROPPED"}
    sewing = BRepBuilderAPI_Sewing(1e-7, True, True, True, False)
    sewing.Add(shape)
    sewing.Perform()
    sewn = sewing.SewedShape()
    evidence = {"method": "ORIGINAL_FACE_SUPPORT_SEWING_AND_CLOSED_SHELL_SOLIDIFICATION",
                "sewing_tolerance_m": 1e-7, "source_faces": len(before_faces),
                "result_faces": len(_subshapes(sewn, TopAbs_FACE)), "free_edges": sewing.NbFreeEdges(),
                "multiple_edges": sewing.NbMultipleEdges(), "deleted_faces": sewing.NbDeletedFaces()}
    if (evidence["free_edges"] or evidence["multiple_edges"] or evidence["deleted_faces"]
            or evidence["source_faces"] != evidence["result_faces"]):
        return None, {**evidence, "reason": "UNRESOLVED_OPEN_NONMANIFOLD_OR_CHANGED_FACE_SUPPORT"}
    compound = TopoDS_Compound()
    builder = BRep_Builder()
    builder.MakeCompound(compound)
    shells = _subshapes(sewn, TopAbs_SHELL)
    accounted = set()
    for raw in shells.values():
        shell = TopoDS.Shell(raw)
        accounted.update(_subshapes(shell, TopAbs_FACE))
        if not BRep_Tool.IsClosed_s(shell):
            return None, {**evidence, "reason": "SHELL_NOT_CLOSED"}
        solid = BRepBuilderAPI_MakeSolid(shell).Solid()
        _, volume, _, valid, reason = _inspect_shape(solid)
        if not valid:
            return None, {**evidence, "reason": reason, "rejected_shell_volume_m3": volume}
        builder.Add(compound, solid)
    if not shells or accounted != set(_subshapes(sewn, TopAbs_FACE)):
        return None, {**evidence, "reason": "UNACCOUNTED_NON_SHELL_FACES"}
    if not BRepCheck_Analyzer(compound).IsValid():
        return None, {**evidence, "reason": "PROMOTED_COMPOUND_INVALID"}
    return compound, {**evidence, "shell_count": len(shells), "status": "PROMOTED_WITHOUT_CAPS_OR_HULLS"}


def _complete_representation_support(model, entity):
    """Conservative native-bound fallback only for known represented IFC items."""
    supported = {"IfcExtrudedAreaSolid", "IfcRevolvedAreaSolid", "IfcSweptDiskSolid", "IfcSweptDiskSolidPolygonal",
                 "IfcFacetedBrep", "IfcFacetedBrepWithVoids", "IfcAdvancedBrep", "IfcAdvancedBrepWithVoids",
                 "IfcPolygonalFaceSet", "IfcTriangulatedFaceSet", "IfcShellBasedSurfaceModel", "IfcFaceBasedSurfaceModel",
                 "IfcBooleanResult", "IfcBooleanClippingResult", "IfcHalfSpaceSolid", "IfcPolygonalBoundedHalfSpace",
                 "IfcCsgSolid", "IfcBlock", "IfcSphere", "IfcRightCircularCylinder", "IfcRightCircularCone",
                 "IfcMappedItem", "IfcGeometricSet"}
    body = [r for r in entity.Representation.Representations if r.RepresentationIdentifier in ("Body", "Facetation", None)] if entity.Representation else []
    items = []
    unsupported = []
    def inspect_item(item):
        items.append({"step_id": item.id(), "type": item.is_a()})
        if item.is_a() not in supported:
            unsupported.append(item.is_a())
        if item.is_a("IfcMappedItem"):
            for child in item.MappingSource.MappedRepresentation.Items:
                inspect_item(child)
        elif item.is_a("IfcGeometricSet"):
            for child in item.Elements:
                inspect_item(child)
    for representation in body:
        for item in representation.Items:
            inspect_item(item)
    return {"complete_supported_body_representation": bool(items) and not unsupported,
            "representation_items": items, "unsupported_item_types": sorted(set(unsupported)),
            "scope": "Imported IFC representation support, not undocumented real-world extent"}


def _source_conversion_diagnostics(model, selected, raw):
    """Separate explicit non-geometric style failures from geometry failures."""
    by_product, unscoped = {}, []
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            item=json.loads(line)
        except (ValueError,TypeError):
            unscoped.append({"reason":"UNPARSEABLE_NATIVE_CONVERSION_DIAGNOSTIC","text":line[:2000]})
            continue
        if item.get("level", "").lower() not in ("error","fatal"):
            continue
        instance_match=re.match(r"#(\d+)",item.get("instance", ""))
        product_match=re.match(r"#(\d+)",item.get("product", ""))
        instance=model.by_id(int(instance_match.group(1))) if instance_match else None
        # These explicit classes carry material appearance, not occupied support.
        appearance=bool(instance and (instance.is_a("IfcMaterial") or instance.is_a("IfcSurfaceStyle")
                        or instance.is_a("IfcSurfaceStyleRendering") or instance.is_a("IfcColourRgb")))
        product_id=int(product_match.group(1)) if product_match else None
        record={"level":item.get("level"),"message":item.get("message"),
                "instance_step_id":instance.id() if instance else None,"instance_type":instance.is_a() if instance else None,
                "scope":"MATERIAL_APPEARANCE_ONLY" if appearance else "GEOMETRY_CONVERSION_FAILURE"}
        if product_id in selected:
            by_product.setdefault(product_id,[]).append(record)
        elif not appearance:
            unscoped.append({"reason":"UNSCOPED_NATIVE_GEOMETRY_CONVERSION_FAILURE",**record})
    return by_product,unscoped


def _load_cad_uncached(path: str | Path, *, guids: set[str] | None = None, threads: int = 4,
                       source_representation_policy=DEFAULT_SOURCE_REPRESENTATION_POLICY,
                       checkpoint: Callable[[str], None] | None = None) -> tuple[list[CadObject], list[dict]]:
    """Read all selected physical objects as world-meter native solids.

    Returns objects plus explicit missing/conversion failures. Source assemblies
    with no own representation are accounted through their physical children.
    """
    import ifcopenshell
    import ifcopenshell.geom
    import ifcopenshell.util.unit
    from OCP.TopoDS import TopoDS_Shape
    from OCP.BRepTools import BRepTools
    from OCP.BRep import BRep_Builder

    _representation_interpretation(source_representation_policy)
    if checkpoint:
        checkpoint("cad_source_parse")
    path = Path(path).resolve()
    source = sha256_file(path)
    ifcopenshell.get_log()  # Clear prior operations' diagnostics in this process.
    ifcopenshell.ifcopenshell_wrapper.set_log_format_json()
    model = ifcopenshell.open(str(path))
    units = [u for assignment in model.by_type("IfcUnitAssignment") for u in assignment.Units
             if getattr(u, "UnitType", None) == "LENGTHUNIT"]
    if len(units) != 1:
        return [], [{"source_sha256": source, "reason": "AMBIGUOUS_OR_MISSING_LENGTH_UNITS"}]
    entities = [e for e in model.by_type("IfcElement") if not e.is_a("IfcFeatureElementSubtraction")
                and (guids is None or e.GlobalId in guids)]
    selected = {e.id(): e for e in entities}
    if guids is not None:
        absent = guids - {e.GlobalId for e in entities}
        if absent:
            return [], [{"source_sha256": source, "reason": "REQUESTED_GUIDS_ABSENT", "guids": sorted(absent)}]
    settings = ifcopenshell.geom.settings()
    settings.set("iterator-output", ifcopenshell.ifcopenshell_wrapper.SERIALIZED)
    settings.set("use-world-coords", True)
    result, errors, processed = [], [], set()
    from .enclosure import ExactIfcEncloser
    encloser = None
    def apply_exact_enclosure(obj):
        nonlocal encloser
        if encloser is None:
            encloser=ExactIfcEncloser(path,model,vertex_hull_completion=source_representation_policy == VERTEX_HULL_SOURCE_REPRESENTATION_POLICY)
        certificate=encloser.enclose_product(selected[obj.step_id])
        obj.support_evidence["exact_source_enclosure"]=certificate
        if certificate["status"] == "ENCLOSURE_CHECKED":
            from fractions import Fraction
            lo,hi=certificate["bounds_m"]
            obj.bounds=tuple(np.nextafter(float(Fraction(v)),-np.inf) for v in lo)+tuple(np.nextafter(float(Fraction(v)),np.inf) for v in hi)
            obj.support_kind="exact_source_support_enclosure"
    if selected:
        iterator = ifcopenshell.geom.iterator(settings, model, max(1, min(16, threads)), include=entities)
        if iterator.initialize():
            while True:
                if checkpoint:
                    checkpoint("cad_native_object")
                serialized = iterator.get()
                entity = selected.get(serialized.id)
                if entity is not None:
                    processed.add(entity.id())
                    try:
                        shape = TopoDS_Shape()
                        BRepTools.Read_s(shape, io.BytesIO(serialized.geometry.brep_data.encode("utf-8")), BRep_Builder())
                        bounds, volume, tolerance, valid, reason = _inspect_shape(shape)
                        support_kind = "native_solid"
                        support = _complete_representation_support(model, entity)
                        if not valid and reason in ("NO_CLOSED_CAD_SOLID", "PARTIALLY_NON_SOLID_TOPOLOGY"):
                            promoted, promotion = _promote_closed_surfaces(shape)
                            support["promotion"] = promotion
                            if promoted is not None:
                                shape = promoted
                                bounds, volume, tolerance, valid, reason = _inspect_shape(shape)
                                support_kind = "original_faces_closed_shell_promotion"
                        if valid and not support["complete_supported_body_representation"]:
                            support["native_topology_valid"]=True
                            valid=False
                            reason="INCOMPLETE_OR_UNSUPPORTED_SOURCE_BODY_ITEMS"
                            support_kind="unresolved_native_support"
                        if not valid and bounds is not None and support["complete_supported_body_representation"]:
                            if encloser is None:
                                encloser = ExactIfcEncloser(path, model, vertex_hull_completion=source_representation_policy == VERTEX_HULL_SOURCE_REPRESENTATION_POLICY)
                            exact_enclosure = encloser.enclose_product(entity)
                            support["exact_source_enclosure"] = exact_enclosure
                            if exact_enclosure["status"] == "ENCLOSURE_CHECKED":
                                from fractions import Fraction
                                lo, hi = exact_enclosure["bounds_m"]
                                # Round rational endpoints outwards, never inward.
                                bounds = tuple(np.nextafter(float(Fraction(v)), -np.inf) for v in lo) + tuple(np.nextafter(float(Fraction(v)), np.inf) for v in hi)
                                support_kind = "exact_source_support_enclosure"
                            else:
                                support_kind = "unresolved_native_support"
                        result.append(CadObject(f"{source}:{entity.id()}", entity.GlobalId, entity.id(), source,
                                                entity.is_a(), shape, bounds, volume, tolerance, valid, reason, support_kind, support))
                    except Exception as exc:
                        errors.append({"entity_id": f"{source}:{entity.id()}", "ifc_guid": entity.GlobalId,
                                       "reason": "CAD_CONVERSION_FAILURE", "error": f"{type(exc).__name__}: {exc}"})
                if not iterator.next():
                    break
    for entity in entities:
        if entity.id() in processed:
            continue
        children = [c for rel in getattr(entity, "IsDecomposedBy", ()) for c in rel.RelatedObjects]
        if entity.Representation is None and children:
            continue
        errors.append({"entity_id": f"{source}:{entity.id()}", "ifc_guid": entity.GlobalId,
                       "reason": "MISSING_PHYSICAL_CAD_GEOMETRY"})
    diagnostics,unscoped=_source_conversion_diagnostics(model,selected,ifcopenshell.get_log())
    errors.extend({"source_sha256":source,**error} for error in unscoped)
    for obj in result:
        records=diagnostics.get(obj.step_id,[])
        if records:
            obj.support_evidence["native_conversion_diagnostics"]=records
        if any(r["scope"] == "GEOMETRY_CONVERSION_FAILURE" for r in records):
            if obj.valid:
                obj.support_evidence["native_topology_valid"]=True
            obj.valid=False
            obj.reason="PARTIAL_NATIVE_SOURCE_CONVERSION_FAILURE"
            obj.support_kind="unresolved_native_support"
            apply_exact_enclosure(obj)
    return result, errors


def load_cad(path: str | Path, *, guids: set[str] | None = None, threads: int = 4,
             cache_directory: str | Path | None = None, cache_report: dict | None = None,
             source_representation_policy=DEFAULT_SOURCE_REPRESENTATION_POLICY,
             checkpoint: Callable[[str], None] | None = None):
    """Fresh source load or immutable checker-produced native-geometry cache.

    Cache identity includes exact source bytes, implementation and kernel versions.
    Every cached BRep digest and native topology is independently rechecked; cached
    margins and engineering verdicts do not exist in this cache.
    """
    if cache_directory is None:
        return _load_cad_uncached(path, guids=guids, threads=threads, source_representation_policy=source_representation_policy, checkpoint=checkpoint)
    from .cad_cache import load_or_build
    return load_or_build(path, guids=guids, threads=threads, directory=cache_directory,
                         report=cache_report, build=_load_cad_uncached, source_representation_policy=source_representation_policy, checkpoint=checkpoint)


def _bbox_distance(a, b):
    if a is None or b is None:
        return 0.
    gap = np.maximum(np.asarray(a[:3]) - np.asarray(b[3:]), np.asarray(b[:3]) - np.asarray(a[3:]))
    return float(np.linalg.norm(np.maximum(gap, 0.)))


def check_pair(a: CadObject, b: CadObject, *, clearance_m: float = 0., numerical_tolerance_m: float = 1e-6) -> dict:
    """Check one pair: common solid volume first, distance second, ambiguity last."""
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common
    from OCP.BRepExtrema import BRepExtrema_DistShapeShape
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    if not np.isfinite(clearance_m) or clearance_m < 0 or not np.isfinite(numerical_tolerance_m) or numerical_tolerance_m <= 0:
        raise ValueError("Finite nonnegative clearance and positive numerical tolerance required")
    budget = numerical_tolerance_m + a.kernel_tolerance_m + b.kernel_tolerance_m
    result = {"participants": [a.entity_id, b.entity_id], "participant_guids": [a.guid, b.guid],
              "required_clearance_m": clearance_m, "numerical_budget_m": budget, "status": "UNKNOWN",
              "common_volume_m3": None, "distance_m": None}
    enclosed_a = a.valid or a.support_kind == "exact_source_support_enclosure"
    enclosed_b = b.valid or b.support_kind == "exact_source_support_enclosure"
    if not enclosed_a or not enclosed_b:
        return {**result, "reason": "INVALID_OR_UNSUPPORTED_SOLID", "details": [a.reason, b.reason]}
    broad_margin = _bbox_distance(a.bounds, b.bounds) - clearance_m
    if broad_margin > budget:
        return {**result, "status": "PASS", "reason": "Conservative native CAD bounding boxes separated beyond clearance and numerical budget",
                "distance_lower_bound_m": broad_margin + clearance_m, "stage": "BROAD_PHASE_PROVEN_SEPARATION",
                "support_kinds": [a.support_kind,b.support_kind],
                "scope": "All represented obstacle support, including interior completion within checked outer enclosure"}
    if not a.valid or not b.valid:
        return {**result, "status":"BLOCKED", "reason":"ROUTE_TOO_CLOSE_TO_EXACT_OUTER_ENCLOSURE_WITH_UNRESOLVED_INTERIOR",
                "support_kinds":[a.support_kind,b.support_kind]}
    try:
        common = BRepAlgoAPI_Common(a.shape, b.shape)
        common.SetRunParallel(False)
        common.SetFuzzyValue(0.)
        common.Build()
        if not common.IsDone():
            return {**result, "reason": "BOOLEAN_INTERSECTION_DID_NOT_COMPLETE"}
        props = GProp_GProps()
        BRepGProp.VolumeProperties_s(common.Shape(), props)
        common_volume = props.Mass()
        result["common_volume_m3"] = common_volume
        if not np.isfinite(common_volume) or common_volume < 0:
            return {**result, "reason": "AMBIGUOUS_BOOLEAN_VOLUME"}
        distance = BRepExtrema_DistShapeShape(a.shape, b.shape)
        distance.Perform()
        if not distance.IsDone() or distance.NbSolution() < 1:
            return {**result, "reason": "CAD_DISTANCE_DID_NOT_COMPLETE"}
        measured = float(distance.Value())
        p1, p2 = distance.PointOnShape1(1), distance.PointOnShape2(1)
        result.update(distance_m=measured, witness={"p1": [p1.X(), p1.Y(), p1.Z()], "p2": [p2.X(), p2.Y(), p2.Z()]})
        # Never use positive distance as a substitute for overlap checking.
        if common_volume > 0:
            return {**result, "status": "FAIL", "reason": "POSITIVE_COMMON_SOLID_VOLUME", "rule": "FORBIDDEN_INTERFERENCE"}
        margin = measured - clearance_m
        result["clearance_margin_m"] = margin
        if margin < -budget:
            return {**result, "status": "FAIL", "reason": "CLEARANCE_VIOLATION", "rule": "CLEARANCE"}
        if margin <= budget:
            return {**result, "reason": "CONTACT_OR_NEAR_THRESHOLD_NUMERICAL_AMBIGUITY"}
        return {**result, "status": "PASS", "reason": "NO_COMMON_SOLID_AND_POSITIVE_CLEARANCE_MARGIN", "stage": "NARROW_PHASE"}
    except Exception as exc:
        return {**result, "reason": "CAD_KERNEL_EXCEPTION", "error": f"{type(exc).__name__}: {exc}"}


def _explicit_joints(export_path, route_guids):
    """Reconstruct joint location, outward axes and sections from exported IFC."""
    import ifcopenshell
    import ifcopenshell.util.placement
    import ifcopenshell.util.unit
    from .ports import ownership_ledger, port_facts, connected_pair_errors
    model = ifcopenshell.open(str(export_path))
    scale = ifcopenshell.util.unit.calculate_unit_scale(model)
    ledger = ownership_ledger(model)
    owners = {pid: next(iter(record["owners"].values())) for pid, record in ledger.items()
              if len(record["owners"]) == 1 and len(record["relationships"]) == 1}
    joints = {}
    for rel in model.by_type("IfcRelConnectsPorts"):
        left, right = owners.get(rel.RelatingPort.id()), owners.get(rel.RelatedPort.id())
        if left is None or right is None or left.GlobalId not in route_guids or right.GlobalId not in route_guids:
            continue
        if connected_pair_errors(rel.RelatingPort, rel.RelatedPort, ledger, scale):
            continue
        pa = ifcopenshell.util.placement.get_local_placement(rel.RelatingPort.ObjectPlacement)
        pb = ifcopenshell.util.placement.get_local_placement(rel.RelatedPort.ObjectPlacement)
        fa = port_facts(rel.RelatingPort, ledger[rel.RelatingPort.id()], scale)
        fb = port_facts(rel.RelatedPort, ledger[rel.RelatedPort.id()], scale)
        solids_a = [i for rep in left.Representation.Representations for i in rep.Items if i.is_a("IfcSweptAreaSolid") and i.SweptArea.is_a("IfcCircleProfileDef")]
        solids_b = [i for rep in right.Representation.Representations for i in rep.Items if i.is_a("IfcSweptAreaSolid") and i.SweptArea.is_a("IfcCircleProfileDef")]
        if len(solids_a) != 1 or len(solids_b) != 1:
            continue
        radius_a, radius_b = solids_a[0].SweptArea.Radius*scale, solids_b[0].SweptArea.Radius*scale
        joints[frozenset((left.GlobalId, right.GlobalId))] = {
            "point_a": (pa[:3,3]*scale).tolist(), "point_b": (pb[:3,3]*scale).tolist(),
            "axis_a": fa["physical_outward_normal"], "axis_b": fb["physical_outward_normal"], "radius_a": radius_a, "radius_b": radius_b,
            "flow_axis_a": fa["flow_axis"], "flow_axis_b": fb["flow_axis"], "axis_convention": fa["axis_convention"],
            "flow_a": rel.RelatingPort.FlowDirection, "flow_b": rel.RelatedPort.FlowDirection,
            "relationship_guid": rel.GlobalId}
    return joints


def _authorize_joint_contact(a, b, joint, tolerance):
    """Constrain zero-volume common topology to one explicit interface disk."""
    from OCP.BRepAlgoAPI import BRepAlgoAPI_Common, BRepAlgoAPI_Cut, BRepAlgoAPI_Section
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder
    from OCP.gp import gp_Ax2, gp_Pnt, gp_Dir
    from OCP.TopAbs import TopAbs_VERTEX, TopAbs_EDGE, TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer

    center = np.asarray(joint["point_a"])
    axis = np.asarray(joint["axis_a"])
    budget = tolerance + a.kernel_tolerance_m + b.kernel_tolerance_m
    if (np.linalg.norm(center-np.asarray(joint["point_b"])) > budget or
            np.linalg.norm(axis+np.asarray(joint["axis_b"])) > tolerance or
            abs(joint["radius_a"]-joint["radius_b"]) > tolerance or
            {joint["flow_a"], joint["flow_b"]} != {"SINK", "SOURCE"}):
        return False, "JOINT_PORTS_OR_SECTIONS_INCOMPATIBLE"
    common = BRepAlgoAPI_Common(a.shape, b.shape)
    common.SetFuzzyValue(0.)
    common.Build()
    if not common.IsDone():
        return False, "JOINT_BOOLEAN_FAILED"
    contact_shape = common.Shape()
    topology_present = any(TopExp_Explorer(contact_shape, k).More() for k in (TopAbs_VERTEX, TopAbs_EDGE, TopAbs_FACE))
    if not topology_present:
        # Solid common discards lower-dimensional contact in this kernel. Rebuild
        # the complete surface-intersection boundary rather than exempting a pair.
        section = BRepAlgoAPI_Section(a.shape, b.shape, False)
        section.SetFuzzyValue(0.)
        section.Build()
        if not section.IsDone():
            return False, "JOINT_SECTION_FAILED"
        contact_shape = section.Shape()
        if not any(TopExp_Explorer(contact_shape, k).More() for k in (TopAbs_VERTEX, TopAbs_EDGE, TopAbs_FACE)):
            return False, "JOINT_COMMON_TOPOLOGY_EMPTY_OR_AMBIGUOUS"
    base = center-axis*budget
    allowed = BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(*base), gp_Dir(*axis)), joint["radius_a"]+budget, 2*budget).Shape()
    outside = BRepAlgoAPI_Cut(contact_shape, allowed)
    outside.SetFuzzyValue(0.)
    outside.Build()
    if not outside.IsDone():
        return False, "JOINT_INTERFACE_DIFFERENCE_FAILED"
    if any(TopExp_Explorer(outside.Shape(), k).More() for k in (TopAbs_VERTEX, TopAbs_EDGE, TopAbs_FACE)):
        return False, "CONTACT_EXTENDS_BEYOND_AUTHORIZED_JOINT_DISK"
    return True, "ZERO_VOLUME_CONTACT_CONFINED_TO_EXPLICIT_JOINT_DISK"


def _source_preservation_evidence(original_paths, export_path):
    """A single unchanged model has an exact source-local datum correspondence."""
    import ifcopenshell
    if len(original_paths) != 1:
        return None
    manifest_path = Path(export_path).with_suffix(".manifest.json")
    if not manifest_path.exists():
        return None
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("source_sha256") != sha256_file(original_paths[0]) or manifest.get("export_sha256") != sha256_file(export_path):
        return None
    before, after = ifcopenshell.open(str(original_paths[0])), ifcopenshell.open(str(export_path))
    for entity in before:
        try:
            if str(entity) != str(after.by_id(entity.id())):
                return None
        except RuntimeError:
            return None
    return {"method": "SOURCE_SHA_AND_ALL_ORIGINAL_STEP_RECORDS_RECHECKED", "source_sha256": manifest["source_sha256"],
            "transform": np.eye(4).tolist(), "export_sha256": manifest["export_sha256"]}


def _transform_object(obj, matrix):
    from OCP.gp import gp_Trsf
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    transform = np.asarray(matrix, dtype=float)
    if np.allclose(transform, np.eye(4), rtol=0, atol=1e-15):
        return obj
    if transform.shape != (4,4) or not np.allclose(transform[:3,:3].T @ transform[:3,:3], np.eye(3), atol=1e-9) or np.linalg.det(transform[:3,:3]) <= 0:
        raise ValueError("CAD federation transform must be rigid and orientation preserving")
    trsf = gp_Trsf()
    trsf.SetValues(*transform[:3,:].ravel().tolist())
    shape = BRepBuilderAPI_Transform(obj.shape, trsf, True).Shape()
    bounds, volume, tolerance, valid, reason = _inspect_shape(shape)
    support = obj.support_evidence
    if obj.support_kind == "exact_source_support_enclosure":
        # The native shape may omit or project source polygon support. Its box
        # must never replace the independently extracted source enclosure.
        from fractions import Fraction
        certificate = support["exact_source_enclosure"]
        source_lo, source_hi = [[Fraction(x) for x in row] for row in certificate["bounds_m"]]
        target_lo, target_hi = [], []
        for row in transform[:3]:
            lower = upper = Fraction.from_float(float(row[3]))
            for coefficient, lo, hi in zip(row[:3], source_lo, source_hi):
                value = Fraction.from_float(float(coefficient))
                lower += min(value*lo, value*hi)
                upper += max(value*lo, value*hi)
            target_lo.append(lower)
            target_hi.append(upper)
        bounds = tuple(np.nextafter(float(x), -np.inf) for x in target_lo) + tuple(np.nextafter(float(x), np.inf) for x in target_hi)
        support = {**support, "federation_enclosure_transform": {
            "matrix": transform.tolist(), "bounds_m": [[str(x) for x in target_lo], [str(x) for x in target_hi]],
            "method": "EXACT_RATIONAL_AFFINE_BOX_IMAGE_AT_DECLARED_BINARY64_MATRIX",
            "frame": "VERIFIED_LOCAL_FEDERATION_ENGINEERING_METRES"}}
    # Transforming a partial native body cannot repair missing/unsupported IFC
    # source items. Preserve the source-level disposition even when the copied
    # native fragment itself happens to be a valid solid.
    transformed_valid = obj.valid and valid
    transformed_reason = reason if not valid else obj.reason
    return CadObject(obj.entity_id, obj.guid, obj.step_id, obj.source_sha256, obj.ifc_type, shape,
                     bounds, volume, tolerance, transformed_valid, transformed_reason, obj.support_kind, support)


def _revalidate_federation(original_paths, requested):
    if not isinstance(requested, dict) or requested.get("status") != "VERIFIED":
        return None
    from .federation import audited_local_federation
    audits = [{"source_path": str(Path(p).resolve()), "source_sha256": sha256_file(p), "units": {"status":"KNOWN"}} for p in original_paths]
    derived = audited_local_federation(audits, requested.get("reference_source_sha256"))
    if derived["status"] != "VERIFIED":
        return None
    claimed = {s["source_sha256"]: s["transform"] for s in requested.get("sources", [])}
    if any(s["source_sha256"] not in claimed or not np.allclose(s["transform"], claimed[s["source_sha256"]], rtol=0, atol=1e-12) for s in derived["sources"]):
        return None
    return derived


def _candidate_obstacle_pairs(routes, obstacles, clearance, tolerance, backend, checkpoint):
    """Accelerator candidates plus independent CPU separation of every omission.

    A returned GPU overlap is never a verdict. Even an erroneous GPU omission is
    restored unless an independent outward-rounded scalar-axis gap is sufficient.
    Unsupported objects are always returned and still block downstream checking.
    """
    from oma.broadphase import BroadphaseIndex
    eligible = [i for i,obj in enumerate(obstacles) if (obj.valid or obj.support_kind == "exact_source_support_enclosure")
                and obj.bounds is not None and len(obj.bounds) == 6 and np.isfinite(obj.bounds).all()
                and np.all(np.asarray(obj.bounds[:3]) <= np.asarray(obj.bounds[3:]))]
    others = set(range(len(obstacles))) - set(eligible)
    valid_routes = [i for i,obj in enumerate(routes) if obj.valid and obj.bounds is not None and np.isfinite(obj.bounds).all()]
    candidates = {i:list(range(len(obstacles))) for i in range(len(routes)) if i not in valid_routes}
    metrics = {"backend":"cpu", "independent_cpu_omission_guard":True, "index_omitted_pairs":0,
               "cpu_certified_omitted_pairs":0,"false_negative_guard_reinsertions":0}
    if not eligible or not valid_routes:
        candidates.update({i:list(range(len(obstacles))) for i in valid_routes})
        return candidates, metrics
    boxes = np.asarray([obstacles[i].bounds for i in eligible],dtype=np.float64)
    query_boxes = np.asarray([routes[i].bounds for i in valid_routes],dtype=np.float64)
    maximum_budget = np.nextafter(clearance+tolerance+max(routes[i].kernel_tolerance_m for i in valid_routes)
                                  +max(obstacles[i].kernel_tolerance_m for i in eligible),np.inf)
    selected_backend = "cpu" if backend == "auto" and len(eligible)*len(valid_routes) < 1_000_000 else backend
    index = BroadphaseIndex(boxes,backend=selected_backend)
    try:
        for query_index, proposed in index.query(query_boxes,expansion_m=maximum_budget):
            if checkpoint:
                checkpoint("cad_broadphase_batch")
            route_index=valid_routes[query_index]
            selected=set(int(i) for i in proposed)
            if any(i<0 or i>=len(eligible) for i in selected):
                raise ValueError("Broadphase returned an invalid obstacle index")
            omitted=np.asarray([i for i in range(len(eligible)) if i not in selected],dtype=np.int64)
            metrics["index_omitted_pairs"]+=len(omitted)
            if len(omitted):
                # Subtraction rounds to binary64; one step toward -infinity is a
                # lower bound. The required gap was rounded upward above.
                query=query_boxes[query_index]
                gap=np.maximum(query[:3]-boxes[omitted,3:],boxes[omitted,:3]-query[3:])
                separated=np.any(np.nextafter(gap,-np.inf)>maximum_budget,axis=1)
                restored=omitted[~separated]
                selected.update(int(i) for i in restored)
                metrics["false_negative_guard_reinsertions"]+=len(restored)
                metrics["cpu_certified_omitted_pairs"]+=int(separated.sum())
            candidates[route_index]=sorted(others | {eligible[i] for i in selected})
        metrics.update(backend=index.backend,fallback_reason=index.fallback_reason,timings=dict(index.timings))
    finally:
        index.close()
    if set(candidates) != set(range(len(routes))):
        raise RuntimeError("Broadphase query accounting incomplete")
    return candidates,metrics


def cad_check_routes(original_paths, export_path, route_guids, *, clearance_m=0., numerical_tolerance_m=1e-6,
                     authorized_contacts=None, threads=4, output_path=None, coordinate_evidence=None,
                     cache_directory=None, broadphase_backend="auto",
                     source_representation_policy=DEFAULT_SOURCE_REPRESENTATION_POLICY,
                     checkpoint: Callable[[str], None] | None = None):
    """Fresh read all obstacles and added route solids, retaining complete scope.

    authorized_contacts is reserved for future interface-specific geometric scopes;
    whole-pair exemptions are deliberately rejected. Adjacent route joints are
    counted separately, never globally exempted from self-interference checks.
    """
    if authorized_contacts:
        raise ValueError("Broad pair exemptions unsupported; interface geometry authorization is required")
    if not np.isfinite(clearance_m) or clearance_m < 0 or not np.isfinite(numerical_tolerance_m) or numerical_tolerance_m <= 0:
        raise ValueError("Finite nonnegative clearance and positive numerical tolerance required")
    representation_interpretation = _representation_interpretation(source_representation_policy)
    start = time.perf_counter()
    original_paths = list(original_paths)
    federation = _revalidate_federation(original_paths, coordinate_evidence) if coordinate_evidence else None
    transforms = {s["source_sha256"]: s["transform"] for s in federation["sources"]} if federation else {}
    routes, route_errors = load_cad(export_path, guids=set(route_guids), threads=threads, checkpoint=checkpoint)
    manifest_path = Path(export_path).with_suffix(".manifest.json")
    export_manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    route_transform = transforms.get(export_manifest.get("source_sha256"))
    if route_transform is not None:
        transformed_routes=[]
        for obj in routes:
            if checkpoint:
                checkpoint("cad_federation_transform_route")
            transformed_routes.append(_transform_object(obj,route_transform))
        routes=transformed_routes
    obstacles, errors = [], list(route_errors)
    cache_reports = []
    sources = []
    for path in original_paths:
        source_started=time.perf_counter()
        cache_report = {}
        objects, failures = load_cad(path, threads=threads, cache_directory=cache_directory, cache_report=cache_report,
                                     source_representation_policy=source_representation_policy, checkpoint=checkpoint)
        cache_reports.append(cache_report)
        source_loaded=time.perf_counter()
        source_root = sha256_file(path)
        if source_root in transforms:
            transformed_objects=[]
            for obj in objects:
                if checkpoint:
                    checkpoint("cad_federation_transform_object")
                transformed_objects.append(_transform_object(obj,transforms[source_root]))
            objects=transformed_objects
        cache_report.update(source_load_seconds=source_loaded-source_started,
                            federation_transform_seconds=time.perf_counter()-source_loaded)
        obstacles.extend(objects)
        errors.extend(failures)
        sources.append({"path": str(Path(path).resolve()), "sha256": sha256_file(path)})
    load_seconds = time.perf_counter() - start
    results = []
    candidates,broadphase_report = _candidate_obstacle_pairs(routes,obstacles,clearance_m,numerical_tolerance_m,broadphase_backend,checkpoint)
    pairs = len(routes)*len(obstacles)
    broad_pass = broadphase_report["cpu_certified_omitted_pairs"]
    checked_pairs = 0
    for route_index,route in enumerate(routes):
        for obstacle_index in candidates[route_index]:
            obstacle=obstacles[obstacle_index]
            if checkpoint:
                checkpoint("cad_route_obstacle_pair")
            check = check_pair(route, obstacle, clearance_m=clearance_m, numerical_tolerance_m=numerical_tolerance_m)
            checked_pairs += 1
            if check["status"] == "PASS" and check.get("stage") == "BROAD_PHASE_PROVEN_SEPARATION":
                broad_pass += 1
            else:
                results.append(check)
    if checked_pairs+broadphase_report["cpu_certified_omitted_pairs"] != pairs:
        raise RuntimeError("Physical obstacle pair denominator changed during broadphase")
    failed = sum(r["status"] == "FAIL" for r in results)
    unknown = sum(r["status"] == "UNKNOWN" for r in results)
    blocked = sum(r["status"] == "BLOCKED" for r in results)
    joints = _explicit_joints(export_path, set(route_guids))
    if route_transform is not None:
        matrix = np.asarray(route_transform)
        for joint in joints.values():
            for key in ("point_a", "point_b"):
                joint[key] = (matrix[:3,:3] @ joint[key] + matrix[:3,3]).tolist()
            for key in ("axis_a", "axis_b"):
                joint[key] = (matrix[:3,:3] @ joint[key]).tolist()
    self_results = []
    for i, first in enumerate(routes):
        for second in routes[i+1:]:
            if checkpoint:
                checkpoint("cad_route_self_pair")
            check = check_pair(first, second, clearance_m=0., numerical_tolerance_m=numerical_tolerance_m)
            joint = joints.get(frozenset((first.guid, second.guid)))
            if joint and check["status"] == "UNKNOWN" and check.get("common_volume_m3") == 0:
                accepted, reason = _authorize_joint_contact(first, second, joint, numerical_tolerance_m)
                check.update(status="PASS" if accepted else "UNKNOWN", reason=reason, interface=joint)
            self_results.append(check)
    self_status = "FAIL" if any(x["status"] == "FAIL" for x in self_results) else "UNKNOWN" if any(x["status"] == "UNKNOWN" for x in self_results) else "PASS"
    invalid = [{"entity_id": x.entity_id, "reason": x.reason, "support_kind":x.support_kind,
                "support_evidence":x.support_evidence} for x in routes + obstacles if not x.valid]
    unresolved_geometry = [x for x in routes if not x.valid] + [x for x in obstacles if not x.valid and x.support_kind != "exact_source_support_enclosure"]
    # If exactly one source is also the exported source, coordinates are unchanged
    # and source record preservation is checked independently by export recheck.
    preservation = _source_preservation_evidence(original_paths, export_path)
    coordinate_evidence = preservation or federation or coordinate_evidence
    verified_external = bool(federation and route_transform is not None)
    coordinate_known = bool(preservation or verified_external)
    coordinate_status = "VERIFIED_SAME_SOURCE_RECORDS" if preservation else "VERIFIED_FEDERATION_EVIDENCE" if verified_external else "UNRESOLVED"
    status = "FAIL" if failed or self_status == "FAIL" else "BLOCKED" if errors or unresolved_geometry or blocked or not routes else "UNKNOWN" if unknown or self_status == "UNKNOWN" else "PASS"
    result = {"checker": "oma-native-cad/1", "status": status,
              "implementation": {"cad_code_sha256":CODE_SHA256,
                                 "enclosure_code_sha256":__import__(__package__+".enclosure",fromlist=["CODE_SHA256"]).CODE_SHA256,
                                 "python_version":sys.version,"numpy_version":np.__version__,
                                 "ifcopenshell_version":importlib.metadata.version("ifcopenshell"),
                                 "ocp_version":importlib.metadata.version("cadquery-ocp")},
              "scope": "new_route_vs_all_source_physical_obstacles", "sources": sources,
              "export_sha256": sha256_file(export_path), "route_guids": sorted(route_guids),
              "route_count": len(routes), "obstacle_count": len(obstacles), "pairs_accounted": pairs,
              "broad_separation_passes": broad_pass, "pair_results": results, "failed_pairs": failed,
              "unknown_pairs": unknown, "missing_geometry": errors, "invalid_solids": invalid,
              "blocked_pairs": blocked, "represented_support_enclosures":sum(x.support_kind == "exact_source_support_enclosure" for x in obstacles),
              "clearance_m": clearance_m, "numerical_tolerance_m": numerical_tolerance_m,
              "coordinate_status": coordinate_status, "coordinate_evidence": coordinate_evidence,
              "representation_interpretation": representation_interpretation,
              "coordination_status": status if coordinate_known else "BLOCKED",
              "self_interference_status": self_status, "self_pair_results": self_results,
              "connectivity_status": "NOT_RUN",
              "contract": "Independent OCP Boolean common-volume plus shape distance on valid native closed solids; ambiguous near-contact never passes",
              "proof_level": "NUMERICAL_CAD_CHECK; kernel tolerance accounting is not a formally certified interval bound",
              "common_mode_risk": "Shared IFC parser and upstream OpenCASCADE representation; different OCP kernel binding rechecks native topology",
              "performance": {"cad_load_seconds": load_seconds, "total_seconds": time.perf_counter()-start,
                              "source_cache":cache_reports,"broadphase":broadphase_report,"pairs_entering_individual_check":checked_pairs}}
    if output_path:
        atomic_json(Path(output_path), result)
    return result
