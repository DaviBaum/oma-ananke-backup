"""Build and exercise a separate offline preview with the validated custom wheel.

No active runtime, existing portable package, original wheelhouse or root lock
is replaced. All native provenance and the exact source checkpoint are carried.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import uuid

from packaging.utils import canonicalize_name, parse_wheel_filename

from native_prepare import ROOT, DEST, EVIDENCE, sha, json_write
from native_build import run
from native_package_evidence import payload_files, verify_payload, verify_test_snapshot


SOURCE = "94e74251a39d1f0d8cc77feb9d2df686e3927eb49473b67d09d8bdf66843c93f"
PYTHON_NAME = "cpython-3.12.14+20260901-x86_64-pc-windows-msvc-install_only.tar.gz"
PYTHON_SHA = "e90c1b6419da3bd812dd73bb3de40287a21abf153438147639ec5e20375ea93f"


def copy_file(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    assert sha(source) == sha(target)
    return {"path": str(target), "sha256": sha(target), "bytes": target.stat().st_size}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--native-wheel", type=Path)
    parser.add_argument("--real-model-inputs", type=Path, help="Predeclared exact joint-budget and pressure-network recheck inputs")
    parser.add_argument("--checkpoint-validation", type=Path,
                        help="A completed isolated full-suite record for a newer coherent app source")
    args = parser.parse_args()
    native = json.loads((EVIDENCE / "candidate-wheel.json").read_text())
    validated = json.loads((EVIDENCE / "handoff.json").read_text())
    assert validated["status"] == "ISOLATED_NATIVE_CANDIDATE_BUILT_AND_VALIDATED_NOT_PROMOTED"
    checkpoint = json.loads(args.checkpoint_validation.read_text()) if args.checkpoint_validation else None
    if checkpoint:
        assert checkpoint["status"] == "CUSTOM_NATIVE_NEW_CHECKPOINT_FULL_SUITE_PASS"
        assert checkpoint["native_wheel_sha256"] == native["sha256"]
        source_checkpoint = checkpoint["source_checkpoint"]
        application_checker = checkpoint["runtime"]["OMA_EXECUTABLE_BUILD"]
        application_tests = {k:checkpoint[k] for k in ("test_node_count", "passed", "failed", "skipped", "test_xml_sha256", "test_node_manifest_sha256")}
        validated_source_files = json.loads((args.checkpoint_validation.parent / "identity-comparison.json").read_text())["candidate"]["source_files"]
    else:
        assert validated["app_source_checkpoint"] == SOURCE
        source_checkpoint = SOURCE
        application_checker = validated["checker_version"]
        application_tests = validated["tests"]
        validated_source_files = json.loads((EVIDENCE / "runtime-identity-comparison.json").read_text())["candidate"]["source_files"]
    wheel = (args.native_wheel or Path(native["wheel"])).resolve()
    assert sha(wheel) == native["sha256"] == validated["wheel"]["sha256"]
    assert canonicalize_name(parse_wheel_filename(wheel.name)[0]) == "ifcopenshell"
    archive = ROOT / ".release" / PYTHON_NAME
    assert sha(archive) == PYTHON_SHA
    package = DEST / "portable-candidates" / (source_checkpoint[:12] + "-" + uuid.uuid4().hex[:12])
    package.mkdir(parents=True)
    evidence = EVIDENCE / "portable-candidates" / package.name
    evidence.mkdir(parents=True)
    result = {"status": "RUNNING", "package": str(package), "source_checkpoint": source_checkpoint,
              "application_test_validation": application_tests, "application_test_checker_version": application_checker,
              "checkpoint_validation_sha256": sha(args.checkpoint_validation) if args.checkpoint_validation else None,
              "native_wheel_sha256": sha(wheel), "native_version": native["version"],
              "native_handoff_sha256": sha(EVIDENCE / "handoff.json"),
              "python_archive_sha256": PYTHON_SHA, "active_runtime_modified": False,
              "previous_portable_preview_modified": False, "public_redistribution": "NOT_CLEARED",
              "scope": "Isolated candidate bundle and offline analytic workflow; not a production release"}
    json_write(evidence / "result.json", result)
    try:
        wheelhouse = package / "wheelhouse"
        wheelhouse.mkdir()
        requirements = (ROOT / "requirements-runtime.lock").read_text().splitlines()
        assert sum(line.startswith("ifcopenshell==") for line in requirements) == 1
        requirements = ["ifcopenshell==" + native["version"] if line.startswith("ifcopenshell==") else line for line in requirements]
        wheels = []
        for requirement in requirements:
            name, version = requirement.split("==")
            if name == "ifcopenshell":
                selected = wheel
            else:
                matches = [p for p in (ROOT / ".release/wheelhouse").glob("*.whl")
                           if canonicalize_name(parse_wheel_filename(p.name)[0]) == canonicalize_name(name)
                           and str(parse_wheel_filename(p.name)[1]) == version]
                assert len(matches) == 1, (requirement, matches)
                selected = matches[0]
            wheels.append(copy_file(selected, wheelhouse / selected.name))
        assert len(wheels) == len(requirements) == 59
        lock = package / "requirements-runtime.lock"
        lock.write_text("\n".join(requirements) + "\n", encoding="utf-8")
        with tarfile.open(archive) as source_archive:
            source_archive.extractall(package, filter="data")
        (package / "python").rename(package / "runtime")
        env = os.environ.copy()
        for key in ("PYTHONPATH", "OMA_EXECUTABLE_BUILD", "OMA_CONTROL_RUN_ID"):
            env.pop(key, None)
        env.update(PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1", PIP_NO_INDEX="1", PIP_DISABLE_PIP_VERSION_CHECK="1")
        installation = run("candidate-bundle-offline-install", [sys.executable, "-m", "pip", "install", "--no-index", "--no-deps",
            "--no-compile", "--ignore-installed", "--find-links", wheelhouse, "--target", package / "runtime/Lib/site-packages", "-r", lock],
            cwd=package, env=env, budget=1200)
        sources = ROOT / ".oma/runtimes" / source_checkpoint / "src"
        assert {p.relative_to(sources / "oma").as_posix(): sha(p) for p in (sources / "oma").rglob("*.py")} == validated_source_files
        shutil.copytree(sources, package / "src", ignore=shutil.ignore_patterns("__pycache__"))
        source_hashes = {p.relative_to(sources).as_posix(): sha(p) for p in sources.rglob("*.py")}
        assert source_hashes == {p.relative_to(package / "src").as_posix(): sha(p) for p in (package / "src").rglob("*.py")}
        # Existing presentation assets are included unchanged; this backend test
        # makes no new UI compatibility or performance claim.
        shutil.copytree(ROOT / "ui/dist", package / "ui/dist")
        for name in ("OMA.cmd", "Start-OMA.ps1", "Install-OMA.ps1", "README.md"):
            copy_file(ROOT / name, package / name)
        shutil.copytree(ROOT / "docs", package / "docs")
        (package / "runtime/Lib/site-packages/oma-workbench.pth").write_text("../../../src\n", encoding="utf-8")
        provenance = package / "provenance"
        provenance.mkdir()
        if args.real_model_inputs:
            from native_package_evidence import real_model_inputs
            copy_file(args.real_model_inputs, provenance / 'real-model-validation-inputs.json')
            result['real_model_validation_inputs_sha256'] = sha(provenance / 'real-model-validation-inputs.json')
            real_model_inputs(package, result)
        # Include build source archives and notices, but no IFC-Bench assets.
        provenance_files = []
        for path in sorted((DEST / "downloads").iterdir()):
            if path.is_file():
                provenance_files.append(copy_file(path, provenance / "source-archives" / path.name))
        for manifest_path in (EVIDENCE / "extraction").glob("*.json"):
            manifest = json.loads(manifest_path.read_text())
            for notice in manifest.get("notice_paths", []):
                source = Path(manifest["destination"]) / notice["path"]
                provenance_files.append(copy_file(source, provenance / "notices" / manifest_path.stem / notice["path"]))
        for name in ("extraction", "patches", "retrievals"):
            shutil.copytree(EVIDENCE / name, provenance / name)
        for path in EVIDENCE.glob("*.json"):
            copy_file(path, provenance / "native-build" / path.name)
        if checkpoint:
            shutil.copytree(args.checkpoint_validation.parent, provenance / "checkpoint-validation")
            assert sha(Path(checkpoint["test_node_manifest"])) == checkpoint["test_node_manifest_sha256"]
            copy_file(Path(checkpoint["test_node_manifest"]), provenance / "checkpoint-validation/selected-tests.args")
            test_declaration = json.loads((args.checkpoint_validation.parent / "test-source-manifest.json").read_text())
            assert sha(args.checkpoint_validation.parent / "test-source-manifest.json") == checkpoint["test_source_manifest_sha256"]
            test_origin = Path(checkpoint["destination"]) / "test-suite"
            verify_test_snapshot(test_origin, test_declaration["files"], allow_generated_evidence=True)
            for relative in test_declaration["files"]:
                copy_file(test_origin / relative, provenance / "checkpoint-test-sources" / relative)
            verify_test_snapshot(provenance / "checkpoint-test-sources", test_declaration["files"])
        for name in ("README.md",):
            copy_file(EVIDENCE / name, provenance / "native-build" / name)
        copy_file(ROOT / "evidence/dependencies/native-review/README.md", provenance / "review-status.md")
        copy_file(ROOT / "scripts/verify_portable_preview.py", package / "scripts/verify_portable_preview.py")
        guard = """import os, sys
