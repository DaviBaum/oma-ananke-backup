"""Independent current IFC/resource binding attacks; no optimizer score authority."""
from copy import deepcopy
from pathlib import Path

import ifcopenshell
import pytest

from oma.routing.fitting_budget import SCHEMA, check_joint_fitting_budget, joint_rule_hash


@pytest.fixture(scope="module")
def straight_budget_case(tmp_path_factory):
    from test_joint_negative_hint_adversarial import _native_candidate
    from oma.routing.checker import evaluate_route_state
    from oma.routing.scenario import RoutingScenario
    from oma.worker import WorkerControl
    case = _native_candidate(tmp_path_factory.mktemp("fitting-budget-audit")/"straight",crossing=False)
    store, state, baseline = case["store"], deepcopy(case["state"]), case["baseline"]
    request = deepcopy(case["run"]["request"])
    request["mission"]["max_new_fittings"] = 0
    run = store.create_run(state["project_id"],request)
    state["derived_artifacts"]["joint_fitting_budget"] = {"schema":SCHEMA,"max_new_fittings":0}
    contracts = state["derived_artifacts"]["routing_contracts"]
    state["mission"]["rule_hash"] = joint_rule_hash([contracts[r]["mission"] for r in sorted(contracts)],0)
    guids = {p["ifc_guid"] for m in case["materialized"].values() for p in m["added_parts"]}
    results = {}
    for route in state["routes"]:
        rid = route["id"]
        contract = contracts[rid]
        scenario = RoutingScenario.model_validate(contract["scenario"])
        records, _, _ = evaluate_route_state(store,state,baseline,scenario,scenario,contract["mission"],
            store.get(route["geometry_artifact"]),[rid],WorkerControl(store,run["id"]),
            candidate_run=run,known_physical_guids=guids)
        results[rid] = [r.model_dump(mode="json") for r in records]
    report = check_joint_fitting_budget(store,state,baseline,results,candidate_run=run)
    assert report.status == "PASS", report.model_dump(mode="json")
    assert report.witness["count"] == 0 and report.witness["count_complete"]
    return {**case,"state":state,"run":run,"per_route":results}


def _check(case, *, state=None, per_route=None, checkpoint=None):
    return check_joint_fitting_budget(case["store"],case["state"] if state is None else state,
        case["baseline"],case["per_route"] if per_route is None else per_route,
        candidate_run=case["run"],checkpoint=checkpoint)


@pytest.mark.parametrize("field",["changed_budget","omitted_budget","boolean_budget","rule_hash","duplicate_route",
    "missing_route","missing_evidence","duplicate_evidence","missing_prerequisite","unknown_native"])
def test_current_budget_and_complete_route_evidence_cannot_be_weakened(straight_budget_case,field):
    case=straight_budget_case
    state, checks=deepcopy(case["state"]),deepcopy(case["per_route"])
    rid=state["routes"][0]["id"]
    if field=="changed_budget":
        state["derived_artifacts"]["joint_fitting_budget"]["max_new_fittings"]=1
    elif field=="omitted_budget":
        del state["derived_artifacts"]["joint_fitting_budget"]
    elif field=="boolean_budget":
        state["derived_artifacts"]["joint_fitting_budget"]["max_new_fittings"]=False
    elif field=="rule_hash":
        contracts=state["derived_artifacts"]["routing_contracts"]
        state["mission"]["rule_hash"]=joint_rule_hash([contracts[r]["mission"] for r in sorted(contracts)],None)
    elif field=="duplicate_route":state["routes"].append(deepcopy(state["routes"][0]))
    elif field=="missing_route":state["routes"].pop()
    elif field=="missing_evidence":checks.pop(rid)
    elif field=="duplicate_evidence":checks[rid].append(deepcopy(checks[rid][0]))
    elif field=="missing_prerequisite":checks[rid]=[r for r in checks[rid] if r["id"]!="physical-port-body-attachment"]
    else:next(r for r in checks[rid] if r["id"]=="physical-interference-and-clearance")["status"]="UNKNOWN"
    report=_check(case,state=state,per_route=checks)
    assert report.status not in {"PASS","NOT_APPLICABLE"}, report.model_dump(mode="json")
    assert not report.witness["count_complete"]


@pytest.mark.parametrize("fault",["duplicate_guid","wrong_route_owner","permuted_index","missing_part","wrong_step"])
def test_part_ownership_and_current_physical_denominator_are_bound(straight_budget_case,fault):
    case=straight_budget_case
    state=deepcopy(case["state"])
    route=state["routes"][0]
    material=case["store"].get(route["geometry_artifact"])
    part=material["added_parts"][0]
    if fault=="duplicate_guid":material["added_parts"].append(deepcopy(part))
    elif fault=="wrong_route_owner":part["route_id"]="another-route"
    elif fault=="permuted_index":part["part_index"]=1
    elif fault=="missing_part":material["added_parts"]=[]
    else:part["step_id"]+=1
    route["geometry_artifact"]=case["store"].put(material)
    report=_check(case,state=state)
    assert report.status!="PASS",report.model_dump(mode="json")
    assert not report.witness["count_complete"]


