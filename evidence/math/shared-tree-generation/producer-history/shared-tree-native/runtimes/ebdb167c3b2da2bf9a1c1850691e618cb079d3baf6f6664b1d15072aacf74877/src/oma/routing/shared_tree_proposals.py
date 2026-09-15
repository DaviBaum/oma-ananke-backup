"""Bounded endpoint-directed connector catalogues; proposals have no native authority."""
from fractions import Fraction as Q
from itertools import permutations, product
import json
import math
import re

from oma.store import digest
from oma.optimization.fabrication import compile_orthogonal_fabrication, verify_orthogonal_fabrication
from oma.routing.scenario import RoutingScenario
from oma.routing.network_scenario import NetworkDesign, SharedNetworkScenario

SCHEMA = 'oma.shared-tree-native-search/1'
LIMITATIONS = {
    'continuous_or_all_topologies_complete': False,
    'native_geometry_or_service_checked': False,
    'nominal_cost_is_native_lower_bound': False,
    'physical_infeasibility_from_empty_catalogue': False,
    'candidate_acceptance_authority': False,
    'coordinates': 'EXACT_BINARY64_REPRESENTABLE_DYADIC_PROPOSAL_GEOMETRY',
}


class _Unavailable(ValueError): pass
class _CallerError(BaseException):
    def __init__(self, original): self.original=original


def _call(checkpoint, stage):
    if checkpoint:
        try: checkpoint(stage)
        except BaseException as exc: raise _CallerError(exc) from exc


class _Budget:
    def __init__(self, maximum, checkpoint):
        if type(maximum) is not int or not 1 <= maximum <= 2_000_000:
            raise ValueError('Work budget must be an integer from1 to2000000')
        self.maximum, self.work, self.checkpoint = maximum, 0, checkpoint

    def use(self, count=1):
        self.work += count
        if self.work > self.maximum: raise _Unavailable('WORK_BUDGET')
        if self.work % 128 == 0: _call(self.checkpoint,'shared_tree_connectors')


def _snapshot(value, budget, max_bytes):
    todo=[(value,0)]; items=0
    while todo:
        item,depth=todo.pop(); budget.use(); items+=1
        if depth>32 or items>40_000: raise _Unavailable('INPUT_STRUCTURE_BUDGET')
        if isinstance(item,dict):
            if any(type(k) is not str for k in item): raise ValueError('String JSON keys required')
            if len(item)>4096: raise _Unavailable('INPUT_STRUCTURE_BUDGET')
            todo.extend((v,depth+1) for v in item.values())
        elif isinstance(item,(list,tuple)):
            if len(item)>4096: raise _Unavailable('INPUT_STRUCTURE_BUDGET')
            todo.extend((v,depth+1) for v in item)
        elif type(item) is str:
            if len(item)>65536: raise _Unavailable('INPUT_STRING_BUDGET')
        elif item is not None and type(item) not in (int,float,bool): raise ValueError('JSON input required')
        elif type(item) is int and item.bit_length()>512: raise _Unavailable('INTEGER_BUDGET')
        elif type(item) is float and not math.isfinite(item): raise ValueError('Finite JSON numbers required')
    encoded=json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)
    if len(encoded.encode())>max_bytes: raise _Unavailable('INPUT_BYTE_BUDGET')
    return json.loads(encoded)


def _q(value):
    if type(value) not in (str,int,float) or (isinstance(value,str) and len(value)>256):
        raise ValueError('Bounded finite rational required')
    if type(value) is float and not math.isfinite(value): raise ValueError('Finite rational required')
    result=Q(value)
    if max(result.numerator.bit_length(),result.denominator.bit_length())>128:
        raise _Unavailable('RATIONAL_BUDGET')
    return result


def _binary(q):
    q=_q(q) if not isinstance(q,Q) else q
    result=float(q)
    if not math.isfinite(result) or Q(result)!=q: raise _Unavailable('NONREPRESENTABLE_NATIVE_COORDINATE')
    return result


