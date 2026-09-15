"""Isolate the next pressure-generation profile from the running b965 regression."""
from pathlib import Path
import hashlib,json,shutil
p=Path(__file__).resolve().parent
base=p.parent/'shared-tree-native/integration-validation/ed63904f61f6439e9f68c488e44d7b70/result.json'
receipt=json.loads(base.read_text(encoding='utf8'))
assert receipt['status']=='PASS' and receipt['passed']==268
assert receipt['checker_version'].endswith('b9652e8e197783facaa03d3e837d67962bb9a60388783b345180833d19402cc1')
source=Path(receipt['source_directory']);assert not (p/'src').exists()
for relative,expected in receipt['source_files'].items():
    original=source/relative;assert hashlib.sha256(original.read_bytes()).hexdigest()==expected
    target=p/'src'/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(original,target)
tests=p/'tests';tests.mkdir()
old=p.parent/'shared-tree-native'
for name in ('test_shared_tree_proposals.py','native_shared_tree_reference.py'):
    shutil.copyfile(old/'tests'/name,tests/name)
root=next(x for x in p.parents if (x/'AGENTS.md').is_file())
fixture=tests/'fixtures/coupled-native-tree/boundary.json';fixture.parent.mkdir(parents=True)
shutil.copyfile(root/'tests/fixtures/coupled-native-tree/boundary.json',fixture)
(p/'base-source.json').write_text(json.dumps({'base_receipt':str(base),
    'checker_version':receipt['checker_version'],'source_files':receipt['source_files'],
    'ownership':'Root producer/job/tests; math agent pressure-checker changes arrive from separate shared-tree-coupled-checker handoff'},indent=2)+'\n',encoding='utf8')
print(json.dumps({'source_files':len(receipt['source_files']),'stage':str(p)}))
