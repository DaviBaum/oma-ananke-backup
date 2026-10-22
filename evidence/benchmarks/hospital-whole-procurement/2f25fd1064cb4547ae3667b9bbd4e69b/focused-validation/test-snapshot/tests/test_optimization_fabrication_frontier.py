"""Exact-count frontier against bounded walk oracles and altered certificates."""
from copy import deepcopy
from fractions import Fraction as Q
import itertools
import json

import pytest

from oma.optimization import fabrication_frontier as frontier
from oma.optimization import fabrication_search as graph
from oma.store import digest
from test_optimization_fabrication_search import problem, tiny_impossible, check_path_with_separate_fixed_fabrication_kernel
from test_optimization_fabrication_pricing import objective, polyline_cost


def certified(p=None, o=None, k=4, **budgets):
    p = problem() if p is None else p
    o = objective() if o is None else o
    c = frontier.compile_fabrication_frontier(p, o, k, **budgets)
    v = frontier.verify_fabrication_frontier(p, o, k, c, **budgets)
    assert c["status"] == "CERTIFIED", c
    assert v["status"] == "PASS", v
    return c, v


def reroot(c):
    c["certificate_root"] = digest({k: v for k, v in c.items() if k != "certificate_root"})
    return c


def cube_walk_costs(radius, length_weight, fitting_weight, maximum):
    """All cube walks with <=K turns, including visits past the goal.

    Each cube edge has length one. Straight continuation is impossible at its
    far face, and U-turns are forbidden, so k turns means precisely k+1 edges.
    This independent finite vertex-walk enumeration is exhaustive, not just a
    simple-path oracle or a replay of the six-coordinate fabrication state.
    """
    best, witnessed = {}, []
    def visit(path, last_axis):
        legs = len(path) - 1
        if legs:
            count = legs - 1
            if path[-1] == (1, 1, 1):
                trim = [Q(1) - radius * int(i > 0) - radius * int(i < legs - 1) for i in range(legs)]
                if min(trim) > Q(1, 8):
                    cost = polyline_cost(path, radius, length_weight, fitting_weight)
                    if count not in best or cost[0] < best[count][0]:
                        best[count] = cost
                    witnessed.append((count, path))
            if count == maximum:
                return
        for axis in range(3):
            if axis == last_axis:
                continue
            point = list(path[-1]); point[axis] = 1 - point[axis]
            visit(path + [tuple(point)], axis)
    visit([(0, 0, 0)], None)
    return best, witnessed


@pytest.mark.parametrize("radius,weights", list(itertools.product(["1/8", "1/4", "3/8"], [("1", "0"), ("0", "1"), ("3/2", "2/7")])))
def test_every_exact_count_matches_complete_bounded_cube_walk_oracle(radius, weights):
    p = problem(grid_axes=[[0, 1], [0, 1], [0, 1]], start=[0, 0, 0], goal=[1, 1, 1], diameter_m="1/16", bend_radius_m=radius)
    c, v = certified(p, objective(*weights), 6)
    oracle, walks = cube_walk_costs(Q(radius), *map(Q, weights), 6)
    assert v["reachable_counts"] == sorted(oracle)
    assert any(len(set(path)) < len(path) for _, path in walks), "The oracle includes graph walks with repeated vertices"
    for item in c["frontier"]:
        k = item["fittings"]
        if k in oracle:
            assert item["status"] == "OPTIMAL_PATH" and tuple(map(Q, item["cost"])) == oracle[k]
            assert tuple(map(Q, item["cost"])) == polyline_cost(item["points_m"], Q(radius), *map(Q, weights))
            assert len(item["points_m"]) == k + 2
        else:
            assert item["status"] == "NO_PATH_AT_EXACT_COUNT" and item["cost"] is None


def test_full_frontier_keeps_intermediate_counts_that_scalar_pricing_can_discard():
    c, v = certified(k=6)
    assert v["reachable_counts"] == [1, 2, 3, 4, 5, 6]
    assert [row["cost"] for row in c["frontier"][1:5]] == [["7", "1/4"], ["6", "1/2"], ["5", "3/4"], ["4", "1"]]
    for row in c["frontier"][1:5]:
        check_path_with_separate_fixed_fabrication_kernel(problem(), row)
    # Every entry remains its exact-count optimum even when a weighted scalar
    # policy would select a different count. No <=k relabeling is performed.
    assert c["frontier"][5]["cost"] == ["5", "5/4"]
    assert c["frontier"][5]["cost"] != c["frontier"][4]["cost"]


