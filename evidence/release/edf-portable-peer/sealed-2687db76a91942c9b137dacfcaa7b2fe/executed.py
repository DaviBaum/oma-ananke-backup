"""Independent exact index/payload/receipt audit of the sealed EDF package."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib,json,shutil,sys,time,uuid,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').exists())
BASE=ROOT/'evidence/dependencies/native-build/portable-candidates/edf555760245-0223f1d6bacc'
PRIOR=ROOT/'evidence/release/edf-portable-peer/f6ffe9dc5a7b4fa09bdda4f4d5b77e45'
PACKAGE=ROOT/'.release/native-build/portable-candidates/edf555760245-0223f1d6bacc'
def sha(p):
    with Path(p).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def write(p,v):Path(p).write_text(json.dumps(v,indent=2)+'\n',encoding='utf8')
start=time.perf_counter();out=ROOT/'evidence/release/edf-portable-peer'/('sealed-'+uuid.uuid4().hex);out.mkdir(parents=True)
shutil.copyfile(__file__,out/'executed.py')
handoff=read(BASE/'sealed-handoff.json');portable=read(BASE/'result.json');indexpath=PACKAGE/'artifact-files.json';index=read(indexpath)
initial_handoff=sha(BASE/'sealed-handoff.json');initial_index=sha(indexpath)
assert initial_handoff=='edc9be98f4337f222d599b317eb2b79acebae1943b09acc393f5b88317de8b08'
assert initial_index=='e11e99e855797e9fee65c674dc9c54a1de4ad022e8696f8460fe94fc45e28f5d'
assert Path(handoff['package']).resolve()==PACKAGE
assert handoff['status']=='ISOLATED_NATIVE_PORTABLE_CANDIDATE_SEALED_NOT_PROMOTED'
assert sha(BASE/'result.json')==handoff['validation_result_sha256']
assert handoff['checker_version']==portable['identity']['checker_version']
assert initial_index==handoff['artifact_index_sha256']
assert index['status']=='COMPLETE_LOCAL_CANDIDATE_FILE_INDEX' and index['exclusions']==['artifact-files.json itself']
rows=index['files'];expected={r['path']:r for r in rows}
assert len(rows)==len(expected)==index['file_count']==handoff['file_count']==14578
assert sum(r['bytes'] for r in rows)==index['logical_bytes']==handoff['logical_bytes']==1983035284
actual={}
for p in PACKAGE.rglob('*'):
    assert not p.is_symlink() and not p.is_junction()
    if p.is_file() and p!=indexpath:
        assert p.resolve().is_relative_to(PACKAGE)
        actual[p.relative_to(PACKAGE).as_posix()]=p
assert set(actual)==set(expected)
def check(name):
    p=actual[name];before=p.stat();h=sha(p);after=p.stat();r=expected[name]
    assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
    assert (h,after.st_size)==(r['sha256'],r['bytes']),name
    return 1
with ThreadPoolExecutor(max_workers=4) as pool:assert sum(pool.map(check,sorted(actual)))==len(rows)
payload=read(PACKAGE/'validated-payload.json')
assert sha(PACKAGE/'validated-payload.json')==portable['validated_payload_manifest_sha256']==handoff['validated_payload_manifest_sha256']
assert all(expected[n]['sha256']==r['sha256'] and expected[n]['bytes']==r['bytes'] for n,r in payload['files'].items())
sources={n.removeprefix('src/'):r['sha256'] for n,r in payload['files'].items() if n.startswith('src/') and n.endswith('.py')}
assert sources==portable['source_python_files'] and len(sources)==112
native=Path(portable['identity']['extension']).resolve();assert native.is_relative_to(PACKAGE)
assert expected[native.relative_to(PACKAGE).as_posix()]['sha256']==handoff['native_extension_sha256']==portable['identity']['extension_sha256']
assert Path(sys.executable).resolve()==PACKAGE/'runtime/python.exe'
for name in ('native_package_evidence.py','native_command_evidence.py','native_real_model_validation.py'):
    assert sha(ROOT/'scripts'/name)==sha(PACKAGE/'provenance/build-recipes'/name)
    shutil.copyfile(ROOT/'scripts'/name,out/name)
sys.path.insert(0,str(PACKAGE/'src'));sys.path.insert(0,str(ROOT/'scripts'))
from oma.build_identity import checker_version
from native_package_evidence import verify_checkpoint_inputs,verify_real_model_receipt,real_model_inputs
from native_command_evidence import candidate_command_closure
assert checker_version()==handoff['checker_version']
checkpoint,inputs=verify_checkpoint_inputs(PACKAGE,portable)
full=read(BASE/'bundled-full-suite.json')
assert sha(BASE/'bundled-full-suite.json')==handoff['bundled_full_suite_sha256']
assert sha(BASE/'bundled-tests.xml')==full['test_xml_sha256']==handoff['bundled_test_xml_sha256']=='fb8a4ec4be7a10fcda7124852bb9c2e60a623b5d749cfb5cfaf9a90df82c4250'
assert full['checker_version']==handoff['checker_version'] and full['source_checkpoint']==portable['source_checkpoint']
assert full['portable_validation_result_sha256']==sha(BASE/'result.json')
assert full['validated_payload_manifest_sha256']==portable['validated_payload_manifest_sha256']
assert full['test_source_manifest']==inputs
nodespath=PACKAGE/'provenance/checkpoint-validation/selected-tests.args';nodes=nodespath.read_text().splitlines()
assert sha(nodespath)==full['test_node_manifest_sha256']==portable['application_test_validation']['test_node_manifest_sha256']
assert len(nodes)==len(set(nodes))==3012
identities=[]
for node in nodes:
    parts=node.split('::');assert parts[0].endswith('.py') and len(parts)>=2
    cls=parts[0][:-3].replace('/','.').replace('\\','.')
    if len(parts)>2:cls+='.'+'.'.join(parts[1:-1])
    identities.append((cls,parts[-1]))
xml=ET.parse(BASE/'bundled-tests.xml');cases=xml.findall('.//testcase')
assert Counter((c.attrib['classname'],c.attrib['name']) for c in cases)==Counter(identities)
assert not xml.findall('.//failure') and not xml.findall('.//error')
skips=[{'classname':c.attrib['classname'],'name':c.attrib['name'],'reason':c.find('skipped').attrib.get('message')} for c in cases if c.find('skipped') is not None]
assert len(skips)==3 and {r['name'] for r in skips}=={'test_private_bridge_corruption_is_not_reused['+f+']' for f in ('binary','configuration','extra_startup')}
assert all(r['classname']=='tests.test_windows_job_containment' and r['reason']=='Current Python is a direct interpreter and needs no bridge' for r in skips)
assert skips==full['skipped']==handoff['bundled_not_applicable'] and full['passed']==handoff['bundled_passed']==3009 and full['failed']==0
for name in ('bundled-full-suite.json','bundled-tests.xml'):
    assert sha(BASE/name)==sha(PACKAGE/'provenance'/name)
guard=read(BASE/'offline-guard-probe.json');assert sha(BASE/'offline-guard-probe.json')==handoff['offline_guard_sha256']
assert guard['package_validation_sha256']==sha(BASE/'result.json')
assert len(guard['records'])==2 and {r['mode'] for r in guard['records']}=={'BUNDLED','FROZEN_CHECKER'}
assert all(r['status']=='PYTHON_SOCKET_CONNECT_DENIED' and r['checker_version']==handoff['checker_version'] for r in guard['records'])
roles={'joint_fitting_budget':('real-office-validation.json','real_office_validation_sha256'),
       'pressure_network':('real-office-pressure-validation.json','real_office_pressure_validation_sha256'),
       'coupled_pressure_network':('real-office-coupled-pressure-validation.json','real_office_coupled_pressure_validation_sha256')}
assert set(real_model_inputs(PACKAGE,portable)['roles'])==set(roles)
receipts={};scopes={};prior_hashes=read(PRIOR/'receipt-hashes.json')
for role,(name,key) in roles.items():
    assert sha(BASE/name)==handoff[key]==sha(PACKAGE/'provenance'/name)==prior_hashes[str(BASE/name)]
    receipts[role]=read(BASE/name);scopes[role]=verify_real_model_receipt(PACKAGE,portable,BASE/'result.json',role,receipts[role])
assert scopes==handoff['real_model_scopes']
assert scopes['joint_fitting_budget']['source_pairs']==4818 and scopes['joint_fitting_budget']['cross_route_pairs']==5
assert scopes['pressure_network']['source_pairs']==3212 and scopes['coupled_pressure_network']['source_pairs']==5621
closure=candidate_command_closure(PACKAGE,portable,checkpoint,full,receipts,workspace=ROOT,
    commands_root=ROOT/'evidence/dependencies/native-build/commands',validation_directory=BASE)
closurepath=PACKAGE/'provenance/command-closure.json'
assert closure==read(closurepath) and sha(closurepath)==handoff['command_closure_sha256']
for name,row in closure['commands'].items():
    for relative,h in row['files'].items():assert expected['provenance/commands/'+name+'/'+relative]['sha256']==h
assert sha(indexpath)==initial_index and sha(BASE/'sealed-handoff.json')==initial_handoff
assert set(actual)=={p.relative_to(PACKAGE).as_posix() for p in PACKAGE.rglob('*') if p.is_file() and p!=indexpath}
result={'schema':'oma.independent-sealed-portable-audit/1','status':'EDF_SEALED_PACKAGE_INDEPENDENT_AUDIT_PASS',
    'package':str(PACKAGE),'sealed_handoff_sha256':initial_handoff,'index_sha256':initial_index,
    'file_count':len(rows),'logical_bytes':index['logical_bytes'],'checker_version':checker_version(),
    'source_checkpoint':portable['source_checkpoint'],'source_python_files':len(sources),'native_extension_sha256':sha(native),
    'validated_payload_manifest_sha256':sha(PACKAGE/'validated-payload.json'),'payload_files':len(payload['files']),
    'copied_test_inputs':len(inputs['files']),'bundled_suite':{'nodes':3012,'passed':3009,'named_not_applicable':skips,'xml_sha256':sha(BASE/'bundled-tests.xml')},
    'command_count':len(closure['commands']),'command_closure_sha256':sha(closurepath),'real_model_scopes':scopes,
    'prior_receipt_review_sha256':sha(PRIOR/'result.json'),'package_written':False,'native_tests_rerun':False,
    'scope':'Exact sealed file inventory and byte hashes, tested payload/source/native identities, complete XML accounting, candidate-specific commands, and three fresh managed saved-Office receipts. No promotion or broader engineering applicability claim.',
    'seconds':time.perf_counter()-start}
write(out/'result.json',result)
for p in (BASE/'sealed-handoff.json',indexpath,closurepath):shutil.copyfile(p,out/p.name)
(out/'README.md').write_text('Every indexed package file was independently rehashed and the exact file set matched. The 3,012 bundled test identities comprise 3,009 passes and only the three declared direct-interpreter bridge cases. All three saved Office receipts, tested source/native identities, copied test inventory, two denial modes and candidate-specific command closure match the seal. The package was not changed and native geometry tests were not rerun.\n',encoding='utf8')
print(json.dumps({'directory':str(out),'status':result['status'],'result_sha256':sha(out/'result.json'),'seconds':result['seconds']}))
