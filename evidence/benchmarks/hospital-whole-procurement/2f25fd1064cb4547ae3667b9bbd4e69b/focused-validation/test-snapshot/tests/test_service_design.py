from fractions import Fraction as F
import copy
import json

import pytest

from oma.optimization.service_design import screen_service_catalog, SUPPORTED_SERVICES


def fluid_requirements(**updates):
    return dict(length_m=10, flow_m3_s="1/10", density_kg_m3="6/5",
                maximum_velocity_m_s=5, available_pressure_pa=100) | updates


def option(identifier="a", cost=1, **updates):
    return dict(id=identifier, total_cost=cost, material_applicability="Specified material under declared fluid/temperature",
                installation_applicability="Declared installation and coefficient applicability",
                section={"shape": "rectangular", "width_m": "1/5", "height_m": "1/5", "insulation_m": "1/50"},
                parameters={"darcy_friction": "1/50", "fitting_loss_coefficient": 2, "efficiency": "7/10"}) | updates


def test_rectangular_model_exact_reference_and_quantitative_margins():
    result = screen_service_catalog("HVAC_DUCT", [option()], fluid_requirements(), catalogue_complete=True)
    row = result["options"][0]
    assert row["verdict"] == "PASS"
    assert row["metrics"]["pressure_drop_pa"]["lower"] == "45/4"
    assert row["margins"]["pressure_pa"]["lower"] == "355/4"
    assert row["margins"]["velocity_m_s"]["lower"] == "5/2"
    assert row["metrics"]["envelope_width_m"] == "6/25"
    assert result["status"] == "CATALOG_OPTIMAL" and result["objective"] == "1"
    assert result["geometry"] == "NOT_RUN" and result["whole_building_adequacy"] == "NOT_CHECKED"
    assert result["code_compliance"] == "NOT_CHECKED"
    json.dumps(result)


@pytest.mark.parametrize("service", ["HVAC_DUCT", "PRESSURE_PIPE", "FIRE_PROTECTION"])
def test_round_diameter_feasibility_and_price_tradeoff(service):
    small = option("small", "1/10", section={"shape": "circular", "diameter_m": "1/10", "insulation_m": 0})
    large = option("large", 5, section={"shape": "circular", "diameter_m": "1/5", "insulation_m": 0})
    result = screen_service_catalog(service, [small, large], fluid_requirements(), catalogue_complete=True)
    assert result["selected"] == "large" and result["status"] == "CATALOG_OPTIMAL"
    rows = {r["id"]: r for r in result["options"]}
    assert rows["small"]["verdict"] == "FAIL"
    assert F(rows["small"]["margins"]["velocity_m_s"]["upper"]) < 0
    assert rows["large"]["verdict"] == "PASS"
    assert result["fire_hazard_and_protection_design"] == "NOT_CHECKED"


def test_missing_fixed_demand_and_applicability_remain_unknown():
    result = screen_service_catalog("HVAC_DUCT", [option(material_applicability=" ")],
                                    fluid_requirements(flow_m3_s=None), catalogue_complete=True)
    assert result["status"] == "UNKNOWN" and result["selected"] is None
    assert set(result["options"][0]["missing"]) == {"requirements.flow_m3_s", "material_applicability"}
    assert result["price_optimization_complete"] is False


def test_no_option_may_override_fixed_service_demand_or_ignore_constraints():
    bad = option()
    bad["parameters"]["flow_m3_s"] = 0
    with pytest.raises(ValueError, match="Unsupported option parameters"):
        screen_service_catalog("HVAC_DUCT", [bad], fluid_requirements())
    with pytest.raises(ValueError, match="Unsupported requirements"):
        screen_service_catalog("HVAC_DUCT", [option()], fluid_requirements(minimum_fire_pressure_pa=1000))


@pytest.mark.parametrize("field", ["darcy_friction", "fitting_loss_coefficient", "efficiency"])
def test_missing_fluid_material_coefficients_unknown(field):
    candidate = option()
    del candidate["parameters"][field]
    result = screen_service_catalog("HVAC_DUCT", [candidate], fluid_requirements())
    assert result["options"][0]["verdict"] == "UNKNOWN"
    assert "parameters." + field in result["options"][0]["missing"]


def test_complete_prices_and_dispositions_and_declared_universe_required():
    known = option("known", 10)
    for unknown in (option("unknown", 1, installation_applicability=None), option("unknown", None)):
        result = screen_service_catalog("HVAC_DUCT", [known, unknown], fluid_requirements(), catalogue_complete=True)
        assert result["status"] == "CATALOG_FEASIBLE"
        assert result["selected"] == "known" and not result["price_optimization_complete"]
    unpriced_fail = option("bad", None, section={"shape": "circular", "diameter_m": "1/100", "insulation_m": 0})
    result = screen_service_catalog("HVAC_DUCT", [known, unpriced_fail], fluid_requirements(), catalogue_complete=True)
    assert result["all_options_disposed"] and not result["all_candidate_prices_known"]
    assert result["status"] == "CATALOG_FEASIBLE"
    assert screen_service_catalog("HVAC_DUCT", [known], fluid_requirements())["status"] == "CATALOG_FEASIBLE"


