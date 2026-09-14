"""Current native counterexamples cannot inherit authority from old pair hints."""
from copy import deepcopy

import ifcopenshell
import pytest

from oma.models import Demand, Mission, Route
from oma.routing.joint import _new_obligation
from oma.routing.joint_materialize import materialize_route_set
from oma.routing.scenario import RoutingScenario
from oma.store import Store, digest
from oma.worker import WorkerControl, import_sources
from test_ifc_pipeline import make_fixture
from test_fabrication_binding_adversarial import native_candidates as prior_native_candidates


def _native_candidate(directory, *, crossing=True, clearance=.1, second_clearance=None):
    """Two actual independent route solids, without expensive proposal search."""
    directory.mkdir(parents=True, exist_ok=True)
    source = make_fixture(directory / "source.ifc")
    model = ifcopenshell.open(str(source))
    original_space = model.create_entity("IfcSpace", GlobalId=ifcopenshell.guid.new(), Name="Protected original space")
    space_guid = original_space.GlobalId
    model.write(str(source))
    store = Store(directory / "store")
    project = store.create_project("Fresh pair hint adversarial fixture", {})
    imported = store.create_run(project["id"], {"operation": "import", "paths": [str(source)]})
    import_sources(store, imported, WorkerControl(store, imported["id"]))
    first = RoutingScenario(start=(-1., 4., 1.), end=(3., 4., 1.), system_type="PRESSURE_PIPE",
        diameter_m=.1, insulation_m=.02, bend_radius_m=.3, minimum_straight_m=.05,
        clearance_m=clearance, allowed_zone={"min": [-2., -2., -2.], "max": [6., 6., 6.]},
        scenario_terminals=True, max_candidates=1)
    second = first.model_copy(update={"start": (1., 3., 1.), "end": (1., 5., 1.)}) if crossing else first.model_copy(
        update={"start": (-1., 4.25, 1.), "end": (3., 4.25, 1.)})
    if second_clearance is not None:
        second = second.model_copy(update={"clearance_m": second_clearance})
    scenarios = {"first": first, "second": second}
    mission = {"route_demands": [{"id": key, "alternatives": [value.model_dump(mode="json")]} for key, value in scenarios.items()],
        "max_joint_candidates": 1, "max_paths_per_alternative": 1}
    run = store.create_run(project["id"], {"operation": "route", "mission": mission, "budget_seconds": 90})
    baseline = store.get(run["base_root"])
    state = deepcopy(baseline)
    selected = state["sources"][0]
    routes, contracts, specs = [], {}, {}
    for key, scenario in scenarios.items():
        rid = "audit-" + key
        contract, ports, section = _new_obligation(baseline, scenario, rid, key, selected["id"])
        contracts[rid] = contract
        state.setdefault("ports", []).extend(p.model_dump(mode="json") for p in ports)
        state.setdefault("assumptions", []).append({"kind": "explicit_scenario", "root": digest(contract["scenario"]), "data": contract["scenario"]})
        points = [list(scenario.start), list(scenario.end)]
        routes.append(Route(id=rid, demand_ids=(contract["mission"]["demands"][0]["id"],), service=scenario.system_type,
            points_m=points, section=section, port_ids=tuple(p.id for p in ports), status="MATERIALIZED").model_dump(mode="json"))
        spec = {"route_id": rid, "points_m": points, "diameter_m": scenario.diameter_m, "insulation_m": scenario.insulation_m,
            "bend_radius_m": scenario.bend_radius_m, "minimum_straight_m": scenario.minimum_straight_m,
            "system_type": scenario.system_type, "assumption_root": digest(contract["scenario"])}
        if selected.get("transform_m") is not None:
            spec["source_to_federation_matrix"] = selected["transform_m"]
        specs[rid] = spec
    materialized = materialize_route_set(store, baseline, contracts, specs, directory / "materialized", lambda stage: None)
    for route in routes:
        route["geometry_artifact"] = store.put(materialized[route["id"]])
    missions = [contracts[rid]["mission"] for rid in sorted(contracts)]
    state["routes"] = routes
    state["mission"] = Mission(id="audit-joint", demands=tuple(Demand.model_validate(d) for m in missions for d in m["demands"]),
        protected_ids=tuple(e["id"] for e in baseline.get("entities", [])), allowed_zones=tuple(z for m in missions for z in m["allowed_zones"]),
        rule_hash=digest([m["rule_hash"] for m in missions]), catalog_hash=digest([m["catalog_hash"] for m in missions]),
        scenario_hash=digest([m["scenario_hash"] for m in missions]), objective_weights=first.objective_weights).model_dump(mode="json")
    state.setdefault("derived_artifacts", {}).update(routing_contracts=contracts,
        route_exports=[{"source_id": selected["id"], "route_spec": specs[rid]} for rid in specs])
    from oma.routing.physical_archive import freeze_route_menu
    from oma.routing.joint_scenario import parse_joint_request
    menu_root = freeze_route_menu(store, run, baseline, parse_joint_request(mission), [
        [("0:0", scenario, {"points_m": [list(scenario.start), list(scenario.end)]})] for scenario in scenarios.values()])
    candidate = store.add_candidate(run["id"], state, {"kind": "physical_route_set", "changed_ids": [r["id"] for r in routes],
        "physical_menu_root": menu_root, "physical_menu_assignment": ["0:0", "0:0"]})
    return {"store": store, "run": run, "candidate": candidate, "state": state, "baseline": baseline,
        "materialized": materialized, "space_guid": space_guid, "scenarios": scenarios}


