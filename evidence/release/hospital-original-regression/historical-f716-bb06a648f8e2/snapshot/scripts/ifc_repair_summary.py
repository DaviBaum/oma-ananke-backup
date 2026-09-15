"""Retain exact build and frozen-reference comparisons for accepted IFC repairs."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from oma.ifc.audit import atomic_json,sha256_file
from oma.store import Store
from oma.validation_advisories import candidate_advisories


def summarize():
    store=Store(ROOT/".oma")
    base=ROOT/"evidence/benchmarks/real-repair"
    accepted=[]
    for path in sorted(base.glob("*/*.accepted-export.json")):
        result=json.loads(path.read_text(encoding="utf-8"))
        candidate=store.candidate(result["candidate_id"])
        mission=store.run(candidate["run_id"])["request"]["mission"]
        comparisons=[]
        for frozen_path in path.parent.rglob("*.frozen.json"):
            frozen=json.loads(frozen_path.read_text(encoding="utf-8"))
            for scenario in frozen.get("scenarios",[]):
                if scenario["mission"]!=mission:
                    continue
                reference_path=ROOT/"data/outputs/real-repair"/path.parent.name/scenario["scenario_id"]/"independent_reference.manifest.json"
                reference=json.loads(reference_path.read_text(encoding="utf-8"))
                reference_length=reference["length_m"]
                accepted_length=result["report"]["objective"]["length_m"]
                comparisons.append({"scenario_id":scenario["scenario_id"],"specification_root":frozen["specification_root"],
                    "reference_manifest_sha256":sha256_file(reference_path),"reference_length_m":reference_length,
                    "accepted_length_m":accepted_length,"accepted_minus_reference_m":accepted_length-reference_length,
                    "relative_reference_gap":(accepted_length-reference_length)/reference_length,
                    "scope":"Independent frozen feasibility witness comparison; no continuous optimality claim"})
        # Historical accepted/export evidence and IFC bytes remain unchanged.
        # Current advisories are a derived view alongside the original report.
        advisories=candidate_advisories(store,candidate)
        accepted.append({"project":path.parent.name,"project_id":result["project_id"],"candidate_id":result["candidate_id"],
            "accepted_revision":result["accepted_revision"],"checker_version":result["checker_version"],
            "status":result["status"],"export_id":result["export"]["export_id"],"export_status":result["export"]["status"],
            "round_trip":result["export"]["round_trip"],"files":result["export"]["files"],"objective":result["report"]["objective"],
            "reference_comparisons":comparisons,"final_check_accept_export_seconds":result["seconds"],
            "joint_references":result.get("joint_references",[]),"port_semantic_regeneration":result.get("port_semantic_regeneration",[]),
            "validation_advisories":advisories,"port_semantics_status":"REGENERATION_REQUIRED" if advisories else "CORRECTED_AND_CHECKED_ON_RECORDED_BUILD",
            "evidence_path":str(path.relative_to(ROOT)),"scope":result["scope"]})
    specifications=[]
    for path in sorted(base.rglob("*.frozen.json")):
        frozen=json.loads(path.read_text(encoding="utf-8"))
        if "scenarios" not in frozen:
            continue
        results_path=path.parent/"results.json"
        records=json.loads(results_path.read_text(encoding="utf-8"))["records"] if results_path.exists() else []
        relevant=[r for r in records if r.get("scenario_id") in {s["scenario_id"] for s in frozen["scenarios"]}]
        specifications.append({"path":str(path.relative_to(ROOT)),"specification_root":frozen["specification_root"],
            "source":frozen["source"],"source_sha256":frozen["source_sha256"],"version":frozen["specification_version"],
            "source_representation_policy":frozen.get("source_representation_policy","LEGACY_MISSION_DEFAULT_STRICT_POLICY"),"frozen_scenarios":frozen["denominator_frozen"],
            "heuristic_dispositions":len(frozen["eligibility_dispositions"]),"attempt_records":len(relevant),
            "attempt_status_counts":dict(Counter(r["status"] for r in relevant)),
            "unique_scenarios_with_attempts":len({r["scenario_id"] for r in relevant}),
            "reference_hidden_from_optimizer":frozen["reference_hidden_from_optimizer"]})
    joint_specifications=[]
    for path in sorted(base.rglob("*.joint-frozen.json")):
        frozen=json.loads(path.read_text(encoding="utf-8"))
        records=[json.loads(p.read_text(encoding="utf-8")) for p in path.parent.glob("attempts/*/result.json")]
        relevant=[r for r in records if r.get("scenario_id") in {s["scenario_id"] for s in frozen["scenarios"]}]
        joint_specifications.append({"path":str(path.relative_to(ROOT)),"specification_root":frozen["specification_root"],
            "source":frozen["source"],"source_sha256":frozen["source_sha256"],"frozen_scenarios":frozen["frozen_scenario_denominator"],
            "attempt_records":len(relevant),"attempt_status_counts":dict(Counter(r["status"] for r in relevant)),
            "unique_scenarios_with_attempts":len({r["scenario_id"] for r in relevant}),"reference_hidden_from_optimizer":True})
    summary={"schema":"oma-real-repair-summary/2","accepted_local_repairs":accepted,"frozen_specifications":specifications,
             "joint_frozen_specifications":joint_specifications,
             "historical_port_semantics_superseded":sum(bool(r["validation_advisories"]) for r in accepted),
             "corrected_port_exports_checked_on_recorded_build":sum(not r["validation_advisories"] for r in accepted),
             "whole_building_certification":"NOT_CERTIFIED","continuous_optimality":"NOT_ESTABLISHED",
             "scope":"Explicit hypothetical added services with fixed physical requirements; original source content protected"}
    atomic_json(base/"summary.json",summary)
    print(json.dumps({"accepted_local_repairs":len(accepted),"frozen_specifications":len(specifications),
                      "comparisons":[{"project":r["project"],"values":r["reference_comparisons"]} for r in accepted]}))
    return summary


if __name__=="__main__":
    summarize()
