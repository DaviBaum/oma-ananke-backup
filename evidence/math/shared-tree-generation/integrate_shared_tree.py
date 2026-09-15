"""Bind the reviewed generated-tree implementation and retain prior evidence."""
from pathlib import Path
import hashlib
import json

ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def copy(src,dst):
    data=src.read_bytes()
    if dst.exists():
        assert dst.read_bytes()==data, f'Existing evidence differs: {dst}'
    else:
        dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(data)
    assert sha(src)==sha(dst)
def tree(src,dst):
    rows=[]
    for p in sorted(src.rglob('*')):
        if not p.is_file() or '__pycache__' in p.parts or '.pytest_cache' in p.parts or p.suffix in ('.pyc','.pyo'):continue
        q=dst/p.relative_to(src);copy(p,q)
        rows.append({'path':q.relative_to(ROOT).as_posix(),'sha256':sha(q),'bytes':q.stat().st_size})
    return rows
def write(p,data):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8',newline='\n')

master_path=ROOT/'.oma/development/shared-tree-combined-validation/frozen-inputs.json'
assert sha(master_path)=='d974f896a9d0f2d78ac9b03af3d91bed4419e4996417eecbbcae8d94263c3b9b'
m=read(master_path)
source=Path(m['source_directory']);inputs=Path(m['input_snapshot'])
assert len(m['source_files'])==112 and len(m['snapshot_files'])==162
before={p.relative_to(ROOT/'src').as_posix():sha(p) for p in (ROOT/'src/oma').rglob('*.py')}
assert len(before)==107
changes=[]
for rel,digest in m['source_files'].items():
    p=source/rel;assert sha(p)==digest
    target=ROOT/'src'/rel
    if before.get(rel)!=digest:
        changes.append({'path':target.relative_to(ROOT).as_posix(),'before':before.get(rel),'after':digest})
assert len(changes)==8 and sum(c['before'] is None for c in changes)==5
new_inputs=[]
base=read(ROOT/'evidence/release/coupled-tree-full-17ea63bc503a4b78bb572ffee1dce06f/result.json')['snapshot_files']
for rel,digest in m['snapshot_files'].items():
    p=inputs/rel;assert sha(p)==digest
    if rel not in base:
        assert rel.startswith('tests/')
        assert not (ROOT/rel).exists(),rel
        new_inputs.append(rel)
assert len(new_inputs)==31
for c in changes:
    target=ROOT/c['path'];target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes((source/target.relative_to(ROOT/'src')).read_bytes())
for rel in new_inputs:copy(inputs/rel,ROOT/rel)
assert {p.relative_to(ROOT/'src').as_posix():sha(p) for p in (ROOT/'src/oma').rglob('*.py')}==m['source_files']

retained=[]
for component,folder in [('shared-tree-synthesis','shared-tree-synthesis'),('shared-tree-native-checker','shared-tree-catalogue-provenance'),('shared-tree-coupled-checker','shared-tree-coupled-provenance')]:
    parent=ROOT/'.oma/development'/component
    source_evidence=parent/'evidence/math'/folder
    h=read(source_evidence/'handoff.json')
    for r in h.get('evidence',h.get('evidence_files',[])):
        assert sha(source_evidence/r['path'])==r['sha256']
    retained+=tree(source_evidence,ROOT/'evidence/math'/folder)
    for r in h['merge_files']:
        if r['path'].startswith('docs/'):
            original=parent/r['path'];assert sha(original)==r['sha256']
            copy(original,ROOT/r['path'])
    # Retain further post-handoff peer/parser/resource checks too.
    for d in (parent/'evidence').iterdir():
        if d.name=='math' or not d.is_dir():continue
        retained+=tree(d,ROOT/'evidence/math'/folder/'supplements'/d.name)
    for d in (parent/'evidence/math').iterdir():
        if d.name==folder or not d.is_dir():continue
        retained+=tree(d,ROOT/'evidence/math'/d.name)

history=ROOT/'evidence/math/shared-tree-generation/producer-history'
for name in ['shared-tree-native','shared-tree-coupled']:
    parent=ROOT/'.oma/development'/name
    for child in ['validation','runtimes','authored-fixtures']:
        if (parent/child).is_dir():retained+=tree(parent/child,history/name/child)
    for p in parent.glob('*.py'):
        copy(p,history/name/p.name)
        retained.append({'path':(history/name/p.name).relative_to(ROOT).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size})
copy(master_path,ROOT/'evidence/math/shared-tree-generation/combined-frozen-inputs.json')
record={'status':'REVIEWED_IMPLEMENTATION_INTEGRATED_FULL_VALIDATION_PENDING','source_identity':m['checker_version'],'source_files':m['source_files'],'application_changes':changes,'new_inputs':{x:m['snapshot_files'][x] for x in new_inputs},'combined_master_sha256':sha(master_path),'retained_files':retained,'full_source_algorithms_implemented':False,'physical_global_optimality':False,'live_and_sealed_package_source':'5e8fe9659cfde60f84f5cf93f38a1959428b3e7522de741e905d1f505db2b73c'}
write(ROOT/'evidence/math/shared-tree-generation/integration-preparation.json',record)
copy(Path(__file__),ROOT/'evidence/math/shared-tree-generation/integrate_shared_tree.py')
print(json.dumps({'application_changes':len(changes),'new_inputs':len(new_inputs),'retained_files':len(retained),'retained_bytes':sum(r['bytes'] for r in retained)},indent=2))
