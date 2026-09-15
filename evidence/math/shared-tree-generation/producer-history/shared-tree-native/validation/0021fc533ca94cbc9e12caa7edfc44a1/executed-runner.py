from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys,uuid
p=Path(__file__).resolve().parent
sys.path.insert(0,str(p/'src'))
from oma.build_identity import frozen_environment
env=frozen_environment(p)
out=p/'validation'/uuid.uuid4().hex;out.mkdir(parents=True)
test=out/'tests/test_shared_tree_proposals.py';test.parent.mkdir();shutil.copyfile(p/'tests/test_shared_tree_proposals.py',test)
shutil.copyfile(__file__,out/'executed-runner.py')
result=subprocess.run([sys.executable,'-m','pytest',str(test),'-q','-o','pythonpath='+env['PYTHONPATH'],'--junitxml='+str(out/'tests.xml')],env=env,capture_output=True,text=True)
(out/'pytest.log').write_text(result.stdout+result.stderr,encoding='utf8')
(out/'source-manifest.json').write_text(json.dumps({x.relative_to(Path(env['PYTHONPATH'])).as_posix():hashlib.sha256(x.read_bytes()).hexdigest() for x in Path(env['PYTHONPATH']).rglob('*.py')},indent=2)+'\n',encoding='utf8')
print(result.stdout)
print('Evidence:',out)
raise SystemExit(result.returncode)
