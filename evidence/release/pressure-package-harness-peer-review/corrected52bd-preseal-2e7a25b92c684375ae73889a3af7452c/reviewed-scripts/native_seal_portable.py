"""Carry complete build recipe/log evidence and hash the finished local bundle."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil

from native_prepare import ROOT, DEST, EVIDENCE, sha, json_write
from native_portable_candidate import copy_file
from native_package_evidence import verify_payload, verify_suite_xml, verify_checkpoint_inputs, verify_real_model_receipt, REAL_MODEL_ROLES, PAYLOAD_DIRECTORIES, PAYLOAD_FILES


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    args.result = args.result.resolve()
    result = json.loads(args.result.read_text())
    assert result["status"] == "ISOLATED_NATIVE_PORTABLE_OFFLINE_WORKFLOW_PASS"
    package = Path(result["package"]).resolve()
    assert package.is_relative_to((DEST / "portable-candidates").resolve())
    verify_payload(package, result)
    checkpoint, test_manifest = verify_checkpoint_inputs(package, result)
    full_suite = json.loads((args.result.parent / "bundled-full-suite.json").read_text())
    assert full_suite["status"] == "BUNDLED_EXACT_FROZEN_FULL_SUITE_PASS_WITH_DECLARED_DIRECT_INTERPRETER_NOT_APPLICABLE"
    assert full_suite["checker_version"] == result["identity"]["checker_version"]
    assert full_suite["source_checkpoint"] == result["source_checkpoint"]
    assert Path(full_suite["package"]).resolve() == package
    assert full_suite["portable_validation_result_sha256"] == sha(args.result)
    assert full_suite["validated_payload_manifest_sha256"] == result["validated_payload_manifest_sha256"]
    assert full_suite["test_node_manifest_sha256"] == result["application_test_validation"]["test_node_manifest_sha256"]
    assert full_suite["test_node_count"] == result["application_test_validation"]["test_node_count"]
    assert full_suite['test_source_manifest'] == test_manifest
    assert sha(args.result.parent / "bundled-tests.xml") == full_suite["test_xml_sha256"]
    assert full_suite["failed"] == 0 and len(full_suite["skipped"]) == 3
    nodes = package / "provenance/checkpoint-validation/selected-tests.args"
    assert sha(nodes) == full_suite["test_node_manifest_sha256"]
    accounting = verify_suite_xml(args.result.parent / "bundled-tests.xml", nodes.read_text().splitlines())
    assert all(full_suite[key] == value for key, value in accounting.items())
    guard = json.loads((args.result.parent / "offline-guard-probe.json").read_text())
    assert guard["status"] == "BUNDLED_AND_FROZEN_PYTHON_NETWORK_DENIAL_VERIFIED"
    assert guard["package_validation_sha256"] == sha(args.result)
    assert len(guard["records"]) == 2 and {r["mode"] for r in guard["records"]} == {"BUNDLED", "FROZEN_CHECKER"}
    assert all(r["checker_version"] == result["identity"]["checker_version"]
               and r["status"] == "PYTHON_SOCKET_CONNECT_DENIED" for r in guard["records"])
    actual = json.loads((args.result.parent / "real-office-validation.json").read_text())
    assert actual["status"] == "REAL_EXPORTED_OFFICE_RECHECK_PASS"
    assert actual["checker_version"] == result["identity"]["checker_version"]
    assert actual["source_checkpoint"] == result["source_checkpoint"]
    assert actual["execution"]["report_published"] and actual["execution"]["status"] == "COMPLETED"
    real_model_scopes = {}
    if result.get('real_model_validation_inputs_sha256'):
        for role, (filename, _) in REAL_MODEL_ROLES.items():
            receipt = json.loads((args.result.parent / filename).read_text())
            real_model_scopes[role] = verify_real_model_receipt(package, result, args.result, role, receipt)
    blocker_path = args.result.parent / 'PROMOTION-BLOCKED.json'
    blocker = json.loads(blocker_path.read_text()) if blocker_path.exists() else None
    if blocker:
        assert blocker['source_checkpoint'] == result['source_checkpoint']
        assert blocker['checker_version'] == result['identity']['checker_version']
    provenance = package / "provenance"
    assert not (provenance / "commands").exists()
    records = []
    for path in sorted((EVIDENCE / "commands").glob("*/record.json")):
        row = json.loads(path.read_text())
        assert row["status"] != "RUNNING"
        records.append((path, row))
    shutil.copytree(EVIDENCE / "commands", provenance / "commands")
    for path in sorted((ROOT / "scripts").glob("native_*.py")):
        copy_file(path, provenance / "build-recipes" / path.name)
    for stage in ("occt", "ifc"):
        for name in ("CMakeCache.txt", "compile_commands.json", "build.ninja"):
            path = DEST / "build" / stage / name
            if path.exists():
                copy_file(path, provenance / "generated-build-config" / stage / name)
    copy_file(args.result, provenance / "portable-validation.json")
    copy_file(args.result.parent / "workflow.json", provenance / "portable-workflow.json")
    if blocker:
        copy_file(blocker_path, provenance / 'PROMOTION-BLOCKED.json')
    for optional in ("real-office-validation.json", "real-office-pressure-validation.json", "real-office-native-scope.json", "ui-byte-equivalence.json",
                     "offline-guard-probe.json", "bundled-full-suite.json", "bundled-tests.xml"):
        if (args.result.parent / optional).exists():
            copy_file(args.result.parent / optional, provenance / optional)
    if (args.result.parent / "attempts").is_dir():
        shutil.copytree(args.result.parent / "attempts", provenance / "validation-attempts")
    test_count = result.get("application_test_validation", {}).get("passed", 916)
    note = f"""This is a local candidate package, not a complete production release.
{('HISTORICAL ARTIFACT: FINAL PROMOTION IS BLOCKED. ' + blocker['known_defect'] + ' Existing validation successes do not correct or certify this affected branch. See provenance/PROMOTION-BLOCKED.json.') if blocker else ''}

