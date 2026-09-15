from pathlib import Path
from collections import Counter
import json,sys,time
from oma.build_identity import checker_version
from oma.ifc.audit import atomic_json,sha256_file
from oma.ifc import cad,enclosure
from oma.ifc.federation import audited_local_federation
out=Path(sys.argv[1]);decl=json.loads((out/'predeclaration.json').read_text())
assert checker_version()==decl['checker_version']
source=Path(decl['source']);export=Path(decl['export'])
assert sha256_file(source)==decl['source_sha256'] and sha256_file(export)==decl['export_sha256']
start=time.perf_counter();counts=Counter();enc=Counter();native_calls=0
log=(out/'progress.jsonl').open('w',encoding='utf8')
def emit(stage,**fields):
    log.write(json.dumps({'stage':stage,'seconds':time.perf_counter()-start,**fields})+'\n');log.flush()
def checkpoint(stage):
    counts[stage]+=1
    if counts[stage]<=2 or counts[stage]%100==0:emit(stage,count=counts[stage],enclosures=dict(enc))
    if time.perf_counter()-start>590:raise TimeoutError('Private full-CAD probe cooperative deadline')
original=enclosure.ExactIfcEncloser.enclose_product
def observed(self,product):
    result=original(self,product);enc[result['status']]+=1
    if sum(enc.values())%100==0:emit('enclosure_completed',count=sum(enc.values()),statuses=dict(enc),step_id=product.id())
    return result
enclosure.ExactIfcEncloser.enclose_product=observed
emit('derive_federation')
frame=audited_local_federation([{'source_path':str(source),'source_sha256':decl['source_sha256'],'units':{'status':'KNOWN'}}],decl['source_sha256'])
assert frame['status']=='VERIFIED';atomic_json(out/'federation.json',frame)
emit('cad_check_start')
result=cad.cad_check_routes([source],export,decl['route_guids'],clearance_m=decl['clearance_m'],
    numerical_tolerance_m=decl['numerical_tolerance_m'],source_representation_policy=decl['source_representation_policy'],
    coordinate_evidence=frame,cache_directory=out/'cache',threads=4,checkpoint=checkpoint,output_path=out/'cad-report.json')
assert result['route_count']==4 and result['obstacle_count']==14409 and result['pairs_accounted']==57636
assert len(result['self_pair_results'])==6
assert sha256_file(source)==decl['source_sha256'] and sha256_file(export)==decl['export_sha256']
summary={'status':'COMPLETE_NATIVE_CAD_PROBE','cad_status':result['status'],'coordination_status':result['coordination_status'],
    'seconds':time.perf_counter()-start,'source_sha256':sha256_file(source),'export_sha256':sha256_file(export),
    'route_count':result['route_count'],'obstacle_count':result['obstacle_count'],'pairs_accounted':result['pairs_accounted'],
    'self_pairs':len(result['self_pair_results']),'failed_pairs':result['failed_pairs'],'unknown_pairs':result['unknown_pairs'],
    'blocked_pairs':result['blocked_pairs'],'missing_geometry':len(result['missing_geometry']),
    'enclosure_counts':dict(enc),'stage_counts':dict(counts),'performance':result['performance'],
    'preservation':result['coordinate_status'],'cad_report_sha256':sha256_file(out/'cad-report.json'),
    'scope':'Retained unchecked Hospital candidate geometry against all original ARC obstacles. No service/selection/accept/export publication claim; original timed-out evidence untouched.'}
atomic_json(out/'child-result.json',summary);emit('complete',cad_status=result['status']);log.close()
