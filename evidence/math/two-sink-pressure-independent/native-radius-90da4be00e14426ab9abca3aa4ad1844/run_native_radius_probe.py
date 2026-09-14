from pathlib import Path
from copy import deepcopy
from fractions import Fraction as F
from decimal import Decimal,localcontext
import sys,json,hashlib,time
ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).parent
sys.path[:0]=[str(ROOT/'tests'),str(ROOT/'.oma/development/two-sink-pressure/tests')]
from test_network_pressure import pressure_scenario,metrics
from test_network_integration import imported_project
from oma.routing.network_scenario import SharedNetworkScenario
from oma.routing.network_pressure import evaluate_pressure_network
from oma.optimization.physical import Interval
from oma.worker import WorkerControl
from oma.routing.engine import route_project_run
import oma.routing.network_engine as engine
from oma.ifc.audit import sha256_file,atomic_json
from oma.ifc.network_semantics import check_network_semantics
from oma.build_identity import checker_version
import ifcopenshell,ifcopenshell.util.unit
import oma
raw=pressure_scenario();raw['diameter_m']=.00001;raw['pressure_driven']['gravity_m_s2']=0.
for c in raw['network_alternatives'][0]['components']:c['diameter_m']=.00001
for s in raw['sinks']:s['required_flow_m3_s']=1e-15
lengths,positions=metrics();budget=F(1,1000000)
lengths={cid:Interval(v-budget,v+budget) for cid,v in lengths.items()}
positions={'source':[Interval(F(v)-budget,F(v)+budget) for v in positions['source']],'sinks':{sid:[Interval(F(v)-budget,F(v)+budget) for v in p] for sid,p in positions['sinks'].items()}}
scenario=SharedNetworkScenario.model_validate(raw)
nominal=evaluate_pressure_network(scenario,scenario.network_alternatives[0],lengths,positions,context={'audit':'nominal metric intervals'})
assert nominal['verdict']=='PASS',nominal
nominal_lower=F(nominal['deliveries']['sink-a']['flow_m3_s']['lower'])
PI=Decimal('3.1415926535897932384626433832795028841971693993751058209749445923078164062862089986280348253421170679')
def oracle(diameter,trunk='0.8',branch='0.8'):
    with localcontext() as c:
        c.prec=100;d=Decimal(str(diameter));f=Decimal('.02');rho=Decimal(1000);p=Decimal(100);k=Decimal('.2')
        area=PI*d*d/4
        return area/2*(2*p/(rho*(f*Decimal(str(trunk))/d+k+f*Decimal(str(branch))/d/4))).sqrt()
delta=9e-11
actual_bore=2*((.00001/2+.02-delta)-.02)
actual_oracle=oracle(actual_bore)
with localcontext() as c:
    c.prec=100;nominal_decimal=Decimal(nominal_lower.numerator)/Decimal(nominal_lower.denominator)
    assert actual_oracle<nominal_decimal,(str(actual_oracle),str(nominal_decimal))
    minimum=float((actual_oracle+nominal_decimal)/2)
for s in raw['sinks']:s['required_flow_m3_s']=minimum
scenario=SharedNetworkScenario.model_validate(raw)
json_dump=lambda path,value:path.write_text(json.dumps(value,indent=2,default=str),encoding='utf-8')
json_dump(HERE/'mission.json',raw)
store,project=imported_project(HERE/'native')
original_source=store.get(store.project(project['id'])['state_root'])['sources'][0]
original_sha=sha256_file(store.resolve_path(original_source['immutable_path']))
real_export=engine.export_network;written=[]
def altered_export(source,export,spec,**kwargs):
    material=real_export(source,export,spec,**kwargs)
    model=ifcopenshell.open(str(export));scale=ifcopenshell.util.unit.calculate_unit_scale(model)
    old_ids={x.id() for x in ifcopenshell.open(str(source))}
    changes=[]
    for profile in model.by_type('IfcCircleProfileDef'):
        if profile.id() in old_ids:continue
        before=float(profile.Radius)*scale
        profile.Radius=(before-delta)/scale
        changes.append({'step_id':profile.id(),'before_radius_m':before,'after_radius_m':float(profile.Radius)*scale})
    assert len(changes)==5,changes
    model.write(str(export));material['export_sha256']=sha256_file(export)
    atomic_json(Path(str(export)+'.manifest.json'),material)
    native=check_network_semantics(export,source,material)
    written.append({'materialization':material,'changed_native_profiles':changes,'native_semantics':native})
    assert native['status']=='PASS',native
    return material
engine.export_network=altered_export
run=store.create_run(project['id'],{'operation':'optimize','mission':raw,'budget_seconds':90})
started=time.monotonic();route_project_run(store,run,WorkerControl(store,run['id']))
candidates=store.candidates(project['id']);assert len(candidates)==1,candidates
candidate=candidates[0];report=store.get(candidate['report_root']) if candidate.get('report_root') else None
assert sha256_file(store.resolve_path(original_source['immutable_path']))==original_sha
native=written[0]['native_semantics'];parts=native['parts'];rad=parts[0]['radius_m'];actual_bore=2*(rad-scenario.insulation_m)
actual_oracle=oracle(actual_bore,next(p['length_m'] for p in parts if p['component_id']=='trunk'),next(p['length_m'] for p in parts if p['component_id']=='arm-a'))
assert actual_oracle<Decimal(str(minimum))
result={'status':'NATIVE_RADIUS_APPLICABILITY_PROBE_COMPLETE','checker_version':checker_version(),'loaded_oma':oma.__file__,'seconds':time.monotonic()-started,'native_change_scope':'Only freshly authored network circular profiles changed before candidate publication; original STEP source untouched','native_changes':written[0]['changed_native_profiles'],'native_semantics_status':native['status'],'nominal_design_bore_diameter_m':raw['diameter_m'],'native_outer_radius_m':rad,'fixed_insulation_m':scenario.insulation_m,'inferred_native_bore_diameter_m':actual_bore,'native_radius_delta_m':delta,'required_minimum_m3_s':minimum,'native_inferred_bore_oracle_m3_s':str(actual_oracle),'nominal_certified_lower_m3_s':str(nominal_lower),'candidate':candidate,'run':store.run(run['id']),'report':report,'native_semantics':native,'original_source_sha256':original_sha,'interpretation':'The oracle infers hydraulic bore as 2*(native represented outer radius - fixed supplied insulation); conditional engineering interpretation, not proof of as-built bore'}
json_dump(HERE/'result.json',result)
print(json.dumps({k:result[k] for k in ('status','checker_version','seconds','native_semantics_status','required_minimum_m3_s','native_inferred_bore_oracle_m3_s')}|{'candidate_status':candidate['status'],'report_status':report['status'] if report else None}),flush=True)
