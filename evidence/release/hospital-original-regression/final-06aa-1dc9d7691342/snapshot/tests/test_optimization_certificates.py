import pytest
from oma.optimization.certificates import classify_core_minimality, verify_farkas


def test_noncertified_deletion_does_not_prove_minimal_core():
    verdicts = {"x>=1": "FEASIBLE_CHECKED", "x<=0": "FEASIBLE_CHECKED", "y>=0": "UNKNOWN"}
    assert classify_core_minimality(tuple(verdicts), verdicts, core_infeasibility_checked=True) == "MINIMALITY_UNKNOWN"
    assert classify_core_minimality(tuple(verdicts), verdicts | {"y>=0": "INFEASIBLE_CHECKED"}, core_infeasibility_checked=True) == "NONMINIMAL_CHECKED"
    minimal = {"x>=1": "FEASIBLE_CHECKED", "x<=0": "FEASIBLE_CHECKED"}
    assert classify_core_minimality(tuple(minimal), minimal, core_infeasibility_checked=True) == "INCLUSION_MINIMAL_CHECKED"
    assert classify_core_minimality(tuple(minimal), minimal, core_infeasibility_checked=False) == "CORE_INFEASIBILITY_UNVERIFIED"


def test_farkas_exact_replay_and_missing_bypass_counterexample():
    # x>=1 and -x>=0 is infeasible.
    assert verify_farkas(((1,), (-1,)), (1, 0), (1, 1))["verdict"] == "PASS"
    # A new bypass column changes the actual finite model and invalidates ray.
    assert verify_farkas(((1, 1), (-1, 0)), (1, 0), (1, 1))["verdict"] == "FAIL"
    assert verify_farkas(((1,), (-1,)), (1, 0), (0, 0))["verdict"] == "FAIL"
    assert verify_farkas(((1,), (-1,)), (1, 0), (-1, 1))["verdict"] == "FAIL"
    with pytest.raises(ValueError):
        verify_farkas(((1,), (-1, 0)), (1, 0), (1, 1))
