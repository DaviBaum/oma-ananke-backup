from copy import deepcopy
from fractions import Fraction as Q
from itertools import product
import json
import random

import pytest

from oma.optimization import route_cells as cells


def problem():
    return {"allowed_bounds": [[0, 0, 0], [10, 10, 10]], "body_radius": 1, "clearance": 0,
        "outer_obstacles": [], "inner_obstacles": [], "grid_axes": [[1, 5, 9]] * 3,
        "start": [2, 5, 5], "goal": [8, 5, 5], "context_root": "immutable-geometry-model",
        "source_roots": {"outer_cover": "complete-outer-cover", "inner_occupancy": "occupied-inner-proof",
                         "frame": "local-frame", "body_model": "translating-ball"}}


def add_obstacle(p, bounds, name="obstacle", *, occupied=True):
    p["outer_obstacles"].append({"id": name, "bounds": bounds})
    if occupied:
        p["inner_obstacles"].append({"id": name + ":inner", "bounds": deepcopy(bounds), "outer_id": name})


def wall_problem(*, occupied=True):
    p = problem()
    add_obstacle(p, [[4, 0, 0], [6, 10, 10]], occupied=occupied)
    p["grid_axes"] = [[1, 3, 4, 6, 7, 9], [1, 5, 9], [1, 5, 9]]
    return p


def compile_check(p):
    certificate = cells.compile_route_cells(p)
    assert certificate["status"] == cells.STATUS
    result = cells.verify_route_cells(p, json.loads(json.dumps(certificate)))
    assert result["status"] == "PASS", result
    return certificate, result


def test_empty_obstacle_model_has_complete_inner_path_and_length_bounds():
    p = problem()
    certificate, result = compile_check(p)
    assert certificate["geometry_outcome"] == "INNER_PATH_CHECKED"
    assert result["verified_cells"] == result["free_cells"] == 8
    assert certificate["length_bounds"]["universal_centreline_length_lower_bound_m"] == "6"
    assert certificate["length_bounds"]["inner_path_length_upper_bound_m"] == "6"
    assert all(v is False for v in result["limitations"].values())


def test_actual_occupied_wall_has_checked_continuous_model_impossibility():
    certificate, result = compile_check(wall_problem())
    assert certificate["geometry_outcome"] == "OUTER_INFEASIBLE"
    assert certificate["outer_connectivity"]["kind"] == "CUT"
    assert result["verified_cells"] == 20
    assert result["outer_retained_cells"] == 8
    assert certificate["inner_path"] is None
    assert certificate["length_bounds"]["inner_path_length_upper_bound_m"] is None


def test_an_outer_bounding_box_alone_cannot_prove_a_wall_exists():
    certificate, result = compile_check(wall_problem(occupied=False))
    assert certificate["geometry_outcome"] == "UNKNOWN"
    assert certificate["outer_connectivity"]["kind"] == "PATH"
    assert result["outer_retained_cells"] == 20
    assert all(c["classification"] != "BLOCKED" for c in certificate["cells"])


def test_coarse_grid_and_no_inner_path_do_not_mean_infeasibility():
    p = problem()
    add_obstacle(p, [[4, 4, 0], [6, 6, 10]])
    p["grid_axes"] = [[1, 9]] * 3
    certificate, result = compile_check(p)
    assert certificate["geometry_outcome"] == "UNKNOWN"
    assert result["outer_retained_cells"] == 1
    assert certificate["cells"][0]["classification"] == "MIXED"
    # Ground-truth ball path exists at y=2, but this inner grid does not find it.
    assert cells._embedding_clear(cells._prepare(p, 2048, cells._Budget(1000)),
        [(Q(2), Q(5), Q(5)), (Q(2), Q(2), Q(5)), (Q(8), Q(2), Q(5)), (Q(8), Q(5), Q(5))], cells._Budget(1000))


def test_refined_free_cells_construct_a_real_full_body_detour():
    p = problem()
    add_obstacle(p, [[4, 4, 0], [6, 6, 10]])
    p["grid_axes"] = [[1, 2, "5/2", "15/2", 8, 9], [1, 2, "5/2", "15/2", 8, 9], [1, 5, 9]]
    certificate, _ = compile_check(p)
    assert certificate["geometry_outcome"] == "INNER_PATH_CHECKED"
    assert len(certificate["inner_path"]) > 2
    assert Q(certificate["length_bounds"]["inner_path_length_upper_bound_m"]) > 6
    # No claim that this finite detour is globally shortest.
    assert certificate["limitations"]["continuous_cost_optimality_claimed"] is False


