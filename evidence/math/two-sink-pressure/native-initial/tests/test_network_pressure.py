"""Independent algebra and contract checks for the native two-outlet adapter."""
import copy
from decimal import Decimal, localcontext
from fractions import Fraction

import pytest
from pydantic import ValidationError

from oma.optimization.physical import Interval
from oma.routing.network_pressure import derive_two_sink_pressure_model, evaluate_pressure_network, partition_two_sink_tree
from oma.routing.network_scenario import SharedNetworkScenario, network_requirements
from oma.store import digest
from test_network_scenario import network_scenario


def pressure_scenario():
    raw = network_scenario()
    physics = raw.pop("physics")
    for key in ("source_kinetic_energy_correction", "sink_kinetic_energy_correction", "fixed_flow_control_assumption"):
        physics.pop(key)
    physics.update(source_total_pressure_pa=100., sink_total_pressures_pa={"sink-a": 0., "sink-b": 0.},
        tee_branch_loss_coefficient=.2, pressure_reference="TOTAL_PRESSURE_P_PLUS_KINETIC_EXCLUDING_ELEVATION",
        loss_model="FIXED_COEFFICIENT_STEADY_INCOMPRESSIBLE", boundary_control_assumption="Test-only regulated total pressures at the three physical ports")
    raw["pressure_driven"] = physics
    for sink in raw["sinks"]:
        sink.pop("available_static_pressure_pa")
    return raw


def metrics():
    return ({"trunk": Fraction(4, 5), "junction": Fraction(3, 5), "arm-a": Fraction(4, 5), "arm-b": Fraction(4, 5)},
            {"source": [-1, 4, 3], "sinks": {"sink-a": [1, 4, 3], "sink-b": [0, 5, 3]}})


def evaluate(raw=None, *, lengths=None, positions=None, checkpoint=None):
    scenario = SharedNetworkScenario.model_validate(raw or pressure_scenario())
    default_lengths, default_positions = metrics()
    return evaluate_pressure_network(scenario, scenario.network_alternatives[0],
        default_lengths if lengths is None else lengths, default_positions if positions is None else positions,
        context={"native-test-case": "explicit synthetic metric enclosures"}, checkpoint=checkpoint)


def test_optional_pressure_mode_preserves_frozen_original_fixed_flow_hashes():
    scenario = SharedNetworkScenario.model_validate(network_scenario())
    assert "pressure_driven" not in scenario.model_dump(mode="json", by_alias=True)
    assert digest(scenario.model_dump(mode="json", by_alias=True)) == "325e42b8438567c3593814d0c8cc0684b86c994ff5e81b2030347dad2275d864"
    assert network_requirements({}, scenario)[0]["rule_hash"] == "1285d1b13298c90be97861a85d56c4d74fcadd8b0a036217eecc80046b0e9915"


def test_pressure_mode_roundtrip_and_rule_bind_every_boundary_and_minimum():
    raw = pressure_scenario()
    first = SharedNetworkScenario.model_validate(raw)
    assert SharedNetworkScenario.model_validate(first.model_dump(mode="json", by_alias=True)) == first
    root = network_requirements({}, first)[0]["rule_hash"]
    raw["pressure_driven"]["sink_total_pressures_pa"]["sink-b"] = 1.
    assert network_requirements({}, SharedNetworkScenario.model_validate(raw))[0]["rule_hash"] != root


@pytest.mark.parametrize("fault", ["fixed_physics", "static_budget", "missing_sink", "missing_minimum", "wrong_service", "geometry_only", "nan", "bool_pressure"])
def test_pressure_boundaries_cannot_silently_reinterpret_other_contracts(fault):
    raw = pressure_scenario()
    if fault == "fixed_physics": raw["physics"] = network_scenario()["physics"]
    if fault == "static_budget": raw["sinks"][0]["available_static_pressure_pa"] = 100
    if fault == "missing_sink": raw["pressure_driven"]["sink_total_pressures_pa"].pop("sink-a")
    if fault == "missing_minimum": raw["sinks"][0]["required_flow_m3_s"] = None
    if fault == "wrong_service": raw["system_type"] = "ROUND_DUCT"
    if fault == "geometry_only": raw["target_modality"] = "LOCAL_GEOMETRIC_COORDINATION"
    if fault == "nan": raw["pressure_driven"]["source_total_pressure_pa"] = float("nan")
    if fault == "bool_pressure": raw["pressure_driven"]["source_total_pressure_pa"] = True
    with pytest.raises(ValidationError): SharedNetworkScenario.model_validate(raw)


