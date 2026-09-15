"""Bounded completion gate for the authorized seal; never infer test success."""
import hashlib,json,subprocess,time,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
STAGE=Path(__file__).resolve().parent
PREP=ROOT/'evidence/release/factorized-tree-portable-preparation/6e8550168ebb4d21af44196962e2b8f8'
EVIDENCE=ROOT/'evidence/dependencies/native-build/portable-candidates/f73a8793ae0d-ddbee4976390'
PEER=ROOT/'evidence/release/f73-portable-peer/8ea56650c3e045a19916a7f9bcd64bb8/result.json'
OUT=STAGE/'seal-orchestration'/uuid.uuid4().hex;OUT.mkdir(parents=True)
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(v):(OUT/'status.json').write_text(json.dumps(v,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
write({'status':'WAITING_FOR_EXACT_BUNDLED_FULL_PASS','directory':str(OUT)})
try:
    p=read(EVIDENCE/'result.json');peer=read(PEER)
    assert peer['status']=='F73_THREE_RECEIPT_SOURCE_AND_CHECKPOINT_PEER_PASS'
    assert peer['package']==p['package'] and peer['checker_version']==p['identity']['checker_version']
    start=time.monotonic()
    while time.monotonic()-start<3000:
        r=read(EVIDENCE/'bundled-full-suite.json')
        if r['status']=='BUNDLED_EXACT_FROZEN_FULL_SUITE_PASS_WITH_DECLARED_DIRECT_INTERPRETER_NOT_APPLICABLE':break
        assert r['status']=='RUNNING',r['status'];time.sleep(20)
    else:raise TimeoutError('Bounded suite wait exceeded')
    assert r['test_node_count']==3275 and r['passed']==3272 and r['failed']==0 and len(r['skipped'])==3
    for mode in ('suite','cases'):
        for _ in range(10):
            if (PREP/(mode+'-exit.json')).exists():break
            time.sleep(1)
        e=read(PREP/(mode+'-exit.json'));assert e['exit_code']==0 and e['status']=='WRAPPER_EXIT_OBSERVED'
    write({'status':'SEALING_VALIDATED_PACKAGE','peer_sha256':sha(PEER),'full_suite_sha256':sha(EVIDENCE/'bundled-full-suite.json')})
    with (OUT/'stdout.log').open('w',encoding='utf-8') as stdout,(OUT/'stderr.log').open('w',encoding='utf-8') as stderr:
        done=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(PREP/'run-seal.ps1'),'-Result',str(EVIDENCE/'result.json'),'-Preparation',str(PREP)],cwd=ROOT,stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW,timeout=900)
    assert done.returncode==0
    seal=read(EVIDENCE/'sealed-handoff.json');assert seal['status']=='ISOLATED_NATIVE_PORTABLE_CANDIDATE_SEALED_NOT_PROMOTED'
    write({'status':'SEALED_WAITING_FOR_INDEPENDENT_FINAL_INDEX_AUDIT','sealed_handoff_sha256':sha(EVIDENCE/'sealed-handoff.json'),'directory':str(OUT)})
except BaseException as e:write({'status':'FAILED_OR_INCOMPLETE','error':repr(e),'directory':str(OUT)});raise
finally:(OUT/'executed-driver.py').write_bytes(Path(__file__).read_bytes())
print(OUT)
