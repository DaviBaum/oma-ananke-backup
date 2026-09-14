"""Standard-library-only preparation. No application, native checks or Store writes."""
from pathlib import Path
from fractions import Fraction as Q
from copy import deepcopy
import hashlib
import json
import shutil
import sqlite3
import uuid

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').is_file())
STAGE=Path(__file__).resolve().parent
COMMON=ROOT/'evidence/benchmarks/passive-pressure/office/f64e250b57bb480f9dfe352892b61b3f/campaign'
PRIOR_RUN='deb6bc686d184021aeb3646dd0f67e6c'
PRIOR_CANDIDATE='123924e355164a5ba330e5b30cc72384'
EXPECTED_SOURCE='7108485ac8d2856922a83f1353aea8c6eaab60ff393546750bf648200617a544'
COMMON_STORE=ROOT/'.oma/development/passive-native-tree/bench-stores/f64e250b57bb480f9dfe352892b61b3f'

def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
def write(p,v):Path(p).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def enc(a,b=None):return {'lower':str(a),'upper':str(a if b is None else b)}

def original_rows(directory,run_id,candidate_id):
    with sqlite3.connect((directory/'oma.sqlite3').resolve().as_uri()+'?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        run=dict(db.execute('SELECT * FROM runs WHERE id=?',(run_id,)).fetchone())
        candidate=dict(db.execute('SELECT * FROM candidates WHERE id=?',(candidate_id,)).fetchone())
        project=dict(db.execute('SELECT * FROM projects WHERE id=?',(run['project_id'],)).fetchone())
    return {'directory':str(directory.resolve()),'run':run,'candidate':candidate,'project':project,'mode':'SQLITE_READ_ONLY'}

def boundary(spec):
    leaves=['sink-a','sink-b','sink-c'];flow=dict(zip(leaves,map(Q,('3/1000','3/2000','1/1000'))))
    coefficients={'tee-1':{'b':'1/5','branch':'3/10'},'tee-2':{'b':'1/4','branch':'2/5'}}
    parts={c['id']:c for c in spec['components']};paths={p['sink_id']:p['steps'] for p in spec['demand_paths']}
    assert len(parts)==7 and len(paths)==3
    source=spec['source'];source_z=Q(str(parts[source['component']]['geometry']['start_m'][2]))
    rho,f,g,d=Q(1000),Q(1,50),Q('9.80665'),Q(1,10)
    nom_lengths={};loss_factors={}
    for cid,c in parts.items():
        if c['kind']=='tee':continue
        assert c['kind']=='segment'
        differences=[abs(Q(str(b))-Q(str(a))) for a,b in zip(c['geometry']['start_m'],c['geometry']['end_m'])]
        assert sum(v!=0 for v in differences)==1
        nom_lengths[cid]=sum(differences);loss_factors[cid]=f*nom_lengths[cid]/d
    # Independently recompute Machin bounds, not a stored pressure scalar.
    def atan(n):
        lower=sum((Q((-1)**k,(2*k+1)*n**(2*k+1)) for k in range(48)),Q(0))
        return lower,lower+Q(1,97*n**97)
    a0,a1=atan(5);b0,b1=atan(239);pi0,pi1=16*a0-4*b1,16*a1-4*b0
    area_without_pi=d*d/4;beta_without_pi=rho/(2*area_without_pi**2)
    expressions={};sink_pressures={};partition={}
    for leaf,path in paths.items():
        loss=Q(0);partition[leaf]=[]
        for step in path:
            cid,slot=step['component'],step['exit_port']
            descendants=[other for other,p in paths.items() if any(s['component']==cid for s in p)]
            q=sum(flow[x] for x in descendants)
            factor=Q(coefficients[cid][slot]) if parts[cid]['kind']=='tee' else loss_factors[cid]
            loss+=beta_without_pi*factor*q*q
            partition[leaf].append({'component':cid,'outlet':slot,'full_inlet_descendants':descendants,
                'nominal_inlet_flow_m3_s':str(q),'dimensionless_loss_factor':str(factor),'tee_darcy_charged':False})
        sink=next(s for s in spec['sinks'] if s['id']==leaf);end=sink['endpoint']
        z=Q(str(parts[end['component']]['geometry']['end_m'][2]))
        offset=Q(200)+rho*g*(source_z-z)
        lower,upper=offset-loss/pi0**2,offset-loss/pi1**2
        scale=10**6;sink_pressures[leaf]=enc(Q((lower*scale).__floor__(),scale),Q((upper*scale).__ceil__(),scale))
        expressions[leaf]={'rational_offset_pa':str(offset),'negative_pi_inverse_square_coefficient_pa':str(loss)}
    widths=dict(zip(leaves,map(Q,('3/1000000','17/1000000','17/1000000'))))
    result={'schema':'oma.coupled-tree-boundary/1','source_total_pressure_pa':enc(Q(200)),
        'sink_total_pressures_pa':sink_pressures,'minimum_sink_flows_m3_s':dict(zip(leaves,('1/400','3/2500','1/1250'))),
        'flow_search_box_m3_s':{leaf:enc(q-widths[leaf],q+widths[leaf]) for leaf,q in flow.items()},
        'density_kg_m3':str(rho),'darcy_friction':str(f),'maximum_velocity_m_s':'2','gravity_m_s2':str(g),
        'elbow_loss_coefficient':'1/5','tee_outlet_loss_coefficients':coefficients,
        'applicability':'New hypothetical Office ideal steady incompressible bore model with distinct positive total inlet-flow-referenced loss at each physical tee outlet. Tee internal distributed loss is included; no additional Darcy charge for tee skeleton.',
        'boundary_control_assumption':'New hypothetical regulated total-pressure intervals at the unchanged four physical terminal caps. Sink pressures are manufactured independently from exact rational nominal leaf flows and declared Office geometry before fresh checks. Prior common-loss mission remains unchanged.',
        'pressure_reference':'TOTAL_PRESSURE_P_PLUS_KINETIC_EXCLUDING_ELEVATION','loss_model':'FIXED_COEFFICIENT_STEADY_INCOMPRESSIBLE',
        'hydraulic_section_interpretation':'IDEAL_CIRCULAR_BORE_FROM_NATIVE_ENVELOPE_MINUS_DECLARED_INSULATION',
        'friction_convention':'DARCY','elbow_loss_reference':'EXCESS_LOCAL_LOSS_EXCLUDING_CURVED_PIPE_FRICTION',
        'tee_loss_reference':'OUTLET_SPECIFIC_TOTAL_LOSS_AT_TOTAL_INLET_FLOW',
        'connection_model':'NO_EXTRA_LOSS_AT_CHECKED_MATCHING_CONNECTED_CAPS','boundary_loss_scope':'BETWEEN_PHYSICAL_NETWORK_PORTS_ONLY'}
    reference={'schema':'oma.office-unequal-tree-manufactured-boundary/1','nominal_leaf_flows_m3_s':{k:str(v) for k,v in flow.items()},
        'nominal_lengths_from_declared_office_coordinates_m':{k:str(v) for k,v in nom_lengths.items()},
        'nominal_bore_m':str(d),'declared_insulation_m':'1/50','nominal_area_m2':'pi/400',
        'source_elevation_m':str(source_z),'density_kg_m3':str(rho),'gravity_m_s2':str(g),
        'sink_pressure_expressions':expressions,'complete_path_loss_partition':partition,'pi_bounds':enc(pi0,pi1),
        'pressure_rounding':'Independent 48-term rational Machin bounds, then outward 1e-6 Pa regulator brackets',
        'box_history':'Anisotropic halfwidths from retained analytic reference: uniform1e-5 was UNKNOWN; (3,17,17)e-6 verified. Those are proposal-history results only, not current Office checks.',
        'native_checks':'NOT_RUN','application_schema_validation':'PENDING_COMBINED_FROZEN_SOURCE'}
    return result,reference

def main():
    old_path=COMMON/'frozen-mission.json';old=read(old_path);old_result=read(COMMON/'run-result.json')
    out=STAGE/'prepared'/uuid.uuid4().hex;out.mkdir(parents=True)
    old_mission=deepcopy(old['mission']);mission=deepcopy(old_mission);spec=mission['network_alternatives'][0]
    assert len(mission['network_alternatives'])==1
    spec['network_id']='office-explicit-unequal-outlet-three-sink'
    new_boundary,nominal=boundary(spec)
    mission.pop('passive_tree');mission['coupled_tree']=new_boundary
    mission['assumptions']=['New hypothetical regulated total-pressure service with three sinks and two distinct unequal-outlet tees',
        'Native outer envelopes imply an ideal declared circular bore only after subtracting declared insulation; bore is not directly measured',
        'Every original Office physical object remains in the full native obstacle denominator',
        'Hypothetical scenario terminals do not claim attachment to original building ports',
        'One retained geometry alternative; no optimization-improvement or whole-building sufficiency claim']
    original=original_rows(ROOT/'.oma',PRIOR_RUN,PRIOR_CANDIDATE)
    common=original_rows(COMMON_STORE,old_result['run_id'],old_result['selected_candidate_id'])
    assert original['run']['base_root']==old['baseline_root']
    execution=read(COMMON/'execution-predeclaration.json');sources=execution['original_files']
    assert len(sources)==1 and set(sources.values())=={EXPECTED_SOURCE} and all(sha(p)==v for p,v in sources.items())
    write(out/'mission-draft.json',mission);write(out/'manufactured-boundary.json',nominal)
    write(out/'original-stores-before.json',{'baseline_original':original,'common_tee_original':common})
    declaration={'schema':'oma.office-unequal-tree-draft/1','status':'PREPARED_NATIVE_NOT_RUN','mission_root':digest(mission),
        'baseline_root':old['baseline_root'],'source_sha256':EXPECTED_SOURCE,'original_files':sources,
        'previous_common_mission_path':str(old_path),'previous_common_mission_sha256':sha(old_path),'previous_common_mission_root':old['mission_root'],
        'previous_common_result_sha256':sha(COMMON/'run-result.json'),'new_boundary_root':digest(new_boundary),
        'mission_draft_sha256':sha(out/'mission-draft.json'),'manufactured_boundary_sha256':sha(out/'manufactured-boundary.json'),
        'baseline_origin_run':PRIOR_RUN,'baseline_origin_candidate':PRIOR_CANDIDATE,
        'geometry_changes':['New network identity only; all7 component coordinates/sections/ports/connections/paths and allowed zone unchanged'],
        'physical_semantics':'Explicit new loss/boundary contract; old common-tee mission untouched',
        'expected_native_denominators':{'parts':7,'ports':16,'connections':6,'source_obstacles':803,'source_pairs':5621,'self_pairs':21,'deliveries':3,'continuity_identities':17,'head_path_identities':19},
        'required_local_kernel_sha256':'ce5a264c7815b860b9ce0b8001e1b35cc3ecf7f4acacafc4925f7a6e37060c90',
        'required_global_kernel_sha256':'f433e0c007912aa9501306b2bfc95f0809a135e46b5ad898421410eabe10e4df',
        'required_adapter_sha256':'bc1ce17fe8c0bc97287cb8d2ef3212de8fdddbfbf03456898635ff77eb6aecae',
        'execution_gate':'WAIT_FOR_PARENT_COMBINED_NATIVE_INTEGRATION_FREEZE','production_app_loaded':False,'native_checks_run':0}
    write(out/'preparation.json',declaration);shutil.copyfile(__file__,out/'executed-prepare.py')
    assert original_rows(ROOT/'.oma',PRIOR_RUN,PRIOR_CANDIDATE)==original
    assert original_rows(COMMON_STORE,old_result['run_id'],old_result['selected_candidate_id'])==common
    assert sha(old_path)==declaration['previous_common_mission_sha256'] and all(sha(p)==v for p,v in sources.items())
    print(json.dumps({'status':declaration['status'],'directory':str(out),'mission_root':declaration['mission_root'],'boundary':new_boundary['sink_total_pressures_pa']}))

if __name__=='__main__':main()
