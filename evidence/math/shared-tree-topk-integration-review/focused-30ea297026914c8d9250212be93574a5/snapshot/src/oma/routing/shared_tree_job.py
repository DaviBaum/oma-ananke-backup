"""Supervised proposal job; finite menus retain their immutable request binding."""
import math
import subprocess
import time

from oma.build_identity import checker_version
from oma.store import digest
from oma.routing.network_scenario import SharedNetworkScenario,network_baseline_context
from oma.routing.shared_tree_proposals import (compile_shared_tree_proposals,compact_proof_limits,
    _Budget,_snapshot,_proof_hash,_Unavailable,_CallerError,_call)

JOB_SCHEMA='oma.shared-tree-proposal-job/1'


def propose_shared_tree_run(store,run,control):
    run_id=run['id'];immutable=store.run(run_id);budget=None
    fixed_keys=('id','project_id','base_root','base_revision')
    fixed={key:immutable[key] for key in fixed_keys}
    def fail(status,message):
        store.update_run(run_id,status,message,'network_generation',
            payload={'native_checks_run':False,'project_state_changed':False,
                     'accounted_work':budget.work if budget is not None else 0})
    try:
        if any(run.get(key)!=value for key,value in fixed.items()):raise ValueError('Generation run identity differs')
        seconds=float(immutable['request'].get('budget_seconds',300))
        if not math.isfinite(seconds) or seconds<=0:raise ValueError('Finite positive generation time budget required')
        deadline=time.monotonic()+seconds
        def checkpoint(stage,*,forced=False):
            if time.monotonic()>=deadline:raise subprocess.TimeoutExpired('shared_tree_generation',seconds)
            _call(control.checkpoint if forced else control.search_checkpoint,stage)
            if time.monotonic()>=deadline:raise subprocess.TimeoutExpired('shared_tree_generation',seconds)
        checkpoint('shared_tree_generation_start',forced=True)
        query=run['request'].get('mission');required={'schema','requirements','search','max_results'}
        if (type(query) is not dict or not 4<=len(query)<=7 or not required<=set(query)
                or set(query)-required-{'generation_budget','proof_method','compact_limits'} or query.get('schema')!=JOB_SCHEMA):
            raise ValueError('A complete shared-tree generation request is required')
        limits=query.get('generation_budget',{'max_work':2_000_000,'max_partial_trees':20_000})
        proof_method=query.get('proof_method','FULL_LEDGER')
        if type(proof_method) is not str or proof_method not in ('FULL_LEDGER','COMPACT_TOP_K'):
            raise ValueError('Proof method must be FULL_LEDGER or COMPACT_TOP_K')
        compact_options={}
        if 'compact_limits' in query:
            if proof_method!='COMPACT_TOP_K' or query['compact_limits'] is None:raise ValueError('Explicit compact policy required')
            compact_options['compact_limits']=compact_proof_limits(query['compact_limits'])
        maximum=40_000_000 if proof_method=='COMPACT_TOP_K' else 10_000_000
        if (type(limits) is not dict or len(limits)!=2 or set(limits)!={'max_work','max_partial_trees'}
                or type(limits['max_work']) is not int or not 1<=limits['max_work']<=maximum
                or type(limits['max_partial_trees']) is not int or not 1<=limits['max_partial_trees']<=200_000):
            raise ValueError('Generation budget requires bounded integer max_work and max_partial_trees')
        budget=_Budget(limits['max_work'],checkpoint,hard_maximum=maximum)
        request=_snapshot(run['request'],budget,2_097_152);request_root=digest(request)
        if request_root!=digest(immutable['request']):raise ValueError('Generation request differs from immutable stored request')
        query=request['mission']
        limits=query.get('generation_budget',{'max_work':2_000_000,'max_partial_trees':20_000})
        proof_method=query.get('proof_method','FULL_LEDGER')
        compact_options=({'compact_limits':compact_proof_limits(query['compact_limits'])}
                         if 'compact_limits' in query else {})
        baseline=store.get(fixed['base_root']);sources=baseline.get('sources',[])
        if not sources:raise ValueError('Import at least one source before generating project proposals')
        context={'schema':'oma.shared-tree-project-context/1','base_root':fixed['base_root'],
            'project_id':fixed['project_id'],'base_revision':fixed['base_revision'],
            'source_manifest_root':digest(sources),'numerical_policy_root':digest(baseline.get('numerical_policy',{})),
            'request_root':request_root,'checker_version':checker_version(),
            'source_geometry_usage':'FIXED_CONTEXT_ONLY; NO_OBSTACLE_OR_NATIVE_AUTHORITY_FROM_GENERATION'}
        def current_request():
            current=store.run(run_id)
            if (any(run.get(key)!=value or current.get(key)!=value for key,value in fixed.items())
                    or _proof_hash(run['request'],budget,2_097_152)!=request_root
                    or _proof_hash(current['request'],budget,2_097_152)!=request_root):
                raise ValueError('Generation request or fixed run identity changed before publication')
        store.update_run(run_id,'RUNNING','Generating bounded directed connectors and shared-tree alternatives','network_generation')
        generated=compile_shared_tree_proposals(query['requirements'],query['search'],context=context,
            max_results=query['max_results'],max_work=budget.remaining(),
            max_partial_trees=limits['max_partial_trees'],proof_method=proof_method,**compact_options,checkpoint=checkpoint)
        used=generated.get('work',0)
        if type(used) is not int or used<0:raise ValueError('Invalid generation work accounting')
        budget.use(used,callbacks=False)
        if generated['status']=='PROPOSALS_READY':
            try:
                scenario=SharedNetworkScenario.model_validate(generated['mission'])
                network_baseline_context(baseline,scenario)
            except (ValueError,KeyError,TypeError) as exc:
                generated={'status':'INVALID_INPUT','reason':str(exc),'mission':None,'proof_complete':False}
        packet={'schema':'oma.shared-tree-project-proposals/1','context':context,
            'authored_query':query,'result':generated,'project_state_changed':False,
            'native_feasibility_or_acceptance_claim':False,'next_operation':'Submit the returned explicit mission to the existing optimize run API'}
        output_limit=compact_proof_limits(compact_options.get('compact_limits'))['max_bytes'] if proof_method=='COMPACT_TOP_K' else 16_777_216
        packet_root=_proof_hash(packet,budget,output_limit)
        checkpoint('shared_tree_generation_before_artifact',forced=True)
        current_request()
        if _proof_hash(packet,budget,output_limit)!=packet_root:raise ValueError('Generation packet changed before publication')
        artifact=store.put(packet)
        if artifact!=packet_root:raise ValueError('Stored generation packet root differs')
        # Freeze event metadata before the final callback. The immutable artifact
        # already contains the checked packet; no mutable result is trusted later.
        proposal_count=len((generated.get('mission') or {}).get('network_alternatives',[]))
        if generated['status']=='PROPOSALS_READY':
            status='COMPLETED';message='Generated shared-tree mission available for native optimization and checking'
        elif generated['status']=='NO_FINITE_CATALOGUE_ASSIGNMENT':
            status='COMPLETED';message='No rooted tree in the generated finite catalogue; physical feasibility remains unresolved'
        elif generated['status']=='INVALID_INPUT':status='MISSING_INPUTS';message=generated.get('reason','Invalid generation request')
        else:
            reason=generated.get('reason','Uncertified bounded generation')
            status='UNSUPPORTED_OPERATION' if reason.startswith(('GENERATED_PRESSURE','NONREPRESENTABLE')) else 'BUDGET_EXHAUSTED';message=reason
        checkpoint('shared_tree_generation_complete',forced=True)
        current_request();budget.use(callbacks=False)
        store.update_run(run_id,status,message,'network_generation_complete',artifacts=[artifact],
            payload={'proposal_artifact_root':artifact,'proposal_count':proposal_count,
                'native_checks_run':False,'project_state_changed':False,'accounted_work':budget.work})
    except _CallerError as exc:raise exc.original
    except _Unavailable as exc:fail('BUDGET_EXHAUSTED',str(exc))
    except (ValueError,TypeError,KeyError,OverflowError) as exc:fail('MISSING_INPUTS',str(exc))
