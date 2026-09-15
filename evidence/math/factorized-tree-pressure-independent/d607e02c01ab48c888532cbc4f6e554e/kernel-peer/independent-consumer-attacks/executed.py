"""Bounded independently resealed packet attacks against an immutable implementation."""
from pathlib import Path
from fractions import Fraction
import copy, hashlib, json, shutil, sys, uuid

STAGE=Path(__file__).resolve().parent
ROOT=next(p for p in STAGE.parents if (p/'AGENTS.md').exists())
PROBE=ROOT/'.oma/development/factorized-tree-pressure/probes/78236775b4134a4aaa0374e84288b155'
sys.path.insert(0,str(PROBE/'src'))
from oma.optimization import factorized_tree_pressure as impl
def read(p):return json.loads(p.read_text(encoding='utf8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,v):p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf8')
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def reseal(c):c['certificate_root']=hashlib.sha256(canonical({k:v for k,v in c.items() if k!='certificate_root'})).hexdigest()
source=Path(impl.__file__);assert sha(source)=='bc37fb0dc97c453eb2337fc5be31ea581029565cb9801d048e5cefb6f18614bf'
out=STAGE/'packet-attempts'/uuid.uuid4().hex;out.mkdir(parents=True);shutil.copyfile(__file__,out/'executed.py')
fixture=ROOT/'.oma/development/factorized-tree-pressure/tests/fixtures/five-native'
model=read(fixture/'model.json');box=read(fixture/'original-box.json');cert=read(PROBE/'certificate.json')
for old,name in [(fixture/'model.json','model.json'),(fixture/'original-box.json','box.json'),(PROBE/'certificate.json','certificate.json'),(source,'factorized-source.py')]:shutil.copyfile(old,out/name)
original_compile=impl.compile_factorized_tree_pressure
def forbidden(*args,**kwargs):raise AssertionError('Verifier invoked a forbidden producer routine')
impl.compile_factorized_tree_pressure=impl._producer_polynomial=impl._producer_evaluate=impl.old._produce_polynomial=forbidden
results=[]
def check(name,m,b,c,**kwargs):
    r=impl.verify_factorized_tree_pressure(m,b,c,**kwargs);results.append({'name':name,'status':r['status'],'reason':r.get('reason'),'work':r.get('work')});return r
baseline=check('genuine_with_all_producers_disabled',model,box,cert);assert baseline['status']=='PASS'
names=sorted(model['leaves'])
attacks={
 'missing_monomial':lambda c:c['preconditioned_polynomial'].pop(),
 'duplicated_monomial':lambda c:c['preconditioned_polynomial'].append(copy.deepcopy(c['preconditioned_polynomial'][0])),
 'reversed_variable_pair':lambda c:c['preconditioned_polynomial'][1].__setitem__('variables',list(reversed(c['preconditioned_polynomial'][1]['variables']))),
 'wrong_signed_weight':lambda c:c['preconditioned_polynomial'][0].__setitem__('weight',str(-Fraction(c['preconditioned_polynomial'][0]['weight']))),
 'cross_monomial_missing_factor_two':lambda c:c['preconditioned_polynomial'][1].__setitem__('weight',str(Fraction(c['preconditioned_polynomial'][1]['weight'])/2)),
 'same_interval_distinct_ID_alias':lambda c:c['preconditioned_polynomial'][0].__setitem__('coefficient_id',sorted(model['coefficients'])[1]),
 'wrong_output_row':lambda c:c['preconditioned_polynomial'][0].__setitem__('row',names[-1]),
 'missing_original_term':lambda c:c['term_evidence'].pop(),
 'forged_B':lambda c:c['derivative_map'][0].__setitem__(0,{'lower':'0','upper':'0'}),
 'forged_J':lambda c:c['jacobian'][0].__setitem__(0,{'lower':'0','upper':'0'}),
 'forged_R':lambda c:c['preconditioner'][0].__setitem__(0,'0'),
 'forged_inverse_witness':lambda c:c['inverse_witness'][0].__setitem__(0,'0'),
 'forged_inverse_product':lambda c:c['inverse_products']['left'][0].__setitem__(0,'0'),
 'forged_RF_center':lambda c:c['center_image'].__setitem__(names[0],{'lower':'1','upper':'1'}),
 'forged_residual':lambda c:c['center_residual'].__setitem__(names[0],{'lower':'0','upper':'0'}),
 'forged_enclosure':lambda c:c['root_enclosure'].__setitem__(names[0],copy.deepcopy(c['center_image'][names[0]])),
 'forged_norm':lambda c:c.__setitem__('contraction_norm_upper','0'),
 'forged_row_norm':lambda c:c['row_norm_upper'].__setitem__(0,'0'),
 'forged_margin':lambda c:c['inclusion_margins'][names[0]].__setitem__('lower','1'),
 'old_certificate_schema':lambda c:c.__setitem__('schema','oma.coupled-tree-positive-box-certificate/1'),
 'boolean_count_alias':lambda c:c['counts'].__setitem__('variables',True),
 'missing_coefficient_inventory':lambda c:c['inventories']['coefficient_ids'].pop(),
 'wrong_root_scope':lambda c:c.__setitem__('physical_model_root','0'*64),
 'zero_denominator':lambda c:c['preconditioner'][0].__setitem__(0,'1/0'),
}
for name,mutate in attacks.items():
    packet=copy.deepcopy(cert);mutate(packet);reseal(packet);r=check(name,model,box,packet);assert r['status']!='PASS',name
for name,mutation in [
 ('changed_physical_coefficient',lambda m:m['coefficients'][sorted(m['coefficients'])[0]].__setitem__('lower','0')),
 ('changed_named_parameter_identity',lambda m:m['terms'][0].__setitem__('coefficient_id',sorted(m['coefficients'])[1])),
 ('changed_physical_head',lambda m:m['available_heads'][names[0]].__setitem__('upper','999999999')),
 ('changed_full_incidence',lambda m:m['terms'][0].__setitem__('descendant_leaves',names[:1]))]:
    m=copy.deepcopy(model);mutation(m);assert check(name,m,box,cert)['status']!='PASS'
for name,kwargs in [('too_few_monomials',{'max_monomials':len(cert['preconditioned_polynomial'])-1}),
                    ('too_few_bytes',{'max_certificate_bytes':len(canonical(cert))-1}),
                    ('work_minus_one',{'max_work':baseline['work']-1}),
                    ('work_very_small',{'max_work':1}),('rational_bits_small',{'max_rational_bits':32})]:
    assert check(name,model,box,cert,**kwargs)['status']=='UNKNOWN'
assert check('exact_reported_work_budget',model,box,cert,max_work=baseline['work'])['status']=='PASS'
assert check('exact_packet_byte_budget',model,box,cert,max_certificate_bytes=len(canonical(cert)))['status']=='PASS'
assert check('exact_nonzero_monomial_budget',model,box,cert,max_monomials=len(cert['preconditioned_polynomial']))['status']=='PASS'
for target in ('model','box','certificate'):
    m,b,c=copy.deepcopy(model),copy.deepcopy(box),copy.deepcopy(cert);fired=[]
    def mutate(stage):
        if stage=='factorized_verifier_complete':
            fired.append(stage)
            if target=='model':m['available_heads'][names[0]]['upper']='999999999'
            elif target=='box':b[names[0]]['upper']='1'
            else:c['preconditioned_polynomial'].pop()
    assert check('final_callback_mutation_'+target,m,b,c,checkpoint=mutate)['status']!='PASS';assert fired
error=ValueError('independent caller cancellation sentinel')
def cancel(stage):
    if stage=='factorized_verifier_complete':raise error
try:check('final_callback_exception_identity',model,box,cert,checkpoint=cancel)
except ValueError as e:assert e is error;results.append({'name':'final_callback_exception_identity','status':'PRESERVED'})
else:raise AssertionError('Caller cancellation swallowed')
assert sha(source)=='bc37fb0dc97c453eb2337fc5be31ea581029565cb9801d048e5cefb6f18614bf'
result={'status':'ALL_INDEPENDENT_PACKET_GATES_PASS','checks':len(results),'results':results,
        'implementation_sha256':sha(source),'loaded_module':str(source),
        'input_and_certificate_copies_sha256':{n:sha(out/n) for n in ('model.json','box.json','certificate.json')},
        'script_sha256':sha(out/'executed.py'),'all_producers_disabled':True,
        'scope':'Pure certificate consumer gates; no native rerun, source or physical assumption mutation'}
dump(out/'result.json',result);print(json.dumps({'out':str(out),'status':result['status'],'checks':len(results)}))
