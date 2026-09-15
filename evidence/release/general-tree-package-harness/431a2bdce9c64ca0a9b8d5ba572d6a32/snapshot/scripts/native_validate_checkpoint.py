"""Validate a coherent newer application checkpoint with the isolated native wheel."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import uuid
import xml.etree.ElementTree as ET

from native_prepare import ROOT, DEST, EVIDENCE, sha, json_write
from native_build import run
from native_package_evidence import verify_test_snapshot, verify_suite_xml
import native_package_evidence
import native_prepare
import native_build

DRIVER_SOURCES = {Path(p).name: Path(p).read_bytes() for p in
                  (__file__, native_package_evidence.__file__, native_prepare.__file__, native_build.__file__)}
DRIVER_SHA256 = hashlib.sha256(DRIVER_SOURCES[Path(__file__).name]).hexdigest()


def test_files():
    paths = [p for p in (ROOT / "tests").rglob("*") if p.is_file() and "__pycache__" not in p.parts and ".pytest_cache" not in p.parts]
    return [*paths, ROOT / "pyproject.toml", ROOT / "docs/ifc-network-spec.json",
            ROOT / "scripts/corpus_route_metadata_probe.py",
            ROOT / "scripts/native_real_model_validation.py", ROOT / "scripts/native_prepare.py",
            ROOT / "scripts/native_build.py", ROOT / "Start-OMA.ps1"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-checkpoint", required=True)
    parser.add_argument("--source-directory", type=Path,
                        help="Explicit immutable source tree for a staged checkpoint; probed source identity must match")
    parser.add_argument("--test-snapshot-record", type=Path,
                        help="Copy exactly the declared test_snapshot/snapshot_files of an existing frozen root run")
    args = parser.parse_args()
    source = args.source_checkpoint
    assert len(source) == 64 and all(c in "0123456789abcdef" for c in source)
    source_path = (args.source_directory or ROOT / ".oma/runtimes" / source / "src").resolve()
    assert source_path.is_dir()
    identifier = source[:12] + "-" + uuid.uuid4().hex[:12]
    destination = DEST / "checkpoint-validation" / identifier
    evidence = EVIDENCE / "checkpoint-validation" / identifier
    destination.mkdir(parents=True)
    evidence.mkdir(parents=True)
    (evidence / 'driver-sources').mkdir()
    for name, content in DRIVER_SOURCES.items():
        (evidence / 'driver-sources' / name).write_bytes(content)
    result = {"status": "RUNNING", "source_checkpoint": source, "destination": str(destination),
              "active_runtime_modified": False, "prior_native_validation_modified": False,
              "driver_source_files": {name: hashlib.sha256(content).hexdigest() for name, content in DRIVER_SOURCES.items()}}
    start = time.monotonic()
    json_write(evidence / "result.json", result)
    try:
        snapshot = destination / "test-suite"
        declared_nodes = None
        if args.test_snapshot_record:
            declaration = json.loads(args.test_snapshot_record.read_text())
            assert declaration["checker_version"] == "oma-independent-checker/2:" + source
            origin = Path(declaration["test_snapshot"]).resolve()
            assert origin.is_dir()
            before = declaration["snapshot_files"]
            assert isinstance(before, dict) and before and any(p.startswith("tests/") for p in before)
            for relative, expected in before.items():
                path = (origin / relative).resolve()
                assert path.is_relative_to(origin) and path.is_file()
                assert sha(path) == expected
            result["initial_origin_snapshot_inventory"] = verify_test_snapshot(origin, before, allow_generated_evidence=True)
            json_write(evidence / "declared-test-snapshot.json", declaration)
            result.update(test_snapshot_origin=str(origin),
                test_snapshot_declaration_sha256=sha(evidence / "declared-test-snapshot.json"))
            if declaration.get('test_nodes_sha256'):
                declared_node_path = args.test_snapshot_record.parent / 'test-nodes.json'
                assert sha(declared_node_path) == declaration['test_nodes_sha256']
                declared_nodes = json.loads(declared_node_path.read_text())
                assert isinstance(declared_nodes, list) and len(declared_nodes) == declaration['test_node_count']
                shutil.copyfile(declared_node_path, evidence / 'declared-test-nodes.json')
        else:
            origin = ROOT
            before = {p.relative_to(ROOT).as_posix(): sha(p) for p in test_files()}
        for relative, digest in before.items():
            target = snapshot / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(origin / relative, target)
            assert sha(target) == digest
        assert before == {relative: sha(origin / relative) for relative in before}
        if not args.test_snapshot_record:
            assert before == {p.relative_to(ROOT).as_posix(): sha(p) for p in test_files()}
        verify_test_snapshot(snapshot, before)
        json_write(evidence / "test-source-manifest.json", {
            "status": "DECLARED_TEST_SNAPSHOT_COPIED_AND_REHASHED" if args.test_snapshot_record else "ALL_CURRENT_TEST_FILES_COPIED_AND_REHASHED",
            "files": before})
        env = os.environ.copy()
        env["PYTHONPATH"] = str(source_path)
        env.pop("OMA_EXECUTABLE_BUILD", None)
        env.pop("OMA_CONTROL_RUN_ID", None)
        probe = """import hashlib,importlib.metadata,json,sys
