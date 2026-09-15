"""Wait boundedly for both authorized exact runs; build a new bundle, never seal."""
import json,os,subprocess,sys,time,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
STAGE=Path(__file__).resolve().parent
CUSTOM=ROOT/'evidence/dependencies/native-build/checkpoint-validation/f73a8793ae0d-0cf1c8bf0868/result.json'
ORIGINAL=ROOT/'.oma/development/factorized-tree-pressure/combined-validation/d6d1204384b84bc6b0a5c5e47c5540ad/result.json'
OUT=STAGE/'orchestration'/uuid.uuid4().hex;OUT.mkdir(parents=True)
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(v):(OUT/'status.json').write_text(json.dumps(v,indent=2),encoding='utf-8')
def execute(name,argv,budget=1800):
    with (OUT/(name+'.stdout.log')).open('w',encoding='utf-8') as out,(OUT/(name+'.stderr.log')).open('w',encoding='utf-8') as err:
        r=subprocess.run(list(map(str,argv)),cwd=ROOT,stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW,timeout=budget)
    assert r.returncode==0,(name,r.returncode)
    return (OUT/(name+'.stdout.log')).read_text().strip()
start=time.monotonic();write({'status':'WAITING_FOR_BOTH_EXACT_NATIVE_FULL_PASSES','pid':os.getpid(),'directory':str(OUT)})
try:
    while time.monotonic()-start<3000:
        c,o=read(CUSTOM),read(ORIGINAL)
        if c['status']=='CUSTOM_NATIVE_NEW_CHECKPOINT_FULL_SUITE_PASS' and o['status']=='PASS':break
        assert c['status'] in {'RUNNING','CUSTOM_NATIVE_NEW_CHECKPOINT_FULL_SUITE_PASS'},c['status']
        assert o['status'] in {'RUNNING','PASS'},o['status']
        time.sleep(20)
    else:raise TimeoutError('Both exact suites did not complete within bounded wait')
    for _ in range(30):
        if (CUSTOM.parent/'post-run-exact-audit.json').exists():break
        time.sleep(2)
    else:raise TimeoutError('Independent completion audit did not appear')
    text=execute('prepare',[sys.executable,STAGE/'prepare.py'],120)
    prep=Path(text.splitlines()[-1]);assert prep.is_dir()
    write({'status':'BUILDING_NEW_IMMUTABLE_PACKAGE','preparation':str(prep),'pid':os.getpid(),'directory':str(OUT)})
    known={p.name for p in (ROOT/'evidence/dependencies/native-build/portable-candidates').glob('f73a8793ae0d-*')}
    execute('build',['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',prep/'run-build.ps1','-Preparation',prep],1800)
    candidates=[p for p in (ROOT/'evidence/dependencies/native-build/portable-candidates').glob('f73a8793ae0d-*') if p.name not in known]
    assert len(candidates)==1
    result=candidates[0]/'result.json';assert read(result)['status']=='ISOLATED_NATIVE_PORTABLE_OFFLINE_WORKFLOW_PASS'
    write({'status':'BUILT_WAITING_FOR_AUTHORIZED_VALIDATION_LAUNCH','preparation':str(prep),'portable_result':str(result),'pid':os.getpid(),'directory':str(OUT),'sealed':False})
except BaseException as e:
    write({'status':'FAILED_OR_INCOMPLETE','error':repr(e),'pid':os.getpid(),'directory':str(OUT)});raise
finally:
    (OUT/'executed-orchestrator.py').write_bytes(Path(__file__).read_bytes())
print(OUT)
