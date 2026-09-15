"""Retain finite fabrication paths, cuts and actual IFC wall correspondence."""
from pathlib import Path
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
sys.path.insert(0,str(ROOT/"tests"))

from oma.ifc.audit import atomic_json,sha256_file
from oma.optimization.fabrication_search import compile_fabrication_search,verify_fabrication_search
from test_optimization_fabrication_search import native_wall_case,tiny_impossible


def main():
    out=ROOT/"evidence/math/fabrication-search/attempts"/uuid.uuid4().hex
    out.mkdir(parents=True)
    files=[ROOT/name for name in ("src/oma/optimization/fabrication_search.py","src/oma/optimization/fabrication.py",
        "src/oma/ifc/export.py","src/oma/ifc/orthogonal_fillet.py","src/oma/ifc/network_semantics.py",
        "src/oma/ifc/cad.py","src/oma/routing/checker.py")]
    hashes={str(p.relative_to(ROOT)):sha256_file(p) for p in files}
    native=[]
    for mm in (False,True):
        name="millimetres" if mm else "metres"
        result=native_wall_case(out/name,millimeters=mm)
        atomic_json(out/name/"checked-result.json",result)
        native.append({"units":name,"source_sha256":result["source_sha256"],"export_sha256":result["export_sha256"],
            "finite_graph":result["independent_check"]["geometry_outcome"],
            "native_coordination":result["actual_native_coordination"]["coordination_status"],
            "native_self_interference":result["actual_native_coordination"]["self_interference_status"],
            "pairs_accounted":result["actual_native_coordination"]["pairs_accounted"],
            "polyline":result["certificate"]["points_m"]})
    model=tiny_impossible()
    certificate=compile_fabrication_search(model)
    checked=verify_fabrication_search(model,certificate)
    assert checked["status"]=="PASS" and checked["geometry_outcome"]=="NO_PATH_IN_DECLARED_GRAPH"
    atomic_json(out/"finite-cut.json",{"model":model,"certificate":certificate,"independent_check":checked})
    after={str(p.relative_to(ROOT)):sha256_file(p) for p in files}
    if hashes!=after:raise RuntimeError("Relevant implementation changed during benchmark; evidence not published")
    summary={"scope":"FINITE_NOMINAL_FABRICATION_GRAPH_WITH_SEPARATE_ACTUAL_NATIVE_IFC_WALL_CHECKS",
        "native_cases":native,"finite_cut_outcome":checked["geometry_outcome"],"code_sha256":hashes,
        "candidate_accepted":False,"physical_route_completeness":False,"physical_infeasibility_claim":False,"length_optimality_claim":False}
    atomic_json(out/"benchmark.json",summary)
    atomic_json(ROOT/"evidence/math/fabrication-search/latest.json",{"attempt":str(out.relative_to(ROOT)),"summary":str((out/"benchmark.json").relative_to(ROOT))})
    print({"attempt":str(out),"native":native,"finite_cut":checked["geometry_outcome"]})


if __name__=="__main__":main()
