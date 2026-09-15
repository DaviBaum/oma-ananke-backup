"""Same-model Banach proof preserving named-coefficient polynomial cancellation."""
from copy import deepcopy
from fractions import Fraction as Q
from . import coupled_tree_pressure as old

p=old.p
CERTIFICATE_SCHEMA='oma.factorized-tree-positive-box-certificate/1'
RULE='RATIONAL_COEFFICIENT_MONOMIAL_PRECONDITIONED_BANACH_V1'
SCOPE=old.SCOPE


def _normalize(raw,b):
    m=old._normalize(raw,b)
    m['header']['schema']=CERTIFICATE_SCHEMA;m['header']['rule']=RULE
    return m


class _Slots:
    def __init__(self,maximum):self.maximum=maximum;self.used=0
    def add(self):
        self.used+=1
        if self.used>self.maximum:raise p._Limit('MONOMIAL_BUDGET')


def _producer_polynomial(m,r,b,maximum):
    """Term expansion followed by exact collection of like monomials."""
    output=[{} for _ in m['leaves']];slots=_Slots(maximum)
    index={name:i for i,name in enumerate(m['leaves'])}
    for term in m['terms']:
        b.tick('factorized_producer_term')
        d=term['descendant_leaves'];a=term['coefficient_id']
        for i,row in enumerate(output):
            weight=old._sum((r[i][index[name]] for name in term['applies_to_leaves']),b)
            if not weight:continue
            for j,u in enumerate(d):
                for v in d[j:]:
                    b.tick('factorized_producer_monomial');key=(a,u,v)
                    if key not in row:slots.add();row[key]=Q(0)
                    row[key]=b.add(row[key],b.mul(weight,Q(1 if u==v else 2)))
    return [{key:value for key,value in row.items() if value} for row in output]


def _checker_polynomial(m,r,b,maximum):
    """Independent complete row/parameter/variable-pair incidence traversal."""
    output=[];slots=_Slots(maximum)
    for i,_ in enumerate(m['leaves']):
        row={}
        for a in sorted(m['coefficients']):
            for j,u in enumerate(m['leaves']):
                for v in m['leaves'][j:]:
                    value=Q(0)
                    for term in m['terms']:
                        b.tick('factorized_check_monomial_incidence')
                        if term['coefficient_id']!=a or u not in term['descendant_leaves'] or v not in term['descendant_leaves']:continue
                        for col,leaf in enumerate(m['leaves']):
                            b.tick('factorized_check_equation_incidence')
                            if leaf in term['applies_to_leaves']:
                                value=b.add(value,b.mul(r[i][col],Q(1 if u==v else 2)))
                    if value:slots.add();row[a,u,v]=value
        output.append(row)
    return output


def _polynomial_record(m,poly,b):
    output=[]
    for i,row in enumerate(poly):
        for (a,u,v),weight in sorted(row.items()):
            b.tick('factorized_record')
            output.append({'row':m['leaves'][i],'coefficient_id':a,'variables':[u,v],'weight':str(weight)})
    return output


def _producer_evaluate(m,poly,center,r,b):
    rf=[];rj=[]
    for i,row in enumerate(poly):
        scalar={};gradient={}
        for (a,u,v),weight in row.items():
            b.tick('factorized_producer_evaluation')
            scalar[a]=b.add(scalar.get(a,Q(0)),b.mul(b.mul(weight,center[u]),center[v]))
            # Differentiating a square contributes twice to this same key.
            for col,var in ((u,v),(v,u)):
                key=(a,col,var);gradient[key]=b.add(gradient.get(key,Q(0)),weight)
        loss=old._isum((old._times((value,value),m['coefficients'][a],b) for a,value in sorted(scalar.items())),b)
        heads=old._isum((old._times((r[i][k],r[i][k]),m['heads'][leaf],b) for k,leaf in enumerate(m['leaves'])),b)
        rf.append(old._minus(loss,heads,b));line=[]
        for col in m['leaves']:
            contributions=[]
            for a in sorted(m['coefficients']):
                linear=old._isum((old._times((gradient.get((a,col,var),Q(0)),)*2,m['box'][var],b) for var in m['leaves']),b)
                contributions.append(old._times(m['coefficients'][a],linear,b))
            line.append(old._isum(contributions,b))
        rj.append(line)
    return rf,rj


