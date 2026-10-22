from fastapi.testclient import TestClient

from oma.api import create_app


def test_loopback_api_rejects_external_origins_and_invalid_imports(tmp_path):
    app = create_app(tmp_path / "engine")
    with TestClient(app) as client:
        assert client.get("/api/projects").json() == []
        assert client.get("/api/projects", headers={"Origin": "https://attacker.example"}).status_code == 403
        assert client.get("/api/projects", headers={"Host": "attacker.example"}).status_code == 400
        assert client.post("/api/projects/import", json={"paths": [], "name": "test"}).status_code == 422
        fake = tmp_path / "fake.ifc"
        fake.write_text("<html>Download error</html>")
        assert client.post("/api/projects/import", json={"paths": [str(fake)], "name": "test"}).status_code == 422
        assert client.get("/api/projects").json() == []


def test_snapshot_events_and_revert_are_real_revision_data(tmp_path):
    app = create_app(tmp_path / "engine")
    store = app.state.engine.store
    p = store.create_project("test", {"entities": [], "sources": []})
    store.publish(p["id"], {"project_id": p["id"], "entities": [], "sources": [], "assumptions": ["test"]}, 0, "edit")
    with TestClient(app) as client:
        snap = client.get(f"/api/projects/{p['id']}/snapshot").json()
        assert snap["project"]["revision"] == 1
        assert len(snap["history"]) == 2
        events = client.get(f"/api/projects/{p['id']}/events?after=1").json()
        assert len(events) == 1 and events[0]["payload"]["revision"] == 1
        body = {"revision": 0, "expected_revision": 1, "idempotency_key": "undo"}
        assert client.post(f"/api/projects/{p['id']}/revert", json=body).json()["revision"] == 2
        assert client.post(f"/api/projects/{p['id']}/revert", json=body).json()["revision"] == 2
        body["idempotency_key"] = "stale"
        assert client.post(f"/api/projects/{p['id']}/revert", json=body).status_code == 409
        assert client.post(f"/api/projects/{p['id']}/export", json={"draft": False}).status_code == 422


def test_candidate_recheck_is_project_bound_and_idempotent(tmp_path):
    app = create_app(tmp_path / "engine")
    service = app.state.engine
    service.schedule = lambda run_id: None
    project = service.store.create_project("first", {})
    other = service.store.create_project("other", {})
    old = service.store.create_run(project["id"], {"operation": "check"})
    candidate = service.store.add_candidate(old["id"], service.store.get(old["base_root"]), {"kind": "baseline_check"})
    with TestClient(app) as client:
        body = {"budget_seconds": 60, "idempotency_key": "fresh-1"}
        url = f"/api/projects/{project['id']}/candidates/{candidate['id']}/recheck"
        one = client.post(url, json=body)
        assert one.status_code == 202
        assert one.json()["request"]["candidate_id"] == candidate["id"]
        assert client.post(url, json=body).json()["id"] == one.json()["id"]
        assert client.post(f"/api/projects/{other['id']}/candidates/{candidate['id']}/recheck", json=body).status_code == 422
