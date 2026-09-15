"""Predeclared hospital finite site generation; isolated scope and fresh native reports."""
from pathlib import Path
from itertools import combinations
import json,os,sys,time,uuid,shutil,traceback,gzip
from oma.store import Store,digest
from oma.ifc.audit import atomic_json,sha256_file
from oma.build_identity import checker_version
from oma.export_checks import supervise_check
from oma.exporting import export_project

STAGE=Path(__file__).resolve().parent
BUILD='f716dd5cbdd84134a50d855b217b91a886832abc582ee761b1340cec2026b8e7'
def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def blob(out,name,value):
    data=(json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n').encode('utf8')
    with gzip.open(out/(name+'.json.gz'),'wb') as stream:stream.write(data)
    return {'file':name+'.json.gz','sha256':sha256_file(out/(name+'.json.gz')),'uncompressed_bytes':len(data)}
def events(store,project):
    result=[];cursor=0
    while batch:=store.events(project,cursor,1000):result.extend(batch);cursor=batch[-1]['seq']
    return result
def query(source_id,scope):
    return {'schema':'oma.shared-tree-proposal-job/1','max_results':2,'requirements':{
        'mission_type':'shared_network','source_id':source_id,'system_type':'PRESSURE_PIPE','start_m':[32,64,173.875],
        'sinks':[{'id':'sink-a','demand_id':'demand-a','end_m':[36,64,173.875],'required_flow_m3_s':.0005,'available_static_pressure_pa':100},
                 {'id':'sink-b','demand_id':'demand-b','end_m':[33,65,173.875],'required_flow_m3_s':.0005,'available_static_pressure_pa':100}],
        'diameter_m':.0625,'insulation_m':.015625,'clearance_m':.0625,'minimum_straight_m':.0625,'minimum_bend_radius_m':.125,
        'allowed_zone':{'min':[31.75,63.75,173.625],'max':[36.25,65.25,174.125]},'scenario_terminals':True,
        'target_modality':'ENGINEERING_SERVICE','source_representation_policy':'NATIVE_CAD_WITH_SOURCE_VERTEX_HULL_ENCLOSURES',
        'physics':{'density_kg_m3':1000,'darcy_friction':.02,'maximum_velocity_m_s':2,'gravity_m_s2':9.81,
            'elbow_loss_coefficient':.2,'tee_straight_loss_coefficient':.2,'tee_branch_loss_coefficient':.3,
            'source_kinetic_energy_correction':1,'sink_kinetic_energy_correction':1,
            'applicability':'Hypothetical hospital ideal-bore/fixed-loss model; '+scope,
            'fixed_flow_control_assumption':'Hypothetical independently prescribed simultaneous positive terminal deliveries',
            'friction_convention':'DARCY','elbow_loss_reference':'EXCESS_LOCAL_LOSS_EXCLUDING_CURVED_PIPE_FRICTION',
            'tee_loss_reference':'INLET_VELOCITY_TOTAL_IRREVERSIBLE_LOSS','boundary_loss_scope':'BETWEEN_PHYSICAL_NETWORK_PORTS_ONLY'},
        'objective_weights':{'length_m':1},'assumptions':['New hypothetical hospital mission; no installed-service or clinical design claim',scope,
            'Finite tee sites and connector templates; no unrestricted routing or continuous global optimum claim']},
        'search':{'schema':'oma.shared-tree-native-search/1','source_direction':[1,0,0],
            'sink_directions':{'sink-a':[1,0,0],'sink-b':[0,1,0]},
            'tee_instances':[{'id':identity,'center_m':[x,64,173.875],'axis_x':[1,0,0],'axis_y':[0,1,0],
                'trunk_takeout_m':'1/8','branch_takeout_m':'1/8'} for identity,x in [('tee-a',33),('tee-b',34)]],
            'stub_lengths_m':['1/4'],'detour_planes':[{'axis':1,'value_m':'129/2'}]}}
def collect(store,candidate,out):
    dest=out/'candidates'/candidate['id'];dest.mkdir(parents=True,exist_ok=True)
    state=store.get(candidate['state_root']);atomic_json(dest/'candidate.json',candidate);blob(dest,'state',state)
    row={k:candidate.get(k) for k in ('id','status','state_root','report_root')}
    for record in state.get('physical_networks',[]):
        material=store.get(record['geometry_artifact']);atomic_json(dest/'materialization.json',material)
        path=store.resolve_path(material['export_path']);assert sha256_file(path)==material['export_sha256']
        shutil.copyfile(path,dest/'actual.ifc');assert sha256_file(dest/'actual.ifc')==material['export_sha256']
        row['actual_ifc_sha256']=material['export_sha256']
    with store.connect() as db:execution=[dict(e) for e in db.execute('SELECT * FROM check_executions WHERE candidate_id=?',(candidate['id'],))]
    atomic_json(dest/'executions.json',execution)
    for e in execution:
        if e['evidence_root']:blob(dest,'execution-'+e['execution_id'],store.get(e['evidence_root']))
    if not candidate.get('report_root'):return row
    report=store.get(candidate['report_root']);assert report['candidate_root']==candidate['state_root'] and report['checker_version']==checker_version()
    atomic_json(dest/'report.json',report);checks={x['id']:x for x in report['results']};assert len(checks)==len(report['results'])
    row.update(report_status=report['status'],checks={k:{'status':v['status'],'reason':v['reason']} for k,v in checks.items()},objective=report['objective'])
    artifacts={}
    for key,c in checks.items():
        root=(c.get('witness') or {}).get('artifact')
        if root:artifacts[key]=store.get(root);blob(dest,key,artifacts[key])
    if checks.get('network-all-source-clearance',{}).get('status')=='PASS':
        cad=artifacts['network-all-source-clearance'];sem=artifacts['network-native-semantics'];guids=[p['ifc_guid'] for p in sem['parts']];n=len(guids)
        assert len(set(guids))==n==len(set(p['component_id'] for p in sem['parts']))
        assert cad['route_count']==n and set(cad['route_guids'])==set(guids) and len(cad['route_guids'])==n
        assert cad['pairs_accounted']==cad['obstacle_count']*n
        assert sorted(x['sha256'] for x in cad['sources'])==sorted(x['sha256'] for x in state['sources'])
        pairs=cad['self_pair_results'];assert len(pairs)==n*(n-1)//2
        assert {frozenset(p['participant_guids']) for p in pairs}=={frozenset(p) for p in combinations(guids,2)}
        assert sem['physical_ports']==len(sem['ports'])
        row['native']={'components':n,'ports':sem['physical_ports'],'obstacles':cad['obstacle_count'],'source_pairs':cad['pairs_accounted'],
            'self_pairs':len(pairs),'sources':len(cad['sources']),'source_status':cad['coordination_status'],'self_status':cad['self_interference_status']}
    calculation=(checks.get('network-demand-conditioned-service',{}).get('witness') or {}).get('calculation')
    if calculation:blob(dest,'fixed-flow-service',calculation);row['service_status']=checks['network-demand-conditioned-service']['status']
    if candidate['status']=='CHECKED':
        assert report['status']=='PASS' and row['service_status']=='PASS'
        assert row['native']['source_status']==row['native']['self_status']=='PASS'
        assert any(e['status']=='COMPLETED' and e['report_root']==candidate['report_root'] for e in execution)
    return row
def main():
    imported=read(sys.argv[1]);scope=sys.argv[2];store=Store(imported['store']);project=store.project(imported['project_id'])
    assert checker_version()=='oma-independent-checker/2:'+BUILD
    baseline=store.get(project['state_root']);source=next(s for s in baseline['sources'] if s['name']=='arc_ifc4.ifc')
    authored=query(source['id'],scope);out=STAGE/'campaigns'/uuid.uuid4().hex;out.mkdir(parents=True)
    started=time.monotonic();src=Path(os.environ['PYTHONPATH']);app={p.relative_to(src).as_posix():sha256_file(p) for p in src.rglob('*.py')}
    originals={str(store.resolve_path(s['immutable_path'])):s['sha256'] for s in baseline['sources']}
    assert all(sha256_file(Path(p))==h for p,h in originals.items())
    declaration={'schema':'oma.hospital-finite-generated-tree-campaign/1','checker_version':checker_version(),'app_source':str(src),'app_sources':app,
        'scope':scope,'project_before':project,'baseline_root':project['state_root'],'original_files':originals,'authored_query':authored,
        'authored_query_root':digest(authored),'script_sha256':sha256_file(Path(__file__)),
        'generation_budget_seconds':300,'optimization_budget_seconds':1800,'export_budget_seconds':1800,
        'selection':'Normal native selection among two nominal finite proposals; no forced candidate',
        'geometry_proposal_basis':'Dyadic rectangle in Level 2 architectural region; complete imported bounds screen, no native authority until fresh checks'}
    atomic_json(out/'predeclaration.json',declaration);shutil.copyfile(__file__,out/'executed.py')
    result={'status':'RUNNING','out':str(out),'store':str(store.directory),'project_id':project['id'],'predeclaration_root':digest(declaration)}
    atomic_json(out/'result.json',result);print(json.dumps(result),flush=True)
    try:
        generation=store.create_run(project['id'],{'operation':'propose_network','mission':authored,'budget_seconds':300})
        result['generation_run_id']=generation['id'];atomic_json(out/'result.json',result)
        sup=supervise_check([sys.executable,'-m','oma.worker',str(store.directory),generation['id']],environment=dict(os.environ),
            directory=out/'generation-supervision',deadline=time.monotonic()+300,memory_limit_bytes=12*1024**3)
        result['generation_supervision']=sup;result['generation_run']=store.run(generation['id'])
        ev=events(store,project['id']);blob(out,'generation-events',ev)
        terminal=next((e for e in reversed(ev) if e['run_id']==generation['id'] and e['stage']=='network_generation_complete'),None)
        if terminal:
            root=terminal['payload']['proposal_artifact_root'];packet=store.get(root);blob(out,'generation-packet',packet)
            result['generation_artifact_root']=root;generated=packet['result'];result['generation_status']=generated['status']
        else:generated={'status':'NO_COMPLETE_PACKET'}
        assert store.project(project['id'])==project and not store.candidates(project['id'])
        if sup['status']!='COMPLETED' or generated['status']!='PROPOSALS_READY':
            result['status']='GENERATION_BLOCKED';result['reason']=generated.get('reason',result['generation_run'].get('detail'));return
        from oma.optimization.shared_tree_synthesis import verify_shared_tree_catalogue
        from oma.routing.shared_tree_catalogue_check import verify_generated_catalogue
        finite=verify_shared_tree_catalogue(generated['generation']['catalogue'],generated['synthesis']['certificate'],max_results=2)
        assert finite['status']=='PASS'
        provenance=verify_generated_catalogue(authored['requirements'],authored['search'],generated['generation'],context=packet['context'])
        assert provenance['status']=='PASS'
        blob(out,'independent-finite-check',finite);blob(out,'independent-provenance-check',provenance)
        result['proposal_count']=len(generated['mission']['network_alternatives']);atomic_json(out/'generated-mission.json',generated['mission'])
        run=store.create_run(project['id'],{'operation':'optimize','mission':generated['mission'],'budget_seconds':1800})
        result['optimization_run_id']=run['id'];atomic_json(out/'result.json',result)
        print(json.dumps({'stage':'NATIVE_OPTIMIZATION','out':str(out),'run':run['id'],'alternatives':result['proposal_count']}),flush=True)
        sup=supervise_check([sys.executable,'-m','oma.worker',str(store.directory),run['id']],environment=dict(os.environ),directory=out/'native-supervision',
            deadline=time.monotonic()+1800,memory_limit_bytes=12*1024**3)
        result['native_supervision']=sup;result['optimization_run']=store.run(run['id'])
        candidates=[c for c in store.candidates(project['id']) if c['run_id']==run['id']];result['candidates']=[collect(store,c,out) for c in candidates]
        ev=events(store,project['id']);blob(out,'optimization-events',ev)
        complete=next((e for e in reversed(ev) if e['run_id']==run['id'] and e['stage']=='complete'),None)
        selected=(complete or {}).get('payload',{}).get('selected_candidate_ids',[])
        if sup['status']!='COMPLETED' or not selected:
            result['status']='NO_CHECKED_INCUMBENT';return
        chosen,=selected;assert store.candidate(chosen)['status']=='CHECKED';result['selected_candidate_id']=chosen
        result['accepted']=store.accept(project['id'],chosen,project['revision'],'hospital:'+run['id'],checker_version=checker_version())
        assert result['accepted']['revision']==project['revision']+1
        atomic_json(out/'result.json',result);print(json.dumps({'stage':'ACCEPTED','candidate':chosen,'elapsed_seconds':time.monotonic()-started}),flush=True)
        export=export_project(store,project['id'],chosen,draft=False,budget_seconds=1800);result['export']=export
        assert export['status']=='CHECKED_LOCAL_SCOPE' and export['round_trip']=='PASS'
        manifest=store.get(export['artifact_root']);atomic_json(out/'export-manifest.json',manifest)
        assert len(manifest['checking']['release_bindings'])==9 and all(v is True for v in manifest['checking']['release_bindings'].values())
        checked_id=manifest['checking']['exported_candidate_id'];result['exported_candidate']=collect(store,store.candidate(checked_id),out)
        assert result['exported_candidate']['status']=='CHECKED'
        result['status']='ACCEPTED_AND_FRESH_EXPORT_CHECKED'
    except Exception:
        result['status']='CAMPAIGN_EXCEPTION';result['traceback']=traceback.format_exc()
    finally:
        result['elapsed_seconds']=time.monotonic()-started;result['original_bytes_unchanged']=all(sha256_file(Path(p))==h for p,h in originals.items())
        result['app_unchanged']={p.relative_to(src).as_posix():sha256_file(p) for p in src.rglob('*.py')}==app
        result['project_after']=store.project(project['id']);atomic_json(out/'result.json',result)
        print(json.dumps({k:result.get(k) for k in ('status','out','elapsed_seconds','reason','traceback','selected_candidate_id')}),flush=True)
if __name__=='__main__':main()
