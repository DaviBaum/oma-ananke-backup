"""Freshly export a checked graph candidate without changing the accepted head."""
import json
import os
from pathlib import Path
import sys
import time

from oma.build_identity import checker_version
from oma.exporting import export_project
from oma.ifc.audit import atomic_json, sha256_file
from oma.store import Store, utcnow

ROOT=Path(__file__).resolve().parents[1]


def main():
    assert os.environ.get("OMA_EXECUTABLE_BUILD")=="94e74251a39d1f0d8cc77feb9d2df686e3927eb49473b67d09d8bdf66843c93f"
    directory=ROOT / "evidence/benchmarks/fabrication-graph/office/21e3d70a85934079b508ff2d48d074e5"
    campaign=json.loads((directory / "result.json").read_text())
    store=Store(ROOT / ".oma")
    candidate=store.candidate("57d4927086544a46aa9122acadc9578c")
    accepted=store.project(candidate["project_id"])
    report=store.get(candidate["report_root"])
    assert candidate["status"]=="CHECKED" and report["status"]=="PASS" and report["checker_version"]==checker_version()
    assert (candidate.get("proposal_evidence") or {})["method"]=="SOURCE_BOUND_FABRICATION_GRAPH"
    start=time.monotonic()
    result={"status":"RUNNING","started_at":utcnow(),"checker_version":checker_version(),
        "graph_candidate_id":candidate["id"],"graph_candidate_root":candidate["state_root"],
        "graph_report_root":candidate["report_root"],"graph_objective":report["objective"],
        "ordinary_selected_candidate_id":campaign["selected_candidate_id"],
        "ordinary_selected_method":campaign["selected_method"],
        "campaign_evidence_sha256":sha256_file(directory / "result.json"),
        "scope":"Separate checked graph-design export; ordinary selected and accepted head preserved"}
    atomic_json(directory / "graph-export.json",result)
    try:
        exported=export_project(store,candidate["project_id"],candidate["id"],draft=False,budget_seconds=1200)
        manifest=store.get(exported["artifact_root"])
        checked=store.get(manifest["verification_root"])
        assert checked["status"]=="PASS" and checked["checker_version"]==checker_version()
        assert checked["candidate_root"]==manifest["exported_state_root"] and checked["objective"]==report["objective"]
        assert all(manifest["checking"]["release_bindings"].values())
        assert all(sha256_file(f["path"])==f["sha256"] for f in manifest["files"])
        assert store.project(candidate["project_id"])==accepted
        result.update(status="CHECKED_GRAPH_EXPORTED_AND_INDEPENDENTLY_RECHECKED",export=exported,
            export_verification_root=manifest["verification_root"],exported_state_root=manifest["exported_state_root"],
            accepted_head_unchanged=True,accepted_head_root=accepted["state_root"])
        atomic_json(directory / "graph-export.verification.json",checked)
    except BaseException as error:
        result.update(status="INCOMPLETE",error=f"{type(error).__name__}: {error}")
        raise
    finally:
        result["elapsed_seconds"]=time.monotonic()-start
        atomic_json(directory / "graph-export.json",result)
        print(json.dumps({k:result.get(k) for k in ["status","graph_candidate_id","elapsed_seconds","export_verification_root"]}),flush=True)


if __name__=="__main__":
    main()