from pathlib import Path
import ifcopenshell._ifcopenshell_wrapper as extension
from oma.build_identity import checker_version
import oma
root=Path(oma.__file__).parent
print(json.dumps({'checker_version':checker_version(),'python':sys.executable,'python_version':sys.version,
 'source_files':{p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob('*.py'))},
 'packages':{p:importlib.metadata.version(p) for p in ('ifcopenshell','cadquery-ocp','numpy','scipy','pydantic','cupy-cuda12x')},
 'extension_path':extension.__file__,'extension_sha256':hashlib.sha256(Path(extension.__file__).read_bytes()).hexdigest()}))
"""
        original = json.loads(subprocess.check_output([str(ROOT / ".venv/Scripts/python.exe"), "-c", probe], env=env, text=True))
        python = DEST / "test-venv/Scripts/python.exe"
        candidate = json.loads(subprocess.check_output([str(python), "-c", probe], env=env, text=True))
        wheel = json.loads((EVIDENCE / "candidate-wheel.json").read_text())
        assert original["checker_version"].endswith(source)
        assert original["source_files"] == candidate["source_files"] and original["python_version"] == candidate["python_version"]
        assert original["packages"]["ifcopenshell"] == "0.8.5" and candidate["packages"]["ifcopenshell"] == wheel["version"]
        assert candidate["extension_sha256"] == wheel["variant"]["native_extension_sha256"]
        assert {k:v for k,v in original["packages"].items() if k != "ifcopenshell"} == {k:v for k,v in candidate["packages"].items() if k != "ifcopenshell"}
        assert original["checker_version"] != candidate["checker_version"]
        json_write(evidence / "identity-comparison.json", {"status": "IDENTICAL_SOURCE_DISTINCT_VALIDATED_NATIVE_BUILD", "original": original, "candidate": candidate})
        freeze = "from oma.build_identity import frozen_environment;import json;e=frozen_environment(" + repr(str(destination)) + ");print(json.dumps({k:e[k] for k in ('PYTHONPATH','OMA_EXECUTABLE_BUILD')}))"
        frozen = json.loads(subprocess.check_output([str(python), "-c", freeze], env=env, text=True))
        assert frozen["OMA_EXECUTABLE_BUILD"] == candidate["checker_version"]
        env.update(frozen)
        direct_kernel = Path(frozen["PYTHONPATH"]) / "oma/optimization/shared_tree_synthesis.py"
        if "tests/test_general_shared_tree_synthesis.py" in before:
            assert direct_kernel.is_file()
            assert sha(direct_kernel) == candidate["source_files"]["optimization/shared_tree_synthesis.py"]
            env["OMA_SHARED_TREE_SOURCE"] = str(direct_kernel)
            result["kernel_direct_load"] = {"path": str(direct_kernel), "sha256": sha(direct_kernel),
                                          "scope": "Exact custom frozen application module"}
        else:
            env.pop("OMA_SHARED_TREE_SOURCE", None)
        result.update(runtime=frozen, native_wheel_sha256=sha(Path(wheel["wheel"])), native_version=wheel["version"],
                      native_extension_sha256=candidate["extension_sha256"], test_source_manifest_sha256=sha(evidence / "test-source-manifest.json"))
        collection = run("checkpoint-test-collection", [python, "-m", "pytest", "--collect-only", "-q", "-o", "pythonpath=", "tests"],
                         cwd=snapshot, env=env, budget=300)
        nodes = [line for line in (collection / "output.log").read_text().splitlines() if line.startswith("tests/") and "::" in line]
        assert len(nodes) == len(set(nodes)) and len(nodes) >= 916
        if declared_nodes is not None:
            assert nodes == declared_nodes, 'Custom-native collection differs from declared root node order'
        node_path = destination / "selected-tests.args"
        node_path.write_text("\n".join(nodes) + "\n", encoding="utf-8")
        result.update(test_node_count=len(nodes), test_node_manifest_sha256=sha(node_path), test_node_manifest=str(node_path),
                      test_collection_record=str(collection / "record.json"))
        json_write(evidence / "result.json", result)
        suite = run("checkpoint-full-suite", [python, "-m", "pytest", "-q", "-o", "pythonpath=", "@" + str(node_path),
                    "--junitxml=" + str(evidence / "tests.xml")], cwd=snapshot, env=env, budget=1800)
        verify_suite_xml(evidence / "tests.xml", nodes, direct_interpreter=False)
        if "kernel_direct_load" in result:
            assert sha(direct_kernel) == result["kernel_direct_load"]["sha256"]
        result["final_test_snapshot_inventory"] = verify_test_snapshot(snapshot, before, allow_generated_evidence=True)
        if args.test_snapshot_record:
            result["final_origin_snapshot_inventory"] = verify_test_snapshot(origin, before, allow_generated_evidence=True)
        result.update(status="CUSTOM_NATIVE_NEW_CHECKPOINT_FULL_SUITE_PASS", test_suite_record=str(suite / "record.json"),
                      test_xml_sha256=sha(evidence / "tests.xml"), passed=len(nodes), failed=0, skipped=0)
    except BaseException as error:
        result.update(status="INCOMPLETE_OR_FAILED", error=repr(error))
        raise
    finally:
        result.update(seconds=time.monotonic() - start, driver_sha256=DRIVER_SHA256,
                      driver_bytes_unchanged=sha(Path(__file__)) == DRIVER_SHA256)
        json_write(evidence / "result.json", result)
        print(json.dumps({key:result.get(key) for key in ("status", "source_checkpoint", "runtime", "test_node_count", "seconds", "error")}), flush=True)


if __name__ == "__main__":
    main()
