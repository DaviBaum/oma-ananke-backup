from fastapi.testclient import TestClient

from oma.api import create_app
from oma.worker import WorkerControl, import_sources
from test_ifc_openings import host_fixture


def test_native_inspection_is_read_only_identity_bound_and_project_scoped(tmp_path):
    path, guid = host_fixture(tmp_path / "source.ifc")
    app = create_app(tmp_path / "store", recover=False)
    store = app.state.engine.store
    project = store.create_project("Inspect host", {})
    imp = store.create_run(project["id"], {"operation": "import", "paths": [str(path)]})
    import_sources(store, imp, WorkerControl(store, imp["id"]))
    head = store.project(project["id"])
    state = store.get(head["state_root"])
    entity = next(e for e in state["entities"] if e["provenance"]["guid"] == guid)
    other = store.create_project("Other", {})
    url = f"/api/projects/{project['id']}/opening-host"
    with TestClient(app) as client:
        response = client.get(url, params={"entity_id": entity["id"]})
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["status"] == "ELIGIBLE"
        assert payload["host"]["host_guid"] == guid
        assert payload["state_root"] == head["state_root"]
        assert payload["opening_permission"] == "NOT_INFERRED"
        assert payload["requires_explicit_permission"]
        assert store.project(project["id"])["state_root"] == head["state_root"]
        assert store.project(project["id"])["revision"] == 1
        assert client.get(url, params={"entity_id": "unknown"}).status_code == 422
        assert client.get(f"/api/projects/{other['id']}/opening-host", params={"entity_id": entity["id"]}).status_code == 422
        assert client.get(url, params={"entity_id": entity["id"], "revision": 0}).status_code == 422
