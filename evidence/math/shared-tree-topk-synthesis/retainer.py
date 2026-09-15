"""Preserve the completed compact topology proof and separate peer review."""
from pathlib import Path
import hashlib,json,shutil
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').is_file())
stage=ROOT/'.oma/development/shared-tree-topk-synthesis'
out=ROOT/'evidence/math/shared-tree-topk-synthesis'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):p.write_text(json.dumps(x,indent=2)+'\n',encoding='utf-8')
assert sha(stage/'handoff.json')=='c56920ad5cecac208f78114de786b4d815b3b29173809778c073f97ff36d3076'
assert sha(stage/'file-index.json')=='02420a17699eb34fe466740ef7b03b0b1e798179e1223086276796db77f69190'
assert not out.exists()
files=json.loads((stage/'file-index.json').read_text())['files']
for key in ('file-index.json','handoff.json'):files[key]=sha(stage/key)
for relative,expected in files.items():
    source=stage/relative;assert sha(source)==expected
    target=out/'producer-history'/relative;target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(source,target);assert sha(target)==expected
peer=stage/'evidence/peer-review-topk/a1547a0298da42f9a6e25d966c85b1f5'
assert sha(peer/'result.json')=='18809cfcfcc7acf6158bce1e15cd9cadeccab192da519df4db4a0ac3de29e164'
assert json.loads((peer/'result.json').read_text())['status']=='PASS'
for p in peer.rglob('*'):
    if p.is_file() and not {'__pycache__','.pytest_cache'}.intersection(p.relative_to(peer).parts):
        target=out/'peer-review'/p.relative_to(peer);target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(p,target);assert sha(p)==sha(target)
shutil.copyfile(__file__,out/'retainer.py')
payload={p.relative_to(out).as_posix():sha(p) for p in out.rglob('*') if p.is_file()}
write(out/'file-index.json',{'files':payload})
write(out/'handoff.json',{'schema':'oma.retained-compact-tree-kernel/1','status':'PURE_KERNEL_AND_PEER_VALIDATED',
    'file_index_sha256':sha(out/'file-index.json'),'files':len(payload),
    'module_sha256':'d04f2ad9ffb72f9935cba93472f49f5dbbe257a0595ccc8c39dcb62d14ca2dbc',
    'cases':261,'unchanged_cases':175,'new_cases':86,'additional_peer_oracle_prefixes':42,'peer_resealed_attacks':7,
    'native_integration_in_progress':True,'full_original_algorithms_implemented':False})
assert all(sha(out/k)==v for k,v in payload.items())
print(json.dumps({'directory':str(out),'files':len(payload),'handoff_sha256':sha(out/'handoff.json')}))
