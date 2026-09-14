"""Fresh read-only native envelope diagnosis of the rejected priced Office path."""
import json
from pathlib import Path
import time

from oma.build_identity import checker_version
from oma.ifc.audit import atomic_json, sha256_file
from oma.ifc.cad import load_cad, _transform_object
from oma.routing.scenario import RoutingScenario
from oma.store import Store, digest, utcnow


ROOT = Path(__file__).resolve().parents[5]
EXPECTED = "ebe15db28b384f99ffe9c19f8cfe9d16128d424b829250d75d5251372836e219"
assert checker_version().endswith(EXPECTED)
started = time.monotonic()
store = Store(ROOT / ".oma")
candidate = store.candidate("dc1cdd0d98e14838897f60dc0e3796ff")
run = store.run(candidate["run_id"])
scenario = RoutingScenario.model_validate(run["request"]["mission"])
material = store.get(candidate["routes"][0]["geometry_artifact"])
path = store.resolve_path(material["export_path"])
assert sha256_file(path) == material["export_sha256"]
parts = {part["ifc_guid"]:part for part in material["added_parts"]}
solids,errors = load_cad(path,guids=set(parts))
matrix = material.get("route_spec",{}).get("source_to_federation_matrix")
if matrix:
    solids = [_transform_object(solid,matrix) for solid in solids]
records = []
for solid in solids:
    lower = [solid.bounds[i]-scenario.allowed_zone.min[i] for i in range(3)]
    upper = [scenario.allowed_zone.max[i]-solid.bounds[i+3] for i in range(3)]
    gap = min(lower+upper)
    threshold = 1e-6+solid.kernel_tolerance_m
    records.append({"guid":solid.guid,"ifc_type":solid.ifc_type,"part":parts[solid.guid],
        "bounds_m":list(solid.bounds),"lower_zone_gaps_m":lower,"upper_zone_gaps_m":upper,
        "minimum_zone_gap_m":gap,"kernel_tolerance_m":solid.kernel_tolerance_m,
        "required_strict_gap_m":threshold,"status":"FAIL" if gap<0 else "UNKNOWN" if gap<=threshold else "PASS"})
result = {"scope":"FRESH_PER_PART_NATIVE_ZONE_ENVELOPE_DIAGNOSIS_ONLY; NOT_FULL_CANDIDATE_RECHECK",
    "created_at":utcnow(),"checker_version":checker_version(),"candidate_id":candidate["id"],
    "candidate_status":candidate["status"],"candidate_state_root":candidate["state_root"],
    "original_report_root":candidate["report_root"],"scenario_root":digest(scenario.model_dump(mode="json")),
    "original_allowed_zone":scenario.allowed_zone.model_dump(mode="json"),
    "export_path":str(path),"export_sha256":material["export_sha256"],"load_errors":errors,
    "parts":records,"part_count":len(records),"expected_part_count":len(parts),
    "candidate_file_unchanged":sha256_file(path)==material["export_sha256"],
    "elapsed_seconds":time.monotonic()-started}
atomic_json(Path(__file__).with_name("rejected-priced-route-zone-gaps.json"),result)
print(json.dumps(result,indent=2))
