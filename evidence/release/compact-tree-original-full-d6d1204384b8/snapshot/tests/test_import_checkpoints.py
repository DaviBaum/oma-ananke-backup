"""Cancellation leaves the last committed project intact during late import work."""
import pytest

from oma.normalization import normalize_connectivity
from oma.store import Store
from oma.worker import Cancelled, WorkerControl, import_sources
from test_ifc_pipeline import make_fixture


@pytest.mark.parametrize("stop_stage", ["import_inventory_refresh", "inventory_source_parsed", "inventory_source_derived", "import_inventory_refreshed", "federation_source", "federation_source_parsed",
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


def test_cached_import_refreshes_inventory_and_persists_actual_port_audit(tmp_path):
    import json
    import ifcopenshell
    from oma.ifc.audit import audit_file, sha256_file
    source = make_fixture(tmp_path / "source.ifc")
    model = ifcopenshell.open(str(source))
    parent = model.create_entity("IfcElementAssembly", GlobalId=ifcopenshell.guid.new())
    space = model.create_entity("IfcSpace", GlobalId=ifcopenshell.guid.new())
    model.create_entity("IfcRelAggregates", GlobalId=ifcopenshell.guid.new(), RelatingObject=parent, RelatedObjects=[space])
    owner = model.by_type("IfcBuildingElementProxy")[0]
    port = model.create_entity("IfcDistributionPort", GlobalId=ifcopenshell.guid.new(), FlowDirection="SOURCE")
    model.create_entity("IfcRelConnectsPortToElement", GlobalId=ifcopenshell.guid.new(), RelatingPort=port, RelatedElement=owner)
    parent_id, port_id, owner_id = parent.id(), port.id(), owner.id()
    model.write(str(source))
    store = Store(tmp_path / "store")
    out = store.directory / "geometry" / sha256_file(source)
    audit = audit_file(source, out, geometry=True, mesh=True)
    # Recreate a historical cache: a nonphysical child used to hide its parent,
    # and earlier port audits lack current ownership/flow-axis fields.
    record = next(p for p in audit["products"] if p["step_id"] == parent_id)
    record["geometry_status"] = "explicitly_non_geometric"
    audit.pop("physical_inventory", None)
    audit.pop("inventory_refresh", None)
    audit["source_path"] = str(tmp_path / "unavailable-prior-location.ifc")
    for p in audit["ports"]:
        for field in ("owner_step_ids", "owner_placement_status", "axis_convention"):
            p.pop(field, None)
    cached = next(out.glob("*.audit.json"))
    cached.write_text(json.dumps(audit), encoding="utf-8")
    original_cache = cached.read_bytes()
    project = store.create_project("Legacy source evidence", {})
    run = store.create_run(project["id"], {"operation": "import", "paths": [str(source)]})
    import_sources(store, run, WorkerControl(store, run["id"]))
    state = store.get(store.project(project["id"])["state_root"])
    imported = state["sources"][0]
    corrected = store.get(imported["audit_root"])
    assert corrected["source_path"] == imported["immutable_path"]
    assert next(e for e in state["entities"] if e["provenance"]["step_id"] == parent_id)["geometry"]["status"] == "unresolved"
    assert any(b["code"] == "INCOMPLETE_PHYSICAL_GEOMETRY" for b in imported["blockers"])
    assert next(p for p in corrected["ports"] if p["step_id"] == port_id)["owner_step_ids"] == [owner_id]
    assert corrected["ownership_normalization"]["method"] == "fresh_explicit_IFC_relationships_and_flow_axes/2"
    assert state["derived_artifacts"]["source_port_audits"][imported["id"]] == imported["audit_root"]
    assert corrected["inventory_refresh"]["changed_dispositions"][0]["step_id"] == parent_id
    assert cached.read_bytes() == original_cache


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
