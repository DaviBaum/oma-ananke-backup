"""Audit complete native front/back tables and expose all nonduplicated prose.

Structural correspondence is distinct from semantic review. This tool never
marks source review complete; its prose report must be read, and body template
referents must be independently reviewed with their parameter contexts.
"""
from pathlib import Path
import json
import xml.etree.ElementTree as ET
from collections import Counter
import argparse
from datetime import datetime, timezone
from corpus_audit import NS, paragraph_text, digest, save_json

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence/math"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--acknowledge", action="store_true")
    parser.add_argument("--notes")
    args = parser.parse_args()
    if args.acknowledge:
        if not args.notes:
            raise ValueError("Substantive review notes required")
        directory = OUT / "index-review"
        save_json(directory / "read_review.json", {
            "status":"NOVEL_PROSE_AND_EXACT_TABLE_CORRESPONDENCE_REVIEWED",
            "reviewer":"math-audit-agent", "utc":datetime.now(timezone.utc).isoformat(),
            "audit_sha256":digest((directory / "audit.json").read_bytes()),
            "novel_sha256":digest((directory / "novel.txt").read_bytes()), "notes":args.notes,
            "notice":"Row equality is an exhaustive structural check, not independent validation of source assertions. Template body referents require their own completed reading. No full-corpus or engineering release claim."})
        print("Index review acknowledged with immutable report hashes")
        return
    manifest = json.loads(next((ROOT / "math1/math1").glob("*Manifest*.json")).read_text(encoding="utf8"))
    records = [json.loads(line) for line in (OUT / "extracted/ananke-canonical.jsonl").read_text(encoding="utf8").splitlines()]
    native = (OUT / "native/ananke-canonical/document.xml").read_bytes()
    root = ET.fromstring(native)
    para = root.findall(".//w:p", NS)
    ids = {id(p): i + 1 for i, p in enumerate(para)}
    objects, equations, prompts = manifest["mathematical_objects"], manifest["equations"], manifest["prompts"]
    def expected(header):
        if header == ["Prompt","Prefix","Title","Package","Provenance"]:
            return [[p[k] for k in ("n","prefix","title","package","provenance")] for p in prompts]
        if header == ["Identifier","Prompt","Type","Status","Provenance"]:
            return [[p[k] for k in ("id","prompt","typ","status","provenance")] for p in objects]
        if header == ["Equation","Prompt","Title","Provenance","Repair"]:
            return [[p[k] for k in ("id","prompt","title","provenance","repair")] for p in equations]
        if header == ["Prompt","Title","Provenance","Words","Equations","Objects","Anchors","Canonical hash"]:
            return [[p["n"],p["title"],p["provenance"],p["words"],p["equations"],sum(o["prompt"]==p["n"] for o in objects),p["anchors"],p["hash"]] for p in prompts]
        if header == ["Identifier","Prompt","Type","Title","Status","Provenance","Dependencies / Supersession"]:
            return [[p[k] for k in ("id","prompt","typ","title","status","provenance")]+["deps="+",".join(p["deps"])+"; supersedes="+",".join(p["supersedes"])+"; superseded_by="+",".join(p["superseded_by"])] for p in objects]
        if header == ["Equation","Prompt","Title","Provenance","Repair status","SHA-256"]:
            return [[p[k] for k in ("id","prompt","title","provenance","repair","hash")] for p in equations]
        if header == ["Anchor","Prompt","Archive","Index","Type","Title","Status","SHA-256"]:
            return [[p[k] for k in ("id","prompt","archive","index","typ","title","status","hash")] for p in manifest["embedded_objects"]]
        if header == ["Historical result","Prompt","Historical status","Active replacement"]:
            return [[p["id"],p["prompt"],p["status"],", ".join(p["superseded_by"])] for p in objects if p["superseded_by"]]
        if header == ["Active result","Prompt","Supersedes"]:
            return [[p["id"],p["prompt"],", ".join(p["supersedes"])] for p in objects if p["status"] == "ACTIVE — REPAIRED"]
        return None
    tables, checked_paragraphs = [], set()
    for table in root.findall(".//w:tbl", NS):
        ps = table.findall(".//w:p", NS)
        start = ids[id(ps[0])]
        if 15507 <= start <= 40638:
            continue
        rows = [["\n".join(paragraph_text(p) for p in cell.findall(".//w:p",NS)) for cell in row.findall("w:tc",NS)] for row in table.findall("w:tr",NS)]
        want = expected(rows[0])
        differences = None
        if want is not None:
            actual = Counter(tuple(r) for r in rows[1:])
            desired = Counter(tuple(str(c) for c in r) for r in want)
            differences = {"unexpected":list((actual-desired).elements()),"missing":list((desired-actual).elements())}
            if not differences["unexpected"] and not differences["missing"]:
                checked_paragraphs.update(ids[id(p)] for p in ps)
        tables.append({"paragraphs":[start,ids[id(ps[-1])]],"header":rows[0],"rows":len(rows)-1,
            "status":"EXACT_ROW_MULTISET_MATCH_TO_MANIFEST" if differences == {"unexpected":[],"missing":[]} else "REQUIRES_REVIEW",
            "differences":differences,"native_table_sha256":digest(ET.tostring(table))})
    seen = {r["text"]:r["location"] for r in reversed(records[15506:40638])}
    mapped, novel = [], []
    for r in records:
        if 15507 <= r["location"] <= 40638:
            continue
        row = {"paragraph":r["location"],"text_sha256":r["text_sha256"]}
        if r["location"] in checked_paragraphs:
            row["disposition"] = "FULL_TABLE_ROW_MATCH_TO_MANIFEST"
        elif r["text"] in seen:
            row.update(disposition="EXACT_TEXT_MATCH_REQUIRES_REVIEWED_REFERENT",referent=seen[r["text"]])
        else:
            row["disposition"] = "NOVEL_TEXT_REQUIRES_READING"
            novel.append(r)
            seen[r["text"]] = r["location"]
        mapped.append(row)
    dest = OUT / "index-review"
    dest.mkdir(exist_ok=True)
    report = "\n".join("["+str(r["location"])+"] "+r["text"] for r in novel)
    report += "\nPreamble equations (manifest source):\n"+"\n".join(e["id"]+": "+e["latex"] for e in equations if e["prompt"] == 0)+"\n"
    (dest / "novel.txt").write_text(report,encoding="utf8")
    save_json(dest / "audit.json",{"source_native_sha256":digest(native),"whole_source_semantic_review":False,
        "tables":tables,"paragraphs":mapped,"novel_paragraph_count":len(novel),"novel_report_sha256":digest(report.encode())})
    print(json.dumps({"tables":tables,"novel_paragraphs":len(novel),"novel_characters":len(report)},ensure_ascii=False))


if __name__ == "__main__":
    main()
