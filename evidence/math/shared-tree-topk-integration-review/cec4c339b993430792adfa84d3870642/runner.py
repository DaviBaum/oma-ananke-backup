"""Independent bounded current integration review; app sources are copied only."""
from pathlib import Path
from copy import deepcopy
import hashlib,json,shutil,sys,uuid

ROOT=Path(__file__).resolve().parents[2]
STAGE=ROOT/'.oma/development/factorized-tree-pressure'
OUT=ROOT/'evidence/math/shared-tree-topk-integration-review'/uuid.uuid4().hex
OUT.mkdir(parents=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):p.write_text(json.dumps(x,indent=2)+'\n',encoding='utf-8')
sources={}
for path in sorted((STAGE/'src').rglob('*.py')):
    name=path.relative_to(STAGE).as_posix();sources[name]=sha(path)
    dest=OUT/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest)
shutil.copyfile(STAGE/'tests/general_tree_fixture.py',OUT/'general_tree_fixture.py')
shutil.copyfile(__file__,OUT/'runner.py')
write(OUT/'declaration.json',{'source_files':sources,'runner_sha256':sha(OUT/'runner.py'),
    'fixture_sha256':sha(OUT/'general_tree_fixture.py'),
    'scope':'Actual nominal producer/checker and isolated Store. No native CAD or source authenticity claim. All mutation probes bounded.'})
sys.path[:0]=[str(OUT/'src'),str(OUT)]
from general_tree_fixture import fixture
from oma.routing import shared_tree_proposals as p, shared_tree_job as j
from oma.optimization import shared_tree_topk as k
from oma.store import Store,digest
from oma.worker import WorkerControl
L={'max_transitions':2_000_000,'max_label_pairs':10_000_000,'max_bytes':33_554_432}
records={}

def inputs():return fixture(2,pressure=False)[:3]
def compile(r,s,c,**kwargs):
    return p.compile_shared_tree_proposals(r,s,context=c,max_results=1,max_work=40_000_000,
                                         proof_method='COMPACT_TOP_K',**kwargs)

r,s,c=inputs();positive=compile(r,s,c,compact_limits=deepcopy(L))
assert positive['status']=='PROPOSALS_READY'
write(OUT/'positive.json',positive)
records['positive']={'status':positive['status'],'work':positive['work']}

r,s,c=inputs();policy=deepcopy(L)
def mutate_policy(stage):
    if stage=='shared_tree_proposal_complete':policy['max_bytes']=1
result=compile(r,s,c,compact_limits=policy,checkpoint=mutate_policy)
write(OUT/'mutated-policy.json',result)
records['late_policy_mutation']={'status':result['status'],'current_policy':policy,
   'current_policy_still_corresponds_to_executed_limit':False,'native_authority':False}

real_compile=k.compile_shared_tree_topk_catalogue;captured={}
def remember(*args,**kwargs):
    answer=real_compile(*args,**kwargs);captured['answer']=answer
    return answer
k.compile_shared_tree_topk_catalogue=remember
r,s,c=inputs()
def mutate_producer_proof(stage):
    if stage=='shared_tree_proposal_complete':
        certificate=captured['answer']['certificate']
        certificate['states'][-1]['tree_count']='0'
        certificate['certificate_root']=digest({key:value for key,value in certificate.items() if key!='certificate_root'})
try:result=compile(r,s,c,compact_limits=deepcopy(L),checkpoint=mutate_producer_proof)
finally:k.compile_shared_tree_topk_catalogue=real_compile
write(OUT/'mutated-producer-certificate.json',result)
replay=k.verify_shared_tree_topk_catalogue(result['generation']['catalogue'],result['synthesis']['certificate'],
    k=1,max_work=2_000_000)
write(OUT/'mutated-producer-fresh-replay.json',replay)
records['late_producer_certificate_mutation']={'status':result['status'],'proof_complete':result.get('proof_complete'),
   'recorded_check_status':result['independent_check']['status'],'fresh_replay_status':replay['status'],
   'recorded_and_actual_certificate_roots_equal':result['independent_check']['certificate_root']==result['synthesis']['certificate']['certificate_root']}

store=Store(OUT/'isolated-store')
project=store.create_project('read-only-integration-probe',{'entities':[],
    'sources':[{'id':'fixture','transform_m':[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]}]})
r,s,c=inputs()
query={'schema':j.JOB_SCHEMA,'requirements':r,'search':s,'max_results':1,
       'proof_method':'COMPACT_TOP_K','compact_limits':deepcopy(L),
       'generation_budget':{'max_work':40_000_000,'max_partial_trees':20000}}
run=store.create_run(project['id'],{'operation':'propose_network','mission':query,'budget_seconds':300})
original_request_root=digest(run['request'])
class MutationControl:
    def __init__(self):self.actual=WorkerControl(store,run['id'])
    def checkpoint(self,stage):
        self.actual.checkpoint(stage)
        if stage=='shared_tree_generation_before_artifact':
            run['request']['mission']['compact_limits']['max_bytes']=1
    def search_checkpoint(self,stage):return self.actual.search_checkpoint(stage)
j.propose_shared_tree_run(store,run,MutationControl())
event=store.events(project['id'],0,1000)[-1]
packet=store.get(event['payload']['proposal_artifact_root'])
write(OUT/'mutated-job-packet.json',packet)
records['job_request_mutation_before_publication']={'run_status':store.run(run['id'])['status'],
 'result_status':packet['result']['status'],'original_request_root':original_request_root,
 'published_context_request_root':packet['context']['request_root'],
 'published_authored_policy':packet['authored_query']['compact_limits'],
 'immutable_stored_policy':store.run(run['id'])['request']['mission']['compact_limits'],
 'project_head_unchanged':store.project(project['id'])['state_root']==project['state_root']}

# Replacing an already visited field during a later callback must not evade the
# advertised structural gate before serialization. This uses only5000 integers.
value={'early':None,'padding':list(range(200))};seen=[]
def shape_mutation(stage):
    if not seen:seen.append(True);value['early']=list(range(5000))
budget=p._Budget(100000,shape_mutation)
try:
    result=p._snapshot(value,budget,1_000_000)
    records['snapshot_postwalk_shape']={'status':'RETURNED','late_list_length':len(result['early']),
                                      'advertised_list_limit':4096,'work':budget.work}
except Exception as error:records['snapshot_postwalk_shape']={'status':'REJECTED','type':type(error).__name__,'reason':str(error)}

current_hashes={name:sha(STAGE/name) for name in sources}
result={'status':'REVIEW_FINDINGS','records':records,'snapshot_source_files':sources,
 'snapshot_sources_unchanged':all(sha(OUT/name)==expected for name,expected in sources.items()),
 'current_source_changes_since_snapshot':[name for name in sources if current_hashes[name]!=sources[name]],
 'scope':'Proof publication/control integrity and bounded resource review only; no physical false admission demonstrated.'}
write(OUT/'result.json',result)
write(OUT/'file-index.json',{q.relative_to(OUT).as_posix():sha(q) for q in sorted(OUT.rglob('*'))
    if q.is_file() and '__pycache__' not in q.parts and 'isolated-store' not in q.parts and q.name!='file-index.json'})
print(json.dumps({'directory':str(OUT),'result_sha256':sha(OUT/'result.json'),'records':records}),flush=True)
