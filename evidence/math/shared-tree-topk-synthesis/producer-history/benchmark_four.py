"""Exact frozen top-K versus retained v1 outputs; no native geometry rerun."""
from pathlib import Path
import hashlib,json,os,shutil,sys,time,uuid

S=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,x):p.write_text(json.dumps(x,indent=2)+'\n',encoding='utf-8')
receipt=read(S/'latest-validation.json');assert receipt['status']=='PASS'
snap=Path(receipt['snapshot']);sys.path.insert(0,str(snap/'src'))
from oma.optimization import shared_tree_topk as t
out=S/'evidence/actual-four'/uuid.uuid4().hex;out.mkdir(parents=True)
for name in ('authored-four-catalogue.json','authored-four-v1-prefix32.json'):
 shutil.copyfile(snap/'tests/fixtures/shared-tree-topk'/name,out/name)
shutil.copyfile(__file__,out/'runner.py')
for name,value in receipt['source_files'].items():
 p=out/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(snap/name,p);assert sha(p)==value
p=read(out/'authored-four-catalogue.json');reference=read(out/'authored-four-v1-prefix32.json')
results={}
for k in (8,32):
 start=time.perf_counter();a=t.compile_shared_tree_topk_catalogue(p,k=k);pt=time.perf_counter()-start
 assert a['status']=='CERTIFIED';start=time.perf_counter();b=t.verify_shared_tree_topk_catalogue(p,a['certificate'],k=k);vt=time.perf_counter()-start
 assert b['status']=='PASS' and a['proposals']==b['proposals']==reference['proposals'][:k]
 assert int(a['counts']['complete_assignments'])==reference['complete_assignments']==18048
 write(out/f'produced-k{k}.json',a);write(out/f'checked-k{k}.json',b)
 size=len(json.dumps(a['certificate'],sort_keys=True,separators=(',',':'),ensure_ascii=False).encode())
 results[str(k)]={'producer_seconds':pt,'checker_seconds':vt,'producer_work':a['work'],'checker_work':b['work'],
    'combined_work':a['work']+b['work'],'certificate_bytes':size,'counts':a['counts'],'certificate_root':a['certificate_root'],
    'exact_v1_prefix_equal':True}
prior=S.parent/'general-shared-tree-synthesis/evidence/authored-query/131eb52a678c4853bbb8cb1701b20628/produced.json'
v1=read(prior);v1bytes=len(json.dumps(v1['certificate'],sort_keys=True,separators=(',',':'),ensure_ascii=False).encode())
record={'status':'PASS','source_files':receipt['source_files'],'validation_receipt_sha256':receipt['receipt_sha256'],
 'results':results,'retained_v1_certificate_bytes':v1bytes,'v1_certificate_root':v1['certificate_root'],
 'retained_v1_producer_work':2963067,'retained_v1_checker_work':3952986,
 'input_sha256':sha(out/'authored-four-catalogue.json'),'runner_sha256':sha(out/'runner.py'),
 'scope':'Exact same nominal catalogue/count/prefix; historical full-ledger timing is separate, no native or whole-algorithm claim'}
assert all(sha(snap/k)==v for k,v in receipt['source_files'].items())
write(out/'result.json',record)
print(json.dumps({'directory':str(out),'result_sha256':sha(out/'result.json'),**record}))
