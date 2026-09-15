"""Retain the completed live switch and make its metadata self-describing."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT=next(p for p in Path(__file__).resolve().parents if (p/"AGENTS.md").exists())
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
directory=Path(read(Path(__file__).parent/'latest-preflight.json')['directory'])
result=read(directory/'result.json')
assert result['status']=='VALIDATED_HOSPITAL_BACKEND_LIVE_AND_INVARIANTS_PASS'
meta=read(ROOT/'.oma/service.validated.json')
assert meta['pid']==result['launcher_pid'] and meta['executable_build']==result['checker_version']
meta.update(server_pid=result['server_pid'],server_created=result['server_created'],launcher_created=result['launcher_created'],
    validation_receipt=str(directory/'result.json'),validation_receipt_sha256=sha(directory/'result.json'))
(ROOT/'.oma/service.validated.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
shutil.copyfile(ROOT/'.oma/service.validated.json',directory/'verified-service.validated.json')
shutil.copyfile(ROOT/'.oma/start_validated_backend.py',directory/'verified-start_validated_backend.py')
for key in ('stdout','stderr'):shutil.copyfile(meta[key],directory/('verified-startup.'+key+'.log'))
shutil.copyfile(__file__,directory/'executed-finalize.py')
handoff={'status':'VALIDATED_HOSPITAL_LIVE_UPDATE_COMPLETED','url':result['url'],
    'result_sha256':sha(directory/'result.json'),'metadata_sha256':sha(ROOT/'.oma/service.validated.json'),
    'scope':'Original-native local runtime with immutable validated source; same Store and six UI assets; no new portable package',
    'append_only_active_logs':[meta['stdout'],meta['stderr']],
    'retained_files':{p.name:sha(p) for p in directory.iterdir() if p.is_file() and str(p) not in (meta['stdout'],meta['stderr'])}}
(directory/'handoff.json').write_text(json.dumps(handoff,indent=2),encoding='utf-8')
print(json.dumps({'handoff':str(directory/'handoff.json'),'sha256':sha(directory/'handoff.json'),'result':result}))