It uses the pinned {result['source_checkpoint']} application source with the separately identified
CGAL-disabled custom IfcOpenShell wheel and standalone Python 3.12.14. The exact
source, extension, wheel and checker identities appear in package-manifest.json.
The {test_count}-test suite passed under Python 3.12.10 with the custom native build.
The exact same frozen suite under bundled Python 3.12.14 passed {full_suite['passed']}
tests, with three explicitly recorded virtual-environment bridge corruption tests
not applicable to its direct interpreter. The bundle also passed its complete
offline analytic import, planted-collision rejection, route acceptance and fresh
IFC export workflow, plus a fresh real Office exported joint-route recheck.
{('The separately declared real Office pressure-network export also passed a fresh managed native and operating-point recheck under its fixed hypothetical mission.' if real_model_scopes else '')}

Source archives, applicable notices, declared source patches, actual command
logs, generated configurations and build scripts are retained in provenance.
Paths in original command logs describe the original isolated source workspace;
these are provenance records, not promises that an arbitrary relocated compiler
environment can reproduce identical machine code. No IFC-Bench source models
are included. offline-qa contains only the generated analytic fixture and its
derived test artifacts.

All 59 dependencies were installed with --no-index from the included wheelhouse.
The offline test disabled Python network operations using an audit hook inherited
by fresh checker processes; it did not install a machine-wide firewall. Setting
OMA_OFFLINE_DENY_NETWORK=1 reenables that diagnostic guard.

