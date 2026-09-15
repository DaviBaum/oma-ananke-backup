"""Measured real-IFC-bound CPU/CUDA comparison including transfers and synchronization."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np
from oma.broadphase import BroadphaseIndex
from oma.hardware import diagnose
from oma.store import digest, utcnow


def benchmark(audit_paths, output, queries_count=4096):
    boxes, sources = [], []
    for path in audit_paths:
        audit = json.loads(Path(path).read_text(encoding="utf-8"))
        sources.append({"source_sha256": audit["source_sha256"], "audit_sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest()})
        boxes.extend(p["bounds"]["min"] + p["bounds"]["max"] for p in audit["products"] if p.get("bounds"))
    boxes = np.asarray(boxes)
    if not len(boxes):
        raise ValueError("No real geometry bounds")
    rng = np.random.default_rng(20260914)
    ids = rng.integers(0, len(boxes), size=queries_count)
    centers = (boxes[ids, :3] + boxes[ids, 3:]) / 2
    queries = np.column_stack((centers - .15, centers + .15))
    results = {}
    for backend in ("cpu", "cuda"):
        started = time.perf_counter()
        index = BroadphaseIndex(boxes, backend=backend)
        values = []
        for repeat in range(3):
            begin = time.perf_counter()
            hasher, hits = hashlib.sha256(), 0
            for i, row in index.query(queries):
                hasher.update(np.asarray([i], dtype=np.int64).tobytes())
                hasher.update(row.astype(np.int64).tobytes())
                hits += len(row)
            values.append({"seconds_including_download_and_synchronization": time.perf_counter() - begin, "pair_hash": hasher.hexdigest(), "hits": hits})
        results[backend] = {"measurements": values, "timings": index.timings, "end_to_end_seconds": time.perf_counter() - started,
                            "memory_budget_bytes": index.memory_budget_bytes, "fallback_reason": index.fallback_reason}
        index.close()
    agree = len({m["pair_hash"] for r in results.values() for m in r["measurements"]}) == 1
    report = {"track": "OMA-PERF-3090", "created_at": utcnow(), "status": "PASS" if agree else "FAIL", "scope": "Real IFC axis-aligned-bound query workload; narrow phase not included",
              "sources": sources, "box_count": len(boxes), "queries": len(queries), "comparisons_per_repeat": len(boxes) * len(queries),
              "input_root": digest({"boxes": hashlib.sha256(boxes.tobytes()).hexdigest(), "queries": hashlib.sha256(queries.tobytes()).hexdigest()}),
              "hardware": diagnose(refresh=True), "seed": 20260914, "results": results,
              "rendering_cost": "NOT_RUN in this headless measurement; live UI navigation must be measured separately",
              "predicate_tests": "tests/test_broadphase.py includes independent scalar oracle and boundary cases"}
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"status": report["status"], "boxes": len(boxes), "queries": len(queries), "results": results}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("audits", nargs="+")
    parser.add_argument("--output", default="evidence/benchmarks/gpu-broadphase.json")
    parser.add_argument("--queries", type=int, default=4096)
    args = parser.parse_args()
    benchmark(args.audits, args.output, args.queries)
