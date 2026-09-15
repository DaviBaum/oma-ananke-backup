"""Read-only current native five-sink report/accept/export and proof-consumer audit."""
from pathlib import Path
from fractions import Fraction as F
from itertools import combinations
import copy, hashlib, json, shutil, sqlite3, sys, uuid, zlib
STAGE=Path(__file__).resolve().parent
ROOT=next(p for p in STAGE.parents if (p/'AGENTS.md').exists())
VALID=ROOT/'.oma/development/factorized-tree-pressure/validation/027d04f6bea045f3970c29ce9c644247'
SOURCE=ROOT/'.oma/development/factorized-tree-pressure/runtimes/73d7eed7accfd706f9972e1548e750009127e24c6106cc25d98c812239a836ee/src'
STORE=VALID/'native-stores/test_compact_generated_pressur1/store'
sys.path.insert(0,str(SOURCE))
from oma.routing import coupled_tree_pressure as adapter
from oma.routing.network_scenario import NetworkDesign
from oma.build_identity import checker_version
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf8'))
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
def dump(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf8')
def inventory(root):return {p.relative_to(root).as_posix():sha(p) for p in root.rglob('*') if p.is_file()}
out=STAGE/'native-replays'/uuid.uuid4().hex;out.mkdir(parents=True);shutil.copyfile(__file__,out/'executed.py')
before=inventory(STORE);app_before={p.relative_to(SOURCE).as_posix():sha(p) for p in SOURCE.rglob('*.py')}
assert checker_version()=='oma-independent-checker/2:73d7eed7accfd706f9972e1548e750009127e24c6106cc25d98c812239a836ee'
db=sqlite3.connect((STORE/'oma.sqlite3').as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
def rows(sql,*args):return [dict(x) for x in db.execute(sql,args)]
blob_roots=set()
def blob(root):
    raw=zlib.decompress((STORE/'blobs'/(root+'.json.z')).read_bytes());v=json.loads(raw);assert digest(v)==root
    blob_roots.add(root);return v
project,=rows('select * from projects');assert project['revision']==2 and project['status']=='ACCEPTED'
revisions=rows('select * from revisions order by revision');assert revisions[-1]['root']==project['state_root']
selected,=rows('select * from candidates where state_root=?',project['state_root'])
assert revisions[-1]['candidate_id']==selected['id'] and selected['status']=='CHECKED'
all_candidates=rows('select * from candidates');events=[json.loads(r['payload']) for r in rows('select payload from events order by seq')]
generation,= [x for x in events if x['stage']=='network_generation_complete']
packet=blob(generation['payload']['proposal_artifact_root']);assert packet['authored_query']['proof_method']=='COMPACT_TOP_K'
assert packet['result']['independent_check']['status']=='PASS'
assert packet['result']['synthesis']['certificate']['schema']=='oma.shared-tree-topk-certificate/1'
selected_event=[x for x in events if x['stage']=='complete' and x['run_id']==selected['run_id']][-1]
assert selected_event['payload']['selected_candidate_ids']==[selected['id']]
manifest_path,=(STORE/'exports').glob('*/manifest.json');manifest=read(manifest_path)
assert manifest['status']=='CHECKED_LOCAL_SCOPE' and manifest['round_trip']=='PASS'
assert len(manifest['checking']['release_bindings'])==9 and all(v is True for v in manifest['checking']['release_bindings'].values())
assert manifest['candidate_id']==selected['id'] and manifest['state_root']==selected['state_root']
fresh,=rows('select * from candidates where id=?',manifest['checking']['exported_candidate_id'])
assert fresh['id']!=selected['id'] and fresh['state_root']!=selected['state_root'] and fresh['status']=='CHECKED'
assert manifest['verification_root']==fresh['report_root'] and manifest['exported_state_root']==fresh['state_root']
for f in manifest['files']:assert sha(Path(f['path']))==f['sha256']
def forbidden(*args,**kwargs):raise AssertionError('A producer was called during independent native-metric proof verification')
for module,attributes in [(adapter,('evaluate_coupled_tree',)),(adapter.local,('compile_coupled_tree_pressure',)),
    (adapter.factorized,('compile_factorized_tree_pressure','_producer_polynomial','_producer_evaluate')),
    (adapter.global_proof,('compile_coupled_tree_univalence',))]:
    for attribute in attributes:setattr(module,attribute,forbidden)
summaries=[];packets=[]
for candidate in all_candidates:
    state=blob(candidate['state_root']);report=blob(candidate['report_root'])
    assert report['candidate_root']==candidate['state_root'] and report['checker_version']==checker_version()
    assert report['mission_hash']==digest(state['mission']) and report['rule_hash']==state['mission']['rule_hash']
    checks={r['id']:r for r in report['results']};assert len(checks)==len(report['results'])
    record,=state['physical_networks'];material=blob(record['geometry_artifact'])
    assert sha(Path(material['source_path']))==material['source_sha256']
    assert sha(Path(material['export_path']))==material['export_sha256']
    dest=out/'candidates'/candidate['id'];dump(dest/'candidate.json',candidate);dump(dest/'state.json',state);dump(dest/'report.json',report);dump(dest/'materialization.json',material)
    shutil.copyfile(material['export_path'],dest/'actual.ifc')
    executions=rows('select * from check_executions where candidate_id=?',candidate['id'])
    completed=[e for e in executions if e['status']=='COMPLETED' and e['report_root']==candidate['report_root']];assert len(completed)==1
    execution,=completed;binding=json.loads(execution['binding']);assert binding['candidate_root']==candidate['state_root'] and binding['checker_version']==report['checker_version']
    evidence=blob(execution['evidence_root']);dump(dest/'execution.json',execution);dump(dest/'execution-evidence.json',evidence)
    summary={'id':candidate['id'],'status':candidate['status'],'report_root':candidate['report_root'],
        'report_status':report['status'],'checks':{k:v['status'] for k,v in checks.items()},'ifc_sha256':material['export_sha256']}
    if candidate['status']=='REJECTED':
        assert checks['network-native-counterexample']['status']=='FAIL'
        assert checks['network-demand-conditioned-service']['status']=='NOT_RUN'
        summary['reason']=checks['network-native-counterexample']['reason'];summaries.append(summary);continue
    assert report['status']=='PASS' and all(x['status']=='PASS' for x in report['results'])
    semroot=checks['network-native-semantics']['witness']['artifact'];cadroot=checks['network-all-source-clearance']['witness']['artifact']
    sem=blob(semroot);cad=blob(cadroot);assert sem['status']=='PASS' and not sem['errors']
    actual={p['component_id']:p for p in sem['parts']};guids={p['ifc_guid'] for p in sem['parts']}
    assert len(actual)==len(guids)==17 and sem['physical_ports']==len(sem['ports'])==38
    assert set(record['component_ids'])==set(actual) and len(record['component_ids'])==17
    assert set(cad['route_guids'])==guids and len(cad['route_guids'])==17
    assert cad['route_count']==17 and cad['obstacle_count']==2 and cad['pairs_accounted']==34
    assert cad['coordination_status']==cad['self_interference_status']=='PASS'
    pairs=cad['self_pair_results'];assert len(pairs)==136 and {frozenset(x['participant_guids']) for x in pairs}=={frozenset(x) for x in combinations(guids,2)}
    assert sorted(x['sha256'] for x in cad['sources'])==sorted(x['sha256'] for x in state['sources'])
    assert all(sha(Path(x['path']))==x['sha256'] for x in cad['sources'])
    w=checks['network-pressure-operating-point']['witness'];calc=blob(w['artifact']);metrics=blob(w['native_metrics_artifact'])
    assert calc==checks['network-demand-conditioned-service']['witness']['calculation']
    cert=calc['certificate'];assert cert['local_certificate']['schema']==adapter.factorized.CERTIFICATE_SCHEMA
    assert cert['flow_box']==read(ROOT/'.oma/development/factorized-tree-pressure/tests/fixtures/five-native/original-box.json')
    run,=rows('select * from runs where id=?',candidate['run_id']);request=json.loads(run['request'])['mission']
    assert request['coupled_tree']['flow_search_box_m3_s']==cert['flow_box']
    physical_spec=copy.deepcopy(material['network_spec']);matrix=physical_spec.pop('source_to_federation_matrix')
    assert matrix==[[1.0,0.0,0.0,0.0],[0.0,1.0,0.0,0.0],[0.0,0.0,1.0,0.0],[0.0,0.0,0.0,1.0]]
    design=NetworkDesign.model_validate(physical_spec).model_dump(mode='json',by_alias=True)
    assert metrics['native_evidence_root']==semroot and metrics['network_root']==digest(design)
    assert set(metrics['components'])==set(actual)
    tolerance=F(checks['network-demand-conditioned-service']['witness']['metric_tolerance_m'])
    for cid,p in actual.items():
        m=metrics['components'][cid]
        assert m['outer_radius_m']=={'lower':str(F(str(p['radius_m']))-tolerance),'upper':str(F(str(p['radius_m']))+tolerance)}
        assert m['length_m']=={'lower':str(max(F(0),F(str(p['length_m']))-tolerance)),'upper':str(F(str(p['length_m']))+tolerance)}
        assert set(m['ports'])==set(p['caps'])
        for slot,cap in p['caps'].items():
            assert m['ports'][slot]['position_m']==[{'lower':str(F(str(x))-tolerance),'upper':str(F(str(x))+tolerance)} for x in cap['position_m']]
    context={'candidate_root':candidate['state_root'],'baseline_root':run['base_root'],'source_sha256':material['source_sha256'],
        'export_sha256':material['export_sha256'],'native_semantics_root':semroot,'native_metrics_root':w['native_metrics_artifact'],
        'native_cad_root':cadroot,'checker_version':report['checker_version'],'mission_hash':digest(state['mission']),
        'rule_hash':state['mission']['rule_hash'],'native_metric_absolute_tolerance_m':str(tolerance)}
    replay=adapter.verify_coupled_tree_envelope(request['coupled_tree'],design,metrics,cert,context=context)
    assert replay['status']==replay['verdict']==replay['local_check']['status']==replay['global_check']['status']=='PASS'
    assert replay['service']==calc['service']==calc['independent_check']['service']
    service=replay['service'];assert len(service['deliveries'])==5 and all(x['status']=='PASS' for x in service['deliveries'])
    assert len(service['physical_ports'])==38 and all(x['forward_status']==x['maximum_velocity_status']=='PASS' for x in service['physical_ports'])
    for name,value in [('semantics',sem),('cad',cad),('calculation',calc),('metrics',metrics),('proof-consumer-replay',replay),('replay-context',context)]:dump(dest/(name+'.json'),value)
    summary.update(components=17,ports=38,source_obstacles=2,source_pairs=34,self_pairs=136,deliveries=5,
        original_parsed_records_checked=sem['original_records_checked'],model_root=replay['model_root'],
        local_schema=cert['local_certificate']['schema'],local_status=replay['local_check']['status'],global_status=replay['global_check']['status'],
        service_verdict=replay['verdict'],proof_replay_work=replay['work'])
    summaries.append(summary);packets.append(cert)
assert len(packets)==2 and packets[0]['flow_box']==packets[1]['flow_box']
assert {k:v for k,v in packets[0]['model'].items() if k not in ('context_root','physical_model_root')}=={k:v for k,v in packets[1]['model'].items() if k not in ('context_root','physical_model_root')}
dump(out/'project.json',project);dump(out/'revisions.json',revisions);dump(out/'generation.json',packet);dump(out/'export-manifest.json',manifest)
for r in blob_roots:
    p=STORE/'blobs'/(r+'.json.z');dst=out/'blobs'/p.name;dst.parent.mkdir(exist_ok=True);shutil.copyfile(p,dst)
for p in (STORE/'imports').rglob('*.ifc'):
    d=out/'original-ifc'/p.parent.name/p.name;d.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,d)
shutil.copyfile(manifest['files'][0]['path'],out/'fresh-export.ifc')
db.close();assert inventory(STORE)==before
assert {p.relative_to(SOURCE).as_posix():sha(p) for p in SOURCE.rglob('*.py')}==app_before
dump(out/'bound-source-map.json',app_before)
result={'status':'FIVE_SINK_NATIVE_ACCEPT_EXPORT_AND_INDEPENDENT_PROOF_REPLAY_PASS','checker_version':checker_version(),
    'original_store':str(STORE),'source_directory':str(SOURCE),'all_original_store_files_unchanged':True,
    'source_file_count':len(app_before),'source_unchanged':True,'selected_candidate_id':selected['id'],'fresh_candidate_id':fresh['id'],
    'project_revision':2,'candidates':summaries,'same_physical_model_and_original_box_after_export':True,
    'native_geometry_rerun':False,'all_producers_disabled_during_envelope_replay':True,
    'native_scope':'Retained authenticated native reports; exact current IFC/source bytes rehashed, pure independent proof consumers replayed',
    'script_sha256':sha(out/'executed.py')}
dump(out/'result.json',result);print(json.dumps({'out':str(out),'status':result['status'],'candidates':summaries},indent=2))
