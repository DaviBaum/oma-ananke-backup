"""Independent evidence-only reconstruction; no application admission authority."""
from copy import deepcopy
from decimal import Decimal, localcontext
from fractions import Fraction as Q
import hashlib
import json

LEAVES = ['sink-a', 'sink-b', 'sink-c']
NOMINAL = dict(zip(LEAVES, map(Q, ('3/1000', '3/2000', '1/1000'))))
K = {'tee-1': {'b': '1/5', 'branch': '3/10'}, 'tee-2': {'b': '1/4', 'branch': '2/5'}}
TOL = Q(1, 1_000_000)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def enc(lo, hi=None): return {'lower': str(lo), 'upper': str(lo if hi is None else hi)}
def interval(v): return Q(v['lower']), Q(v['upper'])
def add(a, b): return a[0]+b[0], a[1]+b[1]
def neg(a): return -a[1], -a[0]
def sub(a, b): return add(a, neg(b))
def mul(a, b):
    values = [x*y for x in a for y in b]
    return min(values), max(values)
def div(a, b):
    assert b[0] > 0
    return mul(a, (1/b[1], 1/b[0]))
def point(q): return Q(q), Q(q)
def square(a):
    assert a[0] >= 0
    return a[0]**2, a[1]**2
def rounded(a, digits=12):
    scale = 10**digits
    return Q((a[0]*scale).__floor__(), scale), Q((a[1]*scale).__ceil__(), scale)


def dyadic(a):
    scale = 2**40
    return Q((a[0]*scale).__floor__(), scale), Q((a[1]*scale).__ceil__(), scale)


def pi_bounds():
    # Independent rational Machin alternating-series enclosure, 48 terms.
    def atan(n):
        v = sum((Q((-1)**k, (2*k+1)*n**(2*k+1)) for k in range(48)), Q(0))
        w = v + Q(1, 97*n**97)
        return v, w
    return rounded(sub(mul(point(16), atan(5)), mul(point(4), atan(239))), 24)


def topology(spec):
    components = {c['id']: c for c in spec['components']}
    assert len(components) == len(spec['components']) == 7
    expected_ports = {(c['id'], s) for c in components.values() for s in c['ports']}
    assert len(expected_ports) == 16
    def endpoint(e): return e['component'], e['port']
    source = endpoint(spec['source'])
    leaves = {endpoint(s['endpoint']): s['id'] for s in spec['sinks']}
    assert len(leaves) == len(spec['sinks']) == 3 and set(leaves.values()) == set(LEAVES)
    links = {}; targets = set()
    for row in spec['connections']:
        a, b = endpoint(row['source']), endpoint(row['sink'])
        assert a in expected_ports and b in expected_ports and a not in links and b not in targets
        assert components[a[0]]['ports'][a[1]] == 'SOURCE' and components[b[0]]['ports'][b[1]] == 'SINK'
        links[a] = b; targets.add(b)
    assert len(links) == 6 and set(links) | targets | {source} | set(leaves) == expected_ports
    assert len(set(links) | targets | {source} | set(leaves)) == 2*len(links)+1+len(leaves)
    descendants = {}; outlet = {}; paths = {}; visiting = set(); completed = set()
    def visit(cid, prefix):
        assert cid not in visiting and cid not in completed
        visiting.add(cid); c = components[cid]
        assert c['ports']['a'] == 'SINK'
        assert c['kind'] in ('segment', 'elbow', 'tee')
        assert set(c['ports']) == ({'a','b','branch'} if c['kind']=='tee' else {'a','b'})
        all_leaves = []
        for slot in sorted(set(c['ports'])-{'a'}):
            ep = cid, slot
            step = {'component': cid, 'entry_port': 'a', 'exit_port': slot}
            if ep in leaves:
                child = [leaves[ep]]; paths[leaves[ep]] = prefix + [step]
            else:
                assert ep in links and links[ep][1] == 'a'
                child = visit(links[ep][0], prefix + [step])
            assert not set(all_leaves) & set(child)
            outlet[f'{cid}.{slot}'] = sorted(child); all_leaves += child
        visiting.remove(cid); completed.add(cid); descendants[cid] = sorted(all_leaves)
        return all_leaves
    assert source[1] == 'a' and set(visit(source[0], [])) == set(LEAVES)
    assert completed == set(components)
    assert len(spec['demand_paths']) == 3
    supplied = {p['sink_id']: p for p in spec['demand_paths']}
    assert set(supplied) == set(LEAVES) and len({p['demand_id'] for p in supplied.values()}) == 3
    assert all(supplied[k]['steps'] == paths[k] for k in LEAVES)
    return components, descendants, outlet, paths


