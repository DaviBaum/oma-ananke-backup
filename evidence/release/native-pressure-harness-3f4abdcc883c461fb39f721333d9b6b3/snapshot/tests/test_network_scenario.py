import copy
import json
from fractions import Fraction
from pathlib import Path

import pytest
from pydantic import ValidationError

from oma.routing.network_scenario import NetworkDesign, SharedNetworkScenario
from oma.routing.network_flow import evaluate_network_flow


def network_spec():
    raw = json.loads(Path("docs/ifc-network-spec.json").read_text(encoding="utf-8"))
    raw.pop("source_to_federation_matrix")
    return raw


def network_scenario():
    return {"mission_type": "shared_network", "system_type": "PRESSURE_PIPE", "start_m": [-1, 4, 3],
        "sinks": [{"id": "sink-a", "demand_id": "demand-a", "end_m": [1, 4, 3], "required_flow_m3_s": .001,
                   "available_static_pressure_pa": 1000},
                  {"id": "sink-b", "demand_id": "demand-b", "end_m": [0, 5, 3], "required_flow_m3_s": .002,
                   "available_static_pressure_pa": 1000}],
        "diameter_m": .1, "insulation_m": .02, "clearance_m": .01, "minimum_straight_m": .05,
        "minimum_bend_radius_m": .1, "allowed_zone": {"min": [-2, 3, 2], "max": [2, 6, 4]},
        "scenario_terminals": True, "target_modality": "ENGINEERING_SERVICE",
        "source_representation_policy": "NATIVE_CAD_WITH_EXACT_PLANAR_ENCLOSURES", "network_alternatives": [network_spec()],
        "physics": {"density_kg_m3": 1000, "darcy_friction": .02, "maximum_velocity_m_s": 2,
            "gravity_m_s2": 9.80665, "elbow_loss_coefficient": .2, "tee_straight_loss_coefficient": .2,
            "tee_branch_loss_coefficient": 1.2, "source_kinetic_energy_correction": 1, "sink_kinetic_energy_correction": 1,
            "applicability": "Test-only supplied stationary incompressible water model and specified equal-tee family",
            "fixed_flow_control_assumption": "Both downstream test flows prescribed by external controls",
            "friction_convention": "DARCY", "elbow_loss_reference": "EXCESS_LOCAL_LOSS_EXCLUDING_CURVED_PIPE_FRICTION",
            "tee_loss_reference": "INLET_VELOCITY_TOTAL_IRREVERSIBLE_LOSS", "boundary_loss_scope": "BETWEEN_PHYSICAL_NETWORK_PORTS_ONLY"}}


def flow_result(raw=None, lengths=None, positions=None):
    scenario = SharedNetworkScenario.model_validate(raw or network_scenario())
    lengths = lengths or {"trunk": Fraction(4, 5), "junction": Fraction(3, 5), "arm-a": Fraction(4, 5), "arm-b": Fraction(4, 5)}
    positions = positions or {"source": [-1, 4, 3], "sinks": {"sink-a": [1, 4, 3], "sink-b": [0, 5, 3]}}
    return evaluate_network_flow(scenario, scenario.network_alternatives[0], lengths, positions)


def interval_contains(value, expected):
    return Fraction(value["lower"]) <= expected <= Fraction(value["upper"])


def test_tree_and_request_round_trip_preserve_every_oriented_path():
    model = SharedNetworkScenario.model_validate(network_scenario())
    assert SharedNetworkScenario.model_validate(model.model_dump(mode="json", by_alias=True)) == model
    tree = model.network_alternatives[0]
    assert len(tree.components) == 4
    assert sum(s.component == "trunk" for p in tree.demand_paths for s in p.steps) == 2
    assert len({c.id for c in tree.components}) == 4


@pytest.mark.parametrize("mutation", [
    lambda n: n["components"].append(copy.deepcopy(n["components"][0])),
    lambda n: n["connections"].append(copy.deepcopy(n["connections"][0])),
    lambda n: n["connections"].pop(),
    lambda n: n["demand_paths"][1]["steps"].pop(0),
    lambda n: n["demand_paths"][1]["steps"][1].update(exit_port="b"),
    lambda n: n["demand_paths"][1].update(demand_id="demand-a"),
    lambda n: n["components"][1]["ports"].update(branch="SINK"),
    lambda n: n["components"][1]["geometry"].update(trunk_takeout_m=.01),
    lambda n: n["components"][1]["geometry"]["frame_m"][0].__setitem__(0, -1),
    lambda n: n["components"][3].update(diameter_m=.12),
    lambda n: n["components"][3]["geometry"].update(start_m=[0, 4.4, 3]),
    lambda n: n.update(source_to_federation_matrix=[[1, 0, 0, 50], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]),
])
def test_malformed_or_unfaithful_tree_is_rejected(mutation):
    raw = network_spec()
    mutation(raw)
    with pytest.raises(ValidationError):
        NetworkDesign.model_validate(raw)


