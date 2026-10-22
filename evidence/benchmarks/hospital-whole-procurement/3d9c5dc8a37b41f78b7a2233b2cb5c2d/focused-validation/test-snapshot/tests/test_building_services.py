"""Whole-project job binding and publication; no clinical/design approval fixtures."""
import copy
import hashlib
import json

import pytest

from oma.building_services import SCHEMA, design_services_run
from oma.store import IntegrityError, Store, digest
from oma.worker import Cancelled


class Control:
    def checkpoint(self, stage):
        pass


def project(tmp_path):
    store = Store(tmp_path / "store")
    sources = []
    for name in ("mechanical", "electrical"):
        import ifcopenshell
        path = tmp_path / (name + ".ifc")
        model = ifcopenshell.file(schema="IFC4")
        product = model.create_entity("IfcPipeSegment" if name == "mechanical" else "IfcCableSegment", GlobalId=ifcopenshell.guid.new())
        model.write(path)
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        audit = {"audit_version": "oma-ifc-audit/1", "schema": "IFC4", "source_sha256": sha, "products": [{"step_id": product.id(), "type": product.is_a(),
                 "physical": True, "ifc_guid": product.GlobalId, "system_ids": []}], "ports": [], "explicit_connections": [], "systems": []}
        sources.append({"id": sha, "sha256": sha, "name": name + ".ifc", "immutable_path": str(path), "audit_root": store.put(audit)})
    state = {"sources": sources, "entities": [], "derived_artifacts": {"local_coordinate_evidence": {"status": "UNRESOLVED"}}}
    p = store.create_project("whole project", state)
    state["project_id"] = p["id"]
    return store, p, state


def request(state, **mission):
    return {"operation": "design_services", "budget_seconds": 30, "mission": {"schema": SCHEMA,
        "source_disciplines": {state["sources"][0]["id"]: "HVAC", state["sources"][1]["id"]: "ELECTRICAL"}, **mission}}


def test_every_source_and_portless_service_remains_in_denominator(tmp_path):
    store, p, state = project(tmp_path)
    run = store.create_run(p["id"], request(state))
    before = store.project(p["id"])
    report = design_services_run(store, run, Control())
    assert report["summary"]["source_count"] == 2
    assert report["summary"]["network_count"] == 2
    assert report["summary"]["network_status_counts"] == {"MISSING_DESIGN_CONTRACT": 2}
    assert report["federation"] == "UNRESOLVED"
    assert not report["whole_building_optimized"] and not report["construction_approval"]
    assert store.project(p["id"]) == before
    assert store.candidates(p["id"]) == []
    assert store.run(run["id"])["status"] == "MISSING_INPUTS"


@pytest.mark.parametrize("attack", ["source_bytes", "audit_source", "scope", "unknown_label", "absent_network"])
def test_bad_source_binding_or_restricted_denominator_rejected(tmp_path, attack):
    store, p, state = project(tmp_path)
    req = request(state)
    if attack == "source_bytes":
        from pathlib import Path
        Path(state["sources"][0]["immutable_path"]).write_text("changed")
    elif attack == "audit_source":
        a = store.get(state["sources"][0]["audit_root"])
        a["source_sha256"] = "0" * 64
        state["sources"][0]["audit_root"] = store.put(a)
        store.publish(p["id"], state, 0, "bad audit")
    elif attack == "scope":
        req["scope"] = [state["sources"][0]["id"]]
    elif attack == "unknown_label":
        req["mission"]["source_disciplines"] = {"0" * 64: "HVAC"}
    elif attack == "absent_network":
        req["mission"]["contracts"] = [{"network_id": "not-installed", "network_root": "0" * 64,
            "source_sha256": "0" * 64, "service": "PRESSURE_PIPE", "options": [], "requirements": {}, "catalogue_complete": True}]
    run = store.create_run(p["id"], req)
    with pytest.raises((ValueError, IntegrityError)):
        design_services_run(store, run, Control())
    assert store.run(run["id"])["status"] != "COMPLETED"
    assert store.candidates(p["id"]) == []


def test_cancellation_has_no_complete_report_or_candidate(tmp_path):
    store, p, state = project(tmp_path)
    run = store.create_run(p["id"], request(state))
    class Cancel:
        def checkpoint(self, stage):
            if stage == "service_network_design":
                raise Cancelled()
    with pytest.raises(Cancelled):
        design_services_run(store, run, Cancel())
    assert store.candidates(p["id"]) == []
    assert store.project(p["id"])["revision"] == 0


