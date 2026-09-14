"""Bounded exported-byte checks; incomplete work always remains a draft.

Each export shares one deadline and immutable executable snapshot. Logs retain
at most one MiB per stream; byte counts and full-stream hashes expose truncation.
Only processes discovered below the newly created child are ever terminated.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import threading
import time

import psutil

from .build_identity import frozen_environment
from .ifc.audit import atomic_json, sha256_file
from .models import VerificationReport
from .store import digest, utcnow

DEFAULT_EXPORT_BUDGET_SECONDS = 3600
MAX_EXPORT_BUDGET_SECONDS = 7200
LOG_LIMIT_BYTES = 1024 * 1024
DESCENDANT_SHUTDOWN_GRACE_SECONDS = 1.


def export_budget(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 1 <= value <= MAX_EXPORT_BUDGET_SECONDS:
        raise ValueError("Export budget_seconds must be finite and between 1 and 7200")
    return float(value)


def supervise_check(command, *, environment, directory, deadline, memory_limit_bytes=None, reserve_bytes=2 * 1024**3):
    """Run one child with bounded output, elapsed time and process-tree memory."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    memory_limit_bytes = memory_limit_bytes or min(48 * 1024**3, int(psutil.virtual_memory().total * .375))
    result = {"status": "NOT_RUN", "command": command, "checker_version": environment["OMA_EXECUTABLE_BUILD"],
        "started_at": utcnow(), "memory_limit_bytes": memory_limit_bytes, "machine_reserve_bytes": reserve_bytes,
        "log_limit_bytes_per_stream": LOG_LIMIT_BYTES, "stdout": {}, "stderr": {}, "peak_tree_rss_bytes": 0}
    if started >= deadline:
        result.update(status="UNKNOWN_TIMEOUT", reason="The shared export deadline expired before this check started", elapsed_seconds=0)
        atomic_json(directory / "check.json", result)
        return result
    atomic_json(directory / "check.json", {**result, "status": "STARTING"})
    process = None
    observed = {}
    threads = []
    parent_exit_seen = None

    def drain(stream, name):
        info = result[name]
        path = directory / f"{name}.log"
        info.update(path=str(path), total_bytes=0, retained_bytes=0, truncated=False)
        hasher = hashlib.sha256()
        try:
            with path.open("wb") as output:
                while block := stream.read(65536):
                    hasher.update(block)
                    info["total_bytes"] += len(block)
                    kept = block[:max(0, LOG_LIMIT_BYTES - info["retained_bytes"])]
                    output.write(kept)
                    output.flush()
                    info["retained_bytes"] += len(kept)
        except (OSError, ValueError) as exc:
            info["read_error"] = str(exc)
        finally:
            info.update(sha256_of_observed_stream=hasher.hexdigest(), truncated=info["total_bytes"] > info["retained_bytes"])
            stream.close()

    def observe(parent):
        try:
            for child in [parent, *parent.children(recursive=True)]:
                observed[(child.pid, child.create_time())] = child
        except psutil.NoSuchProcess:
            pass

    def terminate_owned():
        # psutil verifies process creation times before signalling, preventing
        # a recycled PID from becoming a target. Never enumerate unrelated apps.
        killed = []
        for child in reversed(list(observed.values())):
            try:
                if child.is_running():
                    child.kill()
                    killed.append(child.pid)
            except psutil.NoSuchProcess:
                pass
        _, alive = psutil.wait_procs(list(observed.values()), timeout=2)
        result["termination"] = {"signalled_pids": killed, "remaining_pids": [p.pid for p in alive]}

    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        parent = psutil.Process(process.pid)
        observed[(parent.pid, parent.create_time())] = parent
        result.update(status="RUNNING", pid=process.pid, process_created_at=parent.create_time())
        atomic_json(directory / "check.json", result)
        for name in ("stdout", "stderr"):
            thread = threading.Thread(target=drain, args=(getattr(process, name), name), daemon=True)
            thread.start()
            threads.append(thread)
        while True:
            observe(parent)
            rss = 0
            for child in observed.values():
                try:
                    if child.is_running():
                        rss += child.memory_info().rss
                except psutil.NoSuchProcess:
                    pass
            result["peak_tree_rss_bytes"] = max(result["peak_tree_rss_bytes"], rss)
            if time.monotonic() >= deadline:
                result.update(status="UNKNOWN_TIMEOUT", reason="Shared export wall-clock budget exhausted; no physical verdict inferred")
                terminate_owned()
                break
            if rss > memory_limit_bytes or psutil.virtual_memory().available < reserve_bytes:
                result.update(status="UNKNOWN_RESOURCE_LIMIT", reason="Child process tree exceeded its memory contract or machine reserve")
                terminate_owned()
                break
            if process.poll() is not None:
                if any(p.pid != parent.pid and p.is_running() for p in observed.values()):
                    # Windows' venv launcher can acknowledge the Python exit
                    # just before its child completes OS teardown. Continue
                    # deadline/memory supervision during this bounded grace;
                    # a persistent descendant still prevents completion.
                    if parent_exit_seen is None:
                        parent_exit_seen = time.monotonic()
                    result["descendant_shutdown_grace_seconds"] = DESCENDANT_SHUTDOWN_GRACE_SECONDS
                    if time.monotonic()-parent_exit_seen < DESCENDANT_SHUTDOWN_GRACE_SECONDS:
                        time.sleep(min(.05,max(0,deadline-time.monotonic())))
                        continue
                    result.update(status="UNKNOWN_PROCESS_TREE", reason="Checker exited with live descendants")
                    terminate_owned()
                else:
                    result.update(status="COMPLETED" if process.returncode == 0 else "FAILED", returncode=process.returncode)
                break
            time.sleep(min(.1, max(0, deadline - time.monotonic())))
    except Exception as exc:
        result.update(status="UNKNOWN_PROCESS_ERROR", reason=f"{type(exc).__name__}: {exc}")
        if process is not None:
            terminate_owned()
    finally:
        if process is not None:
            try:
                result["returncode"] = process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                result.update(status="UNKNOWN_TERMINATION", reason="Owned child did not acknowledge termination")
            for thread in threads:
                thread.join(timeout=2)
            if any(t.is_alive() for t in threads):
                result.update(status="UNKNOWN_LOG_DRAIN", reason="Check output streams did not close within their cleanup bound")
        result["elapsed_seconds"] = time.monotonic() - started
        atomic_json(directory / "check.json", result)
    return result


