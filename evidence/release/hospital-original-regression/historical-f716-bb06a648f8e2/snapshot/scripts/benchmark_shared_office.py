"""Frozen real-IFC shared-tree alternatives; no unrestricted search claim."""
from pathlib import Path
import os
import subprocess
import sys

if not os.environ.get("OMA_EXECUTABLE_BUILD"):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from oma.build_identity import frozen_environment
    if __name__ == "__main__":
        raise SystemExit(subprocess.call([sys.executable, __file__], env=frozen_environment(Path(".oma") / "benchmark-builds")))

import copy
import json
import time
import uuid

import numpy as np

from oma.build_identity import checker_version
from oma.exporting import export_project
from oma.ifc.audit import atomic_json
from oma.ifc.export import fillet_route
from oma.routing.engine import route_project_run
from oma.routing.network_scenario import SharedNetworkScenario
from oma.store import Store, digest
from oma.worker import WorkerControl


def design(center, source, sink_a, sink_b, *, offset):
    tee = np.asarray(center) + [-offset, 0, 0]
    def pt(v):
        return np.asarray(v).tolist()
    common = {"system_type": "PRESSURE_PIPE", "diameter_m": .1, "insulation_m": .02}
    a, b, branch = tee + [-.2, 0, 0], tee + [.2, 0, 0], tee + [0, .2, 0]
    components = [
        {**common, "id": "trunk", "kind": "segment", "geometry": {"start_m": pt(source), "end_m": pt(a)}, "ports": {"a": "SINK", "b": "SOURCE"}},
        {**common, "id": "tee", "kind": "tee", "geometry": {"frame_m": [[1, 0, 0, float(tee[0])], [0, 1, 0, float(tee[1])], [0, 0, 1, float(tee[2])], [0, 0, 0, 1]],
            "trunk_takeout_m": .2, "branch_takeout_m": .2}, "ports": {"a": "SINK", "b": "SOURCE", "branch": "SOURCE"}},
        {**common, "id": "straight-outlet", "kind": "segment", "geometry": {"start_m": pt(b), "end_m": pt(sink_a)}, "ports": {"a": "SINK", "b": "SOURCE"}}]
    points = [branch, sink_b] if not offset else [branch, tee + [0, .4, 0], np.asarray(center) + [0, .4, 0], sink_b]
    branch_parts = fillet_route(points, .08, .05)
    branch_ids = []
    for index, part in enumerate(branch_parts):
        cid = f"branch-{index}"
        branch_ids.append(cid)
        geometry = {"start_m": part["start"], "end_m": part["end"]}
        if part["kind"] == "elbow":
            geometry.update(center_m=part["center"], normal=part["normal"], bend_radius_m=part["bend_radius_m"], angle_rad=part["angle_rad"])
        components.append({**common, "id": cid, "kind": part["kind"], "geometry": geometry, "ports": {"a": "SINK", "b": "SOURCE"}})
    def endpoint(cid, slot):
        return {"component": cid, "port": slot}
    def link(a, p, b):
        return {"source": endpoint(a, p), "sink": endpoint(b, "a")}
    def step(cid, slot="b"):
        return {"component": cid, "entry_port": "a", "exit_port": slot}
    return {"schema": "oma-physical-network/1", "network_id": "office-offset-tee" if offset else "office-direct-tee", "system_type": "PRESSURE_PIPE",
        "components": components, "connections": [link("trunk", "b", "tee"), link("tee", "b", "straight-outlet"),
            link("tee", "branch", branch_ids[0]), *[link(a, "b", b) for a, b in zip(branch_ids, branch_ids[1:])]],
        "source": endpoint("trunk", "a"), "sinks": [{"id": "straight", "endpoint": endpoint("straight-outlet", "b")}, {"id": "branch", "endpoint": endpoint(branch_ids[-1], "b")}],
        "demand_paths": [{"demand_id": "straight-demand", "sink_id": "straight", "steps": [step("trunk"), step("tee"), step("straight-outlet")]},
            {"demand_id": "branch-demand", "sink_id": "branch", "steps": [step("trunk"), step("tee", "branch"), *[step(cid) for cid in branch_ids]]}]}


