"""Retain finite nominal pricing proofs and a separate actual IFC wall check."""
from pathlib import Path
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
sys.path.insert(0,str(ROOT/"tests"))

from oma.ifc.audit import atomic_json,sha256_file
from oma.optimization.fabrication_pricing import compile_fabrication_pricing,verify_fabrication_pricing
from test_optimization_fabrication_pricing import native_priced_wall_case,objective
from test_optimization_fabrication_search import problem,tiny_impossible


def main():
    out=ROOT/"evidence/math/fabrication-pricing/attempts"/uuid.uuid4().hex
    out.mkdir(parents=True)
    names=("src/oma/optimization/fabrication_pricing.py","src/oma/optimization/fabrication_search.py",
           "src/oma/optimization/fabrication.py","src/oma/ifc/export.py","src/oma/ifc/orthogonal_fillet.py",
           "src/oma/ifc/network_semantics.py","src/oma/ifc/cad.py","src/oma/routing/checker.py")
    hashes={name:sha256_file(ROOT/name) for name in names}
    native=native_priced_wall_case(out/"native-wall")
    atomic_json(out/"native-wall"/"checked-result.json",native)
    examples=[]
    for name,p,o in (("length-only",problem(),objective()),("fitting-tradeoff",problem(),objective(fitting="1")),
                     ("near-pi-threshold",problem(),objective(fitting="97/452")),("finite-cut",tiny_impossible(),objective())):
        certificate=compile_fabrication_pricing(p,o)
        checked=verify_fabrication_pricing(p,o,certificate)
        assert checked["status"]=="PASS",checked
        atomic_json(out/(name+".json"),{"model":p,"objective":o,"certificate":certificate,"independent_check":checked})
        examples.append({"name":name,"pricing_outcome":checked["pricing_outcome"],"cost":checked["cost"],
                         "points_m":certificate["points_m"],"explicit_labels":len(certificate["potentials"]),
                         "producer_work":certificate["producer_work"],"checker_work":checked["work"]})
    ambiguity=compile_fabrication_pricing(problem(),objective(fitting="97/452"),max_pi_terms=1)
    assert ambiguity["status"]=="UNKNOWN" and ambiguity["reason"]=="PI_COMPARISON_PRECISION_BUDGET"
    atomic_json(out/"budgeted-ambiguity.json",ambiguity)
    if hashes!={name:sha256_file(ROOT/name) for name in names}:
        raise RuntimeError("Relevant implementation changed during benchmark; evidence not published")
    summary={"scope":"FINITE_GRAPH_NOMINAL_COST_CERTIFICATES_AND_SEPARATE_ACTUAL_NATIVE_WALL_CHECK",
             "code_sha256":hashes,"examples":examples,"native_cost":native["certificate"]["cost"],
             "native_coordination":native["actual_native_coordination"]["coordination_status"],
             "native_self_interference":native["actual_native_coordination"]["self_interference_status"],
             "native_pairs_accounted":native["actual_native_coordination"]["pairs_accounted"],
             "native_correspondence":native["actual_native_correspondence"]["status"],
             "source_sha256":native["source_sha256"],"export_sha256":native["export_sha256"],
             "native_objective_optimality":False,"candidate_accepted":False,"continuous_optimality":False}
    atomic_json(out/"benchmark.json",summary)
    atomic_json(ROOT/"evidence/math/fabrication-pricing/latest.json",{"attempt":str(out.relative_to(ROOT)),
                "summary":str((out/"benchmark.json").relative_to(ROOT))})
    print({"attempt":str(out),"native_cost":summary["native_cost"],"native_pairs":summary["native_pairs_accounted"],"examples":examples})


if __name__=="__main__":main()
