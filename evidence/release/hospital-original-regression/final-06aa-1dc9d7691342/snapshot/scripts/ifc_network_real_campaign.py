"""Freeze generic source-space shared-tree references before finite selection."""
from __future__ import annotations

import argparse
import copy
from fractions import Fraction
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
if not os.environ.get("OMA_EXECUTABLE_BUILD"):
    sys.path.insert(0, str(ROOT / "src"))
    if __name__ == "__main__":
        from oma.build_identity import frozen_environment
        raise SystemExit(subprocess.call([sys.executable, __file__, *sys.argv[1:]], env=frozen_environment(ROOT / ".oma/benchmark-builds")))

import numpy as np
from oma.build_identity import checker_version
from oma.ifc.audit import atomic_json, sha256_file
from oma.ifc.cad import cad_check_routes, load_cad, VERTEX_HULL_SOURCE_REPRESENTATION_POLICY
from oma.ifc.export import fillet_route
from oma.ifc.network import export_network
from oma.ifc.network_semantics import check_network_semantics
from oma.optimization.physical import Interval
from oma.routing.engine import route_project_run
from oma.routing.network_flow import evaluate_network_flow
from oma.routing.network_scenario import SharedNetworkScenario
from oma.store import Store, digest
from oma.worker import WorkerControl, import_sources


def design(center, crossing):
    center = np.asarray(center)
    pt = lambda p: (center + np.array(p)).tolist()
    common = {"system_type": "PRESSURE_PIPE", "diameter_m": .1, "insulation_m": .02}
    components = [
        {**common, "id": "trunk", "kind": "segment", "geometry": {"start_m": pt([-.6, 0, 0]), "end_m": pt([-.15, 0, 0])}, "ports": {"a": "SINK", "b": "SOURCE"}},
        {**common, "id": "tee", "kind": "tee", "geometry": {"frame_m": [[1, 0, 0, center[0]], [0, 1, 0, center[1]], [0, 0, 1, center[2]], [0, 0, 0, 1]],
         "trunk_takeout_m": .15, "branch_takeout_m": .15}, "ports": {"a": "SINK", "b": "SOURCE", "branch": "SOURCE"}},
        {**common, "id": "outlet-a", "kind": "segment", "geometry": {"start_m": pt([.15, 0, 0]), "end_m": pt([.6, 0, 0])}, "ports": {"a": "SINK", "b": "SOURCE"}}]
    path = [[0, .15, 0], [0, .6, 0]] if not crossing else [[0, .15, 0], [0, .4, 0], [-.4, .4, 0], [-.4, -.4, 0], [.4, -.4, 0], [.4, .4, 0], [0, .4, 0], [0, .6, 0]]
    parts = fillet_route([pt(p) for p in path], .1, .04)
    ids = []
    for index, part in enumerate(parts):
        cid = f"branch-{index:02d}"
        ids.append(cid)
        geometry = {"start_m": part["start"], "end_m": part["end"]}
        if part["kind"] == "elbow":
            geometry.update(center_m=part["center"], normal=part["normal"], bend_radius_m=part["bend_radius_m"], angle_rad=part["angle_rad"])
        components.append({**common, "id": cid, "kind": part["kind"], "geometry": geometry, "ports": {"a": "SINK", "b": "SOURCE"}})
    endpoint = lambda cid, port: {"component": cid, "port": port}
    link = lambda cid, port, other: {"source": endpoint(cid, port), "sink": endpoint(other, "a")}
    step = lambda cid, port="b": {"component": cid, "entry_port": "a", "exit_port": port}
    return {"schema": "oma-physical-network/1", "network_id": "self-crossing-branch" if crossing else "compact-tree", "system_type": "PRESSURE_PIPE",
        "components": components, "connections": [link("trunk", "b", "tee"), link("tee", "b", "outlet-a"), link("tee", "branch", ids[0]),
            *[link(a, "b", b) for a, b in zip(ids, ids[1:])]], "source": endpoint("trunk", "a"),
        "sinks": [{"id": "sink-a", "endpoint": endpoint("outlet-a", "b")}, {"id": "sink-b", "endpoint": endpoint(ids[-1], "b")}],
        "demand_paths": [{"demand_id": "demand-a", "sink_id": "sink-a", "steps": [step("trunk"), step("tee"), step("outlet-a")]},
            {"demand_id": "demand-b", "sink_id": "sink-b", "steps": [step("trunk"), step("tee", "branch"), *[step(cid) for cid in ids]]}]}


