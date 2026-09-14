"""Independent native audit of the earlier prescribed-flow section model."""
from pathlib import Path
from decimal import Decimal, localcontext
from fractions import Fraction
import hashlib
import json
import os
import sys
import time
import uuid

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "AGENTS.md").is_file())
STAGE = Path(__file__).resolve().parent
SOURCE = ROOT / ".oma/development/next-best-fabrication/runtimes/1abe9a077844a184ec17e1c8a0a390aa4bf33d05dd302a6eefff7d770a0ff719/src"
SNAPSHOT = ROOT / ".oma/development/next-best-fabrication/validation/14bff19b88c54779af3d15b1295b5d8b"
sys.path[:0] = [str(SOURCE), str(SNAPSHOT / "tests")]
os.environ["PYTHONPATH"] = str(SOURCE)
from oma.build_identity import checker_version
from oma.ifc.audit import atomic_json, sha256_file
from oma.ifc.network_semantics import check_network_semantics
from oma.routing.engine import route_project_run
from oma.worker import WorkerControl
from test_network_integration import imported_project
from test_network_scenario import network_scenario
import ifcopenshell
import ifcopenshell.util.unit
import oma.routing.network_engine as engine

PI = Decimal("3.1415926535897932384626433832795028841971693993751058209749445923078164062862089986")


def main():
    out = STAGE / "evidence" / uuid.uuid4().hex
    out.mkdir(parents=True, exist_ok=False)
    raw = network_scenario()
    raw["diameter_m"] = 1e-5
    with localcontext() as ctx:
        ctx.prec = 80
        q = float(PI * Decimal("1e-5") ** 2 / 8)
    for sink in raw["sinks"]:
        sink.update(required_flow_m3_s=q, available_static_pressure_pa=1e12)
    for component in raw["network_alternatives"][0]["components"]:
        component["diameter_m"] = raw["diameter_m"]
    raw["physics"].update(maximum_velocity_m_s=1.00002, gravity_m_s2=0.)
    declared = {"status": "PREDECLARED", "checker_version": checker_version(), "mission": raw,
        "native_profile_radius_reduction_m": "9/100000000000", "script_sha256": sha256_file(__file__),
        "oracle": "Total prescribed source flow divided by independently measured native circular bore area",
        "source_files": {p.relative_to(SOURCE / "oma").as_posix(): sha256_file(p) for p in (SOURCE / "oma").rglob("*.py")}}
    assert declared["checker_version"].endswith("1abe9a077844a184ec17e1c8a0a390aa4bf33d05dd302a6eefff7d770a0ff719")
    atomic_json(out / "declaration.json", declared)
    store, project = imported_project(out)
    source_state = store.get(store.project(project["id"])["state_root"])
    exporter = engine.export_network
    observed = []

    def authored_native_difference(source, destination, spec, **kwargs):
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
            changed.append([before, float(profile.Radius) * scale])
        assert len(changed) == 5
        model.write(str(destination))
        materialized["export_sha256"] = sha256_file(destination)
        atomic_json(destination.with_suffix(".manifest.json"), materialized)
        actual = check_network_semantics(destination, source, materialized)
        observed.append(actual)
        atomic_json(out / "authored-native-semantics.json", actual)
        return materialized

    engine.export_network = authored_native_difference
    started = time.perf_counter()
    try:
        run = store.create_run(project["id"], {"operation": "optimize", "mission": raw, "budget_seconds": 90})
        route_project_run(store, run, WorkerControl(store, run["id"]))
    finally:
        engine.export_network = exporter
    candidate, = store.candidates(project["id"])
    report = store.get(candidate["report_root"])
    atomic_json(out / "candidate.json", candidate)
    atomic_json(out / "report.json", report)
    checks = {item["id"]: item for item in report["results"]}
    native, = observed
    measured = {p["component_id"]: p["radius_m"] for p in native["parts"]}
    with localcontext() as ctx:
        ctx.prec = 80
        diameter = 2 * (Decimal(str(measured["trunk"])) - Decimal(str(raw["insulation_m"])))
        flow = sum(Decimal(str(s["required_flow_m3_s"])) for s in raw["sinks"])
        actual_velocity = flow / (PI * diameter ** 2 / 4)
        nominal_velocity = flow / (PI * Decimal(str(raw["diameter_m"])) ** 2 / 4)
    result = {"status": "AUDIT_COMPLETE", "seconds": time.perf_counter() - started,
        "checker_version": checker_version(), "candidate_status": candidate["status"], "report_status": report["status"],
        "checks": {k: v["status"] for k, v in checks.items()},
        "nominal_source_velocity_m_s": str(nominal_velocity), "native_bore_source_velocity_m_s": str(actual_velocity),
        "maximum_velocity_m_s": str(raw["physics"]["maximum_velocity_m_s"]),
        "native_bore_velocity_exceeds_limit": actual_velocity > Decimal(str(raw["physics"]["maximum_velocity_m_s"])),
        "complete_actual_geometry_pass": all(checks[k]["status"] == "PASS" for k in ("network-native-semantics", "network-all-source-clearance", "network-all-component-pairs", "network-permitted-zone")),
        "native_check_stubs_used": False, "accepted": False,
        "declared_source_unchanged": all(sha256_file(store.resolve_asset(s["path"])) == s["sha256"] for s in source_state["sources"]),
        "source_files_unchanged": all(sha256_file(SOURCE / "oma" / p) == h for p, h in declared["source_files"].items()),
        "candidate_id": candidate["id"], "store": str(store.directory), "evidence": str(out)}
    atomic_json(out / "result.json", result)
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
