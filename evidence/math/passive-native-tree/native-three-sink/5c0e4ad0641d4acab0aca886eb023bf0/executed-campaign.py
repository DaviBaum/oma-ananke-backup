"""Retain a fresh native two-tee tree and an independent nominal flow oracle."""
from pathlib import Path
from fractions import Fraction as Q
from decimal import Decimal, localcontext
import argparse
import hashlib
import json
import os
import shutil
import sys
import time
import uuid

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').is_file())
STAGE=ROOT/'.oma/development/passive-native-tree'
BUILD='52bd5d29217117127da6dc0576a1626c8512ae7e145132ba9f9ef7b8ed12ea52'
RUNTIME=ROOT/'.oma/development/combined-pressure-checkpoint/runtimes'/BUILD/'src'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def write(path,value):Path(path).write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
def enc(a,b=None):return {'lower':str(a),'upper':str(a if b is None else b)}


def boundary():
    return {'schema':'oma.passive-tree-boundary/1','source_total_pressure_pa':'100',
        'sink_total_pressures_pa':{'sink-a':'0','sink-b':'0','sink-c':'0'},
        'minimum_sink_flows_m3_s':{'sink-a':'1/1000','sink-b':'1/2000','sink-c':'1/2000'},
        'density_kg_m3':'1000','darcy_friction':'1/50','maximum_velocity_m_s':'2','gravity_m_s2':'9.80665',
        'elbow_loss_coefficient':'1/5','tee_common_loss_coefficients':{'tee-1':'1/5','tee-2':'3/10'},
        'applicability':'New explicit ideal steady incompressible circular-bore model. Each physical tee has identical positive TOTAL inlet-flow-referenced loss at both outlets, including its internal distributed losses. No old unequal-outlet contract is reused.',
        'boundary_control_assumption':'Hypothetical regulated total-pressure terminals at the exact four physical boundary caps',
        'pressure_reference':'TOTAL_PRESSURE_P_PLUS_KINETIC_EXCLUDING_ELEVATION',
        'loss_model':'FIXED_COEFFICIENT_STEADY_INCOMPRESSIBLE',
        'hydraulic_section_interpretation':'IDEAL_CIRCULAR_BORE_FROM_NATIVE_ENVELOPE_MINUS_DECLARED_INSULATION',
        'friction_convention':'DARCY','elbow_loss_reference':'EXCESS_LOCAL_LOSS_EXCLUDING_CURVED_PIPE_FRICTION',
        'tee_loss_reference':'IDENTICAL_OUTLET_TOTAL_LOSS_AT_INLET_FLOW_COMMON_HEAD',
        'connection_model':'NO_EXTRA_LOSS_AT_CHECKED_MATCHING_CONNECTED_CAPS','boundary_loss_scope':'BETWEEN_PHYSICAL_NETWORK_PORTS_ONLY'}


def nominal_reference():
    with localcontext() as context:
        context.prec=85
        D=Decimal
        pi=D('3.141592653589793238462643383279502884197169399375105820974944592307816406286208998628')
        area=pi/D(400);beta=D(1000)/(2*area*area)
        ratio=(D(33)/2).sqrt()
        qb=(D(100)/(beta*(D('.36')*(ratio+2)**2+D('2.64')))).sqrt()
        qa=ratio*qb;qtotal=qa+2*qb; qdown=2*qb
        flow={'trunk':qtotal,'tee-1':qtotal,'arm-a':qa,'inter-tee':qdown,'tee-2':qdown,'arm-b':qb,'arm-c':qb}
        coefficient={'trunk':D('.16'),'tee-1':D('.2'),'arm-a':D('.16'),'inter-tee':D('.32'),'tee-2':D('.3'),'arm-b':D('.16'),'arm-c':D('.16')}
        delta={name:beta*coefficient[name]*q*q for name,q in flow.items()}
        h={'source':D(100),'tee-1-in':D(100)-delta['trunk']}
        h['tee-1-out']=h['tee-1-in']-delta['tee-1'];h['tee-2-in']=h['tee-1-out']-delta['inter-tee']
        h['tee-2-out']=h['tee-2-in']-delta['tee-2']
        closure={'sink-a':h['tee-1-out']-delta['arm-a'],'sink-b':h['tee-2-out']-delta['arm-b'],'sink-c':h['tee-2-out']-delta['arm-c']}
        assert all(abs(v)<D('1e-78') for v in closure.values())
        assert qtotal==qa+2*qb and all(q>0 for q in flow.values())
        port_flow={name:{'a':q,'b':q} for name,q in flow.items()}
        port_flow['tee-1']={'a':qtotal,'b':qdown,'branch':qa};port_flow['tee-2']={'a':qdown,'b':qb,'branch':qb}
        return {'status':'INDEPENDENT_85_DIGIT_NOMINAL_COMMON_LOSS_TREE_REFERENCE','precision_digits':85,'pi_used':str(pi),
            'area_m2':str(area),'beta_pa_s2_m6':str(beta),'qa_over_qb':'sqrt(33/2)',
            'formula_qb':'sqrt(100 / (beta * ((9/25)*(sqrt(33/2)+2)^2 + 66/25)))',
            'component_inlet_flows_m3_s':{k:str(v) for k,v in flow.items()},
            'physical_port_forward_flows_m3_s':{k:{s:str(q) for s,q in slots.items()} for k,slots in port_flow.items()},
            'relative_total_head_pa':{k:str(v) for k,v in h.items()},'sink_pressure_closure_pa':{k:str(v) for k,v in closure.items()},
            'component_loss_drop_pa':{k:str(v) for k,v in delta.items()},
            'scope':'Independent decimal closed-form nominal point only; native radius/length uncertainty belongs to later adapter intervals, not this scalar reference. Equal physical elevations cancel gravitational terms.'}