def test_run_mutation_before_publish_is_detected(tmp_path):
    store, p, state = project(tmp_path)
    run = store.create_run(p["id"], request(state))
    class Mutate:
        def checkpoint(self, stage):
            if stage == "service_design_publish":
                bad = copy.deepcopy(run["request"])
                bad["seed"] = 999
                with store.transaction() as db:
                    db.execute("UPDATE runs SET request=? WHERE id=?", (json.dumps(bad), run["id"]))
    with pytest.raises(IntegrityError, match="request changed"):
        design_services_run(store, run, Mutate())
    assert store.run(run["id"])["status"] != "COMPLETED"


def test_stale_network_contract_cannot_screen_a_different_network(tmp_path):
    store, p, state = project(tmp_path)
    initial = design_services_run(store, store.create_run(p["id"], request(state)), Control())
    network = initial["networks"][0]
    contract = {k: network[k] for k in ("network_id", "network_root", "source_sha256")}
    contract.update(network_root="0" * 64, service="PRESSURE_PIPE", options=[], requirements={}, catalogue_complete=True)
    run = store.create_run(p["id"], request(state, contracts=[contract]))
    with pytest.raises(IntegrityError, match="stale"):
        design_services_run(store, run, Control())


def test_final_control_callback_cannot_invalidate_source_byte_fence(tmp_path):
    from pathlib import Path
    store, p, state = project(tmp_path)
    run = store.create_run(p["id"], request(state))
    class Mutate:
        def checkpoint(self, stage):
            if stage == "service_design_complete":
                Path(state["sources"][0]["immutable_path"]).write_text("changed after callbacks")
    with pytest.raises(IntegrityError, match="Original IFC changed"):
        design_services_run(store, run, Mutate())
    assert store.run(run["id"])["status"] not in {"COMPLETED", "MISSING_INPUTS"}


def test_changed_audit_facts_invalidate_prior_contract_even_with_same_source_sha(tmp_path):
    store, p, state = project(tmp_path)
    inventory = design_services_run(store, store.create_run(p["id"], request(state)), Control())
    network = inventory["networks"][0]
    contract = {k: network[k] for k in ("network_id", "network_root", "source_sha256")}
    contract.update(service="PRESSURE_PIPE", options=[], requirements={}, catalogue_complete=True)
    source = next(s for s in state["sources"] if s["sha256"] == network["source_sha256"])
    audit = store.get(source["audit_root"])
    audit["products"][0]["properties"] = {"corrected_material_information": {"grade": "different"}}
    source["audit_root"] = store.put(audit)
    store.publish(p["id"], state, 0, "corrected audit")
    run = store.create_run(p["id"], request(state, contracts=[contract]))
    with pytest.raises(IntegrityError, match="stale"):
        design_services_run(store, run, Control())


def test_local_catalogue_result_cannot_grant_building_or_revision_authority(tmp_path):
    store, p, state = project(tmp_path)
    inventory = design_services_run(store, store.create_run(p["id"], request(state)), Control())
    network, = [n for n in inventory["networks"] if n["source_sha256"] == state["sources"][1]["sha256"]]
    contract = {k: network[k] for k in ("network_id", "network_root", "source_sha256")}
    option = {"id": "wire", "parameters": {"loop_resistance_ohm": "1/10", "ampacity_a": "3"}, "total_cost": "20",
              "material_applicability": "Explicit caller material assumption", "installation_applicability": "Supplied DC full loop"}
    contract.update(service="ELECTRICAL_DC", options=[option], requirements={"current_a": "2", "voltage_drop_limit_v": "1"}, catalogue_complete=True)
    run = store.create_run(p["id"], request(state, contracts=[contract]))
    report = design_services_run(store, run, Control())
    screened, = [n for n in report["networks"] if n["status"] == "CATALOGUE_SCREENED"]
    calculation = store.get(screened["design_result_root"])
    assert calculation["status"] == "CATALOG_OPTIMAL"
    assert calculation["options"][0]["metrics"]["voltage_drop_v"]["lower"] == "1/5"
    assert report["status"] == "DESIGN_INPUTS_REQUIRED"  # Mechanical still present and unresolved.
    assert not screened["network_service_verified"] and not report["whole_building_optimized"]
    assert store.project(p["id"])["revision"] == 0 and store.candidates(p["id"]) == []


def test_api_accepts_supervised_whole_building_operation(tmp_path):
    from fastapi.testclient import TestClient
    from oma.api import create_app
    app = create_app(tmp_path / "api", recover=False)
    service = app.state.engine
    service.schedule = lambda run_id: None
    p = service.store.create_project("request", {"sources": []})
    with TestClient(app) as client:
        response = client.post(f"/api/projects/{p['id']}/runs", json={"operation": "design_services", "mission": {"schema": SCHEMA}})
    assert response.status_code == 202
    assert response.json()["operation"] == "design_services"
