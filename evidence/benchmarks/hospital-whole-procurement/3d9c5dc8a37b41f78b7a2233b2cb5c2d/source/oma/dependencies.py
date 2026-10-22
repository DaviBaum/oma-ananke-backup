"""Conservative semantic invalidation and certified finite cyclic closure.

Sources: canonical THM-F5/F10, THM-RT16/18/19 (not the integration's
misnumbered RT15/17 imports); integration DEF-CMP218–243, THM-CMP32/79–85.
Dependency completeness and host-function applicability are explicit contracts.
Guarded reads catch undeclared accesses through the supplied input interface;
arbitrary hidden Python globals cannot be inferred and must be versioned inputs.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, asdict
from fractions import Fraction
import hashlib
import itertools
import json
import math
from typing import Callable, Any


def _json(value):
    if isinstance(value, Fraction):
        return ["rational", str(value)]
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Nonfinite artifact value")
    if isinstance(value, dict):
        if any(not isinstance(k, str) for k in value):
            raise ValueError("Artifact map keys must be strings")
        return ["map", [[k, _json(value[k])] for k in sorted(value)]]
    if isinstance(value, (list, tuple)):
        return ["sequence", [_json(v) for v in value]]
    if value is None or isinstance(value, (str, int, float, bool)):
        return [type(value).__name__, value.hex() if isinstance(value, float) else value]
    raise TypeError(f"Artifact is not canonically serializable: {type(value).__name__}")


def _hash(value):
    return hashlib.sha256(json.dumps(_json(value), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class CacheContext:
    theory: str
    objective: str
    experiment_family: str
    checker: str
    environment: str
    tool_version: str
    scope: str

    def __post_init__(self):
        if any(not isinstance(v, str) or not v for v in asdict(self).values()):
            raise ValueError("Every semantic cache context field requires an explicit version")


@dataclass(frozen=True)
class Value:
    value: Any = None
    status: str = "READY"
    reason: str = ""

    def __post_init__(self):
        if self.status not in ("READY", "UNKNOWN", "FAILED"):
            raise ValueError("Artifact status must be READY, UNKNOWN or FAILED")
        _json(self.value)


@dataclass(frozen=True)
class DerivedNode:
    id: str
    dependencies: tuple[str, ...]
    compute: Callable[[Mapping], Any]
    version: str
    lattice_values: tuple[Any, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "dependencies", tuple(sorted(self.dependencies)))
        if not self.id or not self.version or len(set(self.dependencies)) != len(self.dependencies):
            raise ValueError("Node identity, version and distinct dependencies required")
        if len({_hash(v) for v in self.lattice_values}) != len(self.lattice_values):
            raise ValueError("Finite lattice chain contains duplicate values")


class UndeclaredDependency(KeyError):
    pass


class GuardedInputs(Mapping):
    def __init__(self, values, allowed):
        self._values, self._allowed = values, frozenset(allowed)

    def __getitem__(self, key):
        if key not in self._allowed:
            raise UndeclaredDependency(f"Undeclared semantic read: {key}")
        return deepcopy(self._values[key])

    def __iter__(self):
        return iter(sorted(self._allowed))

    def __len__(self):
        return len(self._allowed)

    def get(self, key, default=None):
        if key not in self._allowed:
            raise UndeclaredDependency(f"Undeclared semantic read: {key}")
        return deepcopy(self._values.get(key, default))

    def __contains__(self, key):
        if key not in self._allowed:
            raise UndeclaredDependency(f"Undeclared semantic read: {key}")
        return key in self._values


@dataclass(frozen=True)
class _Artifact:
    result: Value
    key: str


@dataclass
class BuildReport:
    values: dict[str, Value]
    artifact_keys: dict[str, str]
    recomputed: tuple[str, ...]
    reused: tuple[str, ...]
    cycle_certificates: dict[str, dict]

    @property
    def semantic_root(self):
        return _hash({"values": {k: asdict(v) for k, v in self.values.items()}, "keys": self.artifact_keys})


def invalidation_closure(nodes, changed_ids):
    """Every reachable consumer is affected, across zones and through cycles."""
    consumers = {}
    for node in nodes:
        for parent in node.dependencies:
            consumers.setdefault(parent, set()).add(node.id)
    affected, frontier = set(changed_ids), list(changed_ids)
    while frontier:
        parent = frontier.pop()
        for child in consumers.get(parent, ()):
            if child not in affected:
                affected.add(child)
                frontier.append(child)
    return frozenset(affected)


def _components(nodes):
    # Iterative Kosaraju avoids Python recursion limits on long engineering
    # dependency chains. Edges point from a consumer to its prerequisites.
    outgoing = {name: [dep for dep in node.dependencies if dep in nodes] for name, node in nodes.items()}
    incoming = {name: [] for name in nodes}
    for name, dependencies in outgoing.items():
        for dep in dependencies:
            incoming[dep].append(name)
    visited, finish = set(), []
    for root in sorted(nodes):
        stack = [(root, False)]
        while stack:
            name, expanded = stack.pop()
            if expanded:
                finish.append(name)
            elif name not in visited:
                visited.add(name)
                stack.append((name, True))
                stack.extend((dep, False) for dep in reversed(outgoing[name]) if dep not in visited)
    assigned, components = set(), []
    for root in reversed(finish):
        if root in assigned:
            continue
        stack, component = [root], []
        assigned.add(root)
        while stack:
            name = stack.pop()
            component.append(name)
            for consumer in incoming[name]:
                if consumer not in assigned:
                    assigned.add(consumer)
                    stack.append(consumer)
        components.append(tuple(sorted(component)))
    return list(reversed(components))


class DependencyEngine:
    def __init__(self, nodes, *, dependencies_complete: bool):
        nodes = tuple(nodes)
        self.nodes = {node.id: node for node in nodes}
        if len(self.nodes) != len(nodes):
            raise ValueError("Duplicate derived identity")
        self.dependencies_complete = dependencies_complete
        self._cache = {}
        self._cycle_cache = {}
        self._graph_hash = _hash([{ "id": n.id, "dependencies": n.dependencies, "version": n.version,
                                  "lattice": n.lattice_values} for n in sorted(nodes, key=lambda n: n.id)])

    def _call(self, node, values):
        result = node.compute(GuardedInputs(values, node.dependencies))
        result = result if isinstance(result, Value) else Value(result)
        return deepcopy(result)

    def build(self, inputs, context: CacheContext, *, cold=False, max_lattice_states=10_000, max_cycle_rounds=10_000):
        if set(inputs) & self.nodes.keys():
            raise ValueError("Source input cannot shadow derived node")
        if max_lattice_states < 1 or max_cycle_rounds < 1:
            raise ValueError("Closure budgets must be positive")
        artifacts = {k: _Artifact(deepcopy(v if isinstance(v, Value) else Value(v)), _hash({"source": k, "value": asdict(v if isinstance(v, Value) else Value(v))}))
                     for k, v in inputs.items()}
        recomputed, reused, certificates = [], [], {}
        for component in _components(self.nodes):
            external = sorted({dep for name in component for dep in self.nodes[name].dependencies if dep not in component})
            missing = [dep for dep in external if dep not in artifacts]
            blocked = [dep for dep in external if dep in artifacts and artifacts[dep].result.status != "READY"]
            base = {"context": asdict(context), "graph": self._graph_hash, "component": component,
                    "external": {dep: artifacts[dep].key if dep in artifacts else "MISSING" for dep in external},
                    "dependencies_complete": self.dependencies_complete,
                    "closure_budgets": [max_lattice_states, max_cycle_rounds]}
            component_key = _hash(base)
            keys = {name: _hash({"component": component_key, "node": name}) for name in component}
            if not cold and all(name in self._cache and self._cache[name].key == keys[name] and self._cache[name].result.status == "READY" for name in component):
                for name in component:
                    artifacts[name] = deepcopy(self._cache[name])
                    reused.append(name)
                if component_key in self._cycle_cache:
                    certificates[component_key] = deepcopy(self._cycle_cache[component_key])
                continue
            if not self.dependencies_complete:
                results = {name: Value(status="UNKNOWN", reason="DEPENDENCIES_NOT_DECLARED_COMPLETE") for name in component}
            elif missing or blocked:
                results = {name: Value(status="UNKNOWN", reason="UNRESOLVED_INPUTS:" + ",".join(missing + blocked)) for name in component}
            else:
                cyclic = len(component) > 1 or component[0] in self.nodes[component[0]].dependencies
                values = {dep: artifacts[dep].result.value for dep in external}
                try:
                    if cyclic:
                        results, certificate = self._close(component, values, max_lattice_states, max_cycle_rounds)
                        if certificate is not None:
                            certificates[component_key] = certificate
                            self._cycle_cache[component_key] = deepcopy(certificate)
                    else:
                        name = component[0]
                        results = {name: self._call(self.nodes[name], values)}
                except UndeclaredDependency as exc:
                    results = {name: Value(status="FAILED", reason=str(exc)) for name in component}
                except Exception as exc:
                    results = {name: Value(status="FAILED", reason=f"DERIVATION_ERROR:{type(exc).__name__}:{exc}") for name in component}
            for name in component:
                artifacts[name] = _Artifact(deepcopy(results[name]), keys[name])
                self._cache[name] = deepcopy(artifacts[name])
                recomputed.append(name)
        return BuildReport({k: deepcopy(a.result) for k, a in artifacts.items()},
                           {k: a.key for k, a in artifacts.items()}, tuple(recomputed), tuple(reused), certificates)

    def _close(self, component, external, maximum_states, maximum_rounds):
        nodes = [self.nodes[name] for name in component]
        sizes = [len(node.lattice_values) for node in nodes]
        unknown = lambda reason: ({name: Value(status="UNKNOWN", reason=reason) for name in component}, None)
        if not all(sizes):
            return unknown("CYCLE_FINITE_LATTICE_MISSING")
        count = math.prod(sizes)
        if count > maximum_states:
            return unknown("CYCLE_MONOTONICITY_BUDGET")
        ranks = [{_hash(v): i for i, v in enumerate(node.lattice_values)} for node in nodes]
        table = {}
        for state in itertools.product(*(range(size) for size in sizes)):
            values = external | {name: deepcopy(nodes[i].lattice_values[state[i]]) for i, name in enumerate(component)}
            output = []
            for i, node in enumerate(nodes):
                result = self._call(node, values)
                if result.status != "READY":
                    return unknown("CYCLE_OPERATOR_UNRESOLVED")
                rank = ranks[i].get(_hash(result.value))
                if rank is None:
                    return unknown("CYCLE_OPERATOR_LEAVES_LATTICE")
                output.append(rank)
            table[state] = tuple(output)
        covers = 0
        for state, output in table.items():
            for axis, size in enumerate(sizes):
                if state[axis] + 1 == size:
                    continue
                above = state[:axis] + (state[axis] + 1,) + state[axis + 1:]
                covers += 1
                if any(a > b for a, b in zip(output, table[above])):
                    return unknown("CYCLE_OPERATOR_NOT_MONOTONE")
        state, trace = tuple(0 for _ in sizes), []
        for _ in range(maximum_rounds):
            trace.append(state)
            following = table[state]
            if following == state:
                certificate = {"kind": "FINITE_PRODUCT_CHAIN_LEAST_FIXED_POINT", "component": component,
                               "sizes": sizes, "table": [[list(k), list(v)] for k, v in sorted(table.items())],
                               "trace": trace, "fixed_point": state, "checked_cover_relations": covers}
                return ({name: Value(deepcopy(nodes[i].lattice_values[state[i]])) for i, name in enumerate(component)}, certificate)
            state = following
        return unknown("CYCLE_ITERATION_BUDGET")

    def compare_with_cold(self, inputs, context, **kwargs):
        incremental = self.build(inputs, context, **kwargs)
        cold = DependencyEngine(self.nodes.values(), dependencies_complete=self.dependencies_complete).build(inputs, context, cold=True, **kwargs)
        return {"equivalent": incremental.semantic_root == cold.semantic_root,
                "incremental_root": incremental.semantic_root, "cold_root": cold.semantic_root,
                "reused": incremental.reused, "recomputed": incremental.recomputed}


def verify_closure_certificate(certificate, *, max_states=10_000):
    """Independent finite-table checker, without calling derivation functions."""
    try:
        sizes = certificate["sizes"]
        if not sizes or any(type(s) is not int or s < 1 for s in sizes):
            return "FAIL"
        if math.prod(sizes) > max_states:
            return "UNKNOWN"
        pairs = certificate["table"]
        table = {tuple(state): tuple(result) for state, result in pairs}
        states = set(itertools.product(*(range(size) for size in sizes)))
        if len(pairs) != len(table) or set(table) != states or any(result not in states for result in table.values()):
            return "FAIL"
        covers = 0
        for state in states:
            for axis, size in enumerate(sizes):
                if state[axis] < size - 1:
                    covers += 1
                    upper = list(state)
                    upper[axis] += 1
                    if any(a > b for a, b in zip(table[state], table[tuple(upper)])):
                        return "FAIL"
        if certificate["checked_cover_relations"] != covers:
            return "FAIL"
        state, trace = tuple(0 for _ in sizes), []
        for _ in range(sum(sizes) + 1):
            trace.append(state)
            following = table[state]
            if following == state:
                return "PASS" if state == tuple(certificate["fixed_point"]) and trace == [tuple(s) for s in certificate["trace"]] else "FAIL"
            state = following
        return "FAIL"
    except (KeyError, TypeError, ValueError):
        return "FAIL"
