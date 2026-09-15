"""Reproduce exact cell evidence on a declared host/through-opening model."""
from copy import deepcopy
from fractions import Fraction as Q
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from oma.optimization.rectilinear_opening import compile_rectilinear_opening, verify_rectilinear_opening
from oma.optimization.route_cells import compile_route_cells, verify_route_cells, verify_route_cell_refinement


def main():
    destination = ROOT / "evidence/math/route-cells"
    destination.mkdir(parents=True, exist_ok=True)
    host, cut = [[0, 0, 0], [10, 10, 1]], [[4, 4, -1], [6, 6, 2]]
    opening_keys = {"through_axis": 2, "context_root": "synthetic-authorized-opening-model",
        "source_roots": {"source": "synthetic-rational-host", "host": "ten-by-ten-by-one-host",
                         "frame": "identity-local-metres", "authorization": "synthetic-proposed-edit-only"}}
    opening = compile_rectilinear_opening(host, cut, **opening_keys)
    opening_check = verify_rectilinear_opening(host, cut, opening, **opening_keys)
    assert opening_check["status"] == "PASS"
    base = {"allowed_bounds": [[3, 3, -2], [7, 7, 3]], "body_radius": "1/4", "clearance": "1/10",
        "outer_obstacles": [{"id": "host", "bounds": host}],
        "inner_obstacles": [{"id": "host:inner", "bounds": host, "outer_id": "host"}],
        "grid_axes": [["13/4", "27/4"], ["13/4", "27/4"], ["-7/4", "11/4"]],
        "start": [5, 5, -1], "goal": [5, 5, 2], "context_root": "rational-local-slab-model",
        "source_roots": {"outer_cover": "original-host-box", "inner_occupancy": "original-host-box",
                         "frame": "identity-local-metres", "body_model": "closed-ball-radius-quarter-metre"}}
    refined = deepcopy(base)
    refined["grid_axes"] = [["13/4", "4", "9/2", "11/2", "6", "27/4"],
                            ["13/4", "4", "9/2", "11/2", "6", "27/4"],
                            ["-7/4", "-7/20", "0", "1", "27/20", "11/4"]]
    edited = deepcopy(refined)
    edited["outer_obstacles"] = [{"id": c["id"], "bounds": c["bounds_local"]} for c in opening["remaining_cells"]]
    edited["inner_obstacles"] = [{"id": c["id"] + ":inner", "bounds": c["bounds_local"], "outer_id": c["id"]}
                                 for c in opening["remaining_cells"]]
    edited["source_roots"]["outer_cover"] = edited["source_roots"]["inner_occupancy"] = opening["root"]
    results, certificates = {}, {}
    for name, problem in (("uncut-coarse", base), ("uncut-refined", refined), ("opening-refined", edited)):
        began = time.perf_counter()
        certificate = compile_route_cells(problem)
        compiled = time.perf_counter()
        check = verify_route_cells(problem, certificate)
        ended = time.perf_counter()
        assert check["status"] == "PASS", check
        artifact = {"problem": problem, "certificate": certificate, "independent_check": check}
        (destination / f"{name}.json").write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
        certificates[name] = certificate
        results[name] = {"geometry_outcome": check["geometry_outcome"], "verified_cells": check["verified_cells"],
            "free_cells": check["free_cells"], "outer_retained_cells": check["outer_retained_cells"],
            "compile_seconds": compiled - began, "verify_seconds": ended - compiled,
            "length_bounds": check["length_bounds"], "artifact": f"evidence/math/route-cells/{name}.json"}
    assert results["uncut-coarse"]["geometry_outcome"] == "UNKNOWN"
    assert results["uncut-refined"]["geometry_outcome"] == "OUTER_INFEASIBLE"
    assert results["opening-refined"]["geometry_outcome"] == "INNER_PATH_CHECKED"
    assert Q(results["opening-refined"]["length_bounds"]["inner_path_length_upper_bound_m"]) == 3
    refinement = verify_route_cell_refinement(base, certificates["uncut-coarse"], refined, certificates["uncut-refined"])
    assert refinement["status"] == "PASS"
    output = {"schema": "oma.route-cell-benchmark/1", "scope": "SYNTHETIC_EXACT_RATIONAL_GEOMETRY; NO_NATIVE_IFC_OR_ENGINEERING_APPROVAL",
        "opening_kernel_independent_check": opening_check, "opening_certificate": opening,
        "cases": results, "fixed_model_refinement": refinement,
        "opening_changes_model_not_refinement": True,
        "ground_truth": "The uncut slab spans the complete allowed XY cross-section, so every path between opposite Z sides intersects it. The cut opens a 2x2 footprint; the centre line at x=y=5 has one metre gap to each residual side, exceeding ball radius1/4 plus clearance1/10.",
        "implementation_sha256": hashlib.sha256((ROOT / "src/oma/optimization/route_cells.py").read_bytes()).hexdigest()}
    (destination / "benchmark.json").write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "cases": results, "fixed_model_refinement": refinement["status"]}))


if __name__ == "__main__":
    main()
