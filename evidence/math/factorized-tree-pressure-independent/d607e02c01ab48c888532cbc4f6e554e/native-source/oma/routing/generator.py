"""Bounded heuristic proposal search; never a certified inner/outer abstraction.

Integration DEF-RTR18–24 requires complete-body embedding certificates before
graph edges can support a theorem. This module emits *proposals*, subsequently
materialized and independently checked. A missing path is not infeasibility.
"""
from __future__ import annotations

import heapq
import itertools
import math
import time
from collections.abc import Callable, Iterator

import numpy as np

from .scenario import RoutingScenario


def simplify(points):
    result = []
    for p in points:
        p = np.asarray(p, dtype=np.float64)
        if result and np.linalg.norm(p - result[-1]) < 1e-10:
            continue
        if len(result) >= 2:
            a, b = result[-1] - result[-2], p - result[-1]
            if np.linalg.norm(np.cross(a, b)) < 1e-10 and np.dot(a, b) > 0:
                result.pop()
        result.append(p)
    return [p.tolist() for p in result]


def segment_hits_boxes(start, end, lower, upper):
    """Slab test for candidate pruning only; solid checker is independent."""
    if not len(lower):
        return False
    start, end = np.asarray(start), np.asarray(end)
    direction = end - start
    tmin, tmax = np.zeros(len(lower)), np.ones(len(lower))
    possible = np.ones(len(lower), dtype=bool)
    for axis in range(3):
        if abs(direction[axis]) < 1e-14:
            possible &= (start[axis] >= lower[:, axis]) & (start[axis] <= upper[:, axis])
        else:
            t0 = (lower[:, axis] - start[axis]) / direction[axis]
            t1 = (upper[:, axis] - start[axis]) / direction[axis]
            tmin = np.maximum(tmin, np.minimum(t0, t1))
            tmax = np.minimum(tmax, np.maximum(t0, t1))
    return bool(np.any(possible & (tmax >= tmin)))


def proposal_paths(scenario: RoutingScenario, obstacle_bounds: list, *, deadline: float,
                   checkpoint: Callable[[], None] = lambda: None, on_search: Callable[[dict], None] = lambda e: None) -> Iterator[dict]:
    start, end = np.array(scenario.start), np.array(scenario.end)
    seen = set()
    def proposal(points, reason):
        points = simplify(points)
        key = tuple(tuple(round(x, 10) for x in p) for p in points)
        if key in seen or len(points) < 2:
            return None
        seen.add(key)
        return {"points_m": points, "rationale": reason, "search_model": "heuristic finite proposals; independent full-body check required"}
    first = proposal([start, end], "Direct terminal connection is the baseline candidate")
    if first:
        yield first
    for axes in itertools.permutations(range(3)):
        checkpoint()
        point, points = start.copy(), [start.copy()]
        for axis in axes:
            point = point.copy()
            point[axis] = end[axis]
            points.append(point)
        candidate = proposal(points, f"Orthogonal axis order {axes} with parameterized elbows")
        if candidate:
            yield candidate
        if time.monotonic() >= deadline:
            return
    # Strategic detour planes are derived from obstacles/domain, never benchmark IDs.
    box = scenario.allowed_zone
    outer = scenario.outer_radius + scenario.clearance_m
    for axis in range(3):
        low = box.min[axis] + outer + scenario.bend_radius_m
        high = box.max[axis] - outer - scenario.bend_radius_m
        for fraction in (.25, .5, .75, 0., 1.):
            checkpoint()
            level = low + fraction * (high - low)
            a, b = start.copy(), end.copy()
            a[axis] = b[axis] = level
            candidate = proposal([start, a, b, end], f"Alternative corridor at axis {axis}, elevation/offset {level:.6g} m")
            if candidate:
                yield candidate
            if time.monotonic() >= deadline:
                return
    # Lift heading and straight-run state; full geometry is still checked later.
    bounds = np.asarray(obstacle_bounds, dtype=np.float64).reshape(-1, 6)
    lower, upper = bounds[:, :3] - outer, bounds[:, 3:] + outer
    for bend_penalty in (scenario.bend_radius_m, scenario.bend_radius_m * 5):
        path = astar(scenario, lower, upper, deadline, checkpoint, on_search, bend_penalty)
        if path:
            candidate = proposal(path, "Lifted heading/straight-run search avoiding inflated obstacle bounds")
            if candidate:
                yield candidate


def astar(scenario, lower, upper, deadline, checkpoint, on_search, bend_penalty):
    lo = np.array(scenario.allowed_zone.min) + scenario.outer_radius
    hi = np.array(scenario.allowed_zone.max) - scenario.outer_radius
    extent = hi - lo
    step = max(scenario.search_step_m, float(max(extent) / 80))
    axes = [np.unique(np.concatenate((np.arange(lo[i], hi[i], step), [hi[i], scenario.start[i], scenario.end[i]]))) for i in range(3)]
    start = tuple(int(np.searchsorted(axes[i], scenario.start[i])) for i in range(3))
    target = tuple(int(np.searchsorted(axes[i], scenario.end[i])) for i in range(3))
    position = lambda p: np.array([axes[i][p[i]] for i in range(3)])
    start_state = (*start, -1, 0)
    queue, costs, parents = [(0., 0, start_state)], {start_state: 0.}, {}
    count, expanded = 1, 0
    runway = 2 * scenario.bend_radius_m + scenario.minimum_straight_m
    quant = max(step / 8, 1e-4)
    max_run = math.ceil(runway / quant)
    while queue and expanded < 250000 and time.monotonic() < deadline:
        _, _, state = heapq.heappop(queue)
        p, direction, run_length = state[:3], state[3], state[4]
        if p == target:
            path = [position(p)]
            while state in parents:
                state = parents[state]
                path.append(position(state[:3]))
            return simplify(reversed(path))
        expanded += 1
        if expanded % 128 == 0:
            checkpoint()
            on_search({"expanded_states": expanded, "frontier_size": len(queue), "region": scenario.allowed_zone.model_dump(), "step_m": step})
        for new_direction, (axis, sign) in enumerate(itertools.product(range(3), (-1, 1))):
            new = list(p)
            new[axis] += sign
            if new[axis] < 0 or new[axis] >= len(axes[axis]):
                continue
            turning = direction >= 0 and new_direction != direction
            if turning and (direction // 2 == axis or run_length < max_run):
                continue
            q = tuple(new)
            first, second = position(p), position(q)
            if scenario.system_type == "GRAVITY_DRAINAGE" and second[2] > first[2]:
                continue
            if segment_hits_boxes(first, second, lower, upper):
                continue
            distance = float(np.linalg.norm(second - first))
            new_run = min(max_run, (0 if turning else run_length) + math.floor(distance / quant))
            next_state = (*q, new_direction, new_run)
            cost = costs[state] + distance + (bend_penalty if turning else 0)
            if cost < costs.get(next_state, float("inf")):
                costs[next_state] = cost
                parents[next_state] = state
                heuristic = float(np.linalg.norm(second - np.asarray(scenario.end)))
                heapq.heappush(queue, (cost + heuristic, count, next_state))
                count += 1
    on_search({"expanded_states": expanded, "frontier_size": len(queue), "status": "BUDGET_EXHAUSTED" if time.monotonic() >= deadline else "NO_INNER_PATH", "claim": "No infeasibility certificate"})
    return None
