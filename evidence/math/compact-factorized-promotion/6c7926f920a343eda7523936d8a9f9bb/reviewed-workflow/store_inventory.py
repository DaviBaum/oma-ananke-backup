"""Read-only all-table logical snapshot and complete application data artifacts."""
from pathlib import Path
import ast,hashlib,json,sqlite3
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').is_file())
DATA=ROOT/'.oma'
# These trees contain development/runtime code or independently owned logs, not
# Store data. Never hash live logs. All other top-level application directories
# are enumerated, including caches, blobs, imported bytes and check/export data.
NON_DATA={'benchmark-builds','development','logs','math-builds','runtimes','test-builds','test-shared-debug','test-snapshots','validated-runtimes'}
CONTROL={'oma.sqlite3','oma.sqlite3-wal','oma.sqlite3-shm','service.validated.json','start_validated_backend.py'}
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def terminal_states(source):
    tree=ast.parse((Path(source)/'oma/store.py').read_text(encoding='utf8'))
    nodes=[n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='TERMINAL_RUN_STATUSES' for t in n.targets)]
    assert len(nodes)==1 and isinstance(nodes[0].value,ast.Call) and isinstance(nodes[0].value.func,ast.Name) and nodes[0].value.func.id=='frozenset'
    value=ast.literal_eval(nodes[0].value.args[0]);assert isinstance(value,set) and all(type(v) is str for v in value)
    return value
def encode(value):
    if isinstance(value,bytes):return {'sqlite_blob_hex':value.hex()}
    return value
def all_tables():
    with sqlite3.connect((DATA/'oma.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
        db.execute('BEGIN')
        schema=[list(r) for r in db.execute('SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name')]
        tables={}
        for kind,name,_,_ in schema:
            if kind!='table':continue
            identifier='"'+name.replace('"','""')+'"'
            cursor=db.execute('SELECT * FROM '+identifier)
            rows=[[encode(v) for v in row] for row in cursor]
            rows.sort(key=lambda row:json.dumps(row,sort_keys=True,separators=(',',':')))
            tables[name]={'columns':[col[0] for col in cursor.description],'rows':rows}
    return {'schema':schema,'tables':tables}
def snapshot():
    result=all_tables();files={};excluded=[]
    for root in DATA.iterdir():
        if root.name in CONTROL or (root.is_dir() and (root.name in NON_DATA or root.name.startswith('test-'))):
            excluded.append(root.name);continue
        assert not root.is_symlink() and not root.is_junction()
        paths=root.rglob('*') if root.is_dir() else [root]
        for path in paths:
            assert not path.is_symlink() and not path.is_junction()
            if not path.is_file():continue
            before=path.stat();h=sha(path);after=path.stat()
            assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
            files[path.relative_to(DATA).as_posix()]={'bytes':after.st_size,'sha256':h}
    assert result==all_tables(),'Database changed during artifact snapshot'
    return {**result,'artifact_files':files,'excluded_runtime_control_or_active_log_members':sorted(excluded),
        'sqlite_scope':'All tables and schema preserved logically; raw WAL/checkpoint byte layout is not an application-data identity.'}
