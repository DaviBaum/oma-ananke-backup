"""Freshly check, accept and export one real shared-tree benchmark candidate."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from oma.build_identity import checker_version, frozen_environment
from oma.exporting import export_project
from oma.ifc.audit import atomic_json, sha256_file
from oma.store import Store, digest


def finalize(candidate_id, project_label):
    started = time.perf_counter()
    store = Store(ROOT / ".oma")
    version = checker_version()
    candidate = store.candidate(candidate_id)
    state = store.get(candidate["state_root"])
    if len(state.get("physical_networks", [])) != 1 or state.get("routes"):
        raise ValueError("This finalizer requires exactly one shared physical component tree")
    print(json.dumps({"stage": "FRESH_CHECK", "candidate_id": candidate_id, "checker_version": version}), flush=True)
    child = subprocess.run([sys.executable, "-m", "oma.verification", str(store.directory), candidate_id],
        capture_output=True, text=True, timeout=900, env=frozen_environment(store.directory),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if child.returncode:
        raise RuntimeError(child.stderr[-5000:])
    candidate = store.candidate(candidate_id)
    report = store.get(candidate["report_root"])
    if candidate["status"] != "CHECKED" or report["checker_version"] != version or checker_version() != version:
        raise ValueError("Current stable checker did not establish the full shared-network obligations")
    project = store.project(candidate["project_id"])
    accepted = store.accept(project["id"], candidate_id, project["revision"], "final-shared-network:" + candidate_id, checker_version=version)
    print(json.dumps({"stage": "ACCEPTED", "project_id": project["id"], "revision": accepted["revision"]}), flush=True)
    exported = export_project(store, project["id"], candidate_id, draft=False)
    directory = Path(exported["directory"])
    attribution = []
    for source_name, destination in (("license.txt", "source-license.txt"), ("model_card.md", "source-model-card.md")):
        original = ROOT / "data/ifc-bench/projects" / project_label / source_name
        if original.exists():
            target = directory / destination
            shutil.copyfile(original, target)
            attribution.append({"path": str(target), "sha256": sha256_file(target), "original": str(original)})
    request = store.run(candidate["run_id"])["request"]["mission"]
    references = []
    folder = ROOT / "evidence/benchmarks/shared-network" / project_label
    for path in folder.glob("*-frozen-*.json"):
        frozen = json.loads(path.read_text())
        for scenario in frozen.get("scenarios", []):
            if scenario["mission"] == request:
                attempts = []
                for result_path in folder.glob("attempts/*/result.json"):
                    result = json.loads(result_path.read_text())
                    if result.get("scenario_id") == scenario["scenario_id"]:
                        attempts.append({"path": str(result_path.relative_to(ROOT)), "sha256": sha256_file(result_path), "result": result})
                references.append({"scenario_id": scenario["scenario_id"], "specification_root": frozen["specification_root"],
                    "frozen_path": str(path.relative_to(ROOT)), "frozen_scenario_denominator": frozen["frozen_scenario_denominator"], "attempts": attempts})
    result = {"schema": "oma-accepted-shared-network/1", "status": "CHECKED_ACCEPTED_EXPORTED_RECHECKED", "project_id": project["id"],
        "candidate_id": candidate_id, "accepted_revision": accepted["revision"], "checker_version": version,
        "candidate_root": candidate["state_root"], "report_root": candidate["report_root"], "report": report,
        "fixed_mission_root": digest(request), "reference_evidence": references, "export": exported, "source_attribution": attribution,
        "scope": "Unique physical component tree, native terminal/cap connectivity, all source obstacles and explicitly imposed simultaneous flows",
        "whole_building_adequacy": "NOT_CERTIFIED", "operating_point": "NOT_ESTABLISHED", "unrestricted_topology_optimality": "NOT_ESTABLISHED",
        "seconds": time.perf_counter() - started}
    atomic_json(folder / (candidate_id + ".accepted-export.json"), result)
    atomic_json(directory / "shared-network-evidence.json", result)
    print(json.dumps({k: result[k] for k in ("status", "project_id", "candidate_id", "accepted_revision", "seconds", "export")}), flush=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--project-label", required=True)
    args = parser.parse_args()
    finalize(args.candidate, args.project_label)
