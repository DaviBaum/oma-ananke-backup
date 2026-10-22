import copy

import pytest

from oma.models import PhysicalNetwork
from oma.routing.network_scenario import SharedNetworkScenario, network_requirements, network_baseline_context
from oma.store import digest
from test_network_scenario import network_scenario


def prior_state():
    scenario = SharedNetworkScenario.model_validate(network_scenario())
    state = {"sources": [{"id": "source-one", "transform_m": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]}],
             "entities": [], "ports": [], "routes": [], "explicit_connections": [], "inferred_connections": []}
    mission, ports, section = network_requirements(state, scenario)
    tree = scenario.network_alternatives[0]
    state.update(mission=mission, ports=ports, physical_networks=[PhysicalNetwork(id=tree.network_id,
        demand_ids=tuple(s.demand_id for s in scenario.sinks), component_ids=tuple(c.id for c in tree.components),
        port_ids=tuple(p["id"] for p in ports), service=scenario.system_type, section=section,
        geometry_artifact="a" * 64).model_dump(mode="json")])
    state["derived_artifacts"] = {"network_contract": {"scenario": scenario.model_dump(mode="json", by_alias=True),
        "selected_alternative": tree.network_id, "source_id": "source-one"}}
    return state


def revised_scenario(state):
    raw = copy.deepcopy(state["derived_artifacts"]["network_contract"]["scenario"])
    raw.update(replace_network_id=state["physical_networks"][0]["id"], source_id="source-one")
    tree = raw["network_alternatives"][0]
    tree["network_id"] = "revised-tree"
    tree["components"][0]["geometry"]["end_m"] = [-.25, 4, 3]
    tree["components"][1]["geometry"].update(trunk_takeout_m=.25, branch_takeout_m=.25)
    tree["components"][2]["geometry"]["start_m"] = [.25, 4, 3]
    tree["components"][3]["geometry"]["start_m"] = [0, 4.25, 3]
    return raw


def test_initial_optional_revision_field_preserves_historical_scenario_hash():
    scenario = SharedNetworkScenario.model_validate(network_scenario())
    raw = scenario.model_dump(mode="json", by_alias=True)
    assert "replace_network_id" not in raw
    assert digest(raw) == digest(SharedNetworkScenario.model_validate({**raw, "replace_network_id": None}).model_dump(mode="json", by_alias=True))


@pytest.mark.parametrize("mutation", [
    lambda s: s.update(clearance_m=0),
    lambda s: s.update(minimum_straight_m=0),
    lambda s: s.update(minimum_bend_radius_m=.09),
    lambda s: s["allowed_zone"]["max"].__setitem__(0, 3),
    lambda s: s["sinks"][0].update(required_flow_m3_s=.0001),
    lambda s: s["sinks"][0].update(available_static_pressure_pa=2000),
    lambda s: s["physics"].update(darcy_friction=0),
    lambda s: s["physics"].update(fixed_flow_control_assumption="Different controls"),
    lambda s: s.update(target_modality="LOCAL_GEOMETRIC_COORDINATION"),
    lambda s: s.update(assumptions=["Additional unstated relaxation"]),
    lambda s: s.update(objective_weights={"fitting_count": 1}),
    lambda s: s.update(source_representation_policy="NATIVE_CAD_WITH_SOURCE_VERTEX_HULL_ENCLOSURES"),
])
def test_revision_cannot_change_fixed_requirements(mutation):
    baseline = prior_state()
    request = revised_scenario(baseline)
    mutation(request)
    with pytest.raises(ValueError, match="every fixed"):
        network_baseline_context(baseline, SharedNetworkScenario.model_validate(request))


@pytest.mark.parametrize("mutation", [
    lambda s: s["mission"]["demands"][0].update(required_flow_m3_s=.0001),
    lambda s: s["physical_networks"][0]["component_ids"].pop(),
    lambda s: s["ports"].pop(),
    lambda s: s["ports"].append(copy.deepcopy(s["ports"][0])),
    lambda s: s["explicit_connections"].append([s["ports"][0]["id"], "original-port"]),
    lambda s: s["inferred_connections"].append({"ports": [s["ports"][0]["id"], "original-port"]}),
])
def test_revision_cannot_silently_discard_previous_obligations(mutation):
    baseline = prior_state()
    request = SharedNetworkScenario.model_validate(revised_scenario(baseline))
    mutation(baseline)
    with pytest.raises(ValueError):
        network_baseline_context(baseline, request)


