"""Rederive all acquired source inventories without regenerating display assets."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from oma.ifc.audit import atomic_json, sha256_file
from oma.ifc.inventory import refresh_inventory_audit, VERSION, CODE_SHA256


def main():
    campaign_path = ROOT / "evidence/ifc/campaign.json"
    campaign = json.loads(campaign_path.read_text(encoding="utf-8"))
    rows = campaign["files"]
    output = ROOT / "evidence/ifc/physical-inventory-amendment.json"
    result = {"status":"RUNNING", "inventory_version":VERSION, "implementation_sha256":CODE_SHA256,
              "campaign_sha256":sha256_file(campaign_path), "immutable_dataset_revision":campaign["revision"],
              "discovered_ifcs":campaign["discovered_ifcs"], "selected_count":len(rows), "files":[],
              "scope":"SOURCE_DECLARATION_CLOSURE_AND_EXISTING_DISPLAY_AUDIT_AMENDMENT; NO_NATIVE_RECONVERSION_OR_NEW_COORDINATION_CERTIFICATE",
              "original_audits_overwritten":False, "mesh_assets_reconverted":False}
    assert len(rows) == campaign["discovered_ifcs"] == 50
    old_counts, new_counts = Counter(), Counter()
    started = time.perf_counter()
    # Obtain the pending federation's concrete denominator evidence first.
    rows = sorted(rows, key=lambda r:(r["project"] != "digital_hub", r["path"]))
    for row in rows:
        begin = time.perf_counter()
        audit_path = ROOT / row["audit_path"]
        raw = audit_path.read_bytes()
        audit = json.loads(raw)
        source = ROOT / "data/ifc-bench" / row["path"]
        try:
            amended = refresh_inventory_audit(audit, source)
            old_counts.update(audit["physical_geometry_counts"])
            new_counts.update(amended["physical_geometry_counts"])
            record = {"path":row["path"], "project":row["project"], "schema_track":row["schema_track"],
                      "source_sha256":amended["source_sha256"], "prior_audit_path":str(audit_path),
                      "prior_audit_sha256":hashlib.sha256(raw).hexdigest(), "status":"INVENTORY_REDERIVED",
                      "physical_object_count":amended["physical_object_count"],
                      "original_physical_geometry_counts":audit["physical_geometry_counts"],
                      "corrected_physical_geometry_counts":amended["physical_geometry_counts"],
                      "changed_dispositions":amended["inventory_refresh"]["changed_dispositions"],
                      "physical_inventory":amended["physical_inventory"],
                      "corrected_blocker_codes":[b["code"] for b in amended["blockers"]]}
            assert sha256_file(audit_path) == hashlib.sha256(raw).hexdigest()
        except Exception as exc:
            record = {"path":row["path"], "project":row["project"], "status":"FAILED_REDERIVATION", "error":repr(exc)}
        record["seconds"] = time.perf_counter() - begin
        result["files"].append(record)
        result.update(completed_count=len(result["files"]), original_physical_geometry_counts=dict(old_counts),
                      corrected_physical_geometry_counts=dict(new_counts), seconds=time.perf_counter()-started)
        atomic_json(output, result)
        print(json.dumps({k:record.get(k) for k in ["path","status","physical_object_count","seconds"]}), flush=True)
    result["status"] = "COMPLETE" if all(r["status"] == "INVENTORY_REDERIVED" for r in result["files"]) else "INCOMPLETE"
    result["changed_disposition_count"] = sum(len(r.get("changed_dispositions",[])) for r in result["files"])
    atomic_json(output, result)
    print(json.dumps({k:v for k,v in result.items() if k != "files"}), flush=True)


if __name__ == "__main__":
    main()
