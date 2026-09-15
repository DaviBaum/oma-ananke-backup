"""Additional graph words remain checked proposals with separate native scope."""
from copy import deepcopy
from fractions import Fraction
import time

import numpy as np
import pytest

from oma.ifc.audit import sha256_file
from oma.routing import certified_cells, certified_fabrication, fabrication_residual
from oma.store import digest
from test_certified_fabrication_frontier import run, reroot
from test_certified_fabrication_pricing import scenario
from test_ifc_pipeline import make_fixture


@pytest.fixture(scope="module")
def source(tmp_path_factory):
    path = make_fixture(tmp_path_factory.mktemp("residual-source")/"original.ifc")
    return [{"path":path,"sha256":sha256_file(path),"transform_m":np.eye(4).tolist()}]


def additional(report):
    return [p for p in report["proposals"] if p.get("path_certificate_kind") == "FABRICATION_RESIDUAL_FRONTIER"]


def test_original_count_minima_and_residual_minima_keep_separate_roots(source):
    report = run(source,max_fittings=2,residual_rounds=1,max_residual_seconds=10)
    residual = report["residual_round"]
    assert residual["status"] == "CHECKED_RESIDUAL_PROPOSALS", residual
    assert residual["independent_check"]["status"] == "PASS"
    assert [p["exact_fittings"] for p in additional(report)] == [1,2]
    original = [p for p in report["proposals"] if p["path_certificate_kind"] == "FABRICATION_FRONTIER"]
    assert len(original) == 2
    assert len({tuple(map(tuple,p["points_m"])) for p in report["proposals"]}) == len(report["proposals"])
    words = residual["generation_ledger"]["excluded_words"]
    assert words == [report["frontier_certificate"]["frontier"][p["exact_fittings"]]["path_states"] for p in original]
    for p in additional(report):
        row = residual["certificate"]["frontier"][p["exact_fittings"]]
        conversion = next(a for a in residual["attempts"] if a["exact_fittings"] == p["exact_fittings"])
        assert p["residual_certificate_root"] == p["path_certificate_root"] == digest(residual["certificate"])
        assert p["residual_entry_root"] == digest(row)
        assert p["residual_exclusion_root"] == residual["certificate"]["exclusion_root"]
        assert p["generation_ledger_root"] == digest(residual["generation_ledger"])
        assert p["binary64_fabrication_certificate_root"] == digest(conversion["binary64_fabrication_certificate"])
        assert p["binary64_exact_fittings"] == conversion["binary64_fabrication_check"]["transitions_checked"]
        assert [s[:7] for s in row["path_states"]] not in words
        assert p["nominal_exact_count_residual_optimality"]
        assert not p["nominal_exact_count_optimality"] and not p["nominal_graph_optimality"]
        assert not p["binary64_objective_optimality"] and not p["candidate_acceptance_authority"]
        assert p["shared_native_budget_feasibility"] == "NOT_CHECKED"


def test_actual_source_residual_path_has_fresh_ifc_body_and_complete_native_pairs(source,tmp_path):
    from oma.ifc.export import export_route
    from oma.ifc.cad import cad_check_routes
    from oma.routing.checker import _semantics
    from test_optimization_fabrication import actual_ifc_correspondence
    s = scenario()
    report = run(source,s,max_fittings=1,residual_rounds=1,max_residual_seconds=10)
    p = additional(report)[0]
    assert p["exact_fittings"] == 1
    path = tmp_path/"residual.ifc"
    material = export_route(source[0]["path"],path,{"route_id":"residual-native","points_m":p["points_m"],
        "system_type":s.system_type,"diameter_m":s.diameter_m,"insulation_m":s.insulation_m,
        "bend_radius_m":s.bend_radius_m,"minimum_straight_m":s.minimum_straight_m},fresh_recheck=False)
    guids = {part["ifc_guid"] for part in material["added_parts"]}
    native = cad_check_routes([source[0]["path"]],path,guids,clearance_m=s.clearance_m)
    assert native["status"] == native["self_interference_status"] == "PASS"
    assert native["pairs_accounted"] == len(guids) == 3 and native["obstacle_count"] == 1
    semantics = _semantics(path,source[0]["path"],material,s)
    assert not semantics["errors"] and semantics["fitting_count"] == 1
    proof = report["residual_round"]["attempts"][1]["binary64_fabrication_certificate"]
    assert actual_ifc_correspondence(path,material,proof)["status"] == "PASS"
    assert sha256_file(source[0]["path"]) == source[0]["sha256"]


