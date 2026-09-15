"""Prepare exact prior full-suite inputs plus the new private development tests."""
from pathlib import Path
import hashlib,json,shutil,uuid

p=Path(__file__).resolve().parent
root=next(x for x in p.parents if (x/'AGENTS.md').is_file())
base=root/'evidence/release/coupled-tree-full-17ea63bc503a4b78bb572ffee1dce06f/result.json'
record=json.loads(base.read_text(encoding='utf8'))
assert record['status']=='PASS' and record['passed']==2467
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
out=p/'integration-inputs'/uuid.uuid4().hex;out.mkdir(parents=True)
for relative,expected in record['snapshot_files'].items():
    original=Path(record['test_snapshot'])/relative
    assert sha(original)==expected,original
    target=out/relative;target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(original,target);assert sha(target)==expected
assert len(record['snapshot_files'])==131
new_inputs={}
for source in sorted((p/'tests').glob('*.py')):
    target=out/'tests'/source.name
    assert not target.exists(),target
    shutil.copyfile(source,target);new_inputs[target.relative_to(out).as_posix()]=sha(source)
manifest={'status':'PRIOR_FULL_SUITE_AND_ROOT_TESTS_PREPARED','directory':str(out),
    'prior_receipt':str(base),'prior_receipt_sha256':sha(base),'prior_input_files':record['snapshot_files'],
    'new_root_input_files':new_inputs,
    'pending_inputs':['shared_tree_synthesis final85cases/fourfixtures','shared_tree_catalogue_check finalhandoff tests/fixtures'],
    'all_tests_run':False}
(out/'preparation.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf8')
print(json.dumps({'status':manifest['status'],'directory':str(out),'prior_inputs':len(record['snapshot_files']),'new_inputs':len(new_inputs)}))
