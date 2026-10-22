"""The validation CLI rechecks actual network bytes from an explicit private Store."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from oma.build_identity import checker_version, frozen_environment
from oma.exporting import export_project
from oma.routing.engine import route_project_run
from oma.worker import WorkerControl
from test_native_real_model_validation_script import _script, ReadOnly
from test_network_integration import imported_project
from test_network_pressure import pressure_scenario


@pytest.fixture(scope="module")
def exported_pressure_network(tmp_path_factory):
    directory = tmp_path_factory.mktemp("validation-pressure-native")
    store, project = imported_project(directory)
    run = store.create_run(project["id"], {"operation": "optimize", "mission": pressure_scenario(), "budget_seconds": 90})
    route_project_run(store, run, WorkerControl(store, run["id"]))
    candidate, = store.candidates(project["id"])
    assert candidate["status"] == "CHECKED", store.get(candidate["report_root"])
    store.accept(project["id"], candidate["id"], 1, "native-validation-pressure", checker_version=checker_version())
    exported = export_project(store, project["id"], candidate["id"], draft=False, budget_seconds=90)
    assert exported["status"] == "CHECKED_LOCAL_SCOPE" and exported["round_trip"] == "PASS"
    manifest = store.get(exported["artifact_root"])
    fresh, = [c for c in store.candidates(project["id"]) if c.get("report_root") == manifest["verification_root"]]
    return {"store": store, "candidate": fresh, "export_sha256": manifest["files"][0]["sha256"]}


def invoke_new_source(tmp_path, case, *, expected_sha=None):
    script = _script()
    environment = frozen_environment(tmp_path / "frozen-current")
    changed_source = tmp_path / "next-source"
    shutil.copytree(environment["PYTHONPATH"], changed_source)
    (changed_source / "oma/validation_revision_fixture.py").write_text(
        '"""An independently identified subsequent validation-only source."""\n', encoding="utf-8")
    environment.update(PYTHONPATH=str(changed_source), PYTHONDONTWRITEBYTECODE="1")
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    output = tmp_path / "output" / "isolated"
    previous = case["store"].get(case["candidate"]["report_root"])
    # The implicit .oma is deliberately absent, so passing this actual network
    # through the CLI requires the explicit original Store argument.
    program = (
        "import sys,os; from pathlib import Path; "
        f"sys.path.insert(0,{str(scripts)!r}); import native_real_model_validation as v; "
        "from oma.build_identity import checker_version; version=checker_version(); "
        "os.environ['OMA_EXECUTABLE_BUILD']=version; "
        f"v.ROOT=Path({str(tmp_path / 'no-default-workspace')!r}); v.DEST=Path({str(output.parent)!r}); "
        f"sys.argv=['native_real_model_validation.py','--child-directory',{str(output)!r},"
        f"'--candidate-id',{case['candidate']['id']!r},'--original-store',{str(case['store'].directory)!r},"
        f"'--expected-export-sha256',{(expected_sha or case['export_sha256'])!r},"
        f"'--prior-checker-version',{previous['checker_version']!r},'--source-checkpoint',version.rsplit(':',1)[-1]]; v.main()")
    completed = subprocess.run([sys.executable, "-c", program], env=environment, capture_output=True, text=True, timeout=90)
    return script, completed, output


def test_explicit_read_only_store_rechecks_exported_pressure_network_under_new_source(tmp_path, exported_pressure_network):
    case = exported_pressure_network
    original = ReadOnly(case["store"].directory)
    candidate = original.candidate(case["candidate"]["id"])
    original_head = original.project(candidate["project_id"])
    original_run = original.run(candidate["run_id"])
    script, completed, output = invoke_new_source(tmp_path, case)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    result = json.loads((output / "real-model-result.json").read_text())
    assert result["status"] == "REAL_EXPORTED_OFFICE_RECHECK_PASS"
    assert result["physical_kind"] == "physical_network"
    assert result["original_store"] == str(original.directory)
    assert result["candidate_root"] == candidate["state_root"] and result["prior_report_root"] == candidate["report_root"]
    assert result["checker_version"] != result["prior_checker_version"]
    assert result["execution"]["status"] == "COMPLETED" and result["execution"]["report_published"]
    native = result["network_evidence"]
    assert native["physical_components"] == 4 and native["physical_ports"] == 9
    assert native["source_pairs"] == 4 and native["original_obstacles"] == 1 and native["component_pairs"] == 6
    assert native["component_velocity_count"] == 9 and len(native["deliveries"]) == 2
    assert native["operating_point_status"] == native["service_status"] == native["complete_native_status"] == "PASS"
    assert native["pressure_model_root"] != result["prior_network_evidence"]["pressure_model_root"]
    assert native["deliveries"] == result["prior_network_evidence"]["deliveries"]
    assert original.candidate(candidate["id"]) == candidate
    assert original.project(candidate["project_id"]) == original_head and original.run(candidate["run_id"]) == original_run
    copied = json.loads((output / "validation-input-copy.json").read_text())
    assert all(script.sha(Path(a["original_resolved_path"])) == a["sha256"]
        and script.sha(output / a["copied_path"]) == a["sha256"] for a in copied["assets"])


def test_wrong_declared_network_export_bytes_stop_before_fresh_child(tmp_path, exported_pressure_network):
    case = exported_pressure_network
    before = case["store"].candidate(case["candidate"]["id"])
    script, completed, output = invoke_new_source(tmp_path, case, expected_sha="0" * 64)
    assert completed.returncode != 0
    assert "AssertionError" in completed.stderr
    assert not (output / "checks/candidate-executions").exists()
    assert not (output / "real-model-result.json").exists()
    assert case["store"].candidate(before["id"]) == before


def test_network_evidence_rejects_vacuous_native_or_pressure_denominators(tmp_path, exported_pressure_network):
    import copy
    case = exported_pressure_network
    store = case["store"]
    state = store.get(case["candidate"]["state_root"])
    report = store.get(case["candidate"]["report_root"])
    rows = {r["id"]: r for r in report["results"]}
    semantic_root = rows["network-native-semantics"]["witness"]["artifact"]
    cad_root = rows["network-all-source-clearance"]["witness"]["artifact"]
    pressure_root = rows["network-pressure-operating-point"]["witness"]["artifact"]
    script = _script()
    for fault in ("missing_part", "missing_sink", "missing_velocity", "repeated_pair", "repeated_route_guid", "repeated_component"):
        current_state = copy.deepcopy(state)
        if fault == "repeated_component":
            current_state["physical_networks"][0]["component_ids"].append(current_state["physical_networks"][0]["component_ids"][0])
        class Narrowed:
            def get(self, root):
                value = copy.deepcopy(store.get(root))
                if fault == "missing_part" and root == semantic_root:
                    value["parts"].pop()
                if fault == "missing_sink" and root == pressure_root:
                    value["deliveries"].pop(next(iter(value["deliveries"])))
                if fault == "missing_velocity" and root == pressure_root:
                    value["component_velocities"].pop(next(iter(value["component_velocities"])))
                if fault == "repeated_pair" and root == cad_root:
                    value["self_pair_results"] = [value["self_pair_results"][0]] * len(value["self_pair_results"])
                if fault == "repeated_route_guid" and root == cad_root:
                    value["route_guids"].append(value["route_guids"][0])
                return value
        with pytest.raises(AssertionError):
            script.network_validation_evidence(Narrowed(), current_state, report, tmp_path, fault)
