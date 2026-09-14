"""Freeze the complete input set and run all affected network admission paths."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET
from collections import Counter

STAGE = Path(__file__).resolve().parent
ROOT = next(p for p in STAGE.parents if (p / "AGENTS.md").is_file())
sys.path.insert(0, str(STAGE / "src"))
from oma.build_identity import checker_version, frozen_environment
from oma.ifc.audit import atomic_json


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(directory):
    return {p.relative_to(directory).as_posix(): sha(p) for p in directory.rglob("*")
        if p.is_file() and not {"__pycache__", ".pytest_cache"}.intersection(p.relative_to(directory).parts)}


def main():
    identity = uuid.uuid4().hex
    out, snapshot = STAGE / "evidence" / ("integration-" + identity), STAGE / "validation" / identity
    out.mkdir(parents=True); snapshot.mkdir(parents=True)
    base_path = ROOT / "evidence/release/combined-pressure-full-9d7898a1fcca4928a1f3159ec64f81d0/result.json"
    base = json.loads(base_path.read_text(encoding="utf8"))
    assert base["status"] == "PASS" and len(base["snapshot_files"]) == 110
    files = dict(base["snapshot_files"])
    for relative, expected in files.items():
        source, target = Path(base["test_snapshot"]) / relative, snapshot / relative
        assert sha(source) == expected
        target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(source, target)
    for source in (STAGE / "tests").rglob("*"):
        if not source.is_file() or source.suffix not in (".py", ".json") or "__pycache__" in source.parts:
            continue
        relative = source.relative_to(STAGE).as_posix()
        assert relative not in files
        target = snapshot / relative
        target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(source, target)
        files[relative] = sha(source)
    assert inventory(snapshot) == files
    env = frozen_environment(STAGE)
    source_dir = Path(env["PYTHONPATH"]) / "oma"
    source_files = {p.relative_to(source_dir).as_posix(): sha(p) for p in source_dir.rglob("*.py")}
    selected = sorted(name for name in files if name.startswith("tests/test_") and name.endswith(".py") and
        (name.startswith(("tests/test_network", "tests/test_passive_tree", "tests/test_three_sink"))
         or name in ("tests/test_physical_report_admission.py", "tests/test_fixed_flow_native_section.py")))
    prefix = [sys.executable, "-m", "pytest", "-o", "pythonpath=" + env["PYTHONPATH"]]
    collected = subprocess.run([*prefix, *selected, "--collect-only", "-q"], cwd=snapshot, env=env,
        text=True, encoding="utf8", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
    (out / "collection.log").write_text(collected.stdout, encoding="utf8")
    assert collected.returncode == 0, collected.stdout
    nodes = [s.strip() for s in collected.stdout.splitlines() if s.startswith("tests/") and "::" in s]
    assert len(nodes) == len(set(nodes))
    atomic_json(out / "test-nodes.json", nodes)
    shutil.copyfile(__file__, out / "runner.py")
    record = {"status": "RUNNING", "checker_version": env["OMA_EXECUTABLE_BUILD"], "source_directory": str(source_dir.parent),
        "source_files": source_files, "snapshot_files": files, "test_snapshot": str(snapshot),
        "selected_files": selected, "test_node_count": len(nodes), "test_nodes_sha256": sha(out / "test-nodes.json"),
        "runner_sha256": sha(out / "runner.py"), "base_full_result_sha256": sha(base_path)}
    atomic_json(out / "result.json", record)
    print(json.dumps({k: record[k] for k in ("status", "checker_version", "test_node_count", "test_snapshot")}), flush=True)
    start = time.perf_counter()
    with (out / "pytest.log").open("w", encoding="utf8") as stream:
        proc = subprocess.run([*prefix, *selected, "-q", "--junitxml=" + str(out / "tests.xml")],
            cwd=snapshot, env=env, stdout=stream, stderr=subprocess.STDOUT)
    record.update(returncode=proc.returncode, seconds=time.perf_counter() - start)
    try:
        assert inventory(snapshot) == files
        assert {p.relative_to(source_dir).as_posix(): sha(p) for p in source_dir.rglob("*.py")} == source_files
        cases = ET.parse(out / "tests.xml").getroot().findall(".//testcase")
        expected = Counter((n.split("::")[0][:-3].replace("/", "."), n.split("::")[-1]) for n in nodes)
        assert Counter((c.attrib["classname"], c.attrib["name"]) for c in cases) == expected
        failures = [c for c in cases if c.find("failure") is not None or c.find("error") is not None]
        skips = [c for c in cases if c.find("skipped") is not None]
        record.update(passed=len(cases)-len(failures)-len(skips), failed=len(failures), skipped=len(skips),
            exact_case_identities_checked=True, inputs_unchanged=True, source_unchanged=True, test_xml_sha256=sha(out / "tests.xml"))
        assert proc.returncode == 0 and not failures and not skips
        record["status"] = "PASS"
    except BaseException as exc:
        record.update(status="FAIL", error=repr(exc))
    atomic_json(out / "result.json", record)
    print((out / "pytest.log").read_text(encoding="utf8"), flush=True)
    print(json.dumps({k: v for k,v in record.items() if k not in ("source_files", "snapshot_files", "selected_files")}), flush=True)
    return 0 if record["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
