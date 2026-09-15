"""Exercise real IFC repair/export using the bundled interpreter and dependencies."""
from pathlib import Path
import json
import os
import subprocess
import sys
import time


def child(package: Path):
    import ifcopenshell.api
    import numpy as np
    import oma
    from oma.store import Store
    from oma.worker import import_sources, WorkerControl
    from oma.routing.engine import route_project_run
    from oma.build_identity import checker_version
    from oma.exporting import export_project
    assert Path(oma.__file__).resolve().is_relative_to(package), oma.__file__
    began = time.perf_counter()
    workspace = package / "offline-qa"
    workspace.mkdir(exist_ok=False)
    source = workspace / "analytic-obstacle.ifc"
    model = ifcopenshell.api.run("project.create_file", version="IFC4")
    project = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcProject", name="Offline analytic fixture")
    ifcopenshell.api.run("unit.assign_unit", model, length={"is_metric": True, "raw": "METERS"})
    assignment = model.by_type("IfcUnitAssignment")[0]
    assignment.Units = [*assignment.Units, model.create_entity("IfcSIUnit", UnitType="PLANEANGLEUNIT", Name="RADIAN")]
    context = ifcopenshell.api.run("context.add_context", model, context_type="Model")
    body = ifcopenshell.api.run("context.add_context", model, context_type="Model", context_identifier="Body", target_view="MODEL_VIEW", parent=context)
    obstacle = ifcopenshell.api.run("root.create_entity", model, ifc_class="IfcBuildingElementProxy", name="Independent 2 metre cube")
    representation = ifcopenshell.api.run("geometry.add_wall_representation", model, context=body, length=2., thickness=2., height=2.)
    ifcopenshell.api.run("geometry.assign_representation", model, product=obstacle, representation=representation)
    ifcopenshell.api.run("geometry.edit_object_placement", model, product=obstacle, matrix=np.eye(4))
    model.write(str(source))
    store = Store(workspace / "data")
    p = store.create_project("Offline repair verification", {"sources": [], "entities": []})
    imp = store.create_run(p["id"], {"operation": "import", "paths": [str(source)]})
    import_sources(store, imp, WorkerControl(store, imp["id"]))
    mission = {"start": [-1, 1, 1], "end": [3, 1, 1], "system_type": "PRESSURE_PIPE", "diameter_m": .1,
               "insulation_m": .02, "bend_radius_m": .3, "minimum_straight_m": .05, "clearance_m": .1,
               "allowed_zone": {"min": [-2, -2, -2], "max": [4, 4, 4]}, "scenario_terminals": True, "max_candidates": 6}
    run = store.create_run(p["id"], {"operation": "route", "mission": mission, "budget_seconds": 120})
    route_project_run(store, run, WorkerControl(store, run["id"]))
    candidates = store.candidates(p["id"])
    assert candidates[0]["status"] == "REJECTED"
    selected = next(c for c in candidates if c["status"] == "CHECKED")
    accepted = store.accept(p["id"], selected["id"], 1, "offline-accept", checker_version=checker_version())
    exported = export_project(store, p["id"], selected["id"], draft=False)
    assert accepted["revision"] == 2
    assert exported["status"] == "CHECKED_LOCAL_SCOPE" and exported["round_trip"] == "PASS"
    report = {"status": "PASS", "seconds": time.perf_counter()-began, "python": sys.version, "executable": sys.executable,
              "package_source": oma.__file__, "checker_build": checker_version(), "project": store.project(p["id"]),
              "rejected_baseline": candidates[0]["id"], "checked_candidate": selected["id"], "export": exported,
              "installation": "59 locally pinned wheels installed with --no-index; bundled CPython; no Node or external Python needed",
              "scope": "Analytic IFC repair, acceptance and fresh exported IFC recheck; full production gates remain open"}
    (workspace / "result.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--child":
        child(Path(sys.argv[2]).resolve())
        return
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "evidence" / "dependencies" / "portable-preview.json").read_text())
    package = Path(manifest["package"])
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PIP_NO_INDEX"] = "1"
    result = subprocess.run([str(package / "runtime" / "python.exe"), "-s", str(Path(__file__).resolve()), "--child", str(package)],
                            env=environment, cwd=package, text=True, capture_output=True, timeout=300)
    if result.returncode:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise SystemExit(result.returncode)
    evidence = json.loads((package / "offline-qa" / "result.json").read_text())
    (root / "evidence" / "dependencies" / "portable-offline-workflow.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
