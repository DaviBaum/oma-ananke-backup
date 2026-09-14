from copy import deepcopy
from fractions import Fraction as Q
from itertools import product
import math

import numpy as np
import pytest

from oma.optimization import fabrication as fab
from oma.routing.scenario import RoutingScenario
from oma.store import digest


def scenario(points, **kwargs):
    data = dict(start=points[0],end=points[-1],system_type="PRESSURE_PIPE",diameter_m=.25,
        insulation_m=0.,bend_radius_m=.5,minimum_straight_m=.01,clearance_m=.1,
        allowed_zone={"min":[-5.,-5.,-5.],"max":[5.,5.,5.]},scenario_terminals=True)
    data.update(kwargs)
    return RoutingScenario(**data)


def compile_case(points, **kwargs):
    s = scenario(points,**kwargs)
    c = fab.compile_orthogonal_fabrication(s,points,context_root="fixed-case")
    v = fab.verify_orthogonal_fabrication(s,points,c,context_root="fixed-case")
    assert v["status"] == "PASS",v
    assert v["fabrication_status"] == c["status"]
    return s,c


def resign(cert):
    cert.pop("certificate_root",None)
    cert["certificate_root"] = digest(cert)


AXES = [tuple(sign*int(i==axis) for i in range(3)) for axis,sign in product(range(3),(-1,1))]
TURNS = [(u,v) for u in AXES for v in AXES if sum(a*b for a,b in zip(u,v))==0]


@pytest.mark.parametrize("incoming,outgoing",TURNS)
def test_all_24_signed_quarter_turns_have_exact_attained_body_bounds(incoming,outgoing):
    points = [tuple(-2*x for x in incoming),(0.,0.,0.),tuple(2*x for x in outgoing)]
    s,c = compile_case(points)
    assert c["status"] == "PASS"
    assert len(c["components"]) == 3 and len(c["transitions"]) == 1
    from oma.ifc.export import fillet_route
    actual_parts = fillet_route(points,s.bend_radius_m,s.minimum_straight_m)
    for exact,actual in zip(c["components"],actual_parts,strict=True):
        assert exact["kind"] == actual["kind"]
        for key in ("start","end","center","normal"):
            if key in exact:
                assert actual[key] == [float(Q(x)) for x in exact[key]]
    elbow = next(p for p in c["components"] if p["kind"]=="elbow")
    center = tuple(map(Q,elbow["center"]))
    normal = tuple(map(Q,elbow["normal"]))
    lower,upper = [tuple(map(Q,row)) for row in elbow["body_bounds_m"]]
    radius,R = Q(elbow["outer_radius_m"]),Q(elbow["bend_radius_m"])
    # Independent rational circle parametrization samples the continuous swept
    # disk, including both flat cap circles, with no trig/producer dependency.
    for step,cross_step,radial_sign,normal_sign in product(range(6),range(4),(-1,1),(-1,1)):
        t,h = Q(step,5),Q(cross_step,3)
        sine,cosine = 2*t/(1+t*t),(1-t*t)/(1+t*t)
        radial = radial_sign*radius*2*h/(1+h*h)
        transverse = normal_sign*radius*(1-h*h)/(1+h*h)
        position = [center[j]+(R+radial)*(incoming[j]*sine-outgoing[j]*cosine)+transverse*normal[j] for j in range(3)]
        assert all(a <= p <= b for a,p,b in zip(lower,position,upper))


def test_flat_cap_straight_does_not_add_axial_radius_or_clearance_to_body():
    points = [(0.,0.,0.),(2.,0.,0.)]
    _,c = compile_case(points,insulation_m=.125,clearance_m=.7)
    part = c["components"][0]
    assert part["body_bounds_m"] == [["0","-1/4","-1/4"],["2","1/4","1/4"]]
    assert c["manifest"]["outer_radius_m"] == "1/4"


