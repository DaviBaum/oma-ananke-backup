"""Seal the exact private kernel/test/evidence handoff; no production writes."""
from pathlib import Path
import hashlib,json

STAGE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,x):p.write_text(json.dumps(x,indent=2)+'\n',encoding='utf-8')
assert not (STAGE/'handoff.json').exists()
latest=read(STAGE/'latest-validation.json');assert latest['status']=='PASS' and latest['counts']=={'testcase':175,'failure':0,'error':0,'skipped':0}
validation=Path(latest['directory']);manifest=read(validation/'manifest.json')
assert sha(validation/'result.json')==latest['receipt_sha256']
assert all(sha(STAGE/k)==v for k,v in manifest['inputs'].items())
module='src/oma/optimization/shared_tree_synthesis.py'
assert sha(STAGE/module)==latest['module_sha256']=='9a9f6c76b4691d70d5d9a21a5a371635549992f5de06fbd0f4ffaf745c97c55d'
merge_paths=[module,'tests/test_general_shared_tree_synthesis.py','tests/fixtures/general-shared-tree-synthesis/legacy003.py',
             'docs/math/general-shared-tree-synthesis.md']
merge={p:sha(STAGE/p) for p in merge_paths}
preconditions={p:v for p,v in read(STAGE/'base-manifest.json').items() if p!=module}
oracle=STAGE/'evidence/authored-oracle/facbc3fa1d7a4da8a958d81ceb2f2db2/result.json'
assert read(oracle)['status']=='PASS' and read(oracle)['complete_assignments']==18048
exclude={'__pycache__','.pytest_cache','temp'}
files={p.relative_to(STAGE).as_posix():sha(p) for p in sorted(STAGE.rglob('*')) if p.is_file()
       and not exclude.intersection(p.relative_to(STAGE).parts) and p.name not in ('file-index.json','handoff.json')}
write(STAGE/'file-index.json',{'schema':'oma.private-component-evidence-index/1','files':files,
    'exclusions':['bytecode/pytest caches','temporary test directories','file-index.json','handoff.json'],
    'scope':'Exact files at this handoff; any later peer review is a separately indexed supplement'})
handoff={'schema':'oma.general-shared-tree-synthesis-handoff/1','status':'PASS','private_only':True,
    'module_sha256':latest['module_sha256'],'legacy_module_sha256':'0034130d057fbb012d031fb31a69ce89aac857ce6aeaf4d8a73f55c2d1a23d43',
    'merge_files':merge,'unchanged_test_preconditions':preconditions,'tested_input_files':manifest['inputs'],
    'tests':{'passed':175,'unchanged_legacy':85,'new':90,'receipt':str(validation.relative_to(STAGE)/'result.json'),
             'receipt_sha256':latest['receipt_sha256'],'exact_node_multiset':True,'inputs_unchanged':True},
    'api':{'model_schema':'oma.shared-tree-catalogue/1','certificate_schema':'oma.shared-tree-synthesis-certificate/1',
           'public_functions':['compile_shared_tree_catalogue','verify_shared_tree_catalogue'],
           'new_domain':'4 through 8 sinks; old 2/3 result and callback bytes preserved',
           'new_keyword':'max_partial_trees=20000, strict integer1..200000; attempted joins/transitions charged before allocations',
           'required_success':'complete independently reconstructed ledger and exact nominal ranked prefix',
           'resource_failure':'UNKNOWN, proof_complete false, no proposals or partial certificate authority'},
    'source_excerpts_sha256':sha(STAGE/'source-excerpts.json'),'full_original_algorithms_implemented':False,
    'native_adapter_and_geometry_service_authority':'External; not implemented or authorized by this pure kernel handoff',
    'independent_authored_oracle':{'receipt':str(oracle.relative_to(STAGE)),'sha256':sha(oracle),'complete_assignments':18048,'prefix':32},
    'index':'file-index.json','index_sha256':sha(STAGE/'file-index.json'),'indexed_files':len(files)}
write(STAGE/'handoff.json',handoff)
assert all(sha(STAGE/k)==v for k,v in files.items())
print(json.dumps({'handoff':str(STAGE/'handoff.json'),'handoff_sha256':sha(STAGE/'handoff.json'),
                  'index_sha256':sha(STAGE/'file-index.json'),'indexed_files':len(files),'merge_files':merge}))
