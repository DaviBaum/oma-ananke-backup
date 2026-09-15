"""Finalize only after both frozen suites, current supplements and live upgrade pass."""
import hashlib,json,subprocess,urllib.request
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SOURCE='33a20d125bba02a298d12048a5b6227e51a98d8a043b999097d94a8d88b67b95'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,value):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8',newline='\n')
def pointer(p):return {'path':Path(p).relative_to(ROOT).as_posix(),'sha256':sha(p)}

original=ROOT/'.oma/development/shared-tree-combined-validation/validation/0f2100ee9fce4b88960ca0cc19bc509b/result.json'
o=read(original);assert o['status']=='PASS' and o['passed']==2788 and o['failures']==o['skipped']==0
public_original=ROOT/'evidence/math/shared-tree-generation-validation/handoff.json';assert public_original.exists()
custom=ROOT/'evidence/dependencies/native-build/checkpoint-validation/33a20d125bba-ffe49e5e40d0/result.json'
c=read(custom);assert c['status']=='CUSTOM_NATIVE_NEW_CHECKPOINT_FULL_SUITE_PASS' and c['passed']==2788 and c['failed']==c['skipped']==0
supp=[]
for p in (ROOT/'evidence/release/shared-tree-package-supplement').glob('*/result.json'):
 r=read(p)
 if r.get('passed') in (75,121,196) and r.get('status') in ('PASS','EXACT_196_CURRENT_PACKAGE_SUPPLEMENT_PASS'):
  assert r.get('failures',r.get('failed',0))==0 and r.get('skipped')==0
  supp.append((p,r))
assert sorted(r['passed'] for _,r in supp)==[75,121,196]
service=read(ROOT/'.oma/service.validated.json')
assert service['executable_build']=='oma-independent-checker/2:'+SOURCE
live=Path(service['validation_receipt']);assert sha(live)==service['validation_receipt_sha256']
with urllib.request.urlopen('http://127.0.0.1:8768/api/health',timeout=10) as response:health=json.load(response)
assert health['status']=='ok',health.get('status')
identity=health['server_identity']
assert identity['checker_version']=='oma-independent-checker/2:'+SOURCE
assert identity.get('source_changed') is False and identity.get('startup_environment_matches') is True
master=read(ROOT/'.oma/development/shared-tree-combined-validation/frozen-inputs.json')
actual={'oma/'+p.relative_to(ROOT/'src/oma').as_posix():sha(p) for p in (ROOT/'src/oma').rglob('*.py')}
assert actual==master['source_files'] and len(actual)==112
reconcile=ROOT/'evidence/math/shared-tree-generation/current-inventory-reconciliation.json';assert read(reconcile)['unique_current_cases']==2909

