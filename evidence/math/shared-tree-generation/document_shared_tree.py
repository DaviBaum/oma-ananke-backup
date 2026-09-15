from pathlib import Path
import importlib,json,sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
def read(p):return json.loads((ROOT/p).read_text(encoding='utf-8'))
def write(p,d):
 q=ROOT/p;q.parent.mkdir(parents=True,exist_ok=True);q.write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8',newline='\n')
base='.oma/development/shared-tree-coupled/authored-fixtures/17edec43d93d43fe907462302e686b29/'
write('examples/shared-tree-three-sink-request.json',{'operation':'propose_network','budget_seconds':120,'idempotency_key':'synthetic-three-sink-generation','mission':{'schema':'oma.shared-tree-proposal-job/1','requirements':read(base+'requirements.json'),'search':read(base+'search.json'),'max_results':2}})

obligation='FINITE_SHARED_TREE_CATALOGUE_SYNTHESIS_AND_NATIVE_PROPOSAL_PROVENANCE'
producer=['oma.optimization.shared_tree_synthesis.compile_shared_tree_catalogue','oma.routing.shared_tree_proposals.build_connector_catalogue','oma.routing.shared_tree_proposals.compile_shared_tree_proposals','oma.routing.shared_tree_job.propose_shared_tree_run']
checker=['oma.optimization.shared_tree_synthesis.verify_shared_tree_catalogue','oma.routing.shared_tree_catalogue_check.verify_generated_catalogue']
probes=[]
for name in producer+checker:
 module,attr=name.rsplit('.',1);assert callable(getattr(importlib.import_module(module),attr));probes.append({'path':name,'callable':True})
testfiles=['tests/test_shared_tree_synthesis.py','tests/test_shared_tree_catalogue_check.py','tests/test_shared_tree_proposals.py','tests/test_shared_tree_job.py','tests/test_shared_tree_generated_workflow.py','tests/test_shared_tree_coupled_catalogue_check.py','tests/test_shared_tree_coupled_proposals.py','tests/test_shared_tree_coupled_workflow.py']
t=read('evidence/math/traceability_register.json');assert len(t['obligations'])==41
t['obligations'].insert(0,{'obligation':obligation,'source':{'document':'oma-integration','sha256':'72379f535f744b15ccbdcbbb6f68904f6c1177ace27a8fcc028229039b8bd129','paragraphs':[3787,3806,4472,4517,5254,5265,5526,5527,5528,5529],'objects':['ADD-SIR2.1','DEF-RTR39-45','THM-RTR50-53','ALG-RTR17','ALG-RTR18']},'interpretation_and_assumptions':'Two or three fixed labelled sinks, finite placed orthogonal equal-section tee instances and directed connector macros. Independent open-slot enumeration checks complete supplied-catalogue rooted incidence and exact rational-plus-pi nominal ranking. Independent geometry/fabrication/macro provenance precedes expansion to full physical alternatives. Coupled pressure generation uses exactly one site per persistent named tee/outlet loss identity and preserves the complete hydraulic requirements.','implementations':producer,'independent_checkers':checker,'callable_probe':probes,'automated_tests':testfiles,'real_model_benchmark':{'status':'GENERATED_FIXED_FLOW_OFFICE_AND_ANALYTIC_COUPLED_ACCEPTANCE_EXPORT_PASS','evidence':'evidence/math/shared-tree-native-independent/','office_evidence':'evidence/benchmarks/shared-tree-generation-office/','scope':'Office fixed-flow generation on earlier4b0 source: four native/service-checked alternatives, acceptance and fresh export. Final33a analytic coupled generation:11parts24ports22source55self,3deliveries25continuity27head identities; same-model local/global and fresh export pass; reverse regime remains unaccepted.'},'status':'IMPLEMENTED_SCOPED_UNIT_TESTED','amendments':['Bounded two/three-sink finite catalogue specialization, not completion of general original route skeleton algorithms.'],'certificate_and_limitations':'Finite nominal graph coverage only. Authored connector-language membership does not certify complete geometric template generation. No native cost bound, unrestricted topology optimum, continuous Steiner closure, physical infeasibility from empty catalogue, or acceptance authority from generation. Every actual candidate still requires fresh current native/service/admission checks. Fixed-ID unequal pressure scope excludes role/site remapping and other generated pressure profiles.','cache_invalidation':['source-state','geometry','envelope','net-obligations','catalog','rules','objective','scenarios','theory','checker','solver-version'],'documentation':'docs/shared-tree-generation.md','evidence':'evidence/math/shared-tree-generation/latest.json','full_source_algorithms_implemented':False})
assert not t['full_engine_mathematics_implemented'];write('evidence/math/traceability_register.json',t)
a=read('evidence/math/source_algorithm_capabilities.json')
before=dict(a['classification_counts'])
for x in a['algorithms']:
 if x['id'] not in ('ALG-RTR17','ALG-RTR18'):continue
 names=producer if x['id']=='ALG-RTR17' else checker
 x['bounded_related_callables']=list(dict.fromkeys(x['bounded_related_callables']+names))
 x['callable_probe']+= [p for p in probes if p['path'] in names]
 x['relied_on_obligations']=list(dict.fromkeys(x['relied_on_obligations']+[obligation]))
 x['automated_tests']=list(dict.fromkeys(x['automated_tests']+testfiles))
 x['actual_adapter_contract']='Generated two/three-sink finite shared-tree alternatives from terminal requirements, fixed tee instances and bounded directed fabrication macros; independently checked supplied-catalogue provenance and complete nominal graph rank, then separate native/service/accept/export. Fixed-ID unequal-outlet pressure requirements remain unchanged.'
 x['limitations_and_missing_requirements']='Complete all-template geometric generation, general multi-terminal topology pricing, continuous inner/outer graph completeness, 3D homotopy, topology-native branch-and-price and unrestricted fabrication/physics remain unimplemented. Nominal finite ranking is not physical global optimality. Other generated pressure profiles and multiple sites per persistent hydraulic tee role remain unsupported.'
 assert not x['full_algorithm_implemented']
