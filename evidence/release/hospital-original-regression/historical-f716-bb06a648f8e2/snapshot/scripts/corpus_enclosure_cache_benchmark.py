"""Read-only, measured same-source direct versus memoized enclosure comparison."""
import argparse
from fractions import Fraction
import json
from pathlib import Path
import time

import ifcopenshell
from oma.ifc.enclosure import ExactIfcEncloser, CODE_SHA256

IDS = [109397, 122902, 73098, 73254, 129256, 129799, 129878, 129637,
       142555, 167897, 155227, 183966, 184130, 184675, 208036, 184292,
       220706, 347055, 347217, 347760, 347379, 365945, 378615, 510810,
       524182, 474663, 474754, 530390, 530933, 531012, 530771, 569024,
       556355, 543686]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-direct", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("evidence/math/source-enclosure-plumbing-memoization.json"))
    args = parser.parse_args()
    source = Path("data/ifc-bench/projects/digital_hub/plumbing.ifc")
    started = time.monotonic()
    model = ifcopenshell.open(str(source))
    result = {"schema": "oma.source-enclosure-cache-benchmark/1", "source": str(source),
              "checker_code_sha256": CODE_SHA256, "product_ids": IDS,
              "ifcopenshell_load_seconds": time.monotonic() - started,
              "vertex_hull_completion": True, "runs": [],
              "status": "RUNNING",
              "scope": "Measured support-enclosure evaluation for 34 actual plumbing products; no route verdict, original-solid validity, full-building certificate or general performance bound.",
              "measurement_conditions": "Same process/source/model, distinct fresh direct and cached helpers. Other workstation tasks may contend; wall times are observed, not isolated hardware benchmarks."}

    def save():
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf8")

    cached = ExactIfcEncloser(source, model, vertex_hull_completion=True)
    result["source_sha256"] = cached.raw.source_sha256
    modes = [("cached_cold", cached), ("cached_warm", cached)]
    if not args.skip_direct:
        modes.append(("direct_uncached", ExactIfcEncloser(source, model, vertex_hull_completion=True, memoize_item_support=False)))
    for name, helper in modes:
        begin = time.monotonic()
        run = {"mode": name, "products": []}
        result["runs"].append(run)
        for identifier in IDS:
            tick = time.monotonic()
            certificate = helper.enclose_product(model.by_id(identifier))
            run["products"].append({"step_id": identifier, "seconds": time.monotonic() - tick, "certificate": certificate})
            run.update(seconds=time.monotonic() - begin, cache_hits=helper.support_cache_hits,
                       cache_misses=helper.support_cache_misses, complete_cached_items=len(helper._support_cache))
            save()
            print(json.dumps({"mode": name, "product": identifier, "status": certificate["status"],
                              "seconds": run["products"][-1]["seconds"], "completed": len(run["products"])}), flush=True)
    cold, warm = result["runs"][:2]
    result["warm_certificates_equal_cold"] = all(a["certificate"] == b["certificate"] for a, b in zip(cold["products"], warm["products"]))
    result["all_products_checked"] = all(p["certificate"]["status"] == "ENCLOSURE_CHECKED" for r in result["runs"] for p in r["products"])
    if not args.skip_direct:
        checks = []
        for a, b in zip(cold["products"], result["runs"][2]["products"]):
            x, y = a["certificate"], b["certificate"]
            equal_coverage = x["item_coverage"] == y["item_coverage"] and x.get("nonplanar_polygon_checks") == y.get("nonplanar_polygon_checks")
            contains_direct_box = None
            if x["status"] == y["status"] == "ENCLOSURE_CHECKED":
                xl, xh = [[Fraction(v) for v in row] for row in x["bounds_m"]]
                yl, yh = [[Fraction(v) for v in row] for row in y["bounds_m"]]
                contains_direct_box = all(xl[i] <= yl[i] and xh[i] >= yh[i] for i in range(3))
            checks.append({"step_id": a["step_id"], "same_complete_source_coverage": equal_coverage,
                           "memoized_box_contains_direct_interval_box": contains_direct_box})
        result["direct_comparison"] = checks
    result["status"] = "COMPLETED"
    result["elapsed_seconds"] = time.monotonic() - started
    save()
    print(json.dumps({"status": result["status"], "runs": [{k: v for k, v in r.items() if k != "products"} for r in result["runs"]]}), flush=True)


if __name__ == "__main__":
    main()