@pytest.mark.parametrize("points,kwargs,code",[
    ([(-.5,0.,0.),(0.,0.,0.),(0.,.5,0.)],{"bend_radius_m":1.},"INSUFFICIENT_REMAINING_STRAIGHT"),
    ([(0.,0.,0.),(2.,0.,0.),(2.,.5,0.),(4.,.5,0.)],{"bend_radius_m":.3},"INSUFFICIENT_REMAINING_STRAIGHT"),
    ([(0.,0.,0.),(.5,0.,0.),(.5,.5,0.)],{"bend_radius_m":.25,"minimum_straight_m":.25},"INSUFFICIENT_REMAINING_STRAIGHT"),
    ([(0.,0.,0.),(2.,0.,0.),(1.,0.,0.)],{},"NO_TANGENT_QUARTER_BEND_FOR_UTURN"),
    ([(0.,0.,0.),(0.,0.,0.),(2.,0.,0.)],{},"ZERO_SEGMENT"),
])
def test_exact_fixed_realization_failures_are_independently_verified(points,kwargs,code):
    _,c = compile_case(points,**kwargs)
    assert c["status"] == "FAIL" and c["disposition"]["early"]["code"] == code
    assert c["components"] == []
    assert not c["limitations"]["physical_route_universe_infeasibility_claim"]


def test_one_binary_step_above_strict_straight_threshold_is_not_rounded_into_failure():
    length = math.nextafter(.5,math.inf)
    _,c = compile_case([(0.,0.,0.),(length,0.,0.),(length,length,0.)],bend_radius_m=.25,minimum_straight_m=.25)
    assert c["status"] == "PASS"
    assert Q(c["components"][0]["length_m"]) > Q(1,4)


@pytest.mark.parametrize("field,value",list(product(("bend_radius_m","minimum_straight_m"),(math.nan,math.inf,-math.inf,-.1))))
def test_writer_rejects_nonfinite_and_negative_dimensions_before_either_geometry_branch(field,value):
    from oma.ifc.export import fillet_route
    kwargs = {"bend_radius_m":.5,"minimum_straight_m":.01,field:value}
    for points in ([(0,0,0),(2,0,0),(2,2,0)],[(0,0,0),(2,1,0),(3,2,0)]):
        with pytest.raises(ValueError,match="Finite nonnegative fitting dimensions"):
            fillet_route(points,**kwargs)


def test_unimplemented_nonorthogonal_gravity_and_point_budget_are_unknown():
    points = [(0.,0.,0.),(2.,1.,0.)]
    _,c = compile_case(points)
    assert c["status"] == "UNKNOWN"
    points = [(0.,0.,1.),(0.,0.,0.)]
    _,c = compile_case(points,system_type="GRAVITY_DRAINAGE",min_slope=.01)
    assert c["status"] == "UNKNOWN"
    points = [(0.,0.,0.),(2.,0.,0.),(2.,2.,0.)]
    s = scenario(points)
    c = fab.compile_orthogonal_fabrication(s,points,context_root="budget",max_points=2)
    assert c["status"] == "UNKNOWN"
    assert fab.verify_orthogonal_fabrication(s,points,c,context_root="budget",max_points=2)["status"] == "PASS"


def test_overbudget_result_never_traverses_or_parses_uninspected_geometry():
    class Untraversable(list):
        def __iter__(self): raise AssertionError("Oversized input was traversed")
    points = Untraversable([object()]*10000)
    c = fab.compile_orthogonal_fabrication(object(),points,context_root="caller-bound",max_points=2)
    assert c["status"] == "UNKNOWN" and c["components"] == []
    assert c["manifest"]["input_binding"] == "COUNT_AND_EXTERNAL_CONTEXT_ONLY; GEOMETRY_INPUTS_UNINSPECTED"
    assert fab.verify_orthogonal_fabrication(object(),points,c,context_root="caller-bound",max_points=2)["status"] == "PASS"
    assert fab.verify_orthogonal_fabrication(object(),points,c,context_root="different",max_points=2)["status"] == "FAIL"
    assert fab.verify_orthogonal_fabrication(object(),points,c,context_root="caller-bound",max_points=3)["status"] == "FAIL"


