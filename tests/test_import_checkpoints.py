"""Cancellation leaves the last committed project intact during late import work."""
import pytest

from oma.normalization import normalize_connectivity
from oma.store import Store
from oma.worker import Cancelled, WorkerControl, import_sources
from test_ifc_pipeline import make_fixture


@pytest.mark.parametrize("stop_stage", ["federation_source", "federation_source_parsed",
    "federation_entity_batch", "connectivity_ownership_source", "connectivity_source",
    "import_state_serialization", "import_publish"])
def test_cancel_during_late_import_never_publishes_partial_inventory(tmp_path, stop_stage):
    source = make_fixture(tmp_path / "source.ifc")
    store = Store(tmp_path / "store")
    project = store.create_project("Cancellation", {})
    run = store.create_run(project["id"], {"operation": "import", "paths": [str(source)]})
    before = store.project(project["id"])

    class CancelAt(WorkerControl):
        def checkpoint(self, stage="compute"):
            if stage == stop_stage:
                store.control(run["id"], "cancel")
            super().checkpoint(stage)

    with pytest.raises(Cancelled):
        import_sources(store, run, CancelAt(store, run["id"]))
    after = store.project(project["id"])
    assert after["state_root"] == before["state_root"]
    assert after["revision"] == before["revision"]
    assert len(store.history(project["id"])) == 1


def test_completed_import_exposes_real_stage_denominators(tmp_path):
    source = make_fixture(tmp_path / "source.ifc")
    store = Store(tmp_path / "store")
    project = store.create_project("Progress", {})
    run = store.create_run(project["id"], {"operation": "import", "paths": [str(source)]})
    import_sources(store, run, WorkerControl(store, run["id"]))
    events = store.events(project["id"], limit=1000)
    stages = [e["stage"] for e in events]
    assert stages.index("federation") < stages.index("connectivity_ownership") < stages.index("connectivity") < stages.index("import_state")
    state = store.get(store.project(project["id"])["state_root"])
    payload = next(e["payload"] for e in events if e["stage"] == "import_state")
    assert payload["source_count"] == len(state["sources"])
    assert payload["entity_count"] == len(state["entities"])
    assert payload["port_count"] == len(state["ports"])
    assert store.run(run["id"])["status"] == "COMPLETED"


@pytest.mark.parametrize("cancel_stage", ["connectivity_port_batch", "connectivity_connection_batch"])
def test_normalization_can_cancel_inside_large_source_without_suppressing_signal(cancel_stage):
    audit = {"source_sha256": "source", "ports": [{"step_id": i, "owner_step_ids": [2000]} for i in range(1025)],
             "explicit_connections": [{"port_a_step_id": 0, "port_b_step_id": 1} for _ in range(1025)]}
    calls = []

    def stop(stage):
        calls.append(stage)
        if calls.count(cancel_stage) == 2:
            raise Cancelled()

    with pytest.raises(Cancelled):
        normalize_connectivity([audit], [{"id": "source"}], checkpoint=stop)
    assert calls.count(cancel_stage) == 2