The current application runtime, original portable preview and original wheelhouse
remain unchanged. A source build and passing tests do not establish public
redistribution rights or completion of the application's engineering coverage.
See provenance/review-status.md and the capability register for retained limits.
UI assets are included unchanged; this campaign performed backend/native tests.
"""
    (package / "CANDIDATE-STATUS.txt").write_text(note, encoding="utf-8")
    verify_payload(package, result)
    paths = []
    for path in sorted(package.rglob("*")):
        if path.is_symlink():
            raise ValueError("Bundle integrity index does not accept symlinks")
        if path.is_file():
            paths.append(path)
    def indexed(path):
        before = path.stat()
        digest = sha(path)
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError("Package member changed during integrity indexing")
        return {"path": path.relative_to(package).as_posix(), "sha256": digest, "bytes": after.st_size}
    rows = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for index, row in enumerate(pool.map(indexed, paths), 1):
            rows.append(row)
            if index % 2000 == 0:
                print(json.dumps({"stage": "package-file-integrity", "hashed": index, "total": len(paths)}), flush=True)
    index = {"status": "COMPLETE_LOCAL_CANDIDATE_FILE_INDEX", "files": rows,
             "file_count": len(rows), "logical_bytes": sum(row["bytes"] for row in rows),
             "exclusions": ["artifact-files.json itself"],
             "scope": "Exact package files after offline validation; runtime-generated future files are outside this snapshot"}
    payload = json.loads((package / "validated-payload.json").read_text())
    assert sha(package / "validated-payload.json") == result["validated_payload_manifest_sha256"]
    indexed_payload = {row["path"]: {key: row[key] for key in ("sha256", "bytes")}
                       for row in rows if row["path"] in PAYLOAD_FILES
                       or row["path"].split("/", 1)[0] in PAYLOAD_DIRECTORIES}
    assert indexed_payload == payload["files"], "Indexed executable bytes differ from the tested portable payload"
    json_write(package / "artifact-files.json", index)
    handoff = {"status": "ISOLATED_NATIVE_PORTABLE_CANDIDATE_SEALED_NOT_PROMOTED", "package": str(package),
               "validation_result_sha256": sha(args.result), "checker_version": result["identity"]["checker_version"],
               "native_extension_sha256": result["identity"]["extension_sha256"],
               "artifact_index_sha256": sha(package / "artifact-files.json"), "file_count": len(rows),
               "logical_bytes": index["logical_bytes"], "active_runtime_modified": False,
               "previous_portable_preview_modified": False, "public_redistribution": "NOT_CLEARED"}
    if blocker:
        handoff.update(status='HISTORICAL_NATIVE_PORTABLE_CANDIDATE_SEALED_PROMOTION_BLOCKED',
                       promotion_blocker_sha256=sha(blocker_path), known_defect=blocker['known_defect'])
    handoff.update(bundled_full_suite_sha256=sha(args.result.parent / "bundled-full-suite.json"),
                   validated_payload_manifest_sha256=result["validated_payload_manifest_sha256"],
                   bundled_test_xml_sha256=sha(args.result.parent / "bundled-tests.xml"),
                   bundled_passed=full_suite["passed"], bundled_not_applicable=full_suite["skipped"],
                   offline_guard_sha256=sha(args.result.parent / "offline-guard-probe.json"))
    if (args.result.parent / "real-office-validation.json").exists():
        actual = json.loads((args.result.parent / "real-office-validation.json").read_text())
        assert actual["status"] == "REAL_EXPORTED_OFFICE_RECHECK_PASS" and actual["checker_version"] == handoff["checker_version"]
        handoff["real_office_validation_sha256"] = sha(args.result.parent / "real-office-validation.json")
    if real_model_scopes:
        handoff['real_model_validation_inputs_sha256'] = result['real_model_validation_inputs_sha256']
        handoff['real_model_scopes'] = real_model_scopes
        handoff['real_office_pressure_validation_sha256'] = sha(args.result.parent / 'real-office-pressure-validation.json')
    json_write(args.result.parent / "sealed-handoff.json", handoff)
    print(json.dumps(handoff), flush=True)


if __name__ == "__main__":
    main()
