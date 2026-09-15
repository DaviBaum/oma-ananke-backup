"""Retain closed archive execution and separately indexed public companion."""
from pathlib import Path
import hashlib,json,shutil,subprocess

ROOT=Path(__file__).resolve().parents[3]
STAGE=Path(__file__).resolve().parent
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def copy(source,target):
    raw=Path(source).read_bytes();expected=hashlib.sha256(raw).hexdigest()
    Path(target).write_bytes(raw);assert sha(source)==sha(target)==expected
def save(p,value):
    assert not p.exists(),p
    p.write_text(json.dumps(value,indent=2),encoding='utf-8')

closed=read(STAGE/'archive-exit.json')
assert closed['status']=='WRAPPER_EXIT_OBSERVED' and closed['exit_code']==0
launch=read(STAGE/'archive-launcher.json')
# A completed exit receipt plus closed wrapper confirms no remaining writer of its logs.
process=subprocess.run(['powershell.exe','-NoProfile','-Command',
    f"@(Get-CimInstance Win32_Process -Filter 'ProcessId={int(launch['pid'])}').Count"],
    capture_output=True,text=True,check=True)
assert process.stdout.strip()=='0','Archive wrapper is still live; retain only closed logs'
assert sha(STAGE/'run-archive.ps1')==launch['wrapper_sha256']
assert sha(STAGE/'archive.py')==launch['driver_sha256']
lines=[json.loads(line) for line in (STAGE/'archive.stdout.log').read_text(encoding='utf-8-sig').splitlines() if line.strip()]
result=lines[-1];out=Path(result['directory']);public=Path(result['public'])
assert out.is_relative_to(ROOT/'.release/github-backup')
assert public==ROOT/'evidence/release/factorized-tree-portable-archive'/out.name
manifest=read(out/'f73-portable-archive-manifest.json')
assert manifest==result['manifest']
assert manifest['status']=='SEALED_F73_PORTABLE_AND_DOCUMENTATION_ARCHIVE_VERIFIED_READY_FOR_PRIVATE_UPLOAD'
assert Path(manifest['archive']).resolve()==(out/'oma-ananke-f73a8793ae0d-portable.zip').resolve()
assert sha(manifest['archive'])==manifest['archive_sha256']
assert Path(manifest['archive']).stat().st_size==manifest['archive_bytes']
for name in ('f73-portable-archive-manifest.json','RESTORE-F73-PORTABLE.md'):
    assert sha(out/name)==sha(public/name)
assert sha(public/'executed-archive.py')==launch['driver_sha256']
for name in ('run-archive.ps1','archive-launcher.json','archive-exit.json','archive.stdout.log','archive.stderr.log'):
    copy(STAGE/name,public/name)
copy(__file__,public/'executed-retention.py')

docs=STAGE/'f73-checkpoint-documentation'
companion=ROOT/'evidence/release/factorized-tree-documentation-companion-ddbee4976390'
index=read(docs/'documentation-files.json')
assert sha(docs/'documentation-files.json')==manifest['documentation_index_sha256']
assert index['completed_package_handoff_sha256']==manifest['completed_handoff_sha256']
expected={name:row['sha256'] for name,row in index['files'].items()}
expected['documentation-files.json']=sha(docs/'documentation-files.json')
assert set(expected)=={p.relative_to(docs).as_posix() for p in docs.rglob('*') if p.is_file()}
assert set(expected)=={p.relative_to(companion).as_posix() for p in companion.rglob('*') if p.is_file()}
for name,value in expected.items():assert sha(docs/name)==sha(companion/name)==value
save(companion/'handoff.json',{'status':'F73_SEPARATE_DOCUMENTATION_COMPANION_RETAINED',
    'documentation_index_sha256':expected['documentation-files.json'],
    'package_handoff_sha256':index['completed_package_handoff_sha256'],
    'git_commit':index['git_commit'],'package_payload_modified':False,
    'scope':'Public copy of separately indexed companion, with no additions to sealed package.',
    'files':expected})
assets={name:{'path':str(out/name),'sha256':sha(out/name),'bytes':(out/name).stat().st_size}
    for name in ('oma-ananke-f73a8793ae0d-portable.zip','f73-portable-archive-manifest.json','RESTORE-F73-PORTABLE.md')}
save(public/'completed-evidence.json',{'status':'VERIFIED_F73_ARCHIVE_PREPARATION_COMPLETE',
    'files':{p.relative_to(public).as_posix():sha(p) for p in public.rglob('*') if p.is_file()},
    'assets':assets,'companion_handoff':str(companion/'handoff.json'),
    'companion_handoff_sha256':sha(companion/'handoff.json'),'upload_performed':False,
    'wrapper_closed':True,'observed_exit_code':0})
print(json.dumps({'archive_handoff':str(public/'completed-evidence.json'),
    'archive_handoff_sha256':sha(public/'completed-evidence.json'),
    'companion_handoff':str(companion/'handoff.json'),
    'companion_handoff_sha256':sha(companion/'handoff.json'),'assets':assets}))
