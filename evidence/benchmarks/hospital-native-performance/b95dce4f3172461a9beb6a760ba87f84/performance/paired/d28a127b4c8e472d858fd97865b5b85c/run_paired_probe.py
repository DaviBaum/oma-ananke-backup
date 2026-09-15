from pathlib import Path
import json,os,shutil,sys,time,uuid
from oma.ifc.audit import atomic_json,sha256_file
from oma.export_checks import supervise_check
from oma.build_identity import checker_version

STAGE=Path(__file__).resolve().parent;ROOT=next(p for p in STAGE.parents if (p/'AGENTS.md').exists())
SOURCE=ROOT/'data/ifc-bench/projects/west_riverside_hospital/arc_ifc4.ifc'
BASE=ROOT/'.oma/validated-runtimes/33a20d125bba-c304a60d38e9/src';APP=STAGE/'src'
out=STAGE/'paired'/uuid.uuid4().hex;out.mkdir(parents=True)
events=[json.loads(l) for l in (STAGE/'probes/42d47815990c4d54b3b621f4fafe83b7/progress.jsonl').read_text(encoding='utf8').splitlines()]
first=[r['step_id'] for r in events if r['stage']=='iterator_get_end'][:12]
slow=[261792,287327,327436,327909,328353,361437,346693,328320]
steps=sorted(set(first+slow))
source_before=sha256_file(SOURCE);assert source_before=='230afa4d72a59c9ce18cdd9a7bc7c5c3e409a46078de6e14b19741b4cf92cf09'
app_before={p.relative_to(APP).as_posix():sha256_file(p) for p in APP.rglob('*.py')}
for p in (Path(__file__),STAGE/'paired_probe.py'):shutil.copyfile(p,out/p.name)
decl={'source':str(SOURCE),'source_sha256':source_before,'base_cad':str(BASE/'oma/ifc/cad.py'),'base_cad_sha256':sha256_file(BASE/'oma/ifc/cad.py'),
    'private_cad_sha256':sha256_file(APP/'oma/ifc/cad.py'),'private_app_sources':app_before,'checker_version':checker_version(),
    'sample_step_ids':steps,'selection':'First twelve emitted objects plus eight observed slow objects from original 90s probe. Timing sample, never obstacle selection.',
    'deadline_seconds':120,'memory_limit_bytes':12*1024**3,'scripts':{p.name:sha256_file(p) for p in (out/'run_paired_probe.py',out/'paired_probe.py')}}
atomic_json(out/'predeclaration.json',decl)
supervision=supervise_check([sys.executable,str(out/'paired_probe.py'),str(out)],environment=dict(os.environ),directory=out/'supervision',deadline=time.monotonic()+120,memory_limit_bytes=12*1024**3)
assert source_before==sha256_file(SOURCE) and app_before=={p.relative_to(APP).as_posix():sha256_file(p) for p in APP.rglob('*.py')}
child=json.loads((out/'child-result.json').read_text(encoding='utf8')) if (out/'child-result.json').exists() else None
atomic_json(out/'result.json',{'status':'PAIRED_INSPECTION_PASS' if supervision['status']=='COMPLETED' and child else 'INCOMPLETE','supervision':supervision,'child':child,'original_source_and_private_app_unchanged':True})
print(json.dumps({'directory':str(out),'supervision':supervision['status'],'child':child},indent=2))
