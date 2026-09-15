"""Wait for the owned campaign's final receipt, then run a bounded read-only audit."""
from pathlib import Path
import hashlib,json,os,shutil,sys,time,uuid
ROOT=Path(__file__).resolve().parents[3];STAGE=Path(__file__).resolve().parent
CAMPAIGN=ROOT/'.oma/development/hospital-clearance-20260915/campaign-v2/campaigns/4f0e44e4557a43528250e6884e8efd95'
SOURCE=ROOT/'.oma/development/hospital-clearance-20260915/campaign-v2/runtimes/06aa865600b4ab2dc8f42f77b2cb5f82816dec99bbf8a1ff5f67673fb44c1949/src'
sys.path.insert(0,str(SOURCE))
from oma.export_checks import supervise_check
from oma.build_identity import checker_version
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,value):p.write_text(json.dumps(value,indent=2),encoding='utf-8')
out=STAGE/'watchers'/uuid.uuid4().hex;out.mkdir(parents=True)
shutil.copyfile(__file__,out/'executed-watcher.py')
driver=STAGE/'audit.py';driver_sha=sha(driver)
shutil.copyfile(driver,out/'prepared-audit.py')
result={'status':'WAITING_FOR_TERMINAL_CAMPAIGN','campaign':str(CAMPAIGN),'source':str(SOURCE),
    'audit_script_sha256':driver_sha,'checker_version':checker_version(),'poll_interval_seconds':30}
write(out/'result.json',result);print(json.dumps({'watcher':str(out)}),flush=True)
limit=time.monotonic()+3600;last=None
while time.monotonic()<limit:
    campaign=json.loads((CAMPAIGN/'result.json').read_text())
    status=campaign['status']
    if status!=last:print(json.dumps({'campaign_status':status}),flush=True);last=status
    if status!='RUNNING':break
    time.sleep(30)
else:
    result['status']='WATCH_DEADLINE_NO_TERMINAL_CAMPAIGN';write(out/'result.json',result);raise SystemExit(0)
assert sha(driver)==driver_sha
result.update(status='AUDIT_RUNNING',campaign_status=status,campaign_result_sha256=sha(CAMPAIGN/'result.json'))
write(out/'result.json',result)
env=dict(os.environ,PYTHONPATH=str(SOURCE),OMA_EXECUTABLE_BUILD=checker_version())
supervision=supervise_check([str(ROOT/'.venv/Scripts/python.exe'),str(driver),str(CAMPAIGN),'--source-directory',str(SOURCE)],
    environment=env,directory=out/'supervision',deadline=time.monotonic()+300,memory_limit_bytes=12*1024**3)
result.update(status='AUDIT_CHILD_CLOSED',supervision=supervision,driver_unchanged=sha(driver)==driver_sha)
if supervision['status']=='COMPLETED' and supervision['returncode']==0:
    lines=(out/'supervision/stdout.log').read_text(encoding='utf-8').splitlines()
    result['audit_summary']=json.loads(lines[-1])
write(out/'result.json',result)
print(json.dumps({'watcher':str(out),'status':result['status'],'audit_summary':result.get('audit_summary')}),flush=True)