def term_id(cid, slot, components): return f'{cid}:{slot}' if components[cid]['kind']=='tee' else cid


def nominal_declaration(spec):
    comps, desc, outlet, paths = topology(spec)
    coefficients_without_pi = {}; term_d = {}
    for cid, c in comps.items():
        if c['kind'] == 'tee':
            for slot, k in K[cid].items():
                coefficients_without_pi[f'{cid}:{slot}'] = Q(80_000_000)*Q(k)
                term_d[f'{cid}:{slot}'] = desc[cid]
        else:
            start, end = c['geometry']['start_m'], c['geometry']['end_m']
            # Existing fixture is orthogonal: exact nominal length from one coordinate.
            delta = [abs(Q(str(b))-Q(str(a))) for a,b in zip(start,end)]
            assert sum(x != 0 for x in delta) == 1
            coefficients_without_pi[cid] = Q(80_000_000)*Q(1,50)*sum(delta)/Q(1,10)
            term_d[cid] = desc[cid]
    path_c = {}
    for leaf, path in paths.items():
        path_c[leaf] = sum((coefficients_without_pi[term_id(p['component'],p['exit_port'],comps)] *
            sum(NOMINAL[x] for x in term_d[term_id(p['component'],p['exit_port'],comps)])**2 for p in path), Q(0))
    assert path_c == {'sink-a':Q(6142,5),'sink-b':Q(1185),'sink-c':Q(1244)}
    p2 = square(pi_bounds())
    sink = {leaf: enc(*rounded(sub(point(200), div(point(value), p2)), 6)) for leaf,value in path_c.items()}
    boundary = {'schema':'oma.coupled-tree-boundary/1','source_total_pressure_pa':enc(Q(200)),
        'sink_total_pressures_pa':sink,'minimum_sink_flows_m3_s':dict(zip(LEAVES,('1/400','3/2500','1/1250'))),
        'flow_search_box_m3_s':{k:enc(v-Q(1,100000),v+Q(1,100000)) for k,v in NOMINAL.items()},
        'density_kg_m3':'1000','darcy_friction':'1/50','maximum_velocity_m_s':'2','gravity_m_s2':'9.80665',
        'elbow_loss_coefficient':'1/5','tee_outlet_loss_coefficients':deepcopy(K),
        'applicability':'New hypothetical ideal steady incompressible bore model. Each tee outlet has its own strictly positive TOTAL loss coefficient referenced to full inlet flow. Internal tee distributed loss is included; no tee skeleton Darcy term. Existing common-loss missions are unchanged.',
        'boundary_control_assumption':'Hypothetical regulated total-pressure intervals at the four physical boundary caps, manufactured from declared rational positive nominal leaf flows before native checks.',
        'pressure_reference':'TOTAL_PRESSURE_P_PLUS_KINETIC_EXCLUDING_ELEVATION','loss_model':'FIXED_COEFFICIENT_STEADY_INCOMPRESSIBLE',
        'hydraulic_section_interpretation':'IDEAL_CIRCULAR_BORE_FROM_NATIVE_ENVELOPE_MINUS_DECLARED_INSULATION',
        'friction_convention':'DARCY','elbow_loss_reference':'EXCESS_LOCAL_LOSS_EXCLUDING_CURVED_PIPE_FRICTION',
        'tee_loss_reference':'OUTLET_SPECIFIC_TOTAL_LOSS_AT_TOTAL_INLET_FLOW',
        'connection_model':'NO_EXTRA_LOSS_AT_CHECKED_MATCHING_CONNECTED_CAPS','boundary_loss_scope':'BETWEEN_PHYSICAL_NETWORK_PORTS_ONLY'}
    manufactured = {'nominal_leaf_flows_m3_s':{k:str(v) for k,v in NOMINAL.items()},
        'nominal_bore_m':'1/10','nominal_insulation_m':'1/50','nominal_area_m2':'pi/400',
        'nominal_source_total_pressure_pa':'200','nominal_boundary_elevation_m':'3',
        'coefficient_without_pi_squared':{k:str(v) for k,v in coefficients_without_pi.items()},
        'sink_pressure_expression':{k:{'rational_offset':'200','negative_pi_inverse_square_coefficient':str(v)} for k,v in path_c.items()},
        'sink_pressure_bracket_method':'Exact 48-term Machin alternating bounds rounded outward to 1e-6 Pa',
        'pi_interval':enc(*pi_bounds()),'scope':'Exact manufactured nominal symbolic point plus rational outward regulator intervals; not native uncertainty or global uniqueness.'}
    return boundary, manufactured


