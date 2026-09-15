"""Prepare one verified private-release ZIP of the sealed EDF bundle, no upload."""
import hashlib,json,shutil,uuid,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
HANDOFF=ROOT/'evidence/release/general-tree-portable-completed-0223f1d6bacc/handoff.json'
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
h=read(HANDOFF);assert h['status']=='EDF_NATIVE_PORTABLE_SEALED_AND_INDEPENDENTLY_AUDITED'
source=Path(h['package']);index_path=source/'artifact-files.json'
assert sha(index_path)==h['artifact_index_sha256']
index=read(index_path);expected={x['path']:{'sha256':x['sha256'],'bytes':x['bytes']} for x in index['files']}
assert len(expected)==h['file_count']==index['file_count']
expected['artifact-files.json']={'sha256':sha(index_path),'bytes':index_path.stat().st_size}
assert set(expected)=={p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file()}
out=ROOT/'.release/github-backup'/('edf555760245-'+uuid.uuid4().hex[:12]);out.mkdir(parents=True)
archive=out/'oma-ananke-edf555760245-portable.zip'
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
    for i,(name,row) in enumerate(sorted(expected.items()),1):
        p=(source/name).resolve();assert p.is_relative_to(source.resolve()) and p.is_file()
        digest=hashlib.sha256();count=0
        with p.open('rb') as original,z.open(source.name+'/'+name,'w',force_zip64=True) as target:
            for block in iter(lambda:original.read(1024*1024),b''):
                digest.update(block);count+=len(block);target.write(block)
        assert digest.hexdigest()==row['sha256'] and count==row['bytes'],name
        if i%2000==0:print(json.dumps({'stage':'archive','files':i}),flush=True)
assert archive.stat().st_size<int(1.8*1024**3),'Retain oversized archive; split before upload'
with zipfile.ZipFile(archive) as z:
    infos=z.infolist();assert len(infos)==len(expected) and len({x.filename for x in infos})==len(expected)
    for i,info in enumerate(infos,1):
        name=info.filename.removeprefix(source.name+'/');assert info.filename==source.name+'/'+name and name in expected
        row=expected[name];assert info.file_size==row['bytes'];digest=hashlib.sha256()
        with z.open(info) as member:
            for block in iter(lambda:member.read(1024*1024),b''):digest.update(block)
        assert digest.hexdigest()==row['sha256'],name
        if i%2000==0:print(json.dumps({'stage':'archive-member-recheck','files':i}),flush=True)
assert sha(index_path)==h['artifact_index_sha256']
assert set(expected)=={p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file()}
manifest={'status':'SEALED_EDF_PORTABLE_ARCHIVE_VERIFIED_READY_FOR_PRIVATE_UPLOAD','archive':str(archive),
    'archive_sha256':sha(archive),'archive_bytes':archive.stat().st_size,'zip_members':len(expected),
    'source_checkpoint':h['source_checkpoint'],'checker_version':h['checker_version'],
    'artifact_index_sha256':h['artifact_index_sha256'],'indexed_files':h['file_count'],'indexed_logical_bytes':h['logical_bytes'],
    'completed_handoff_sha256':sha(HANDOFF),'source_package':str(source),'source_package_written':False,
    'scope':'Each archived member matches the sealed source bytes and was independently decompressed/rehashed. All prior package archives preserved. Upload is root-owned and has not been performed by this script.'}
(out/'edf-portable-archive-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
restore=f'''# EDF portable backup

This ZIP contains the separately sealed `{source.name}` Windows package. It preserves the exact EDF application source and bundled Python/native runtime identified in `edf-portable-archive-manifest.json`.

1. Verify the ZIP SHA256 against that manifest, then extract it into a new directory. Keep earlier 5e8 or 52bd packages separate.
2. The extracted folder contains `OMA.cmd`, `Start-OMA.ps1`, its bundled runtime, and `artifact-files.json`. Launch `OMA.cmd` when you intend to start that copy. Existing running services and their Store directories should be handled separately.
3. Application data is a separate backup. Use the existing verified Store backup and its RESTORE instructions; this package is not a replacement for those Store/source archives. Preserve the original backup and restore into a new location.

Original-native and custom-native suites each passed 3012 exact cases. The bundled run passed 3009 plus the three named direct-interpreter bridge cases marked not applicable; those three passed in the other environments. Three unchanged saved Office IFC exports were freshly rechecked. The source and evidence are limited to the declared supported numerical models, finite catalogues and native check scope; this is not a complete original-mathematics or unrestricted/global building optimization claim.

The next private compact-search module is absent. Six prebuilt UI assets are unchanged. The original 5e8 archive remains a distinct historical backup. This archive is prepared for the user's private GitHub backup; no public redistribution approval is asserted.
'''
(out/'RESTORE-EDF-PORTABLE.md').write_text(restore,encoding='utf-8')
public=ROOT/'evidence/release/general-tree-portable-archive'/out.name;public.mkdir(parents=True)
for name in ('edf-portable-archive-manifest.json','RESTORE-EDF-PORTABLE.md'):shutil.copyfile(out/name,public/name)
shutil.copyfile(__file__,public/'executed-archive.py')
print(json.dumps({'directory':str(out),'public':str(public),'manifest':manifest}),flush=True)
