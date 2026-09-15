"""Read-only real ARC reference/semantics profile; no full-clearance verdict."""
from pathlib import Path
import cProfile,hashlib,importlib.util,io,json,pstats,shutil,sys,time,uuid
ROOT=Path(__file__).resolve().parents[3];STAGE=Path(__file__).resolve().parent
FROZEN=ROOT/'.oma/development/factorized-tree-pressure/runtimes/f73a8793ae0df76d9ec53400cec18b05d2731f63c735b225c2246fee62df6b21/src'
sys.path.insert(0,str(FROZEN))
from oma.ifc import cad
from oma.ifc.audit import sha256_file,atomic_json
from oma.ifc.network_semantics import check_network_semantics
import numpy as np

out=STAGE/'attempts'/uuid.uuid4().hex;out.mkdir(parents=True)
shutil.copyfile(__file__,out/'executed-profile.py')
material_path=ROOT/'.oma/development/hospital-generated-tree/campaigns/eac181c60f1748f4841b0796dfd69e00/candidates/85453f9ad960487297bf0231cd549a79/materialization.json'
material=json.loads(material_path.read_text());source=Path(material['source_path']);export=Path(material['export_path'])
identities={str(p):sha256_file(p) for p in (source,export,material_path,FROZEN/'oma/ifc/cad.py',FROZEN/'oma/ifc/network_semantics.py',STAGE/'before/federation.py',STAGE/'after/federation.py')}
assert identities[str(source)]==material['source_sha256'] and identities[str(export)]==material['export_sha256']
atomic_json(out/'inputs.json',identities)
audit={'source_path':str(source),'source_sha256':material['source_sha256'],'units':{'status':'KNOWN'}}
result={'status':'RUNNING','scope':'Actual ARC reference-frame and four authored native parts; semantics-only profile, no source-clearance or feasibility claim','matrices':{},'native_comparison':{}}
def retain():atomic_json(out/'result.json',result);print(json.dumps({'output':str(out),'status':result['status'],'keys':list(result)}),flush=True)
retain()
for mode in ('before','after'):
    spec=importlib.util.spec_from_file_location('oma.ifc.federation_'+mode,STAGE/mode/'federation.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    start=time.perf_counter();federation=module.audited_local_federation([audit])
    result['matrices'][mode]={'seconds':time.perf_counter()-start,'matrix':federation['sources'][0]['transform'],'status':federation['status']}
    atomic_json(out/(mode+'-federation.json'),federation)
    retain()
guids={p['ifc_guid'] for p in material['added_parts']}
start=time.perf_counter();native,errors=cad.load_cad(export,guids=guids)
assert not errors and len(native)==4 and all(n.valid for n in native)
result['native_load_seconds']=time.perf_counter()-start
original=cad._inspect_shape
for mode in ('before','after'):
    count=[0]
    def inspect(shape):count[0]+=1;return original(shape)
    cad._inspect_shape=inspect
    start=time.perf_counter();changed=[cad._transform_object(n,result['matrices'][mode]['matrix']) for n in native]
    result['native_comparison'][mode]={'seconds':time.perf_counter()-start,'reinspection_calls':count[0],
        'same_object_count':sum(a is b for a,b in zip(native,changed)),'valid_count':sum(n.valid for n in changed),
        'parts':[{'guid':n.guid,'step_id':n.step_id,'bounds':list(n.bounds),'volume_m3':n.volume_m3} for n in changed]}
    retain()
cad._inspect_shape=original
assert result['native_comparison']['before']['reinspection_calls']==4
assert result['native_comparison']['after']['reinspection_calls']==0
assert result['native_comparison']['after']['same_object_count']==4
# Measure the actual million-record semantic comparison separately from source CAD.
profile=cProfile.Profile();start=time.perf_counter();profile.enable()
semantics=check_network_semantics(export,source,material)
profile.disable();seconds=time.perf_counter()-start
atomic_json(out/'semantics.json',semantics)
profile.dump_stats(str(out/'semantics.prof'))
stream=io.StringIO();pstats.Stats(profile,stream=stream).strip_dirs().sort_stats('cumulative').print_stats(25)
(out/'semantics-profile.txt').write_text(stream.getvalue(),encoding='utf-8')
assert semantics['status']=='PASS'
result['semantic_profile']={'seconds':seconds,'status':semantics['status'],'original_step_records':material['original_step_records'],
    'native_parts':len(semantics['parts']),'ports':len(semantics['ports'])}
assert all(sha256_file(p)==value for p,value in identities.items())
result.update(status='ACTUAL_REFERENCE_IDENTITY_AND_SEMANTICS_PROFILE_PASS',inputs_unchanged=True,
    outcome_scope='Avoids a redundant native transform/reinspection on the selected reference source; does not reduce obstacle or pair denominator or prove Hospital feasibility.')
retain()
