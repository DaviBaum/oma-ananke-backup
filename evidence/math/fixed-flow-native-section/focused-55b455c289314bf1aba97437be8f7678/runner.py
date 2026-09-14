"""Run focused native correction checks from frozen application and test inputs."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import shutil
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET

STAGE = Path(__file__).resolve().parent
ROOT = next(p for p in STAGE.parents if (p / "AGENTS.md").is_file())
sys.path.insert(0, str(STAGE / "src"))
from oma.build_identity import frozen_environment
from oma.ifc.audit import atomic_json


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    identity = uuid.uuid4().hex
    out = STAGE / "evidence" / ("focused-" + identity)
    snapshot = STAGE / "validation" / identity
    out.mkdir(parents=True)
    snapshot.mkdir(parents=True)
    base_file = ROOT / ".oma/development/next-best-fabrication/evidence/full-backend-14bff19b88c54779af3d15b1295b5d8b/result.json"
    base = json.loads(base_file.read_text())
    files = {}
    for relative, digest in base["snapshot_files"].items():
        source = Path(base["test_snapshot"]) / relative
        assert sha(source) == digest
        target = snapshot / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        files[relative] = sha(target)
    for name in ("test_network_scenario.py", "test_fixed_flow_native_section.py"):
        source = STAGE / "tests" / name
        target = snapshot / "tests" / name
        shutil.copyfile(source, target)
        assert sha(source) == sha(target)
        files["tests/" + name] = sha(target)
    selected = ["tests/" + name for name in (
        "test_network_scenario.py", "test_network_integration.py", "test_network_revision.py", "test_network_projection.py",
        "test_network_pressure.py", "test_network_pressure_integration.py", "test_network_pressure_native_section.py",
        "test_fixed_flow_native_section.py", "test_physical_report_admission.py", "test_native_pressure_model_validation.py")]
    env = frozen_environment(STAGE)
    prefix = [sys.executable, "-m", "pytest", "-o", "pythonpath=" + env["PYTHONPATH"]]
    collection = subprocess.run([*prefix, *selected, "--collect-only", "-q"], cwd=snapshot, env=env,
        text=True, encoding="utf8", stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (out / "collection.log").write_text(collection.stdout, encoding="utf8")
    assert collection.returncode == 0, collection.stdout
    nodes = [s.strip() for s in collection.stdout.splitlines() if s.startswith("tests/") and "::" in s]
    assert len(nodes) == len(set(nodes)) > 0
    atomic_json(out / "test-nodes.json", nodes)
    shutil.copyfile(__file__, out / "runner.py")
    result = {"status": "RUNNING", "checker_version": env["OMA_EXECUTABLE_BUILD"], "snapshot_files": files,
        "test_snapshot": str(snapshot), "test_node_count": len(nodes), "test_nodes_sha256": sha(out / "test-nodes.json"),
        "runner_sha256": sha(out / "runner.py"), "source_base_snapshot": str(base_file), "selected": selected}
    atomic_json(out / "result.json", result)
    print(json.dumps({k: result[k] for k in ("status", "checker_version", "test_node_count", "test_snapshot")}), flush=True)
    command = [*prefix, *selected, "-q", "--junitxml=" + str(out / "tests.xml")]
    started = time.perf_counter()
    with (out / "pytest.log").open("w", encoding="utf8") as stream:
        completed = subprocess.run(command, cwd=snapshot, env=env, stdout=stream, stderr=subprocess.STDOUT)
    result.update(command=command, returncode=completed.returncode, seconds=time.perf_counter() - started)
    actual = {p.relative_to(snapshot).as_posix(): sha(p) for p in snapshot.rglob("*") if p.is_file()
        and not {"__pycache__", ".pytest_cache"}.intersection(p.relative_to(snapshot).parts)}
    result["snapshot_unchanged"] = actual == files
    xml = ET.parse(out / "tests.xml").getroot()
    expected = []
    for node in nodes:
        pieces = node.split("::")
        expected.append((pieces[0][:-3].replace("/", ".") + ("." + ".".join(pieces[1:-1]) if len(pieces) > 2 else ""), pieces[-1]))
    cases = xml.findall(".//testcase")
    result["exact_case_identities_checked"] = Counter((c.get("classname"), c.get("name")) for c in cases) == Counter(expected)
    result["test_xml_sha256"] = sha(out / "tests.xml")
    result["failures"] = len(xml.findall(".//failure")) + len(xml.findall(".//error"))
    result["skipped"] = len(xml.findall(".//skipped"))
    result["passed"] = len(cases) - result["failures"] - result["skipped"]
    result["status"] = "PASS" if completed.returncode == 0 and result["snapshot_unchanged"] and result["exact_case_identities_checked"] and not result["skipped"] else "FAIL"
    atomic_json(out / "result.json", result)
    print((out / "pytest.log").read_text(), flush=True)
    print(json.dumps({k: v for k, v in result.items() if k not in {"snapshot_files", "command", "selected"}}), flush=True)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
