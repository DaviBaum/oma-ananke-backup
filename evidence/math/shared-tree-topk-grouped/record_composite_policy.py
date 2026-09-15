"""Read-only accounting recommendation; does not execute a native proposal job."""
from pathlib import Path
import hashlib,json

stage=Path(__file__).resolve().parent
probe=stage.parent/'general-shared-tree-native/catalogue-probes/b66610f8c6b54966aa8cf2b7a9bf8d1e/8'
bench=stage/'evidence/final-authored/51bf73e7ebec4ff4984a33cbada14369'
adapter=stage.parent/'shared-tree-topk-native/src/oma/routing/shared_tree_proposals.py'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def snapshot_count(value):
    todo=[value];items=0;work=0
    while todo:
        v=todo.pop();items+=1;work+=1
        if isinstance(v,dict):work+=len(v);todo.extend(v.values())
        elif isinstance(v,list):todo.extend(v)
    return {'items':items,'work':work,'canonical_bytes':len(json.dumps(value,sort_keys=True,separators=(',',':')).encode())}
generated=read(probe/'generated.json');provenance=read(probe/'checked.json')
original={key:read(probe/(key+'.json')) for key in ('requirements','search','context')}
counts={'original_request_one_snapshot':snapshot_count(original),'generated_final_snapshot':snapshot_count(generated),
        'generator_reported_work':generated['work'],'catalogue_provenance_reported_work':provenance['work']}
rows=[]
for k in (1,2):
    a=read(bench/'8'/f'produced-k{k}.json');b=read(bench/'8'/f'checked-k{k}.json')
    assert a['status']=='CERTIFIED' and b['status']=='PASS'
    subtotal=(a['work']+b['work']+counts['generator_reported_work']+counts['catalogue_provenance_reported_work']
              +2*counts['original_request_one_snapshot']['work']+counts['generated_final_snapshot']['work'])
    rows.append({'k':k,'compiled_work':a['work'],'checked_work':b['work'],'accounted_phase_subtotal':subtotal,
                 'mission_conversion_and_parent_overhead_excluded':True,
                 'certificate_bytes':len(json.dumps(a['certificate'],sort_keys=True,separators=(',',':')).encode()),
                 'max_label_pairs_observed':max(a['counts']['label_pairs'],b['counts']['label_pairs'])})
out=stage/'evidence/composite-policy';out.mkdir(parents=True,exist_ok=True)
record={'status':'RECOMMENDATION_NOT_NATIVE_VALIDATION','source_sha256':sha(stage/'src/oma/optimization/shared_tree_topk.py'),
        'read_only_current_adapter_sha256':sha(adapter),'benchmark_receipt_sha256':sha(bench/'result.json'),
        'upstream_input_hashes':{p.name:sha(p) for p in sorted(probe.glob('*.json'))},'counts':counts,'queries':rows,
        'recommended_explicit_compact_policy':{'total_max_work':40_000_000,'nested_work':'min(current_remaining, callee_hard_maximum)',
          'kernel_per_stage_hard_max_work':20_000_000,'max_transitions':2_000_000,'max_label_pairs':10_000_000,
          'max_connectors':512,'k1_output_and_proof_bytes':16_777_216,'k2_output_and_proof_bytes':33_554_432,
          'default_limits_unchanged':True,'full_ledger_limits_unchanged':True},
        'requirements':['Bind explicit total work/method/K/output limits into the immutable generation-job request.',
          'Consume each nested returned work in the one parent accumulator, including final no-callback kernel tails; do not count callbacks as work a second time.',
          'Raise budget UNKNOWN before a nested call if no work remains; never pass0 or a value greater than that callee hard limit.',
          'Charge original-input capture, generation, catalogue verification, compilation, verification, proposal conversion and final input/generated snapshots.',
          'Keep current cancellation/deadline checkpoints and the final no-callback input/root guard.',
          'Bound complete returned artifact bytes separately; a certificate-byte PASS does not prove the enclosing generated artifact fits.',
          'Native geometry, pressure/service and acceptance remain separately checked. No wall-time or physical feasibility guarantee follows.'],
        'scope':'Exact observed phase counts plus independent snapshot-count calculation. Parent composite and native execution remain required.'}
(out/'result.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'path':str(out/'result.json'),'sha256':sha(out/'result.json'),'queries':rows}))
