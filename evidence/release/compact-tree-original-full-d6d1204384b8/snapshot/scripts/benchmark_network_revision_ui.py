"""Revise the accepted real Office network under one frozen executable build.

The revision extends equal tee takeouts by 20 mm and shortens adjacent straight
pieces accordingly. Fixed terminal/service requirements are preserved. This is
a physical revision demonstration, not an asserted objective improvement.
"""
from pathlib import Path
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if not os.environ.get("OMA_EXECUTABLE_BUILD"):
    sys.path.insert(0, str(ROOT / "src"))
    from oma.build_identity import frozen_environment
    if __name__ == "__main__":
        child = subprocess.Popen([sys.executable, __file__, *sys.argv[1:]],
            env=frozen_environment(ROOT / ".oma" / "benchmark-builds"),
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        for line in child.stdout:
            print(line, end="", flush=True)
        raise SystemExit(child.wait())

import argparse
import copy
import json
import time
import uuid

from oma.build_identity import checker_version
from oma.exporting import export_project
from oma.ifc.audit import atomic_json
from oma.routing.engine import route_project_run
from oma.routing.network_scenario import SharedNetworkScenario, network_fixed_requirements, proposed_cap
from oma.service import EngineService
from oma.store import Store, digest
from oma.worker import WorkerControl

PROJECT = "a561fdf78fcc411295e4821cb560c829"


def prepare(store):
    project = store.project(PROJECT)
    baseline = store.get(project["state_root"])
    old = baseline["physical_networks"]
    if len(old) != 1 or baseline.get("routes"):
        raise ValueError("Benchmark requires the one accepted Office network")
    contract = baseline["derived_artifacts"]["network_contract"]
    prior = SharedNetworkScenario.model_validate(contract["scenario"])
    design = copy.deepcopy(next(n for n in contract["scenario"]["network_alternatives"]
        if n["network_id"] == contract["selected_alternative"]))
    design["network_id"] = "office-tee-revision-" + uuid.uuid4().hex[:10]
    parts = {p["id"]: p for p in design["components"]}
    modifications = []
    for component in design["components"]:
        if component["kind"] != "tee":
            continue
        before = copy.deepcopy(component["geometry"])
        component["geometry"]["trunk_takeout_m"] += .02
        component["geometry"]["branch_takeout_m"] += .02
        # Revalidate the tee independently before asking its cap positions.
        from oma.routing.network_scenario import Tee
        tee = Tee.model_validate(component)
        for link in design["connections"]:
            if link["sink"]["component"] == component["id"]:
                adjacent = parts[link["source"]["component"]]
                if adjacent["kind"] != "segment" or link["source"]["port"] != "b":
                    raise ValueError("This bounded benchmark requires straight pieces at each tee cap")
                adjacent["geometry"]["end_m"] = list(proposed_cap(tee, link["sink"]["port"]))
            if link["source"]["component"] == component["id"]:
                adjacent = parts[link["sink"]["component"]]
                if adjacent["kind"] != "segment" or link["sink"]["port"] != "a":
                    raise ValueError("This bounded benchmark requires straight pieces at each tee cap")
                adjacent["geometry"]["start_m"] = list(proposed_cap(tee, link["source"]["port"]))
        modifications.append({"component_id": component["id"], "before": before, "after": component["geometry"]})
    if not modifications:
        raise ValueError("No accepted tee was available to revise")
    mission = copy.deepcopy(contract["scenario"])
    mission.update(source_id=contract["source_id"], replace_network_id=old[0]["id"], network_alternatives=[design])
    scenario = SharedNetworkScenario.model_validate(mission)
    if network_fixed_requirements(prior, contract["source_id"]) != network_fixed_requirements(scenario, contract["source_id"]):
        raise ValueError("Benchmark attempted to modify fixed requirements")
    return {"project_id": PROJECT, "base_revision": project["revision"], "base_root": project["state_root"],
        "previous_network": old[0], "previous_contract": contract,
        "fixed_requirements_root": digest(network_fixed_requirements(prior, contract["source_id"])),
        "mission": scenario.model_dump(mode="json", by_alias=True), "physical_modifications": modifications,
        "source_hashes": [s["sha256"] for s in baseline["sources"]],
        "scope": "Actual IFC source; existing hypothetical fixed-flow service; explicit tee-takeout revision only"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--input", type=Path)
    args = parser.parse_args()
    store = Store(ROOT / ".oma")
    frozen = json.loads(args.input.read_text(encoding="utf-8")) if args.input else prepare(store)
    output = args.input.parent if args.input else ROOT / "evidence/benchmarks/network-revisions/office" / uuid.uuid4().hex
    output.mkdir(parents=True, exist_ok=True)
    if not args.input:
        atomic_json(output / "frozen-input.json", frozen)
    print(json.dumps({"stage": "INPUT_READY", "evidence": str(output), "base_revision": frozen["base_revision"],
        "checker_version": checker_version()}), flush=True)
    if args.prepare_only:
        return
    current = store.project(PROJECT)
    if current["state_root"] != frozen["base_root"] or current["revision"] != frozen["base_revision"]:
        raise ValueError("Accepted head changed after freezing the proposed revision")
    service = EngineService(store.directory)
    atomic_json(output / "before-snapshot.json", service.snapshot(PROJECT))
    run = store.create_run(PROJECT, {"operation": "optimize", "mission": frozen["mission"], "budget_seconds": 900,
        "idempotency_key": "office-network-revision:" + digest(frozen)})
    store.claim_run(run["id"], "worker")
    started = time.perf_counter()
    atomic_json(output / "progress.json", {"run_id": run["id"], "stage": "CHECKING", "checker_version": checker_version()})
    print(json.dumps({"stage": "CHECKING", "run_id": run["id"]}), flush=True)
    try:
        route_project_run(store, run, WorkerControl(store, run["id"]))
        rows = []
        for candidate in store.candidates(PROJECT):
            if candidate["run_id"] != run["id"]:
                continue
            report = store.get(candidate["report_root"]) if candidate.get("report_root") else None
            rows.append({**candidate, "report": report})
        if len(rows) != 1 or rows[0]["status"] != "CHECKED" or rows[0]["report"]["checker_version"] != checker_version():
            raise ValueError("Fresh frozen checker did not establish the one revision candidate: " + str([(c['id'], c['status']) for c in rows]))
        candidate = rows[0]
        atomic_json(output / "candidate-snapshot.json", service.snapshot(PROJECT, candidate_id=candidate["id"]))
        acceptance = store.accept(PROJECT, candidate["id"], frozen["base_revision"],
            "accept-office-network-revision:" + run["id"], checker_version=checker_version())
        print(json.dumps({"stage": "ACCEPTED", "candidate_id": candidate["id"], "revision": acceptance["revision"]}), flush=True)
        exported = export_project(store, PROJECT, candidate["id"], draft=False)
        atomic_json(output / "after-snapshot.json", service.snapshot(PROJECT))
        result = {"status": "CHECKED_ACCEPTED_EXPORTED_RECHECKED", "project_id": PROJECT,
            "run_id": run["id"], "candidate_id": candidate["id"], "accepted_revision": acceptance["revision"],
            "checker_version": checker_version(), "frozen_input_root": digest(frozen), "candidates": rows,
            "export": exported, "seconds": time.perf_counter() - started,
            "comparison": "Tee takeouts extended by20mm; fixed terminals and complete service requirements unchanged. No objective improvement is asserted.",
            "whole_building_adequacy": "NOT_CERTIFIED", "operating_point": "NOT_ESTABLISHED", "global_optimality": "NOT_ESTABLISHED"}
        atomic_json(output / "result.json", result)
        print(json.dumps({k: result[k] for k in ("status", "candidate_id", "accepted_revision", "seconds", "export")}), flush=True)
    except Exception as exc:
        atomic_json(output / "failure.json", {"status": "FAILED", "run_id": run["id"], "reason": str(exc),
            "seconds": time.perf_counter() - started, "checker_version": checker_version()})
        raise


if __name__ == "__main__":
    main()
