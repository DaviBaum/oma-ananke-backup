"""Measure imported IFC without inferring absent engineering information.

Meshes are display/analysis approximations, not certified CAD clearance bounds.
Every product is accounted for, including iterator failures and absent geometry.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import time
from typing import Any

import numpy as np

AUDIT_VERSION = "oma-ifc-audit/1"


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    temp.replace(path)


def _safe_types(model, name):
    try:
        return model.by_type(name)
    except RuntimeError:
        return []


def _json_safe(value):
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_safe(v) for v in value]
    if hasattr(value, "is_a"):
        return {"step_id": value.id(), "type": value.is_a(), "name": getattr(value, "Name", None)}
    if isinstance(value, float) and not np.isfinite(value):
        return str(value)
    return value


def _identity(product, source):
    semantic = f"{source}:{product.id()}"
    return {"source_id": source, "source_sha256": source, "ifc_guid": getattr(product, "GlobalId", None),
            "step_id": product.id(), "semantic_id": semantic, "entity_id": semantic,
            "render_id": hashlib.sha256(semantic.encode()).hexdigest()[:24]}


def audit_file(path: str | Path, output_dir: str | Path | None = None, geometry: bool = True,
               mesh: bool = True, threads: int = 4) -> dict:
    """Return and optionally persist a complete product audit of one source file.

    Geometry uses source world placements and SI meters, never model centering.
    Missing/failed physical geometry blocks whole-model coordination verification.
    The returned audit contains paths to packed and streamed display mesh artifacts.
    """
    import ifcopenshell
    import ifcopenshell.geom
    import ifcopenshell.util.element
    import ifcopenshell.util.placement
    import ifcopenshell.util.unit

    start = time.perf_counter()
    path = Path(path).resolve()
    with path.open("rb") as stream:
        if not stream.read(4096).lstrip(b"\xef\xbb\xbf \r\n\t").startswith(b"ISO-10303-21;"):
            raise ValueError("Expected actual STEP IFC bytes, not pointer, HTML, or arbitrary data")
    source = sha256_file(path)
    model = ifcopenshell.open(str(path))
    parsed_seconds = time.perf_counter() - start
    unit_scale = ifcopenshell.util.unit.calculate_unit_scale(model)
    if not np.isfinite(unit_scale) or unit_scale <= 0:
        raise ValueError("Invalid length unit scale")
    length_units = [u for a in model.by_type("IfcUnitAssignment") for u in a.Units
                    if getattr(u, "UnitType", None) == "LENGTHUNIT"]
    unit_status = "KNOWN" if len(length_units) == 1 else "AMBIGUOUS_OR_MISSING"
    records = []
    by_id = {}
    guids = defaultdict(list)
    field_counts = Counter()
    for product in sorted(model.by_type("IfcProduct"), key=lambda p: p.id()):
        physical = product.is_a("IfcElement") and not product.is_a("IfcFeatureElementSubtraction")
        representation = getattr(product, "Representation", None)
        children = [child.id() for rel in getattr(product, "IsDecomposedBy", ()) for child in rel.RelatedObjects]
        explicitly_non_geometric = (not physical and representation is None) or (physical and representation is None and bool(children))
        state = "unresolved" if representation or physical else "explicitly_non_geometric"
        if explicitly_non_geometric:
            state = "explicitly_non_geometric"
        record = {**_identity(product, source), "type": product.is_a(), "name": getattr(product, "Name", None),
                  "description": getattr(product, "Description", None), "physical": physical,
                  "geometry_status": state, "geometry_reason": "awaiting_conversion" if representation else
                      ("assembly_children_accounted_separately" if children else "no_representation_in_source"),
                  "has_representation": representation is not None, "decomposed_children": children,
                  "predefined_type": getattr(product, "PredefinedType", None)}
        try:
            container = ifcopenshell.util.element.get_container(product)
            record["container_step_id"] = container.id() if container else None
            record["container_name"] = getattr(container, "Name", None) if container else None
            record["storey_id"] = str(container.id()) if container else None
        except Exception as exc:
            record["containment_error"] = str(exc)
        placement = getattr(product, "ObjectPlacement", None)
        if placement:
            try:
                matrix = ifcopenshell.util.placement.get_local_placement(placement)
                matrix[:3, 3] *= unit_scale
                if not np.isfinite(matrix).all():
                    raise ValueError("Source placement contains degenerate axes or nonfinite coordinates")
                record["placement_matrix_m"] = matrix.tolist()
            except Exception as exc:
                record["placement_error"] = str(exc)
                record["geometry_status"] = "unsupported"
        try:
            psets = ifcopenshell.util.element.get_psets(product)
            record["properties"] = _json_safe(psets)
            names = " ".join(str(key).lower() for props in psets.values() if isinstance(props, dict) for key in props)
            for field, terms in {"size": ("diameter", "width", "height", "size"),
                                 "capacity": ("capacity", "flowrate", "flow rate"),
                                 "load": ("load", "demand"), "maintenance": ("maintenance", "clearance", "access"),
                                 "fire_rating": ("firerating", "fire rating")}.items():
                present = any(term in names for term in terms)
                record[f"has_{field}_property"] = present
                field_counts[field] += int(present)
            materials = ifcopenshell.util.element.get_materials(product)
            record["materials"] = [{"step_id": m.id(), "name": m.Name} for m in materials]
            field_counts["material"] += bool(materials)
        except Exception as exc:
            record["property_error"] = str(exc)
        records.append(record)
        by_id[product.id()] = record
        if record["ifc_guid"]:
            guids[record["ifc_guid"]].append(product.id())
    metadata_seconds = time.perf_counter() - start - parsed_seconds
    out = Path(output_dir) if output_dir is not None else None
    if out:
        out.mkdir(parents=True, exist_ok=True)
    artifact_stem = f"{path.stem}-{source[:12]}"
    mesh_path = out / f"{artifact_stem}.mesh.json.gz" if out and mesh else None
    mesh_temp = mesh_path.with_suffix(".tmp") if mesh_path else None
    mesh_stream = gzip.open(mesh_temp, "wt", encoding="utf-8", compresslevel=3) if mesh_temp else None
    if mesh_stream:
        mesh_stream.write(json.dumps({"state_root": source, "source_id": source, "units": "m", "coordinate_system": "world"})[:-1] + ',"meshes":[')
    vertices_parts, faces_parts, offsets = [], [], []
    total_vertices = 0
    total_faces = 0
    lower, upper = np.full(3, np.inf), np.full(3, -np.inf)
    converted = 0
    geometry_start = time.perf_counter()
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    settings.set("weld-vertices", True)
    settings.set("mesher-linear-deflection", 0.001)
    settings.set("mesher-angular-deflection", 0.1)
    iterator_error = None
    try:
        if geometry:
            iterator = ifcopenshell.geom.iterator(settings, model, max(1, min(16, threads)))
            if iterator.initialize():
                while True:
                    shape = iterator.get()
                    record = by_id.get(shape.id)
                    if record is not None:
                        vertices = np.asarray(shape.geometry.verts, dtype=np.float64).reshape(-1, 3)
                        faces = np.asarray(shape.geometry.faces, dtype=np.int32).reshape(-1, 3)
                        if not len(vertices) or not len(faces):
                            record.update(geometry_status="unsupported", geometry_reason="empty_or_non_surface_representation")
                        elif not np.isfinite(vertices).all() or faces.min() < 0 or faces.max() >= len(vertices):
                            record.update(geometry_status="invalid", geometry_reason="invalid_mesh_coordinates_or_indices")
                        else:
                            lo, hi = vertices.min(axis=0), vertices.max(axis=0)
                            lower, upper = np.minimum(lower, lo), np.maximum(upper, hi)
                            record.update(geometry_status="represented", geometry_reason="tessellated_world_meters",
                                          bounds={"min": lo.tolist(), "max": hi.tolist()},
                                          vertex_count=len(vertices), triangle_count=len(faces),
                                          representation_id=str(shape.geometry.id))
                            record["geometry_content_hash"] = hashlib.sha256(vertices.tobytes() + faces.tobytes()).hexdigest()
                            if mesh_stream:
                                if converted:
                                    mesh_stream.write(",")
                                json.dump({"entity_id": record["entity_id"], "render_id": record["render_id"],
                                           "step_id": shape.id, "type": record["type"],
                                           "vertices": vertices.ravel().tolist(), "faces": faces.ravel().tolist()}, mesh_stream, separators=(",", ":"))
                            if out and mesh:
                                vertices_parts.append(vertices)
                                faces_parts.append(faces)
                                offsets.append((shape.id, total_vertices, len(vertices), total_faces, len(faces)))
                            total_vertices += len(vertices)
                            total_faces += len(faces)
                            converted += 1
                    if not iterator.next():
                        break
    except Exception as exc:
        iterator_error = f"{type(exc).__name__}: {exc}"
    finally:
        if mesh_stream:
            mesh_stream.write("]}")
            mesh_stream.close()
            mesh_temp.replace(mesh_path)
    for record in records:
        if record.get("placement_error"):
            record["geometry_status"] = "invalid"
            record["geometry_reason"] = "invalid_source_placement"
        if record["geometry_status"] == "unresolved" and record["has_representation"]:
            record["geometry_reason"] = "iterator_did_not_produce_geometry" if geometry else "geometry_not_attempted"
    geometry_seconds = time.perf_counter() - geometry_start
    ports = []
    port_owners = defaultdict(set)
    port_owner_relationships = defaultdict(set)
    for rel in _safe_types(model, "IfcRelConnectsPortToElement"):
        port_owners[rel.RelatingPort.id()].add(rel.RelatedElement.id())
        port_owner_relationships[rel.RelatingPort.id()].add(rel.id())
    for rel in _safe_types(model, "IfcRelNests"):
        for child in rel.RelatedObjects:
            if child.is_a("IfcPort"):
                port_owners[child.id()].add(rel.RelatingObject.id())
                port_owner_relationships[child.id()].add(rel.id())
    for port in _safe_types(model, "IfcDistributionPort"):
        owners = sorted(port_owners[port.id()])
        ports.append({**_identity(port, source), "name": port.Name,
                      "owner_step_ids": owners, "owner_step_id": owners[0] if len(owners) == 1 else None,
                      "owner_status": "unique" if len(owners) == 1 else "ambiguous" if owners else "missing",
                      "owner_relationship_step_ids": sorted(port_owner_relationships[port.id()]),
                      "flow_direction": port.FlowDirection, "system_type": getattr(port, "SystemType", None),
                      "predefined_type": getattr(port, "PredefinedType", None),
                      "placement_matrix_m": by_id.get(port.id(), {}).get("placement_matrix_m")})
    explicit_connections = [{"relationship_step_id": rel.id(), "port_a_step_id": rel.RelatingPort.id(),
                             "port_b_step_id": rel.RelatedPort.id(), "realizing_element_step_id":
                                 rel.RealizingElement.id() if rel.RealizingElement else None}
                            for rel in _safe_types(model, "IfcRelConnectsPorts")]
    systems = []
    for system in _safe_types(model, "IfcSystem"):
        members = [obj.id() for rel in getattr(system, "IsGroupedBy", ()) for obj in rel.RelatedObjects]
        systems.append({"step_id": system.id(), "ifc_guid": system.GlobalId, "name": system.Name,
                        "type": system.is_a(), "predefined_type": getattr(system, "PredefinedType", None), "members": members})
        for member in members:
            if member in by_id:
                by_id[member].setdefault("system_ids", []).append(str(system.id()))
    physical = [r for r in records if r["physical"]]
    blocking_objects = [r["entity_id"] for r in physical if r["geometry_status"] in ("invalid", "unsupported", "unresolved")]
    blockers = []
    if blocking_objects:
        blockers.append({"code": "INCOMPLETE_PHYSICAL_GEOMETRY", "entity_ids": blocking_objects, "count": len(blocking_objects)})
    if unit_status != "KNOWN":
        blockers.append({"code": "AMBIGUOUS_OR_MISSING_LENGTH_UNITS"})
    if iterator_error:
        blockers.append({"code": "GEOMETRY_ITERATOR_ERROR", "detail": iterator_error})
    connections_status = "PRESENT" if explicit_connections else "MISSING_INPUTS"
    crs = [_json_safe(entity.get_info()) for name in ("IfcProjectedCRS", "IfcMapConversion", "IfcMapConversionScaled") for entity in _safe_types(model, name)]
    contexts = [{"step_id": c.id(), "type": c.is_a(), "identifier": c.ContextIdentifier,
                 "context_type": c.ContextType, "precision": getattr(c, "Precision", None),
                 "world_coordinate_system": _json_safe(getattr(c, "WorldCoordinateSystem", None))}
                for c in model.by_type("IfcGeometricRepresentationContext", include_subtypes=False)]
    audit = {"audit_version": AUDIT_VERSION, "created_at": datetime.now(timezone.utc).isoformat(),
             "source_path": str(path), "source_id": source, "source_sha256": source, "source_bytes": path.stat().st_size,
             "schema": model.schema, "ifcopenshell_version": ifcopenshell.version,
             "authoring": _json_safe(model.header.file_name.get_info()),
             "units": {"canonical": "m", "source_to_m": unit_scale, "status": unit_status,
                       "declarations": [_json_safe(u.get_info()) for u in length_units]},
             "coordinate_system": "source_world", "coordinate_reference_systems": crs, "contexts": contexts,
             "entity_counts": dict(Counter(entity.is_a() for entity in model)),
             "product_counts": dict(Counter(r["type"] for r in records)),
             "geometry_counts": dict(Counter(r["geometry_status"] for r in records)),
             "physical_geometry_counts": dict(Counter(r["geometry_status"] for r in physical)),
             "physical_object_count": len(physical), "product_count": len(records), "represented_count": converted,
             "bounds": {"min": lower.tolist(), "max": upper.tolist()} if converted else None,
             "properties_presence_counts": dict(field_counts),
             "spatial_hierarchy": [{"step_id": e.id(), "type": e.is_a(), "name": e.Name, "elevation": getattr(e, "Elevation", None)}
                                   for name in ("IfcSite", "IfcBuilding", "IfcBuildingStorey", "IfcSpace") for e in _safe_types(model, name)],
             "missing_containment_count": sum(r.get("container_step_id") is None for r in physical),
             "duplicate_guids": {guid: ids for guid, ids in guids.items() if len(ids) > 1},
             "identity_policy": "source_sha256:STEP_ID; GUID duplicates reported; no automatic merge",
             "products": records, "ports": ports, "explicit_connections": explicit_connections,
             "inferred_connections": [], "connectivity_status": connections_status, "systems": systems,
             "blockers": blockers, "import_status": "IMPORTED_WITH_BLOCKERS" if blockers else "IMPORTED",
             "coordination_verification": {"status": "NOT_RUN", "reason": "Import/mesh conversion is not engineering coordination verification"},
             "geometry_contract": {"kernel": "IfcOpenShell/OpenCASCADE", "world_coordinates": True,
                                   "length_unit": "m", "linear_deflection_m": 0.001, "angular_deflection_rad": 0.1,
                                   "certified_tessellation_error_bound": None,
                                   "use": "display and bounded candidate analysis; not exact CAD clearance proof"},
             "performance": {"parse_seconds": parsed_seconds, "metadata_seconds": metadata_seconds,
                             "geometry_seconds": geometry_seconds, "total_seconds": time.perf_counter() - start,
                             "vertices": total_vertices, "triangles": total_faces, "geometry_threads": threads}}
    if out:
        audit["artifacts"] = {"audit": str(out / f"{artifact_stem}.audit.json")}
        if mesh_path:
            audit["artifacts"]["mesh_json_gz"] = str(mesh_path)
            packed_path = out / f"{artifact_stem}.mesh.npz"
            np.savez_compressed(packed_path, vertices=np.concatenate(vertices_parts) if vertices_parts else np.empty((0, 3)),
                                faces=np.concatenate(faces_parts) if faces_parts else np.empty((0, 3), dtype=np.int32),
                                offsets=np.asarray(offsets, dtype=np.int64).reshape(-1, 5))
            audit["artifacts"]["mesh_npz"] = str(packed_path)
        atomic_json(Path(audit["artifacts"]["audit"]), audit)
    return audit


def load_mesh_payload(audit: dict) -> dict:
    with gzip.open(audit["artifacts"]["mesh_json_gz"], "rt", encoding="utf-8") as stream:
        return json.load(stream)


def federation_manifest(audits: list[dict], project_id: str, transformations: dict | None = None) -> dict:
    """Federate identities, leaving alignment unverified without explicit evidence.

    transformations maps source SHA to {matrix, evidence, verified: bool}.
    An identity matrix is retained for display if absent, but is not called verified.
    """
    if not audits:
        raise ValueError("Federation requires at least one source audit")
    schemas = {a["schema"] for a in audits}
    tracks = {"ifc2x3" if "ifc2x3" in Path(a["source_path"]).stem.lower() else
              "ifc4" if "ifc4" in Path(a["source_path"]).stem.lower() else None for a in audits} - {None}
    if len(tracks) > 1:
        raise ValueError("Separate schema representations cannot be combined into one physical federation")
    transforms = transformations or {}
    sources, guid_index = [], defaultdict(list)
    for audit in audits:
        specified = transforms.get(audit["source_id"], {})
        matrix = np.asarray(specified.get("matrix", np.eye(4)), dtype=float)
        if matrix.shape != (4, 4) or not np.isfinite(matrix).all() or not np.allclose(matrix[3], [0, 0, 0, 1]):
            raise ValueError("Federation transform must be a finite affine 4x4 matrix")
        if not np.allclose(matrix[:3, :3].T @ matrix[:3, :3], np.eye(3), atol=1e-9) or np.linalg.det(matrix[:3, :3]) < 0:
            raise ValueError("Federation accepts rigid orientation-preserving transforms only; units already normalized")
        verified = bool(specified.get("verified") and specified.get("evidence"))
        sources.append({"source_id": audit["source_id"], "path": audit["source_path"], "schema": audit["schema"],
                        "transform_m": matrix.tolist(), "alignment_status": "VERIFIED" if verified else "UNRESOLVED",
                        "alignment_evidence": specified.get("evidence"), "blockers": audit["blockers"]})
        for product in audit["products"]:
            if product["ifc_guid"]:
                guid_index[product["ifc_guid"]].append(product["entity_id"])
    result = {"project_id": project_id, "sources": sources, "schema_track": sorted(schemas),
              "alignment_status": "VERIFIED" if all(s["alignment_status"] == "VERIFIED" for s in sources) else "UNRESOLVED",
              "cross_source_duplicate_guids": {g: ids for g, ids in guid_index.items() if len(ids) > 1},
              "identity_policy": "Never merge by GUID or coincidence; preserve source identity",
              "independent_centering": False}
    result["state_root"] = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
    return result
