"""Exact-count options remain source-bound proposals, never joint acceptance."""
from copy import deepcopy
from fractions import Fraction
import time

import numpy as np
import pytest

from oma.ifc.audit import sha256_file
from oma.optimization import fabrication_frontier as frontier
from oma.routing import certified_cells, certified_fabrication
from oma.store import digest
from test_certified_fabrication_pricing import scenario
from test_geometry_coverage_checkpoints import _scenario as wall_scenario
from test_ifc_pipeline import make_fixture


@pytest.fixture(scope="module")
def source(tmp_path_factory):
    path = make_fixture(tmp_path_factory.mktemp("frontier-source") / "wall.ifc")
    return [{"path":path, "sha256":sha256_file(path), "transform_m":np.eye(4).tolist()}]


def run(source, s=None, **kwargs):
    s = s or scenario()
    cells = certified_cells.build_certified_cell_proposals(source,s,context_root="actual-frontier-source",grid_divisions=4)
    assert cells["coverage_check"]["status"] == "PASS", cells
    identity = digest(cells)
    result = certified_fabrication.build_certified_fabrication_proposals(source,s,cells,
        context_root=digest({"mission":s.model_dump(mode="json"),"source":source[0]["sha256"]}),
        **{"max_pricing_work":1, **kwargs})
    assert digest(cells) == identity
    return result


def options(report):
    return [p for p in report["proposals"] if p["path_certificate_kind"] == "FABRICATION_FRONTIER"]


def assert_fallback(report):
    assert report["status"] == "CHECKED_FABRICATION_PROPOSALS", report.get("reason")
    assert not options(report)
    assert report["proposals"]
    for p in report["proposals"]:
        assert p["path_certificate_kind"] in {"FABRICATION_SEARCH","FABRICATION_PRICING"}
        assert "exact_fittings" not in p
        assert "shared_native_budget_feasibility" not in p
        assert not p["candidate_acceptance_authority"]


def reroot(proof):
    proof["certificate_root"] = digest({k:v for k,v in proof.items() if k != "certificate_root"})
    return proof


def test_actual_source_retains_separate_count_optima_and_conversion_roots(source):
    report = run(source,max_fittings=2)
    assert report["frontier_check"]["status"] == "PASS", report
    assert report["frontier_check"]["reachable_counts"] == [1,2]
    assert report["frontier_check"]["counts_checked"] == 3
    assert report["coverage_check"]["loaded_obstacles"] == 1
    assert report["coverage_check"]["omitted_with_full_body_region_proof"] == 1
    budget = report["fitting_budget"]
    assert budget["declared_max_new_fittings"] == budget["represented_count_cap"] == 2
    assert report["model"]["source_roots"]["fitting_budget"] == digest(budget)
    assert [p["exact_fittings"] for p in options(report)] == [1,2]
    assert report["proposals"][:2] == options(report)
    assert not report["frontier_output_policy"]["complete_cartesian_route_universe"]
    for p in options(report):
        k = p["exact_fittings"]
        row = report["frontier_certificate"]["frontier"][k]
        conversion = report["frontier_conversions"][k]
        assert p["path_certificate_root"] == p["frontier_certificate_root"] == digest(report["frontier_certificate"])
        assert p["frontier_entry_root"] == digest(row) == conversion["frontier_entry_root"]
        assert p["frontier_count_domain_root"] == report["frontier_certificate"]["count_domain_root"]
        assert p["binary64_fabrication_certificate_root"] == digest(conversion["binary64_fabrication_certificate"])
        assert p["binary64_exact_fittings"] == k == conversion["binary64_fabrication_check"]["transitions_checked"]
        assert p["points_m"] == [[float(Fraction(x)) for x in point] for point in row["points_m"]]
        assert p["nominal_exact_count_optimality"] and not p["nominal_graph_optimality"]
        assert not p["binary64_objective_optimality"] and not p["candidate_acceptance_authority"]
        assert p["shared_native_budget_feasibility"] == "NOT_CHECKED"
    # One fitting costs more in this length-only problem; retaining it is the
    # useful hard-budget option that unconditional scalar minimization loses.
    a,b = report["frontier_certificate"]["frontier"][1:3]
    assert float(Fraction(a["cost"][0])) + float(Fraction(a["cost"][1]))*np.pi > float(Fraction(b["cost"][0])) + float(Fraction(b["cost"][1]))*np.pi