@pytest.fixture(scope="module")
def actual_joint_cases(tmp_path_factory):
    directory = tmp_path_factory.mktemp("joint-negative-hint-adversarial")
    return {"crossing": _native_candidate(directory / "crossing"),
        "separated": _native_candidate(directory / "separated", crossing=False),
        "clearance": _native_candidate(directory / "clearance", crossing=False, second_clearance=.2)}


def _hint(case):
    menu = case["store"].get(case["candidate"]["physical_menu_root"])
    members = []
    for route in case["state"]["routes"]:
        demand = case["state"]["derived_artifacts"]["routing_contracts"][route["id"]]["request_demand_id"]
        part = case["materialized"][route["id"]]["added_parts"][0]
        members.append({"route": {"kind": "choice", "demand_id": demand, "choice_id": "0:0",
            "definition_root": menu["definitions"][demand + "/0:0"]}, "part_index": 0, "part_kind": part["kind"]})
    return {"origin_candidate_id": "forged-old-identity", "origin_report_root": "f" * 64,
        "frozen_menu_root": case["candidate"]["physical_menu_root"], "members": members,
        "authority": "SCHEDULING_HINT_ONLY", "status": "FAIL", "common_volume_m3": 1.e99}


def _request(case):
    """Explicit current member bindings; old numbers deliberately cannot agree."""
    from oma.build_identity import checker_version
    from oma.routing.joint_negative_probe import SCHEMA, _file_inventory
    candidate, store, state = case["candidate"], case["store"], case["state"]
    members = []
    for route in state["routes"]:
        part = case["materialized"][route["id"]]["added_parts"][0]
        members.append({"route_id": route["id"], "part_index": 0, "ifc_guid": part["ifc_guid"],
            "step_id": part["step_id"], "materialization_root": route["geometry_artifact"]})
    return {"schema": SCHEMA, "candidate_id": candidate["id"], "state_root": candidate["state_root"],
        "run_id": candidate["run_id"], "checker_version": checker_version(), "files": _file_inventory(store, state),
        "pairs": [{"members": members, "hint": _hint(case)}]}


def _no_authority(result):
    assert result["status"] == "NO_COUNTEREXAMPLE_FOUND", result
    assert result["continue_full_check"]
    assert result["full_source_denominator"] == result["full_cross_route_denominator"] == "NOT_RUN"
    assert result["objective_authority"] == result["acceptance_authority"] == "NONE"
    assert result["feasibility_verdict"] == "NOT_RUN"
    assert not result["old_verdict_reused"] and "witness" not in result