def metrics_from_native(spec, evidence):
    from oma.routing.network_scenario import NetworkDesign
    parts = evidence['semantics']['parts']; ports = evidence['semantics']['ports']
    p = {(r['component_id'],r['slot']):r for r in ports}
    assert len(p)==len(ports)==16 and len(parts)==7 and len({r['component_id'] for r in parts})==7
    components = {}
    for r in parts:
        cid=r['component_id']; length=Q(str(r['length_m'])); radius=Q(str(r['radius_m']))
        components[cid]={'length_m':enc(length-TOL,length+TOL),'outer_radius_m':enc(radius-TOL,radius+TOL),
            'ports':{slot:{'position_m':[enc(Q(str(v))-TOL,Q(str(v))+TOL) for v in p[cid,slot]['position_m']]} for slot in r['caps']}}
    return {'schema':'oma.coupled-tree-native-metrics/1','network_root':digest(NetworkDesign.model_validate(spec).model_dump(mode='json',by_alias=True)),
        'native_evidence_root':digest(evidence),'components':components}


def derive_reference(spec, boundary, metrics, context):
    from oma.optimization.coupled_tree_pressure import MODEL_SCHEMA, MODEL_ASSUMPTIONS
    comps, desc, outlet, paths = topology(spec)
    assert set(metrics['components'])==set(comps)
    rho=Q(boundary['density_kg_m3']); f=Q(boundary['darcy_friction']); g=Q(boundary['gravity_m_s2'])
    sections={}; terms=[]; coeffs={}; metadata={}
    for cid,c in comps.items():
        m=metrics['components'][cid]
        assert set(m['ports'])==set(c['ports'])
        rad=interval(m['outer_radius_m']); length=interval(m['length_m']); ins=Q(str(c['insulation_m']))
        diameter=mul(point(2),sub(rad,point(ins))); assert diameter[0]>0 and length[0]>0
        area=mul(pi_bounds(),mul(square(diameter),point(Q(1,4))))
        sections[cid]={'diameter_m':enc(*diameter),'area_m2':enc(*rounded(area,24)),
            'outer_radius_m':m['outer_radius_m'],'length_m':m['length_m'],'declared_insulation_m':str(ins)}
        for slot in sorted(set(c['ports'])-{'a'}):
            tid=term_id(cid,slot,comps)
            if c['kind']=='tee':
                loss=point(boundary['tee_outlet_loss_coefficients'][cid][slot]); applicable=outlet[f'{cid}.{slot}']
            else:
                loss=add(mul(point(f),div(length,diameter)),point(boundary['elbow_loss_coefficient'] if c['kind']=='elbow' else 0))
                applicable=desc[cid]
            a=div(mul(point(rho),loss),mul(point(2),square(area)))
            coeffs[tid]=enc(*dyadic(a))
            terms.append({'id':tid,'coefficient_id':tid,'descendant_leaves':desc[cid],'applies_to_leaves':applicable})
            metadata[tid]={'component_id':cid,'outlet_slot':slot,'kind':c['kind'],
                'hydraulic_inlet_descendants':desc[cid],'applies_to_leaves':applicable,
                'coefficient_units':'Pa*s^2/m^6','tee_skeleton_darcy_charged':False,
                'loss_factor':enc(*loss),'exact_coefficient_bounds':enc(*a),'coefficient_outward_rounding':'2^-40 Pa*s^2/m^6'}
    src=spec['source']; zsrc=interval(metrics['components'][src['component']]['ports'][src['port']]['position_m'][2])
    heads={}
    for sink in spec['sinks']:
        e=sink['endpoint']; z=interval(metrics['components'][e['component']]['ports'][e['port']]['position_m'][2])
        heads[sink['id']]=enc(*dyadic(add(sub(interval(boundary['source_total_pressure_pa']),interval(boundary['sink_total_pressures_pa'][sink['id']])),mul(point(rho*g),sub(zsrc,z)))))
    port_map={}
    for cid,c in comps.items():
        for slot in c['ports']:
            # A source-to-leaf path uniquely determines each visited prefix, including tee inlet.
            candidates=[]
            for path in paths.values():
                prefix=[]
                for step in path:
                    if step['component']==cid:
                        if slot=='a': candidates.append(prefix[:])
                        elif slot==step['exit_port']: candidates.append(prefix+[term_id(cid,slot,comps)])
                    prefix.append(term_id(step['component'],step['exit_port'],comps))
            assert candidates and all(x==candidates[0] for x in candidates)
            d=desc[cid] if slot=='a' else outlet[f'{cid}.{slot}']
            port_map[f'{cid}.{slot}']={'component_id':cid,'slot':slot,'flow_direction':c['ports'][slot],
                'forward_flow_leaf_coefficients':{leaf:1 for leaf in d},'outward_flow_sign':-1 if slot=='a' else 1,
                'total_head_loss_terms':candidates[0], 'total_head_relation':'H_source - sum a_t*(sum descendant q)^2',
                'total_pressure_relation':'H_port - rho*g*z_port','position_m':metrics['components'][cid]['ports'][slot]['position_m']}
    identities=[]
    for cid,c in comps.items():
        identities.append({'id':'component:'+cid,'port_coefficients':{f'{cid}.{slot}':1 if slot=='a' else -1 for slot in c['ports']},'external_coefficients':{}})
    for index,connection in enumerate(spec['connections']):
        a,b=connection['source'],connection['sink']; x=f"{a['component']}.{a['port']}"; y=f"{b['component']}.{b['port']}"
        assert port_map[x]['total_head_loss_terms']==port_map[y]['total_head_loss_terms']
        identities.append({'id':f'connection:{index}','port_coefficients':{x:1,y:-1},'external_coefficients':{}})
    identities.append({'id':'source','port_coefficients':{f"{src['component']}.{src['port']}":-1},'external_coefficients':{leaf:1 for leaf in LEAVES}})
    for sink in spec['sinks']:
        e=sink['endpoint'];identities.append({'id':sink['id'],'port_coefficients':{f"{e['component']}.{e['port']}":-1},'external_coefficients':{sink['id']:1}})
    for row in identities:
        residual={leaf:row['external_coefficients'].get(leaf,0)+sum(a*port_map[p]['forward_flow_leaf_coefficients'].get(leaf,0) for p,a in row['port_coefficients'].items()) for leaf in LEAVES}
        assert all(v==0 for v in residual.values());row['exact_leaf_residual']=residual
    singletons={leaf:[t['id'] for t in terms if t['descendant_leaves']==t['applies_to_leaves']==[leaf] and metadata[t['id']]['kind']!='tee' and Q(coeffs[t['id']]['lower'])>0] for leaf in LEAVES}
    assert all(singletons.values())
    physical={'network_root':metrics['network_root'],'metrics_root':digest(metrics),'boundary_root':digest(boundary),'context_root':digest(context),
        'sections':sections,'term_metadata':metadata,'paths':paths,'ports':port_map,'continuity':identities,'positive_singleton_leaf_terms':singletons}
    model={'schema':MODEL_SCHEMA,'leaves':LEAVES[:],'coefficients':coeffs,'terms':terms,'available_heads':heads,
        'context_root':digest(context),'physical_model_root':digest(physical),'assumptions':deepcopy(MODEL_ASSUMPTIONS)}
    return {'schema':'oma.unequal-tee-native-reference/1','physical':physical,'model':model,
        'limits':{'global_uniqueness':False,'native_application_integration':False,'accepted_project':False,'internal_bore_measured':False,
            'conditional_native_metric_policy':'Measured native dimensions and all cap positions enlarged by 1 micrometre; locally trusted conversion and numerical policy, not interval-certified native geometry.',
            'parameter_scope':'Cartesian coefficient/head box contains all declared primitive parameter tuples; dependency relaxation can widen the enclosure. Each true primitive tuple maps to the SAME coefficient/head tuple for all equations.'}}


