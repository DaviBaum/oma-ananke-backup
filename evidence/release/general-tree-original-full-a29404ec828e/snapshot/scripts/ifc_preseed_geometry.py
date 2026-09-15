"""Populate future import display caches from fully verified corpus audits."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / "src"))
from oma.ifc.audit import AUDIT_VERSION,atomic_json,sha256_file


def preseed(project,stems,store_dir):
    import ifcopenshell
    acquisition=json.loads((ROOT / "evidence/ifc/acquisition.json").read_text(encoding="utf-8"))
    results=[]
    for item in acquisition["files"]:
        stem=Path(item["path"]).stem
        if not item["is_ifc"] or item["project"]!=project or stem not in stems:
            continue
        source=ROOT / item["local_path"]
        if sha256_file(source)!=item["sha256"]:
            raise ValueError("Original source bytes changed")
        audit_path=ROOT / "evidence/ifc/audits" / project / f"{stem}-{item['sha256'][:12]}.audit.json"
        audit=json.loads(audit_path.read_text(encoding="utf-8"))
        expected={"world_coordinates":True,"length_unit":"m","linear_deflection_m":.001,"angular_deflection_rad":.1,"certified_tessellation_error_bound":None}
        if (audit["audit_version"]!=AUDIT_VERSION or audit["ifcopenshell_version"]!=ifcopenshell.version or
            audit["source_sha256"]!=item["sha256"] or any(audit["geometry_contract"].get(k)!=v for k,v in expected.items())):
            raise ValueError("Audit cache applicability does not match current imported geometry policy")
        destination=Path(store_dir)/"geometry"/item["sha256"]
        # Any prior/in-flight directory is left to its owning importer.
        if destination.exists():
            results.append({"source":item["path"],"status":"SKIPPED_EXISTING_OR_IN_FLIGHT_DIRECTORY"})
            continue
        staging=destination.with_name(destination.name+".preseed-"+uuid.uuid4().hex)
        staging.mkdir(parents=True)
        artifacts={}
        hashes={}
        for name,filename in audit["artifacts"].items():
            original=Path(filename)
            final=destination/original.name
            artifacts[name]=str(final.resolve())
            if name=="audit":
                continue
            copied=staging/original.name
            shutil.copyfile(original,copied)
            source_hash=sha256_file(original)
            if sha256_file(copied)!=source_hash:
                raise ValueError("Copied display artifact digest mismatch")
            hashes[name]=source_hash
        immutable=Path(store_dir)/"imports"/item["sha256"]/Path(item["path"]).name
        if immutable.exists():
            if sha256_file(immutable)!=item["sha256"]:
                raise ValueError("Existing immutable imported source differs")
            audit["source_path"]=str(immutable.resolve())
        else:
            audit["source_path"]=str(source.resolve())
        audit["artifacts"]=artifacts
        audit["derived_cache_provenance"]={"original_audit_sha256":sha256_file(audit_path),"source_sha256":item["sha256"],
            "artifact_sha256":hashes,"geometry_parameters_rechecked":expected,"import_count_unchanged":True}
        atomic_json(staging/audit_path.name,audit)
        if destination.exists():
            results.append({"source":item["path"],"status":"RACE_SKIPPED_STAGING_RETAINED","staging":str(staging)})
            continue
        staging.rename(destination)
        results.append({"source":item["path"],"status":"PRESEEDED_VERIFIED","source_sha256":item["sha256"],
                        "destination":str(destination.resolve()),"artifact_sha256":hashes})
        print(json.dumps(results[-1]),flush=True)
    atomic_json(ROOT / f"evidence/ifc/{project}-preseed.json",{"project":project,"records":results})


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project",required=True)
    parser.add_argument("--stem",action="append",required=True)
    parser.add_argument("--store",default=str(ROOT/".oma"))
    args=parser.parse_args()
    preseed(args.project,args.stem,args.store)
