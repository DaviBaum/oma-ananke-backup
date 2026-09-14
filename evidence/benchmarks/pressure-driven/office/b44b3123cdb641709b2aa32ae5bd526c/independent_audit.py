"""Read-only audit of retained historical evidence; never invokes a checker or Store."""
from __future__ import annotations

import hashlib
import itertools
import json
import sqlite3
import time
import zlib
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

import ifcopenshell


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def differences(a, b, prefix=""):
    if isinstance(a, dict) and isinstance(b, dict):
        return [x for key in sorted(a.keys() | b.keys()) for x in
                ([prefix + "/" + key] if key not in a or key not in b else differences(a[key], b[key], prefix + "/" + key))]
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return [x for i, (left, right) in enumerate(zip(a, b)) for x in differences(left, right, prefix + "/" + str(i))]
    return [] if a == b else [prefix]


def main():
    started = time.perf_counter()
    destination = Path(__file__).resolve().parent
    root = next(p for p in destination.parents if (p / "src/oma/store.py").is_file())
    attempt = destination.name
    stage = root / ".oma/development/two-sink-pressure"
    retained = stage / "evidence/benchmarks/pressure-office" / attempt
    store = stage / "bench-stores" / attempt
    reads = {}

    def read(name):
        path = retained / (name + ".json")
        raw = path.read_bytes()
        reads[path.name] = hashlib.sha256(raw).hexdigest()
        # Also verify the production evidence copies supplied by the campaign owner.
        assert (destination / path.name).read_bytes() == raw, path.name
        return json.loads(raw)

    def blob(key):
        value = json.loads(zlib.decompress((store / "blobs" / (key + ".json.z")).read_bytes()))
        assert digest(value) == key, key
        return value

    def connect(directory):
        result = sqlite3.connect((directory / "oma.sqlite3").resolve().as_uri() + "?mode=ro", uri=True)
        result.row_factory = sqlite3.Row
        result.execute("BEGIN")
        return result

    result, frozen = read("result"), read("frozen-input")
    copied, exported = read("copied-inputs"), read("export-manifest")
    read("optimization-events")
    assert digest(frozen) == result["frozen_input_root"]
    version = result["checker_version"]
    assert version == frozen["checker_version"] == "oma-independent-checker/2:b61a7a9f20f0f5dccc7f4f69207037e36110e895fdd3835f232d4f3f62d6d895"
    db, original_db = connect(store), connect(root / ".oma")
    run = dict(db.execute("SELECT * FROM runs WHERE id=?", (result["run_id"],)).fetchone())
    assert json.loads(run["request"])["mission"] == frozen["mission"]
    assert run["project_id"] == result["project_id"]
    current_head = dict(db.execute("SELECT * FROM projects WHERE id=?", (result["project_id"],)).fetchone())
    accepted = dict(db.execute("SELECT * FROM revisions WHERE project_id=? AND revision=1", (result["project_id"],)).fetchone())
    assert current_head["revision"] == 1 and current_head["status"] == "ACCEPTED"
    assert accepted["candidate_id"] == result["selected_candidate_id"] == "9bcc48f8b4514d028268846e36c8445a"
    assert accepted["root"] == current_head["state_root"] == result["accepted"]["state_root"]

    original_head = dict(original_db.execute("SELECT * FROM projects WHERE id=?", (frozen["original_project_head"]["id"],)).fetchone())
    assert original_head == frozen["original_project_head"]
    original_run = dict(original_db.execute("SELECT * FROM runs WHERE id=?", (frozen["prior_run_id"],)).fetchone())
    original_mission = json.loads(original_run["request"])["mission"]
    assert digest(original_mission) == frozen["prior_mission_root"]
    assert original_run["base_root"] == frozen["prior_baseline_root"]
    mission_changes = differences(original_mission, frozen["mission"])
    assert set(mission_changes) == {"/pressure_driven", "/physics", "/sinks/0/available_static_pressure_pa", "/sinks/1/available_static_pressure_pa", "/assumptions"}
    original_hashes = {path: sha(path) for path in frozen["original_files"]}
    assert original_hashes == frozen["original_files"]
    for asset in copied["assets"]:
        assert sha(asset["original_resolved_path"]) == asset["sha256"]
        assert sha(store / asset["copied_path"]) == asset["sha256"]

    summaries, pressures = [], {}
    rows = result["candidates"] + [result["export_recheck"]]
    for row in rows:
        cid = row["candidate_id"]
        name = "export-recheck" if row is rows[-1] else cid
        documents = {kind: read(name + "." + kind) for kind in ["state", "report", "semantics", "cad", "pressure"]}
        for kind, document in documents.items():
            key = row[kind + "_root"]
            assert digest(document) == key and blob(key) == document, (cid, kind)
        state, report, semantics, cad, pressure = (documents[k] for k in ["state", "report", "semantics", "cad", "pressure"])
        assert report["checker_version"] == version and report["candidate_root"] == row["state_root"]
        assert report["status"] == row["report_status"]
        checks = {check["id"]: check["status"] for check in report["results"]}
        assert len(checks) == len(report["results"]) and checks == row["checks"]
        assert {"network-pressure-operating-point", "network-demand-conditioned-service"} <= checks.keys()
        assert all(checks[key] == "PASS" for key in ["network-native-semantics", "network-all-source-clearance", "network-all-component-pairs", "network-permitted-zone", "network-pressure-operating-point"])
        candidate = dict(db.execute("SELECT * FROM candidates WHERE id=?", (cid,)).fetchone())
        assert candidate["state_root"] == row["state_root"] and candidate["report_root"] == row["report_root"] and candidate["status"] == row["status"]
        executions = [dict(e) for e in db.execute("SELECT * FROM check_executions WHERE candidate_id=?", (cid,))]
        assert len(executions) == 1
        execution = executions[0]
        assert execution["status"] == "COMPLETED" and execution["report_root"] == row["report_root"]
        process = blob(execution["evidence_root"])
        assert process["observed_receipt"]["report_root"] == row["report_root"]
        assert process["observed_receipt"]["checker_version"] == version
        supervision = process["supervision"]
        assert supervision["status"] == "COMPLETED"
        containment = supervision["containment"]
        assert containment["assigned_before_resume"] and containment["active_processes"] == 0
        assert containment["completion_authority"] == "KERNEL_JOB_ACTIVE_PROCESSES_ZERO"

        count = 8 if cid.startswith("aaf3") else 4
        assert semantics["status"] == cad["status"] == pressure["operating_point_status"] == pressure["independent_check"]["status"] == "PASS"
        guids = [part["ifc_guid"] for part in semantics["parts"]]
        assert len(guids) == len(set(guids)) == semantics["physical_components"] == cad["route_count"] == count
        assert set(guids) == set(cad["route_guids"])
        assert cad["obstacle_count"] == 803 and cad["pairs_accounted"] == count * 803
        assert cad["broad_separation_passes"] == count * 803 and not cad["pair_results"]
        assert not cad["failed_pairs"] and not cad["unknown_pairs"] and not cad["blocked_pairs"]
        pair_ids = [tuple(sorted(pair["participant_guids"])) for pair in cad["self_pair_results"]]
        assert len(pair_ids) == len(set(pair_ids)) == count * (count - 1) // 2
        assert set(pair_ids) == set(itertools.combinations(sorted(guids), 2))
        assert all(pair["status"] == "PASS" for pair in cad["self_pair_results"])
        assert semantics["original_records_checked"] == 62930
        deliveries = pressure["deliveries"]
        for delivery in deliveries.values():
            lo, hi = (Fraction(delivery["flow_m3_s"][k]) for k in ["lower", "upper"])
            minimum = Fraction(delivery["required_minimum_flow_m3_s"])
            assert lo <= hi
            assert delivery["status"] == ("PASS" if lo >= minimum else "FAIL" if hi < minimum else "UNKNOWN")
        assert deliveries["branch"]["status"] == ("FAIL" if count == 8 else "PASS")
        assert deliveries["straight"]["status"] == "PASS"
        assert checks["network-demand-conditioned-service"] == pressure["verdict"] == ("FAIL" if count == 8 else "PASS")
        assert cad["export_sha256"] == ("c360043af31552e635c1c3aa483e237f4a7f87edf10919d16b9e8cf88cb3eb39" if count == 8 else exported["files"][0]["sha256"])
        pressures[name] = pressure
        summaries.append({"candidate_id": cid, "label": name, "state_root": row["state_root"], "report_root": row["report_root"], "pressure_root": row["pressure_root"], "status": row["status"], "required_check_count": len(checks), "check_statuses": checks, "physical_components": count, "physical_ports": semantics["physical_ports"], "explicit_connections": semantics["connections"], "obstacles": cad["obstacle_count"], "source_pairs": cad["pairs_accounted"], "source_bound_separation_passes": cad["broad_separation_passes"], "source_narrowphase_result_rows": len(cad["pair_results"]), "source_support_enclosures": cad["represented_support_enclosures"], "self_pairs": len(pair_ids), "all_self_pairs_pass": True, "objective": report["objective"], "deliveries": deliveries, "model_root": pressure["independent_check"]["model_root"], "accuracy": pressure["independent_check"]["accuracy"], "execution_id": execution["execution_id"], "execution_evidence_root": execution["evidence_root"], "managed_publication_verified_from_database": True, "kernel_job_active_processes_on_completion": 0})

    direct = pressures[result["selected_candidate_id"]]
    fresh = pressures["export-recheck"]
    for field in ["deliveries", "source_flow_m3_s", "component_velocities"]:
        assert direct[field] == fresh[field]
    assert direct["independent_check"]["enclosures"] == fresh["independent_check"]["enclosures"]
    assert direct["independent_check"]["model_root"] != fresh["independent_check"]["model_root"]
    assert direct["model_input"]["context_root"] != fresh["model_input"]["context_root"]
    assert exported == blob(result["export"]["artifact_root"])
    assert exported["checking"]["exported_candidate_id"] == result["export_recheck"]["candidate_id"]
    assert exported["checking"]["report_root"] == result["export_recheck"]["report_root"]
    assert exported["checking"]["checker_version"] == version
    assert exported["status"] == "CHECKED_LOCAL_SCOPE" and exported["round_trip"] == "PASS"
    exported_file = exported["files"][0]
    assert sha(exported_file["path"]) == exported_file["sha256"]
    original_file = next(iter(original_hashes))
    source_ifc, final_ifc = ifcopenshell.open(original_file), ifcopenshell.open(exported_file["path"])
    original_records = list(source_ifc)
    assert len(original_records) == 62930
    assert all(str(entity) == str(final_ifc.by_id(entity.id())) for entity in original_records)
    assert len([e for e in final_ifc.by_type("IfcElement") if e.id() > max(x.id() for x in original_records)]) == 4
    # Final file guard: all observed evidence and input bytes still match after inspection.
    for name, expected in reads.items():
        assert sha(retained / name) == expected and sha(destination / name) == expected
    for path, expected in original_hashes.items():
        assert sha(path) == expected
    assert sha(exported_file["path"]) == exported_file["sha256"]
    db.close()
    original_db.close()
    audit = {"schema": "oma.independent-pressure-office-evidence-audit/1", "status": "PASS", "audited_at": datetime.now(timezone.utc).isoformat(), "method": "Read-only SQLite transactions, canonical blob rehash, exact retained-copy/file hashes, rational delivery comparisons, complete pair enumeration and source STEP-record comparison; no checker or campaign rerun", "historical_checker_version": version, "new_store_admission_hardening": "NOT_EVALUATED_BY_THIS_HISTORICAL_CAMPAIGN", "source_artifact_directory": str(retained), "source_store": str(store), "project_id": result["project_id"], "run_id": result["run_id"], "retained_campaign_seconds": result["seconds"], "selected_candidate_id": result["selected_candidate_id"], "accepted_revision": accepted, "original_project_head_unchanged": original_head, "prior_mission_root_unchanged": frozen["prior_mission_root"], "prior_baseline_root_unchanged": frozen["prior_baseline_root"], "original_ifc_hashes_unchanged": original_hashes, "copied_asset_pairs_rehashed": len(copied["assets"]), "explicit_new_mission_differences": mission_changes, "frozen_input_root": result["frozen_input_root"], "candidate_audits": summaries, "export": {"id": exported["export_id"], "manifest_root": result["export"]["artifact_root"], "status": exported["status"], "file": exported_file, "original_STEP_records_identical": len(original_records), "appended_physical_elements": 4, "fresh_recheck_candidate_id": result["export_recheck"]["candidate_id"], "exact_flow_and_velocity_enclosures_preserved": True, "fresh_model_and_context_roots_distinct": True}, "evidence_file_sha256": reads, "audit_script_sha256": sha(__file__), "audit_seconds": time.perf_counter() - started, "limitations": ["This validates retained b61a evidence and recorded publication, not a new current-build acceptance or the later obligation-admission hardening.", "All source pairs here passed conservative support-bound separation; they are not 3,212 or 6,424 Boolean narrowphase calls. Forty-eight source objects use explicitly declared source-support enclosures and retain unresolved native solid validity.", "Pressure results assume declared regulated total-pressure boundaries, fixed loss coefficients and an ideal circular bore inferred from native envelope minus declared insulation; they do not measure an as-built inner bore.", "Reported uncertainty widths include parameter uncertainty; the requested split-width target is not met. Minimum delivery decisions are nevertheless separated by the retained full flow intervals.", "No whole-building adequacy, unrestricted topology optimum, continuous global optimum or unrepresented physical extent claim.", "The prepublication execution evidence stores report_published=false; actual publication is verified independently from completed execution rows and matching live candidate report roots."]}
    target = destination / "independent-audit.json"
    with target.open("x", encoding="utf-8") as stream:
        json.dump(audit, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"status": audit["status"], "path": str(target), "sha256": sha(target), "seconds": audit["audit_seconds"]}))


if __name__ == "__main__":
    main()