def native_source_frontier_case(directory):
    """Reusable actual source adapter -> certificate -> IFC correspondence."""
    from oma.ifc.cad import cad_check_routes, load_cad
    from oma.ifc.export import export_route
    from oma.routing.checker import _semantics
    from oma.routing.native_zone import check_native_zone
    from test_optimization_fabrication import actual_ifc_correspondence
    directory.mkdir(parents=True,exist_ok=True)
    path = make_fixture(directory/"original.ifc")
    source = [{"path":path,"sha256":sha256_file(path),"transform_m":np.eye(4).tolist()}]
    s = wall_scenario()
    report = run(source,s,max_fittings=2,max_frontier_seconds=10)
    assert report["frontier_check"]["status"] == "PASS", report
    proposal = options(report)[0]
    assert proposal["exact_fittings"] == 2
    output = directory/"frontier-route.ifc"
    material = export_route(path,output,{"route_id":"source-frontier-wall","points_m":proposal["points_m"],
        "system_type":s.system_type,"diameter_m":s.diameter_m,"insulation_m":s.insulation_m,
        "bend_radius_m":s.bend_radius_m,"minimum_straight_m":s.minimum_straight_m},fresh_recheck=False)
    guids = {p["ifc_guid"] for p in material["added_parts"]}
    native = cad_check_routes([path],output,guids,clearance_m=s.clearance_m)
    semantics = _semantics(output,path,material,s)
    correspondence = actual_ifc_correspondence(output,material,report["frontier_conversions"][2]["binary64_fabrication_certificate"])
    solids,errors = load_cad(output,guids=guids)
    zone = check_native_zone(solids,s.allowed_zone,expected_count=len(guids),errors=errors)
    assert native["status"] == zone["status"] == correspondence["status"] == "PASS"
    assert semantics["errors"] == [] and semantics["fitting_count"] == 2
    assert native["obstacle_count"] == 1 and native["pairs_accounted"] == len(guids) == 5
    assert sha256_file(path) == source[0]["sha256"]
    return {"report":report,"materialization":material,"native":native,"semantics":semantics,
        "native_zone":zone,"binary64_native_correspondence":correspondence,
        "source_sha256":source[0]["sha256"],"export_sha256":sha256_file(output),
        "scope":"ACTUAL_SOURCE_BOUND_EXACT_TWO_FITTING_PROPOSAL_AND_SEPARATE_NATIVE_PATH_CHECK",
        "joint_budget_checked":False,"candidate_accepted":False,"physical_optimality":False}


def test_actual_source_wall_frontier_path_materializes_two_native_fittings(tmp_path):
    from oma.ifc.audit import atomic_json
    result = native_source_frontier_case(tmp_path)
    atomic_json(tmp_path/"source-frontier-evidence.json",result)


@pytest.mark.parametrize("attack",["missing_count","false_no_path","path","count_root","source","weights","different_cap"])
def test_independent_replay_rejects_changed_frontier_before_any_option(source,monkeypatch,attack):
    real = frontier.compile_fabrication_frontier
    def changed(problem,objective,maximum,**kw):
        p,o,k = deepcopy(problem),deepcopy(objective),maximum
        if attack == "source":
            p["context_root"] = "another-immutable-context"
        if attack == "weights":
            o["fitting_weight"] = "9"
        if attack == "different_cap":
            k = 1
        proof = real(p,o,k,**kw)
        assert proof["status"] == "CERTIFIED"
        if attack == "missing_count":
            proof["frontier"].pop()
        elif attack == "false_no_path":
            proof["frontier"][1] = {"fittings":1,"status":"NO_PATH_AT_EXACT_COUNT","cost":None,"path_states":[],"points_m":[]}
        elif attack == "path":
            proof["frontier"][1]["points_m"][1][0] = "1000"
        elif attack == "count_root":
            proof["count_domain_root"] = "0"*64
        return reroot(proof)
    monkeypatch.setattr(frontier,"compile_fabrication_frontier",changed)
    report = run(source,max_fittings=2)
    assert report["frontier_check"]["status"] == "FAIL"
    assert_fallback(report)


@pytest.mark.parametrize("budget",[{"max_frontier_states":1},{"max_frontier_work":1}])
def test_optional_product_budget_exhaustion_preserves_unrestricted_fallback(source,budget):
    report = run(source,max_fittings=2,**budget)
    assert report["frontier_check"]["status"] == "UNKNOWN"
    assert "frontier" not in report["frontier_certificate"]
    assert_fallback(report)


@pytest.mark.parametrize("elapsed,status",[(4.,"CHECKED_FABRICATION_PROPOSALS"),(31.,"UNKNOWN")])
def test_frontier_local_deadline_retains_fallback_global_deadline_publishes_none(source,monkeypatch,elapsed,status):
    clock = [0.]
    monkeypatch.setattr(certified_fabrication.time,"monotonic",lambda:clock[0])
    def checkpoint(stage):
        if stage == "fabrication_frontier_expand":
            clock[0] = elapsed
    report = run(source,max_fittings=2,deadline=30.,checkpoint=checkpoint)
    assert report["status"] == status
    if status == "UNKNOWN":
        assert not report["proposals"] and report["reason"] == "FABRICATION_SEARCH_DEADLINE"
    else:
        assert report["frontier_check"]["reason"] == "FABRICATION_FRONTIER_DEADLINE"
        assert_fallback(report)


