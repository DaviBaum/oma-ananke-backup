"""Shared-anchor local federation transforms, with separate global CRS status."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import numpy as np

from .audit import sha256_file


def audited_local_federation(audits: list[dict], reference_source_id: str | None = None) -> dict:
    """Derive transforms from shared Site and Building identities and placements.

    Preconditions: one shared site and building GUID per source, matching relative
    building/site transform, compatible project/world orientation and normalized
    named storey elevations. The reference anchor is unchanged. All transforms
    act on world-meter source coordinates; no discipline bounds are centered.
    Site RefElevation/lat/lon are retained separately and never override geometry.
    """
    import ifcopenshell
    import ifcopenshell.util.placement
    import ifcopenshell.util.unit

    if not audits:
        raise ValueError("No federation sources")
    observations = []
    for audit in audits:
        path = audit["source_path"]
        if sha256_file(path) != audit["source_sha256"]:
            raise ValueError("Source hash changed after import")
        model = ifcopenshell.open(path)
        scale = ifcopenshell.util.unit.calculate_unit_scale(model)
        declared_length_units = [u for assignment in model.by_type("IfcUnitAssignment") for u in assignment.Units if getattr(u,"UnitType",None) == "LENGTHUNIT"]
        sites, buildings = model.by_type("IfcSite"), model.by_type("IfcBuilding")
        record = {"source_sha256": audit["source_sha256"], "path": str(path), "units_to_m": scale,
                  "schema": model.schema, "status": "UNRESOLVED"}
        if len(sites) != 1 or len(buildings) != 1 or len(declared_length_units) != 1 or audit["units"]["status"] != "KNOWN":
            observations.append({**record, "reason": "Single shared site/building and explicit length units required"})
            continue
        site, building = sites[0], buildings[0]
        def matrix(entity):
            result = ifcopenshell.util.placement.get_local_placement(entity.ObjectPlacement)
            result[:3,3] *= scale
            if not np.isfinite(result).all():
                raise ValueError("Nonfinite anchor placement")
            return result
        try:
            site_matrix, building_matrix = matrix(site), matrix(building)
            contexts = model.by_type("IfcGeometricRepresentationContext", include_subtypes=False)
            north = [list(c.TrueNorth.DirectionRatios) if c.TrueNorth else None for c in contexts]
            wcs = []
            for context in contexts:
                m = ifcopenshell.util.placement.get_axis2placement(context.WorldCoordinateSystem)
                m[:3,3] *= scale
                wcs.append(m.tolist())
            levels = {e.Name: e.Elevation*scale for e in model.by_type("IfcBuildingStorey") if e.Name and e.Elevation is not None}
            observations.append({**record, "status": "MEASURED", "site_guid": site.GlobalId,
                "building_guid": building.GlobalId, "project_guids": [e.GlobalId for e in model.by_type("IfcProject")],
                "site_matrix_m": site_matrix.tolist(), "building_matrix_m": building_matrix.tolist(),
                "building_relative_to_site_m": (np.linalg.inv(site_matrix) @ building_matrix).tolist(),
                "true_north": north, "world_contexts_m": wcs, "named_storey_elevations_m": levels,
                "site_geospatial": {"latitude": list(site.RefLatitude) if site.RefLatitude else None,
                                     "longitude": list(site.RefLongitude) if site.RefLongitude else None,
                                     "ref_elevation_m": site.RefElevation*scale if site.RefElevation is not None else None}})
        except Exception as exc:
            observations.append({**record, "reason": f"{type(exc).__name__}: {exc}"})
    reference = next((r for r in observations if r["source_sha256"] == reference_source_id), observations[0])
    sources, transforms = [], {}
    for observed in observations:
        reasons = []
        if observed["status"] != "MEASURED" or reference["status"] != "MEASURED":
            reasons.append("ANCHOR_METADATA_UNRESOLVED")
        else:
            for key in ("site_guid", "building_guid", "project_guids", "true_north"):
                if observed[key] != reference[key]:
                    reasons.append(f"INCONSISTENT_{key.upper()}")
            if not np.allclose(observed["building_relative_to_site_m"], reference["building_relative_to_site_m"], atol=1e-7, rtol=0):
                reasons.append("BUILDING_SITE_RELATIVE_TRANSFORM_DISAGREES")
            if not np.allclose(observed["world_contexts_m"], reference["world_contexts_m"], atol=1e-7, rtol=0):
                reasons.append("WORLD_CONTEXTS_DISAGREE")
            common_levels = observed["named_storey_elevations_m"].keys() & reference["named_storey_elevations_m"].keys()
            if not common_levels or any(abs(observed["named_storey_elevations_m"][k] - reference["named_storey_elevations_m"][k]) > 1e-7 for k in common_levels):
                reasons.append("NAMED_STOREY_ELEVATION_CORRESPONDENCE_UNRESOLVED")
        transform = np.eye(4)
        if not reasons:
            transform = np.asarray(reference["site_matrix_m"]) @ np.linalg.inv(observed["site_matrix_m"])
        evidence = {"method": "SHARED_SITE_BUILDING_GUID_ANCHORS_AND_RELATIVE_TRANSFORMS", "reference_source_sha256": reference["source_sha256"],
                    "observation": observed, "reasons": reasons}
        transforms[observed["source_sha256"]] = {"matrix": transform.tolist(), "inverse_matrix": np.linalg.inv(transform).tolist(),
                                                  "verified": not reasons, "evidence": evidence}
        sources.append({"source_sha256": observed["source_sha256"], "transform": transform.tolist(),
                        "inverse_transform": np.linalg.inv(transform).tolist(), "method": evidence["method"],
                        "status": "VERIFIED" if not reasons else "UNRESOLVED", "evidence": evidence})
    geospatial_values = [r.get("site_geospatial") for r in observations]
    global_consistent = all(value == geospatial_values[0] for value in geospatial_values) and geospatial_values[0] is not None
    result = {"status": "VERIFIED" if all(r["status"] == "VERIFIED" for r in sources) else "UNRESOLVED",
              "scope": "LOCAL_ENGINEERING_ANCHOR_CORRESPONDENCE", "reference_source_sha256": reference["source_sha256"],
              "sources": sources, "transforms": transforms, "observations": observations,
              "global_geospatial_status": "CONSISTENT_DECLARATIONS_NOT_SURVEY_VALIDATION" if global_consistent else "UNRESOLVED_CONFLICTING_OR_MISSING_GEOREFERENCING",
              "global_geospatial_observations": geospatial_values,
              "independent_centering": False, "raw_identity_federation_status": "UNRESOLVED_UNLESS_ALL_ANCHORS_ALREADY_IDENTICAL"}
    result["evidence_root"] = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
    return result


def transform_mesh_payload(payload: dict, matrix) -> dict:
    transform = np.asarray(matrix, dtype=float)
    if transform.shape != (4,4) or not np.isfinite(transform).all():
        raise ValueError("Expected finite affine 4x4 transform")
    result = {**payload, "meshes": []}
    lower, upper = np.full(3, np.inf), np.full(3, -np.inf)
    for mesh in payload["meshes"]:
        vertices = np.asarray(mesh["vertices"], dtype=float).reshape(-1,3)
        vertices = vertices @ transform[:3,:3].T + transform[:3,3]
        lower, upper = np.minimum(lower, vertices.min(axis=0)), np.maximum(upper, vertices.max(axis=0))
        result["meshes"].append({**mesh, "vertices": vertices.ravel().tolist()})
    result["applied_transform_m"] = transform.tolist()
    result["bounds"] = {"min": lower.tolist(), "max": upper.tolist()} if result["meshes"] else None
    return result
