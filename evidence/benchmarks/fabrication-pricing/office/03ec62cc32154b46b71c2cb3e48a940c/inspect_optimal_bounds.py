"""Compare OCCT bound algorithms without altering native shapes or acceptance."""
from fractions import Fraction
import json
import math
from pathlib import Path
import time

from OCP.Bnd import Bnd_Box
from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
from OCP.BRepBndLib import BRepBndLib
from OCP.BRepClass import BRepClass_FaceClassifier
from OCP.BRepTools import BRepTools
from OCP.TopAbs import TopAbs_FACE, TopAbs_EDGE, TopAbs_VERTEX, TopAbs_IN, TopAbs_ON
from OCP.TopoDS import TopoDS
from OCP.gp import gp_Pnt2d

from oma.build_identity import checker_version
from oma.ifc.audit import atomic_json, sha256_file
from oma.ifc.cad import load_cad, _transform_object, _subshapes
from oma.routing.scenario import RoutingScenario
from oma.store import Store, utcnow


ROOT = Path(__file__).resolve().parents[5]
EXPECTED = "ebe15db28b384f99ffe9c19f8cfe9d16128d424b829250d75d5251372836e219"
assert checker_version().endswith(EXPECTED)
started = time.monotonic()
store = Store(ROOT/".oma")
candidate = store.candidate("dc1cdd0d98e14838897f60dc0e3796ff")
scenario = RoutingScenario.model_validate(store.run(candidate["run_id"])["request"]["mission"])
report = store.get(candidate["proposal_evidence"]["report_root"])["report"]
nominal = report["priced_binary64_fabrication_certificate"]["components"]
material = store.get(candidate["routes"][0]["geometry_artifact"])
path = store.resolve_path(material["export_path"])
assert sha256_file(path) == material["export_sha256"]
parts = {part["ifc_guid"]:part for part in material["added_parts"]}
solids,errors = load_cad(path,guids=set(parts))
matrix = material.get("route_spec",{}).get("source_to_federation_matrix")
if matrix:
    solids = [_transform_object(solid,matrix) for solid in solids]


def bound(shape,optimal,tolerance=True):
    box = Bnd_Box()
    if optimal:
        BRepBndLib.AddOptimal_s(shape,box,False,tolerance)
    else:
        BRepBndLib.Add_s(shape,box,False)
    assert not box.IsVoid() and not box.IsOpen()
    lo,hi = box.CornerMin(),box.CornerMax()
    return [lo.X(),lo.Y(),lo.Z(),hi.X(),hi.Y(),hi.Z()]


def coordinates(point):
    return [point.X(),point.Y(),point.Z()]


def sample_native(shape):
    points,faces,edges = [],[],[]
    for raw in _subshapes(shape,TopAbs_FACE).values():
        face = TopoDS.Face(raw)
        surface = BRepAdaptor_Surface(face,True)
        u0,u1,v0,v1 = BRepTools.UVBounds_s(face)
        assert all(math.isfinite(x) for x in (u0,u1,v0,v1))
        before = len(points)
        # Include endpoints and 1/4-period subdivisions when the native surface
        # is circular/toroidal, in addition to the complete uniform UV lattice.
        us = {u0+(u1-u0)*i/32 for i in range(33)}
        vs = {v0+(v1-v0)*i/32 for i in range(33)}
        for values,lo,hi in ((us,u0,u1),(vs,v0,v1)):
            if abs(lo)<100 and abs(hi)<100:
                values.update(k*math.pi/2 for k in range(-64,65) if lo<=k*math.pi/2<=hi)
        for u in sorted(us):
            for v in sorted(vs):
                state = BRepClass_FaceClassifier(face,gp_Pnt2d(u,v),1e-9).State()
                if state in (TopAbs_IN,TopAbs_ON):
                    points.append(coordinates(surface.Value(u,v)))
        faces.append({"surface_type":str(surface.GetType()),"uv_bounds":[u0,u1,v0,v1],
            "accepted_trimmed_face_samples":len(points)-before})
    for raw in _subshapes(shape,TopAbs_EDGE).values():
        edge = BRepAdaptor_Curve(TopoDS.Edge(raw))
        lo,hi = edge.FirstParameter(),edge.LastParameter()
        assert math.isfinite(lo) and math.isfinite(hi)
        parameters = {lo+(hi-lo)*i/64 for i in range(65)}
        if abs(lo)<100 and abs(hi)<100:
            parameters.update(k*math.pi/2 for k in range(-64,65) if lo<=k*math.pi/2<=hi)
        points.extend(coordinates(edge.Value(t)) for t in sorted(parameters))
        edges.append({"curve_type":str(edge.GetType()),"parameter_bounds":[lo,hi],"samples":len(parameters)})
    for raw in _subshapes(shape,TopAbs_VERTEX).values():
        points.append(coordinates(BRep_Tool.Pnt_s(TopoDS.Vertex(raw))))
    assert points
    extrema = [{"axis":axis,"min_point":min(points,key=lambda p:p[axis]),
        "max_point":max(points,key=lambda p:p[axis])} for axis in range(3)]
    bounds = [min(p[i] for p in points) for i in range(3)]+[max(p[i] for p in points) for i in range(3)]
    return {"count":len(points),"bounds_m":bounds,"directional_extrema":extrema,"faces":faces,"edges":edges},points