def _point(p):
    if not isinstance(p,(list,tuple)) or len(p)!=3: raise ValueError('Three coordinates required')
    result=tuple(_q(x) for x in p)
    if any(abs(x)>1_000_000 for x in result): raise _Unavailable('COORDINATE_DOMAIN')
    return result


def _axis(p):
    if not isinstance(p,(list,tuple)) or len(p)!=3 or any(type(x) is not int for x in p):
        raise ValueError('Exact signed integer axis required')
    if sum(abs(x) for x in p)!=1: raise ValueError('Axis must have one signed unit entry')
    return tuple(p)


def _identifier(value):
    if type(value) is not str or not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}',value):
        raise ValueError('Bounded catalogue identifier without colon required')
    return value


def _add(a,b,s=1): return tuple(x+s*y for x,y in zip(a,b))
def _cross(a,b): return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def _qp(p): return list(map(str,p))
def _fp(p): return list(map(_binary,p))
def _cap(position,direction): return {'position_m':_qp(position),'flow_direction':list(direction)}


def _simplify(points):
    out=[]
    for point in points:
        if out and out[-1]==point: continue
        out.append(point)
        while len(out)>=3:
            a,b,c=out[-3:];u=_add(b,a,-1);v=_add(c,b,-1)
            if _cross(u,v)==(0,0,0) and sum(x*y for x,y in zip(u,v))>0:
                out.pop(-2)
            else: break
    return out


def _direction(a,b):
    d=_add(b,a,-1);nz=[x for x in d if x]
    if len(nz)!=1: raise ValueError('Nonzero orthogonal segment required')
    return tuple(int(x/abs(nz[0])) for x in d)


def connector_templates(start,end,start_direction,end_direction,stub_lengths,detour_planes):
    """Enumerate a finite authored template language, not all possible polylines."""
    p,q=_point(start),_point(end);u,v=_axis(start_direction),_axis(end_direction)
    stubs=[_q(x) for x in stub_lengths]
    if not 1<=len(stubs)<=4 or any(x<=0 for x in stubs): raise ValueError('One to four positive stubs required')
    if len(detour_planes)>8: raise _Unavailable('PLANE_BUDGET')
    planes=[]
    for plane in detour_planes:
        if set(plane)!={'axis','value_m'} or type(plane['axis']) is not int or plane['axis'] not in (0,1,2):
            raise ValueError('Exact detour axis/value required')
        planes.append((plane['axis'],_q(plane['value_m'])))
    candidates=[(p,q)]
    for lead,tail in product(stubs,repeat=2):
        a,b=_add(p,u,lead),_add(q,v,-tail)
        for plane in [None,*planes]:
            aa,bb=list(a),list(b)
            if plane is not None: aa[plane[0]]=bb[plane[0]]=plane[1]
            aa,bb=tuple(aa),tuple(bb)
            axes=[i for i in range(3) if aa[i]!=bb[i]]
            for order in permutations(axes):
                middle=[aa];cursor=list(aa)
                for axis in order: cursor[axis]=bb[axis];middle.append(tuple(cursor))
                candidates.append((p,a,*middle,b,q))
    seen=set()
    for raw in candidates:
        points=_simplify(raw)
        if len(points)<2: continue
        try:
            if _direction(points[0],points[1])!=u or _direction(points[-2],points[-1])!=v: continue
            for a,b in zip(points,points[1:]):_direction(a,b)
        except ValueError:continue
        key=tuple(points)
        if key not in seen:seen.add(key);yield points


def _fabrication_scenario(requirements,start,end):
    return RoutingScenario.model_validate({
        'start':_fp(start),'end':_fp(end),'diameter_m':requirements['diameter_m'],
        'insulation_m':requirements['insulation_m'],'clearance_m':requirements['clearance_m'],
        'bend_radius_m':requirements['minimum_bend_radius_m'],'minimum_straight_m':requirements['minimum_straight_m'],
        'allowed_zone':requirements['allowed_zone'],'system_type':requirements['system_type'],
        'scenario_terminals':True,'target_modality':'LOCAL_GEOMETRIC_COORDINATION',
        'source_representation_policy':requirements['source_representation_policy']})