@pytest.mark.parametrize("count",[1,True,-1,0.0])
def test_old_or_noninteger_semantic_count_cannot_replace_current_ifc_interpretation(straight_budget_case,count):
    case=straight_budget_case
    checks=deepcopy(case["per_route"])
    rid=case["state"]["routes"][0]["id"]
    semantic=next(r for r in checks[rid] if r["id"]=="exported-physical-semantics")
    semantic["witness"]["recomputed"]["fitting_count"]=count
    report=_check(case,per_route=checks)
    assert report.status!="PASS",report.model_dump(mode="json")
    assert not report.witness["count_complete"]


def test_native_count_parser_only_opens_copied_bound_bytes(straight_budget_case,monkeypatch):
    case=straight_budget_case
    actual_open=ifcopenshell.open
    public={str(case["store"].resolve_path(m["export_path"]).resolve()) for m in case["materialized"].values()}
    opened=[]
    def guarded_open(path,*args,**kwargs):
        resolved=str(Path(path).resolve())
        assert resolved not in public,"Resource parser reopened a mutable public export path"
        opened.append(resolved)
        return actual_open(path,*args,**kwargs)
    monkeypatch.setattr(ifcopenshell,"open",guarded_open)
    report=_check(case)
    assert report.status=="PASS" and opened


@pytest.mark.parametrize("target",["source","export"])
def test_input_changed_after_native_interpretation_removes_count_authority(straight_budget_case,target):
    case=straight_budget_case
    material=next(iter(case["materialized"].values()))
    path=case["store"].resolve_path(case["state"]["sources"][0]["immutable_path"] if target=="source" else material["export_path"])
    original=path.read_bytes()
    changed=[]
    def checkpoint(stage):
        if stage=="joint_fitting_final_input" and not changed:
            path.write_bytes(original+b"\n")
            changed.append(True)
    try:
        report=_check(case,checkpoint=checkpoint)
    finally:
        path.write_bytes(original)
    assert changed and report.status=="FAIL",report.model_dump(mode="json")
    assert not report.witness["count_complete"]


def test_source_changed_while_paused_at_final_checkpoint_cannot_keep_current_count_pass(straight_budget_case):
    case=straight_budget_case
    path=case["store"].resolve_path(case["state"]["sources"][0]["immutable_path"])
    original=path.read_bytes()
    changed=[]
    def checkpoint(stage):
        if stage=="joint_fitting_complete":
            path.write_bytes(original+b"\n")
            changed.append(True)
    try:
        report=_check(case,checkpoint=checkpoint)
        current=path.read_bytes()
    finally:
        path.write_bytes(original)
    assert changed and current!=original
    assert report.status!="PASS",report.model_dump(mode="json")


def test_complete_joint_report_rejects_source_changed_at_final_fitting_pause(tmp_path,monkeypatch):
    import uuid
    from test_joint_fitting_budget import _native_budget_candidate
    from oma.ifc.audit import atomic_json,sha256_file
    from oma.routing.joint_checker import verify_joint_candidate
    from oma.worker import WorkerControl
    case=_native_budget_candidate(tmp_path/"actual",kinds=("long","short"),budget=6)
    assert case["report"].status=="PASS",case["report"].model_dump(mode="json")
    store=case["store"]
    candidate=store.add_candidate(case["run"]["id"],case["state"],{"kind":"physical_route_set","changed_ids":case["new_ids"]})
    source=store.resolve_path(case["state"]["sources"][0]["immutable_path"])
    original=source.read_bytes()
    original_checkpoint=WorkerControl.checkpoint
    changed=[]
    def pause_boundary(self,stage="compute"):
        original_checkpoint(self,stage)
        if stage=="joint_fitting_complete" and not changed:
            source.write_bytes(original+b"\n")
            changed.append(True)
    monkeypatch.setattr(WorkerControl,"checkpoint",pause_boundary)
    try:
        report=verify_joint_candidate(store,candidate["id"])
        altered=source.read_bytes()
        current_sha=sha256_file(source)
    finally:
        source.write_bytes(original)
    assert changed and altered!=original
    evidence=Path("evidence/release/joint-fitting-budget-audit")/uuid.uuid4().hex
    evidence.mkdir(parents=True)
    (evidence/"declared-source.ifc").write_bytes(original)
    (evidence/"source-after-pause.ifc").write_bytes(altered)
    atomic_json(evidence/"result.json",{"case":"SOURCE_MUTATION_AT_FINAL_FITTING_PAUSE","checker_version":report.checker_version,
        "declared_source_sha256":case["state"]["sources"][0]["sha256"],"current_source_sha256_at_publication":current_sha,
        "actual_native_baseline_report":case["report"].model_dump(mode="json"),"after_pause_full_report":report.model_dump(mode="json"),
        "candidate_status_at_publication":store.candidate(candidate["id"])["status"],"original_restored":sha256_file(source)==case["state"]["sources"][0]["sha256"]})
    assert report.status!="PASS",report.model_dump(mode="json")


