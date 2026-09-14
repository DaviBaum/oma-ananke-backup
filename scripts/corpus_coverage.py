"""Reconcile review attestations without equating text coverage with proof.

Direct native ranges, explicit template substitutions, and exhaustive index-row
correspondence are reported separately. All attestations are content-hash bound.
This does not assert that an extracted source has been independently verified.
"""
from pathlib import Path
from collections import Counter
import json
import re
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from corpus_audit import NS, paragraph_text, digest, records_for, save_json

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence/math"


def read(path):
    return json.loads(path.read_text(encoding="utf8"))


def lines(path):
    return [json.loads(line) for line in path.read_text(encoding="utf8").splitlines()]


def ranges(values):
    result = []
    for value in sorted(values):
        if result and result[-1][1] == value - 1:
            result[-1][1] = value
        else:
            result.append([value, value])
    return result


def integration_coverage(source, records, direct):
    """Verify text referents and every actual native table row independently."""
    path = OUT / "integration-review/map.json"
    mapping = read(path)
    if mapping["source_sha256"] != source["sha256"]:
        raise ValueError("Integration source mapping stale")
    map_hash = digest(path.read_bytes())
    ack = {a["chunk"]: a for a in lines(path.parent / "review_ledger.jsonl")
           if a["map_sha256"] == map_hash and a["status"] == "COMPLETE_UNTRUNCATED_TEXT_READ"}
    valid_chunks = set()
    for chunk in mapping["chunks"]:
        n = chunk["chunk"]
        report = (path.parent / f"chunk-{n:03d}.txt").read_bytes()
        expected = "\n".join(f"[{i}] {records[i - 1]['text']}" for i in chunk["paragraphs"]) + "\n"
        # write_text uses native CRLF on Windows; source payload is unchanged.
        if report.decode("utf8").replace("\r\n", "\n") != expected or digest(expected.encode("utf8")) != chunk["sha256"]:
            raise ValueError(f"Integration read report not native text: {n}")
        if n in ack and ack[n]["report_sha256"] == digest(report):
            valid_chunks.add(n)
    modes = {n: "DIRECT_NATIVE_RANGE_READ" for n in direct}
    if [r["paragraph"] for r in mapping["paragraphs"]] != list(range(1, len(records) + 1)):
        raise ValueError("Integration map incomplete")
    for row in mapping["paragraphs"]:
        n = row["paragraph"]
        if row["source_text_sha256"] != records[n - 1]["text_sha256"]:
            raise ValueError(f"Integration paragraph changed: {n}")
        if row["method"] == "NOVEL_REQUIRES_READING" and row["chunk"] in valid_chunks:
            modes[n] = "NOVEL_EXACT_TEXT_CONTENT_READ"
        elif row["method"] == "EXACT_TEXT_MATCH_REQUIRES_REVIEWED_REFERENT":
            ref = row["referent"]
            if records[n - 1]["text"] != records[ref - 1]["text"]:
                raise ValueError("Integration exact-text referent differs")
            if ref in modes:
                modes[n] = "EXACT_TEXT_MATCH_TO_REVIEWED_REFERENT"

    table_path = OUT / "integration-table-review/map.json"
    tables = read(table_path)
    with ZipFile(source["path"]) as document:
        native = document.read("word/document.xml")
    if digest(native) != tables["source_native_sha256"]:
        raise ValueError("Integration table source changed")
    root = ET.fromstring(native)
    numbers = {id(p): i + 1 for i, p in enumerate(root.findall(".//w:p", NS))}
    actual = {}
    for table in root.findall(".//w:tbl", NS):
        ps = [numbers[id(p)] for p in table.findall(".//w:p", NS)]
        rows = [["\n".join(paragraph_text(p) for p in cell.findall(".//w:p", NS))
                 for cell in row.findall("w:tc", NS)] for row in table.findall("w:tr", NS)]
        actual[ps[0]] = (ps, rows)
    table_hash = digest(table_path.read_bytes())
    table_acks = {a["chunk"]: a for a in lines(table_path.parent / "review_ledger.jsonl")
                  if a["map_sha256"] == table_hash and a["status"] == "FULL_TABLE_ROW_CONTEXT_READ"}
    seen_rows = set()
    for n in range(1, tables["chunks"] + 1):
        report = (table_path.parent / f"chunk-{n:03d}.txt").read_bytes()
        if n not in table_acks or table_acks[n]["report_sha256"] != digest(report):
            continue
        for line in report.decode("utf8").splitlines():
            match = re.fullmatch(r"\[table native(\d+) row(\d+)\] (.*)", line)
            if not match:
                match = re.fullmatch(r"\[table native(\d+) continued columns\] (.*)", line)
                if not match or json.loads(match[2]) != actual[int(match[1])][1][0]:
                    raise ValueError("Invalid continued table header")
                continue
            first, row_index = int(match[1]), int(match[2])
            payload = json.loads(match[3])
            expected_key = "columns" if row_index == 0 else "cells"
            if payload != {expected_key: actual[first][1][row_index]}:
                raise ValueError("Table row content differs from original native source")
            if (first, row_index) in seen_rows:
                raise ValueError("Duplicate read table row")
            seen_rows.add((first, row_index))
    complete_tables = set()
    if [row["paragraphs"][0] for row in tables["tables"]] != list(actual):
        raise ValueError("Table map omits native tables")
    for table in tables["tables"]:
        first = table["paragraphs"][0]
        ps, rows = actual[first]
        if table["paragraphs"] != ps or table["full_rows_sha256"] != digest(json.dumps(rows, ensure_ascii=False).encode()):
            raise ValueError("Table mapping differs from native source")
        if table["method"] == "EXACT_FULL_TABLE_MATCH":
            ref = table["referent"]
            complete = ref in complete_tables and rows == actual[ref][1]
        else:
            complete = all((first, i) in seen_rows for i in range(len(rows)))
        if complete:
            complete_tables.add(first)
        else:
            for n in ps:
                modes.pop(n, None)
    return modes, {"text_chunks_reviewed": len(valid_chunks), "text_chunks_total": len(mapping["chunks"]),
                   "tables_with_full_row_context": len(complete_tables), "native_tables": len(actual),
                   "direct_unique_table_rows_read": len(seen_rows)}


