"""One explicitly larger bounded query of the unchanged retained four-sink catalogue."""
from pathlib import Path
import hashlib,importlib.util,json,shutil,time,uuid

STAGE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,x):p.write_text(json.dumps(x,indent=2)+'\n',encoding='utf-8')
latest=read(STAGE/'latest-validation.json');source=Path(latest['source_snapshot']);assert sha(source)==latest['module_sha256']
spec=importlib.util.spec_from_file_location('bounded_authored_kernel',source);s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
prior=STAGE/'evidence/benchmarks/df96d890a508437fb1040115d679e733/current-authored-four/catalogue.json'
p=read(prior);out=STAGE/'evidence/authored-query'/uuid.uuid4().hex;out.mkdir(parents=True)
shutil.copyfile(prior,out/'catalogue.json');shutil.copyfile(__file__,out/'runner.py');shutil.copyfile(source,out/'shared_tree_synthesis.py')
options={'max_partial_trees':200000,'max_work':10000000}
start=time.perf_counter();a=s.compile_shared_tree_catalogue(p,**options);producer_seconds=time.perf_counter()-start
write(out/'produced.json',a)
result={'status':a['status'],'options':options,'production_seconds':producer_seconds,'producer_work':a['work'],
        'producer_counts':a.get('counts'),'reason':a.get('reason'),'module_sha256':sha(source),'input_sha256':sha(prior),
        'runner_sha256':sha(out/'runner.py'),'scope':'Unchanged authored finite catalogue only, larger declared computation budget; no native rerun or current geometry/service acceptance'}
if a['status']=='CERTIFIED':
 start=time.perf_counter();b=s.verify_shared_tree_catalogue(p,a['certificate'],**options);result['verification_seconds']=time.perf_counter()-start
 write(out/'checked.json',b);result.update(independent_check=b['status'],checker_counts=b.get('counts'),checker_work=b['work'])
 assert b['status']=='PASS'
assert sha(source)==latest['module_sha256'] and sha(prior)==sha(out/'catalogue.json')
write(out/'result.json',result)
print(json.dumps({'directory':str(out),'result_sha256':sha(out/'result.json'),**result}))