def test_diagonal_euclidean_clearance_is_not_l_infinity_blocking():
    p = problem()
    p.update(allowed_bounds=[[-2, -2, -2], [4, 4, 4]],
             grid_axes=[[-1, "9/5", 2, 3], [-1, "9/5", 2, 3], [-1, "1/4", "3/4", 3]],
             start=["19/10", "19/10", "1/2"], goal=["19/10", "19/10", "1/2"])
    add_obstacle(p, [[0, 0, 0], [1, 1, 1]])
    certificate, _ = compile_check(p)
    selected = next(c for c in certificate["cells"] if c["id"] == "1:1:1")
    assert selected["classification"] == "FREE"
    assert certificate["geometry_outcome"] == "INNER_PATH_CHECKED"
    # Every transverse coordinate is below the incorrectly expanded upper face2.
    # True minimum squared Euclidean gap is 2*(4/5)^2 = 32/25 > radius^2.
    assert Q(32, 25) > 1


def test_different_occupied_boxes_cannot_collectively_cover_only_corners():
    p = problem()
    p.update(allowed_bounds=[[0, 0, 0], [1, 1, 1]], body_radius=0, grid_axes=[[0, 1]] * 3,
             start=["1/2"] * 3, goal=["1/2"] * 3)
    add_obstacle(p, [[0, 0, 0], [1, 1, 1]], occupied=False)
    for i, corner in enumerate(product((0, 1), repeat=3)):
        p["inner_obstacles"].append({"id": str(i), "bounds": [list(corner)] * 2, "outer_id": "obstacle"})
    certificate, _ = compile_check(p)
    assert certificate["cells"][0]["classification"] == "MIXED"
    certificate["cells"][0] = {"id": "0:0:0", "classification": "BLOCKED",
        "cover": {"inner_id": "0", "corner_occupied_points": [list(c) for c in product((0, 1), repeat=3)]}}
    assert cells.verify_route_cells(p, certificate)["status"] == "FAIL"


def test_verifier_does_not_repeat_compiler_or_connectivity_search(monkeypatch):
    p = wall_problem()
    certificate = cells.compile_route_cells(p)
    def forbidden(*a, **k):
        raise AssertionError("Producer/search called by checker")
    monkeypatch.setattr(cells, "compile_route_cells", forbidden)
    monkeypatch.setattr(cells, "_find_path", forbidden)
    assert cells.verify_route_cells(p, certificate)["status"] == "PASS"


@pytest.mark.parametrize("attack", ["missing_cell", "duplicate_cell", "empty_cut", "cut_goal", "fake_free", "wrong_inner", "bad_corner", "omit_corner", "fake_infeasible"])
def test_adversarial_cell_coverage_and_outer_cut(attack):
    p = wall_problem()
    certificate = cells.compile_route_cells(p)
    blocked = next(c for c in certificate["cells"] if c["classification"] == "BLOCKED")
    if attack == "missing_cell":
        certificate["cells"].pop()
    elif attack == "duplicate_cell":
        certificate["cells"][-1] = deepcopy(certificate["cells"][0])
    elif attack == "empty_cut":
        certificate["outer_connectivity"]["reachable"] = []
    elif attack == "cut_goal":
        certificate["outer_connectivity"]["reachable"].append("4:0:0")
    elif attack == "fake_free":
        blocked.clear()
        blocked.update(id="2:0:0", classification="FREE", separating_planes=[{"outer_id": "obstacle", "normal": [1, 0, 0]}])
    elif attack == "wrong_inner":
        blocked["cover"]["inner_id"] = "outer-box-is-not-inner-proof"
    elif attack == "bad_corner":
        blocked["cover"]["corner_occupied_points"][0] = [100, 100, 100]
    elif attack == "omit_corner":
        blocked["cover"]["corner_occupied_points"].pop()
    elif attack == "fake_infeasible":
        p = wall_problem(occupied=False)
        certificate = cells.compile_route_cells(p)
        certificate["geometry_outcome"] = "OUTER_INFEASIBLE"
    assert cells.verify_route_cells(p, certificate)["status"] == "FAIL"