def main():
    inventory = read(OUT / "source_inventory.json")["sources"]
    historical = read(OUT / "pages/review/coverage.json")
    historical_sources = {row["source"]: row for row in historical["sources"]}
    metadata_review = read(OUT / "manifest_metadata_review.json")
    ledger = lines(OUT / "review_ledger.jsonl")
    canonical = records_for(OUT, "ananke-canonical")
    source = next(s for s in inventory if s["document_id"] == "ananke-canonical")
    if digest(Path(source["path"]).read_bytes()) != source["sha256"]:
        raise ValueError("Canonical original changed")
    mapped = read(OUT / "template-review/map.json")
    map_hash = digest((OUT / "template-review/map.json").read_bytes())
    acknowledged = {}
    for attestation in lines(OUT / "template-review/review_ledger.jsonl"):
        p = attestation["prompt"]
        report = OUT / "template-review" / f"P{p:02d}-novel.txt"
        if attestation["map_sha256"] == map_hash and attestation["read_report_sha256"] == digest(report.read_bytes()):
            acknowledged[p] = attestation
    coverage = {}
    for row in mapped["paragraphs"]:
        n = row["paragraph"]
        if row.get("source_sha256", row.get("sha256")) != canonical[n - 1]["text_sha256"]:
            raise ValueError(f"Template source paragraph changed: {n}")
        p = row.get("prompt")
        if p is None:
            if n - 1 in coverage:
                coverage[n] = "EQUATION_MANIFEST_AND_NATIVE_STRUCTURE"
            continue
        attestation = acknowledged.get(p)
        if not attestation or any(ref not in acknowledged for ref in attestation["referent_prompts"]):
            continue
        first = row["first_equivalent_paragraph"]
        if first is not None and first not in coverage:
            continue
        coverage[n] = "NOVEL_TEMPLATE_CONTENT_READ" if first is None else "EXPLICIT_PARAMETER_SUBSTITUTION_CONTEXT_REVIEWED"
    index_path = OUT / "index-review/audit.json"
    index = read(index_path)
    index_ack = read(OUT / "index-review/read_review.json")
    index_valid = index_ack["audit_sha256"] == digest(index_path.read_bytes()) and index_ack["novel_sha256"] == digest((OUT / "index-review/novel.txt").read_bytes())
    index_valid &= index["source_native_sha256"] == digest((OUT / "native/ananke-canonical/document.xml").read_bytes())
    if index_valid:
        for row in index["paragraphs"]:
            n = row["paragraph"]
            if row["text_sha256"] != canonical[n - 1]["text_sha256"]:
                raise ValueError(f"Index source paragraph changed: {n}")
            disposition = row["disposition"]
            if disposition == "FULL_TABLE_ROW_MATCH_TO_MANIFEST":
                coverage[n] = "EXHAUSTIVE_INDEX_ROW_CORRESPONDENCE_REVIEWED"
            elif disposition == "NOVEL_TEXT_REQUIRES_READING":
                coverage[n] = "NOVEL_INDEX_PROSE_READ"
            elif row["referent"] in coverage:
                coverage[n] = "EXACT_TEXT_MATCH_TO_REVIEWED_REFERENT"
    documents = []
    integration_report = None
    for source in inventory:
        doc = source["document_id"]
        direct = set()
        source_current = digest(Path(source["path"]).read_bytes()) == source["sha256"]
        if doc in historical_sources:
            row = historical_sources[doc]
            if row["source_sha256"] != source["sha256"]:
                raise ValueError("Historical coverage source changed")
            documents.append({"document_id": doc, "source_sha256": source["sha256"], "source_current": source_current,
                "extracted_locations": row["paragraphs"], "direct_native_read": row["novel_paragraphs_read"],
                "content_covered": row["paragraphs"] - row["paragraphs_remaining"],
                "coverage_modes": {"NATIVE_TEXT_AND_ATTACHED_TABLE_ROWS_READ": row["novel_paragraphs_read"],
                    "EXACT_CONTENT_MATCH_TO_REVIEWED_REFERENT": row["exact_duplicate_paragraphs_with_reviewed_referent"]},
                "remaining_native_ranges": "See hash-bound historical paragraph map" if row["paragraphs_remaining"] else [],
                "content_review_complete": row["content_reading_complete"] and source_current,
                "independent_mathematical_verification_complete": False})
            continue
        if doc == "ananke-manifest":
            current = source_current and metadata_review["source_sha256"] == source["sha256"]
            documents.append({"document_id": doc, "source_sha256": source["sha256"], "source_current": source_current,
                "extracted_locations": source["extracted_records"], "direct_native_read": 0,
                "content_covered": source["extracted_records"] if current else 0,
                "coverage_modes": metadata_review["coverage_modes"], "remaining_native_ranges": [] if current else [[1, source["extracted_records"]]],
                "content_review_complete": current and metadata_review["all_manifest_records_equal_extracted_namespace"],
                "independent_mathematical_verification_complete": False})
            continue
        total = source.get("extracted_records")
        records = records_for(OUT, doc) if total else []
        if source_current:
            for entry in ledger:
                if entry["document_id"] != doc or entry["source_sha256"] != source["sha256"] or entry["status"] == "AMBIGUOUS":
                    continue
                subset = records[entry["start"] - 1:entry["end"]]
                actual = digest(json.dumps(subset, ensure_ascii=False, sort_keys=True).encode("utf8"))
                if actual != entry["range_sha256"]:
                    raise ValueError(f"Stale native range: {doc}:{entry['start']}-{entry['end']}")
                direct.update(range(entry["start"], entry["end"] + 1))
        modes = dict(coverage) if doc == "ananke-canonical" else {}
        modes.update({n:"DIRECT_NATIVE_RANGE_READ" for n in direct})
        if doc == "oma-integration" and source_current:
            modes, integration_report = integration_coverage(source, records, direct)
        remaining = set(range(1, (total or 0) + 1)) - modes.keys()
        documents.append({"document_id":doc,"source_sha256":source["sha256"],"source_current":source_current,
            "extracted_locations":total,"direct_native_read":len(direct),"content_covered":len(modes),
            "coverage_modes":dict(Counter(modes.values())),"remaining_native_ranges":ranges(remaining),
            "content_review_complete":bool(total and not remaining and source_current),
            "independent_mathematical_verification_complete":False})
    substantive = [d for d in documents if d["document_id"] not in ("ds-store", "ananke-canonical-pdf")]
    save_json(OUT / "combined_review_coverage.json",{
        "schema":"oma.corpus.combined-review-coverage/1", "documents":documents,
        "canonical_parameter_prompts_acknowledged":sorted(acknowledged),
        "canonical_index_attestation_current":index_valid,
        "integration_review":integration_report,
        "all_supplied_mathematical_content_covered_by_declared_review_methods": all(d["content_review_complete"] for d in substantive),
        "whole_corpus_fully_read": all(d["content_review_complete"] for d in substantive),
        "whole_corpus_verified":False,
        "nonbody_sources": {"ds-store": "Filesystem metadata hash-inventoried; no mathematical text",
            "ananke-canonical-pdf": "Companion rendering used for ambiguous source equations and layout; no claim every PDF page was visually inspected"},
        "source_content_gaps": read(OUT / "pages/source-gaps.json"),
        "notice":"Content coverage includes declared exact substitutions and exhaustive index correspondence, each with reviewed referents. Full content review does not mean every repeated paragraph was independently read, every PDF page visually inspected, proofs verified, absent source bodies recovered, or all obligations implemented."})
    print(json.dumps([{k:d[k] for k in ("document_id","extracted_locations","direct_native_read","content_covered","content_review_complete")} for d in documents],indent=2))


if __name__ == "__main__":
    main()
