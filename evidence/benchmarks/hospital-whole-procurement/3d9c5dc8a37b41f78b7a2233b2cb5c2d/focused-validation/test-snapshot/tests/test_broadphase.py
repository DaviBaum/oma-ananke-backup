import numpy as np
import pytest

from oma.broadphase import BroadphaseIndex, reference_pairs, expand_boxes


def pairs(index, queries, **kwargs):
    return [(i, int(j)) for i, hits in index.query(queries, **kwargs) for j in hits]


def test_batched_cpu_includes_containment_tangency_thin_and_negative_controls():
    boxes = [[0, 0, 0, 2, 2, 2], [.5, .5, .5, .6, .6, .6], [3, 0, 0, 3 + 1e-12, 1, 1], [-2, -2, -2, -1, -1, -1]]
    queries = [[1, 1, 1, 3, 3, 3], [10, 10, 10, 11, 11, 11], [2, 0, 0, 3, 1, 1]]
    index = BroadphaseIndex(boxes, backend="cpu")
    assert pairs(index, queries, batch_size=1) == reference_pairs(boxes, queries)
    assert (1, 0) not in reference_pairs(boxes, queries)


def test_cuda_matches_independent_reference_and_cpu_on_near_boundaries():
    import cupy as cp
    assert cp.cuda.runtime.getDeviceCount() >= 1, "RTX 3090 gate must run on this workstation"
    rng = np.random.default_rng(812)
    lo = rng.normal(size=(1000, 3))
    boxes = np.column_stack((lo, lo + rng.uniform(0, .5, size=(1000, 3))))
    queries = boxes[::17].copy()
    gpu = BroadphaseIndex(boxes, backend="cuda")
    cpu = BroadphaseIndex(boxes, backend="cpu")
    assert pairs(gpu, queries, expansion_m=.01, batch_size=7) == reference_pairs(boxes, queries, expansion_m=.01)
    assert pairs(gpu, queries) == pairs(cpu, queries)
    gpu.close()


def test_invalid_unknown_bounds_never_become_empty_space():
    with pytest.raises(ValueError):
        BroadphaseIndex([[0, 0, 0, float("nan"), 1, 1]])
    with pytest.raises(ValueError):
        BroadphaseIndex([[1, 0, 0, 0, 1, 1]])
    with pytest.raises(MemoryError):
        BroadphaseIndex(np.zeros((100, 6)), memory_budget_bytes=1024)
    with pytest.raises(ValueError):
        expand_boxes(np.zeros((1, 6)), -1)
