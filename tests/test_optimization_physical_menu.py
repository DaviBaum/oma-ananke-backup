from copy import deepcopy
from itertools import product
import json

import pytest

from oma.optimization import physical_menu as menu


def problem(n=2, *, outcome=lambda a: ("PASS", {"length_m": "12"}), examined=None):
    assignments = list(product(("a", "b"), repeat=n))
    rows = []
    for i, a in enumerate(assignments):
        if examined is not None and a not in examined:
            continue
        verdict, projection = outcome(a)
        rows.append({"assignment": list(a), "candidate_id": f"candidate:{i}", "state_root": f"state:{i}",
                     "report_root": f"report:{i}", "verdict": verdict, "projection": projection})
    return {"schema": menu.SCHEMA, "context_root": "federation:rules:evidence:build:v1",
            "projection_contract_root": "verdict:declared-costs:authority-v1",
            "demands": [{"id": f"d{i}", "choices": [{"id": c, "definition_root": f"route:{i}:{c}"}
                         for c in ("a", "b")]} for i in range(n)], "examined": rows}


def test_complete_menu_keeps_all_labels_and_distinct_report_provenance():
    p = problem()
    cert = menu.compile_physical_menu(p)
    assert cert["status"] == menu.STATUS
    assert cert["summary"]["assignment_count"] == 4
    assert cert["summary"]["terminal_profile_group_count"] == 1
    assert cert["summary"]["action_stable_group_count"] == 1
    assert cert["summary"]["separator_metrics"]["root_labeled_realization_count"] == 4
    assert len(cert["terminal_profile_groups"][0]["assignment_ids"]) == 4
    assert len({r["report_root"] for r in cert["manifest"]["assignment_table"]}) == 4
    checked = menu.verify_physical_menu(p, json.loads(json.dumps(cert)))
    assert checked["status"] == "PASS"
    assert checked["verified_assignments"] == 4
    assert checked["limitations"]["candidate_acceptance_authority"] is False


def test_unknown_assignments_are_explicit_and_never_discarded():
    p = problem(examined={("a", "a")})
    cert = menu.compile_physical_menu(p)
    assert cert["summary"]["verdict_counts"] == {"PASS": 1, "UNKNOWN": 3}
    rows = cert["manifest"]["assignment_table"]
    assert sum(r["assessment"] == "UNEXAMINED" for r in rows) == 3
    assert all(r["report_root"] is None for r in rows if r["assessment"] == "UNEXAMINED")
    assert menu.verify_physical_menu(p, cert)["status"] == "PASS"


def test_reported_unknown_is_distinct_from_unexamined_unknown():
    p = problem(1, outcome=lambda a: ("UNKNOWN", {}), examined={("a",)})
    cert = menu.compile_physical_menu(p)
    assert cert["summary"]["terminal_profile_group_count"] == 2
    assert cert["summary"]["verdict_counts"] == {"UNKNOWN": 2}


def test_future_replacement_distinguishes_equal_current_profiles():
    p = problem(outcome=lambda a: ("PASS", {"parity": sum(x == "b" for x in a) % 2}))
    cert = menu.compile_physical_menu(p)
    assert cert["summary"]["terminal_profile_group_count"] == 2
    assert cert["summary"]["action_stable_group_count"] == 4
    assert menu.verify_physical_menu(p, cert)["status"] == "PASS"


def test_full_three_way_interaction_is_not_replaced_by_pairwise_passes():
    p = problem(3, outcome=lambda a: ("FAIL" if a == ("b", "b", "b") else "PASS", {}))
    cert = menu.compile_physical_menu(p)
    assert cert["summary"]["verdict_counts"] == {"FAIL": 1, "PASS": 7}
    assert cert["summary"]["action_stable_group_count"] == 8
    assert menu.verify_physical_menu(p, cert)["status"] == "PASS"