@pytest.mark.parametrize("field,value",[("components",{}),("transitions",{}),("components",[{}]*20)])
def test_unknown_certificate_does_not_accept_untyped_or_oversized_empty_claims(field,value):
    points = [[0,0,0]]*3
    c = fab.compile_orthogonal_fabrication(None,points,context_root="count",max_points=2)
    c[field] = value
    resign(c)
    assert fab.verify_orthogonal_fabrication(None,points,c,context_root="count",max_points=2)["status"] == "FAIL"


def test_centerline_inside_zone_but_insulated_body_outside_is_exact_failure():
    points = [(0.,0.,0.),(2.,0.,0.),(2.,2.,0.),(0.,2.,0.)]
    _,c = compile_case(points,allowed_zone={"min":[-.2,-.2,-.2],"max":[2.05,2.2,.2]})
    # Both endpoint capsules fit; the intermediate vertical cylinder protrudes.
    assert c["status"] == "FAIL"


@pytest.mark.parametrize("fault",["missing_elbow","duplicate_component","wrong_center","normal_sign","shifted_equal_bounds",
    "smaller_body","axial_cap_extension","trim_debt","incoming_direction","wrong_size","wrong_scope","numeric_scope","boolean_index","false_status"])
def test_forged_rooted_transition_and_body_witnesses_fail(fault):
    points = [(0.,0.,0.),(2.,0.,0.),(2.,2.,0.)]
    s,c = compile_case(points)
    elbow = next(p for p in c["components"] if p["kind"]=="elbow")
    if fault == "missing_elbow": c["components"].remove(elbow)
    elif fault == "duplicate_component": c["components"].append(deepcopy(elbow))
    elif fault == "wrong_center": elbow["center"][0] = str(Q(elbow["center"][0])+1)
    elif fault == "normal_sign": elbow["normal"][2] = str(-Q(elbow["normal"][2]))
    elif fault == "shifted_equal_bounds":
        for row in elbow["body_bounds_m"]: row[0] = str(Q(row[0])+1)
    elif fault == "smaller_body": elbow["body_bounds_m"][1][0] = "2"
    elif fault == "axial_cap_extension": c["components"][0]["body_bounds_m"][0][0] = "-1/8"
    elif fault == "trim_debt": c["transitions"][0]["trim_debt_m"] = "0"
    elif fault == "incoming_direction": c["transitions"][0]["incoming"] = ["0","1","0"]
    elif fault == "wrong_size": elbow["outer_radius_m"] = "1/16"
    elif fault == "wrong_scope": c["limitations"]["candidate_acceptance_authority"] = True
    elif fault == "numeric_scope": c["limitations"]["candidate_acceptance_authority"] = 0
    elif fault == "boolean_index": elbow["index"] = True
    elif fault == "false_status": c["status"] = "FAIL"
    resign(c)
    assert fab.verify_orthogonal_fabrication(s,points,c,context_root="fixed-case")["status"] == "FAIL"


def test_outer_box_contact_is_unknown_never_claimed_collision_or_route_impossibility():
    points = [(0.,0.,0.),(2.,0.,0.),(2.,2.,0.)]
    s = scenario(points)
    for bounds,status in (([[10,10,10],[11,11,11]],"PASS"),([[1,0,0],[2,1,1]],"UNKNOWN")):
        boxes = [{"id":"declared-outer","bounds":bounds}]
        c = fab.compile_orthogonal_fabrication(s,points,context_root="outer",outer_obstacles=boxes,outer_model_root="authenticated-elsewhere")
        assert c["status"] == status
        checked = fab.verify_orthogonal_fabrication(s,points,c,context_root="outer",outer_obstacles=boxes,outer_model_root="authenticated-elsewhere")
        assert checked["status"] == "PASS" and checked["fabrication_status"] == status


