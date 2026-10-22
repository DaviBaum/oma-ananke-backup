"""Untrusted geometric scheduling for the independent, failure-only CAD probe."""
from __future__ import annotations

import math

from oma.ifc.negative_witness import find_forbidden_volume_witness


def _proposal_boxes(material):
    """These broad boxes prioritize work only and never discharge an obligation."""
    route = material.get("route_spec")
    if route:
        points = route["points_m"]
        radius = route["diameter_m"] / 2 + route.get("insulation_m", 0) + route.get("bend_radius_m", 0)
        return [([min(p[i] for p in points)-radius for i in range(3)],
                 [max(p[i] for p in points)+radius for i in range(3)])]
    boxes = []
    for component in material.get("network_spec", {}).get("components", []):
        geometry = component["geometry"]
        radius = component["diameter_m"] / 2 + component.get("insulation_m", 0)
        if component["kind"] == "tee":
            frame = geometry["frame_m"]
            points = [[frame[i][3] for i in range(3)]]
            radius += max(geometry["trunk_takeout_m"], geometry["branch_takeout_m"])
        elif component["kind"] == "elbow":
            points = [geometry["center_m"]]
            radius += geometry["bend_radius_m"]
        else:
            points = [geometry["start_m"], geometry["end_m"]]
        boxes.append(([min(p[i] for p in points)-radius for i in range(3)],
                      [max(p[i] for p in points)+radius for i in range(3)]))
    return boxes


def probe_candidate_failure(store, state, material, guids, control):
    """A missing hint or unsuccessful probe always leaves full checking required."""
    try:
        boxes = _proposal_boxes(material)
        hints = []
        for entity in state.get("entities", []):
            bounds = entity.get("geometry", {}).get("bounds")
            provenance = entity.get("provenance", {})
            if not bounds or not provenance.get("guid"):
                continue
            lo, hi = bounds["min"], bounds["max"]
            if not all(math.isfinite(v) for v in [*lo, *hi]):
                continue
            if any(all(hi[i] >= a[i] and lo[i] <= b[i] for i in range(3)) for a, b in boxes):
                hints.append({"source_sha256": provenance["content_hash"], "ifc_guid": provenance["guid"]})
                if len(hints) == 16:
                    break
    except (KeyError, ValueError, TypeError, IndexError):
        hints = []
    if not hints:
        return {"status": "NO_COUNTEREXAMPLE_FOUND", "scope": "ONE_COUNTEREXAMPLE",
                "stop_reason": "NO_OVERLAPPING_PROPOSAL_HINTS", "continue_full_check": True,
                "full_source_denominator": "NOT_RUN", "feasibility_verdict": "NOT_RUN",
                "acceptance_authority": "NONE", "probe_count": 0}
    sources = state["sources"]
    return find_forbidden_volume_witness(
        [store.resolve_path(s["immutable_path"]) for s in sources],
        store.resolve_path(material["export_path"]), sorted(guids),
        expected_source_sha256s=[s["sha256"] for s in sources],
        expected_export_sha256=material["export_sha256"],
        authoring_source_sha256=material["source_sha256"],
        # A replacement and its one unchanged original share their native
        # metre frame, even when no site/geographic anchors are available.
        coordinate_evidence=None if len(sources) == 1 else state.get("derived_artifacts", {}).get("local_coordinate_evidence"),
        obstacle_hints=hints, max_probes=16, max_seconds=15., checkpoint=control.checkpoint)
