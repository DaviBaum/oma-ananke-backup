"""Portable immutable-store backups, with byte hashes and provenance relocation.

Snapshot roots and checker reports are never rewritten. A separate path resolver
relocates their referenced bytes; all restored bytes must pass the manifest hash.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
from pathlib import Path

from .store import IntegrityError, Store, canonical, utcnow


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _copy(source: Path, destination: Path):
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    if file_hash(source) != file_hash(destination):
        raise IntegrityError(f"Asset changed while taking backup: {source.name}")


def _asset_references(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"immutable_path", "source_path", "export_path", "mesh_json_gz", "mesh_npz"} and isinstance(item, str):
                yield item
            elif key != "properties":
                yield from _asset_references(item)
    elif isinstance(value, list):
        for item in value:
            yield from _asset_references(item)


def backup_store(store: Store, destination: str | Path) -> Path:
    destination = Path(destination).resolve()
    if destination == store.directory or destination.is_relative_to(store.directory):
        raise ValueError("Backup destination must be outside the live store")
    destination.mkdir(parents=True, exist_ok=False)
    # Full published assets, including past candidates and exports. Kernel caches,
    # rendered view caches and logs are reproducible and not proof dependencies.
    omitted = {"cad-cache", "logs"}
    with store.transaction():
        with store.connect() as source, sqlite3.connect(destination / "oma.sqlite3") as target:
            source.backup(target)
            row = source.execute("SELECT value FROM metadata WHERE key='relocation_roots'").fetchone()
            roots = list(dict.fromkeys([str(store.directory), *(json.loads(row[0]) if row else [])]))
            target.execute("INSERT OR REPLACE INTO metadata VALUES('relocation_roots',?)", (json.dumps(roots),))
            # Restoring never inherits live process ownership or a permission to
            # resume a run from the original machine.
            target.execute("DELETE FROM run_owners")
            for path in store.directory.rglob("*"):
                relative = path.relative_to(store.directory)
                if not path.is_file() or relative.parts[0] in omitted or relative.name.startswith(".pending-") or relative.suffix == ".pending":
                    continue
                if relative.parts[0] in {"oma.sqlite3", "oma.sqlite3-wal", "oma.sqlite3-shm", "backup-manifest.json", "service.json"}:
                    continue
                if relative.parts[:2] == ("geometry", "views"):
                    continue
                if path.is_symlink() or not path.resolve().is_relative_to(store.directory):
                    raise IntegrityError("Backup refuses a linked asset outside the store")
                _copy(path, destination / relative)
            for blob in store.blobs.glob("*.json.z"):
                for reference in _asset_references(store.get(blob.name.removesuffix(".json.z"))):
                    resolved = store.resolve_path(reference).resolve()
                    if resolved.is_relative_to(store.directory):
                        if not (destination / resolved.relative_to(store.directory)).is_file():
                            raise IntegrityError(f"Referenced asset is absent from backup: {resolved.name}")
                        continue
                    if not resolved.is_file():
                        raise IntegrityError(f"External referenced asset is missing: {resolved.name}")
                    hashed = file_hash(resolved)
                    relative = Path("external-assets") / hashed / resolved.name
                    if not (destination / relative).exists():
                        _copy(resolved, destination / relative)
                    target.execute("INSERT OR REPLACE INTO asset_aliases VALUES(?,?,?)", (reference, str(relative), hashed))
            target.commit()
            target.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            target.execute("PRAGMA journal_mode=DELETE")
        target.close()
    assets = [{"path": str(path.relative_to(destination)).replace("\\", "/"), "size_bytes": path.stat().st_size,
               "sha256": file_hash(path)} for path in sorted(destination.rglob("*")) if path.is_file()]
    manifest = {"format": "oma-portable-store/1", "created_at": utcnow(), "source_store": str(store.directory),
                "status": "COMPLETE", "roots_rewritten": False, "files": assets,
                "omitted_reproducible": ["cad-cache", "geometry/views", "logs", "live-process-ownership"]}
    (destination / "backup-manifest.json").write_bytes(canonical(manifest))
    verify_backup(destination)
    return destination


def verify_backup(directory: str | Path) -> dict:
    directory = Path(directory).resolve()
    manifest = json.loads((directory / "backup-manifest.json").read_bytes())
    if manifest.get("format") != "oma-portable-store/1" or manifest.get("status") != "COMPLETE":
        raise IntegrityError("Incomplete or unsupported backup")
    files = manifest["files"]
    names = set()
    for entry in files:
        path = (directory / entry["path"]).resolve()
        if not path.is_relative_to(directory) or path in names or not path.is_file():
            raise IntegrityError("Invalid, duplicate or missing backup asset")
        names.add(path)
        if path.stat().st_size != entry["size_bytes"] or file_hash(path) != entry["sha256"]:
            raise IntegrityError(f"Backup asset hash mismatch: {entry['path']}")
    if directory / "oma.sqlite3" not in names:
        raise IntegrityError("Backup database missing")
    with sqlite3.connect(f"file:{(directory / 'oma.sqlite3').as_posix()}?mode=ro", uri=True) as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise IntegrityError("Backup SQLite integrity check failed")
        for (root,) in db.execute("SELECT root FROM revisions UNION SELECT state_root FROM candidates UNION SELECT report_root FROM candidates WHERE report_root IS NOT NULL"):
            if directory / "blobs" / f"{root}.json.z" not in names:
                raise IntegrityError("Database refers to a missing immutable content root")
    return {"status": "PASS", "files_checked": len(files), "roots_rewritten": False}


def restore_store(backup: str | Path, destination: str | Path) -> Store:
    backup, destination = Path(backup).resolve(), Path(destination).resolve()
    verify_backup(backup)
    if destination.exists():
        raise ValueError("Restore destination must not exist")
    shutil.copytree(backup, destination)
    verify_backup(destination)
    restored = Store(destination)
    restored.recover()
    return restored