def test_finite_infeasible_is_not_unrestricted_infeasible_and_ties_are_stable():
    bad = option(section={"shape": "circular", "diameter_m": "1/100", "insulation_m": 0})
    assert screen_service_catalog("PRESSURE_PIPE", [bad], fluid_requirements())["status"] == "UNKNOWN"
    complete = screen_service_catalog("PRESSURE_PIPE", [bad], fluid_requirements(), catalogue_complete=True)
    assert complete["status"] == "CATALOG_INFEASIBLE"
    assert complete["scope"] == "SUPPLIED_FINITE_CATALOGUE_DECLARED_SERVICE_MODEL_ONLY"
    for choices in ([option("b", "1/3"), option("a", "1/3")], [option("a", "1/3"), option("b", "1/3")]):
        assert screen_service_catalog("HVAC_DUCT", choices, fluid_requirements(), catalogue_complete=True)["selected"] == "a"


def gravity_option(**changes):
    return option(section={"shape": "prescribed_open_channel", "flow_area_m2": 8, "wetted_perimeter_m": 1,
                           "hydraulic_section_applicability": "Explicit wetted area/perimeter at declared design condition"},
                  parameters={"manning_n_s_per_m_third": "1/10"}) | changes


def gravity_requirements(**changes):
    return dict(flow_m3_s=32, slope_m_m="1/100", minimum_slope_m_m="1/200", maximum_slope_m_m="1/50") | changes


def test_manning_exact_analytic_capacity_and_slope_boundary():
    result = screen_service_catalog("GRAVITY_DRAINAGE", [gravity_option()], gravity_requirements(), catalogue_complete=True)
    row = result["options"][0]
    assert row["verdict"] == "PASS"
    assert row["metrics"]["capacity_m3_s"]["lower"] == row["metrics"]["capacity_m3_s"]["upper"] == "32"
    assert row["margins"]["capacity_m3_s"]["lower"] == "0"
    failed = screen_service_catalog("GRAVITY_DRAINAGE", [gravity_option()], gravity_requirements(minimum_slope_m_m="3/200"))
    assert failed["options"][0]["margins"]["minimum_slope_m_m"]["verdict"] == "FAIL"


def test_manning_irrational_capacity_enclosure_by_independent_sixth_power():
    candidate = gravity_option()
    candidate["section"].update(flow_area_m2="1/20", wetted_perimeter_m="1/2")
    candidate["parameters"]["manning_n_s_per_m_third"] = "13/1000"
    result = screen_service_catalog("GRAVITY_DRAINAGE", [candidate], gravity_requirements(flow_m3_s="1/20"))
    capacity = result["options"][0]["metrics"]["capacity_m3_s"]
    exact_sixth_power = (F(1, 20) / F(13, 1000))**6 * F(1, 10)**4 * F(1, 100)**3
    assert F(capacity["lower"])**6 <= exact_sixth_power <= F(capacity["upper"])**6
    assert result["options"][0]["verdict"] == "PASS"


def test_missing_gravity_regime_or_roughness_is_unknown_without_inferred_fill():
    candidate = gravity_option()
    del candidate["section"]["hydraulic_section_applicability"]
    candidate["parameters"] = {}
    result = screen_service_catalog("GRAVITY_DRAINAGE", [candidate], gravity_requirements())
    assert result["options"][0]["verdict"] == "UNKNOWN"
    assert set(result["options"][0]["missing"]) == {"section.hydraulic_section_applicability", "parameters.manning_n_s_per_m_third"}


def test_manning_numerical_boundary_cannot_be_promoted_to_feasible():
    candidate = gravity_option()
    candidate["section"].update(flow_area_m2=1, wetted_perimeter_m=2)
    candidate["parameters"]["manning_n_s_per_m_third"] = 1
    req = gravity_requirements(slope_m_m=1, minimum_slope_m_m=0, maximum_slope_m_m=2,
                               flow_m3_s="1259921049894873164767211/2000000000000000000000000")
    result = screen_service_catalog("GRAVITY_DRAINAGE", [candidate], req, catalogue_complete=True)
    assert result["options"][0]["margins"]["capacity_m3_s"]["verdict"] == "UNKNOWN"
    assert result["status"] == "UNKNOWN" and result["selected"] is None
    req = gravity_requirements(minimum_slope_m_m=10**110)
    del req["maximum_slope_m_m"]
    missing = screen_service_catalog("GRAVITY_DRAINAGE", [candidate], req)
    assert "requirements.maximum_slope_m_m" in missing["options"][0]["missing"]