def _physical_components(certificate,connector_id,requirements):
    components=[]
    for index,part in enumerate(certificate['components']):
        common={'id':f'{connector_id}-p{index}','kind':part['kind'],'system_type':requirements['system_type'],
            'diameter_m':requirements['diameter_m'],'insulation_m':requirements['insulation_m'],
            'ports':{'a':'SINK','b':'SOURCE'}}
        geometry={'start_m':_fp(_point(part['start'])),'end_m':_fp(_point(part['end']))}
        if part['kind']=='elbow':
            geometry.update(center_m=_fp(_point(part['center'])),normal=_fp(_point(part['normal'])),
                bend_radius_m=_binary(_q(part['bend_radius_m'])),angle_rad=math.pi/2)
        common['geometry']=geometry;components.append(common)
    return components


def _cost(certificate,weights):
    length=sum((_q(p['length_m']) for p in certificate['components'] if p['kind']=='segment'),Q(0))
    pi=sum((_q(p['length_pi_m']) for p in certificate['components'] if p['kind']=='elbow'),Q(0))
    fittings=sum(p['kind']=='elbow' for p in certificate['components'])
    return [str(weights[0]*length+weights[1]*fittings),str(weights[0]*pi)]


def build_connector_catalogue(requirements,search,*,context,max_work=250_000,max_bytes=2_097_152,checkpoint=None):
    """Build exact nominal macros from finite tee sites and directed terminal templates."""
    budget=_Budget(max_work,checkpoint)
    try:
        if type(max_bytes) is not int or not 1024<=max_bytes<=16_777_216: raise ValueError('Invalid input byte bound')
        originals={'requirements':requirements,'search':search,'context':context}
        snapshot=_snapshot(originals,budget,max_bytes);input_root=digest(snapshot)
        r,s,c=(snapshot[k] for k in ('requirements','search','context'))
        if 'network_alternatives' in r: raise ValueError('Search input supplies requirements, not complete network alternatives')
        if set(s)!={'schema','source_direction','sink_directions','tee_instances','stub_lengths_m','detour_planes'} or s['schema']!=SCHEMA:
            raise ValueError('Complete exact search schema required')
        if any(r.get(k) is not None for k in ('pressure_driven','passive_tree','coupled_tree')):
            raise _Unavailable('GENERATED_PRESSURE_TEE_IDENTITY_PROFILE_NOT_IMPLEMENTED')
        if not isinstance(c,dict) or not c: raise ValueError('Current source/application context required')
        sinks=r['sinks']
        if not isinstance(sinks,list) or len(sinks) not in (2,3): raise ValueError('Two or three fixed sinks required')
        sink_ids=[_identifier(x['id']) for x in sinks]
        if len(set(sink_ids))!=len(sink_ids) or set(s['sink_directions'])!=set(sink_ids):raise ValueError('Complete unique sink directions required')
        tees=s['tee_instances']
        if not isinstance(tees,list) or not 1<=len(tees)<=8:raise _Unavailable('TEE_INSTANCE_BUDGET')
        source={'id':'source','cap':_cap(_point(r['start_m']),_axis(s['source_direction']))}
        terminal_rows=[{'id':x['id'],'demand_id':_identifier(x['demand_id']),
            'cap':_cap(_point(x['end_m']),_axis(s['sink_directions'][x['id']]))} for x in sinks]
        weights=tuple(_q(r.get('objective_weights',{'length_m':1}).get(k,0)) for k in ('length_m','fitting_count'))
        if any(w<0 for w in weights) or not any(weights):raise ValueError('Nonnegative nonzero cost policy required')
        section={'diameter_m':str(_q(r['diameter_m'])),'insulation_m':str(_q(r['insulation_m']))}
        nodes={'source':{'out':source['cap']}}
        nodes.update({x['id']:{'in':x['cap']} for x in terminal_rows})
        tee_rows=[];tee_components={}
        for tee in tees:
            budget.use()
            if set(tee)!={'id','center_m','axis_x','axis_y','trunk_takeout_m','branch_takeout_m'}:raise ValueError('Exact tee site fields required')
            identity=_identifier(tee['id'])
            if identity in nodes:raise ValueError('Node identities must be globally unique')
            center=_point(tee['center_m']);x,y=_axis(tee['axis_x']),_axis(tee['axis_y']);z=_cross(x,y)
            if sum(abs(v) for v in z)!=1:raise ValueError('Tee axes must be perpendicular')
            trunk,branch=_q(tee['trunk_takeout_m']),_q(tee['branch_takeout_m'])
            frame=[[x[i],y[i],z[i],_binary(center[i])] for i in range(3)]+[[0,0,0,1]]
            component={'id':identity,'kind':'tee','system_type':r['system_type'],'diameter_m':r['diameter_m'],
                'insulation_m':r['insulation_m'],'ports':{'a':'SINK','b':'SOURCE','branch':'SOURCE'},
                'geometry':{'frame_m':frame,'trunk_takeout_m':_binary(trunk),'branch_takeout_m':_binary(branch)}}
            from oma.routing.network_scenario import Tee
            Tee.model_validate(component)
            caps={'a':_cap(_add(center,x,-trunk),x),'b':_cap(_add(center,x,trunk),x),'branch':_cap(_add(center,y,branch),y)}
            for cap in caps.values():_fp(_point(cap['position_m']))
            nodes[identity]=caps;tee_components[identity]=component
            tee_rows.append({**tee,'center_m':_qp(center),'trunk_takeout_m':str(trunk),'branch_takeout_m':str(branch),
                'catalogue_root':digest(component),'loss_contract_root':digest(r.get('physics')),
                'nominal_cost':[str(weights[0]*(2*trunk+branch)+weights[1]),'0']})
        outgoing=[('source','out')]+[(t['id'],port) for t in tee_rows for port in ('b','branch')]
        incoming=[(t['id'],'a') for t in tee_rows]+[(t['id'],'in') for t in terminal_rows]
        connectors=[];macros={};attempts=[]
        for start,end in product(outgoing,incoming):
            budget.use()
            if start[0]==end[0] or (start[0]=='source' and end[1]=='in'):continue
            a,b=nodes[start[0]][start[1]],nodes[end[0]][end[1]]
            for points in connector_templates(a['position_m'],b['position_m'],a['flow_direction'],b['flow_direction'],s['stub_lengths_m'],s['detour_planes']):
                budget.use(1+len(points));path=[_qp(p) for p in points]
                definition={'from':{'node':start[0],'port':start[1]},'to':{'node':end[0],'port':end[1]},'points_m':path}
                identity='connector-'+digest(definition)[:24]
                if identity in macros:continue
                try:
                    for point in points:_fp(point)
                    scenario=_fabrication_scenario(r,points[0],points[-1])
                    cert=compile_orthogonal_fabrication(scenario,path,context_root=input_root,max_points=16)
                    checked=verify_orthogonal_fabrication(scenario,path,cert,context_root=input_root,max_points=16)
                    budget.use(len(json.dumps(cert))//64+1)
                    if checked['status']!='PASS' or cert['status']!='PASS':
                        attempts.append({**definition,'status':'NOMINAL_TEMPLATE_NOT_ADMITTED','certificate':cert,'check':checked});continue
                    parts=_physical_components(cert,identity,r)
                    geometry={'points_m':path,'components':parts}
                    row={'id':identity,'from':definition['from'],'to':definition['to'],'start_cap':a,'end_cap':b,
                        'section':section,'geometry_root':digest(geometry),'fabrication_root':cert['certificate_root'],'nominal_cost':_cost(cert,weights)}
                    macros[identity]={'geometry':geometry,'certificate':cert,'independent_check':checked}
                    connectors.append(row);attempts.append({**definition,'status':'NOMINAL_MACRO_ADMITTED','connector_id':identity})
                except _Unavailable as exc:
                    if str(exc)=='WORK_BUDGET':raise
                    attempts.append({**definition,'status':'UNSUPPORTED_TEMPLATE','reason':str(exc)})
                if len(connectors)>1024:raise _Unavailable('CONNECTOR_BUDGET')
        catalogue={'schema':'oma.shared-tree-catalogue/1','context_root':digest(c),'source_roots':{'authored_requirements':digest(r),'search':digest(s)},
            'cost_policy_root':digest({'weights':[str(w) for w in weights],'tee_length':'2*trunk_takeout+branch_takeout','fitting_count':'one_per_tee_or_elbow'}),
            'section':section,'source':source,'sinks':terminal_rows,'tee_instances':tee_rows,'connectors':connectors}
        result={'status':'CATALOGUE_PROPOSED','input_root':input_root,'catalogue':catalogue,'tee_components':tee_components,
            'connector_macros':macros,'attempts':attempts,'limitations':LIMITATIONS,'work':budget.work}
        encoded=json.dumps(result,sort_keys=True,separators=(',',':'),allow_nan=False)
        if len(encoded.encode())>16_777_216-64:raise _Unavailable('OUTPUT_BYTE_BUDGET')
        _call(checkpoint,'shared_tree_connector_complete')
        budget.checkpoint=None
        if digest(_snapshot(originals,budget,max_bytes))!=input_root:raise ValueError('Input changed during connector construction')
        result['work']=budget.work
        return result
    except _CallerError as exc:raise exc.original
    except _Unavailable as exc:return {'status':'UNKNOWN','reason':str(exc),'work':budget.work,'catalogue':None,'limitations':LIMITATIONS}
    except (ValueError,TypeError,KeyError,ZeroDivisionError,OverflowError) as exc:
        return {'status':'INVALID_INPUT','reason':str(exc),'work':budget.work,'catalogue':None,'limitations':LIMITATIONS}


def _network_from_assignment(requirements,generated,proposal):
    """Independently expand selected macro incidence into physical demand paths."""
    catalogue=generated['catalogue'];by_id={x['id']:x for x in catalogue['connectors']}
    selected=[by_id[x] for x in proposal['connector_ids']]
    components=[generated['tee_components'][x] for x in proposal['tee_ids']]
    connections=[];first={};last={}
    for row in selected:
        macro=generated['connector_macros'][row['id']]
        if digest(macro['geometry'])!=row['geometry_root'] or macro['certificate']['certificate_root']!=row['fabrication_root']:
            raise ValueError('Selected macro geometry/fabrication binding differs')
        parts=macro['geometry']['components'];components.extend(parts)
        first[row['id']]={'component':parts[0]['id'],'port':'a'}
        last[row['id']]={'component':parts[-1]['id'],'port':'b'}
        connections += [{'source':{'component':a['id'],'port':'b'},'sink':{'component':b['id'],'port':'a'}} for a,b in zip(parts,parts[1:])]
        if row['from']['node'] in proposal['tee_ids']:
            connections.append({'source':{'component':row['from']['node'],'port':row['from']['port']},'sink':first[row['id']]})
        if row['to']['node'] in proposal['tee_ids']:
            connections.append({'source':last[row['id']],'sink':{'component':row['to']['node'],'port':'a'}})
    source_rows=[x for x in selected if x['from']=={'node':catalogue['source']['id'],'port':'out'}]
    if len(source_rows)!=1:raise ValueError('Exactly one source macro required')
    source=first[source_rows[0]['id']]
    sinks=[];paths=[];incoming={x['sink']['component']:x['source'] for x in connections}
    if len(incoming)!=len(connections):raise ValueError('Multiple physical predecessors')
    for sink in requirements['sinks']:
        matches=[x for x in selected if x['to']=={'node':sink['id'],'port':'in'}]
        if len(matches)!=1:raise ValueError('Exactly one connector to each fixed sink required')
        endpoint=last[matches[0]['id']];sinks.append({'id':sink['id'],'endpoint':endpoint})
        cursor=endpoint;steps=[];seen=set()
        while True:
            if cursor['component'] in seen:raise ValueError('Physical path cycle')
            seen.add(cursor['component']);steps.append({'component':cursor['component'],'entry_port':'a','exit_port':cursor['port']})
            if cursor['component']==source['component']:break
            cursor=incoming[cursor['component']]
        paths.append({'demand_id':sink['demand_id'],'sink_id':sink['id'],'steps':list(reversed(steps))})
    raw={'schema':'oma-physical-network/1','network_id':'generated-'+proposal['assignment_root'][:24],
        'system_type':requirements['system_type'],'components':components,'connections':connections,
        'source':source,'sinks':sinks,'demand_paths':paths}
    return NetworkDesign.model_validate(raw).model_dump(mode='json',by_alias=True)


def compile_shared_tree_proposals(requirements,search,*,context,max_results=8,max_work=2_000_000,
        max_bytes=2_097_152,checkpoint=None):
    """Produce a checked finite nominal proposal menu for the existing native run API."""
    budget=_Budget(max_work,checkpoint)
    try:
        if type(max_results) is not int or not 1<=max_results<=32:raise ValueError('One to32 returned proposals required')
        original={'requirements':requirements,'search':search,'context':context}
        captured=_snapshot(original,budget,max_bytes);original_root=digest(captured)
        r,s,c=(captured[k] for k in ('requirements','search','context'))
        relay=lambda stage:_call(checkpoint,stage)
        budget.use()
        generated=build_connector_catalogue(r,s,context=c,max_work=min(250_000,budget.maximum-budget.work),max_bytes=max_bytes,checkpoint=relay)
        budget.use(generated['work'])
        if generated['status']!='CATALOGUE_PROPOSED':
            return {'status':generated['status'],'reason':generated.get('reason'),'mission':None,'proof_complete':False,'work':budget.work}
        from oma.optimization.shared_tree_synthesis import compile_shared_tree_catalogue,verify_shared_tree_catalogue
        catalogue=generated['catalogue']
        budget.use()
        compiled=compile_shared_tree_catalogue(catalogue,max_results=max_results,max_work=budget.maximum-budget.work,checkpoint=relay)
        budget.use(compiled['work'])
        if compiled['status']!='CERTIFIED':
            return {'status':compiled['status'],'reason':compiled.get('reason'),'mission':None,'proof_complete':False,'work':budget.work}
        budget.use()
        checked=verify_shared_tree_catalogue(catalogue,compiled['certificate'],max_results=max_results,
            max_work=budget.maximum-budget.work,checkpoint=relay)
        budget.use(checked['work'])
        if checked['status']!='PASS':raise _Unavailable('SYNTHESIS_INDEPENDENT_CHECK_'+checked['status'])
        if not checked['proposals']:
            _call(checkpoint,'shared_tree_proposal_complete');budget.checkpoint=None
            if digest(_snapshot(original,budget,max_bytes))!=original_root:raise ValueError('Original proposal request changed')
            return {'status':'NO_FINITE_CATALOGUE_ASSIGNMENT','mission':None,'proof_complete':True,
                'input_root':original_root,'synthesis':compiled,'independent_check':checked,'work':budget.work,'limitations':LIMITATIONS}
        alternatives=[]
        for proposal in checked['proposals']:
            budget.use(1+len(proposal['connector_ids']))
            alternatives.append(_network_from_assignment(r,generated,proposal))
        raw={**r,'network_alternatives':alternatives}
        mission=SharedNetworkScenario.model_validate(raw).model_dump(mode='json',by_alias=True)
        _call(checkpoint,'shared_tree_proposal_complete');budget.checkpoint=None
        if digest(_snapshot(original,budget,max_bytes))!=original_root:raise ValueError('Original proposal request changed')
        result={'status':'PROPOSALS_READY','mission':mission,'input_root':original_root,'generation':generated,
            'synthesis':compiled,'independent_check':checked,'proof_complete':True,'work':budget.work,'limitations':LIMITATIONS}
        if len(json.dumps(result,sort_keys=True,separators=(',',':')).encode())>16_777_216:raise _Unavailable('OUTPUT_BYTE_BUDGET')
        return result
    except _CallerError as exc:raise exc.original
    except _Unavailable as exc:return {'status':'UNKNOWN','reason':str(exc),'mission':None,'proof_complete':False,'work':budget.work}
    except (ValueError,TypeError,KeyError,ZeroDivisionError,OverflowError) as exc:
        return {'status':'INVALID_INPUT','reason':str(exc),'mission':None,'proof_complete':False,'work':budget.work}
