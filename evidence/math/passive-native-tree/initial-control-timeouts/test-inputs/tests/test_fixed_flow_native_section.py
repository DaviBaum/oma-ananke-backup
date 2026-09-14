"""Independent prescribed-flow section uncertainty and genuine native regressions."""
import copy
from decimal import Decimal, localcontext
from fractions import Fraction
import random

import ifcopenshell
import ifcopenshell.util.unit
import pytest

from oma.ifc.audit import atomic_json, sha256_file
from oma.ifc.network_semantics import check_network_semantics
from oma.optimization.physical import Interval
from oma.routing.engine import route_project_run
from oma.routing.network_flow import evaluate_network_flow
from oma.routing.network_scenario import SharedNetworkScenario
from oma.worker import WorkerControl
from test_network_integration import imported_project
from test_network_scenario import network_scenario

PI = Decimal("3.1415926535897932384626433832795028841971693993751058209749445923078164062862089986")
IDS = ("trunk", "junction", "arm-a", "arm-b")


def inputs(raw=None):
    scenario = SharedNetworkScenario.model_validate(raw or network_scenario())
    return scenario, scenario.network_alternatives[0], {cid: Fraction(4, 5) for cid in IDS}, {
        "source": [-1, 4, 3], "sinks": {"sink-a": [1, 4, 3], "sink-b": [0, 5, 3]}}, {cid: Fraction(7, 100) for cid in IDS}


def decimal(value):
    value = Fraction(value)
    return Decimal(value.numerator) / Decimal(value.denominator)


def enclosed(value, actual):
    assert decimal(value["lower"]) <= actual <= decimal(value["upper"]), (value, actual)


@pytest.mark.parametrize("fault", ["absent", "missing", "extra"])
def test_current_native_sections_must_cover_every_component(fault):
    scenario, network, lengths, positions, radii = inputs()
    if fault == "absent": radii = None
    if fault == "missing": radii.pop("junction")
    if fault == "extra": radii["unknown"] = Fraction(7, 100)
    result = evaluate_network_flow(scenario, network, lengths, positions, component_outer_radii=radii)
    assert result["verdict"] == "BLOCKED"
    assert "complete_native_component_outer_radii" in result["missing"]
    assert "components" not in result


@pytest.mark.parametrize("radius", [Fraction(1, 50), Interval(Fraction(1, 100), Fraction(3, 100)), Fraction(1, 100)])
def test_nonpositive_or_unresolved_native_bore_never_has_service_authority(radius):
    scenario, network, lengths, positions, radii = inputs()
    radii["junction"] = radius
    result = evaluate_network_flow(scenario, network, lengths, positions, component_outer_radii=radii)
    assert result["verdict"] == "UNKNOWN"
    assert "positive_native_hydraulic_bore_enclosure" in result["missing"]
    assert "components" not in result


@pytest.mark.parametrize("changed", IDS)
def test_each_component_radius_changes_its_own_velocity_and_relevant_losses(changed):
    scenario, network, lengths, positions, radii = inputs()
    baseline = evaluate_network_flow(scenario, network, lengths, positions, component_outer_radii=radii)
    radii[changed] = Fraction(6, 100)
    result = evaluate_network_flow(scenario, network, lengths, positions, component_outer_radii=radii)
    for cid in IDS:
        expected_change = cid == changed
        assert (result["components"][cid]["velocity_m_s"] != baseline["components"][cid]["velocity_m_s"]) == expected_change
    for sid, arm in (("sink-a", "arm-a"), ("sink-b", "arm-b")):
        for old, new in zip(baseline["paths"][sid]["terms"], result["paths"][sid]["terms"], strict=True):
            assert (old["loss_pa"] != new["loss_pa"]) == (new["component"] == changed)
    assert result["section_model"]["native_inner_bore_or_wall_thickness_measured"] is False


def test_160_independent_parameter_samples_enclosed_by_component_metric_boxes():
    rng = random.Random(728415)
    raw = network_scenario()
    raw["physics"].update(source_kinetic_energy_correction=1.2, sink_kinetic_energy_correction=.8)
    scenario, network, lengths, positions, radii = inputs(raw)
    radii = {cid: Interval(Fraction(6 + i, 100), Fraction(7 + i, 100)) for i, cid in enumerate(IDS)}
    lengths = {cid: Interval(Fraction(7 + i, 10), Fraction(8 + i, 10)) for i, cid in enumerate(IDS)}
    positions["source"][2] = Interval(Fraction(29, 10), Fraction(31, 10))
    positions["sinks"]["sink-a"][2] = Interval(Fraction(28, 10), Fraction(32, 10))
    positions["sinks"]["sink-b"][2] = Interval(Fraction(3), Fraction(33, 10))
    result = evaluate_network_flow(scenario, network, lengths, positions, component_outer_radii=radii)
    assert result["unique_physical_components"] == 4
    assert sum(len(v["velocity_m_s"]) for v in result["components"].values()) == 9
    with localcontext() as ctx:
        ctx.prec = 75
        choose = lambda bound: decimal(bound.lo + Fraction(rng.randrange(0, 101), 100) * (bound.hi - bound.lo))
        for _ in range(160):
            d = {cid: 2 * (choose(bound) - Decimal(".02")) for cid, bound in radii.items()}
            a = {cid: PI * diameter ** 2 / 4 for cid, diameter in d.items()}
            length = {cid: choose(bound) for cid, bound in lengths.items()}
            flows = {"trunk": {"a": Decimal(".003"), "b": Decimal(".003")},
                "junction": {"a": Decimal(".003"), "b": Decimal(".001"), "branch": Decimal(".002")},
                "arm-a": {"a": Decimal(".001"), "b": Decimal(".001")},
                "arm-b": {"a": Decimal(".002"), "b": Decimal(".002")}}
            velocity = {cid: {port: q / a[cid] for port, q in ports.items()} for cid, ports in flows.items()}
            for cid, ports in velocity.items():
                for port, value in ports.items():
                    enclosed(result["components"][cid]["velocity_m_s"][port], value)
            z_source = choose(positions["source"][2])
            for sid, arm, tee_k in (("sink-a", "arm-a", Decimal(".2")), ("sink-b", "arm-b", Decimal("1.2"))):
                loss_trunk = Decimal(".02") * length["trunk"] / d["trunk"] * Decimal(500) * velocity["trunk"]["a"] ** 2
                loss_tee = tee_k * Decimal(500) * velocity["junction"]["a"] ** 2
                loss_arm = Decimal(".02") * length[arm] / d[arm] * Decimal(500) * velocity[arm]["a"] ** 2
                elevation = Decimal("9806.65") * (choose(positions["sinks"][sid][2]) - z_source)
                kinetic = Decimal(500) * (Decimal(".8") * velocity[arm]["b"] ** 2 - Decimal("1.2") * velocity["trunk"]["a"] ** 2)
                row = result["paths"][sid]
                for term, actual in zip(row["terms"], (loss_trunk, loss_tee, loss_arm), strict=True):
                    enclosed(term["loss_pa"], actual)
                enclosed(row["kinetic_pressure_pa"], kinetic)
                enclosed(row["elevation_pressure_pa"], elevation)
                enclosed(row["required_source_minus_sink_static_pressure_pa"], loss_trunk + loss_tee + loss_arm + elevation + kinetic)