def test_alternative_cannot_move_fixed_sink_or_weaken_section():
    raw = network_scenario()
    raw["network_alternatives"][0]["components"][3]["geometry"]["end_m"] = [0, 5.2, 3]
    with pytest.raises(ValidationError, match="fixed sink"):
        SharedNetworkScenario.model_validate(raw)
    raw = network_scenario()
    for c in raw["network_alternatives"][0]["components"]:
        c["diameter_m"] = .11
    with pytest.raises(ValidationError, match="fixed circular section"):
        SharedNetworkScenario.model_validate(raw)


def test_shared_trunk_carries_sum_once_and_each_branch_keeps_its_flow():
    result = flow_result()
    assert result["verdict"] == "PASS"
    assert result["source_flow_m3_s"] == "3/1000"
    assert result["components"]["trunk"]["flow_m3_s"] == {"a": "3/1000", "b": "3/1000"}
    assert result["components"]["junction"]["flow_m3_s"] == {"a": "3/1000", "b": "1/1000", "branch": "1/500"}
    assert result["components"]["arm-a"]["flow_m3_s"]["a"] == "1/1000"
    assert result["unique_physical_components"] == 4
    assert all(v["status"] == "PASS" for v in result["connections"])
    assert result["operating_point_solution"] == "NOT_ESTABLISHED"


def test_trunk_velocity_can_fail_while_individual_branches_pass():
    raw = network_scenario()
    raw["physics"]["maximum_velocity_m_s"] = .3
    result = flow_result(raw)
    assert result["verdict"] == "FAIL"
    assert result["components"]["trunk"]["checks"]["a"] == "FAIL"
    assert result["components"]["arm-a"]["checks"]["a"] == "PASS"
    assert result["components"]["arm-b"]["checks"]["a"] == "PASS"


def test_tee_friction_is_not_double_counted_and_branch_loss_uses_inlet_flow():
    result = flow_result()
    modified = flow_result(lengths={"trunk": Fraction(4, 5), "junction": 100, "arm-a": Fraction(4, 5), "arm-b": Fraction(4, 5)})
    assert result["paths"] == modified["paths"]
    straight = result["paths"]["sink-a"]["terms"][1]["loss_pa"]
    branch = result["paths"]["sink-b"]["terms"][1]["loss_pa"]
    assert Fraction(branch["lower"]) == 6 * Fraction(straight["lower"])
    assert Fraction(branch["upper"]) == 6 * Fraction(straight["upper"])


def test_static_pressure_includes_elevation_and_kinetic_energy_change():
    result = flow_result()
    for record in result["paths"].values():
        assert Fraction(record["kinetic_pressure_pa"]["upper"]) < 0
    elevated = flow_result(positions={"source": [-1, 4, 3], "sinks": {"sink-a": [1, 4, 4], "sink-b": [0, 5, 3]}})
    assert interval_contains(elevated["paths"]["sink-a"]["elevation_pressure_pa"], Fraction("9806.65"))
    assert elevated["paths"]["sink-a"]["status"] == "FAIL"
    assert elevated["paths"]["sink-b"] == result["paths"]["sink-b"]


def test_missing_service_values_and_native_coverage_remain_blocked():
    raw = network_scenario()
    raw["sinks"][1].pop("required_flow_m3_s")
    assert flow_result(raw)["verdict"] == "BLOCKED"
    scenario = SharedNetworkScenario.model_validate(network_scenario())
    result = evaluate_network_flow(scenario, scenario.network_alternatives[0], {"trunk": 1}, None)
    assert result["verdict"] == "BLOCKED"
    assert "complete_native_component_lengths" in result["missing"]


def test_loss_and_profile_conventions_are_explicit_not_defaulted():
    raw = network_scenario()
    raw["physics"].pop("source_kinetic_energy_correction")
    with pytest.raises(ValidationError):
        SharedNetworkScenario.model_validate(raw)
    raw = network_scenario()
    raw["physics"]["friction_convention"] = "FANNING"
    with pytest.raises(ValidationError):
        SharedNetworkScenario.model_validate(raw)