def test_actual_native_fixtures_have_different_cross_route_truth(actual_joint_cases):
    from oma.routing.joint_checker import verify_joint_candidate
    for name, expected in (("crossing", "FAIL"), ("separated", "PASS")):
        case = actual_joint_cases[name]
        report = verify_joint_candidate(case["store"], case["candidate"]["id"])
        result = next(r for r in report.results if r.id == "cross-route-interference")
        assert result.status == expected, report.model_dump(mode="json")
        assert report.status == expected, report.model_dump(mode="json")


@pytest.mark.parametrize("name,expected,reason", [("crossing", "FAIL", "POSITIVE_COMMON_SOLID_VOLUME"),
    ("separated", "NO_COUNTEREXAMPLE_FOUND", None),
    ("clearance", "FAIL", "CLEARANCE_VIOLATION")])
def test_forged_prior_scalar_is_ignored_and_current_geometry_and_max_rule_are_computed(actual_joint_cases, name, expected, reason):
    from oma.routing.joint_negative_probe import _run_request
    case = actual_joint_cases[name]
    result = _run_request(case["store"], _request(case))
    assert result["status"] == expected, result
    assert result["new_native_verification_performed"] and not result["old_verdict_reused"]
    pair = result["probes"][0]["native_pair_result"]
    if reason is None:
        assert pair["status"] == "PASS"
    else:
        assert pair["reason"] == reason
    assert pair["required_clearance_m"] == max(s.clearance_m for s in case["scenarios"].values())
    assert pair["common_volume_m3"] != 1.e99
    assert result["full_source_denominator"] == result["full_cross_route_denominator"] == "NOT_RUN"
    assert result["objective_authority"] == result["acceptance_authority"] == "NONE"
    if expected != "FAIL":
        _no_authority(result)


@pytest.mark.parametrize("fault", ["state", "build", "files", "material", "guid", "step", "same_route", "index"])
def test_stale_current_member_or_input_binding_never_inherits_prior_failure(actual_joint_cases, fault):
    from oma.routing.joint_negative_probe import _run_request
    case = actual_joint_cases["crossing"]
    request = _request(case)
    if fault == "state": request["state_root"] = "0" * 64
    elif fault == "build": request["checker_version"] = "old-executable"
    elif fault == "files": request["files"][0][1] = "0" * 64
    else:
        pair = request["pairs"][0]["members"]
        if fault == "material": pair[0]["materialization_root"] = "0" * 64
        elif fault == "guid": pair[0]["ifc_guid"] = case["space_guid"]
        elif fault == "step": pair[0]["step_id"] += 1
        elif fault == "same_route": pair[1] = deepcopy(pair[0])
        else: pair[0]["part_index"] = -1
    _no_authority(_run_request(case["store"], request))


@pytest.mark.parametrize("target", ["source", "export"])
def test_bytes_changed_after_fresh_native_failure_remove_all_counterexample_authority(actual_joint_cases, monkeypatch, target):
    import oma.ifc.cad as cad
    from oma.routing.joint_negative_probe import _run_request
    case = actual_joint_cases["crossing"]
    path = case["store"].resolve_path(case["state"]["sources"][0]["immutable_path"] if target == "source"
        else case["materialized"]["audit-first"]["export_path"])
    original = path.read_bytes()
    check_pair = cad.check_pair
    calls = []
    def changed(*args, **kwargs):
        result = check_pair(*args, **kwargs)
        assert result["status"] == "FAIL"
        calls.append(result)
        path.write_bytes(original + b"\n")
        return result
    monkeypatch.setattr(cad, "check_pair", changed)
    try:
        result = _run_request(case["store"], _request(case))
        _no_authority(result)
        assert len(calls) == 1 and result["stop_reason"] == "CURRENT_INPUT_CHANGED_DURING_PROBE"
    finally:
        path.write_bytes(original)


