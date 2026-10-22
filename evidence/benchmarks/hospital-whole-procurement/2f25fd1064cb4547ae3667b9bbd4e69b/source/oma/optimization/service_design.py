"""Bounded finite catalogue screening under explicit, supplied SI service models.

This module does not derive building demands, material applicability, hydraulic
regimes, installation derating, hazard classifications or code approval. A PASS
means the declared model inequalities pass. Geometry and whole-building authority
are separate. Prices are explicit total candidate prices in one declared unit.

Fluid paths reuse the fixed-flow Darcy model. ELECTRICAL means balanced three
phase with supplied full-path impedance. DC services use supplied full-loop
resistance. Manning uses an explicitly supplied wetted section at its declared
design condition, steady uniform flow, and SI Q=A/n*(A/P)^(2/3)*sqrt(S).
Reference: https://www.hec.usace.army.mil/confluence/rasdocs/d2sd/ras2dsedtr/6.5/
numerical-methods/face-hydraulic-properties
"""
from __future__ import annotations

from fractions import Fraction
from typing import Mapping

from .master import rational
from .physical import (Interval, circular_section, rectangular_section,
                       evaluate_fluid_path, evaluate_electrical_path,
                       combine_verdicts, sqrt_interval)


SUPPORTED_SERVICES = frozenset({"HVAC_DUCT", "PRESSURE_PIPE", "FIRE_PROTECTION",
                                "GRAVITY_DRAINAGE", "ELECTRICAL", "ELECTRICAL_DC", "FIRE_ALARM_DC"})
_FLUID = {"HVAC_DUCT", "PRESSURE_PIPE", "FIRE_PROTECTION"}
_DC = {"ELECTRICAL_DC", "FIRE_ALARM_DC"}
_REQUIREMENTS = {
    **{s: ("length_m", "flow_m3_s", "density_kg_m3", "maximum_velocity_m_s", "available_pressure_pa") for s in _FLUID},
    "GRAVITY_DRAINAGE": ("flow_m3_s", "slope_m_m", "minimum_slope_m_m", "maximum_slope_m_m"),
    "ELECTRICAL": ("current_a", "cos_phi", "voltage_drop_limit_v", "maximum_tray_fill"),
    **{s: ("current_a", "voltage_drop_limit_v") for s in _DC},
}
_PARAMETERS = {
    **{s: ("darcy_friction", "fitting_loss_coefficient", "efficiency") for s in _FLUID},
    "GRAVITY_DRAINAGE": ("manning_n_s_per_m_third",),
    "ELECTRICAL": ("resistance_ohm", "reactance_ohm", "ampacity_a", "tray_fill"),
    **{s: ("loop_resistance_ohm", "ampacity_a") for s in _DC},
}
_SECTION_FIELDS = {
    "circular": ("diameter_m", "insulation_m"),
    "rectangular": ("width_m", "height_m", "insulation_m"),
    "prescribed_open_channel": ("flow_area_m2", "wetted_perimeter_m", "hydraulic_section_applicability"),
}
_OPTION_FIELDS = {"id", "section", "parameters", "total_cost", "material_applicability", "installation_applicability"}


