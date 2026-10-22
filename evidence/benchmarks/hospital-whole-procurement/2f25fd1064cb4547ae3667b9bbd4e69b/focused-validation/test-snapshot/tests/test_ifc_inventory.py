"""Physical assembly coverage must not erase unsupported source identities."""
import hashlib
import json
from copy import deepcopy

import ifcopenshell
import pytest

from oma.ifc.audit import audit_file
from oma.ifc.cad import load_cad
from oma.ifc.inventory import physical_inventory, accounted_assemblies, refresh_inventory_audit, VERSION
from test_ifc_pipeline import make_fixture


def assembled_source(path, mode="valid"):
    make_fixture(path)
    model = ifcopenshell.open(str(path))
    leaf = model.by_type("IfcBuildingElementProxy")[0]
    parent = model.create_entity("IfcElementAssembly", GlobalId=ifcopenshell.guid.new())
    inner = model.create_entity("IfcElementAssembly", GlobalId=ifcopenshell.guid.new())
    def relation(owner, children):
        return model.create_entity("IfcRelAggregates", GlobalId=ifcopenshell.guid.new(), RelatingObject=owner, RelatedObjects=children)
    relation(parent, [inner])
    children = [leaf]
    if mode in {"space", "void", "missing"}:
        cls = {"space":"IfcSpace", "void":"IfcOpeningElement", "missing":"IfcBeam"}[mode]
        children.append(model.create_entity(cls, GlobalId=ifcopenshell.guid.new()))
    if mode == "cycle":
        children.append(parent)
    if mode == "represented_cycle":
        relation(leaf, [parent])
    relation(inner, children)
    model.write(str(path))
    return path, parent.id(), inner.id(), leaf.id()


@pytest.mark.parametrize("mode", ["space", "void", "missing", "cycle", "represented_cycle"])
def test_invalid_descendant_never_disappears_from_native_or_display_denominator(tmp_path, mode):
    path, parent, inner, leaf = assembled_source(tmp_path / "assembly.ifc", mode)
    model = ifcopenshell.open(str(path))
    inventory = physical_inventory(model)
    assert inventory["errors"]
    assert inventory["assemblies"][parent]["status"] == "UNRESOLVED"
    objects, errors = load_cad(path)
    assert errors
    error_ids = {int(e["entity_id"].rsplit(":", 1)[1]) for e in errors if e.get("entity_id")}
    assert parent in error_ids and inner in error_ids
    assert {o.step_id for o in objects} | error_ids >= set(inventory["physical_step_ids"])
    audit = audit_file(path)
    assert audit["physical_object_count"] == len(inventory["physical_step_ids"])
    assert next(p for p in audit["products"] if p["step_id"] == parent)["geometry_status"] == "unresolved"
    assert any(b["code"] == "INVALID_PHYSICAL_DECOMPOSITION" for b in audit["blockers"])


def test_nested_assembly_requires_every_selected_leaf_and_preserves_counts(tmp_path):
    path, parent, inner, leaf = assembled_source(tmp_path / "valid.ifc")
    model = ifcopenshell.open(str(path))
    inventory = physical_inventory(model)
    assert not inventory["errors"]
    assert accounted_assemblies(inventory, [parent, inner, leaf], [leaf]) == {parent, inner}
    assert not accounted_assemblies(inventory, [parent, inner], [leaf])
    report = {}
    objects, errors = load_cad(path, cache_report=report)
    assert not errors and [o.step_id for o in objects] == [leaf]
    assert report["accounted_assembly_step_ids"] == [parent, inner]
    assert report["selected_physical_count"] == 3
    _, errors = load_cad(path, guids={model.by_id(parent).GlobalId})
    assert errors[0]["reason"] == "PHYSICAL_ASSEMBLY_DESCENDANTS_NOT_ACCOUNTED"
    audit = audit_file(path)
    assert audit["physical_geometry_counts"] == {"represented":1, "explicitly_non_geometric":2}
    assert not audit["blockers"]