@pytest.mark.parametrize("exception_type", [TimeoutError, ValueError, RuntimeError])
def test_late_child_cancellation_does_not_become_a_geometric_verdict(actual_joint_cases, monkeypatch, exception_type):
    import oma.verification as verification
    from oma.routing.joint_negative_probe import _run_request
    case = actual_joint_cases["crossing"]
    signal = exception_type("cancel after native witness before publication")
    class Control:
        def checkpoint(self, stage):
            if stage == "joint_hint_child_publish":
                raise signal
    monkeypatch.setattr(verification, "candidate_control", lambda *args: Control())
    with pytest.raises(exception_type) as caught:
        _run_request(case["store"], _request(case))
    assert caught.value is signal


def _add_hinted_candidate(case, state=None):
    state = deepcopy(state or case["state"])
    return case["store"].add_candidate(case["run"]["id"], state, {"kind": "physical_route_set",
        "changed_ids": case["candidate"]["changed_ids"], "physical_menu_root": case["candidate"]["physical_menu_root"],
        "physical_menu_assignment": case["candidate"]["physical_menu_assignment"], "joint_pair_hints": [_hint(case)]})


def test_actual_hinted_failure_has_no_full_denominator_or_objective_authority(actual_joint_cases, monkeypatch):
    import oma.routing.checker as route_checker
    from oma.routing.joint_checker import verify_joint_candidate
    case = actual_joint_cases["crossing"]
    candidate = _add_hinted_candidate(case)
    def forbidden(*args, **kwargs):
        raise AssertionError("Full native source scans should remain NOT_RUN after fresh pair failure")
    monkeypatch.setattr(route_checker, "cad_check_routes", forbidden)
    report = verify_joint_candidate(case["store"], candidate["id"])
    assert report.status == "FAIL" and report.objective == {}, report.model_dump(mode="json")
    witness = next(r for r in report.results if r.id == "native-cross-route-counterexample")
    assert witness.status == "FAIL" and witness.witness["new_native_verification_performed"]
    assert not witness.witness["old_verdict_reused"]
    cross = next(r for r in report.results if r.id == "cross-route-interference")
    assert cross.status == "NOT_RUN" and cross.witness["pairs_accounted"] == 0
    assert not cross.witness["complete_component_coverage"]
    for route in case["state"]["routes"]:
        for obligation in ("physical-interference-and-clearance", "physical-self-interference", "permitted-zone-containment",
                           "independent-objective-recomputation", "engineering-service"):
            assert next(r for r in report.results if r.id == route["id"] + ":" + obligation).status == "NOT_RUN"
    assert next(r for r in report.results if r.id == "joint-objective").status == "NOT_RUN"


def test_forged_old_failure_on_current_separated_bodies_runs_the_complete_native_checker(actual_joint_cases, monkeypatch):
    import oma.routing.checker as route_checker
    from oma.routing.joint_checker import verify_joint_candidate
    case = actual_joint_cases["separated"]
    candidate = _add_hinted_candidate(case)
    calls = []
    check = route_checker.cad_check_routes
    def counted(*args, **kwargs):
        calls.append(args)
        return check(*args, **kwargs)
    monkeypatch.setattr(route_checker, "cad_check_routes", counted)
    report = verify_joint_candidate(case["store"], candidate["id"])
    assert report.status == "PASS", report.model_dump(mode="json")
    assert len(calls) == 2 and report.objective == {"length_m": 8., "fitting_count": 0.}
    cross = next(r for r in report.results if r.id == "cross-route-interference")
    assert cross.status == "PASS" and cross.witness["pairs_accounted"] == 1
    assert cross.witness["complete_component_coverage"]
    assert not any(r.id == "native-cross-route-counterexample" for r in report.results)