def test_duplicate_definition_still_preserves_independent_labels():
    p = problem(1)
    p["demands"][0]["choices"][1]["definition_root"] = p["demands"][0]["choices"][0]["definition_root"]
    cert = menu.compile_physical_menu(p)
    assert cert["terminal_profile_groups"][0]["labeled_count"] == 2
    assert [r["assignment"] for r in cert["manifest"]["assignment_table"]] == [["a"], ["b"]]


@pytest.mark.parametrize("change", [
    lambda p: p.update(context_root="changed-source"),
    lambda p: p.update(projection_contract_root="expanded-experiments"),
    lambda p: p["demands"][0]["choices"][0].update(definition_root="different-route-geometry"),
    lambda p: p["examined"][0].update(report_root="different-check"),
    lambda p: p["examined"][0].update(state_root="different-design"),
    lambda p: p["examined"][0].update(projection={"length_m": "13"}),
])
def test_every_scope_and_report_change_invalidates_certificate(change):
    p = problem()
    cert = menu.compile_physical_menu(p)
    change(p)
    assert menu.verify_physical_menu(p, cert)["status"] == "FAIL"


@pytest.mark.parametrize("change", [
    lambda c: c["manifest"]["assignment_table"].pop(),
    lambda c: c["terminal_profile_groups"][0]["assignment_ids"].pop(),
    lambda c: c["action_stable_groups"][0].update(labeled_count=True),
    lambda c: c["summary"].update(terminal_profile_group_count=True),
    lambda c: c["limitations"].update(continuous_route_universe_complete=True),
    lambda c: c["limitations"].update(candidate_acceptance_authority=0),
    lambda c: c["separator"]["messages"]["prefix:2"][0].update(count=3),
    lambda c: c["causal"]["block_of"].__setitem__(0, 17),
])
def test_tampered_bindings_counts_scope_and_kernel_witnesses_fail(change):
    p = problem()
    cert = menu.compile_physical_menu(p)
    change(cert)
    assert menu.verify_physical_menu(p, cert)["status"] == "FAIL"


def test_checker_does_not_rerun_either_compiler(monkeypatch):
    p = problem()
    cert = menu.compile_physical_menu(p)
    def forbidden(*args, **kwargs):
        raise AssertionError("Compiler called by independent checker")
    monkeypatch.setattr(menu, "compile_separator", forbidden)
    monkeypatch.setattr(menu, "compile_bisimulation", forbidden)
    assert menu.verify_physical_menu(p, cert)["status"] == "PASS"


@pytest.mark.parametrize("change", [
    lambda p: p["examined"].append(deepcopy(p["examined"][0])),
    lambda p: p["examined"][0].update(assignment=["undeclared", "a"]),
    lambda p: p["examined"][0].update(report_root=""),
    lambda p: p["examined"][0].update(verdict="OPTIMAL"),
    lambda p: p["examined"][0].update(projection={"x": float("nan")}),
    lambda p: p["demands"][0].update(choices=[]),
])
def test_invalid_input_fails_before_compilation(change):
    p = problem()
    change(p)
    with pytest.raises(ValueError):
        menu.compile_physical_menu(p)


def test_budget_limits_do_not_produce_partial_exact_certificates():
    p = problem()
    assert menu.compile_physical_menu(p, max_assignments=3)["status"] == "UNKNOWN"
    assert menu.compile_physical_menu(p, max_work=0)["status"] == "UNKNOWN"
    cert = menu.compile_physical_menu(p)
    assert menu.verify_physical_menu(p, cert, max_work=0)["status"] == "UNKNOWN"


def test_examined_order_is_irrelevant_but_original_menu_order_is_bound():
    p = problem()
    cert = menu.compile_physical_menu(p)
    p["examined"].reverse()
    assert menu.verify_physical_menu(p, cert)["status"] == "PASS"
    p["demands"][0]["choices"].reverse()
    assert menu.verify_physical_menu(p, cert)["status"] == "FAIL"
