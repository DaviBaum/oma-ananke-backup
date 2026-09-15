"""Recover completed frozen-suite evidence after a relative XML-location error.

No subprocess or tests are launched. The recorded completed command, XML,
collection, immutable test sources, runtime identity and payload are rechecked.
"""
import argparse
import json
from pathlib import Path
import shutil
import time

from native_prepare import sha, json_write
from native_package_evidence import verify_payload, verify_suite_xml


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--suite-record", type=Path, required=True)
    parser.add_argument("--collection-record", type=Path, required=True)
    parser.add_argument("--retained-failure", type=Path, required=True)
    args = parser.parse_args()
    result_path = args.result.resolve()
    output = result_path.parent / "bundled-full-suite.json"
    previous = json.loads(output.read_text())
    assert previous["status"] == "INCOMPLETE_OR_FAILED" and "FileNotFoundError" in previous["error"]
    assert sha(output) == sha(args.retained_failure / "bundled-full-suite.json")
    assert previous["driver_sha256"] == sha(args.retained_failure / "native_portable_full_suite.py")
    portable = json.loads(result_path.read_text())
    package = Path(portable["package"]).resolve()
    assert portable["status"] == "ISOLATED_NATIVE_PORTABLE_OFFLINE_WORKFLOW_PASS"
    assert Path(previous["package"]).resolve() == package
    assert previous["portable_validation_result_sha256"] == sha(result_path)
    assert previous["checker_version"] == previous["identity"]["checker_version"] == portable["identity"]["checker_version"]
    started = time.monotonic()
    suite = json.loads(args.suite_record.read_text())
    collection = json.loads(args.collection_record.read_text())
    snapshot = Path(previous["directory"]) / "test-suite"
    python = package / "runtime/python.exe"
    for path, record in ((args.suite_record, suite), (args.collection_record, collection)):
        assert record["status"] == "PASS" and record["exit_code"] == 0
        assert Path(record["cwd"]).resolve() == snapshot.resolve()
        assert Path(record["command"][0]).resolve() == python
        assert sha(path.parent / "output.log") == record["log_sha256"]
    copied_nodes = Path(previous["directory"]) / "selected-tests.args"
    nodes = copied_nodes.read_text().splitlines()
    assert sha(copied_nodes) == previous["test_node_manifest_sha256"]
    assert len(nodes) == previous["test_node_count"] and len(nodes) == len(set(nodes))
    assert suite["command"][1:-1] == ["-B", "-s", "-m", "pytest", "-q", "-o", "pythonpath=", "@" + str(copied_nodes)]
    assert collection["command"][1:] == ["-B", "-s", "-m", "pytest", "--collect-only", "-q", "-o", "pythonpath=", "tests"]
    collected = [line for line in (args.collection_record.parent / "output.log").read_text().splitlines()
                 if line.startswith("tests/") and "::" in line]
    assert collected == nodes
    xml_argument = suite["command"][-1]
    assert xml_argument.startswith("--junitxml=")
    actual_xml = (snapshot / xml_argument.split("=", 1)[1]).resolve()
    assert actual_xml.is_relative_to(snapshot.resolve())
    accounting = verify_suite_xml(actual_xml, nodes)
    declaration = previous["test_source_manifest"]["files"]
    assert declaration == {relative: sha(snapshot / relative) for relative in declaration}
    verify_payload(package, portable)
    target = result_path.parent / "bundled-tests.xml"
    assert not target.exists() or sha(target) == sha(actual_xml)
    shutil.copyfile(actual_xml, target)
    assert sha(target) == sha(actual_xml)
    result = {**previous, "status": "BUNDLED_EXACT_FROZEN_FULL_SUITE_PASS_WITH_DECLARED_DIRECT_INTERPRETER_NOT_APPLICABLE",
              **accounting, "test_xml_sha256": sha(target), "collection_record": str(args.collection_record.resolve()),
              "suite_record": str(args.suite_record.resolve()), "recovery": {
                  "kind": "COMPLETED_SUITE_XML_LOCATION_RECOVERY_NO_RERUN", "tests_rerun": False,
                  "original_xml": str(actual_xml), "original_xml_sha256": sha(actual_xml),
                  "retained_failure": str(args.retained_failure.resolve()),
                  "retained_failure_sha256": sha(args.retained_failure / "bundled-full-suite.json"),
                  "suite_record_sha256": sha(args.suite_record), "collection_record_sha256": sha(args.collection_record),
                  "seconds": time.monotonic() - started, "recovery_script_sha256": sha(Path(__file__))}}
    result.pop("error", None)
    json_write(output, result)
    print(json.dumps({"status": result["status"], **accounting, "tests_rerun": False}), flush=True)


if __name__ == "__main__":
    main()
