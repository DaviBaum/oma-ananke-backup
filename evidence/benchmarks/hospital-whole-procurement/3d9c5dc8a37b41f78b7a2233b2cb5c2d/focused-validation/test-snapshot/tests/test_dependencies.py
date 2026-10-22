from dataclasses import replace
from fractions import Fraction
import copy
import pytest

from oma.dependencies import (CacheContext, DerivedNode, DependencyEngine, Value,
    invalidation_closure, verify_closure_certificate)


CONTEXT = CacheContext("theory-1", "cost-1", "experiments-1", "checker-1", "cpu", "solver-1", "project-a")


def test_nonlocal_closure_cache_and_cold_equivalence():
    nodes = [DerivedNode("duct-area", ("diameter",), lambda d: d["diameter"]**2, "1"),
             DerivedNode("remote-pressure", ("duct-area", "load"), lambda d: d["load"] / d["duct-area"], "1"),
             DerivedNode("release", ("remote-pressure",), lambda d: d["remote-pressure"] < 20, "1"),
             DerivedNode("viewer", ("camera",), lambda d: d["camera"], "1")]
    assert invalidation_closure(nodes, ["diameter"]) == {"diameter", "duct-area", "remote-pressure", "release"}
    engine = DependencyEngine(nodes, dependencies_complete=True)
    inputs = {"diameter": 2, "load": 60, "camera": "north"}
    first = engine.build(inputs, CONTEXT)
    assert first.values["release"].value is True
    second = engine.build(inputs, CONTEXT)
    assert set(second.reused) == {n.id for n in nodes}
    changed = inputs | {"diameter": 1}
    third = engine.build(changed, CONTEXT)
    assert third.values["release"].value is False
    assert third.reused == ("viewer",)
    assert engine.compare_with_cold(changed, CONTEXT)["equivalent"]


@pytest.mark.parametrize("field", ["theory", "objective", "experiment_family", "checker", "environment", "tool_version", "scope"])
def test_every_context_guard_invalidates_cache(field):
    engine = DependencyEngine([DerivedNode("result", ("input",), lambda d: d["input"], "1")], dependencies_complete=True)
    original = engine.build({"input": 1}, CONTEXT)
    changed = engine.build({"input": 1}, replace(CONTEXT, **{field: "changed"}))
    assert changed.recomputed == ("result",)
    assert original.semantic_root != changed.semantic_root


def test_missing_or_undeclared_dependency_cannot_become_ready():
    missing = DependencyEngine([DerivedNode("r", ("absent",), lambda d: 1, "1")], dependencies_complete=True)
    assert missing.build({}, CONTEXT).values["r"].status == "UNKNOWN"
    hidden = DependencyEngine([DerivedNode("r", ("a",), lambda d: d["b"], "1")], dependencies_complete=True)
    assert hidden.build({"a": 1, "b": 2}, CONTEXT).values["r"].status == "FAILED"
    optional_hidden = DependencyEngine([DerivedNode("r", ("a",), lambda d: d.get("b", 0), "1")], dependencies_complete=True)
    assert optional_hidden.build({"a": 1, "b": 2}, CONTEXT).values["r"].status == "FAILED"
    unclosed = DependencyEngine([DerivedNode("r", ("a",), lambda d: 1, "1")], dependencies_complete=False)
    assert unclosed.build({"a": 1}, CONTEXT).values["r"].status == "UNKNOWN"


def test_unknown_input_and_mutable_output_do_not_corrupt_sibling():
    node = DerivedNode("r", ("a",), lambda d: d["a"] + [2], "1")
    engine = DependencyEngine([node], dependencies_complete=True)
    inputs = {"a": [1]}
    first = engine.build(inputs, CONTEXT)
    first.values["r"].value.append(999)
    assert inputs == {"a": [1]}
    second = engine.build(inputs, CONTEXT)
    assert second.values["r"].value == [1, 2]
    unresolved = engine.build({"a": Value(status="UNKNOWN", reason="missing survey")}, CONTEXT)
    assert unresolved.values["r"].status == "UNKNOWN"


