from pathlib import Path
import hashlib,json,shutil,sys
P=Path(__file__).resolve().parent;ROOT=next(p for p in P.parents if (p/'AGENTS.md').is_file())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
out=ROOT/'evidence/math/general-tree-generation';out.mkdir(exist_ok=True)
promotion=ROOT/'.oma/development/general-tree-promotion/attempts/8343a5e3d9b5412995cece445e493557'
shutil.copytree(promotion,out/'promotion',dirs_exist_ok=True)
live=ROOT/'evidence/release/validated-backend-general-tree-update/e3c3bea38c864d18b46730de92a92187'
receipts=[live/'handoff.json',ROOT/'evidence/release/general-tree-original-full-a29404ec828e/handoff.json',
          ROOT/'evidence/release/general-tree-custom-completed-4c1eddeca46f/handoff.json',
          ROOT/'evidence/math/general-shared-tree-native-independent/5d1d8b19c2a9426087f1d3dbae844fc2/completed-handoff.json']
source={p.relative_to(ROOT/'src').as_posix():sha(p) for p in (ROOT/'src').rglob('*.py')}
expected=read(ROOT/'evidence/release/general-tree-original-full-a29404ec828e/source.json');assert source==expected
record={'schema':'oma.general-tree-generation-checkpoint/1','status':'VALIDATED_LIVE_BACKEND','source_checkpoint':'edf555760245581599c33a06d99e1010f88f684a5c323ae00e3370f31f73448c',
    'original_and_custom_unique_tests':3012,'original_app_files':112,'frozen_test_support_inputs':264,
    'current_driver_overlapping_tests':121,'generated_domain':'TWO_THROUGH_EIGHT_FIXED_SINKS_FINITE_FULL_LEDGER_WITH_EXPLICIT_BUDGETS',
    'native_positive_fixture_sinks':4,'full_original_math_complete':False,'production_ready':False,
    'source_files':source,'receipts':{p.relative_to(ROOT).as_posix():sha(p) for p in receipts},
    'native_four':{'components':14,'ports':31,'source_pairs':28,'unique_self_pairs':91,'deliveries':4,'continuity':32,'head_paths':35,'fresh_export':'PASS'},
    'next_private_extensions':['COMPACT_TOP_K_GROUPED_TRAVERSAL','FACTORIZED_POSITIVE_BOX_PROOF'],
    'hospital_release':'NONE_ALIGNMENT_UNRESOLVED_AND_SEPARATE_ARC_TIMEOUT'}
write(out/'latest.json',record);shutil.copyfile(__file__,out/'executed-checkpoint.py')
p=ROOT/'evidence/math/traceability_register.json';register=read(p);o=register['obligations'][0]
assert o['obligation']=='FINITE_SHARED_TREE_CATALOGUE_SYNTHESIS_AND_NATIVE_PROPOSAL_PROVENANCE'
o['interpretation_and_assumptions']=o['interpretation_and_assumptions'].replace('Two or three fixed labelled sinks','Two through eight fixed labelled sinks')
for t in ('tests/test_general_shared_tree_synthesis.py','tests/test_general_tree_native.py'):
    if t not in o['automated_tests']:o['automated_tests'].append(t)
o['amendments'].append('EDF checkpoint extends exact finite full-ledger synthesis to four through eight sinks. Both complete native environments pass3012 tests; four-sink native geometry, local/global operating proof, service, acceptance and fresh export independently replay. Dense larger catalogues may exhaust explicit budgets. Compact/factorized extensions are not yet in this checkpoint.')
o['current_checkpoint']='evidence/math/general-tree-generation/latest.json'
write(p,register)
p=ROOT/'docs/capabilities.json';cap=read(p)
for row in cap['capabilities']:
    if 'New bounded two/three-sink generation' in row.get('scope',''):
        row['scope']=row['scope'].replace('New bounded two/three-sink generation','Bounded two-through-eight-sink generation')
        start=row['scope'].index('Current generated-tree source33a')
        row['scope']=row['scope'][:start]+'Current EDF backend passes3012 tests in both native environments and an additional121 overlapping current package-driver tests. Generated four-sink native service/acceptance/fresh export is independently replayed. Dense larger finite catalogues can exhaust the full-ledger budget. Full source/production flags remain false.'
        row['evidence'].extend(['evidence/math/general-tree-generation/latest.json','docs/math/general-shared-tree-synthesis.md'])
write(p,cap)
print(json.dumps({'status':'CHECKPOINT_AND_SCOPED_REGISTERS_UPDATED','source_files':len(source),'tests':3012}))
