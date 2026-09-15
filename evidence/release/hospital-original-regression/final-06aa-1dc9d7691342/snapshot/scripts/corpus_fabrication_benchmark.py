"""Reproduce exact orthogonal fabrication and actual IFC correspondence evidence."""
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
sys.path.insert(0,str(ROOT/"tests"))

from oma.ifc.audit import atomic_json,sha256_file
from oma.ifc.export import export_route
from oma.optimization.fabrication import compile_orthogonal_fabrication,verify_orthogonal_fabrication
from oma.store import digest
from test_ifc_openings import host_fixture
from test_optimization_fabrication import scenario,actual_ifc_correspondence,actual_ifc_threshold_boundary


def main():
    base = ROOT/"evidence/math/fabrication"
    out = base/"attempts"/uuid.uuid4().hex
    out.mkdir(parents=True)
    points = [(0.,0.,0.),(2.,0.,0.),(2.,2.,0.),(2.,2.,2.)]
    request = scenario(points,insulation_m=.0625)
    context = digest({"scenario":request.model_dump(mode="json"),"points":points,"scope":"SYNTHETIC_FIXED_REALIZATION_CORRESPONDENCE"})
    certificate = compile_orthogonal_fabrication(request,points,context_root=context)
    independent = verify_orthogonal_fabrication(request,points,certificate,context_root=context)
    atomic_json(out/"exact-certificate.json",certificate)
    atomic_json(out/"independent-check.json",independent)
    if independent["status"] != "PASS" or independent["fabrication_status"] != "PASS":
        raise RuntimeError(independent)
    native_reports = []
    boundary_reports = []
    for schema in ("IFC4","IFC2X3"):
        source,_ = host_fixture(out/(schema+"-source.ifc"),schema=schema)
        output = out/(schema+"-route.ifc")
        source_hash = sha256_file(source)
        manifest = export_route(source,output,{"route_id":"exact-orthogonal-fabrication","system_type":request.system_type,
            "points_m":points,"diameter_m":request.diameter_m,"insulation_m":request.insulation_m,
            "bend_radius_m":request.bend_radius_m,"minimum_straight_m":request.minimum_straight_m},fresh_recheck=False)
        actual = actual_ifc_correspondence(output,manifest,certificate)
        actual.update(source_sha256=source_hash,export_sha256=sha256_file(output),schema=schema,
            original_source_unchanged=source_hash==sha256_file(source),certificate_root=certificate["certificate_root"])
        atomic_json(out/(schema+"-native-correspondence.json"),actual)
        native_reports.append({"schema":schema,"status":actual["status"],"parts_checked":actual["parts_checked"],"export_sha256":actual["export_sha256"]})
        boundary = actual_ifc_threshold_boundary(out,schema)
        atomic_json(out/(schema+"-threshold-boundary.json"),boundary)
        boundary_reports.append({"schema":schema,"exact_equality_status":"FAIL","writer_rejected_equality":True,
            "next_float_status":boundary["next_float_native_correspondence"]["status"],"export_sha256":boundary["export_sha256"]})
    summary = {"scope":"EXACT_FIXED_ORTHOGONAL_FABRICATION_WITH_SEPARATE_NUMERICAL_NATIVE_CORRESPONDENCE",
        "certificate_root":certificate["certificate_root"],"independent_check":independent,
        "native_reports":native_reports,"actual_whole_route_clearance_checked":False,"candidate_accepted":False,
        "corrected_threshold_tests":boundary_reports,"automatic_pruning_authority":False,
        "code_sha256":{str(p.relative_to(ROOT)):sha256_file(p) for p in (ROOT/"src/oma/optimization/fabrication.py",ROOT/"src/oma/ifc/export.py",ROOT/"src/oma/ifc/orthogonal_fillet.py",ROOT/"src/oma/ifc/network_semantics.py",ROOT/"src/oma/ifc/openings.py",ROOT/"src/oma/ifc/cad.py")}}
    atomic_json(out/"benchmark.json",summary)
    atomic_json(base/"latest.json",{"attempt":str(out.relative_to(ROOT)),"summary":str((out/"benchmark.json").relative_to(ROOT))})
    print({"attempt":str(out),"exact":independent["fabrication_status"],"native":native_reports})


if __name__ == "__main__": main()
