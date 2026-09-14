"""Full-body outer support cannot inherit a smaller model's omissions."""
from copy import deepcopy
from fractions import Fraction as Q

import pytest

from oma.routing.certified_fabrication import body_outer_coverage, verify_body_outer_coverage
from oma.routing.scenario import RoutingScenario


def scenario():
    return RoutingScenario(start=(1.,1.,1.),end=(3.,1.,1.),system_type="PRESSURE_PIPE",
        diameter_m=.1,insulation_m=.02,bend_radius_m=.3,minimum_straight_m=.05,
        clearance_m=.1,allowed_zone={"min":[0.,0.,0.],"max":[4.,4.,4.]},scenario_terminals=True)


def source_coverage():
    return {"blockers":[],"objects":[
        {"id":"near-a","bounds_m":[[2.,2.,2.],[2.2,2.2,2.2]]},
        {"id":"near-b","bounds_m":[[3.,2.,2.],[3.2,2.2,2.2]]},
        {"id":"far","bounds_m":[[5.,1.,1.],[6.,2.,2.]]},
    ]}


def test_complete_body_cover_retains_all_grouped_and_provably_omitted_support():
    source = source_coverage()
    original = deepcopy(source)
    result = body_outer_coverage(source,scenario(),1)
    checked = verify_body_outer_coverage(source,result)
    assert checked["status"] == "PASS"
    assert checked["loaded_obstacles"] == 3 and checked["outer_groups"] == 1
    assert checked["omitted_with_full_body_region_proof"] == 1
    assert source == original


@pytest.mark.parametrize("fault",["missing","extra","duplicate","shrunken_group","unreferenced_group","false_plane","changed_source","negative_clearance"])
def test_body_cover_rejects_missing_support_and_false_group_or_omission_claims(fault):
    source = source_coverage()
    result = body_outer_coverage(source,scenario(),1)
    if fault == "missing": result["entries"].pop()
    elif fault == "extra": result["entries"].append({"id":"phantom","disposition":"GROUPED","group_id":result["outer_obstacles"][0]["id"]})
    elif fault == "duplicate": result["entries"].append(deepcopy(result["entries"][0]))
    elif fault == "shrunken_group": result["outer_obstacles"][0]["bounds"][1][0] = "2"
    elif fault == "unreferenced_group": result["outer_obstacles"].append({"id":"phantom","bounds":[[0,0,0],[1,1,1]]})
    elif fault == "false_plane": next(e for e in result["entries"] if e["id"] == "far")["normal"] = [0,0,0]
    elif fault == "changed_source": source["objects"][0]["bounds_m"][1][0] = 4.
    elif fault == "negative_clearance": result["clearance_m"] = "-1"
    assert verify_body_outer_coverage(source,result)["status"] == "FAIL"


def test_ball_centre_domain_omission_is_not_reused_for_entire_body_region():
    from oma.routing.certified_cells import _plane
    s = scenario()
    corner = ((Q("-.061"),Q("-.061"),Q(1)),(Q("-.06"),Q("-.06"),Q(2)))
    rounded_radius = Q(s.outer_radius)
    eroded = ((rounded_radius,)*3,(Q(4)-rounded_radius,)*3)
    assert _plane(eroded,corner,rounded_radius+Q(s.clearance_m)) is not None
    source = {"blockers":[],"objects":[{"id":"corner","bounds_m":[list(map(str,row)) for row in corner]}]}
    result = body_outer_coverage(source,s,1)
    assert result["entries"][0]["disposition"] == "GROUPED"
    assert verify_body_outer_coverage(source,result)["status"] == "PASS"


def test_body_omission_requires_strict_clearance_at_the_boundary():
    s = scenario().model_copy(update={"clearance_m":.125})
    source = {"blockers":[],"objects":[{"id":"touch","bounds_m":[[4.125,1,1],[5,2,2]]}]}
    result = body_outer_coverage(source,s,1)
    assert result["entries"][0]["disposition"] == "GROUPED"


