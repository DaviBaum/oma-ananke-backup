"""Account for installed IFC service topology without inventing design roles.

This consumes the imported ``oma-ifc-audit/1`` dictionary, not mesh proximity.
The caller must revalidate the original IFC SHA and audit provenance. Connected
components describe explicit port relationships and unique ownership only;
neither a component nor an IFC SOURCE/SINK port establishes engineering duty.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from functools import lru_cache
import hashlib
import json
import re
from typing import Callable

SCHEMA = "oma.installed-service-networks/1"
DISCIPLINES = frozenset({"HVAC", "PLUMBING", "ELECTRICAL", "FIRE", "ARCHITECTURE", "STRUCTURE", "MIXED", "UNKNOWN"})
_MISSING_DESIGN = ["ENGINEERING_TERMINAL_ROLES", "DEMAND_AND_BOUNDARY_CONDITIONS",
                   "MATERIAL_AND_INSTALLATION_APPLICABILITY", "DESIGN_LIMITS_AND_APPROVAL_BASIS",
                   "GEOMETRY_AND_FEDERATION_VERIFICATION", "CATALOGUE_AND_COSTS"]
_STRUCTURAL = {"IfcBeam", "IfcColumn", "IfcFooting", "IfcPile", "IfcMember", "IfcReinforcingElement", "IfcTendon"}
_HVAC = {"IfcDuctSegment", "IfcDuctFitting", "IfcDuctSilencer", "IfcAirTerminal", "IfcAirTerminalBox",
         "IfcDamper", "IfcFan", "IfcAirToAirHeatRecovery", "IfcCoil", "IfcChiller", "IfcBoiler",
         "IfcEvaporativeCooler", "IfcEvaporator", "IfcCondenser", "IfcCoolingTower", "IfcSpaceHeater",
         "IfcHumidifier", "IfcHeatExchanger", "IfcFilter", "IfcCompressor"}
_ELECTRICAL = {"IfcCableSegment", "IfcCableFitting", "IfcCableCarrierSegment", "IfcCableCarrierFitting",
               "IfcElectricAppliance", "IfcElectricDistributionBoard", "IfcElectricDistributionPoint",
               "IfcElectricFlowStorageDevice", "IfcElectricGenerator", "IfcElectricMotor", "IfcTransformer",
               "IfcSwitchingDevice", "IfcProtectiveDevice", "IfcProtectiveDeviceTrippingUnit",
               "IfcLightFixture", "IfcLamp", "IfcOutlet", "IfcJunctionBox", "IfcCommunicationsAppliance"}
_PIPE = {"IfcPipeSegment", "IfcPipeFitting", "IfcValve", "IfcPump", "IfcTank", "IfcSanitaryTerminal",
         "IfcWasteTerminal", "IfcInterceptor"}


def _encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def _hash(value):
    return hashlib.sha256(_encoded(value)).hexdigest()


def _step(value):
    return type(value) is int and value > 0


@lru_cache(maxsize=512)
def _ancestry(schema, name):
    """Use the installed IFC schema, including generic IFC2X3 distribution types."""
    import ifcopenshell.ifcopenshell_wrapper as wrapper
    try:
        entity = wrapper.schema_by_name(schema).declaration_by_name(name)
        result = set()
        while entity is not None:
            result.add(entity.name())
            entity = entity.supertype()
        return frozenset(result)
    except (RuntimeError, AttributeError):
        return frozenset()


class _Disjoint:
    def __init__(self):
        self.parent = {}
        self.size = {}

    def add(self, node):
        self.parent.setdefault(node, node)
        self.size.setdefault(node, 1)

    def root(self, node):
        while self.parent[node] != node:
            self.parent[node] = self.parent[self.parent[node]]
            node = self.parent[node]
        return node

    def join(self, a, b):
        a, b = self.root(a), self.root(b)
        if a == b:
            return False
        if self.size[a] < self.size[b] or (self.size[a] == self.size[b] and a > b):
            a, b = b, a
        self.parent[b] = a
        self.size[a] += self.size[b]
        return True


def extract_service_networks(audit: dict, *, source_sha256: str | None = None,
                             source_discipline: str | None = None,
                             checkpoint: Callable[[str], None] | None = None,
                             max_records: int = 2_000_000,
                             max_input_bytes: int = 512 * 1024 * 1024) -> dict:
    """Return a deterministic, source-bound inventory and explicit multigraph.

    All product/port/connection/system records are retained, with source-record
    hashes and normalized indices. Architecture/structure are accounted apart
    from services. Unclassified physical objects remain visible; an explicit
    caller discipline can include portless proxy equipment in service coverage.

    Invalid/duplicate STEP identities and wrong source binding raise ValueError;
    incomplete or contradictory topology is returned with issues, never PASS.
    Missing port endpoints receive unresolved graph nodes, not inferred edges.
    System membership never creates a physical connection. Checkpoint exceptions
    propagate. Mutation during a checkpoint invalidates the complete result.
    """
    if not isinstance(audit, dict):
        raise ValueError("An imported audit dictionary is required")
    if type(max_records) is not int or not 1 <= max_records <= 10_000_000:
        raise ValueError("max_records must be a bounded positive integer")
    if type(max_input_bytes) is not int or not 1 <= max_input_bytes <= 2_147_483_648:
        raise ValueError("max_input_bytes must be a bounded positive integer")
    if source_discipline is not None and source_discipline not in DISCIPLINES:
        raise ValueError("Explicit supported source discipline required")
    fields = ("products", "ports", "explicit_connections", "systems")
    for name in fields:
        if name in audit and not isinstance(audit[name], list):
            raise ValueError(f"{name} must be a list")
    references = sum(len(row.get(key, [])) for name, key in (("ports", "owner_step_ids"), ("systems", "members"))
                     for row in audit.get(name, []) if isinstance(row, dict) and isinstance(row.get(key), list))
    if sum(len(audit.get(name, [])) for name in fields) + references > max_records:
        raise ValueError("Installed topology record budget exhausted")
    original = _encoded(audit)
    if len(original) > max_input_bytes:
        raise ValueError("Imported audit byte budget exhausted")
    input_hash = hashlib.sha256(original).hexdigest()
    frozen = json.loads(original)
    del original
    source = source_sha256 or frozen.get("source_sha256")
    if not isinstance(source, str) or re.fullmatch(r"[0-9a-f]{64}", source) is None:
        raise ValueError("Exact source SHA256 required")
    if frozen.get("source_sha256") != source or frozen.get("source_id", source) != source:
        raise ValueError("Imported audit source binding mismatch")
    pulse = checkpoint or (lambda stage: None)
    pulse("service_networks_start")
    issues, issue_nodes = [], []

    def issue(code, nodes=(), **details):
        number = len(issues)
        issues.append({"id": number, "code": code, **details})
        issue_nodes.append(tuple(nodes))
        return number

    if frozen.get("audit_version") != "oma-ifc-audit/1":
        issue("AUDIT_VERSION_UNRECOGNIZED", declared=frozen.get("audit_version"))
    for name in fields:
        if name not in frozen:
            issue("AUDIT_COLLECTION_MISSING", collection=name)
    schema = frozen.get("schema", "IFC4")
    if not isinstance(schema, str):
        raise ValueError("IFC schema name must be a string")
    if "schema" not in frozen:
        issue("IFC_SCHEMA_MISSING_DEFAULT_CLASSIFICATION_ONLY")
    graph = _Disjoint()

    def records(name, key):
        rows = frozen.get(name, [])
        result = {}
        for row in rows:
            if not isinstance(row, dict) or not _step(row.get(key)):
                raise ValueError(f"{name} requires positive integer {key}")
            if row[key] in result:
                raise ValueError(f"Duplicate {name} STEP identity: {row[key]}")
            for field in ("source_sha256", "source_id"):
                if field in row and row[field] != source:
                    raise ValueError("Cross-source record in single-source audit")
            if "entity_id" in row and row["entity_id"] != f"{source}:{row[key]}":
                raise ValueError("Source-qualified entity identity mismatch")
            result[row[key]] = row
        return dict(sorted(result.items()))

    products = records("products", "step_id")
    ports = records("ports", "step_id")
    edges = records("explicit_connections", "relationship_step_id")
    systems = records("systems", "step_id")
    if set(systems) & (set(products) | set(ports) | set(edges)) or set(edges) & (set(products) | set(ports)):
        raise ValueError("IFC STEP identity reused by incompatible audit record categories")
    declared_denominators_consistent = True
    actual_counts = {"product_count": len(products),
                     "physical_object_count": sum(row.get("physical") is True for row in products.values()),
                     "product_counts": dict(Counter(row.get("type") for row in products.values()))}
    for key, actual in actual_counts.items():
        if key in frozen and _encoded(frozen[key]) != _encoded(actual):
            declared_denominators_consistent = False
            issue("AUDIT_DENOMINATOR_MISMATCH", field=key, declared=frozen[key], accounted=actual)
    if isinstance(frozen.get("entity_counts"), dict) and "IfcDistributionPort" in frozen["entity_counts"]:
        declared = frozen["entity_counts"]["IfcDistributionPort"]
        if type(declared) is not int or declared != len(ports):
            declared_denominators_consistent = False
            issue("AUDIT_DENOMINATOR_MISMATCH", field="entity_counts.IfcDistributionPort", declared=declared, accounted=len(ports))
    ancestors, product_output, categories, service_products = {}, {}, {}, set()
    ownership = defaultdict(list)
    for pid, row in ports.items():
        owners = row.get("owner_step_ids")
        if isinstance(owners, list):
            for oid in owners:
                if _step(oid):
                    ownership[oid].append(pid)
    system_members = defaultdict(set)
    for sid, row in systems.items():
        members = row.get("members")
        if not isinstance(members, list) or any(not _step(m) for m in members):
            issue("SYSTEM_MEMBERS_INVALID", system_step_id=sid)
            members = []
        if len(members) != len(set(members)):
            issue("SYSTEM_MEMBERS_REPEATED", system_step_id=sid)
        for member in set(members):
            system_members[member].add(sid)
            if member not in products and member not in ports:
                issue("SYSTEM_MEMBER_NOT_IN_PRODUCT_AUDIT", system_step_id=sid, member_step_id=member)
    for index, (eid, row) in enumerate(products.items()):
        if index % 2048 == 0:
            pulse("service_networks_products")
        kind = row.get("type")
        if not isinstance(kind, str):
            raise ValueError("Product IFC type required")
        lineage = _ancestry(schema, kind)
        ancestors[eid] = lineage
        families = set()
        if kind in _HVAC:
            families.add("HVAC")
        if kind in _PIPE:
            families.add("PIPE")
        if kind in _ELECTRICAL:
            families.add("ELECTRICAL")
        if kind == "IfcFireSuppressionTerminal":
            families.add("FIRE")
        if "IfcPort" in lineage or eid in ports:
            category = "PORT"
        elif "IfcDistributionElement" in lineage or ((eid in ownership or eid in system_members)
                                                     and (row.get("physical") is True or "IfcElement" in lineage)):
            category = "SERVICE"
        elif (kind == "IfcBuildingElementProxy" or not lineage) and row.get("physical") is True:
            category = ("SERVICE" if source_discipline in {"HVAC", "PLUMBING", "ELECTRICAL", "FIRE"}
                        else source_discipline if source_discipline in {"ARCHITECTURE", "STRUCTURE"}
                        else "UNCLASSIFIED_PHYSICAL")
        elif any(c in lineage for c in _STRUCTURAL):
            category = "STRUCTURE"
        elif "IfcElement" in lineage:
            category = "ARCHITECTURE"
        else:
            category = "SPATIAL_OR_OTHER"
        categories[eid] = category
        if category in {"SERVICE", "UNCLASSIFIED_PHYSICAL"}:
            service_products.add(eid)
            graph.add(("product", eid))
            if not families:
                families.add("SERVICE_UNSPECIFIED")
            if category == "UNCLASSIFIED_PHYSICAL":
                issue("PHYSICAL_SERVICE_CLASSIFICATION_UNRESOLVED", (("product", eid),), product_step_id=eid)
            if not ownership[eid]:
                issue("PRODUCT_WITHOUT_PORTS", (("product", eid),), product_step_id=eid)
        product_output[eid] = {**row, "source_record_sha256": _hash(row), "category": category,
                               "service_families": sorted(families),
                               "explicit_system_step_ids": sorted(system_members[eid]),
                               "declared_terminal_type": "IfcFlowTerminal" in lineage}
        declared = row.get("system_ids", [])
        try:
            declared_ids = {int(s) for s in declared if not isinstance(s, bool)}
        except (TypeError, ValueError):
            declared_ids = set()
        if ("system_ids" in row and declared_ids != system_members[eid]):
            issue("PRODUCT_SYSTEM_MEMBERSHIP_CONTRADICTION", (("product", eid),), product_step_id=eid,
                  product_declared=sorted(declared_ids), system_declared=sorted(system_members[eid]))

    port_output, valid_owner = {}, {}
    for index, (pid, row) in enumerate(ports.items()):
        if index % 2048 == 0:
            pulse("service_networks_ports")
        node = ("port", pid)
        graph.add(node)
        owners = row.get("owner_step_ids")
        if not isinstance(owners, list) or any(not _step(v) for v in owners):
            issue("PORT_OWNERS_INVALID", (node,), port_step_id=pid)
            candidates = []
        else:
            candidates = sorted(set(owners))
            if len(candidates) != len(owners):
                issue("PORT_OWNERS_REPEATED", (node,), port_step_id=pid)
        expected_status = "unique" if len(candidates) == 1 else "ambiguous" if candidates else "missing"
        if (("owner_status" in row and row["owner_status"] != expected_status)
                or ("owner_step_id" in row and row["owner_step_id"] != (candidates[0] if len(candidates) == 1 else None))):
            issue("PORT_OWNER_FIELDS_CONTRADICT", (node,), port_step_id=pid)
        if not candidates:
            issue("PORT_OWNER_MISSING", (node,), port_step_id=pid)
        elif len(candidates) > 1:
            issue("PORT_OWNER_AMBIGUOUS", (node,), port_step_id=pid, declared_owner_step_ids=candidates)
        elif candidates[0] not in service_products:
            issue("PORT_OWNER_NOT_A_SERVICE_PRODUCT", (node,), port_step_id=pid, owner_step_id=candidates[0])
        else:
            valid_owner[pid] = candidates[0]
            graph.join(node, ("product", candidates[0]))
        if pid not in products:
            issue("PORT_MISSING_FROM_PRODUCT_AUDIT", (node,), port_step_id=pid)
        elif "IfcPort" not in ancestors[pid]:
            issue("PORT_PRODUCT_TYPE_CONTRADICTION", (node,), port_step_id=pid)
        if row.get("port_semantic_errors"):
            issue("IMPORTED_PORT_SEMANTIC_ERRORS", (node,), port_step_id=pid, errors=row["port_semantic_errors"])
        if row.get("flow_direction") not in {"SOURCE", "SINK", "SOURCEANDSINK", "NOTDEFINED"}:
            issue("PORT_FLOW_DIRECTION_MISSING_OR_INVALID", (node,), port_step_id=pid)
        port_output[pid] = {**row, "source_record_sha256": _hash(row),
                            "resolved_owner_step_id": valid_owner.get(pid), "engineering_terminal_role": None}
    for pid, category in categories.items():
        if category == "PORT" and pid not in ports:
            graph.add(("port", pid))
            issue("PRODUCT_PORT_MISSING_FROM_PORT_AUDIT", (("port", pid),), port_step_id=pid)

    edge_output, degree = {}, Counter()
    product_degree, peers, duplicate_pairs = Counter(), defaultdict(set), defaultdict(list)
    cycle_edges = []
    for index, (rid, row) in enumerate(edges.items()):
        if index % 2048 == 0:
            pulse("service_networks_connections")
        a, b = row.get("port_a_step_id"), row.get("port_b_step_id")
        if not _step(a) or not _step(b):
            raise ValueError("Explicit connection endpoint STEP identities required")
        nodes = (("port", a), ("port", b))
        for pid, node in zip((a, b), nodes):
            if node not in graph.parent:
                graph.add(node)
            if pid not in ports:
                issue("CONNECTION_ENDPOINT_MISSING", (node,), connection_step_id=rid, port_step_id=pid)
            degree[pid] += 1
        if a == b:
            issue("PORT_SELF_CONNECTION", nodes, connection_step_id=rid)
        if not graph.join(*nodes):
            cycle_edges.append(rid)
        duplicate_pairs[tuple(sorted((a, b)))].append(rid)
        oa, ob = valid_owner.get(a), valid_owner.get(b)
        if oa is not None and ob is not None:
            product_degree[oa] += 1
            product_degree[ob] += 1
            peers[oa].add(ob)
            peers[ob].add(oa)
            if oa == ob:
                issue("SAME_OWNER_PORT_CONNECTION", nodes, connection_step_id=rid, product_step_id=oa)
        if a in ports and b in ports:
            directions = (ports[a].get("flow_direction"), ports[b].get("flow_direction"))
            if directions in (("SOURCE", "SOURCE"), ("SINK", "SINK")):
                issue("CONNECTED_FLOW_DIRECTION_CONFLICT", nodes, connection_step_id=rid, directions=list(directions))
            for key in ("system_type", "predefined_type"):
                av, bv = ports[a].get(key), ports[b].get(key)
                if av not in (None, "NOTDEFINED") and bv not in (None, "NOTDEFINED") and av != bv:
                    issue("CONNECTED_PORT_DECLARATION_CONFLICT", nodes, connection_step_id=rid, field=key, values=[av, bv])
        realizer = row.get("realizing_element_step_id")
        if realizer is not None and realizer not in products:
            issue("CONNECTION_REALIZER_MISSING", nodes, connection_step_id=rid, realizing_element_step_id=realizer)
        edge_output[rid] = {**row, "source_record_sha256": _hash(row),
                            "resolved_owner_a_step_id": oa, "resolved_owner_b_step_id": ob,
                            "owner_connectivity_status": "EXPLICIT_UNIQUE_OWNERS" if oa is not None and ob is not None else "UNRESOLVED_OWNER"}
    for pid in sorted(degree):
        if degree[pid] > 1:
            issue("PORT_MULTIPLE_CONNECTIONS", (("port", pid),), port_step_id=pid, relationship_count=degree[pid])
    for pair, ids in sorted(duplicate_pairs.items()):
        if len(ids) > 1:
            issue("DUPLICATE_PORT_PAIR_RELATIONSHIPS", tuple(("port", p) for p in pair), connection_step_ids=ids)

    groups = defaultdict(lambda: {"products": [], "ports": [], "connections": [], "issues": set(), "cycles": []})
    for node in sorted(graph.parent):
        groups[graph.root(node)]["products" if node[0] == "product" else "ports"].append(node[1])
    for rid, row in edges.items():
        groups[graph.root(("port", row["port_a_step_id"]))]["connections"].append(rid)
    for rid in cycle_edges:
        groups[graph.root(("port", edges[rid]["port_a_step_id"]))]["cycles"].append(rid)
    for number, nodes in enumerate(issue_nodes):
        for node in nodes:
            if node in graph.parent:
                groups[graph.root(node)]["issues"].add(number)
    networks = []
    for index, group in enumerate(groups.values()):
        if index % 2048 == 0:
            pulse("service_networks_components")
        product_ids, port_ids = sorted(group["products"]), sorted(group["ports"])
        branch = [eid for eid in product_ids if len(peers[eid]) > 2]
        endpoints = [eid for eid in product_ids if len(peers[eid] - {eid}) == 1]
        unconnected = [pid for pid in port_ids if degree[pid] == 0]
        declared_terminals = [eid for eid in product_ids if product_output[eid]["declared_terminal_type"]]
        system_ids = sorted(set().union(*(system_members[eid] for eid in product_ids + port_ids)))
        families = sorted(set().union(*(product_output[eid]["service_families"] for eid in product_ids)))
        identity = {"source_sha256": source, "product_step_ids": product_ids, "port_step_ids": port_ids,
                    "connection_step_ids": sorted(group["connections"])}
        networks.append({"id": "service-network:" + _hash(identity), **identity,
                         "service_families": families or ["SERVICE_UNSPECIFIED"],
                         "source_discipline": source_discipline,
                         "system_step_ids": system_ids,
                         "issues": [issues[i] for i in sorted(group["issues"])],
                         "topology": {"branch_product_step_ids": branch, "cycle_rank": len(group["cycles"]),
                                      "cycle_closing_connection_step_ids": group["cycles"],
                                      "graph_kind": "EXPLICIT_OWNERSHIP_AND_CONNECTION_MULTIGRAPH",
                                      "physical_connectivity_verified": False},
                         "terminal_candidates": {"declared_ifc_terminal_product_step_ids": declared_terminals,
                                                 "degree_one_product_step_ids": endpoints,
                                                 "unconnected_port_step_ids": unconnected,
                                                 "engineering_role_inference": "NOT_PERFORMED"},
                         "portless_product_step_ids": [eid for eid in product_ids if not ownership[eid]],
                         "engineering_status": "UNKNOWN", "missing_design_inputs": list(_MISSING_DESIGN)})
    networks.sort(key=lambda n: n["id"])
    membership = defaultdict(list)
    for network in networks:
        for sid in network["system_step_ids"]:
            membership[sid].append(network["id"])
    system_output = [{**row, "source_record_sha256": _hash(row), "network_ids": sorted(membership[sid]),
                      "membership_is_connectivity": False} for sid, row in systems.items()]
    products_by_category = {category: sorted(eid for eid, c in categories.items() if c == category)
                            for category in sorted(set(categories.values()))}
    accounting = {"products_by_category": products_by_category,
                  "declared_audit_denominators_consistent": declared_denominators_consistent,
                  "all_products_accounted": sum(map(len, products_by_category.values())) == len(products),
                  "service_product_step_ids": sorted(service_products),
                  "all_service_products_in_exactly_one_network": sorted(eid for n in networks for eid in n["product_step_ids"]) == sorted(service_products),
                  "all_audited_ports_in_exactly_one_network": set(ports) <= {pid for n in networks for pid in n["port_step_ids"]},
                  "all_explicit_connections_in_exactly_one_network": sorted(rid for n in networks for rid in n["connection_step_ids"]) == sorted(edges),
                  "unresolved_port_step_ids": sorted({pid for n in networks for pid in n["port_step_ids"]} - set(ports)),
                  "original_source_completeness_verified": False}
    summary = {"source_product_count": len(products), "source_port_count": len(ports),
               "source_explicit_connection_count": len(edges), "source_system_count": len(systems),
               "service_product_count": len(service_products), "network_count": len(networks),
               "portless_service_product_count": sum(not ownership[eid] for eid in service_products),
               "category_counts": dict(sorted(Counter(categories.values()).items())),
               "issue_counts": dict(sorted(Counter(i["code"] for i in issues).items())),
               "branched_network_count": sum(bool(n["topology"]["branch_product_step_ids"]) for n in networks),
               "cyclic_network_count": sum(n["topology"]["cycle_rank"] > 0 for n in networks)}
    result = {"schema": SCHEMA, "status": "EXTRACTED_WITH_ISSUES" if issues else "EXTRACTED",
              "engineering_status": "UNKNOWN" if networks else "NOT_RUN", "source_sha256": source,
              "source_discipline": source_discipline, "audit_input_sha256": input_hash,
              "summary": summary, "networks": networks, "products": list(product_output.values()),
              "ports": list(port_output.values()), "explicit_connections": list(edge_output.values()),
              "systems": system_output, "accounting": accounting, "issues": issues,
              "missing_audit_collections": [name for name in fields if name not in frozen],
              "scope": "Imported explicit topology only. No inferred proximity edges, cross-source joining, engineering source/sink duties, demands, hydraulic/electrical/code/structural acceptance or installed completeness claim."}
    pulse("service_networks_complete")
    if _hash(audit) != input_hash:
        raise ValueError("Imported source audit changed during service-network extraction")
    result["graph_sha256"] = _hash(result)
    return result