def test_cut_must_be_closed_under_every_retained_diagonal_incidence():
    p = problem()
    certificate = cells.compile_route_cells(p)
    certificate["inner_path"] = None
    certificate["length_bounds"]["inner_segment_length_intervals_m"] = []
    certificate["length_bounds"]["inner_path_length_upper_bound_m"] = None
    certificate["geometry_outcome"] = "OUTER_INFEASIBLE"
    certificate["outer_connectivity"] = {"kind": "CUT", "reachable": ["0:0:0", "0:0:1", "0:1:0", "0:1:1"]}
    result = cells.verify_route_cells(p, certificate)
    assert result["status"] == "FAIL"
    assert "closed under" in result["reason"]


@pytest.mark.parametrize("attack", ["zero_plane", "reverse_plane", "missing_plane", "unsafe_path", "radius", "root", "boolean_scope", "lower_bound", "upper_bound", "interval"])
def test_adversarial_embedding_support_and_cost(attack):
    p = problem()
    add_obstacle(p, [[4, 0, 0], [6, 2, 10]])
    p["grid_axes"] = [[1, 3, 7, 9], [1, 4, 9], [1, 5, 9]]
    certificate, _ = compile_check(p)
    assert certificate["geometry_outcome"] == "INNER_PATH_CHECKED"
    free = next(c for c in certificate["cells"] if c["classification"] == "FREE")
    if attack == "zero_plane":
        free["separating_planes"][0]["normal"] = [0, 0, 0]
    elif attack == "reverse_plane":
        free["separating_planes"][0]["normal"] = [-Q(x) for x in free["separating_planes"][0]["normal"]]
    elif attack == "missing_plane":
        free["separating_planes"] = []
    elif attack == "unsafe_path":
        certificate["inner_path"] = [p["start"], [5, 1, 5], p["goal"]]
    elif attack == "radius":
        certificate["manifest"]["body_radius"] = "0"
    elif attack == "root":
        certificate["root"] = "different"
    elif attack == "boolean_scope":
        certificate["limitations"]["native_IFC_candidate_acceptance_authority"] = 0
    elif attack == "lower_bound":
        certificate["length_bounds"]["universal_centreline_length_lower_bound_m"] = "7"
    elif attack == "upper_bound":
        certificate["length_bounds"]["inner_path_length_upper_bound_m"] = "0"
    elif attack == "interval":
        certificate["length_bounds"]["inner_segment_length_intervals_m"][0] = ["0", "1"]
    assert cells.verify_route_cells(p, certificate)["status"] == "FAIL"


@pytest.mark.parametrize("field", ["outer_cover", "inner_occupancy", "frame", "body_model"])
def test_each_applicability_root_is_bound(field):
    p = problem()
    certificate = cells.compile_route_cells(p)
    p["source_roots"][field] = "changed"
    assert cells.verify_route_cells(p, certificate)["status"] == "FAIL"


@pytest.mark.parametrize("attack", ["axis_hole", "axis_reverse", "radius_negative", "nan", "outside_endpoint", "duplicate_obstacle", "inner_outside", "missing_parent", "extra_field", "missing_root"])
def test_invalid_or_incomplete_model_is_rejected(attack):
    p = wall_problem()
    if attack == "axis_hole":
        p["grid_axes"][0] = [2, 3, 4, 6, 7, 9]
    elif attack == "axis_reverse":
        p["grid_axes"][0] = [1, 4, 3, 9]
    elif attack == "radius_negative":
        p["body_radius"] = -1
    elif attack == "nan":
        p["clearance"] = float("nan")
    elif attack == "outside_endpoint":
        p["start"] = [0, 5, 5]
    elif attack == "duplicate_obstacle":
        p["outer_obstacles"].append(deepcopy(p["outer_obstacles"][0]))
    elif attack == "inner_outside":
        p["inner_obstacles"][0]["bounds"][0][0] = 3
    elif attack == "missing_parent":
        p["inner_obstacles"][0]["outer_id"] = "missing"
    elif attack == "extra_field":
        p["assumed_feasible"] = True
    elif attack == "missing_root":
        p["source_roots"].pop("inner_occupancy")
    with pytest.raises(ValueError):
        cells.compile_route_cells(p)


def test_budget_returns_unknown_without_a_partial_exact_claim():
    p = wall_problem()
    assert cells.compile_route_cells(p, max_cells=1)["status"] == "UNKNOWN"
    assert cells.compile_route_cells(p, max_work=0)["status"] == "UNKNOWN"
    certificate = cells.compile_route_cells(p)
    assert cells.verify_route_cells(p, certificate, max_work=0)["status"] == "UNKNOWN"


