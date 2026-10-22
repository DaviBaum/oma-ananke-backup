"""Grid provenance, bounded omission and callback adversaries."""
from copy import deepcopy

import pytest

from oma.optimization import fabrication_search as graph
from oma.routing import fabrication_grid as grid
from test_fabrication_grid import inputs, reroot


@pytest.mark.parametrize("attack",["swap_attribution","remove_addition_witness","double_addition_witness"])
def test_coincident_source_planes_require_exactly_one_addition_without_claiming_ranking(attack):
    args = inputs()
    args["outer_obstacles"].append({**deepcopy(args["outer_obstacles"][0]),"id":"second-real-source"})
    result = grid.enrich_fabrication_grid(**args)
    added = next(row for row in result["plane_records"] if row["disposition"] == "ADDED_COORDINATE")
    other = next(row for row in result["plane_records"] if row["axis"] == added["axis"]
        and row["value"] == added["value"] and row["disposition"] == "RETAINED_COORDINATE")
    if attack == "swap_attribution":
        added["disposition"],other["disposition"] = other["disposition"],added["disposition"]
    elif attack == "remove_addition_witness":
        added["disposition"] = "RETAINED_COORDINATE"
    else:
        other["disposition"] = "ADDED_COORDINATE"
    checked = grid.verify_fabrication_grid_enrichment(**args,result=reroot(result))
    if attack == "swap_attribution":
        assert checked["status"] == "PASS"
        assert checked["limitations"]["canonical_ranking_verified"] is False
        assert checked["source_planes_accounted"] == 12
    else:
        assert checked["status"] == "FAIL"


@pytest.mark.parametrize("change",["guard","same_geometry_different_source","first_turn_debt"])
def test_valid_other_input_grid_cannot_be_replayed_against_original_provenance(change):
    args = inputs()
    options = {"bend_radius_m":"1/2","minimum_straight_m":"1/4","guard_m":"1/1000000"}
    actual,modified = deepcopy(args),deepcopy(options)
    if change == "guard":
        modified["guard_m"] = "1/10000"
    elif change == "same_geometry_different_source":
        actual["outer_obstacles"][0]["id"] = "unrelated-source-identical-box"
    else:
        modified["bend_radius_m"] = "3/4"
    result = grid.enrich_fabrication_grid(**actual,**modified)
    assert grid.verify_fabrication_grid_enrichment(**actual,**modified,result=result)["status"] == "PASS"
    checked = grid.verify_fabrication_grid_enrichment(**args,**options,result=result)
    assert checked["status"] == "FAIL" and "differs" in checked["reason"]


def test_complete_grid_provenance_pass_does_not_imply_a_feasible_fabrication_path():
    args = inputs()
    args["outer_obstacles"] = [{"id":"complete-blocker","bounds":[[-1,-1,-1],[5,5,5]]}]
    result = grid.enrich_fabrication_grid(**args)
    checked = grid.verify_fabrication_grid_enrichment(**args,result=result)
    assert checked["status"] == "PASS"
    assert checked["limitations"]["free_space_or_route_certificate"] is False
    assert checked["limitations"]["native_acceptance_authority"] is False
    problem = {"schema":"oma.fabrication-grid-problem/1","context_root":"independent-blocked-model",
        "source_roots":{"declared_boxes":"complete-blocker"},"allowed_bounds":args["allowed_bounds"],
        "grid_axes":result["grid_axes"],"start":args["start"],"goal":args["goal"],
        "diameter_m":"1/4","insulation_m":"0","bend_radius_m":"1/2",
        "minimum_straight_m":"1/8","clearance_m":args["clearance_m"],"outer_obstacles":args["outer_obstacles"]}
    certificate = graph.compile_fabrication_search(problem)
    replay = graph.verify_fabrication_search(problem,certificate)
    assert replay["status"] == "PASS" and replay["geometry_outcome"] == "NO_PATH_IN_DECLARED_GRAPH"


@pytest.mark.parametrize("operation",["producer","verifier"])
@pytest.mark.parametrize("error_type",[graph._Exhausted,TimeoutError,ValueError])
def test_late_large_source_plane_traversal_cancellation_preserves_original_ledger(operation,error_type):
    args = inputs()
    args["outer_obstacles"] = [{"id":f"source:{i}","bounds":[[1,1,1],[3,3,3]]} for i in range(200)]
    before = deepcopy(args)
    result = grid.enrich_fabrication_grid(**args)
    assert len(result["plane_records"]) == 1200
    error = error_type("caller cancelled after more than one thousand ledger operations")
    hits = 0
    def checkpoint(stage):
        nonlocal hits
        if stage == "fabrication_graph_work":
            hits += 1
            if hits == 10:
                raise error
    with pytest.raises(error_type) as caught:
        if operation == "producer":
            grid.enrich_fabrication_grid(**args,checkpoint=checkpoint)
        else:
            grid.verify_fabrication_grid_enrichment(**args,result=result,checkpoint=checkpoint)
    assert caught.value is error and hits == 10 and args == before
    assert grid.verify_fabrication_grid_enrichment(**args,result=result)["status"] == "PASS"
