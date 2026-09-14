"""Incremental, cold-compared derived state for real project revisions.

This module derives inventory, declared connectivity, mission coverage and
complete physical/service input fingerprints. It does not reuse CAD PASS across
different roots or substitute input fingerprints for geometric calculations.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict
import time

from .dependencies import CacheContext, DependencyEngine, DerivedNode, invalidation_closure
from .store import digest


VERSION = "oma-project-dependencies/1"


def _indexed(records, label):
    index = {record["id"]: record for record in records}
    if len(index) != len(records):
        raise ValueError(f"Duplicate {label} identity prevents an exact dependency projection")
    return index


def _entity_projection(entities):
    # The digest covers every field, including properties that this particular
    # inventory does not inspect. Large raw IFC property dictionaries need not
    # be repeatedly copied and recursively re-encoded by the dependency cache.
    return {"content_hash": digest(entities), "entity_count": len(entities),
            "geometry": dict(Counter(e.get("geometry", {}).get("status", "unresolved") for e in entities)),
            "protected_count": sum(bool(e.get("protected", True)) for e in entities)}


def project_inputs(state, *, source_ids, route_ids, report=None):
    sources = _indexed(state.get("sources", []), "source")
    routes = _indexed(state.get("routes", []), "route")
    entities = defaultdict(list)
    for entity in state.get("entities", []):
        entities[entity.get("provenance", {}).get("source_id", "UNKNOWN")].append(entity)
    result = {"snapshot:root": digest(state), "snapshot:field-index": sorted(state)}
    for key, value in state.items():
        if key not in {"sources", "entities", "routes"}:
            result[f"state:{key}"] = value
    for key, default in (("ports", []), ("explicit_connections", []), ("inferred_connections", []),
                         ("mission", None), ("derived_artifacts", {}), ("numerical_policy", {}), ("units", "m")):
        result.setdefault("state:" + key, default)
    result["source:index"] = sorted(sources)
    result["route:index"] = sorted(routes)
    for identifier in source_ids:
        result[f"source-record:{identifier}"] = sources.get(identifier)
        result[f"entity-records:{identifier}"] = _entity_projection(entities.pop(identifier, []))
    result["entities:unattributed"] = {key: _entity_projection(records) for key, records in entities.items()}
    for identifier in route_ids:
        result[f"route-record:{identifier}"] = routes.get(identifier)
    result["evidence:report"] = report
    return result


def _source_inventory(inputs, identifier):
    source = inputs[f"source-record:{identifier}"]
    entities = inputs[f"entity-records:{identifier}"]
    # Both units and tolerance are declared dependencies even though this
    # inventory only reports the source's supplied geometry classifications.
    units, policy = inputs["state:units"], inputs["state:numerical_policy"]
    return {"source_id": identifier, "present": source is not None, "entity_count": entities["entity_count"],
            "geometry": entities["geometry"], "protected_count": entities["protected_count"],
            "source_hash": (source or {}).get("sha256"), "transform": (source or {}).get("transform_m"),
            "units": units, "numerical_policy_hash": digest(policy), "source_blockers": (source or {}).get("blockers", []),
            "claim": "Persisted source inventory; native geometry is not re-evaluated by this derivation"}


def _netlist(inputs, route_ids):
    ports = _indexed(inputs["state:ports"], "port")
    parent = {p: p for p in ports}
    def root(p):
        while parent[p] != p:
            parent[p] = parent[parent[p]]
            p = parent[p]
        return p
    invalid, links = [], []
    for pair in inputs["state:explicit_connections"]:
        if len(pair) != 2 or any(p not in ports for p in pair):
            invalid.append(pair)
            continue
        left, right = pair
        parent[root(left)] = root(right)
        links.append(pair)
    declared = []
    for identifier in route_ids:
        route = inputs[f"route-record:{identifier}"]
        if route:
            declared.append({"route_id": identifier, "ports": route.get("port_ids", []), "demands": route.get("demand_ids", []),
                             "unresolved_ports": [p for p in route.get("port_ids", []) if p not in ports]})
    return {"explicit_port_count": len(ports), "explicit_connection_count": len(links),
            "explicit_components": len({root(p) for p in ports}), "invalid_explicit_connections": invalid,
            "port_position_status": dict(Counter(p.get("position_status", "MISSING") for p in ports.values())),
            "port_ownership_status": dict(Counter(p.get("ownership_status", "UNVERIFIED") for p in ports.values())),
            "declared_route_links": declared, "inferred_connection_count": len(inputs["state:inferred_connections"]),
            "inferred_connections_promoted_to_explicit": False,
            "claim": "Declared state connectivity, not a physical port attachment or hydraulic certificate"}


def _coverage(inputs, route_ids):
    mission = inputs["state:mission"]
    if mission is None:
        return {"status": "MISSING_MISSION", "demands": [], "claim": "No service adequacy inference"}
    ports = _indexed(inputs["state:ports"], "port")
    routes = [inputs[f"route-record:{identifier}"] for identifier in route_ids]
    records = []
    for demand in mission.get("demands", []):
        assigned = [r for r in routes if r and demand["id"] in r.get("demand_ids", [])]
        required = {demand["source_port"], *demand.get("sink_ports", [])}
        reached = set().union(*(set(r.get("port_ids", [])) for r in assigned))
        records.append({"demand_id": demand["id"], "routes": [r["id"] for r in assigned],
            "missing_route_terminals": sorted(required - reached), "missing_state_ports": sorted(required - ports.keys()),
            "section_matches": bool(assigned) and all(r.get("section") == demand["section"] for r in assigned),
            "service_matches": bool(assigned) and all(r.get("service") == demand["service"] for r in assigned)})
    complete = bool(records) and all(r["routes"] and not r["missing_route_terminals"] and not r["missing_state_ports"]
                                       and r["section_matches"] and r["service_matches"] for r in records)
    return {"status": "SATISFIED_IN_DECLARED_STATE" if complete else "UNRESOLVED", "demands": records,
            "claim": "Demand membership and required metadata only; connected physical paths remain independently checked"}


def _fingerprint(inputs, kind):
    return {"input_hash": digest({key: inputs[key] for key in inputs}), "derivation": kind,
            "engineering_verdict": "NOT_RUN", "reuse_contract": "Input equivalence only; a numerical artifact requires its own checked applicability"}


def _check_applicability(inputs, executable):
    report = inputs["evidence:report"]
    if not report:
        return {"status": "NOT_RUN", "reason": "No independent report supplied for this revision"}
    mission = inputs["state:mission"]
    mismatches = []
    for field, value in (("candidate_root", inputs["snapshot:root"]), ("mission_hash", digest(mission)),
                         ("rule_hash", (mission or {}).get("rule_hash", "baseline-unapproved-contact-policy")),
                         ("checker_version", executable)):
        if report.get(field) != value:
            mismatches.append(field)
    return {"status": "INAPPLICABLE" if mismatches else "CURRENT_RECORDED_REPORT", "mismatches": mismatches,
            "recorded_status": report.get("status"), "scope": report.get("scope"),
            "external_artifact_bytes": "NOT_REHASHED_BY_METADATA_DERIVATION"}


def build_nodes(source_ids, route_ids, input_keys, executable):
    nodes = []
    for identifier in source_ids:
        deps = (f"source-record:{identifier}", f"entity-records:{identifier}", "state:units", "state:numerical_policy")
        nodes.append(DerivedNode(f"inventory:{identifier}", deps,
            lambda values, identifier=identifier: _source_inventory(values, identifier), VERSION))
    route_keys = tuple(f"route-record:{i}" for i in route_ids)
    nodes.append(DerivedNode("netlist", ("state:ports", "state:explicit_connections", "state:inferred_connections", *route_keys),
                            lambda values: _netlist(values, route_ids), VERSION))
    nodes.append(DerivedNode("mission-coverage", ("state:mission", "state:ports", *route_keys),
                            lambda values: _coverage(values, route_ids), VERSION))
    for identifier in route_ids:
        nodes.append(DerivedNode(f"route-shape:{identifier}", (f"route-record:{identifier}", "state:units", "state:numerical_policy", "state:derived_artifacts"),
            lambda values: _fingerprint(values, "Physical route shape inputs"), VERSION))
        # All source products and every route remain dependencies of clearance.
        # A far-away system is never omitted solely because of its distance.
        nodes.append(DerivedNode(f"route-clearance:{identifier}", (f"route-shape:{identifier}", *route_keys,
            *(f"source-record:{i}" for i in source_ids), *(f"entity-records:{i}" for i in source_ids),
            "entities:unattributed", "state:mission", "state:derived_artifacts", "state:numerical_policy"),
            lambda values: _fingerprint(values, "Full-federation physical clearance inputs"), VERSION))
        nodes.append(DerivedNode(f"route-service:{identifier}", (f"route-shape:{identifier}", "netlist", "mission-coverage",
            "state:mission", "state:derived_artifacts"), lambda values: _fingerprint(values, "Nonlocal service and demand inputs"), VERSION))
    nodes.append(DerivedNode("independent-check-applicability", ("snapshot:root", "state:mission", "evidence:report"),
        lambda values: _check_applicability(values, executable), VERSION))
    # Account for every authoritative field, including future extension fields.
    nodes.append(DerivedNode("complete-state-inputs", tuple(sorted(input_keys)),
        lambda values: _fingerprint(values, "Every persisted authoritative field"), VERSION))
    return nodes


def derive_transition(before, after, *, executable, before_report=None, after_report=None):
    started = time.perf_counter()
    source_ids = sorted({s["id"] for state in (before, after) for s in state.get("sources", [])})
    route_ids = sorted({r["id"] for state in (before, after) for r in state.get("routes", [])})
    left = project_inputs(before, source_ids=source_ids, route_ids=route_ids, report=before_report)
    right = dict(left) if before is after and before_report == after_report else project_inputs(after, source_ids=source_ids, route_ids=route_ids, report=after_report)
    # Missing extension fields are explicit inputs, not hidden changed guards.
    for key in left.keys() | right.keys():
        left.setdefault(key, {"absent_authoritative_field": True})
        right.setdefault(key, {"absent_authoritative_field": True})
    nodes = build_nodes(source_ids, route_ids, right, executable)
    context = CacheContext(VERSION, "explicit-state-obligations", "persisted-project-states", executable,
                           "SI-and-versioned-state-inputs", VERSION, "inventory-netlist-coverage-applicability-and-input-fingerprints")
    engine = DependencyEngine(nodes, dependencies_complete=True)
    prior = engine.build(left, context)
    current = engine.build(right, context)
    cold = DependencyEngine(nodes, dependencies_complete=True).build(right, context, cold=True)
    changed = sorted(key for key in right if digest(left[key]) != digest(right[key]))
    affected = sorted(invalidation_closure(nodes, changed) & engine.nodes.keys())
    semantic_changes = sorted(node.id for node in nodes if asdict(prior.values[node.id]) != asdict(current.values[node.id]))
    equivalent = current.semantic_root == cold.semantic_root
    return {"schema": VERSION, "before_root": left["snapshot:root"], "after_root": right["snapshot:root"],
            "changed_authoritative_inputs": changed, "conservatively_affected": affected,
            "semantic_output_changes": semantic_changes, "recomputed": list(current.recomputed), "reused": list(current.reused),
            "cold_equivalent": equivalent, "incremental_root": current.semantic_root, "cold_root": cold.semantic_root,
            "input_roots": {key: digest(value) for key, value in right.items()},
            "dependencies": {node.id: list(node.dependencies) for node in nodes},
            "artifacts": {node.id: {**asdict(current.values[node.id]), "artifact_key": current.artifact_keys[node.id]} for node in nodes},
            "elapsed_seconds": time.perf_counter() - started,
            "physical_checks_reused_across_roots": False,
            "scope": "Actual state inventory, declared netlist, mission membership, applicability and complete derived-input invalidation; native CAD and simulation recomputation remains a separate checker operation"}