@pytest.mark.parametrize("field", ["rule_hash", "catalog_hash", "scenario_hash", "objective_weights"])
def test_current_aggregate_mission_binding_precedes_every_hinted_native_probe(actual_joint_cases, monkeypatch, field):
    import oma.routing.joint_negative_probe as probe
    from oma.routing.joint_checker import verify_joint_candidate
    case = actual_joint_cases["crossing"]
    state = deepcopy(case["state"])
    state["mission"][field] = {"length_m": 2., "fitting_count": 0.} if field == "objective_weights" else "0" * 64
    candidate = _add_hinted_candidate(case, state)
    def forbidden(*args, **kwargs):
        raise AssertionError("An unbound composite mission cannot reach the hinted-pair gate")
    monkeypatch.setattr(probe, "probe_joint_failure", forbidden)
    report = verify_joint_candidate(case["store"], candidate["id"])
    assert report.status == "FAIL"
    assert next(r for r in report.results if r.id == "joint-mission-binding").status == "FAIL"
    assert not any(r.id == "native-cross-route-counterexample" for r in report.results)


def _replace_export(case, path, mutate):
    from oma.ifc.audit import sha256_file
    state = deepcopy(case["state"])
    before = case["store"].resolve_path(case["materialized"]["audit-first"]["export_path"])
    model = ifcopenshell.open(str(before))
    mutate(model)
    model.write(str(path))
    for route in state["routes"]:
        material = deepcopy(case["materialized"][route["id"]])
        material.update(export_path=str(path), export_sha256=sha256_file(path))
        route["geometry_artifact"] = case["store"].put(material)
    return state


@pytest.mark.parametrize("attack", ["property", "group"])
def test_original_inverse_effect_preflight_is_not_bypassed_by_a_real_pair_counterexample(actual_joint_cases, tmp_path, monkeypatch, attack):
    import oma.routing.joint_negative_probe as probe
    from oma.routing.joint_checker import verify_joint_candidate
    case = actual_joint_cases["crossing"]
    def mutate(model):
        original = model.by_guid(case["space_guid"])
        if attack == "property":
            value = model.create_entity("IfcPropertySingleValue", Name="Unapproved", NominalValue=model.create_entity("IfcLabel", "Changed"))
            prop = model.create_entity("IfcPropertySet", GlobalId=ifcopenshell.guid.new(), HasProperties=[value])
            model.create_entity("IfcRelDefinesByProperties", GlobalId=ifcopenshell.guid.new(), RelatedObjects=[original], RelatingPropertyDefinition=prop)
        else:
            group = model.create_entity("IfcSystem", GlobalId=ifcopenshell.guid.new(), Name="Unapproved group")
            model.create_entity("IfcRelAssignsToGroup", GlobalId=ifcopenshell.guid.new(), RelatedObjects=[original], RelatingGroup=group)
    state = _replace_export(case, tmp_path / "inverse-attack.ifc", mutate)
    original_model = ifcopenshell.open(str(case["store"].resolve_path(state["sources"][0]["immutable_path"])))
    changed_model = ifcopenshell.open(str(tmp_path / "inverse-attack.ifc"))
    assert all(str(e) == str(changed_model.by_id(e.id())) for e in original_model)
    candidate = _add_hinted_candidate(case, state)
    def forbidden(*args, **kwargs):
        raise AssertionError("Unapproved inverse effects cannot reach the hinted-pair gate")
    monkeypatch.setattr(probe, "probe_joint_failure", forbidden)
    report = verify_joint_candidate(case["store"], candidate["id"])
    assert report.status == "FAIL"
    errors = [r for r in report.results if r.id.endswith(":exported-physical-semantics") and r.status == "FAIL"]
    assert errors and all("inverse semantics" in r.reason for r in errors)