def select_scenarios(audit, count):
    physical = [p for p in audit["products"] if p["physical"] and p.get("bounds")]
    lower, upper = [np.array([p["bounds"][key] for p in physical]) for key in ("min", "max")]
    scenarios, dispositions = [], []
    spaces = sorted((p for p in audit["products"] if p["type"] == "IfcSpace" and p.get("bounds")), key=lambda p: p["step_id"])
    for space in spaces:
        lo, hi = [np.asarray(space["bounds"][key]) for key in ("min", "max")]
        for height in (.65, .4):
            center = (lo + hi) / 2
            center[2] = lo[2] + height * (hi[2] - lo[2])
            zlo, zhi = center - [.8, .8, .2], center + [.8, .8, .2]
            selection = {"source_sha256": audit["source_sha256"], "space_id": space["entity_id"], "height_fraction": height}
            if np.any(zlo < lo) or np.any(zhi > hi):
                dispositions.append({**selection, "status": "HEURISTIC_ZONE_OUTSIDE_SPACE_BOUNDS"})
                continue
            hits = np.flatnonzero(np.all((zhi >= lower) & (zlo <= upper), axis=1))
            if len(hits):
                dispositions.append({**selection, "status": "HEURISTIC_ENVELOPE_OVERLAP", "participants": [physical[i]["entity_id"] for i in hits]})
                continue
            mission = {"mission_type": "shared_network", "source_id": audit["source_sha256"], "system_type": "PRESSURE_PIPE",
                "start_m": (center + [-.6, 0, 0]).tolist(), "sinks": [
                    {"id": "sink-a", "demand_id": "demand-a", "end_m": (center + [.6, 0, 0]).tolist(), "required_flow_m3_s": .001, "available_static_pressure_pa": 1000.},
                    {"id": "sink-b", "demand_id": "demand-b", "end_m": (center + [0, .6, 0]).tolist(), "required_flow_m3_s": .002, "available_static_pressure_pa": 1000.}],
                "diameter_m": .1, "insulation_m": .02, "clearance_m": .1, "minimum_straight_m": .04, "minimum_bend_radius_m": .1,
                "allowed_zone": {"min": zlo.tolist(), "max": zhi.tolist()}, "scenario_terminals": True, "target_modality": "ENGINEERING_SERVICE",
                "source_representation_policy": VERTEX_HULL_SOURCE_REPRESENTATION_POLICY,
                "network_alternatives": [design(center, True), design(center, False)], "objective_weights": {"length_m": 1., "fitting_count": 0.},
                "physics": {"density_kg_m3": 1000., "darcy_friction": .02, "maximum_velocity_m_s": 2., "gravity_m_s2": 9.80665,
                    "elbow_loss_coefficient": .2, "tee_straight_loss_coefficient": .2, "tee_branch_loss_coefficient": 1.2,
                    "source_kinetic_energy_correction": 1., "sink_kinetic_energy_correction": 1., "friction_convention": "DARCY",
                    "elbow_loss_reference": "EXCESS_LOCAL_LOSS_EXCLUDING_CURVED_PIPE_FRICTION", "tee_loss_reference": "INLET_VELOCITY_TOTAL_IRREVERSIBLE_LOSS",
                    "boundary_loss_scope": "BETWEEN_PHYSICAL_NETWORK_PORTS_ONLY",
                    "applicability": "Hypothetical stationary incompressible water with explicitly supplied constant Darcy and fitting coefficients; no manufacturer or actual building operating-data assertion",
                    "fixed_flow_control_assumption": "External controls impose both specified sink flows simultaneously; an operating point is not solved"},
                "assumptions": ["Explicit hypothetical shared service with fixed terminals, section, demands and pressure budgets",
                    "Source space bounds select a service box; room membership and existing building service intent are not inferred",
                    "Only the frozen finite component trees are compared; unrestricted topology and continuous optimality remain open"]}
            validated = SharedNetworkScenario.model_validate(mission).model_dump(mode="json", by_alias=True)
            scenarios.append({"scenario_id": digest(selection)[:20], "selection": selection, "mission": validated})
            if len(scenarios) >= count:
                return scenarios, dispositions
    return scenarios, dispositions


