"""Read-only retained native/acceptance inventory and producer-disabled math replay."""
from pathlib import Path
from fractions import Fraction as Q
from copy import deepcopy
from itertools import combinations
import hashlib,json,os,shutil,sqlite3,sys,time,zlib

ROOT=Path(__file__).resolve().parent
origin=json.loads((ROOT/'origin.json').read_text(encoding='utf-8'))
sys.path.insert(0,str(ROOT/'src'));os.environ['OMA_EXECUTABLE_BUILD']=origin['source_version']
import numpy as np
from oma.store import digest
from oma.routing import coupled_tree_pressure as adapter
from oma.routing.network_scenario import SharedNetworkScenario,network_requirements,network_baseline_context
from oma.routing.selection import validate_physical_report_admission

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
def forbidden(*args,**kwargs):raise AssertionError('Producer/native execution is forbidden in this audit')
adapter.evaluate_coupled_tree=forbidden
adapter.local.compile_coupled_tree_pressure=forbidden
adapter.factorized.compile_factorized_tree_pressure=forbidden
adapter.global_proof.compile_coupled_tree_univalence=forbidden
source_manifest=json.loads((ROOT/'source.json').read_text(encoding='utf-8'))
assert all(sha(ROOT/'src'/name)==value for name,value in source_manifest.items())


class Reader:
    def __init__(self,path,destination):
        self.path,self.destination=path,destination
        self.db=sqlite3.connect('file:'+path.joinpath('oma.sqlite3').as_posix()+'?mode=ro',uri=True)
        self.db.row_factory=sqlite3.Row;self.observed={};self.files={}
    def records(self,table):return [dict(x) for x in self.db.execute('select * from '+table)]
    def get(self,root):
        p=self.path/'blobs'/(root+'.json.z');raw=zlib.decompress(p.read_bytes())
        assert hashlib.sha256(raw).hexdigest()==root
        self.observed[str(p)]=sha(p)
        out=self.destination/'blobs'/(root+'.json');out.parent.mkdir(parents=True,exist_ok=True)
        if not out.exists():out.write_bytes(raw)
        return json.loads(raw)
    def resolve_path(self,path):
        p=Path(path);return p if p.is_absolute() else self.path/p
    def physical_file(self,path,expected):
        p=self.resolve_path(path);actual=sha(p);assert actual==expected
        target=self.destination/'physical-files'/(actual+p.suffix)
        target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists():shutil.copyfile(p,target)
        self.files[str(p)]=actual


def candidate_record(row):
    result=dict(row);result.update(json.loads(result.pop('payload')));return result


