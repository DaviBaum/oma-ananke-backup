"""Retain the enclosing dataset notices separately from immutable hospital ZIP."""
import hashlib,json,subprocess,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
DEST=ROOT/'.release/github-backup/1a202fcf467a47368a4b3abc1167eb94'
OUT=ROOT/'evidence/release/github-backup/1a202fcf467a47368a4b3abc1167eb94'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def gh(*args):return subprocess.check_output(['gh',*args],cwd=ROOT,text=True)
names=['LICENSE','README.md']
assert json.loads(gh('repo','view','DaviBaum/oma-ananke-backup','--json','isPrivate'))['isPrivate']
files={name:sha(ROOT/'data/ifc-bench'/name) for name in names}
manifest={'source':'Original enclosing IFC-Bench dataset files','files':files,
    'scope':'Dataset documentation/model-card notices; hospital IFCs retain the project-specific license already included in hospital-original-models ZIP',
    'hospital_archive_sha256':'e71714dd825c6b906d7294cfc8bcb4b0f4dfd619d4cad8eb5e6ecd3808219f04'}
path=DEST/'original-dataset-provenance.zip'
with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED) as z:
    for name in names:z.write(ROOT/'data/ifc-bench'/name,'ifc-bench-original-notices/'+name)
    z.writestr('ifc-bench-original-notices/manifest.json',json.dumps(manifest,indent=2))
with zipfile.ZipFile(path) as z:
    assert set(z.namelist())=={'ifc-bench-original-notices/'+name for name in names}|{'ifc-bench-original-notices/manifest.json'}
    for name,value in files.items():assert hashlib.sha256(z.read('ifc-bench-original-notices/'+name)).hexdigest()==value==sha(ROOT/'data/ifc-bench'/name)
digest=sha(path)
gh('release','upload','backup-2026-09-15',str(path),'--repo','DaviBaum/oma-ananke-backup')
release=json.loads(gh('api','repos/DaviBaum/oma-ananke-backup/releases/tags/backup-2026-09-15'))
asset,=[a for a in release['assets'] if a['name']==path.name]
assert asset['digest']=='sha256:'+digest and asset['size']==path.stat().st_size
result={'status':'ADDITIONAL_DATASET_NOTICES_UPLOADED_AND_VERIFIED','manifest':manifest,'asset':asset,'local_sha256':digest,'script_sha256':sha(__file__)}
(OUT/'dataset-provenance-upload.json').write_text(json.dumps(result,indent=2))
(OUT/'executed-dataset-provenance.py').write_bytes(Path(__file__).read_bytes())
print(json.dumps({'status':result['status'],'bytes':asset['size'],'sha256':digest}))
