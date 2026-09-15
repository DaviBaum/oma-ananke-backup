"""Read-only IFC cost/quantity inventory; never interprets omissions as zero cost.

Usage: python scripts/ifc_cost_readiness.py --manifest FILE --output NEW_DIRECTORY
The manifest contains original_sources: [{path, sha256, ...}]. Quantities are
reported as authored, by set/name/unit, without CAD inference or deduplication
across disciplines. IFC cost entities are evidence to inspect, not accepted rates.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gc
import hashlib
import json
from pathlib import Path
import shutil
import time

import ifcopenshell


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def encode(value):
    if isinstance(value, ifcopenshell.entity_instance):
        return {"step_id": value.id(), "type": value.is_a(), "step": str(value)}
    if isinstance(value, (tuple, list)):
        return [encode(v) for v in value]
    if isinstance(value, dict):
        return {k: encode(v) for k, v in value.items()}
    return value


def identity(obj):
    return {"step_id": obj.id(), "type": obj.is_a(), "guid": getattr(obj, "GlobalId", None), "name": getattr(obj, "Name", None)}


def audit(path):
    model = ifcopenshell.open(str(path))
    counts = Counter(obj.is_a() for obj in model)
    cost_classes = sorted(k for k in counts if k.startswith("IfcCost") or k in ("IfcMonetaryUnit", "IfcAppliedValue"))
    quantities = {q.id(): q for q in model.by_type("IfcElementQuantity")}
    quantity_objects = defaultdict(set)
    for relation in model.by_type("IfcRelDefinesByProperties"):
        definition = relation.RelatingPropertyDefinition
        definitions = definition if isinstance(definition, tuple) else (definition,)
        for item in definitions:
            if item and item.is_a("IfcElementQuantity"):
                quantity_objects[item.id()].update(o.id() for o in relation.RelatedObjects)
    # Retain inherited quantities as a separate population. They are not a
    # per-occurrence bill of quantities and are never multiplied by type count.
    type_quantities = defaultdict(set)
    types = model.by_type("IfcTypeObject")
    for obj in types:
        for item in obj.HasPropertySets or ():
            if item.is_a("IfcElementQuantity"):
                type_quantities[item.id()].add(obj.id())
    qrecords = [{**identity(q), "method": q.MethodOfMeasurement,
                 "direct_object_step_ids": sorted(quantity_objects[q.id()]),
                 "type_object_step_ids": sorted(type_quantities[q.id()]),
                 "quantities": [encode(v.get_info()) for v in q.Quantities]}
                for q in quantities.values()]
    elements = model.by_type("IfcElement")
    element_ids = {o.id() for o in elements}
    assigned_elements = set().union(*(v & element_ids for v in quantity_objects.values())) if quantity_objects else set()
    type_assignments = defaultdict(set)
    for relation in model.by_type("IfcRelDefinesByType"):
        type_assignments[relation.RelatingType.id()].update(o.id() for o in relation.RelatedObjects if o.id() in element_ids)
    type_repeats = sorted(({**identity(model.by_id(k)), "element_count": len(v), "element_step_ids": sorted(v)}
                           for k, v in type_assignments.items()), key=lambda x: (-x["element_count"], x["step_id"]))
    property_names = Counter()
    rate_clues = []
    for prop in model.by_type("IfcProperty"):
        name = prop.Name or ""
        property_names[name] += 1
        if any(token in name.casefold() for token in ("cost", "price", "rate", "currency", "budget")):
            rate_clues.append(encode(prop.get_info()))
    materials = model.by_type("IfcMaterial")
    material_assignments = model.by_type("IfcRelAssociatesMaterial")
    material_objects = {obj.id() for rel in material_assignments for obj in rel.RelatedObjects}
    # An association may point to a type, layer set or usage: count presence,
    # not structural/thermal/fire adequacy or installed material quantities.
    spaces = model.by_type("IfcSpace")
    spaces_with_qto = {s.id() for s in spaces} & set().union(set(), *quantity_objects.values())
    locations = []
    for obj in model.by_type("IfcSite") + model.by_type("IfcBuilding"):
        values = {k: v for k, v in obj.get_info().items() if k in (
            "GlobalId", "Name", "LongName", "Description", "RefLatitude", "RefLongitude",
            "RefElevation", "SiteAddress", "BuildingAddress")}
        locations.append(encode(values))
    result = {
        "source": path.name, "schema": model.schema, "entity_count": sum(counts.values()),
        "entity_counts": dict(sorted(counts.items())),
        "cost_entities": {k: [encode(obj.get_info()) for obj in model.by_type(k, include_subtypes=False)] for k in cost_classes},
        "units": [encode(obj.get_info()) for obj in model.by_type("IfcUnitAssignment")],
        "element_count": len(elements), "element_counts": dict(Counter(o.is_a() for o in elements)),
        "direct_quantity_element_count": len(assigned_elements),
        "direct_quantity_missing_element_count": len(element_ids - assigned_elements),
        "quantity_set_count": len(quantities), "quantity_sets": qrecords,
        "space_count": len(spaces), "spaces_with_direct_quantity_sets": len(spaces_with_qto),
        "type_count": len(types), "element_type_groups": type_repeats,
        "untyped_element_count": len(element_ids - set().union(set(), *type_assignments.values())),
        "materials": [encode(obj.get_info()) for obj in materials],
        "material_properties": [encode(obj.get_info()) for obj in model.by_type("IfcMaterialProperties")],
        "material_association_count": len(material_assignments),
        "direct_material_association_element_count": len(material_objects & element_ids),
        "property_name_counts": dict(sorted(property_names.items())),
        "price_property_clues_unvalidated": rate_clues,
        "declared_locations_unvalidated": locations,
        "whole_building_cost": None,
        "construction_savings": None,
        "structural_safety": "NOT_ASSESSED",
        "scope": "Authoring-data inventory only. Quantity presence is not completeness, cost validity, geometry checking or design approval.",
    }
    del model
    gc.collect()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path.cwd().resolve()
    manifest = args.manifest.resolve()
    records = json.loads(manifest.read_text(encoding="utf-8-sig"))["original_sources"]
    sources = [(root / item["path"]).resolve() for item in records]
    if len(sources) != len(set(sources)):
        raise ValueError("Duplicate source path")
    before = {str(path): sha(path) for path in sources}
    for path, item in zip(sources, records):
        if before[str(path)] != item["sha256"]:
            raise ValueError(f"Original source hash mismatch: {path}")
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(__file__, out / "executed.py")
    shutil.copyfile(manifest, out / "input-manifest.json")
    start = time.monotonic()
    summary = []
    for path in sources:
        result = audit(path)
        result["source_path"] = str(path)
        result["source_sha256"] = before[str(path)]
        result_path = out / (path.stem + "-inventory.json")
        result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
        row = {k: result[k] for k in ("source", "source_sha256", "entity_count", "element_count", "quantity_set_count",
                                   "direct_quantity_element_count", "direct_quantity_missing_element_count", "space_count",
                                   "spaces_with_direct_quantity_sets", "type_count", "untyped_element_count")}
        row.update(cost_entity_counts={k: len(v) for k, v in result["cost_entities"].items()},
                   material_count=len(result["materials"]), price_property_clue_count=len(result["price_property_clues_unvalidated"]),
                   inventory_file=result_path.name, inventory_sha256=sha(result_path))
        summary.append(row)
        print(json.dumps(row), flush=True)
    after = {str(path): sha(path) for path in sources}
    if before != after:
        raise RuntimeError("Original source changed during read-only audit")
    output = {"status": "READ_ONLY_COST_INPUT_INVENTORY_COMPLETE", "elapsed_seconds": time.monotonic() - start,
              "manifest_sha256": sha(manifest), "script_sha256": sha(out / "executed.py"),
              "original_hashes_unchanged": True, "sources": summary,
              "whole_building_cost": None, "construction_savings": None,
              "limitations": ["No market rates authenticated", "No quantities inferred from display meshes",
                              "No cross-discipline deduplication", "No structural or construction approval"]}
    (out / "result.json").write_text(json.dumps(output, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({k: output[k] for k in ("status", "elapsed_seconds", "original_hashes_unchanged")}), flush=True)


if __name__ == "__main__":
    main()
