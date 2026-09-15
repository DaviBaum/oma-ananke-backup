"""Read-only pre-seal three-role receipt/source/checkpoint audit; no native geometry run."""
from pathlib import Path
import copy,hashlib,json,shutil,sys,uuid
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').exists())
EVIDENCE=ROOT/'evidence/dependencies/native-build/portable-candidates/f73a8793ae0d-ddbee4976390'
PACKAGE=ROOT/'.release/native-build/portable-candidates/f73a8793ae0d-ddbee4976390'
sys.path.insert(0,str(PACKAGE/'src'));sys.path.insert(0,str(ROOT/'scripts'))
from native_package_evidence import verify_checkpoint_inputs,verify_real_model_receipt,real_model_inputs
from oma.build_identity import checker_version
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf8'))
def dump(p,v):p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf8')
OUT=ROOT/'evidence/release/f73-portable-peer'/uuid.uuid4().hex;OUT.mkdir(parents=True);shutil.copyfile(__file__,OUT/'executed.py')
portable_path=EVIDENCE/'result.json';portable=read(portable_path)
assert Path(sys.executable).resolve()==PACKAGE/'runtime/python.exe'
assert checker_version()==portable['identity']['checker_version']=='oma-independent-checker/2:3492e0f42f803ff71dea9c70558bdd276c4b5469a3d17c00ae7c37b59dda7541'
fixed_paths=[portable_path,PACKAGE/'validated-payload.json',PACKAGE/'provenance/checkpoint-validation/result.json']
fixed_paths += [EVIDENCE/name for name in ('real-office-validation.json','real-office-pressure-validation.json','real-office-coupled-pressure-validation.json')]
before={str(p):sha(p) for p in fixed_paths}
sources={p.relative_to(PACKAGE/'src').as_posix():sha(p) for p in (PACKAGE/'src').rglob('*.py')}
assert sources==portable['source_python_files'] and len(sources)==114
payload=read(PACKAGE/'validated-payload.json');assert sha(PACKAGE/'validated-payload.json')==portable['validated_payload_manifest_sha256']
assert payload['checker_version']==portable['identity']['checker_version'] and payload['source_checkpoint']==portable['source_checkpoint']
assert {k.removeprefix('src/'):v['sha256'] for k,v in payload['files'].items() if k.startswith('src/') and k.endswith('.py')}==sources
native=Path(portable['identity']['extension']);assert native.resolve().is_relative_to(PACKAGE)
assert sha(native)==portable['identity']['extension_sha256']==payload['files'][native.relative_to(PACKAGE).as_posix()]['sha256']
assert sha(PACKAGE/'runtime/python.exe')==payload['files']['runtime/python.exe']['sha256']
checkpoint,inputs=verify_checkpoint_inputs(PACKAGE,portable)
assert portable['application_test_validation']['test_node_count']==portable['application_test_validation']['passed']==3275
declaration=real_model_inputs(PACKAGE,portable)
assert declaration['schema']=='oma.portable-real-model-inputs/2'
assert set(declaration['roles'])=={'joint_fitting_budget','pressure_network','coupled_pressure_network'}
results={}
roles={'joint_fitting_budget':'real-office-validation.json','pressure_network':'real-office-pressure-validation.json',
       'coupled_pressure_network':'real-office-coupled-pressure-validation.json'}
for role,name in roles.items():
    receipt=read(EVIDENCE/name)
    verified=verify_real_model_receipt(PACKAGE,portable,portable_path,role,receipt)
    if role=='joint_fitting_budget':
        assert verified['source_pairs']==4818 and verified['cross_route_pairs']==5
        assert verified['fittings']==verified['fitting_budget']==2
    elif role=='pressure_network':
        assert verified['physical_components']==4 and verified['physical_ports']==9
    else:
        assert verified['physical_components']==7 and verified['physical_ports']==16
        assert verified['pressure_mode']=='COUPLED_UNEQUAL_TREE'
    dump(OUT/(role+'.json'),verified)
    results[role]={'status':'INDEPENDENT_RECEIPT_BINDINGS_PASS','report_root':receipt['report_root'],
        'candidate_id':receipt['candidate_id'],'candidate_root':receipt['candidate_root'],'expected_export_sha256':declaration['roles'][role]['expected_export_sha256'],
        'verified_denominators':verified,'retained_native_seconds':receipt['seconds'],
        'source_and_export_files':receipt['source_and_exported_files'],'original_unchanged':receipt['original_bytes_and_head_unchanged']}
mutated=copy.deepcopy(portable);mutated['source_python_files']['oma/routing/coupled_tree_pressure.py']='0'*64
try:verify_real_model_receipt(PACKAGE,mutated,portable_path,'coupled_pressure_network',read(EVIDENCE/roles['coupled_pressure_network']))
except AssertionError as error:
    assert 'Replay source differs' in str(error);negative={'status':'REJECTED_AS_REQUIRED','reason':str(error),'actual_package_changed':False}
else:raise AssertionError('Forged loaded-source map was accepted')
assert {str(p):sha(p) for p in fixed_paths}==before
assert {p.relative_to(PACKAGE/'src').as_posix():sha(p) for p in (PACKAGE/'src').rglob('*.py')}==sources
for name in ('native_package_evidence.py','native_real_model_validation.py'):
    shutil.copyfile(ROOT/'scripts'/name,OUT/name)
dump(OUT/'source-map.json',sources);dump(OUT/'receipt-hashes.json',before)
result={'status':'F73_THREE_RECEIPT_SOURCE_AND_CHECKPOINT_PEER_PASS','package':str(PACKAGE),
    'checker_version':checker_version(),'source_python_files':114,'copied_test_inputs':len(inputs['files']),
    'custom_native_completed_nodes':3275,'three_roles':results,'forged_source_map':negative,
    'native_extension_sha256':sha(native),'payload_manifest_sha256':sha(PACKAGE/'validated-payload.json'),
    'scope':'Pre-seal read-only receipt/DB/blob/IFC/native-proof/source/checkpoint audit. No native geometry rerun. Complete bundled suite and final full file-set/payload index audit remain separate.',
    'full_payload_rehash_performed':False,'original_and_receipt_bytes_unchanged':True,'script_sha256':sha(OUT/'executed.py')}
dump(OUT/'result.json',result)
print(json.dumps({'out':str(OUT),'status':result['status'],'checker':result['checker_version'],'copied_test_inputs':result['copied_test_inputs']}))
