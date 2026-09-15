"""Complete physical source inventory and conservative assembly coverage.

Declarations alone do not establish geometric support. Assembly leaves must
also appear in the consumer's loaded geometry or explicit failure ledger.
"""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path

VERSION = "oma.physical-source-inventory/1"
CODE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def physical_inventory(model):
    products = sorted((e for e in model.by_type("IfcElement") if not e.is_a("IfcFeatureElementSubtraction")), key=lambda e:e.id())
    by_id = {e.id(): e for e in products}
    children = {}
    for entity in products:
        relations = list(getattr(entity, "IsDecomposedBy", ())) + list(getattr(entity, "IsNestedBy", ()))
        children[entity.id()] = sorted({c.id() for rel in relations for c in rel.RelatedObjects})
    cycles, complete, active = set(), set(), []
    def visit(step):
        if step in active:
            cycles.update(active[active.index(step):])
            return
        if step in complete:
            return
        if len(active) >= 256:
            cycles.update(active)
            cycles.add(step)
            return
        active.append(step)
        for child in children[step]:
            if child in by_id:
                visit(child)
        active.pop()
        complete.add(step)
    for step in by_id:
        visit(step)
    memo = {}
    def coverage(step, path=()):
        if step in cycles or step in path:
            return {"status": "UNRESOLVED", "reason": "CYCLIC_OR_DEPTH_EXHAUSTED_PHYSICAL_DECOMPOSITION", "leaf_step_ids": [], "descendant_step_ids": []}
        if step in memo:
            return memo[step]
        if by_id[step].Representation is not None:
            return {"status": "REPRESENTED_LEAF_DECLARED", "leaf_step_ids": [step], "descendant_step_ids": []}
        descendants, leaves = set(), set()
        reason = None
        if not children[step]:
            reason = "MISSING_PHYSICAL_REPRESENTATION_AND_DESCENDANTS"
        for child in children[step]:
            descendants.add(child)
            if child not in by_id:
                reason = reason or "NONPHYSICAL_OR_SUBTRACTIVE_ASSEMBLY_CHILD"
                continue
            result = coverage(child, (*path, step))
            descendants.update(result["descendant_step_ids"])
            leaves.update(result["leaf_step_ids"])
            if result["status"] == "UNRESOLVED":
                reason = reason or "UNRESOLVED_PHYSICAL_DESCENDANT"
        memo[step] = {"status": "UNRESOLVED" if reason or not leaves else "COVERED_BY_DECLARED_PHYSICAL_DESCENDANTS",
            "reason": reason, "leaf_step_ids": sorted(leaves), "descendant_step_ids": sorted(descendants),
            "direct_child_step_ids": children[step]}
        return memo[step]
    assemblies = {e.id(): coverage(e.id()) for e in products if e.Representation is None}
    errors = [{"step_id": step, "ifc_guid": by_id[step].GlobalId, "reason": "CYCLIC_OR_DEPTH_EXHAUSTED_PHYSICAL_DECOMPOSITION"} for step in sorted(cycles)]
    errors.extend({"step_id": step, "ifc_guid": by_id[step].GlobalId, "reason": record["reason"]}
                  for step, record in assemblies.items() if record["status"] == "UNRESOLVED" and step not in cycles)
    return {"products": products, "all_products": model.by_type("IfcProduct"), "assemblies": assemblies, "errors": errors,
        "physical_step_ids": sorted(by_id), "decomposition_children": children}