@pytest.mark.parametrize("outcome", ["UNKNOWN_TIMEOUT", "UNKNOWN_RESOURCE_LIMIT", "UNKNOWN_PROCESS_TREE", "FAILED"])
def test_partial_child_failure_is_discarded_on_every_unsuccessful_supervision(actual_joint_cases, monkeypatch, outcome):
    import json
    from pathlib import Path
    import oma.routing.joint_negative_probe as probe
    from oma.ifc.audit import atomic_json
    case = actual_joint_cases["crossing"]
    candidate = _add_hinted_candidate(case)
    def partial(command, **kwargs):
        request = json.loads(Path(command[-2]).read_text(encoding="utf-8"))
        result = probe._run_request(case["store"], request)
        assert result["status"] == "FAIL" and result["new_native_verification_performed"]
        atomic_json(Path(command[-1]), result)
        return {"status": outcome}
    monkeypatch.setattr(probe, "supervise_check", partial)
    result = probe.probe_joint_failure(case["store"], candidate, case["state"], WorkerControl(case["store"], case["run"]["id"]))
    _no_authority(result)
    assert result["observed_child_status"] == "FAIL" and result["stop_reason"] == outcome


@pytest.mark.parametrize("field", ["schema", "request_root", "checker_version", "candidate_root", "mission_hash", "rule_hash",
    "new_native_verification_performed", "old_verdict_reused"])
def test_completed_native_child_still_needs_current_report_binding(actual_joint_cases, monkeypatch, field):
    import json
    from pathlib import Path
    import oma.routing.joint_negative_probe as probe
    from oma.ifc.audit import atomic_json
    case = actual_joint_cases["crossing"]
    candidate = _add_hinted_candidate(case)
    def misbound(command, **kwargs):
        request = json.loads(Path(command[-2]).read_text(encoding="utf-8"))
        result = probe._run_request(case["store"], request)
        assert result["status"] == "FAIL"
        result[field] = not result[field] if isinstance(result[field], bool) else "unrelated-old-input"
        atomic_json(Path(command[-1]), result)
        return {"status": "COMPLETED"}
    monkeypatch.setattr(probe, "supervise_check", misbound)
    result = probe.probe_joint_failure(case["store"], candidate, case["state"], WorkerControl(case["store"], case["run"]["id"]))
    _no_authority(result)
    assert result["stop_reason"] == "CHILD_RESULT_BINDING_FAILED"


def test_malformed_completed_child_witness_falls_back_without_an_exception(actual_joint_cases, monkeypatch):
    import json
    from pathlib import Path
    import oma.routing.joint_negative_probe as probe
    from oma.ifc.audit import atomic_json
    case = actual_joint_cases["crossing"]
    candidate = _add_hinted_candidate(case)
    def malformed(command, **kwargs):
        request = json.loads(Path(command[-2]).read_text(encoding="utf-8"))
        result = probe._run_request(case["store"], request)
        assert result["status"] == "FAIL"
        result["witness"] = None
        atomic_json(Path(command[-1]), result)
        return {"status": "COMPLETED"}
    monkeypatch.setattr(probe, "supervise_check", malformed)
    result = probe.probe_joint_failure(case["store"], candidate, case["state"], WorkerControl(case["store"], case["run"]["id"]))
    _no_authority(result)


@pytest.mark.parametrize("exception_type", [TimeoutError, ValueError, RuntimeError])
def test_parent_cancellation_after_valid_fresh_child_cannot_publish_failure(actual_joint_cases, monkeypatch, exception_type):
    import json
    from pathlib import Path
    import oma.routing.joint_negative_probe as probe
    from oma.ifc.audit import atomic_json
    case = actual_joint_cases["crossing"]
    candidate = _add_hinted_candidate(case)
    outputs = []
    def actual_current(command, **kwargs):
        request = json.loads(Path(command[-2]).read_text(encoding="utf-8"))
        result = probe._run_request(case["store"], request)
        assert result["status"] == "FAIL"
        outputs.append(Path(command[-1]))
        atomic_json(outputs[-1], result)
        return {"status": "COMPLETED"}
    signal = exception_type("late parent cancellation")
    class Control:
        def checkpoint(self, stage):
            if stage == "joint_hint_result":
                raise signal
    monkeypatch.setattr(probe, "supervise_check", actual_current)
    with pytest.raises(exception_type) as caught:
        probe.probe_joint_failure(case["store"], candidate, case["state"], Control())
    assert caught.value is signal
    assert len(outputs) == 1 and not (outputs[0].parent / "parent-result.json").exists()


