"""Read-only assembly and replay of frozen historical Office candidate reports.

This demonstrates real stored IFC candidate inputs, without recertifying their
historical physical conclusions under today's build or modifying the store.
"""
from pathlib import Path
import hashlib
import json
import sqlite3
import time

from oma.store import Store, digest
from oma.optimization.physical_menu import compile_physical_menu, verify_physical_menu


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence/math"
CANDIDATES = ["a820998dc8b3440f9aa8e90760a8de59", "f583693cce4644ad8306b31d51c8540f"]


def save(name, value):
    data = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode()
    (OUT / name).write_bytes(data + b"\n")
    return hashlib.sha256(data + b"\n").hexdigest()


def main():
    directory = ROOT / ".oma"
    # Store.get is a read-only digest-checked blob reader; avoid constructor DDL.
    reader = object.__new__(Store)
    reader.blobs = directory / "blobs"
    with sqlite3.connect((directory / "oma.sqlite3").as_uri() + "?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        candidates = [dict(db.execute("SELECT * FROM candidates WHERE id=?", (cid,)).fetchone()) for cid in CANDIDATES]
        assert len({c["run_id"] for c in candidates}) == 1
        run = dict(db.execute("SELECT * FROM runs WHERE id=?", (candidates[0]["run_id"],)).fetchone())
    states = [reader.get(c["state_root"]) for c in candidates]
    reports = [reader.get(c["report_root"]) for c in candidates]
    request = json.loads(run["request"])
    demand_ids = [d["id"] for d in request["mission"]["route_demands"]]
    domains = {d: {} for d in demand_ids}
    assignments = []
    for state in states:
        contracts = state["derived_artifacts"]["routing_contracts"]
        by_id = {r["id"]: r for r in state["routes"]}
        assignment = []
        for demand_id in demand_ids:
            entries = [(rid, c) for rid, c in contracts.items() if c["request_demand_id"] == demand_id]
            assert len(entries) == 1
            rid, contract = entries[0]
            route = by_id[rid]
            definition = {"scenario": contract["scenario"], "points_m": route["points_m"],
                          "section": route["section"], "service": route["service"], "source_id": contract["source_id"]}
            definition_root = digest(definition)
            label = "route:" + definition_root
            domains[demand_id][label] = definition_root
            assignment.append(label)
        assignments.append(assignment)
    projection_contract = {"name": "Historical complete-assignment report status, objective, scope and original checker version",
        "fields": ["status", "objective", "scope", "checker_version"],
        "physical_claim": "Exact projection of stored reports only; their historical physical verdicts are not recertified under the current build"}
    context = {"base_root": run["base_root"], "request": request,
        "source_identities": [[s["id"] for s in state["sources"]] for state in states],
        "historical_checker_versions": [r["checker_version"] for r in reports], "projection_contract": projection_contract}
    problem = {"schema": "oma.physical-menu/1", "context_root": digest(context),
        "projection_contract_root": digest(projection_contract),
        "demands": [{"id": d, "choices": [{"id": label, "definition_root": root} for label, root in domains[d].items()]} for d in demand_ids],
        "examined": []}
    for c, report, assignment in zip(candidates, reports, assignments):
        assert report["candidate_root"] == c["state_root"]
        problem["examined"].append({"assignment": assignment, "candidate_id": c["id"], "state_root": c["state_root"],
            "report_root": c["report_root"], "verdict": report["status"],
            "projection": {field: report[field] for field in projection_contract["fields"]}})
    start = time.perf_counter()
    certificate = compile_physical_menu(problem)
    compile_seconds = time.perf_counter() - start
    start = time.perf_counter()
    checked = verify_physical_menu(problem, json.loads(json.dumps(certificate)))
    check_seconds = time.perf_counter() - start
    assert checked["status"] == "PASS"
    assert certificate["summary"]["verdict_counts"] == {"FAIL": 1, "PASS": 1}
    # Remove one real report to exercise UNKNOWN retention on the same menu.
    incomplete = json.loads(json.dumps(problem))
    incomplete["examined"].pop()
    partial = compile_physical_menu(incomplete)
    assert partial["summary"]["verdict_counts"] == {"FAIL": 1, "UNKNOWN": 1}
    assert verify_physical_menu(incomplete, partial)["status"] == "PASS"
    summary = {"schema": "oma.real-candidate-menu-benchmark/1", "status": "PROJECTION_CERTIFICATE_CHECKED",
        "scope": projection_contract["physical_claim"], "store_read_only": True,
        "run_id": run["id"], "candidate_ids": CANDIDATES,
        "source_context": context, "projection_contract": projection_contract,
        "input_sha256": save("physical-menu-office.input.json", problem),
        "certificate_sha256": save("physical-menu-office.certificate.json", certificate),
        "source_reports_sha256": save("physical-menu-office.source-reports.json", reports),
        "independent_check": checked, "summary": certificate["summary"],
        "compile_seconds": compile_seconds, "check_seconds": check_seconds,
        "withheld_report_probe": partial["summary"],
        "implementation_sha256": hashlib.sha256((ROOT / "src/oma/optimization/physical_menu.py").read_bytes()).hexdigest()}
    save("physical-menu-office.benchmark.json", summary)
    print(json.dumps({k: summary[k] for k in ("status", "compile_seconds", "check_seconds", "summary")}, indent=2))


if __name__ == "__main__":
    main()
