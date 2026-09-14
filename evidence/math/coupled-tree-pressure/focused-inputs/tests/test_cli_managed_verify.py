"""CLI rechecks use a fresh managed owner without changing a historical mission."""
import json
from pathlib import Path
import sys
import time

import pytest
from typer.testing import CliRunner

from oma.cli import app, verify
from oma.routing import check_execution
from oma.store import IntegrityError
from test_joint_negative_hint_adversarial import _native_candidate


@pytest.fixture(scope="module")
def managed_native_cases(tmp_path_factory):
    directory = tmp_path_factory.mktemp("cli-managed-native")
    cases = {}
    for name,crossing in (("separated",False),("crossing",True),("timeout",False),("setup-error",False)):
        case = _native_candidate(directory/name,crossing=crossing)
        initial = check_execution.run_candidate_check(case["store"],case["candidate"]["id"],
            deadline=time.monotonic()+45,reserve_bytes=0)
        assert initial["status"] == "COMPLETED" and initial["report_published"],initial
        assert initial["report_status"] == ("FAIL" if crossing else "PASS")
        case["initial_execution"] = initial
        case["original_run"] = case["store"].update_run(case["run"]["id"],"COMPLETED","Original fixture run is historical")
        case["original_project"] = case["store"].project(case["candidate"]["project_id"])
        case["original_state"] = case["store"].get(case["candidate"]["state_root"])
        cases[name] = case
    return cases


def invoke(case,budget=45):
    result = CliRunner().invoke(app,["verify",case["candidate"]["id"],"--data-dir",str(case["store"].directory),
        "--budget-seconds",str(budget)])
    assert result.output.strip().startswith("{"), (result.output,result.exception)
    return result,json.loads(result.output)


def unchanged_original(case):
    store = case["store"]
    assert store.run(case["run"]["id"]) == case["original_run"]
    assert store.project(case["candidate"]["project_id"]) == case["original_project"]
    assert store.get(case["candidate"]["state_root"]) == case["original_state"]


def execution_row(case,result):
    with case["store"].connect() as db:
        return dict(db.execute("SELECT * FROM check_executions WHERE execution_id=?",(result["execution_id"],)).fetchone())


@pytest.mark.parametrize("name,report_status",[("separated","PASS"),("crossing","FAIL")])
def test_cli_managed_historical_native_recheck_publishes_its_fresh_report(managed_native_cases,name,report_status):
    case = managed_native_cases[name]
    result,value = invoke(case)
    assert result.exit_code == 0,(value,result.exception)
    assert value["execution_status"] == "COMPLETED" and value["report_published"]
    assert value["report_status"] == report_status and not value["acceptance_performed"]
    assert value["execution_id"] != case["initial_execution"]["execution_id"]
    assert value["run"]["id"] != case["run"]["id"]
    assert value["run"]["operation"] == "recheck" and value["run"]["status"] == "COMPLETED"
    assert value["run"]["request"] == {"operation":"recheck","candidate_id":case["candidate"]["id"],"budget_seconds":45.}
    checked = case["store"].candidate(case["candidate"]["id"])
    assert checked["report_root"] == value["report_root"]
    report = case["store"].get(value["report_root"])
    assert report["status"] == report_status and report["candidate_root"] == case["candidate"]["state_root"]
    row = execution_row(case,value)
    assert row["status"] == "COMPLETED" and row["report_root"] == value["report_root"]
    binding = json.loads(row["binding"])
    assert binding["control_run_id"] == value["run"]["id"]
    assert binding["origin_run_id"] == case["run"]["id"]
    assert binding["control_request_root"] != binding["request_root"]
    assert next(r for r in report["results"] if r["id"]=="cross-route-interference")["status"] == report_status
    unchanged_original(case)


def test_cli_actual_private_native_pass_followed_by_timeout_has_no_public_report(managed_native_cases,monkeypatch):
    case = managed_native_cases["timeout"]
    def command(store,request):
        program = ("from oma.routing.check_execution import _child; import time; "
            f"_child({str(store.directory)!r},{str(request)!r}); time.sleep(30)")
        return [sys.executable,"-c",program]
    monkeypatch.setattr(check_execution,"_command",command)
    result,value = invoke(case,budget=4)
    assert result.exit_code == 2,(value,result.exception)
    assert value["execution_status"] == "UNKNOWN_TIMEOUT"
    assert value["run"]["status"] == "TIMED_OUT"
    assert not value["report_published"] and value["report_status"] is None and value["report_root"] is None
    assert not value["acceptance_performed"]
    execution = json.loads((case["store"].directory/"checks/candidate-executions"/value["execution_id"]/"execution.json").read_text())
    assert execution["observed_receipt"]["report_status"] == "PASS"
    assert execution["supervision"]["termination"]["active_processes_after"] == 0
    assert execution_row(case,value)["status"] == "UNKNOWN_TIMEOUT"
    candidate = case["store"].candidate(case["candidate"]["id"])
    assert candidate["status"] == "UNKNOWN" and candidate["report_root"] is None
    with pytest.raises(IntegrityError):
        case["store"].accept(candidate["project_id"],candidate["id"],case["original_project"]["revision"],
            "cannot-accept-cli-timeout",checker_version=check_execution.checker_version())
    unchanged_original(case)


def test_cli_setup_error_does_not_mislabel_a_retained_old_report_as_current(managed_native_cases,monkeypatch):
    case = managed_native_cases["setup-error"]
    before = case["store"].candidate(case["candidate"]["id"])
    def fail(*args,**kwargs):
        raise OSError("Explicit fixture: snapshot unavailable before launch")
    monkeypatch.setattr(check_execution,"run_candidate_check",fail)
    result,value = invoke(case)
    assert result.exit_code == 2 and value["execution_status"] == "UNKNOWN_EXECUTION_ERROR"
    assert value["run"]["status"] == "FAILED" and "snapshot unavailable" in value["reason"]
    assert not value["report_published"] and value["report_status"] is None and value["report_root"] is None
    assert value["execution_id"] is None and not value["acceptance_performed"]
    assert case["store"].candidate(case["candidate"]["id"]) == before
    unchanged_original(case)


@pytest.mark.parametrize("budget",["nan","inf","-inf","0","-1","3601"])
def test_cli_invalid_budget_is_rejected_before_creating_a_store(tmp_path,budget):
    directory = tmp_path/"must-not-create"
    result = CliRunner().invoke(app,["verify","not-a-candidate","--data-dir",str(directory),"--budget-seconds",budget])
    assert result.exit_code == 2 and "budget" in result.output
    assert not directory.exists()


def test_direct_cli_entry_rejects_boolean_budget_before_storage(tmp_path):
    import typer
    directory = tmp_path/"must-not-create"
    with pytest.raises(typer.BadParameter):
        verify("not-a-candidate",data_dir=directory,budget_seconds=True)
    assert not directory.exists()
