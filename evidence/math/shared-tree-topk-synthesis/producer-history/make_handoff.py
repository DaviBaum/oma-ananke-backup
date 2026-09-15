"""Seal the first tested compact-kernel handoff; later reviews are supplements."""
from pathlib import Path
import hashlib,json
S=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,x):p.write_text(json.dumps(x,indent=2)+'\n',encoding='utf-8')
assert not (S/'handoff.json').exists()
r=read(S/'latest-validation.json');assert r['status']=='PASS' and r['counts']=={'testcase':261,'failure':0,'error':0,'skipped':0}
manifest=read(Path(r['directory'])/'manifest.json')
assert all(sha(S/k)==v for k,v in {**manifest['source_files'],**manifest['input_files']}.items())
paths=['src/oma/optimization/shared_tree_topk.py','tests/test_shared_tree_topk.py',
       'tests/fixtures/shared-tree-topk/authored-four-catalogue.json','tests/fixtures/shared-tree-topk/authored-four-v1-prefix32.json',
       'docs/math/shared-tree-topk.md']
merge={k:sha(S/k) for k in paths}
files={p.relative_to(S).as_posix():sha(p) for p in sorted(S.rglob('*')) if p.is_file()
       and not {'__pycache__','.pytest_cache','temp','peer-review-topk'}.intersection(p.relative_to(S).parts)
       and p.name not in ('handoff.json','file-index.json')}
write(S/'file-index.json',{'schema':'oma.private-component-evidence-index/1','files':files,
      'scope':'Exact initial261-case handoff files; later peer/catalogue benchmarks are separate supplements'})
h={'schema':'oma.shared-tree-topk-handoff/1','status':'PASS','private_only':True,'merge_files':merge,
   'source_dependencies':{k:v for k,v in manifest['source_files'].items() if k not in merge},
   'unchanged_test_dependencies':{k:v for k,v in manifest['input_files'].items() if k not in merge},
   'validation':{'passed':261,'new_cases':86,'unchanged_cases':175,'receipt':str(Path(r['directory']).relative_to(S)/'result.json'),
                 'receipt_sha256':r['receipt_sha256'],'exact_node_multiset':True,'all_files_unchanged':True},
   'api':{'functions':['compile_shared_tree_topk_catalogue','verify_shared_tree_topk_catalogue'],
          'statuses':['CERTIFIED','PASS','UNKNOWN','INVALID_INPUT','FAIL'],'proposal_shape':'identical to v1',
          'count_encoding':'counts.complete_assignments is an exact canonical decimal string',
          'certificate_schema':'oma.shared-tree-topk-certificate/1','k_default':8,'k_range':[1,32]},
   'actual_four_benchmark':'evidence/actual-four/4dfe4a051e2c4f0782b8b4e7c4937af0/result.json',
   'actual_four_benchmark_sha256':sha(S/'evidence/actual-four/4dfe4a051e2c4f0782b8b4e7c4937af0/result.json'),
   'full_original_algorithms_implemented':False,'native_authority':False,
   'file_index':'file-index.json','file_index_sha256':sha(S/'file-index.json'),'indexed_files':len(files)}
write(S/'handoff.json',h)
assert all(sha(S/k)==v for k,v in files.items())
print(json.dumps({'handoff':str(S/'handoff.json'),'handoff_sha256':sha(S/'handoff.json'),
                 'index_sha256':sha(S/'file-index.json'),'merge_files':merge,'indexed_files':len(files)}))
