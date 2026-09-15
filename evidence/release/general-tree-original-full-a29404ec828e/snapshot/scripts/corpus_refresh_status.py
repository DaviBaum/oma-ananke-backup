"""Refresh stale inventory review labels from checked coverage, not extraction."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence/math"


def main():
    inventory_path = OUT / "source_inventory.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf8"))
    coverage = json.loads((OUT / "combined_review_coverage.json").read_text(encoding="utf8"))
    by_id = {d["document_id"]: d for d in coverage["documents"]}
    rows = []
    for source in inventory["sources"]:
        doc = source["document_id"]
        c = by_id[doc]
        if hashlib.sha256(Path(source["path"]).read_bytes()).hexdigest() != source["sha256"]:
            raise ValueError("Immutable source bytes changed")
        if doc == "ds-store":
            status = "EXCLUDED_FILESYSTEM_METADATA"
        elif doc == "ananke-canonical-pdf":
            status = "COMPANION_VISUAL_REFERENCE_SELECTED_AMBIGUITIES_REVIEWED"
        else:
            status = "CONTENT_REVIEW_COMPLETE_WITH_DECLARED_CORRESPONDENCE" if c["content_review_complete"] else "CONTENT_REVIEW_INCOMPLETE"
        source["review_status"] = status
        source["review_coverage_artifact"] = "evidence/math/combined_review_coverage.json"
        source["independent_mathematical_verification_complete"] = False
        if doc in ("1-10", "11-20", "21-30"):
            source["extraction_status"] = "NATIVE_IWA_BODY_AND_ALL_ATTACHED_TABLES_EXTRACTED"
            source["extraction_method"] = "Read-only Snappy/Protobuf field decoding; exact UTF-16 body offsets and typed native table cells retained"
            source["native_pages_paragraphs"] = c["extracted_locations"]
            source["extraction_artifact"] = f"evidence/math/pages/{doc}/content-audit.json"
        rows.append({"document_id": doc, "source_sha256": source["sha256"], "status": status,
            "extracted_locations": c["extracted_locations"], "direct_native_read": c["direct_native_read"],
            "content_covered": c["content_covered"], "content_review_complete": c["content_review_complete"],
            "coverage_modes": c.get("coverage_modes", {}), "independent_mathematical_verification_complete": False})
    inventory["review_status_refreshed_utc"] = datetime.now(timezone.utc).isoformat()
    inventory_path.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    report = {"schema": "oma.corpus.review-status/2", "sources": rows,
        "all_supplied_mathematical_content_covered_by_declared_review_methods": coverage["all_supplied_mathematical_content_covered_by_declared_review_methods"],
        "source_content_gaps": coverage["source_content_gaps"], "whole_corpus_verified": False,
        "notice": coverage["notice"]}
    (OUT / "review_status.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(json.dumps({"sources": len(rows), "content_review_complete": report["all_supplied_mathematical_content_covered_by_declared_review_methods"], "whole_corpus_verified": False}))


if __name__ == "__main__":
    main()
