from copy import deepcopy

from oma.project_dependencies import derive_transition
from oma.store import Store, digest, utcnow
from oma.models import CheckResult, VerificationReport, Verdict
from oma.project_assurance import build_report_assurance


def state_fixture():
    section = {"shape": "circular", "diameter_m": .1, "insulation_m": .02}
    return {"schema_version": 1, "project_id": "fixture", "units": "m", "numerical_policy": {"tolerance_m": 1e-6},
        "sources": [{"id": "near", "sha256": "original-near"}, {"id": "far", "sha256": "original-far"}],
        "entities": [{"id": "near:1", "provenance": {"source_id": "near"}, "geometry": {"status": "represented", "bounds": [0, 1]}},
                     {"id": "far:1", "provenance": {"source_id": "far"}, "geometry": {"status": "represented", "bounds": [1000, 1001]}}],
        "ports": [{"id": "in", "position_status": "KNOWN"}, {"id": "out", "position_status": "KNOWN"}],
        "routes": [{"id": "service", "section": section, "service": "PRESSURE_PIPE", "port_ids": ["in", "out"],
                    "points_m": [[0, 0, 0], [2, 0, 0]], "demand_ids": ["demand"]}],
        "explicit_connections": [], "inferred_connections": [{"ports": ["in", "out"], "evidence": "proximity_only"}],
        "mission": {"rule_hash": "fixed-rules", "assumptions": ["Fixed declared flow"], "demands": [
            {"id": "demand", "source_port": "in", "sink_ports": ["out"], "section": section,
             "service": "PRESSURE_PIPE", "required_flow_m3_s": .001}]}, "derived_artifacts": {}}


def test_actual_state_reuse_matches_cold_and_distant_geometry_invalidates_clearance():
    before = state_fixture()
    no_change = derive_transition(before, deepcopy(before), executable="test-build")
    assert no_change["cold_equivalent"]
    assert no_change["recomputed"] == []
    assert no_change["changed_authoritative_inputs"] == []
    assert no_change["artifacts"]["netlist"]["value"]["explicit_components"] == 2
    assert not no_change["artifacts"]["netlist"]["value"]["inferred_connections_promoted_to_explicit"]
    after = deepcopy(before)
    after["entities"][1]["geometry"]["bounds"] = [900, 901]
    result = derive_transition(before, after, executable="test-build")
    assert result["cold_equivalent"]
    assert "entity-records:far" in result["changed_authoritative_inputs"]
    assert "route-clearance:service" in result["conservatively_affected"]
    assert "inventory:near" in result["reused"]
    assert "route-shape:service" in result["reused"]
    assert not result["physical_checks_reused_across_roots"]
    after["entities"][1]["future_property"] = {"source-defined-interaction": True}
    opaque = derive_transition(before, after, executable="test-build")
    assert "route-clearance:service" in opaque["conservatively_affected"]
    assert opaque["input_roots"]["entity-records:far"] != result["input_roots"]["entity-records:far"]


def test_nonlocal_flow_and_new_fields_are_accounted_without_claiming_geometry_pass():
    before = state_fixture()
    after = deepcopy(before)
    after["mission"]["demands"][0]["required_flow_m3_s"] *= 5
    after["new_guarded_contract"] = {"enabled": True}
    result = derive_transition(before, after, executable="test-build")
    assert result["cold_equivalent"]
    assert "state:new_guarded_contract" in result["changed_authoritative_inputs"]
    assert "route-service:service" in result["semantic_output_changes"]
    assert "inventory:far" in result["reused"]
    assert result["artifacts"]["route-clearance:service"]["value"]["engineering_verdict"] == "NOT_RUN"
    after["ports"].pop()
    result = derive_transition(before, after, executable="test-build")
    assert result["artifacts"]["mission-coverage"]["value"]["status"] == "UNRESOLVED"


def test_reserved_looking_source_identity_is_not_omitted():
    before = state_fixture()
    before["sources"][0]["id"] = "index"
    before["entities"][0]["provenance"]["source_id"] = "index"
    before["sources"][1]["id"] = "unattributed"
    before["entities"][1]["provenance"]["source_id"] = "unattributed"
    result = derive_transition(before, before, executable="test-build")
    assert result["cold_equivalent"]
    assert result["artifacts"]["inventory:index"]["value"]["entity_count"] == 1
    assert result["artifacts"]["inventory:unattributed"]["value"]["entity_count"] == 1


