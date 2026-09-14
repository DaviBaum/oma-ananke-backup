"""A semantic directrix subtotal cannot impersonate a native checked objective."""
import time
from unittest.mock import patch

import ifcopenshell
import pytest

from oma.ifc.audit import atomic_json
from oma.routing.check_execution import run_candidate_check
import test_joint_negative_hint_adversarial as fixtures


def native_objective_case(directory, *, source_clash):
    original = fixtures.make_fixture
    def source_with_actual_collision(path,*args,**kwargs):
        path = original(path,*args,**kwargs)
        model = ifcopenshell.open(str(path))
        # Author the original analytic obstacle here, before import/hash binding.
        # The two new parallel routes are y=4 and y=4.25, inside this solid.
        model.by_type("IfcBuildingElementProxy")[0].ObjectPlacement.RelativePlacement.Location.Coordinates = (0.,3.,0.)
        model.write(str(path))
        return path
    if source_clash:
        with patch.object(fixtures,"make_fixture",source_with_actual_collision):
            case = fixtures._native_candidate(directory,crossing=False)
    else:
        # Both source/objective checks run, but the two routes intersect each
        # other. A global FAIL need not discard an independently checked cost.
        case = fixtures._native_candidate(directory,crossing=True)
    execution = run_candidate_check(case["store"],case["candidate"]["id"],
        deadline=time.monotonic()+45,reserve_bytes=0)
    assert execution["status"] == "COMPLETED" and execution["report_published"],execution
    report = case["store"].get(execution["report_root"])
    assert report["status"] == "FAIL"
    atomic_json(directory/"managed-objective-report.json",report)
    case.update(execution=execution,report=report)
    return case


def test_native_source_counterexample_leaves_unperformed_aggregate_objective_empty(tmp_path):
    case = native_objective_case(tmp_path/"source-clash",source_clash=True)
    report = case["report"]
    by_id = {r["id"]:r for r in report["results"]}
    for route in case["state"]["routes"]:
        rid = route["id"]
        assert by_id[rid+":exported-physical-semantics"]["status"] == "PASS"
        assert by_id[rid+":native-forbidden-volume-counterexample"]["status"] == "FAIL"
        assert by_id[rid+":independent-objective-recomputation"]["status"] == "NOT_RUN"
    assert by_id["joint-objective"]["status"] == "NOT_RUN"
    assert report["objective"] == {}
    assert case["store"].candidate(case["candidate"]["id"])["status"] == "REJECTED"


def test_global_collision_failure_can_retain_a_genuinely_checked_complete_objective(tmp_path):
    case = native_objective_case(tmp_path/"cross-route-clash",source_clash=False)
    report = case["report"]
    by_id = {r["id"]:r for r in report["results"]}
    for route in case["state"]["routes"]:
        assert by_id[route["id"]+":independent-objective-recomputation"]["status"] == "PASS"
    assert by_id["cross-route-interference"]["status"] == "FAIL"
    assert by_id["joint-objective"]["status"] == "PASS"
    assert report["objective"] == {"length_m":6.,"fitting_count":0.}


def checked_authority():
    from oma.models import CheckResult
    return [CheckResult(id=identity,status="PASS",reason="Fresh invocation fixture",scope="Aggregation seam only")
        for identity in ("exported-physical-semantics","independent-objective-recomputation")]


@pytest.mark.parametrize("value",[float("nan"),float("inf"),-float("inf"),-1.,True,10**1000])
@pytest.mark.parametrize("field",["length_m","fitting_count"])
def test_objective_aggregation_rejects_invalid_or_overflowing_fields_without_conversion_error(field,value):
    from oma.routing.joint_checker import _aggregate_objective
    objective = {"length_m":1.,"fitting_count":0.}
    objective[field] = value
    total,witness,complete = _aggregate_objective(["r"],{"r":checked_authority()},{"r":objective})
    assert not complete and total == {} and witness["per_route"] == {}


def test_individually_finite_lengths_cannot_authorize_an_infinite_sum():
    from oma.routing.joint_checker import _aggregate_objective
    total,witness,complete = _aggregate_objective(["a","b"],{r:checked_authority() for r in ("a","b")},
        {r:{"length_m":1.7e308,"fitting_count":0.} for r in ("a","b")})
    assert not complete and total == {} and not witness["finite_complete_aggregate"]


def test_zero_objective_values_are_valid_at_aggregation_seam_without_asserting_a_zero_route_mission():
    from oma.routing.joint_checker import _aggregate_objective
    total,witness,complete = _aggregate_objective(["r"],{"r":checked_authority()},
        {"r":{"length_m":0.,"fitting_count":0.}})
    assert complete and total == {"length_m":0.,"fitting_count":0.} and witness["finite_complete_aggregate"]


@pytest.mark.parametrize("kind",["missing","not_run","fail","duplicate","phantom","fractional_count"])
def test_complete_exact_route_and_authority_denominators_are_required(kind):
    from oma.routing.joint_checker import _aggregate_objective
    from oma.models import Verdict
    checks = checked_authority()
    objectives = {"r":{"length_m":1.,"fitting_count":0.}}
    if kind == "missing":
        checks.pop()
    elif kind in {"not_run","fail"}:
        checks[-1] = checks[-1].model_copy(update={"status":Verdict(kind.upper())})
    elif kind == "duplicate":
        checks.append(checks[-1])
    elif kind == "phantom":
        objectives["extra"] = {"length_m":1.,"fitting_count":0.}
    else:
        objectives["r"]["fitting_count"] = .5
    total,witness,complete = _aggregate_objective(["r"],{"r":checks},objectives)
    assert not complete and total == {} and witness["per_route"] == {}
