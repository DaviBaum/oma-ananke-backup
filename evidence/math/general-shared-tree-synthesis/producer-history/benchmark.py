"""Retain exact frozen finite-catalogue observations; no native executions."""
from pathlib import Path
import hashlib,importlib.util,itertools,json,math,os,shutil,time,uuid

STAGE=Path(__file__).resolve().parent
ROOT=STAGE.parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,x):p.write_text(json.dumps(x,indent=2)+'\n',encoding='utf-8')
def load(p,name):
 spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
latest=read(STAGE/'latest-validation.json');assert latest['status']=='PASS'
source=Path(latest['source_snapshot']);assert sha(source)==latest['module_sha256']
os.environ['OMA_SHARED_TREE_SOURCE']=str(source)
tests=source.parents[3]/'tests/test_general_shared_tree_synthesis.py'
fixture=load(tests,'benchmark_fixture');s=fixture.s
out=STAGE/'evidence/benchmarks'/uuid.uuid4().hex;out.mkdir(parents=True)
shutil.copyfile(__file__,out/'runner.py');shutil.copyfile(source,out/'shared_tree_synthesis.py')
cases={
 'complete-four':fixture.catalogue(4,dense=True,parallel=False),
 'sparse-eight-chain':fixture.catalogue(8),
 'sparse-eight-balanced':fixture.catalogue(8,layout='balanced'),
 'complete-eight-budgeted':fixture.catalogue(8,dense=True,parallel=False),
}
native_dir=ROOT/'.oma/development/general-shared-tree-native/authored-fixtures/4'
generated=read(native_dir/'generated.json')
assert generated['status']=='CATALOGUE_PROPOSED'
cases['current-authored-four']=generated['catalogue']
cases['current-authored-four-cap200000']=generated['catalogue']
copied={}
for p in native_dir.iterdir():
 if p.is_file():
  target=out/'authored-four';target.mkdir(exist_ok=True);shutil.copyfile(p,target/p.name);copied[p.name]=sha(p)
result={}
for name,p in cases.items():
 directory=out/name;directory.mkdir();write(directory/'catalogue.json',p)
 options={'max_partial_trees':200000} if name.endswith('cap200000') else {}
 start=time.perf_counter();produced=s.compile_shared_tree_catalogue(p,**options);production_seconds=time.perf_counter()-start
 write(directory/'produced.json',produced)
 record={'status':produced['status'],'production_seconds':production_seconds,'producer_work':produced['work'],
         'counts':produced.get('counts'),'reason':produced.get('reason'),'input_sha256':sha(directory/'catalogue.json'),
         'proposals':len(produced['proposals']),'options':options}
 if produced['status']=='CERTIFIED':
  start=time.perf_counter();checked=s.verify_shared_tree_catalogue(p,produced['certificate'],**options);record['verification_seconds']=time.perf_counter()-start
  assert checked['status']=='PASS';write(directory/'checked.json',checked)
  record['checker_work']=checked['work'];record['checker_counts']=checked['counts'];record['certificate_root']=checked['certificate_root']
  # Bound the independent incoming-function product oracle BEFORE enumeration.
  sinks={x['id'] for x in p['sinks']};tees={x['id'] for x in p['tee_instances']};source_id=p['source']['id'];combinations=0
  for chosen in itertools.combinations(tees,len(sinks)-1):
   chosen=set(chosen)
   for edge in p['connectors']:
    if edge['from']['node']!=source_id or edge['to']['node'] not in chosen:continue
    targets=(chosen-{edge['to']['node']})|sinks
    combinations+=math.prod(sum(e['to']['node']==node and e['from']['node'] in chosen for e in p['connectors']) for node in targets)
  record['independent_parent_function_domain']=combinations
  if combinations<=1000000:
   start=time.perf_counter();oracle=fixture.incoming_function_oracle(p);record['oracle_seconds']=time.perf_counter()-start
   assert fixture.row_map(produced)==oracle
   write(directory/'independent-oracle.json',[{'connector_ids':list(ids),'tee_ids':list(v[0]),'nominal_cost':list(v[1])} for ids,v in sorted(oracle.items())])
   record['independent_oracle']='PASS'
  else:record['independent_oracle']='NOT_RUN_EXPLICIT_DOMAIN_BUDGET'
 else:
  assert produced['status']=='UNKNOWN' and produced['proposals']==[] and not produced['proof_complete']
 result[name]=record
assert sha(source)==latest['module_sha256'] and all(sha(native_dir/k)==v for k,v in copied.items())
packet={'status':'PASS','module_sha256':latest['module_sha256'],'validation_receipt_sha256':latest['receipt_sha256'],
        'results':result,'authored_input_files':copied,'inputs_unchanged':True,
        'scope':'Pure finite supplied-catalogue topology/cost proof. Authored-four macro provenance/native acceptance remains external; no native rerun.',
        'runner_sha256':sha(out/'runner.py')}
write(out/'result.json',packet)
print(json.dumps({'directory':str(out),'result_sha256':sha(out/'result.json'),**packet}),flush=True)
