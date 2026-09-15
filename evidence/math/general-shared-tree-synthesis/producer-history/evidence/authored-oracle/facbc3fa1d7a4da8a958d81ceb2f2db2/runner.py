"""Third enumeration: bounded complete incoming-edge functions, exact cost/prefix oracle."""
from fractions import Fraction as Q
from pathlib import Path
import hashlib,importlib.util,itertools,json,math,os,shutil,time,uuid

STAGE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,x):p.write_text(json.dumps(x,indent=2)+'\n',encoding='utf-8')
latest=read(STAGE/'latest-validation.json');source=Path(latest['source_snapshot'])
os.environ['OMA_SHARED_TREE_SOURCE']=str(source)
test=source.parents[3]/'tests/test_general_shared_tree_synthesis.py'
spec=importlib.util.spec_from_file_location('independent_parent_function_fixture',test);f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
prior=STAGE/'evidence/authored-query/131eb52a678c4853bbb8cb1701b20628'
p=read(prior/'catalogue.json');produced=read(prior/'produced.json');assert produced['status']=='CERTIFIED'
out=STAGE/'evidence/authored-oracle'/uuid.uuid4().hex;out.mkdir(parents=True)
for name in ('catalogue.json','produced.json','checked.json'):shutil.copyfile(prior/name,out/name)
shutil.copyfile(__file__,out/'runner.py');shutil.copyfile(test,out/'oracle-test-source.py')
sinks={x['id'] for x in p['sinks']};tees={x['id'] for x in p['tee_instances']};source_id=p['source']['id'];domain=0
for chosen in itertools.combinations(tees,len(sinks)-1):
 chosen=set(chosen)
 for edge in p['connectors']:
  if edge['from']['node']!=source_id or edge['to']['node'] not in chosen:continue
  domain+=math.prod(sum(e['to']['node']==node and e['from']['node'] in chosen for e in p['connectors']) for node in (chosen-{edge['to']['node']})|sinks)
write(out/'predeclared-domain.json',{'candidate_parent_functions':domain,'max_parent_functions':5000000,'input_sha256':sha(prior/'catalogue.json')})
assert domain<=5000000
start=time.perf_counter();reference=f.incoming_function_oracle(p);seconds=time.perf_counter()-start
assert reference==f.row_map(produced)
# A separate 48-term alternating Machin sum gives exact enclosing pi rationals.
def atan_bounds(d):
 total=sum((Q((-1)**k,(2*k+1)*d**(2*k+1)) for k in range(48)),Q())
 return total,total+Q(1,97*d**97)
a,b=atan_bounds(5),atan_bounds(239)
raw=(16*a[0]-4*b[1],16*a[1]-4*b[0]);scale=10**50
pi=(Q(raw[0]*scale//1,scale),Q(-(-raw[1]*scale//1),scale))
assert pi[0]<=raw[0]<=raw[1]<=pi[1]
def compare(ids1,ids2):
 a,b=(Q(x)-Q(y) for x,y in zip(reference[ids1][1],reference[ids2][1]))
 if a==b==0:return (ids1>ids2)-(ids1<ids2)
 lo,hi=(a+b*pi[0],a+b*pi[1]) if b>=0 else (a+b*pi[1],a+b*pi[0])
 assert lo>0 or hi<0,'Independent exact comparison unresolved'
 return 1 if lo>0 else -1
ranked=[tuple(x['connector_ids']) for x in produced['proposals']]
assert len(ranked)==32 and len(set(ranked))==len(ranked)
assert all(compare(a,b)<0 for a,b in zip(ranked,ranked[1:]))
assert all(compare(ids,ranked[-1])>0 for ids in reference if ids not in set(ranked))
write(out/'independent-assignments.json',[{'connector_ids':list(ids),'tee_ids':list(v[0]),'nominal_cost':list(v[1])} for ids,v in sorted(reference.items())])
result={'status':'PASS','parent_function_domain':domain,'complete_assignments':len(reference),'prefix_checked':len(ranked),
        'independent_enumeration_seconds':seconds,'pi_bounds':list(map(str,pi)),'kernel_producer_or_verifier_invoked':False,
        'input_sha256':sha(out/'catalogue.json'),'assignments_sha256':sha(out/'independent-assignments.json'),
        'oracle_source_sha256':sha(test),'runner_sha256':sha(out/'runner.py'),
        'scope':'Independent nominal finite topology/complete ledger/prefix oracle; no native geometry or operating claim'}
write(out/'result.json',result)
print(json.dumps({'directory':str(out),'result_sha256':sha(out/'result.json'),**result}))