if os.environ.get('OMA_OFFLINE_DENY_NETWORK') == '1':
    def deny_network(event, args):
        if event in ('socket.connect', 'socket.getaddrinfo', 'socket.gethostbyname'):
            raise RuntimeError('Offline verification denies Python network operations: ' + event)
    sys.addaudithook(deny_network)
"""
        (package / "runtime/Lib/site-packages/sitecustomize.py").write_text(guard, encoding="utf-8")
        env["OMA_OFFLINE_DENY_NETWORK"] = "1"
        executable = package / "runtime/python.exe"
        probe = """import sys,json,hashlib,importlib.metadata,pathlib,oma
import ifcopenshell._ifcopenshell_wrapper as extension
from oma.build_identity import checker_version
print(json.dumps({'python':sys.version,'executable':sys.executable,'oma':oma.__file__,
 'ifc_version':importlib.metadata.version('ifcopenshell'),'extension':extension.__file__,
 'extension_sha256':hashlib.sha256(pathlib.Path(extension.__file__).read_bytes()).hexdigest(),
 'checker_version':checker_version()}))
"""
        identity = json.loads(subprocess.check_output([str(executable), "-s", "-c", probe], cwd=package, env=env, text=True))
        assert Path(identity["oma"]).resolve().is_relative_to(package)
        assert Path(identity["extension"]).resolve().is_relative_to(package)
        assert identity["ifc_version"] == native["version"] and identity["extension_sha256"] == native["variant"]["native_extension_sha256"]
        assert identity["checker_version"] != application_checker  # bundled Python differs
        installed_probe = "import importlib.metadata,json;print(json.dumps({name:importlib.metadata.version(name) for name in " + repr([line.split("==")[0] for line in requirements]) + "}))"
        installed = json.loads(subprocess.check_output([str(executable), "-s", "-c", installed_probe], cwd=package, env=env, text=True))
        assert installed == dict(line.split("==") for line in requirements)
        # Persist the package declaration before the smoke can produce derived state.
        result.update(identity=identity, installed_distribution_versions=installed, wheels=wheels, requirements_sha256=sha(lock), source_python_files=source_hashes,
                      source_provenance=provenance_files, installation_record=str(installation / "record.json"),
                      python_network_guard="Audit-hook denial enabled in bundle and checker subprocesses; no OS/native socket firewall claim",
                      ui_claim="Existing prebuilt assets copied; no new UI validation in this backend campaign")
        payload = {"schema": "oma.validated-portable-payload/1", "source_checkpoint": source_checkpoint,
                   "checker_version": identity["checker_version"], "files": payload_files(package),
                   "scope": "Exact executable, runtime, application, UI, wheelhouse, launchers, docs and workflow script bytes; later QA/provenance evidence is separate"}
        json_write(package / "validated-payload.json", payload)
        result["validated_payload_manifest_sha256"] = sha(package / "validated-payload.json")
        json_write(package / "package-manifest.json", result)
        smoke = run("candidate-bundle-offline-workflow", [executable, "-s", package / "scripts/verify_portable_preview.py", "--child", package],
                    cwd=package, env=env, budget=600)
        workflow = json.loads((package / "offline-qa/result.json").read_text())
        assert workflow["status"] == "PASS" and workflow["checker_build"] == identity["checker_version"]
        assert workflow["export"]["round_trip"] == "PASS" and workflow["export"]["status"] == "CHECKED_LOCAL_SCOPE"
        verify_payload(package, result)
        result.update(status="ISOLATED_NATIVE_PORTABLE_OFFLINE_WORKFLOW_PASS", workflow=workflow,
                      workflow_record=str(smoke / "record.json"))
        json_write(evidence / "workflow.json", workflow)
        json_write(package / "package-manifest.json", result)
    except BaseException as error:
        result.update(status="INCOMPLETE_OR_FAILED", error=repr(error))
        raise
    finally:
        result["builder_script_sha256"] = sha(Path(__file__))
        json_write(evidence / "result.json", result)
        print(json.dumps({key: result.get(key) for key in ("status", "package", "identity", "error")}), flush=True)


if __name__ == "__main__":
    main()
