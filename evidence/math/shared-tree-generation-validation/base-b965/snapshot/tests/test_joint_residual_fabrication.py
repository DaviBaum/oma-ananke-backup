"""Actual frozen joint mission recovered by a residual same-count graph option."""
from copy import deepcopy
from fractions import Fraction
import json
from pathlib import Path
import sys

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'tests/test_ifc_pipeline.py').is_file())
sys.path.insert(0,str(ROOT/'tests'))

from oma.build_identity import checker_version
from oma.exporting import export_project
from oma.ifc.audit import sha256_file
from oma.optimization.fabrication_alternatives import verify_fabrication_alternatives
from oma.routing.engine import route_project_run
from oma.store import Store,digest
from oma.worker import WorkerControl,import_sources
from test_ifc_pipeline import make_fixture


def mission():
    main={'start':[-1.,.5,1.],'end':[3.,.5,1.],'system_type':'PRESSURE_PIPE',
        'diameter_m':.25,'insulation_m':0.,'bend_radius_m':.5,'minimum_straight_m':.125,'clearance_m':.125,
        'allowed_zone':{'min':[-2.,-2.,.8],'max':[4.,5.,1.2]},'scenario_terminals':True,'max_candidates':3,
        'objective_weights':{'length_m':1.,'fitting_count':0.}}
    competing={**deepcopy(main),'start':[1.,-1.875,.5],'end':[1.,-1.875,1.5],
        'allowed_zone':{'min':[-2.,-3.,0.],'max':[4.,5.,2.]},'max_candidates':1}
    return {'route_demands':[{'id':'wall-detour','alternatives':[main]}, {'id':'fixed-competing-route','alternatives':[competing]}],
        'max_new_fittings':2,'max_joint_candidates':3,'max_paths_per_alternative':3}