def main():
    store = Store(".oma")
    prior = store.candidate("7766684939a146579d07297318f9845a")
    prior_run = store.run(prior["run_id"])
    baseline = store.get(prior_run["base_root"])
    first = prior_run["request"]["mission"]["route_demands"][0]["alternatives"][0]
    crossing = prior_run["request"]["mission"]["route_demands"][1]["alternatives"][0]
    center = (np.asarray(first["start"]) + first["end"]) / 2
    spec = {"mission_type": "shared_network", "source_id": first["source_id"], "system_type": "PRESSURE_PIPE",
        "start_m": first["start"], "sinks": [{"id": "straight", "demand_id": "straight-demand", "end_m": first["end"],
                "required_flow_m3_s": .001, "available_static_pressure_pa": 1000},
            {"id": "branch", "demand_id": "branch-demand", "end_m": crossing["end"], "required_flow_m3_s": .002, "available_static_pressure_pa": 1000}],
        "diameter_m": .1, "insulation_m": .02, "clearance_m": .1, "minimum_straight_m": .05, "minimum_bend_radius_m": .08,
        "allowed_zone": first["allowed_zone"], "scenario_terminals": True, "target_modality": "ENGINEERING_SERVICE",
        "source_representation_policy": first["source_representation_policy"],
        "network_alternatives": [design(center, first["start"], first["end"], crossing["end"], offset=.25), design(center, first["start"], first["end"], crossing["end"], offset=0)],
        "objective_weights": {"length_m": 1, "fitting_count": 0},
        "physics": {"density_kg_m3": 1000, "darcy_friction": .02, "maximum_velocity_m_s": 2, "gravity_m_s2": 9.80665,
            "elbow_loss_coefficient": .2, "tee_straight_loss_coefficient": .2, "tee_branch_loss_coefficient": 1.2,
            "source_kinetic_energy_correction": 1, "sink_kinetic_energy_correction": 1,
            "applicability": "Hypothetical stationary incompressible water scenario with caller-supplied Darcy and equal-tee loss parameters; no manufacturer or actual building operating-data claim",
            "fixed_flow_control_assumption": "External controls are assumed to impose both specified demand flows simultaneously; no operating-point solution is inferred",
            "friction_convention": "DARCY", "elbow_loss_reference": "EXCESS_LOCAL_LOSS_EXCLUDING_CURVED_PIPE_FRICTION",
            "tee_loss_reference": "INLET_VELOCITY_TOTAL_IRREVERSIBLE_LOSS", "boundary_loss_scope": "BETWEEN_PHYSICAL_NETWORK_PORTS_ONLY"},
        "assumptions": ["Hypothetical added two-demand shared service; original building service intent is not inferred",
            "Two explicit fixed-endpoint component layouts are frozen before checking; this is finite alternative selection, not unrestricted topology search",
            "This new shared-source mission differs from the earlier independent crossing-services mission, so their total lengths are not an optimization comparison"]}
    scenario = SharedNetworkScenario.model_validate(spec)
    output = Path("evidence/benchmarks/shared-network/office") / uuid.uuid4().hex
    output.mkdir(parents=True)
    frozen = {"mission": scenario.model_dump(mode="json", by_alias=True), "baseline_root": prior_run["base_root"],
        "prior_candidate_used_only_for_zone": prior["id"], "source_hashes": [s["sha256"] for s in baseline["sources"]],
        "scope": "Real IFC source with two explicitly frozen hypothetical shared-service layouts"}
    atomic_json(output / "frozen-input.json", frozen)
    project = store.create_project("WBDG Office · shared trunk and tee", copy.deepcopy(baseline))
    run = store.create_run(project["id"], {"operation": "optimize", "mission": frozen["mission"], "budget_seconds": 1200})
    store.claim_run(run["id"], "worker")
    started = time.perf_counter()
    route_project_run(store, run, WorkerControl(store, run["id"]))
    candidates = [c for c in store.candidates(project["id"]) if c["run_id"] == run["id"]]
    rows = []
    for candidate in candidates:
        report = store.get(candidate["report_root"]) if candidate.get("report_root") else None
        if report:
            atomic_json(output / f"{candidate['id']}.report.json", report)
        rows.append({"candidate_id": candidate["id"], "state_root": candidate["state_root"], "report_root": candidate.get("report_root"),
            "status": candidate["status"], "objective": report["objective"] if report else None})
    accepted = sorted((r for r in rows if r["status"] == "CHECKED"), key=lambda r: (r["objective"]["length_m"], r["candidate_id"]))
    bundle = None
    if accepted:
        selected = accepted[0]
        store.accept(project["id"], selected["candidate_id"], 0, f"network:{run['id']}", checker_version=checker_version())
        bundle = export_project(store, project["id"], selected["candidate_id"], draft=False)
    result = {"project_id": project["id"], "run_id": run["id"], "status": store.run(run["id"])["status"], "checker_version": checker_version(),
        "frozen_input_root": digest(frozen), "candidates": rows, "export": bundle, "seconds": time.perf_counter()-started,
        "optimization_scope": "Selection among two supplied fixed-requirement physical network layouts; no global continuous lower bound",
        "whole_building": "NOT_CERTIFIED", "operating_point": "NOT_ESTABLISHED"}
    atomic_json(output / "result.json", result)
    print(json.dumps({"evidence": str(output), **result}, indent=2), flush=True)


if __name__ == "__main__":
    main()
