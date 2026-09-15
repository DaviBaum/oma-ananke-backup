"""Freshly check and export an accepted immutable state under a pinned build."""
from pathlib import Path
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if not os.environ.get("OMA_EXECUTABLE_BUILD"):
    sys.path.insert(0, str(ROOT / "src"))
    from oma.build_identity import frozen_environment
    if __name__ == "__main__":
        raise SystemExit(subprocess.call([sys.executable, __file__, *sys.argv[1:]], env=frozen_environment(ROOT / ".oma" / "benchmark-builds")))

import argparse
import json
import time
import uuid
from oma.build_identity import checker_version, frozen_environment
from oma.exporting import export_project
from oma.ifc.audit import atomic_json
from oma.store import Store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--evidence-directory", type=Path, required=True)
    args = parser.parse_args()
    store = Store(ROOT / ".oma")
    before = store.candidate(args.candidate)
    project = store.project(before["project_id"])
    if before["state_root"] != project["state_root"]:
        raise ValueError("Candidate is not the currently accepted immutable project head")
    version = checker_version()
    started = time.monotonic()
    print(json.dumps({"stage": "FRESH_ACCEPTED_STATE_CHECK", "candidate": args.candidate, "checker_version": version}), flush=True)
    subprocess.run([sys.executable, "-m", "oma.verification", str(store.directory), args.candidate],
        env=frozen_environment(store.directory), check=True, timeout=1800)
    candidate = store.candidate(args.candidate)
    report = store.get(candidate["report_root"])
    if candidate["status"] != "CHECKED" or report["checker_version"] != version:
        raise ValueError("Accepted artifact did not pass the current pinned checker")
    exported = export_project(store, project["id"], args.candidate, draft=False)
    result = {"status": "ACCEPTED_STATE_FRESHLY_CHECKED_AND_EXPORTED", "candidate_id": args.candidate,
        "project_id": project["id"], "accepted_revision": project["revision"], "candidate_root": candidate["state_root"],
        "previous_report_root": before["report_root"], "report_root": candidate["report_root"], "report": report,
        "checker_version": version, "export": exported, "geometry_regenerated": False,
        "scope": "Same accepted IFC bytes rechecked under new implementation; no new optimizer comparison",
        "elapsed_seconds": time.monotonic()-started}
    output = args.evidence_directory / (args.candidate + ".recheck-" + version.rsplit(":", 1)[-1][:12] + "-" + uuid.uuid4().hex + ".json")
    atomic_json(output, result)
    atomic_json(Path(exported["directory"]) / "current-recheck-evidence.json", result)
    print(json.dumps({"status": result["status"], "candidate_id": args.candidate, "export_id": exported["export_id"],
        "evidence": str(output), "elapsed_seconds": result["elapsed_seconds"]}), flush=True)


if __name__ == "__main__":
    main()
