"""Finish retained B2 candidate under its exact worker runtime; never rerun search."""
from pathlib import Path
import importlib.util
import json
import os
import time
import traceback
import uuid

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').is_file())
STAGE = ROOT/'.oma/development/next-best-fabrication'
ATTEMPT = STAGE/'evidence/benchmarks/office-budgets/310e9ac661714f8e91fcf67d91409415'
spec = importlib.util.spec_from_file_location('retained_campaign', ATTEMPT/'executed-campaign.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


def native_summary(store, candidate, directory):
    summary = c.retain_candidate(store, candidate, directory)
    report = store.get(candidate['report_root'])
    state = store.get(candidate['state_root'])
    contracts = state['derived_artifacts']['routing_contracts']
    assert candidate['status'] == 'CHECKED' and report['status'] == 'PASS'
    assert report['candidate_root'] == candidate['state_root'] and report['checker_version'] == c.checker_version()
    assert summary['fitting_budget']['status'] == 'PASS'
    witness = summary['fitting_budget']['witness']
    assert witness['count_complete'] is True and witness['count'] == 2
    assert sorted(witness['per_new_route'].values()) == [0,2]
    assert len(summary['native']) == len(contracts) == 2
    assert {n['route_id'] for n in summary['native']} == set(contracts)
    for row in summary['native']:
        assert row['status'] == row['coordination_status'] == row['self_interference_status'] == 'PASS'
        assert row['pairs_accounted'] == row['route_count']*row['obstacle_count']
        assert not any(row[k] for k in ('failed_pairs','unknown_pairs','blocked_pairs'))
    cross = summary['cross_route']
    assert cross['status'] == 'PASS' and cross['witness']['complete_component_coverage'] is True
    assert cross['witness']['pairs_accounted'] == summary['native'][0]['route_count']*summary['native'][1]['route_count']
    return summary


def main():
    declared = json.loads((ATTEMPT/'predeclaration.json').read_text())
    prior = json.loads((ATTEMPT/'budget-2/result.json').read_text())
    assert prior['status'] == 'INCOMPLETE' and prior['error'] == 'AssertionError: '
    assert c.sha256_file(ATTEMPT/'executed-campaign.py') == declared['script_sha256']
    assert c.checker_version() == declared['checker_version']
    store = c.Store(STAGE/'bench-stores'/ATTEMPT.name)
    expected_runtime = store.directory/'runtimes'/declared['checker_version'].rsplit(':',1)[-1]/'src'
    assert Path(os.environ['PYTHONPATH']).resolve() == expected_runtime.resolve()
    chosen = store.candidate(prior['selected_candidate_id'])
    run = store.run(prior['run_id'])
    assert prior['completion']['payload']['selected_candidate_ids'] == [chosen['id']]
    assert run['status'] == 'COMPLETED' and c.digest(run['request']['mission']) == prior['mission_root']
    out = ATTEMPT/'budget-2'/('finalization-'+uuid.uuid4().hex)
    out.mkdir()
    pre = {'status':'DECLARED_BEFORE_ACCEPTANCE','checker_version':c.checker_version(),
        'loaded_runtime':str(expected_runtime),'candidate_id':chosen['id'],'candidate_root':chosen['state_root'],
        'report_root':chosen['report_root'],'mission_root':prior['mission_root'],
        'retained_campaign_predeclaration_sha256':c.sha256_file(ATTEMPT/'predeclaration.json'),
        'retained_incomplete_result_sha256':c.sha256_file(ATTEMPT/'budget-2/result.json'),
        'script_sha256':c.sha256_file(__file__),
        'correction':'Use exact worker frozen source path for path-keyed dependency equality; source bytes and checker hash unchanged',
        'optimizer_rerun':False,'physical_predicates_changed':False}
    c.atomic_json(out/'predeclaration.json',pre)
    result={'status':'RUNNING','predeclaration_root':c.digest(pre),'directory':str(out)}
    c.atomic_json(out/'result.json',result)
    start=time.monotonic()
    try:
        result['selected_native'] = native_summary(store,chosen,out)
        state=store.get(chosen['state_root'])
        rid=next(r for r,contract in state['derived_artifacts']['routing_contracts'].items() if contract['request_demand_id']=='obstructed-service')
        events=c.all_events(store,run['project_id'])
        result['independent_selected_proof']=c.selected_frontier_replay(store,run,chosen,rid,events,out)
        result['exact_capacity_replay']=c.exact_capacity_replay(store,run,chosen,events,out)
        head=store.project(run['project_id'])
        assert head['revision']==0 and head['state_root']==run['base_root']
        result['acceptance']=store.accept(run['project_id'],chosen['id'],head['revision'],'private-office-residual-B2',checker_version=c.checker_version())
        result['export']=c.export_project(store,run['project_id'],chosen['id'],draft=False,budget_seconds=1200)
        manifest=store.get(result['export']['artifact_root'])
        report=store.get(manifest['verification_root'])
        c.atomic_json(out/'export.manifest.json',manifest)
        c.atomic_json(out/'export.verification.json',report)
        assert result['export']['status']=='CHECKED_LOCAL_SCOPE' and result['export']['round_trip']=='PASS'
        assert report['status']=='PASS' and report['checker_version']==c.checker_version()
        assert report['candidate_root']==manifest['exported_state_root']!=chosen['state_root']
        assert all(manifest['checking']['release_bindings'].values())
        assert all(c.sha256_file(f['path'])==f['sha256'] for f in manifest['files'])
        exported=store.candidate(manifest['checking']['exported_candidate_id'])
        result['exported_native']=native_summary(store,exported,out)
        result['accepted_head']=store.project(run['project_id'])
        assert result['accepted_head']['revision']==1 and result['accepted_head']['state_root']==chosen['state_root']
        result['status']='UNCHANGED_B2_RESIDUAL_SELECTED_NATIVE_ACCEPTED_EXPORTED_RECHECKED'
    except Exception as error:
        result.update(status='INCOMPLETE',error=f'{type(error).__name__}: {error}',traceback=traceback.format_exc())
    finally:
        original=c.ReadOnlyOriginal()
        guards={'original_head':original.project(declared['original_run']['project_id'])==declared['original_head'],
            'original_candidate':original.candidate(declared['original_candidate']['id'])==declared['original_candidate'],
            'original_run':original.run(declared['original_run']['id'])==declared['original_run'],
            'original_sources':all(c.sha256_file(s['path'])==s['sha256'] for s in declared['original_sources']),
            'original_specification':c.sha256_file(c.RETAINED_SPEC)==declared['historical_specification_sha256'],
            'build':c.checker_version()==declared['checker_version'],'script':c.sha256_file(__file__)==pre['script_sha256']}
        result.update(preservation=guards,elapsed_seconds=time.monotonic()-start)
        if not all(guards.values()):result['status']='FAIL_PRESERVATION_OR_BUILD_CHANGED'
        c.atomic_json(out/'result.json',result)
        print(json.dumps({'status':result['status'],'directory':str(out),'elapsed_seconds':result['elapsed_seconds'],'error':result.get('error')}),flush=True)
    return 0 if result['status']=='UNCHANGED_B2_RESIDUAL_SELECTED_NATIVE_ACCEPTED_EXPORTED_RECHECKED' else 1


if __name__=='__main__':
    raise SystemExit(main())
