"""Independent rational Bernstein-face proof and Decimal corner consistency.

No kernel interval arithmetic, polynomial, inverse or fixed-point helpers are
used below. Face Bernstein signs prove existence for every same parameter
tuple (Poincare--Miranda); full rational J/R product bounds separately prove
contraction. Decimal roots are only finite consistency checks.
"""
from copy import deepcopy
from decimal import Decimal as D,localcontext
from fractions import Fraction as Q
from itertools import product
from pathlib import Path
import hashlib,importlib.util,json,shutil,sys,time,uuid

STAGE=Path(__file__).resolve().parents[1]
BUILD=sys.argv[1] if len(sys.argv)>1 else "8144e76ddff8f1b4cb146aad47592a1ced7ba12dc2d21853c0f087c386cc2a70"
SOURCE=STAGE/"runtimes"/BUILD/"src"
sys.path.insert(0,str(SOURCE))
from oma.optimization import coupled_tree_pressure as kernel


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def enc(x):return {"lower":str(x[0]),"upper":str(x[1])}
def span(x):return Q(x["lower"]),Q(x["upper"])
def isum(xs):
    xs=list(xs);return sum((x[0] for x in xs),Q()),sum((x[1] for x in xs),Q())
def scale(a,x):return min(a*x[0],a*x[1]),max(a*x[0],a*x[1])


def determinant(m):
    return (m[0][0]*(m[1][1]*m[2][2]-m[1][2]*m[2][1])
            -m[0][1]*(m[1][0]*m[2][2]-m[1][2]*m[2][0])
            +m[0][2]*(m[1][0]*m[2][1]-m[1][1]*m[2][0]))


def inverse3(m):
    d=determinant(m);assert d
    out=[]
    for i in range(3):
        row=[]
        for j in range(3):
            # transposed cofactor, independently of Gaussian elimination
            rows=[r for r in range(3) if r!=j];cols=[c for c in range(3) if c!=i]
            co=m[rows[0]][cols[0]]*m[rows[1]][cols[1]]-m[rows[0]][cols[1]]*m[rows[1]][cols[0]]
            row.append((-1)**(i+j)*co/d)
        out.append(row)
    return out


def bernstein_faces(model,box,r):
    names=sorted(model["leaves"]);bounds={k:span(v) for k,v in box.items()}
    coefficients={k:span(v) for k,v in model["coefficients"].items()}
    heads={k:span(v) for k,v in model["available_heads"].items()}
    result=[]
    for i,name in enumerate(names):
        free=[k for k in names if k!=name]
        for face in (0,1):
            rows=[]
            for indexes in product(range(3),repeat=2):
                ix=dict(zip(free,indexes));weights={a:Q() for a in coefficients}
                for term in model["terms"]:
                    d=term["descendant_leaves"]
                    base=sum((bounds[k][face] if k==name else bounds[k][0] for k in d),Q())
                    w={k:bounds[k][1]-bounds[k][0] for k in free if k in d}
                    value=base*base
                    for k,width in w.items():
                        value+=2*base*width*Q(ix[k],2)+width*width*Q(ix[k]*(ix[k]-1),2)
                    for j,k in enumerate(free):
                        for other in free[j+1:]:
                            if k in w and other in w:value+=2*w[k]*w[other]*Q(ix[k],2)*Q(ix[other],2)
                    weight=sum((r[i][names.index(k)] for k in term["applies_to_leaves"]),Q())
                    weights[term["coefficient_id"]]+=weight*value
                image=isum([scale(weight,coefficients[a]) for a,weight in weights.items()]
                           +[scale(-r[i][j],heads[k]) for j,k in enumerate(names)])
                assert (image[1]<0 if face==0 else image[0]>0),(name,face,indexes,image)
                rows.append({"tensor_index":list(indexes),"range":enc(image)})
            result.append({"coordinate":name,"side":"lower" if face==0 else "upper","coefficients":rows})
    return result


def independent_contraction(model,box,r):
    names=sorted(model["leaves"]);bounds={k:span(v) for k,v in box.items()}
    jac=[]
    for i in names:
        row=[]
        for j in names:
            terms=[]
            for t in model["terms"]:
                if i in t["applies_to_leaves"] and j in t["descendant_leaves"]:
                    a=span(model["coefficients"][t["coefficient_id"]]);s=isum(bounds[k] for k in t["descendant_leaves"])
                    terms.append((2*a[0]*s[0],2*a[1]*s[1]))
            row.append(isum(terms))
        jac.append(row)
    derivative=[]
    for i in range(3):
        row=[]
        for j in range(3):
            low,high=isum(scale(r[i][k],jac[k][j]) for k in range(3))
            row.append((Q(i==j)-high,Q(i==j)-low))
        derivative.append(row)
    norm=max(sum((max(abs(lo),abs(hi)) for lo,hi in row),Q()) for row in derivative)
    assert norm<1
    return norm,jac,derivative


