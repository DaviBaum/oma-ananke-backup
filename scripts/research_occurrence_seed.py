"""Create an UNREAD occurrence ledger from independently audited extraction artifacts.

This prepares the requested 100-slot reading assignment; it launches no agents.
It deliberately does not assert that body paragraphs cover every native object.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import re


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def bound_path(root: Path, relative: str) -> Path:
    path = (root / relative).resolve(strict=True)
    if root not in path.parents:
        raise ValueError(f"Artifact outside repository: {relative}")
    return path


def build(root: Path, audit_path: Path, output: Path) -> dict:
    root = root.resolve(strict=True)
    output = output.resolve()
    forbidden = [(root / "math1").resolve(), (root / "data").resolve()]
    if root not in output.parents or any(output == p or p in output.parents for p in forbidden):
        raise ValueError("Output must be a fresh repository evidence directory outside original inputs")
    if output.exists():
        raise FileExistsError(output)
    audit_raw = audit_path.read_bytes()
    audit = json.loads(audit_raw)
    # Verify original sources and every extraction before making any ledger.
    originals = []
    for source in audit["full_tree_inventory"]:
        path = bound_path(root, source["relative_path"])
        if digest(path.read_bytes()) != source["sha256"]:
            raise ValueError(f"Source hash changed: {path}")
        originals.append((path, source["sha256"]))
    bindings = {x["path"]: x["sha256"] for x in audit["artifact_bindings"]}
    inputs = []
    for source in audit["sources"]:
        document_id = source["document_id"]
        if not re.fullmatch(r"[a-z0-9-]+", document_id):
            raise ValueError("Unsafe document identifier")
        if source.get("extracted_records"):
            relative = source["extraction_artifact"]
            expected = source["actual_extraction_sha256"]
            field = "location"
        elif document_id in ("1-10", "11-20", "21-30"):
            relative = f"evidence/math/pages/{document_id}/body-records.jsonl"
            expected = bindings[relative]
            field = "paragraph"
        else:
            continue
        path = bound_path(root, relative)
        if digest(path.read_bytes()) != expected:
            raise ValueError(f"Extraction hash changed: {path}")
        inputs.append((source, path, expected, field))
    total = audit["counts"]["primary_extracted_locations"]
    if not isinstance(total, int) or total < 100:
        raise ValueError("Expected an audited primary census sufficient for 100 reading slots")
    output.mkdir(parents=True, exist_ok=False)
    # An incomplete directory has no status.json; consumers must fail closed.
    (output / "source-audit.json").write_bytes(audit_raw)
    global_index = 0
    ids = set()
    shards = []
    assignments = defaultdict(list)
    for source, path, expected, field in inputs:
        shard = output / (source["document_id"] + ".jsonl.gz")
        count = 0
        ranges = {}
        with path.open(encoding="utf-8-sig") as original, shard.open("xb") as compressed:
            with gzip.GzipFile(filename="", fileobj=compressed, mode="wb", mtime=0) as destination:
                for line_number, line in enumerate(original, 1):
                    if not line.strip():
                        continue
                    rec = json.loads(line)
                    if digest(rec["text"].encode("utf-8")) != rec["text_sha256"]:
                        raise ValueError(f"Text hash mismatch: {path}:{line_number}")
                    ordinal = rec[field]
                    locator = rec.get("locator") or f"IWA::body-paragraph[{ordinal}]::UTF16[{rec.get('utf16_range', [])}]"
                    identity = digest(canonical([source["sha256"], source["source_path"], locator]))
                    if identity in ids:
                        raise ValueError(f"Duplicate occurrence identity: {source['document_id']} {locator}")
                    ids.add(identity)
                    global_index += 1
                    count += 1
                    slot = min(100, (global_index - 1) * 100 // total + 1)
                    reviewer = (slot + 49) % 100 + 1
                    row = {
                        "occurrence_id": identity,
                        "source_path": source["source_path"],
                        "source_sha256": source["sha256"],
                        "document_id": source["document_id"],
                        "locator": locator, "ordinal": ordinal,
                        "text_sha256": rec["text_sha256"],
                        "extraction_path": path.relative_to(root).as_posix(),
                        "extraction_sha256": expected,
                        "extraction_record_line": line_number,
                        "extraction_record_sha256": digest(canonical(rec)),
                        "primary_reader_slot": f"{slot:03}",
                        "independent_reviewer_slot": f"{reviewer:03}",
                        "actual_reader_agent_id": None,
                        "actual_reviewer_agent_id": None,
                        "direct_read_status": "UNREAD", "direct_review_events": [],
                        "omml_children": rec.get("omml_count", 0),
                        "attached_table_ids": rec.get("tables", []),
                        "utf16_range": rec.get("utf16_range"),
                    }
                    destination.write(canonical(row) + b"\n")
                    entry = ranges.setdefault(slot, {"first_ordinal": ordinal, "last_ordinal": ordinal, "count": 0})
                    entry["last_ordinal"] = ordinal
                    entry["count"] += 1
        for slot, span in ranges.items():
            assignments[f"{slot:03}"].append({"document_id": source["document_id"], "shard": shard.name, **span})
        shards.append({"path": shard.name, "sha256": digest(shard.read_bytes()), "bytes": shard.stat().st_size, "occurrences": count})
    if global_index != total:
        raise ValueError(f"Census mismatch: {global_index} != {total}")
    for path, expected in originals + [(p, h) for _, p, h, _ in inputs]:
        if digest(path.read_bytes()) != expected:
            raise ValueError(f"Input changed during seeding: {path}")
    if audit_path.read_bytes() != audit_raw:
        raise ValueError("Audit changed during seeding")
    report = {
        "schema": "oma.research.occurrence-seed/1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "source_audit_sha256": digest(audit_raw),
        "seed_script_sha256": digest(Path(__file__).read_bytes()),
        "primary_occurrences": total,
        "direct_read_occurrences": 0,
        "independently_reviewed_occurrences": 0,
        "complete_corpus_ledger": False,
        "final_zero_omission_denominator": None,
        "pending_child_obligations": audit["occurrence_ledger_design"]["additional_units_to_materialize"],
        "shards": shards,
        "planned_primary_assignments": dict(assignments),
        "reviewer_rule": "The assigned slot 50 positions later reviews each range; actual agents are unstarted.",
        "notice": "Primary-location seed only. Extraction, assignment, and past summaries add no reading credit. All occurrences UNREAD. No workers launched.",
    }
    with (output / "status.json").open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(Path(__file__).resolve().parents[1], args.audit, args.output)
    print(json.dumps({"primary_occurrences": result["primary_occurrences"], "direct_read_occurrences": 0,
                      "independently_reviewed_occurrences": 0, "shards": len(result["shards"]),
                      "complete_corpus_ledger": False}))


if __name__ == "__main__":
    main()
