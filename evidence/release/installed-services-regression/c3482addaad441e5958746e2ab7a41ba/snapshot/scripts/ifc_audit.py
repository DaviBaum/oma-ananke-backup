"""Isolated per-file IFC-Bench campaign; resume only matching source/version artifacts."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from oma.ifc.audit import AUDIT_VERSION, atomic_json, audit_file, federation_manifest


def campaign(projects=None, workers=2, timeout=1800):
    manifest = json.loads((ROOT / "evidence/ifc/acquisition.json").read_text(encoding="utf-8"))
    files = [f for f in manifest["files"] if f["is_ifc"] and f["status"] == "ACQUIRED"
             and (not projects or f["project"] in projects)]
    # Early interactive integration first, then all mandatory/compatibility files.
    files.sort(key=lambda f: (f["project"] != "digital_hub", not f["required"], f["path"]))
    output = ROOT / "evidence/ifc/campaign.json"
    previous = json.loads(output.read_text(encoding="utf-8")) if output.exists() else {}
    records = {r["path"]: r for r in previous.get("files", [])}

    def worker(entry):
        out = ROOT / "evidence/ifc/audits" / entry["project"]
        out.mkdir(parents=True, exist_ok=True)
        expected = out / f"{Path(entry['path']).stem}-{entry['sha256'][:12]}.audit.json"
        result = {"path": entry["path"], "project": entry["project"], "required": entry["required"],
                  "source_sha256": entry["sha256"], "schema_track": "ifc2x3" if "ifc2x3" in entry["path"] else "ifc4" if "ifc4" in entry["path"] else "default"}
        start = time.perf_counter()
        try:
            reuse = False
            if expected.exists():
                prior = json.loads(expected.read_text(encoding="utf-8"))
                reuse = prior.get("audit_version") == AUDIT_VERSION and prior["source_sha256"] == entry["sha256"]
            if not reuse:
                with (out / f"{Path(entry['path']).stem}.log").open("w", encoding="utf-8") as log:
                    run = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--file", str(ROOT / entry["local_path"]), "--output", str(out)],
                                         stdout=log, stderr=subprocess.STDOUT, timeout=timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                if run.returncode:
                    raise RuntimeError(f"Isolated importer exited {run.returncode}")
            audit = json.loads(expected.read_text(encoding="utf-8"))
            result.update(status="IMPORTED", audit_path=str(expected.relative_to(ROOT)),
                          schema=audit["schema"], products=audit["product_count"], physical=audit["physical_object_count"],
                          geometry_counts=audit["geometry_counts"], blockers=audit["blockers"],
                          ports=len(audit["ports"]), explicit_connections=len(audit["explicit_connections"]),
                          systems=len(audit["systems"]), performance=audit["performance"],
                          negative_capability={"missing_connectivity": audit["connectivity_status"] == "MISSING_INPUTS",
                                               "unqualified_coordination_blocked": audit["coordination_verification"]["status"] != "PASS"})
        except subprocess.TimeoutExpired:
            result.update(status="TIMED_OUT", error=f"Per-file limit {timeout}s")
        except Exception as exc:
            result.update(status="FAILED", error=f"{type(exc).__name__}: {exc}")
        result["wall_seconds"] = time.perf_counter() - start
        return result

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for future in as_completed([pool.submit(worker, f) for f in files]):
            result = future.result()
            records[result["path"]] = result
            atomic_json(output, {"revision": manifest["revision"], "audit_version": AUDIT_VERSION,
                                 "discovered_ifcs": sum(f["is_ifc"] for f in manifest["files"]),
                                 "selected_this_invocation": len(files), "files": sorted(records.values(), key=lambda r: r["path"])})
            print(json.dumps({k:result[k] for k in ("path", "status", "wall_seconds")}), flush=True)
    groups = {}
    for result in records.values():
        if result["status"] == "IMPORTED":
            key = (result["project"], result["schema_track"])
            groups.setdefault(key, []).append(json.loads((ROOT / result["audit_path"]).read_text(encoding="utf-8")))
    for (project, track), audits in groups.items():
        federation = federation_manifest(audits, f"{project}/{track}")
        atomic_json(ROOT / f"evidence/ifc/federations/{project}-{track}.json", federation)
    return records


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file")
    parser.add_argument("--output")
    parser.add_argument("--project", action="append")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()
    if args.file:
        result = audit_file(args.file, args.output, threads=4)
        print(json.dumps({"source_id": result["source_id"], "status": result["import_status"], "performance": result["performance"]}), flush=True)
    else:
        campaign(args.project, max(1, min(4, args.workers)), args.timeout)
