"""Bind the independently tested idle-stream timeout to the prepared launcher."""
from pathlib import Path
import ast,hashlib,json,shutil
ROOT=Path.cwd();HERE=Path(__file__).resolve().parent
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
evidence=Path(read(HERE/'prepared/latest-preflight.json')['directory'])
probe=ROOT/'evidence/release/uvicorn-sse-shutdown/e2f87cc540e34a62a1cc588943b47c55'
assert sha(probe/'handoff.json')=='05cd515cc32d48a63fb9afcc01544801ab3ed4e50c7079fb26d8447cfb696427'
assert sha(probe/'timeout-10/result.json')=='b670431332fb1f33e4769d85a60ee10114dcfa3445f31c015603055b9ec845d0'
test=read(probe/'timeout-10/result.json');assert test['status']=='PASS' and test['timeout_graceful_shutdown']==10 and test['returncode']==0
assert test['two_SSE_heartbeats_observed'] and test['store_semantically_unchanged'] and test['port_released'] and test['cleanup_complete']['closing'] and test['cleanup_complete']['alive']==0
manifest=read(evidence/'live-expected-source.json');assert test['environment']['OMA_EXECUTABLE_BUILD']==manifest['checker_version']
old=read(evidence/'prepared-start.json');launcher=evidence/'prepared-launcher.py';assert sha(launcher)==old['launcher_sha256']
out=evidence/'shutdown-timeout';out.mkdir(exist_ok=False)
shutil.copyfile(launcher,out/'before-launcher.py');shutil.copyfile(evidence/'prepared-start.json',out/'before-prepared-start.json');shutil.copyfile(__file__,out/'apply.py')
code=launcher.read_text();needle='host="127.0.0.1", port=8768, log_level="info", access_log=False)'
assert code.count(needle)==1
code=code.replace(needle,'host="127.0.0.1", port=8768, log_level="info", access_log=False, timeout_graceful_shutdown=10)')
tree=ast.parse(code);calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and isinstance(n.func.value,ast.Name) and n.func.value.id=='uvicorn' and n.func.attr=='run'];assert len(calls)==1
assert [ast.literal_eval(k.value) for k in calls[0].keywords if k.arg=='timeout_graceful_shutdown']==[10]
launcher.write_text(code,encoding='utf-8');shutil.copyfile(launcher,out/'after-launcher.py')
new={**old,'launcher_sha256':sha(launcher),'timeout_graceful_shutdown_seconds':10,'shutdown_test_handoff':str(probe/'handoff.json'),'shutdown_test_handoff_sha256':sha(probe/'handoff.json')}
(evidence/'prepared-start.json').write_text(json.dumps(new,indent=2));shutil.copyfile(evidence/'prepared-start.json',out/'after-prepared-start.json')
result={'status':'TESTED_IDLE_STREAM_TIMEOUT_BOUND_TO_PREPARED_LAUNCHER','timeout_graceful_shutdown_seconds':10,'source_version':manifest['checker_version'],'application_source_unchanged':True,'old_live_launcher_unchanged':sha(ROOT/'.oma/start_validated_backend.py')==read(evidence/'old-service.validated.json')['launcher_sha256'],'launcher_sha256':sha(launcher),'test_receipt_sha256':sha(probe/'timeout-10/result.json'),'scope':'Bounds Uvicorn idle connection/task draining; lifespan cleanup is still awaited separately. No full shutdown time bound or active-worker cancellation guarantee.'}
assert result['old_live_launcher_unchanged']
(out/'result.json').write_text(json.dumps(result,indent=2));(out/'handoff.json').write_text(json.dumps({'status':result['status'],'retained_files':{p.name:sha(p) for p in out.iterdir() if p.is_file()}},indent=2))
print(json.dumps(result))
