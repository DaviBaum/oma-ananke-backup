"""Full combined application regression from exact frozen source/test inputs."""
from pathlib import Path
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import time
import uuid

STAGE = Path(__file__).resolve().parent
ROOT = next(p for p in STAGE.parents if (p / "AGENTS.md").is_file())
sys.path.insert(0, str(ROOT / "src"))
from oma.build_identity import checker_version, frozen_environment
from oma.ifc.audit import atomic_json


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    identity = uuid.uuid4().hex
    out = ROOT / "evidence/release" / ("combined-pressure-full-" + identity)
    snapshot = STAGE / "validation" / identity
    out.mkdir(parents=True)
    snapshot.mkdir(parents=True)
    base_file = ROOT / ".oma/development/fixed-flow-native-section/evidence/focused-55b455c289314bf1aba97437be8f7678/result.json"
    base = json.loads(base_file.read_text(encoding="utf8"))
    assert base["status"] == "PASS" and base["passed"] == 172 and len(base["snapshot_files"]) == 107
    files = {}
    for relative, expected in base["snapshot_files"].items():
        source = Path(base["test_snapshot"]) / relative
        assert sha(source) == expected, source
        target = snapshot / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        assert sha(target) == expected
        files[relative] = expected
    for relative in ("tests/test_passive_pressure.py", "tests/fixtures/passive-pressure/reference-results.json",
                     "tests/fixtures/passive-pressure/coupled-loop-result.json"):
        source = ROOT / relative
        target = snapshot / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        expected = sha(source)
        shutil.copyfile(source, target)
        assert sha(source) == sha(target) == expected
        files[relative] = expected
    assert len(files) == 110
    env = frozen_environment(STAGE)
    prefix = [sys.executable, "-m", "pytest", "-o", "pythonpath=" + env["PYTHONPATH"]]
    collected = subprocess.run([*prefix, "tests", "--collect-only", "-q"], cwd=snapshot, env=env,
        text=True, encoding="utf8", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
    (out / "collection.log").write_text(collected.stdout, encoding="utf8")
    assert collected.returncode == 0, collected.stdout
    nodes = [s.strip() for s in collected.stdout.splitlines() if s.startswith("tests/") and "::" in s]
    assert len(nodes) == len(set(nodes)) == 1979
    atomic_json(out / "test-nodes.json", nodes)
    (out / "test-nodes.args").write_text("\n".join(nodes) + "\n", encoding="utf8")
    shutil.copyfile(__file__, out / "runner.py")
    helper = ROOT / "evidence/release/pressure-package-harness-peer-review/audit_completed_suites.py"
    shutil.copyfile(helper, out / "inventory-helper.py")
    spec = importlib.util.spec_from_file_location("completed_inventory", out / "inventory-helper.py")
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    source_files = {p.relative_to(Path(env["PYTHONPATH"]) / "oma").as_posix(): sha(p)
        for p in (Path(env["PYTHONPATH"]) / "oma").rglob("*.py")}
    result = {"status": "RUNNING", "checker_version": env["OMA_EXECUTABLE_BUILD"], "source_files": source_files,
        "source_directory": env["PYTHONPATH"], "snapshot_files": files, "test_snapshot": str(snapshot),
        "test_node_count": len(nodes), "test_nodes_sha256": sha(out / "test-nodes.json"),
        "test_nodes_args_sha256": sha(out / "test-nodes.args"), "runner_sha256": sha(out / "runner.py"),
        "inventory_helper_sha256": sha(out / "inventory-helper.py"), "source_base_snapshot": str(base_file),
        "scope": "All application cases in the declared frozen snapshot; separate packaging-harness tests retain their own receipts"}
    atomic_json(out / "result.json", result)
    print(json.dumps({k: result[k] for k in ("status", "checker_version", "test_node_count", "test_snapshot", "source_directory")}), flush=True)
    started = time.perf_counter()
    command = [*prefix, "tests", "-q", "--junitxml=" + str(out / "tests.xml")]
    with (out / "pytest.log").open("w", encoding="utf8") as stream:
        completed = subprocess.run(command, cwd=snapshot, env=env, stdout=stream, stderr=subprocess.STDOUT)
    result.update(returncode=completed.returncode, seconds=time.perf_counter() - started, command=command)
    try:
        assert completed.returncode == 0
        inventory = audit.snapshot(snapshot, files)
        xml = audit.account_xml(out / "tests.xml", nodes)
        actual_source = {p.relative_to(Path(env["PYTHONPATH"]) / "oma").as_posix(): sha(p)
            for p in (Path(env["PYTHONPATH"]) / "oma").rglob("*.py")}
        assert actual_source == source_files
        atomic_json(out / "completed-inventory.json", inventory)
        result.update(status="PASS", passed=xml["passed"], failures=0, skipped=0, snapshot_unchanged=True,
            exact_case_identities_checked=True, frozen_source_unchanged=True,
            current_source_unchanged=checker_version() == env["OMA_EXECUTABLE_BUILD"],
            test_xml_sha256=xml["xml_sha256"], derived_test_outputs=inventory["derived_output_sha256"],
            completed_inventory_sha256=sha(out / "completed-inventory.json"))
    except BaseException as exc:
        result.update(status="FAIL", error=repr(exc))
    atomic_json(out / "result.json", result)
    print((out / "pytest.log").read_text(encoding="utf8"), flush=True)
    print(json.dumps({k: v for k, v in result.items() if k not in {"snapshot_files", "source_files", "command"}}), flush=True)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
