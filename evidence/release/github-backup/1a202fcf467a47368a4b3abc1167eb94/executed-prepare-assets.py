"""Verified private backup release assets; originals and existing packages are read-only."""
from contextlib import contextmanager
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import time
import uuid
import zipfile

ROOT=Path(__file__).resolve().parents[3]
ID=uuid.uuid4().hex
DEST=ROOT/'.release/github-backup'/ID
EVIDENCE=ROOT/'evidence/release/github-backup'/ID
DEST.mkdir(parents=True);EVIDENCE.mkdir(parents=True)
LIMIT=int(1.7*1024**3)
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
    return h.hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,v):Path(p).write_text(json.dumps(v,indent=2),encoding='utf-8')
state={'status':'RUNNING','id':ID,'destination':str(DEST),'started_utc':datetime.now(timezone.utc).isoformat(),
    'assets':[],'originals_modified':False,'upload_performed':False,'script_sha256':sha(__file__)}
def persist():write(EVIDENCE/'result.json',state)
def log(message):print(json.dumps(message),flush=True)
persist();shutil.copyfile(__file__,EVIDENCE/'executed-prepare-assets.py')
log({'evidence':str(EVIDENCE),'destination':str(DEST)})
def inventory(directory):
    return [{'path':p.relative_to(directory).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)}
            for p in sorted(directory.rglob('*')) if p.is_file()]
def archive(label,directory,rows,metadata=None):
    write(EVIDENCE/(label+'-input-manifest.json'),{'root':str(directory),'files':rows,'metadata':metadata})
    batches=[];batch=[];size=0
    for row in rows:
        assert row['bytes']<LIMIT, 'Individual file needs explicit split protocol'
        if batch and size+row['bytes']>LIMIT:batches.append(batch);batch=[];size=0
        batch.append(row);size+=row['bytes']
    if batch:batches.append(batch)
    for part,batch in enumerate(batches,1):
        name=f'{label}.part{part:03d}-of-{len(batches):03d}.zip'
        path=DEST/name
        with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=True) as z:
            for row in batch:
                p=directory/row['path'];h=hashlib.sha256();n=0
                with p.open('rb') as f,z.open(label+'/'+row['path'],'w',force_zip64=True) as out:
                    for b in iter(lambda:f.read(4*1024**2),b''):out.write(b);h.update(b);n+=len(b)
                assert n==row['bytes'] and h.hexdigest()==row['sha256'], 'Input changed during zip'
        assert path.stat().st_size<int(1.8*1024**3)
        with zipfile.ZipFile(path) as z:
            expected={label+'/'+r['path']:r for r in batch}
            assert len(z.infolist())==len(expected) and set(z.namelist())==set(expected)
            for info in z.infolist():
                row=expected[info.filename];assert info.file_size==row['bytes']
                h=hashlib.sha256()
                with z.open(info) as f:
                    for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
                assert h.hexdigest()==row['sha256']
        asset={'name':name,'path':str(path),'bytes':path.stat().st_size,'sha256':sha(path),'members':len(batch),
            'uncompressed_bytes':sum(r['bytes'] for r in batch),'status':'ZIP_MEMBER_SHA256_VERIFIED',
            'input_manifest':str(EVIDENCE/(label+'-input-manifest.json')),'part':part,'parts':len(batches)}
        state['assets'].append(asset);persist();log(asset)
    assert inventory(directory)==rows,'Original input inventory changed after archive'