def check_reference(spec,boundary,metrics,context,packet):
    """Separate path-based inventory/formula replay, not a native signature check."""
    from oma.routing.network_scenario import NetworkDesign
    try:
        assert metrics['network_root']==digest(NetworkDesign.model_validate(spec).model_dump(mode='json',by_alias=True))
        physical=packet['physical'];model=packet['model']; comps={c['id']:c for c in spec['components']}
        assert len(comps)==len(spec['components'])==7
        paths={p['sink_id']:p['steps'] for p in spec['demand_paths']}
        assert len(paths)==len(spec['demand_paths'])==3 and set(paths)==set(LEAVES)
        assert physical['paths']==paths
        assert set(physical['sections'])==set(comps)==set(metrics['components'])
        assert physical['network_root']==metrics['network_root'] and physical['metrics_root']==digest(metrics)
        assert physical['boundary_root']==digest(boundary) and physical['context_root']==digest(context)
        assert model['context_root']==digest(context) and model['physical_model_root']==digest(physical)
        observed={}; coefficients={}; required_ports={}; expected_prefix={}
        for leaf,path in paths.items():
            prefix=[]
            for step in path:
                cid,slot=step['component'],step['exit_port'];c=comps[cid];tid=term_id(cid,slot,comps)
                observed.setdefault(tid,{'d':set(),'a':set(),'cid':cid,'slot':slot})['a'].add(leaf)
                expected_prefix.setdefault(f'{cid}.a',prefix[:]);assert expected_prefix[f'{cid}.a']==prefix
                prefix=prefix+[tid];expected_prefix[f'{cid}.{slot}']=prefix[:]
                required_ports.setdefault(f'{cid}.a',set()).add(leaf);required_ports.setdefault(f'{cid}.{slot}',set()).add(leaf)
        for tid,row in observed.items():
            cid=row['cid'];c=comps[cid];m=metrics['components'][cid]
            row['d']={leaf for leaf,path in paths.items() if any(s['component']==cid for s in path)}
            r0,r1=interval(m['outer_radius_m']);l0,l1=interval(m['length_m']);ins=Q(str(c['insulation_m']))
            d0,d1=2*(r0-ins),2*(r1-ins);assert d0>0 and l0>0
            pi0,pi1=pi_bounds();a0,a1=pi0*d0*d0/4,pi1*d1*d1/4
            rho=Q(boundary['density_kg_m3']);f=Q(boundary['darcy_friction'])
            if c['kind']=='tee':
                k=Q(boundary['tee_outlet_loss_coefficients'][cid][row['slot']]);factor=(k,k)
            else:
                k=Q(boundary['elbow_loss_coefficient']) if c['kind']=='elbow' else Q(0)
                factor=f*l0/d1+k,f*l1/d0+k
            coefficients[tid]=enc(*dyadic((rho*factor[0]/(2*a1*a1),rho*factor[1]/(2*a0*a0))))
            section=physical['sections'][cid]
            assert section=={'diameter_m':enc(d0,d1),'area_m2':enc(*rounded((a0,a1),24)),
                'outer_radius_m':m['outer_radius_m'],'length_m':m['length_m'],'declared_insulation_m':str(ins)}
            expected_meta={'component_id':cid,'outlet_slot':row['slot'],'kind':c['kind'],'hydraulic_inlet_descendants':sorted(row['d']),
                'applies_to_leaves':sorted(row['a']),'coefficient_units':'Pa*s^2/m^6','tee_skeleton_darcy_charged':False,
                'loss_factor':enc(*factor),'exact_coefficient_bounds':enc(rho*factor[0]/(2*a1*a1),rho*factor[1]/(2*a0*a0)),'coefficient_outward_rounding':'2^-40 Pa*s^2/m^6'}
            assert physical['term_metadata'][tid]==expected_meta
        actual={t['id']:t for t in model['terms']};assert len(actual)==len(model['terms'])==9
        assert set(actual)==set(observed)==set(model['coefficients'])==set(physical['term_metadata'])
        assert coefficients==model['coefficients']
        for tid,row in observed.items():
            assert actual[tid]=={'id':tid,'coefficient_id':tid,'descendant_leaves':sorted(row['d']),'applies_to_leaves':sorted(row['a'])}
        assert len(required_ports)==16 and set(required_ports)==set(physical['ports'])
        for pid,leaves in required_ports.items():
            cid,slot=pid.rsplit('.',1);p=physical['ports'][pid]
            assert p=={'component_id':cid,'slot':slot,'flow_direction':comps[cid]['ports'][slot],
                'forward_flow_leaf_coefficients':{leaf:1 for leaf in sorted(leaves)},'outward_flow_sign':-1 if slot=='a' else 1,
                'total_head_loss_terms':expected_prefix[pid],'total_head_relation':'H_source - sum a_t*(sum descendant q)^2',
                'total_pressure_relation':'H_port - rho*g*z_port','position_m':metrics['components'][cid]['ports'][slot]['position_m']}
        # Complete equation identities are independently built from the direct graph boundary.
        expected=[]
        for cid,c in comps.items():expected.append(('component:'+cid,{f'{cid}.{s}':1 if s=='a' else -1 for s in c['ports']},{}))
        for i,r in enumerate(spec['connections']):
            ids=[f"{r[k]['component']}.{r[k]['port']}" for k in ('source','sink')]
            assert expected_prefix[ids[0]]==expected_prefix[ids[1]]
            expected.append((f'connection:{i}',{ids[0]:1,ids[1]:-1},{}))
        src=spec['source'];expected.append(('source',{f"{src['component']}.{src['port']}":-1},{leaf:1 for leaf in LEAVES}))
        for sink in spec['sinks']:
            ep=sink['endpoint'];expected.append((sink['id'],{f"{ep['component']}.{ep['port']}":-1},{sink['id']:1}))
        assert len(expected)==len(physical['continuity'])==17
        assert len({r['id'] for r in physical['continuity']})==17
        for given,(ident,ports,external) in zip(physical['continuity'],expected):
            residual={leaf:external.get(leaf,0)+sum(v*(leaf in required_ports[p]) for p,v in ports.items()) for leaf in LEAVES}
            assert all(x==0 for x in residual.values())
            assert given=={'id':ident,'port_coefficients':ports,'external_coefficients':external,'exact_leaf_residual':residual}
        for leaf in LEAVES:
            assert physical['positive_singleton_leaf_terms'][leaf]==[tid for tid,row in observed.items() if row['d']==row['a']=={leaf} and comps[row['cid']]['kind']!='tee' and Q(coefficients[tid]['lower'])>0]
            assert physical['positive_singleton_leaf_terms'][leaf]
        zsrc=interval(metrics['components'][src['component']]['ports'][src['port']]['position_m'][2])
        for sink in spec['sinks']:
            ep=sink['endpoint'];z=interval(metrics['components'][ep['component']]['ports'][ep['port']]['position_m'][2])
            ps=interval(boundary['source_total_pressure_pa']);pt=interval(boundary['sink_total_pressures_pa'][sink['id']]);rg=Q(boundary['density_kg_m3'])*Q(boundary['gravity_m_s2'])
            assert model['available_heads'][sink['id']]==enc(*dyadic((ps[0]-pt[1]+rg*(zsrc[0]-z[1]),ps[1]-pt[0]+rg*(zsrc[1]-z[0]))))
        return {'status':'PASS','terms':9,'components':7,'ports':16,'continuity_identities':17,'positive_singleton_leaf_terms':3,
            'scope':'Independent reference mapping and exact coefficient replay; native authenticity rests on separately retained fresh native evidence.'}
    except (AssertionError,KeyError,ValueError,TypeError,ZeroDivisionError):return {'status':'FAIL'}