def _checker_evaluate(m,poly,center,r,b):
    rf=[];rj=[]
    for i,row in enumerate(poly):
        loss=(Q(0),Q(0))
        for a in sorted(m['coefficients']):
            value=Q(0)
            for (aid,u,v),weight in sorted(row.items()):
                b.tick('factorized_check_center')
                if aid==a:value=b.add(value,b.mul(weight,b.mul(center[u],center[v])))
            loss=old._plus(loss,old._times(m['coefficients'][a],(value,value),b),b)
        for k,leaf in enumerate(m['leaves']):
            loss=old._minus(loss,old._times(m['heads'][leaf],(r[i][k],r[i][k]),b),b)
        rf.append(loss);line=[]
        for col in m['leaves']:
            interval=(Q(0),Q(0))
            for a in sorted(m['coefficients']):
                linear=(Q(0),Q(0))
                for (aid,u,v),weight in sorted(row.items()):
                    b.tick('factorized_check_derivative')
                    if aid!=a:continue
                    if col==u:linear=old._plus(linear,old._times((weight,weight),m['box'][v],b),b)
                    if col==v:linear=old._plus(linear,old._times((weight,weight),m['box'][u],b),b)
                interval=old._plus(interval,old._times(m['coefficients'][a],linear,b),b)
            line.append(interval)
        rj.append(line)
    return rf,rj


def _proof(m,center,r,inverse,poly,b,checked):
    n=len(m['leaves']);identity=[[Q(int(i==j)) for j in range(n)] for i in range(n)]
    left,right=old._mm(r,inverse,b),old._mm(inverse,r,b)
    if left!=identity or right!=identity:raise p._Invalid('Both exact preconditioner inverse products are required')
    rf,rj=(_checker_evaluate if checked else _producer_evaluate)(m,poly,center,r,b)
    derivative=[[old._minus((Q(int(i==j)),)*2,rj[i][j],b) for j in range(n)] for i in range(n)]
    norms=[old._sum((max(abs(lo),abs(hi)) for lo,hi in row),b) for row in derivative]
    images={};enclosures={};margins={}
    for i,name in enumerate(m['leaves']):
        image=old._minus((center[name],center[name]),rf[i],b)
        error=old._isum((old._times(derivative[i][j],old._minus(m['box'][leaf],(center[leaf],)*2,b),b) for j,leaf in enumerate(m['leaves'])),b)
        enclosure=old._plus(image,error,b)
        images[name]=p._enc(image);enclosures[name]=p._enc(enclosure)
        margins[name]={'lower':str(b.sub(enclosure[0],m['box'][name][0])),'upper':str(b.sub(m['box'][name][1],enclosure[1]))}
    return {'preconditioned_polynomial':_polynomial_record(m,poly,b),
        'inverse_products':{'left':old._encode_matrix(left),'right':old._encode_matrix(right)},
        'derivative_map':old._encode_matrix(derivative,True),'center_image':images,'root_enclosure':enclosures,
        'inclusion_margins':margins,'row_norm_upper':list(map(str,norms)),'contraction_norm_upper':str(max(norms))}


def _certificate_shape(c,b,maximum):
    old._certificate_shape(c,b)
    if type(c.get('preconditioned_polynomial')) is not list:raise p._Invalid('Complete collected polynomial required')
    if len(c['preconditioned_polynomial'])>maximum:raise p._Limit('MONOMIAL_BUDGET')