@pytest.mark.parametrize("stage",["fabrication_frontier_expand","fabrication_frontier_independent_replay","fabrication_frontier_conversion_checked"])
@pytest.mark.parametrize("kind",[ValueError,TimeoutError,certified_fabrication._FrontierDeadline])
def test_external_cancellation_identity_never_becomes_optional_fallback(source,stage,kind):
    signal = kind("external stop")
    def stop(observed):
        if observed == stage:
            raise signal
    with pytest.raises(kind) as caught:
        run(source,max_fittings=2,checkpoint=stop)
    assert caught.value is signal


def test_source_mutation_during_frontier_replay_publishes_no_path(source):
    path = source[0]["path"]
    original = path.read_bytes()
    def mutate(stage):
        if stage == "fabrication_frontier_independent_replay":
            path.write_bytes(original+b"\n")
    try:
        report = run(source,max_fittings=2,checkpoint=mutate)
        assert report["status"] == "BLOCKED" and "source bytes changed" in report["reason"].lower()
        assert not report["proposals"]
    finally:
        path.write_bytes(original)


def test_executable_change_after_frontier_proof_publishes_none(source,monkeypatch):
    def mutate(stage):
        if stage == "fabrication_frontier_independent_replay":
            monkeypatch.setattr(certified_fabrication,"checker_version",lambda:"changed-build")
    report = run(source,max_fittings=2,checkpoint=mutate)
    assert report["status"] == "BLOCKED" and "implementation changed" in report["reason"]
    assert not report["proposals"]


@pytest.mark.parametrize("field",["count","verdict"])
def test_binary64_correspondence_is_fresh_and_exact_count_guarded(source,monkeypatch,field):
    real = certified_fabrication.verify_orthogonal_fabrication
    frontier_phase = [False]
    calls = []
    def checkpoint(stage):
        if stage == "fabrication_frontier_conversion":
            frontier_phase[0] = True
    def changed(*a,**kw):
        result = real(*a,**kw)
        if frontier_phase[0]:
            calls.append(result["transitions_checked"])
            if field == "count":
                result["transitions_checked"] += 1
            else:
                result["fabrication_status"] = "UNKNOWN"
        return result
    monkeypatch.setattr(certified_fabrication,"verify_orthogonal_fabrication",changed)
    report = run(source,max_fittings=2,checkpoint=checkpoint)
    assert calls == [1,2]
    assert report["frontier_check"]["status"] == "PASS"
    assert [r["status"] for r in report["frontier_conversions"]] == ["NO_PATH_AT_EXACT_COUNT", "BINARY64_FABRICATION_UNRESOLVED", "BINARY64_FABRICATION_UNRESOLVED"]
    assert_fallback(report)


def test_output_limit_retains_low_count_and_records_unconverted_optimum(source):
    report = run(source,max_fittings=2,max_frontier_proposals=1)
    assert report["frontier_check"]["reachable_counts"] == [1,2]
    assert [p["exact_fittings"] for p in options(report)] == [1]
    assert report["frontier_conversions"][2]["status"] == "OUTPUT_LIMIT_NOT_CONVERTED"
    assert not report["frontier_output_policy"]["complete_cartesian_route_universe"]


def test_zero_budget_does_not_claim_a_nonzero_fallback_is_feasible(source):
    report = run(source,max_fittings=0)
    assert report["frontier_check"]["counts_checked"] == 1
    assert report["frontier_check"]["reachable_counts"] == []
    assert_fallback(report)
    s = scenario().model_copy(update={"end":(14.,10.,1.)})
    straight = run(source,s,max_fittings=0)
    assert straight["frontier_check"]["reachable_counts"] == [0]
    assert options(straight)[0]["exact_fittings"] == 0
    assert options(straight)[0]["points_m"] == [list(s.start),list(s.end)]


@pytest.mark.parametrize("maximum",[33,1024])
def test_large_declared_budget_binds_full_value_but_represents_only_zero_through_32(source,maximum):
    report = run(source,max_fittings=maximum,max_frontier_work=1)
    assert report["frontier_check"]["status"] == "UNKNOWN"
    assert report["fitting_budget"]["represented_count_cap"] == 32
    assert report["fitting_budget"]["declared_max_new_fittings"] == maximum
    assert not report["fitting_budget"]["requested_count_domain_within_kernel_cap"]
    assert report["model"]["source_roots"]["fitting_budget"] == digest(report["fitting_budget"])
    assert_fallback(report)


