"""Clarify the exact original-entity preservation scope of the saved Office export."""
from pathlib import Path
import hashlib
import json
import re
import ifcopenshell

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "evidence/benchmarks/pressure-driven/office/b44b3123cdb641709b2aa32ae5bd526c"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def records(path, expected_count):
    matches = re.findall(rb"^#([0-9]+)=([^\r\n]*);\s*$", Path(path).read_bytes(), re.MULTILINE)
    rows = {int(k): value for k, value in matches}
    assert len(rows) == len(matches) == expected_count
    return rows


def main():
    prior_path = OUT / "independent-audit.json"
    prior = json.loads(prior_path.read_text(encoding="utf8"))
    source_name, source_hash = next(iter(prior["original_ifc_hashes_unchanged"].items()))
    export = prior["export"]["file"]
    source, final = Path(source_name), Path(export["path"])
    assert sha(source) == source_hash and sha(final) == export["sha256"]
    original_model, final_model = ifcopenshell.open(str(source)), ifcopenshell.open(str(final))
    originals, finals = {x.id(): str(x) for x in original_model}, {x.id(): str(x) for x in final_model}
    assert len(originals) == 62930 and all(finals.get(k) == v for k,v in originals.items())
    before, after = records(source, len(originals)), records(final, len(finals))
    changed = [k for k,v in before.items() if after.get(k) != v]
    assert sha(source) == source_hash and sha(final) == export["sha256"]
    result = {"status": "ORIGINAL_PARSED_ENTITIES_PRESERVED_RAW_RECORD_TEXT_SEPARATELY_ACCOUNTED",
        "prior_audit_sha256": sha(prior_path), "script_sha256": sha(__file__), "source_sha256": source_hash,
        "export_sha256": export["sha256"], "original_parsed_entities": len(originals),
        "output_entities": len(finals), "all_original_canonical_parsed_entities_identical": True,
        "raw_original_record_strings_identical": len(before)-len(changed), "raw_original_record_strings_reformatted": len(changed),
        "reformatted_original_ids": changed,
        "examples": [{"id": k, "before": before[k].decode("utf8"), "after": after[k].decode("utf8")} for k in changed[:8]],
        "scope": "The historical audit compared str(IfcOpenShell entity) after parsing. It establishes that comparison for every original ID, not byte-identical source decimal tokens or complete preservation under another parser.",
        "original_ifc_file_bytes_unchanged": True, "saved_export_bytes_unchanged": True,
        "native_checks_or_optimization_rerun": False, "prior_receipts_unchanged": True}
    (OUT / "step-text-scope-audit.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf8")
    print(json.dumps({k:result[k] for k in ("status", "original_parsed_entities", "raw_original_record_strings_identical", "raw_original_record_strings_reformatted")}))


if __name__ == "__main__":
    main()