@pytest.mark.parametrize("attack", ["property", "group", "nest", "prior_ports", "unauthorized_branch"])
def test_appended_property_cannot_mutate_a_previously_accepted_route(prior_native_candidates, tmp_path, attack):
    from oma.ifc.audit import atomic_json, sha256_file
    from oma.routing.joint_checker import verify_joint_candidate
    store, _, original, joint = prior_native_candidates
    state = store.get(joint["state_root"])
    prior_route = store.get(original["state_root"])["routes"][0]
    prior_material = store.get(prior_route["geometry_artifact"])
    current_material = store.get(state["routes"][0]["geometry_artifact"])
    before = ifcopenshell.open(str(store.resolve_path(current_material["export_path"])))
    prior_part = before.by_guid(prior_material["added_parts"][0]["ifc_guid"])
    if attack == "property":
        value = before.create_entity("IfcPropertySingleValue", Name="Unapproved prior change", NominalValue=before.create_entity("IfcLabel", "Reassigned"))
        prop = before.create_entity("IfcPropertySet", GlobalId=ifcopenshell.guid.new(), HasProperties=[value])
        before.create_entity("IfcRelDefinesByProperties", GlobalId=ifcopenshell.guid.new(), RelatedObjects=[prior_part], RelatingPropertyDefinition=prop)
    elif attack in ("group", "nest"):
        group = before.create_entity("IfcSystem", GlobalId=ifcopenshell.guid.new(), Name="Unapproved prior reassignment")
        if attack == "group":
            before.create_entity("IfcRelAssignsToGroup", GlobalId=ifcopenshell.guid.new(), RelatedObjects=[prior_part], RelatingGroup=group)
        else:
            before.create_entity("IfcRelNests", GlobalId=ifcopenshell.guid.new(), RelatingObject=group, RelatedObjects=[prior_part])
    else:
        first_port = before.by_guid(prior_material["added_parts"][0]["ports"][0])
        if attack == "prior_ports":
            second_port = before.by_guid(prior_material["added_parts"][0]["ports"][1])
        else:
            new_route = next(r for r in state["routes"] if r["id"] != prior_route["id"])
            new_material = store.get(new_route["geometry_artifact"])
            second_port = before.by_guid(new_material["added_parts"][0]["ports"][0])
        before.create_entity("IfcRelConnectsPorts", GlobalId=ifcopenshell.guid.new(), RelatingPort=first_port, RelatedPort=second_port)
    output = tmp_path / "prior-inverse-attack.ifc"
    before.write(str(output))
    # The ordinary native same-source datum guard must remain satisfied: this
    # attack changes inverse semantics, not source byte or coordinate identity.
    atomic_json(output.with_suffix(".manifest.json"), {**current_material,
        "export_path": str(output), "export_sha256": sha256_file(output)})
    prior_model = ifcopenshell.open(str(store.resolve_path(prior_material["export_path"])))
    assert all(str(e) == str(before.by_id(e.id())) for e in prior_model)
    for route in state["routes"]:
        material = store.get(route["geometry_artifact"])
        material.update(export_path=str(output), export_sha256=sha256_file(output))
        route["geometry_artifact"] = store.put(material)
    candidate = store.add_candidate(joint["run_id"], state, {"kind": "physical_route_set", "changed_ids": joint["changed_ids"]})
    report = verify_joint_candidate(store, candidate["id"])
    # Preserve reproducible native output for both the initially vulnerable and
    # corrected executions without changing the original accepted IFC bytes.
    atomic_json(tmp_path / "prior-inverse-result.json", {"candidate_id": candidate["id"],
        "candidate_root": candidate["state_root"], "original_candidate_id": original["id"],
        "source_records_unchanged": True, "report": report.model_dump(mode="json")})
    assert report.status == "FAIL", report.model_dump(mode="json")
    if attack in ("property", "group", "nest"):
        preservation = next(r for r in report.results if r.id.startswith("prior-physical-preservation:"))
        assert preservation.status == "FAIL" and preservation.witness["inverse_effect_errors"]
