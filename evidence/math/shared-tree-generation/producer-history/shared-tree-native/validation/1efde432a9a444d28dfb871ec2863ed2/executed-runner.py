from pathlib import Path
import hashlib,importlib.util,json,shutil,subprocess,sys,time,uuid
p=Path(__file__).resolve().parent
sys.path.insert(0,str(p/'src'))
from oma.build_identity import frozen_environment
env=frozen_environment(p)
out=p/'validation'/uuid.uuid4().hex;out.mkdir(parents=True)
tests=out/'tests';tests.mkdir()
for source in (p/'tests').glob('*.py'):shutil.copyfile(source,tests/source.name)
shutil.copyfile(__file__,out/'executed-runner.py')
root=next(x for x in p.parents if (x/'AGENTS.md').is_file())
shutil.copyfile(root/'evidence/release/pressure-package-harness-peer-review/audit_completed_suites.py',out/'inventory-helper.py')
spec=importlib.util.spec_from_file_location('validation_inventory',out/'inventory-helper.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
inputs={x.relative_to(out).as_posix():hashlib.sha256(x.read_bytes()).hexdigest() for x in out.rglob('*') if x.is_file()}
sources={x.relative_to(Path(env['PYTHONPATH'])).as_posix():hashlib.sha256(x.read_bytes()).hexdigest() for x in Path(env['PYTHONPATH']).rglob('*.py')}
prefix=[sys.executable,'-m','pytest','tests','-q','-o','pythonpath='+env['PYTHONPATH']]
collection=subprocess.run([*prefix,'--collect-only'],cwd=out,env=env,text=True,encoding='utf8',stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120)
(out/'collection.log').write_text(collection.stdout,encoding='utf8')
assert collection.returncode==0,collection.stdout
nodes=[line.strip() for line in collection.stdout.splitlines() if line.startswith('tests/') and '::' in line]
assert nodes and len(nodes)==len(set(nodes))
(out/'test-nodes.json').write_text(json.dumps(nodes,indent=2)+'\n',encoding='utf8')
command=[*prefix,'--junitxml='+str(out/'tests.xml'),'--basetemp='+str(out/'native-stores')]
result={'status':'RUNNING','source_directory':env['PYTHONPATH'],'checker_version':env['OMA_EXECUTABLE_BUILD'],'source_files':sources,'inputs':inputs,'command':command}
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
print(json.dumps({'status':'RUNNING','out':str(out),'checker_version':result['checker_version']}),flush=True)
start=time.perf_counter()
with (out/'pytest.log').open('w',encoding='utf8') as log:done=subprocess.run(command,cwd=out,env=env,stdout=log,stderr=subprocess.STDOUT)
result.update(status='PASS' if done.returncode==0 else 'FAIL',returncode=done.returncode,seconds=time.perf_counter()-start)
result['inputs_unchanged']=all(hashlib.sha256((out/k).read_bytes()).hexdigest()==h for k,h in inputs.items())
result['source_unchanged']={x.relative_to(Path(env['PYTHONPATH'])).as_posix():hashlib.sha256(x.read_bytes()).hexdigest() for x in Path(env['PYTHONPATH']).rglob('*.py')}==sources
result['test_node_count']=len(nodes)
result['test_nodes_sha256']=hashlib.sha256((out/'test-nodes.json').read_bytes()).hexdigest()
if done.returncode==0:
    try:
        result['case_inventory']=audit.account_xml(out/'tests.xml',nodes)
        result['exact_case_identities_checked']=True
    except BaseException as exc:
        result.update(status='FAIL',case_inventory_error=repr(exc))
if not result['inputs_unchanged'] or not result['source_unchanged']:result['status']='FAIL'
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
print(json.dumps({k:result[k] for k in ('status','seconds')}),flush=True)
raise SystemExit(0 if result['status']=='PASS' else 1)
