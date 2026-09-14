"""Read-only reconciliation of unchanged Office native runs and wrapper failures."""
from pathlib import Path
import importlib.util
import json
import os
import shutil

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').is_file())
STAGE=ROOT/'.oma/development/next-best-fabrication'
BASE=STAGE/'evidence/benchmarks/office-budgets/310e9ac661714f8e91fcf67d91409415'
FINAL=BASE/'budget-2/finalization-072547c35f884ac5a104d8dc49193284'
module=importlib.util.spec_from_file_location('retained_campaign',BASE/'executed-campaign.py')
c=importlib.util.module_from_spec(module);module.loader.exec_module(c)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def main():
    declared=read(BASE/'predeclaration.json');outer=read(BASE/'result.json')
    b2=read(BASE/'budget-2/result.json');b0=read(BASE/'budget-0/result.json');final=read(FINAL/'result.json')
    assert outer['status']=='INCOMPLETE' and b2['status']=='INCOMPLETE' and b2['error']=='AssertionError: '
    assert final['status']=='FAIL_PRESERVATION_OR_BUILD_CHANGED' and 'error' not in final
    assert {k for k,v in final['preservation'].items() if not v}=={'original_head'}
    original=c.ReadOnlyOriginal()
    preservation={'head':original.project(declared['original_run']['project_id'])==declared['original_head'],
        'candidate':original.candidate(declared['original_candidate']['id'])==declared['original_candidate'],
        'run':original.run(declared['original_run']['id'])==declared['original_run'],
        'source_bytes':all(c.sha256_file(s['path'])==s['sha256'] for s in declared['original_sources']),
        'specification_bytes':c.sha256_file(c.RETAINED_SPEC)==declared['historical_specification_sha256']==c.sha256_file(BASE/'specification.json'),
        'build':c.checker_version()==declared['checker_version']}
    assert all(preservation.values()),preservation
    store=c.Store(Path(outer['isolated_store']))
    assert Path(os.environ['PYTHONPATH']).resolve()==(store.directory/'runtimes'/declared['checker_version'].rsplit(':',1)[-1]/'src').resolve()
    copied=store.get(declared['historical_baseline_root'])
    assert copied==original.get(declared['historical_baseline_root'])
    assets=read(store.directory/'baseline-input-copy.json')['assets']
    assert all(c.sha256_file(a['source'])==c.sha256_file(a['copy'])==a['sha256'] for a in assets)
    source_map={p.relative_to(Path(os.environ['PYTHONPATH'])/'oma').as_posix():c.sha256_file(p) for p in (Path(os.environ['PYTHONPATH'])/'oma').rglob('*.py')}
    assert source_map==declared['application_source_sha256']
    spec=read(BASE/'specification.json')
    runs={}
    for budget,case in ((2,b2),(0,b0)):
        run=store.run(case['run_id']);mission={**spec['mission'],'max_new_fittings':budget}
        assert run['request']['mission']==mission and c.digest(mission)==case['mission_root']
        assert case['worker']['status']=='COMPLETED' and run['status']=='COMPLETED'
        for row in case['candidates']:
            current=store.candidate(row['id'])
            assert current['state_root']==row['state_root'] and current['report_root']==row['report_root']
            assert store.get(current['report_root'])==read(BASE/('budget-'+str(budget))/(row['id']+'.verification.json'))
        runs[budget]={'run_id':run['id'],'mission_root':case['mission_root'],'candidates':case['candidates'],
            'completion':case['completion'],'elapsed_seconds':case['elapsed_seconds']}
    assert b0['status']=='NO_CHECKED_INCUMBENT_IN_BOUNDED_ZERO_BUDGET_SEARCH'
    assert not any(row['status']=='CHECKED' for row in b0['candidates'])
    assert b0['completion']['payload']['selected_candidate_ids']==[] and b0['completion']['payload']['global_lower_bound'] is None
    selected=store.candidate(b2['selected_candidate_id'])
    assert b2['completion']['payload']['selected_candidate_ids']==[selected['id']]
    assert selected['status']=='CHECKED' and selected['state_root']==final['acceptance']['state_root']
    head=store.project(selected['project_id'])
    assert head['revision']==1 and head['state_root']==selected['state_root']
    proof=read(FINAL/'selected-frontier-independent-replay.json')
    assert proof==final['independent_selected_proof'] and proof['status']=='PASS'
    assert proof['candidate_id']==selected['id'] and proof['selected_certificate_kind']=='FABRICATION_RESIDUAL_FRONTIER'
    assert proof['residual_check']['status']==proof['frontier_check']['status']==proof['binary64_fabrication_check']['status']=='PASS'
    capacity=read(FINAL/'exact-capacity-replay.json')
    assert capacity==final['exact_capacity_replay'] and capacity['independent_check']['verdict']=='PASS'
    native=[]
    for name in ('selected_native','exported_native'):
        summary=final[name];candidate=store.candidate(summary['id']);report=store.get(candidate['report_root'])
        assert candidate['status']=='CHECKED' and report['status']=='PASS' and report['checker_version']==c.checker_version()
        assert candidate['state_root']==summary['state_root'] and candidate['report_root']==summary['report_root']
        witness=next(row for row in report['results'] if row['id']=='joint-new-fitting-budget')['witness']
        assert witness['count_complete'] is True and witness['count']==2 and sorted(witness['per_new_route'].values())==[0,2]
        pairs=[]
        for item in summary['native']:
            cad=store.get(item['artifact_root'])
            assert cad['coordination_status']==cad['self_interference_status']=='PASS'
            assert cad['pairs_accounted']==cad['route_count']*cad['obstacle_count']
            assert not any(cad[k] for k in ('failed_pairs','unknown_pairs','blocked_pairs'))
            pairs.append({'route_id':item['route_id'],'parts':cad['route_count'],'obstacles':cad['obstacle_count'],'source_pairs':cad['pairs_accounted'],'self_pairs':len(cad['self_pair_results'])})
        cross=next(row for row in report['results'] if row['id']=='cross-route-interference')
        assert cross['status']=='PASS' and cross['witness']['complete_component_coverage'] is True
        assert cross['witness']['pairs_accounted']==pairs[0]['parts']*pairs[1]['parts']
        native.append({'kind':name,'candidate_id':candidate['id'],'candidate_root':candidate['state_root'],'report_root':candidate['report_root'],
            'fitting_budget_count':witness['count'],'routes':pairs,'cross_route_pairs':cross['witness']['pairs_accounted']})
    manifest=store.get(final['export']['artifact_root']);assert manifest==read(FINAL/'export.manifest.json')
    assert all(manifest['checking']['release_bindings'].values())
    assert final['export']['status']=='CHECKED_LOCAL_SCOPE' and final['export']['round_trip']=='PASS'
    assert manifest['verification_root']==final['exported_native']['report_root']
    assert all(c.sha256_file(row['path'])==row['sha256'] for row in manifest['files'])
    result={'status':'UNCHANGED_OFFICE_B2_RESIDUAL_ACCEPTED_EXPORTED_AND_B0_BOUNDED_NO_INCUMBENT',
        'checker_version':c.checker_version(),'isolated_store':str(store.directory),'specification_root':spec['specification_root'],
        'preservation':preservation,'cases':runs,'selected_candidate_id':selected['id'],'accepted_revision':head['revision'],
        'selected_objective':store.get(selected['report_root'])['objective'],'independent_residual_proof':proof,'exact_capacity_replay':capacity,
        'native_denominators':native,'export':final['export'],
        'retained_wrapper_results':{'initial_campaign_sha256':c.sha256_file(BASE/'result.json'),'exact_runtime_finalization_sha256':c.sha256_file(FINAL/'result.json')},
        'wrapper_corrections':[{'issue':'Parent and worker source hashes were keyed by different absolute frozen paths','correction':'Replayed unchanged predicate under exact worker runtime; same1abe bytes/build; no search rerun'},
            {'issue':'UTF-8 project name predeclaration decoded as cp1252 in final wrapper','correction':'Explicit UTF-8 read yields exact equality with original read-only SQLite project; no original data change'}],
        'script_sha256':c.sha256_file(__file__),'optimizer_or_native_rerun_by_this_audit':False,
        'scope':'Pinned1abe explicit hypothetical geometry mission. All current numerical native route/source/self/cross obligations checked; B0 is bounded no-incumbent, not physical infeasibility. No hydraulic adequacy, continuous optimum, whole-building or release promotion claim.'}
    c.atomic_json(BASE/'campaign-reconciliation.json',result)
    shutil.copyfile(STAGE/'scripts/finalize_office_residual_budget.py',FINAL/'executed-finalization.py')
    assert c.sha256_file(FINAL/'executed-finalization.py')==read(FINAL/'predeclaration.json')['script_sha256']
    print(json.dumps({'status':result['status'],'native_denominators':native,'sha256':c.sha256_file(BASE/'campaign-reconciliation.json')}))


if __name__=='__main__':main()