def inventory_evidence(inventory, source_sha256):
    evidence = {"version": VERSION, "implementation_sha256": CODE_SHA256, "source_sha256": source_sha256,
        "physical_step_ids": inventory["physical_step_ids"], "physical_product_count": len(inventory["products"]),
        "assemblies": {str(k):v for k,v in inventory["assemblies"].items()}, "errors": inventory["errors"],
        "assembly_status_counts": dict(Counter(r["status"] for r in inventory["assemblies"].values())),
        "scope": "COMPLETE_SOURCE_DECLARATIONS; EACH_ASSEMBLY_LEAF_REQUIRES_GEOMETRY_OR_EXPLICIT_FAILURE_ACCOUNTING"}
    evidence["root"] = hashlib.sha256(json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return evidence


def accounted_assemblies(inventory, selected_step_ids, accounted_step_ids):
    """Return only selected assembly IDs whose complete leaves are accounted."""
    selected, accounted = set(selected_step_ids), set(accounted_step_ids)
    return {step for step, data in inventory["assemblies"].items() if step in selected
        and data["status"] == "COVERED_BY_DECLARED_PHYSICAL_DESCENDANTS"
        and set(data["leaf_step_ids"]) <= selected & accounted}


def apply_inventory_audit(audit, inventory, source_sha256):
    """Produce amended metadata while retaining original display mesh artifacts."""
    amended = deepcopy(audit)
    if audit["source_sha256"] != source_sha256:
        raise ValueError("Inventory refresh source bytes differ from the original audit")
    records = {r["step_id"]: r for r in amended["products"]}
    originals = {e.id(): e for e in inventory["all_products"]}
    if len(records) != len(amended["products"]) or set(records) != set(originals):
        raise ValueError("Legacy audit has duplicated, omitted or extra source product identities")
    for step, record in records.items():
        original = originals[step]
        expected_physical = original.is_a("IfcElement") and not original.is_a("IfcFeatureElementSubtraction")
        if (record.get("type") != original.is_a() or record.get("ifc_guid") != original.GlobalId
                or record.get("entity_id") != f"{source_sha256}:{step}"
                or record.get("source_sha256") != source_sha256
                or record.get("physical") is not expected_physical
                or record.get("has_representation") is not (original.Representation is not None)):
            raise ValueError("Legacy audit product provenance differs from actual immutable source")
    physical_ids = {r["step_id"] for r in amended["products"] if r["physical"]}
    if physical_ids != set(inventory["physical_step_ids"]):
        raise ValueError("Legacy audit physical product inventory differs from actual immutable source")
    changes = []
    for step, assembly in inventory["assemblies"].items():
        record = records[step]
        before = record["geometry_status"]
        represented_leaves = (assembly["status"] == "COVERED_BY_DECLARED_PHYSICAL_DESCENDANTS"
            and all(records.get(leaf, {}).get("geometry_status") == "represented" for leaf in assembly["leaf_step_ids"]))
        if record.get("placement_error"):
            record["geometry_status"] = "invalid"
            record["geometry_reason"] = "invalid_source_placement"
        else:
            record["geometry_status"] = "explicitly_non_geometric" if represented_leaves else "unresolved"
            record["geometry_reason"] = "assembly_physical_descendant_meshes_accounted" if represented_leaves else (assembly.get("reason") or "PHYSICAL_DESCENDANT_MESH_NOT_ACCOUNTED")
        record["assembly_coverage"] = assembly
        if before != record["geometry_status"]:
            changes.append({"step_id": step, "from": before, "to": record["geometry_status"], "reason": record["geometry_reason"]})
    amended["physical_inventory"] = inventory_evidence(inventory, source_sha256)
    amended["inventory_refresh"] = {"version": VERSION, "implementation_sha256": CODE_SHA256,
        "changed_dispositions": changes, "mesh_reconversion": False,
        "prior_inventory_root": audit.get("physical_inventory", {}).get("root")}
    amended["geometry_counts"] = dict(Counter(r["geometry_status"] for r in amended["products"]))
    amended["physical_geometry_counts"] = dict(Counter(r["geometry_status"] for r in amended["products"] if r["physical"]))
    blocking = [r["entity_id"] for r in amended["products"] if r["physical"] and r["geometry_status"] in ("invalid", "unresolved", "unsupported")]
    amended["blockers"] = [b for b in amended["blockers"] if b["code"] not in ("INCOMPLETE_PHYSICAL_GEOMETRY", "INVALID_PHYSICAL_DECOMPOSITION")]
    if blocking:
        amended["blockers"].append({"code": "INCOMPLETE_PHYSICAL_GEOMETRY", "entity_ids": blocking, "count": len(blocking)})
    if inventory["errors"]:
        amended["blockers"].append({"code": "INVALID_PHYSICAL_DECOMPOSITION", "errors": inventory["errors"], "count": len(inventory["errors"])})
    amended["import_status"] = "IMPORTED_WITH_BLOCKERS" if amended["blockers"] else "IMPORTED"
    return amended


def refresh_inventory_audit(audit, source_path, *, checkpoint=None):
    """Read-only source rederivation; returns a new audit and never writes assets."""
    import ifcopenshell
    from .audit import sha256_file
    if checkpoint:
        checkpoint("inventory_source_before_parse")
    source_sha256 = sha256_file(source_path)
    if source_sha256 != audit["source_sha256"]:
        raise ValueError("Inventory refresh requires the exact originally audited source bytes")
    model = ifcopenshell.open(str(source_path))
    if checkpoint:
        checkpoint("inventory_source_parsed")
    amended = apply_inventory_audit(audit, physical_inventory(model), source_sha256)
    if checkpoint:
        checkpoint("inventory_source_derived")
    if sha256_file(source_path) != source_sha256:
        raise ValueError("Immutable source bytes changed during inventory refresh")
    return amended
