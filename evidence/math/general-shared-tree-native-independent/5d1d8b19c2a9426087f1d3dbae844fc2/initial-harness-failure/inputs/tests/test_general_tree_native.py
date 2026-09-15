from copy import deepcopy
from fractions import Fraction as Q
import pytest

from oma.build_identity import checker_version
from oma.exporting import export_project
from oma.ifc.audit import sha256_file
from oma.routing.engine import route_project_run
from oma.routing import shared_tree_job as job
from oma.routing.shared_tree_proposals import compile_shared_tree_proposals
from oma.store import Store,digest,IntegrityError
from oma.worker import WorkerControl,import_sources
from general_tree_fixture import fixture
from native_shared_tree_reference import make_original


@pytest.mark.parametrize('limits',[None,{}, {'max_work':True,'max_partial_trees':20000},
    {'max_work':0,'max_partial_trees':20000},{'max_work':10000001,'max_partial_trees':20000},
    {'max_work':2000000,'max_partial_trees':False},{'max_work':2000000,'max_partial_trees':0},
    {'max_work':2000000,'max_partial_trees':200001},{'max_work':2000000,'max_partial_trees':20000,'unbound':1}])
def test_invalid_job_budget_cannot_generate_or_publish_candidates(tmp_path,monkeypatch,limits):
    store=Store(tmp_path/'store');project=store.create_project('Budget guard',{'sources':[],'entities':[]})
    r,s,_,_=fixture()
    run=store.create_run(project['id'],{'operation':'propose_network','mission':{'schema':job.JOB_SCHEMA,
        'requirements':r,'search':s,'max_results':2,'generation_budget':limits}})
    monkeypatch.setattr(job,'compile_shared_tree_proposals',lambda *a,**kw:pytest.fail('Invalid limit reached compiler'))
    job.propose_shared_tree_run(store,run,WorkerControl(store,run['id']))
    assert store.run(run['id'])['status']=='MISSING_INPUTS'
    assert store.project(project['id'])['state_root']==project['state_root'] and store.candidates(project['id'])==[]


@pytest.mark.parametrize('limits,expected',[(None,(2000000,20000)),({'max_work':10000000,'max_partial_trees':200000},(10000000,200000))])
def test_default_and_explicit_controls_are_forwarded_and_bound(tmp_path,monkeypatch,limits,expected):
    store=Store(tmp_path/'store');project=store.create_project('Budget binding',{'sources':[{'id':'fixture'}],'entities':[]})
    r,s,_,_=fixture();query={'schema':job.JOB_SCHEMA,'requirements':r,'search':s,'max_results':2}
    if limits is not None:query['generation_budget']=limits
    run=store.create_run(project['id'],{'operation':'propose_network','mission':query})
    def compiler(*args,**kw):
        assert (kw['max_work'],kw['max_partial_trees'])==expected
        return {'status':'UNKNOWN','reason':'WORK_BUDGET','mission':None,'proof_complete':False}
    monkeypatch.setattr(job,'compile_shared_tree_proposals',compiler)
    job.propose_shared_tree_run(store,run,WorkerControl(store,run['id']))
    assert store.run(run['id'])['status']=='BUDGET_EXHAUSTED'
    event=next(e for e in store.events(project['id'],0,1000) if e['stage']=='network_generation_complete')
    artifact=store.get(event['payload']['proposal_artifact_root'])
    assert artifact['authored_query']==query and artifact['context']['request_root']==digest(run['request'])
    assert store.project(project['id'])['state_root']==project['state_root']