def test_zero_length_path_still_checks_body_and_boundary_contact():
    p = problem()
    p["goal"] = p["start"] = [1, 5, 5]
    certificate, _ = compile_check(p)
    assert certificate["inner_path"] == [["1", "5", "5"]]
    assert certificate["length_bounds"]["inner_path_length_upper_bound_m"] == "0"
    add_obstacle(p, [[2, 0, 0], [3, 10, 10]])
    certificate, _ = compile_check(p)
    assert certificate["inner_path"] is None  # Strict obstacle contact forbidden.


def test_input_is_immutable_and_obstacle_row_order_is_not_identity():
    p = problem()
    add_obstacle(p, [[1, 0, 0], [2, 1, 10]], "first")
    add_obstacle(p, [[7, 0, 0], [8, 1, 10]], "second")
    before = deepcopy(p)
    certificate = cells.compile_route_cells(p)
    assert p == before
    p["outer_obstacles"].reverse()
    p["inner_obstacles"].reverse()
    assert cells.verify_route_cells(p, certificate)["status"] == "PASS"


def test_thirty_random_walls_match_analytic_intermediate_value_obstruction():
    rng = random.Random(91283)
    for _ in range(30):
        axis, a, b = rng.randrange(3), rng.randrange(3, 5), rng.randrange(6, 8)
        p = problem()
        p["body_radius"] = "1/2"
        p["grid_axes"] = [[Q(1, 2), Q(19, 2)] for _ in range(3)]
        p["grid_axes"][axis] = [Q(1, 2), Q(2 * a - 1, 2), a, b, Q(2 * b + 1, 2), Q(19, 2)]
        p["start"], p["goal"] = [5] * 3, [5] * 3
        p["start"][axis], p["goal"][axis] = 1, 9
        lo, hi = [0] * 3, [10] * 3
        lo[axis], hi[axis] = a, b
        add_obstacle(p, [lo, hi])
        certificate, _ = compile_check(p)
        # Every continuous path from coordinate1 to9 crosses coordinate(a+b)/2,
        # where this full transverse wall occupies all allowed other coordinates.
        assert certificate["geometry_outcome"] == "OUTER_INFEASIBLE"


def test_nested_refinement_can_certify_impossibility_without_changing_model():
    coarse = wall_problem()
    coarse["grid_axes"] = [[1, 9]] * 3
    fine = wall_problem()
    before, after = cells.compile_route_cells(coarse), cells.compile_route_cells(fine)
    assert before["geometry_outcome"] == "UNKNOWN"
    assert after["geometry_outcome"] == "OUTER_INFEASIBLE"
    result = cells.verify_route_cell_refinement(coarse, before, fine, after)
    assert result["status"] == "PASS"
    assert result["termination_or_boundary_resolution_proved"] is False


def test_changed_obstacle_model_is_not_relabelled_as_refinement():
    coarse, fine = wall_problem(), wall_problem()
    fine["inner_obstacles"] = []
    result = cells.verify_route_cell_refinement(coarse, cells.compile_route_cells(coarse), fine, cells.compile_route_cells(fine))
    assert result["status"] == "FAIL"
    assert "Changed geometry" in result["reason"]


def test_non_nested_cell_grid_is_not_a_refinement():
    coarse = problem()
    fine = problem()
    fine["grid_axes"] = [[1, 4, 9]] * 3
    result = cells.verify_route_cell_refinement(coarse, cells.compile_route_cells(coarse), fine, cells.compile_route_cells(fine))
    assert result["status"] == "FAIL"
    assert "coarse boundary" in result["reason"]


def test_refinement_cannot_discard_previously_certified_free_region():
    coarse, fine = problem(), problem()
    fine["grid_axes"] = [[1, 3, 5, 7, 9]] * 3
    before, after = cells.compile_route_cells(coarse), cells.compile_route_cells(fine)
    first = after["cells"][0]
    after["cells"][0] = {"id": first["id"], "classification": "MIXED"}
    assert cells.verify_route_cells(fine, after)["status"] == "PASS"  # Safe but weaker standalone certificate.
    result = cells.verify_route_cell_refinement(coarse, before, fine, after)
    assert result["status"] == "FAIL"
    assert "loses a certified" in result["reason"]