def test_source_bound_lifted_path_materializes_and_clears_actual_native_wall(tmp_path):
    import time
    import numpy as np
    from oma.ifc.audit import sha256_file
    from oma.ifc.cad import cad_check_routes
    from oma.ifc.export import export_route
    from oma.routing.certified_cells import build_certified_cell_proposals
    from oma.routing.certified_fabrication import build_certified_fabrication_proposals
    from oma.store import digest
    from test_ifc_pipeline import make_fixture

    source = make_fixture(tmp_path/"wall.ifc")
    source_hash = sha256_file(source)
    s = RoutingScenario(start=(-1.,1.,1.),end=(3.,1.,1.),system_type="PRESSURE_PIPE",
        diameter_m=.1,insulation_m=.02,bend_radius_m=.3,minimum_straight_m=.05,
        clearance_m=.1,allowed_zone={"min":[-2.,-2.,-2.],"max":[4.,4.,4.]},scenario_terminals=True)
    specs = [{"path":source,"sha256":source_hash,"transform_m":np.eye(4).tolist()}]
    cells = build_certified_cell_proposals(specs,s,context_root="fresh-native-wall",grid_divisions=6,deadline=time.monotonic()+30)
    assert cells["coverage_check"]["status"] == "PASS", cells
    lifted = build_certified_fabrication_proposals(specs,s,cells,context_root=digest({"source":source_hash,"scenario":s.model_dump(mode="json")}),
        deadline=time.monotonic()+30)
    assert lifted["status"] == "CHECKED_FABRICATION_PROPOSALS", {k:v for k,v in lifted.items() if k not in {"certificate","coverage","model"}}
    assert lifted["independent_check"]["geometry_outcome"] == "PATH"
    assert lifted["coverage_check"]["loaded_obstacles"] == 1
    assert lifted["binary64_fabrication_check"]["fabrication_status"] == "PASS"
    assert not lifted["candidate_acceptance_authority"] and not lifted["physical_infeasibility_claim"]
    points = lifted["proposals"][0]["points_m"]
    output = tmp_path/"route.ifc"
    material = export_route(source,output,{"route_id":"source-fabrication-path","points_m":points,
        "system_type":s.system_type,"diameter_m":s.diameter_m,"insulation_m":s.insulation_m,
        "bend_radius_m":s.bend_radius_m,"minimum_straight_m":s.minimum_straight_m},fresh_recheck=False)
    native = cad_check_routes([source],output,{p["ifc_guid"] for p in material["added_parts"]},clearance_m=s.clearance_m)
    assert native["status"] == "PASS", native
    assert sha256_file(source) == source_hash

    # The native support model cannot silently move to another input or frame.
    changed = deepcopy(cells)
    changed["coverage"]["objects"][0]["bounds_m"][0][0] = "999"
    rejected = build_certified_fabrication_proposals(specs,s,changed,context_root="tampered-report")
    assert rejected["status"] == "BLOCKED" and not rejected["proposals"]
    wrong_frame = deepcopy(specs)
    wrong_frame[0]["transform_m"][0][3] = 1.
    rejected = build_certified_fabrication_proposals(wrong_frame,s,cells,context_root="wrong-frame")
    assert rejected["status"] == "BLOCKED" and not rejected["proposals"]
    original_bytes = source.read_bytes()
    try:
        source.write_bytes(original_bytes+b"\n")
        rejected = build_certified_fabrication_proposals(specs,s,cells,context_root="changed-source")
        assert rejected["status"] == "BLOCKED" and not rejected["proposals"]
    finally:
        source.write_bytes(original_bytes)


def test_fabrication_model_deadline_and_cancel_preserve_inconclusive_state():
    import time
    from oma.routing.certified_fabrication import build_certified_fabrication_proposals
    from oma.worker import Cancelled
    result = build_certified_fabrication_proposals([],scenario(),{},context_root="deadline",deadline=time.monotonic()-1)
    assert result["status"] == "UNKNOWN" and not result["proposals"]
    assert result["reason"] == "FABRICATION_SEARCH_DEADLINE"
    def stop(_stage):
        raise Cancelled()
    with pytest.raises(Cancelled):
        build_certified_fabrication_proposals([],scenario(),{},context_root="cancelled",checkpoint=stop)
