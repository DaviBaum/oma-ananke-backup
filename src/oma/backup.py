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
            if key in {"immutable_path", "source_path", "export_path", "mesh_json_gz", "mesh_npz", "audit", "replacement_path"} and isinstance(item, str):
                yield item
            elif key == "path" and isinstance(item, str) and ("sha256" in value or "source_sha256" in value):
                yield item
            elif key != "properties":
                yield from _asset_references(item)
    elif isinstance(value, list):
        for item in value:
            yield from _asset_references(item)


def _content_roots(value):
    if isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _content_roots(item)
    elif isinstance(value, list):
        for item in value:
            yield from _content_roots(item)


def backup_store(store: Store, destination: str | Path) -> Path:
    destination = Path(destination).resolve()
    if destination == store.directory or destination.is_relative_to(store.directory):
        raise ValueError("Backup destination must be outside the live store")
    destination.mkdir(parents=True, exist_ok=False)
    # The write lock covers only the database snapshot. Referenced content is
    # immutable and has no concurrent garbage collector, so large asset copies
    # cannot freeze unrelated publications or durable control requests.
    with store.transaction():
        with store.connect() as source, sqlite3.connect(destination / "oma.sqlite3") as target:
            source.backup(target)
            row = source.execute("SELECT value FROM metadata WHERE key='relocation_roots'").fetchone()
            roots = list(dict.fromkeys([str(store.directory), *(json.loads(row[0]) if row else [])]))
            target.execute("INSERT OR REPLACE INTO metadata VALUES('relocation_roots',?)", (json.dumps(roots),))
            # Restoring never inherits live process ownership or a permission to
            # resume a run from the original machine.
            target.execute("DELETE FROM run_owners")
            target.commit()
            target.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            target.execute("PRAGMA journal_mode=DELETE")
        target.close()
    with sqlite3.connect(destination / "oma.sqlite3") as target:
        roots = {r[0] for r in target.execute("SELECT root FROM revisions UNION SELECT state_root FROM candidates UNION SELECT report_root FROM candidates WHERE report_root IS NOT NULL UNION SELECT base_root FROM runs")}
        documents = [json.loads(r[0]) for r in target.execute("SELECT payload FROM events UNION ALL SELECT request FROM runs UNION ALL SELECT payload FROM candidates UNION ALL SELECT response FROM requests")]
        references, copied = set(), set()
        for document in documents:
            references.update(_asset_references(document))
            roots.update(r for r in _content_roots(document) if (store.blobs / f"{r}.json.z").exists())
        while roots:
            root = roots.pop()
            if root in copied:
                continue
            document = store.get(root)
            _copy(store.blobs / f"{root}.json.z", destination / "blobs" / f"{root}.json.z")
            copied.add(root)
            references.update(_asset_references(document))
            roots.update(r for r in _content_roots(document) if r not in copied and (store.blobs / f"{r}.json.z").exists())
        for reference in sorted(references):
            resolved = store.resolve_path(reference).resolve()
            if not resolved.is_file():
                raise IntegrityError(f"Referenced asset is missing: {resolved.name}")
            hashed = file_hash(resolved)
            relative = resolved.relative_to(store.directory) if resolved.is_relative_to(store.directory) else Path("external-assets") / hashed / resolved.name
            if not (destination / relative).exists():
                _copy(resolved, destination / relative)
            # Native CAD revalidation reads an IFC's materialization sidecar to
            # independently establish unchanged source coordinates. It is part
            # of the physical artifact, not a reproducible display cache.
            if resolved.suffix.lower() == ".ifc":
                sidecar = resolved.with_suffix(".manifest.json")
                if sidecar.is_file():
                    _copy(sidecar, (destination / relative).with_suffix(".manifest.json"))
            if not resolved.is_relative_to(store.directory):
                target.execute("INSERT OR REPLACE INTO asset_aliases VALUES(?,?,?)", (reference, str(relative), hashed))
        # Keep archived checker executables for reproducibility of historical
        # report versions; copied .py files are never loaded from proof blobs.
        runtimes = store.directory / "runtimes"
        for version in runtimes.iterdir() if runtimes.exists() else []:
            if (version / "build-version.txt").is_file():
                for path in version.rglob("*"):
                    if path.is_file() and (path.suffix == ".py" or path.name == "build-version.txt"):
                        _copy(path, destination / path.relative_to(store.directory))
        target.commit()
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
