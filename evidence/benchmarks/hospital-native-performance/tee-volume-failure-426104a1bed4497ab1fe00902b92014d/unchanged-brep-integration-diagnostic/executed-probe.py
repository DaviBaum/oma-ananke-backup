"""Compare native integration methods on unchanged old/new actual Hospital tees."""
from pathlib import Path
import hashlib,json,sys,time,uuid,shutil
ROOT=Path(__file__).resolve().parents[3];STAGE=Path(__file__).resolve().parent
SOURCE=ROOT/'.oma/development/hospital-clearance-20260915/runtimes/f716dd5cbdd84134a50d855b217b91a886832abc582ee761b1340cec2026b8e7/src'
sys.path.insert(0,str(SOURCE))
from oma.ifc.cad import load_cad
from OCP.BRepGProp import BRepGProp
from OCP.GProp import GProp_GProps
from OCP.BRepTools import BRepTools
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCP.gp import gp_Trsf,gp_Vec,gp_Pnt
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text())
out=STAGE/'volume-probes'/uuid.uuid4().hex;out.mkdir(parents=True)
shutil.copyfile(__file__,out/'executed-probe.py')
materials={
    'old':ROOT/'.oma/development/hospital-generated-tree/campaigns/eac181c60f1748f4841b0796dfd69e00/candidates/85453f9ad960487297bf0231cd549a79/materialization.json',
    'new':ROOT/'.oma/development/hospital-clearance-20260915/campaign-v1/campaigns/426104a1bed4497ab1fe00902b92014d/candidates/d5e66650ce5a4e09ae9958cc0600d7de/materialization.json'}
result={'status':'RUNNING','observations':{},'scope':'Numerical integration diagnostic only; no tolerance or BRep modification to any source/candidate.'}
def save():
    (out/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'output':str(out),'status':result['status'],'observations':result['observations']}),flush=True)
for mode,path in materials.items():
    material=read(path);source=Path(material['export_path']);assert sha(source)==material['export_sha256']
    tee=next(p for p in material['added_parts'] if p['kind']=='tee')
    started=time.perf_counter();native,errors=load_cad(source,guids={tee['ifc_guid']})
    assert not errors and len(native)==1 and native[0].valid
    obj=native[0];measurements=[]
    BRepTools.Write_s(obj.shape,str(out/(mode+'.brep')))
    for centered in (False,True):
        shape=obj.shape
        if centered:
            transform=gp_Trsf();transform.SetTranslation(gp_Vec(-33.,-64.,-173.875))
            shape=BRepBuilderAPI_Transform(shape,transform,True).Shape()
        for method,epsilon in [('default',None),('adaptive',1e-7),('adaptive',1e-9),('adaptive',1e-12),('gk',1e-9),('gk',1e-12)]:
            props=GProp_GProps();start=time.perf_counter()
            if method=='default':error=BRepGProp.VolumeProperties_s(shape,props)
            elif method=='adaptive':error=BRepGProp.VolumeProperties_s(shape,props,epsilon,True,False)
            else:error=BRepGProp.VolumePropertiesGK_s(shape,props,epsilon,True,True,False,False,False)
            measurements.append({'method':method,'epsilon':epsilon,'centered_diagnostic_copy':centered,
                'volume_m3':props.Mass(),'estimated_relative_error':error,'seconds':time.perf_counter()-start})
    result['observations'][mode]={'materialization_sha256':sha(path),'actual_ifc_sha256':sha(source),'guid':obj.guid,
        'source_native_volume_m3':obj.volume_m3,'source_native_bounds':obj.bounds,'source_kernel_tolerance_m':obj.kernel_tolerance_m,
        'brep_sha256':sha(out/(mode+'.brep')),'measurements':measurements,'seconds':time.perf_counter()-started}
    assert sha(source)==material['export_sha256'];save()
result['status']='NATIVE_TEE_VOLUME_INTEGRATION_DIAGNOSTIC_COMPLETE';save()
