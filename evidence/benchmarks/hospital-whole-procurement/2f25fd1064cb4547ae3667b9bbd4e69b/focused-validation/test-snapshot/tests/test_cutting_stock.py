from copy import deepcopy
from fractions import Fraction

import pytest

from oma.optimization.cutting_stock import optimize_cutting_stock, verify_cut_plan


def data(lengths, stock=10, *, price=None):
    pieces = [{"id": f"p{i:03d}", "source_id": f"sha:ifc:{i}", "group": "same_spec",
               "length_m": v, "batch_id": f"net-{i}"} for i, v in enumerate(lengths)]
    stocks = [{"id": "bar", "group": "same_spec", "length_m": stock}]
    if price is not None:
        stocks[0].update(unit_price=price, currency="USD")
    return pieces, stocks


def test_exact_search_improves_ffd_and_proves_capacity_bound():
    p, s = data([6, 5, 3, 2, 2, 2])
    r = optimize_cutting_stock(p, s)
    assert r["plans"]["baseline"]["totals"]["stock_count"] == 3
    assert r["plans"]["selected"]["totals"]["stock_count"] == 2
    assert r["improvements"]["versus_pooled_ffd"]["purchased_length_reduction_m"] == "10"
    assert r["optimality"] == "PRIMARY_OBJECTIVE_OPTIMAL_FOR_DECLARED_GROUPS"
    assert r["verification"]["selected"]["all_required_pieces_exactly_once"]


def test_zero_budget_retains_feasible_plan_without_false_optimum():
    p, s = data([6, 5, 3, 2, 2, 2])
    r = optimize_cutting_stock(p, s, budget_nodes=0)
    assert r["search"]["nodes_used"] == 0
    assert r["search"]["budget_exhausted"]
    assert r["optimality"] == "VERIFIED_FEASIBLE_HEURISTIC"
    assert r["verification"]["selected"]["status"] == "PASS"


def test_budget_never_exceeded_and_timeout_does_not_omit_pieces(monkeypatch):
    p, s = data([6, 5, 3, 2, 2, 2])
    for kwargs in ({"budget_nodes": 3}, {"max_seconds": "1/1000000000000"}):
        if "max_seconds" in kwargs:
            # Windows GetTickCount64 may not advance within this tiny search.
            # Test an actually elapsed deadline independently of OS clock resolution.
            ticks = iter([0.0, 1.0])
            monkeypatch.setattr("oma.optimization.cutting_stock.time.monotonic", lambda: next(ticks, 1.0))
        r = optimize_cutting_stock(p, s, **kwargs)
        assert r["search"]["nodes_used"] <= kwargs.get("budget_nodes", 200000)
        assert r["search"]["budget_exhausted"]
        assert r["plans"]["selected"]["totals"]["piece_count"] == len(p)
        assert r["optimality"] == "VERIFIED_FEASIBLE_HEURISTIC"


def subset_repair_data():
    # Fixed generic packing instance: 1395 units fit fourteen 100-unit bars.
    return data([12, 19, 28, 27, 61, 32, 10, 29, 36, 29, 51, 34, 58, 50, 43,
                 45, 8, 50, 50, 38, 51, 15, 11, 48, 9, 45, 10, 21, 52, 28,
                 40, 30, 13, 33, 33, 47, 52, 64, 30, 53], stock=100)


def test_large_group_subset_fill_improves_real_schedule_without_exhaustive_claim():
    p, s = subset_repair_data()
    out = optimize_cutting_stock(p, s, max_exact_pieces=18, budget_nodes=10000)
    assert out["plans"]["baseline"]["totals"]["stock_count"] == 15
    assert out["plans"]["selected"]["totals"]["stock_count"] == 14
    assert out["plans"]["selected"]["totals"]["total_waste_m"] == "5"
    group, = out["search"]["groups"]
    assert group["method"] == "BOUNDED_INTEGER_SUBSET_REPAIR"
    assert group["exact_search_complete"] is False
    assert group["optimality"] == "PRIMARY_OBJECTIVE_OPTIMAL_BY_LOWER_BOUND"
    assert out["verification"]["selected"]["all_required_pieces_exactly_once"]


@pytest.mark.parametrize("budget", [1, 20, 200])
def test_interrupted_subset_repair_keeps_a_complete_feasible_incumbent(budget):
    p, s = subset_repair_data()
    out = optimize_cutting_stock(p, s, max_exact_pieces=18, budget_nodes=budget)
    assert out["search"]["nodes_used"] <= budget
    assert out["plans"]["selected"]["totals"]["piece_count"] == 40
    assert out["verification"]["selected"]["status"] == "PASS"
    assert Fraction(out["improvements"]["versus_pooled_ffd"]["purchased_length_reduction_m"]) >= 0


