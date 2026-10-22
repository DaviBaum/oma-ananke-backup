"""Fresh-process export fidelity check; no optimizer flags or meshes are trusted."""
from pathlib import Path
import json
import sys

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.placement
import ifcopenshell.util.unit
import numpy as np
from oma.ifc.audit import atomic_json, sha256_file
from oma.ifc.ports import ownership_ledger, port_facts, connected_pair_errors


def recheck(manifest_path):
    path = Path(manifest_path)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if sha256_file(manifest["source_path"]) != manifest["source_sha256"]:
        raise ValueError("Source bytes changed")
    if sha256_file(manifest["export_path"]) != manifest["export_sha256"]:
        raise ValueError("Export hash changed")
    source = ifcopenshell.open(manifest["source_path"])
    exported = ifcopenshell.open(manifest["export_path"])
    lost, changed = [], []
    for entity in source:
        try:
            after = exported.by_id(entity.id())
        except RuntimeError:
            lost.append(entity.id())
            continue
        if str(entity) != str(after):
            changed.append(entity.id())
    if lost or changed:
        raise ValueError(f"Unedited originals changed/lost: {lost[:10]} / {changed[:10]}")
    scale = ifcopenshell.util.unit.calculate_unit_scale(exported)
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    settings.set("mesher-linear-deflection", 0.0001)
    settings.set("mesher-angular-deflection", 0.05)
    findings = []
    all_ports = set()
    ledger = ownership_ledger(exported)
    for item in manifest["added_parts"]:
        entity = exported.by_guid(item["ifc_guid"])
        shape = ifcopenshell.geom.create_shape(settings, entity)
        vertices = np.asarray(shape.geometry.verts).reshape(-1, 3)
        if len(vertices) < 6 or not np.isfinite(vertices).all():
            raise ValueError("New physical part failed geometry reimport")
        expected = item["expected"]
        endpoints = [expected["start"], expected["end"]]
        for endpoint_index, (guid, expected_point) in enumerate(zip(item["ports"], endpoints)):
            port = exported.by_guid(guid)
            all_ports.add(port.id())
            matrix = ifcopenshell.util.placement.get_local_placement(port.ObjectPlacement)
            actual = matrix[:3, 3] * scale
            if not np.allclose(actual, expected_point, rtol=0, atol=1e-7):
                raise ValueError("Port placement lost during round trip")
            tangent = (np.cross(expected["normal"], np.asarray(expected_point)-expected["center"]) if expected["kind"] == "elbow"
                       else np.asarray(expected["end"])-expected["start"])
            tangent /= np.linalg.norm(tangent)
            expected_outward = tangent if endpoint_index else -tangent
            facts = port_facts(port, ledger[port.id()], scale)
            if facts["errors"] or facts["owner_guids"] != [entity.GlobalId]:
                raise ValueError(f"Port ownership/relative placement invalid: {facts['errors']}")
            if port.FlowDirection != ("SINK" if endpoint_index == 0 else "SOURCE"):
                raise ValueError("Port flow role differs from intended route endpoint")
            if not np.allclose(facts["physical_outward_normal"], expected_outward, rtol=0, atol=1e-7):
                raise ValueError("Port orientation differs from physical route tangent")
        outer_radius = manifest["route_spec"]["diameter_m"]/2 + manifest["route_spec"].get("insulation_m", 0)
        # End-face vertices must reach both intended ends, catching truncated sweeps.
        for endpoint in endpoints:
            nearest = np.linalg.norm(vertices - np.asarray(endpoint), axis=1).min()
            if abs(nearest - outer_radius) > 0.002:
                raise ValueError(f"Physical sweep fails to reach intended endpoint: {nearest} vs {outer_radius}")
        findings.append({"ifc_guid": item["ifc_guid"], "vertices": len(vertices),
                         "bounds": {"min": vertices.min(axis=0).tolist(), "max": vertices.max(axis=0).tolist()},
                         "status": "PASS"})
    relationships = [r for r in exported.by_type("IfcRelConnectsPorts")
                     if r.RelatingPort.id() in all_ports and r.RelatedPort.id() in all_ports]
    if len(relationships) != manifest["explicit_internal_connections"]:
        raise ValueError("Export lost or duplicated intended route connectivity")
    all_connections = [r for r in exported.by_type("IfcRelConnectsPorts")
                       if r.RelatingPort.id() in all_ports or r.RelatedPort.id() in all_ports]
    degree = {p: 0 for p in all_ports}
    for relationship in all_connections:
        problems = connected_pair_errors(relationship.RelatingPort, relationship.RelatedPort, ledger, scale)
        if problems:
            raise ValueError(f"Exported port connection invalid: {problems}")
        for port in (relationship.RelatingPort, relationship.RelatedPort):
            if port.id() in degree:
                degree[port.id()] += 1
    if any(count > 1 for count in degree.values()):
        raise ValueError("Exported route port has multiple connections")
    system = exported.by_guid(manifest["source_system_guid"])
    grouped = {o.GlobalId for r in system.IsGroupedBy for o in r.RelatedObjects}
    if grouped != {p["ifc_guid"] for p in manifest["added_parts"]}:
        raise ValueError("System membership differs from materialized route")
    opening_report = None
    if manifest.get("authorized_opening"):
        from oma.routing.opening import opening_check_arguments
        from oma.ifc.openings import check_opening_semantics
        arguments = opening_check_arguments(manifest["export_path"], manifest["source_path"],
            manifest["authorized_opening"]["request"], manifest["authorized_opening"], manifest["export_sha256"],
            {p["ifc_guid"] for p in manifest["added_parts"]},
            terminal_guids=tuple(manifest["route_spec"][k] for k in ("source_port_guid", "sink_port_guid") if manifest["route_spec"].get(k)))
        opening_report = check_opening_semantics(manifest["export_path"], manifest["source_path"], **arguments)
        if opening_report["status"] != "PASS":
            raise ValueError(f"Exported authorized opening failed: {opening_report}")
    manifest["reimport"] = {"status": "PASS", "scope": "Original STEP preservation, new physical geometry, port locations, connectivity and system membership",
                            "fresh_process": True, "original_records_checked": len(list(source)),
                            "parts": findings, "connections_checked": len(relationships),
                            "coordination_status": "NOT_RUN", "common_mode_risk": "IFC parser/tessellator shared with importer; not an engineering coordination certificate"}
    if opening_report:
        manifest["reimport"]["authorized_opening"] = opening_report
    atomic_json(path, manifest)
    print(json.dumps({"status": "PASS", "parts": len(findings), "connections": len(relationships)}))


if __name__ == "__main__":
    recheck(sys.argv[1])
