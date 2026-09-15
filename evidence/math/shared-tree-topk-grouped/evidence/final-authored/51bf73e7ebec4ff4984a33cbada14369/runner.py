"""Final frozen grouped traversal, explicit bounded authored catalogue queries."""
from pathlib import Path
import hashlib,json,shutil,sys,time,uuid

S=Path(__file__).resolve().parent
P=S.parent/'general-shared-tree-native/catalogue-probes/b66610f8c6b54966aa8cf2b7a9bf8d1e'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):p.write_text(json.dumps(x,indent=2)+'\n',encoding='utf-8')
v=read(S/'latest-validation.json');assert v['status']=='PASS'
snap=Path(v['snapshot']);out=S/'evidence/final-authored'/uuid.uuid4().hex;out.mkdir(parents=True)
shutil.copyfile(__file__,out/'runner.py')
for name,expected in v['source_files'].items():
 q=out/name;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(snap/name,q);assert sha(q)==expected
inputs={}
for n in (5,6,7,8):
 d=out/str(n);d.mkdir()
 for p in sorted((P/str(n)).glob('*.json')):
  q=d/p.name;shutil.copyfile(p,q);inputs[q.relative_to(out).as_posix()]=sha(q)
cases=[(5,8,16_777_216),(6,8,16_777_216),(7,2,16_777_216),(8,1,16_777_216),(8,2,33_554_432)]
limits=dict(max_connectors=512,max_states=50000,max_transitions=2_000_000,
            max_label_pairs=10_000_000,max_work=20_000_000)
write(out/'declaration.json',{'source_files':v['source_files'],'validation_sha256':v['receipt_sha256'],
 'inputs':inputs,'cases':cases,'limits':limits,'seconds_per_phase':60,'runner_sha256':sha(out/'runner.py'),
 'scope':'Exact nominal finite-catalogue proof; no native/geometry/pressure acceptance claim.'})
sys.path.insert(0,str(out/'src'))
from oma.optimization import shared_tree_topk as t
print(json.dumps({'started':str(out)}),flush=True)
records=[]
for n,k,byte_limit in cases:
 p=read(out/str(n)/'generated.json')['catalogue'];kwargs={**limits,'k':k,'max_bytes':byte_limit}
 def invoke(checker,cert=None):
  started=time.perf_counter();deadline=started+60;sentinel=TimeoutError('Declared60secondphase')
  def tick(*args):
   if time.perf_counter()>=deadline:raise sentinel
  try:r=t.verify_shared_tree_topk_catalogue(p,cert,checkpoint=tick,**kwargs) if checker else t.compile_shared_tree_topk_catalogue(p,checkpoint=tick,**kwargs)
  except TimeoutError as e:
   assert e is sentinel;r={'status':'UNKNOWN','reason':'BENCHMARK_DEADLINE','proof_complete':False,'proposals':[],'exception_identity_preserved':True}
  return r,time.perf_counter()-started
 a,at=invoke(False);write(out/str(n)/f'produced-k{k}.json',a)
 b,bt=invoke(True,a['certificate']) if a['status']=='CERTIFIED' else ({'status':'NOT_RUN'},0)
 write(out/str(n)/f'checked-k{k}.json',b)
 passed=a['status']=='CERTIFIED' and b['status']=='PASS'
 if passed:assert a['proposals']==b['proposals'] and a['counts']['complete_assignments']==b['counts']['complete_assignments']
 r={'sinks':n,'k':k,'max_bytes':byte_limit,'producer_status':a['status'],'checker_status':b['status'],
    'producer_reason':a.get('reason'),'checker_reason':b.get('reason'),'producer_seconds':at,'checker_seconds':bt,
    'producer_work':a.get('work'),'checker_work':b.get('work'),'combined_work':a.get('work',0)+b.get('work',0),
    'counts':a.get('counts'),'certificate_root':a.get('certificate_root'),'independently_checked':passed,
    'certificate_bytes':len(json.dumps(a['certificate'],sort_keys=True,separators=(',',':')).encode()) if 'certificate' in a else None}
 records.append(r);write(out/'progress.json',records);print(json.dumps(r),flush=True)
assert all(sha(snap/name)==expected==sha(out/name) for name,expected in v['source_files'].items())
assert all(sha(out/name)==expected==sha(P/name) for name,expected in inputs.items())
write(out/'result.json',{'status':'COMPLETED','source_and_inputs_unchanged':True,
 'declaration_sha256':sha(out/'declaration.json'),'cases':records,'scope':'Nominal finite catalogue only; per-query status controls authority.'})
write(out/'file-index.json',{p.relative_to(out).as_posix():sha(p) for p in sorted(out.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.name!='file-index.json'})
print(json.dumps({'completed':str(out),'result_sha256':sha(out/'result.json')}),flush=True)
