"""Validate immutable historical review acknowledgments and derive coverage."""
from pathlib import Path
from hashlib import sha256
from datetime import datetime, timezone
import json

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "evidence/math/pages/review"


def main():
    raw = (DEST / "map.json").read_bytes()
    mapping = json.loads(raw)
    map_hash = sha256(raw).hexdigest()
    ledger_raw = (DEST / "review-ledger.jsonl").read_bytes()
    rows = [json.loads(line) for line in ledger_raw.splitlines() if line.strip()]
    chunks = {c["number"]: c for c in mapping["chunks"]}
    acknowledged = set()
    for row in rows:
        number = row["chunk"]
        chunk = chunks[number]
        digest = sha256((DEST / f"chunk-{number:03d}.txt").read_bytes()).hexdigest()
        assert row["map_sha256"] == map_hash
        assert row["chunk_sha256"] == digest == chunk["sha256"]
        assert row["source_sha256"] == chunk["source_sha256"]
        assert row["source"] == chunk["source"]
        assert row["status"] == "NATIVE_TEXT_AND_ATTACHED_TABLE_ROWS_READ"
        assert row["notes"].strip() and row["reviewer"].strip()
        acknowledged.add(number)
    paragraphs = {(p["source"], p["paragraph"]): p for p in mapping["paragraphs"]}

    def covered(p):
        if "chunk" in p:
            return p["chunk"] in acknowledged
        r = p["referent"]
        first = paragraphs[r["source"], r["paragraph"]]
        assert first["combined_content_sha256"] == p["combined_content_sha256"]
        assert "chunk" in first
        return first["chunk"] in acknowledged

    sources = []
    for source in mapping["sources"]:
        ps = [p for p in paragraphs.values() if p["source"] == source["source"]]
        direct = [p for p in ps if "chunk" in p and covered(p)]
        inherited = [p for p in ps if "referent" in p and covered(p)]
        complete = len(direct) + len(inherited) == len(ps)
        sources.append({
            "source": source["source"], "source_sha256": source["source_sha256"],
            "paragraphs": len(ps), "novel_paragraphs_read": len(direct),
            "exact_duplicate_paragraphs_with_reviewed_referent": len(inherited),
            "paragraphs_remaining": len(ps) - len(direct) - len(inherited),
            "native_tables": source["native_tables"],
            "reviewed_native_tables": len({t for p in ps if covered(p) for t in p["table_ids"]}),
            "content_reading_complete": complete,
            "source_content_issues": source["source_content_issues"],
        })
    result = {
        "schema": "oma.historical-reading-coverage/1",
        "utc": datetime.now(timezone.utc).isoformat(),
        "map_sha256": map_hash, "ledger_sha256": sha256(ledger_raw).hexdigest(),
        "acknowledgments": len(rows), "unique_reviewed_chunks": len(acknowledged),
        "total_chunks": len(chunks),
        "unread_chunks": sorted(set(chunks) - acknowledged),
        "sources": sources,
        "all_historical_native_content_read": all(s["content_reading_complete"] for s in sources),
        "independent_verification_of_every_mathematical_claim": False,
        "all_historical_algorithms_implemented": False,
        "known_missing_body": "Original Prompt 7 is absent. Original Prompt 26 begins at the continuation of THM-LIFE34, proof step 14; its preceding body is absent. See source-gaps.json for exact native boundaries.",
        "source_gaps_artifact": "evidence/math/pages/source-gaps.json",
        "notice": "Review means full novel native text and attached table rows read, with exact duplicate correspondence validated. It does not repair damaged source formulas or establish proofs, physical validity, implementation or reconstructed-canonical equivalence.",
    }
    (DEST / "coverage.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