def electrical_option(**updates):
    return option(section={}, parameters={"resistance_ohm": "1/10", "reactance_ohm": 0, "ampacity_a": 20, "tray_fill": "1/5"}) | updates


def test_balanced_three_phase_explicit_regime_and_independent_voltage_bound():
    requirements = dict(current_a=10, cos_phi=1, voltage_drop_limit_v=2, maximum_tray_fill="2/5")
    result = screen_service_catalog("ELECTRICAL", [electrical_option()], requirements, catalogue_complete=True)
    row = result["options"][0]
    drop = row["metrics"]["voltage_drop_v"]
    assert F(drop["lower"])**2 <= 3 <= F(drop["upper"])**2
    assert row["metrics"]["resistive_loss_w"] == "30"
    assert row["margins"]["ampacity_a"]["lower"] == "10"
    assert row["verdict"] == "PASS"
    assert result["assumptions"]["electrical_regime"] == "BALANCED_THREE_PHASE"
    requirements["current_a"] = 21
    assert screen_service_catalog("ELECTRICAL", [electrical_option()], requirements)["options"][0]["verdict"] == "FAIL"


@pytest.mark.parametrize("service", ["ELECTRICAL_DC", "FIRE_ALARM_DC"])
def test_dc_full_loop_no_conductor_multiplier_and_negative_controls(service):
    candidate = option(section={}, parameters={"loop_resistance_ohm": "3/2", "ampacity_a": 3})
    req = {"current_a": 2, "voltage_drop_limit_v": 3}
    row = screen_service_catalog(service, [candidate], req)["options"][0]
    assert row["metrics"]["voltage_drop_v"]["lower"] == "3"
    assert row["metrics"]["resistive_loss_w"] == "6"
    assert row["verdict"] == "PASS" and row["margins"]["voltage_drop_v"]["lower"] == "0"
    assert screen_service_catalog(service, [candidate], req | {"voltage_drop_limit_v": "299/100"})["options"][0]["verdict"] == "FAIL"
    with pytest.raises(ValueError, match="nonnegative"):
        screen_service_catalog(service, [candidate], req | {"current_a": -1})
    assert screen_service_catalog(service, [candidate], {"current_a": 2})["options"][0]["verdict"] == "UNKNOWN"
    candidate["parameters"] = {"resistance_ohm": "3/2", "ampacity_a": 3}
    with pytest.raises(ValueError, match="Unsupported option parameters"):
        screen_service_catalog(service, [candidate], req)


@pytest.mark.parametrize("bad", [True, "NaN", float("inf"), "1/0", "1" * 257, 1 << 2049])
def test_invalid_or_unbounded_numeric_inputs_are_rejected(bad):
    with pytest.raises(ValueError):
        screen_service_catalog("HVAC_DUCT", [option()], fluid_requirements(flow_m3_s=bad))


def test_invalid_domains_schema_and_catalogue_budget():
    with pytest.raises(ValueError):
        screen_service_catalog("STRUCTURAL", [option()], {})
    with pytest.raises(ValueError, match="shape"):
        screen_service_catalog("FIRE_PROTECTION", [option()], fluid_requirements())
    with pytest.raises(ValueError, match="unique"):
        screen_service_catalog("HVAC_DUCT", [option(), option()], fluid_requirements())
    with pytest.raises(ValueError, match="budget"):
        screen_service_catalog("HVAC_DUCT", [option("a"), option("b")], fluid_requirements(), max_options=1)
    with pytest.raises(ValueError, match="boolean"):
        screen_service_catalog("HVAC_DUCT", [option()], fluid_requirements(), catalogue_complete=1)
    with pytest.raises(ValueError, match="Slope bounds"):
        screen_service_catalog("GRAVITY_DRAINAGE", [gravity_option()], gravity_requirements(minimum_slope_m_m=1))
    with pytest.raises(ValueError, match="nonnegative"):
        screen_service_catalog("ELECTRICAL_DC", [option(section={}, parameters={"loop_resistance_ohm": -1, "ampacity_a": 1})],
                               {"current_a": 1, "voltage_drop_limit_v": 1})


def test_inputs_untouched_and_services_exposed_for_job_validation():
    choices, requirements = [option()], fluid_requirements()
    before = copy.deepcopy((choices, requirements))
    screen_service_catalog("HVAC_DUCT", choices, requirements, context_root="test-fixed-model")
    assert (choices, requirements) == before
    assert {"FIRE_ALARM_DC", "ELECTRICAL_DC", "GRAVITY_DRAINAGE", "ELECTRICAL"} <= SUPPORTED_SERVICES
