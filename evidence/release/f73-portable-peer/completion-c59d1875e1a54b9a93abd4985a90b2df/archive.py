"""Archive a sealed package plus separately indexed current documentation."""
import hashlib,json,shutil,uuid,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
STAGE=Path(__file__).resolve().parent
HANDOFF=ROOT/'evidence/release/factorized-tree-portable-completed-ddbee4976390/handoff.json'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
h=read(HANDOFF);assert h['status']=='F73_NATIVE_PORTABLE_SEALED_AND_INDEPENDENTLY_AUDITED'
package=Path(h['package']);docs=STAGE/'f73-checkpoint-documentation'
package_index=package/'artifact-files.json';docs_index=docs/'documentation-files.json'
assert sha(package_index)==h['artifact_index_sha256']
pi=read(package_index);di=read(docs_index)
assert pi['file_count']==h['file_count'] and di['completed_package_handoff_sha256']==sha(HANDOFF)
assert di['package_artifact_index_sha256']==h['artifact_index_sha256'] and di['package_payload_modified'] is False
assert di['status']=='SEPARATE_CURRENT_F73_DOCUMENTATION_COMPANION'
package_files={r['path']:{k:r[k] for k in ('sha256','bytes')} for r in pi['files']}
assert len(package_files)==pi['file_count']
package_files['artifact-files.json']={'sha256':sha(package_index),'bytes':package_index.stat().st_size}
docs_files=dict(di['files']);assert len(docs_files)==di['file_count']
docs_files['documentation-files.json']={'sha256':sha(docs_index),'bytes':docs_index.stat().st_size}
expected={}
for source,files in ((package,package_files),(docs,docs_files)):
    assert set(files)=={p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file()}
    for name,row in files.items():
        path=(source/name).resolve();assert path.is_relative_to(source.resolve()) and not path.is_symlink()
        target=source.name+'/'+name;assert target not in expected
        expected[target]={'path':path,**row}
out=ROOT/'.release/github-backup'/('f73a8793ae0d-'+uuid.uuid4().hex[:12]);out.mkdir(parents=True)
archive=out/'oma-ananke-f73a8793ae0d-portable.zip'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
    for i,(name,row) in enumerate(sorted(expected.items()),1):
        digest=hashlib.sha256();count=0
        with row['path'].open('rb') as original,z.open(name,'w',force_zip64=True) as target:
            for block in iter(lambda:original.read(1024*1024),b''):
                digest.update(block);count+=len(block);target.write(block)
        assert digest.hexdigest()==row['sha256'] and count==row['bytes'],name
        if i%2000==0:print(json.dumps({'stage':'archive','files':i}),flush=True)
assert archive.stat().st_size<int(1.8*1024**3),'Keep oversized archive; split before upload'
with zipfile.ZipFile(archive) as z:
    members=z.infolist();assert len(members)==len(expected) and {m.filename for m in members}==set(expected)
    for i,member in enumerate(members,1):
        row=expected[member.filename];assert member.file_size==row['bytes'];digest=hashlib.sha256()
        with z.open(member) as f:
            for block in iter(lambda:f.read(1024*1024),b''):digest.update(block)
        assert digest.hexdigest()==row['sha256'],member.filename
        if i%2000==0:print(json.dumps({'stage':'archive-member-recheck','files':i}),flush=True)
assert sha(package_index)==h['artifact_index_sha256'] and sha(docs_index)==docs_files['documentation-files.json']['sha256']
for source,files in ((package,package_files),(docs,docs_files)):
    assert set(files)=={p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file()}
manifest={'status':'SEALED_F73_PORTABLE_AND_DOCUMENTATION_ARCHIVE_VERIFIED_READY_FOR_PRIVATE_UPLOAD',
    'archive':str(archive),'archive_sha256':sha(archive),'archive_bytes':archive.stat().st_size,
    'zip_members':len(expected),'source_checkpoint':h['source_checkpoint'],'checker_version':h['checker_version'],
    'artifact_index_sha256':h['artifact_index_sha256'],'indexed_package_files':h['file_count'],
    'indexed_package_logical_bytes':h['logical_bytes'],'package_archive_members':len(package_files),
    'documentation_archive_members':len(docs_files),'documentation_index_sha256':sha(docs_index),
    'documentation_git_commit':di['git_commit'],'documentation_entry':docs.name+'/CHECKPOINT.md',
    'completed_handoff_sha256':sha(HANDOFF),'source_package':str(package),'source_package_written':False,
    'scope':'Every ZIP member is separately decompressed/rehashed against either the sealed package index or the explicit documentation companion index. No validated package bytes changed. Upload remains root-owned.'}
(out/'f73-portable-archive-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
restore=f'''# Restore the f73 portable checkpoint

**Read `f73-checkpoint-documentation/CHECKPOINT.md` first.** The companion contains the current compact/factorized API guide, complete five/eight-sink examples and mathematical contracts. The package's own `docs` folder is its historical EDF documentation captured before f73 documentation promotion; it is deliberately preserved as tested.

1. Verify this ZIP's SHA256 against `f73-portable-archive-manifest.json`, then extract into a new location. It contains two distinct folders: `{package.name}` (sealed package) and `f73-checkpoint-documentation` (separately indexed current docs). The archive manifest accounts for both.
2. Enter `{package.name}` and run `OMA.cmd`. Its package launcher defaults to **8765**, so the default URL is **http://127.0.0.1:8765**. To choose another port explicitly, run `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\Start-OMA.ps1 -Port <port>` and use that configured URL. The separate validated workspace server used **8768** at handoff; it is not automatically this extracted copy.
3. Application data is a separate backup. Preserve original Store/source archives and use their verified restore instructions to restore to a new location. This runtime ZIP contains no Hospital/IFC-Bench dataset and does not replace the data backup. Earlier EDF and 5e8 packages remain separate versions.

Source: `{h['source_checkpoint']}`. Bundled checker: `{h['checker_version']}`. Original and custom native suites each passed 3,275 exact cases. The same bundled inventory passed 3,272 plus three named direct-interpreter bridge cases not applicable; those three passed in both other environments. Three saved Office exports were freshly checked under the bundle, with independent receipt/proof review and complete final file-index hashing.

The new compact/factorized functions are bounded to the declared catalogue, coefficient model and native numerical scope. A nominal prefix is not physical feasibility or unrestricted optimality; original mathematics and whole-building routing remain incomplete. Hospital attempts remain unresolved. The companion is documentation, not additional native proof. Python network-denial probes are not an OS firewall. This is a private backup; public redistribution rights are not asserted.
'''
(out/'RESTORE-F73-PORTABLE.md').write_text(restore,encoding='utf-8')
public=ROOT/'evidence/release/factorized-tree-portable-archive'/out.name;public.mkdir(parents=True)
for name in ('f73-portable-archive-manifest.json','RESTORE-F73-PORTABLE.md'):shutil.copyfile(out/name,public/name)
shutil.copyfile(__file__,public/'executed-archive.py')
print(json.dumps({'directory':str(out),'public':str(public),'manifest':manifest}),flush=True)
