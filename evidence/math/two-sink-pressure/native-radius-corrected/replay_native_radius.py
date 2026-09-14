from pathlib import Path
import sys,json,time
ROOT=Path(__file__).resolve().parents[4];HERE=Path(__file__).parent
OLD=ROOT/'evidence/math/two-sink-pressure-independent/native-radius-465813329ada4885aaeb089d31320d82'
from oma.routing.network_scenario import SharedNetworkScenario
from oma.worker import WorkerControl,import_sources
from oma.routing.engine import route_project_run
from oma.store import Store
import oma.routing.network_engine as engine
from oma.ifc.audit import sha256_file,atomic_json
from oma.ifc.network_semantics import check_network_semantics
from oma.build_identity import checker_version
import ifcopenshell,ifcopenshell.util.unit,oma
old=json.loads((OLD/'result.json').read_text());raw=json.loads((OLD/'mission.json').read_text());original_mission=json.loads((OLD/'mission.json').read_text())
raw['pressure_driven']['hydraulic_section_interpretation']='IDEAL_CIRCULAR_BORE_FROM_NATIVE_ENVELOPE_MINUS_DECLARED_INSULATION'
comparison=json.loads(json.dumps(raw));comparison['pressure_driven'].pop('hydraulic_section_interpretation');assert comparison==original_mission
scenario=SharedNetworkScenario.model_validate(raw)
source=OLD/'native/obstacle.ifc';assert sha256_file(source)==old['original_source_sha256']
store=Store(HERE/'native/store');project=store.create_project('Native pressure radius corrected replay',{'sources':[],'entities':[]})
imp=store.create_run(project['id'],{'operation':'import','paths':[str(source)]});import_sources(store,imp,WorkerControl(store,imp['id']))
real_export=engine.export_network;written=[]
def altered_export(source,export,spec,**kwargs):
    material=real_export(source,export,spec,**kwargs);model=ifcopenshell.open(str(export));scale=ifcopenshell.util.unit.calculate_unit_scale(model)
    old_ids={x.id() for x in ifcopenshell.open(str(source))};changes=[]
    for profile in model.by_type('IfcCircleProfileDef'):
        if profile.id() in old_ids:continue
        before=float(profile.Radius)*scale;profile.Radius=(before-9e-11)/scale
        changes.append({'step_id':profile.id(),'before_radius_m':before,'after_radius_m':float(profile.Radius)*scale})
    assert len(changes)==5
    model.write(str(export));material['export_sha256']=sha256_file(export);atomic_json(Path(export).with_suffix('.manifest.json'),material)
    native=check_network_semantics(export,source,material);assert native['status']=='PASS',native
    written.append({'materialization':material,'changed_native_profiles':changes,'native_semantics':native});return material
engine.export_network=altered_export
run=store.create_run(project['id'],{'operation':'optimize','mission':raw,'budget_seconds':90});started=time.monotonic();route_project_run(store,run,WorkerControl(store,run['id']))
candidate,=store.candidates(project['id']);report=store.get(candidate['report_root']);checks={r['id']:r for r in report['results']}
assert checks['network-native-semantics']['status']=='PASS'
assert checks['network-all-source-clearance']['status']=='PASS'
assert checks['network-all-component-pairs']['status']=='PASS'
assert checks['network-demand-conditioned-service']['status']!='PASS' and candidate['status']!='CHECKED'
assert sha256_file(source)==old['original_source_sha256']
result={'status':'CORRECTED_NATIVE_RADIUS_REPLAY_REJECTS_DELIVERY_AUTHORITY','checker_version':checker_version(),'loaded_oma':oma.__file__,'seconds':time.monotonic()-started,'previous_attempt':str(OLD),'mission_change_only':'Required explicit hydraulic_section_interpretation field; all other fixed requirements and geometry unchanged','mission':raw,'original_source_sha256':old['original_source_sha256'],'same_source_bytes':True,'same_native_radius_delta_m':9e-11,'native_semantics':written[0]['native_semantics'],'candidate':candidate,'report':report,'run':store.run(run['id']),'operating_status':checks['network-pressure-operating-point']['status'],'delivery_status':checks['network-demand-conditioned-service']['status'],'physical_checks_pass':True,'previous_native_inferred_bore_oracle_m3_s':old['native_inferred_bore_oracle_m3_s'],'required_minimum_m3_s':old['required_minimum_m3_s']}
(HERE/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps({k:result[k] for k in ('status','checker_version','seconds','operating_status','delivery_status','same_source_bytes')}|{'candidate_status':candidate['status'],'report_status':report['status']}),flush=True)
