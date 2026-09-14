"""Preserve explicit IFC port facts without inventing engineering inputs."""
from __future__ import annotations

from collections import Counter

import numpy as np

from .models import Port, Provenance


def refresh_ownership(store, audit: dict, source: dict) -> dict:
    """Read legacy audit ownership afresh from the hash-verified immutable IFC."""
    if all("owner_step_ids" in p and "owner_placement_status" in p and "axis_convention" in p for p in audit.get("ports", [])):
        return audit
    import ifcopenshell
    from .ifc.audit import sha256_file
    path = store.resolve_path(source["immutable_path"])
    if sha256_file(path) != source["sha256"]:
        raise ValueError("Source hash changed before explicit connectivity normalization")
    model = ifcopenshell.open(str(path))
    import ifcopenshell.util.unit
    from .ifc.ports import ownership_ledger, port_facts
    ledger = ownership_ledger(model)
    scale = ifcopenshell.util.unit.calculate_unit_scale(model)
    records = []
    for record in audit.get("ports", []):
        facts = port_facts(model.by_id(record["step_id"]), ledger[record["step_id"]], scale)
        ids = facts["owner_step_ids"]
        records.append({**record, "owner_step_ids": ids, "owner_step_id": ids[0] if len(ids) == 1 else None,
                        "owner_relationship_step_ids": facts["owner_relationship_step_ids"],
                        "axis_convention": facts["axis_convention"], "owner_placement_status": facts["owner_placement_status"],
                        "port_semantic_errors": facts["errors"], "flow_axis": facts["flow_axis"],
                        "physical_outward_normal": facts["physical_outward_normal"]})
    return {**audit, "ports": records, "ownership_normalization": {"method": "fresh_explicit_IFC_relationships_and_flow_axes/2", "source_sha256": source["sha256"]}}


def normalize_connectivity(audits: list[dict], sources: list[dict]):
    ports, connections, issues = [], [], []
    counts = Counter()
    source_map = {s["id"]: s for s in sources}
    for audit in audits:
        source_id = audit["source_sha256"]
        source = source_map[source_id]
        frame = source.get("transform_m")
        known_ids = {p["step_id"] for p in audit.get("ports", [])}
        for record in audit.get("ports", []):
            identity = f"{source_id}:{record['step_id']}"
            position, axis = None, None
            status = "MISSING"
            placement = record.get("placement_matrix_m")
            if placement is not None:
                matrix = np.asarray(placement, dtype=float)
                if matrix.shape == (4, 4) and np.isfinite(matrix).all():
                    if frame is not None:
                        matrix = np.asarray(frame, dtype=float) @ matrix
                    position = tuple(matrix[:3, 3])
                    length = float(np.linalg.norm(matrix[:3, 2]))
                    if length > 0:
                        axis = tuple(matrix[:3, 2] / length)
                    status = "KNOWN" if frame is not None else "UNRESOLVED_FEDERATION"
                else:
                    status = "INVALID"
            owners = record.get("owner_step_ids")
            if owners is None:
                owner = record.get("owner_step_id")
                ownership = "UNVERIFIED" if owner is not None else "MISSING"
            elif len(owners) == 1:
                owner, ownership = owners[0], "DECLARED"
            else:
                owner, ownership = None, "AMBIGUOUS" if owners else "MISSING"
            direction = record.get("flow_direction") or "NOTDEFINED"
            if direction not in {"SOURCE", "SINK", "SOURCEANDSINK", "NOTDEFINED"}:
                issues.append({"port_id": identity, "code": "INVALID_DECLARED_FLOW_DIRECTION", "raw": direction})
                direction = "NOTDEFINED"
            from .ifc.ports import physical_normal
            normal = physical_normal(axis, direction) if axis is not None else None
            convention = record.get("axis_convention", "HISTORICAL_UNKNOWN")
            if convention == "HISTORICAL_UNKNOWN":
                normal = None
            owner_placement = record.get("owner_placement_status", "UNVERIFIED")
            if record.get("port_semantic_errors"):
                issues.append({"port_id": identity, "code": "IMPORTED_PORT_SEMANTICS_UNRESOLVED", "details": record["port_semantic_errors"]})
            port = Port(id=identity, entity_id=f"{source_id}:{owner}" if owner is not None else None,
                        position_m=position, axis=axis, coordinate_frame="federation" if frame is not None else f"source:{source_id}",
                        physical_outward_normal=None if normal is None else tuple(normal), axis_convention=convention,
                        owner_placement_status=owner_placement,
                        position_status=status, ownership_status=ownership, direction=direction,
                        service=record.get("system_type") or "NOTDEFINED", section=None, connection_evidence="explicit_ifc",
                        provenance=Provenance(source_id=source_id, content_hash=source_id, step_id=record["step_id"],
                                              guid=record.get("ifc_guid"), description="Explicit IFC port; section and service are not inferred from proximity or file name"))
            ports.append(port)
            counts[f"position_{status}"] += 1
            counts[f"owner_{ownership}"] += 1
            if status != "KNOWN" or ownership != "DECLARED":
                issues.append({"port_id": identity, "code": "PORT_INPUT_OBLIGATION", "position": status, "ownership": ownership})
        for record in audit.get("explicit_connections", []):
            a, b = record["port_a_step_id"], record["port_b_step_id"]
            connections.append((f"{source_id}:{a}", f"{source_id}:{b}"))
            if a not in known_ids or b not in known_ids:
                issues.append({"source_id": source_id, "relationship_step_id": record["relationship_step_id"], "code": "DANGLING_EXPLICIT_CONNECTION"})
    return tuple(ports), tuple(connections), {"policy": "explicit_source_facts_only/1", "source_port_count": sum(len(a.get("ports", [])) for a in audits),
                                             "normalized_port_count": len(ports), "explicit_connection_count": len(connections),
                                             "inferred_connection_count": 0, "counts": dict(counts), "issues": issues,
                                             "service_adequacy": "NOT_CHECKED", "section_inference": "NONE"}


def normalize_project_run(store, run, control):
    """Publish a new semantic baseline; never carry an old geometric PASS."""
    from .store import digest
    state = store.get(run["base_root"])
    audits = []
    for source in state.get("sources", []):
        control.checkpoint("connectivity_source")
        audits.append(refresh_ownership(store, store.get(source["audit_root"]), source))
    if not audits:
        store.update_run(run["id"], "MISSING_INPUTS", "Source import must finish before normalization", "connectivity")
        return
    ports, connections, report = normalize_connectivity(audits, state["sources"])
    original_ports = [p for p in state.get("ports", []) if p["connection_evidence"] != "explicit_ifc"]
    state["ports"] = [p.model_dump(mode="json") for p in ports] + original_ports
    state["explicit_connections"] = list(connections)
    state.setdefault("derived_artifacts", {})["connectivity_normalization"] = report
    state["derived_artifacts"]["source_port_audits"] = {a["source_sha256"]: store.put(a) for a in audits}
    state["derived_artifacts"]["normalization_context"] = {"base_root": run["base_root"], "source_hashes": [s["sha256"] for s in state["sources"]],
                                                          "output_ports_hash": digest(state["ports"]), "output_connections_hash": digest(connections),
                                                          "old_checks_applicable": False}
    control.checkpoint("connectivity_publish")
    store.publish(run["project_id"], state, run["base_revision"], f"normalize:{run['id']}", status="BASELINE", changed_ids=[p.id for p in ports])
    store.update_run(run["id"], "COMPLETED", f"Normalized {len(ports)} explicit ports and {len(connections)} declared connections; engineering adequacy remains unchecked", "connectivity", payload={"counts": report["counts"]})
