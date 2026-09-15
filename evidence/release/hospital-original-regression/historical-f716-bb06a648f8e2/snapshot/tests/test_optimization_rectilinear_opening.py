from copy import deepcopy
from fractions import Fraction as Q
from itertools import product
import json
import random

import pytest

from oma.optimization import rectilinear_opening as opening


HOST = [[0, 0, 0], [10, 8, 2]]
CUT = [[2, 3, -1], [5, 6, 3]]
KW = {"through_axis": 2, "context_root": "frozen-opening-context",
      "source_roots": {"source": "original-ifc", "host": "host-step-definition",
                       "frame": "local-frame-definition", "authorization": "supplied-approval"}}


def compile_one(host=HOST, cut=CUT, **changes):
    return opening.compile_rectilinear_opening(host, cut, **{**KW, **changes})


def check_one(certificate, host=HOST, cut=CUT, **changes):
    return opening.verify_rectilinear_opening(host, cut, certificate, **{**KW, **changes})


def test_exact_remaining_support_volume_and_boundaries():
    cert = compile_one()
    assert cert["host_volume_m3"] == "160"
    assert cert["removed_volume_m3"] == "18"
    assert cert["remaining_volume_m3"] == "142"
    result = check_one(json.loads(json.dumps(cert)))
    assert result["status"] == "PASS"
    assert result["arrangement_strata_checked"] == 147
    boxes = [tuple(tuple(Q(x) for x in row) for row in c["bounds_local"]) for c in cert["remaining_cells"]]
    contains = lambda p: any(all(lo <= x <= hi for x, lo, hi in zip(p, *box)) for box in boxes)
    assert contains((2, 4, 1))  # Shaft boundary belongs to regularized support.
    assert contains((3, 3, 2))
    assert not contains((3, 4, 1))
    assert not contains((3, 4, 0))  # No blind cap on either thickness face.
    assert not contains((3, 4, 2))
    assert contains((0, 0, 0))
    assert all(value is False for value in result["limitations"].values())


@pytest.mark.parametrize("axis", [0, 1, 2])
def test_each_through_axis_and_noninteger_coordinates(axis):
    perm = [i for i in range(3) if i != axis]
    host = [[Q(-7, 3)] * 3, [Q(11, 3)] * 3]
    cut = [[Q(-2, 3)] * 3, [Q(4, 3)] * 3]
    cut[0][axis], cut[1][axis] = -3, 4
    cert = compile_one(host, cut, through_axis=axis)
    assert Q(cert["removed_volume_m3"]) == 24
    assert Q(cert["remaining_volume_m3"]) == 192
    assert check_one(cert, host, cut, through_axis=axis)["status"] == "PASS"
    assert len(perm) == 2


def test_verifier_does_not_call_compiler_and_accepts_cell_order(monkeypatch):
    cert = compile_one()
    cert["remaining_cells"].reverse()
    monkeypatch.setattr(opening, "compile_rectilinear_opening", lambda *a, **kw: (_ for _ in ()).throw(AssertionError("compiler called")))
    assert check_one(cert)["status"] == "PASS"


def test_same_volume_shifted_cut_cannot_replace_original_support():
    original = compile_one()
    forged = compile_one(cut=[[3, 3, -1], [6, 6, 3]])
    forged["root"], forged["manifest"] = original["root"], original["manifest"]
    forged["removed_bounds_local"] = original["removed_bounds_local"]
    assert forged["remaining_volume_m3"] == original["remaining_volume_m3"]
    result = check_one(forged)
    assert result["status"] == "FAIL"
    assert result["reason"] == "REMAINING_SUPPORT_SET_MISMATCH"
    assert "witness_local" in result


@pytest.mark.parametrize("change", ["missing", "duplicate", "overlap", "degenerate", "outside", "fake_volume", "removed_shift", "empty_id"])
def test_adversarial_support_cells(change):
    cert = compile_one()
    cells = cert["remaining_cells"]
    if change == "missing":
        cells.pop()
    elif change == "duplicate":
        cells[-1] = deepcopy(cells[0])
    elif change == "overlap":
        cells[2]["bounds_local"][0][0] = "1"
        cells[2]["volume_m3"] = "24"
        cert["remaining_volume_m3"] = "148"
    elif change == "degenerate":
        cells[0]["bounds_local"][1][0] = "0"
        cells[0]["volume_m3"] = "0"
    elif change == "outside":
        cells[0]["bounds_local"][0][0] = "-1"
        cells[0]["volume_m3"] = "48"
    elif change == "fake_volume":
        cells[0]["volume_m3"] = "31"
    elif change == "removed_shift":
        cert["removed_bounds_local"][0][0] = "3"
        cert["removed_bounds_local"][1][0] = "6"
    elif change == "empty_id":
        cells[0]["id"] = ""
    assert check_one(cert)["status"] == "FAIL"


