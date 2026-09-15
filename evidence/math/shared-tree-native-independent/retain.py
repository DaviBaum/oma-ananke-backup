"""Copy exact independent evidence without changing private artifacts or Stores."""
from pathlib import Path
import hashlib,json,shutil,time

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').exists())
MATH=ROOT/'evidence/math/shared-tree-native-independent'
OFFICE=ROOT/'evidence/benchmarks/shared-tree-generation-office'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def write(p,v):
    Path(p).parent.mkdir(parents=True,exist_ok=True)
    data=(json.dumps(v,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode('utf8')
    if Path(p).exists():assert Path(p).read_bytes()==data,p
    else:Path(p).write_bytes(data)

mapping=[];declared=[];copies=[]
def copy(source,target,expected=None):
    source=source.resolve();target=target.resolve()
    assert target.is_relative_to(MATH) or target.is_relative_to(OFFICE)
    assert source.is_file() and not source.is_symlink()
    h=sha(source)
    if expected is not None:assert h==expected,source
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():assert sha(target)==h,target
    else:shutil.copy2(source,target)
    assert sha(source)==sha(target)==h
    mapping.append({'original_path':str(source),'original_workspace_relative':source.relative_to(ROOT).as_posix(),
                    'public_path':target.relative_to(ROOT).as_posix(),'sha256':h,'bytes':target.stat().st_size})

def inventory(path):
    data=read(path);rows=data['files'];rows=rows if isinstance(rows,list) else [{'path':name,**row} for name,row in rows.items()]
    total=0
    for row in rows:
        p=(path.parent/row['path']).resolve();assert p.is_relative_to(path.parent.resolve())
        assert p.is_file() and sha(p)==row['sha256'],p
        size=row.get('size_bytes',row.get('bytes'));assert size is not None and p.stat().st_size==size,p
        total+=size
    declared.append({'original_manifest':str(path.resolve()),'sha256':sha(path),'declared_file_count':len(rows),'declared_bytes':total,'status':'ALL_DECLARED_BYTES_REHASHED'})

def tree(source,target):
    before=len(mapping)
    for p in sorted(source.rglob('*')):
        if p.is_file() and '__pycache__' not in p.parts:
            copy(p,target/p.relative_to(source))
    copies.append({'source':str(source.resolve()),'public':target.relative_to(ROOT).as_posix(),'copied_files':len(mapping)-before,
                   'excluded':'Unindexed transient __pycache__ only; explicitly declared historical bytecode is copied with its validation snapshot'})

def checkpoint(stage,identity):
    v=ROOT/'.oma/development'/stage/'validation'/identity;r=read(v/'result.json')
    destination=MATH/'validation-snapshots'/identity
    for relative,h in r.get('input_files',r.get('inputs',{})).items():copy(v/relative,destination/relative,h)
    for name in ('result.json','tests.xml','pytest.log','test-nodes.json'):
        if (v/name).is_file():copy(v/name,destination/name)
    src=Path(r['source_directory']);expected=r['source_files']
    assert {p.relative_to(src).as_posix():sha(p) for p in src.rglob('*.py')}==expected
    build=r['checker_version'].split(':')[-1]
    for relative,h in expected.items():copy(src/relative,MATH/'source-snapshots'/build/'src'/relative,h)
    return {'validation':identity,'checker_version':r['checker_version'],'source_files':len(expected),'validation_status':r['status']}

def main():
    started=time.monotonic()
    roots=[('native-reference',ROOT/'.oma/development/shared-tree-native-reference'),
           ('workflow-review',ROOT/'.oma/development/shared-tree-native-workflow-review'),
           ('coupled-review',ROOT/'.oma/development/shared-tree-coupled-review')]
    office=ROOT/'.oma/development/shared-tree-office/evidence/5f68a587a8654bd187768d03f913388d'
    for _,source in roots:
        for p in source.rglob('*.json'):
            if p.name in ('files.json','completed-files.json'):inventory(p)
    inventory(office/'files.json')
    for name,source in roots:tree(source,MATH/name)
    tree(office,OFFICE/office.name)
    checkpoints=[checkpoint('shared-tree-native','f9c75d13b1334319a6d4822e3acc05da'),
        checkpoint('shared-tree-native','cfe95e6329d740aeafddc3f8d9445d62'),
        checkpoint('shared-tree-coupled','3a0b4376378449f1b52402ffb412f546'),
        checkpoint('shared-tree-coupled','0b39284a65564d34b94af6500453051b')]
    # The native reference uses frozen5e8; the real Office request uses frozen4b0.
    extra=[ROOT/'.oma/development/coupled-native-integration/runtimes/5e8fe9659cfde60f84f5cf93f38a1959428b3e7522de741e905d1f505db2b73c/src',
           ROOT/'.oma/development/shared-tree-native/runtimes/4b0af802a0934f31a0fc0812a9d23afccb22b048e48f888604d7ff9c1603fbb0/src']
    office_sources=read(office/'predeclaration.json')['application_sources']
    for src in extra:
        files={p.relative_to(src).as_posix():sha(p) for p in src.rglob('*.py')}
        if src.parent.name.startswith('4b0'):assert files==office_sources
        for relative,h in files.items():copy(src/relative,MATH/'source-snapshots'/src.parent.name/'src'/relative,h)
    standalone=[ROOT/'.oma/development/shared-tree-synthesis/runtimes/d1245404a41acadc38880a45a584757654c867aeb15971d7260cccf817551cb7/src/oma/optimization/shared_tree_synthesis.py',
        ROOT/'.oma/development/shared-tree-native-checker/runtimes/2db9a9cd13eea2fbd1633b4b9a02f44892a90d37f870d25d005c6a283c648ab4/src/oma/routing/shared_tree_catalogue_check.py',
        ROOT/'.oma/development/shared-tree-coupled-checker/runtimes/0f780ef00357d14887bdb067263b8ed891cddeed91aa7ccdc5169e3ebf1a7a29/src/oma/routing/shared_tree_catalogue_check.py']
    for path in standalone:copy(path,MATH/'standalone-source-snapshots'/sha(path)/path.name)
    authored=ROOT/'.oma/development/shared-tree-coupled/authored-fixtures/3db9529abfc94c59a72ac2dfd6a06138'
    tree(authored,MATH/'authored-fixture-snapshots'/authored.name)
    # Recheck the public copies against every preserved declared inventory.
    for root in (MATH/'native-reference',MATH/'workflow-review',MATH/'coupled-review',OFFICE/office.name):
        for p in root.rglob('*.json'):
            if p.name in ('files.json','completed-files.json'):
                data=read(p);rows=data['files'];rows=rows if isinstance(rows,list) else [{'path':n,**r} for n,r in rows.items()]
                for row in rows:assert sha(p.parent/row['path'])==row['sha256']
    manifest={'schema':'oma.shared-tree-independent-public-mapping/1','copies':copies,'declared_inventory_rechecks':declared,
        'files':mapping,'source_checkpoints':checkpoints,
        'scope':'Exact copied files and source/test dependencies; absolute original provenance preserved. Original live Stores/native caches/wheels are not duplicated. Source snapshots alone do not recreate a matching native runtime.'}
    write(MATH/'public-mapping.json',manifest)
    office_map={'schema':manifest['schema'],'files':[x for x in mapping if x['public_path'].startswith(OFFICE.relative_to(ROOT).as_posix()+'/')],
        'shared_source_dependency_mapping':'../../math/shared-tree-native-independent/public-mapping.json',
        'checker_version':'oma-independent-checker/2:4b0af802a0934f31a0fc0812a9d23afccb22b048e48f888604d7ff9c1603fbb0',
        'superseded_by_33a':False,'scope':'Historical actual Office fixed-flow generation campaign; final33a coupled native workflow is a separate analytic mission.'}
    write(OFFICE/'public-mapping.json',office_map)
    result={'status':'PUBLIC_RETENTION_COPY_AND_INVENTORY_PASS','declared_inventories':len(declared),'copied_file_rows':len(mapping),
        'copied_logical_bytes':sum(x['bytes'] for x in mapping),'copy_groups':copies,'source_checkpoints':checkpoints,
        'all_originals_unchanged':all(sha(Path(x['original_path']))==x['sha256'] for x in mapping),'elapsed_seconds':time.monotonic()-started}
    write(MATH/'retention-result.json',result)
    print(json.dumps(result))

if __name__=='__main__':main()