class ExportChecks:
    def __init__(self, store, directory, manifest, *, budget_seconds=DEFAULT_EXPORT_BUDGET_SECONDS, started=None):
        self.store, self.directory, self.manifest = store, Path(directory), manifest
        self.deadline = (started if started is not None else time.monotonic()) + export_budget(budget_seconds)
        self.checking = manifest["checking"] = {"budget_seconds": budget_seconds, "status": "NOT_RUN", "checks": [],
            "deadline_scope": "All export preparation and child checks; bounded process cleanup may follow deadline"}
        self.persist()
        try:
            self.environment = frozen_environment(store.directory)
            self.version = self.environment["OMA_EXECUTABLE_BUILD"]
            self.checking["checker_version"] = self.version
        except Exception as exc:
            self.checking.update(status="UNKNOWN_EXECUTABLE_SNAPSHOT", reason=str(exc))
            self.persist()
            raise
        self.persist()

    def persist(self):
        atomic_json(self.directory / "manifest.json", self.manifest)

    def run(self, module, arguments, stage):
        index = len(self.checking["checks"]) + 1
        record = {"stage": stage, "status": "RUNNING"}
        self.checking["checks"].append(record)
        self.checking["status"] = "RUNNING"
        self.persist()
        result = supervise_check([sys.executable, "-m", module, *map(str, arguments)], environment=self.environment,
            directory=self.directory / "checks" / f"{index:03d}-{stage}", deadline=self.deadline)
        record.update(result)
        self.checking["status"] = result["status"]
        self.persist()
        return result

    def reimport(self, module, path, stage="round-trip"):
        material = json.loads(Path(path).read_text(encoding="utf-8"))
        result = self.run(module, [path], stage)
        try:
            material = json.loads(Path(path).read_text(encoding="utf-8"))
            observed_status = material.get("reimport", {}).get("status", "UNKNOWN_MISSING_RESULT")
        except (OSError, ValueError, TypeError) as exc:
            observed_status = "UNKNOWN_INVALID_RESULT"
            self.manifest["limitations"].append(f"{stage} sidecar unreadable: {exc}")
        status = observed_status if result["status"] == "COMPLETED" else result["status"]
        if result["status"] != "COMPLETED":
            self.manifest["limitations"].append(f"{stage}: {result['status']}; bounded logs and actual child result retained")
        # Never inherit a PASS sidecar written before a timeout/abnormal exit.
        material["reimport"] = {**material.get("reimport", {}), "status": status,
            "observed_child_status": observed_status, "child_process_status": result["status"]}
        atomic_json(path, material)
        return material, status

    def verify(self, candidate, original_report):
        result = self.run("oma.verification", [self.store.directory, candidate["id"]], "independent-check")
        checked = self.store.candidate(candidate["id"])
        self.checking["exported_candidate_id"] = candidate["id"]
        self.checking["candidate_status"] = checked["status"]
        self.checking["report_root"] = checked.get("report_root")
        if result["status"] != "COMPLETED" or checked["status"] != "CHECKED" or not checked.get("report_root"):
            self.manifest["round_trip"] = result["status"] if result["status"] != "COMPLETED" else "FAIL_INDEPENDENT_CHECK"
            self.manifest["limitations"].append(f"Full exported-state check: {result['status']}; candidate status {checked['status']}")
            self.persist()
            return
        report = self.store.get(checked["report_root"])
        try:
            VerificationReport.model_validate(report)
            state = self.store.get(candidate["state_root"])
            identities = [r["id"] for r in report["results"]]
            original_ids = [r["id"] for r in original_report["results"]]
            if state.get("physical_networks"):
                correspondence_ids = {"network-export-federation-correspondence"}
            elif state.get("derived_artifacts", {}).get("routing_contracts"):
                correspondence_ids = {r["id"] + ":export-federation-correspondence" for r in state["routes"]}
            else:
                correspondence_ids = {"export-federation-correspondence"}
            bindings = {
                "passing_report": report["status"] == "PASS",
                "candidate_root": report["candidate_root"] == candidate["state_root"] == checked["state_root"],
                "checker_version": report["checker_version"] == self.version == original_report["checker_version"],
                "mission_hash": report["mission_hash"] == original_report["mission_hash"] == digest(state.get("mission")),
                "rule_hash": report["rule_hash"] == original_report["rule_hash"] == state["mission"]["rule_hash"],
                "objective": report["objective"] == original_report["objective"],
                "scope": report["scope"] == original_report["scope"],
                "check_set": (len(identities) == len(set(identities)) and len(original_ids) == len(set(original_ids))
                    and set(identities) == set(original_ids) | correspondence_ids),
                "exported_bytes": all(Path(f["path"]).is_file() and sha256_file(f["path"]) == f["sha256"] for f in self.manifest["files"]),
            }
            self.checking["release_bindings"] = bindings
            if not all(bindings.values()):
                self.manifest["round_trip"] = "FAIL_EVIDENCE_BINDING"
                self.manifest["limitations"].append("Export evidence mismatch: " + ", ".join(k for k, ok in bindings.items() if not ok))
            else:
                self.manifest.update(status="CHECKED_LOCAL_SCOPE", checked_scope=report["scope"], exported_state_root=checked["state_root"],
                    verification_root=checked["report_root"], objective=report["objective"], round_trip="PASS")
                atomic_json(self.directory / "verification.json", report)
        except (ValueError, KeyError, TypeError) as exc:
            self.manifest["round_trip"] = "FAIL_INVALID_REPORT"
            self.manifest["limitations"].append(f"Invalid exported-state evidence: {exc}")
        self.persist()
