"""Run one predeclared Office common-tee mission in a new isolated Store."""
from __future__ import annotations
import argparse
from copy import deepcopy
from itertools import combinations
import json
import os
from pathlib import Path
import shutil
import sys
import time
import traceback
import uuid

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').is_file())
STAGE=ROOT/'.oma/development/passive-native-tree'
sys.path.insert(0,str(STAGE/'scripts'))
sys.path.insert(0,str(ROOT/'.oma/development/next-best-fabrication/scripts'))
from prepare_office_three_sink import Original, PRIOR_RUN, PRIOR_CANDIDATE
from office_residual_budget_campaign import copy_baseline, seed_native_cache
from oma.build_identity import checker_version
from oma.export_checks import supervise_check
from oma.exporting import export_project
from oma.ifc.audit import atomic_json, sha256_file
from oma.routing.network_scenario import SharedNetworkScenario
from oma.store import Store, digest


def collect(store,candidate,output,prefix):
    state=store.get(candidate['state_root'])
    atomic_json(output/(prefix+'.candidate.json'),candidate)
    atomic_json(output/(prefix+'.state.json'),state)
    result={'candidate_id':candidate['id'],'state_root':candidate['state_root'],
        'status':candidate['status'],'report_root':candidate.get('report_root')}
    materials=[]
    for network in state.get('physical_networks',[]):
        material=store.get(network['geometry_artifact'])
        atomic_json(output/(prefix+'.materialization.json'),material)
        source=store.resolve_path(material['export_path'])
        assert sha256_file(source)==material['export_sha256']
        target=output/'actual-ifcs'/(prefix+'.ifc');target.parent.mkdir(exist_ok=True)
        shutil.copyfile(source,target);assert sha256_file(target)==material['export_sha256']
        materials.append({'path':str(target.relative_to(output)),'sha256':material['export_sha256'],
            'materialization_root':network['geometry_artifact']})
    result['actual_ifcs']=materials
    if not candidate.get('report_root'):return result
    report=store.get(candidate['report_root'])
    atomic_json(output/(prefix+'.report.json'),report)
    assert report['candidate_root']==candidate['state_root'] and report['checker_version']==checker_version()
    rows={r['id']:r for r in report['results']};assert len(rows)==len(report['results'])
    result.update(report_status=report['status'],objective=report['objective'],
        checks={key:r['status'] for key,r in rows.items()})
    artifacts={}
    for row in report['results']:
        root=(row.get('witness') or {}).get('artifact')
        if root:
            value=store.get(root);atomic_json(output/(root+'.artifact.json'),value)
            artifacts[row['id']]=value
    if rows.get('network-all-source-clearance',{}).get('status')=='PASS':
        cad=artifacts['network-all-source-clearance'];semantics=artifacts['network-native-semantics']
        parts=semantics['parts'];guids=[p['ifc_guid'] for p in parts];cids=[p['component_id'] for p in parts]
        assert len(parts)==len(set(guids))==len(set(cids))==7
        assert semantics['physical_ports']==len(semantics['ports'])==16
        assert cad['route_count']==7 and cad['obstacle_count']==803 and cad['pairs_accounted']==5621
        assert cad['coordination_status']==cad['self_interference_status']=='PASS'
        assert not any(cad[k] for k in ('failed_pairs','unknown_pairs','blocked_pairs'))
        pairs=cad['self_pair_results'];assert len(pairs)==21 and all(p['status']=='PASS' for p in pairs)
        assert {frozenset(p['participant_guids']) for p in pairs}=={frozenset(p) for p in combinations(guids,2)}
        assert len(cad['route_guids'])==7 and set(cad['route_guids'])==set(guids)
        assert sorted(s['sha256'] for s in cad['sources'])==sorted(s['sha256'] for s in state['sources'])
        result['native']={'parts':7,'ports':16,'source_obstacles':803,'source_pairs':5621,'self_pairs':21,
            'component_ids':cids,'part_guids':guids,'self_status':'PASS','source_status':'PASS',
            'native_semantics_root':rows['network-native-semantics']['witness']['artifact'],
            'native_cad_root':rows['network-all-source-clearance']['witness']['artifact']}
    calculation=(rows.get('network-demand-conditioned-service',{}).get('witness') or {}).get('calculation')
    if calculation:
        independent=calculation.get('independent_check',{});service=independent.get('service',{})
        result['pressure']={'status':calculation['status'],'verdict':calculation['verdict'],
            'independent_status':independent.get('status'),'independent_verdict':independent.get('verdict'),
            'model_root':independent.get('model_root'),'deliveries':service.get('deliveries'),
            'physical_ports':service.get('physical_ports'),'conservation_identities':service.get('conservation_identities')}
        atomic_json(output/(prefix+'.pressure-calculation.json'),calculation)
    if candidate['status']=='CHECKED':
        assert report['status']=='PASS' and 'native' in result and calculation is not None
        assert rows['network-pressure-operating-point']['status']==rows['network-demand-conditioned-service']['status']=='PASS'
        assert calculation['proof_complete'] is True and independent['status']==independent['verdict']=='PASS'
        assert len(service['physical_ports'])==16 and len(service['deliveries'])==3 and len(service['conservation_identities'])==17
        assert all(p['forward_status']==p['maximum_velocity_status']=='PASS' for p in service['physical_ports'])
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepared',type=Path,required=True)
    parser.add_argument('--budget-seconds',type=float,default=1200.)
    args=parser.parse_args()
    output=args.prepared.resolve();frozen_path=output/'frozen-mission.json'
    frozen=json.loads(frozen_path.read_text(encoding='utf-8'))
    assert checker_version()==os.environ['OMA_EXECUTABLE_BUILD']==frozen['checker_version']
    mission=frozen['mission'];assert digest(mission)==frozen['mission_root']
    assert SharedNetworkScenario.model_validate(mission).model_dump(mode='json',by_alias=True)==mission
    original=Original();prior=original.run(PRIOR_RUN);head=original.project(prior['project_id']);oldcandidate=original.candidate(PRIOR_CANDIDATE)
    baseline=original.get(frozen['baseline_root']);assert prior['base_root']==frozen['baseline_root']
    assert not baseline.get('routes') and not baseline.get('physical_networks')
    originals={str(original.resolve_path(s['immutable_path'])):s['sha256'] for s in baseline['sources']}
    assert all(sha256_file(Path(p))==sha for p,sha in originals.items())
    store_path=STAGE/'bench-stores'/output.name
    assert not store_path.exists() and not (output/'run-result.json').exists()
    helper_paths=[Path(__file__),STAGE/'scripts/prepare_office_three_sink.py',ROOT/'.oma/development/next-best-fabrication/scripts/office_residual_budget_campaign.py']
    declaration={'schema':'oma.office-three-sink-execution/1','checker_version':checker_version(),
        'frozen_mission_sha256':sha256_file(frozen_path),'mission_root':digest(mission),
        'scripts':{str(p):sha256_file(p) for p in helper_paths},'original_files':originals,
        'prior_run':prior,'prior_candidate':oldcandidate,'original_head':head,
        'store':str(store_path),'worker_budget_seconds':args.budget_seconds,'export_budget_seconds':args.budget_seconds,
        'runtime_source':os.environ['PYTHONPATH'],'selection':'Normal engine selection from the one predeclared complete physical alternative'}
    atomic_json(output/'execution-predeclaration.json',declaration)
    scripts_dir=output/'executed-scripts';scripts_dir.mkdir()
    for p in helper_paths:shutil.copyfile(p,scripts_dir/p.name)
    result={'status':'RUNNING','checker_version':checker_version(),'execution_predeclaration_root':digest(declaration),
        'mission_root':digest(mission),'store':str(store_path),'scope':'New hypothetical Office common-tee three-sink service; ideal bore/loss model and numerical native geometry premises explicit',
        'whole_building':'NOT_CERTIFIED','unrestricted_topology_optimality':'NOT_ESTABLISHED'}
    atomic_json(output/'run-result.json',result);started=time.monotonic()
    print(json.dumps({'stage':'EXECUTION_FROZEN','output':str(output),'mission_root':digest(mission)}),flush=True)
    try:
        store,copied=copy_baseline(original,store_path,frozen['baseline_root'])
        atomic_json(output/'copied-baseline-inputs.json',copied)
        atomic_json(output/'native-cache-copy.json',seed_native_cache(original,store,baseline,mission['source_representation_policy']))
        project=store.create_project('Office • explicit three-sink common-tee pressure service',deepcopy(baseline))
        run=store.create_run(project['id'],{'operation':'optimize','mission':mission,'budget_seconds':args.budget_seconds})
        result.update(project_id=project['id'],run_id=run['id']);atomic_json(output/'run-result.json',result)
        worker=supervise_check([sys.executable,'-m','oma.worker',str(store.directory),run['id']],environment=dict(os.environ),
            directory=output/'worker',deadline=time.monotonic()+args.budget_seconds,memory_limit_bytes=12*1024**3)
        result['worker']=worker;result['run_status']=store.run(run['id'])['status']
        candidates=[c for c in store.candidates(project['id']) if c['run_id']==run['id']]
        result['candidates']=[collect(store,c,output,c['id']) for c in candidates]
        events=[];cursor=0
        while batch:=store.events(project['id'],cursor,1000):events.extend(batch);cursor=batch[-1]['seq']
        atomic_json(output/'optimization-events.json',events)
        atomic_json(output/'optimization-run.json',store.run(run['id']))
        assert worker['status']=='COMPLETED' and result['run_status']=='COMPLETED',result
        complete=next(e for e in reversed(events) if e['run_id']==run['id'] and e['stage']=='complete')
        selected,=complete['payload']['selected_candidate_ids'];chosen=store.candidate(selected)
        result['selected_candidate_id']=selected;assert chosen['status']=='CHECKED'
        result['accepted']=store.accept(project['id'],selected,0,'passive-office:'+run['id'],checker_version=checker_version())
        assert result['accepted']['revision']==1
        atomic_json(output/'run-result.json',result)
        print(json.dumps({'stage':'ACCEPTED','candidate_id':selected,'elapsed_seconds':time.monotonic()-started}),flush=True)
        exported=export_project(store,project['id'],selected,draft=False,budget_seconds=args.budget_seconds)
        result['export']=exported
        assert exported['status']=='CHECKED_LOCAL_SCOPE' and exported['round_trip']=='PASS',exported
        manifest=store.get(exported['artifact_root']);atomic_json(output/'export-manifest.json',manifest)
        assert all(manifest['checking']['release_bindings'].values())
        fresh=store.candidate(manifest['checking']['exported_candidate_id'])
        result['export_recheck']=collect(store,fresh,output,'export-recheck')
        assert fresh['status']=='CHECKED' and fresh['state_root']!=chosen['state_root']
        selected_evidence=next(c for c in result['candidates'] if c['candidate_id']==selected)
        assert result['export_recheck']['pressure']['model_root']!=selected_evidence['pressure']['model_root']
        assert result['export_recheck']['pressure']['deliveries']==selected_evidence['pressure']['deliveries']
        result['status']='SELECTED_ACCEPTED_EXPORTED_FRESH_NATIVE_AND_PRESSURE_PASS'
    except BaseException:
        result.update(status='INCOMPLETE_OR_FAILED',failure=traceback.format_exc())
        raise
    finally:
        result['elapsed_seconds']=time.monotonic()-started
        result['original_guards']={'source_bytes_unchanged':all(sha256_file(Path(p))==sha for p,sha in originals.items()),
            'prior_run_and_mission_unchanged':original.run(PRIOR_RUN)==prior,'prior_candidate_unchanged':original.candidate(PRIOR_CANDIDATE)==oldcandidate,
            'original_head_unchanged':original.project(prior['project_id'])==head,
            'new_frozen_mission_unchanged':sha256_file(frozen_path)==declaration['frozen_mission_sha256']}
        if not all(result['original_guards'].values()):result['status']='ORIGINAL_OR_FROZEN_INPUT_MUTATION'
        atomic_json(output/'run-result.json',result)
        print(json.dumps({'stage':'FINISHED','status':result['status'],'elapsed_seconds':result['elapsed_seconds']}),flush=True)


if __name__=='__main__':main()
