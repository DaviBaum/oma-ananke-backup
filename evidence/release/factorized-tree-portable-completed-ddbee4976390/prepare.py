"""Prepare a distinct compact/factorized portable run after both exact native suites pass."""
import hashlib,json,shutil,sqlite3,zlib
from pathlib import Path
import uuid
ROOT=Path(__file__).resolve().parents[3]
SOURCE='f73a8793ae0df76d9ec53400cec18b05d2731f63c735b225c2246fee62df6b21'
CUSTOM=ROOT/'evidence/dependencies/native-build/checkpoint-validation/f73a8793ae0d-0cf1c8bf0868/result.json'
ORIGINAL=ROOT/'.oma/development/factorized-tree-pressure/combined-validation/d6d1204384b84bc6b0a5c5e47c5540ad/result.json'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,v):Path(p).write_text(json.dumps(v,indent=2),encoding='utf-8')
c=read(CUSTOM);o=read(ORIGINAL)
assert c['status']=='CUSTOM_NATIVE_NEW_CHECKPOINT_FULL_SUITE_PASS' and c['passed']==3275
assert o['status']=='PASS' and o['test_node_count']==3275
assert o['checker_version']=='oma-independent-checker/2:'+SOURCE and c['source_checkpoint']==SOURCE
audit=read(CUSTOM.parent/'post-run-exact-audit.json')
assert audit['result_sha256']==sha(CUSTOM) and audit['test_node_count']==3275
assert audit['source_python_files']==114 and audit['test_input_files']==305 and c['driver_bytes_unchanged'] is True
old=ROOT/'.release/native-build/portable-candidates/5e8fe9659cfd-82d3a00a6ff4/provenance/real-model-validation-inputs.json'
plan=read(old);assert plan['schema']=='oma.portable-real-model-inputs/2'
plan['source_checkpoint']=SOURCE
plan['scope']='Three independently retained Office exported cases rechecked by the new compact/factorized native bundle. Explicit compact finite-catalogue generation and factorized coupled pressure for supported four-to-eight-sink trees are separately covered by the exact3275 suite, including actual native acceptance/export tests; no claim of complete-building routing or global physical optimality.'
bindings={}
for role,entry in plan['roles'].items():
    store=Path(entry['original_store']);database=store/'oma.sqlite3'
    with sqlite3.connect(database.as_uri()+'?mode=ro',uri=True) as db:
        row=db.execute('SELECT state_root,report_root,payload,status FROM candidates WHERE id=?',(entry['candidate_id'],)).fetchone()
    assert row and row[0]==entry['candidate_root'] and row[1]==entry['prior_report_root'] and row[3]=='CHECKED'
    assert json.loads(row[2])['kind']==entry['physical_kind']
    report=json.loads(zlib.decompress((store/'blobs'/(row[1]+'.json.z')).read_bytes()))
    assert report['checker_version']==entry['prior_checker_version'] and report['status']=='PASS'
    bindings[role]={'database':str(database),'database_sha256_at_preparation':sha(database),'candidate_root':row[0],'prior_report_root':row[1]}
directory=ROOT/'evidence/release/factorized-tree-portable-preparation'/uuid.uuid4().hex;directory.mkdir(parents=True)
write(directory/'real-model-inputs.json',plan)
drivers={}
for p in sorted((ROOT/'scripts').glob('native_*.py')):
    target=directory/'driver-sources'/p.name;target.parent.mkdir(exist_ok=True);shutil.copyfile(p,target)
    drivers[p.relative_to(ROOT).as_posix()]=sha(p)
for name in ('run-build.ps1','run-validations.ps1','run-seal.ps1'):
    shutil.copyfile(ROOT/'.oma/development/coupled-portable-validation'/name,directory/name)
shutil.copyfile(__file__,directory/'prepare-executed.py')
for p,name in ((ORIGINAL,'original-full-pass.json'),(CUSTOM,'custom-full-pass.json'),(CUSTOM.parent/'post-run-exact-audit.json','custom-full-audit.json')):
    shutil.copyfile(p,directory/name)
prep={'schema':'oma.factorized-tree-portable-preparation/1','source_checkpoint':SOURCE,'checkpoint_validation':str(CUSTOM),
      'checkpoint_validation_sha256':sha(CUSTOM),'original_full_receipt':str(ORIGINAL),'original_full_sha256':sha(ORIGINAL),
      'real_model_inputs_sha256':sha(directory/'real-model-inputs.json'),'prior_sealed_three_role_declaration_sha256':sha(old),
      'original_read_only_candidate_bindings':bindings,'driver_sources':drivers,
      'ui_files':{p.relative_to(ROOT/'ui/dist').as_posix():sha(p) for p in (ROOT/'ui/dist').rglob('*') if p.is_file()},
      'expected_nodes':3275,'expected_inputs':305,'expected_app_files':114,
      'scope':'Distinct compact/factorized bundle; old packages, live Store and UI source untouched. Test snapshot uses exact original305 inputs; the current package drivers match that same frozen input inventory.'}
assert len(prep['ui_files'])==6
write(directory/'preparation.json',prep)
print(directory)
