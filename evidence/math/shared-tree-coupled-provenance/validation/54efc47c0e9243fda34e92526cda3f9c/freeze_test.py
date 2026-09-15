"""Immutable new-checker/test/fixture receipt against an explicit dependency snapshot."""
from pathlib import Path
import hashlib,json,os,subprocess,sys,time,uuid
import xml.etree.ElementTree as ET

STAGE=Path(__file__).resolve().parents[1]
def sha(data):return hashlib.sha256(data).hexdigest()
def dump(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
dependency=json.loads((STAGE/'dependencies/base.json').read_text(encoding='utf-8'))
dep=STAGE/'dependencies'/dependency['root']/'src'
assert all(sha((dep/x['path']).read_bytes())==x['sha256'] for x in dependency['files'])
module='src/oma/routing/shared_tree_catalogue_check.py'
tests=['tests/test_shared_tree_catalogue_check.py','tests/test_shared_tree_coupled_catalogue_check.py']
paths=[module,*tests]+[x.relative_to(STAGE).as_posix() for x in sorted((STAGE/'tests/fixtures').rglob('*')) if x.is_file() and '__pycache__' not in x.parts and x.suffix in ('.json','.py')]
records=[{'path':p,'sha256':sha((STAGE/p).read_bytes())} for p in paths]
root=sha(json.dumps({'new_files':records,'dependency_source_root':dependency['root']},sort_keys=True,separators=(',',':')).encode())
runtime=STAGE/'runtimes'/root
for record in records:
 target=runtime/record['path'];target.parent.mkdir(parents=True,exist_ok=True);data=(STAGE/record['path']).read_bytes()
 if target.exists():assert target.read_bytes()==data
 else:target.write_bytes(data)
receipt=STAGE/'validation'/uuid.uuid4().hex;receipt.mkdir(parents=True)
(receipt/'freeze_test.py').write_bytes(Path(__file__).read_bytes())
(receipt/'dependency-source-manifest.json').write_bytes((STAGE/'dependencies/base.json').read_bytes())
env=os.environ.copy();env['OMA_CATALOGUE_CHECK_SOURCE']=str(runtime/module);env['PYTHONIOENCODING']='utf-8'
env['PYTHONPATH']=str(dep)
command=[sys.executable,'-m','pytest',*[str(runtime/test) for test in tests],'-q','-o','addopts=','-o','pythonpath='+dep.as_posix()]
start=time.monotonic()
collect=subprocess.run(command+['--collect-only'],capture_output=True,text=True,encoding='utf-8',env=env,timeout=60)
(receipt/'collection.txt').write_text(collect.stdout+collect.stderr,encoding='utf-8')
assert collect.returncode==0
nodes=[x for x in collect.stdout.splitlines() if '::test_' in x];assert nodes and len(set(nodes))==len(nodes)
dump(receipt/'collected-nodes.json',nodes)
run=subprocess.run(command+['--junitxml',str(receipt/'tests.xml'),'--tb=short'],capture_output=True,text=True,encoding='utf-8',env=env,timeout=60)
(receipt/'pytest.txt').write_text(run.stdout+run.stderr,encoding='utf-8')
xml=ET.parse(receipt/'tests.xml').getroot();cases=xml.findall('.//testcase')
counts={x:len(xml.findall('.//'+x)) for x in ('failure','error','skipped')}
unchanged=all(sha((runtime/x['path']).read_bytes())==x['sha256'] for x in records)
dep_unchanged=all(sha((dep/x['path']).read_bytes())==x['sha256'] for x in dependency['files'])
result={'schema':'oma.private-coupled-catalogue-provenance-test-receipt/1',
 'status':'PASS' if run.returncode==0 and len(cases)==len(nodes) and not any(counts.values()) and unchanged and dep_unchanged else 'FAIL',
 'source_root':root,'source_root_is_production_build':False,'module_sha256':records[0]['sha256'],
 'dependency_source_root':dependency['root'],'dependency_files':len(dependency['files']),
 'collected':len(nodes),'testcases':len(cases),**counts,'exit_code':run.returncode,'elapsed_seconds':time.monotonic()-start,
 'files':records,'snapshot_unchanged':unchanged,'dependencies_unchanged':dep_unchanged,'command':command,
 'scope':'Independent supplied-catalogue checker with fixed-ID coupled binding plus unchanged base94; no native service or acceptance rerun'}
dump(receipt/'result.json',result)
print(json.dumps({'runtime':str(runtime),'receipt':str(receipt),'result':result}))
assert result['status']=='PASS'
