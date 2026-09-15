from pathlib import Path
import cProfile,io,json,pstats,sys,time
import ifcopenshell
from oma.ifc.audit import sha256_file,atomic_json
from oma.ifc.enclosure import ExactIfcEncloser
from oma.ifc.inventory import physical_inventory,inventory_evidence
from oma.build_identity import checker_version
out=Path(sys.argv[1]);decl=json.loads((out/'predeclaration.json').read_text())
source=Path(decl['source']);assert sha256_file(source)==decl['source_sha256']
assert checker_version()==decl['checker_version']
started=time.perf_counter();log=(out/'progress.jsonl').open('w',encoding='utf8')
def emit(stage,**extra):log.write(json.dumps({'stage':stage,'seconds':time.perf_counter()-started,**extra})+'\n');log.flush()
emit('parse_start');model=ifcopenshell.open(str(source));emit('parse_end')
inventory=physical_inventory(model);products=[p for p in inventory['products'] if p.Representation is not None]
atomic_json(out/'inventory.json',inventory_evidence(inventory,decl['source_sha256']))
emit('inventory',represented=len(products));reader=ExactIfcEncloser(source,model,vertex_hull_completion=True)
rows=[];profile=cProfile.Profile()
for i,product in enumerate(products[:decl['limit']]):
    before=time.perf_counter();profile.enable();result=reader.enclose_product(product);profile.disable()
    rows.append({'step_id':product.id(),'guid':product.GlobalId,'seconds':time.perf_counter()-before,'result':result})
    emit('product',i=i+1,step_id=product.id(),status=result['status'],cache_hits=reader.support_cache_hits,cache_misses=reader.support_cache_misses)
    if (i+1)%25==0:profile.dump_stats(str(out/'profile.pstats'));atomic_json(out/'partial-results.json',rows)
profile.dump_stats(str(out/'profile.pstats'))
stream=io.StringIO();pstats.Stats(profile,stream=stream).sort_stats('cumulative').print_stats(45)
(out/'profile.txt').write_text(stream.getvalue(),encoding='utf8')
assert sha256_file(source)==decl['source_sha256']
atomic_json(out/'child-result.json',{'status':'BOUNDED_EXACT_SOURCE_PROFILE_COMPLETE','seconds':time.perf_counter()-started,'represented_total':len(products),'sample_count':len(rows),'products':rows,'source_unchanged':True,'native_clearance_claim':False})
emit('complete');log.close()
