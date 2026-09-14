from dataclasses import replace
from copy import deepcopy
from itertools import combinations

from oma.assurance import Claim, Foundation, Inference, Theory, solve_assurance, verify_assurance, evidence_cuts


NOW = "2026-09-14T09:00:00+00:00"
CONTEXT = {"root": "fixture-root", "rules": "v1"}


def fixture():
    claims = tuple(Claim(c, c, "finite test") for c in ("a", "b", "c", "goal", "cycle1", "cycle2"))
    atoms = tuple(Foundation(c, (c,), "EVIDENCE", CONTEXT, c) for c in ("a", "b", "c"))
    rules = (Inference("ab", "goal", ("a", "b"), "declared AND"),
             Inference("c", "goal", ("c",), "alternative proof"),
             Inference("cycle-a", "cycle1", ("cycle2",), "cycle"),
             Inference("cycle-b", "cycle2", ("cycle1",), "cycle"))
    return Theory(claims, atoms, rules, ("goal",))


def check(theory, active=("a", "b", "c"), **kwargs):
    certificate = solve_assurance(theory, [CONTEXT], set(active), NOW, **kwargs)
    verification = verify_assurance(theory, [CONTEXT], set(active), NOW, certificate)
    return certificate, verification


def test_alternative_grounded_proofs_cores_cuts_and_revocation():
    theory = fixture()
    certificate, verification = check(theory)
    assert verification["status"] == "PASS"
    assert certificate["cores"] == [["c"], ["a", "b"]]
    assert certificate["frontiers"]["cycle1"] == []
    assert evidence_cuts(theory, certificate)["cuts"] == [["a", "c"], ["b", "c"]]
    for active, expected in [(('a', 'b'), [["a", "b"]]), (('c',), [["c"]]), (('a',), [])]:
        result, checked = check(theory, active)
        assert checked["status"] == "PASS"
        assert result["cores"] == expected


def test_forged_complete_closure_and_ungrounded_cycle_are_rejected():
    theory = fixture()
    certificate, _ = check(theory)
    forged = deepcopy(certificate)
    forged["frontiers"]["goal"] = forged["frontiers"]["goal"][:1]
    forged["cores"] = [["c"]]
    assert verify_assurance(theory, [CONTEXT], {"a", "b", "c"}, NOW, forged)["status"] == "FAIL"
    forged = deepcopy(certificate)
    forged["steps"][0]["support"] = []
    assert verify_assurance(theory, [CONTEXT], {"a", "b", "c"}, NOW, forged)["status"] == "FAIL"
    assert check(replace(theory, targets=("cycle1",)))[0]["status"] == "UNSUPPORTED"


def test_universal_applicability_and_observation_time_calibration():
    theory = fixture()
    expired = replace(theory.foundations[2], valid_from="2026-01-01T00:00:00Z",
        valid_until="2026-09-01T00:00:00Z", observed_at="2026-08-14T00:00:00Z")
    theory = replace(theory, foundations=(*theory.foundations[:2], expired))
    assert check(theory)[0]["excluded_foundations"]["c"] == "EXPIRED"
    historical = replace(theory, foundations=(*theory.foundations[:2], replace(expired, time_basis="OBSERVATION_TIME")))
    assert check(historical)[0]["cores"] == [["c"], ["a", "b"]]
    assert check(historical, active=("a", "b"))[0]["cores"] == [["a", "b"]]
    result = solve_assurance(historical, [CONTEXT, {**CONTEXT, "root": "different"}], {"a", "b", "c"}, NOW)
    assert result["status"] == "UNSUPPORTED"
    future = replace(theory, foundations=(*theory.foundations[:2], replace(theory.foundations[2],
        observed_at="2026-10-01T00:00:00Z", valid_until=None, time_basis="OBSERVATION_TIME")))
    assert check(future)[0]["excluded_foundations"]["c"] == "OBSERVATION_NOT_YET_AVAILABLE"


def test_nonempty_assumptions_are_explicit_and_excluded_from_external_cuts():
    theory = fixture()
    theory = replace(theory, foundations=tuple(replace(f, kind="TCB") if f.id == "c" else f for f in theory.foundations))
    certificate, verification = check(theory)
    assert verification["status"] == "PASS"
    assert evidence_cuts(theory, certificate)["status"] == "NO_EXTERNAL_EVIDENCE_CUT"
    # Removing a blocker-frontier item a still leaves b absent; it is not a repair.
    assert check(fixture(), active=("a",))[0]["status"] == "UNSUPPORTED"


def test_budget_cannot_certify_core_completeness():
    certificate, checked = check(fixture(), max_work=1)
    assert certificate["status"] == "UNKNOWN_BUDGET"
    assert certificate["cores"] == []
    assert checked["status"] == "UNKNOWN"


def test_all_small_horn_theories_match_independent_subset_forward_chaining():
    import random
    randomizer = random.Random(3191)
    for _ in range(80):
        names = tuple("abcde")
        claims = tuple(Claim(c, c, "exhaustive") for c in names)
        atoms = tuple(Foundation(c, (c,), "EVIDENCE", CONTEXT, c) for c in names[:3])
        rules = tuple(Inference(str(i), randomizer.choice(names), tuple(sorted(randomizer.sample(names, randomizer.randint(1, 3)))), "finite declared rule") for i in range(7))
        theory = Theory(claims, atoms, rules, ("d", "e"))
        cert, verify = check(theory)
        assert verify["status"] == "PASS"
        feasible = []
        for size in range(4):
            for subset in combinations("abc", size):
                reached = set(subset)
                while True:
                    after = reached | {r.conclusion for r in rules if set(r.premises) <= reached}
                    if after == reached:
                        break
                    reached = after
                if {"d", "e"} <= reached and not any(set(s) <= set(subset) for s in feasible):
                    feasible.append(subset)
        assert cert["cores"] == [list(s) for s in feasible]
