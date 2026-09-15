import math

from oma.build_identity import checker_version
from oma.exporting import export_project
from oma.ifc.audit import sha256_file
from oma.routing.engine import route_project_run
from oma.routing.shared_tree_proposals import compile_shared_tree_proposals
from oma.store import Store,digest
from oma.worker import WorkerControl,import_sources
from native_shared_tree_reference import make_original
from test_shared_tree_proposals import fixture


def test_generated_tree_avoids_actual_obstacle_then_accepts_and_freshly_exports(tmp_path):
    original=tmp_path/'original.ifc';make_original(original);original_sha=sha256_file(original)
    store=Store(tmp_path/'store');project=store.create_project('Generated shared tree',{'sources':[],'entities':[]})
    imported=store.create_run(project['id'],{'operation':'import','paths':[str(original)]})
    import_sources(store,imported,WorkerControl(store,imported['id']))
    project=store.project(project['id']);baseline=store.get(project['state_root'])
    r,s,_=fixture();r['source_id']=baseline['sources'][0]['id']
    authored_root=digest({'requirements':r,'search':s})
    generation=compile_shared_tree_proposals(r,s,context={'base_root':project['state_root'],
        'source_sha256':original_sha,'checker_version':checker_version()},max_results=8)
    assert generation['status']=='PROPOSALS_READY',generation
    assert len(generation['mission']['network_alternatives'])>=2
    generation_root=store.put(generation)
    run=store.create_run(project['id'],{'operation':'optimize','mission':generation['mission'],'budget_seconds':180})
    route_project_run(store,run,WorkerControl(store,run['id']))
    candidates=store.candidates(project['id'])
    assert store.run(run['id'])['status']=='COMPLETED',store.run(run['id'])
    assert candidates[0]['status']=='REJECTED'
    blocked=store.get(candidates[0]['report_root'])
    assert next(x for x in blocked['results'] if x['id']=='network-native-counterexample')['status']=='FAIL'
    assert next(x for x in blocked['results'] if x['id']=='network-all-source-clearance')['status']=='NOT_RUN'
    completed=[e for e in store.events(project['id'],0,10000) if e.get('run_id')==run['id'] and e.get('stage')=='complete']
    selected=store.candidate(completed[-1]['payload']['selected_candidate_ids'][0])
    assert selected['status']=='CHECKED'
    report=store.get(selected['report_root']);rows={x['id']:x for x in report['results']}
    assert report['status']=='PASS' and rows['network-demand-conditioned-service']['status']=='PASS'
    assert math.isclose(report['objective']['length_m'],8+math.pi/4,rel_tol=0,abs_tol=1e-7)
    assert report['objective']['fitting_count']==3
    state=store.get(selected['state_root']);parts=state['physical_networks'][0]['component_ids']
    assert len(parts)==len(set(parts))==8
    cad=store.get(rows['network-all-component-pairs']['witness']['artifact'])
    assert cad['route_count']==8 and cad['pairs_accounted']==16 and len(cad['self_pair_results'])==28
    assert store.accept(project['id'],selected['id'],1,'accept-generated-tree',checker_version=checker_version())['revision']==2
    exported=export_project(store,project['id'],selected['id'],draft=False,budget_seconds=180)
    assert exported['status']=='CHECKED_LOCAL_SCOPE' and exported['round_trip']=='PASS',exported
    fresh=store.get(store.get(exported['artifact_root'])['verification_root'])
    assert fresh['status']=='PASS' and fresh['candidate_root']!=report['candidate_root']
    assert sha256_file(original)==original_sha
    assert digest({'requirements':r,'search':s})==authored_root
    assert store.get(generation_root)['input_root']==generation['input_root']
