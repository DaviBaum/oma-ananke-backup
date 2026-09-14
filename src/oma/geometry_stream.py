"""Bounded per-mesh transport of real immutable source and route geometry."""
from __future__ import annotations

import gzip
import json
import os
import uuid
import zlib
from pathlib import Path

import ijson
import orjson

from .store import IntegrityError, Store


def iter_network_meshes(store: Store, state: dict):
    """Tessellate each authored physical part once, irrespective of demand paths."""
    from .ifc.federation import transform_mesh_payload
    for network in state.get("physical_networks", []):
        if not network.get("geometry_artifact"):
            continue
        materialized = store.get(network["geometry_artifact"])
        spec = materialized["network_spec"]
        parts = materialized["added_parts"]
        component_ids = [part["component_id"] for part in parts]
        if (len(component_ids) != len(set(component_ids))
                or set(component_ids) != {c["id"] for c in spec["components"]}
                or set(component_ids) != set(network["component_ids"])):
            raise IntegrityError("Network display requires one native part for every unique physical component")
        if len({p["ifc_guid"] for p in parts}) != len(parts):
            raise IntegrityError("Network display manifest repeats a native IFC component")
        matrix = spec.get("source_to_federation_matrix")
        if matrix is None:
            raise IntegrityError("Network display requires its pinned source-to-federation datum")
        import ifcopenshell
        import ifcopenshell.geom
        model = ifcopenshell.open(str(store.resolve_path(materialized["export_path"])))
        settings = ifcopenshell.geom.settings()
        settings.set("use-world-coords", True)
        for part in parts:
            shape = ifcopenshell.geom.create_shape(settings, model.by_guid(part["ifc_guid"]))
            mesh = {"entity_id": f"{network['id']}:{part['component_id']}",
                    "vertices": list(shape.geometry.verts), "faces": list(shape.geometry.faces),
                    "discipline": network["service"], "color": [.1, .72, .5]}
            yield transform_mesh_payload({"meshes": [mesh]}, matrix)["meshes"][0]


def bounds_of_sources(state: dict):
    bounds = [s["bounds"] for s in state.get("sources", []) if s.get("bounds")]
    if not bounds:
        return None
    return {"min": [min(b["min"][i] for b in bounds) for i in range(3)],
            "max": [max(b["max"][i] for b in bounds) for i in range(3)]}


def iter_meshes(store: Store, state: dict):
    from .ifc.federation import transform_mesh_payload
    for source in state.get("sources", []):
        path = source.get("artifacts", {}).get("mesh_json_gz")
        if not path:
            continue
        with gzip.open(store.resolve_path(path), "rb") as stream:
            for mesh in ijson.items(stream, "meshes.item", use_float=True):
                mesh["discipline"] = source.get("discipline", "unclassified")
                if source.get("transform_m"):
                    mesh = transform_mesh_payload({"meshes": [mesh]}, source["transform_m"])["meshes"][0]
                yield mesh
    for route in state.get("routes", []):
        if not route.get("geometry_artifact"):
            continue
        materialized = store.get(route["geometry_artifact"])
        cache = store.directory / "geometry" / "routes" / f"{route['geometry_artifact']}.json.gz"
        if cache.exists():
            with gzip.open(cache, "rb") as stream:
                yield from ijson.items(stream, "item", use_float=True)
            continue
        import ifcopenshell
        import ifcopenshell.geom
        model = ifcopenshell.open(str(store.resolve_path(materialized["export_path"])))
        settings = ifcopenshell.geom.settings()
        settings.set("use-world-coords", True)
        for part in materialized["added_parts"]:
            shape = ifcopenshell.geom.create_shape(settings, model.by_guid(part["ifc_guid"]))
            mesh = {"entity_id": route["id"], "vertices": list(shape.geometry.verts), "faces": list(shape.geometry.faces),
                    "discipline": route["service"], "color": [.1, .72, .5]}
            matrix = materialized.get("route_spec", {}).get("source_to_federation_matrix")
            if matrix:
                mesh = transform_mesh_payload({"meshes": [mesh]}, matrix)["meshes"][0]
            yield mesh

    yield from iter_network_meshes(store, state)


def records(store: Store, project: dict):
    state = store.get(project["state_root"])
    yield {"type": "header", "project_id": project["id"], "state_root": project["state_root"],
           "units": "m", "coordinate_system": "world", "bounds": bounds_of_sources(state),
           "source_count": len(state.get("sources", []))}
    count, triangles = 0, 0
    for mesh in iter_meshes(store, state):
        count += 1
        triangles += len(mesh["faces"]) // 3
        yield {**mesh, "type": "mesh"}
    yield {"type": "complete", "state_root": project["state_root"], "mesh_count": count, "triangle_count": triangles}


def compressed_stream(store: Store, project: dict):
    """Stream gzip as produced; commit reusable cache only after full completion."""
    directory = store.directory / "geometry" / "views"
    cache = directory / f"stream-v2-{project['state_root']}.ndjson.gz"
    if cache.exists():
        with cache.open("rb") as stream:
            yield from iter(lambda: stream.read(512 * 1024), b"")
        return
    directory.mkdir(parents=True, exist_ok=True)
    pending = directory / f".pending-{uuid.uuid4().hex}"
    encoder = zlib.compressobj(level=2, wbits=31)
    finished = False
    try:
        with pending.open("wb") as output:
            for i, record in enumerate(records(store, project)):
                data = encoder.compress(orjson.dumps(record) + b"\n")
                if i % 16 == 0:
                    data += encoder.flush(zlib.Z_SYNC_FLUSH)
                if data:
                    output.write(data)
                    yield data
            data = encoder.flush()
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
            yield data
            finished = True
        os.replace(pending, cache)
    finally:
        if not finished and pending.exists():
            pending.unlink()