def replay_candidate(reader,candidate,run,count,label):
    state=reader.get(candidate['state_root']);baseline=reader.get(run['base_root']);report=reader.get(candidate['report_root'])
    assert candidate['status']=='CHECKED' and report['status']=='PASS'
    admitted=validate_physical_report_admission(reader,candidate,run,state,baseline,report)
    request=SharedNetworkScenario.model_validate(run['request']['mission'])
    contract=state['derived_artifacts']['network_contract']
    selected=next(n for n in request.network_alternatives if n.network_id==contract['selected_alternative'])
    assert len(selected.sinks)==count
    mission,ports,section=network_requirements(baseline,request)
    assert state['mission']==mission
    source,kept,revision=network_baseline_context(baseline,request)
    assert revision is None
    material=reader.get(state['physical_networks'][0]['geometry_artifact'])
    spec=selected.model_dump(mode='json',by_alias=True)
    assert material['network_spec']==dict(spec,source_to_federation_matrix=source['transform_m'])
    for original in baseline['sources']:reader.physical_file(original['immutable_path'],original['sha256'])
    reader.physical_file(material['export_path'],material['export_sha256'])
    reader.physical_file(material['source_path'],source['sha256'])
    rows={row['id']:row for row in report['results']}
    semantics_root=rows['network-native-semantics']['witness']['artifact'];semantics=reader.get(semantics_root)
    cad_root=rows['network-all-component-pairs']['witness']['artifact'];cad=reader.get(cad_root)
    assert semantics['status']==cad['status']==cad['self_interference_status']=='PASS'
    part_ids={c.id for c in selected.components};part_guids={p['ifc_guid'] for p in material['added_parts']}
    assert len(part_ids)==len(semantics['parts'])==len(part_guids)==semantics['physical_components']==cad['route_count']
    assert {p['component_id'] for p in semantics['parts']}==part_ids
    expected_ports={(c.id,p) for c in selected.components for p in c.ports}
    actual_ports={(p['component_id'],p['slot']) for p in semantics['ports']}
    assert actual_ports==expected_ports and len(actual_ports)==len(semantics['ports'])==semantics['physical_ports']
    assert all(p['status']=='PASS' for p in semantics['ports'])
    assert not semantics['errors'] and semantics['connections']==len(selected.connections)
    assert not cad['invalid_solids'] and not cad['missing_geometry'] and not any(cad[k] for k in ('blocked_pairs','failed_pairs','unknown_pairs'))
    expected_self={frozenset(pair) for pair in combinations(part_guids,2)}
    actual_self=[frozenset(pair['participant_guids']) for pair in cad['self_pair_results']]
    assert len(actual_self)==len(expected_self) and set(actual_self)==expected_self
    assert all(pair['status']=='PASS' for pair in cad['self_pair_results'])
    original_count=0
    for src in baseline['sources']:
        audit=reader.get(src['audit_root']);original_count+=audit['physical_object_count']
    assert cad['obstacle_count']==original_count
    assert cad['pairs_accounted']==len(part_ids)*original_count==cad['broad_separation_passes']+len(cad['pair_results'])
    assert cad['export_sha256']==material['export_sha256']
    assert {x['sha256'] for x in cad['sources']}=={x['sha256'] for x in baseline['sources']}
    pressure=rows['network-pressure-operating-point']['witness']
    calculation=reader.get(pressure['artifact'])
    assert calculation==rows['network-demand-conditioned-service']['witness']['calculation']
    native=reader.get(pressure['native_metrics_artifact'])
    tolerance=Q(str(max(1e-6,state.get('numerical_policy',{}).get('absolute_tolerance_m',1e-6))))
    transform=np.asarray(source['transform_m']);measured={(p['component_id'],p['slot']):p for p in semantics['ports']}
    def interval(v):return {'lower':str(v-tolerance),'upper':str(v+tolerance)}
    expected_metrics={'schema':adapter.METRIC_SCHEMA,'network_root':digest(spec),'native_evidence_root':semantics_root,'components':{}}
    parts={p['component_id']:p for p in semantics['parts']}
    for component in selected.components:
        part=parts[component.id];slot_map={}
        for slot in component.ports:
            point=transform[:3,:3]@measured[(component.id,slot)]['position_m']+transform[:3,3]
            slot_map[slot]={'position_m':[interval(Q(str(float(x)))) for x in point]}
        length=Q(str(part['length_m']))
        expected_metrics['components'][component.id]={'length_m':{'lower':str(max(Q(0),length-tolerance)),'upper':str(length+tolerance)},'outer_radius_m':interval(Q(str(part['radius_m']))),'ports':slot_map}
    assert native==expected_metrics and digest(native)==pressure['native_metrics_artifact']
    context={'candidate_root':candidate['state_root'],'baseline_root':run['base_root'],'source_sha256':source['sha256'],
        'export_sha256':material['export_sha256'],'native_semantics_root':semantics_root,'native_metrics_root':pressure['native_metrics_artifact'],
        'native_cad_root':cad_root,'checker_version':report['checker_version'],'mission_hash':digest(state['mission']),
        'rule_hash':state['mission']['rule_hash'],'native_metric_absolute_tolerance_m':str(tolerance)}
    deadline=time.monotonic()+30
    def checkpoint(stage):
        if time.monotonic()>deadline:raise TimeoutError('Independent replay deadline')
    fresh=adapter.verify_coupled_tree_envelope(request.coupled_tree,selected,native,calculation['certificate'],context=context,checkpoint=checkpoint)
    assert fresh['status']==fresh['verdict']==fresh['local_check']['status']==fresh['global_check']['status']=='PASS',fresh
    assert fresh['proof_complete'] is True and fresh['model_root']==pressure['model_root']
    assert fresh['certificate_root']==calculation['independent_check']['certificate_root']
    assert fresh['local_check']['model_root']==fresh['global_check']['model_root']
    service=fresh['service'];assert service==calculation['service']
    assert len(service['physical_ports'])==len(expected_ports) and len(service['deliveries'])==count
    assert all(p['forward_status']==p['maximum_velocity_status']=='PASS' for p in service['physical_ports'])
    assert all(d['status']=='PASS' for d in service['deliveries'])
    attacks=[]
    for name in ('missing-global','wrong-context'):
        proof=deepcopy(calculation['certificate']);ctx=deepcopy(context)
        if name=='missing-global':
            proof['univalence_certificate']={};proof['certificate_root']=digest({k:v for k,v in proof.items() if k!='certificate_root'})
        else:ctx['candidate_root']='0'*64
        rejected=adapter.verify_coupled_tree_envelope(request.coupled_tree,selected,native,proof,context=ctx,checkpoint=checkpoint)
        assert rejected['status']!='PASS';attacks.append({'name':name,'result':rejected})
    write(reader.destination/(label+'-replay.json'),{'input_context':context,'admission':admitted,'independent_replay':fresh,'attacks':attacks})
    return {'candidate_id':candidate['id'],'candidate_root':candidate['state_root'],'report_root':candidate['report_root'],
        'parts':len(part_ids),'ports':len(expected_ports),'connections':len(selected.connections),'sources':original_count,'source_pairs':cad['pairs_accounted'],
        'self_pairs':len(actual_self),'model_root':fresh['model_root'],'certificate_root':fresh['certificate_root'],'local_schema':calculation['certificate']['local_certificate']['schema'],
        'deliveries':len(service['deliveries']),'flow_and_pressure_replay':'PASS','producer_disabled':True,'work':fresh['work']}


