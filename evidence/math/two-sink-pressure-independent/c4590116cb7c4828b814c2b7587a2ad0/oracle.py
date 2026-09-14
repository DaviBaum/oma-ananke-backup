from pathlib import Path
from copy import deepcopy
from decimal import Decimal, localcontext
from fractions import Fraction as F
from itertools import product
import random,importlib.util,json,hashlib,time
path=Path(__file__).with_name("original-kernel.py")
spec=importlib.util.spec_from_file_location("k",path); k=importlib.util.module_from_spec(spec);spec.loader.exec_module(k)
rng=random.Random(91426)
def decimal(f):
    f=F(f);return Decimal(f.numerator)/Decimal(f.denominator)
def solve(p):
    # Independently bisect equality of the two original path-derived Q^2 values.
    lo,hi=Decimal(0),Decimal(1)
    for _ in range(250):
        t=(lo+hi)/2
        qsq1=p['P1']/(p['beta']*(p['A1']+p['B1']*t*t))
        qsq2=p['P2']/(p['beta']*(p['A2']+p['B2']*(1-t)*(1-t)))
        if qsq1==qsq2: break
        if qsq1>qsq2:lo=t
        else:hi=t
    Q=((qsq1+qsq2)/2).sqrt()
    residual=max(abs(p['P1']-p['beta']*Q*Q*(p['A1']+p['B1']*t*t)),abs(p['P2']-p['beta']*Q*Q*(p['A2']+p['B2']*(1-t)*(1-t))))
    return t,Q,t*Q,(1-t)*Q,residual
start=time.monotonic(); results=[]
with localcontext() as ctx:
    ctx.prec=100
    for box in range(12):
        axes={}
        for key in k.PARAMETERS:
            denominator=100 if key.startswith('A') else 10
            endpoints=sorted([F(rng.randint(0,1) if key.startswith('A') else rng.randint(1,200),denominator) for _ in range(2)])
            axes[key]=endpoints
        model={'schema':k.MODEL_SCHEMA,'branch_ids':['one','two'],'parameters':{key:{'lower':str(v[0]),'upper':str(v[1])} for key,v in axes.items()},'context_root':'a'*64,'physical_model_root':'b'*64,'assumptions':deepcopy(k.MODEL_ASSUMPTIONS)}
        compiled=k.compile_two_sink_pressure(model)
        if compiled['status']!='CERTIFIED':
            results.append({'model':model,'status':compiled['status'],'reason':compiled.get('reason'),'samples':0});continue
        cert=compiled['certificate']; check=k.verify_two_sink_pressure(model,cert);assert check['status']=='PASS',check
        e=cert['enclosures']; intervals=[e['split_fraction'],e['total_flow_m3_s'],e['branch_flows_m3_s']['one'],e['branch_flows_m3_s']['two']]
        cases=list(product(*[axes[key] for key in k.PARAMETERS]))
        cases.extend(tuple(lo+(hi-lo)*F(rng.randint(0,100),100) for lo,hi in axes.values()) for _ in range(32))
        residual=Decimal(0)
        for case in cases:
            p={key:decimal(value) for key,value in zip(k.PARAMETERS,case)}
            solved=solve(p);residual=max(residual,solved[-1])
            for value,interval in zip(solved,intervals):
                assert decimal(interval['lower'])<=value<=decimal(interval['upper']), (box,p,value,interval)
            assert abs(solved[1]-solved[2]-solved[3])<Decimal('1e-95')
        results.append({'model':model,'status':'SAMPLED_EQUATIONS_AND_ALL_ENCLOSURES_MATCH','samples':len(cases),'max_pressure_equation_residual':str(residual),'certificate':cert,'checker':check})
output={'status':'BOUNDED_INDEPENDENT_ORACLE_PASS','source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'boxes':len(results),'certified_boxes':sum(r['samples']>0 for r in results),'unknown_boxes':sum(r['samples']==0 for r in results),'sample_count':sum(r['samples'] for r in results),'results':results,'seconds':time.monotonic()-start,'scope':'Numerical 100-decimal-digit bisection of original path equations; finite samples are consistency evidence, not universal proof or physical native applicability'}
Path(__file__).with_name('oracle-result.json').write_text(json.dumps(output,indent=2));print(json.dumps({k:v for k,v in output.items() if k!='results'}))
