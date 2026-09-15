"""Copy validated bytes and write a reviewable launcher before the old server stops."""
import hashlib
import json
from pathlib import Path
import shutil
from validation_gate import completed_validation

ROOT=next(p for p in Path(__file__).resolve().parents if (p/"AGENTS.md").exists())
def read(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
EVIDENCE=Path(read(Path(__file__).parent/'latest-preflight.json')['directory'])
expected=read(EVIDENCE/'expected-source.json')
assert read(EVIDENCE/'preflight.json')['status']=='OWNED_IDLE_PREFLIGHT_PASS'
gate=completed_validation()
assert expected==gate
runtime=ROOT/'.oma/validated-runtimes'/(expected['checker_version'].rsplit(':',1)[1][:12]+'-'+EVIDENCE.name[:12])
runtime.mkdir(exist_ok=False)
source=Path(expected['source_directory'])
for relative,value in expected['files'].items():
    assert sha(source/relative)==value
    target=runtime/'src'/relative;target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(source/relative,target);assert sha(target)==value
ui=read(EVIDENCE/'before-ui.json')['files']
for relative,value in ui.items():
    target=runtime/'ui/dist'/relative;target.parent.mkdir(parents=True,exist_ok=True)
    assert sha(ROOT/'ui/dist'/relative)==value
    shutil.copyfile(ROOT/'ui/dist'/relative,target);assert sha(target)==value
caps = read(EVIDENCE/'capabilities-binding.json')
assert sha(ROOT/'docs/capabilities.json') == caps['sha256']
assert sha(EVIDENCE/'before-capabilities.json') == caps['sha256']
(runtime/'docs').mkdir()
shutil.copyfile(EVIDENCE/'before-capabilities.json',runtime/'docs/capabilities.json')
expected.update(source_directory=str(runtime/'src'), capabilities_sha256=caps['sha256'])
(EVIDENCE/'live-expected-source.json').write_text(json.dumps(expected,indent=2))
launcher=(EVIDENCE/'old-start_validated_backend.py').read_text()
lines=[]
for line in launcher.splitlines():
    if line.startswith('MANIFEST = '):
        line='MANIFEST = Path('+repr(str(EVIDENCE/'live-expected-source.json'))+')'
    elif line.startswith('EXPECTED = '):
        line='EXPECTED = '+repr(expected['checker_version'])
    lines.append(line)
launcher='\n'.join(lines)+'\n'
assert launcher.count('assert len(expected["files"]) == 114')==1
launcher=launcher.replace('Run the exact fully validated coupled-pressure backend', 'Run the validated local Hospital-clearance backend')
assert 'recover=False' in launcher
compile(launcher,'prepared-launcher','exec')
(EVIDENCE/'prepared-launcher.py').write_text(launcher)
(EVIDENCE/'prepared-start.json').write_text(json.dumps({'status':'READY_AFTER_GUARDED_STOP','runtime':str(runtime),
    'launcher_sha256':sha(EVIDENCE/'prepared-launcher.py'),'manifest_sha256':sha(EVIDENCE/'live-expected-source.json'),
    'source_count':114,'ui_count':6,'source_files':expected['files'],'ui_files':ui},indent=2))
shutil.copyfile(__file__,EVIDENCE/'executed-prepare-start.py')
print(EVIDENCE)
