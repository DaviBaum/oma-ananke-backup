"""Summarize bounded measurements without promoting partial geometry to PASS."""
from pathlib import Path
from collections import Counter,defaultdict
import hashlib,json,shutil,time,uuid
STAGE=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text(encoding='utf8'))
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf8')
def analyze(probe):
    events=[json.loads(l) for l in (probe/'progress.jsonl').read_text(encoding='utf8').splitlines()]
    stack=[];times=defaultdict(lambda:{'calls':0,'inclusive_seconds':0.,'exclusive_seconds':0.})
    for e in events:
        stage=e['stage']
        if stage.endswith('_start'):
            stack.append({'stage':stage[:-6],'start':e['seconds'],'child':0.,'step_id':e.get('step_id')})
        elif stage.endswith('_end'):
            key=stage[:-4]
            if not stack or stack[-1]['stage']!=key:raise AssertionError((key,stack))
            opened=stack.pop();dt=e['seconds']-opened['start'];r=times[key]
            r['calls']+=1;r['inclusive_seconds']+=dt;r['exclusive_seconds']+=dt-opened['child']
            if stack:stack[-1]['child']+=dt
    result=read(probe/'result.json');declaration=read(probe/'predeclaration.json')
    return {'probe':probe.name,'mode':declaration['mode'],'result_sha256':sha(probe/'result.json'),
        'supervision_status':result['supervision']['status'],'elapsed_seconds':result['supervision']['elapsed_seconds'],
        'native_objects_emitted':sum(e['stage']=='iterator_get_end' for e in events),
        'enclosures_completed':dict(Counter(e['status'] for e in events if e['stage']=='exact_enclosure_result')),
        'completed_stage_times':dict(times),'unfinished_stages':stack,
        'original_source_and_app_unchanged':result['source_and_app_unchanged'],
        'active_processes_after':result['supervision']['containment']['active_processes'],
        'timing_scope':'Inclusive times overlap; exclusive times subtract fully completed nested observed stages only. Native iterator conversion also runs asynchronously.'}
probes=[STAGE/'probes'/x for x in ('42d47815990c4d54b3b621f4fafe83b7','72174c8c8efc4a46adea8cf95f90f82c','f09e1e3bdbb34834924317ba1862c9f3')]
measurements=[analyze(p) for p in probes]
paired=STAGE/'paired/488cca1e07ee4509851d69e585733809';rows=read(paired/'paired-results.json')
sample={'objects':len(rows),'two_alternating_rounds':True,'raw_dispositions':dict(Counter(row['rounds'][0]['legacy']['result'][-1] or 'VALID_SOLID' for row in rows)),
        'raw_inspection_seconds':{name:sum(r[name]['seconds'] for row in rows for r in row['rounds']) for name in ('legacy','private')},
        'promotion_plus_final_inspection_seconds':{name:sum(row['promotion'][name]['seconds'] for row in rows if 'promotion' in row) for name in ('legacy','private')},
        'every_raw_tuple_and_promotion_evidence_equal':True,'receipt_sha256':sha(paired/'result.json'),
        'scope':'Deliberate first12+observed slow8 timing sample; no estimate of full hospital clearance speedup.'}
test=STAGE/'validation/80997a76c2694cc385db89872d8b6afe'
assert read(test/'result.json')['status']=='PRIVATE_FOCUSED_TESTS_PASS'
out=STAGE/'handoff'/uuid.uuid4().hex;out.mkdir(parents=True);shutil.copyfile(__file__,out/'executed.py')
write(out/'measurements.json',measurements);write(out/'paired-summary.json',sample)
source=read(STAGE/'source-declaration.json')
result={'schema':'oma.private-hospital-native-performance-review/1','status':'BOUNDED_DIAGNOSIS_AND_PRIVATE_PREREQUISITE_FIX_VALIDATED',
    'base_source':source['base_source'],'private_source':source['private_source'],'private_cad_sha256':source['private_files']['oma/ifc/cad.py'],
    'complete_source_represented_products':14409,'baseline_90s_native_products':measurements[0]['native_objects_emitted'],
    'private_90s_native_products':measurements[2]['native_objects_emitted'],'exact_first_90s_completed':sum(measurements[1]['enclosures_completed'].values()),
    'focused_tests':read(test/'result.json')['counts'],'test_result_sha256':sha(test/'result.json'),
    'independent_review':'evidence/math/hospital-prerequisite-review/786fd7b9ef6648c8b05ec1ee8f425fdf',
    'findings':[
        'Initial IFC parse/iterator wait are not the dominant observed serial stages; native topology inspection, sewing/promotion and exact fallback consume the sampled time.',
        'Skip geometric validity analysis only after existing unconditional no-solid/full-solid-topology prerequisite failures; successful native solid, promotion, fallback and full inventory obligations remain.',
        'The paired20-BRep sample shows a raw inspection improvement with equal outcomes. The one-shot full-loader90s probes show only736 versus748 emitted products; no material whole-hospital speedup is established.',
        'The fresh enclosure-first90s probe completed707 products, so current exact enclosure evaluation is also costly. A lazy broadphase redesign is not justified as an immediate measured solution.',
        'No-solid analyzer exceptions may now reach checked promotion/enclosure; this intentional failure-path difference is documented and independently tested.'],
    'historical_hospital_status':'UNKNOWN_TIMEOUT_UNCHANGED','full_hospital_rerun':False,'production_modified':False,
    'limitations':['No complete source clearance report, selection, acceptance or IFC export was produced by these observations.',
        'Samples and concurrent machine load do not establish a stable full-corpus speedup.',
        'Any future lazy path must freshly prove all authoritative Body/Facetation/unnamed representation support and retain unknown/missing products, openings, complete federation identity, and native refinement near uncertain pairs.'],
    'retained_initial_harness_failures':['probes/7f814d369f4540f69ca225c2449d4673: observer attempted to JSON encode iterator.next entity',
        'paired/d28a127b4c8e472d858fd97865b5b85c: supervisor environment lacked OMA_EXECUTABLE_BUILD; no child launched',
        'validation/6730879b3299499db783b29e534f4e06:139passed,1missing copied network-spec fixture; corrected140passed with unchanged app']}
write(out/'result.json',result)
(out/'README.md').write_text('The private change delays expensive native topology analysis until the existing complete-solid prerequisites pass. All successful native solid checks remain mandatory. Twenty retained hospital BReps produced identical raw inspection tuples and promotion outcomes; 140 focused tests and six independent loader fault/cancellation tests passed.\n\nThe bounded whole-loader observation advanced only from 736 to 748 represented products in 90 seconds. This does not resolve the historical 1,800-second hospital timeout. Exact-enclosure-first also processed only 707 products in its own 90-second observation. No full clearance, acceptance, export or whole-hospital speedup is claimed. Production and original IFC bytes were not modified.\n',encoding='utf8')
paths=[p for p in STAGE.rglob('*') if p.is_file() and '__pycache__' not in p.parts and '.pytest_cache' not in p.parts and p!=out/'index.json']
write(out/'index.json',{'schema':'oma.private-evidence-file-inventory/1','root':str(STAGE),'files':[{'path':p.relative_to(STAGE).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(paths)]})
print(json.dumps({'directory':str(out),'status':result['status'],'measurements':[{k:m[k] for k in ('mode','native_objects_emitted','enclosures_completed')} for m in measurements],'sample':sample,'result_sha256':sha(out/'result.json')},indent=2))