latest={'schema':'oma.generated-shared-tree-integrated-checkpoint/1','status':'VALIDATED_RUNNABLE_CHECKPOINT','completed_at':datetime.now(timezone.utc).isoformat(),'source_checkpoint':SOURCE,'application_source_files':112,'current_unique_cases_per_native_environment':2909,'frozen_backend_full_cases':2788,'additional_package_cases':121,'overlapping_current_input_cases_repeated':75,'original_full_public_handoff':pointer(public_original),'original_full_receipt_sha256':sha(original),'custom_full':pointer(custom),'supplements':[pointer(p) for p,_ in supp],'inventory_reconciliation':pointer(reconcile),'native_independent_handoff':pointer(ROOT/'evidence/math/shared-tree-native-independent/handoff.json'),'office_handoff':pointer(ROOT/'evidence/benchmarks/shared-tree-generation-office/handoff.json'),'live_update':pointer(live),'local_url':'http://127.0.0.1:8768','sealed_portable_source':'5e8fe9659cfde60f84f5cf93f38a1959428b3e7522de741e905d1f505db2b73c','bounded_executable_obligations':42,'full_original_math_implemented':False,'full_production_ready':False,'physical_global_optimality':False,'current_generation_scope':'Two/three-sink finite tee/connector catalogues; exact nominal graph rank and independently checked catalogue provenance; separate current native/service/admission/accept/export; fixed-ID unequal-outlet pressure profile','ui_refinement_paused':True}
write(ROOT/'evidence/math/shared-tree-generation/latest.json',latest)
write(ROOT/'evidence/math/shared-tree-generation/final-health.json',health)
(ROOT/'evidence/math/shared-tree-generation/finalize_shared_tree_checkpoint.py').write_bytes(Path(__file__).read_bytes())
(ROOT/'evidence/math/shared-tree-generation/document_shared_tree.py').write_bytes((ROOT/'.oma/development/document_shared_tree.py').read_bytes())
old=ROOT/'docs/PROGRESS.md';archive=ROOT/'docs/checkpoints/2026-09-15-before-generated-tree.md'
archive.parent.mkdir(exist_ok=True)
if not archive.exists():archive.write_bytes(old.read_bytes())
progress=f'''# Current backend checkpoint

Updated 2026-09-15. The final-reset work is complete as a validated, runnable checkpoint. **Full original mathematics and full production readiness remain incomplete.** The user's requested rough estimate was about45%; that is a judgment, not a measured completion metric.

The current backend is running at **http://127.0.0.1:8768** on source `{SOURCE}`. All112 application files match the frozen validated runtime. Existing project data and the six compiled interface assets are preserved. UI refinement remains paused.

## Delivered in this checkpoint

- Generate complete two/three-sink branching alternatives from fixed terminal requirements, individual placed tees and bounded directed connector options. Shared trunks and fittings are counted once.
- Independently verify connector/fabrication provenance and the complete supplied finite graph assignment ledger, using exact rational-plus-pi nominal ranking.
- Preserve named unequal-outlet pressure boundaries through generation, including every loss coefficient, minimum delivery, velocity limit and proof proposal box. Actual candidates still require fresh native geometry, same-model local/global operating proofs and all-port service.
- Run generation through the supervised `propose_network` job, with immutable source/project/request/software bindings and cancellation/deadline handling. Feed its returned mission into the existing `optimize` workflow, acceptance and IFC export.

Use the [API workflow and complete synthetic example](../shared-tree-generation.md). The generation API is implemented; an additional workbench authoring screen was not added during the mathematics/backend priority.

## Completed validation

Both original and separately built native environments cover **2,909 unique current tests**, with no failures or skips: the frozen2,788-case backend suite plus121 additional packaging cases. Another75 overlapping cases were rerun against the current admission-test and package-helper bytes. The exact union, input snapshots and369 application/test/script byte identities are accounted separately. The360 focused backend suite also passes.

The generated unequal-pressure analytic workflow selects and accepts a tree at revision2, then passes fresh exported-IFC rechecking:11 components,24 ports,22 source pairs,55 component pairs,3 deliveries,25 continuity identities and27 head identities. Independent replay passes with producer routines disabled. Reversed-pressure and collision cases remain unaccepted. An earlier inconclusive proof attempt is retained; widening only the computational flow proposal box allowed certification of the unchanged physical pressure/loss/delivery requirements.

The separately identified real Office campaign generated and checked four fixed-flow alternatives, selected and accepted one, then passed a fresh export check. Its selected tree has4 components,9 ports,3,212 source pairs and6 component pairs. All62,930 parsed original IFC entities are preserved. This historical Office case used source4b0; the final33a coupled case is an analytic fixture. No comparison across different missions or unrestricted physical optimum is claimed.

Authoritative [checkpoint receipt](../../evidence/math/shared-tree-generation/latest.json), [full-suite handoff](../../evidence/math/shared-tree-generation-validation/handoff.json), [independent native evidence](../../evidence/math/shared-tree-native-independent/handoff.json), and [Office evidence](../../evidence/benchmarks/shared-tree-generation-office/handoff.json).

## Runnable and portable states

The latest112-file backend runs from a frozen source copy on port8768 using the existing original native environment. The separately sealed portable package remains `.release/native-build/portable-candidates/5e8fe9659cfd-82d3a00a6ff4/`; it includes the validated unequal-pressure backend but predates generated-tree synthesis. Its `OMA.cmd` and `Start-OMA.ps1` launch that sealed version. See [portable candidate details](../native-portable-candidate.md). A new bundled-interpreter package containing33a has not been built or certified.

## Remaining work

The register now contains42 explicitly bounded executable obligations. The original algorithm index retains its partial/unimplemented classifications and all full-completion flags remain false. Remaining major areas are unrestricted multi-terminal topology/placement search, complete continuous geometry and homotopy/fabrication coverage, topology-native branch-and-price, broader nonlinear/thermal/electrical physical models, full architectural rewrite/Benders closure, complete corpus validation and final distribution gates. Original P7 and initial P26 source-body gaps remain documented.

Nominal finite graph ranking is not a native numerical objective bound or global physical optimum. Supported pressure models remain conditional on their declared ideal-bore, loss and boundary assumptions. Missing inputs, unsupported geometry/regimes and exhausted proof budgets remain explicit UNKNOWN or unsupported states.

The next engineering step is to extend a single declared scope from these tested contracts, with independent evidence, then package that new checkpoint. No feature expansion remains running from this final-reset pass. The full requested directive is preserved in [PRODUCTION_DIRECTIVE.md](../PRODUCTION_DIRECTIVE.md); the [capability register](../capabilities.json) and [source algorithm coverage](../math/source-capabilities.md) state the remaining boundaries. Earlier chronological work is retained in [checkpoint history](checkpoints/2026-09-15-before-generated-tree.md).
'''
# PROGRESS lives directly under docs, so links are relative to that location.
progress=progress.replace('(../shared-tree-generation.md)','(shared-tree-generation.md)').replace('(../../evidence/','(../evidence/').replace('(../native-portable-candidate.md)','(native-portable-candidate.md)').replace('(../PRODUCTION_DIRECTIVE.md)','(PRODUCTION_DIRECTIVE.md)').replace('(../capabilities.json)','(capabilities.json)').replace('(../math/source-capabilities.md)','(math/source-capabilities.md)')
for before,after in [('about45%','about 45%'),('All112','All 112'),('frozen2,788','frozen 2,788'),('plus121','plus 121'),('Another75','Another 75'),('and369','and 369'),('The360','The 360'),('revision2','revision 2'),('check:11','check: 11'),(',24 ports',', 24 ports'),(',22 source',', 22 source'),(',55 component',', 55 component'),(',3 deliveries',', 3 deliveries'),(',25 continuity',', 25 continuity'),('and27 head','and 27 head'),('has4 components','has 4 components'),(',9 ports',', 9 ports'),(',3,212 source',', 3,212 source'),('and6 component','and 6 component'),('All62,930','All 62,930'),('source4b0','source 4b0'),('final33a','final 33a'),('latest112-file','latest 112-file'),('port8768','port 8768'),('containing33a','containing 33a'),('contains42','contains 42')]:
 progress=progress.replace(before,after)
