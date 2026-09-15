"""Expose complete integration table rows, preserving their column context."""
from pathlib import Path
import argparse
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from corpus_audit import NS, paragraph_text, digest, save_json

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "evidence/math/integration-table-review"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read",type=int)
    parser.add_argument("--acknowledge",type=int)
    parser.add_argument("--notes")
    args = parser.parse_args()
    if args.read is not None:
        print((DEST / f"chunk-{args.read:03d}.txt").read_text(encoding="utf8"))
        return
    if args.acknowledge is not None:
        if not args.notes:
            raise ValueError("Substantive notes required")
        rec = {"chunk":args.acknowledge,"map_sha256":digest((DEST / "map.json").read_bytes()),
            "report_sha256":digest((DEST / f"chunk-{args.acknowledge:03d}.txt").read_bytes()),
            "status":"FULL_TABLE_ROW_CONTEXT_READ","notes":args.notes,
            "reviewer":"math-audit-agent","utc":datetime.now(timezone.utc).isoformat()}
        with (DEST / "review_ledger.jsonl").open("a",encoding="utf8") as stream:
            stream.write(json.dumps(rec,ensure_ascii=False)+"\n")
        print(json.dumps(rec,ensure_ascii=False))
        return
    if (DEST / "review_ledger.jsonl").exists():
        raise ValueError("Existing table campaign must not be overwritten")
    native = (ROOT / "evidence/math/native/oma-integration/document.xml").read_bytes()
    root = ET.fromstring(native)
    numbers = {id(p):i+1 for i,p in enumerate(root.findall(".//w:p",NS))}
    chunks, current, mapping, seen = [], [], [], {}
    size = 0
    for table in root.findall(".//w:tbl",NS):
        ps = [numbers[id(p)] for p in table.findall(".//w:p",NS)]
        rows = [["\n".join(paragraph_text(p) for p in c.findall(".//w:p",NS)) for c in r.findall("w:tc",NS)] for r in table.findall("w:tr",NS)]
        table_hash = digest(json.dumps(rows,ensure_ascii=False).encode())
        entry = {"paragraphs":ps,"full_rows_sha256":table_hash}
        if table_hash in seen:
            entry.update(method="EXACT_FULL_TABLE_MATCH",referent=seen[table_hash])
        else:
            entry.update(method="FULL_TABLE_ROWS_REQUIRE_READING",chunks=[])
            seen[table_hash] = ps[0]
            for i,row in enumerate(rows):
                output = f"[table native{ps[0]} row{i}] "+json.dumps({"cells":row} if i else {"columns":row},ensure_ascii=False)+"\n"
                if current and size + len(output) > 23500:
                    chunks.append(current)
                    current, size = [], 0
                    header = f"[table native{ps[0]} continued columns] "+json.dumps(rows[0],ensure_ascii=False)+"\n"
                    current.append(header)
                    size += len(header)
                current.append(output)
                size += len(output)
                entry["chunks"].append(len(chunks)+1)
            entry["chunks"] = sorted(set(entry["chunks"]))
        mapping.append(entry)
    if current:
        chunks.append(current)
    DEST.mkdir(exist_ok=True)
    for i,chunk in enumerate(chunks,1):
        (DEST / f"chunk-{i:03d}.txt").write_text("".join(chunk),encoding="utf8")
    save_json(DEST / "map.json",{"source_native_sha256":digest(native),"tables":mapping,"chunks":len(chunks),
        "notice":"Every table row retains full column association; matching tables require complete reviewed referents."})
    print(json.dumps({"tables":len(mapping),"unique_tables":len(seen),"chunks":len(chunks)}))


if __name__ == "__main__":
    main()
