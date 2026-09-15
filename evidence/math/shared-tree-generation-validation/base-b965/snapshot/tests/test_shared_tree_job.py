import copy
import os
from pathlib import Path
import subprocess
import time
from types import SimpleNamespace

from fastapi.testclient import TestClient
import pytest

from oma.api import create_app
from oma.build_identity import checker_version
from oma.routing import shared_tree_job as job
from oma.store import Store,TERMINAL_RUN_STATUSES,digest
from oma.worker import Cancelled,WorkerControl,import_sources
from native_shared_tree_reference import make_original
from test_shared_tree_proposals import fixture


def setup(store,baseline=None):
    r,s,_=fixture()
    project=store.create_project('Proposal job',baseline if baseline is not None else {
        'sources':[{'id':'fixture-source','transform_m':[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]}],
        'entities':[]})
    query={'schema':job.JOB_SCHEMA,'requirements':r,'search':s,'max_results':8}
    return project,query


def completion(store,project,run):
    rows=[e for e in store.events(project['id'],0,10000)
          if e.get('run_id')==run['id'] and e['stage']=='network_generation_complete']
    assert len(rows)==1
    event=rows[0]
    artifact=store.get(event['payload']['proposal_artifact_root'])
    assert event['artifacts']==[event['payload']['proposal_artifact_root']]
    return event,artifact


def test_proposal_job_binds_original_request_and_leaves_project_unchanged(tmp_path):
    store=Store(tmp_path/'store');project,query=setup(store)
    request={'operation':'propose_network','mission':query,'budget_seconds':30}
    run=store.create_run(project['id'],request)
    original=digest(request)
    job.propose_shared_tree_run(store,run,WorkerControl(store,run['id']))
    assert store.run(run['id'])['status']=='COMPLETED'
    event,artifact=completion(store,project,run)
    assert artifact['result']['status']=='PROPOSALS_READY'
    assert artifact['authored_query']==query
    assert artifact['context']['request_root']==original
    assert artifact['context']['checker_version']==checker_version()
    assert artifact['context']['base_root']==project['state_root']
    assert len(artifact['result']['mission']['network_alternatives'])==8
    assert event['payload']['native_checks_run'] is False
    assert artifact['project_state_changed'] is False
    assert artifact['native_feasibility_or_acceptance_claim'] is False
    assert digest(store.run(run['id'])['request'])==original
    current=store.project(project['id'])
    assert (current['state_root'],current['revision'])==(project['state_root'],0)
    assert store.candidates(project['id'])==[]
    assert len(store.history(project['id']))==1


@pytest.mark.parametrize('fault,expected',[
    ('missing_source','MISSING_INPUTS'),('missing_key','MISSING_INPUTS'),
    ('wrong_schema','MISSING_INPUTS'),('boolean_results','MISSING_INPUTS'),
    ('float_results','MISSING_INPUTS'),('unknown_requirements','MISSING_INPUTS'),
    ('wrong_source','MISSING_INPUTS'),('existing_mission','MISSING_INPUTS'),
    ('nonrepresentable','UNSUPPORTED_OPERATION'),('pressure_identity','UNSUPPORTED_OPERATION')])
def test_generation_rejects_invalid_or_unsupported_request_without_candidates(tmp_path,fault,expected):
    store=Store(tmp_path/'store')
    baseline={'sources':[],'entities':[]} if fault=='missing_source' else None
    if fault=='existing_mission':
        baseline={'sources':[{'id':'source','transform_m':[]}],'mission':{'fixed':'keep'},'entities':[]}
    project,query=setup(store,baseline)
    if fault=='missing_key':query.pop('search')
    if fault=='wrong_schema':query['schema']='unknown'
    if fault=='boolean_results':query['max_results']=True
    if fault=='float_results':query['max_results']=8.0
    if fault=='unknown_requirements':query['requirements']['network_alternatives']=[]
    if fault=='wrong_source':query['requirements']['source_id']='missing'
    if fault=='nonrepresentable':query['search']['tee_instances'][0]['trunk_takeout_m']='1/3'
    if fault=='pressure_identity':query['requirements']['coupled_tree']={'not':'implemented'}
    request={'operation':'propose_network','mission':query,'budget_seconds':30}
    run=store.create_run(project['id'],request)
    job.propose_shared_tree_run(store,run,WorkerControl(store,run['id']))
    assert store.run(run['id'])['status']==expected,store.run(run['id'])
    assert store.run(run['id'])['request']==request
    assert store.project(project['id'])['state_root']==project['state_root']
    assert store.candidates(project['id'])==[]


