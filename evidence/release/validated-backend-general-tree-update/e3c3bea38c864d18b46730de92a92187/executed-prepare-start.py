"""Copy validated bytes and write a reviewable launcher before the old server stops."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[3]
def read(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
EVIDENCE=Path(read(Path(__file__).parent/'latest-preflight.json')['directory'])
expected=read(EVIDENCE/'expected-source.json')
assert read(EVIDENCE/'preflight.json')['status']=='OWNED_IDLE_PREFLIGHT_PASS'
cp=ROOT/'evidence/dependencies/native-build/checkpoint-validation/edf555760245-4c1eddeca46f/result.json'
assert read(cp)['status']=='CUSTOM_NATIVE_NEW_CHECKPOINT_FULL_SUITE_PASS'
supplement=Path(read(Path(__file__).parent/'supplement.json')['result'])
assert read(supplement)['status']=='PASS' and read(supplement)['accounting']['passed']==121
runtime=ROOT/'.oma/validated-runtimes'/('edf555760245-'+EVIDENCE.name[:12])
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
expected.update(source_directory=str(runtime/'src'),custom_native_receipt=str(cp),custom_native_receipt_sha256=sha(cp),
    package_supplement=str(supplement),package_supplement_sha256=sha(supplement))
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
compile(launcher,'prepared-launcher','exec')
(EVIDENCE/'prepared-launcher.py').write_text(launcher)
(EVIDENCE/'prepared-start.json').write_text(json.dumps({'status':'READY_AFTER_GUARDED_STOP','runtime':str(runtime),
    'launcher_sha256':sha(EVIDENCE/'prepared-launcher.py'),'manifest_sha256':sha(EVIDENCE/'live-expected-source.json'),
    'source_count':112,'ui_count':6,'source_files':expected['files'],'ui_files':ui},indent=2))
shutil.copyfile(__file__,EVIDENCE/'executed-prepare-start.py')
print(EVIDENCE)
