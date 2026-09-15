"""Supervised proposal job; it publishes a finite menu without changing project state."""
import subprocess
import time

from oma.build_identity import checker_version
from oma.store import digest
from oma.routing.network_scenario import SharedNetworkScenario,network_baseline_context
from oma.routing.shared_tree_proposals import compile_shared_tree_proposals

JOB_SCHEMA='oma.shared-tree-proposal-job/1'


def propose_shared_tree_run(store,run,control):
    seconds=float(run['request'].get('budget_seconds',300))
    deadline=time.monotonic()+seconds
    def checkpoint(stage,*,forced=False):
        if time.monotonic()>=deadline:
            raise subprocess.TimeoutExpired('shared_tree_generation',seconds)
        (control.checkpoint if forced else control.search_checkpoint)(stage)
        if time.monotonic()>=deadline:
            raise subprocess.TimeoutExpired('shared_tree_generation',seconds)
    checkpoint('shared_tree_generation_start',forced=True)
    query=run['request'].get('mission')
    required={'schema','requirements','search','max_results'}
    if (not isinstance(query,dict) or set(query) not in (required,required|{'generation_budget'})
            or query.get('schema')!=JOB_SCHEMA):
        store.update_run(run['id'],'MISSING_INPUTS','A complete shared-tree generation request is required','network_generation')
        return
    limits=query.get('generation_budget',{'max_work':2_000_000,'max_partial_trees':20_000})
    if (not isinstance(limits,dict) or set(limits)!={'max_work','max_partial_trees'}
            or type(limits['max_work']) is not int or not 1<=limits['max_work']<=10_000_000
            or type(limits['max_partial_trees']) is not int or not 1<=limits['max_partial_trees']<=200_000):
        store.update_run(run['id'],'MISSING_INPUTS','Generation budget requires bounded integer max_work and max_partial_trees','network_generation')
        return
    baseline=store.get(run['base_root'])
    sources=baseline.get('sources',[])
    if not sources:
        store.update_run(run['id'],'MISSING_INPUTS','Import at least one source before generating project proposals','network_generation')
        return
    context={'schema':'oma.shared-tree-project-context/1','base_root':run['base_root'],
        'project_id':run['project_id'],'base_revision':run['base_revision'],
        'source_manifest_root':digest(sources),'numerical_policy_root':digest(baseline.get('numerical_policy',{})),
        'request_root':digest(run['request']),'checker_version':checker_version(),
        'source_geometry_usage':'FIXED_CONTEXT_ONLY; NO_OBSTACLE_OR_NATIVE_AUTHORITY_FROM_GENERATION'}
    store.update_run(run['id'],'RUNNING','Generating bounded directed connectors and shared-tree alternatives','network_generation')
    generated=compile_shared_tree_proposals(query['requirements'],query['search'],context=context,
        max_results=query['max_results'],max_work=limits['max_work'],
        max_partial_trees=limits['max_partial_trees'],checkpoint=checkpoint)
    if generated['status']=='PROPOSALS_READY':
        try:
            scenario=SharedNetworkScenario.model_validate(generated['mission'])
            network_baseline_context(baseline,scenario)
        except (ValueError,KeyError,TypeError) as exc:
            generated={'status':'INVALID_INPUT','reason':str(exc),'mission':None,'proof_complete':False}
    checkpoint('shared_tree_generation_before_artifact',forced=True)
    artifact=store.put({'schema':'oma.shared-tree-project-proposals/1','context':context,
        'authored_query':query,'result':generated,'project_state_changed':False,
        'native_feasibility_or_acceptance_claim':False,'next_operation':'Submit the returned explicit mission to the existing optimize run API'})
    checkpoint('shared_tree_generation_complete',forced=True)
    if generated['status']=='PROPOSALS_READY':
        status='COMPLETED';message='Generated shared-tree mission available for native optimization and checking'
    elif generated['status']=='NO_FINITE_CATALOGUE_ASSIGNMENT':
        status='COMPLETED';message='No rooted tree in the generated finite catalogue; physical feasibility remains unresolved'
    elif generated['status']=='INVALID_INPUT':
        status='MISSING_INPUTS';message=generated.get('reason','Invalid generation request')
    else:
        reason=generated.get('reason','Uncertified bounded generation')
        status='UNSUPPORTED_OPERATION' if reason.startswith(('GENERATED_PRESSURE','NONREPRESENTABLE')) else 'BUDGET_EXHAUSTED'
        message=reason
    store.update_run(run['id'],status,message,'network_generation_complete',artifacts=[artifact],
        payload={'proposal_artifact_root':artifact,'proposal_count':len((generated.get('mission') or {}).get('network_alternatives',[])),
            'native_checks_run':False,'project_state_changed':False})
