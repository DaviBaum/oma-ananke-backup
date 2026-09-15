"""Frozen actual nominal generation-job budget, including Store publication guards."""
from pathlib import Path
import hashlib,json,shutil,sys,time,uuid

ROOT=Path(__file__).resolve().parents[2];S=ROOT/'.oma/development/factorized-tree-pressure'
OUT=ROOT/'evidence/math/shared-tree-topk-integration-review'/('budget-'+uuid.uuid4().hex)
OUT.mkdir(parents=True)
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8')
source={}
for p in sorted((S/'src').rglob('*.py')):
    name=p.relative_to(S).as_posix();q=OUT/name;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q);source[name]=sha(q)
shutil.copyfile(__file__,OUT/'runner.py')
cases=[(4,'FULL_LEDGER',10_000_000),(8,'COMPACT_TOP_K',int(sys.argv[1]) if len(sys.argv)>1 else 40_000_000)]
for n,_,_ in cases:
    origin=(ROOT/'.oma/development/general-shared-tree-native/authored-fixtures/4' if n==4 else
        ROOT/'.oma/development/general-shared-tree-native/catalogue-probes/b66610f8c6b54966aa8cf2b7a9bf8d1e/8')
    folder=OUT/str(n);folder.mkdir()
    for name in ('requirements.json','search.json'):
        shutil.copyfile(origin/name,folder/name)
write(OUT/'declaration.json',{'source_files':source,'cases':cases,'runner_sha256':sha(OUT/'runner.py'),
    'max_results':2,'seconds_per_job':300,'native_checks':False})
sys.path.insert(0,str(OUT/'src'))
from oma.store import Store,digest
from oma.worker import WorkerControl
from oma.routing.shared_tree_job import propose_shared_tree_run,JOB_SCHEMA
print(json.dumps({'started':str(OUT)}),flush=True)
records=[]
for n,method,maximum in cases:
    store=Store(OUT/str(n)/'store')
    project=store.create_project('bounded nominal publication',{'entities':[],'sources':[{'id':'fixture',
        'transform_m':[[1,0,0,0],[0,1,0,0],[0,0,1,0],[0,0,0,1]]}]})
    query={'schema':JOB_SCHEMA,'requirements':read(OUT/str(n)/'requirements.json'),
        'search':read(OUT/str(n)/'search.json'),'max_results':2,'proof_method':method,
        'generation_budget':{'max_work':maximum,'max_partial_trees':200000}}
    if method=='COMPACT_TOP_K':query['compact_limits']={'max_transitions':2_000_000,'max_label_pairs':10_000_000,'max_bytes':33_554_432}
    run=store.create_run(project['id'],{'operation':'propose_network','mission':query,'budget_seconds':300})
    write(OUT/str(n)/'authored-run.json',run);start=time.perf_counter()
    propose_shared_tree_run(store,run,WorkerControl(store,run['id']))
    seconds=time.perf_counter()-start;current=store.run(run['id']);events=store.events(project['id'],0,1000)
    write(OUT/str(n)/'events.json',events);write(OUT/str(n)/'completed-run.json',current)
    record={'sinks':n,'method':method,'maximum_work':maximum,'seconds':seconds,'status':current['status'],
            'project_head_unchanged':store.project(project['id'])['state_root']==project['state_root'],
            'candidates':len(store.candidates(project['id'])),'last_event':events[-1]}
    references=[e['payload']['proposal_artifact_root'] for e in events if 'proposal_artifact_root' in e['payload']]
    if references:
        packet=store.get(references[-1]);write(OUT/str(n)/'packet.json',packet)
        record.update(artifact_root=references[-1],packet_sha256=sha(OUT/str(n)/'packet.json'),
                      result_status=packet['result']['status'],result_work=packet['result'].get('work'),
                      accounted_work=events[-1]['payload'].get('accounted_work'))
        assert packet['authored_query']==query and packet['context']['request_root']==digest(run['request'])
    records.append(record);write(OUT/'progress.json',records)
    print(json.dumps({k:v for k,v in record.items() if k!='last_event'}),flush=True)
assert all(sha(OUT/name)==expected for name,expected in source.items())
write(OUT/'result.json',{'status':'COMPLETED','source_files':source,'cases':records,
    'scope':'Actual isolated nominal generation/publication only; no CAD, pressure/service acceptance or physical inference.'})
write(OUT/'file-index.json',{p.relative_to(OUT).as_posix():sha(p) for p in sorted(OUT.rglob('*'))
    if p.is_file() and '__pycache__' not in p.parts and 'store' not in p.relative_to(OUT).parts and p.name!='file-index.json'})
print(json.dumps({'directory':str(OUT),'result_sha256':sha(OUT/'result.json')}),flush=True)
