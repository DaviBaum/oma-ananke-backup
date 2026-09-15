"""Read-only source inventory, native extraction, and hash-bound review ledger.

This tool never equates extraction or registry validation with mathematical review.
Source locators are XML paragraph numbers (including table cells), not PDF pages.
OMML source trees are retained alongside searchable text because concatenated math
tokens alone lose fraction, radical, matrix, and superscript structure.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "math1" / "math1"
DEFAULT_OUT = ROOT / "evidence" / "math"
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
      "m": "http://schemas.openxmlformats.org/officeDocument/2006/math"}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def save_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def identity(path: Path) -> str:
    if "Repaired_Canonical_Complete" in path.name:
        return "ananke-canonical" + ("-pdf" if path.suffix == ".pdf" else "")
    if "5 things" in path.name:
        return "oma-integration"
    if "CEILING_ROUTER" in path.name:
        return "ceiling-router"
    if "Repair_and_Zero" in path.name:
        return "ananke-repair-audit"
    if "Manifest" in path.name:
        return "ananke-manifest"
    if "Inventory" in path.name:
        return "ananke-inventory"
    return re.sub(r"[^a-z0-9]+", "-", path.stem.lower()).strip("-")


def paragraph_text(p) -> str:
    output = []
    for el in p.iter():
        local = el.tag.rsplit("}", 1)[-1]
        if el.tag in ("{" + NS["w"] + "}t", "{" + NS["m"] + "}t"):
            output.append(el.text or "")
        elif local == "tab":
            output.append("\t")
        elif local in ("br", "cr"):
            output.append("\n")
    return "".join(output)


def extract_docx(path: Path, out: Path, doc: str):
    records, sections, issues = [], [], []
    with zipfile.ZipFile(path) as z:
        bad = z.testzip()
        if bad:
            raise ValueError(f"Corrupt ZIP member: {bad}")
        total = sum(x.file_size for x in z.infolist())
        if total > 256 * 1024 * 1024:
            raise ValueError("Document exceeds 256 MiB expanded-size limit")
        raw = z.read("word/document.xml")
        target = out / "native" / doc
        target.mkdir(parents=True, exist_ok=True)
        (target / "document.xml").write_bytes(raw)
        root = ET.fromstring(raw)
        equations = []
        for number, paragraph in enumerate(root.findall(".//w:p", NS), 1):
            text = paragraph_text(paragraph)
            style_el = paragraph.find("w:pPr/w:pStyle", NS)
            style = style_el.get("{" + NS["w"] + "}val", "") if style_el is not None else ""
            math = paragraph.findall(".//m:oMath", NS)
            if math:
                for mi, equation in enumerate(math, 1):
                    equations.append({"paragraph": number, "index": mi,
                                      "xml": ET.tostring(equation, encoding="unicode"),
                                      "tokens": paragraph_text(equation)})
            rec = {"location": number, "locator": f"word/document.xml::p[{number}]",
                   "text": text, "style": style, "omml_count": len(math),
                   "text_sha256": digest(text.encode("utf-8"))}
            records.append(rec)
            if style.lower().startswith(("heading", "title")) or re.match(r"^(PART [IVX]+|PROMPT \d+ OF|\d+(?:\.\d+)*\. [A-Z])", text):
                sections.append({"location": number, "title": text, "style": style})
            if "\ufffd" in text:
                issues.append({"location": number, "problem": "SOURCE_UNICODE_REPLACEMENT_CHARACTER",
                               "count": text.count("\ufffd"), "status": "UNRESOLVED"})
        save_json(target / "equations.json", equations)
        ancillary = []
        for name in z.namelist():
            if name.startswith("word/") and name.endswith(".xml") and any(x in name for x in ("footnote", "endnote", "header", "footer", "comment")):
                content = z.read(name)
                safe_name = name.replace("/", "_")
                (target / safe_name).write_bytes(content)
                ancillary.append({"part": name, "text": "\n".join(paragraph_text(p) for p in ET.fromstring(content).findall(".//w:p", NS))})
        save_json(target / "ancillary.json", ancillary)
        assets = [{"part": n, "sha256": digest(z.read(n)), "size_bytes": z.getinfo(n).file_size}
                  for n in z.namelist() if n.startswith(("word/media/", "word/embeddings/"))]
        save_json(target / "assets.json", assets)
        for asset in assets:
            asset_target = target / "assets" / Path(asset["part"]).name
            asset_target.parent.mkdir(exist_ok=True)
            asset_target.write_bytes(z.read(asset["part"]))
    return records, sections, issues, {"paragraphs": len(records), "omml_nodes": len(equations),
            "tables": len(root.findall(".//w:tbl", NS)), "assets": len(assets),
            "ancillary_parts": len(ancillary), "native_document_xml_sha256": digest(raw)}


def inventory(source: Path, out: Path):
    source = source.resolve()
    out = out.resolve()
    if out == source or source in out.parents:
        raise ValueError("Outputs must be outside read-only originals")
    out.mkdir(parents=True, exist_ok=True)
    sources = []
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        doc = identity(path)
        ext = path.suffix.lower()
        rec = {"path": str(path), "relative_path": path.relative_to(source).as_posix(),
               "document_id": doc, "sha256": digest(path.read_bytes()), "size_bytes": path.stat().st_size,
               "version": "UNRESOLVED", "canonical_status": "UNCLASSIFIED",
               "scope_classification": "PENDING_REVIEW", "relevance": "PENDING_REVIEW",
               "extraction_status": "NOT_EXTRACTED", "review_status": "NOT_REVIEWED"}
        records = []
        if ext == ".docx":
            records, sections, issues, counts = extract_docx(path, out, doc)
            rec.update(extraction_method="OOXML native paragraphs, table cells, OMML XML, ancillary XML and assets",
                       extraction_status="NATIVE_EXTRACTED_VISUAL_REVIEW_PENDING", counts=counts,
                       unresolved_extraction_issues=len(issues))
            save_json(out / "indexes" / f"{doc}.sections.json", sections)
            save_json(out / "indexes" / f"{doc}.issues.json", issues)
        elif ext in (".md", ".json", ".csv"):
            text = path.read_text(encoding="utf-8-sig")
            records = [{"location": i, "locator": f"line[{i}]", "text": line,
                        "text_sha256": digest(line.encode("utf-8"))} for i, line in enumerate(text.splitlines(), 1)]
            rec.update(extraction_method="UTF-8 native text; equations retain source delimiters", extraction_status="NATIVE_EXTRACTED")
            if ext == ".md":
                save_json(out / "indexes" / f"{doc}.sections.json", [{"location": r["location"], "title": r["text"]} for r in records if r["text"].startswith("#")])
        elif ext == ".pages":
            with zipfile.ZipFile(path) as archive:
                members = [{"part": i.filename, "size_bytes": i.file_size, "sha256": digest(archive.read(i.filename))} for i in archive.infolist()]
            save_json(out / "indexes" / f"{doc}.archive.json", members)
            rec.update(extraction_method="ZIP member inventory; IWA content decoding pending", extraction_status="ARCHIVE_INVENTORIED_IWA_UNREAD",
                       canonical_status="HISTORICAL_SOURCE_REQUIRES_RECONCILIATION", scope_classification="HISTORICAL_REFERENCE",
                       relevance="Historical originals now present; canonical manifest described these as unavailable during its reconstruction")
        elif ext == ".pdf":
            rec.update(extraction_method="Hash inventory; native DOCX companion preferred, page inspection pending",
                       extraction_status="RENDER_REFERENCE_PENDING", canonical_status="CANONICAL_RENDER_COMPANION")
        else:
            rec.update(extraction_method="Binary hash inventory", extraction_status="INVENTORIED",
                       scope_classification="EXCLUDED_PRODUCT_SCOPE", relevance="Filesystem metadata")
        if doc.startswith("ananke-canonical"):
            rec.update(version="Prompt-32 repaired canonical 1.0", canonical_status="RECONSTRUCTED_CANONICAL_BODY",
                       scope_classification="REQUIRED_ENGINE_AND_SUPPORT_MATHEMATICS",
                       relevance="Prompt-specific scope mapping required; canonical status is source declaration, not completed mathematical verification")
        elif doc in ("ananke-manifest", "ananke-inventory", "ananke-repair-audit"):
            rec.update(version="Prompt-32 repaired canonical 1.0", canonical_status="CANONICAL_SUPPORT_RECORD",
                       scope_classification="REQUIRED_SUPPORTING_MATHEMATICS", relevance="Provenance, namespaces, repairs and source-closure claims")
        elif doc == "oma-integration":
            rec.update(version="Supplied five-part OMA program; hash authoritative", canonical_status="ACTIVE_EXTENSION",
                       scope_classification="REQUIRED_ENGINE_MATHEMATICS", relevance="Spatial IR, routing, co-design, robust execution, integration")
        elif doc == "ceiling-router":
            rec.update(version="2026-08-18", canonical_status="DOMAIN_TRANSFER_REFERENCE",
                       scope_classification="REQUIRED_ENGINE_MATHEMATICS", relevance="PCB source patterns require explicit building-domain adaptation; source/spec/audit evidence distinguished")
        if records:
            target = out / "extracted" / f"{doc}.jsonl"
            target.parent.mkdir(exist_ok=True)
            with target.open("w", encoding="utf-8") as stream:
                for record in records:
                    stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            rec["extracted_records"] = len(records)
            rec["extracted_sha256"] = digest(target.read_bytes())
            (out / "extracted" / f"{doc}.txt").write_text("\n".join(f"[{r['location']}] {r['text']}" for r in records), encoding="utf-8")
        sources.append(rec)
    save_json(out / "source_inventory.json", {"schema": "oma.corpus.inventory/1", "generated_utc": datetime.now(timezone.utc).isoformat(),
              "source_root": str(source), "originals_read_only": True,
              "notice": "Extraction, source-declared validation, and human/agent mathematical review are different evidence states.", "sources": sources})
    manifest_path = next(source.glob("*Canonical_Manifest*.json"), None)
    if manifest_path:
        m = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        namespace = f"ananke:prompt32-v1:{digest(manifest_path.read_bytes())[:12]}"
        by_id = {o["id"]: o for o in m["mathematical_objects"]}
        objects = []
        unresolved = []
        for o in m["mathematical_objects"]:
            objects.append({**o, "qualified_id": f"{namespace}:P{o['prompt']:02d}:{o['id']}", "review_status": "NOT_REVIEWED",
                            "implementation_status": "NOT_TRACED", "namespace": namespace})
            for dep in o.get("deps", []):
                if dep not in by_id:
                    unresolved.append({"object": o["id"], "dependency": dep})
        hash_checks = []
        for name, expected in m.get("file_hashes", {}).items():
            normalized_name = name.rsplit(".", 1)
            local = next((s for s in sources if s["relative_path"] == name or s["relative_path"] == f"{normalized_name[0]} 3.{normalized_name[1]}"), None)
            hash_checks.append({"declared_file": name, "expected": expected["sha256"], "actual": local["sha256"] if local else None,
                                "status": "PASS" if local and local["sha256"] == expected["sha256"] else "MISSING" if not local else "HASH_MISMATCH"})
        save_json(out / "canonical_namespace.json", {"namespace": namespace, "version": m["document_version"], "objects": objects,
                  "equations": m["equations"], "supersession_graph": m["supersession_graph"], "prompts": m["prompts"]})
        save_json(out / "manifest_audit.json", {"hash_checks": hash_checks, "source_declared_validation": m["validation"],
                  "object_count": len(objects), "unresolved_registry_dependencies": unresolved,
                  "review_status": "AUTOMATED_REGISTRY_AUDIT_ONLY", "historical_availability_change": "Three Pages originals are now present; manifest absence statements describe a prior run."})
    integration_path = out / "extracted" / "oma-integration.jsonl"
    if integration_path.exists():
        paragraphs = [json.loads(line) for line in integration_path.read_text(encoding="utf-8").splitlines()]
        integration_source = next(s for s in sources if s["document_id"] == "oma-integration")
        integration_namespace = "oma:integration:" + integration_source["sha256"][:12]
        objects, current_prompt = [], 1
        for record in paragraphs:
            heading = re.fullmatch(r"PROMPT (\d) OF 5", record["text"])
            if heading:
                current_prompt = int(heading.group(1))
            match = re.match(r"^((?:DEF|THM|LEM|PROP|COR|ALG|ASSUMP|ADD)-[A-Z0-9.\-]+)\s+[—–-]\s+(.+)", record["text"])
            if match:
                objects.append({"qualified_id": f"{integration_namespace}:P{current_prompt}:{match.group(1)}",
                                "id": match.group(1), "title": match.group(2), "prompt": current_prompt,
                                "paragraph": record["location"], "review_status": "CHECK_REVIEW_LEDGER"})
        duplicate_a = [r["text"] for r in paragraphs[3584:8330]]
        duplicate_b = [r["text"] for r in paragraphs[8330:13076]]
        duplicate_equal = duplicate_a == duplicate_b
        save_json(out / "integration_namespace.json", {"namespace": integration_namespace, "objects": objects,
                  "duplicate_prompt_2": {"canonical_range": [3585, 8330], "duplicate_range": [8331, 13076],
                     "paragraph_text_equal": duplicate_equal, "hash": digest(json.dumps(duplicate_a, ensure_ascii=False).encode("utf-8"))},
                  "notice": "Object index is lexical discovery, not proof review or implementation evidence."})
    print(json.dumps({"sources": len(sources), "output": str(out), "status": "EXTRACTED_REVIEW_PENDING"}))


def records_for(out: Path, doc: str):
    return [json.loads(line) for line in (out / "extracted" / f"{doc}.jsonl").read_text(encoding="utf-8").splitlines()]


def read_range(args):
    records = [r for r in records_for(args.out, args.document) if args.start <= r["location"] <= args.end]
    equation_map = {}
    if args.document == "ananke-canonical":
        index = json.loads((args.out / "canonical_namespace.json").read_text(encoding="utf-8"))
        equation_map = {e["id"]: e["latex"] for e in index["equations"]}
    for record in records:
        print(f"[{record['location']}] {record['text']}")
        match = re.search(r"Equation (P\d+-E\d+)", record["text"])
        if match and match.group(1) in equation_map:
            print("  [canonical manifest equation source] " + equation_map[match.group(1)])
    print(f"\nRANGE {args.document}:{args.start}-{args.end}; records={len(records)}; native OMML requires structural inspection when ambiguous.")


def record_review(args):
    records = [r for r in records_for(args.out, args.document) if args.start <= r["location"] <= args.end]
    if not records or len(records) != args.end - args.start + 1:
        raise ValueError("Range missing or out of bounds")
    sources = json.loads((args.out / "source_inventory.json").read_text(encoding="utf-8"))["sources"]
    source = next(s for s in sources if s["document_id"] == args.document)
    if digest(Path(source["path"]).read_bytes()) != source["sha256"]:
        raise ValueError("Source changed; review cannot attach to stale inventory")
    rec = {"document_id": args.document, "source_sha256": source["sha256"], "start": args.start, "end": args.end,
           "range_sha256": digest(json.dumps(records, ensure_ascii=False, sort_keys=True).encode("utf-8")),
           "reviewed_utc": datetime.now(timezone.utc).isoformat(), "reviewer": args.reviewer,
           "status": args.status, "notes": args.notes, "visual_status": args.visual_status}
    with (args.out / "review_ledger.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(json.dumps(rec, ensure_ascii=False))


def review_status(out):
    inventory = json.loads((out / "source_inventory.json").read_text(encoding="utf-8"))
    ledger_path = out / "review_ledger.jsonl"
    reviews = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines()] if ledger_path.exists() else []
    records = []
    for source in inventory["sources"]:
        reviewed, audited, visual = set(), set(), set()
        for entry in reviews:
            if entry["document_id"] == source["document_id"] and entry["source_sha256"] == source["sha256"]:
                locations = set(range(entry["start"], entry["end"] + 1))
                reviewed.update(locations)
                if entry["status"] == "DEPENDENCY_AUDITED":
                    audited.update(locations)
                if entry["visual_status"] == "INSPECTED":
                    visual.update(locations)
        denominator = source.get("extracted_records")
        source["review_status"] = "TEXT_READING_COMPLETE" if denominator and len(reviewed) == denominator else "PARTIALLY_READ" if reviewed else "NOT_REVIEWED"
        records.append({"document_id": source["document_id"], "source_sha256": source["sha256"],
                        "extracted_locations": denominator, "read_locations": len(reviewed),
                        "dependency_audited_locations": len(audited), "visually_reviewed_locations": len(visual),
                        "remaining_text_locations": denominator - len(reviewed) if denominator else None,
                        "status": source["review_status"]})
    save_json(out / "source_inventory.json", inventory)
    summary = {"schema": "oma.corpus.review-status/1", "sources": records,
               "whole_corpus_fully_read": False, "whole_corpus_verified": False,
               "notice": "Review progress counts exact source locations, not implementation or release coverage."}
    save_json(out / "review_status.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    sub = p.add_subparsers(dest="command", required=True)
    inv = sub.add_parser("inventory")
    inv.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    sub.add_parser("status")
    for name in ("read", "review"):
        command = sub.add_parser(name)
        command.add_argument("document")
        command.add_argument("start", type=int)
        command.add_argument("end", type=int)
        if name == "review":
            command.add_argument("--notes", required=True)
            command.add_argument("--reviewer", default="math-audit-agent")
            command.add_argument("--status", choices=("READ_INTERPRETED", "DEPENDENCY_AUDITED", "AMBIGUOUS"), default="READ_INTERPRETED")
            command.add_argument("--visual-status", choices=("NOT_REQUIRED_NATIVE_UNAMBIGUOUS", "PENDING", "INSPECTED"), default="PENDING")
    args = p.parse_args()
    if args.command == "inventory":
        inventory(args.source, args.out)
    elif args.command == "read":
        read_range(args)
    elif args.command == "status":
        review_status(args.out)
    else:
        record_review(args)


if __name__ == "__main__":
    main()
