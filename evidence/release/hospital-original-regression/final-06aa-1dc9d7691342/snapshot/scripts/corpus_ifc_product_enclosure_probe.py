"""Read-only exact source support probe for explicitly named IFC products."""
import argparse
import json
from pathlib import Path
import time

import ifcopenshell
from oma.ifc.enclosure import ExactIfcEncloser, CODE_SHA256


parser = argparse.ArgumentParser()
parser.add_argument("source", type=Path)
parser.add_argument("output", type=Path)
parser.add_argument("products", type=int, nargs="+")
parser.add_argument("--vertex-hull-completion", action="store_true")
args = parser.parse_args()
started = time.monotonic()
model = ifcopenshell.open(str(args.source))
checker = ExactIfcEncloser(args.source, model, vertex_hull_completion=args.vertex_hull_completion)
results = [checker.enclose_product(model.by_id(identifier)) for identifier in args.products]
report = {
    "source": str(args.source), "source_sha256": checker.raw.source_sha256,
    "checker_code_sha256": CODE_SHA256, "product_ids": args.products,
    "scope": "Complete selected Body source support only; no native solid validity or route claim",
    "vertex_hull_completion": args.vertex_hull_completion,
    "results": results, "elapsed_seconds": time.monotonic() - started,
}
args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf8")
print(json.dumps({key: value for key, value in report.items() if key != "results"}, indent=2))
print(json.dumps([{key: value for key, value in result.items() if key in ("status", "reason", "product_id")} for result in results]))