@pytest.mark.parametrize("axis,sign", list(itertools.product(range(3), (-1, 1))))
def test_zero_count_terminal_debt_and_each_signed_axis(axis, sign):
    start = [2, 2, 1]; goal = list(start); goal[axis] += sign
    c, v = certified(problem(start=start, goal=goal), objective("7/3", "100"), 0)
    assert v["reachable_counts"] == [0]
    assert c["frontier"][0]["cost"] == ["7/3", "0"]
    assert len(c["frontier"][0]["points_m"]) == 2


def test_zero_length_weight_and_zero_terminal_cost_still_count_every_elbow():
    c, _ = certified(o=objective("0", "3/7"), k=4)
    for row in c["frontier"][1:]:
        assert row["cost"] == [str(Q(3, 7) * row["fittings"]), "0"]
    c, _ = certified(problem(goal=[4, 0, 1]), objective("0", "1"), 0)
    assert c["frontier"][0]["cost"] == ["0", "0"]
    assert all(row["potential"] == "0" for row in c["states"])


def test_complete_blocked_graph_closes_all_counts_without_physical_infeasibility():
    c, v = certified(tiny_impossible(), k=6)
    assert not v["reachable_counts"] and all(row["status"] == "NO_PATH_AT_EXACT_COUNT" for row in c["frontier"])
    assert not v["limitations"]["physical_route_infeasibility_claim"]
    assert not v["limitations"]["native_IFC_candidate_acceptance_authority"]


@pytest.fixture(scope="module")
def proof():
    return certified(k=4)[0]


@pytest.mark.parametrize("attack", ["source", "parent", "parent_cycle", "duplicate", "potential", "cost_up", "cost_down", "pi",
    "path", "points", "wrong_count_path", "false_unreachable", "false_reachable", "count_omitted", "count_duplicate", "scope", "domain", "graph", "objective"])
def test_rerooted_false_frontier_cannot_certify(attack, proof):
    c = deepcopy(proof)
    entry = c["frontier"][2]
    if attack == "source": c["states"][0]["potential"] = "1"
    elif attack == "parent": c["states"][2]["parent"] = None
    elif attack == "parent_cycle": c["states"][2]["parent"] = 2
    elif attack == "duplicate": c["states"][-1]["state"] = c["states"][-2]["state"]
    elif attack == "potential": c["states"][1]["potential"] = "1000000"
    elif attack == "cost_up": entry["cost"][0] = str(Q(entry["cost"][0]) + 1)
    elif attack == "cost_down": entry["cost"][0] = str(Q(entry["cost"][0]) - 1)
    elif attack == "pi": entry["cost"][1] = "0"
    elif attack == "path": entry["path_states"].pop(1)
    elif attack == "points": entry["points_m"][1][0] = "123"
    elif attack == "wrong_count_path": entry["path_states"] = c["frontier"][1]["path_states"]
    elif attack == "false_unreachable": entry.update(status="NO_PATH_AT_EXACT_COUNT", cost=None, path_states=[], points_m=[])
    elif attack == "false_reachable": c["frontier"][0] = {**deepcopy(c["frontier"][1]), "fittings": 0}
    elif attack == "count_omitted": c["frontier"].pop()
    elif attack == "count_duplicate": c["frontier"][2]["fittings"] = 1
    elif attack == "scope": c["limitations"]["native_IFC_candidate_acceptance_authority"] = True
    elif attack == "domain": c["count_domain"]["maximum"] = 3
    elif attack == "graph": c["graph_root"] = "0" * 64
    else: c["objective"]["fitting_weight"] = "10"
    checked = frontier.verify_fabrication_frontier(problem(), objective(), 4, reroot(c))
    assert checked["status"] == "FAIL", checked


def test_omitted_leaf_with_repaired_parent_indexes_is_caught_by_full_edge_closure(proof):
    c = deepcopy(proof)
    on_paths = {tuple(s) for row in c["frontier"] for s in row["path_states"]}
    parents = {row["parent"] for row in c["states"]}
    removed = next(i for i, row in enumerate(c["states"]) if i and i not in parents and tuple(row["state"]) not in on_paths)
    c["states"].pop(removed)
    for row in c["states"]:
        if row["parent"] is not None and row["parent"] > removed:
            row["parent"] -= 1
    checked = frontier.verify_fabrication_frontier(problem(), objective(), 4, reroot(c))
    assert checked["status"] == "FAIL" and "closure omits" in checked["reason"]


