"""Finalize current recovery documentation only after verified publication."""
from pathlib import Path
import hashlib,json,shutil,sys,uuid
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').is_file())
PACKAGE=ROOT/'evidence/release/factorized-tree-portable-completed-ddbee4976390/handoff.json'
RELEASE=Path(sys.argv[1]).resolve();assert RELEASE.is_relative_to(ROOT)
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def link(p):return '../'+Path(p).relative_to(ROOT).as_posix()
h=read(PACKAGE);r=read(RELEASE)
assert h['status']=='F73_NATIVE_PORTABLE_SEALED_AND_INDEPENDENTLY_AUDITED'
assert r['status']=='PRIVATE_COMPACT_PORTABLE_RELEASE_PUBLISHED_AND_VERIFIED'
assert h['source_checkpoint']==r['source_checkpoint']=='f73a8793ae0df76d9ec53400cec18b05d2731f63c735b225c2246fee62df6b21'
assert h['bundled_passed']==3272 and h['declared_direct_interpreter_na']==3
manifest=read(RELEASE.parent/'f73-portable-archive-manifest.json')
assert manifest['completed_handoff_sha256']==sha(PACKAGE)
archive_name=Path(manifest['archive']).name;asset=r['assets'][archive_name]
assert asset=={'sha256':manifest['archive_sha256'],'bytes':manifest['archive_bytes']}
out=ROOT/'evidence/release/compact-final-documentation'/uuid.uuid4().hex;out.mkdir(parents=True)
names=['docs/PROGRESS.md','docs/GITHUB_BACKUP.md','docs/native-portable-candidate.md','docs/capabilities.json','docs/math/required-engine-priorities.md']
for name in names:
    target=out/'before'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
url=r['url'];total=f"{r['total_bytes']:,}";size=f"{asset['bytes']:,}"
history=ROOT/'docs/checkpoint-portable-5e8.md';assert not history.exists()
history.write_text('# Historical 5e8 portable checkpoint\n\nSee [the current portable guide](native-portable-candidate.md) for the latest release.\n\n'+(ROOT/'docs/native-portable-candidate.md').read_text(encoding='utf-8'),encoding='utf-8')
portable=f'''# Validated compact topology and pressure portable checkpoint

Download the [private f73 portable release]({url}), verify the ZIP hash in its archive manifest, and extract into a new directory. Read `f73-checkpoint-documentation/CHECKPOINT.md` first. Then run `OMA.cmd` inside `f73a8793ae0d-ddbee4976390`. The package defaults to **http://127.0.0.1:8765**; `Start-OMA.ps1 -Port <port>` selects another port. The separately running workspace service at port 8768 is a different instance.

The three release assets total **{total} bytes**. The ZIP contains the sealed application package and a separately indexed current documentation companion. Its SHA-256 is `{asset['sha256']}`. The package's original documentation remains its historical capture; the companion supplies the current generation API, complete five/eight-terminal examples and mathematical contracts without changing the tested payload.

The sealed package contains **{h['file_count']:,} indexed files and {h['logical_bytes']:,} logical bytes**, with index SHA-256 `{h['artifact_index_sha256']}`. Its 114 application files have source identity `{h['source_checkpoint']}`.

| Runtime | Checker identity | Completed exact validation |
|---|---|---|
| Original Python/native environment | `f73a8793ae0d` | 3,275 passed; zero failures/skips |
| Separately built native environment | `a4aa129a2d19` | 3,275 passed; zero failures/skips |
| Bundled Python 3.12.14 | `3492e0f42f80` | 3,272 passed; three named direct-interpreter bridge cases not applicable |

All three executions retain the same 305 test/support inputs and 3,275 exact case identities. The three bridge cases passed in both other environments. The custom native extension has SHA-256 `{h['native_extension_sha256']}`.

Generated four-through-eight-terminal analytic fixtures complete native checking, acceptance and fresh export. The bundled runtime also freshly checks three saved Office export roles: the two-route fitting-budget case (4,818 source pairs and five cross-route pairs), two-outlet pressure network (3,212 source pairs, six component pairs, nine ports), and unequal-outlet pressure tree (5,621 source pairs, 21 component pairs, 16 ports). Independent replay checks their bound model, source, native report and service evidence. These remain distinct declared engineering models.

The offline import/check/accept/export workflow and both Python network-denial probes pass. The latter are Python audit-hook checks, not an operating-system firewall. The six compiled interface assets remain unchanged.

Evidence: [completed package]({link(PACKAGE)}), [verified upload]({link(RELEASE)}), [current backend](PROGRESS.md), and [backup/restore instructions](GITHUB_BACKUP.md). Original mathematics, unrestricted physical routing, whole-hospital verification and full production readiness remain incomplete. Earlier [EDF recovery](https://github.com/DaviBaum/oma-ananke-backup/releases/tag/validated-general-tree-2026-09-15) and [5e8 checkpoint](checkpoint-portable-5e8.md) remain separate immutable versions.
'''
(ROOT/'docs/native-portable-candidate.md').write_text(portable,encoding='utf-8')
p=(ROOT/'docs/PROGRESS.md').read_text(encoding='utf-8')
start=p.index('The live f73 runtime and the published EDF portable archive are different checkpoints.')
end=p.index('\n\nHospital remains unresolved.',start)
p=p[:start]+f'The [f73 portable release]({url}) is sealed, published and remotely hash-verified. Its bundled runtime passes 3,272 tests plus three named direct-interpreter bridge cases that do not apply; those cases pass in both other native environments. All three saved Office export roles pass fresh bundled checks. The ZIP includes a separately indexed current API/math documentation companion. Read the [portable guide](native-portable-candidate.md) and [backup/restore instructions](GITHUB_BACKUP.md). Earlier EDF and 5e8 packages remain separate recovery checkpoints.'+p[end:]
(ROOT/'docs/PROGRESS.md').write_text(p,encoding='utf-8')
p=(ROOT/'docs/GITHUB_BACKUP.md').read_text(encoding='utf-8');assert '## Compact topology and pressure portable checkpoint' not in p
p=p.replace('# GitHub backup and recovery\n','# GitHub backup and recovery\n\nLatest runnable backend: [f73 compact topology and pressure portable checkpoint]('+url+'). Read the [current portable guide](native-portable-candidate.md) for download, verification and launch instructions. The initial recovery release below supplies the separate original data backup.\n',1)
p=p.replace('The sealed portable package contains source5e8. The generated-tree backend at this backup\'s initial Git checkpoint contains source33a.','The initial recovery release\'s sealed portable package contains source5e8. The generated-tree backend at that backup\'s initial Git checkpoint contains source33a.')
p+=f'''\n\n## Compact topology and pressure portable checkpoint

The newest [validated-compact-pressure-2026-09-15 prerelease]({url}) contains the f73 portable ZIP, manifest and restore instructions: three assets totaling {total} bytes. All remote asset sizes and SHA-256 values match. ZIP SHA-256: `{asset['sha256']}`. The [completed upload receipt]({link(RELEASE)}) and [package handoff]({link(PACKAGE)}) bind the exact files and validation.

Extract to a new directory. The ZIP contains the sealed `f73a8793ae0d-ddbee4976390` application folder and the separate `f73-checkpoint-documentation` companion. Read the companion's `CHECKPOINT.md`, then launch `OMA.cmd` inside the application folder. Use its configured port (8765 by default); the existing workspace service on 8768 is separate. Runtime data, original mathematics and hospital inputs remain in the initial recovery release; this ZIP does not replace that data backup. See [current portable details](native-portable-candidate.md).
'''
(ROOT/'docs/GITHUB_BACKUP.md').write_text(p,encoding='utf-8')
c=read(ROOT/'docs/capabilities.json');row=next(x for x in c['capabilities'] if x['id']=='offline_installation_packaging')
row['scope']=f'The 114-file f73 backend is live after a guarded upgrade preserving all Store tables/artifacts and UI bytes. Both original/custom native environments pass all 3,275 exact cases. The separate bundled Python 3.12.14 runtime passes 3,272 plus three named direct-interpreter bridge cases that pass in the other environments. Its three saved Office export roles, offline workflow, source/input/native identities and final sealed file index pass independent checks. The private f73 release is published with all three remote asset digests/sizes verified ({total} bytes). A separately indexed current documentation companion accompanies the unchanged sealed package. EDF and older 5e8 releases and original data backups remain distinct. Full original mathematics, unrestricted engineering models and production readiness remain incomplete.'
for path in (PACKAGE,RELEASE):
    relative=path.relative_to(ROOT).as_posix()
    if relative not in row['evidence']:row['evidence'].append(relative)
