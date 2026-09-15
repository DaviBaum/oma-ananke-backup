"""Actual native section tolerances cannot disappear from delivery authority."""
from decimal import Decimal, localcontext
from fractions import Fraction

import ifcopenshell
import ifcopenshell.util.unit

from oma.ifc.audit import atomic_json, sha256_file
from oma.ifc.network_semantics import check_network_semantics
from oma.routing.engine import route_project_run
from oma.worker import WorkerControl
from test_network_integration import imported_project
from test_network_pressure import pressure_scenario


def _symmetric_branch_flow(diameter):
    """Independent original path-energy equation, solely a test oracle."""
    with localcontext() as context:
        context.prec = 85
        pi = Decimal("3.1415926535897932384626433832795028841971693993751058209749445923078164062862089986")
        d = Decimal(str(diameter))
        area = pi * d * d / 4
        # Trunk and each arm have 0.8m length; the tee's entire local loss is .2.
        coefficient = Decimal(".02") * Decimal(".8") / d * Decimal("1.25") + Decimal(".2")
        return area / 2 * (Decimal(200) / (Decimal(1000) * coefficient)).sqrt()


def test_native_radius_tolerance_is_carried_into_pressure_delivery(tmp_path, monkeypatch):
    """The historical nominal-area implementation made this candidate CHECKED."""
    store, project = imported_project(tmp_path)
    raw = pressure_scenario()
    raw["diameter_m"] = 1e-5
    raw["pressure_driven"]["gravity_m_s2"] = 0.
    minimum = 3.9266958549444814e-13
    for sink in raw["sinks"]:
        sink["required_flow_m3_s"] = minimum
    for component in raw["network_alternatives"][0]["components"]:
        component["diameter_m"] = 1e-5
    assert _symmetric_branch_flow(raw["diameter_m"]) > Decimal(str(minimum))

    import oma.routing.network_engine as engine
    exporter = engine.export_network
    observed = []

    def export_with_admitted_native_radius_difference(source, destination, spec, **kwargs):
        # Modify only the newly authored proposal before its candidate is stored.
        # Immutable imported source records and published candidate bytes are kept.
        materialized = exporter(source, destination, spec, **kwargs)
        model = ifcopenshell.open(str(destination))
        original_ids = {entity.id() for entity in ifcopenshell.open(str(source))}
        scale = ifcopenshell.util.unit.calculate_unit_scale(model)
        changed = []
        for profile in model.by_type("IfcCircleProfileDef"):
            if profile.id() in original_ids:
                continue
            before = float(profile.Radius) * scale
            profile.Radius = (before - 9e-11) / scale
            changed.append((before, float(profile.Radius) * scale))
        assert len(changed) == 5  # Three straight pipes and both tee operands.
        model.write(str(destination))
        materialized["export_sha256"] = sha256_file(destination)
        atomic_json(destination.with_suffix(".manifest.json"), materialized)
        actual = check_network_semantics(destination, source, materialized)
        assert actual["status"] == "PASS", actual
        observed.append(actual)
        return materialized

    monkeypatch.setattr(engine, "export_network", export_with_admitted_native_radius_difference)
    run = store.create_run(project["id"], {"operation": "optimize", "mission": raw, "budget_seconds": 90})
    route_project_run(store, run, WorkerControl(store, run["id"]))
    candidate, = store.candidates(project["id"])
    report = store.get(candidate["report_root"])
    checks = {item["id"]: item for item in report["results"]}
    for identity in ("network-native-semantics", "network-all-source-clearance", "network-all-component-pairs", "network-permitted-zone"):
        assert checks[identity]["status"] == "PASS", checks[identity]
    assert candidate["status"] != "CHECKED"
    assert report["status"] != "PASS"
    assert checks["network-demand-conditioned-service"]["status"] != "PASS"

    native, = observed
    measured_radius = native["parts"][0]["radius_m"]
    inferred_bore = 2 * (measured_radius - raw["insulation_m"])
    assert _symmetric_branch_flow(inferred_bore) < Decimal(str(minimum))
    calculation = checks["network-demand-conditioned-service"]["witness"]["calculation"]
    derivation = calculation["derivation"]
    assert derivation["native_inner_bore_or_wall_thickness_measured"] is False
    assert derivation["hydraulic_section_interpretation"] == "IDEAL_CIRCULAR_BORE_FROM_NATIVE_ENVELOPE_MINUS_DECLARED_INSULATION"
    assert set(derivation["component_outer_radii_m"]) == {part["component_id"] for part in native["parts"]}
    for part in native["parts"]:
        bound = derivation["component_outer_radii_m"][part["component_id"]]
        lower, upper = Fraction(bound["lower"]), Fraction(bound["upper"])
        assert lower <= Fraction(str(part["radius_m"])) <= upper
        assert upper - lower >= Fraction(2, 1_000_000)
