from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys
ROOT=Path.cwd();STAGE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
from oma.build_identity import frozen_environment
TARGET=STAGE/'campaign-v2';TARGET.mkdir()
env=frozen_environment(TARGET);source=Path(env['PYTHONPATH']);build=env['OMA_EXECUTABLE_BUILD'].split(':')[-1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
sources={p.relative_to(source).as_posix():sha(p) for p in source.rglob('*.py')}
assert len(sources)==114
(TARGET/'source.json').write_text(json.dumps(sources,indent=2))
oldplan=json.loads((STAGE/'campaign-v1/campaign-plan.json').read_text())
for name in ('prepare_architecture.py','campaign.py'):
 code=(STAGE/'campaign-v1'/name).read_text().replace(oldplan['build'],build)
 (TARGET/name).write_text(code,encoding='utf-8')
plan={k:oldplan[k] for k in ('scope','query_root','original_predeclaration_sha256','mission_unchanged')}
plan.update(build=build,source=str(source),changes='Same original source, query, physics, tolerances,2 alternatives and1800s budgets; local tee CSG materialization; fresh isolated Store.',source_files=sources)
(TARGET/'campaign-plan.json').write_text(json.dumps(plan,indent=2))
with (TARGET/'import.stdout.log').open('w') as stdout,(TARGET/'import.stderr.log').open('w') as stderr:
 done=subprocess.run([sys.executable,str(TARGET/'prepare_architecture.py')],cwd=ROOT,env=env,stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
assert done.returncode==0
attempts=list((TARGET/'attempts').glob('*/result.json'));assert len(attempts)==1
result=json.loads(attempts[0].read_text());assert result['status']=='IMPORTED_CURRENT_SOURCE_INVENTORY'
plan.update(import_result=str(attempts[0]),store=result['store'],project_id=result['project_id'])
(TARGET/'campaign-plan.json').write_text(json.dumps(plan,indent=2))
runner=(STAGE/'run_campaign.py').read_text().replace("target=STAGE/'campaign-v1'","target=STAGE/'campaign-v2'")
(STAGE/'run_campaign_v2.py').write_text(runner,encoding='utf-8')
print(json.dumps({'status':'READY','build':build,'plan':str(TARGET/'campaign-plan.json'),'seconds':result['elapsed_seconds']}),flush=True)
