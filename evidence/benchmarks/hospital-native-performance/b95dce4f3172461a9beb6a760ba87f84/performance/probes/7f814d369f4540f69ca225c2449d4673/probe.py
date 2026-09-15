"""Observational wrappers around unchanged native loading; no geometric exclusions."""
from pathlib import Path
import json,sys,time

mode,source_arg,out_arg=sys.argv[1:];source=Path(source_arg);out=Path(out_arg)
start=time.monotonic();counts={};current={'step_id':None};log=(out/'progress.jsonl').open('a',encoding='utf8')
def emit(stage,**extra):
    counts[stage]=counts.get(stage,0)+1
    log.write(json.dumps({'seconds':time.monotonic()-start,'stage':stage,'count':counts[stage],**extra})+'\n');log.flush()
emit('process_started',mode=mode)
import ifcopenshell,ifcopenshell.geom
from oma.ifc import cad,enclosure
from oma.ifc.audit import atomic_json
emit('imports_complete')
real_open=ifcopenshell.open
def observed_open(*args,**kwargs):
    emit('ifc_parse_start');result=real_open(*args,**kwargs);emit('ifc_parse_end');return result
ifcopenshell.open=observed_open
def observe_function(owner,name):
    original=getattr(owner,name)
    def wrapped(*args,**kwargs):
        emit(name+'_start',step_id=current['step_id'])
        try:return original(*args,**kwargs)
        finally:emit(name+'_end',step_id=current['step_id'])
    setattr(owner,name,wrapped)
for name in ('_inspect_shape','_complete_representation_support','_promote_closed_surfaces'):observe_function(cad,name)
original_enclose=enclosure.ExactIfcEncloser.enclose_product
def observed_enclose(self,product):
    current['step_id']=product.id();emit('exact_enclosure_start',step_id=product.id())
    try:
        result=original_enclose(self,product)
        emit('exact_enclosure_result',step_id=product.id(),status=result['status'],reason=result.get('reason'),cache_hits=self.support_cache_hits,cache_misses=self.support_cache_misses)
        return result
    finally:emit('exact_enclosure_end',step_id=product.id())
enclosure.ExactIfcEncloser.enclose_product=observed_enclose
original_iterator=ifcopenshell.geom.iterator
class ObservedIterator:
    def __init__(self,*args,**kwargs):
        emit('iterator_construct_start',selected_count=len(kwargs.get('include',[])))
        self.actual=original_iterator(*args,**kwargs);emit('iterator_construct_end')
    def initialize(self):
        emit('iterator_initialize_start');result=self.actual.initialize();emit('iterator_initialize_end',result=result);return result
    def get(self):
        emit('iterator_get_start');result=self.actual.get();current['step_id']=result.id;emit('iterator_get_end',step_id=result.id);return result
    def next(self):
        emit('iterator_next_start',previous_step_id=current['step_id']);result=self.actual.next();emit('iterator_next_end',result=result);return result
ifcopenshell.geom.iterator=ObservedIterator
if mode=='native':
    inventory={}
    objects,errors=cad._load_cad_uncached(source,threads=4,source_representation_policy=cad.VERTEX_HULL_SOURCE_REPRESENTATION_POLICY,
        checkpoint=lambda stage:emit('checkpoint:'+stage),inventory_report=inventory)
    atomic_json(out/'child-result.json',{'status':'COMPLETE_OBSERVATIONAL_LOAD','objects':len(objects),'errors':errors,'inventory':inventory,'seconds':time.monotonic()-start})
elif mode=='enclosure':
    from oma.ifc.inventory import physical_inventory,inventory_evidence
    model=ifcopenshell.open(str(source));emit('inventory_start');inventory=physical_inventory(model);emit('inventory_end',physical_count=len(inventory['products']),errors=len(inventory['errors']))
    emit('exact_reader_start');reader=enclosure.ExactIfcEncloser(source,model,vertex_hull_completion=True);emit('exact_reader_end')
    rows=[]
    for product in inventory['products']:
        if product.Representation is None:continue
        result=reader.enclose_product(product)
        rows.append({'step_id':product.id(),'guid':product.GlobalId,'ifc_type':product.is_a(),**result})
    atomic_json(out/'child-result.json',{'status':'COMPLETE_EXACT_SUPPORT_INVENTORY','inventory':inventory_evidence(inventory,reader.raw.source_sha256),'objects':rows,'seconds':time.monotonic()-start})
else:raise ValueError(mode)
emit('process_complete');log.close()
