"""Snapshot the complete read-only math tree, including ignored files and ZIP members.

Inventory is not substantive reading. No source, extraction, or review status is
promoted by this tool. Duplicate archive member names retain separate indices.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import struct
import zipfile


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def inventory(source: Path) -> dict:
    if source.is_symlink() or source.is_junction():
        raise ValueError("The source root is a link; resolve and authorize it explicitly")
    source = source.resolve(strict=True)
    if not source.is_dir():
        raise ValueError("The source root must be a directory")
    files = []
    errors = []
    paths = []
    def fail_walk(error):
        raise error
    for folder, directories, names in os.walk(source, followlinks=False, onerror=fail_walk):
        # os.walk(followlinks=False) alone does not establish junction behavior.
        # Prune both kinds before traversal, and retain the unresolved locator.
        retained = []
        for name in directories:
            candidate = Path(folder) / name
            if candidate.is_symlink() or candidate.is_junction():
                errors.append({"path": candidate.relative_to(source).as_posix(), "error": "LINK_REQUIRES_EXPLICIT_REVIEW"})
            else:
                retained.append(name)
        directories[:] = sorted(retained)
        paths.extend(Path(folder) / name for name in names)
    for path in sorted(paths):
        relative = path.relative_to(source).as_posix()
        if path.is_symlink() or path.is_junction():
            errors.append({"path": relative, "error": "LINK_REQUIRES_EXPLICIT_REVIEW"})
            continue
        if not path.is_file():
            continue
        before = path.stat()
        raw = path.read_bytes()
        record = {
            "path": relative,
            "sha256": sha256(raw),
            "bytes": len(raw),
            "kind": path.suffix.lower().lstrip(".") or "unclassified",
            "reading_status": "NOT_READ_IN_NEW_CAMPAIGN",
            "independent_review_status": "NOT_REVIEWED",
        }
        if raw[:4] == b"\x00\x05\x16\x07":
            record["kind"] = "appledouble"
            entries = []
            if len(raw) < 26:
                errors.append({"path": relative, "error": "TRUNCATED_APPLEDOUBLE"})
            else:
                count = struct.unpack_from(">H", raw, 24)[0]
                if 26 + count * 12 > len(raw):
                    errors.append({"path": relative, "error": "TRUNCATED_APPLEDOUBLE_DIRECTORY"})
                else:
                    for index in range(count):
                        entry_id, offset, length = struct.unpack_from(">III", raw, 26 + index * 12)
                        bounded = offset <= len(raw) and length <= len(raw) - offset
                        entries.append({
                            "index": index, "entry_id": entry_id,
                            "offset": offset, "length": length,
                            "in_bounds": bounded,
                            "sha256": sha256(raw[offset:offset + length]) if bounded else None,
                        })
                        if not bounded:
                            errors.append({"path": relative, "error": "APPLEDOUBLE_ENTRY_OUT_OF_BOUNDS", "index": index})
            record["entries"] = entries
            record["unique_substance_status"] = "PENDING_METADATA_INSPECTION"
        elif path.name == ".DS_Store":
            record["kind"] = "filesystem_metadata"
            record["unique_substance_status"] = "PENDING_METADATA_INSPECTION"
        # AppleDouble metadata can have a .docx/.pages suffix without being a ZIP.
        if zipfile.is_zipfile(path):
            members = []
            directory_entries = []
            with zipfile.ZipFile(path) as archive:
                for index, info in enumerate(archive.infolist()):
                    if info.is_dir():
                        directory_entries.append({"index": index, "path": info.filename, "bytes": info.file_size})
                        continue
                    member = archive.read(info)
                    members.append({
                        "index": index, "path": info.filename, "bytes": len(member),
                        "crc32": f"{info.CRC:08x}", "sha256": sha256(member),
                    })
            record["archive_members"] = members
            record["archive_directory_entries"] = directory_entries
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            errors.append({"path": relative, "error": "SOURCE_CHANGED_DURING_READ"})
        if sha256(path.read_bytes()) != record["sha256"]:
            errors.append({"path": relative, "error": "SOURCE_CHANGED_DURING_INVENTORY"})
        files.append(record)
    tree = [(r["path"], r["sha256"], r["bytes"]) for r in files]
    return {
        "schema": "oma.research.recursive-source-inventory/3",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source_root": str(source),
        "hidden_and_ignored_included": True,
        "inventory_is_not_reading": True,
        "occurrence_denominator_frozen": False,
        "file_count": len(files),
        "total_bytes": sum(r["bytes"] for r in files),
        "archive_member_count": sum(len(r.get("archive_members", [])) for r in files),
        "source_tree_sha256": sha256(json.dumps(tree, separators=(",", ":")).encode()),
        "files": files,
        "errors": errors,
        "status": "INVENTORIED" if not errors else "INCOMPLETE",
    }


def same_sources(previous: dict, current: dict) -> bool:
    """Ignore timestamps/status annotations; compare every byte identity and locator."""
    if previous.get("schema") != current.get("schema"):
        return False
    if previous.get("status") != "INVENTORIED" or previous.get("errors") != []:
        return False
    if previous.get("source_root") != current.get("source_root"):
        return False
    if previous.get("file_count") != len(previous.get("files", [])):
        return False
    def identities(report):
        return [{k: r.get(k) for k in ("path", "sha256", "bytes", "archive_members", "archive_directory_entries", "entries")}
                for r in report["files"]]
    return not current["errors"] and identities(previous) == identities(current)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path(__file__).resolve().parents[1] / "math1")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output", type=Path)
    group.add_argument("--check", type=Path)
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    if args.output:
        destination = args.output.resolve()
        if destination == source or source in destination.parents:
            parser.error("Output must be outside the read-only source tree")
        if destination.exists():
            parser.error("Refusing to overwrite an existing inventory; use a new filename or --check")
    # Preserve the user-supplied root identity for the link guard in inventory().
    report = inventory(args.source)
    if args.check:
        previous = json.loads(args.check.read_text(encoding="utf-8"))
        matches = same_sources(previous, report)
        print(json.dumps({"sources_match": matches, "file_count": report["file_count"], "errors": report["errors"]}))
        return 0 if matches else 1
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation protects prior snapshots. The consumer must require valid
    # JSON and status before using a snapshot interrupted while it was being written.
    with destination.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({k: report[k] for k in ("status", "file_count", "total_bytes", "archive_member_count", "source_tree_sha256", "errors")}))
    return 0 if not report["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