def nominal_oracle(spec,boundary,manufactured,packet):
    with localcontext() as ctx:
        ctx.prec=85
        def dec(q):q=Q(q);return Decimal(q.numerator)/Decimal(q.denominator)
        pi=Decimal('3.141592653589793238462643383279502884197169399375105820974944592307816406286208998628')
        coeff={k:dec(v)/(pi*pi) for k,v in manufactured['coefficient_without_pi_squared'].items()}
        terms={t['id']:t for t in packet['model']['terms']};drops={}
        for tid,a in coeff.items():drops[tid]=a*dec(sum(NOMINAL[x] for x in terms[tid]['descendant_leaves']))**2
        ports={};rho=dec(boundary['density_kg_m3']);g=dec(boundary['gravity_m_s2']);hs=Decimal(200)+rho*g*3
        for pid,row in packet['physical']['ports'].items():
            flow=sum((NOMINAL[k]*a for k,a in row['forward_flow_leaf_coefficients'].items()),Q(0))
            head=hs-sum((drops[t] for t in row['total_head_loss_terms']),Decimal(0))
            ports[pid]={'forward_flow_m3_s':str(flow),'outward_flow_m3_s':str(flow*row['outward_flow_sign']),
                'total_head_pa':str(head),'total_pressure_pa':str(head-rho*g*3),'velocity_m_s':str(dec(flow)/(pi/400))}
        sink_closure={}
        for sink in spec['sinks']:
            ep=sink['endpoint'];p=Decimal(ports[f"{ep['component']}.{ep['port']}"]['total_pressure_pa'])
            c=manufactured['sink_pressure_expression'][sink['id']]
            expected=dec(c['rational_offset'])-dec(c['negative_pi_inverse_square_coefficient'])/(pi*pi)
            residual=p-expected;assert abs(residual)<Decimal('1e-78')
            lo,hi=interval(boundary['sink_total_pressures_pa'][sink['id']]);assert dec(lo)<=p<=dec(hi)
            sink_closure[sink['id']]={'nominal_total_pressure_pa':str(p),'residual_pa':str(residual)}
        assert len(ports)==16 and all(Decimal(p['velocity_m_s'])<Decimal(2) for p in ports.values())
        return {'status':'PASS','precision_digits':85,'port_count':16,'term_count':9,'ports':ports,
            'term_loss_pa':{k:str(v) for k,v in drops.items()},'sink_closure':sink_closure,
            'scope':'Independent nominal symbolic manufactured flow and 85-digit pressure/velocity oracle only; no interval or global uniqueness claim.'}
