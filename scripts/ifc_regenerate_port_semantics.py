"""Regenerate a prior geometric proposal from original sources after IFC-PORT-001.

This is semantic correction/reverification, not a new optimization comparison.
All historical states, reports, source files and exported artifacts stay intact.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from oma.build_identity import checker_version, frozen_environment
from oma.ifc.audit import atomic_json, sha256_file
from oma.models import Demand, Mission, Route
from oma.routing.joint import _new_obligation, baseline_contracts
from oma.routing.joint_materialize import materialize_route_set
from oma.routing.scenario import RoutingScenario
from oma.store import Store, digest
from oma.worker import WorkerControl, import_sources


def geometric_requirement(spec):
    # Identity changes; physical choices and source/federation coordinates do not.
    return {key: value for key, value in spec.items() if key != "route_id"}


def regenerate(candidate_id, project_label, timeout=1800):
    started = time.perf_counter()
    store = Store(ROOT / ".oma")
    previous = store.candidate(candidate_id)
    previous_run = store.run(previous["run_id"])
    previous_state = store.get(previous["state_root"])
    original_baseline = store.get(previous_run["base_root"])
    if original_baseline.get("routes"):
        raise ValueError("This correction tool requires an original import baseline; cumulative route history needs an explicit regeneration plan")
    contracts_before = baseline_contracts(previous_state)
    request = copy.deepcopy(previous_run["request"]["mission"])
    attempt_id = uuid.uuid4().hex
    directory = ROOT / "evidence/benchmarks/real-repair" / project_label / "port-regeneration" / attempt_id
    directory.mkdir(parents=True, exist_ok=False)
    record = {"schema": "oma-port-regeneration/1", "advisory": "IFC-PORT-001", "attempt_id": attempt_id,
        "previous_project_id": previous["project_id"], "previous_candidate_id": candidate_id,
        "previous_candidate_root": previous["state_root"], "previous_report_root": previous["report_root"],
        "previous_run_id": previous_run["id"], "original_baseline_root": previous_run["base_root"],
        "fixed_request": request, "fixed_request_root": digest(request), "status": "STARTED",
        "started_at": time.time(), "scope": "Semantic regeneration of the exact prior geometric proposal; no new optimizer or improvement claim"}
    atomic_json(directory / "attempt.json", record)
    run = None
    try:
        paths = [store.resolve_path(s["immutable_path"]) for s in original_baseline["sources"]]
        for source, path in zip(original_baseline["sources"], paths):
            if sha256_file(path) != source["sha256"]:
                raise ValueError("Original immutable source changed")
        created = store.create_project(f"{project_label.replace('_', ' ').title()} - corrected IFC port semantics", {"sources": [], "entities": []})
        imported = store.create_run(created["id"], {"operation": "import", "paths": [str(path) for path in paths]})
        record.update(project_id=created["id"], import_run_id=imported["id"], status="IMPORTING_ORIGINAL_SOURCES")
        atomic_json(directory / "result.json", record)
        print(json.dumps({"stage": record["status"], "project_id": created["id"], "previous_candidate_id": candidate_id}), flush=True)
        import_sources(store, imported, WorkerControl(store, imported["id"]))
        baseline = store.get(store.project(created["id"])["state_root"])
        if [s["sha256"] for s in baseline["sources"]] != [s["sha256"] for s in original_baseline["sources"]]:
            raise ValueError("Complete original source denominator or order changed")
        for before, after in zip(original_baseline["sources"], baseline["sources"]):
            if before.get("transform_m") != after.get("transform_m"):
                raise ValueError("Original frozen source transform changed")
        run = store.create_run(created["id"], {"operation": "semantic_regeneration", "mission": request,
            "previous_candidate_id": candidate_id, "advisory": "IFC-PORT-001", "budget_seconds": timeout})
        control = WorkerControl(store, run["id"])
        state = copy.deepcopy(baseline)
        contracts, specifications, routes, mapping = {}, {}, [], []
        for index, before_route in enumerate(previous_state["routes"]):
            old_id = before_route["id"]
            before_contract = contracts_before[old_id]
            scenario = RoutingScenario.model_validate(before_contract["scenario"])
            old_manifest = store.get(before_route["geometry_artifact"])
            if sha256_file(store.resolve_path(old_manifest["export_path"])) != old_manifest["export_sha256"]:
                raise ValueError("Prior geometric proposal bytes changed")
            new_id = f"oma-ports-{run['id'][:12]}-{index:03d}"
            contract, ports, section = _new_obligation(baseline, scenario, new_id, before_contract["request_demand_id"], before_contract["source_id"])
            if contract["scenario"] != before_contract["scenario"]:
                raise ValueError("Prior fixed scenario changes under current schema; explicit amendment required")
            contracts[new_id] = contract
            spec = copy.deepcopy(old_manifest["route_spec"])
            spec["route_id"] = new_id
            specifications[new_id] = spec
            if geometric_requirement(spec) != geometric_requirement(old_manifest["route_spec"]):
                raise ValueError("Physical route requirements changed during port correction")
            state.setdefault("ports", []).extend(p.model_dump(mode="json") for p in ports)
            state.setdefault("assumptions", []).append({"kind": "explicit_scenario", "root": digest(contract["scenario"]), "data": contract["scenario"]})
            routes.append(Route(id=new_id, demand_ids=(contract["mission"]["demands"][0]["id"],), service=scenario.system_type,
                points_m=tuple(tuple(p) for p in spec["points_m"]), section=section, port_ids=tuple(p.id for p in ports), status="MATERIALIZED").model_dump(mode="json"))
            mapping.append({"old_route_id": old_id, "new_route_id": new_id, "geometry_requirements_root": digest(geometric_requirement(spec)),
                "previous_geometry_artifact": before_route["geometry_artifact"], "previous_export_sha256": old_manifest["export_sha256"],
                "source_sha256": before_contract["source_id"], "scenario_root": digest(contract["scenario"])})
        materialized = materialize_route_set(store, baseline, contracts, specifications,
            store.directory / "candidates" / run["id"] / "port-regeneration", control.checkpoint)
        for route, mapped in zip(routes, mapping):
            manifest = materialized[route["id"]]
            if manifest.get("port_axis_convention") != "IFC_FLOW_AXIS_V1":
                raise ValueError("Corrected materialization marker missing; no verification can proceed")
            route["geometry_artifact"] = store.put(manifest)
            mapped.update(new_geometry_artifact=route["geometry_artifact"], new_export_sha256=manifest["export_sha256"],
                new_physical_guids=[p["ifc_guid"] for p in manifest["added_parts"]])
        state["routes"] = routes
        derived = state.setdefault("derived_artifacts", {})
        derived["route_exports"] = [{"source_id": contracts[r]["source_id"], "route_spec": specifications[r]} for r in specifications]
        joint = "route_demands" in request
        if joint:
            missions = [contracts[r]["mission"] for r in sorted(contracts)]
            state["mission"] = Mission(id=f"joint:{run['id']}", demands=tuple(Demand.model_validate(d) for m in missions for d in m["demands"]),
                protected_ids=tuple(e["id"] for e in baseline.get("entities", [])), allowed_zones=tuple(z for m in missions for z in m["allowed_zones"]),
                rule_hash=digest([m["rule_hash"] for m in missions]), catalog_hash=digest([m["catalog_hash"] for m in missions]),
                scenario_hash=digest([m["scenario_hash"] for m in missions]), objective_weights=missions[0]["objective_weights"]).model_dump(mode="json")
            derived["routing_contracts"] = contracts
        else:
            if len(routes) != 1:
                raise ValueError("Single-route request has multiple physical routes")
            route_id = routes[0]["id"]
            state["mission"] = contracts[route_id]["mission"]
            derived.update(routing_scenario=contracts[route_id]["scenario"],
                route_materialization={"root": routes[0]["geometry_artifact"], "source_id": contracts[route_id]["source_id"], "path": materialized[route_id]["export_path"]})
        derived["port_semantic_regeneration"] = {"advisory": "IFC-PORT-001", "previous_candidate_root": previous["state_root"],
            "fixed_request_root": digest(request), "route_mapping_root": digest(mapping), "new_optimizer_comparison": False}
        candidate = store.add_candidate(run["id"], state, {"kind": "physical_route_set" if joint else "physical_route",
            "changed_ids": [r["id"] for r in routes], "routes": routes, "objective": {},
            "rationale": "Regenerated existing geometric proposal with corrected IFC port semantics; no new optimizer comparison"})
        record.update(status="FRESH_CHECKING", run_id=run["id"], candidate_id=candidate["id"], candidate_root=candidate["state_root"], route_mapping=mapping,
            sources=[{"source_sha256": s["sha256"], "transform_m": s.get("transform_m")} for s in baseline["sources"]])
        atomic_json(directory / "result.json", record)
        store.update_run(run["id"], "CHECKING", "Fresh independent check of corrected physical IFC proposal", "verification")
        print(json.dumps({"stage": "FRESH_CHECKING", "candidate_id": candidate["id"], "checker_version": checker_version()}), flush=True)
        process = subprocess.run([sys.executable, "-m", "oma.verification", str(store.directory), candidate["id"]], capture_output=True,
            text=True, timeout=timeout, env=frozen_environment(store.directory), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if process.returncode:
            raise RuntimeError(process.stderr[-5000:])
        checked = store.candidate(candidate["id"])
        report = store.get(checked["report_root"])
        record.update(status="CORRECTED_CHECKED_AWAITING_ACCEPTANCE" if checked["status"] == "CHECKED" else "CORRECTION_NOT_CHECKED",
            candidate_status=checked["status"], report_root=checked["report_root"], checker_version=report["checker_version"], objective=report["objective"])
        store.update_run(run["id"], "COMPLETED" if checked["status"] == "CHECKED" else "NO_INCUMBENT_FOUND",
            "Semantic regeneration proposal independently examined; no optimization claim", "complete", payload={"candidate_id": candidate["id"], "status": checked["status"]})
    except Exception as exc:
        record.update(status="FAILED", error=f"{type(exc).__name__}: {exc}")
        if run is not None:
            store.update_run(run["id"], "FAILED", record["error"], "port_regeneration_failure")
    record["seconds"] = time.perf_counter() - started
    atomic_json(directory / "result.json", record)
    print(json.dumps(record), flush=True)
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--project-label", required=True)
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()
    outcome = regenerate(args.candidate, args.project_label, args.timeout)
    raise SystemExit(0 if outcome["status"] == "CORRECTED_CHECKED_AWAITING_ACCEPTANCE" else 1)
