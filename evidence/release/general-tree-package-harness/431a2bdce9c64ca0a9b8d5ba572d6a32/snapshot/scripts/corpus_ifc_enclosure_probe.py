"""Measure source-rational enclosure coverage; no routing or solid-validity claim."""
from collections import Counter
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import ifcopenshell
from oma.ifc.enclosure import ExactIfcEncloser


def main():
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data/ifc-bench/projects/digital_hub/arc.ifc"
    started = time.monotonic()
    model = ifcopenshell.open(str(source))
    completion = "--vertex-hull-completion" in sys.argv
    checker = ExactIfcEncloser(source, model, vertex_hull_completion=completion)
    products = [p for p in model.by_type("IfcElement") if not p.is_a("IfcOpeningElement")]
    results = []
    for i, p in enumerate(products):
        results.append(checker.enclose_product(p))
        if (i+1) % 100 == 0:
            print(json.dumps({"checked": i+1, "seconds": round(time.monotonic()-started, 2)}), flush=True)
    payload = {"source": str(source), "source_sha256": checker.raw.source_sha256,
        "scope": "IfcElement excluding IfcOpeningElement; selected Body representations only",
        "counts": dict(Counter(r["status"] for r in results)),
        "unknown_reasons": dict(Counter(r.get("reason") for r in results if r["status"] != "ENCLOSURE_CHECKED")),
        "elapsed_seconds": time.monotonic()-started, "results": results}
    out = ROOT / ("evidence/math/source-enclosure-digital-hub-completion.json" if completion else "evidence/math/source-enclosure-digital-hub.json")
    out.write_text(json.dumps(payload, indent=2)+"\n", encoding="utf8")
    print(json.dumps({k:v for k,v in payload.items() if k != "results"}, indent=2))


if __name__ == "__main__":
    main()
