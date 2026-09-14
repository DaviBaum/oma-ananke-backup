import gzip
import json

from fastapi.testclient import TestClient

from oma.api import create_app
from oma.geometry_stream import compressed_stream
from oma.store import Store


def test_stream_pins_root_transforms_real_vertices_and_requires_completion(tmp_path):
    app = create_app(tmp_path / "engine")
    store = app.state.engine.store
    path = store.directory / "source.json.gz"
    mesh = {"entity_id": "source:1", "vertices": [0, 0, 0, 1, 0, 0, 0, 1, 0], "faces": [0, 1, 2]}
    with gzip.open(path, "wt") as stream:
        json.dump({"meshes": [mesh, {**mesh, "entity_id": "source:2"}]}, stream)
    state = {"sources": [{"artifacts": {"mesh_json_gz": str(path)}, "discipline": "structural", "bounds": {"min": [2, 0, 0], "max": [3, 1, 0]},
                          "transform_m": [[1, 0, 0, 2], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]}]}
    project = store.create_project("stream", state)
    stream = compressed_stream(store, project)
    first = next(stream)
    # Edit the head while the previous geometry stream is in flight.
    store.publish(project["id"], {"project_id": project["id"], "sources": []}, 0, "change")
    records = [json.loads(line) for line in gzip.decompress(first + b"".join(stream)).splitlines()]
    assert [r["type"] for r in records] == ["header", "mesh", "mesh", "complete"]
    assert records[0]["state_root"] == records[-1]["state_root"] == project["state_root"]
    assert records[1]["vertices"] == [2, 0, 0, 3, 0, 0, 2, 1, 0]
    assert records[-1]["mesh_count"] == records[-1]["triangle_count"] == 2
    with TestClient(app) as client:
        response = client.get(f"/api/projects/{project['id']}/geometry-stream?revision=0")
        assert response.status_code == 200
        assert response.headers["x-oma-state-root"] == project["state_root"]
        assert [json.loads(line) for line in response.text.splitlines()] == records
    latest = store.project(project["id"])
    interrupted = compressed_stream(store, latest)
    next(interrupted)
    interrupted.close()
    assert not (store.directory / "geometry" / "views" / f"stream-v2-{latest['state_root']}.ndjson.gz").exists()
    assert not list((store.directory / "geometry" / "views").glob(".pending-*"))