def generated_run(tmp_path,reverse=False):
    original=tmp_path/'original.ifc';make_original(original);original_sha=sha256_file(original)
    store=Store(tmp_path/'store');project=store.create_project('Four-sink generated pressure',{'sources':[],'entities':[]})
    imported=store.create_run(project['id'],{'operation':'import','paths':[str(original)]})
    import_sources(store,imported,WorkerControl(store,imported['id']));project=store.project(project['id'])
    r,s,_,_=fixture()
    if reverse:r['coupled_tree']['sink_total_pressures_pa']['sink-main']={'lower':'2001','upper':'2001'}
    original_boundary=deepcopy(r['coupled_tree'])
    query={'schema':job.JOB_SCHEMA,'requirements':r,'search':s,'max_results':2,
        'generation_budget':{'max_work':10000000,'max_partial_trees':200000}}
    proposal=store.create_run(project['id'],{'operation':'propose_network','mission':query,'budget_seconds':120})
    job.propose_shared_tree_run(store,proposal,WorkerControl(store,proposal['id']))
    assert store.run(proposal['id'])['status']=='COMPLETED',store.run(proposal['id'])
    event=next(e for e in store.events(project['id'],0,10000) if e.get('run_id')==proposal['id'] and e['stage']=='network_generation_complete')
    artifact=store.get(event['payload']['proposal_artifact_root']);result=artifact['result']
    assert result['status']=='PROPOSALS_READY' and result['catalogue_check']['status']=='PASS'
    assert len(result['mission']['sinks'])==4 and len(result['mission']['network_alternatives'])==2
    assert result['mission']['coupled_tree']==original_boundary
    assert all(len(n['sinks'])==4 and sum(c['kind']=='tee' for c in n['components'])==3 for n in result['mission']['network_alternatives'])
    assert store.candidates(project['id'])==[]
    run=store.create_run(project['id'],{'operation':'optimize','mission':result['mission'],'budget_seconds':240})
    route_project_run(store,run,WorkerControl(store,run['id']))
    assert sha256_file(original)==original_sha and store.run(proposal['id'])['request']['mission']==query
    return store,project,run,original


def test_four_sink_generated_pressure_accepts_and_freshly_exports(tmp_path):
    store,project,run,original=generated_run(tmp_path)
    assert store.run(run['id'])['status']=='COMPLETED',store.run(run['id'])
    event=[e for e in store.events(project['id'],0,10000) if e.get('run_id')==run['id'] and e['stage']=='complete'][-1]
    selected=store.candidate(event['payload']['selected_candidate_ids'][0]);assert selected['status']=='CHECKED'
    report=store.get(selected['report_root']);rows={x['id']:x for x in report['results']};assert report['status']=='PASS'
    check=rows['network-demand-conditioned-service']['witness']['calculation']['independent_check']
    assert rows['network-pressure-operating-point']['status']==check['status']==check['local_check']['status']==check['global_check']['status']=='PASS'
    assert len(check['service']['deliveries'])==4
    assert all(x['forward_status']==x['maximum_velocity_status']=='PASS' for x in check['service']['physical_ports'])
    original_sha=sha256_file(original)
    assert store.accept(project['id'],selected['id'],1,'accept-generated-four',checker_version=checker_version())['revision']==2
    exported=export_project(store,project['id'],selected['id'],draft=False,budget_seconds=240)
    assert exported['status']=='CHECKED_LOCAL_SCOPE' and exported['round_trip']=='PASS',exported
    fresh=store.get(store.get(exported['artifact_root'])['verification_root'])
    assert fresh['status']=='PASS' and fresh['candidate_root']!=report['candidate_root']
    assert sha256_file(original)==original_sha


def test_four_sink_reverse_pressure_cannot_accept(tmp_path):
    store,project,run,_=generated_run(tmp_path,reverse=True)
    assert store.run(run['id'])['status']=='NO_INCUMBENT_FOUND',store.run(run['id'])
    candidates=store.candidates(project['id']);assert len(candidates)==2
    assert all(c['status'] in {'REJECTED','UNKNOWN'} for c in candidates)
    assert store.project(project['id'])['state_root']==project['state_root']
    for candidate in candidates:
        with pytest.raises(IntegrityError):store.accept(project['id'],candidate['id'],1,'reject-'+candidate['id'],checker_version=checker_version())
