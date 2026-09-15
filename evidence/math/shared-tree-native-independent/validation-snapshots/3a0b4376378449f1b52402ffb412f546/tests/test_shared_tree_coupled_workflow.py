from fractions import Fraction as Q
import pytest

from oma.build_identity import checker_version
from oma.exporting import export_project
from oma.ifc.audit import sha256_file
from oma.routing.engine import route_project_run
from oma.routing.shared_tree_job import JOB_SCHEMA,propose_shared_tree_run
from oma.store import Store,digest,IntegrityError
from oma.worker import WorkerControl,import_sources
from native_shared_tree_reference import make_original
from shared_tree_coupled_fixture import fixture


def generated_run(tmp_path,reverse=False):
    original=tmp_path/'original.ifc';make_original(original)
    store=Store(tmp_path/'store');project=store.create_project('Generated unequal-pressure tree',{'sources':[],'entities':[]})
    imported=store.create_run(project['id'],{'operation':'import','paths':[str(original)]})
    import_sources(store,imported,WorkerControl(store,imported['id']))
    project=store.project(project['id']);r,s,_=fixture()
    if reverse:r['coupled_tree']['sink_total_pressures_pa']['sink-a']={'lower':'201','upper':'201'}
    query={'schema':JOB_SCHEMA,'requirements':r,'search':s,'max_results':2}
    proposal=store.create_run(project['id'],{'operation':'propose_network','mission':query,'budget_seconds':90})
    request_root=digest(proposal['request'])
    propose_shared_tree_run(store,proposal,WorkerControl(store,proposal['id']))
    assert store.run(proposal['id'])['status']=='COMPLETED',store.run(proposal['id'])
    event=next(e for e in store.events(project['id'],0,10000)
        if e.get('run_id')==proposal['id'] and e['stage']=='network_generation_complete')
    artifact=store.get(event['payload']['proposal_artifact_root'])
    assert artifact['result']['catalogue_check']['status']=='PASS'
    assert store.project(project['id'])['state_root']==project['state_root']
    assert store.candidates(project['id'])==[]
    run=store.create_run(project['id'],{'operation':'optimize','mission':artifact['result']['mission'],'budget_seconds':180})
    route_project_run(store,run,WorkerControl(store,run['id']))
    assert digest(store.run(proposal['id'])['request'])==request_root
    assert artifact['authored_query']==query
    return store,project,run,original


def test_generated_two_tee_pressure_model_operates_accepts_and_freshly_exports(tmp_path):
    store,project,run,original=generated_run(tmp_path)
    assert store.run(run['id'])['status']=='COMPLETED',store.run(run['id'])
    completed=[e for e in store.events(project['id'],0,10000) if e.get('run_id')==run['id'] and e['stage']=='complete']
    selected=store.candidate(completed[-1]['payload']['selected_candidate_ids'][0])
    assert selected['status']=='CHECKED'
    report=store.get(selected['report_root']);rows={x['id']:x for x in report['results']}
    assert report['status']=='PASS'
    assert rows['network-pressure-operating-point']['status']==rows['network-demand-conditioned-service']['status']=='PASS'
    calculation=rows['network-demand-conditioned-service']['witness']['calculation']
    check=calculation['independent_check']
    assert check['status']==check['local_check']['status']==check['global_check']['status']==check['verdict']=='PASS'
    service=check['service']
    assert len(service['physical_ports'])==24 and len(service['deliveries'])==3
    assert len(service['conservation_identities'])==25 and len(service['head_path_identities'])==27
    assert all(row['forward_status']==row['maximum_velocity_status']=='PASS' for row in service['physical_ports'])
    cad=store.get(rows['network-all-component-pairs']['witness']['artifact'])
    assert cad['route_count']==11 and cad['pairs_accounted']==22 and len(cad['self_pair_results'])==55
    original_sha=sha256_file(original)
    assert store.accept(project['id'],selected['id'],1,'accept-generated-coupled',checker_version=checker_version())['revision']==2
    exported=export_project(store,project['id'],selected['id'],draft=False,budget_seconds=180)
    assert exported['status']=='CHECKED_LOCAL_SCOPE' and exported['round_trip']=='PASS',exported
    fresh=store.get(store.get(exported['artifact_root'])['verification_root'])
    assert fresh['status']=='PASS' and fresh['candidate_root']!=report['candidate_root']
    fresh_rows={x['id']:x for x in fresh['results']}
    assert fresh_rows['network-pressure-operating-point']['status']=='PASS'
    assert sha256_file(original)==original_sha


def test_nominal_generated_pressure_success_cannot_accept_unsupported_reverse_regime(tmp_path):
    store,project,run,original=generated_run(tmp_path,reverse=True)
    assert store.run(run['id'])['status']=='NO_INCUMBENT_FOUND',store.run(run['id'])
    candidates=store.candidates(project['id']);assert len(candidates)==2
    assert not any(c['status'] in {'CHECKED','ACCEPTED'} for c in candidates)
    assert store.project(project['id'])['state_root']==project['state_root']
    for candidate in candidates:
        with pytest.raises(IntegrityError):
            store.accept(project['id'],candidate['id'],1,'reject-'+candidate['id'],checker_version=checker_version())
