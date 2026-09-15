"""Summarize the newer source checkpoint's isolated native promotion validation."""
import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

from native_prepare import ROOT, EVIDENCE, sha, json_write


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--portable", type=Path, required=True)
    args = parser.parse_args()
    args.checkpoint = args.checkpoint.resolve()
    args.portable = args.portable.resolve()
    checkpoint = json.loads(args.checkpoint.read_text())
    portable = json.loads(args.portable.read_text())
    sealed_path = args.portable.parent / "sealed-handoff.json"
    sealed = json.loads(sealed_path.read_text())
    comparison = json.loads((args.checkpoint.parent / "identity-comparison.json").read_text())
    test_real_path = args.checkpoint.parent / "real-office-validation.json"
    portable_real_path = args.portable.parent / "real-office-validation.json"
    test_real = json.loads(test_real_path.read_text())
    portable_real = json.loads(portable_real_path.read_text())
    assert checkpoint["status"] == "CUSTOM_NATIVE_NEW_CHECKPOINT_FULL_SUITE_PASS"
    assert portable["status"] == "ISOLATED_NATIVE_PORTABLE_OFFLINE_WORKFLOW_PASS"
    assert sealed["status"] == "ISOLATED_NATIVE_PORTABLE_CANDIDATE_SEALED_NOT_PROMOTED"
    assert checkpoint["source_checkpoint"] == portable["source_checkpoint"]
    assert checkpoint["native_extension_sha256"] == portable["identity"]["extension_sha256"] == sealed["native_extension_sha256"]
    assert test_real["status"] == portable_real["status"] == "REAL_EXPORTED_OFFICE_RECHECK_PASS"
    assert test_real["candidate_root"] == portable_real["candidate_root"]
    assert test_real["source_and_exported_files"] == portable_real["source_and_exported_files"]
    assert test_real["report"]["objective"] == portable_real["report"]["objective"]
    assert test_real["checker_version"] == checkpoint["runtime"]["OMA_EXECUTABLE_BUILD"]
    assert portable_real["checker_version"] == portable["identity"]["checker_version"] == sealed["checker_version"]
    assert {"oma/" + name: digest for name, digest in comparison["candidate"]["source_files"].items()} == portable["source_python_files"]
    assert comparison["candidate"]["source_files"] == comparison["original"]["source_files"]
    active_probe = "import importlib.metadata,hashlib,json,pathlib;import ifcopenshell._ifcopenshell_wrapper as e;print(json.dumps({'version':importlib.metadata.version('ifcopenshell'),'sha256':hashlib.sha256(pathlib.Path(e.__file__).read_bytes()).hexdigest()}))"
    active = json.loads(subprocess.check_output([str(ROOT / ".venv/Scripts/python.exe"), "-c", active_probe], text=True))
    assert active["version"] == comparison["original"]["packages"]["ifcopenshell"] == "0.8.5"
    assert active["sha256"] == comparison["original"]["extension_sha256"]
    package = Path(portable["package"])
    assert sha(package / "artifact-files.json") == sealed["artifact_index_sha256"]
    xml = ET.parse(args.checkpoint.parent / "tests.xml").getroot()
    cases = xml.findall(".//testcase")
    assert len(cases) == checkpoint["passed"] and not xml.findall(".//failure") and not xml.findall(".//error") and not xml.findall(".//skipped")
    files = Counter(case.attrib["classname"] for case in cases)
    scope = {name: count for name, count in files.items() if any(key in name for key in ("fabrication", "native_zone", "routing_integration", "joint", "export", "network_lifecycle"))}
    result = {"status": "NEW_SOURCE_CUSTOM_NATIVE_AND_PORTABLE_VALIDATION_COMPLETE_NOT_PROMOTED",
              "source_checkpoint": checkpoint["source_checkpoint"],
              "custom_test_checker": checkpoint["runtime"]["OMA_EXECUTABLE_BUILD"],
              "portable_checker": sealed["checker_version"],
              "native_version": checkpoint["native_version"], "native_extension_sha256": checkpoint["native_extension_sha256"],
              "suite": {"passed": checkpoint["passed"], "failed": 0, "skipped": 0,
                        "selection_sha256": checkpoint["test_node_manifest_sha256"], "test_xml_sha256": checkpoint["test_xml_sha256"],
                        "requested_scope_module_counts": scope, "complete_suite_module_counts": dict(files)},
              "real_office": {"candidate_id": test_real["candidate_id"], "candidate_root": test_real["candidate_root"],
                              "objective": test_real["report"]["objective"], "source_and_exported_files": test_real["source_and_exported_files"],
                              "test_interpreter_report_root": test_real["report_root"], "test_interpreter_seconds": test_real["seconds"],
                              "bundled_interpreter_report_root": portable_real["report_root"], "bundled_interpreter_seconds": portable_real["seconds"],
                              "original_head_and_bytes_unchanged": test_real["original_bytes_and_head_unchanged"] and portable_real["original_bytes_and_head_unchanged"]},
              "portable": sealed,
              "evidence": {str(path.relative_to(ROOT)): sha(path) for path in
                           (args.checkpoint, args.portable, sealed_path, test_real_path, portable_real_path,
                            args.checkpoint.parent / "identity-comparison.json", args.portable.parent / "offline-guard-probe.json")},
              "active_original_native": active, "active_runtime_modified": False,
              "runtime_promotion": "NOT_PERFORMED", "public_redistribution": "NOT_CLEARED",
              "earlier_916_checkpoint_and_package": "RETAINED; neither result was replaced by this newer checkpoint",
              "scope": "Exact copied new test suite under Python 3.12.10; separate bundled Python 3.12.14 offline workflow and same real Office exported bytes. Native numerical and represented-source assumptions retained."}
    output = args.checkpoint.parent / "promotion-validation-handoff.json"
    json_write(output, result)
    print(json.dumps({"status": result["status"], "suite_passed": checkpoint["passed"], "portable_checker": sealed["checker_version"],
                      "evidence": str(output)}), flush=True)


if __name__ == "__main__":
    main()
