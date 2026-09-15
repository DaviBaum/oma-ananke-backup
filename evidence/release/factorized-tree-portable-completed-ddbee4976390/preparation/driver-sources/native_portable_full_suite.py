"""Run the exact frozen suite under bundled Python with external local test tools."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

from native_prepare import ROOT, DEST, sha, json_write
from native_build import run
from native_package_evidence import verify_payload, verify_suite_xml, verify_test_snapshot, verify_checkpoint_inputs
import native_package_evidence
import native_prepare
import native_build

DRIVER_SOURCES = {Path(p).name: Path(p).read_bytes() for p in
                  (__file__, native_package_evidence.__file__, native_prepare.__file__, native_build.__file__)}
DRIVER_SHA256 = hashlib.sha256(DRIVER_SOURCES[Path(__file__).name]).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    args.result = args.result.resolve()
    portable = json.loads(args.result.read_text())
    assert portable["status"] == "ISOLATED_NATIVE_PORTABLE_OFFLINE_WORKFLOW_PASS"
    package = Path(portable["package"]).resolve()
    checkpoint = json.loads((package / "provenance/checkpoint-validation/result.json").read_text())
    assert checkpoint["status"] == "CUSTOM_NATIVE_NEW_CHECKPOINT_FULL_SUITE_PASS"
    assert checkpoint["source_checkpoint"] == portable["source_checkpoint"]
    verify_payload(package, portable)
    declaration_path = package / "provenance/checkpoint-validation/test-source-manifest.json"
    assert sha(declaration_path) == checkpoint["test_source_manifest_sha256"]
    declaration = json.loads(declaration_path.read_text())
    checked_checkpoint, checked_declaration = verify_checkpoint_inputs(package, portable)
    assert checkpoint == checked_checkpoint and declaration == checked_declaration
    verify_test_snapshot(package / "provenance/checkpoint-test-sources", declaration["files"])
    node_path = package / "provenance/checkpoint-validation/selected-tests.args"
    assert sha(node_path) == checkpoint["test_node_manifest_sha256"]
    nodes = node_path.read_text().splitlines()
    assert len(nodes) == len(set(nodes)) == checkpoint["test_node_count"]
    directory = DEST / "portable-full-suite" / uuid.uuid4().hex
    snapshot = directory / "test-suite"
    snapshot.mkdir(parents=True)
    (directory / 'driver-sources').mkdir()
    for name, content in DRIVER_SOURCES.items():
        (directory / 'driver-sources' / name).write_bytes(content)
    for relative, expected in declaration["files"].items():
        original = package / "provenance/checkpoint-test-sources" / relative
        target = snapshot / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        assert sha(original) == expected
        shutil.copyfile(original, target)
        assert sha(target) == expected
    verify_test_snapshot(snapshot, declaration["files"])
    copied_nodes = directory / "selected-tests.args"
    shutil.copyfile(node_path, copied_nodes)
    assert sha(copied_nodes) == checkpoint["test_node_manifest_sha256"]
    tools = directory / "test-tools"
    tools.mkdir()
    env = os.environ.copy()
    for key in ("PYTHONPATH", "OMA_EXECUTABLE_BUILD", "OMA_CONTROL_RUN_ID", "OMA_OFFLINE_DENY_NETWORK"):
        env.pop(key, None)
    env.update(PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1", PIP_NO_INDEX="1",
               PIP_DISABLE_PIP_VERSION_CHECK="1", PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
    wheels = sorted((DEST / "test-wheels").glob("*.whl"))
    expected_tools = {"pytest", "pluggy", "iniconfig", "lxml", "python_docx", "pymupdf"}
    assert {wheel.name.split("-")[0] for wheel in wheels} == expected_tools
    result = {"status": "RUNNING", "package": str(package), "source_checkpoint": portable["source_checkpoint"],
              "checker_version": portable["identity"]["checker_version"], "test_node_count": len(nodes),
              "test_node_manifest_sha256": sha(copied_nodes), "test_source_manifest": declaration,
              "directory": str(directory), "external_test_tools": str(tools),
              "portable_validation_result_sha256": sha(args.result),
              "validated_payload_manifest_sha256": portable["validated_payload_manifest_sha256"],
              "driver_source_files": {name: hashlib.sha256(content).hexdigest() for name, content in DRIVER_SOURCES.items()},
              "test_tool_wheels": [{"name": w.name, "sha256": sha(w)} for w in wheels],
              "package_runtime_modified": False, "scope": "Exact frozen application suite under bundled interpreter/native packages; only test tools are external"}
    output = args.result.parent / "bundled-full-suite.json"
    started = time.monotonic()
    json_write(output, result)
    try:
        installed = run("bundled-external-test-tools", [sys.executable, "-m", "pip", "install", "--no-index", "--no-deps",
                        "--no-compile", "--ignore-installed", "--target", tools, *wheels], cwd=directory, env=env, budget=180)
        env["PYTHONPATH"] = os.pathsep.join([str(package / "src"), str(tools)])
        env["OMA_EXECUTABLE_BUILD"] = portable["identity"]["checker_version"]
        if "tests/test_general_shared_tree_synthesis.py" in declaration["files"]:
            direct_kernel = package / "src/oma/optimization/shared_tree_synthesis.py"
            assert sha(direct_kernel) == portable["source_python_files"]["oma/optimization/shared_tree_synthesis.py"]
            env["OMA_SHARED_TREE_SOURCE"] = str(direct_kernel)
            result["kernel_direct_load"] = {"path": str(direct_kernel), "sha256": sha(direct_kernel),
                                          "scope": "Exact bundled application module"}
        else:
            env.pop("OMA_SHARED_TREE_SOURCE", None)
        python = package / "runtime/python.exe"
        probe = """import json,sys,pytest,ifcopenshell,OCP,numpy,pydantic,oma
