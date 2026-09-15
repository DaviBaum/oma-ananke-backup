"""Create a separately indexed guide from published docs after package completion."""
import hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
STAGE=Path(__file__).resolve().parent
HANDOFF=ROOT/'evidence/release/factorized-tree-portable-completed-ddbee4976390/handoff.json'
OUT=STAGE/'f73-checkpoint-documentation'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
h=read(HANDOFF);assert h['status']=='F73_NATIVE_PORTABLE_SEALED_AND_INDEPENDENTLY_AUDITED'
assert h['bundled_passed']==3272 and h['declared_direct_interpreter_na']==3
OUT.mkdir(exist_ok=False);captured={}
for folder,expected_manifest in (
    ('documentation-source-633a6cdb','1f4c17c4d2e6020859badffe95c0ff301f96398b620e4cba349d0800462a44ee'),
    ('documentation-registers-633a6cdb','aef87a5a9a8febf30936a8e0c3a5ebfcdf6586334d894cd0b87061c5b4539168')):
    source=STAGE/folder;raw_manifest=(source/'source-manifest.json').read_bytes()
    assert hashlib.sha256(raw_manifest).hexdigest()==expected_manifest
    manifest=json.loads(raw_manifest.decode('utf-8-sig'))
    assert manifest['git_commit']=='633a6cdbcd75a24b0146f4d8228edef1bc0c4046'
    assert set(manifest['files']).isdisjoint(captured)
    for name,row in manifest['files'].items():
        p=source/name;data=p.read_bytes()
        assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256']
        assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==row['git_blob']
        target=OUT/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        assert sha(target)==row['sha256'];captured[name]=row
    (OUT/(folder+'-manifest.json')).write_bytes(raw_manifest)
assert len(captured)==73
text=f'''# f73 checkpoint guide

Read this companion for the current compact/factorized backend and its API examples. The sealed package's `docs` directory is the historical EDF documentation captured before f73 documentation promotion. It is preserved exactly as tested. This companion is separately indexed; it changes no executable, test result, UI asset, Store, or package seal.

Start with [the shared-tree API guide](docs/shared-tree-generation.md), then the complete [five-sink](examples/shared-tree-5-sink-compact-request.json) and [eight-sink](examples/shared-tree-8-sink-compact-request.json) requests. Those coordinates and physical assumptions describe analytic fixtures. Supply a building project's own justified terminals, zones, fittings and boundary data; these examples do not certify a building mission.

The [compact top-K contract](docs/math/shared-tree-topk.md) describes exact finite-catalogue counts/ranking. The [factorized pressure contract](docs/math/factorized-tree-pressure.md) describes the strengthened bounded local proof. Each physical candidate still requires current native geometry, metrics, same-model local/global pressure verification, delivery and velocity checks, acceptance, and fresh export verification. The original mathematics and whole-building routing are not complete; retained Hospital attempts remain unresolved.

## Validated package

- Source checkpoint: `{h['source_checkpoint']}`; 114 application files.
- Bundled checker: `{h['checker_version']}`; standalone Python 3.12.14.
- Original and custom native suites: 3,275 passed each, zero failures/skips.
- Exact same 305-input bundled suite: 3,272 passed and three named direct-interpreter bridge cases not applicable. Those three passed in the two other environments.
- Offline import/collision/route/accept/export workflow, both Python network-denial modes, and three saved Office IFC rechecks passed. The Office records retain B2 fitting use, two-sink pressure and unequal three-sink pressure scopes separately.
- Package index: `{h['artifact_index_sha256']}`. The separately retained seven/eight-sink native fixtures and all new 4–8-sink regression cases do not establish Hospital or unrestricted building success.

Default generation remains FULL_LEDGER with 2,000,000 work units. Compact generation is explicit; the eight-sink example uses the bounded 48,000,000 work/32 MiB policy. Exhaustion is not a proof of feasibility, impossibility or optimality. Pressure, loss and native bore assumptions remain declared modeling assumptions.

## Launch and restore

1. Check the release ZIP SHA256 in its archive manifest, then extract into a new directory. Keep earlier packages separate.
2. Open the extracted package folder and run `OMA.cmd`, or `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\Start-OMA.ps1`. This package launcher defaults to port **8765**, so its default URL is **http://127.0.0.1:8765**. `Start-OMA.ps1 -Port <port>` explicitly selects another port; follow that invocation's actual URL.
3. The separately owned validated workspace service used **8768** at this handoff. That service and its Store are distinct from the extracted package; do not assume its URL opens the new copy.
4. Data is a separate backup. Preserve the original Store/source archives and follow their backup/restore instructions to restore into a new location. This runtime ZIP contains no Hospital/IFC-Bench source dataset and does not replace the data backup.

All documentation/example bytes below come from published commit `633a6cdbcd75a24b0146f4d8228edef1bc0c4046`; the guide above adds actual final package counts and restoration details. `docs/PROGRESS.md` is captured workspace history and may describe packaging as pending at its earlier capture; use this CHECKPOINT.md and the final package receipts for completion status. Links from copied contracts to external evidence refer to the separately retained repository/backup evidence, not additional files implicitly certified by this companion. Use the [immutable documentation/source commit](https://github.com/DaviBaum/oma-ananke-backup/tree/633a6cdbcd75a24b0146f4d8228edef1bc0c4046) and its [mathematical evidence directory](https://github.com/DaviBaum/oma-ananke-backup/tree/633a6cdbcd75a24b0146f4d8228edef1bc0c4046/evidence/math) for those references; access requires permission to the private backup repository.
'''
(OUT/'CHECKPOINT.md').write_text(text,encoding='utf-8')
shutil.copyfile(__file__,OUT/'documentation-completion.py')
files={p.relative_to(OUT).as_posix():{'sha256':sha(p),'bytes':p.stat().st_size} for p in OUT.rglob('*') if p.is_file()}
manifest={'status':'SEPARATE_CURRENT_F73_DOCUMENTATION_COMPANION','source_checkpoint':h['source_checkpoint'],
    'git_commit':'633a6cdbcd75a24b0146f4d8228edef1bc0c4046','completed_package_handoff_sha256':sha(HANDOFF),
    'package_artifact_index_sha256':h['artifact_index_sha256'],'files':files,'file_count':len(files),
    'exclusions':['documentation-files.json itself'],'package_payload_modified':False,
    'scope':'Documentation-only companion with final checkpoint guide. Existing package/docs remains its exact captured historical documentation.'}
(OUT/'documentation-files.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
public=ROOT/'evidence/release/factorized-tree-documentation-companion-ddbee4976390';shutil.copytree(OUT,public)
print(json.dumps({'directory':str(OUT),'public':str(public),'index_sha256':sha(OUT/'documentation-files.json'),'files':len(files)}))
