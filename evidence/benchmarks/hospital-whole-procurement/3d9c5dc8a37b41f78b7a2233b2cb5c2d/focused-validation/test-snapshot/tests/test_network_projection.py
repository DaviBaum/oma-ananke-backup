import copy
import gzip
import json
from pathlib import Path

import numpy as np
import pytest

from oma.geometry_stream import compressed_stream, iter_network_meshes
from oma.ifc.network import export_network
from oma.service import EngineService
from oma.store import IntegrityError
from test_ifc_pipeline import make_fixture


def create_network(service, tmp_path):
    source = make_fixture(tmp_path / "source.ifc", millimeters=True)
    spec = json.loads(Path("docs/ifc-network-spec.json").read_text(encoding="utf-8"))
    # Export in a translated, rotated source frame; the display must restore
    # exactly the declared world coordinates, without recentering this file.
    spec["source_to_federation_matrix"] = [[0, -1, 0, 20], [1, 0, 0, 30], [0, 0, 1, 40], [0, 0, 0, 1]]
    manifest = export_network(source, tmp_path / "network.ifc", spec)
    artifact = service.store.put(manifest)
    network = {"id": "network-record", "demand_ids": ["demand-a", "demand-b"],
               "component_ids": [c["id"] for c in spec["components"]], "port_ids": [],
               "service": "PRESSURE_PIPE", "section": {"diameter_m": .1, "insulation_m": .02},
               "geometry_artifact": artifact, "status": "CANDIDATE"}
    return {"entities": [], "sources": [], "routes": [], "physical_networks": [network]}, manifest


def test_native_network_projection_is_unique_world_meter_and_candidate_bound(tmp_path):
    service = EngineService(tmp_path / "engine")
    state, manifest = create_network(service, tmp_path)
    project = service.store.create_project("projection", {"entities": [], "sources": []})
    run = service.store.create_run(project["id"], {"operation": "route"})
    state["project_id"] = project["id"]
    candidate = service.store.add_candidate(run["id"], state, {"kind": "physical_network"})
    snapshot = service.snapshot(project["id"], candidate_id=candidate["id"])
    assert len(snapshot["entities"]) == 4
    trunk = next(e for e in snapshot["entities"] if e["component_id"] == "trunk")
    assert trunk["demand_ids"] == ["demand-a", "demand-b"]
    assert trunk["properties"]["shared_component"] is True
    assert trunk["step_id"] == manifest["added_parts"][0]["step_id"]
    assert trunk["source_file"] == "network.ifc"
    assert len(snapshot["candidates"][0]["networks"][0]["network_spec"]["components"]) == 4
    assert service.snapshot(project["id"])["networks"] == []
    selected = snapshot["project"]
    records = [json.loads(line) for line in gzip.decompress(b"".join(compressed_stream(service.store, selected))).splitlines()]
    meshes = records[1:-1]
    assert records[-1]["mesh_count"] == len(meshes) == 4
    assert {m["entity_id"] for m in meshes} == {e["id"] for e in snapshot["entities"]}
    assert records[0]["state_root"] == records[-1]["state_root"] == candidate["state_root"]
    trunk_mesh = next(m for m in meshes if m["entity_id"] == trunk["id"])
    points = np.asarray(trunk_mesh["vertices"]).reshape(-1, 3)
    assert points[:, 0].min() == pytest.approx(-1)
    assert points[:, 0].max() == pytest.approx(-.2)
    assert points[:, 1].mean() == pytest.approx(4, abs=.003)
    assert points[:, 2].mean() == pytest.approx(3, abs=.003)
    assert all(len(m["faces"]) > 0 for m in meshes)
    legacy = service.geometry_at(selected)
    assert legacy["meshes"] == [{k: v for k, v in mesh.items() if k != "type"} for mesh in meshes]
    assert all(len(m["faces"]) % 3 == 0 for m in legacy["meshes"])


@pytest.mark.parametrize("damage", ["duplicate", "missing", "missing_datum"])
def test_display_rejects_ambiguous_network_manifest(tmp_path, damage):
    service = EngineService(tmp_path / "engine")
    state, manifest = create_network(service, tmp_path)
    manifest = copy.deepcopy(manifest)
    if damage == "duplicate":
        manifest["added_parts"].append(manifest["added_parts"][0])
    elif damage == "missing":
        manifest["added_parts"].pop()
    else:
        manifest["network_spec"].pop("source_to_federation_matrix")
    state["physical_networks"][0]["geometry_artifact"] = service.store.put(manifest)
    with pytest.raises(IntegrityError):
        list(iter_network_meshes(service.store, state))


def test_network_revision_projects_exact_contract_and_previous_graph_without_old_meshes(tmp_path):
    service = EngineService(tmp_path / "engine")
    state, manifest = create_network(service, tmp_path)
    previous = copy.deepcopy(manifest)
    previous["network_spec"]["network_id"] = "old-network"
    previous_root = service.store.put(previous)
    contract = {"scenario": {"mission_type": "shared_network", "preserved": {"flow": .003}},
        "selected_alternative": "network-record", "source_id": "source",
        "revision": {"base_root": "prior-state", "replaced_network_id": "old-network",
            "previous_component_ids": [f"old-network:{c['id']}" for c in previous["network_spec"]["components"]],
            "previous_geometry_artifact": previous_root, "previous_network_root": "old-record",
            "previous_contract_root": "old-contract", "fixed_requirements_root": "fixed"}}
    state["derived_artifacts"] = {"network_contract": contract}
    view = service.network_views(state)[0]
    assert view["network_contract"] == contract
    assert view["previous_network"]["network_spec"] == previous["network_spec"]
    assert view["previous_network"]["geometry_artifact"] == previous_root
    meshes = list(iter_network_meshes(service.store, state))
    assert len(meshes) == 4
    assert all(m["entity_id"].startswith("network-record:") for m in meshes)
    # A contract for a different component tree must not offer revision inputs.
    contract["selected_alternative"] = "unrelated"
    view = service.network_views(state)[0]
    assert "network_contract" not in view and "previous_network" not in view
