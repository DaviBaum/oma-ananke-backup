"""Actual nominal proof/Store regressions for post-verification publication."""
from copy import deepcopy
import json

import pytest

from oma.optimization import shared_tree_topk as kernel
from oma.routing import shared_tree_job as job, shared_tree_proposals as producer
from oma.store import Store,digest,canonical
from oma.worker import WorkerControl
from general_tree_fixture import fixture

POLICY={'max_transitions':2_000_000,'max_label_pairs':10_000_000,'max_bytes':33_554_432}


def inputs():return fixture(2,pressure=False)[:3]
def compile(r,s,c,**kw):
    return producer.compile_shared_tree_proposals(r,s,context=c,max_results=1,
        proof_method='COMPACT_TOP_K',**kw)


@pytest.mark.parametrize('maximum',[2_000_000,48_000_000])
def test_genuine_compact_result_remains_independently_bound(maximum):
    r,s,c=inputs();result=compile(r,s,c,compact_limits=POLICY,max_work=maximum)
    assert result['status']=='PROPOSALS_READY',result
    assert result['synthesis']['certificate_root']==result['independent_check']['certificate_root']
    fresh=kernel.verify_shared_tree_topk_catalogue(result['generation']['catalogue'],
        result['synthesis']['certificate'],k=1)
    assert fresh['status']=='PASS'


@pytest.mark.parametrize('key,value',[('max_bytes',1),('max_transitions',1),('max_label_pairs',1)])
def test_late_compact_policy_mutation_rejected(key,value):
    r,s,c=inputs();policy=deepcopy(POLICY)
    def callback(stage):
        if stage=='shared_tree_proposal_complete':policy[key]=value
    result=compile(r,s,c,compact_limits=policy,checkpoint=callback)
    assert result['status']=='INVALID_INPUT' and result['mission'] is None


@pytest.mark.parametrize('kind',['certificate','certificate_root','proposals','counts','checked','catalogue-check'])
def test_late_producer_or_checker_alias_mutation_rejected(monkeypatch,kind):
    r,s,c=inputs();held={}
    for name in ('compile_shared_tree_topk_catalogue','verify_shared_tree_topk_catalogue'):
        actual=getattr(kernel,name)
        def remember(*args,_actual=actual,_name=name,**kwargs):
            result=_actual(*args,**kwargs);held[_name]=result;return result
        monkeypatch.setattr(kernel,name,remember)
    import oma.routing.shared_tree_catalogue_check as provenance
    real=provenance.verify_generated_catalogue
    def remember_provenance(*args,**kwargs):
        result=real(*args,**kwargs);held['provenance']=result;return result
    monkeypatch.setattr(provenance,'verify_generated_catalogue',remember_provenance)
    def callback(stage):
        if stage!='shared_tree_proposal_complete':return
        result=held['compile_shared_tree_topk_catalogue']
        if kind=='certificate':
            certificate=result['certificate'];certificate['states'][-1]['tree_count']='0'
            certificate['certificate_root']=digest({k:v for k,v in certificate.items() if k!='certificate_root'})
            result['certificate_root']=certificate['certificate_root']
        elif kind=='certificate_root':result['certificate_root']='0'*64
        elif kind=='proposals':result['proposals'].clear()
        elif kind=='counts':result['counts']['complete_assignments']='0'
        elif kind=='checked':held['verify_shared_tree_topk_catalogue']['counts']['complete_assignments']='0'
        else:held['provenance']['status']='FAIL'
    result=compile(r,s,c,compact_limits=deepcopy(POLICY),checkpoint=callback)
    assert result['status']=='INVALID_INPUT' and result['mission'] is None,result


def test_snapshot_rechecks_late_replacement_before_accepting_copy():
    raw={'early':None,'padding':list(range(200))};calls=[]
    def callback(stage):
        if not calls:calls.append(stage);raw['early']=list(range(5000))
    with pytest.raises(producer._Unavailable,match='INPUT_STRUCTURE_BUDGET'):
        producer._snapshot(raw,producer._Budget(100000,callback),1_000_000)


def test_snapshot_is_plain_json_copy_without_caller_aliases():
    raw={'array':(1,{'word':'π'})}
    captured=producer._snapshot(raw,producer._Budget(1000,None),1024)
    assert captured=={'array':[1,{'word':'π'}]}
    raw['array'][1]['word']='changed'
    assert captured['array'][1]['word']=='π'


@pytest.mark.parametrize('bad',[1,255,True,0,-1])
def test_compact_byte_policy_matches_kernel_lower_bound(bad):
    with pytest.raises(ValueError):producer.compact_proof_limits(dict(POLICY,max_bytes=bad))


def test_streamed_output_exact_utf8_size_hash_and_early_byte_stop():
    raw={'unicode':'π雪','escape':'"\n','negative_zero':-0.0,'array':[True,None,17]}
    encoded=canonical(raw)
    copied,root,size=producer._bounded_json(raw,producer._Budget(1000,None),len(encoded),copy_value=True)
    assert copied==raw and root==digest(raw) and size==len(encoded)
    with pytest.raises(producer._Unavailable,match='INPUT_BYTE_BUDGET'):
        producer._bounded_json(raw,producer._Budget(1000,None),len(encoded)-1)


def test_proof_output_list_domain_is_distinct_from_authored_snapshot():
    value={'states':list(range(5000))}
    with pytest.raises(producer._Unavailable):producer._snapshot(value,producer._Budget(50000,None),100000)
    assert producer._proof_hash(value,producer._Budget(50000,None),100000)==digest(value)