(ROOT/'docs/capabilities.json').write_text(json.dumps(c,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
p=(ROOT/'docs/math/required-engine-priorities.md').read_text(encoding='utf-8')
assert '46 RTR body identities now have 26 explicit component links' in p
assert 'contains 41 relied-on executable obligations' in p
p=p.replace('46 RTR body identities now have 26 explicit component links','46 RTR body identities now have 27 explicit component links')
p=p.replace('contains 41 relied-on executable obligations','contains 42 relied-on executable obligations')
old='The latest integrates the explicit unequal-outlet native adapter with independent full dimensional/path reconstruction, conservative outward model bounds, mandatory local/global operating proofs, all-port service and fresh accepted IFC export. The preceding addition is a separately proved global univalence specialization'
assert old in p
p=p.replace(old,'The f73 checkpoint adds independently checked compact finite top-K synthesis and factorized pressure bounds that preserve named coefficient dependencies. Generated four-through-eight-sink analytic fixtures complete native service checks, acceptance and fresh export; the bounded catalogue and pressure contracts do not establish unrestricted routing or physical-model completeness. Earlier work integrates the explicit unequal-outlet native adapter with independent full dimensional/path reconstruction, conservative outward model bounds, mandatory local/global operating proofs, all-port service and fresh accepted IFC export. A separate addition is the proved global univalence specialization')
(ROOT/'docs/math/required-engine-priorities.md').write_text(p,encoding='utf-8')
shutil.copyfile(__file__,out/'executed-finalization.py')
receipt={'status':'FINAL_COMPACT_RELEASE_DOCUMENTATION_COMPLETE','source_checkpoint':h['source_checkpoint'],
    'package_handoff_sha256':sha(PACKAGE),'release_handoff_sha256':sha(RELEASE),'release_url':url,
    'changed_files':{name:sha(ROOT/name) for name in names+[history.relative_to(ROOT).as_posix()]},
    'runtime_source_or_inputs_changed':False,'full_original_math_complete':False,'whole_hospital_verified':False,
    'retained_files':{p.relative_to(out).as_posix():sha(p) for p in out.rglob('*') if p.is_file()}}
(out/'handoff.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':receipt['status'],'directory':str(out),'handoff_sha256':sha(out/'handoff.json')}))
