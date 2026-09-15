"""Read-only exact audit of a retained generated-tree native workflow."""
from pathlib import Path
from itertools import combinations
import hashlib,importlib.util,json,math,shutil,sqlite3,sys,uuid,zlib
import xml.etree.ElementTree as ET

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').exists())
V=ROOT/'.oma/development/shared-tree-native/validation/f9c75d13b1334319a6d4822e3acc05da'
OLD=V.parent/'db3afa0073b64ed5aa0da8465e3e0492'
OUT=Path(__file__).resolve().parent/'attempts'/uuid.uuid4().hex
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,v):Path(p).write_text(json.dumps(v,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def main():
    from oma.build_identity import checker_version
    import oma.optimization.shared_tree_synthesis as kernel
    import ifcopenshell
    OUT.mkdir(parents=True);shutil.copyfile(__file__,OUT/'executed-audit.py')
    receipt=read(V/'result.json');runtime=Path(receipt['source_directory'])
    assert checker_version()==receipt['checker_version']
    assert {f.relative_to(runtime).as_posix():sha(f) for f in runtime.rglob('*.py')}==receipt['source_files']
    assert all(sha(V/k)==v for k,v in receipt['inputs'].items())
    xml=ET.parse(V/'tests.xml').getroot();assert len(xml.findall('.//testcase'))==24 and not any(xml.findall('.//'+k) for k in ('failure','error','skipped'))
    database=next(V.rglob('oma.sqlite3'));store=database.parent
    db=sqlite3.connect(database.resolve().as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    def table(name):return [dict(r) for r in db.execute('SELECT * FROM '+name)]
    before={t:table(t) for t in ('projects','runs','candidates','revisions','check_executions')}
    blobs={}
    def get(root):
        if root not in blobs:
            value=json.loads(zlib.decompress((store/'blobs'/(root+'.json.z')).read_bytes()));assert digest(value)==root;blobs[root]=value
        return blobs[root]
    for file in (store/'blobs').glob('*.z'):
        value=get(file.name.removesuffix('.json.z'))
    generation_root,generation=next((h,v) for h,v in blobs.items() if isinstance(v,dict) and v.get('status')=='PROPOSALS_READY')
    export_root,export=next((h,v) for h,v in blobs.items() if isinstance(v,dict) and 'verification_root' in v)
    project,=before['projects'];revision=next(r for r in before['revisions'] if r['revision']==2)
    selected=next(c for c in before['candidates'] if c['id']==revision['candidate_id'])
    assert project['status']=='ACCEPTED' and project['revision']==2 and project['state_root']==revision['root']==selected['state_root']
    assert selected['status']=='CHECKED' and export['candidate_id']==selected['id']
    run=next(r for r in before['runs'] if r['id']==selected['run_id']);request=json.loads(run['request'])
    assert run['status']=='COMPLETED' and request['mission']==generation['mission']
    baseline=get(run['base_root']);source,=baseline['sources'];original=Path(json.loads(next(r for r in before['runs'] if r['operation']=='import')['request'])['paths'][0])
    assert sha(original)==source['sha256']==sha(source['immutable_path'])
    fixture=load('review_fixture',V/'tests/test_shared_tree_proposals.py');r,s,_=fixture.fixture();r['source_id']=source['id']
    context={'base_root':run['base_root'],'source_sha256':source['sha256'],'checker_version':checker_version()}
    assert generation['input_root']==digest({'requirements':r,'search':s,'context':context})
    old_fixture=load('old_review_fixture',OLD/'tests/test_shared_tree_proposals.py');old_r,old_s,_=old_fixture.fixture()
    amended=read(V/'tests/test_shared_tree_proposals.py') if False else fixture.fixture()[0]
    assert s==old_s
    for sink in old_r['sinks']:assert 'available_static_pressure_pa' not in sink;sink['available_static_pressure_pa']=100
    assert old_r==amended
    # Independent pure kernel replay, with its producer entry points disabled.
    kernel.compile_shared_tree_catalogue=lambda *a,**k:(_ for _ in ()).throw(AssertionError('producer disabled'))
    kernel._producer_assignments=kernel.compile_shared_tree_catalogue
    proof=kernel.verify_shared_tree_catalogue(generation['generation']['catalogue'],generation['synthesis']['certificate'],max_results=8)
    assert proof['status']=='PASS' and proof['counts']['complete_assignments']==12 and len(proof['proposals'])==8
    assert proof['proposals']==generation['synthesis']['proposals']
    write(OUT/'independent-catalogue-proof.json',proof);write(OUT/'generation.json',generation)
    original_model=ifcopenshell.open(str(original));summaries=[]
    for index,candidate in enumerate(before['candidates']):
        report=get(candidate['report_root']);state=get(candidate['state_root']);network,=state['physical_networks'];material=get(network['geometry_artifact'])
        assert report['candidate_root']==candidate['state_root'] and report['checker_version']==checker_version()
        output=Path(material['export_path']);assert sha(output)==material['export_sha256']
        actual=ifcopenshell.open(str(output));changed=[e.id() for e in original_model if str(e)!=str(actual.by_id(e.id()))];assert not changed
        target=OUT/('candidate-'+str(index));target.mkdir();shutil.copyfile(output,target/'network.ifc')
        for name,value in [('candidate',candidate),('state',state),('report',report),('materialization',material)]:write(target/(name+'.json'),value)
        rows={x['id']:x for x in report['results']};assert len(rows)==len(report['results'])
        is_export=report['candidate_root']==export['exported_state_root']
        if not is_export:
            expected=generation['mission']['network_alternatives'][index]
            spec=dict(json.loads(candidate['payload'])['networks'][0]['spec']);spec.pop('source_to_federation_matrix',None);assert spec==expected
            native_spec=dict(material['network_spec']);native_spec.pop('source_to_federation_matrix',None);assert native_spec==expected
        summary={'candidate_id':candidate['id'],'status':candidate['status'],'state_root':candidate['state_root'],'report_root':candidate['report_root'],
                 'network_id':network['id'],'parts':len(network['component_ids']),'export_sha256':sha(output),'fresh_export_recheck':is_export,
                 'original_parsed_entities':len(list(original_model)),'objective':report['objective']}
        if candidate['status']=='REJECTED':
            negative=rows['network-native-counterexample'];assert negative['status']=='FAIL'
            assert rows['network-all-source-clearance']['status']=='NOT_RUN' and report['status']=='FAIL'
            summary.update(negative_witness=negative['witness'],full_source_denominator='NOT_RUN',
                           objective_scope='Native component measurements retained; rejected candidate has no feasibility or selection authority')
        else:
            assert report['status']=='PASS' and rows['network-demand-conditioned-service']['status']=='PASS'
            cad_root=rows['network-all-source-clearance']['witness']['artifact'];cad=get(cad_root);write(target/'cad.json',cad)
            sem=get(rows['network-native-semantics']['witness']['artifact']);write(target/'semantics.json',sem)
            guids={p['ifc_guid'] for p in sem['parts']};pairs=[frozenset(x['participant_guids']) for x in cad['self_pair_results']]
            assert len(guids)==8 and sem['physical_ports']==17 and len({(p['component_id'],p['slot']) for p in sem['ports']})==17
            assert cad['route_count']==8 and cad['obstacle_count']==2 and cad['pairs_accounted']==16
            assert len(pairs)==len(set(pairs))==28 and set(pairs)=={frozenset(x) for x in combinations(guids,2)}
            assert cad['coordination_status']==cad['self_interference_status']=='PASS'
            assert math.isclose(report['objective']['length_m'],8+math.pi/4,abs_tol=1e-9) and report['objective']['fitting_count']==3
            summary.update(source_pairs=16,self_pairs=28,ports=17,service='PASS')
        execution=next(x for x in before['check_executions'] if x['candidate_id']==candidate['id'] and x['report_root']==candidate['report_root'])
        assert execution['status']=='COMPLETED'
        execution_evidence=get(execution['evidence_root']);write(target/'execution.json',execution_evidence)
        assert execution_evidence['report_published'] and execution_evidence['supervision']['status']=='COMPLETED'
        summaries.append(summary)
    assert sum(c['status']=='REJECTED' for c in summaries)==7
    assert export['status']=='CHECKED_LOCAL_SCOPE' and export['round_trip']=='PASS'
    fresh=next(c for c in before['candidates'] if c['report_root']==export['verification_root'])
    assert fresh['state_root']!=selected['state_root'] and fresh['status']=='CHECKED'
    for file in export['files']:assert sha(file['path'])==file['sha256']
    assert {t:table(t) for t in before}==before;db.close()
    assert sha(original)==source['sha256'] and all(sha(V/k)==v for k,v in receipt['inputs'].items())
    assert {f.relative_to(runtime).as_posix():sha(f) for f in runtime.rglob('*.py')}==receipt['source_files']
    shutil.copyfile(original,OUT/'original.ifc');write(OUT/'export-manifest.json',export);write(OUT/'store-rows.json',before)
    write(OUT/'result.json',{'status':'PASS','reviewed_runtime':checker_version(),'source_files_checked':len(receipt['source_files']),
        'suite_cases':24,'workflow_receipt_sha256':sha(V/'result.json'),'original_store_unchanged':True,
        'generated_connectors':20,'complete_finite_assignments':12,'returned_and_native_checked_alternatives':8,
        'selected_candidate':selected['id'],'accepted_revision':2,'fresh_candidate':fresh['id'],'fresh_report_root':fresh['report_root'],
        'export_manifest_root':export_root,'generation_root':generation_root,'candidates':summaries,
        'historical_amendment':{'old_validation':str(OLD),'old_status':read(OLD/'result.json')['status'],
            'change':'Added explicit hypothetical available_static_pressure_pa=100 for each of two sinks; no other requirement/search field changed. Old incomplete mission remains failed.'},
        'limits':['Generator provenance checker is separately under review; this replays finite catalogue assignment proof only.',
                  'Only returned eight alternatives received native checks; four finite assignments not materialized. No continuous/global native optimum claim.',
                  'Canonical parsed original IFC entities preserved; no raw serialized STEP spelling identity claim.']})
    print(json.dumps({'status':'PASS','output':str(OUT),'selected':selected['id'],'fresh':fresh['id'],'candidate_rows':len(summaries)}))

if __name__=='__main__':main()