def _number(value):
    """Scalar exact inputs with finite encoding/work bounds; booleans are not SI."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Fraction)):
        raise ValueError("SI parameters must be finite scalar numbers or rational strings")
    if isinstance(value, str) and len(value) > 256:
        raise ValueError("Numeric encoding exceeds the 256-character bound")
    try:
        number = rational(value)
    except (ValueError, TypeError, OverflowError, ZeroDivisionError) as exc:
        raise ValueError("Invalid finite rational SI parameter") from exc
    if max(abs(number.numerator).bit_length(), number.denominator.bit_length()) > 2048:
        raise ValueError("SI parameter exceeds the rational input size bound")
    return number


def _label(value):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 4000


def _mapping(value, allowed, name):
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    extra = set(value) - set(allowed)
    if extra:
        raise ValueError(f"Unsupported {name} fields: {', '.join(sorted(map(str, extra)))}")
    return dict(value)


def _numbers(values):
    return {key: _number(value) for key, value in values.items() if value is not None}


def _nonnegative(values):
    if any(v < 0 for v in values.values()):
        raise ValueError("Declared SI parameters must be nonnegative")


def _margin(value):
    if not isinstance(value, Interval):
        value = Interval.point(value)
    return {**value.encoded(), "verdict": "PASS" if value.lo >= 0 else "FAIL" if value.hi < 0 else "UNKNOWN"}


def _decoded(value):
    return Interval(Fraction(value["lower"]), Fraction(value["upper"]))


def _cube_root(value):
    """Outward rational cube-root enclosure at 24 decimal places, integer only."""
    scale = 10**24
    target = value.numerator * scale**3 // value.denominator
    low, high = 0, 1 << ((target.bit_length() + 2) // 3)
    while low < high:
        mid = (low + high + 1) // 2
        if mid**3 <= target:
            low = mid
        else:
            high = mid - 1
    lower = Fraction(low, scale)
    return Interval(lower, lower if lower**3 == value else Fraction(low + 1, scale))


def _screen_model(service, identifier, section, parameters, requirements):
    """All required values have already been accounted for and domain checked."""
    if service in _FLUID:
        numeric = _numbers({k: v for k, v in section.items() if k != "shape"})
        if section["shape"] == "circular":
            chosen = circular_section(identifier, numeric["diameter_m"], insulation_m=numeric["insulation_m"], cost_per_m=0)
        else:
            chosen = rectangular_section(identifier, numeric["width_m"], numeric["height_m"], insulation_m=numeric["insulation_m"], cost_per_m=0)
        result = evaluate_fluid_path(section=chosen, **requirements, **parameters)
        velocity, pressure = _decoded(result["velocity_m_s"]), _decoded(result["pressure_drop_pa"])
        margins = {"velocity_m_s": _margin(Interval.point(requirements["maximum_velocity_m_s"]) - velocity),
                   "pressure_pa": _margin(Interval.point(requirements["available_pressure_pa"]) - pressure)}
        metrics = {k: result[k] for k in ("velocity_m_s", "pressure_drop_pa", "power_w")}
        metrics.update(area_m2=chosen.area_m2.encoded(), hydraulic_diameter_m=chosen.hydraulic_diameter_m.encoded(),
                       envelope_width_m=str(chosen.envelope_width_m), envelope_height_m=str(chosen.envelope_height_m))
        return result["model"], metrics, margins
    if service == "ELECTRICAL":
        result = evaluate_electrical_path(**requirements, **parameters)
        margins = {"ampacity_a": _margin(parameters["ampacity_a"] - requirements["current_a"]),
                   "voltage_drop_v": _margin(Interval.point(requirements["voltage_drop_limit_v"]) - _decoded(result["voltage_drop_v"])),
                   "tray_fill": _margin(requirements["maximum_tray_fill"] - parameters["tray_fill"])}
        return result["model"], {k: result[k] for k in ("voltage_drop_v", "resistive_loss_w")}, margins
    if service in _DC:
        current, resistance = requirements["current_a"], parameters["loop_resistance_ohm"]
        drop, power = current * resistance, current**2 * resistance
        return "DC_prescribed_current_supplied_full_loop_resistance", {
            "voltage_drop_v": Interval.point(drop).encoded(), "resistive_loss_w": str(power)}, {
            "ampacity_a": _margin(parameters["ampacity_a"] - current),
            "voltage_drop_v": _margin(requirements["voltage_drop_limit_v"] - drop)}
    area, perimeter = _number(section["flow_area_m2"]), _number(section["wetted_perimeter_m"])
    radius = area / perimeter
    # Root each positive rational factor monotonically; do not use float powers.
    capacity = area / parameters["manning_n_s_per_m_third"] * _cube_root(radius**2) * sqrt_interval(requirements["slope_m_m"])
    margins = {"capacity_m3_s": _margin(capacity - requirements["flow_m3_s"]),
               "minimum_slope_m_m": _margin(requirements["slope_m_m"] - requirements["minimum_slope_m_m"]),
               "maximum_slope_m_m": _margin(requirements["maximum_slope_m_m"] - requirements["slope_m_m"])}
    return "SI_Manning_prescribed_wetted_section_steady_uniform_flow", {
        "capacity_m3_s": capacity.encoded(), "capacity_velocity_m_s": (capacity / area).encoded(),
        "flow_area_m2": str(area), "wetted_perimeter_m": str(perimeter),
        "hydraulic_radius_m": str(radius), "slope_m_m": str(requirements["slope_m_m"])}, margins


def screen_service_catalog(service, options, requirements, *, catalogue_complete=False,
                           context_root=None, max_options=256):
    """Screen a finite, explicit catalogue without changing fixed requirements.

    Fluid requirements: length_m, flow_m3_s, density_kg_m3,
    maximum_velocity_m_s, available_pressure_pa. Option parameters:
    darcy_friction, fitting_loss_coefficient, efficiency. Sections: circular
    diameter_m or rectangular width_m/height_m; insulation_m is always explicit.

    ELECTRICAL requirements: current_a, cos_phi, voltage_drop_limit_v,
    maximum_tray_fill. Option parameters: resistance_ohm, reactance_ohm,
    ampacity_a, tray_fill. This is the balanced three-phase model only.
    DC requirements: current_a, voltage_drop_limit_v; option parameters:
    loop_resistance_ohm, ampacity_a. Full return-loop resistance is supplied.

    GRAVITY_DRAINAGE requirements: flow_m3_s, slope_m_m, minimum_slope_m_m,
    maximum_slope_m_m. Option parameter: manning_n_s_per_m_third. Section:
    shape='prescribed_open_channel', flow_area_m2, wetted_perimeter_m,
    hydraulic_section_applicability (explicit design-depth/regime description).

    Every option has id, section (except electrical), parameters, total_cost,
    material_applicability and installation_applicability labels. Missing physics
    or labels yields UNKNOWN. Missing cost withholds cost optimality. Caller
    labels remain assumptions, not independent applicability verification.
    Extra fields/invalid domains raise ValueError, avoiding silent constraint loss.
    """
    if not isinstance(service, str) or service not in SUPPORTED_SERVICES:
        raise ValueError("Unsupported service model")
    if type(catalogue_complete) is not bool:
        raise ValueError("catalogue_complete must be an explicit boolean")
    if type(max_options) is not int or not 1 <= max_options <= 1024:
        raise ValueError("Catalogue budget must be in 1..1024")
    if not isinstance(options, (list, tuple)) or not 1 <= len(options) <= max_options:
        raise ValueError("Nonempty catalogue exceeds or lacks the declared option budget")
    if context_root is not None and (not isinstance(context_root, str) or not context_root.strip() or len(context_root) > 1024):
        raise ValueError("context_root must be a bounded nonempty identity")
    requirements = _mapping(requirements, _REQUIREMENTS[service], "requirements")
    req = _numbers(requirements)
    _nonnegative(req)
    if req.get("density_kg_m3", 1) <= 0:
        raise ValueError("Fluid density must be positive")
    if req.get("cos_phi", 0) > 1 or req.get("maximum_tray_fill", 0) > 1:
        raise ValueError("Power factor and tray-fill limits must lie in [0,1]")
    if ("minimum_slope_m_m" in req and "maximum_slope_m_m" in req
            and req["minimum_slope_m_m"] > req["maximum_slope_m_m"]):
        raise ValueError("Slope bounds reversed")
    records, ids = [], set()
    for raw in options:
        option = _mapping(raw, _OPTION_FIELDS, "option")
        identifier = option.get("id")
        if not isinstance(identifier, str) or not identifier.strip() or len(identifier) > 256 or identifier in ids:
            raise ValueError("Catalogue option IDs must be nonempty, bounded and unique")
        ids.add(identifier)
        parameters = _mapping(option.get("parameters", {}), _PARAMETERS[service], "option parameters")
        params = _numbers(parameters)
        _nonnegative(params)
        if not 0 < params.get("efficiency", 1) <= 1 or params.get("manning_n_s_per_m_third", 1) <= 0:
            raise ValueError("Efficiency must lie in (0,1] and Manning roughness must be positive")
        if params.get("tray_fill", 0) > 1:
            raise ValueError("Tray fill must lie in [0,1]")
        missing = ["requirements." + k for k in _REQUIREMENTS[service] if k not in req]
        missing += ["parameters." + k for k in _PARAMETERS[service] if k not in params]
        for key in ("material_applicability", "installation_applicability"):
            if not _label(option.get(key)):
                missing.append(key)
        section = option.get("section", {})
        if not isinstance(section, Mapping):
            raise ValueError("Section must be an object")
        shape = section.get("shape")
        if service in _FLUID or service == "GRAVITY_DRAINAGE":
            allowed_shapes = {"circular", "rectangular"} if service == "HVAC_DUCT" else {"circular"} if service in _FLUID else {"prescribed_open_channel"}
            if shape is None:
                section = _mapping(section, ("shape",), "untyped section")
                missing.append("section.shape")
            elif not isinstance(shape, str) or shape not in allowed_shapes:
                raise ValueError("Section shape is unsupported for the declared service")
            else:
                section = _mapping(section, ("shape", *_SECTION_FIELDS[shape]), "section")
                for key in _SECTION_FIELDS[shape]:
                    value = section.get(key)
                    if value is None or (key == "hydraulic_section_applicability" and not _label(value)):
                        missing.append("section." + key)
                    elif key != "hydraulic_section_applicability":
                        number = _number(value)
                        if number < 0 or (key != "insulation_m" and number == 0):
                            raise ValueError("Section dimensions/area/perimeter must be positive; insulation nonnegative")
        else:
            section = _mapping(section, (), "electrical section")
        cost = None if option.get("total_cost") is None else _number(option["total_cost"])
        if cost is not None and cost < 0:
            raise ValueError("Total candidate price must be nonnegative")
        record = {"id": identifier, "verdict": "UNKNOWN", "missing": missing, "metrics": {}, "margins": {},
                  "parameters": {k: str(v) for k, v in params.items()},
                  "section": {k: (v if k == "shape" else v if _label(v) else None)
                              if k in {"shape", "hydraulic_section_applicability"}
                              else str(_number(v)) if v is not None else None for k, v in section.items()},
                  "total_cost": str(cost) if cost is not None else None,
                  "cost_status": "KNOWN" if cost is not None else "MISSING",
                  "material_applicability": option.get("material_applicability") if _label(option.get("material_applicability")) else None,
                  "installation_applicability": option.get("installation_applicability") if _label(option.get("installation_applicability")) else None,
                  "applicability_status": "CALLER_DECLARED_NOT_INDEPENDENTLY_VERIFIED"}
        if not missing:
            model, metrics, margins = _screen_model(service, identifier, section, params, req)
            record.update(model=model, metrics=metrics, margins=margins,
                          verdict=combine_verdicts([v["verdict"] for v in margins.values()]))
        records.append(record)
    records.sort(key=lambda item: item["id"])
    feasible = [r for r in records if r["verdict"] == "PASS"]
    priced = [r for r in feasible if r["total_cost"] is not None]
    selected = min(priced, key=lambda r: (Fraction(r["total_cost"]), r["id"])) if priced else feasible[0] if feasible else None
    disposed = all(r["verdict"] != "UNKNOWN" for r in records)
    priced_complete = all(r["total_cost"] is not None for r in records)
    price_complete = catalogue_complete and disposed and priced_complete
    status = ("CATALOG_OPTIMAL" if price_complete else "CATALOG_FEASIBLE") if feasible else (
        "CATALOG_INFEASIBLE" if catalogue_complete and disposed else "UNKNOWN")
    return {"schema": "oma.service-design-catalog/1", "service": service, "status": status,
            "requirements": {k: str(v) for k, v in req.items()},
            "selected": selected["id"] if selected else None, "objective": selected["total_cost"] if selected else None,
            "objective_policy": "SUPPLIED_TOTAL_CANDIDATE_PRICE_IN_ONE_CALLER_DECLARED_UNIT",
            "selection_basis": "EXACT_FINITE_PRICE" if price_complete and selected else "PRICED_FEASIBLE_INCUMBENT" if priced else "FEASIBILITY_ONLY",
            "options": records, "catalogue_complete": catalogue_complete,
            "all_options_disposed": disposed, "all_candidate_prices_known": priced_complete,
            "price_optimization_complete": price_complete, "context_root": context_root,
            "scope": "SUPPLIED_FINITE_CATALOGUE_DECLARED_SERVICE_MODEL_ONLY",
            "geometry": "NOT_RUN", "code_compliance": "NOT_CHECKED", "whole_building_adequacy": "NOT_CHECKED",
            "fire_hazard_and_protection_design": "NOT_CHECKED",
            "assumptions": {"applicability": "CALLER_DECLARED_ONLY",
                "electrical_regime": "BALANCED_THREE_PHASE" if service == "ELECTRICAL" else "DC_WITH_SUPPLIED_FULL_LOOP_RESISTANCE" if service in _DC else "NOT_APPLICABLE",
                "manning_regime": "STEADY_UNIFORM_FLOW_AT_SUPPLIED_WETTED_SECTION" if service == "GRAVITY_DRAINAGE" else "NOT_APPLICABLE"}}
