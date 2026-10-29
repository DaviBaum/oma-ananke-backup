import gzip
import importlib.util
import json
from pathlib import Path

import pytest


SPEC = importlib.util.spec_from_file_location(
    "research_occurrence_seed", Path(__file__).resolve().parents[1] / "scripts/research_occurrence_seed.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def fixture(tmp_path, duplicate=False):
    original = tmp_path / "math1" / "source.md"
    original.parent.mkdir()
    original.write_text("original source", encoding="utf-8")
    extracted = tmp_path / "extracted.jsonl"
    rows = [{"location": i, "locator": f"line[{1 if duplicate else i}]", "text": str(i),
             "text_sha256": MODULE.digest(str(i).encode())} for i in range(1, 101)]
    extracted.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    audit = {
        "full_tree_inventory": [{"relative_path": "math1/source.md", "sha256": MODULE.digest(original.read_bytes())}],
        "artifact_bindings": [],
        "sources": [{"document_id": "fixture", "source_path": "math1/source.md", "sha256": MODULE.digest(original.read_bytes()),
                     "extracted_records": 100, "extraction_artifact": "extracted.jsonl", "actual_extraction_sha256": MODULE.digest(extracted.read_bytes())}],
        "counts": {"primary_extracted_locations": 100},
        "occurrence_ledger_design": {"additional_units_to_materialize": {"visual_review": "PENDING"}},
    }
    path = tmp_path / "audit.json"
    path.write_text(json.dumps(audit), encoding="utf-8")
    return path, original, extracted


def test_planned_readers_cover_every_occurrence_without_reading_credit(tmp_path):
    audit, _, _ = fixture(tmp_path)
    output = tmp_path / "evidence" / "seed"
    report = MODULE.build(tmp_path, audit, output)
    with gzip.open(output / "fixture.jsonl.gz", "rt", encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle]
    assert len(rows) == len({r["occurrence_id"] for r in rows}) == 100
    assert {r["primary_reader_slot"] for r in rows} == {f"{i:03}" for i in range(1, 101)}
    assert all(r["primary_reader_slot"] != r["independent_reviewer_slot"] for r in rows)
    assert all(r["direct_read_status"] == "UNREAD" and r["direct_review_events"] == [] for r in rows)
    assert all(r["actual_reader_agent_id"] is None and r["actual_reviewer_agent_id"] is None for r in rows)
    assert report["complete_corpus_ledger"] is False
    assert report["final_zero_omission_denominator"] is None
    assert report["direct_read_occurrences"] == report["independently_reviewed_occurrences"] == 0
    with pytest.raises(FileExistsError):
        MODULE.build(tmp_path, audit, output)


@pytest.mark.parametrize("target", ["original", "extraction"])
def test_changed_input_prevents_seed_publication(tmp_path, target):
    audit, original, extraction = fixture(tmp_path)
    (original if target == "original" else extraction).write_text("changed", encoding="utf-8")
    output = tmp_path / "evidence" / "seed"
    with pytest.raises(ValueError, match="hash changed"):
        MODULE.build(tmp_path, audit, output)
    assert not output.exists()


def test_repeated_locator_fails_without_valid_status(tmp_path):
    audit, _, _ = fixture(tmp_path, duplicate=True)
    output = tmp_path / "evidence" / "seed"
    with pytest.raises(ValueError, match="Duplicate occurrence"):
        MODULE.build(tmp_path, audit, output)
    assert not (output / "status.json").exists()


def test_readonly_source_destination_rejected(tmp_path):
    audit, original, _ = fixture(tmp_path)
    with pytest.raises(ValueError, match="outside original inputs"):
        MODULE.build(tmp_path, audit, tmp_path / "math1" / "new-ledger")
    assert original.read_text(encoding="utf-8") == "original source"
