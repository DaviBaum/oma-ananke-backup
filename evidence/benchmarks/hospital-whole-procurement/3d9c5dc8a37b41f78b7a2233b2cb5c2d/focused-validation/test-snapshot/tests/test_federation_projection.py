import numpy as np
import pytest

from oma.ifc.audit import federation_manifest
from oma.service import EngineService


@pytest.mark.parametrize("verified", [False, True])
def test_snapshot_preserves_real_federation_alignment_obligation(tmp_path, verified):
    service = EngineService(tmp_path / "engine")
    audits = [{"source_id": name, "source_path": str(tmp_path / f"{name}.ifc"),
               "schema": "IFC4", "blockers": [], "products": []}
              for name in ("architecture", "mechanical")]
    transforms = {a["source_id"]: {"matrix": np.eye(4).tolist(),
                  "verified": verified, "evidence": {"method": "explicit_test_anchor"}}
                  for a in audits}
    manifest = federation_manifest(audits, "projection-fixture", transforms)
    assert "status" not in manifest
    project = service.store.create_project("datum", {
        "entities": [], "sources": [{"id": a["source_id"], "name": a["source_id"]} for a in audits],
        "derived_artifacts": {"federation": manifest}})
    snapshot = service.snapshot(project["id"])
    obligations = [item for item in snapshot["missing_inputs"]
                   if isinstance(item, dict) and item.get("code") == "FEDERATION_DATUM_REVIEW"]
    assert bool(obligations) is not verified
    if obligations:
        assert obligations[0]["details"] == manifest
        assert obligations[0]["details"]["alignment_status"] == "UNRESOLVED"
    assert snapshot["project"]["state_root"] == project["state_root"]


def test_canonical_alignment_status_wins_over_legacy_status(tmp_path):
    service = EngineService(tmp_path / "engine")
    project = service.store.create_project("legacy mismatch", {
        "entities": [], "sources": [], "derived_artifacts": {"federation": {
            "alignment_status": "UNRESOLVED", "status": "VERIFIED"}}})
    assert any(isinstance(item, dict) and item.get("code") == "FEDERATION_DATUM_REVIEW"
               for item in service.snapshot(project["id"])["missing_inputs"])