def test_independent_verifier_never_calls_producer_or_its_body_bound_constructor(monkeypatch):
    points = [(0.,0.,0.),(2.,0.,0.),(2.,2.,0.)]
    s,c = compile_case(points)
    def forbidden(*args,**kwargs): raise AssertionError("producer was called")
    monkeypatch.setattr(fab,"compile_orthogonal_fabrication",forbidden)
    monkeypatch.setattr(fab,"_producer_bounds",forbidden)
    assert fab.verify_orthogonal_fabrication(s,points,c,context_root="fixed-case")["status"] == "PASS"


def expected_native_shape(part):
    """Independent analytic OCP primitives built from the checked certificate."""
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeTorus
    from OCP.gp import gp_Ax2,gp_Pnt,gp_Dir
    point = lambda key: np.array([float(Q(v)) for v in part[key]])
    radius = float(Q(part["outer_radius_m"]))
    if part["kind"] == "segment":
        start,end = point("start"),point("end")
        direction = end-start
        direction /= np.linalg.norm(direction)
        return BRepPrimAPI_MakeCylinder(gp_Ax2(gp_Pnt(*start),gp_Dir(*direction)),radius,float(Q(part["length_m"]))).Shape()
    center,normal = point("center"),point("normal")
    radial = -point("outgoing")
    return BRepPrimAPI_MakeTorus(gp_Ax2(gp_Pnt(*center),gp_Dir(*normal),gp_Dir(*radial)),
        float(Q(part["bend_radius_m"])),radius,math.pi/2).Shape()


def actual_ifc_correspondence(output,manifest,certificate):
    import ifcopenshell
    from oma.ifc.cad import load_cad
    from oma.ifc.network_semantics import read_component_geometry
    from oma.ifc.openings import _native_agreement
    model = ifcopenshell.open(str(output))
    guids = {p["ifc_guid"] for p in manifest["added_parts"]}
    objects,errors = load_cad(output,guids=guids)
    assert not errors and len(objects) == len(certificate["components"])
    native = {o.guid:o for o in objects}
    results = []
    for part,declared in zip(certificate["components"],manifest["added_parts"],strict=True):
        actual = read_component_geometry(model,model.by_guid(declared["ifc_guid"]))
        assert actual["kind"] == part["kind"]
        for key in ("start","end"):
            assert actual[key+"_m"] == pytest.approx([float(Q(v)) for v in part[key]],abs=1e-10)
        assert actual["radius_m"] == pytest.approx(float(Q(part["outer_radius_m"])),abs=1e-12)
        if part["kind"] == "elbow":
            assert actual["center_m"] == pytest.approx([float(Q(v)) for v in part["center"]],abs=1e-10)
            assert actual["normal"] == pytest.approx([float(Q(v)) for v in part["normal"]],abs=1e-10)
            expected_length = math.pi*float(Q(part["length_pi_m"]))
        else: expected_length = float(Q(part["length_m"]))
        expected_volume = math.pi*float(Q(part["outer_radius_m"]))**2*expected_length
        obj = native[declared["ifc_guid"]]
        assert obj.volume_m3 == pytest.approx(expected_volume,rel=1e-9,abs=1e-10)
        agreement = _native_agreement(obj,expected_native_shape(part))
        results.append({"ifc_guid":obj.guid,"kind":part["kind"],"index":part["index"],
            "analytic_volume_m3":expected_volume,"actual_source_geometry":actual,"native_agreement":agreement})
    return {"status":"PASS","scope":"NUMERICAL_IFC_REOPENED_PRIMITIVE_AND_SYMMETRIC_DIFFERENCE_CORRESPONDENCE; NOT_FORMAL_NATIVE_EQUALITY",
            "parts_checked":len(results),"parts":results,"whole_route_acceptance":False}


