"""Check the minimal residual merge privately while the current backend stays frozen."""
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
AGENT = ROOT / ".oma/development/passive-residual-bound"
BASE = ROOT / "evidence/release/passive-tree-full-c4e9176a8a97438d892dccd7779cee99/result.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf8"))


def copy(source, destination, expected):
    assert sha(source) == expected, source
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    assert sha(source) == sha(destination) == expected


def main():
    base = read(BASE)
    assert base["checker_version"] == "oma-independent-checker/2:4044a58d563922530546897240791354f7557e40471f6b4222b23f065f5610ef"
    assert len(base["source_files"]) == 102 and len(base["snapshot_files"]) == 118
    agent_handoff = AGENT / "evidence/math/passive-residual-bound/handoff.json"
    assert sha(agent_handoff) == "c34419e0049921668ba52acdda996501caa297b043059d56d1509ecb0db28c00"
    handoff = read(agent_handoff)
    assert handoff["tests"] == 86 and handoff["status"] == "IMPLEMENTED_TESTED_INDEPENDENTLY_REVIEWED"
    identity = uuid.uuid4().hex
    out = STAGE / "evidence" / ("integration-" + identity)
    snapshot = STAGE / "validation" / identity
    out.mkdir(parents=True)
    snapshot.mkdir(parents=True)
    inputs = dict(base["snapshot_files"])
    for relative, expected in inputs.items():
        copy(Path(base["test_snapshot"]) / relative, snapshot / relative, expected)
    source_files = dict(base["source_files"])
    for relative, expected in source_files.items():
        copy(Path(base["source_directory"]) / "oma" / relative, STAGE / "src/oma" / relative, expected)
    for row in handoff["merge_files"]:
        if row["path"].startswith("src/oma/"):
            relative = row["path"].removeprefix("src/oma/")
            assert relative not in source_files
            copy(AGENT / row["path"], STAGE / row["path"], row["sha256"])
            source_files[relative] = row["sha256"]
        else:
            assert row["path"] not in inputs
            copy(AGENT / row["path"], snapshot / row["path"], row["sha256"])
            inputs[row["path"]] = row["sha256"]
    assert len(source_files) == 103 and len(inputs) == 120
    sys.path.insert(0, str(STAGE / "src"))
    from oma.build_identity import checker_version, frozen_environment
    from oma.ifc.audit import atomic_json
    env = frozen_environment(STAGE)
    runtime = Path(env["PYTHONPATH"]) / "oma"
    assert {p.relative_to(runtime).as_posix(): sha(p) for p in runtime.rglob("*.py")} == source_files
    tests = ["tests/test_passive_residual.py", "tests/test_passive_pressure.py", "tests/test_passive_tree_pressure.py",
        "tests/test_passive_tree_integration.py", "tests/test_three_sink_native_geometry.py", "tests/test_worker_control_polling.py"]
    prefix = [sys.executable, "-m", "pytest", "-o", "pythonpath=" + env["PYTHONPATH"]]
    collected = subprocess.run([*prefix, *tests, "--collect-only", "-q"], cwd=snapshot, env=env,
        text=True, encoding="utf8", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
    (out / "collection.log").write_text(collected.stdout, encoding="utf8")
    assert collected.returncode == 0, collected.stdout
    nodes = [s.strip() for s in collected.stdout.splitlines() if s.startswith("tests/") and "::" in s]
    assert len(nodes) == len(set(nodes)) == 303, len(nodes)
    atomic_json(out / "test-nodes.json", nodes)
    copy(Path(__file__), out / "runner.py", sha(Path(__file__)))
    helper = ROOT / "evidence/release/pressure-package-harness-peer-review/audit_completed_suites.py"
    copy(helper, out / "inventory-helper.py", sha(helper))
    spec = importlib.util.spec_from_file_location("residual_integration_inventory", out / "inventory-helper.py")
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    result = {"status": "RUNNING", "checker_version": checker_version(), "source_directory": env["PYTHONPATH"],
        "source_files": source_files, "snapshot_files": inputs, "test_snapshot": str(snapshot),
        "test_node_count": len(nodes), "test_nodes_sha256": sha(out / "test-nodes.json"),
        "runner_sha256": sha(out / "runner.py"), "inventory_helper_sha256": sha(out / "inventory-helper.py"),
        "base_receipt": str(BASE), "base_application_hashes": base["source_files"],
        "agent_handoff_sha256": sha(agent_handoff), "production_application_modified": False}
    atomic_json(out / "result.json", result)
    print(json.dumps({"status": "RUNNING", "checker_version": result["checker_version"], "out": str(out), "cases": len(nodes)}), flush=True)
    started = time.perf_counter()
    command = [*prefix, *tests, "-q", "--junitxml=" + str(out / "tests.xml")]
    with (out / "pytest.log").open("w", encoding="utf8") as log:
        completed = subprocess.run(command, cwd=snapshot, env=env, stdout=log, stderr=subprocess.STDOUT)
    result.update(returncode=completed.returncode, seconds=time.perf_counter() - started, command=command)
    try:
        assert completed.returncode == 0
        assert {p.relative_to(runtime).as_posix(): sha(p) for p in runtime.rglob("*.py")} == source_files
        assert all(sha(snapshot / relative) == expected for relative, expected in inputs.items())
        xml = audit.account_xml(out / "tests.xml", nodes)
        result.update(status="PASS", passed=xml["passed"], failures=0, skipped=0, test_xml_sha256=xml["xml_sha256"],
            snapshot_unchanged=True, frozen_source_unchanged=True, exact_case_identities_checked=True)
    except BaseException as exc:
        result.update(status="FAIL", error=repr(exc))
    atomic_json(out / "result.json", result)
    print(json.dumps({k: result[k] for k in ("status", "checker_version", "seconds", "test_node_count")}), flush=True)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