def cyclic_nodes():
    return [DerivedNode("a", ("b", "load"), lambda d: min(3, max(d["load"], d["b"])), "1", (0, 1, 2, 3)),
            DerivedNode("b", ("a",), lambda d: d["a"], "1", (0, 1, 2, 3))]


def test_finite_scc_least_fixed_point_and_removal_restarts_at_bottom():
    engine = DependencyEngine(cyclic_nodes(), dependencies_complete=True)
    report = engine.build({"load": 2}, CONTEXT)
    assert report.values["a"].value == report.values["b"].value == 2
    certificate = next(iter(report.cycle_certificates.values()))
    assert verify_closure_certificate(certificate) == "PASS"
    lower = engine.build({"load": 1}, CONTEXT)
    assert lower.values["a"].value == lower.values["b"].value == 1
    assert engine.compare_with_cold({"load": 1}, CONTEXT)["equivalent"]
    bad = copy.deepcopy(certificate)
    bad["fixed_point"] = (3, 3)
    assert verify_closure_certificate(bad) == "FAIL"


def test_oscillating_or_unproved_cycle_stays_unknown():
    oscillating = DerivedNode("a", ("a",), lambda d: 1 - d["a"], "1", (0, 1))
    report = DependencyEngine([oscillating], dependencies_complete=True).build({}, CONTEXT)
    assert report.values["a"].reason == "CYCLE_OPERATOR_NOT_MONOTONE"
    no_domain = replace(oscillating, lattice_values=())
    assert DependencyEngine([no_domain], dependencies_complete=True).build({}, CONTEXT).values["a"].reason == "CYCLE_FINITE_LATTICE_MISSING"


def test_cycle_budgets_produce_unknown_without_silent_convergence():
    engine = DependencyEngine(cyclic_nodes(), dependencies_complete=True)
    limited = engine.build({"load": 2}, CONTEXT, max_lattice_states=4)
    assert limited.values["a"].reason == "CYCLE_MONOTONICITY_BUDGET"
    # Larger budget must not reuse an UNKNOWN result from the previous limit.
    complete = engine.build({"load": 2}, CONTEXT)
    assert complete.values["a"].status == "READY"
    assert engine.build({"load": 2}, CONTEXT, cold=True, max_cycle_rounds=1).values["a"].reason == "CYCLE_ITERATION_BUDGET"


def test_node_version_and_dependency_schema_are_semantic():
    node = DerivedNode("r", ("a",), lambda d: d["a"], "1")
    first = DependencyEngine([node], dependencies_complete=True).build({"a": 2}, CONTEXT)
    second = DependencyEngine([replace(node, version="2")], dependencies_complete=True).build({"a": 2}, CONTEXT)
    assert first.semantic_root != second.semantic_root
    with pytest.raises(ValueError):
        DependencyEngine([node, node], dependencies_complete=True)


def test_canonical_type_tag_cannot_alias_user_dictionary():
    engine = DependencyEngine([DerivedNode("r", ("a",), lambda d: d["a"], "1")], dependencies_complete=True)
    fraction = engine.build({"a": Fraction(1, 2)}, CONTEXT)
    dictionary = engine.build({"a": {"rational": "1/2"}}, CONTEXT)
    assert fraction.semantic_root != dictionary.semantic_root
    assert dictionary.values["r"].value == {"rational": "1/2"}


def test_long_dependency_chain_is_not_limited_by_python_recursion():
    nodes = [DerivedNode(f"n{i}", (f"n{i-1}" if i else "source",),
                         lambda d: next(iter(d.values())) + 1, "1") for i in range(1200)]
    result = DependencyEngine(nodes, dependencies_complete=True).build({"source": 0}, CONTEXT)
    assert result.values["n1199"].value == 1200
