"""Supervised fresh candidate checks with deferred report publication.

The checker may persist immutable evidence and poll live controls, but its
Store adapter cannot mark a live candidate CHECKED. Only the parent publishes
the private receipt after the complete owned process tree exits successfully.
The Store execution token fences concurrent checks and cancellation at commit.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
import time
import uuid

from oma.build_identity import checker_version, frozen_environment
from oma.export_checks import supervise_check
from oma.ifc.audit import atomic_json
from oma.models import VerificationReport
from oma.store import IntegrityError, Store, TERMINAL_RUN_STATUSES, digest, utcnow


class DeferredVerificationStore(Store):
    """Use ordinary immutable inputs/artifacts without child publication authority."""

    def __init__(self, directory, request_path):
        super().__init__(directory)
        self.request_path = Path(request_path).resolve()
        self.request = json.loads(self.request_path.read_text(encoding="utf-8"))
        self.request_root = digest(self.request)
        self.receipt_path = self.request_path.parent / "receipt.json"
        self._recorded = False
        if self.request["checker_version"] != checker_version():
            raise IntegrityError("Deferred checker executable does not match its invocation")
        current = self.candidate(self.request["candidate_id"])
        if current["state_root"] != self.request["candidate_root"]:
            raise IntegrityError("Deferred checker candidate changed before launch")

    def record_verification(self, candidate_id, report):
        report = VerificationReport.model_validate(report)
        if self._recorded or self.receipt_path.exists():
            raise IntegrityError("A checker invocation may produce only one report receipt")
        current = self.candidate(candidate_id)
        bindings = {
            "candidate_id": candidate_id == self.request["candidate_id"],
            "candidate_root": report.candidate_root == current["state_root"] == self.request["candidate_root"],
            "checker_version": report.checker_version == self.request["checker_version"] == checker_version(),
            "mission_hash": report.mission_hash == self.request["mission_hash"],
            "rule_hash": report.rule_hash == self.request["rule_hash"],
        }
        if not all(bindings.values()):
            raise IntegrityError("Deferred report binding mismatch: " + ", ".join(k for k, ok in bindings.items() if not ok))
        report_root = self.put(report)
        receipt = {"schema_version": 1, "execution_id": self.request["execution_id"],
            "request_root": self.request_root, "candidate_id": candidate_id,
            "candidate_root": report.candidate_root, "checker_version": report.checker_version,
            "report_root": report_root, "report_status": report.status.value,
            "publication_authority": "NONE_CHILD_RECEIPT_ONLY", "created_at": utcnow()}
        atomic_json(self.receipt_path, receipt)
        self._recorded = True
        return {**current, "status": "DEFERRED", "report_root": report_root}


def _command(store, request_path):
    return [sys.executable, "-m", "oma.routing.check_execution", "--child",
            str(store.directory), str(request_path)]


def _read_receipt(store, request, directory):
    receipt = json.loads((directory / "receipt.json").read_text(encoding="utf-8"))
    expected = {"schema_version": 1, "execution_id": request["execution_id"],
        "request_root": digest(request), "candidate_id": request["candidate_id"],
        "candidate_root": request["candidate_root"], "checker_version": request["checker_version"],
        "publication_authority": "NONE_CHILD_RECEIPT_ONLY"}
    if any(receipt.get(key) != value for key, value in expected.items()):
        raise IntegrityError("Private checker receipt does not bind the current invocation")
    report = VerificationReport.model_validate(store.get(receipt["report_root"]))
    if (report.candidate_root != request["candidate_root"] or report.checker_version != request["checker_version"]
            or report.mission_hash != request["mission_hash"] or report.rule_hash != request["rule_hash"]
            or report.status.value != receipt.get("report_status")):
        raise IntegrityError("Private checker report does not match its receipt and fixed mission")
    return receipt, report


def run_candidate_check(store, candidate_id, *, deadline, control_run_id=None,
                        memory_limit_bytes=None, reserve_bytes=2 * 1024**3, environment=None):
    """Return a control/process outcome; geometric verdict is only the bound report.

    ``deadline`` is the caller's shared monotonic deadline, not a new per-child
    allowance. A cancelled, incomplete, stale or abnormal invocation cannot
    publish its report. Historical prior reports stay retained in the execution
    record. Callers select from the resulting live candidate only on COMPLETED.
    ``control_run_id`` is required for a separately requested historical recheck;
    an originating route/check run uses the candidate's own run by default.
    An existing workflow may supply its already frozen ``environment``. Its
    exact build is still checked by Store admission and the fresh child.
    """
    if isinstance(deadline, bool) or not isinstance(deadline, (float, int)) or not math.isfinite(deadline):
        raise ValueError("Checker deadline must be a finite monotonic timestamp")
    if memory_limit_bytes is not None and (isinstance(memory_limit_bytes, bool) or not isinstance(memory_limit_bytes, int) or memory_limit_bytes <= 0):
        raise ValueError("Checker memory limit must be a positive integer byte count")
    if isinstance(reserve_bytes, bool) or not isinstance(reserve_bytes, int) or reserve_bytes < 0:
        raise ValueError("Checker machine reserve must be a nonnegative integer byte count")
    candidate = store.candidate(candidate_id)
    environment = frozen_environment(store.directory) if environment is None else dict(environment)
    if control_run_id is not None and control_run_id != candidate["run_id"]:
        environment["OMA_CONTROL_RUN_ID"] = control_run_id
    else:
        environment.pop("OMA_CONTROL_RUN_ID", None)
    execution_id = uuid.uuid4().hex
    directory = store.directory / "checks" / "candidate-executions" / execution_id
    directory.mkdir(parents=True, exist_ok=False)
    state = store.get(candidate["state_root"])
    control_id = control_run_id or candidate["run_id"]
    controlled = store.run(control_id)["status"] not in TERMINAL_RUN_STATUSES

    def cancelled():
        run = store.run(control_id)
        return controlled and (run["desired_action"] == "cancel" or run["status"] in {"CANCELLED", "CRASHED", "TIMED_OUT", "FAILED"})

    binding = store.begin_check_execution(candidate_id, execution_id,
        checker_version=environment["OMA_EXECUTABLE_BUILD"], control_run_id=control_run_id, deadline=deadline)
    request = {"schema_version": 1, "execution_id": execution_id, "candidate_id": candidate_id,
        "candidate_root": candidate["state_root"], "checker_version": environment["OMA_EXECUTABLE_BUILD"],
        "mission_hash": digest(state.get("mission")),
        "rule_hash": (state.get("mission") or {}).get("rule_hash", "baseline-unapproved-contact-policy"),
        "binding": binding, "control_run_id": control_run_id}
    result = {"execution_id": execution_id, "candidate_id": candidate_id, "directory": str(directory),
        "status": "NOT_RUN", "publication_authority": "PARENT_AFTER_COMPLETE_PROCESS_TREE_AND_ATOMIC_TOKEN_CHECK",
        "request_root": digest(request), "report_published": False}
    report = None
    try:
        atomic_json(directory / "request.json", request)
        supervision = supervise_check(_command(store, directory / "request.json"), environment=environment,
            directory=directory / "process", deadline=deadline, memory_limit_bytes=memory_limit_bytes,
            reserve_bytes=reserve_bytes, cancellation_requested=cancelled)
        result.update(status=supervision["status"], supervision=supervision)
        # Preserve a late/abnormal receipt as an observation, never as authority.
        if (directory / "receipt.json").exists():
            result["observed_receipt"] = json.loads((directory / "receipt.json").read_text(encoding="utf-8"))
        if result["status"] == "COMPLETED":
            if cancelled():
                result.update(status="CANCELLED", reason="Cancellation observed before report admission")
            elif time.monotonic() >= deadline:
                result.update(status="UNKNOWN_TIMEOUT", reason="Shared deadline expired before report admission")
            else:
                receipt, report = _read_receipt(store, request, directory)
                result.update(observed_receipt=receipt, report_root=receipt["report_root"], report_status=report.status.value)
    except Exception as exc:
        result.update(status="UNKNOWN_EXECUTION_ERROR", reason=f"{type(exc).__name__}: {exc}")
        report = None
    evidence_root = store.put(result)
    result["evidence_root"] = evidence_root
    try:
        finished = store.finish_check_execution(candidate_id, execution_id, status=result["status"],
            report=report, evidence_root=evidence_root)
        result["candidate"] = finished
        result["report_published"] = result["status"] == "COMPLETED" and finished.get("report_root") == result.get("report_root")
    except Exception as exc:
        result.update(status="UNKNOWN_ADMISSION_REJECTED", reason=f"{type(exc).__name__}: {exc}")
        # A failed COMPLETED transaction publishes nothing. Close only this
        # still-owned token; an older invocation must not invalidate a newer one.
        rejection_root = store.put(result)
        try:
            result["candidate"] = store.finish_check_execution(candidate_id, execution_id,
                status=result["status"], report=report, evidence_root=rejection_root)
        except Exception as final_exc:
            result["admission_cleanup"] = f"{type(final_exc).__name__}: {final_exc}"
    atomic_json(directory / "execution.json", result)
    return result


def _child(directory, request_path):
    store = DeferredVerificationStore(directory, request_path)
    candidate = store.candidate(store.request["candidate_id"])
    # Same independent checker dispatch as oma.verification; no optimizer code.
    if candidate.get("kind") == "physical_network":
        from oma.routing.network_checker import verify_network_candidate as verify
    elif candidate.get("kind") == "physical_route_set":
        from oma.routing.joint_checker import verify_joint_candidate as verify
    elif candidate.get("kind") == "physical_route":
        from oma.routing.checker import verify_route_candidate as verify
    else:
        from oma.verification import verify_baseline as verify
    report = verify(store, candidate["id"])
    if not store._recorded:
        raise IntegrityError("Independent checker returned without a report receipt")
    print(json.dumps({"status": report.status.value, "candidate_root": report.candidate_root,
                      "publication_authority": "NONE_CHILD_RECEIPT_ONLY"}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--child", action="store_true", required=True)
    parser.add_argument("directory")
    parser.add_argument("request_path")
    arguments = parser.parse_args()
    _child(arguments.directory, arguments.request_path)


if __name__ == "__main__":
    main()
