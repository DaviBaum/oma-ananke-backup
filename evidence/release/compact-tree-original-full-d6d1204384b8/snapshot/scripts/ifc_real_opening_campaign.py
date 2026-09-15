"""A frozen real-source opening scenario with one actual direct-route proposal."""
from pathlib import Path
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if not os.environ.get("OMA_EXECUTABLE_BUILD"):
    sys.path.insert(0, str(ROOT / "src"))
    from oma.build_identity import frozen_environment
    if __name__ == "__main__":
        raise SystemExit(subprocess.call([sys.executable, __file__, *sys.argv[1:]], env=frozen_environment(ROOT / ".oma" / "benchmark-builds")))

import argparse
from copy import deepcopy
import json
import time
import uuid

import ifcopenshell
import ifcopenshell.util.placement
import numpy as np

from oma.build_identity import checker_version
from oma.exporting import export_project
from oma.ifc.audit import atomic_json, sha256_file
from oma.ifc.openings import inspect_host
from oma.routing.engine import route_project_run
from oma.store import Store, digest
from oma.worker import WorkerControl


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-candidate", default="f583693cce4644ad8306b31d51c8540f")
    parser.add_argument("--project", default="wbdg_office")
    parser.add_argument("--budget", type=float, default=900.)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--source-representation-policy", choices=["NATIVE_CAD_WITH_EXACT_PLANAR_ENCLOSURES", "NATIVE_CAD_WITH_SOURCE_VERTEX_HULL_ENCLOSURES"], default="NATIVE_CAD_WITH_EXACT_PLANAR_ENCLOSURES")
    parser.add_argument("--prior-attempt", type=Path)
    args = parser.parse_args()
    store = Store(ROOT / ".oma")
    historical = store.candidate(args.baseline_candidate)
    historical_run = store.run(historical["run_id"])
    baseline = store.get(historical_run["base_root"])
    if baseline.get("routes") or baseline.get("mission") or baseline.get("physical_networks") or len(baseline["sources"]) != 1:
        raise ValueError("Campaign requires one immutable original imported source baseline")
    source_record = baseline["sources"][0]
    source = store.resolve_path(source_record["immutable_path"])
    if sha256_file(source) != source_record["sha256"]:
        raise ValueError("Baseline source bytes changed")
    transform = np.asarray(source_record["transform_m"])
    if not np.array_equal(transform, np.eye(4)):
        raise ValueError("First campaign requires the persisted source-local identity frame")
    inventory_path = ROOT / "evidence/ifc/opening-host-inventory.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    declared = next(s for s in inventory["sources"] if s["project"] == args.project and s["source_sha256"] == source_record["sha256"])
    model = ifcopenshell.open(str(source))
    physical = {e.GlobalId for e in model.by_type("IfcElement") if not e.is_a("IfcOpeningElement")}
    boxes = [(e["provenance"]["guid"], np.asarray([e["geometry"]["bounds"][k] for k in ("min", "max")]))
        for e in baseline["entities"] if e["provenance"].get("guid") in physical and e.get("geometry", {}).get("bounds")]
    ranked = []
    scale = source_record["units"]["source_to_m"]
    rectangles = [r for r in declared["unvoided_direct_extrusions"] if r["profile"] == "IfcRectangleProfileDef"]
    for row in rectangles:
        x, y, z = [row[k]*scale for k in ("profile_x_source_units", "profile_y_source_units", "depth_source_units")]
        if min(x, z) < 1.4 or not .02 < y < .8:
            continue
        host = model.by_id(row["step_id"])
        body = next(r for r in host.Representation.Representations if r.RepresentationIdentifier == "Body").Items[0]
        frame = (ifcopenshell.util.placement.get_local_placement(host.ObjectPlacement)
            @ ifcopenshell.util.placement.get_axis2placement(body.Position)
            @ ifcopenshell.util.placement.get_axis2placement(body.SweptArea.Position))
        frame[:3, 3] *= scale
        for fraction in (0., -.25, .25):
            center = np.array([fraction*x, 0., z/2])
            start, end = center + [0., -y/2-.5, 0.], center + [0., y/2+.5, 0.]
            points = np.asarray([frame[:3, :3] @ p + frame[:3, 3] for p in (start, end)])
            envelope = np.asarray([points.min(axis=0)-.17, points.max(axis=0)+.17])
            overlaps = [guid for guid, bounds in boxes if guid != row["guid"] and np.all(envelope[0] <= bounds[1]) and np.all(envelope[1] >= bounds[0])]
            ranked.append({"host_guid": row["guid"], "host_step_id": row["step_id"], "center_local_m": center.tolist(),
                "points_m": points.tolist(), "other_bbox_overlap_count": len(overlaps), "other_bbox_overlap_guids": overlaps})
    ranked.sort(key=lambda r: (r["other_bbox_overlap_count"], r["host_step_id"], r["center_local_m"][0]))
    directory = ROOT / "evidence/benchmarks/opening" / args.project / uuid.uuid4().hex
    directory.mkdir(parents=True)
    probes = []
    selected = None
    for proposal in ranked[:16]:
        try:
            descriptor = inspect_host(source, proposal["host_guid"], proposal["host_step_id"])
            probes.append({**proposal, "status": "NATIVE_ELIGIBLE", "descriptor": descriptor})
            selected = probes[-1]
            break
        except (ValueError, RuntimeError) as exc:
            probes.append({**proposal, "status": "NATIVE_INELIGIBLE", "reason": str(exc)})
    atomic_json(directory / "eligibility.json", {"declared_rectangles": len(rectangles), "ranked_position_count": len(ranked),
        "heuristic_ranking": "DISPLAY_BOUNDS_ONLY_NO_FEASIBILITY_AUTHORITY", "probes": probes,
        "all_original_physical_guid_count": len(physical), "source_sha256": source_record["sha256"]})
    if selected is None:
        raise ValueError("No native-eligible host in bounded probes; denominator retained")
    descriptor = selected["descriptor"]
    host_bounds = np.asarray([[float(__import__("fractions").Fraction(v)) for v in row] for row in descriptor["host_bounds_local_m"]])
    center = np.asarray(selected["center_local_m"])
    opening_bounds = {"min": [float(center[0]-.3), float(host_bounds[0,1]-.3), float(center[2]-.3)],
                      "max": [float(center[0]+.3), float(host_bounds[1,1]+.3), float(center[2]+.3)]}
    permission = {"mode": "EXPLICIT_USER_GEOMETRIC_EDIT", "statement": "This frozen implementation benchmark explicitly permits one specified rectangular geometric opening in the selected original IFC host. This is a scenario-only geometric assumption; structural, fire and operational approval are not established.",
        "evidence_roots": [sha256_file(ROOT / "docs/PRODUCTION_DIRECTIVE.md"), sha256_file(inventory_path)], "engineering_scope": "SCENARIO_GEOMETRY_ONLY"}
    request = {"source_sha256": descriptor["source_sha256"], "host_guid": descriptor["host_guid"], "host_step_id": descriptor["host_step_id"],
        "host_geometry_root": descriptor["host_geometry_root"], "opening_bounds_local_m": opening_bounds,
        "allowed_opening_bounds_local_m": deepcopy(opening_bounds), "through_axis": 1, "permission": permission}
    points = np.asarray(selected["points_m"])
    mission = {"start": points[0].tolist(), "end": points[1].tolist(), "system_type": "PRESSURE_PIPE", "diameter_m": .1,
        "insulation_m": .02, "bend_radius_m": .3, "minimum_straight_m": .05, "clearance_m": .1,
        "allowed_zone": {"min": (points.min(axis=0)-.5).tolist(), "max": (points.max(axis=0)+.5).tolist()},
        "scenario_terminals": True, "max_candidates": 1, "authorized_opening": request}
    mission["source_representation_policy"] = args.source_representation_policy
    frozen = {"baseline_root": historical_run["base_root"], "source_sha256": source_record["sha256"], "mission": mission,
        "checker_version": checker_version(), "scope": "One supplied geometric opening option plus one fixed direct-route proposal; no design optimum or whole-building approval claim"}
    if args.prior_attempt:
        prior_path = args.prior_attempt / "frozen-input.json"
        prior = json.loads(prior_path.read_text(encoding="utf-8"))
        if {k:v for k,v in prior["mission"].items() if k != "source_representation_policy"} != {k:v for k,v in mission.items() if k != "source_representation_policy"}:
            raise ValueError("Interpretation variant changed a frozen physical requirement")
        frozen["policy_amendment"] = {"prior_specification_root": prior["specification_root"], "prior_artifact_sha256": sha256_file(prior_path),
            "prior_attempt": str(args.prior_attempt), "physical_requirements_changed": False,
            "source_native_validity": "UNRESOLVED_WHERE_REPORTED_INVALID",
            "claim": "Explicit source-face vertex-hull completion family interpretation; no native source validity or outside-family physical extent claim"}
    frozen["specification_root"] = digest(frozen)
    atomic_json(directory / "frozen-input.json", frozen)
    print(json.dumps({"directory": str(directory), "host": selected["host_step_id"], "other_bbox_overlap_count": selected["other_bbox_overlap_count"], "frozen_root": frozen["specification_root"]}), flush=True)
    if args.prepare_only:
        return
    project = store.create_project("WBDG Office · authorized opening and direct route", baseline)
    records = []
    started = time.monotonic()
    for name, scenario in (("uncut", {k:v for k,v in mission.items() if k != "authorized_opening"}), ("authorized_cut", mission)):
        run = store.create_run(project["id"], {"operation": "route", "mission": scenario, "budget_seconds": args.budget})
        route_project_run(store, run, WorkerControl(store, run["id"]))
        candidates = [c for c in store.candidates(project["id"]) if c["run_id"] == run["id"]]
        record = {"name": name, "run_id": run["id"], "run_status": store.run(run["id"])["status"], "candidates": candidates}
        for candidate in candidates:
            if candidate["report_root"]:
                atomic_json(directory / (candidate["id"] + ".report.json"), store.get(candidate["report_root"]))
        records.append(record)
        atomic_json(directory / "result.json", {"status": "RUNNING", "project_id": project["id"], "records": records, "frozen_specification_root": frozen["specification_root"]})
        print(json.dumps({"stage": name, "project_id": project["id"], "candidates": [{"id":c["id"], "status":c["status"]} for c in candidates]}), flush=True)
    checked = next((c for c in records[-1]["candidates"] if c["status"] == "CHECKED"), None)
    result = {"status": "NO_CHECKED_OPENING_ROUTE", "project_id": project["id"], "records": records, "checker_version": checker_version(),
        "frozen_specification_root": frozen["specification_root"], "scope": frozen["scope"]}
    if checked:
        accepted = store.accept(project["id"], checked["id"], project["revision"], "opening-benchmark-accept", checker_version=checker_version())
        exported = export_project(store, project["id"], checked["id"], draft=False)
        result.update(status="CHECKED_ACCEPTED_EXPORTED_RECHECKED", selected_candidate_id=checked["id"], accepted=accepted, export=exported)
    result["elapsed_seconds"] = time.monotonic()-started
    atomic_json(directory / "result.json", result)
    print(json.dumps({"status": result["status"], "project_id": project["id"], "directory": str(directory), "elapsed_seconds": result["elapsed_seconds"]}), flush=True)


if __name__ == "__main__":
    main()
