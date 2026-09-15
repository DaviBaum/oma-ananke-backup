"""Independent rational nominal loss oracle; no app, producer, CAD or native solve."""
from fractions import Fraction as F
import copy
import hashlib
import json
import math
from pathlib import Path
import shutil
import time
import uuid

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').exists())
STAGE=Path(__file__).resolve().parent
AUTH=ROOT/'.oma/development/shared-tree-coupled/authored-fixtures/3db9529abfc94c59a72ac2dfd6a06138'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
def write(p,v):Path(p).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n',encoding='utf8')

def atan_bounds(x,n=80):
    total=sum(((-1)**i)*x**(2*i+1)/F(2*i+1) for i in range(n))
    next_term=(-1)**n*x**(2*n+1)/F(2*n+1)
    return min(total,total+next_term),max(total,total+next_term)

def main():
    started=time.monotonic();out=STAGE/'attempts'/uuid.uuid4().hex;out.mkdir(parents=True)
    shutil.copy2(__file__,out/'executed.py')
    r=read(AUTH/'requirements.json');s=read(AUTH/'search.json');g=read(AUTH/'generated.json');c=read(AUTH/'context.json')
    paths=list(AUTH.glob('*.json'))+[ROOT/'.oma/development/shared-tree-coupled/tests/shared_tree_coupled_fixture.py']
    before={str(p):sha(p) for p in paths}
    for p in paths:shutil.copy2(p,out/p.name)
    assert digest({'requirements':r,'search':s,'context':c})==g['input_root']
    b=r['coupled_tree'];assert 'physics' not in r and len(r['sinks'])==3
    assert set(b['tee_outlet_loss_coefficients'])=={x['id'] for x in s['tee_instances']}=={'tee-a','tee-c'}
    assert len(s['tee_instances'])==len(r['sinks'])-1
    assert all('required_flow_m3_s' not in x and 'available_static_pressure_pa' not in x for x in r['sinks'])
    expected=[('source','out','tee-a','a',('7/4','0')),('tee-a','b','tee-c','a',('3/2','0')),
              ('tee-c','b','sink-a','in',('7/4','0')),('tee-a','branch','sink-b','in',('11/4','1/4')),
              ('tee-c','branch','sink-c','in',('11/4','0'))]
    selected=[];ambiguity=[]
    for source,port,target,end,cost in expected:
        choices=[row for row in g['catalogue']['connectors'] if row['from']=={'node':source,'port':port} and row['to']=={'node':target,'port':end} and tuple(row['nominal_cost'])==cost]
        assert choices,(source,port,target,cost)
        selected.append(choices[0]);ambiguity.append({'edge':[source,port,target,end],'same_length_macro_count':len(choices),'selected_reference':choices[0]['id']})
    outgoing={(x['from']['node'],x['from']['port']):x for x in selected}
    sinks={x['id'] for x in r['sinks']}
    def below(node,seen=()):
        if node in sinks:return {node}
        assert node not in seen
        return below(outgoing[node,'b']['to']['node'],seen+(node,))|below(outgoing[node,'branch']['to']['node'],seen+(node,))
    tee_leaves={tee:below(tee) for tee in ('tee-a','tee-c')}
    q={sink:F(1,1000) for sink in sinks};rho=F(b['density_kg_m3']);friction=F(b['darcy_friction']);diameter=F(r['diameter_m'])
    assert diameter==F(1,8) and rho==1000 and friction==F(1,50)
    records=[];ids=set()
    for edge in selected:
        leaves=below(edge['to']['node']);flow=sum(q[x] for x in leaves)
        geometry=g['connector_macros'][edge['id']]['geometry'];assert digest(geometry)==edge['geometry_root']
        straight=F(0);arc=F(0);excess=F(0)
        for part in geometry['components']:
            assert part['id'] not in ids;ids.add(part['id'])
            assert F(part['diameter_m'])==diameter and F(part['insulation_m'])==F(r['insulation_m'])
            shape=part['geometry'];start=list(map(F,shape['start_m']));end=list(map(F,shape['end_m']))
            assert start[2]==end[2]==3
            length=F(0);arc_coef=F(0);local=F(0)
            if part['kind']=='segment':
                differences=[abs(a-z) for a,z in zip(start,end)];assert sum(x!=0 for x in differences)==1
                length=sum(differences)
            else:
                assert part['kind']=='elbow' and shape['angle_rad']==math.pi/2
                center=list(map(F,shape['center_m']));radius=F(shape['bend_radius_m'])
                u=[a-z for a,z in zip(start,center)];v=[a-z for a,z in zip(end,center)]
                assert sum(a*a for a in u)==sum(a*a for a in v)==radius**2 and sum(a*z for a,z in zip(u,v))==0
                assert radius==F(r['minimum_bend_radius_m'])
                arc_coef=radius/2;local=F(b['elbow_loss_coefficient'])
            straight+=length;arc+=arc_coef;excess+=local
            records.append({'id':part['id'],'kind':part['kind'],'descendant_leaves':sorted(leaves),'applies_to':sorted(leaves),
                'flow_m3_s':flow,'straight_m':length,'pi_length_coefficient_m':arc_coef,'excess_K':local})
        assert (str(straight),str(arc))==tuple(edge['nominal_cost'])
    assert len(ids)==9
    for tee in ('tee-a','tee-c'):
        flow=sum(q[x] for x in tee_leaves[tee])
        for port in ('b','branch'):
            applies=below(outgoing[tee,port]['to']['node'])
            records.append({'id':tee+':'+port,'kind':'tee_outlet','descendant_leaves':sorted(tee_leaves[tee]),'applies_to':sorted(applies),
                'flow_m3_s':flow,'straight_m':F(0),'pi_length_coefficient_m':F(0),'excess_K':F(b['tee_outlet_loss_coefficients'][tee][port])})
    assert len(records)==13 and sum(x['kind']=='elbow' for x in records)==2
    lo5,hi5=atan_bounds(F(1,5));lo239,hi239=atan_bounds(F(1,239));pi=(16*lo5-4*hi239,16*hi5-4*lo239)
    def heads(terms,*,used_diameter=diameter,kinetic=False):
        result={}
        for sink in sinks:
            relevant=[t for t in terms if sink in t['applies_to']]
            A=sum(8*rho*t['flow_m3_s']**2*(friction*t['straight_m']/used_diameter**5+t['excess_K']/used_diameter**4) for t in relevant)
            B=sum(8*rho*t['flow_m3_s']**2*friction*t['pi_length_coefficient_m']/used_diameter**5 for t in relevant)
            if kinetic:A+=8*rho*(q[sink]**2-sum(q.values())**2)/used_diameter**4
            values=[F(200)-(A+B*p)/p**2 for p in pi]
            result[sink]={'lower':min(values),'upper':max(values),'constant_over_pi_squared':A,'coefficient_over_pi':B}
        return result
    exact=heads(records);comparison={}
    for sink,interval in exact.items():
        declared=b['sink_total_pressures_pa'][sink]
        assert F(declared['lower'])<=interval['lower']<=interval['upper']<=F(declared['upper'])
        assert F(b['minimum_sink_flows_m3_s'][sink])<q[sink]
        box=b['flow_search_box_m3_s'][sink];assert F(box['lower'])<q[sink]<F(box['upper'])
        comparison[sink]={k:str(v) for k,v in interval.items()}
        comparison[sink].update(declared=declared,nominal_pressure_pa=float((interval['lower']+interval['upper'])/2))
    negatives=[]
    def reject(name,terms,**kwargs):
        values=heads(terms,**kwargs)
        violated=[sink for sink,v in values.items() if v['upper']<F(b['sink_total_pressures_pa'][sink]['lower']) or v['lower']>F(b['sink_total_pressures_pa'][sink]['upper'])]
        assert violated,name
        negatives.append({'name':name,'nominal_head_interval_mismatch_sinks':sorted(violated)})
    x=copy.deepcopy(records)
    for t in x:
        if t['kind']=='tee_outlet':t['flow_m3_s']=sum(q[z] for z in t['applies_to'])
    reject('outlet_flow_instead_of_full_tee_inlet_flow',x)
    x=copy.deepcopy(records)
    for t in x:
        if t['kind']=='elbow':t['pi_length_coefficient_m']=F(0)
    reject('omit_curved_Darcy',x)
    x=copy.deepcopy(records)
    for t in x:
        if t['kind']=='elbow':t['excess_K']*=2
    reject('double_elbow_excess',x)
    x=copy.deepcopy(records)
    for t in x:
        if t['kind']=='tee_outlet':t['straight_m']=F(3,4)
    reject('add_tee_skeleton_Darcy',x)
    reject('use_outer_envelope_diameter_as_bore',records,used_diameter=diameter+2*F(r['insulation_m']))
    reject('treat_total_pressure_as_static_with_extra_kinetic_term',records,kinetic=True)
    result={'status':'PASS','elapsed_seconds':time.monotonic()-started,'inputs':before,'nominal_flow_m3_s':{k:str(v) for k,v in q.items()},
        'nominal_reference_connectors':ambiguity,'nominal_components':11,'nominal_nontee_components':9,'nominal_loss_terms':13,
        'tee_Darcy_terms':0,'elbow_excess_terms':2,'curved_Darcy_terms':2,'nominal_heads':comparison,
        'terms':[{k:str(v) if isinstance(v,F) else v for k,v in t.items()} for t in records],
        'oracle_negative_variants':negatives,'native_geometry_reopened':False,'managed_generation_started':False,
        'scope':'Independent exact nominal catalogue geometry and head-loss accounting only. Authored pressures enclose the manufactured nominal1L/s-per-leaf target; native metric uncertainty, physical feasibility, actual operating enclosure and service remain separate obligations.'}
    assert all(sha(p)==h for p,h in before.items())
    write(out/'result.json',result)
    print(json.dumps({'status':'PASS','evidence':str(out),'nominal_heads':{k:v['nominal_pressure_pa'] for k,v in comparison.items()}}))

if __name__=='__main__':main()