@pytest.mark.parametrize("condition", ["velocity", "pressure"])
def test_actual_admitted_native_diameter_change_cannot_publish_false_service_pass(tmp_path, monkeypatch, condition):
    store, project = imported_project(tmp_path)
    raw = network_scenario()
    raw["diameter_m"] = 1e-5
    for sink in raw["sinks"]:
        sink.update(required_flow_m3_s=3.926990816987242e-11,
            available_static_pressure_pa=1e12 if condition == "velocity" else 1000245.)
    raw["physics"].update(maximum_velocity_m_s=1.00002 if condition == "velocity" else 10., gravity_m_s2=0.)
    for component in raw["network_alternatives"][0]["components"]:
        component["diameter_m"] = raw["diameter_m"]
    import oma.routing.network_engine as engine
    exporter = engine.export_network
    observed = []
    def author_difference(source, destination, spec, **kwargs):
        materialized = exporter(source, destination, spec, **kwargs)
        model = ifcopenshell.open(str(destination))
        original_ids = {entity.id() for entity in ifcopenshell.open(str(source))}
        scale = ifcopenshell.util.unit.calculate_unit_scale(model)
        changed = 0
        for profile in model.by_type("IfcCircleProfileDef"):
            if profile.id() not in original_ids:
                profile.Radius = (float(profile.Radius) * scale - 9e-11) / scale
                changed += 1
        assert changed == 5
        model.write(str(destination))
        materialized["export_sha256"] = sha256_file(destination)
        atomic_json(destination.with_suffix(".manifest.json"), materialized)
        native = check_network_semantics(destination, source, materialized)
        assert native["status"] == "PASS", native
        observed.append(native)
        return materialized
    monkeypatch.setattr(engine, "export_network", author_difference)
    run = store.create_run(project["id"], {"operation": "optimize", "mission": raw, "budget_seconds": 90})
    route_project_run(store, run, WorkerControl(store, run["id"]))
    candidate, = store.candidates(project["id"])
    report = store.get(candidate["report_root"])
    checks = {row["id"]: row for row in report["results"]}
    for identity in ("network-native-semantics", "network-all-source-clearance", "network-all-component-pairs", "network-permitted-zone"):
        assert checks[identity]["status"] == "PASS"
    assert candidate["status"] != "CHECKED" and report["status"] != "PASS"
    calculation = checks["network-demand-conditioned-service"]["witness"]["calculation"]
    assert calculation["verdict"] == "UNKNOWN"
    section = calculation["section_model"]
    native, = observed
    assert set(section["component_outer_radii_m"]) == {p["component_id"] for p in native["parts"]}
    assert len(calculation["components"]) == 4
    assert sum(len(v["velocity_m_s"]) for v in calculation["components"].values()) == 9
    for part in native["parts"]:
        interval = section["component_outer_radii_m"][part["component_id"]]
        assert Fraction(interval["lower"]) <= Fraction(str(part["radius_m"])) <= Fraction(interval["upper"])
        assert Fraction(interval["upper"]) - Fraction(interval["lower"]) >= Fraction(2, 1_000_000)
    with localcontext() as ctx:
        ctx.prec = 75
        d = Decimal(".00000999982")
        a = PI * d * d / 4
        q = Decimal("3.926990816987242e-11")
        v = 2 * q / a
        if condition == "velocity":
            assert v > Decimal(str(raw["physics"]["maximum_velocity_m_s"]))
        else:
            needed = Decimal(500) * (Decimal(".02") * Decimal(".8") / d * (v * v + (q / a) ** 2) + Decimal("1.2") * v * v + (q / a) ** 2 - v * v)
            assert needed > Decimal(str(raw["sinks"][1]["available_static_pressure_pa"]))
    atomic_json(tmp_path / "section-regression.json", {"condition": condition, "candidate": candidate, "report": report})
