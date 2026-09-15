from pathlib import Path
import json,os,subprocess,sys,time
STAGE=Path(__file__).resolve().parent
ROOT=next(p for p in STAGE.parents if (p/'AGENTS.md').is_file())
target=STAGE/'campaign-v2';plan=json.loads((target/'campaign-plan.json').read_text())
env=dict(os.environ,PYTHONPATH=plan['source'],OMA_EXECUTABLE_BUILD='oma-independent-checker/2:'+plan['build'])
command=[sys.executable,str(target/'campaign.py'),plan['import_result'],plan['scope']]
start=time.monotonic()
with (target/'campaign.stdout.log').open('w') as stdout,(target/'campaign.stderr.log').open('w') as stderr:
    done=subprocess.run(command,cwd=ROOT,env=env,stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
(target/'campaign-exit.json').write_text(json.dumps({'returncode':done.returncode,'seconds':time.monotonic()-start,'command':command}))
print((target/'campaign.stdout.log').read_text())
if done.returncode:print((target/'campaign.stderr.log').read_text())
raise SystemExit(done.returncode)
