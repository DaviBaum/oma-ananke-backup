"""One predeclared new Office finite site/connector request, never authored trees."""
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

from support import Original, PRIOR_RUN, PRIOR_CANDIDATE, copy_baseline, seed_native_cache
from oma.build_identity import checker_version
from oma.export_checks import supervise_check
from oma.exporting import export_project
from oma.ifc.audit import atomic_json, sha256_file
from oma.store import digest

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').is_file())
STAGE = Path(__file__).resolve().parent
BUILD = '4b0af802a0934f31a0fc0812a9d23afccb22b048e48f888604d7ff9c1603fbb0'
BASELINE = '791776cfca7101c54ee90c0ed45e01a309955e535a1f6fa19110f7a22edc4de2'

def query(source_id):
    requirements = {
        'mission_type':'shared_network','source_id':source_id,'system_type':'PRESSURE_PIPE',
        'start_m':[23.5,-7.125,5.875],
        'sinks':[{'id':'sink-a','demand_id':'demand-a','end_m':[27.5,-7.125,5.875],
                  'required_flow_m3_s':.0005,'available_static_pressure_pa':100},
                 {'id':'sink-b','demand_id':'demand-b','end_m':[24.5,-6.125,5.875],
                  'required_flow_m3_s':.0005,'available_static_pressure_pa':100}],
        'diameter_m':.0625,'insulation_m':.015625,'clearance_m':.0625,
        'minimum_straight_m':.0625,'minimum_bend_radius_m':.125,
        'allowed_zone':{'min':[23.25,-7.375,5.625],'max':[27.75,-5.875,6.125]},
        'scenario_terminals':True,'target_modality':'ENGINEERING_SERVICE',
        'source_representation_policy':'NATIVE_CAD_WITH_SOURCE_VERTEX_HULL_ENCLOSURES',
        'physics':{'density_kg_m3':1000,'darcy_friction':.02,'maximum_velocity_m_s':2,'gravity_m_s2':9.81,
            'elbow_loss_coefficient':.2,'tee_straight_loss_coefficient':.2,'tee_branch_loss_coefficient':.3,
            'source_kinetic_energy_correction':1,'sink_kinetic_energy_correction':1,
            'applicability':'New hypothetical Office constant ideal-bore and fixed-loss model; no measured building service claim',
            'fixed_flow_control_assumption':'Hypothetical independently prescribed positive terminal deliveries',
            'friction_convention':'DARCY','elbow_loss_reference':'EXCESS_LOCAL_LOSS_EXCLUDING_CURVED_PIPE_FRICTION',
            'tee_loss_reference':'INLET_VELOCITY_TOTAL_IRREVERSIBLE_LOSS','boundary_loss_scope':'BETWEEN_PHYSICAL_NETWORK_PORTS_ONLY'},
        'objective_weights':{'length_m':1},
        'assumptions':['New hypothetical two-sink Office mission; prior pressure and fixed-flow missions remain unchanged',
            'Finite tee sites and directed Manhattan connector templates only; no unrestricted routing or installed service claim']}
    search = {'schema':'oma.shared-tree-native-search/1','source_direction':[1,0,0],
        'sink_directions':{'sink-a':[1,0,0],'sink-b':[0,1,0]},
        'tee_instances':[{'id':identity,'center_m':[x,-7.125,5.875],'axis_x':[1,0,0],'axis_y':[0,1,0],
                          'trunk_takeout_m':'1/8','branch_takeout_m':'1/8'} for identity,x in [('tee-a',24.5),('tee-b',25.5)]],
        'stub_lengths_m':['1/4'],'detour_planes':[{'axis':1,'value_m':'-13/2'}]}
    assert 'network_alternatives' not in requirements
    return {'schema':'oma.shared-tree-proposal-job/1','requirements':requirements,'search':search,'max_results':4}

def events(store, project):
    result=[];cursor=0
    while batch:=store.events(project,cursor,1000):
        result.extend(batch);cursor=batch[-1]['seq']
    return result

