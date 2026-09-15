"""Bind fresh source inventory to a retained native report's actual object ledger.

This adds source-denominator evidence only, never a replacement native verdict.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import ifcopenshell
from oma.ifc.audit import sha256_file, atomic_json
from oma.ifc.inventory import physical_inventory, inventory_evidence, accounted_assemblies
from oma.store import Store


def main(candidate_id, output):
    store = Store(ROOT / ".oma")
    candidate = store.candidate(candidate_id)
    state = store.get(candidate["state_root"])
    report = store.get(candidate["report_root"])
    native_root = next(r for r in report["results"] if r["id"] == "physical-interference-and-clearance")["witness"]["artifact"]
    native = store.get(native_root)
    sources = {s["sha256"]:s for s in state["sources"]}
    evidence = {"candidate_id":candidate_id,"candidate_root":candidate["state_root"],"prior_report_root":candidate["report_root"],
                "native_report_root":native_root,"native_checker_version":report["checker_version"],"sources":[],
                "scope":"FRESH_PHYSICAL_SOURCE_INVENTORY_RECONCILED_WITH_RETAINED_NATIVE_OBJECT_IDENTITIES_ONLY",
                "native_verdict_recomputed":False,"conversion_provenance":"LOCAL_CHECKER_CACHE_ASSUMPTION_RETAINED"}
    for cached in native["performance"]["source_cache"]:
        path = ROOT / ".oma/cad-cache/entries" / cached["key"] / "manifest.json"
        assert sha256_file(path) == path.with_name("manifest.sha256").read_text().strip()
        manifest = json.loads(path.read_text(encoding="utf-8"))
        sha = manifest["key"]["source_sha256"]
        source = sources.pop(sha)
        assert sha256_file(source["immutable_path"]) == sha
        model = ifcopenshell.open(source["immutable_path"])
        inventory = physical_inventory(model)
        assert not inventory["errors"] and not manifest["errors"]
        objects = [obj["metadata"] for obj in manifest["objects"]]
        ids = {obj["step_id"] for obj in objects}
        assert len(ids) == len(objects)
        for obj in objects:
            original = model.by_id(obj["step_id"])
            assert obj["source_sha256"] == sha and obj["entity_id"] == f"{sha}:{original.id()}"
            assert obj["guid"] == original.GlobalId and obj["ifc_type"] == original.is_a()
            assert original.Representation is not None
        assemblies = accounted_assemblies(inventory, inventory["physical_step_ids"], ids)
        assert ids | assemblies == set(inventory["physical_step_ids"])
        assert sha256_file(source["immutable_path"]) == sha
        evidence["sources"].append({"source_sha256":sha,"cache_key":cached["key"],"cache_manifest_sha256":sha256_file(path),
            "native_object_count":len(ids),"native_object_step_ids":sorted(ids),"accounted_assembly_step_ids":sorted(assemblies),
            "physical_inventory":inventory_evidence(inventory,sha)})
    assert not sources
    evidence["status"] = "COMPLETE_SOURCE_DENOMINATOR_RECONCILED"
    atomic_json(Path(output), evidence)
    print(json.dumps({"status":evidence["status"],"sources":len(evidence["sources"]),
                      "physical_records":sum(s["physical_inventory"]["physical_product_count"] for s in evidence["sources"]),
                      "native_objects":sum(s["native_object_count"] for s in evidence["sources"])}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    main(args.candidate, args.output)
