"""Bounded reading aid for every unread unique integration paragraph.

Only exact text equality is used. Direct-read paragraphs retain their native
attestations, and every duplicate records the exact reviewed referent. Chunk
acknowledgements require actual reading and substantive semantic notes.
"""
from pathlib import Path
import argparse
import json
from datetime import datetime, timezone
from corpus_audit import digest, records_for, save_json

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence/math"
DEST = OUT / "integration-review"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read", type=int)
    parser.add_argument("--acknowledge", type=int)
    parser.add_argument("--notes")
    args = parser.parse_args()
    if args.read is not None:
        print((DEST / f"chunk-{args.read:03d}.txt").read_text(encoding="utf8"))
        return
    if args.acknowledge is not None:
        if not args.notes:
            raise ValueError("Substantive review notes required")
        path = DEST / f"chunk-{args.acknowledge:03d}.txt"
        rec = {"chunk":args.acknowledge,"status":"COMPLETE_UNTRUNCATED_TEXT_READ",
            "map_sha256":digest((DEST / "map.json").read_bytes()),"report_sha256":digest(path.read_bytes()),
            "notes":args.notes,"reviewer":"math-audit-agent","utc":datetime.now(timezone.utc).isoformat()}
        with (DEST / "review_ledger.jsonl").open("a",encoding="utf8") as stream:
            stream.write(json.dumps(rec,ensure_ascii=False)+"\n")
        print(json.dumps(rec,ensure_ascii=False))
        return
    if (DEST / "review_ledger.jsonl").exists():
        raise ValueError("Existing review campaign must not be overwritten")
    records = records_for(OUT,"oma-integration")
    inventory = json.loads((OUT / "source_inventory.json").read_text(encoding="utf8"))
    source = next(s for s in inventory["sources"] if s["document_id"] == "oma-integration")
    if digest(Path(source["path"]).read_bytes()) != source["sha256"]:
        raise ValueError("Source changed")
    reviews = [json.loads(line) for line in (OUT / "review_ledger.jsonl").read_text(encoding="utf8").splitlines()]
    direct = set()
    for review in reviews:
        if review["document_id"] == "oma-integration" and review["source_sha256"] == source["sha256"]:
            subset = records[review["start"] - 1:review["end"]]
            if digest(json.dumps(subset,ensure_ascii=False,sort_keys=True).encode()) != review["range_sha256"]:
                raise ValueError("Stale direct review")
            direct.update(range(review["start"],review["end"]+1))
    seen = {records[n-1]["text"]:n for n in sorted(direct,reverse=True)}
    mapping, chunks, current = [], [], []
    size = 0
    for r in records:
        n, text = r["location"], r["text"]
        row = {"paragraph":n,"source_text_sha256":r["text_sha256"]}
        if n in direct:
            row["method"] = "DIRECT_NATIVE_READ"
        elif text in seen:
            row.update(method="EXACT_TEXT_MATCH_REQUIRES_REVIEWED_REFERENT",referent=seen[text])
        else:
            if current and size + len(text) > 23000:
                chunks.append(current)
                current, size = [], 0
            current.append(r)
            size += len(text)
            row.update(method="NOVEL_REQUIRES_READING",chunk=len(chunks)+1)
            seen[text] = n
        mapping.append(row)
    if current:
        chunks.append(current)
    DEST.mkdir(exist_ok=True)
    info = []
    for i, chunk in enumerate(chunks,1):
        output = "\n".join(f"[{r['location']}] {r['text']}" for r in chunk)+"\n"
        (DEST / f"chunk-{i:03d}.txt").write_text(output,encoding="utf8")
        info.append({"chunk":i,"paragraphs":[r["location"] for r in chunk],"characters":len(output),"sha256":digest(output.encode())})
    save_json(DEST / "map.json",{"source_sha256":source["sha256"],"direct_ranges_ledger_sha256":digest((OUT / "review_ledger.jsonl").read_bytes()),"paragraphs":mapping,"chunks":info,
        "notice":"Exact text deduplication is a reading aid; no proof or completion is inferred from extraction."})
    print(json.dumps({"chunks":len(chunks),"unique_unread_paragraphs":sum(len(c) for c in chunks),"characters":sum(c["characters"] for c in info)},indent=2))


if __name__ == "__main__":
    main()
