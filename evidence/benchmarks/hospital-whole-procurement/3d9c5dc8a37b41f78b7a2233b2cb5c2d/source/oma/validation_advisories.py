"""Known engineering defects remain visible alongside immutable old reports."""
from __future__ import annotations


def candidate_advisories(store, candidate, state=None):
    if candidate.get("kind") not in {"physical_route", "physical_route_set", "physical_network"}:
        return []
    state = state if state is not None else store.get(candidate["state_root"])
    affected = []
    for route in [*state.get("routes", []), *state.get("physical_networks", [])]:
        artifact = route.get("geometry_artifact")
        manifest = store.get(artifact) if artifact else {}
        if manifest.get("port_axis_convention") != "IFC_FLOW_AXIS_V1":
            affected.append(route["id"])
    if not affected:
        return []
    return [{"id": "IFC-PORT-001", "status": "REGENERATION_AND_FRESH_CHECK_REQUIRED", "route_ids": affected,
        "claim": "Prior application-authored IFC port-semantic checks are superseded",
        "reason": "The earlier exporter used physical outward normals for SINK axes, absolute port placements and reversed sink connection ordering. IFC distribution-port placement and flow semantics require a coordinated correction.",
        "source": "https://standards.buildingsmart.org/documents/Implementation/IFC_Implementation_Agreements/CV-2x3-176.html",
        "scope": "Application-authored route port semantics; original reports and source bytes remain immutable",
        "resolution_contract": "Regenerate with the corrected convention and independently check native axes, ownership, placement, connectivity and physical cap attachment; a manifest marker alone is not a certificate"}]
