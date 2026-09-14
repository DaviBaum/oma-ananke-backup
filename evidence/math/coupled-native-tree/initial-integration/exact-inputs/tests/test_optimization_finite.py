from copy import deepcopy
from fractions import Fraction as Q
import pytest

from oma.optimization.finite import (contextual_quotient, verify_contextual_quotient,
    FiniteOutcome, finite_archive_optimum, finite_chance_constraint, finite_risk,
    check_nonanticipativity, check_quantity_transport)


def test_contextual_quotient_and_experiment_refinement_with_separation_witnesses():
    table = {"a":{"length":10,"fire":"A"}, "b":{"length":10,"fire":"B"}, "c":{"length":11,"fire":"A"}}
    coarse = contextual_quotient({s:{"length":v["length"]} for s,v in table.items()}, ["length"], context_root="E1")
    assert coarse["blocks"] == [("a","b"),("c",)]
    fine = contextual_quotient(table,["length","fire"],context_root="E2")
    assert fine["blocks"] == [("a",),("b",),("c",)]
    assert verify_contextual_quotient(table,["length","fire"],fine,context_root="E2")["status"] == "PASS"
    bad = deepcopy(fine)
    bad["blocks"] = [("a","b"),("c",)]
    assert verify_contextual_quotient(table,["length","fire"],bad,context_root="E2")["status"] == "FAIL"
    assert verify_contextual_quotient(table,["length","fire"],fine,context_root="E3")["status"] == "FAIL"


def test_quotient_preserves_typed_observations_and_requires_complete_experiments():
    result = contextual_quotient({"a":{"x":1},"b":{"x":True}},["x"],context_root="typed")
    assert len(result["blocks"]) == 2
    with pytest.raises(ValueError,match="Every declared"):
        contextual_quotient({"a":{}},["x"],context_root="typed")


def test_unknown_cheaper_feasible_candidate_blocks_finite_optimum_a007():
    expensive = FiniteOutcome("expensive","PASS",10,evidence_root="checked-expensive")
    cheap = FiniteOutcome("cheap","UNKNOWN",1)
    result = finite_archive_optimum([expensive,cheap],context_root="finite",universe_complete=True)
    assert result["status"] == "FINITE_ARCHIVE_FEASIBLE" and result["lower_bound"] == "1"
    nonimproving = FiniteOutcome("unresolved-expensive","UNKNOWN",lower_bound=11)
    result = finite_archive_optimum([expensive,nonimproving],context_root="finite",universe_complete=True)
    assert result["status"] == "FINITE_ARCHIVE_OPTIMAL" and result["unresolved"]
    result = finite_archive_optimum([expensive],context_root="finite",universe_complete=False)
    assert result["status"] == "FINITE_ARCHIVE_FEASIBLE" and result["lower_bound"] is None
    assert finite_archive_optimum([FiniteOutcome("x","FAIL",evidence_root="refutation")],context_root="finite",universe_complete=True)["status"] == "FINITE_ARCHIVE_INFEASIBLE"


def test_exact_tail_risk_and_unknown_chance_bounds():
    risk = finite_risk([Q(99,100),Q(1,100)],[0,1000],alpha=Q(95,100))
    assert risk["expectation"] == "10" and risk["cvar"] == "200" and risk["worst_listed_loss"] == "1000"
    assert finite_risk([Q(1,2)]*2,[-10,10],alpha=0)["cvar"] == "0"
    assert finite_chance_constraint([Q(9,10),Q(1,10)],["FALSE","UNKNOWN"],Q(5,100))["status"] == "UNKNOWN"
    assert finite_chance_constraint([Q(9,10),Q(1,10)],["FALSE","UNKNOWN"],Q(1,10))["status"] == "PASS"
    assert finite_chance_constraint([Q(9,10),Q(1,10)],["FALSE","TRUE"],Q(5,100))["status"] == "FAIL"
    with pytest.raises(ValueError,match="sum exactly"):
        finite_risk([Q(1,3)]*2,[1,2])


def test_history_nonanticipativity_catches_clairvoyant_initial_decision():
    histories = {"hot":("unknown-weather","hot"),"cold":("unknown-weather","cold")}
    bad = {"hot":("install-cooling","cool"),"cold":("install-heating","heat")}
    result = check_nonanticipativity(histories,bad,context_root="SOV")
    assert result["status"] == "FAIL" and result["stage"] == 0
    good = {"hot":("install-flexible","cool"),"cold":("install-flexible","heat")}
    assert check_nonanticipativity(histories,good,context_root="SOV")["status"] == "PASS"


def test_split_merge_conserves_every_named_quantity_and_rejects_unit_alias():
    result = check_quantity_transport({"trunk":10},{"a":4,"b":6},[("trunk","a",4),("trunk","b",6)],source_unit="m3/s",target_unit="m3/s",context_root="split")
    assert result["status"] == "PASS" and result["certificate_reuse"] == "NOT_ESTABLISHED"
    merged = check_quantity_transport({"a":4,"b":6},{"trunk":10},[("a","trunk",4),("b","trunk",6)],source_unit="m3/s",target_unit="m3/s",context_root="merge")
    assert merged["status"] == "PASS"
    bad = check_quantity_transport({"trunk":10},{"a":4,"b":7},[("trunk","a",4),("trunk","b",6)],source_unit="m3/s",target_unit="m3/s",context_root="bad")
    assert bad["status"] == "FAIL" and bad["residuals"]["target"] == {"b":"-1"}
    assert check_quantity_transport({"a":1},{"b":1},[("a","b",1)],source_unit="m3/s",target_unit="L/s",context_root="units")["status"] == "FAIL"