def reference(source, scenario, directory):
    results = {}
    request = SharedNetworkScenario.model_validate(scenario["mission"])
    for selected in request.network_alternatives:
        path = directory / (selected.network_id + ".ifc")
        manifest = export_network(source, path, selected.model_dump(mode="json", by_alias=True))
        semantics = check_network_semantics(path, source, manifest)
        guids = [p["ifc_guid"] for p in manifest["added_parts"]]
        last = [time.monotonic()]
        def progress(stage):
            if time.monotonic() - last[0] > 20:
                print(json.dumps({"stage": stage, "reference": selected.network_id}), flush=True)
                last[0] = time.monotonic()
        cad = cad_check_routes([source], path, guids, clearance_m=request.clearance_m,
            source_representation_policy=request.source_representation_policy, cache_directory=ROOT / ".oma/cad-cache",
            checkpoint=progress, output_path=directory / (selected.network_id + ".cad.json"))
        parts = {p["component_id"]: p for p in semantics["parts"]}
        budget = Fraction("0.000001")
        interval = lambda v: Interval(Fraction(str(v)) - budget, Fraction(str(v)) + budget)
        lengths = {cid: interval(p["length_m"]) for cid, p in parts.items()}
        position = lambda slot: [interval(v) for v in parts[slot.component]["caps"][slot.port]["position_m"]]
        flow = evaluate_network_flow(request, selected, lengths, {"source": position(selected.source), "sinks": {s.id: position(s.endpoint) for s in selected.sinks}})
        objects, errors = load_cad(path, guids=set(guids))
        zone = all(np.all(np.asarray(o.bounds[:3]) > np.asarray(request.allowed_zone.min) + 1e-6)
                   and np.all(np.asarray(o.bounds[3:]) < np.asarray(request.allowed_zone.max) - 1e-6) for o in objects) and not errors
        record = {"native_semantics": semantics, "cad_status": cad["status"], "self_interference_status": cad["self_interference_status"],
            "source_obstacles": cad["obstacle_count"], "all_source_pairs": cad["pairs_accounted"], "zone_status": "PASS" if zone else "FAIL",
            "flow": flow, "materialization": manifest, "cad_path": str((directory / (selected.network_id + ".cad.json")).relative_to(ROOT))}
        atomic_json(directory / (selected.network_id + ".reference.json"), record)
        results[selected.network_id] = record
    good, bad = results["compact-tree"], results["self-crossing-branch"]
    eligible = good["native_semantics"]["status"] == good["cad_status"] == good["zone_status"] == good["flow"]["verdict"] == "PASS"
    eligible &= bad["native_semantics"]["status"] == "PASS" and bad["self_interference_status"] == "FAIL"
    return eligible, results