def test_subset_repair_keeps_fractional_kerf_and_trim_exact():
    p, s = subset_repair_data()
    # Same integer capacities after exact common-unit reduction, with positive
    # kerf and trim. No binary-float approximation enters subset feasibility.
    for piece in p:
        piece["length_m"] = str(Fraction(piece["length_m"], 1000) - Fraction(1, 10000))
    s[0]["length_m"] = "1001/10000"
    out = optimize_cutting_stock(p, s, max_exact_pieces=18, budget_nodes=10000,
                                kerf_m="1/10000", end_trim_m="1/10000")
    assert out["plans"]["selected"]["totals"]["stock_count"] == 14
    assert out["plans"]["selected"]["totals"]["kerf_loss_m"] == "1/250"
    assert out["plans"]["selected"]["totals"]["trim_loss_m"] == "7/5000"
    assert out["verification"]["selected"]["status"] == "PASS"


def test_subset_capacity_work_bound_preserves_unusual_exact_inputs():
    p, s = subset_repair_data()
    p[0]["length_m"] = str(Fraction(p[0]["length_m"]) + Fraction(1, 1000000007))
    out = optimize_cutting_stock(p, s, max_exact_pieces=18, budget_nodes=10000)
    assert out["plans"]["selected"]["totals"]["piece_count"] == 40
    assert out["verification"]["selected"]["status"] == "PASS"
    assert out["search"]["groups"][0]["method"] != "BOUNDED_INTEGER_SUBSET_REPAIR"


def test_conservative_kerf_and_total_end_trim_exact():
    p, s = data(["49/10", "49/10"], 10)
    r = optimize_cutting_stock(p, s, kerf_m="1/20", end_trim_m="1/10")
    totals = r["plans"]["selected"]["totals"]
    assert totals["stock_count"] == 1
    assert totals["required_length_m"] == "49/5"
    assert totals["kerf_loss_m"] == "1/10"
    assert totals["trim_loss_m"] == "1/10"
    assert totals["offcut_length_m"] == "0"
    assert totals["total_waste_m"] == "1/5"
    with pytest.raises(ValueError, match="exceeds stock"):
        optimize_cutting_stock(*data([10], 10), kerf_m="0.001")


def test_batch_consolidation_is_separate_from_algorithm_improvement():
    p, s = data([2, 2], 6, price="24.50")
    r = optimize_cutting_stock(p, s)
    assert r["improvements"]["versus_pooled_ffd"]["price_reduction"] == "0"
    assert r["improvements"]["versus_per_batch_scenario"]["price_reduction"] == "49/2"
    assert r["plans"]["per_batch_scenario"]["totals"]["stock_count"] == 2
    assert r["plans"]["selected"]["totals"]["stock_count"] == 1


def test_missing_batch_ids_disables_only_separate_scenario():
    p, s = data([2, 2])
    del p[0]["batch_id"]
    r = optimize_cutting_stock(p, s)
    assert "per_batch_scenario" not in r["plans"]
    assert r["verification"]["selected"]["status"] == "PASS"


def test_price_objective_uses_supplied_catalogue_not_shortest_stock():
    p, s = data([4, 4], 10, price=2)
    s.append({"id": "short", "group": "same_spec", "length_m": 4, "unit_price": 5, "currency": "USD"})
    r = optimize_cutting_stock(p, s, objective="TOTAL_PRICE", currency="USD")
    assert r["plans"]["selected"]["totals"]["total_price"] == "2"
    assert r["plans"]["selected"]["totals"]["purchased_length_m"] == "10"
    assert r["optimality"] == "PRIMARY_OBJECTIVE_OPTIMAL_FOR_DECLARED_GROUPS"
    assert r["search"]["groups"][0]["optimality"] == "PRIMARY_OBJECTIVE_OPTIMAL_BY_LOWER_BOUND"


def test_compatibility_groups_are_never_mixed():
    p, s = data([2, 2], 6)
    p[1]["group"] = "different_material"
    s.append({"id": "other", "group": "different_material", "length_m": 6})
    r = optimize_cutting_stock(p, s)
    assert r["plans"]["selected"]["totals"]["stock_count"] == 2
    assert {b["group"] for b in r["plans"]["selected"]["bins"]} == {"same_spec", "different_material"}