from oma.build_identity import checker_version
print(json.dumps({'python':sys.executable,'python_version':sys.version,'checker_version':checker_version(),
 'sys_path':sys.path,'modules':{m.__name__:m.__file__ for m in (pytest,ifcopenshell,OCP,numpy,pydantic,oma)}}))"""
        identity = json.loads(subprocess.check_output([str(python), "-B", "-s", "-c", probe], cwd=snapshot, env=env, text=True))
        assert identity["checker_version"] == portable["identity"]["checker_version"]
        assert "3.12.14" in identity["python_version"]
        assert Path(identity["modules"]["pytest"]).resolve().is_relative_to(tools)
        assert all(Path(path).resolve().is_relative_to(package) for name, path in identity["modules"].items() if name != "pytest")
        assert not any(".venv" in path.lower() or "test-venv" in path.lower() for path in identity["sys_path"])
        result.update(identity=identity, installation_record=str(installed / "record.json"))
        json_write(output, result)
        collection = run("bundled-full-suite-collection", [python, "-B", "-s", "-m", "pytest", "--collect-only", "-q", "-o", "pythonpath=", "tests"],
                         cwd=snapshot, env=env, budget=180)
        collected = [line for line in (collection / "output.log").read_text().splitlines() if line.startswith("tests/") and "::" in line]
        assert collected == nodes, "Bundled collection differs from the original frozen node manifest"
        suite = run("bundled-exact-full-suite", [python, "-B", "-s", "-m", "pytest", "-q", "-o", "pythonpath=", "@" + str(copied_nodes),
                    "--junitxml=" + str(args.result.parent / "bundled-tests.xml")], cwd=snapshot, env=env, budget=2400)
        xml_path = args.result.parent / "bundled-tests.xml"
        accounting = verify_suite_xml(xml_path, nodes)
        result["final_test_snapshot_inventory"] = verify_test_snapshot(snapshot, declaration["files"], allow_generated_evidence=True)
        verify_test_snapshot(package / "provenance/checkpoint-test-sources", declaration["files"])
        verify_payload(package, portable)
        result.update(status="BUNDLED_EXACT_FROZEN_FULL_SUITE_PASS_WITH_DECLARED_DIRECT_INTERPRETER_NOT_APPLICABLE", **accounting,
                      test_xml_sha256=sha(xml_path), collection_record=str(collection / "record.json"),
                      suite_record=str(suite / "record.json"))
    except BaseException as error:
        result.update(status="INCOMPLETE_OR_FAILED", error=repr(error))
        raise
    finally:
        result.update(seconds=time.monotonic()-started, driver_sha256=DRIVER_SHA256,
                      driver_bytes_unchanged=sha(Path(__file__)) == DRIVER_SHA256)
        json_write(output, result)
        print(json.dumps({k:result.get(k) for k in ("status", "checker_version", "passed", "skipped", "seconds", "error")}), flush=True)


if __name__ == "__main__":
    main()