def native_joint_residual_case(directory):
    directory.mkdir(parents=True,exist_ok=True)
    declared=mission();request_hash=digest(declared)
    (directory/'declared-mission.json').write_text(json.dumps(declared,indent=2),encoding='utf8')
    source=make_fixture(directory/'source.ifc');source_hash=sha256_file(source)
    store=Store(directory/'store')
    project=store.create_project('Same-count residual joint geometry',{'sources':[],'entities':[]})
    imported=store.create_run(project['id'],{'operation':'import','paths':[str(source)]})
    import_sources(store,imported,WorkerControl(store,imported['id']))
    run=store.create_run(project['id'],{'operation':'optimize','mission':declared,'budget_seconds':120})
    (directory/'initial-run.json').write_text(json.dumps(run,indent=2),encoding='utf8')
    route_project_run(store,run,WorkerControl(store,run['id']))
    candidates=[c for c in store.candidates(project['id']) if c['run_id']==run['id']]
    events=store.events(project['id'],limit=1000)
    diagnostic={'checker_version':checker_version(),'run':store.run(run['id']),'candidates':[],
        'geometry_artifacts':[store.get(e['artifacts'][0]) for e in events if e['stage']=='fabrication_graph' and e['artifacts']]}
    for candidate in candidates:
        state=store.get(candidate['state_root'])
        diagnostic['candidates'].append({'candidate':candidate,'state':state,'report':store.get(candidate['report_root']) if candidate['report_root'] else None})
    (directory/'search-diagnostic.json').write_text(json.dumps(diagnostic,indent=2),encoding='utf8')
    assert len(candidates)==3,[(c['status'],c.get('proposal_evidence')) for c in candidates]
    checked=[c for c in candidates if c['status']=='CHECKED']
    assert len(checked)==1,[(c['status'],store.get(c['report_root']) if c['report_root'] else None) for c in candidates]
    chosen=checked[0];state=store.get(chosen['state_root']);report=store.get(chosen['report_root'])
    assert report['status']=='PASS' and all(r['status'] in {'PASS','NOT_APPLICABLE'} for r in report['results'])
    assert store.run(run['id'])['status']=='COMPLETED'
    final=next(e for e in reversed(events) if e['run_id']==run['id'] and e['stage']=='complete')
    assert final['payload']['selected_candidate_ids']==[chosen['id']]
    evidence_by_route=state['derived_artifacts']['route_proposal_evidence_by_route']
    residual=[(rid,e) for rid,e in evidence_by_route.items() if e.get('path_certificate_kind')=='FABRICATION_RESIDUAL_FRONTIER']
    assert len(residual)==1,evidence_by_route
    rid,evidence=residual[0]
    route=next(r for r in state['routes'] if r['id']==rid)
    artifact=store.get(evidence['report_root']);result=artifact['report'];round_=result['residual_round']
    assert artifact['context']['request_root']==digest(run['request']) and artifact['context']['request_demand_id']=='wall-detour'
    assert artifact['context']['base_root']==run['base_root'] and artifact['context']['executable_version']==checker_version()
    assert round_['status']=='CHECKED_RESIDUAL_PROPOSALS' and round_['independent_check']['status']=='PASS'
    words=round_['generation_ledger']['excluded_words'];certificate=round_['certificate'];entry=certificate['frontier'][2]
    independent=verify_fabrication_alternatives(result['model'],result['pricing_objective'],2,words,certificate)
    assert independent['status']=='PASS',independent
    assert [[float(Fraction(x)) for x in p] for p in entry['points_m']]==route['points_m']
    assert evidence['residual_entry_root']==digest(entry) and evidence['residual_certificate_root']==digest(certificate)
    assert evidence['generation_ledger_root']==digest(round_['generation_ledger'])
    original=result['frontier_certificate']['frontier'][2]
    assert Fraction(original['cost'][0])<Fraction(entry['cost'][0]) and original['cost'][1]==entry['cost'][1]
    assert [s[:7] for s in entry['path_states']] not in words and original['path_states'] in words
    rows={r['id']:r for r in report['results']}
    assert rows['joint-new-fitting-budget']['status']=='PASS'
    assert rows['joint-new-fitting-budget']['witness']['count']==2
    assert rows['joint-new-fitting-budget']['witness']['count_complete'] is True
    assert sorted(rows['joint-new-fitting-budget']['witness']['per_new_route'].values())==[0,2]
    assert rows['cross-route-interference']['status']=='PASS'
    assert rows['cross-route-interference']['witness']=={'complete_component_coverage':True,'findings':[],'pairs_accounted':5}
    native_reports=[]
    for route in state['routes']:
        native=store.get(rows[route['id']+':physical-interference-and-clearance']['witness']['artifact'])
        assert native['coordination_status']=='PASS' and native['self_interference_status']=='PASS'
        assert native['obstacle_count']==1 and native['pairs_accounted']==native['route_count']
        native_reports.append(native)
        proof=rows[route['id']+':nominal-fabrication-witness-integrity']
        assert proof['status']=='PASS' and proof['witness']['origin_run_id']==run['id']
        assert proof['witness']['producer_check_reused'] is False
    assert sorted(n['pairs_accounted'] for n in native_reports)==[1,5]
    rejected_minimum=next(c for c in candidates if c['status']=='REJECTED' and any(e.get('path_certificate_kind')=='FABRICATION_FRONTIER' for e in c.get('proposal_evidence',{}).values()))
    failed=store.get(rejected_minimum['report_root'])
    failure=next(r for r in failed['results'] if r['id']=='cross-route-interference')
    assert failure['status']=='FAIL' and failure['witness']['pairs_accounted']==5
    assert any(p['status']=='FAIL' and p.get('common_volume_m3',0)>0 for p in failure['witness']['findings'])
    before_revision=store.project(project['id'])['revision']
    store.accept(project['id'],chosen['id'],before_revision,'accept-residual-same-count',checker_version=checker_version())
    assert store.project(project['id'])['revision']==before_revision+1
    assert store.project(project['id'])['state_root']==chosen['state_root']
    export=export_project(store,project['id'],chosen['id'],draft=False,budget_seconds=120)
    assert export['status']=='CHECKED_LOCAL_SCOPE' and export['round_trip']=='PASS'
    exported_report=json.loads((Path(export['directory'])/'verification.json').read_text(encoding='utf8'))
    assert exported_report['status']=='PASS' and all(r['status'] in {'PASS','NOT_APPLICABLE'} for r in exported_report['results'])
    assert exported_report['candidate_root']!=report['candidate_root']
    exported_rows={r['id']:r for r in exported_report['results']}
    assert exported_rows['cross-route-interference']['witness']=={'complete_component_coverage':True,'findings':[],'pairs_accounted':5}
    assert exported_rows['joint-new-fitting-budget']['witness']['count']==2
    exported_native=[]
    for route in state['routes']:
        native=store.get(exported_rows[route['id']+':physical-interference-and-clearance']['witness']['artifact'])
        assert native['coordination_status']==native['self_interference_status']=='PASS'
        assert native['obstacle_count']==1 and native['pairs_accounted']==native['route_count']
        exported_native.append(native)
        proof=exported_rows[route['id']+':nominal-fabrication-witness-integrity']['witness']
        assert proof['origin_run_id']==run['id'] and proof['producer_check_reused'] is False
    assert sorted(n['pairs_accounted'] for n in exported_native)==[1,5]
    exported_state=store.get(exported_report['candidate_root'])
    assert exported_state['derived_artifacts']['route_proposal_evidence_by_route']==evidence_by_route
    assert exported_state['derived_artifacts']['fabrication_evidence_by_route']==state['derived_artifacts']['fabrication_evidence_by_route']
    assert len(export['files'])==1 and export['files'][0]['changed']
    assert sha256_file(source)==source_hash and digest(store.run(run['id'])['request']['mission'])==request_hash
    result={'status':'PASS','build':checker_version(),'mission_root':request_hash,'source_sha256':source_hash,
        'run_id':run['id'],'selected_candidate_id':chosen['id'],'selected_candidate_root':chosen['state_root'],
        'initial_minimum_rejected_candidate_id':rejected_minimum['id'],'initial_nominal_cost':original['cost'],'residual_nominal_cost':entry['cost'],
        'selected_proof_reference':evidence,'independent_residual_replay':independent,'complete_native_report':report,
        'initial_cross_route_failure':failure,'source_pair_denominators':[n['pairs_accounted'] for n in native_reports],
        'fresh_export_source_pair_denominators':[n['pairs_accounted'] for n in exported_native],
        'acceptance_revision':store.project(project['id'])['revision'],'export':export,'fresh_exported_report':exported_report,
        'original_source_unchanged':True,'original_mission_unchanged':True,'production_modules_stubbed':False,
        'physical_global_optimality':False,'whole_building_adequacy':False}
    (directory/'result.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    return result


def test_actual_joint_selection_acceptance_and_export_uses_same_count_residual_path(tmp_path):
    result=native_joint_residual_case(tmp_path)
    assert result['status']=='PASS'
