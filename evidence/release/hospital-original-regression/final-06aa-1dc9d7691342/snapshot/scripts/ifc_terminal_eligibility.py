"""Audit original declared free ports without inferring new connectivity."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import ifcopenshell
import ifcopenshell.util.unit
from oma.ifc.audit import atomic_json, sha256_file
from oma.ifc.network_semantics import read_component_geometry
from oma.ifc.ports import ownership_ledger, port_facts, circular_owner_radius


def audit(projects, output):
    started = time.perf_counter()
    acquisition = json.loads((ROOT / "evidence/ifc/acquisition.json").read_text())
    entries = [e for e in acquisition["files"] if e["is_ifc"] and e["project"] in projects]
    report = {"schema": "oma-original-terminal-eligibility/2", "dataset_revision": acquisition["revision"],
        "selected_projects": projects, "selected_source_count": len(entries), "sources": [],
        "scope": "Explicit original unoccupied unidirectional ports and currently supported round cap forms",
        "geometry_attachment": "NOT_RUN", "connection_intent": "NOT_INFERRED", "connection_authorization": "NONE"}
    for entry in entries:
        path = ROOT / entry["local_path"]
        if sha256_file(path) != entry["sha256"]:
            raise ValueError("Original source hash changed: " + str(path))
        model = ifcopenshell.open(str(path))
        ledger = ownership_ledger(model)
        scale = ifcopenshell.util.unit.calculate_unit_scale(model)
        occupied = {p.id() for rel in model.by_type("IfcRelConnectsPorts") for p in (rel.RelatingPort, rel.RelatedPort)}
        counts, reasons, free = Counter(), Counter(), []
        for record in ledger.values():
            port = record["port"]
            counts[port.FlowDirection] += 1
            if port.FlowDirection not in ("SOURCE", "SINK"):
                reasons["FLOW_NOT_UNIDIRECTIONAL"] += 1
                continue
            if port.id() in occupied:
                reasons["DECLARED_OCCUPIED"] += 1
                continue
            facts = port_facts(port, record, scale)
            row = {"port": facts, "status": "UNRESOLVED", "native_attachment": "NOT_RUN"}
            free.append(row)
            if facts["errors"]:
                row["reason"] = "PORT_DECLARATION_ERRORS"
                reasons.update(facts["errors"])
                continue
            owner = next(iter(record["owners"].values()))
            row.update(owner_guid=owner.GlobalId, owner_step_id=owner.id(), owner_type=owner.is_a())
            items = [i for r in owner.Representation.Representations for i in r.Items] if owner.Representation else []
            row["representation_items"] = [{"step_id": i.id(), "type": i.is_a(),
                "profile_type": i.SweptArea.is_a() if i.is_a("IfcSweptAreaSolid") else None,
                "mapped_item_types": [x.is_a() for x in i.MappingSource.MappedRepresentation.Items] if i.is_a("IfcMappedItem") else None} for i in items]
            radius = circular_owner_radius(owner, scale)
            if radius is None:
                row["reason"] = "UNSUPPORTED_OR_UNKNOWN_ROUND_OWNER_SECTION"
                reasons[row["reason"]] += 1
                continue
            try:
                row["parsed_geometry"] = read_component_geometry(model, owner)
                row.update(status="CANDIDATE_REQUIRING_NATIVE_ATTACHMENT_CHECK", radius_m=radius)
            except Exception as exc:
                row.update(reason="UNSUPPORTED_NATIVE_CAP_FORM", error=f"{type(exc).__name__}: {exc}")
                reasons[row["reason"]] += 1
        source = {"path": entry["path"], "source_sha256": entry["sha256"], "ifc_schema": model.schema,
            "ports": len(ledger), "flow_counts": dict(counts), "selection_dispositions": dict(reasons),
            "unoccupied_unidirectional_ports": free,
            "currently_supported_cap_candidates": sum(r["status"] == "CANDIDATE_REQUIRING_NATIVE_ATTACHMENT_CHECK" for r in free)}
        report["sources"].append(source)
        report["seconds"] = time.perf_counter() - started
        atomic_json(output, report)
        print(json.dumps({"source": entry["path"], "ports": len(ledger), "unoccupied_unidirectional": len(free), "cap_candidates": source["currently_supported_cap_candidates"]}), flush=True)
    report["status"] = "AUDIT_COMPLETE"
    report["total_ports"] = sum(s["ports"] for s in report["sources"])
    report["unoccupied_unidirectional_ports"] = sum(len(s["unoccupied_unidirectional_ports"]) for s in report["sources"])
    report["currently_supported_cap_candidates"] = sum(s["currently_supported_cap_candidates"] for s in report["sources"])
    report["seconds"] = time.perf_counter() - started
    atomic_json(output, report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--projects", nargs="+", default=["digital_hub", "dental_clinic", "wbdg_office"])
    parser.add_argument("--output", type=Path, default=ROOT / "evidence/ifc/original-terminal-eligibility-v2.json")
    args = parser.parse_args()
    audit(args.projects, args.output)
