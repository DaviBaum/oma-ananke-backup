import copy
import gzip
import json

import ifcopenshell
import ifcopenshell.geom
import numpy as np
import pytest

from oma.geometry_stream import iter_meshes
from oma.ifc.audit import sha256_file
from oma.routing.opening import materialize_route, edit_record
from oma.service import EngineService
from oma.store import IntegrityError
from test_ifc_openings import host_fixture, opening_request


def opening_projection_fixture(tmp_path, *, millimeters=False, rotated=False):
    service = EngineService(tmp_path / "engine")
    source, guid = host_fixture(tmp_path / "source.ifc", millimeters=millimeters, rotated=rotated)
    model = ifcopenshell.open(str(source))
    host = model.by_guid(guid)
    neighbor = model.create_entity("IfcWall", GlobalId=ifcopenshell.guid.new(), Name="Unchanged neighbor",
        ObjectPlacement=host.ObjectPlacement, Representation=host.Representation)
    model.write(str(source))
    request = opening_request(source, guid)
    source_hash = sha256_file(source)
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    original_meshes, entities = [], []
    for element in (host, neighbor):
        shape = ifcopenshell.geom.create_shape(settings, element)
        vertices = list(shape.geometry.verts)
        points = np.asarray(vertices).reshape(-1, 3)
        identity = f"{source_hash}:{element.id()}"
        original_meshes.append({"entity_id": identity, "vertices": vertices, "faces": list(shape.geometry.faces)})
        entities.append({"id": identity, "name": element.Name, "ifc_type": element.is_a(),
            "provenance": {"source_id": source_hash, "content_hash": source_hash, "step_id": element.id(), "guid": element.GlobalId},
            "geometry": {"status": "represented", "representation": "ifc_brep", "bounds": {"min": points.min(axis=0).tolist(), "max": points.max(axis=0).tolist()}},
            "properties": {"source_fact": "preserve verbatim"}})
    path = tmp_path / "original.mesh.json.gz"
    with gzip.open(path, "wt") as stream:
        json.dump({"meshes": original_meshes}, stream)
    matrix = [[0, -1, 0, 20], [1, 0, 0, 30], [0, 0, 1, 40], [0, 0, 0, 1]]
    baseline = {"entities": entities, "sources": [{"id": source_hash, "sha256": source_hash,
        "name": source.name, "immutable_path": str(source), "discipline": "arc", "transform_m": matrix,
        "artifacts": {"mesh_json_gz": str(path)}}]}
    project = service.store.create_project("opening projection", baseline)
    baseline = service.store.get(project["state_root"])
    context = {"request": request, "host_entity_id": entities[0]["id"], "source_id": source_hash}
    spec = {"route_id": "route-through-opening", "system_type": "PRESSURE_PIPE",
        "points_m": [[21, 30, 41.5], [19, 30, 41.5]], "diameter_m": .1, "source_to_federation_matrix": matrix}
    materialized = materialize_route(source, tmp_path / "combined.ifc", spec, context)
    artifact = service.store.put(materialized)
    service.store.put(materialized["authorized_opening"])
    state = copy.deepcopy(baseline)
    state["routes"] = [{"id": "route-through-opening", "service": "PRESSURE_PIPE", "geometry_artifact": artifact,
        "points_m": spec["points_m"], "section": {"diameter_m": .1}, "demand_ids": ["explicit-demand"], "port_ids": []}]
    state["derived_artifacts"] = {"opening_edit": edit_record(context, materialized["authorized_opening"], project["state_root"])}
    run = service.store.create_run(project["id"], {"operation": "route"})
    candidate = service.store.add_candidate(run["id"], state, {"kind": "physical_route", "changed_ids": [entities[0]["id"], "route-through-opening"]})
    return service, project, candidate, state, original_meshes, path


def mesh_volume(mesh):
    points = np.asarray(mesh["vertices"]).reshape(-1, 3)
    triangles = points[np.asarray(mesh["faces"]).reshape(-1, 3)]
    return abs(np.einsum("ij,ij->i", triangles[:, 0], np.cross(triangles[:, 1], triangles[:, 2])).sum() / 6)


@pytest.mark.parametrize("millimeters,rotated", [(False, False), (True, True)])
def test_effective_host_has_actual_cut_preserves_identity_neighbor_and_history(tmp_path, millimeters, rotated):
    service, project, candidate, state, original, _ = opening_projection_fixture(tmp_path, millimeters=millimeters, rotated=rotated)
    selected = service.selected_project(project["id"], candidate_id=candidate["id"])
    streamed = list(iter_meshes(service.store, state))
    legacy = service.geometry_at(selected)["meshes"]
    assert streamed == legacy
    host_id, neighbor_id = [m["entity_id"] for m in original]
    edited_host = [m for m in streamed if m["entity_id"] == host_id]
    assert len(edited_host) == 1
    assert mesh_volume(original[0]) == pytest.approx(4.8)
    assert mesh_volume(edited_host[0]) == pytest.approx(4.4)
    assert edited_host[0]["effective_geometry"] == "AUTHORIZED_OPENING"
    before = service.geometry(project["id"], revision=0)["meshes"]
    assert next(m for m in streamed if m["entity_id"] == neighbor_id) == next(m for m in before if m["entity_id"] == neighbor_id)
    assert mesh_volume(next(m for m in before if m["entity_id"] == host_id)) == pytest.approx(4.8)
    snapshot = service.snapshot(project["id"], candidate_id=candidate["id"])
    host = next(e for e in snapshot["entities"] if e["id"] == host_id)
    assert host["geometry"] == state["entities"][0]["geometry"]
    assert host["provenance"] == state["entities"][0]["provenance"]
    assert host["properties"] == {"source_fact": "preserve verbatim"}
    assert host["effective_geometry"] == snapshot["opening_edit"]
    assert snapshot["opening_edit"]["effective_source_file"] == "combined.ifc"
    assert service.snapshot(project["id"], revision=0)["opening_edit"] is None


@pytest.mark.parametrize("fault", ["missing_original", "duplicate_original", "host_identity", "original_facts", "datum", "manifest", "native_bytes"])
def test_host_replacement_fails_closed_for_wrong_or_incomplete_binding(tmp_path, fault):
    service, project, candidate, state, original, path = opening_projection_fixture(tmp_path)
    edit = state["derived_artifacts"]["opening_edit"]
    if fault in {"missing_original", "duplicate_original"}:
        with gzip.open(path, "wt") as stream:
            json.dump({"meshes": original[1:] if fault == "missing_original" else original + [original[0]]}, stream)
    elif fault == "host_identity": edit["host_entity_id"] = original[1]["entity_id"]
    elif fault == "original_facts": state["entities"][0]["properties"]["source_fact"] = "changed"
    elif fault == "datum": state["sources"][0].pop("transform_m")
    elif fault == "manifest": edit["request"]["permission"]["statement"] = "unbound changed permission"
    else: (tmp_path / "combined.ifc").write_text("tampered bytes", encoding="utf-8")
    with pytest.raises(IntegrityError):
        list(iter_meshes(service.store, state))
