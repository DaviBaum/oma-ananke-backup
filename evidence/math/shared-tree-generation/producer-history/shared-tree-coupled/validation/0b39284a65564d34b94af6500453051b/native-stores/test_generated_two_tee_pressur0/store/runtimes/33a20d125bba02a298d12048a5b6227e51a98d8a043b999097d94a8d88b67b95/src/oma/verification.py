"""Independent checker entry point reloads persisted state in a fresh process.

This module must not import optimizer scores, flags, caches, or routing search
helpers. Mature-kernel common-mode limitations are included in each report.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from .models import CheckResult, VerificationReport, Verdict
from .store import Store, digest, utcnow

from .build_identity import checker_version

CHECKER_VERSION = checker_version()


def candidate_control(store, candidate):
    """Route a requested recheck's controls without changing its original mission."""
    from .worker import WorkerControl
    owner = os.environ.get("OMA_CONTROL_RUN_ID")
    if owner:
        run = store.run(owner)
        if (run["operation"] != "recheck" or run["request"].get("candidate_id") != candidate["id"]
                or run["project_id"] != candidate["project_id"]):
            raise ValueError("Independent checker control run does not own this requested recheck")
    return WorkerControl(store, owner or candidate["run_id"])


def verify_baseline(store: Store, candidate_id: str):
    from .ifc.check import check_files
    from .ifc.audit import sha256_file
    candidate = store.candidate(candidate_id)
    state = store.get(candidate["state_root"])
    sources = state.get("sources", [])
    results = []
    paths = []
    control = candidate_control(store, candidate)
    for source in sources:
        path = store.resolve_path(source["immutable_path"])
        matched = path.is_file() and sha256_file(path) == source["sha256"]
        results.append(CheckResult(id=f"input-integrity:{source['id']}", status=Verdict.PASS if matched else Verdict.FAIL,
                                   reason="Immutable source hash matches" if matched else "Immutable source missing or changed",
                                   scope=source["name"]))
        if matched:
            paths.append(path)
        for blocker in source.get("blockers", []):
            results.append(CheckResult(id=f"input-coverage:{source['id']}:{blocker['code']}", status=Verdict.BLOCKED,
                                       reason=f"Unresolved source obligation: {blocker['code']}", scope=source["name"],
                                       participants=tuple(blocker.get("entity_ids", []))))
    if len(paths) == len(sources) and paths:
        baseline = check_files(paths, clearance_m=0, checkpoint=control.checkpoint)
        artifact = store.put(baseline)
        for issue in baseline["issues"]:
            witness = issue.get("witness", {})
            results.append(CheckResult(id=issue["id"], status=Verdict(issue["status"]), reason=issue["reason"],
                                       scope="Imported tessellated physical geometry; explicit contact authorization unresolved",
                                       participants=tuple(p["entity_id"] for p in issue["participants"]),
                                       witness={"point": witness.get("p1"), "other_point": witness.get("p2"),
                                                "margin_m": -issue["measured_distance_m"],
                                                "required_clearance_m": issue["required_clearance_m"], "artifact": artifact}))
        results.append(CheckResult(id="native-cad-coordination", status=Verdict(baseline["coordination_status"]),
                                   reason=baseline["reason"], scope="Whole imported federation", witness={"artifact": artifact}))
        results.append(CheckResult(id="geometry-object-accounting", status=Verdict.BLOCKED if baseline["unresolved_geometry"] else Verdict.PASS,
                                   reason=f"{len(baseline['unresolved_geometry'])} unresolved physical objects", scope="All source physical products",
                                   participants=tuple(baseline["unresolved_geometry"])))
    else:
        results.append(CheckResult(id="physical-geometry", status=Verdict.BLOCKED, reason="No complete immutable source set", scope="Project"))
    if state.get("mission") is None:
        results.append(CheckResult(id="mission", status=Verdict.BLOCKED, reason="No explicit engineering mission; loads, terminals and service obligations cannot be verified", scope="Engineering service adequacy"))
    results.append(CheckResult(id="system-engineering", status=Verdict.NOT_RUN,
                               reason="This operation checks imported geometry; independent service/flow/size checks require a defined mission",
                               scope="Hydraulic, electrical and service calculations"))
    verdict = Verdict.FAIL if any(r.status == Verdict.FAIL for r in results) else Verdict.BLOCKED if any(r.status == Verdict.BLOCKED for r in results) else Verdict.UNKNOWN
    report = VerificationReport(candidate_root=candidate["state_root"], mission_hash=digest(state.get("mission")),
                                rule_hash=(state.get("mission") or {}).get("rule_hash", "baseline-unapproved-contact-policy"),
                                checker_version=CHECKER_VERSION, status=verdict, scope="Imported federation baseline; no building release certification",
                                results=tuple(results), objective={}, common_mode_risks=("IfcOpenShell geometry conversion is shared with import; no certified tessellation deviation bound",), created_at=utcnow())
    store.record_verification(candidate_id, report)
    return report


