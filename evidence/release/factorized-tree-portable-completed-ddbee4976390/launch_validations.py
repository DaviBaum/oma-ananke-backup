"""Launch the two already authorized frozen-package validation jobs once."""
import hashlib,json,subprocess,time
from pathlib import Path
import psutil
ROOT=Path(__file__).resolve().parents[3]
STAGE=Path(__file__).resolve().parent
BUILD=STAGE/'orchestration/2bd2764155074a12be7e680e99cf50b2/status.json'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):Path(p).write_text(json.dumps(v,indent=2),encoding='utf-8')
b=read(BUILD);assert b['status']=='BUILT_WAITING_FOR_AUTHORIZED_VALIDATION_LAUNCH'
prep=Path(b['preparation']);result=Path(b['portable_result']);r=read(result)
assert r['status']=='ISOLATED_NATIVE_PORTABLE_OFFLINE_WORKFLOW_PASS'
assert r['source_checkpoint']=='f73a8793ae0df76d9ec53400cec18b05d2731f63c735b225c2246fee62df6b21'
for mode in ('suite','cases'):
    assert not any((prep/(mode+suffix)).exists() for suffix in ('.stdout.log','.stderr.log','-exit.json'))
record={'status':'STARTING_AUTHORIZED_VALIDATIONS','package':r['package'],
    'checker_version':r['identity']['checker_version'],'result':str(result),
    'result_sha256':sha(result),'preparation':str(prep),'preparation_sha256':sha(prep/'preparation.json'),
    'driver_sha256':sha(__file__),'wrapper_sha256':sha(prep/'run-validations.ps1'),'processes':[]}
write(STAGE/'validation-launch.json',record)
for mode in ('suite','cases'):
    argv=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(prep/'run-validations.ps1'),'-Result',str(result),'-Preparation',str(prep),'-Mode',mode]
    with (prep/(mode+'.stdout.log')).open('w') as out,(prep/(mode+'.stderr.log')).open('w') as err:
        process=subprocess.Popen(argv,cwd=ROOT,stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW)
    record['processes'].append({'mode':mode,'pid':process.pid,'creation_time':psutil.Process(process.pid).create_time(),'command':argv,'cwd':str(ROOT)})
    write(STAGE/'validation-launch.json',record)
record['status']='AUTHORIZED_VALIDATIONS_RUNNING';write(STAGE/'validation-launch.json',record)
print(json.dumps(record),flush=True)