def test_revision_preserves_original_ports_and_binds_every_previous_component():
    state = prior_state()
    original = {"id": "original-port", "unmodified": True}
    state["ports"].insert(0, original)
    snapshot = copy.deepcopy(state)
    source, kept, revision = network_baseline_context(state, SharedNetworkScenario.model_validate(revised_scenario(state)))
    assert state == snapshot
    assert source["id"] == "source-one" and kept == [original]
    assert len(revision["previous_component_ids"]) == 4
    assert revision["previous_network_root"] == digest(state["physical_networks"][0])


def test_actual_revision_replaces_one_tree_and_rechecks_its_export(tmp_path):
    import ifcopenshell
    from oma.build_identity import checker_version
    from oma.exporting import export_project
    from oma.routing.engine import route_project_run
    from oma.routing.network_checker import verify_network_candidate
    from oma.worker import WorkerControl
    from test_network_integration import imported_project

    store, project = imported_project(tmp_path)
    first = store.create_run(project["id"], {"operation": "optimize", "mission": network_scenario(), "budget_seconds": 60})
    route_project_run(store, first, WorkerControl(store, first["id"]))
    old = store.candidates(project["id"])[0]
    assert old["status"] == "CHECKED"
    store.accept(project["id"], old["id"], 1, "accept-before-revision", checker_version=checker_version())
    baseline = store.get(old["state_root"])
    request = revised_scenario(baseline)
    request["source_id"] = baseline["sources"][0]["id"]
    run = store.create_run(project["id"], {"operation": "optimize", "mission": request, "budget_seconds": 60})
    route_project_run(store, run, WorkerControl(store, run["id"]))
    candidate = next(c for c in store.candidates(project["id"]) if c["run_id"] == run["id"])
    report = store.get(candidate["report_root"])
    assert candidate["status"] == "CHECKED", report
    assert store.get(old["state_root"]) == baseline
    state = store.get(candidate["state_root"])
    revision = state["derived_artifacts"]["network_contract"]["revision"]
    assert revision["base_root"] == old["state_root"]
    assert len(candidate["changed_ids"]) == 8
    assert len(state["ports"]) == len(baseline["ports"])
    assert not set(baseline["physical_networks"][0]["port_ids"]) & {p["id"] for p in state["ports"]}
    # An injected candidate cannot erase its predecessor or forge revision roots.
    for kind in ("lineage", "changed", "original"):
        forged_state, changes = copy.deepcopy(state), list(candidate["changed_ids"])
        if kind == "lineage":
            forged_state["derived_artifacts"]["network_contract"]["revision"]["base_root"] = "0" * 64
        elif kind == "changed":
            changes.pop()
        else:
            forged_state["sources"][0]["sha256"] = "0" * 64
        forged = store.add_candidate(run["id"], forged_state, {"kind": "physical_network", "changed_ids": changes})
        assert verify_network_candidate(store, forged["id"]).status == "FAIL"
    store.accept(project["id"], candidate["id"], 2, "accept-revision", checker_version=checker_version())
    exported = export_project(store, project["id"], candidate["id"], draft=False)
    assert exported["status"] == "CHECKED_LOCAL_SCOPE", exported
    assert exported["round_trip"] == "PASS"
    model = ifcopenshell.open(exported["files"][0]["path"])
    assert len(model.by_type("IfcPipeSegment")) == 3
    assert len(model.by_type("IfcPipeFitting")) == 1
    assert len(model.by_type("IfcDistributionPort")) == 9
    assert len(model.by_type("IfcRelConnectsPorts")) == 3
    current_parts = store.get(state["physical_networks"][0]["geometry_artifact"])["added_parts"]
    old_parts = store.get(baseline["physical_networks"][0]["geometry_artifact"])["added_parts"]
    assert {p["ifc_guid"] for p in current_parts}.isdisjoint(p["ifc_guid"] for p in old_parts)
    assert {p.GlobalId for p in model.by_type("IfcFlowSegment") + model.by_type("IfcFlowFitting")} == {p["ifc_guid"] for p in current_parts}
