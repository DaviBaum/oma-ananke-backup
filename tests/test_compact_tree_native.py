from copy import deepcopy
import hashlib,json
import pytest
from oma.build_identity import checker_version
from oma.exporting import export_project
from oma.ifc.audit import sha256_file
from oma.routing import shared_tree_job as job
from oma.routing.shared_tree_proposals import compile_shared_tree_proposals
from oma.optimization import shared_tree_topk as topk
from oma.store import Store
from oma.worker import WorkerControl
from general_tree_fixture import fixture
from test_general_tree_native import generated_run


@pytest.mark.parametrize('method',[None,False,1,{},[], 'UNPROVED', 'compact_top_k'])
def test_invalid_proof_method_cannot_reach_generation(tmp_path,monkeypatch,method):
    store=Store(tmp_path/'store');project=store.create_project('Invalid method',{'sources':[],'entities':[]})
    r,s,_,_=fixture();query={'schema':job.JOB_SCHEMA,'requirements':r,'search':s,'max_results':2,'proof_method':method}
    run=store.create_run(project['id'],{'operation':'propose_network','mission':query})
    monkeypatch.setattr(job,'compile_shared_tree_proposals',lambda *a,**kw:pytest.fail('Invalid method reached generator'))
    job.propose_shared_tree_run(store,run,WorkerControl(store,run['id']))
    assert store.run(run['id'])['status']=='MISSING_INPUTS'
    assert store.project(project['id'])['state_root']==project['state_root'] and not store.candidates(project['id'])


@pytest.mark.parametrize('attack',['count','state'])
def test_resealed_compact_producer_proof_cannot_create_native_mission(monkeypatch,attack):
    r,s,c,_=fixture();original=topk.compile_shared_tree_topk_catalogue
    def forged(*args,**kwargs):
        result=deepcopy(original(*args,**kwargs));assert result['status']=='CERTIFIED'
        proof=result['certificate'];proof.pop('certificate_root')
        if attack=='count':proof['total_tree_count']=str(int(proof['total_tree_count'])+1)
        else:proof['states'].pop(0)
        root=hashlib.sha256(json.dumps(proof,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
        proof['certificate_root']=root;result['certificate_root']=root
        return result
    monkeypatch.setattr(topk,'compile_shared_tree_topk_catalogue',forged)
    result=compile_shared_tree_proposals(r,s,context=c,max_results=2,max_work=10000000,proof_method='COMPACT_TOP_K')
    assert result['status']=='UNKNOWN' and result['reason']=='SYNTHESIS_INDEPENDENT_CHECK_FAIL'
    assert result['mission'] is None and result['proof_complete'] is False


@pytest.mark.parametrize('count',[4,5,6,7,8])
def test_compact_generated_pressure_accepts_and_freshly_exports(tmp_path,count):
    store,project,run,original=generated_run(tmp_path,count=count,proof_method='COMPACT_TOP_K')
    assert store.run(run['id'])['status']=='COMPLETED',store.run(run['id'])
    events=store.events(project['id'],0,10000)
    generation=next(e for e in events if e['stage']=='network_generation_complete')
    packet=store.get(generation['payload']['proposal_artifact_root'])
    assert packet['authored_query']['proof_method']=='COMPACT_TOP_K'
    finite=packet['result']['synthesis']
    assert finite['certificate']['schema']=='oma.shared-tree-topk-certificate/1'
    assert int(finite['counts']['complete_assignments'])>=18048
    assert packet['result']['independent_check']['status']=='PASS'
    selected_event=[e for e in events if e.get('run_id')==run['id'] and e['stage']=='complete'][-1]
    selected=store.candidate(selected_event['payload']['selected_candidate_ids'][0])
    report=store.get(selected['report_root']);rows={r['id']:r for r in report['results']}
    assert report['status']=='PASS' and selected['status']=='CHECKED'
    checked=rows['network-demand-conditioned-service']['witness']['calculation']['independent_check']
    assert checked['status']==checked['local_check']['status']==checked['global_check']['status']=='PASS'
    service=checked['service'];assert len(service['deliveries'])==count
    assert all(x['status']=='PASS' for x in service['deliveries'])
    assert all(x['forward_status']==x['maximum_velocity_status']=='PASS' for x in service['physical_ports'])
    assert len(service['physical_ports'])==7*count+3
    cad=store.get(rows['network-all-component-pairs']['witness']['artifact'])
    assert cad['route_count']==3*count+2 and cad['pairs_accounted']==2*(3*count+2)
    assert len(cad['self_pair_results'])==(3*count+2)*(3*count+1)//2
    before=sha256_file(original)
    assert store.accept(project['id'],selected['id'],1,'compact-accept',checker_version=checker_version())['revision']==2
    exported=export_project(store,project['id'],selected['id'],draft=False,budget_seconds=240)
    assert exported['status']=='CHECKED_LOCAL_SCOPE' and exported['round_trip']=='PASS',exported
    fresh=store.get(store.get(exported['artifact_root'])['verification_root'])
    assert fresh['status']=='PASS' and fresh['candidate_root']!=report['candidate_root']
    assert sha256_file(original)==before
