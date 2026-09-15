from pathlib import Path
import gzip,json,os,shutil,sys,time,uuid
from oma.build_identity import checker_version
from oma.export_checks import supervise_check
from oma.ifc.audit import atomic_json,sha256_file
ROOT=Path(__file__).resolve().parents[3];STAGE=Path(__file__).resolve().parent;APP=STAGE/'combined-src'
OLD=ROOT/'evidence/benchmarks/hospital-generated-tree/architecture-d3e1be8f981146fcadede8107addadbe'
candidate=OLD/'campaign/candidates/85453f9ad960487297bf0231cd549a79'
source=ROOT/'data/ifc-bench/projects/west_riverside_hospital/arc_ifc4.ifc'
out=STAGE/'full-probes'/uuid.uuid4().hex;out.mkdir(parents=True)
materialization=json.loads((candidate/'materialization.json').read_text())
request=json.loads((OLD/'campaign/predeclaration.json').read_text())['authored_query']['requirements']
raw=gzip.decompress((candidate/'actual.ifc.gz').read_bytes());export=out/'actual.ifc';export.write_bytes(raw);del raw
shutil.copyfile(candidate/'materialization.json',export.with_suffix('.manifest.json'))
assert sha256_file(export)==materialization['export_sha256']=='e1761bb16830e6d0583d54c141dc9c3cd85260589dc329970c802241e405ec88'
assert sha256_file(source)==materialization['source_sha256']=='230afa4d72a59c9ce18cdd9a7bc7c5c3e409a46078de6e14b19741b4cf92cf09'
files={p.relative_to(APP).as_posix():sha256_file(p) for p in APP.rglob('*.py')}
for p in (Path(__file__),STAGE/'full_probe.py'):shutil.copyfile(p,out/p.name)
decl={'checker_version':checker_version(),'app':str(APP),'app_files':files,'source':str(source),'source_sha256':sha256_file(source),
    'export':str(export),'export_sha256':sha256_file(export),'original_gzip_sha256':sha256_file(candidate/'actual.ifc.gz'),
    'original_materialization_sha256':sha256_file(candidate/'materialization.json'),'original_request_sha256':sha256_file(OLD/'campaign/predeclaration.json'),
    'route_guids':[p['ifc_guid'] for p in materialization['added_parts']],'clearance_m':request['clearance_m'],'numerical_tolerance_m':1e-6,
    'source_representation_policy':request['source_representation_policy'],'deadline_seconds':600,'memory_limit_bytes':12*1024**3,
    'expected_obstacles':14409,'expected_source_pairs':57636,'expected_self_pairs':6,'regenerated_IFC':False,
    'scope':'Geometry-only diagnostic for the exact original unchecked candidate IFC, unchanged physical requirements and all ARC source obstacles'}
atomic_json(out/'predeclaration.json',decl)
environment=dict(os.environ);environment['PYTHONPATH']=str(APP);environment['PYTHONDONTWRITEBYTECODE']='1';environment['OMA_EXECUTABLE_BUILD']=checker_version()
print(json.dumps({'out':str(out),'checker_version':checker_version(),'stage':'STARTED'}),flush=True)
result=supervise_check([sys.executable,'-B',str(out/'full_probe.py'),str(out)],environment=environment,directory=out/'supervision',deadline=time.monotonic()+600,memory_limit_bytes=12*1024**3)
assert files=={p.relative_to(APP).as_posix():sha256_file(p) for p in APP.rglob('*.py')}
assert sha256_file(source)==decl['source_sha256'] and sha256_file(export)==decl['export_sha256']
child=json.loads((out/'child-result.json').read_text()) if (out/'child-result.json').exists() else None
atomic_json(out/'result.json',{'status':'FULL_CAD_PROBE_COMPLETE' if result['status']=='COMPLETED' and child else 'INCOMPLETE','supervision':result,'child':child,'immutable_inputs_unchanged':True})
print(json.dumps({'out':str(out),'supervision':result['status'],'seconds':result['elapsed_seconds'],'cad_status':child['cad_status'] if child else None}),flush=True)
