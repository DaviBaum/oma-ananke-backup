"""Independent attacks on sparse-cap, terminal cost and completion boundaries."""
from copy import deepcopy
from fractions import Fraction as Q

import pytest

from oma.optimization import fabrication_pricing as pricing, fabrication_search as graph
from oma.store import canonical, digest
from test_optimization_fabrication_pricing import objective, reroot
from test_optimization_fabrication_search import problem


def test_zero_dual_lower_bound_alone_cannot_certify_an_uncharged_straight_terminal():
    p,o = problem(goal=[4,0,1]),objective("1","0")
    certificate = pricing.compile_fabrication_pricing(p,o)
    assert certificate["status"] == "CERTIFIED" and certificate["cost"] == ["4","0"]
    # All-zero potentials form a valid lower bound, including every omitted
    # state. The realizing path must still discharge its full terminal length.
    certificate.update(cost=["0","0"],default_potential=["0","0"],
        potentials=[row for row in certificate["potentials"] if row["state"][3] == -1])
    checked = pricing.verify_fabrication_pricing(p,o,reroot(certificate))
    assert checked["status"] == "FAIL"
    assert "realizing path" in checked["reason"]


def test_zero_optimum_needs_no_labels_beyond_explicit_source():
    p,o = problem(goal=[4,0,1]),objective("0","1")
    certificate = pricing.compile_fabrication_pricing(p,o)
    assert certificate["cost"] == ["0","0"] and len(certificate["potentials"]) > 1
    certificate["potentials"] = [row for row in certificate["potentials"] if row["state"][3] == -1]
    checked = pricing.verify_fabrication_pricing(p,o,reroot(certificate))
    assert checked["status"] == "PASS" and checked["explicit_potentials_checked"] == 1
    assert checked["pricing_outcome"] == "OPTIMAL_PATH"


@pytest.mark.parametrize("attack",["below_zero","above_cap"])
def test_mixed_sign_pi_labels_cannot_escape_exact_cap_comparisons(attack):
    p,o = problem(),objective()
    certificate = pricing.compile_fabrication_pricing(p,o)
    row = next(row for row in certificate["potentials"] if row["state"][3] >= 0)
    if attack == "below_zero":
        row["cost"] = ["333/106","-1"]  # 333/106 - pi < 0.
    else:
        a,b = map(Q,certificate["cost"])
        row["cost"] = [str(a+Q(355,113)),str(b-1)]  # C + 355/113 - pi > C.
    checked = pricing.verify_fabrication_pricing(p,o,reroot(certificate))
    assert checked["status"] == "FAIL" and "outside the default cap" in checked["reason"]


def test_untrusted_precision_and_work_metadata_cannot_suppress_checker_arithmetic():
    p,o = problem(),objective(fitting="97/452")
    certificate = pricing.compile_fabrication_pricing(p,o,max_pi_terms=64)
    assert certificate["status"] == "CERTIFIED" and certificate["pi_terms_used"] > 1
    certificate.update(producer_work=0,pi_terms_used=0)
    reroot(certificate)
    low = pricing.verify_fabrication_pricing(p,o,certificate,max_pi_terms=1)
    assert low["status"] == "UNKNOWN" and low["reason"] == "PI_COMPARISON_PRECISION_BUDGET"
    checked = pricing.verify_fabrication_pricing(p,o,certificate,max_pi_terms=64)
    assert checked["status"] == "PASS" and checked["pi_terms_used"] > 1 and checked["work"] > 0


@pytest.mark.parametrize("operation,stage",[
    ("producer","fabrication_pricing_complete"),
    ("checker","fabrication_pricing_verified"),
])
@pytest.mark.parametrize("error_type",[graph._Exhausted,TimeoutError,ValueError])
def test_final_completion_callback_cancellation_never_returns_a_certificate(operation,stage,error_type):
    p,o = problem(goal=[4,0,1]),objective()
    certificate = pricing.compile_fabrication_pricing(p,o)
    before = deepcopy(certificate)
    roots = digest(p),digest(o)
    error = error_type("caller deadline expired after final proof construction")
    reached = []
    def checkpoint(current):
        if current == stage:
            reached.append(current)
            raise error
    with pytest.raises(error_type) as caught:
        if operation == "producer":
            pricing.compile_fabrication_pricing(p,o,checkpoint=checkpoint)
        else:
            pricing.verify_fabrication_pricing(p,o,certificate,checkpoint=checkpoint)
    assert caught.value is error and reached == [stage]
    assert certificate == before and (digest(p),digest(o)) == roots


def test_streamed_certificate_digest_matches_store_canonical_unicode_and_byte_boundary(monkeypatch):
    payload = {"z":[{"route":"\u03c0/\U0001f6b0","quote":"\"\\\n\t", "zero":-0.0,
        "flags":[True,False,None], "value":i} for i in range(513)], "a":{"2":"1/7","1":"-3"}}
    expected = digest(payload)
    size = len(canonical(payload))
    monkeypatch.setattr(pricing,"MAX_CERTIFICATE_BYTES",size)
    stages = []
    assert pricing._certificate_digest(payload,graph._Work(500000,stages.append)) == expected
    assert stages.count("fabrication_pricing_hash") > 3
    monkeypatch.setattr(pricing,"MAX_CERTIFICATE_BYTES",size-1)
    with pytest.raises(graph._Exhausted,match="CERTIFICATE_BYTE_BUDGET"):
        pricing._certificate_digest(payload,graph._Work(500000,None))


@pytest.mark.parametrize("operation,stage",[
    ("producer","fabrication_pricing_serialize"),
    ("producer","fabrication_pricing_hash"),
    ("checker","fabrication_pricing_hash"),
])
@pytest.mark.parametrize("error_type",[graph._Exhausted,TimeoutError,ValueError])
def test_late_serialization_and_hash_cancellation_propagates_without_mutation(operation,stage,error_type):
    p,o = problem(),objective()
    certificate = pricing.compile_fabrication_pricing(p,o)
    before = deepcopy(certificate)
    roots = digest(p),digest(o)
    error = error_type("caller interrupted late certificate construction")
    hits = 0
    def checkpoint(current):
        nonlocal hits
        if current == stage:
            hits += 1
            if hits == 3:
                raise error
    with pytest.raises(error_type) as caught:
        if operation == "producer":
            pricing.compile_fabrication_pricing(p,o,checkpoint=checkpoint)
        else:
            pricing.verify_fabrication_pricing(p,o,certificate,checkpoint=checkpoint)
    assert caught.value is error and hits == 3
    assert certificate == before and (digest(p),digest(o)) == roots


def test_oversized_certificate_is_unknown_before_any_rational_label_allocation(monkeypatch):
    p,o = problem(goal=[4,0,1]),objective()
    certificate = pricing.compile_fabrication_pricing(p,o)
    # Every coordinate has an allowed individual string size and the list is
    # below the state limit, but the aggregate encoding exceeds sixteen MiB.
    certificate["points_m"] = [["0"*2500]*3 for _ in range(2300)]
    assert 2300*3*2500 > pricing.MAX_CERTIFICATE_BYTES
    def forbidden(*args,**kwargs):
        pytest.fail("Oversized proof must be rejected before decoding rational labels")
    monkeypatch.setattr(pricing,"_cost",forbidden)
    checked = pricing.verify_fabrication_pricing(p,o,certificate)
    assert checked["status"] == "UNKNOWN" and checked["reason"] == "CERTIFICATE_BYTE_BUDGET"
