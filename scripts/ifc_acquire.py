"""Acquire immutable IFC-Bench inputs via supported huggingface_hub APIs.

Run: .venv/Scripts/python scripts/ifc_acquire.py --all-projects
Original assets stay in data/ifc-bench and must not be redistributed by default.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

from huggingface_hub import HfApi, hf_hub_download

ROOT = Path(__file__).resolve().parents[1]
REPO = "sylvainHellin/ifc-bench"
REQUIRED = ("digital_hub", "west_riverside_hospital", "sixty5", "wbdg_office", "dental_clinic", "duplex")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(8 * 1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


def validate_ifc_bytes(path: Path) -> None:
    with path.open("rb") as f:
        head = f.read(4096).lstrip(b"\xef\xbb\xbf \r\n\t")
        f.seek(max(0, path.stat().st_size - 4096))
        tail = f.read()
    if not head.startswith(b"ISO-10303-21;") or b"END-ISO-10303-21;" not in tail:
        raise ValueError(f"Not a complete STEP IFC byte stream: {path}")


def atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def acquire(all_projects: bool = False, workers: int = 3, inventory_only: bool = False) -> dict:
    out = ROOT / "evidence" / "ifc"
    destination = ROOT / "data" / "ifc-bench"
    lock_path = out / "dataset-lock.json"
    api = HfApi()
    if lock_path.exists():
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        revision = lock["revision"]
    else:
        revision = api.dataset_info(REPO, revision="main").sha
        lock = {"repository": REPO, "repository_type": "dataset", "revision": revision,
                "resolved_at": datetime.now(timezone.utc).isoformat(), "required_projects": list(REQUIRED),
                "source": f"https://huggingface.co/datasets/{REPO}/tree/{revision}"}
        atomic_json(lock_path, lock)
    if len(revision) != 40:
        raise ValueError("Full immutable commit SHA required")
    entries = []
    for node in api.list_repo_tree(REPO, repo_type="dataset", revision=revision, recursive=True):
        if not hasattr(node, "size"):
            continue
        path = node.path
        project = path.split("/")[1] if path.startswith("projects/") else None
        lfs = getattr(node, "lfs", None)
        entries.append({"path": path, "size": node.size, "project": project,
                        "is_ifc": path.lower().endswith(".ifc"), "required": project in REQUIRED,
                        "lfs_sha256": getattr(lfs, "sha256", None) if lfs else None})
    inventory = {**lock, "entries": entries, "projects": sorted({e["project"] for e in entries if e["project"]}),
                 "total_bytes": sum(e["size"] for e in entries),
                 "ifc_count": sum(e["is_ifc"] for e in entries),
                 "required_ifc_count": sum(e["is_ifc"] and e["required"] for e in entries)}
    atomic_json(out / "repository-inventory.json", inventory)
    print(json.dumps({k: inventory[k] for k in ("revision", "projects", "total_bytes", "ifc_count", "required_ifc_count")}), flush=True)
    if inventory_only:
        return inventory
    # Keep all model cards, licenses, and supporting metadata, without the unrelated QA data.
    selected = [e for e in entries if (e["is_ifc"] and (all_projects or e["required"]))
                or (not e["is_ifc"] and (e["path"].startswith("projects/") or e["path"] == ".gitattributes"
                    or e["path"].lower().endswith((".md", ".txt", ".yaml", ".yml", ".json"))
                    or "licen" in e["path"].lower()))]
    results_path = out / "acquisition.json"
    previous = json.loads(results_path.read_text(encoding="utf-8")) if results_path.exists() else {}
    records = {x["path"]: x for x in previous.get("files", [])}

    def fetch(entry):
        start = time.monotonic()
        result = dict(entry)
        try:
            path = Path(hf_hub_download(repo_id=REPO, filename=entry["path"], repo_type="dataset",
                                        revision=revision, local_dir=destination))
            if entry["is_ifc"]:
                validate_ifc_bytes(path)
            result.update(sha256=sha256(path), actual_size=path.stat().st_size,
                          local_path=str(path.relative_to(ROOT)), status="ACQUIRED")
            if result["actual_size"] != entry["size"]:
                raise ValueError("Remote/local file size mismatch")
            if entry["lfs_sha256"] and result["sha256"] != entry["lfs_sha256"]:
                raise ValueError("Remote LFS SHA-256 differs from actual model hash")
        except Exception as exc:
            result.update(status="FAILED", error=f"{type(exc).__name__}: {exc}")
        result["elapsed_seconds"] = round(time.monotonic() - start, 3)
        return result

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(fetch, entry) for entry in selected]
        for future in as_completed(futures):
            result = future.result()
            records[result["path"]] = result
            atomic_json(results_path, {**lock, "all_projects": all_projects,
                                      "files": sorted(records.values(), key=lambda e: e["path"])})
            print(f"{result['status']} {result['path']} {result.get('actual_size', 0):,} bytes", flush=True)
    failed = [r for r in records.values() if r["status"] != "ACQUIRED"]
    if failed:
        raise RuntimeError(f"{len(failed)} acquisitions failed; see {results_path}")
    return inventory


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all-projects", action="store_true")
    parser.add_argument("--inventory-only", action="store_true")
    parser.add_argument("--workers", type=int, default=3)
    args = parser.parse_args()
    acquire(args.all_projects, max(1, min(8, args.workers)), args.inventory_only)
