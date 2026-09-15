"""Predeclared bounded observational probe with creation-time tree containment."""
from pathlib import Path
import json,os,shutil,sys,time,uuid
from oma.ifc.audit import atomic_json,sha256_file
from oma.export_checks import supervise_check
from oma.build_identity import checker_version
STAGE=Path(__file__).resolve().parent
ROOT=next(p for p in STAGE.parents if (p/'AGENTS.md').exists())
SOURCE=ROOT/'data/ifc-bench/projects/west_riverside_hospital/arc_ifc4.ifc'
APP=ROOT/'.oma/validated-runtimes/33a20d125bba-c304a60d38e9/src'
mode=sys.argv[1];limit=float(sys.argv[2]);assert mode in ('native','enclosure') and 1<=limit<=120
assert checker_version()=='oma-independent-checker/2:33a20d125bba02a298d12048a5b6227e51a98d8a043b999097d94a8d88b67b95'
out=STAGE/'probes'/uuid.uuid4().hex;out.mkdir(parents=True)
before=sha256_file(SOURCE);app={p.relative_to(APP).as_posix():sha256_file(p) for p in APP.rglob('*.py')}
assert before=='230afa4d72a59c9ce18cdd9a7bc7c5c3e409a46078de6e14b19741b4cf92cf09'
for p in (Path(__file__),STAGE/'probe.py'):shutil.copyfile(p,out/p.name)
declaration={'mode':mode,'source':str(SOURCE),'source_sha256':before,'source_bytes':SOURCE.stat().st_size,'checker_version':checker_version(),
    'app_source':str(APP),'app_sources':app,'deadline_seconds':limit,'memory_limit_bytes':12*1024**3,
    'interpretation':'Observational timing only. No geometry exclusion, candidate clearance report or acceptance authority.',
    'scripts':{p.name:sha256_file(p) for p in (out/'run_probe.py',out/'probe.py')}}
atomic_json(out/'predeclaration.json',declaration)
supervision=supervise_check([sys.executable,str(out/'probe.py'),mode,str(SOURCE),str(out)],environment=dict(os.environ),
    directory=out/'supervision',deadline=time.monotonic()+limit,memory_limit_bytes=12*1024**3)
assert sha256_file(SOURCE)==before and {p.relative_to(APP).as_posix():sha256_file(p) for p in APP.rglob('*.py')}==app
events=[json.loads(line) for line in (out/'progress.jsonl').read_text(encoding='utf8').splitlines()] if (out/'progress.jsonl').exists() else []
result={'status':'OBSERVATION_COMPLETE','supervision':supervision,'source_and_app_unchanged':True,'events':len(events),
    'last_events':events[-12:],'native_verification_claim':False}
atomic_json(out/'result.json',result);print(json.dumps({'out':str(out),'status':supervision['status'],'elapsed':supervision['elapsed_seconds'],'last_events':events[-8:]},indent=2))