@pytest.mark.parametrize('stop_stage',[
    'shared_tree_generation_start','shared_tree_generation_before_artifact','shared_tree_generation_complete'])
def test_cancellation_at_forced_boundaries_cannot_publish_completion(tmp_path,stop_stage):
    store=Store(tmp_path/'store');project,query=setup(store)
    run=store.create_run(project['id'],{'operation':'propose_network','mission':query})
    class Control(WorkerControl):
        def checkpoint(self,stage='compute'):
            if stage==stop_stage:store.control(run['id'],'cancel')
            return super().checkpoint(stage)
    with pytest.raises(Cancelled):job.propose_shared_tree_run(store,run,Control(store,run['id']))
    assert not any(e['stage']=='network_generation_complete' for e in store.events(project['id'],0,10000))
    assert store.project(project['id'])['state_root']==project['state_root']
    assert store.candidates(project['id'])==[]


def test_deadline_expiring_inside_last_control_check_cannot_publish_completion(tmp_path,monkeypatch):
    store=Store(tmp_path/'store');project,query=setup(store)
    run=store.create_run(project['id'],{'operation':'propose_network','mission':query,'budget_seconds':1})
    clock=[0.0]
    monkeypatch.setattr(job,'time',SimpleNamespace(monotonic=lambda:clock[0]))
    class Control(WorkerControl):
        def checkpoint(self,stage='compute'):
            if stage=='shared_tree_generation_complete':clock[0]=2.0
            return super().checkpoint(stage)
    with pytest.raises(subprocess.TimeoutExpired):job.propose_shared_tree_run(store,run,Control(store,run['id']))
    assert not any(e['stage']=='network_generation_complete' for e in store.events(project['id'],0,10000))
    assert store.project(project['id'])['state_root']==project['state_root']
    assert store.candidates(project['id'])==[]


def test_api_generation_runs_in_supervised_frozen_worker_and_returns_reusable_mission(tmp_path):
    app=create_app(tmp_path/'store');store=app.state.engine.store
    original=tmp_path/'original.ifc';make_original(original)
    project=store.create_project('Supervised generated tree',{'sources':[],'entities':[]})
    imported=store.create_run(project['id'],{'operation':'import','paths':[str(original)]})
    import_sources(store,imported,WorkerControl(store,imported['id']))
    project=store.project(project['id'])
    r,s,_=fixture()
    request={'operation':'propose_network','mission':{'schema':job.JOB_SCHEMA,'requirements':r,'search':s,'max_results':8},
        'budget_seconds':30,'idempotency_key':'generate-once'}
    with TestClient(app) as client:
        response=client.post(f"/api/projects/{project['id']}/runs",json=request)
        assert response.status_code==202,response.text
        run=response.json();submitted=copy.deepcopy(run['request'])
        again=client.post(f"/api/projects/{project['id']}/runs",json=request)
        assert again.status_code==202 and again.json()['id']==run['id']
        deadline=time.monotonic()+45
        while time.monotonic()<deadline:
            current=client.get(f"/api/runs/{run['id']}").json()
            if current['status'] in TERMINAL_RUN_STATUSES and run['id'] not in app.state.engine.threads:break
            time.sleep(.02)
        else:raise AssertionError('Supervised generation did not finish within timeout')
        assert current['status']=='COMPLETED',current
        event,artifact=completion(store,project,run)
        assert artifact['result']['status']=='PROPOSALS_READY'
        events=[e for e in store.events(project['id'],0,10000) if e.get('run_id')==run['id']]
        starts=[e for e in events if e['stage']=='start']
        assert len(starts)==1 and starts[0]['payload']['pid']!=os.getpid()
        supervisors=[e for e in events if e['stage']=='worker_supervision']
        assert len(supervisors)==1 and supervisors[0]['status']=='COMPLETED'
        assert current['request']==submitted
        assert artifact['context']['request_root']==digest(submitted)
        assert artifact['context']['checker_version']==checker_version()
        assert store.project(project['id'])['state_root']==project['state_root']
        assert store.candidates(project['id'])==[]
        # A new optimize request carries an explicit immutable network mission.
        optimize=store.create_run(project['id'],{'operation':'optimize','mission':artifact['result']['mission']})
        assert optimize['request']['mission']['mission_type']=='shared_network'
        assert optimize['request']['mission']['network_alternatives']
        assert store.run(run['id'])['request']==submitted
        store.update_run(optimize['id'],'CANCELLED','Only checking request handoff in this test')