def collect(store,candidate,output):
    directory=output/'candidates'/candidate['id'];directory.mkdir(parents=True,exist_ok=True)
    state=store.get(candidate['state_root'])
    atomic_json(directory/'candidate.json',candidate);atomic_json(directory/'state.json',state)
    row={'candidate_id':candidate['id'],'state_root':candidate['state_root'],'status':candidate['status'],'report_root':candidate.get('report_root')}
    for network in state.get('physical_networks',[]):
        material=store.get(network['geometry_artifact']);atomic_json(directory/'materialization.json',material)
        actual=store.resolve_path(material['export_path']);assert sha256_file(actual)==material['export_sha256']
        shutil.copyfile(actual,directory/'actual.ifc');assert sha256_file(directory/'actual.ifc')==material['export_sha256']
        import ifcopenshell
        original=next(s for s in state['sources'] if s['sha256']==material['source_sha256'])
        before=ifcopenshell.open(str(store.resolve_path(original['immutable_path'])))
        after=ifcopenshell.open(str(directory/'actual.ifc'))
        changed=[e.id() for e in before if str(e)!=str(after.by_id(e.id()))]
        count=len(list(before));assert count==62930 and not changed
        row['parsed_preservation']={'original_entities':count,'changed_ids':changed,'source_sha256':original['sha256'],
            'export_sha256':material['export_sha256'],'scope':'Canonical parsed entity strings at original STEP IDs; not raw serializer spelling'}
    with store.connect() as db:
        executions=[dict(r) for r in db.execute('SELECT * FROM check_executions WHERE candidate_id=? ORDER BY started_at',(candidate['id'],))]
    atomic_json(directory/'executions.json',executions)
    for execution in executions:
        if execution['evidence_root']:atomic_json(directory/(execution['execution_id']+'.json'),store.get(execution['evidence_root']))
    if not candidate.get('report_root'):return row
    report=store.get(candidate['report_root']);atomic_json(directory/'report.json',report)
    assert report['candidate_root']==candidate['state_root'] and report['checker_version']==checker_version()
    checks={r['id']:r for r in report['results']};assert len(checks)==len(report['results'])
    row.update(report_status=report['status'],checks={k:r['status'] for k,r in checks.items()},objective=report['objective'])
    artifacts={}
    for key,check in checks.items():
        root=(check.get('witness') or {}).get('artifact')
        if root:
            artifacts[key]=store.get(root);atomic_json(directory/(key+'.json'),artifacts[key])
    if checks.get('network-all-source-clearance',{}).get('status')=='PASS':
        cad=artifacts['network-all-source-clearance'];sem=artifacts['network-native-semantics']
        guids=[p['ifc_guid'] for p in sem['parts']];n=len(guids)
        assert len(set(guids))==n and len(set(p['component_id'] for p in sem['parts']))==n
        assert cad['route_count']==n and set(cad['route_guids'])==set(guids) and len(cad['route_guids'])==n
        assert cad['obstacle_count']==803 and cad['pairs_accounted']==803*n
        assert sorted(s['sha256'] for s in cad['sources'])==sorted(s['sha256'] for s in state['sources'])
        pairs=cad['self_pair_results'];assert len(pairs)==n*(n-1)//2
        assert {frozenset(p['participant_guids']) for p in pairs}=={frozenset(p) for p in combinations(guids,2)}
        assert sem['physical_ports']==len(sem['ports'])
        row['native']={'components':n,'ports':sem['physical_ports'],'source_obstacles':803,'source_pairs':cad['pairs_accounted'],
            'self_pairs':len(pairs),'source_status':cad['coordination_status'],'self_status':cad['self_interference_status'],
            'native_semantics_root':checks['network-native-semantics']['witness']['artifact'],
            'native_cad_root':checks['network-all-source-clearance']['witness']['artifact']}
    calculation=(checks.get('network-demand-conditioned-service',{}).get('witness') or {}).get('calculation')
    if calculation:
        row['service']=calculation;atomic_json(directory/'fixed-flow-service.json',calculation)
    if candidate['status']=='CHECKED':
        assert report['status']=='PASS' and checks['network-demand-conditioned-service']['status']=='PASS'
        assert row['native']['source_status']==row['native']['self_status']=='PASS'
        assert all(r['status'] in ('PASS','NOT_APPLICABLE') for r in checks.values())
        completed=[e for e in executions if e['status']=='COMPLETED' and e['report_root']==candidate['report_root']]
        assert completed
        evidence=store.get(completed[-1]['evidence_root']);assert evidence['status']==evidence['supervision']['status']=='COMPLETED'
    return row