records = []
for solid in sorted(solids,key=lambda s:parts[s.guid]["part_index"]):
    entry = parts[solid.guid]
    exact = nominal[entry["part_index"]]
    assert exact["kind"] == entry["kind"]
    for terminal in ("start","end"):
        assert all(abs(float(Fraction(x))-y)<1e-9 for x,y in zip(exact[terminal],entry["expected"][terminal]))
    ideal = [float(Fraction(x)) for row in exact["body_bounds_m"] for x in row]
    ordinary = bound(solid.shape,False)
    optimal = bound(solid.shape,True)
    optimal_without_tolerance = bound(solid.shape,True,False)
    sampled,points = sample_native(solid.shape)
    gaps = [optimal[i]-scenario.allowed_zone.min[i] for i in range(3)]+[scenario.allowed_zone.max[i]-optimal[i+3] for i in range(3)]
    records.append({"guid":solid.guid,"part_index":entry["part_index"],"kind":entry["kind"],
        "shape_valid":solid.valid,"kernel_tolerance_m":solid.kernel_tolerance_m,
        "add_bounds_m":ordinary,"add_optimal_with_shape_tolerance_bounds_m":optimal,
        "add_optimal_without_shape_tolerance_bounds_m":optimal_without_tolerance,
        "exact_nominal_primitive_bounds_rational":exact["body_bounds_m"],"nominal_bounds_as_binary64_m":ideal,
        "ordinary_outward_delta_from_nominal_m":[ideal[i]-ordinary[i] for i in range(3)]+[ordinary[i+3]-ideal[i+3] for i in range(3)],
        "optimal_outward_delta_from_nominal_m":[ideal[i]-optimal[i] for i in range(3)]+[optimal[i+3]-ideal[i+3] for i in range(3)],
        "optimal_zone_gaps_m":gaps,"minimum_optimal_zone_gap_m":min(gaps),
        "optimal_zone_status_with_unchanged_numerical_rule":"FAIL" if min(gaps)<0 else "UNKNOWN" if min(gaps)<=1e-6+solid.kernel_tolerance_m else "PASS",
        "samples":sampled,
        "sampled_points_outside_optimal_bounds":sum(not all(optimal[i]<=p[i]<=optimal[i+3] for i in range(3)) for p in points),
        "ordinary_matches_recorded_bounds":ordinary==list(solid.bounds)})
result = {"scope":"NUMERICAL_NATIVE_BREP_ENCLOSURE_DIAGNOSIS; SAMPLING_IS_CORROBORATION_NOT_ENCLOSURE_PROOF",
    "created_at":utcnow(),"checker_version":checker_version(),"candidate_id":candidate["id"],
    "candidate_status_unchanged":store.candidate(candidate["id"])["status"]==candidate["status"],
    "export_sha256":material["export_sha256"],"candidate_file_unchanged":sha256_file(path)==material["export_sha256"],
    "algorithms":{"ordinary":"BRepBndLib.Add_s(shape,box,False)","optimal":"BRepBndLib.AddOptimal_s(shape,box,False,True)",
        "optimal_api_doc":BRepBndLib.AddOptimal_s.__doc__,"native_sampling":"Trim-classified face UV lattice plus quarter-period parameters; edge lattice plus quarter periods; all vertices"},
    "load_errors":errors,"records":records,"elapsed_seconds":time.monotonic()-started,
    "candidate_acceptance_performed":False,"original_mission_modified":False}
atomic_json(Path(__file__).with_name("native-optimal-bounds-diagnosis.json"),result)
print(json.dumps({"scope":result["scope"],"elapsed_seconds":result["elapsed_seconds"],"records":[{k:r[k] for k in
    ("part_index","kind","kernel_tolerance_m","ordinary_outward_delta_from_nominal_m","optimal_outward_delta_from_nominal_m",
        "minimum_optimal_zone_gap_m","optimal_zone_status_with_unchanged_numerical_rule","sampled_points_outside_optimal_bounds")} for r in records]},indent=2))
