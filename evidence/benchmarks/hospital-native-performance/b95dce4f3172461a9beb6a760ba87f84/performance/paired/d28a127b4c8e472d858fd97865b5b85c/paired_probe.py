"""Compare two inspectors on fresh copies of the same retained native BReps."""
from pathlib import Path
import importlib.util,io,json,sys,time
import ifcopenshell,ifcopenshell.geom
from OCP.TopoDS import TopoDS_Shape
from OCP.BRepTools import BRepTools
from OCP.BRep import BRep_Builder
from oma.ifc import cad
from oma.ifc.audit import atomic_json,sha256_file
from oma.ifc.inventory import physical_inventory,inventory_evidence

out=Path(sys.argv[1]);decl=json.loads((out/'predeclaration.json').read_text(encoding='utf8'))
source=Path(decl['source']);assert sha256_file(source)==decl['source_sha256']
spec=importlib.util.spec_from_file_location('oma.ifc._legacy_inspector',decl['base_cad'])
legacy=importlib.util.module_from_spec(spec);sys.modules[spec.name]=legacy;spec.loader.exec_module(legacy)
assert sha256_file(legacy.__file__)==decl['base_cad_sha256']
assert sha256_file(cad.__file__)==decl['private_cad_sha256']
started=time.perf_counter();events=(out/'progress.jsonl').open('a',encoding='utf8')
def emit(stage,**row):
    events.write(json.dumps({'stage':stage,'seconds':time.perf_counter()-started,**row})+'\n');events.flush()
emit('parse_start');model=ifcopenshell.open(str(source));emit('parse_end')
inventory=physical_inventory(model);atomic_json(out/'complete-source-inventory.json',inventory_evidence(inventory,decl['source_sha256']))
entities={p.id():p for p in inventory['products']}
assert set(decl['sample_step_ids'])<=set(entities)
selected=[entities[i] for i in decl['sample_step_ids']]
assert all(p.Representation is not None for p in selected)
settings=ifcopenshell.geom.settings();settings.set('iterator-output',ifcopenshell.ifcopenshell_wrapper.SERIALIZED);settings.set('use-world-coords',True)
iterator=ifcopenshell.geom.iterator(settings,model,4,include=selected)
seen=set();records=[];(out/'native-breps').mkdir()
def read_shape(data):
    shape=TopoDS_Shape();BRepTools.Read_s(shape,io.BytesIO(data),BRep_Builder());return shape
def inspect(module,data):
    shape=read_shape(data);t=time.perf_counter();result=module._inspect_shape(shape)
    return result,time.perf_counter()-t
assert iterator.initialize()
while True:
    obj=iterator.get();assert obj.id not in seen and obj.id in entities;seen.add(obj.id)
    data=obj.geometry.brep_data.encode('utf8');path=out/'native-breps'/f'{obj.id}.brep';path.write_bytes(data)
    emit('object_start',step_id=obj.id)
    rounds=[]
    for order in (('legacy','private'),('private','legacy')):
        row={}
        for name in order:
            result,seconds=inspect(legacy if name=='legacy' else cad,data);row[name]={'result':result,'seconds':seconds}
        assert row['legacy']['result']==row['private']['result'],(obj.id,row)
        rounds.append(row)
    record={'step_id':obj.id,'guid':entities[obj.id].GlobalId,'ifc_type':entities[obj.id].is_a(),'brep_sha256':sha256_file(path),'rounds':rounds}
    if rounds[0]['legacy']['result'][-1] in ('NO_CLOSED_CAD_SOLID','PARTIALLY_NON_SOLID_TOPOLOGY'):
        promotion={}
        for name,module in (('legacy',legacy),('private',cad)):
            t=time.perf_counter();promoted,evidence=module._promote_closed_surfaces(read_shape(data))
            inspection=None if promoted is None else module._inspect_shape(promoted)
            promotion[name]={'evidence':evidence,'inspection':inspection,'seconds':time.perf_counter()-t}
        assert promotion['legacy']['evidence']==promotion['private']['evidence'],(obj.id,promotion)
        assert promotion['legacy']['inspection']==promotion['private']['inspection'],(obj.id,promotion)
        record['promotion']=promotion
    records.append(record);atomic_json(out/'paired-results.json',records);emit('object_complete',step_id=obj.id,reason=rounds[0]['legacy']['result'][-1])
    if not iterator.next():break
assert seen==set(decl['sample_step_ids'])
assert sha256_file(source)==decl['source_sha256']
total={name:sum(r[name]['seconds'] for row in records for r in row['rounds']) for name in ('legacy','private')}
atomic_json(out/'child-result.json',{'status':'ALL_PAIRED_NATIVE_RESULTS_EQUAL','objects':len(records),'inspection_seconds':total,
    'source_unchanged':True,'seconds':time.perf_counter()-started,'scope':'Paired actual source BRep inspection and promotion sample only; no complete hospital clearance or acceptance.'})
emit('complete');events.close()
