"""Bind completed isolated build, source, binary and validation evidence."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

from native_prepare import ROOT, DEST, EVIDENCE, sha, json_write


def footprint(directory):
    count = size = 0
    for current, directories, files in os.walk(directory, followlinks=False):
        directories[:] = [name for name in directories if not (Path(current) / name).is_symlink()]
        for name in files:
            path = Path(current) / name
            if not path.is_symlink():
                count += 1
                size += path.stat().st_size
    return {"files": count, "logical_bytes": size}


def main():
    names = ("candidate-wheel.json", "application-validation.json", "all-schema-smoke.json",
             "runtime-identity-comparison.json", "real-office-validation.json",
             "source-revalidation.json", "source-revalidation-ifc.json",
             "ifc-opaque-coordinate-patch.json", "test-selection.json")
    inputs = {name: json.loads((EVIDENCE / name).read_text()) for name in names}
    wheel = inputs["candidate-wheel.json"]
    application = inputs["application-validation.json"]
    real = inputs["real-office-validation.json"]
    assert application["status"] == "ALL_SCHEMA_SMOKE_AND_EXACT_916_TEST_BASELINE_PASS"
    assert real["status"] == "REAL_EXPORTED_OFFICE_RECHECK_PASS"
    xml = ET.parse(EVIDENCE / "application-916-tests.xml").getroot()
    assert len(xml.findall(".//testcase")) == 916 and not xml.findall(".//failure") and not xml.findall(".//error") and not xml.findall(".//skipped")
    assert sha(Path(wheel["wheel"])) == wheel["sha256"]
    original = inputs["runtime-identity-comparison.json"]["original"]
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("OMA_EXECUTABLE_BUILD", None)
    probe = "import hashlib,importlib.metadata,json,pathlib; import ifcopenshell._ifcopenshell_wrapper as e; print(json.dumps({'version':importlib.metadata.version('ifcopenshell'),'path':e.__file__,'sha256':hashlib.sha256(pathlib.Path(e.__file__).read_bytes()).hexdigest()}))"
    active = json.loads(subprocess.check_output([str(ROOT / ".venv/Scripts/python.exe"), "-c", probe], env=env, text=True))
    assert active["version"] == original["packages"]["ifcopenshell"] == "0.8.5"
    assert active["sha256"] == original["extension_sha256"]
    commands = []
    for path in sorted((EVIDENCE / "commands").glob("*/record.json")):
        record = json.loads(path.read_text())
        commands.append({"path": str(path.relative_to(ROOT)), "sha256": sha(path),
                         **{k: record.get(k) for k in ("stage", "status", "seconds", "peak_process_tree_rss_bytes", "exit_code")}})
    assert not any(row["status"] == "RUNNING" for row in commands)
    result = {
        "status": "ISOLATED_NATIVE_CANDIDATE_BUILT_AND_VALIDATED_NOT_PROMOTED",
        "wheel": {k: wheel[k] for k in ("wheel", "version", "sha256", "bytes", "record_entries_verified")},
        "checker_version": application["runtime"]["OMA_EXECUTABLE_BUILD"],
        "native_extension_sha256": wheel["variant"]["native_extension_sha256"],
        "app_source_checkpoint": application["source_checkpoint"],
        "tests": {"count": 916, "passed": 916, "failed": 0, "skipped": 0,
                  "source_commit": application["test_commit"], "selection_sha256": application["test_node_manifest_sha256"],
                  "junit_sha256": sha(EVIDENCE / "application-916-tests.xml"),
                  "suite_record": application["suite_record"]},
        "real_office": {k: real[k] for k in ("candidate_id", "candidate_root", "report_root", "seconds",
                                               "original_bytes_and_head_unchanged", "same_objective_and_obligation_dispositions")},
        "evidence": {name: {"sha256": sha(EVIDENCE / name), "status": inputs[name].get("status")} for name in names},
        "source_revalidation_scope": "The full original-member scan read IFC before its declared SWIG patch; the separate postpatch IFC scan rehashed all 3510 core members and permitted only the exact recorded patch. OCCT's four upstream patched members were validated at their declared hashes.",
        "variant_scope": wheel["variant"]["scope"],
        "commands": commands,
        "artifact_footprint": {p.name: footprint(p) for p in sorted(DEST.iterdir()) if p.is_dir()},
        "footprint_semantics": "Logical file bytes at handoff; no symlinks followed; sparse/shared physical allocation is not inferred",
        "disk_free_bytes": shutil.disk_usage(DEST).free,
        "active_runtime": active,
        "active_runtime_modified": False,
        "runtime_promotion": "NOT_PERFORMED",
        "public_redistribution": "NOT_CLEARED; separate dependency and application release obligations remain",
        "claims": "Successful compilation, all-schema smoke, exact pinned application regression and one complete real exported-route recheck. No proof of every upstream optional feature, all IFC files, or legal redistribution rights.",
    }
    json_write(EVIDENCE / "handoff.json", result)
    print(json.dumps({"status": result["status"], "tests": result["tests"], "real_office": result["real_office"],
                      "artifact_logical_bytes": sum(v["logical_bytes"] for v in result["artifact_footprint"].values())}), flush=True)


if __name__ == "__main__":
    main()
