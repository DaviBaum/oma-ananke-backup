"""Independent Fraction oracle; no OMA imports or producer/verifier helpers."""
from fractions import Fraction as F
from pathlib import Path
from itertools import product
import copy, hashlib, json, random, shutil, uuid

STAGE=Path(__file__).resolve().parent
ROOT=next(p for p in STAGE.parents if (p/'AGENTS.md').exists())
INPUT=ROOT/'.oma/development/factorized-tree-pressure/tests/fixtures/five-native'
PROBE=ROOT/'.oma/development/factorized-tree-pressure/probes/78236775b4134a4aaa0374e84288b155'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def encode(v):
    if isinstance(v,F):return str(v)
    if isinstance(v,dict):return {k:encode(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [encode(x) for x in v]
    return v
def dump(p,v):p.write_text(json.dumps(encode(v),indent=2)+'\n',encoding='utf8')
def iv(v):return F(v['lower']),F(v['upper'])
def add(a,b):return a[0]+b[0],a[1]+b[1]
def neg(a):return -a[1],-a[0]
def mul(a,b):
    q=[x*y for x in a for y in b];return min(q),max(q)
def isum(rows):
    result=(F(0),F(0))
    for x in rows:result=add(result,x)
    return result
def scale(a,b):return mul((a,a),b)
def matmul(a,b):return [[sum(x*y for x,y in zip(row,col)) for col in zip(*b)] for row in a]
def inverse(a):
    n=len(a);rows=[list(row)+[F(i==j) for j in range(n)] for i,row in enumerate(a)]
    for i in range(n):
        k=next(k for k in range(i,n) if rows[k][i]);rows[i],rows[k]=rows[k],rows[i]
        factor=rows[i][i];rows[i]=[x/factor for x in rows[i]]
        for k in range(n):
            if k!=i:
                factor=rows[k][i];rows[k]=[x-factor*y for x,y in zip(rows[k],rows[i])]
    result=[row[n:] for row in rows];identity=[[F(i==j) for j in range(n)] for i in range(n)]
    assert matmul(a,result)==matmul(result,a)==identity
    return result
def direct(m,q,k,h):
    names=sorted(m['leaves']);f=[-h[x] for x in names];j=[[F(0) for _ in names] for _ in names]
    for t in m['terms']:
        total=sum(q[x] for x in t['descendant_leaves']);a=k[t['coefficient_id']]
        for i,x in enumerate(names):
            if x in t['applies_to_leaves']:
                f[i]+=a*total**2
                for col,y in enumerate(names):
                    if y in t['descendant_leaves']:j[i][col]+=2*a*total
    return f,j
def collect(m,r):
    names=sorted(m['leaves']);rows=[]
    # Reconstruct every output row, named coefficient and unordered leaf pair.
    for row in r:
        out={}
        for k in sorted(m['coefficients']):
            for u in range(len(names)):
                for v in range(u,len(names)):
                    weight=F(0)
                    for equation,leaf in enumerate(names):
                        incidence=sum(t['coefficient_id']==k and leaf in t['applies_to_leaves'] and names[u] in t['descendant_leaves'] and names[v] in t['descendant_leaves'] for t in m['terms'])
                        weight+=row[equation]*incidence*(1 if u==v else 2)
                    if weight:out[k,names[u],names[v]]=weight
        rows.append(out)
    return rows
def point(poly,names,q,k):
    values=[];jac=[]
    for row in poly:
        values.append(sum(weight*k[a]*q[u]*q[v] for (a,u,v),weight in row.items()))
        jac.append([sum(weight*k[a]*((q[v] if u==col else 0)+(q[u] if v==col else 0)) for (a,u,v),weight in row.items()) for col in names])
    return values,jac
def enclosures(m,box,r):
    names=sorted(m['leaves']);c={x:sum(iv(box[x]))/2 for x in names};poly=collect(m,r)
    coefficients={k:iv(v) for k,v in m['coefficients'].items()};heads={k:iv(v) for k,v in m['available_heads'].items()}
    rf=[];rj=[]
    for i,row in enumerate(poly):
        rf.append(add(isum(scale(sum(w*c[u]*c[v] for (a,u,v),w in row.items() if a==k),span) for k,span in coefficients.items()),
                      neg(isum(scale(r[i][j],heads[x]) for j,x in enumerate(names)))))
        line=[]
        for col in names:
            terms=[]
            for k,span in coefficients.items():
                linear=(F(0),F(0))
                for var in names:
                    weight=sum(w*((u==col and v==var)+(v==col and u==var)) for (a,u,v),w in row.items() if a==k)
                    linear=add(linear,scale(weight,iv(box[var])))
                terms.append(mul(span,linear))
            line.append(isum(terms))
        rj.append(line)
    b=[[add((F(i==j),)*2,neg(x)) for j,x in enumerate(row)] for i,row in enumerate(rj)]
    center_image={};image={};margins={};norms=[sum(max(abs(lo),abs(hi)) for lo,hi in row) for row in b]
    for i,x in enumerate(names):
        center_image[x]=add((c[x],c[x]),neg(rf[i]));error=isum(mul(b[i][j],add(iv(box[y]),(-c[y],-c[y]))) for j,y in enumerate(names))
        image[x]=add(center_image[x],error);margins[x]=(image[x][0]-iv(box[x])[0],iv(box[x])[1]-image[x][1])
    return {'poly':poly,'RF':rf,'RJ':rj,'B':b,'center_image':center_image,'root_enclosure':image,'margins':margins,'row_norms':norms,'norm':max(norms),'center':c}
def contains(a,x):return a[0]<=x<=a[1]
def check_points(m,box,r,points):
    names=sorted(m['leaves']);bounds=enclosures(m,box,r);count=0
    for q,k,h in points:
        f,j=direct(m,q,k,h);rf=[sum(r[i][col]*f[col] for col in range(len(names))) for i in range(len(names))];rj=matmul(r,j)
        expanded,ej=point(bounds['poly'],names,q,k);rh=[sum(r[i][col]*h[names[col]] for col in range(len(names))) for i in range(len(names))]
        assert rf==[v-z for v,z in zip(expanded,rh)] and rj==ej
        assert all(contains(bounds['RJ'][i][col],rj[i][col]) for i in range(len(names)) for col in range(len(names)))
        centerf,_=direct(m,bounds['center'],k,h);centerrf=[sum(r[i][col]*centerf[col] for col in range(len(names))) for i in range(len(names))]
        assert all(contains(bounds['RF'][i],centerrf[i]) for i in range(len(names)))
        count+=1
    return count
def samples(m,box,count,seed):
    rng=random.Random(seed)
    def draw(interval):
        lo,hi=iv(interval);return lo+(hi-lo)*F(rng.randrange(17),16)
    for _ in range(count):yield ({x:draw(v) for x,v in box.items()},{x:draw(v) for x,v in m['coefficients'].items()},{x:draw(v) for x,v in m['available_heads'].items()})

out=STAGE/'attempts'/uuid.uuid4().hex;out.mkdir(parents=True);shutil.copyfile(__file__,out/'executed.py')
paths={'model':INPUT/'model.json','box':INPUT/'original-box.json','certificate':PROBE/'certificate.json'}
before={k:sha(p) for k,p in paths.items()}
for k,p in paths.items():shutil.copyfile(p,out/(k+'.json'))
m=read(paths['model']);box=read(paths['box']);certificate=read(paths['certificate']);names=sorted(m['leaves'])
center={x:sum(iv(box[x]))/2 for x in names};km={k:sum(iv(v))/2 for k,v in m['coefficients'].items()};hm={k:sum(iv(v))/2 for k,v in m['available_heads'].items()}
_,j=direct(m,center,km,hm);r=inverse(j);assert r==[[F(x) for x in row] for row in certificate['preconditioner']]
bounds=enclosures(m,box,r)
record=[{'row':names[i],'coefficient_id':a,'variables':[u,v],'weight':str(w)} for i,row in enumerate(bounds['poly']) for (a,u,v),w in sorted(row.items())]
assert record==certificate['preconditioned_polynomial']
assert bounds['B']==[[iv(v) for v in row] for row in certificate['derivative_map']]
assert bounds['norm']==F(certificate['contraction_norm_upper'])
for x in names:
    assert bounds['center_image'][x]==iv(certificate['center_image'][x])
    assert bounds['root_enclosure'][x]==iv(certificate['root_enclosure'][x])
    assert bounds['margins'][x]==(F(certificate['inclusion_margins'][x]['lower']),F(certificate['inclusion_margins'][x]['upper']))
assert bounds['norm']<1 and all(lo>0 and hi>0 for lo,hi in bounds['margins'].values())
native_samples=check_points(m,box,r,samples(m,box,256,51234))
tiny={'leaves':['a','b'],'coefficients':{'shared':{'lower':'1','upper':'2'},'independent':{'lower':'1','upper':'2'}},
      'available_heads':{'a':{'lower':'1','upper':'2'},'b':{'lower':'2','upper':'3'}},
      'terms':[{'id':'1','coefficient_id':'shared','descendant_leaves':['a','b'],'applies_to_leaves':['a','b']},
               {'id':'2','coefficient_id':'shared','descendant_leaves':['a'],'applies_to_leaves':['a']},
               {'id':'3','coefficient_id':'independent','descendant_leaves':['b'],'applies_to_leaves':['b']}]}
tinybox={'a':{'lower':'1','upper':'2'},'b':{'lower':'2','upper':'3'}};signedr=[[F(2),F(-1)],[F(-3),F(4)]]
corner_points=[]
for q0,q1,k0,k1,h0,h1 in product((0,1),repeat=6):
    corner_points.append(({'a':F(1+q0),'b':F(2+q1)},{'shared':F(1+k0),'independent':F(1+k1)},{'a':F(1+h0),'b':F(2+h1)}))
corners=check_points(tiny,tinybox,signedr,corner_points)
random_checks=0
for seed in range(40):
    rng=random.Random(seed);matrix=[[F(rng.randrange(-7,8),rng.randrange(1,5)) for _ in range(2)] for _ in range(2)]
    random_checks+=check_points(tiny,tinybox,matrix,samples(tiny,tinybox,16,seed+8000))
identity_counterexample={'distinct_named_coefficients_same_interval':{'k1':['1','2'],'k2':['1','2']},
    'expression':'k1*q^2-k2*q^2','q':'1','true_interval':['-1','1'],'invalid_value_based_merge_interval':['0','0'],
    'witness':{'k1':'1','k2':'2','exact_value':'-1'},'declared_same_ID_cancellation_is_valid':True}
dump(out/'independent-proof.json',{'preconditioner':r,'preconditioned_polynomial':record,'derivative_map':bounds['B'],
    'center_image':bounds['center_image'],'root_enclosure':bounds['root_enclosure'],'inclusion_margins':bounds['margins'],
    'row_norm_upper':bounds['row_norms'],'contraction_norm_upper':bounds['norm']})
dump(out/'identity-counterexample.json',identity_counterexample)
assert all(sha(p)==before[k] for k,p in paths.items())
result={'status':'INDEPENDENT_POLYNOMIAL_AND_ORIGINAL_BOX_BANACH_PASS','input_sha256':before,
    'source_script_sha256':sha(out/'executed.py'),'application_helpers_imported':False,
    'variables':len(names),'terms':len(m['terms']),'named_coefficients':len(m['coefficients']),
    'nonzero_collected_monomials':len(record),'native_model_rational_samples':native_samples,
    'shared_parameter_signed_R_exhaustive_corners':corners,'additional_signed_R_rational_samples':random_checks,
    'norm_upper_float_for_readability':float(bounds['norm']),
    'smallest_strict_margin_float_for_readability':float(min(v for row in bounds['margins'].values() for v in row)),
    'same_model_same_box':True,'new_native_check_or_acceptance_claim':False,
    'scope':'Exact polynomial identity and interval-Banach conditions. Native applicability remains in separately authenticated original artifacts; global uniqueness remains the separately checked global theorem.'}
dump(out/'result.json',result);print(json.dumps({'output':str(out),**result},indent=2))