def _run(model,flow_box,certificate,*,max_leaves,max_terms,max_matrix_entries,max_monomials,
         max_work,max_rational_bits,max_input_bytes,max_certificate_bytes,checkpoint,checked):
    b=None
    try:
        if type(max_monomials) is not int or not 1<=max_monomials<=262144:raise p._Invalid('Invalid max_monomials')
        b=old._Budget(max_leaves,max_terms,max_matrix_entries,max_work,max_rational_bits,max_input_bytes,max_certificate_bytes,checkpoint)
        raw={'model':model,'flow_box':flow_box};old._shape(raw,b)
        if checked:_certificate_shape(certificate,b,max_monomials)
        input_root,frozen=p._snapshot(raw,b.input_bytes,b,'passive_input')
        m=_normalize(frozen,b)
        if checked:
            certificate_hash,packet=p._snapshot(certificate,b.certificate_bytes,b,'factorized_certificate')
            _certificate_shape(packet,b,max_monomials)
            fields={'center','term_evidence','center_residual','jacobian','preconditioner','inverse_witness',
                'preconditioned_polynomial','inverse_products','derivative_map','center_image','root_enclosure',
                'inclusion_margins','row_norm_upper','contraction_norm_upper','certificate_root'}
            if set(packet)!=set(m['header'])|fields:raise p._Invalid('Complete exact factorized certificate inventory required')
            old._equal({k:packet[k] for k in m['header']},m['header'],b,'Wrong factorized model/domain/method header')
            if type(packet['certificate_root']) is not str or not p._ROOT.fullmatch(packet['certificate_root']):raise p._Invalid('Malformed certificate root')
            if p._hash({k:v for k,v in packet.items() if k!='certificate_root'},b)!=packet['certificate_root']:raise p._Invalid('Certificate content root mismatch')
            if type(packet['center']) is not dict or set(packet['center'])!=set(m['leaves']):raise p._Invalid('Complete center required')
            center={i:p._q(packet['center'][i],b) for i in m['leaves']}
            if any(not m['box'][i][0]<v<m['box'][i][1] for i,v in center.items()):raise p._Invalid('Strictly interior center required')
            f,j=old._check_polynomial(m,center,packet['term_evidence'],b)
            old._equal(packet['center_residual'],{i:p._enc(v) for i,v in f.items()},b,'Wrong full center residual')
            old._equal(packet['jacobian'],old._encode_matrix(j,True),b,'Wrong full original Jacobian')
            r=old._read_matrix(packet['preconditioner'],len(m['leaves']),b)
            inverse=old._read_matrix(packet['inverse_witness'],len(m['leaves']),b)
            poly=_checker_polynomial(m,r,b,max_monomials)
            proof=_proof(m,center,r,inverse,poly,b,True)
            for key,value in proof.items():old._equal(packet[key],value,b,'Forged factorized proof field: '+key)
            old._admissible(proof,b)
            b.tick('factorized_verifier_complete');old._final(model,flow_box,input_root,b,certificate,certificate_hash)
            return {'status':'PASS','scope':SCOPE,'proof_complete':True,'certificate_root':packet['certificate_root'],
                'model_root':m['header']['model_root'],'query_root':m['header']['query_root'],'counts':deepcopy(m['header']['counts']),
                'root_enclosure':deepcopy(proof['root_enclosure']),'contraction_norm_upper':proof['contraction_norm_upper'],
                'limitations':deepcopy(old.LIMITATIONS),'work':b.used}
        center={i:b.div(b.add(*m['box'][i]),Q(2)) for i in m['leaves']}
        rows,f,j=old._produce_polynomial(m,center,b)
        mid=deepcopy(m);mid['coefficients']={a:(b.div(b.add(*v),Q(2)),)*2 for a,v in m['coefficients'].items()}
        mid['box']={i:(center[i],center[i]) for i in m['leaves']}
        _,_,point_j=old._produce_polynomial(mid,center,b)
        inverse=[[v[0] for v in row] for row in point_j];r=old._inverse(inverse,b)
        poly=_producer_polynomial(m,r,b,max_monomials);proof=_proof(m,center,r,inverse,poly,b,False)
        old._admissible(proof,b)
        packet={**m['header'],'center':{i:str(v) for i,v in center.items()},'term_evidence':rows,
            'center_residual':{i:p._enc(v) for i,v in f.items()},'jacobian':old._encode_matrix(j,True),
            'preconditioner':old._encode_matrix(r),'inverse_witness':old._encode_matrix(inverse),**proof}
        packet['certificate_root']=p._hash(packet,b);_certificate_shape(packet,b,max_monomials)
        p._hash(packet,b)  # The complete returned packet, including its root, must fit.
        b.tick('factorized_producer_complete');old._final(model,flow_box,input_root,b)
        return packet
    except (p._Invalid,p._Limit,old._NoProof,ValueError,TypeError,KeyError,OverflowError) as exc:
        return old._failure(exc,b,checked)


def compile_factorized_tree_pressure(model,flow_box,*,max_leaves=16,max_terms=128,max_matrix_entries=256,max_monomials=65536,
        max_work=2000000,max_rational_bits=4096,max_input_bytes=1048576,max_certificate_bytes=16777216,checkpoint=None):
    return _run(model,flow_box,None,max_leaves=max_leaves,max_terms=max_terms,max_matrix_entries=max_matrix_entries,
        max_monomials=max_monomials,max_work=max_work,max_rational_bits=max_rational_bits,max_input_bytes=max_input_bytes,
        max_certificate_bytes=max_certificate_bytes,checkpoint=checkpoint,checked=False)


def verify_factorized_tree_pressure(model,flow_box,certificate,*,max_leaves=16,max_terms=128,max_matrix_entries=256,max_monomials=65536,
        max_work=2000000,max_rational_bits=4096,max_input_bytes=1048576,max_certificate_bytes=16777216,checkpoint=None):
    return _run(model,flow_box,certificate,max_leaves=max_leaves,max_terms=max_terms,max_matrix_entries=max_matrix_entries,
        max_monomials=max_monomials,max_work=max_work,max_rational_bits=max_rational_bits,max_input_bytes=max_input_bytes,
        max_certificate_bytes=max_certificate_bytes,checkpoint=checkpoint,checked=True)
