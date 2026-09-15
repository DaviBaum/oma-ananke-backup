"""Whole-project installed-service accounting and explicit catalogue design jobs.

Every source and installed service component remains in the denominator. Local
engineering catalogue screens do not grant network or IFC acceptance authority.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import math
import os
import subprocess
import time

from .build_identity import checker_version
from .store import IntegrityError, digest, utcnow, TERMINAL_RUN_STATUSES

SCHEMA = "oma.building-service-design/1"
DISCIPLINES = {"HVAC", "PLUMBING", "ELECTRICAL", "FIRE", "ARCHITECTURE", "STRUCTURE", "MIXED", "UNKNOWN"}


def _source_bytes(store, sources, checkpoint):
    records = []
    identities = set()
    for source in sources:
        checkpoint("service_source_bytes")
        sid = source["sha256"]
        if source["id"] != sid or sid in identities:
            raise IntegrityError("Source identities must be unique content hashes")
        identities.add(sid)
        path = store.resolve_path(source["immutable_path"]).resolve()
        hasher = hashlib.sha256()
        with path.open("rb") as stream:
            before = os.fstat(stream.fileno())
            while chunk := stream.read(8 * 1024 * 1024):
                checkpoint("service_source_bytes_chunk")
                hasher.update(chunk)
            after = os.fstat(stream.fileno())
        identity = lambda stat: (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)
        if identity(before) != identity(after) or identity(after) != identity(path.stat()) or hasher.hexdigest() != sid:
            raise IntegrityError("Original IFC changed or differs from the imported source")
        records.append({"source_id": sid, "path": str(path), "bytes": after.st_size, "sha256": hasher.hexdigest()})
    return records


def _request(query, sources):
    if not isinstance(query, dict) or query.get("schema") != SCHEMA:
        raise ValueError(f"Mission requires schema {SCHEMA}")
    if set(query) - {"schema", "source_disciplines", "contracts"}:
        raise ValueError("Unknown building service mission fields")
    labels, contracts = query.get("source_disciplines", {}), query.get("contracts", [])
    if not isinstance(labels, dict) or set(labels) - {s["id"] for s in sources}:
        raise ValueError("Source discipline labels must reference imported sources")
    if any(value not in DISCIPLINES for value in labels.values()):
        raise ValueError("Unsupported explicit source discipline")
    if not isinstance(contracts, list) or len(contracts) > 100000:
        raise ValueError("Contracts must be a bounded list")
    keyed = {}
    for contract in contracts:
        required = {"network_id", "network_root", "source_sha256", "service", "options", "requirements", "catalogue_complete"}
        if not isinstance(contract, dict) or set(contract) != required:
            raise ValueError("Each design contract requires an exact installed network/root/source binding and explicit catalogue")
        if not isinstance(contract["network_id"], str) or contract["network_id"] in keyed:
            raise ValueError("Duplicate/invalid network contract")
        if not isinstance(contract["network_root"], str) or len(contract["network_root"]) != 64:
            raise ValueError("A network content root from the previous inventory is required")
        if type(contract["catalogue_complete"]) is not bool:
            raise ValueError("Catalogue completeness must be an explicit boolean")
        keyed[contract["network_id"]] = contract
    return labels, keyed


def design_services_run(store, run, control):
    """Supervised full-source run, persist results without changing IFC/revision."""
    from .ifc.service_networks import extract_service_networks, validate_service_audit_source
    from .optimization.service_design import screen_service_catalog

    original = store.run(run["id"])
    fixed = {k: original[k] for k in ("id", "project_id", "base_root", "base_revision", "operation")}
    request_root = digest(original["request"])
    if any(run.get(k) != v for k, v in fixed.items()) or digest(run["request"]) != request_root:
        raise IntegrityError("Building design run differs from its immutable stored request")
    seconds = float(original["request"].get("budget_seconds", 300))
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("Positive finite service-design budget required")
    deadline = time.monotonic() + seconds

    def checkpoint(stage):
        if time.monotonic() >= deadline:
            raise subprocess.TimeoutExpired("building_service_design", seconds)
        control.checkpoint(stage)
        if time.monotonic() >= deadline:
            raise subprocess.TimeoutExpired("building_service_design", seconds)

    def unchanged_request():
        current = store.run(run["id"])
        if any(current[k] != value for k, value in fixed.items()) or digest(current["request"]) != request_root:
            raise IntegrityError("Building service request changed during execution")

    checkpoint("service_design_start")
    state = store.get(original["base_root"])
    sources = state.get("sources", [])
    if not sources:
        raise ValueError("Import the project before running whole-building service design")
    if original["request"].get("scope"):
        raise ValueError("Whole-building service design cannot silently restrict the imported source denominator")
    labels, contracts = _request(original["request"].get("mission"), sources)
    before = _source_bytes(store, sources, checkpoint)
    packet = {"schema": SCHEMA, "project_id": original["project_id"], "base_root": original["base_root"],
              "base_revision": original["base_revision"], "request_root": request_root, "checker_version": checker_version(),
              "sources": [], "networks": [], "source_files": before,
              "federation": state.get("derived_artifacts", {}).get("local_coordinate_evidence", {}).get("status", "UNKNOWN"),
              "project_state_changed": False, "native_checks_run": False, "construction_approval": False,
              "network_engineering_verdict": "NOT_RUN", "whole_building_optimized": False,
              "scope": "All imported service network inventory plus explicitly requested local catalogue screens. No full-network hydraulic/electrical solution, installation or code approval follows."}
    known_networks = set()
    statuses = Counter()
    design_statuses = Counter()
    for index, source in enumerate(sources):
        checkpoint("service_source_inventory")
        store.append_event(original["project_id"], run_id=run["id"], state_root=original["base_root"],
            stage="service_networks", status="RUNNING", message=f"Accounting for installed services in {source['name']}",
            payload={"source_id": source["id"], "source_index": index + 1, "source_count": len(sources)})
        audit = store.get(source["audit_root"])
        if audit["source_sha256"] != source["sha256"]:
            raise IntegrityError("Imported audit belongs to a different source")
        reconciliation = validate_service_audit_source(audit, store.resolve_path(source["immutable_path"]), checkpoint=checkpoint)
        graph = extract_service_networks(audit, source_sha256=source["sha256"],
            source_discipline=labels.get(source["id"], "UNKNOWN"), checkpoint=checkpoint)
        obligations = ("declared_audit_denominators_consistent", "all_products_accounted",
                       "all_service_products_in_exactly_one_network", "all_audited_ports_in_exactly_one_network",
                       "all_explicit_connections_in_exactly_one_network")
        if graph["missing_audit_collections"] or not all(graph["accounting"].get(key) is True for key in obligations):
            raise IntegrityError("Installed source inventory is incomplete or its denominators disagree")
        graph_root = store.put(graph)
        packet["sources"].append({"source_id": source["id"], "name": source["name"],
            "discipline_label": labels.get(source["id"], "UNKNOWN"), "audit_root": source["audit_root"],
            "network_inventory_root": graph_root, "source_reconciliation_root": store.put(reconciliation),
            "summary": graph["summary"], "accounting": graph["accounting"]})
        for network in graph["networks"]:
            checkpoint("service_network_design")
            nid = network["id"]
            network_root = digest({"network": network, "source_inventory_root": graph_root,
                                   "source_audit_root": source["audit_root"]})
            if nid in known_networks:
                raise IntegrityError("Installed network ID collision")
            known_networks.add(nid)
            row = {"network_id": nid, "network_root": network_root, "source_sha256": source["sha256"],
                   "source_inventory_root": graph_root, "service_families": network["service_families"],
                   "product_count": len(network["product_step_ids"]), "port_count": len(network["port_step_ids"]),
                   "connection_count": len(network["connection_step_ids"]),
                   "topology": network.get("topology"), "issues": network["issues"],
                   "network_service_verified": False, "native_optimization_ready": False}
            contract = contracts.get(nid)
            if contract is None:
                row.update(status="MISSING_DESIGN_CONTRACT", missing_design_inputs=network.get("missing_design_inputs", []))
            else:
                if contract["source_sha256"] != source["sha256"] or contract["network_root"] != network_root:
                    raise IntegrityError("Design contract is stale or belongs to another installed network")
                context = digest({"base_root": original["base_root"], "network_root": network_root, "contract": contract})
                result = screen_service_catalog(contract["service"], contract["options"], contract["requirements"],
                    catalogue_complete=contract["catalogue_complete"], context_root=context)
                row.update(status="CATALOGUE_SCREENED", design_result_root=store.put(result),
                           design_status=result.get("status"), contract_root=digest(contract),
                           constraint="Local supplied duty/catalogue only; network coupling and native geometry remain unchecked")
                design_statuses[result.get("status", "UNKNOWN")] += 1
            statuses[row["status"]] += 1
            packet["networks"].append(row)
    if set(contracts) - known_networks:
        raise ValueError("Design contract names a network absent from the complete imported inventory")
    packet["summary"] = {"source_count": len(sources), "network_count": len(known_networks),
                         "network_status_counts": dict(sorted(statuses.items())), "contract_count": len(contracts),
                         "catalogue_status_counts": dict(sorted(design_statuses.items()))}
    missing_inputs = bool(statuses["MISSING_DESIGN_CONTRACT"] or design_statuses["UNKNOWN"])
    packet["status"] = "DESIGN_INPUTS_REQUIRED" if missing_inputs else "LOCAL_CATALOGUE_SCREENS_COMPLETE_NETWORK_VERIFICATION_REQUIRED"
    if not known_networks:
        packet["status"] = "NO_INSTALLED_SERVICE_NETWORKS_IDENTIFIED"
    checkpoint("service_design_publish")
    checkpoint("service_design_complete")
    # No further user/control callback may mutate a source after the byte fence.
    # Deadline checks remain active during hashing; cancel/pause is checked under
    # the same SQLite write transaction as final event/status publication below.
    def final_deadline(stage):
        if time.monotonic() >= deadline:
            raise subprocess.TimeoutExpired("building_service_design", seconds)
    after = _source_bytes(store, sources, final_deadline)
    if before != after:
        raise IntegrityError("Source identities changed before whole-building report publication")
    unchanged_request()
    root = store.put(packet)
    terminal = "MISSING_INPUTS" if missing_inputs else "COMPLETED"
    import json
    with store.transaction() as db:
        current = db.execute("SELECT * FROM runs WHERE id=?", (run["id"],)).fetchone()
        if not current or any(current[k] != value for k, value in fixed.items()) or digest(json.loads(current["request"])) != request_root:
            raise IntegrityError("Building service request changed at publication")
        if current["status"] in TERMINAL_RUN_STATUSES or current["desired_action"] == "cancel":
            from .worker import Cancelled
            raise Cancelled()
        if current["desired_action"] not in {"run", "step"}:
            raise IntegrityError("Control changed after final source fence; retry from a fresh job")
        final_deadline("service_design_publication")
        detail = "Whole-project service accounting complete; physical network optimization and construction verification remain separate"
        db.execute("UPDATE runs SET status=?,detail=?,updated_at=? WHERE id=?", (terminal, detail, utcnow(), run["id"]))
        store._event(db, original["project_id"], run_id=run["id"], state_root=original["base_root"],
            status=terminal, stage="service_design_complete", message=detail, artifacts=[root],
            payload={"service_design_artifact_root": root, **packet["summary"],
                     "whole_building_optimized": False, "project_state_changed": False})
    return packet
