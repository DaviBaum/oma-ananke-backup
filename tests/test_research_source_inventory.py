from copy import deepcopy
import importlib.util
from pathlib import Path
import subprocess
import sys
import warnings
import zipfile

import pytest


SPEC = importlib.util.spec_from_file_location(
    "research_source_inventory", Path(__file__).resolve().parents[1] / "scripts/research_source_inventory.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_hidden_files_and_duplicate_archive_members_are_retained(tmp_path):
    source = tmp_path / "math"
    source.mkdir()
    (source / ".hidden").write_bytes(b"hidden")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(source / "source.docx", "w") as archive:
            archive.writestr("folder/", b"")
            archive.writestr("folder/repeated.xml", b"first")
            archive.writestr("folder/repeated.xml", b"second")
    report = MODULE.inventory(source)
    assert report["file_count"] == 2
    assert report["archive_member_count"] == 2
    doc = next(x for x in report["files"] if x["kind"] == "docx")
    assert len(doc["archive_directory_entries"]) == 1
    assert doc["archive_members"][0]["sha256"] != doc["archive_members"][1]["sha256"]
    assert all(r["reading_status"] == "NOT_READ_IN_NEW_CAMPAIGN" for r in report["files"])


def test_source_must_be_directory(tmp_path):
    path = tmp_path / "source"
    path.write_bytes(b"not a directory")
    with pytest.raises(ValueError, match="directory"):
        MODULE.inventory(path)


@pytest.mark.parametrize("change", ["schema", "status", "errors", "source_root", "file_count"])
def test_replay_rejects_invalid_prior_report(tmp_path, change):
    (tmp_path / "original.md").write_text("original", encoding="utf-8")
    report = MODULE.inventory(tmp_path)
    assert MODULE.same_sources(report, MODULE.inventory(tmp_path))
    modified = deepcopy(report)
    modified[change] = None
    assert not MODULE.same_sources(modified, report)


def test_replay_detects_mutation_and_removal(tmp_path):
    original = tmp_path / "source.md"
    original.write_text("before", encoding="utf-8")
    report = MODULE.inventory(tmp_path)
    original.write_text("after", encoding="utf-8")
    assert not MODULE.same_sources(report, MODULE.inventory(tmp_path))
    original.unlink()
    assert not MODULE.same_sources(report, MODULE.inventory(tmp_path))


def test_output_cannot_overwrite_sources_or_previous_evidence(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    original = source / "original.md"
    original.write_bytes(b"original")
    outside = tmp_path / "existing.json"
    outside.write_bytes(b"prior evidence")
    script = Path(MODULE.__file__)
    for output in [original, source / "new.json", outside]:
        result = subprocess.run([sys.executable, str(script), "--source", str(source), "--output", str(output)], capture_output=True)
        assert result.returncode != 0
    assert original.read_bytes() == b"original"
    assert outside.read_bytes() == b"prior evidence"
    assert not (source / "new.json").exists()
