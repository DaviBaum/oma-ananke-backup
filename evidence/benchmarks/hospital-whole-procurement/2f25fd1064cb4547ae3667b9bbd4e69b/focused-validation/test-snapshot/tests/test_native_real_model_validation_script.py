"""The native validation script's copied store works across a real child boundary."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import time

import pytest

from oma.build_identity import frozen_environment
from oma.routing import check_execution
from oma.store import Store
from test_joint_negative_hint_adversarial import _native_candidate


def _script():
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    sys.path.insert(0, str(scripts))
    try:
        spec = importlib.util.spec_from_file_location("native_real_validation_test", scripts / "native_real_model_validation.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(scripts))


class ReadOnly(Store):
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.database = self.directory / "oma.sqlite3"
        self.blobs = self.directory / "blobs"

    def connect(self):
        from oma.store import _Connection
        db = sqlite3.connect(self.database.as_uri() + "?mode=ro", uri=True, factory=_Connection)
        db.row_factory = sqlite3.Row
        return db

    def put(self, value):
        raise AssertionError("Original store cannot be a validation output")


@pytest.fixture(scope="module")
def managed_original(tmp_path_factory):
    directory = tmp_path_factory.mktemp("native-validation-script") / "original"
    case = _native_candidate(directory, crossing=False)
    result = check_execution.run_candidate_check(case["store"], case["candidate"]["id"],
                                                deadline=time.monotonic() + 45, reserve_bytes=0)
    assert result["status"] == "COMPLETED" and result["report_status"] == "PASS", result
    case["store"].update_run(case["run"]["id"], "COMPLETED")
    case["candidate"] = result["candidate"]
    unrelated = case["store"].create_project("Do not copy unrelated assets", {"unrelated": "other-project"})
    case["unrelated_root"] = unrelated["state_root"]
    case["directory"] = directory
    return case


def test_managed_joint_candidate_rechecks_from_copied_inputs_with_original_unavailable(tmp_path, managed_original):
    script = _script()
    original = ReadOnly(managed_original["store"].directory)
    before_candidate = original.candidate(managed_original["candidate"]["id"])
    before_head = original.project(before_candidate["project_id"])
    isolated, copied = script.isolate_candidate(original, tmp_path / "isolated", before_candidate["id"])
    assert managed_original["unrelated_root"] not in copied["copied_artifact_roots"]
    assert not (isolated.blobs / (managed_original["unrelated_root"] + ".json.z")).exists()
    assert any(a["copied_path"].endswith(".manifest.json") for a in copied["assets"])
    parent = managed_original["directory"].resolve()
    hidden = parent.with_name("original-unavailable")
    assert parent.parent == hidden.parent and not hidden.exists()
    parent.rename(hidden)
    try:
        environment = frozen_environment(isolated.directory)
        result = script.managed_recheck(isolated, before_candidate["id"],
                                       deadline=time.monotonic() + 45, environment=environment)
        assert result["status"] == "COMPLETED" and result["report_published"], result
        assert result["report_status"] == "PASS"
        assert result["control_run_id"] != before_candidate["run_id"]
        assert result["candidate"]["state_root"] == before_candidate["state_root"]
        assert result["candidate"]["report_root"] != before_candidate["report_root"]
        before = isolated.get(before_candidate["report_root"])
        after = isolated.get(result["candidate"]["report_root"])
        assert after["objective"] == before["objective"]
        assert {r["id"]: r["status"] for r in after["results"]} == {r["id"]: r["status"] for r in before["results"]}
        assert all(script.sha(isolated.directory / a["copied_path"]) == a["sha256"] for a in copied["assets"])
    finally:
        hidden.rename(parent)
    assert original.candidate(before_candidate["id"]) == before_candidate
    assert original.project(before_candidate["project_id"]) == before_head
    assert all(script.sha(a["original_resolved_path"]) == a["sha256"] for a in copied["assets"])


def test_script_does_not_treat_private_native_pass_followed_by_failure_as_validation_success(tmp_path, monkeypatch, managed_original):
    script = _script()
    original = ReadOnly(managed_original["store"].directory)
    before = original.candidate(managed_original["candidate"]["id"])
    isolated, _ = script.isolate_candidate(original, tmp_path / "failed-execution", before["id"])
    def command(store, request):
        code = ("from oma.routing.check_execution import _child; "
                f"_child({str(store.directory)!r}, {str(request)!r}); "
                "raise SystemExit(17)")
        return [sys.executable, "-c", code]
    monkeypatch.setattr(check_execution, "_command", command)
    result = script.managed_recheck(isolated, before["id"], deadline=time.monotonic() + 45,
                                   environment=frozen_environment(isolated.directory))
    assert result["status"] == "FAILED" and not result["report_published"]
    assert result["observed_receipt"]["report_status"] == "PASS"
    assert isolated.candidate(before["id"])["status"] == "UNKNOWN"
    assert isolated.candidate(before["id"])["report_root"] is None
    assert isolated.run(result["control_run_id"])["status"] == "FAILED"
    assert original.candidate(before["id"]) == before
    assert isolated.get(before["report_root"])["status"] == "PASS"


def test_corrupt_original_artifact_prevents_copy_before_child_launch(tmp_path, managed_original):
    script = _script()
    class CorruptRead(ReadOnly):
        def get(self, root):
            if root == managed_original["candidate"]["state_root"]:
                raise RuntimeError("Injected immutable artifact hash mismatch")
            return super().get(root)
    with pytest.raises(RuntimeError, match="hash mismatch"):
        script.isolate_candidate(CorruptRead(managed_original["store"].directory),
                                 tmp_path / "corrupt-input", managed_original["candidate"]["id"])


def test_script_compares_genuine_prior_native_report_across_application_source_revisions(tmp_path, managed_original):
    script = _script()
    prior = managed_original["store"].candidate(managed_original["candidate"]["id"])
    prior_report = managed_original["store"].get(prior["report_root"])
    # Seed a fake workspace with only copied genuine native evidence. The
    # validation child sees a normal read-only .oma, never the live workspace.
    fake_root = tmp_path / "workspace"
    script.isolate_candidate(ReadOnly(managed_original["store"].directory), fake_root / ".oma", prior["id"])
    environment = frozen_environment(tmp_path / "source")
    changed_source = tmp_path / "next-source"
    shutil.copytree(environment["PYTHONPATH"], changed_source)
    (changed_source / "oma" / "validation_revision_fixture.py").write_text(
        '"""A subsequent application source checkpoint for runtime-validation testing."""\n', encoding="utf-8")
    environment["PYTHONPATH"] = str(changed_source)
    scripts = Path(__file__).resolve().parents[1] / "scripts"
    output = fake_root / ".release" / "actual-new-check"
    program = (
        "import sys,os; from pathlib import Path; "
        f"sys.path.insert(0,{str(scripts)!r}); "
        "import native_real_model_validation as v; from oma.build_identity import checker_version; "
        "version=checker_version(); os.environ['OMA_EXECUTABLE_BUILD']=version; "
        f"v.ROOT=Path({str(fake_root)!r}); v.DEST=v.ROOT/'.release'; "
        f"v.child({str(output)!r},{prior['id']!r},version.rsplit(':',1)[-1],"
        f"prior_checker_version={prior_report['checker_version']!r})")
    completed = subprocess.run([sys.executable, "-c", program], env=environment,
                               capture_output=True, text=True, timeout=45)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    result = json.loads((output / "real-model-result.json").read_text())
    assert result["status"] == "REAL_EXPORTED_OFFICE_RECHECK_PASS"
    assert result["prior_report_root"] == prior["report_root"]
    assert result["prior_checker_version"] == prior_report["checker_version"]
    assert result["checker_version"] != result["prior_checker_version"]
    assert result["source_checkpoint"] == result["checker_version"].rsplit(":", 1)[-1]
    assert result["report"]["objective"] == prior_report["objective"]
    assert result["execution"]["report_published"]