try:
    math=ROOT/'math1';archive('original-mathematics',math,inventory(math))
    hospital=ROOT/'data/ifc-bench/projects/west_riverside_hospital'
    rows=inventory(hospital)
    assert sum(r['path'].endswith('.ifc') for r in rows)==14
    assert {'license.txt','model_card.md'}<=set(r['path'] for r in rows)
    archive('hospital-original-models',hospital,rows,{'scope':'Both IFC2x3/IFC4 seven-discipline original tracks with original model card and license'})

    pending=read(ROOT/'evidence/release/github-backup/4ae448a09d3147fd88d95f7c2ec1b0ef/pending-status.json')
    names=['ui/src/style.css','ui/qa/opening-README.md']+[s[3:] for s in pending if s.startswith('?? ui/qa/')]
    assert len(names)==13 and len(set(names))==13
    wip=DEST/'ui-working-state';wip.mkdir()
    for name in names:
        target=wip/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
        assert sha(ROOT/name)==sha(target)
    patch=subprocess.check_output(['git','diff','--binary','0c7b0fb592e0fe64bd69b4e54088995781336158','--','ui/src/style.css','ui/qa/opening-README.md'],cwd=ROOT)
    (wip/'original-two-file-diff.patch').write_bytes(patch)
    write(wip/'scope.json',{'base_commit':'0c7b0fb592e0fe64bd69b4e54088995781336158','raw_files':names,
        'scope':'Raw two modified files and 11 QA files observed before backup; binary diff against the pre-backup commit, also valid if files were subsequently committed'})
    archive('ui-working-state',wip,inventory(wip))

    meta=read(ROOT/'.oma/service.validated.json');sys.path.insert(0,meta['pythonpath'])
    os.environ['PYTHONPATH']=meta['pythonpath'];os.environ['OMA_EXECUTABLE_BUILD']=meta['executable_build']
    from oma.build_identity import checker_version
    from oma.backup import backup_store,verify_backup
    from oma.store import Store,_Connection
    assert checker_version()==meta['executable_build']
    class ReadOnlyStore(Store):
        def __init__(self,directory):
            self.directory=Path(directory).resolve();self.database=self.directory/'oma.sqlite3';self.blobs=self.directory/'blobs'
        def connect(self):
            db=sqlite3.connect(self.database.as_uri()+'?mode=ro',uri=True,timeout=30,isolation_level=None,factory=_Connection)
            db.row_factory=sqlite3.Row;return db
        def put(self,*a,**k):raise AssertionError('Original Store write forbidden')
    store=ReadOnlyStore(ROOT/'.oma')
    with store.connect() as db:
        before={name:[list(row) for row in db.execute('SELECT * FROM '+name+' ORDER BY rowid')]
                for name in ('projects','revisions','runs','candidates','run_owners')}
    db_sha=sha(store.database)
    backup=backup_store(store,DEST/'current-project-store')
    verified=verify_backup(backup);assert verified['status']=='PASS'
    with store.connect() as db:
        after={name:[list(row) for row in db.execute('SELECT * FROM '+name+' ORDER BY rowid')] for name in before}
    assert before==after and sha(store.database)==db_sha
    write(EVIDENCE/'store-backup-verification.json',{'status':'PASS','verification':verified,'original_database_sha256':db_sha,
        'original_rows_unchanged':True,'counts':{k:len(v) for k,v in before.items()},'checker_version':checker_version(),
        'original_open_mode':'SQLite mode=ro; no Store initializer or source publication invoked'})
    archive('current-project-store',backup,inventory(backup),verified)

    package=ROOT/'.release/native-build/portable-candidates/5e8fe9659cfd-82d3a00a6ff4'
    sealed=read(ROOT/'evidence/dependencies/native-build/portable-candidates/5e8fe9659cfd-82d3a00a6ff4/sealed-handoff.json')
    index=package/'artifact-files.json'
    assert sha(index)==sealed['artifact_index_sha256']=='672444ca71c94e3970e60243a341b4d30d2c5070d39b179dc8d28c72ea75b997'
    indexed=read(index)
    rows=inventory(package)
    actual={r['path']:r for r in rows if r['path']!='artifact-files.json'}
    assert actual=={r['path']:r for r in indexed['files']}
    assert len(actual)==14450 and sum(r['bytes'] for r in actual.values())==1980048071
    archive('sealed-runtime-5e8',package,rows,{'sealed_handoff':sealed,'scope':'Existing validated 5e8 portable runtime; latest33a application source is in the Git repository; this archive does not upgrade or relabel the older package'})

    instructions='''# Restoring this private backup

The Git repository retains committed application source, evidence, and history. Clone it normally. The current validated source checkpoint is 33a20d125bba02a298d12048a5b6227e51a98d8a043b999097d94a8d88b67b95. The runtime archive is the separately validated older 5e8 package; its original proofs remain unchanged and do not certify newer source automatically.

Download all ZIP parts for each desired label into a new directory. Verify each SHA256 against backup-assets-manifest.json before extraction. Each part is an independent ZIP: extract every part into the same EMPTY restore directory. Do not overwrite the original workspace. ZIP member identities were independently read and hashed after creation.

- original-mathematics: original math1 contents, preserved verbatim.
- hospital-original-models: all 14 original hospital IFC files (seven disciplines in each of IFC2x3 and IFC4), plus the original license and model card. No new hospital result is claimed by this backup.
- ui-working-state: raw two changed UI files, 11 QA files, and a binary diff against the pre-backup commit. Review before applying to any checkout; the Git backup may already include them.
- current-project-store: portable Store with immutable roots, report/source/materialization closure and database. With the checked-out source and dependencies available, call oma.backup.verify_backup(path). To create a NEW operational Store, use oma.backup.restore_store(path, new_destination); never restore over the live original. Restored runs do not inherit live process ownership. Existing reports may require fresh verification under a different checker or runtime.
- sealed-runtime-5e8: all files of the unchanged sealed Windows portable candidate. Extract all parts together, read its README.md and CANDIDATE-STATUS.txt, then use its launcher. Its public redistribution status remains NOT_CLEARED; this backup repository is private.

No active process, virtual environment, whole private development tree, duplicated benchmark caches, or every historical temporary Store is claimed to be included. The supported current Store closure, original math, hospital inputs, source/evidence/history, UI work and sealed runtime are explicitly covered.
'''
    (DEST/'RESTORE.md').write_text(instructions,encoding='utf-8')
    state.update(status='ALL_BACKUP_ASSETS_PREPARED_AND_VERIFIED',completed_utc=datetime.now(timezone.utc).isoformat(),
        restore_instructions_sha256=sha(DEST/'RESTORE.md'),total_archive_bytes=sum(a['bytes'] for a in state['assets']))
    write(DEST/'backup-assets-manifest.json',state)
    shutil.copyfile(DEST/'RESTORE.md',EVIDENCE/'RESTORE.md')
    shutil.copyfile(DEST/'backup-assets-manifest.json',EVIDENCE/'backup-assets-manifest.json')
    persist();log({'status':state['status'],'result':str(EVIDENCE/'result.json'),'assets':len(state['assets']),'bytes':state['total_archive_bytes']})
except BaseException as exc:
    state.update(status='FAILED_RETAINED_PARTIAL_ASSETS',error=repr(exc));persist();raise
