"""Bind displayed effective support to one explicitly versioned native host edit."""
from pathlib import Path

from .store import IntegrityError, digest


def opening_binding(store, state):
    edit = state.get("derived_artifacts", {}).get("opening_edit")
    if edit is None:
        return None
    request = edit["request"]
    identity = edit["host_entity_id"]
    sources = [s for s in state.get("sources", []) if s["id"] == edit["source_id"]]
    entities = [e for e in state.get("entities", []) if e["id"] == identity]
    if len(sources) != 1 or len(entities) != 1:
        raise IntegrityError("Opening display requires exactly one original host and source")
    source, entity = sources[0], entities[0]
    provenance = entity["provenance"]
    if (identity != f"{source['id']}:{request['host_step_id']}"
            or source["sha256"] != request["source_sha256"]
            or provenance.get("source_id") != source["id"]
            or provenance.get("content_hash") != source["sha256"]
            or provenance.get("step_id") != request["host_step_id"]
            or provenance.get("guid") != request["host_guid"]):
        raise IntegrityError("Opening display source, host GUID and STEP identity disagree")
    baseline = store.get(edit["base_root"])
    original = [e for e in baseline.get("entities", []) if e["id"] == identity]
    if baseline.get("project_id") != state.get("project_id") or original != [entity]:
        raise IntegrityError("Opening display must preserve the bound original host facts")
    manifest = store.get(edit["manifest_root"])
    if (manifest.get("request") != request or manifest.get("source_sha256") != source["sha256"]
            or manifest.get("host", {}).get("host_geometry_root") != request["host_geometry_root"]):
        raise IntegrityError("Opening display manifest does not match its permission and original support")
    matches = []
    for route in state.get("routes", []):
        if not route.get("geometry_artifact"):
            continue
        materialized = store.get(route["geometry_artifact"])
        authored = materialized.get("authorized_opening")
        if authored is not None and digest(authored) == edit["manifest_root"]:
            matches.append((route, materialized))
    if len(matches) != 1:
        raise IntegrityError("Opening display requires one final materialized IFC containing the bound edit")
    route, materialized = matches[0]
    matrix = materialized.get("route_spec", {}).get("source_to_federation_matrix")
    if (matrix is None or matrix != source.get("transform_m")
            or materialized.get("source_sha256") != source["sha256"]):
        raise IntegrityError("Opening display requires the pinned original source and federation datum")
    return {"edit": edit, "source": source, "entity": entity, "route": route,
            "materialized": materialized, "manifest": manifest, "matrix": matrix}


def opening_view(store, state):
    binding = opening_binding(store, state)
    if binding is None:
        return None
    return {**binding["edit"], "geometry_artifact": binding["route"]["geometry_artifact"],
            "original_source_file": binding["source"].get("name"),
            "effective_source_file": Path(binding["materialized"]["export_path"]).name,
            "effective_export_sha256": binding["materialized"]["export_sha256"],
            "display_policy": "EXACT_SELECTED_HOST_REPLACEMENT_FROM_MATERIALIZED_IFC",
            "original_entity_facts_preserved": True,
            "manifest_scope": binding["manifest"].get("scope")}


def effective_host_mesh(store, binding):
    """Tessellate the final IFC host, including its real IfcRelVoidsElement cut."""
    import ifcopenshell
    import ifcopenshell.geom
    from .ifc.audit import sha256_file
    from .ifc.federation import transform_mesh_payload
    materialized = binding["materialized"]
    path = store.resolve_path(materialized["export_path"])
    if sha256_file(path) != materialized["export_sha256"]:
        raise IntegrityError("Opening display final IFC bytes changed")
    model = ifcopenshell.open(str(path))
    request = binding["edit"]["request"]
    host = model.by_guid(request["host_guid"])
    if host.id() != request["host_step_id"]:
        raise IntegrityError("Opening display final host STEP identity changed")
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    shape = ifcopenshell.geom.create_shape(settings, host)
    mesh = {"entity_id": binding["edit"]["host_entity_id"],
            "vertices": list(shape.geometry.verts), "faces": list(shape.geometry.faces),
            "discipline": binding["source"].get("discipline", "unclassified"),
            "effective_geometry": "AUTHORIZED_OPENING", "opening_manifest_root": binding["edit"]["manifest_root"]}
    if not mesh["vertices"] or not mesh["faces"]:
        raise IntegrityError("Opening display host produced no native effective geometry")
    if sha256_file(path) != materialized["export_sha256"]:
        raise IntegrityError("Opening display IFC changed during native tessellation")
    return transform_mesh_payload({"meshes": [mesh]}, binding["matrix"])["meshes"][0]
