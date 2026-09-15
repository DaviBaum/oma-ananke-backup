"""Seal private and portable public grouped-kernel evidence, without old edits."""
from pathlib import Path
import hashlib,json,shutil

S=Path(__file__).resolve().parent
ROOT=S.parents[2]
PUBLIC=ROOT/'evidence/math/shared-tree-topk-grouped'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):p.write_text(json.dumps(x,indent=2)+'\n',encoding='utf-8')
v=read(S/'latest-validation.json');assert v['status']=='PASS' and v['counts']['testcase']==303
assert v['source_files']['src/oma/optimization/shared_tree_topk.py']=='116390796eab23e2921915d982130ee9739439d8696d11e1694c96b76e79e063'
bench=S/'evidence/final-authored/51bf73e7ebec4ff4984a33cbada14369/result.json'
peer=S/'evidence/peer-review/04523011a8cc4d28b3b956fec93b2465/result.json'
assert sha(bench)=='f6666b9c961cf2142e155879f5d1d0b192afd18f366f1589a56d0a3c5171b797'
assert sha(peer)=='0e3ec001819fbefee2eea866064267a43fdc830f2e3d456aef2223a02b45ca88'
assert all(sha(S/name)==value for name,value in v['source_files'].items())
old=S.parent/'shared-tree-topk-synthesis'
old_fail=old/'evidence/actual-five-eight/d9ee67fce677455888a57b1633023d91'
dest=S/'evidence/prior-d04/d9ee67fce677455888a57b1633023d91'
assert not dest.exists()
for p in old_fail.rglob('*'):
    if p.is_file() and '__pycache__' not in p.parts:
        q=dest/p.relative_to(old_fail);q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q);assert sha(p)==sha(q)
for name in ('handoff.json','file-index.json','supplement-handoff.json','supplement-file-index.json'):
    shutil.copyfile(old/name,S/'evidence/prior-d04'/name)
write(S/'evidence/prior-d04/README.json',{
    'scope':'Original d04 dense5-8 benchmark copied unchanged with its complete local input/dependency closure. Original handoff/index metadata are reference records; unrelated old payload remains in its original stage.',
    'original_directory':str(old_fail),'original_result_sha256':sha(old_fail/'result.json'),
    'retained_result_sha256':sha(dest/'result.json')})
merge_names=['src/oma/optimization/shared_tree_topk.py','tests/test_shared_tree_topk_grouped.py',
 'tests/fixtures/shared-tree-topk/d04_shared_tree_topk.py','tests/fixtures/shared-tree-topk/authored-six-catalogue.json',
 'docs/math/shared-tree-topk-grouped.md']
merge={name:sha(S/name) for name in merge_names}
excluded={'__pycache__','.pytest_cache','temp'}
files={}
for p in sorted(S.rglob('*')):
    if (p.is_file() and not excluded.intersection(p.relative_to(S).parts)
            and p.relative_to(S).as_posix() not in ('handoff.json','file-index.json','public-handoff.json')):
        files[p.relative_to(S).as_posix()]={'sha256':sha(p),'bytes':p.stat().st_size}
write(S/'file-index.json',files)
handoff={'schema':'oma.shared-tree-topk-grouped-handoff/1','status':'PASS','private_only_implementation':True,
 'merge_files':merge,'source_dependencies':{name:value for name,value in v['source_files'].items() if name not in merge},
 'previous_kernel_sha256':'d04f2ad9ffb72f9935cba93472f49f5dbbe257a0595ccc8c39dcb62d14ca2dbc',
 'certificate_schema':'oma.shared-tree-topk-certificate/1','schema_and_proposals_unchanged':True,
 'certificate_byte_compatibility':'303 scoped tests plus42 separate edge-subset peer cases; all completed old/new equivalent queries agree.',
 'validation':{'path':'validation/1993e0b4475f44398780d4789f143d75/result.json','sha256':v['receipt_sha256'],
   'passed':303,'previous_tests_unchanged':261,'new_tests':42,'source_files':6,'test_config_support_inputs':14,
   'exact_node_multiset':True,'source_inputs_unchanged':True},
 'peer':{'path':peer.relative_to(S).as_posix(),'sha256':sha(peer),'status':'PASS'},
 'authored_benchmark':{'path':bench.relative_to(S).as_posix(),'sha256':sha(bench),'cases':read(bench)['cases']},
 'composite_policy':{'path':'evidence/composite-policy/result.json','sha256':sha(S/'evidence/composite-policy/result.json'),
                     'status':'RECOMMENDATION_NOT_NATIVE_VALIDATION'},
 'native_authority':False,'full_original_algorithms_implemented':False,
 'file_index':{'path':'file-index.json','sha256':sha(S/'file-index.json'),'files':len(files)}}
write(S/'handoff.json',handoff)
assert not PUBLIC.exists();PUBLIC.mkdir(parents=True)
for name,value in files.items():
    p=S/name;q=PUBLIC/name;q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
    assert sha(q)==value['sha256']
for name in ('handoff.json','file-index.json'):shutil.copyfile(S/name,PUBLIC/name)
retention={'schema':'oma.shared-tree-topk-grouped-public-retention/1','status':'PASS',
 'handoff_sha256':sha(PUBLIC/'handoff.json'),'file_index_sha256':sha(PUBLIC/'file-index.json'),
 'indexed_files':len(files),'all_public_payload_hashes_match':True,'all_original_records_unchanged':True,
 'note':'Paths in handoff and index resolve within this public directory; original execution logs may preserve historical absolute paths. No native acceptance or production integration claim.'}
write(PUBLIC/'public-retention.json',retention)
write(S/'public-handoff.json',{'directory':str(PUBLIC),'receipt_sha256':sha(PUBLIC/'public-retention.json'),**retention})
print(json.dumps({'private_handoff_sha256':sha(S/'handoff.json'),'public_directory':str(PUBLIC),
                  'public_receipt_sha256':sha(PUBLIC/'public-retention.json'),**retention}))