@pytest.mark.parametrize("field", ["source", "host", "frame", "authorization"])
def test_each_declared_identity_is_bound(field):
    roots = {**KW["source_roots"], field: "changed"}
    assert check_one(compile_one(), source_roots=roots)["status"] == "FAIL"


@pytest.mark.parametrize("field,value", [("status", "PASS"), ("scope", "PHYSICAL_APPROVAL"), ("root", "different"),
    ("host_volume_m3", "160.0"), ("remaining_volume_m3", True), ("set_semantics", "OPEN_DIFFERENCE")])
def test_certificate_identity_and_claim_tampering(field, value):
    cert = compile_one()
    cert[field] = value
    assert check_one(cert)["status"] == "FAIL"


def test_booleans_cannot_replace_typed_limitations_or_axis():
    cert = compile_one()
    cert["limitations"]["candidate_acceptance_authority"] = 0
    assert check_one(cert)["status"] == "FAIL"
    with pytest.raises(ValueError):
        compile_one(through_axis=True)
    cert = compile_one()
    cert["manifest"]["through_axis"] = 2.0
    assert check_one(cert)["status"] == "FAIL"


@pytest.mark.parametrize("cut", [
    [[2, 3, 0], [5, 6, 3]], [[2, 3, -1], [5, 6, 2]],
    [[2, 3, "1/2"], [5, 6, "3/2"]], [[0, 3, -1], [5, 6, 3]],
    [[2, 3, -1], [10, 6, 3]], [[2, 3, -1], [2, 6, 3]],
    [[2, 3, -1], [5, 9, 3]], [[2, 3, -1], [5, 6, -2]],
])
def test_blind_touching_degenerate_and_outside_cuts_rejected(cut):
    with pytest.raises(ValueError):
        compile_one(cut=cut)
    assert check_one(compile_one(), cut=cut)["status"] == "FAIL"


@pytest.mark.parametrize("coordinate", [float("nan"), float("inf"), True, None, "1/0", "1e10000000", "9" * 4097])
def test_invalid_numeric_inputs_rejected(coordinate):
    host = deepcopy(HOST)
    host[0][0] = coordinate
    with pytest.raises(ValueError):
        compile_one(host=host)


@pytest.mark.parametrize("changes", [
    {"through_axis": 3}, {"through_axis": -1}, {"context_root": ""},
    {"source_roots": {}}, {"source_roots": {**KW["source_roots"], "authorization": ""}},
    {"source_roots": {**KW["source_roots"], "extra": "unbound"}},
])
def test_incomplete_inputs_rejected(changes):
    with pytest.raises(ValueError):
        compile_one(**changes)


def test_float_is_exact_binary_value_and_input_not_mutated():
    host, cut, roots = deepcopy(HOST), deepcopy(CUT), deepcopy(KW["source_roots"])
    cut[0][0] = .1
    cert = compile_one(host, cut, source_roots=roots)
    assert cert["manifest"]["opening_bounds_local"][0][0] == str(Q(.1))
    assert check_one(cert, host, cut, source_roots=roots)["status"] == "PASS"
    exact_decimal = deepcopy(cut)
    exact_decimal[0][0] = "0.1"
    assert check_one(cert, host, exact_decimal, source_roots=roots)["status"] == "FAIL"
    assert host == HOST and cut[0][0] == .1 and roots == KW["source_roots"]
    roots["host"] = "changed after compilation"
    assert cert["manifest"]["source_roots"]["host"] == KW["source_roots"]["host"]


def test_fifty_random_exact_boxes_match_independent_lattice_ground_truth():
    rng = random.Random(71727)
    for _ in range(50):
        axis = rng.randrange(3)
        side = rng.randint(5, 12)
        host = [[0] * 3, [side] * 3]
        cut = [[rng.randint(1, side - 3) for _ in range(3)], [0] * 3]
        cut[1] = [rng.randint(a + 1, side - 1) for a in cut[0]]
        cut[0][axis], cut[1][axis] = -1, side + 1
        cert = compile_one(host, cut, through_axis=axis)
        assert check_one(cert, host, cut, through_axis=axis)["status"] == "PASS"
        boxes = [tuple(tuple(Q(x) for x in row) for row in c["bounds_local"]) for c in cert["remaining_cells"]]
        occupied_units = 0
        for unit in product(range(side), repeat=3):
            point = [Q(2 * x + 1, 2) for x in unit]
            # Independent integer voxel oracle: a through opening removes the
            # units in its strict rectangular transverse footprint.
            is_void = all(cut[0][i] <= unit[i] < cut[1][i] for i in range(3) if i != axis)
            count = sum(all(a < x < b for x, a, b in zip(point, *box)) for box in boxes)
            assert count == (0 if is_void else 1)
            occupied_units += not is_void
        assert Q(cert["remaining_volume_m3"]) == occupied_units