@pytest.mark.parametrize("maximum",[float("nan"),float("inf"),-1,1025,True,"2"])
def test_invalid_declared_count_never_enters_frontier(source,maximum,monkeypatch):
    monkeypatch.setattr(frontier,"compile_fabrication_frontier",lambda *a,**kw:pytest.fail("invalid count reached product graph"))
    report = run(source,max_fittings=maximum)
    assert report["status"] == "BLOCKED" and not report["proposals"]


@pytest.mark.parametrize("seconds",[float("nan"),float("inf"),0,-1,11,True])
def test_invalid_phase_duration_is_rejected(source,seconds):
    report = run(source,max_fittings=2,max_frontier_seconds=seconds)
    assert report["status"] == "BLOCKED" and not report["proposals"]


def test_none_preserves_existing_model_and_proposal_fields(source,monkeypatch):
    monkeypatch.setattr(frontier,"compile_fabrication_frontier",lambda *a,**kw:pytest.fail("None started frontier"))
    omitted = run(source)
    explicit = run(source,max_fittings=None)
    assert omitted["model"] == explicit["model"] and omitted["model_root"] == explicit["model_root"]
    assert omitted["proposals"] == explicit["proposals"]
    assert not any(k.startswith("frontier") or k == "fitting_budget" for k in explicit)
    assert "fitting_budget" not in explicit["model"]["source_roots"]


def test_pipeline_binds_mission_and_persists_exact_count_proof_fields(tmp_path,monkeypatch):
    from oma.routing.proposals import project_proposals
    from test_project_proposals import setup
    store,initial,s = setup(tmp_path)
    run = store.create_run(initial["project_id"],{"operation":"route_joint","mission":{"max_new_fittings":2}})
    report = {"status":"UNKNOWN","proposals":[],"coverage_check":{"status":"PASS"},"timing":{}}
    monkeypatch.setattr(certified_cells,"build_certified_cell_proposals",lambda *a,**kw:deepcopy(report))
    frontier_path = [list(s.start),[-1.,-1.,1.],[3.,-1.,1.],list(s.end)]
    item = {"points_m":frontier_path,"rationale":"synthetic protocol fixture",
        "geometry_scope":"NOMINAL_ONLY","path_certificate_kind":"FABRICATION_FRONTIER",
        "path_certificate_root":"proof","binary64_fabrication_certificate_root":"binary-proof",
        "nominal_graph_optimality":False,"exact_fittings":2,"frontier_certificate_root":"proof",
        "frontier_entry_root":"entry","frontier_count_domain_root":"domain","nominal_exact_count_optimality":True,
        "binary64_exact_fittings":2,"shared_native_budget_feasibility":"NOT_CHECKED"}
    seen = []
    def adapter(*args,**kwargs):
        seen.append(kwargs)
        return {"status":"CHECKED_FABRICATION_PROPOSALS","proposals":[item],"model_root":"model",
            "coverage":{},"frontier_check":{"status":"PASS"},"fitting_budget":{"declared_max_new_fittings":2},"timing":{}}
    monkeypatch.setattr(certified_fabrication,"build_certified_fabrication_proposals",adapter)
    paths = list(project_proposals(store,run,{"sources":[]},s,[],deadline=time.monotonic()+60,
        checkpoint=lambda stage:None,on_search=lambda event:None,max_fittings=2))
    assert seen[0]["max_fittings"] == 2
    chosen = next(p for p in paths if p.get("path_certificate_kind") == "FABRICATION_FRONTIER")
    evidence = chosen["geometry_evidence"]
    for key in ("exact_fittings","frontier_certificate_root","frontier_entry_root","frontier_count_domain_root",
                "nominal_exact_count_optimality","binary64_exact_fittings","shared_native_budget_feasibility"):
        assert evidence[key] == item[key]
    artifact = store.get(evidence["report_root"])
    assert artifact["context"]["max_new_fittings"] == 2
    assert artifact["context"]["request_root"] == digest(run["request"])
    event = next(e for e in store.events(run["project_id"]) if e["stage"] == "fabrication_graph")
    assert event["payload"]["frontier"]["status"] == "PASS"
    assert event["payload"]["fitting_budget"]["declared_max_new_fittings"] == 2
    assert not evidence["route_acceptance"]


@pytest.mark.parametrize("budget",[0,2,float("nan"),True])
def test_pipeline_rejects_mismatched_or_invalid_budget_before_direct_proposal(tmp_path,budget):
    from oma.routing.proposals import project_proposals
    from test_project_proposals import setup
    store,run,s = setup(tmp_path)
    gen = project_proposals(store,run,{"sources":[]},s,[],deadline=time.monotonic()+30,
        checkpoint=lambda stage:None,on_search=lambda event:None,max_fittings=budget)
    with pytest.raises(ValueError):
        next(gen)
