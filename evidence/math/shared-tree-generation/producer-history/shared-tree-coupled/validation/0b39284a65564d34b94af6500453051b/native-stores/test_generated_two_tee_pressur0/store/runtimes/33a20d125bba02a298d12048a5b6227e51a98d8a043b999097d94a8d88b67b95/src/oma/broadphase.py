"""Bounded CPU/CUDA spatial candidate generation with identical float64 inputs.

Inclusive interval comparisons never establish interference. Narrow-phase checks
must independently dispose every returned pair, invalid solid, and unknown input.
No global dense pair matrix is stored; query batches are immediately drained.
"""
from __future__ import annotations

import time
from collections.abc import Iterator

import numpy as np

KERNEL = r'''
extern "C" __global__ void aabb_pairs(const double* boxes, const double* queries,
                                      const long long n, const long long m,
                                      unsigned char* hit) {
  long long i = (long long)blockDim.x * blockIdx.x + threadIdx.x;
  if (i >= n*m) return;
  long long b = (i % n)*6, q = (i / n)*6;
  hit[i] = (boxes[b] <= queries[q+3] && queries[q] <= boxes[b+3] &&
            boxes[b+1] <= queries[q+4] && queries[q+1] <= boxes[b+4] &&
            boxes[b+2] <= queries[q+5] && queries[q+2] <= boxes[b+5]);
}
'''


def validated_boxes(boxes):
    boxes = np.asarray(boxes, dtype=np.float64)
    if boxes.size == 0:
        return np.empty((0, 6), dtype=np.float64)
    if boxes.ndim != 2 or boxes.shape[1] != 6 or not np.isfinite(boxes).all() or np.any(boxes[:, :3] > boxes[:, 3:]):
        raise ValueError("AABB inputs must be finite ordered [min_xyz,max_xyz] rows")
    return np.ascontiguousarray(boxes)


def expand_boxes(boxes, distance_m: float):
    boxes = validated_boxes(boxes).copy()
    if not np.isfinite(distance_m) or distance_m < 0:
        raise ValueError("Expansion must be finite and nonnegative")
    boxes[:, :3] = np.nextafter(boxes[:, :3] - distance_m, -np.inf)
    boxes[:, 3:] = np.nextafter(boxes[:, 3:] + distance_m, np.inf)
    if not np.isfinite(boxes).all():
        raise OverflowError("AABB expansion overflow; rescale coordinates")
    return boxes


class BroadphaseIndex:
    def __init__(self, boxes, *, backend="auto", memory_budget_bytes=256 * 1024**2):
        if backend not in {"auto", "cpu", "cuda"}:
            raise ValueError("Backend must be auto, cpu or cuda")
        self.boxes = validated_boxes(boxes)
        if memory_budget_bytes < max(1024, self.boxes.nbytes * 2):
            raise MemoryError("Spatial index exceeds declared memory budget")
        self.memory_budget_bytes = memory_budget_bytes
        self.backend = "cpu"
        self.fallback_reason = None
        self.timings = {"setup_seconds": 0., "upload_seconds": 0., "query_seconds": 0., "queries": 0, "comparisons": 0}
        self.device = None
        start = time.perf_counter()
        if backend != "cpu":
            try:
                import cupy as cp
                free, _ = cp.cuda.runtime.memGetInfo()
                if free < memory_budget_bytes + 3 * 1024**3:
                    raise MemoryError("GPU display/driver reserve would be exceeded")
                self.cp = cp
                self.kernel = cp.RawKernel(KERNEL, "aabb_pairs", options=("--std=c++17", "--fmad=false"))
                self.kernel.compile()
                upload = time.perf_counter()
                self.device = cp.asarray(self.boxes)
                cp.cuda.get_current_stream().synchronize()
                self.timings["upload_seconds"] = time.perf_counter() - upload
                self.backend = "cuda"
            except Exception as exc:
                self.fallback_reason = f"{type(exc).__name__}: {exc}"
                if backend == "cuda":
                    raise RuntimeError(f"CUDA unavailable: {self.fallback_reason}") from exc
        self.timings["setup_seconds"] = time.perf_counter() - start

    def query(self, queries, *, expansion_m=0., batch_size=64) -> Iterator[tuple[int, np.ndarray]]:
        queries = expand_boxes(queries, expansion_m)
        n = len(self.boxes)
        batch_size = max(1, min(int(batch_size), max(1, (self.memory_budget_bytes - self.boxes.nbytes * 2) // max(1, n * 10))))
        for offset in range(0, len(queries), batch_size):
            started = time.perf_counter()
            q = queries[offset:offset + batch_size]
            if n == 0:
                masks = np.zeros((len(q), 0), dtype=bool)
            elif self.backend == "cuda":
                cp = self.cp
                device_queries = cp.asarray(q)
                hits = cp.empty((len(q), n), dtype=cp.uint8)
                self.kernel(((len(q) * n + 255) // 256,), (256,), (self.device, device_queries, np.int64(n), np.int64(len(q)), hits))
                masks = cp.asnumpy(hits)  # Transfer includes synchronization in measured query cost.
                del hits, device_queries
            else:
                masks = np.ones((len(q), n), dtype=bool)
                for axis in range(3):
                    masks &= self.boxes[None, :, axis] <= q[:, None, axis + 3]
                    masks &= q[:, None, axis] <= self.boxes[None, :, axis + 3]
            self.timings["query_seconds"] += time.perf_counter() - started
            self.timings["queries"] += len(q)
            self.timings["comparisons"] += len(q) * n
            for i, row in enumerate(masks):
                yield offset + i, np.flatnonzero(row)

    def close(self):
        if self.device is not None:
            del self.device
            self.device = None


def reference_pairs(boxes, queries, *, expansion_m=0.):
    """Exhaustive independent scalar oracle for finite IEEE input intervals."""
    boxes = validated_boxes(boxes)
    queries = expand_boxes(queries, expansion_m)
    return [(i, j) for i, query in enumerate(queries) for j, box in enumerate(boxes)
            if not any(float(query[axis + 3]) < float(box[axis]) or float(box[axis + 3]) < float(query[axis]) for axis in range(3))]
