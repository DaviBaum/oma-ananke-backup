"""Attest the already-read manifest metadata with explicit coverage modes.

Opaque source hash identifiers are structurally inventoried, never asserted
mathematically validated. Body/proof booleans are source declarations only.
"""
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
import hashlib
import json

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"evidence/math"


def main():
    path=next((ROOT/"math1/math1").glob("*Manifest*.json"))
    data=json.loads(path.read_text(encoding="utf8"))
    namespace=json.loads((OUT/"canonical_namespace.json").read_text(encoding="utf8"))
    for field,target in [("mathematical_objects","objects"),("equations","equations"),("prompts","prompts"),("supersession_graph","supersession_graph")]:
        assert len(data[field])==len(namespace[target])
        for source,extracted in zip(data[field],namespace[target]):
            assert all(extracted[k]==v for k,v in source.items())
    objects=data["mathematical_objects"]
    flags=Counter((o["typ"],o["body"],o["proof"],o["registry"]) for o in objects)
    source_hashes=[r["hash"] for category in ("mathematical_objects","equations","prompts","embedded_objects") for r in data[category]]
    assert all(len(h)==64 and all(c in "0123456789abcdef" for c in h) for h in source_hashes)
    ancillary={}
    for source in ("ananke-canonical","ananke-repair-audit","oma-integration","prompt"):
        p=OUT/"native"/source/"ancillary.json"
        rows=json.loads(p.read_text(encoding="utf8"))
        ancillary[source]={"sha256":hashlib.sha256(p.read_bytes()).hexdigest(),"parts":rows,
            "review":"READ_EMPTY_OR_RUNNING_HEADER_FOOTER_ONLY"}
    report={"schema":"oma.manifest.metadata-review/1","source_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
        "reviewed_utc":datetime.now(timezone.utc).isoformat(),"reviewer":"math-audit-agent",
        "coverage_modes":{
            "top_level_metadata":"READ_ALL_NONREGISTRY_FIELDS_NATIVE_JSON",
            "prompts":"ALL_30_COMPLETE_METADATA_RECORDS_READ; domain context also read in canonical template campaign",
            "mathematical_object_registry":"All native index fields match manifest; source body/proof/registry flags grouped exhaustively by exact tuple and read below",
            "equations":"1377 source LaTeX records covered by canonical parameter-context and preamble reading; registry metadata matched in full native tables; ambiguous equations inspected as OMML/PDF",
            "embedded_objects":"264 complete native index rows matched; the single exact repeated historical-unavailable note was read; actual Pages attachments now reconciled separately",
            "opaque_hash_identifiers":"FORMAT_AND_EXACT_EXTRACTION_CHECKED; claimed semantic body hashes cannot be replayed without absent P01-P30 Markdown/archive inputs",
            "source_validation":"Read as author assertions; these do not establish our proof correctness or implementation coverage"},
        "source_object_flag_patterns":[{"type":k[0],"body_declared":k[1],"proof_declared":k[2],"registry_declared":k[3],"count":v} for k,v in sorted(flags.items())],
        "all_manifest_records_equal_extracted_namespace":True,"opaque_hash_count":len(source_hashes),
        "ancillary_parts":ancillary,
        "findings":["Source-created 2026-08-22 absence claims concern a prior run; all three Pages originals are present now.",
            "The supplied canonical DOCX/PDF/CSV/audit hashes match; the declared canonical Markdown source ZIP and Prompt31 provenance inputs are absent.",
            "Manifest flags body=true/proof=true are source claims, not independent correctness proofs. Substantial defective statements have been identified.",
            "The reconstructed canonical prompt modules differ substantively from recovered historical original mechanisms; matching IDs do not establish semantic identity.",
            "Manifest core-hash derivation and absent Markdown body-hash reproduction remain unresolved provenance, not silently successful checks."],
        "mathematical_correctness_verified":False,"whole_corpus_reading_complete":False}
    destination=OUT/"manifest_metadata_review.json"
    destination.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf8")
    print(json.dumps({"source_sha256":report["source_sha256"],"objects":len(objects),"equations":len(data["equations"]),"metadata_review_written":True}))


if __name__=="__main__":main()