old.write_text(progress,encoding='utf-8',newline='\n')
p=ROOT/'docs/native-portable-candidate.md';s=p.read_text(encoding='utf-8');start='The same validated application source is running at `http://127.0.0.1:8768` against the existing local Store.'
s=s.replace(start,'The latest generated-tree backend is now running at `http://127.0.0.1:8768` against the existing local Store; see [current checkpoint](PROGRESS.md). This sealed package remains the earlier5e8 source.')
s=s.replace('The new generated-tree work remains a later development checkpoint and is not included in this package.','The validated33a generated-tree checkpoint is not included in this older sealed package.')
p.write_text(s,encoding='utf-8',newline='\n')
caps_path=ROOT/'docs/capabilities.json';caps=read(caps_path)
for entry in caps['capabilities']:
 if entry['id'] in ('oma_ananke_joint_optimization','engineering_analysis'):
  entry['evidence']=list(dict.fromkeys(entry['evidence']+['evidence/math/shared-tree-generation/latest.json']))
  entry['scope']+=' Current generated-tree source33a covers2,909 unique tests in both native environments, via the frozen2,788-case full suite and current packaging/admission supplements. Full source/production flags remain false.'
 if entry['id']=='offline_installation_packaging':
  entry['scope']=entry['scope'].replace('The same5e8 source is live on8768 against unchanged Store/source inventories. Later generated-tree development is not included.','The newer validated33a generated-tree backend is live on8768 against unchanged Store/source inventories. It is not included in this older sealed5e8 package.')
  entry['evidence']=list(dict.fromkeys(entry['evidence']+[live.relative_to(ROOT).as_posix(),'evidence/math/shared-tree-generation/latest.json']))
write(caps_path,caps)
print(json.dumps({'status':'FINAL_CHECKPOINT_READY','source':SOURCE,'unique_cases_each_runtime':2909,'live_receipt':str(live),'supplements':[r['passed'] for _,r in supp]},indent=2))