@pytest.mark.parametrize("schema",["IFC4","IFC2X3"])
@pytest.mark.parametrize("incoming,outgoing",[(AXES[1],AXES[3]),(AXES[2],AXES[5]),(AXES[4],AXES[0])])
def test_actual_ifc_straights_and_elbow_match_independent_exact_construction(tmp_path,schema,incoming,outgoing):
    from oma.ifc.export import export_route
    from test_ifc_openings import host_fixture
    points = [tuple(-2*x for x in incoming),(0.,0.,0.),tuple(2*x for x in outgoing)]
    s,c = compile_case(points,insulation_m=.0625)
    source,_ = host_fixture(tmp_path/"source.ifc",schema=schema)
    original = source.read_bytes()
    output = tmp_path/"route.ifc"
    manifest = export_route(source,output,{"route_id":"fabrication-correspondence","system_type":s.system_type,
        "points_m":points,"diameter_m":s.diameter_m,"insulation_m":s.insulation_m,"bend_radius_m":s.bend_radius_m,
        "minimum_straight_m":s.minimum_straight_m},fresh_recheck=False)
    assert actual_ifc_correspondence(output,manifest,c)["status"] == "PASS"
    assert source.read_bytes() == original


def actual_ifc_threshold_boundary(directory,schema):
    """Verify corrected equality rejection and actual next-float construction."""
    from oma.ifc.audit import sha256_file
    from oma.ifc.export import export_route,fillet_route
    from test_ifc_openings import host_fixture
    points = [(0.,0.,0.),(.75,0.,0.),(.75,.75,0.)]
    s,c = compile_case(points,minimum_straight_m=.25)
    assert c["status"] == "FAIL"
    assert c["disposition"]["early"]["available_m"] == "1/4"
    with pytest.raises(ValueError,match="exact orthogonal construction"):
        fillet_route(points,.5,.25)
    source,_ = host_fixture(directory/(schema+"-threshold-source.ifc"),schema=schema)
    original_hash = sha256_file(source)
    output = directory/(schema+"-threshold-route.ifc")
    spec = {"route_id":"strict-threshold-corrected-boundary","system_type":s.system_type,
        "points_m":points,"diameter_m":s.diameter_m,"insulation_m":s.insulation_m,
        "bend_radius_m":s.bend_radius_m,"minimum_straight_m":s.minimum_straight_m}
    with pytest.raises(ValueError,match="exact orthogonal construction"):
        export_route(source,output,spec,fresh_recheck=False)
    assert not output.exists()
    larger = math.nextafter(.75,math.inf)
    near_points = [(0.,0.,0.),(larger,0.,0.),(larger,larger,0.)]
    _,near_certificate = compile_case(near_points,minimum_straight_m=.25)
    assert near_certificate["status"] == "PASS"
    spec["points_m"] = near_points
    manifest = export_route(source,output,spec,fresh_recheck=False)
    actual = actual_ifc_correspondence(output,manifest,near_certificate)
    assert sha256_file(source) == original_hash
    return {"schema":schema,"scope":"EXACT_SOURCE_AXIS_STRICT_PREDICATE_CORRECTION_WITH_NUMERICAL_NATIVE_CORRESPONDENCE",
        "points_m":points,"bend_radius_m":.5,"minimum_straight_m":.25,
        "exact_equality_certificate":c,"writer_rejected_equality":True,
        "next_float_points_m":near_points,"next_float_certificate":near_certificate,
        "next_float_native_correspondence":actual,
        "source_sha256":original_hash,"export_sha256":sha256_file(output),
        "candidate_acceptance_checked":False,"automatic_pruning_authority":False,
        "legacy_numerical_counterexample":"evidence/math/fabrication/attempts/92c8f7d0b95a456e89f4787bec2a3310"}


@pytest.mark.parametrize("schema",["IFC4","IFC2X3"])
def test_actual_ifc_corrected_strict_boundary_rejects_equality_and_constructs_next_float(tmp_path,schema):
    result = actual_ifc_threshold_boundary(tmp_path,schema)
    assert result["writer_rejected_equality"] and result["next_float_native_correspondence"]["status"]=="PASS"