def dec(q):return D(q.numerator)/D(q.denominator)


def solve(model,coeff,heads):
    names=sorted(model["leaves"]);x=[D(1),D(2),D(3)]
    for _ in range(20):
        f=[-heads[k] for k in names];j=[[D(0) for _ in names] for _ in names]
        for term in model["terms"]:
            total=sum((x[names.index(k)] for k in term["descendant_leaves"]),D(0));a=coeff[term["coefficient_id"]]
            for row,k in enumerate(names):
                if k in term["applies_to_leaves"]:
                    f[row]+=a*total*total
                    for col,k2 in enumerate(names):
                        if k2 in term["descendant_leaves"]:j[row][col]+=2*a*total
        if max(map(abs,f))<D("1e-65"):return x,max(map(abs,f))
        aug=[row+[v] for row,v in zip(j,f)]
        for col in range(3):
            pivot=max(range(col,3),key=lambda i:abs(aug[i][col]));aug[col],aug[pivot]=aug[pivot],aug[col]
            d=aug[col][col];aug[col]=[v/d for v in aug[col]]
            for i in range(3):
                if i!=col:
                    factor=aug[i][col];aug[i]=[v-factor*w for v,w in zip(aug[i],aug[col])]
        x=[v-row[-1] for v,row in zip(x,aug)]
    raise AssertionError("Independent Decimal solve failed to converge")


def main():
    start=time.perf_counter();attempt=STAGE/"evidence/independent-rational-oracle"/uuid.uuid4().hex;attempt.mkdir(parents=True)
    spec=importlib.util.spec_from_file_location("manufactured_fixture",STAGE/"validation/7da216bb14a647829d41f1444c03c1ca/tests/test_coupled_tree_pressure.py")
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    model,box=helper.example(True);packet=kernel.compile_coupled_tree_pressure(model,box)
    assert packet["status"]=="CERTIFIED_BOX"
    point_model,_=helper.example(False)
    midpoint=[[Q("29/5"),Q("24/5"),Q("24/5")],[Q("18/5"),Q(10),Q("38/5")],[Q("18/5"),Q("91/10"),Q("133/10")]]
    r=inverse3(midpoint);assert [[str(v) for v in row] for row in r]==packet["preconditioner"]
    faces=bernstein_faces(model,box,r);norm,jac,derivative=independent_contraction(model,box,r)
    assert str(norm)==packet["contraction_norm_upper"]
    assert [[enc(v) for v in row] for row in jac]==packet["jacobian"]
    assert [[enc(v) for v in row] for row in derivative]==packet["derivative_map"]
    keys=sorted(model["coefficients"]);names=sorted(model["leaves"]);max_res=D(0);minimum=[None]*3;maximum=[None]*3
    count=0
    with localcontext() as ctx:
        ctx.prec=80
        for corner in product((0,1),repeat=len(keys)+len(names)):
            coeff={k:dec(span(model["coefficients"][k])[corner[i]]) for i,k in enumerate(keys)}
            heads={k:dec(span(model["available_heads"][k])[corner[len(keys)+i]]) for i,k in enumerate(names)}
            root,res=solve(model,coeff,heads);max_res=max(max_res,res);count+=1
            for i,k in enumerate(names):
                bound=span(packet["root_enclosure"][k]);assert dec(bound[0])<=root[i]<=dec(bound[1])
                minimum[i]=root[i] if minimum[i] is None else min(minimum[i],root[i]);maximum[i]=root[i] if maximum[i] is None else max(maximum[i],root[i])
    for name,data in (("model.json",model),("flow-box.json",box),("certificate.json",packet)):
        (attempt/name).write_text(json.dumps(data,indent=2)+"\n",encoding="utf-8")
    shutil.copyfile(__file__,attempt/"oracle.py");shutil.copyfile(SOURCE/"oma/optimization/coupled_tree_pressure.py",attempt/"reviewed-kernel.py")
    result={"status":"PASS","build":BUILD,"kernel_sha256":sha(SOURCE/"oma/optimization/coupled_tree_pressure.py"),
        "proof":"54 exact rational tensor Bernstein coefficients on six faces have strict Miranda signs for entire parameter box; independent full Jacobian contraction and adjugate inverse",
        "bernstein_faces":faces,"contraction_norm_upper":str(norm),"corners":count,"decimal_digits":80,"maximum_residual":str(max_res),
        "observed_corner_ranges":{k:{"lower":str(minimum[i]),"upper":str(maximum[i])} for i,k in enumerate(names)},
        "corner_samples_are_universal_proof":False,"native_applicability_or_global_uniqueness":False,"seconds":time.perf_counter()-start}
    (attempt/"result.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":"PASS","directory":attempt.relative_to(STAGE).as_posix(),"corners":count,"seconds":result["seconds"]}))


if __name__=="__main__":main()