def test_zero_lower_labels_cannot_omit_actual_terminal_cost():
    p = problem(goal=[4, 0, 1])
    c, _ = certified(p, k=0)
    c["frontier"][0]["cost"] = ["0", "0"]
    assert all(row["potential"] == "0" for row in c["states"])
    checked = frontier.verify_fabrication_frontier(p, objective(), 0, reroot(c))
    assert checked["status"] == "FAIL" and "terminal debt" in checked["reason"]


def test_checker_reconstructs_without_any_producer_search_cost_or_point_helper(proof, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Producer invoked during independent verification")
    monkeypatch.setattr(frontier, "compile_fabrication_frontier", forbidden)
    monkeypatch.setattr(frontier, "_producer_edges", forbidden)
    monkeypatch.setattr(frontier, "_points", forbidden)
    monkeypatch.setattr(graph, "_producer_successors", forbidden)
    assert frontier.verify_fabrication_frontier(problem(), objective(), 4, proof)["status"] == "PASS"


@pytest.mark.parametrize("budget", [{"max_states": 30}, {"max_work": 200}, {"max_certificate_bytes": 1024}])
def test_partial_computation_never_labels_remaining_counts_unreachable(budget):
    result = frontier.compile_fabrication_frontier(problem(), objective(), 6, **budget)
    assert result["status"] == "UNKNOWN" and not result["proof_complete"]
    assert "frontier" not in result and "states" not in result
    assert frontier.verify_fabrication_frontier(problem(), objective(), 6, result)["status"] == "UNKNOWN"


def test_checker_budgets_are_its_own_and_do_not_trust_producer_work(proof):
    c = deepcopy(proof); c["producer_work"] = 0; reroot(c)
    assert frontier.verify_fabrication_frontier(problem(), objective(), 4, c, max_work=200)["status"] == "UNKNOWN"
    assert frontier.verify_fabrication_frontier(problem(), objective(), 4, c, max_states=10)["status"] == "UNKNOWN"


@pytest.mark.parametrize("maximum", [-1, 33, True, 1.5, "3", 10**1000])
def test_count_domain_is_bounded_before_graph_parsing(maximum, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Graph parsed before count budget was checked")
    monkeypatch.setattr(graph, "_prepare", forbidden)
    with pytest.raises(ValueError):
        frontier.compile_fabrication_frontier(problem(), objective(), maximum)
    assert frontier.verify_fabrication_frontier(problem(), objective(), maximum, {})["status"] == "FAIL"


def test_oversized_proof_is_rejected_before_any_cost_fraction_allocation(proof, monkeypatch):
    c = deepcopy(proof)
    for row in c["states"]:
        row["potential"] = "9" * 3500
    reroot(c)
    def forbidden(*args, **kwargs):
        raise AssertionError("Cost Fraction allocated before full proof byte bound")
    monkeypatch.setattr(frontier, "_rational_cost", forbidden)
    checked = frontier.verify_fabrication_frontier(problem(), objective(), 4, c, max_certificate_bytes=4096)
    assert checked["status"] == "UNKNOWN" and checked["reason"] == "CERTIFICATE_BYTE_BUDGET"


def test_streamed_root_matches_store_canonical_digest_and_exact_byte_limit(proof):
    payload = {k: v for k, v in proof.items() if k != "certificate_root"}
    size = len(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8"))
    assert frontier.verify_fabrication_frontier(problem(), objective(), 4, proof, max_certificate_bytes=size)["status"] == "PASS"
    checked = frontier.verify_fabrication_frontier(problem(), objective(), 4, proof, max_certificate_bytes=size - 1)
    assert checked["status"] == "UNKNOWN" and checked["reason"] == "CERTIFICATE_BYTE_BUDGET"
    assert digest(payload) == proof["certificate_root"]


@pytest.mark.parametrize("stage,checker", [("fabrication_frontier_expand", False), ("fabrication_frontier_hash", False),
    ("fabrication_frontier_complete", False), ("fabrication_frontier_closure_verify", True),
    ("fabrication_frontier_hash", True), ("fabrication_frontier_verified", True)])
@pytest.mark.parametrize("exception_type", [ValueError, TimeoutError, graph._Exhausted])
def test_cancellation_identity_survives_expansion_verification_and_serialization(proof, stage, checker, exception_type):
    signal = exception_type("intentional caller cancellation")
    calls = 0
    def checkpoint(observed):
        nonlocal calls
        if observed == stage:
            calls += 1
            if calls >= (3 if stage == "fabrication_frontier_hash" else 1):
                raise signal
    with pytest.raises(exception_type) as caught:
        if checker:
            frontier.verify_fabrication_frontier(problem(), objective(), 4, proof, checkpoint=checkpoint)
        else:
            frontier.compile_fabrication_frontier(problem(), objective(), 4, checkpoint=checkpoint)
    assert caught.value is signal


def native_frontier_wall_case(directory):
    from oma.ifc.audit import sha256_file
    from oma.ifc.cad import cad_check_routes
    from oma.ifc.export import export_route
    from oma.routing.checker import _semantics
    from oma.routing.scenario import RoutingScenario
    from test_ifc_pipeline import make_fixture
    from test_optimization_fabrication import actual_ifc_correspondence
    directory.mkdir(parents=True, exist_ok=True)
    source = make_fixture(directory / "source.ifc")
    before = sha256_file(source)
    p = problem(allowed_bounds=[[-2, -2, -1], [4, 4, 3]], grid_axes=[[-1, 0, 1, 2, 3], [-1, 0, 1, 2, 3], ["1/2", 1]],
        start=[-1, 1, 1], goal=[3, 1, 1], source_roots={"source_bytes": before, "outer_cover": "ANALYTIC_INTEGER_BOX_0_TO_2_METRES"},
        outer_obstacles=[{"id": "actual-analytic-wall", "bounds": [[0, 0, 0], [2, 2, 2]]}])
    o = objective("1", "1/5")
    c, v = certified(p, o, 3)
    row = c["frontier"][2]
    assert row["status"] == "OPTIMAL_PATH"
    exact = check_path_with_separate_fixed_fabrication_kernel(p, row)
    points = [[float(Q(x)) for x in point] for point in row["points_m"]]
    scenario = RoutingScenario(start=points[0], end=points[-1], system_type="PRESSURE_PIPE", diameter_m=.25,
        insulation_m=0, bend_radius_m=.5, minimum_straight_m=.125, clearance_m=.125,
        allowed_zone={"min": p["allowed_bounds"][0], "max": p["allowed_bounds"][1]}, scenario_terminals=True)
    spec = {"route_id": "frontier-native-wall", "points_m": points, "system_type": scenario.system_type,
        "diameter_m": scenario.diameter_m, "insulation_m": scenario.insulation_m, "bend_radius_m": scenario.bend_radius_m,
        "minimum_straight_m": scenario.minimum_straight_m, "assumption_root": digest(scenario.model_dump(mode="json"))}
    output = directory / "route.ifc"
    manifest = export_route(source, output, spec, fresh_recheck=False)
    correspondence = actual_ifc_correspondence(output, manifest, exact)
    physical = cad_check_routes([source], output, {part["ifc_guid"] for part in manifest["added_parts"]}, clearance_m=scenario.clearance_m)
    semantics = _semantics(output, source, manifest, scenario)
    assert semantics["errors"] == [] and semantics["fitting_count"] == row["fittings"] == 2
    assert physical["coordination_status"] == physical["self_interference_status"] == "PASS", physical
    assert physical["obstacle_count"] == 1 and physical["pairs_accounted"] == len(manifest["added_parts"]) == 5
    assert sha256_file(source) == before
    return {"scope": "EXACT_COUNT_FINITE_FRONTIER_AND_SEPARATE_NATIVE_TWO_ELBOW_WALL_DETOUR",
        "model": p, "objective": o, "certificate": c, "independent_check": v,
        "chosen_exact_fittings": 2, "actual_native_correspondence": correspondence,
        "actual_native_coordination": physical, "actual_semantics": semantics,
        "source_sha256": before, "export_sha256": sha256_file(output), "original_source_unchanged": True,
        "candidate_accepted": False, "native_objective_optimality": False, "continuous_optimality": False}


def test_actual_ifc_two_fitting_frontier_path_has_native_correspondence(tmp_path):
    from oma.ifc.audit import atomic_json
    result = native_frontier_wall_case(tmp_path)
    assert result["actual_native_correspondence"]["status"] == "PASS"
    atomic_json(tmp_path / "checked-frontier.json", result)