def test_multiple_stock_lengths_and_exact_price_calculation():
    p, s = data([5, 3, 2], 10, price="19.99")
    s.append({"id": "six", "group": "same_spec", "length_m": 6, "unit_price": "14.25", "currency": "USD"})
    r = optimize_cutting_stock(p, s, objective="TOTAL_PRICE")
    assert r["plans"]["selected"]["totals"]["total_price"] == "1999/100"
    assert r["plans"]["selected"]["totals"]["stock_count"] == 1


@pytest.mark.parametrize("bad", [-1, 0, float("nan"), float("inf"), True, "1/0", "x", None])
def test_invalid_required_lengths_rejected(bad):
    with pytest.raises(ValueError):
        optimize_cutting_stock(*data([bad]))


@pytest.mark.parametrize("field,value", [("kerf_m", -1), ("end_trim_m", -1), ("end_trim_m", 10),
                                          ("budget_nodes", -1), ("budget_nodes", True),
                                          ("max_exact_pieces", 33), ("max_seconds", 0)])
def test_invalid_model_and_budget_values_rejected(field, value):
    with pytest.raises(ValueError):
        optimize_cutting_stock(*data([2]), **{field: value})


def test_missing_identity_duplicate_and_long_piece_rejected():
    p, s = data([2])
    with pytest.raises(ValueError, match="Duplicate"):
        optimize_cutting_stock(p + p, s)
    del p[0]["source_id"]
    with pytest.raises(ValueError, match="source_id"):
        optimize_cutting_stock(p, s)
    with pytest.raises(ValueError, match="splicing is not inferred"):
        optimize_cutting_stock(*data([11]))
    with pytest.raises(ValueError, match="Provide"):
        optimize_cutting_stock([], s)


def test_missing_negative_partial_and_mixed_prices_rejected():
    p, s = data([2], price=10)
    for changed in ({"unit_price": -1}, {"currency": ""}, {"unit_price": float("nan")}):
        with pytest.raises(ValueError):
            optimize_cutting_stock(p, [{**s[0], **changed}])
    for addition in ({"id": "second", "group": "same_spec", "length_m": 6},
                     {"id": "second", "group": "same_spec", "length_m": 6, "unit_price": 4, "currency": "EUR"}):
        with pytest.raises(ValueError):
            optimize_cutting_stock(p, s + [addition])
    with pytest.raises(ValueError, match="complete stock prices"):
        optimize_cutting_stock(*data([2]), objective="TOTAL_PRICE")


def test_input_order_does_not_change_deterministic_plan_or_ledger():
    p, s = data([6, 5, 3, 2, 2, 2])
    a = optimize_cutting_stock(p, s)
    b = optimize_cutting_stock(list(reversed(p)), list(reversed(s)))
    assert a == b


@pytest.mark.parametrize("tamper", ["duplicate", "missing", "overlap", "length", "source", "stock", "group", "price", "kerf", "waste", "totals", "root"])
def test_independent_verifier_rejects_tampered_evidence(tamper):
    p, s = data([2, 2], 6, price=10)
    plan = deepcopy(optimize_cutting_stock(p, s)["plans"]["selected"])
    b, c = plan["bins"][0], plan["bins"][0]["cuts"][0]
    if tamper == "duplicate":
        b["cuts"][1]["piece_id"] = c["piece_id"]
    elif tamper == "missing":
        plan["bins"] = []
    elif tamper == "overlap":
        b["cuts"][1]["start_m"] = "0"
    elif tamper == "length":
        c["length_m"] = "1"
    elif tamper == "source":
        c["source_id"] = "different-ifc"
    elif tamper == "stock":
        b["stock_length_m"] = "7"
    elif tamper == "group":
        b["group"] = "different_spec"
    elif tamper == "price":
        b["unit_price"] = "1"
    elif tamper == "kerf":
        c["kerf_after_m"] = "1"
    elif tamper == "waste":
        b["offcut_length_m"] = "0"
    elif tamper == "totals":
        plan["totals"]["total_price"] = "1"
    elif tamper == "root":
        plan["input_sha256"] = "wrong"
    with pytest.raises(ValueError):
        verify_cut_plan(p, s, plan)


def test_verifier_source_binding_rejects_mutated_required_input():
    p, s = data([2, 2])
    plan = optimize_cutting_stock(p, s)["plans"]["selected"]
    p[0]["length_m"] = "2.001"
    with pytest.raises(ValueError, match="bound"):
        verify_cut_plan(p, s, plan)