def child(directory):
    directory=Path(directory).resolve();sys.path.insert(0,str(directory))
    from native_three_sink_fixture import complete_native_evidence
    from oma.build_identity import checker_version
    declared=read(directory/'predeclaration.json')
    assert checker_version()==declared['checker_version']
    assert sha(directory/'original.ifc')==declared['source_sha256']
    assert sha(directory/'specification.json')==declared['specification_sha256']
    evidence=complete_native_evidence(directory/'original.ifc',directory/'three-sink.ifc',read(directory/'specification.json'))
    assert evidence['semantics']['status']==evidence['cad']['coordination_status']==evidence['cad']['self_interference_status']==evidence['zone']['status']=='PASS'
    assert evidence['cad']['pairs_accounted']==7 and len(evidence['cad']['self_pair_results'])==21
    assert checker_version()==declared['checker_version'] and sha(directory/'original.ifc')==declared['source_sha256']
    write(directory/'native-evidence.json',evidence)
    print(json.dumps({'status':'THREE_SINK_NATIVE_GEOMETRY_PASS','components':7,'ports':16,'source_pairs':7,'self_pairs':21}))


def main():
    from oma.build_identity import checker_version
    from oma.export_checks import supervise_check
    from oma.routing.network_scenario import NetworkDesign
    assert checker_version()=='oma-independent-checker/2:'+BUILD
    out=STAGE/'evidence/native-three-sink'/uuid.uuid4().hex;out.mkdir(parents=True)
    fixture=STAGE/'tests/native_three_sink_fixture.py';shutil.copyfile(fixture,out/fixture.name)
    shutil.copyfile(Path(__file__),out/'executed-campaign.py')
    sys.path.insert(0,str(out))
    from native_three_sink_fixture import make_original,three_sink_spec
    make_original(out/'original.ifc')
    specification=three_sink_spec();write(out/'specification.json',specification);write(out/'new-boundary-declaration.json',boundary())
    source_map={p.relative_to(RUNTIME).as_posix():sha(p) for p in RUNTIME.rglob('*.py')}
    declared={'schema':'oma.private-three-sink-native-predeclaration/1','checker_version':checker_version(),
        'source_sha256':sha(out/'original.ifc'),'specification_sha256':sha(out/'specification.json'),
        'new_boundary_sha256':sha(out/'new-boundary-declaration.json'),'script_sha256':sha(__file__),'fixture_sha256':sha(fixture),
        'application_sources':source_map,'expected_components':7,'expected_ports':16,'expected_connections':6,
        'expected_source_obstacles':1,'expected_component_pairs':21,
        'source_policy':'New analytic IFC fixture created once; original never modified',
        'scope':'Native geometry and independent nominal reference before new passive adapter integration; no accepted project or hydraulic certificate yet'}
    write(out/'predeclaration.json',declared)
    environment=os.environ.copy();environment.update(PYTHONPATH=str(RUNTIME),OMA_EXECUTABLE_BUILD=checker_version(),PYTHONDONTWRITEBYTECODE='1')
    supervision=supervise_check([sys.executable,str(out/'executed-campaign.py'),'--child',str(out)],environment=environment,directory=out/'process',deadline=time.monotonic()+120)
    write(out/'supervision.json',supervision)
    assert supervision['status']=='COMPLETED',supervision
    evidence=read(out/'native-evidence.json');reference=nominal_reference();write(out/'independent-nominal-reference.json',reference)
    tolerance=Q(1,1_000_000)
    ports={(p['component_id'],p['slot']):p for p in evidence['semantics']['ports']}
    metric_components={}
    for part in evidence['semantics']['parts']:
        cid=part['component_id'];length=Q(str(part['length_m']));radius=Q(str(part['radius_m']))
        metric_components[cid]={'length_m':enc(length-tolerance,length+tolerance),'outer_radius_m':enc(radius-tolerance,radius+tolerance),
            'ports':{slot:{'position_m':[enc(Q(str(x))-tolerance,Q(str(x))+tolerance) for x in ports[(cid,slot)]['position_m']]} for slot in part['caps']}}
    network=NetworkDesign.model_validate(specification)
    metrics={'schema':'oma.passive-tree-native-metrics/1','network_root':digest(network.model_dump(mode='json',by_alias=True)),
        'components':metric_components,'native_evidence_root':digest(evidence)}
    write(out/'native-metrics.json',metrics)
    guards={'source':sha(out/'original.ifc')==declared['source_sha256'],
        'specification':sha(out/'specification.json')==declared['specification_sha256'],
        'boundary':sha(out/'new-boundary-declaration.json')==declared['new_boundary_sha256'],
        'application':{p.relative_to(RUNTIME).as_posix():sha(p) for p in RUNTIME.rglob('*.py')}==source_map,
        'fixture':sha(fixture)==declared['fixture_sha256'],'script':sha(__file__)==declared['script_sha256']}
    assert all(guards.values()),guards
    result={'status':'THREE_SINK_TWO_TEE_NATIVE_GEOMETRY_AND_INDEPENDENT_REFERENCE_PASS','checker_version':checker_version(),
        'preservation':guards,'source_sha256':declared['source_sha256'],'export_sha256':evidence['export_sha256'],
        'network_root':metrics['network_root'],'native_evidence_root':metrics['native_evidence_root'],
        'metrics_root':digest(metrics),'native_denominators':{'components':7,'ports':16,'connections':6,'source_obstacles':1,'source_pairs':7,'self_pairs':21,'authorized_cap_contacts':6,'zone_solids':7},
        'metric_envelope_policy':{'native_absolute_tolerance_m':str(tolerance),'interpretation':'Numerically conditional native dimensions/positions enlarged by explicit 1 micrometre; not interval-certified IFC conversion'},
        'independent_reference_sha256':sha(out/'independent-nominal-reference.json'),'supervision_status':supervision['status'],
        'scope':declared['scope']}
    write(out/'result.json',result)
    (out/'README.md').write_text('Actual IFC4 geometry has seven unique solids, two distinct regularized-union tees, 16 owner-relative flow-axis ports, six matching cap connections, seven complete original-obstacle pairs and all 21 component pairs. All native geometry, self-contact, source preservation and zone checks pass in a fresh supervised Windows Job child. Five straight lengths plus both tees are counted once; shared path traversal never duplicates physical occupancy.\n\nThe separate new boundary explicitly assigns equal positive inlet-flow total loss to both outlets of each tee (0.2 and 0.3 respectively). It includes tee distributed loss; tee skeleton length is retained but not independently Darcy-charged. The 85-digit nominal formula is an independent point oracle, not a pressure certificate. Native metrics retain 1 micrometre uncertainty and an ideal bore interpretation. No prior unequal-loss mission, actual building source, accepted revision or production application was changed.\n',encoding='utf-8')
    write(out/'files.json',{'files':[{'path':p.relative_to(out).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(out.rglob('*')) if p.is_file()]})
    print(json.dumps({'status':result['status'],'directory':str(out),'result_sha256':sha(out/'result.json'),'native_denominators':result['native_denominators']}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--child',type=Path);args=parser.parse_args()
    child(args.child) if args.child else main()
