"""Replay actual persisted state changes; no building revision is modified."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from oma.build_identity import checker_version
from oma.project_dependencies import derive_transition
from oma.project_assurance import candidate_assurance
from oma.store import Store


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate")
    parser.add_argument("--project")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    store = Store(".oma")
    if args.candidate:
        candidate = store.candidate(args.candidate)
        before = store.get(store.run(candidate["run_id"])["base_root"])
        after = store.get(candidate["state_root"])
        report = store.get(candidate["report_root"]) if candidate["report_root"] else None
        mode = "ACTUAL_CANDIDATE_TRANSITION"
    else:
        project = store.project(args.project)
        before = after = store.get(project["state_root"])
        report, mode = None, "UNCHANGED_REAL_FEDERATION_REUSE"
    print(json.dumps({"stage": "LOADED", "mode": mode, "entities": len(after.get("entities", [])),
                      "sources": len(after.get("sources", [])), "routes": len(after.get("routes", []))}), flush=True)
    started = time.perf_counter()
    evidence = derive_transition(before, after, executable=checker_version(), after_report=report)
    evidence["benchmark"] = {"mode": mode, "candidate_id": args.candidate, "project_id": after["project_id"],
                             "engine_version": checker_version(), "native_geometry_checks": "NOT_RUN_BY_THIS_BENCHMARK"}
    if args.candidate:
        evidence["assurance"] = candidate_assurance(store, args.candidate)
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"stage": "COMPLETE", "cold_equivalent": evidence["cold_equivalent"],
        "recomputed": evidence["recomputed"], "reused": evidence["reused"], "seconds": time.perf_counter() - started,
        "evidence": str(destination)}), flush=True)


if __name__ == "__main__":
    if not os.environ.get("OMA_EXECUTABLE_BUILD"):
        from oma.build_identity import frozen_environment
        environment = frozen_environment(Path(".oma") / "benchmark-builds")
        raise SystemExit(subprocess.call([sys.executable, __file__, *sys.argv[1:]], env=environment))
    main()
