from fractions import Fraction as F
import copy
import pytest

from oma.optimization.physical import (Interval, pi_interval, sqrt_interval, circular_section,
    rectangular_section, evaluate_fluid_path, select_fluid_catalog, evaluate_electrical_path,
    check_conservation, aggregate_tree_flows, solve_gravity_elevations, verify_gravity_result)


def fluid_parameters(**changes):
    return dict(length_m=10, flow_m3_s=F(1, 10), density_kg_m3=F(6, 5), darcy_friction=F(2, 100),
                fitting_loss_coefficient=2, maximum_velocity_m_s=5, available_pressure_pa=100,
                efficiency=F(7, 10)) | changes


def test_exact_enclosures_and_zero_division():
    pi = pi_interval()
    assert pi.lo < F("3.14159265358979323846264338327950288419716939937511")
    assert pi.hi > F("3.14159265358979323846264338327950288419716939937510")
    root = sqrt_interval(3)
    assert root.lo**2 <= 3 <= root.hi**2
    assert Interval(-2, 3).square() == Interval(0, 9)
    with pytest.raises(ValueError):
        Interval.point(1) / Interval(-1, 1)


def test_fixed_duct_pressure_and_missing_inputs():
    section = rectangular_section("duct", F(1, 5), F(1, 5), insulation_m=F(1, 50), cost_per_m=20)
    result = evaluate_fluid_path(section=section, **fluid_parameters())
    assert result["verdict"] == "PASS"
    assert result["pressure_drop_pa"] == Interval.point(F(45, 4)).encoded()
    assert result["geometry"] == "NOT_RUN"
    missing = evaluate_fluid_path(section=section, **fluid_parameters(darcy_friction=None))
    assert missing["verdict"] == "UNKNOWN"
    assert "darcy_friction" in missing["missing"]


def test_joint_size_and_envelope_prevents_monotone_size_shortcut():
    options = [rectangular_section("small", F(1, 10), F(1, 10), insulation_m=0, cost_per_m=1),
               rectangular_section("medium", F(1, 5), F(1, 5), insulation_m=0, cost_per_m=2),
               rectangular_section("large", F(1, 2), F(1, 2), insulation_m=0, cost_per_m=3)]
    result = select_fluid_catalog(options, geometry_check=lambda s: "PASS" if s.envelope_width_m <= F(3, 10) else "FAIL", **fluid_parameters())
    assert result["selected"] == "medium" and result["status"] == "CATALOG_OPTIMAL"
    assert {r["section"]: r["verdict"] for r in result["options"]} == {"small": "FAIL", "medium": "PASS", "large": "FAIL"}
    unknown = select_fluid_catalog(options, geometry_check=lambda s: "UNKNOWN", **fluid_parameters())
    assert unknown["status"] == "UNKNOWN"


def test_insulation_is_part_of_envelope_and_uncertain_pressure_is_unknown():
    pipe = circular_section("pipe", F(1, 10), insulation_m=F(1, 50), cost_per_m=2)
    assert pipe.envelope_width_m == F(14, 100)
    duct = rectangular_section("duct", F(1, 5), F(1, 5), insulation_m=0, cost_per_m=1)
    result = evaluate_fluid_path(section=duct, **fluid_parameters(darcy_friction=Interval(0, 1), available_pressure_pa=30))
    assert result["checks"]["pressure"] == "UNKNOWN"


def test_electrical_fixed_impedance_model_and_negative_control():
    args = dict(current_a=10, resistance_ohm=F(1, 10), reactance_ohm=0, cos_phi=1,
                ampacity_a=20, voltage_drop_limit_v=2, tray_fill=F(1, 5), maximum_tray_fill=F(2, 5))
    result = evaluate_electrical_path(**args)
    assert result["verdict"] == "PASS" and result["resistive_loss_w"] == "30"
    assert evaluate_electrical_path(**(args | {"ampacity_a": 9}))["verdict"] == "FAIL"
    assert evaluate_electrical_path(**(args | {"ampacity_a": None}))["verdict"] == "UNKNOWN"


def test_shared_trunk_aggregate_and_correct_conservation_sign():
    routed = aggregate_tree_flows("source", [("source", "tee"), ("tee", "a"), ("tee", "b")], {"a": 2, "b": 3})
    assert routed["edge_flows"][("source", "tee")] == 5
    edges = [(u, v, f) for (u, v), f in routed["edge_flows"].items()]
    injections = {"source": 5, "tee": 0, "a": -2, "b": -3}
    assert check_conservation(edges, injections)["verdict"] == "PASS"
    assert check_conservation(edges, {k: -v for k, v in injections.items()})["verdict"] == "FAIL"
    assert check_conservation(edges, {"source": 5})["verdict"] == "UNKNOWN"
    with pytest.raises(ValueError):
        aggregate_tree_flows("source", [("source", "a")], {"a": 2, "disconnected": 1})


def test_gravity_exact_feasibility_and_forged_export_rejected():
    nodes = ["a", "b", "c"]
    edges = [("a", "b", 10, F(1, 100), F(2, 100)), ("b", "c", 10, F(1, 100), F(2, 100))]
    bounds = {"a": (3, 3), "b": (F(28, 10), F(29, 10)), "c": (F(26, 10), F(28, 10))}
    result = solve_gravity_elevations(nodes, edges, bounds)
    assert result["status"] == "FEASIBLE"
    assert verify_gravity_result(result, nodes, edges, bounds) == "PASS"
    forged = copy.deepcopy(result)
    forged["elevations_m"]["c"] = "4"
    assert verify_gravity_result(forged, nodes, edges, bounds) == "FAIL"
    forged = copy.deepcopy(result)
    forged["constraints"] = []
    assert verify_gravity_result(forged, nodes, edges, bounds) == "FAIL"


def test_gravity_positive_cycle_gets_independently_checked_negative_cycle():
    nodes = ["a", "b"]
    edges = [("a", "b", 10, F(1, 100), F(2, 100)), ("b", "a", 10, F(1, 100), F(2, 100))]
    bounds = {"a": (0, 10), "b": (0, 10)}
    result = solve_gravity_elevations(nodes, edges, bounds)
    assert result["status"] == "INFEASIBLE"
    assert verify_gravity_result(result, nodes, edges, bounds) == "PASS"
    result["negative_cycle"] = []
    assert verify_gravity_result(result, nodes, edges, bounds) == "FAIL"
