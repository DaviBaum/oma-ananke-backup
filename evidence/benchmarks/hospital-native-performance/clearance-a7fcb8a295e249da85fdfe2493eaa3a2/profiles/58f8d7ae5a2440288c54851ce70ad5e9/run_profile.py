from pathlib import Path
import json,os,shutil,sys,time,uuid
from oma.build_identity import checker_version
from oma.export_checks import supervise_check
from oma.ifc.audit import sha256_file,atomic_json
STAGE=Path(__file__).resolve().parent;ROOT=STAGE.parents[2]
mode=sys.argv[1];assert mode in ('base-src','src');app=STAGE/mode
source=ROOT/'data/ifc-bench/projects/west_riverside_hospital/arc_ifc4.ifc'
out=STAGE/'profiles'/uuid.uuid4().hex;out.mkdir(parents=True)
files={p.relative_to(app).as_posix():sha256_file(p) for p in app.rglob('*.py')}
environment=dict(os.environ);environment['PYTHONPATH']=str(app);environment['PYTHONDONTWRITEBYTECODE']='1';environment['OMA_EXECUTABLE_BUILD']=checker_version()
decl={'mode':mode,'source':str(source),'source_sha256':sha256_file(source),'app':str(app),'app_files':files,'checker_version':checker_version(),'limit':200,'deadline_seconds':120,'scope':'First 200 represented products for timing, no obstacle exclusion or clearance verdict'}
assert decl['source_sha256']=='230afa4d72a59c9ce18cdd9a7bc7c5c3e409a46078de6e14b19741b4cf92cf09'
for p in (Path(__file__),STAGE/'profile_enclosure.py'):shutil.copyfile(p,out/p.name)
atomic_json(out/'predeclaration.json',decl)
result=supervise_check([sys.executable,'-B',str(out/'profile_enclosure.py'),str(out)],environment=environment,directory=out/'supervision',deadline=time.monotonic()+120,memory_limit_bytes=12*1024**3)
assert files=={p.relative_to(app).as_posix():sha256_file(p) for p in app.rglob('*.py')}
assert sha256_file(source)==decl['source_sha256']
atomic_json(out/'result.json',{'status':'PROFILE_EXECUTION_RECORDED','supervision':result,'source_and_app_unchanged':True})
print(json.dumps({'out':str(out),'supervision':result['status'],'seconds':result['elapsed_seconds']}))
