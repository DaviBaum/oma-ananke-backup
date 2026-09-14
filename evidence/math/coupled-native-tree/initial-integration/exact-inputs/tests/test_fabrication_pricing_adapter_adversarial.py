"""Pricing evidence is never promoted across objective, source or deadline changes."""
from copy import deepcopy

import pytest

from oma.ifc.audit import sha256_file
from oma.optimization import fabrication_pricing as pricing
from oma.routing import certified_fabrication as adapter
from oma.store import digest
from test_geometry_coverage_checkpoints import native_source


@pytest.mark.parametrize("substitution",["objective","source_context"])
def test_valid_pricing_from_another_objective_or_context_keeps_only_feasible_fallback(native_source,monkeypatch,substitution):
    specs,scenario,source_report = native_source
    original = deepcopy(source_report)
    real_compile = pricing.compile_fabrication_pricing
    def substituted(problem,objective,**kwargs):
        if substitution == "objective":
            objective = {**objective,"fitting_weight":"99"}
        else:
            problem = {**problem,"context_root":"unrelated-source-and-mission"}
        # This is a valid cost proof for a different declared mathematical input.
        certificate = real_compile(problem,objective,**kwargs)
        assert certificate["status"] == "CERTIFIED", certificate
        assert pricing.verify_fabrication_pricing(problem,objective,certificate)["status"] == "PASS"
        return certificate
    monkeypatch.setattr(pricing,"compile_fabrication_pricing",substituted)
    result = adapter.build_certified_fabrication_proposals(specs,scenario,source_report,context_root="active-source-and-mission")
    assert result["status"] == "CHECKED_FABRICATION_PROPOSALS", result.get("reason")
    assert result["pricing_check"]["status"] == "FAIL"
    assert "identity differs" in result["pricing_check"]["reason"]
    assert len(result["proposals"]) == 1
    proposal = result["proposals"][0]
    assert proposal["path_certificate_kind"] == "FABRICATION_SEARCH"
    assert proposal["path_certificate_root"] == digest(result["certificate"])
    assert proposal["binary64_fabrication_certificate_root"] == digest(result["binary64_fabrication_certificate"])
    assert proposal["nominal_graph_optimality"] is False
    assert proposal["binary64_objective_optimality"] is False and proposal["candidate_acceptance_authority"] is False
    assert source_report == original and sha256_file(specs[0]["path"]) == specs[0]["sha256"]


@pytest.mark.parametrize("error_type",[adapter._PricingDeadline,TimeoutError,ValueError])
def test_caller_pricing_cancellation_is_not_reinterpreted_as_optional_timeout(native_source,error_type):
    specs,scenario,source_report = native_source
    original = deepcopy(source_report)
    error = error_type("external caller cancelled pricing")
    reached = []
    def checkpoint(stage):
        if stage == "fabrication_pricing_independent_replay":
            reached.append(stage)
            raise error
    with pytest.raises(error_type) as caught:
        adapter.build_certified_fabrication_proposals(specs,scenario,source_report,
            context_root="external-cancellation",checkpoint=checkpoint)
    assert caught.value is error and len(reached) == 1
    assert source_report == original and sha256_file(specs[0]["path"]) == specs[0]["sha256"]


def test_source_bytes_changed_after_pricing_cannot_publish_either_path(native_source):
    specs,scenario,source_report = native_source
    source = specs[0]["path"]
    original_bytes,original_report = source.read_bytes(),deepcopy(source_report)
    reached = []
    def checkpoint(stage):
        if stage == "fabrication_pricing_independent_replay":
            reached.append(stage)
            source.write_bytes(original_bytes+b"\n")
    try:
        result = adapter.build_certified_fabrication_proposals(specs,scenario,source_report,
            context_root="late-source-change",checkpoint=checkpoint)
        assert reached
        assert result["binary64_fabrication_check"]["fabrication_status"] == "PASS"
        assert result["status"] == "BLOCKED" and result["proposals"] == []
        assert "source bytes changed" in result["reason"]
    finally:
        source.write_bytes(original_bytes)
    assert source_report == original_report and sha256_file(source) == specs[0]["sha256"]


def test_checked_nominal_price_does_not_survive_a_late_executable_change(native_source,monkeypatch):
    specs,scenario,source_report = native_source
    version = adapter.checker_version()
    changed = []
    def checkpoint(stage):
        if stage == "fabrication_pricing_independent_replay":
            changed.append(stage)
    monkeypatch.setattr(adapter,"checker_version",lambda:"changed-executable" if changed else version)
    result = adapter.build_certified_fabrication_proposals(specs,scenario,source_report,
        context_root="late-version-change",checkpoint=checkpoint)
    assert changed
    assert result["binary64_fabrication_check"]["fabrication_status"] == "PASS"
    assert result["status"] == "BLOCKED" and result["proposals"] == []
    assert "implementation changed" in result["reason"]
    assert sha256_file(specs[0]["path"]) == specs[0]["sha256"]