def check_project_run(store, run, control):
    control.checkpoint("check")
    state = store.get(run["base_root"])
    candidate = store.add_candidate(run["id"], state, {"kind": "baseline_check", "changed_ids": [], "routes": [], "objective": {}})
    store.update_run(run["id"], "CHECKING", "Fresh process is rebuilding the baseline check from persisted inputs", "verification")
    from .routing.check_execution import run_candidate_check
    execution = run_candidate_check(store, candidate["id"],
        deadline=time.monotonic() + run["request"].get("budget_seconds", 300))
    control.checkpoint("check")
    if execution["status"] != "COMPLETED" or not execution["report_published"]:
        status = "TIMED_OUT" if execution["status"] == "UNKNOWN_TIMEOUT" else "FAILED"
        store.update_run(run["id"], status, "Baseline checker execution was incomplete; no report was published", "verification",
            artifacts=[execution["evidence_root"]], payload={"execution_status": execution["status"]})
        return
    candidate = execution["candidate"]
    store.update_run(run["id"], "COMPLETED", f"Baseline check finished: {candidate['status']}", "verification", artifacts=[candidate["report_root"]])


def recheck_candidate_run(store, run, control):
    candidate = store.candidate(run["request"]["candidate_id"])
    if candidate["project_id"] != run["project_id"]:
        raise ValueError("Recheck candidate belongs to another project")
    control.checkpoint("recheck")
    store.update_run(run["id"], "CHECKING", "Rechecking the persisted candidate under its immutable original mission", "recheck", payload={"candidate_id": candidate["id"]})
    from .routing.check_execution import run_candidate_check
    execution = run_candidate_check(store, candidate["id"], control_run_id=run["id"],
        deadline=time.monotonic() + run["request"].get("budget_seconds", 300))
    control.checkpoint("recheck_complete")
    if execution["status"] != "COMPLETED" or not execution["report_published"]:
        status = "TIMED_OUT" if execution["status"] == "UNKNOWN_TIMEOUT" else "FAILED"
        store.update_run(run["id"], status, "Fresh recheck execution was incomplete; its report remains unpublished", "recheck",
            artifacts=[execution["evidence_root"]], payload={"candidate_id": candidate["id"], "execution_status": execution["status"]})
        return
    checked = execution["candidate"]
    store.update_run(run["id"], "COMPLETED", f"Fresh candidate check finished: {checked['status']}", "recheck",
        artifacts=[checked["report_root"]], payload={"candidate_id": checked["id"], "status": checked["status"]})


def main():
    store = Store(sys.argv[1])
    candidate = store.candidate(sys.argv[2])
    if candidate.get("kind") == "physical_network":
        from .routing.network_checker import verify_network_candidate
        report = verify_network_candidate(store, candidate["id"])
    elif candidate.get("kind") == "physical_route_set":
        from .routing.joint_checker import verify_joint_candidate
        report = verify_joint_candidate(store, candidate["id"])
    elif candidate.get("kind") == "physical_route":
        from .routing.checker import verify_route_candidate
        report = verify_route_candidate(store, candidate["id"])
    else:
        report = verify_baseline(store, candidate["id"])
    print(json.dumps({"status": report.status.value, "candidate_root": report.candidate_root}))


if __name__ == "__main__":
    main()
