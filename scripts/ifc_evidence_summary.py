"""Publish compact IFC acquisition/import evidence without bundling source assets."""
from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT / "src"))
from oma.ifc.audit import atomic_json,sha256_file


def summarize():
    acquisition=json.loads((ROOT / "evidence/ifc/acquisition.json").read_text(encoding="utf-8"))
    campaign=json.loads((ROOT / "evidence/ifc/campaign.json").read_text(encoding="utf-8"))
    audited={r["path"]:r for r in campaign["files"]}
    products=physical=vertices=triangles=ports=connections=0
    physical_status=Counter()
    files=[]
    for source in acquisition["files"]:
        if not source["is_ifc"]:
            continue
        record=audited.get(source["path"],{})
        row={k:source[k] for k in ("path","project","required","sha256","actual_size","lfs_sha256")}
        row["status"]=record.get("status","NOT_ATTEMPTED")
        row["lfs_hash_verified"]=source["lfs_sha256"] == source["sha256"]
        if row["status"]=="IMPORTED":
            audit=json.loads((ROOT / record["audit_path"]).read_text(encoding="utf-8"))
            if audit["source_sha256"]!=source["sha256"]:
                raise ValueError("Audit/source identity mismatch")
            products+=audit["product_count"]
            physical+=audit["physical_object_count"]
            physical_status.update(audit["physical_geometry_counts"])
            vertices+=audit["performance"]["vertices"]
            triangles+=audit["performance"]["triangles"]
            ports+=len(audit["ports"])
            connections+=len(audit["explicit_connections"])
            row.update(schema=audit["schema"],products=audit["product_count"],physical=audit["physical_object_count"],
                physical_geometry_status=audit["physical_geometry_counts"],units=audit["units"],
                explicit_ports=len(audit["ports"]),explicit_port_connections=len(audit["explicit_connections"]),
                inference_count=len(audit["inferred_connections"]),systems=len(audit["systems"]),
                import_seconds=audit["performance"]["total_seconds"],blockers=audit["blockers"],
                connectivity_status=audit["connectivity_status"],mesh_artifacts=record["audit_path"],
                unqualified_coordination_status=audit["coordination_verification"]["status"])
        else:
            row["error"]=record.get("error","No completed audit")
        files.append(row)
    disk=shutil.disk_usage(ROOT)
    footprints={name:sum(p.stat().st_size for p in (ROOT / location).rglob("*") if p.is_file())
                for name,location in (("downloaded_sources_and_support","data/ifc-bench"),("audit_artifacts","evidence/ifc/audits"),("native_cache",".oma/cad-cache"))}
    result={"dataset_repository":acquisition["repository"],"immutable_revision":acquisition["revision"],
        "acquisition_manifest_sha256":sha256_file(ROOT / "evidence/ifc/acquisition.json"),
        "discovered_projects":len({f["project"] for f in files}),"discovered_ifcs":len(files),
        "mandatory_ifcs":sum(f["required"] for f in files),"status_counts":dict(Counter(f["status"] for f in files)),
        "all_ifc_lfs_hashes_match":all(f["lfs_hash_verified"] for f in files),
        "products_accounted":products,"physical_objects_accounted":physical,"physical_geometry_status":dict(physical_status),
        "display_vertices":vertices,"display_triangles":triangles,"explicit_ports":ports,"explicit_port_connections":connections,
        "source_and_derived_bytes":footprints,"workspace_volume_free_bytes":disk.free,
        "method":{"geometry":"IfcOpenShell world-metre geometry iterator; source identity retained in display meshes",
                  "identity":"source_sha256:STEP_ID, source GUID recorded separately; GUID collisions never merged automatically",
                  "unknowns":"Every missing/invalid physical representation blocks unqualified verification; import is not coordination approval",
                  "connectivity":"Only declared IFC ports, ownership and relationships; absent connectivity is not inferred",
                  "datum":"Raw source transformations retained; local federation requires generic shared-anchor evidence; geospatial conflicts remain unresolved",
                  "hospital_tracks":"IFC2X3 and IFC4 alternatives separately inventoried/audited; never one duplicate federation",
                  "export":"Actual additive swept physical geometry, tangent elbows, explicit directed ports, systems and fresh reimport; originals unchanged",
                  "native_checker":"Boolean common positive volume/containment and shape-distance recomputed with OCP; fixed tolerance ambiguities stay unresolved",
                  "native_cache":"Immutable source and implementation hashes; native BRep digests/topology and exact support certificates revalidated per process",
                  "source_enclosures":"Default exact planar support; explicit scenario opt-in can cover declared source vertex-hull completion families; no source validity upgrade",
                  "license":"Per-project source cards/license text retained in data-license-register.json; application package excludes source assets"},
        "files":files}
    atomic_json(ROOT / "evidence/ifc/summary.json",result)
    print(json.dumps({k:result[k] for k in ("discovered_projects","discovered_ifcs","mandatory_ifcs","status_counts","physical_objects_accounted","explicit_ports","all_ifc_lfs_hashes_match","source_and_derived_bytes")}))
    return result


if __name__=="__main__":
    summarize()