@pytest.mark.parametrize("mode", ["space", "void", "missing", "valid"])
def test_refresh_is_read_only_and_corrects_legacy_classification(tmp_path, mode):
    path, parent, inner, leaf = assembled_source(tmp_path / "audit.ifc", mode)
    audit = audit_file(path, tmp_path / "artifacts")
    legacy = deepcopy(audit)
    for p in legacy["products"]:
        if p["step_id"] in [parent, inner]:
            p["geometry_status"] = "explicitly_non_geometric"
    before = deepcopy(legacy)
    source_bytes = path.read_bytes()
    artifact_bytes = {name: open(asset, "rb").read() for name, asset in audit["artifacts"].items()}
    amended = refresh_inventory_audit(legacy, path)
    assert legacy == before and path.read_bytes() == source_bytes
    assert artifact_bytes == {name: open(asset, "rb").read() for name, asset in amended["artifacts"].items()}
    assert amended["physical_inventory"]["version"] == VERSION
    assert amended["inventory_refresh"]["mesh_reconversion"] is False
    assert len(amended["inventory_refresh"]["changed_dispositions"]) == (0 if mode == "valid" else 2)
    if mode == "valid":
        # Geometry failures in descendants prevent a declaration-only exemption.
        next(p for p in legacy["products"] if p["step_id"] == leaf)["geometry_status"] = "unsupported"
        blocked = refresh_inventory_audit(legacy, path)
        assert blocked["physical_geometry_counts"] == {"unsupported":1, "unresolved":2}
    path.write_bytes(source_bytes + b"\n")
    with pytest.raises(ValueError, match="exact originally audited"):
        refresh_inventory_audit(legacy, path)


def test_cache_cannot_forge_assembly_coverage_to_omit_actual_leaf(tmp_path):
    path, parent, inner, leaf = assembled_source(tmp_path / "cache.ifc")
    report = {}
    cold, errors = load_cad(path, cache_directory=tmp_path / "cache", cache_report=report)
    assert not errors
    warm_report = {}
    warm, errors = load_cad(path, cache_directory=tmp_path / "cache", cache_report=warm_report)
    assert not errors and warm_report["status"] == "HIT_REVALIDATED"
    assert [o.step_id for o in cold] == [o.step_id for o in warm] == [leaf]
    entry = tmp_path / "cache" / "entries" / report["key"]
    manifest_path = entry / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["objects"] = []
    for record in manifest["inventory_report"]["physical_inventory"]["assemblies"].values():
        record["leaf_step_ids"] = []
    raw = json.dumps(manifest).encode()
    manifest_path.write_bytes(raw)
    (entry / "manifest.sha256").write_text(hashlib.sha256(raw).hexdigest())
    fresh = {}
    objects, errors = load_cad(path, cache_directory=tmp_path / "cache", cache_report=fresh)
    assert not errors and [o.step_id for o in objects] == [leaf]
    assert fresh["status"] == "CORRUPT_REBUILT"
    assert "accounting" in fresh["invalid_reason"]


def test_cache_cannot_remove_rederived_cycle_failure(tmp_path):
    path, *_ = assembled_source(tmp_path / "cycle.ifc", "represented_cycle")
    report = {}
    _, errors = load_cad(path, cache_directory=tmp_path / "cache", cache_report=report)
    assert errors
    entry = tmp_path / "cache" / "entries" / report["key"]
    manifest_path = entry / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for error in manifest["errors"]:
        error["reason"] = "FORGED_BENIGN_ACCOUNTING"
    raw = json.dumps(manifest).encode()
    manifest_path.write_bytes(raw)
    (entry / "manifest.sha256").write_text(hashlib.sha256(raw).hexdigest())
    fresh = {}
    _, errors = load_cad(path, cache_directory=tmp_path / "cache", cache_report=fresh)
    assert fresh["status"] == "CORRUPT_REBUILT" and errors
    assert "inventory failures were omitted" in fresh["invalid_reason"]


@pytest.mark.parametrize("field,value", [("type","IfcSlab"), ("ifc_guid","forged"), ("entity_id","fake:1"), ("physical",False), ("has_representation",False), ("source_sha256","0"*64)])
def test_refresh_rejects_forged_legacy_product_provenance(tmp_path, field, value):
    path = make_fixture(tmp_path / "source.ifc")
    audit = audit_file(path)
    physical = next(p for p in audit["products"] if p["physical"])
    physical[field] = value
    with pytest.raises(ValueError, match="provenance"):
        refresh_inventory_audit(audit, path)


def test_refresh_rejects_duplicate_and_omitted_audit_product_and_midread_source_change(tmp_path):
    path = make_fixture(tmp_path / "source.ifc")
    audit = audit_file(path)
    for products in [audit["products"] + [audit["products"][0]], audit["products"][1:]]:
        with pytest.raises(ValueError, match="identities"):
            refresh_inventory_audit({**audit, "products":products}, path)
    def mutate(stage):
        if stage == "inventory_source_derived":
            path.write_bytes(path.read_bytes() + b"\n")
    with pytest.raises(ValueError, match="changed during"):
        refresh_inventory_audit(audit, path, checkpoint=mutate)


def test_refresh_checkpoint_cancellation_propagates(tmp_path):
    path = make_fixture(tmp_path / "source.ifc")
    audit = audit_file(path)
    def cancel(stage):
        raise RuntimeError("cancel source audit")
    with pytest.raises(RuntimeError, match="cancel source audit"):
        refresh_inventory_audit(audit, path, checkpoint=cancel)
