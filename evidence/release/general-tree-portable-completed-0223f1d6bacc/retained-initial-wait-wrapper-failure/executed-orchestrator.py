"""Wait boundedly for both authorized exact runs; build a new bundle, never seal."""
import json,os,subprocess,sys,time,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
STAGE=Path(__file__).resolve().parent
CUSTOM=ROOT/'evidence/dependencies/native-build/checkpoint-validation/edf555760245-4c1eddeca46f/result.json'
ORIGINAL=ROOT/'.oma/development/general-shared-tree-native/combined-validation/a29404ec828e4919b8968959019b8eb8/result.json'
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
    while time.monotonic()-start<2400:
        c,o=read(CUSTOM),read(ORIGINAL)
        if c['status']=='CUSTOM_NATIVE_NEW_CHECKPOINT_FULL_SUITE_PASS' and o['status']=='PASS':break
        assert c['status']=='RUNNING',c['status']
        assert o['status']=='RUNNING',o['status']
        time.sleep(20)
    else:raise TimeoutError('Both exact suites did not complete within bounded wait')
    execute('custom-completion-audit',[sys.executable,ROOT/'scripts/native_checkpoint_audit.py','--result',CUSTOM],120)
    text=execute('prepare',[sys.executable,STAGE/'prepare.py'],120)
    prep=Path(text.splitlines()[-1]);assert prep.is_dir()
    write({'status':'BUILDING_NEW_IMMUTABLE_PACKAGE','preparation':str(prep),'pid':os.getpid(),'directory':str(OUT)})
    known={p.name for p in (ROOT/'evidence/dependencies/native-build/portable-candidates').glob('edf555760245-*')}
    execute('build',['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',prep/'run-build.ps1','-Preparation',prep],1800)
    candidates=[p for p in (ROOT/'evidence/dependencies/native-build/portable-candidates').glob('edf555760245-*') if p.name not in known]
    assert len(candidates)==1
    result=candidates[0]/'result.json';assert read(result)['status']=='ISOLATED_NATIVE_PORTABLE_OFFLINE_WORKFLOW_PASS'
    write({'status':'BUILT_WAITING_FOR_AUTHORIZED_VALIDATION_LAUNCH','preparation':str(prep),'portable_result':str(result),'pid':os.getpid(),'directory':str(OUT),'sealed':False})
except BaseException as e:
    write({'status':'FAILED_OR_INCOMPLETE','error':repr(e),'pid':os.getpid(),'directory':str(OUT)});raise
finally:
    (OUT/'executed-orchestrator.py').write_bytes(Path(__file__).read_bytes())
print(OUT)