def test_partition_and_coefficients_count_trunk_once_and_do_not_charge_tee_darcy():
    scenario = SharedNetworkScenario.model_validate(pressure_scenario())
    lengths, positions = metrics()
    model, derivation = derive_two_sink_pressure_model(scenario, scenario.network_alternatives[0], lengths, positions, context={"test": "partition"})
    assert derivation["partition"] == {"tee": "junction", "common_trunk": ["trunk"],
        "branches": {"sink-a": ["arm-a"], "sink-b": ["arm-b"]},
        "tee_exit_ports": {"sink-a": "b", "sink-b": "branch"},
        "component_ids": ["arm-a", "arm-b", "junction", "trunk"]}
    for key, value in {"A1": Fraction(9, 25), "A2": Fraction(9, 25), "B1": Fraction(4, 25), "B2": Fraction(4, 25), "P1": Fraction(100), "P2": Fraction(100)}.items():
        assert model["parameters"][key] == {"lower": str(value), "upper": str(value)}
    lengths["junction"] = Fraction(1000)
    second, _ = derive_two_sink_pressure_model(scenario, scenario.network_alternatives[0], lengths, positions, context={"test": "partition"})
    assert second["parameters"] == model["parameters"]
    assert second["physical_model_root"] != model["physical_model_root"]


def test_symmetric_network_encloses_independent_closed_form_and_all_port_checks():
    result = evaluate()
    assert result["operating_point_status"] == result["verdict"] == "PASS", result
    assert result["unique_physical_components"] == 4
    assert sum(map(len, result["component_velocities"].values())) == 9
    with localcontext() as context:
        context.prec = 65
        pi = Decimal("3.1415926535897932384626433832795028841971693993751058209749445923078")
        area = pi / 400
        # Exact symmetric relation: t=1/2, common+tee=.36, branch=.16.
        reference = (Decimal(100) * 2 * area * area / (Decimal(1000) * Decimal(".4"))).sqrt() / 2
        bounds = result["deliveries"]["sink-a"]["flow_m3_s"]
        convert = lambda s: Decimal(Fraction(s).numerator) / Decimal(Fraction(s).denominator)
        assert convert(bounds["lower"]) <= reference <= convert(bounds["upper"])
    assert all(v["status"] == "PASS" for v in result["deliveries"].values())


def test_native_metric_uncertainty_is_retained_in_pressure_and_delivery_bounds():
    lengths, positions = metrics()
    positions["sinks"]["sink-a"][2] = Interval(Fraction(2999999, 1000000), Fraction(3000001, 1000000))
    scenario = SharedNetworkScenario.model_validate(pressure_scenario())
    model, _ = derive_two_sink_pressure_model(scenario, scenario.network_alternatives[0], lengths, positions, context={"test": "elevation"})
    assert Fraction(model["parameters"]["P1"]["lower"]) < 100 < Fraction(model["parameters"]["P1"]["upper"])
    result = evaluate(lengths=lengths, positions=positions)
    assert result["verdict"] == "PASS", result


@pytest.mark.parametrize("fault", ["minimum", "velocity"])
def test_a_valid_operating_point_can_fail_delivery_or_trunk_velocity(fault):
    raw = pressure_scenario()
    if fault == "minimum": raw["sinks"][0]["required_flow_m3_s"] = .004
    else: raw["pressure_driven"]["maximum_velocity_m_s"] = .5
    result = evaluate(raw)
    assert result["operating_point_status"] == "PASS" and result["verdict"] == "FAIL", result
    if fault == "minimum": assert result["deliveries"]["sink-a"]["status"] == "FAIL"
    else:
        assert result["component_velocities"]["trunk"]["a"]["status"] == "FAIL"
        assert result["component_velocities"]["arm-a"]["a"]["status"] == "PASS"


def test_missing_native_component_is_blocked_and_adverse_elevation_is_not_a_zero_flow():
    lengths, positions = metrics()
    lengths.pop("arm-b")
    result = evaluate(lengths=lengths)
    assert result["verdict"] == "BLOCKED" and result["operating_point_status"] == "NOT_ESTABLISHED"
    positions["sinks"]["sink-a"][2] = 4
    result = evaluate(positions=positions)
    assert result["verdict"] in {"BLOCKED", "UNKNOWN"} and result["operating_point_status"] == "NOT_ESTABLISHED"
    assert "deliveries" not in result


def test_callback_exception_propagates_before_any_operating_claim():
    error = ValueError("caller interrupted pressure analysis")
    def stop(stage): raise error
    with pytest.raises(ValueError) as caught: evaluate(checkpoint=stop)
    assert caught.value is error
