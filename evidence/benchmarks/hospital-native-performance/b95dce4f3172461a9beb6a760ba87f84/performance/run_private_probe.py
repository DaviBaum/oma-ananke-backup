"""Same complete-source 90-second observer, with only private prerequisite order changed."""
from pathlib import Path
import json,os,shutil,sys,time,uuid
from oma.ifc.audit import atomic_json,sha256_file
from oma.export_checks import supervise_check
from oma.build_identity import checker_version
from oma.ifc import cad
STAGE=Path(__file__).resolve().parent;ROOT=next(p for p in STAGE.parents if (p/'AGENTS.md').exists())
SOURCE=ROOT/'data/ifc-bench/projects/west_riverside_hospital/arc_ifc4.ifc';APP=STAGE/'src'
assert Path(cad.__file__).resolve()==APP/'oma/ifc/cad.py'
out=STAGE/'probes'/uuid.uuid4().hex;out.mkdir(parents=True)
before=sha256_file(SOURCE);assert before=='230afa4d72a59c9ce18cdd9a7bc7c5c3e409a46078de6e14b19741b4cf92cf09'
app={p.relative_to(APP).as_posix():sha256_file(p) for p in APP.rglob('*.py')}
assert app==json.loads((STAGE/'source-declaration.json').read_text(encoding='utf8'))['private_files']
for p in (Path(__file__),STAGE/'probe.py'):shutil.copyfile(p,out/p.name)
atomic_json(out/'predeclaration.json',{'mode':'private_native','source':str(SOURCE),'source_sha256':before,'source_bytes':SOURCE.stat().st_size,
    'checker_version':checker_version(),'app_source':str(APP),'app_sources':app,'deadline_seconds':90,'memory_limit_bytes':12*1024**3,
    'comparison_probe':'42d47815990c4d54b3b621f4fafe83b7','scope':'Complete physical enumeration; bounded observational throughput only. No full hospital clearance report.',
    'scripts':{p.name:sha256_file(p) for p in (out/'run_private_probe.py',out/'probe.py')}})
env=dict(os.environ);env['OMA_EXECUTABLE_BUILD']=checker_version()
supervision=supervise_check([sys.executable,str(out/'probe.py'),'native',str(SOURCE),str(out)],environment=env,directory=out/'supervision',deadline=time.monotonic()+90,memory_limit_bytes=12*1024**3)
assert sha256_file(SOURCE)==before and {p.relative_to(APP).as_posix():sha256_file(p) for p in APP.rglob('*.py')}==app
events=[json.loads(l) for l in (out/'progress.jsonl').read_text(encoding='utf8').splitlines()]
result={'status':'OBSERVATION_COMPLETE','supervision':supervision,'source_and_app_unchanged':True,'events':len(events),'last_events':events[-12:],'native_verification_claim':False}
atomic_json(out/'result.json',result);print(json.dumps({'directory':str(out),'status':supervision['status'],'elapsed':supervision['elapsed_seconds'],'last_events':events[-5:]},indent=2))