@pytest.fixture(scope="module")
def bent_budget_case(tmp_path_factory):
    from test_joint_fitting_budget import _native_budget_candidate
    case=_native_budget_candidate(tmp_path_factory.mktemp("bent-fitting-audit")/"native",budget=6)
    assert case["report"].status=="PASS",case["report"].model_dump(mode="json")
    return {**case,"per_route":case["per_route_results"]}


@pytest.mark.parametrize("field,value",[("angle_rad",float("nan")),("angle_rad",float("inf")),
    ("angle_rad",1e-12),("angle_rad",1.2),("length_m",float("nan")),("length_m",-1),
    ("radius_m",float("nan")),("radius_m",1e-12),("kind","tee"),("kind","segment")])
def test_corrupt_current_native_component_interpretation_never_certifies_budget(bent_budget_case,monkeypatch,field,value):
    from oma.ifc import network_semantics
    original=network_semantics.read_component_geometry
    changed=[]
    def corrupted(model,element):
        actual=original(model,element)
        if actual["kind"]=="elbow":
            actual={**actual,field:value}
            changed.append(element.GlobalId)
        return actual
    monkeypatch.setattr(network_semantics,"read_component_geometry",corrupted)
    report=_check(bent_budget_case)
    assert changed and report.status!="PASS",report.model_dump(mode="json")
    if field in {"length_m","radius_m"} and (value != value or value <= 0):
        assert report.status == "UNKNOWN", report.model_dump(mode="json")
    assert not report.witness["count_complete"] and report.witness["count"] is None


def test_final_request_mutation_cannot_rebind_a_completed_count(bent_budget_case):
    from oma.store import canonical
    case=bent_budget_case
    store=case["store"]
    original=deepcopy(case["run"]["request"])
    altered=deepcopy(original)
    altered["mission"]["max_new_fittings"]=8
    def checkpoint(stage):
        if stage=="joint_fitting_complete":
            with store.transaction() as db:
                db.execute("UPDATE runs SET request=? WHERE id=?",(canonical(altered).decode(),case["run"]["id"]))
    try:
        report=_check(case,checkpoint=checkpoint)
    finally:
        with store.transaction() as db:
            db.execute("UPDATE runs SET request=? WHERE id=?",(canonical(original).decode(),case["run"]["id"]))
    assert report.status=="FAIL" and not report.witness["count_complete"],report.model_dump(mode="json")


def test_restored_budgeted_state_rechecks_and_unbudgeted_increment_does_not_inherit_limit(tmp_path):
    from test_joint_fitting_budget import _native_budget_candidate
    from oma.backup import restore_store
    from oma.build_identity import checker_version
    from oma.routing.joint_checker import verify_joint_candidate
    from oma.routing.engine import route_project_run
    from oma.worker import WorkerControl
    old=_native_budget_candidate(tmp_path/"original",kinds=("long","long"),budget=4)
    store=old["store"]
    project=old["run"]["project_id"]
    assert old["report"].status=="PASS",old["report"].model_dump(mode="json")
    store.accept(project,old["candidate"]["id"],1,"accept-budgeted-before-relocation",checker_version=checker_version())
    old_root=store.project(project)["state_root"]
    backup=store.backup(tmp_path/"backup")
    store.directory.rename(tmp_path/"old-store-unavailable")
    restored=restore_store(backup,tmp_path/"restored")
    assert restored.project(project)["state_root"]==old_root
    report=verify_joint_candidate(restored,old["candidate"]["id"])
    assert report.status=="PASS",report.model_dump(mode="json")
    resource=next(r for r in report.results if r.id=="joint-new-fitting-budget")
    assert resource.witness["count"]==4 and resource.witness["count_complete"]
    scenario=next(iter(old["scenarios"].values())).model_dump(mode="json")
    scenario.update(start=[-1.,4.5,3.],end=[3.,4.5,3.],max_candidates=1)
    request={"route_demands":[{"id":"unbudgeted-new-straight","alternatives":[scenario]}],
        "max_joint_candidates":1,"max_paths_per_alternative":1}
    run=restored.create_run(project,{"operation":"route","mission":request,"budget_seconds":60})
    route_project_run(restored,run,WorkerControl(restored,run["id"]))
    candidates=[c for c in restored.candidates(project) if c["run_id"]==run["id"]]
    assert len(candidates)==1,candidates
    candidate=candidates[0]
    assert candidate["status"]=="CHECKED",restored.get(candidate["report_root"])
    state=restored.get(candidate["state_root"])
    assert "joint_fitting_budget" not in state["derived_artifacts"]
    assert "max_new_fittings" not in restored.run(run["id"])["request"]["mission"]
    checked=restored.get(candidate["report_root"])
    assert checked["objective"]["fitting_count"]==4
    assert len(state["routes"])==3 and set(old["new_ids"])<={r["id"] for r in state["routes"]}
    assert not any(r["id"]=="joint-new-fitting-budget" and r["status"]!="NOT_APPLICABLE" for r in checked["results"])
    assert restored.project(project)["state_root"]==old_root