def test_checkpoint_cancellation_propagates_without_partial_result():
    p, s = data([6, 5, 3, 2, 2, 2])
    def cancel():
        raise RuntimeError("cancelled")
    with pytest.raises(RuntimeError, match="cancelled"):
        optimize_cutting_stock(p, s, checkpoint=cancel)


def test_many_pieces_covered_with_large_group_local_search_budget():
    p, s = data(([6, 5, 3, 2, 2, 2] * 20), 10)
    r = optimize_cutting_stock(p, s, budget_nodes=50, max_exact_pieces=18)
    assert r["search"]["nodes_used"] <= 50
    totals = r["plans"]["selected"]["totals"]
    assert totals["piece_count"] == 120
    assert Fraction(totals["required_length_m"]) == 400
    assert totals["stock_count"] <= r["plans"]["baseline"]["totals"]["stock_count"]
    assert r["scope"]["installed_geometry_changed"] is False


def test_primary_baseline_cannot_silently_be_changed_to_per_piece_roundup():
    with pytest.raises(ValueError, match="Primary baseline"):
        optimize_cutting_stock(*data([2, 2]), baseline_policy="PER_NETWORK")


def test_zero_price_does_not_prove_minimum_stock_count():
    p, s = data([6, 5, 3, 2, 2, 2], price=0)
    r = optimize_cutting_stock(p, s, objective="TOTAL_PRICE", budget_nodes=0)
    assert r["plans"]["selected"]["totals"]["stock_count"] == 3
    assert r["optimality"] == "PRIMARY_OBJECTIVE_OPTIMAL_FOR_DECLARED_GROUPS"
    assert r["search"]["groups"][0]["lower_bound"]["stock_count"] == 2


def test_complete_search_matches_separate_small_partition_enumerator():
    # Independent reference enumerates labeled assignments without optimizer
    # pruning, symmetry elimination, stock selectors, or bound helpers.
    from itertools import product
    scenarios = [([6, 5, 3, 2, 2, 2], [(10, 17)]),
                 ([4, 4, 3, 3, 2], [(6, 8), (10, 15)]),
                 ([3, 3, 2, 2], [(5, 9), (8, 10)]),
                 ([2, 2, 2], [(4, 0), (7, 5)])]
    for lengths, catalogue in scenarios:
        p, _ = data(lengths)
        s = [{"id": f"s{i}", "group": "same_spec", "length_m": n, "unit_price": cost,
              "currency": "USD"} for i, (n, cost) in enumerate(catalogue)]
        for objective in ("TOTAL_PRICE", "PURCHASED_LENGTH"):
            exact = None
            for assignment in product(range(len(lengths)), repeat=len(lengths)):
                loads = [sum(v for j, v in enumerate(lengths) if assignment[j] == b)
                         for b in range(len(lengths))]
                value, feasible = 0, True
                for load in filter(None, loads):
                    options = [(cost if objective == "TOTAL_PRICE" else n) for n, cost in catalogue if n >= load]
                    if not options:
                        feasible = False
                        break
                    value += min(options)
                if feasible and (exact is None or value < exact):
                    exact = value
            r = optimize_cutting_stock(p, s, objective=objective, include_batch_scenario=False)
            actual = r["plans"]["selected"]["totals"]["total_price" if objective == "TOTAL_PRICE" else "purchased_length_m"]
            assert Fraction(actual) == exact
            assert r["optimality"] == "PRIMARY_OBJECTIVE_OPTIMAL_FOR_DECLARED_GROUPS"


def test_batch_plan_is_an_incumbent_even_if_pooled_greedy_is_worse():
    p, s = data([6, 5, 3, 2, 2, 2])
    # Explicit batches each fill exactly 10, while pooled FFD uses three bars.
    for i, batch in enumerate(["a", "b", "b", "a", "a", "b"]):
        p[i]["batch_id"] = batch
    r = optimize_cutting_stock(p, s, budget_nodes=0)
    assert r["plans"]["baseline"]["totals"]["stock_count"] == 3
    assert r["plans"]["selected"]["totals"]["stock_count"] == 2
    assert r["plans"]["per_batch_scenario"]["totals"]["stock_count"] == 2
    assert r["search"]["groups"][0]["method"] == "PER_BATCH_FFD_FEASIBLE_INCUMBENT"


def test_verifier_rejects_boolean_counts_even_when_equal_to_one():
    p, s = data([2])
    plan = optimize_cutting_stock(p, s)["plans"]["selected"]
    plan["totals"]["stock_count"] = True
    with pytest.raises(ValueError, match="totals"):
        verify_cut_plan(p, s, plan)
