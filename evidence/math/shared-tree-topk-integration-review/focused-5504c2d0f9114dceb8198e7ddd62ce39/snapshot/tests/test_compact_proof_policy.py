from copy import deepcopy
import pytest
from oma.routing import shared_tree_job as job
from oma.routing import shared_tree_proposals as p
from oma.store import Store,digest
from oma.worker import WorkerControl
from general_tree_fixture import fixture

L={'max_transitions':2_000_000,'max_label_pairs':10_000_000,'max_bytes':33_554_432}

@pytest.mark.parametrize('key,bad',[(k,v) for k in L for v in [None,True,0,-1,'1',{},[]]]+[(k,v+1) for k,v in L.items()])
def test_invalid_compact_policy_never_reaches_generation(tmp_path,monkeypatch,key,bad):
    limits={**L,key:bad};store=Store(tmp_path/'store');project=store.create_project('guard',{'sources':[{'id':'fixture'}],'entities':[]})
    r,s,_,_=fixture();query={'schema':job.JOB_SCHEMA,'requirements':r,'search':s,'max_results':2,
        'proof_method':'COMPACT_TOP_K','compact_limits':limits}
    run=store.create_run(project['id'],{'operation':'propose_network','mission':query})
    monkeypatch.setattr(job,'compile_shared_tree_proposals',lambda *a,**kw:pytest.fail('invalid policy forwarded'))
    job.propose_shared_tree_run(store,run,WorkerControl(store,run['id']))
    assert store.run(run['id'])['status']=='MISSING_INPUTS' and not store.candidates(project['id'])

def test_explicit_compact_limits_forwarded_and_bound(tmp_path,monkeypatch):
    store=Store(tmp_path/'store');project=store.create_project('binding',{'sources':[{'id':'fixture'}],'entities':[]})
    r,s,_,_=fixture();query={'schema':job.JOB_SCHEMA,'requirements':r,'search':s,'max_results':2,
        'proof_method':'COMPACT_TOP_K','compact_limits':deepcopy(L),'generation_budget':{'max_work':40_000_000,'max_partial_trees':20000}}
    run=store.create_run(project['id'],{'operation':'propose_network','mission':query})
    def compile(*a,**kw):
        assert 0<kw['max_work']<40_000_000 and kw['compact_limits']==L
        assert kw['context']['request_root']==digest(run['request'])
        return {'status':'UNKNOWN','reason':'deliberate stub','mission':None,'proof_complete':False}
    monkeypatch.setattr(job,'compile_shared_tree_proposals',compile)
    job.propose_shared_tree_run(store,run,WorkerControl(store,run['id']))
    event=store.events(project['id'],0,1000)[-1];packet=store.get(event['payload']['proposal_artifact_root'])
    assert packet['authored_query']==query and store.project(project['id'])['state_root']==project['state_root']

def test_default_policy_unchanged():
    assert p.compact_proof_limits(None)=={'max_transitions':500000,'max_label_pairs':2000000,'max_bytes':16777216}
    with pytest.raises(ValueError):p._Budget(10_000_001,None)

@pytest.mark.parametrize('policy',[None,{},False,{'max_transitions':1},dict(L,unknown=1)])
def test_explicit_policy_requires_complete_inventory(tmp_path,monkeypatch,policy):
    store=Store(tmp_path/'store');project=store.create_project('shape',{'sources':[{'id':'fixture'}],'entities':[]})
    r,s,_,_=fixture();query={'schema':job.JOB_SCHEMA,'requirements':r,'search':s,'max_results':2,
        'proof_method':'COMPACT_TOP_K','compact_limits':policy}
    run=store.create_run(project['id'],{'operation':'propose_network','mission':query})
    monkeypatch.setattr(job,'compile_shared_tree_proposals',lambda *a,**kw:pytest.fail('invalid policy forwarded'))
    job.propose_shared_tree_run(store,run,WorkerControl(store,run['id']))
    assert store.run(run['id'])['status']=='MISSING_INPUTS'

def test_full_ledger_cannot_use_compact_limits():
    r,s,c,_=fixture()
    value=p.compile_shared_tree_proposals(r,s,context=c,compact_limits=L)
    assert value['status']=='INVALID_INPUT' and value['mission'] is None
