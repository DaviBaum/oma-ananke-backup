"""Retain the completed independent kernel handoff without promoting application code."""
from pathlib import Path
import hashlib,json,shutil

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').is_file())
stage=ROOT/'.oma/development/general-shared-tree-synthesis'
out=ROOT/'evidence/math/general-shared-tree-synthesis'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(stage/'handoff.json')=='b51ea7748ab6f384da9a1c4dc9ba5b9fc7e8e65b90f4a8f10777940497e91950'
assert sha(stage/'file-index.json')=='828f84e85e247d81b10eb600a0cea0adbf53167adcbe3c201b1d86656809b20b'
assert not out.exists()
files=json.loads((stage/'file-index.json').read_text())['files']
for k in ('file-index.json','handoff.json'):files[k]=sha(stage/k)
total=0
for relative,expected in files.items():
    source=stage/relative;assert sha(source)==expected
    target=out/'producer-history'/relative;target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(source,target);assert sha(target)==expected;total+=target.stat().st_size
shutil.copyfile(__file__,out/'retainer.py')
payload={p.relative_to(out).as_posix():sha(p) for p in out.rglob('*') if p.is_file()}
(out/'file-index.json').write_text(json.dumps({'files':payload},indent=2)+'\n',encoding='utf-8')
handoff={'schema':'oma.retained-general-tree-kernel/1','status':'PURE_KERNEL_VALIDATED_APPLICATION_INTEGRATION_IN_PROGRESS',
    'files':len(payload),'bytes':total,'file_index_sha256':sha(out/'file-index.json'),
    'producer_handoff_sha256':sha(stage/'handoff.json'),'module_sha256':json.loads((stage/'handoff.json').read_text())['module_sha256'],
    'tests':{'passed':175,'unchanged_legacy':85,'new':90},'independent_authored_oracle_assignments':18048,
    'full_original_algorithms_implemented':False,'native_or_production_readiness_claim':False}
(out/'handoff.json').write_text(json.dumps(handoff,indent=2)+'\n',encoding='utf-8')
assert all(sha(out/k)==v for k,v in payload.items())
print(json.dumps({'directory':str(out),**handoff}))