results=[]
for text,folder in origin['stores'].items():
    count=int(text);destination=ROOT/text;destination.mkdir(exist_ok=True)
    path=Path(origin['validation'])/'native-stores'/folder/'store';reader=Reader(path,destination)
    before=sha(path/'oma.sqlite3');projects=reader.records('projects');assert len(projects)==1
    project=projects[0];assert project['revision']==2 and project['status']=='ACCEPTED'
    runs=reader.records('runs')
    for run in runs:run['request']=json.loads(run['request'])
    assert len(runs)==4 and all(run['status']=='COMPLETED' for run in runs)
    candidates=[candidate_record(row) for row in reader.records('candidates')]
    events=[json.loads(row['payload']) for row in reader.records('events')]
    write(destination/'database-records.json',{'projects':projects,'runs':runs,'candidates':candidates,'events':events})
    original_run=next(run for run in runs if run['operation']=='optimize')
    selected_ids=next(event for event in events if event['run_id']==original_run['id'] and event['stage']=='complete')['payload']['selected_candidate_ids']
    assert len(selected_ids)==1
    selected=next(c for c in candidates if c['id']==selected_ids[0]);assert project['state_root']==selected['state_root']
    accepted=[event for event in events if event['status']=='ACCEPTED'];assert len(accepted)==1 and accepted[0]['candidate_id']==selected['id']
    selected_result=replay_candidate(reader,selected,original_run,count,'selected')
    exported_event=next(event for event in events if event['stage']=='export')
    assert exported_event['status']=='CHECKED_LOCAL_SCOPE' and exported_event['candidate_id']==selected['id']
    exported=reader.get(exported_event['artifacts'][0])
    assert exported['round_trip']=='PASS' and exported['state_root']==selected['state_root']
    assert all(exported['checking']['release_bindings'].values())
    copied=next(c for c in candidates if c['id']==exported['checking']['exported_candidate_id'])
    assert copied['state_root']==exported['exported_state_root'] and copied['report_root']==exported['verification_root']
    assert copied['state_root']!=selected['state_root']
    for file in exported['files']:reader.physical_file(file['path'],file['sha256'])
    fresh_result=replay_candidate(reader,copied,original_run,count,'fresh-export')
    assert selected_result['model_root']!=fresh_result['model_root']
    for candidate in (selected,copied):
        completions=[event for event in events if event['stage']=='check_execution' and event.get('candidate_id')==candidate['id'] and event['status']=='COMPLETED']
        assert len(completions)==1 and completions[0]['payload']['report_root']==candidate['report_root']
        reader.get(completions[0]['payload']['current_physical_input_root'])
    assert before==sha(path/'oma.sqlite3')
    assert all(sha(Path(p))==h for p,h in reader.observed.items()) and all(sha(Path(p))==h for p,h in reader.files.items())
    reader.db.close()
    record={'sinks':count,'status':'PASS','revision':2,'all_runs_final':True,'selected':selected_result,'fresh_export':fresh_result,
        'database_sha256':before,'original_files_unchanged':reader.files,'observed_blobs_unchanged':reader.observed}
    write(destination/'result.json',record);results.append(record);print(json.dumps({'sinks':count,'selected':selected_result,'fresh_export':fresh_result}),flush=True)
assert all(sha(ROOT/'src'/name)==value for name,value in source_manifest.items())
write(ROOT/'result.json',{'status':'PASS','results':results,'source_version':origin['source_version'],'all_frozen_source_unchanged':True,
    'scope':'Read-only retained native evidence, physical input hashes, exact report admission and independent producer-disabled parameter/service proof replay. No native geometry was rerun.'})
write(ROOT/'file-index.json',{p.relative_to(ROOT).as_posix():sha(p) for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='file-index.json'})
print('result_sha256',sha(ROOT/'result.json'),flush=True)
