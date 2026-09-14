"""Actual process-boundary faults cannot publish a candidate's deferred PASS."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

import psutil
import pytest

from oma.export_checks import supervise_check
from oma.routing import check_execution as execution
from oma.store import IntegrityError, Store


def _candidate(tmp_path):
    store = Store(tmp_path / "store")
    project = store.create_project("Process admission fixture", {"mission": {"rule_hash": "fixed-test-rules"}})
    run = store.create_run(project["id"], {"operation": "route", "budget_seconds": 10})
    candidate = store.add_candidate(run["id"], store.get(project["state_root"]), {"kind": "process_fixture"})
    return store, project, run, candidate


def _receipt_program(store, request_path):
    # Only the report-producing body is a synthetic fixture. The real child,
    # deferred Store, private receipt, supervisor, token admission and accept
    # boundary are production code. Native complete IFC fixtures follow below.
    return (
        "from oma.routing.check_execution import DeferredVerificationStore; "
        "from oma.store import utcnow; "
        f"s=DeferredVerificationStore({str(store.directory)!r},{str(request_path)!r}); r=s.request; "
        "s.record_verification(r['candidate_id'],dict(schema_version=1,candidate_root=r['candidate_root'],"
        "mission_hash=r['mission_hash'],rule_hash=r['rule_hash'],checker_version=r['checker_version'],"
        "status='PASS',scope='Synthetic process-admission fixture only',objective={},created_at=utcnow(),"
        "results=[dict(id='process-fixture',status='PASS',reason='Fixture report',scope='Test only')]))"
    )


def _fake_command(monkeypatch, *, after="", produce=True):
    def command(store, request_path):
        code = _receipt_program(store, request_path) if produce else "pass"
        return [sys.executable, "-c", code + "; " + (after or "pass")]
    monkeypatch.setattr(execution, "_command", command)


@pytest.mark.parametrize("after,timeout,expected", [
    ("pass", 10, "COMPLETED"),
    ("import sys; sys.exit(17)", 10, "FAILED"),
    ("import time; time.sleep(3)", 1.5, "UNKNOWN_TIMEOUT"),
])
def test_private_pass_requires_successful_process_completion(tmp_path, monkeypatch, after, timeout, expected):
    store, project, run, candidate = _candidate(tmp_path)
    _fake_command(monkeypatch, after=after)
    result = execution.run_candidate_check(store, candidate["id"], deadline=time.monotonic()+timeout, reserve_bytes=0)
    assert result["status"] == expected, result
    checked = store.candidate(candidate["id"])
    assert result["observed_receipt"]["report_status"] == "PASS"
    assert result["observed_receipt"]["publication_authority"] == "NONE_CHILD_RECEIPT_ONLY"
    assert result["report_published"] == (expected == "COMPLETED")
    if expected == "COMPLETED":
        assert checked["status"] == "CHECKED"
        accepted = store.accept(project["id"], candidate["id"], 0, "accept-complete",
            checker_version=result["observed_receipt"]["checker_version"])
        assert accepted["revision"] == 1
    else:
        assert checked["status"] == "UNKNOWN" and checked["report_root"] is None
        with pytest.raises(IntegrityError):
            store.accept(project["id"], candidate["id"], 0, "reject-incomplete",
                checker_version=result["observed_receipt"]["checker_version"])
    retained = json.loads((Path(result["directory"])/"execution.json").read_text())
    assert retained["status"] == expected
    assert store.project(project["id"])["revision"] == int(expected == "COMPLETED")


@pytest.mark.parametrize("stop_action", ["cancel", "COMPLETED", "BUDGET_EXHAUSTED"])
def test_stopped_owner_after_private_pass_never_publishes_it(tmp_path, monkeypatch, stop_action):
    store, project, run, candidate = _candidate(tmp_path)
    _fake_command(monkeypatch, after="import time; time.sleep(4)")
    observation = {}
    stop = threading.Event()
    def cancel_after_receipt():
        while not stop.wait(.02):
            receipts = list((store.directory/"checks/candidate-executions").glob("*/receipt.json"))
            if receipts:
                observation["candidate_before_cancel"] = store.candidate(candidate["id"])
                try:
                    store.accept(project["id"], candidate["id"], 0, "accept-during-child",
                        checker_version=execution.checker_version())
                except IntegrityError:
                    observation["accept_rejected"] = True
                if stop_action == "cancel":
                    store.control(run["id"], "cancel")
                else:
                    store.update_run(run["id"], stop_action)
                return
    thread = threading.Thread(target=cancel_after_receipt, daemon=True)
    thread.start()
    try:
        result = execution.run_candidate_check(store, candidate["id"], deadline=time.monotonic()+8, reserve_bytes=0)
    finally:
        stop.set(); thread.join(2)
    assert result["status"] == "CANCELLED", result
    assert result["observed_receipt"]["report_status"] == "PASS"
    assert observation["accept_rejected"]
    assert observation["candidate_before_cancel"]["status"] == "CHECKING"
    assert not result["report_published"]
    assert store.candidate(candidate["id"])["status"] == "UNKNOWN"
    assert not result["supervision"]["termination"]["remaining_pids"]


@pytest.mark.parametrize("fault", ["missing", "wrong_execution", "wrong_mission", "wrong_report_root"])
def test_zero_exit_without_current_bound_receipt_is_unknown(tmp_path, monkeypatch, fault):
    store, _, _, candidate = _candidate(tmp_path)
    if fault == "missing":
        _fake_command(monkeypatch, produce=False)
    else:
        mutation = {"wrong_execution": "v['execution_id']='another-execution'",
            "wrong_mission": "v['report_root']=s.put({**s.get(v['report_root']),'mission_hash':'f'*64})",
            "wrong_report_root": "v['report_root']='f'*64"}[fault]
        _fake_command(monkeypatch, after=f"import json; p=s.receipt_path; v=json.loads(p.read_text()); {mutation}; p.write_text(json.dumps(v))")
    result = execution.run_candidate_check(store, candidate["id"], deadline=time.monotonic()+10, reserve_bytes=0)
    assert result["status"] == "UNKNOWN_EXECUTION_ERROR", result
    assert result["supervision"]["status"] == "COMPLETED"
    assert store.candidate(candidate["id"])["status"] == "UNKNOWN"
    assert not result["report_published"]


def test_supervised_nested_late_receipt_is_killed_and_never_authoritative(tmp_path, monkeypatch):
    store, _, _, candidate = _candidate(tmp_path)
    identity = tmp_path/"nested-identity.json"
    def command(store, request):
        code = "import time; time.sleep(3); " + _receipt_program(store, request)
        program = ("import subprocess,sys,time,json,psutil; "
            f"p=subprocess.Popen([sys.executable,'-c',{code!r}],creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)); "
            f"q=psutil.Process(p.pid); open({str(identity)!r},'w').write(json.dumps(dict(pid=q.pid,created=q.create_time()))); "
            "time.sleep(5)")
        return [sys.executable, "-c", program]
    monkeypatch.setattr(execution, "_command", command)
    result = execution.run_candidate_check(store, candidate["id"], deadline=time.monotonic()+1.5, reserve_bytes=0)
    assert result["status"] == "UNKNOWN_TIMEOUT", result
    assert not result["report_published"] and store.candidate(candidate["id"])["status"] == "UNKNOWN"
    assert not result["supervision"]["termination"]["remaining_pids"]
    native = json.loads(identity.read_text())
    try:
        p = psutil.Process(native["pid"])
        assert p.create_time() != native["created"] or not p.is_running()
    except psutil.NoSuchProcess:
        pass
    assert not (Path(result["directory"])/"receipt.json").exists()


def test_resource_limit_cannot_infer_a_geometry_failure(tmp_path, monkeypatch):
    store, _, _, candidate = _candidate(tmp_path)
    _fake_command(monkeypatch, after="import time; time.sleep(3)")
    result = execution.run_candidate_check(store, candidate["id"], deadline=time.monotonic()+5,
        memory_limit_bytes=1024*1024, reserve_bytes=0)
    assert result["status"] == "UNKNOWN_RESOURCE_LIMIT", result
    assert not result["report_published"]
    assert store.candidate(candidate["id"])["status"] == "UNKNOWN"


@pytest.mark.parametrize("bad_deadline", [True, float("inf"), float("nan")])
def test_invalid_deadline_does_not_launch_or_change_candidate(tmp_path, bad_deadline):
    store, _, _, candidate = _candidate(tmp_path)
    with pytest.raises(ValueError):
        execution.run_candidate_check(store, candidate["id"], deadline=bad_deadline)
    assert store.candidate(candidate["id"]) == candidate


@pytest.mark.parametrize("crossing,status", [(False,"PASS"),(True,"FAIL")])
def test_actual_native_joint_report_survives_deferred_dispatch(tmp_path, crossing, status):
    from test_joint_negative_hint_adversarial import _native_candidate
    case = _native_candidate(tmp_path/"native", crossing=crossing)
    result = execution.run_candidate_check(case["store"], case["candidate"]["id"],
        deadline=time.monotonic()+45, reserve_bytes=0)
    assert result["status"] == "COMPLETED", result
    assert result["report_published"] and result["report_status"] == status
    report = case["store"].get(result["report_root"])
    assert report["status"] == status
    assert next(r["status"] for r in report["results"] if r["id"] == "cross-route-interference") == status


def test_cancellation_callback_before_launch_and_control_failure_are_closed(tmp_path):
    marker = tmp_path/"must-not-launch"
    command = [sys.executable,"-c",f"open({str(marker)!r},'w').write('launched')"]
    for name, callback, expected in (("cancel",lambda: True,"CANCELLED"),
            ("control-error",lambda: (_ for _ in ()).throw(RuntimeError("control unavailable")),"UNKNOWN_CONTROL_ERROR")):
        result = supervise_check(command, environment={**os.environ,"OMA_EXECUTABLE_BUILD":"control-test"},
            directory=tmp_path/name, deadline=time.monotonic()+5, reserve_bytes=0, cancellation_requested=callback)
        assert result["status"] == expected
        assert "pid" not in result and not marker.exists()


def test_control_poll_failure_after_launch_terminates_owned_process(tmp_path):
    marker = tmp_path/"started"
    def control():
        if marker.exists():
            raise RuntimeError("Control state became unavailable")
        return False
    result = supervise_check([sys.executable,"-c",f"import time; open({str(marker)!r},'w').write('ready'); time.sleep(4)"],
        environment={**os.environ,"OMA_EXECUTABLE_BUILD":"control-fault"}, directory=tmp_path/"check",
        deadline=time.monotonic()+8, reserve_bytes=0, cancellation_requested=control)
    assert result["status"] == "UNKNOWN_PROCESS_ERROR", result
    assert "Control state became unavailable" in result["reason"]
    assert not result["termination"]["remaining_pids"]


def test_separate_historical_recheck_retains_original_mission_and_native_report(tmp_path):
    from test_joint_negative_hint_adversarial import _native_candidate
    case = _native_candidate(tmp_path/"native", crossing=False)
    store, candidate = case["store"], case["candidate"]
    first = execution.run_candidate_check(store, candidate["id"], deadline=time.monotonic()+45,
        control_run_id=candidate["run_id"], reserve_bytes=0)
    assert first["status"] == "COMPLETED" and first["report_status"] == "PASS", first
    store.update_run(candidate["run_id"], "COMPLETED")
    prior_mission = store.get(candidate["state_root"])["mission"]
    run = store.create_run(candidate["project_id"], {"operation":"recheck","candidate_id":candidate["id"],"budget_seconds":45})
    checked = execution.run_candidate_check(store, candidate["id"], deadline=time.monotonic()+45,
        control_run_id=run["id"], reserve_bytes=0)
    assert checked["status"] == "COMPLETED" and checked["report_status"] == "PASS", checked
    assert checked["execution_id"] != first["execution_id"]
    assert checked["report_root"] != first["report_root"]
    request = json.loads((Path(checked["directory"])/"request.json").read_text())
    assert request["binding"]["prior_report_root"] == first["report_root"]
    assert request["binding"]["control_run_id"] == run["id"]
    assert store.get(candidate["state_root"])["mission"] == prior_mission