@pytest.mark.parametrize("fault",["count","points","exclusion","context","empty_exclusions"])
def test_changed_residual_proof_never_displaces_original_options(source,monkeypatch,fault):
    real = fabrication_residual.compile_fabrication_alternatives
    def corrupt(problem,objective,maximum,words,**kwargs):
        if fault == "empty_exclusions":
            return real(problem,objective,maximum,[],**kwargs)
        p = deepcopy(problem)
        if fault == "context":
            p["context_root"] = "foreign-model"
        proof = real(p,objective,maximum,words,**kwargs)
        assert proof["status"] == "CERTIFIED"
        if fault == "count": proof["frontier"].pop()
        if fault == "points": proof["frontier"][1]["points_m"][1][0] = "1000"
        if fault == "exclusion": proof["exclusion_root"] = "0"*64
        return reroot(proof)
    monkeypatch.setattr(fabrication_residual,"compile_fabrication_alternatives",corrupt)
    report = run(source,max_fittings=2,residual_rounds=1,max_residual_seconds=10)
    assert report["residual_round"]["independent_check"]["status"] == "FAIL"
    assert not additional(report)
    assert report["status"] == "CHECKED_FABRICATION_PROPOSALS"
    assert len([p for p in report["proposals"] if p["path_certificate_kind"] == "FABRICATION_FRONTIER"]) == 2


@pytest.mark.parametrize("budget",[{"max_residual_states":1},{"max_residual_work":1}])
def test_residual_resource_exhaustion_preserves_checked_original_frontier(source,budget):
    report = run(source,max_fittings=2,residual_rounds=1,**budget)
    assert report["residual_round"]["status"] == "UNKNOWN"
    assert not additional(report) and report["frontier_check"]["status"] == "PASS"
    assert report["status"] == "CHECKED_FABRICATION_PROPOSALS" and report["proposals"]


@pytest.mark.parametrize("elapsed",[4.,31.])
def test_optional_local_deadline_and_whole_adapter_deadline_are_distinct(source,monkeypatch,elapsed):
    clock = [0.]
    monkeypatch.setattr(certified_fabrication.time,"monotonic",lambda:clock[0])
    def checkpoint(stage):
        if stage == "residual_expand": clock[0] = elapsed
    report = run(source,max_fittings=2,residual_rounds=1,deadline=30.,checkpoint=checkpoint)
    if elapsed == 31.:
        assert report["status"] == "UNKNOWN" and not report["proposals"]
        assert report["reason"] == "FABRICATION_SEARCH_DEADLINE"
    else:
        assert report["status"] == "CHECKED_FABRICATION_PROPOSALS"
        assert report["residual_round"]["reason"] == "FABRICATION_RESIDUAL_DEADLINE"
        assert not additional(report) and report["frontier_check"]["status"] == "PASS"


@pytest.mark.parametrize("stage",["fabrication_residual_seed","residual_expand","residual_closure_verify",
    "fabrication_residual_conversion_checked","fabrication_residual_complete"])
@pytest.mark.parametrize("kind",[ValueError,TimeoutError,fabrication_residual.ResidualDeadline])
def test_external_cancellation_propagates_unchanged(source,stage,kind):
    signal = kind("caller cancelled")
    def checkpoint(observed):
        if observed == stage: raise signal
    with pytest.raises(kind) as caught:
        run(source,max_fittings=1,residual_rounds=1,checkpoint=checkpoint)
    assert caught.value is signal


@pytest.mark.parametrize("fault",["count","verdict"])
def test_residual_binary64_proof_is_fresh_and_count_complete(source,monkeypatch,fault):
    real = fabrication_residual.verify_orthogonal_fabrication
    def changed(*args,**kwargs):
        checked = real(*args,**kwargs)
        if fault == "count": checked["transitions_checked"] += 1
        else: checked["fabrication_status"] = "UNKNOWN"
        return checked
    monkeypatch.setattr(fabrication_residual,"verify_orthogonal_fabrication",changed)
    report = run(source,max_fittings=2,residual_rounds=1)
    assert report["residual_round"]["independent_check"]["status"] == "PASS"
    assert not additional(report)
    assert [a["status"] for a in report["residual_round"]["attempts"]][1:] == ["BINARY64_FABRICATION_UNRESOLVED"]*2


def test_residual_output_quota_records_omitted_counts_and_keeps_originals(source):
    report = run(source,max_fittings=2,residual_rounds=1,max_residual_proposals=1)
    assert [p["exact_fittings"] for p in additional(report)] == [1]
    assert report["residual_round"]["attempts"][2]["status"] == "OUTPUT_LIMIT_NOT_CONVERTED"
    assert not report["residual_round"]["policy"]["physical_unique_path_completeness"]