def main():
    started=time.monotonic();out=STAGE/'evidence'/uuid.uuid4().hex;out.mkdir(parents=True)
    src=Path(os.environ['PYTHONPATH']);version='oma-independent-checker/2:'+BUILD
    assert checker_version()==os.environ['OMA_EXECUTABLE_BUILD']==version
    original=Original();prior=original.run(PRIOR_RUN);oldcandidate=original.candidate(PRIOR_CANDIDATE);head=original.project(prior['project_id'])
    assert prior['base_root']==BASELINE
    baseline=original.get(BASELINE);assert not baseline.get('routes') and not baseline.get('physical_networks')
    authored=query(baseline['sources'][0]['id'])
    original_files={str(original.resolve_path(s['immutable_path'])):s['sha256'] for s in baseline['sources']}
    assert all(sha256_file(Path(p))==h for p,h in original_files.items())
    app={p.relative_to(src).as_posix():sha256_file(p) for p in src.rglob('*.py')}
    scripts={str(p):sha256_file(p) for p in (Path(__file__),STAGE/'support.py')}
    declaration={'schema':'oma.office-finite-generation-campaign/1','checker_version':version,'application_source':str(src),
        'application_sources':app,'baseline_root':BASELINE,'authored_query':authored,'authored_query_root':digest(authored),
        'original_files':original_files,'original_head':head,'original_run':prior,'original_candidate':oldcandidate,
        'scripts':scripts,'generation_budget_seconds':120,'optimization_budget_seconds':900,'export_budget_seconds':900,
        'selection':'Normal native engine selection from up to four generated alternatives; no forced candidate',
        'proposal_rationale':'Dyadic two-sink geometry in earlier checked Office region with smaller outer radius; this is only a proposal, not native evidence',
        'comparison':'New mission; no improvement or equivalence claim against old Office missions'}
    atomic_json(out/'predeclaration.json',declaration)
    for p in scripts:shutil.copyfile(p,out/Path(p).name)
    result={'status':'RUNNING','evidence_directory':str(out),'predeclaration_root':digest(declaration),'checker_version':version}
    atomic_json(out/'result.json',result);print(json.dumps({'stage':'PREDECLARED','output':str(out)}),flush=True)
    store=None
    try:
        store,copied=copy_baseline(original,STAGE/'bench-stores'/out.name,BASELINE)
        atomic_json(out/'copied-baseline.json',copied)
        atomic_json(out/'native-cache-copy.json',seed_native_cache(original,store,baseline,authored['requirements']['source_representation_policy']))
        project=store.create_project('Office hypothetical two-sink finite generated shared tree',deepcopy(baseline))
        gen=store.create_run(project['id'],{'operation':'propose_network','mission':authored,'budget_seconds':120})
        result.update(store=str(store.directory),project_id=project['id'],generation_run_id=gen['id'])
        generation_worker=supervise_check([sys.executable,'-m','oma.worker',str(store.directory),gen['id']],environment=dict(os.environ),directory=out/'generation-worker',deadline=time.monotonic()+120,memory_limit_bytes=12*1024**3)
        result['generation_worker']=generation_worker
        assert generation_worker['status']=='COMPLETED' and store.run(gen['id'])['status']=='COMPLETED'
        gen_events=events(store,project['id']);atomic_json(out/'generation-events.json',gen_events)
        terminal=next(e for e in reversed(gen_events) if e['run_id']==gen['id'] and e['stage']=='network_generation_complete')
        packet_root=terminal['payload']['proposal_artifact_root'];packet=store.get(packet_root);atomic_json(out/'generated-packet.json',packet)
        generated=packet['result'];assert generated['status']=='PROPOSALS_READY'
        result.update(generation_artifact_root=packet_root,generation_input_root=generated['input_root'])
        assert store.project(project['id'])==project and not store.candidates(project['id'])
        from oma.optimization import shared_tree_synthesis as kernel
        def no_producer(*a,**kw):raise AssertionError('Producer invoked by independent verifier')
        kernel.compile_shared_tree_catalogue=no_producer
        checked=kernel.verify_shared_tree_catalogue(generated['generation']['catalogue'],generated['synthesis']['certificate'])
        assert checked['status']=='PASS' and checked['proposals']==generated['synthesis']['proposals']
        atomic_json(out/'independent-finite-kernel.json',checked)
        result['generation']={'alternatives':len(generated['mission']['network_alternatives']),
            'connectors':len(generated['generation']['catalogue']['connectors']),
            'tee_sites':len(generated['generation']['catalogue']['tee_instances']),
            'kernel_status':checked['status'],'full_generated_provenance':'SEPARATE_CHECK_PENDING',
            'nominal_proposals':checked['proposals']}
        atomic_json(out/'generated-mission.json',generated['mission'])
        print(json.dumps({'stage':'GENERATED','counts':{k:v for k,v in result['generation'].items() if k!='nominal_proposals'}}),flush=True)
        run=store.create_run(project['id'],{'operation':'optimize','mission':generated['mission'],'budget_seconds':900})
        result['optimization_run_id']=run['id'];atomic_json(out/'result.json',result)
        worker=supervise_check([sys.executable,'-m','oma.worker',str(store.directory),run['id']],environment=dict(os.environ),directory=out/'native-worker',deadline=time.monotonic()+900,memory_limit_bytes=12*1024**3)
        result['native_worker']=worker
        candidates=[c for c in store.candidates(project['id']) if c['run_id']==run['id']]
        result['candidates']=[collect(store,c,out) for c in candidates]
        current_events=events(store,project['id']);atomic_json(out/'optimization-events.json',current_events)
        assert worker['status']=='COMPLETED' and store.run(run['id'])['status']=='COMPLETED'
        complete=next(e for e in reversed(current_events) if e['run_id']==run['id'] and e['stage']=='complete')
        selected,=complete['payload']['selected_candidate_ids'];candidate=store.candidate(selected)
        assert candidate['status']=='CHECKED';result['selected_candidate_id']=selected
        result['accepted']=store.accept(project['id'],selected,project['revision'],'office-generated:'+run['id'],checker_version=version)
        assert result['accepted']['revision']==project['revision']+1
        atomic_json(out/'result.json',result);print(json.dumps({'stage':'ACCEPTED','candidate_id':selected,'elapsed':time.monotonic()-started}),flush=True)
        exported=export_project(store,project['id'],selected,draft=False,budget_seconds=900);result['export']=exported
        assert exported['status']=='CHECKED_LOCAL_SCOPE' and exported['round_trip']=='PASS'
        manifest=store.get(exported['artifact_root']);atomic_json(out/'export-manifest.json',manifest)
        assert len(manifest['checking']['release_bindings'])==9 and all(v is True for v in manifest['checking']['release_bindings'].values())
        fresh=store.candidate(manifest['checking']['exported_candidate_id']);result['fresh_export']=collect(store,fresh,out)
        assert fresh['status']=='CHECKED' and fresh['state_root']!=candidate['state_root']
        result['status']='GENERATED_SELECTED_ACCEPTED_FRESH_EXPORT_PASS'
    except BaseException:
        result.update(status='INCOMPLETE_OR_FAILED',failure=traceback.format_exc());raise
    finally:
        result['original_guards']={'source_bytes_unchanged':all(sha256_file(Path(p))==h for p,h in original_files.items()),
            'head_unchanged':original.project(prior['project_id'])==head,'run_and_mission_unchanged':original.run(PRIOR_RUN)==prior,
            'candidate_unchanged':original.candidate(PRIOR_CANDIDATE)==oldcandidate,'authored_query_unchanged':digest(authored)==declaration['authored_query_root'],
            'scripts_unchanged':all(sha256_file(p)==h for p,h in scripts.items()),
            'app_sources_unchanged':{p.relative_to(src).as_posix():sha256_file(p) for p in src.rglob('*.py')}==app}
        if not all(result['original_guards'].values()):result['status']='INPUT_MUTATION'
        result['elapsed_seconds']=time.monotonic()-started
        if store:
            atomic_json(out/'final-events.json',events(store,result['project_id']))
            atomic_json(out/'final-project.json',store.project(result['project_id']))
            for rid in (result.get('generation_run_id'),result.get('optimization_run_id')):
                if rid:atomic_json(out/(rid+'.run.json'),store.run(rid))
        atomic_json(out/'result.json',result)
        print(json.dumps({'stage':'FINISHED','status':result['status'],'evidence':str(out),'elapsed_seconds':result['elapsed_seconds']}),flush=True)

if __name__=='__main__':main()
