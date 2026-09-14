"""Independently account for completed root/custom native suites; never rerun them."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def snapshot(directory, expected):
    declared, generated, caches = {}, {}, []
    producers = {
        "joint-fitting-budget-audit": {
            "files": {"declared-source.ifc", "source-after-pause.ifc", "result.json"},
            "test": "tests/test_joint_fitting_budget_adversarial.py::test_complete_joint_report_rejects_source_changed_at_final_fitting_pause"},
        "joint-probe-native-audit": {
            "files": {"current-separated.ifc", "transient-overlap.ifc", "result.json"},
            "test": "tests/test_joint_probe_native_audit.py::test_transient_export_replacement_cannot_bind_other_geometry_to_current_hash"}}
    for path in directory.rglob("*"):
        assert not path.is_symlink()
        if not path.is_file():
            continue
        relative = path.relative_to(directory).as_posix()
        if {"__pycache__", ".pytest_cache"}.intersection(path.relative_to(directory).parts):
            caches.append(relative)
        elif relative in expected:
            declared[relative] = sha(path)
        else:
            pieces = relative.split("/")
            assert len(pieces) == 5 and pieces[:2] == ["evidence", "release"] and pieces[2] in producers, relative
            assert re.fullmatch('[0-9a-f]{32}', pieces[3]) and pieces[4] in producers[pieces[2]]["files"], relative
            generated[relative] = sha(path)
    assert declared == expected
    assert len(generated) == 6
    evidence = {}
    for family, producer in producers.items():
        paths = [Path(name) for name in generated if name.split('/')[2] == family]
        assert len(paths) == 3 and len({p.parent for p in paths}) == 1
        assert {p.name for p in paths} == producer['files']
        result_path = next(directory / p for p in paths if p.name == 'result.json')
        record = json.loads(result_path.read_text())
        if family == 'joint-fitting-budget-audit':
            assert record['case'] == 'SOURCE_MUTATION_AT_FINAL_FITTING_PAUSE'
        else:
            assert record['experiment'] == 'Actual native file parse sees B while before/after declared-byte guards see A'
            assert record['wrong_current_geometry_failure'] is False and record['kernel_pair_result_not_mocked'] is True
            assert sha(result_path.parent / 'current-separated.ifc') == record['current_export_sha256'] == record['final_export_sha256']
        evidence[family] = {'producer_test': producer['test'], 'producer_source_sha256': expected[producer['test'].split('::')[0]],
            'files_sha256': {p.as_posix(): generated[p.as_posix()] for p in paths}}
    return {"directory": str(directory), "declared_input_count": len(declared), "all_declared_input_sha256": declared,
        "derived_output_sha256": generated, "derived_producers": evidence, "cache_file_count": len(caches), "unexpected_files": []}


def account_xml(path, nodes):
    expected = []
    for node in nodes:
        names = node.split("::")
        classname = names[0][:-3].replace("/", ".").replace("\\", ".")
        if len(names) > 2:
            classname += "." + ".".join(names[1:-1])
        expected.append((classname, names[-1]))
    xml = ET.parse(path).getroot()
    cases = xml.findall(".//testcase")
    assert Counter((x.attrib["classname"], x.attrib["name"]) for x in cases) == Counter(expected)
    assert not any(xml.findall(".//" + name) for name in ("failure", "error", "skipped"))
    return {"xml_path": str(path), "xml_sha256": sha(path), "exact_node_identity_multiset": True,
        "passed": len(cases), "failed": 0, "skipped": 0}


def main():
    root_record_path = ROOT / "evidence/release/pressure-admission-complete-c2250254bc084d14abb63f6bf6237c8d/result.json"
    custom_record_path = ROOT / "evidence/dependencies/native-build/checkpoint-validation/bac10b7f20d4-a70b4635e7d5/result.json"
    root_run, custom = (json.loads(p.read_text()) for p in (root_record_path, custom_record_path))
    assert root_run["status"] != "RUNNING" and custom["status"] != "RUNNING", "Wait for both original supervised runs to complete"
    assert custom["status"] == "CUSTOM_NATIVE_NEW_CHECKPOINT_FULL_SUITE_PASS"
    manifest_path = custom_record_path.parent / "test-source-manifest.json"
    expected = json.loads(manifest_path.read_text())["files"]
    assert sha(manifest_path) == custom["test_source_manifest_sha256"]
    assert expected == root_run["snapshot_files"] and len(expected) == 103
    nodes_path = Path(custom["test_node_manifest"])
    nodes = nodes_path.read_text().splitlines()
    assert len(nodes) == len(set(nodes)) == custom["test_node_count"] == 1722
    assert sha(nodes_path) == custom["test_node_manifest_sha256"]
    root_xml = account_xml(root_record_path.parent / "tests.xml", nodes)
    custom_xml = account_xml(custom_record_path.parent / "tests.xml", nodes)
    collection = json.loads(Path(custom["test_collection_record"]).read_text())
    assert collection["status"] == "PASS" and collection["exit_code"] == 0
    collected = [line for line in (Path(custom["test_collection_record"]).parent / "output.log").read_text().splitlines() if line.startswith("tests/") and "::" in line]
    assert collected == nodes
    suite = json.loads(Path(custom["test_suite_record"]).read_text())
    assert suite["status"] == "PASS" and suite["exit_code"] == 0
    root_inventory = snapshot(Path(root_run["test_snapshot"]), expected)
    custom_inventory = snapshot(Path(custom["destination"]) / "test-suite", expected)
    identities = json.loads((custom_record_path.parent / "identity-comparison.json").read_text())
    assert identities["original"]["source_files"] == identities["candidate"]["source_files"]
    for directory in (ROOT / ".oma/runtimes" / custom["source_checkpoint"] / "src/oma", Path(custom["runtime"]["PYTHONPATH"]) / "oma"):
        assert {p.relative_to(directory).as_posix(): sha(p) for p in directory.rglob("*.py")} == identities["candidate"]["source_files"]
    for label in ["original", "candidate"]:
        assert sha(identities[label]["extension_path"]) == identities[label]["extension_sha256"]
    assert identities["original"]["checker_version"] == root_run["checker_version"]
    assert identities["candidate"]["checker_version"] == custom["runtime"]["OMA_EXECUTABLE_BUILD"]
    result = {"status": "BOTH_RETAINED_NATIVE_SUITES_INDEPENDENTLY_ACCOUNTED", "audited_at": datetime.now(timezone.utc).isoformat(),
        "original_record_sha256": sha(root_record_path), "original_raw_status": root_run["status"],
        "custom_record_sha256": sha(custom_record_path), "source_checkpoint": custom["source_checkpoint"],
        "original_checker": root_run["checker_version"], "custom_checker": custom["runtime"]["OMA_EXECUTABLE_BUILD"],
        "node_manifest_sha256": sha(nodes_path), "nodes": len(nodes), "original_suite": root_xml, "custom_suite": custom_xml,
        "original_snapshot": root_inventory, "custom_snapshot": custom_inventory, "source_python_files_verified": len(identities["candidate"]["source_files"]),
        "loaded_native_extension_hashes_rechecked": True, "custom_command_record_sha256": sha(Path(custom["test_suite_record"])),
        "script_sha256": sha(__file__), "scope": "Independent post-completion read-only inventory/XML/source/native-identity checks of the retained runs; no test rerun and no portable or public release approval"}
    with (OUT / "completed-suites-audit.json").open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"status": result["status"], "passed_each": len(nodes), "path": str(OUT / "completed-suites-audit.json")}))


if __name__ == "__main__":
    main()