@pytest.mark.parametrize("fault",["source","scenario","source_report","source_specs","executable"])
def test_last_callback_cannot_publish_changed_original_inputs(source,monkeypatch,fault):
    specs = deepcopy(source)
    s = scenario()
    cells = certified_cells.build_certified_cell_proposals(specs,s,context_root="final-callback",grid_divisions=4)
    path = specs[0]["path"]
    original = path.read_bytes()
    def mutate(stage):
        if stage != "fabrication_proposal_publish": return
        if fault == "source": path.write_bytes(original+b"\n")
        elif fault == "scenario": s.objective_weights["length_m"] = 99.
        elif fault == "source_report": cells["assumptions"]["changed"] = True
        elif fault == "source_specs": specs[0]["transform_m"][0][3] = 999.
        else: monkeypatch.setattr(certified_fabrication,"checker_version",lambda:"changed-build")
    try:
        result = certified_fabrication.build_certified_fabrication_proposals(specs,s,cells,
            context_root="final-callback",max_fittings=1,residual_rounds=1,max_pricing_work=1,checkpoint=mutate)
        assert result["status"] == "BLOCKED" and not result["proposals"], result
    finally:
        path.write_bytes(original)


@pytest.mark.parametrize("kwargs",[{"residual_rounds":True},{"residual_rounds":2},
    {"max_residual_seconds":float("nan")},{"max_residual_seconds":float("inf")},
    {"max_residual_seconds":0},{"max_residual_seconds":True},{"max_residual_proposals":True},
    {"max_residual_proposals":0},{"max_residual_proposals":17}])
def test_invalid_residual_configuration_never_emits_proposals(source,kwargs):
    result = run(source,**{"max_fittings":2,"residual_rounds":1,**kwargs})
    assert result["status"] == "BLOCKED" and not result["proposals"]


def test_disabled_residual_phase_preserves_existing_proposal_models(source,monkeypatch):
    monkeypatch.setattr(fabrication_residual,"compile_fabrication_alternatives",lambda *a,**k:pytest.fail("disabled residual phase ran"))
    implicit = run(source,max_fittings=1)
    explicit = run(source,max_fittings=1,residual_rounds=0)
    assert implicit["proposals"] == explicit["proposals"] and implicit["model"] == explicit["model"]
    assert "residual_round" not in implicit


def test_joint_proposal_pipeline_persists_residual_language_and_generation_roots(source,tmp_path,monkeypatch):
    from oma.routing.proposals import project_proposals
    from oma.store import Store
    s = scenario().model_copy(update={"max_candidates":6})
    cells = certified_cells.build_certified_cell_proposals(source,s,context_root="pipeline-source",grid_divisions=4)
    lifted = certified_fabrication.build_certified_fabrication_proposals(source,s,cells,context_root="pipeline-source",
        max_fittings=1,residual_rounds=1,max_pricing_work=1)
    assert len(additional(lifted)) == 1
    store = Store(tmp_path/"store")
    project = store.create_project("Residual provenance",{})
    mission = {"max_new_fittings":1,"route_demands":[{"id":"service","alternatives":[s.model_dump(mode="json")]}]}
    origin = store.create_run(project["id"],{"operation":"route_joint","mission":mission})
    monkeypatch.setattr(certified_cells,"build_certified_cell_proposals",lambda *a,**k:deepcopy(cells))
    seen = []
    def prepared(*args,**kwargs):
        seen.append(kwargs)
        return deepcopy(lifted)
    monkeypatch.setattr(certified_fabrication,"build_certified_fabrication_proposals",prepared)
    proposals = list(project_proposals(store,origin,{"sources":[]},s,[],deadline=time.monotonic()+60,
        checkpoint=lambda stage:None,on_search=lambda payload:None,max_fittings=1,request_demand_id="service"))
    assert seen[0]["residual_rounds"] == 1 and seen[0]["max_fittings"] == 1
    p, = additional({"proposals":proposals})
    evidence = p["geometry_evidence"]
    for key in ("exact_fittings","residual_certificate_root","residual_entry_root","residual_count_domain_root",
            "residual_exclusion_root","residual_model_root","generation_ledger_root",
            "nominal_exact_count_residual_optimality","nominal_exact_count_optimality",
            "binary64_exact_fittings","shared_native_budget_feasibility"):
        assert evidence[key] == p[key]
    artifact = store.get(evidence["report_root"])
    assert artifact["report"]["residual_round"] == lifted["residual_round"]
    assert artifact["context"]["request_root"] == digest(origin["request"])
    assert artifact["context"]["request_demand_id"] == "service"
    assert not evidence["route_acceptance"]
    event = next(e for e in store.events(project["id"]) if e["stage"] == "fabrication_graph")
    assert event["payload"]["residual"]["independent_check"]["status"] == "PASS"
    assert event["payload"]["residual"]["policy"]["native_rejections_used_as_exclusions"] is False
