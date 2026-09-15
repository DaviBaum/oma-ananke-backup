"""Exact-text historical Pages reading aid with native table rows in context.

No source paragraph or attached table is omitted from the correspondence map.
Exact duplicates still require their first occurrence to be read. Native LaTeX
line separators remain literal; no reconstructed canonical namespace is assumed.
"""
from pathlib import Path
from datetime import datetime,timezone
import argparse
import json
from corpus_pages import OUT,sha

DEST=OUT/"review"


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read",type=int)
    parser.add_argument("--acknowledge",type=int)
    parser.add_argument("--notes")
    parser.add_argument("--reviewer",default="math-audit-agent")
    args=parser.parse_args()
    if args.read or args.acknowledge:
        number=args.read or args.acknowledge
        mapping=json.loads((DEST/"map.json").read_text())
        chunk=mapping["chunks"][number-1]
        path=DEST/f"chunk-{number:03d}.txt"
        if args.read:
            print(path.read_text(encoding="utf8"))
            print("EXACT_CHUNK",number,"SHA256",sha(path.read_bytes()))
        else:
            if not args.notes:raise ValueError("Substantive notes required after reading")
            with (DEST/"review-ledger.jsonl").open("a",encoding="utf8") as f:
                f.write(json.dumps({"chunk":number,"source":chunk["source"],"source_sha256":chunk["source_sha256"],
                    "map_sha256":sha((DEST/"map.json").read_bytes()),"chunk_sha256":sha(path.read_bytes()),
                    "reviewer":args.reviewer,"utc":datetime.now(timezone.utc).isoformat(),"notes":args.notes,
                    "status":"NATIVE_TEXT_AND_ATTACHED_TABLE_ROWS_READ","independent_math_verification":False})+"\n")
            print("Acknowledged historical chunk",number)
        return
    if (DEST/"review-ledger.jsonl").exists():raise ValueError("Existing reading campaign must not be overwritten")
    DEST.mkdir(exist_ok=True)
    seen={};mapped=[];chunks=[];pending=[];pending_chars=0;next_number=1
    summaries=[]
    def flush(source,identity):
        nonlocal pending,pending_chars,next_number
        if not pending:return
        report=f"HISTORICAL ORIGINAL {source}; source SHA256 {identity}\nNATIVE PARAGRAPHS AND ATTACHED TABLE ROWS; NO IMPLIED RECONSTRUCTION EQUIVALENCE\n"
        report+="\n".join(p["report"] for p in pending)+"\n"
        path=DEST/f"chunk-{next_number:03d}.txt"
        path.write_text(report,encoding="utf8",newline="\n")
        chunks.append({"number":next_number,"source":source,"source_sha256":identity,
            "paragraphs":[p["paragraph"] for p in pending],"characters":len(report),"sha256":sha(path.read_bytes())})
        for p in pending:mapped[p["map_index"]]["chunk"]=next_number
        pending=[];pending_chars=0;next_number+=1
    for directory in sorted(OUT.iterdir()):
        if not (directory/"content-audit.json").exists():continue
        audit=json.loads((directory/"content-audit.json").read_text())
        if audit["issues"]:raise ValueError("Unresolved historical extraction issues")
        source,identity=directory.name,audit["source_sha256"]
        tables={r["drawable_id"]:r for r in map(json.loads,(directory/"tables.jsonl").read_text().splitlines())}
        records=list(map(json.loads,(directory/"body-records.jsonl").read_text().splitlines()))
        first_chunk=next_number
        for r in records:
            table_rows=[tables[t]["rows"] for t in r["tables"]]
            key=sha(json.dumps([r["text"],table_rows],ensure_ascii=False).encode())
            row={"source":source,"source_sha256":identity,"paragraph":r["paragraph"],"text_sha256":r["text_sha256"],
                "utf16_range":r["utf16_range"],"table_ids":r["tables"],"combined_content_sha256":key}
            if key in seen:
                row.update(method="EXACT_CONTENT_MATCH_REQUIRES_REVIEWED_REFERENT",referent=seen[key])
            else:
                seen[key]={"source":source,"paragraph":r["paragraph"]}
                row["method"]="NOVEL_NATIVE_CONTENT_REQUIRES_READING"
                report=f"[{source}:P{r['paragraph']}; UTF16 {r['utf16_range'][0]}] {r['text']}"
                for t in r["tables"]:
                    report+=f"\nATTACHED TABLE {t}; native row/column order; {len(tables[t]['rows'])} rows\n"
                    report+="\n".join(f"ROW {i}: "+json.dumps(cells,ensure_ascii=False) for i,cells in enumerate(tables[t]["rows"]))
                if pending_chars+len(report)>24500:flush(source,identity)
                pending.append({"paragraph":r["paragraph"],"report":report,"map_index":len(mapped)})
                pending_chars+=len(report)+1
            mapped.append(row)
        flush(source,identity)
        summaries.append({"source":source,"paragraphs":len(records),"first_chunk":first_chunk,"last_chunk":next_number-1,
            "source_sha256":identity,"native_tables":len(tables),"source_content_issues":audit["source_content_issues"]})
    mapping={"schema":"oma.pages.reading-map/1","sources":summaries,"paragraphs":mapped,"chunks":chunks,
        "source_reading_complete":False,"notice":"Exact duplicate references are reading aids, never evidence that remaining original mathematics was read or implemented."}
    (DEST/"map.json").write_text(json.dumps(mapping,ensure_ascii=False,indent=2)+"\n",encoding="utf8",newline="\n")
    print(json.dumps({"sources":summaries,"chunks":len(chunks),"novel_characters":sum(c["characters"] for c in chunks)},indent=2))


if __name__=="__main__":main()
