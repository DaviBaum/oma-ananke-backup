"""Bind one explicit host edit to original source facts and a physical route.

Imported entity records remain source facts. The versioned edit below replaces
their selected host's effective support; original STEP equality is insufficient.
"""
from pathlib import Path

from oma.ifc.audit import atomic_json, sha256_file
from oma.ifc.export import export_route
from oma.store import digest


def opening_context(state, scenario, source):
    opening = scenario.authorized_opening
    if opening is None:
        return None
    if state.get("routes") or state.get("physical_networks") or state.get("mission") or state.get("derived_artifacts", {}).get("opening_edit"):
        raise ValueError("First opening contract requires an imported baseline without prior engineering edits")
    if opening.source_sha256 != source["sha256"]:
        raise ValueError("Opening host and route must belong to the same selected immutable source")
    if source.get("transform_m") is None:
        raise ValueError("Opening requires a known source-local or independently verified federation frame")
    identity = f"{source['id']}:{opening.host_step_id}"
    matches = [e for e in state.get("entities", []) if e["id"] == identity]
    if len(matches) != 1:
        raise ValueError("Opening host is absent or ambiguous in the imported entity inventory")
    host = matches[0]
    provenance = host["provenance"]
    if (provenance["source_id"] != source["id"] or provenance["content_hash"] != opening.source_sha256
            or provenance["step_id"] != opening.host_step_id or provenance["guid"] != opening.host_guid):
        raise ValueError("Opening host source, GUID and STEP identities disagree")
    return {"request": opening.model_dump(mode="json"), "host_entity_id": identity, "source_id": source["id"]}


def edit_record(context, manifest, base_root):
    return {**context, "base_root": base_root, "manifest_root": digest(manifest),
        "invalidation": {"effective_host_geometry": "REQUIRES_FRESH_NATIVE_SUBTRACTION_CHECK",
            "route_clearance": "REQUIRES_ALL_ORIGINAL_OBSTACLES_WITH_EXACT_HOST_REPLACEMENT",
            "structural_adequacy": "NOT_CHECKED", "fire_adequacy": "NOT_CHECKED", "access_adequacy": "NOT_CHECKED",
            "prior_geometry_checks_applicable": False},
        "scope": "EXPLICIT_SCENARIO_GEOMETRY_ONLY"}


def materialize_route(source_path, destination, route_spec, context):
    if context is None:
        return export_route(source_path, destination, route_spec, fresh_recheck=True)
    from oma.ifc.openings import export_opening
    destination = Path(destination)
    parent = destination.with_name("opening.ifc")
    manifest = export_opening(source_path, parent, context["request"], fresh_recheck=False)
    result = export_route(parent, destination, route_spec, fresh_recheck=True)
    result.update(source_path=str(Path(source_path).resolve()), source_sha256=sha256_file(source_path),
                  append_input_sha256=result["source_sha256"], authorized_opening=manifest,
                  original_step_records=result["original_step_records"] - len(manifest["added_step_ids"]),
                  reimport={"status": "NOT_RUN", "reason": "Combined opening and route requires its own original-source recheck"})
    atomic_json(destination.with_suffix(".manifest.json"), result)
    return result


def opening_check_arguments(export_path, source_path, request, manifest, expected_hash, route_guids, *, terminal_guids=()):
    """Derive the exact additional STEP set, permitting only route record types.

The ordinary route checker separately accounts for all parts, directrices,
ports, connectivity and obligations. No further void/host relation is admitted.
"""
    import ifcopenshell
    if sha256_file(export_path) != expected_hash:
        raise ValueError("Combined physical artifact hash changed")
    before = ifcopenshell.open(str(source_path))
    after = ifcopenshell.open(str(export_path))
    original = {e.id() for e in before}
    opening_ids = set(manifest["added_step_ids"])
    extra = [e for e in after if e.id() not in original | opening_ids]
    allowed_types = {"IfcSystem", "IfcFlowSegment", "IfcFlowFitting", "IfcPipeSegment", "IfcPipeFitting", "IfcDuctSegment", "IfcDuctFitting",
        "IfcDistributionPort", "IfcRelConnectsPortToElement", "IfcRelNests", "IfcRelConnectsPorts",
        "IfcRelAssignsToGroup", "IfcRelContainedInSpatialStructure", "IfcRelDefinesByProperties", "IfcPropertySet",
        "IfcPropertySingleValue", "IfcLocalPlacement", "IfcAxis2Placement3D", "IfcAxis2Placement2D", "IfcAxis1Placement",
        "IfcCartesianPoint", "IfcDirection", "IfcCircleProfileDef", "IfcExtrudedAreaSolid", "IfcRevolvedAreaSolid",
        "IfcShapeRepresentation", "IfcProductDefinitionShape"}
    unsupported = [e.is_a() for e in extra if e.is_a() not in allowed_types]
    if unsupported:
        raise ValueError(f"Unaccounted added physical/edit record types: {sorted(set(unsupported))}")
    actual_guids = [e.GlobalId for e in extra if e.is_a("IfcElement")]
    if len(actual_guids) != len(set(actual_guids)) or set(actual_guids) != set(route_guids):
        raise ValueError("Combined opening file has unaccounted or duplicate route elements")
    added_ids = {e.id() for e in extra}
    part_ids = {e.id() for e in extra if e.is_a("IfcElement")}
    port_ids = {e.id() for e in extra if e.is_a("IfcDistributionPort")}
    terminal_ids = {e.id() for e in before.by_type("IfcDistributionPort") if e.GlobalId in set(terminal_guids)}
    def only_related(items, allowed):
        ids = [item.id() for item in items]
        return bool(ids) and len(ids) == len(set(ids)) and set(ids) <= allowed
    for entity in extra:
        valid = True
        kind = entity.is_a()
        if kind == "IfcRelDefinesByProperties":
            valid = (only_related(entity.RelatedObjects, part_ids) and entity.RelatingPropertyDefinition.id() in added_ids
                     and entity.RelatingPropertyDefinition.is_a("IfcPropertySet"))
        elif kind == "IfcRelAssignsToGroup":
            valid = (only_related(entity.RelatedObjects, part_ids) and entity.RelatingGroup.id() in added_ids
                     and entity.RelatingGroup.is_a("IfcSystem"))
        elif kind == "IfcRelNests":
            valid = entity.RelatingObject.id() in part_ids and only_related(entity.RelatedObjects, port_ids)
        elif kind == "IfcRelConnectsPortToElement":
            valid = entity.RelatingPort.id() in port_ids and entity.RelatedElement.id() in part_ids
        elif kind == "IfcRelConnectsPorts":
            pair = {entity.RelatingPort.id(), entity.RelatedPort.id()}
            valid = (len(pair) == 2 and pair <= port_ids | terminal_ids and bool(pair & port_ids)
                     and entity.RealizingElement is not None and entity.RealizingElement.id() in part_ids)
        elif kind == "IfcRelContainedInSpatialStructure":
            valid = (only_related(entity.RelatedElements, part_ids) and entity.RelatingStructure.id() in original
                     and entity.RelatingStructure.is_a("IfcSpatialStructureElement"))
        if not valid:
            raise ValueError(f"Unapproved inverse semantic effect from added route relationship: {kind}")
    return {"request": request, "manifest": manifest, "allowed_new_step_ids": {e.id() for e in extra},
            "allowed_new_element_guids": set(route_guids), "allowed_existing_terminal_guids": set(terminal_guids),
            "expected_export_sha256": expected_hash}
