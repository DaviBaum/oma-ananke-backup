from pathlib import Path
import hashlib,json,os,shutil,sys,time,uuid,xml.etree.ElementTree as ET
from oma.build_identity import checker_version
from oma.export_checks import supervise_check
from oma.ifc.audit import atomic_json,sha256_file
STAGE=Path(__file__).resolve().parent;ROOT=STAGE.parents[2]
out=STAGE/'validation'/uuid.uuid4().hex;out.mkdir(parents=True)
app=out/'src';testdir=out/'tests';testdir.mkdir()
for p in (STAGE/'src').rglob('*.py'):
    target=app/p.relative_to(STAGE/'src');target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
for name in ('test_ifc_cad.py','test_ifc_pipeline.py','test_ifc_enclosure.py'):
    shutil.copyfile(ROOT/'tests'/name,testdir/name)
shutil.copyfile(STAGE/'tests/test_ifc_cad_lazy_support.py',testdir/'test_ifc_cad_lazy_support.py')
shutil.copyfile(__file__,out/'executed.py')
files={p.relative_to(out).as_posix():sha256_file(p) for p in out.rglob('*') if p.is_file()}
environment=dict(os.environ);environment['PYTHONPATH']=str(app);environment['PYTHONDONTWRITEBYTECODE']='1';environment['OMA_EXECUTABLE_BUILD']=checker_version()
command=[sys.executable,'-B','-m','pytest',str(testdir/'test_ifc_cad_lazy_support.py'),str(testdir/'test_ifc_cad.py'),'-q','-o','pythonpath='+str(app),'--basetemp='+str(out/'temporary'),'--junitxml='+str(out/'tests.xml')]
atomic_json(out/'predeclaration.json',{'checker_version':checker_version(),'files':files,'command':command,'deadline_seconds':180})
result=supervise_check(command,environment=environment,directory=out/'supervision',deadline=time.monotonic()+180,memory_limit_bytes=12*1024**3)
assert all(sha256_file(out/n)==h for n,h in files.items())
xml=ET.parse(out/'tests.xml') if (out/'tests.xml').exists() else None
counts={'tests':len(xml.findall('.//testcase')),'failed':len(xml.findall('.//failure')),'errors':len(xml.findall('.//error')),'skipped':len(xml.findall('.//skipped'))} if xml is not None else None
atomic_json(out/'result.json',{'status':'PASS' if result['status']=='COMPLETED' and counts and not(counts['failed'] or counts['errors'] or counts['skipped']) else 'INCOMPLETE_OR_FAILED','supervision':result,'counts':counts,'inputs_unchanged':True,'checker_version':checker_version()})
print(json.dumps({'out':str(out),'supervision':result['status'],'counts':counts}))