def test_recorded_report_gets_grounded_assurance_and_revision_derivation(tmp_path):
    store = Store(tmp_path / "store")
    state = state_fixture()
    project = store.create_project("assurance fixture", state, project_id="fixture")
    run = store.create_run(project["id"], {"operation": "check"})
    candidate = store.add_candidate(run["id"], state, {"kind": "test"})
    report = VerificationReport(candidate_root=candidate["state_root"], mission_hash=digest(state["mission"]),
        rule_hash=state["mission"]["rule_hash"], checker_version="test-build", status=Verdict.PASS,
        scope="Analytic fixture check only", results=(CheckResult(id="fixture", status=Verdict.PASS,
        reason="Known synthetic reference", scope="Analytic fixture check only"),), objective={},
        common_mode_risks=("Test assumption, not a real building",), created_at=utcnow())
    checked = store.record_verification(candidate["id"], report)
    event = next(e for e in reversed(store.events(project["id"])) if e["stage"] == "verification")
    packet = store.get(event["payload"]["assurance"]["root"])
    assert packet["support_status"] == "SUPPORTED_CONDITIONALLY"
    assert packet["independent_assurance_check"]["status"] == "PASS"
    assert packet["whole_building_certification"] == "NOT_ESTABLISHED"
    assert packet["assumption_ledger"]
    stale = build_report_assurance(store, checked, checked["report_root"], executable="changed-build", assessment_time=utcnow())
    assert stale["support_status"] == "UNSUPPORTED"
    assert set(stale["certificate"]["excluded_foundations"].values()) == {"INAPPLICABLE_CONTEXT"}
    store.accept(project["id"], candidate["id"], 0, "accept", checker_version="test-build")
    publication = next(e for e in reversed(store.events(project["id"])) if e["status"] == "ACCEPTED")
    transition = store.get(publication["payload"]["derivation_root"])
    assert transition["cold_equivalent"]
    assert transition["after_root"] == candidate["state_root"]
    # Evidence is rooted in the event graph, so portable backup retains it.
    backup = Store(store.backup(tmp_path / "backup"))
    assert backup.get(event["payload"]["assurance"]["root"]) == packet
    assert backup.get(publication["payload"]["derivation_root"])["cold_equivalent"]


def test_known_port_advisory_invalidates_support_and_blocks_accept_and_checked_export(tmp_path):
    import pytest
    from oma.store import IntegrityError
    from oma.exporting import export_project
    from oma.validation_advisories import candidate_advisories
    store = Store(tmp_path / "store")
    state = state_fixture()
    state["routes"][0]["geometry_artifact"] = store.put({"port_encoding": "historical-outward-normals"})
    project = store.create_project("historical port convention", state, project_id="fixture")
    run = store.create_run(project["id"], {"operation": "check"})
    candidate = store.add_candidate(run["id"], state, {"kind": "physical_route"})
    report = VerificationReport(candidate_root=candidate["state_root"], mission_hash=digest(state["mission"]),
        rule_hash=state["mission"]["rule_hash"], checker_version="test-build", status=Verdict.PASS,
        scope="Historical fixture report", results=(CheckResult(id="old-port-check", status=Verdict.PASS,
        reason="Earlier convention", scope="Historical fixture"),), objective={}, created_at=utcnow())
    checked = store.record_verification(candidate["id"], report)
    packet = build_report_assurance(store, checked, checked["report_root"], executable="test-build", assessment_time=utcnow())
    assert packet["recorded_engineering_status"] == "PASS"
    assert packet["support_status"] == "UNSUPPORTED"
    assert packet["validation_advisories"][0]["id"] == "IFC-PORT-001"
    assert packet["certificate"]["frontiers"]["claim:known-validation-advisories"] == []
    assert candidate_advisories(store, candidate)[0]["route_ids"] == ["service"]
    with pytest.raises(IntegrityError, match="IFC-PORT-001"):
        store.accept(project["id"], candidate["id"], 0, "forbidden", checker_version="test-build")
    with pytest.raises(IntegrityError, match="IFC-PORT-001"):
        export_project(store, project["id"], candidate["id"], draft=False)