@pytest.mark.parametrize('error_type',[ValueError,TimeoutError,RuntimeError])
@pytest.mark.parametrize('stage',['shared_tree_connector_complete','shared_tree_proposal_complete'])
def test_exact_caller_exception_identity_survives_all_wrapper_layers(error_type,stage):
    r,s,c=inputs();sentinel=error_type('caller exception')
    def callback(actual):
        if actual==stage:raise sentinel
    with pytest.raises(error_type) as caught:compile(r,s,c,compact_limits=POLICY,checkpoint=callback)
    assert caught.value is sentinel


def test_final_work_guard_counts_encoding_and_hash_tails():
    r,s,c=inputs();good=compile(r,s,c,compact_limits=POLICY)
    exact=compile(r,s,c,compact_limits=POLICY,max_work=good['work'])
    assert exact['status']=='PROPOSALS_READY',exact
    short=compile(r,s,c,compact_limits=POLICY,max_work=good['work']-1)
    assert short['status']=='UNKNOWN' and short['mission'] is None


@pytest.mark.parametrize('method,maximum',[('COMPACT_TOP_K',48_000_001),('FULL_LEDGER',10_000_001),('COMPACT_TOP_K',True)])
def test_explicit_compact_ceiling_does_not_raise_other_domains(method,maximum):
    r,s,c=inputs()
    with pytest.raises(ValueError):
        producer.compile_shared_tree_proposals(r,s,context=c,proof_method=method,max_work=maximum)


def make_job(tmp_path,maximum=40_000_000):
    store=Store(tmp_path/'store')
    project=store.create_project('publication integrity',{'entities':[],'sources':[{'id':'fixture',
        'transform_m':[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]}]})
    r,s,_=inputs();query={'schema':job.JOB_SCHEMA,'requirements':r,'search':s,'max_results':1,
        'proof_method':'COMPACT_TOP_K','compact_limits':deepcopy(POLICY),
        'generation_budget':{'max_work':maximum,'max_partial_trees':20000}}
    run=store.create_run(project['id'],{'operation':'propose_network','mission':query,'budget_seconds':300})
    return store,project,run


class InterceptControl:
    def __init__(self,store,run_id,action):self.actual=WorkerControl(store,run_id);self.action=action
    def checkpoint(self,stage):self.actual.checkpoint(stage);self.action(stage)
    def search_checkpoint(self,stage):self.actual.search_checkpoint(stage);self.action(stage)


@pytest.mark.parametrize('maximum',[40_000_000,48_000_000])
def test_actual_job_records_bound_query_and_cumulative_publication_work(tmp_path,maximum):
    store,project,run=make_job(tmp_path,maximum)
    job.propose_shared_tree_run(store,run,WorkerControl(store,run['id']))
    assert store.run(run['id'])['status']=='COMPLETED'
    event=store.events(project['id'],0,1000)[-1];packet=store.get(event['payload']['proposal_artifact_root'])
    assert packet['authored_query']==store.run(run['id'])['request']['mission']
    assert packet['context']['request_root']==digest(store.run(run['id'])['request'])
    assert packet['result']['work']<event['payload']['accounted_work']<=maximum
    assert store.project(project['id'])['state_root']==project['state_root'] and not store.candidates(project['id'])


@pytest.mark.parametrize('when',['shared_tree_generation_before_artifact','shared_tree_generation_complete'])
@pytest.mark.parametrize('field',['compact_limits','requirements','proof_method'])
def test_actual_job_rejects_mutable_query_after_generation(tmp_path,when,field):
    store,project,run=make_job(tmp_path)
    def mutate(stage):
        if stage!=when:return
        query=run['request']['mission']
        if field=='compact_limits':query[field]['max_bytes']=1
        elif field=='requirements':query[field]['diameter_m']=.125
        else:query[field]='FULL_LEDGER'
    job.propose_shared_tree_run(store,run,InterceptControl(store,run['id'],mutate))
    assert store.run(run['id'])['status']=='MISSING_INPUTS'
    assert not any('proposal_artifact_root' in event['payload'] for event in store.events(project['id'],0,1000))
    assert store.project(project['id'])['state_root']==project['state_root']


def test_job_rejects_mutable_result_packet_before_linking(tmp_path,monkeypatch):
    store,project,run=make_job(tmp_path);real=job.compile_shared_tree_proposals;held={}
    def remember(*args,**kwargs):
        result=real(*args,**kwargs);held['result']=result;return result
    monkeypatch.setattr(job,'compile_shared_tree_proposals',remember)
    def mutate(stage):
        if stage=='shared_tree_generation_before_artifact':held['result']['mission']['diameter_m']=.125
    job.propose_shared_tree_run(store,run,InterceptControl(store,run['id'],mutate))
    assert store.run(run['id'])['status']=='MISSING_INPUTS'
    assert not any('proposal_artifact_root' in event['payload'] for event in store.events(project['id'],0,1000))


@pytest.mark.parametrize('error_type',[ValueError,TimeoutError,RuntimeError])
def test_job_cancellation_exception_identity_and_no_artifact_event(tmp_path,error_type):
    store,project,run=make_job(tmp_path);sentinel=error_type('exact job callback')
    def stop(stage):
        if stage=='shared_tree_generation_before_artifact':raise sentinel
    with pytest.raises(error_type) as caught:
        job.propose_shared_tree_run(store,run,InterceptControl(store,run['id'],stop))
    assert caught.value is sentinel
    assert not any('proposal_artifact_root' in event['payload'] for event in store.events(project['id'],0,1000))
