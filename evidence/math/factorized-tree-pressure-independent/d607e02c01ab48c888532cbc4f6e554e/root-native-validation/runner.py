"""Freeze and validate the next isolated pressure generation stage."""
from pathlib import Path
import hashlib,json,shutil,subprocess,sys,time,uuid
p=Path(__file__).resolve().parent
sys.path.insert(0,str(p/'src'))
from oma.build_identity import frozen_environment
root=next(x for x in p.parents if (x/'AGENTS.md').is_file())
out=p/'validation'/uuid.uuid4().hex;out.mkdir(parents=True)
shutil.copytree(p/'tests',out/'tests',ignore=shutil.ignore_patterns('__pycache__'))
shutil.copyfile(root/'pyproject.toml',out/'pyproject.toml')
shutil.copyfile(__file__,out/'runner.py')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
inputs={x.relative_to(out).as_posix():sha(x) for x in out.rglob('*') if x.is_file()}
env=frozen_environment(p);source=Path(env['PYTHONPATH'])
sources={x.relative_to(source).as_posix():sha(x) for x in source.rglob('*.py')}
selection=sys.argv[1:] or ['tests/test_general_tree_native.py']
command=[sys.executable,'-m','pytest',*selection,'-q','-o','pythonpath='+str(source),
    '--junitxml='+str(out/'tests.xml'),'--basetemp='+str(out/'native-stores')]
result={'status':'RUNNING','checker_version':env['OMA_EXECUTABLE_BUILD'],'source_directory':str(source),
    'source_files':sources,'input_files':inputs,'command':command}
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
print(json.dumps({'status':'RUNNING','directory':str(out),'checker_version':result['checker_version']}),flush=True)
start=time.perf_counter()
with (out/'pytest.log').open('w',encoding='utf8') as log:
    completed=subprocess.run(command,cwd=out,env=env,stdout=log,stderr=subprocess.STDOUT)
result.update(status='PASS' if completed.returncode==0 else 'FAIL',returncode=completed.returncode,seconds=time.perf_counter()-start,
    inputs_unchanged=all(sha(out/k)==h for k,h in inputs.items()),
    source_unchanged={x.relative_to(source).as_posix():sha(x) for x in source.rglob('*.py')}==sources)
if not result['inputs_unchanged'] or not result['source_unchanged']:result['status']='FAIL'
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
print(json.dumps({k:result[k] for k in ('status','seconds')}),flush=True)
raise SystemExit(0 if result['status']=='PASS' else 1)