def run(project, count, execute, budget):
    acquisition = json.loads((ROOT / "evidence/ifc/acquisition.json").read_text())
    item = next(e for e in acquisition["files"] if e["is_ifc"] and e["project"] == project and Path(e["path"]).stem == "arc")
    source = ROOT / item["local_path"]
    audit = json.loads(next((ROOT / "evidence/ifc/audits" / project).glob("arc-*.audit.json")).read_text())
    folder = ROOT / "evidence/benchmarks/shared-network" / project
    frozen_path = folder / "source-space-frozen-v1.json"
    if frozen_path.exists():
        frozen = json.loads(frozen_path.read_text())
        if digest({k: v for k, v in frozen.items() if k != "specification_root"}) != frozen["specification_root"] or frozen["source_sha256"] != sha256_file(source):
            raise ValueError("Frozen source-space benchmark changed")
    else:
        scenarios, dispositions = select_scenarios(audit, count)
        frozen = {"schema": "oma-real-shared-network-campaign/1", "source_path": item["path"], "source_sha256": sha256_file(source),
            "dataset_revision": acquisition["revision"], "scenarios": scenarios, "selection_dispositions": dispositions,
            "frozen_scenario_denominator": len(scenarios), "reference_checks_are_not_optimizer_inputs": True}
        frozen["specification_root"] = digest(frozen)
        atomic_json(frozen_path, frozen)
    for scenario in frozen["scenarios"]:
        directory = folder / "attempts" / uuid.uuid4().hex
        directory.mkdir(parents=True)
        record = {"scenario_id": scenario["scenario_id"], "specification_root": frozen["specification_root"], "status": "CHECKING_INDEPENDENT_REFERENCES",
            "checker_version": checker_version(), "frozen_scenario_denominator": frozen["frozen_scenario_denominator"]}
        atomic_json(directory / "result.json", record)
        started = time.perf_counter()
        try:
            eligible, references = reference(source, scenario, directory)
            record.update(status="INDEPENDENT_REFERENCE_CHECKED" if eligible else "INELIGIBLE_REFERENCE",
                references={k: {"native_semantics": v["native_semantics"]["status"], "cad": v["cad_status"], "self": v["self_interference_status"],
                    "flow": v["flow"]["verdict"], "zone": v["zone_status"], "unique_length_m": v["native_semantics"]["unique_length_m"],
                    "source_obstacles": v["source_obstacles"], "all_source_pairs": v["all_source_pairs"]} for k, v in references.items()})
            atomic_json(directory / "result.json", record)
            print(json.dumps(record), flush=True)
            if not eligible:
                continue
            if execute:
                store = Store(ROOT / ".oma")
                created = store.create_project(project.replace("_", " ").title() + " - shared trunk, tee and fixed flow", {"sources": [], "entities": []})
                imported = store.create_run(created["id"], {"operation": "import", "paths": [str(source.resolve())]})
                record.update(project_id=created["id"], import_run_id=imported["id"], status="IMPORTING")
                atomic_json(directory / "result.json", record)
                import_sources(store, imported, WorkerControl(store, imported["id"]))
                run = store.create_run(created["id"], {"operation": "optimize", "mission": scenario["mission"], "budget_seconds": budget})
                store.claim_run(run["id"], "worker")
                record.update(run_id=run["id"], status="OPTIMIZING")
                atomic_json(directory / "result.json", record)
                route_project_run(store, run, WorkerControl(store, run["id"]))
                candidates = [c for c in store.candidates(created["id"]) if c["run_id"] == run["id"]]
                record["candidates"] = [{"id": c["id"], "status": c["status"], "report_root": c.get("report_root")} for c in candidates]
                record["status"] = "CHECKED_SHARED_TREE_AWAITING_CURRENT_BUILD_FINALIZATION" if any(c["status"] == "CHECKED" for c in candidates) else "NO_CHECKED_SHARED_TREE"
            record["seconds"] = time.perf_counter() - started
            atomic_json(directory / "result.json", record)
            print(json.dumps({"evidence": str(directory.relative_to(ROOT)), **record}), flush=True)
            return record
        except Exception as exc:
            record.update(status="ATTEMPT_FAILED", error=f"{type(exc).__name__}: {exc}", seconds=time.perf_counter() - started)
            atomic_json(directory / "result.json", record)
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="dental_clinic")
    parser.add_argument("--max-scenarios", type=int, default=4)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--budget", type=float, default=1800.)
    args = parser.parse_args()
    run(args.project, args.max_scenarios, args.execute, args.budget)