assert a['classification_counts']==before and not a['all_source_algorithms_implemented'];write('evidence/math/source_algorithm_capabilities.json',a)
c=read('docs/capabilities.json')
for x in c['capabilities']:
 if x['id']=='oma_ananke_joint_optimization':
  x['evidence']+=['docs/shared-tree-generation.md','evidence/math/shared-tree-generation/latest.json',*testfiles]
  x['scope']+=' New bounded two/three-sink generation builds full physical alternatives from fixed tee sites and connector options, with independent catalogue provenance and complete finite nominal graph ranking. It preserves named unequal-outlet hydraulic requirements. Supervised proposal jobs bind source/project/request/software and leave project state unchanged. Native feasibility, all-port service, acceptance and fresh export remain mandatory downstream checks. Full original algorithms remain incomplete.'
 if x['id']=='engineering_analysis':
  x['evidence']+=['docs/shared-tree-generation.md','evidence/math/shared-tree-generation/latest.json']
  x['scope']='Exact rational/interval and independently checked linear port reductions, prescribed-flow service, one-tee pressure relations, grounded positive-K signed quadratic graph envelopes and residual/error bounds are implemented in stated scopes. Native common-tee and unequal-outlet directed pressure-tree adapters derive current component dimensions, loss equations and complete physical port inventories. Unequal trees require same-model local positive-box existence and global nonnegative univalence before exact delivery and all-port velocity checks. Missing, reversed or unresolved regimes remain UNKNOWN; new-model applicability remains explicit. Generated two/three-sink alternatives preserve all named hydraulic requirements and undergo the same native/service/accept/export pipeline. Full original source algorithms, general cyclic nonlinear native models, unrestricted tee role/site search, thermal/electrical systems and general physical applicability remain open. Exact current regression evidence is linked from the generated-tree checkpoint; historical receipts retain their distinct source identities.'
c['updated_at']='2026-09-15';write('docs/capabilities.json',c)
p=ROOT/'docs/math/source-capabilities.md';p.write_text(p.read_text(encoding='utf-8').replace('The 41 relied-on executable obligations','The 42 relied-on executable obligations'),encoding='utf-8',newline='\n')
for name in ['shared-tree-synthesis','shared-tree-catalogue-provenance','shared-tree-coupled-provenance']:
 p=ROOT/'docs/math'/f'{name}.md';s=p.read_text(encoding='utf-8')
 s=s.replace('The implementation is private; no production source or original mathematical document was changed.','The module is integrated into the generated-tree backend. Original mathematical documents remain unchanged; the retained component receipts below describe their earlier isolated validation.')
 s=s.replace('No production module or prior frozen checker was changed by this private implementation.','The original isolated implementation changed no production module or prior frozen checker. The final extension is now integrated; those earlier component receipts remain historical.')
 s=s.replace('Native generated coupled workflow validation is a separate parent-owned integration task.','The integrated generated coupled native workflow is documented in `docs/shared-tree-generation.md`, with separate complete regression and native evidence.')
 p.write_text(s,encoding='utf-8',newline='\n')
p=ROOT/'docs/shared-networks.md';s=p.read_text(encoding='utf-8');s=s.replace('The present family supports one source,','The backend also generates bounded two/three-sink alternatives from individual tee sites; see [generated shared-tree API](shared-tree-generation.md). Its nominal proof does not replace the physical checks below.\n\nThe present family supports one source,',1);p.write_text(s,encoding='utf-8',newline='\n')
print('42 bounded obligations; source classification counts unchanged; API example and documentation written')
