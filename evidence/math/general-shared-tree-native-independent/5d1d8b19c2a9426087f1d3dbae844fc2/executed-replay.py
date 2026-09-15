"""Read-only audit of final generated coupled job/native/accept/export evidence."""
from collections import Counter
from copy import deepcopy
from itertools import combinations
from pathlib import Path
import difflib,hashlib,json,os,shutil,sqlite3,time,uuid,zlib
import xml.etree.ElementTree as ET

from oma.routing.network_scenario import SharedNetworkScenario
from oma.routing.shared_tree_catalogue_check import verify_generated_catalogue
from oma.optimization.shared_tree_synthesis import verify_shared_tree_catalogue
from oma.routing import coupled_tree_pressure as adapter
from oma.store import digest

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').exists())
STAGE=Path(__file__).resolve().parent
V=ROOT/'.oma/development/general-shared-tree-native/validation/2e3b9cc8205c4386b28982cfebd13bd2'
OLD=V.parent/'0efc7bd0ad4444e6acbb5d167f1ce01b'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def write(p,v):Path(p).write_text(json.dumps(v,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf8')

class Archive:
    def __init__(self,path):
        self.path=path;self.db=sqlite3.connect((path/'oma.sqlite3').resolve().as_uri()+'?mode=ro',uri=True);self.db.row_factory=sqlite3.Row
        self.tables={t:[dict(r) for r in self.db.execute('SELECT * FROM '+t)] for t in ('projects','runs','candidates','revisions','check_executions','candidate_check_executions','events')}
        self.blobs={}
    def get(self,root):
        if root not in self.blobs:
            v=json.loads(zlib.decompress((self.path/'blobs'/(root+'.json.z')).read_bytes()));assert digest(v)==root;self.blobs[root]=v
        return self.blobs[root]
    def unchanged(self):return all([dict(r) for r in self.db.execute('SELECT * FROM '+t)]==v for t,v in self.tables.items())
    def request(self,operation):
        row=next(r for r in self.tables['runs'] if r['operation']==operation)
        return row,json.loads(row['request'])

def audit_archive(archive,out,positive):
    out.mkdir();write(out/'store-rows.json',archive.tables)
    for p in (archive.path/'blobs').glob('*.json.z'):archive.get(p.name.removesuffix('.json.z'))
    packets=[(h,v) for h,v in archive.blobs.items() if isinstance(v,dict) and v.get('schema')=='oma.shared-tree-project-proposals/1']
    assert len(packets)==1;root,packet=packets[0];write(out/'generated-packet.json',packet)
    proposed,query=archive.request('propose_network');run,optimization=archive.request('optimize')
    assert proposed['status']=='COMPLETED' and query['mission']==packet['authored_query']
    assert packet['context']['base_root']==proposed['base_root'] and packet['context']['request_root']==digest(query)
    assert packet['context']['project_id']==proposed['project_id'] and packet['context']['checker_version']==VERSION
    assert packet['project_state_changed'] is False and packet['native_feasibility_or_acceptance_claim'] is False
    authored=packet['authored_query'];generated=packet['result']
    assert 'network_alternatives' not in authored['requirements'] and len(authored['search']['tee_instances'])==3
    proof=verify_generated_catalogue(authored['requirements'],authored['search'],generated['generation'],context=packet['context'])
    finite=verify_shared_tree_catalogue(generated['generation']['catalogue'],generated['synthesis']['certificate'],max_results=authored['max_results'],max_work=10000000,max_partial_trees=200000)
    assert proof['status']==finite['status']=='PASS' and finite['proposals']==generated['synthesis']['proposals']
    assert optimization['mission']==generated['mission'] and len(optimization['mission']['network_alternatives'])==2
    write(out/'provenance-replay.json',proof);write(out/'finite-replay.json',finite)
    project,=archive.tables['projects'];cases=[];files={};pass_checks=[]
    for candidate in archive.tables['candidates']:
        folder=out/candidate['id'];folder.mkdir()
        state=archive.get(candidate['state_root']);report=archive.get(candidate['report_root']);checks={r['id']:r for r in report['results']}
        assert len(checks)==len(report['results']) and report['checker_version']==VERSION and report['candidate_root']==candidate['state_root']
        write(folder/'candidate.json',candidate);write(folder/'state.json',state);write(folder/'report.json',report)
        material=archive.get(state['physical_networks'][0]['geometry_artifact']);write(folder/'materialization.json',material)
        actual=Path(material['export_path']);assert sha(actual)==material['export_sha256'];files[str(actual)]=sha(actual)
        shutil.copy2(actual,folder/'actual.ifc')
        import ifcopenshell
        source=next(s for s in state['sources'] if s['sha256']==material['source_sha256']);path=Path(source['immutable_path'])
        assert sha(path)==source['sha256'];files[str(path)]=sha(path)
        before=ifcopenshell.open(str(path));after=ifcopenshell.open(str(actual))
        changed=[e.id() for e in before if str(e)!=str(after.by_id(e.id()))];assert not changed
        case={'candidate_id':candidate['id'],'status':candidate['status'],'state_root':candidate['state_root'],'report_root':candidate['report_root'],
              'checks':{k:r['status'] for k,r in checks.items()},'export_sha256':material['export_sha256'],'parsed_original_entities':len(list(before)),
              'changed_parsed_entities':changed,'objective':report['objective']}
        for key,check in checks.items():
            for field in ('artifact','native_metrics_artifact'):
                a=(check.get('witness') or {}).get(field)
                if a:write(folder/(key+'-'+field+'.json'),archive.get(a))
        if checks.get('network-all-source-clearance',{}).get('status')=='PASS':
            cad=archive.get(checks['network-all-source-clearance']['witness']['artifact']);sem=archive.get(checks['network-native-semantics']['witness']['artifact'])
            guids=[p['ifc_guid'] for p in sem['parts']]
            assert len(guids)==len(set(guids))==14 and cad['route_count']==14 and cad['obstacle_count']==2 and cad['pairs_accounted']==28
            assert len(cad['self_pair_results'])==91 and all(x['status']=='PASS' for x in cad['self_pair_results'])
            assert {frozenset(x['participant_guids']) for x in cad['self_pair_results']}=={frozenset(x) for x in combinations(guids,2)}
            assert sem['physical_ports']==len(sem['ports'])==31 and checks['network-permitted-zone']['status']=='PASS'
            case['native']={'components':14,'ports':31,'source_obstacles':2,'source_pairs':28,'self_pairs':91,'status':'PASS'}
        if candidate['status']=='CHECKED':
            assert positive and report['status']=='PASS' and checks['network-pressure-operating-point']['status']==checks['network-demand-conditioned-service']['status']=='PASS'
            calc=checks['network-demand-conditioned-service']['witness']['calculation'];stored=calc['independent_check']
            contract=state['derived_artifacts']['network_contract'];scenario=SharedNetworkScenario.model_validate(contract['scenario'])
            network=next(n for n in scenario.network_alternatives if n.network_id==contract['selected_alternative'])
            owner=next(r for r in archive.tables['runs'] if r['id']==candidate['run_id'])
            metric_root=checks['network-pressure-operating-point']['witness']['native_metrics_artifact'];metrics=archive.get(metric_root)
            context={'candidate_root':candidate['state_root'],'baseline_root':owner['base_root'],'source_sha256':source['sha256'],'export_sha256':material['export_sha256'],
                'native_semantics_root':checks['network-native-semantics']['witness']['artifact'],'native_metrics_root':metric_root,
                'native_cad_root':checks['network-all-source-clearance']['witness']['artifact'],'checker_version':VERSION,
                'mission_hash':digest(state['mission']),'rule_hash':state['mission']['rule_hash'],'native_metric_absolute_tolerance_m':'1/1000000'}
            fresh=adapter.verify_coupled_tree_envelope(scenario.coupled_tree,network,metrics,calc['certificate'],context=context)
            assert fresh==stored and fresh['status']==fresh['verdict']==fresh['local_check']['status']==fresh['global_check']['status']=='PASS'
            service=fresh['service'];assert service['counts']=={'physical_ports':31,'deliveries':4,'conservation_identities':32,'head_path_identities':35}
            assert len({(x['component'],x['port']) for x in service['physical_ports']})==31
            assert all(x['forward_status']==x['maximum_velocity_status']=='PASS' for x in service['physical_ports'])
            assert len(service['deliveries'])==4 and all(x['status']=='PASS' for x in service['deliveries'])
            assert all(x['difference']=={} for x in service['conservation_identities'])
            assert len({x['id'] for x in service['conservation_identities']})==32 and len({x['id'] for x in service['head_path_identities']})==35
            write(folder/'independent-pressure-replay.json',fresh)
            case['pressure']={'model_root':fresh['model_root'],'local_certificate_root':fresh['local_check']['certificate_root'],
                'global_certificate_root':fresh['global_check']['certificate_root'],'counts':service['counts'],'deliveries':service['deliveries']}
            head=next(e for e in archive.tables['candidate_check_executions'] if e['candidate_id']==candidate['id'])
            completed=[e for e in archive.tables['check_executions'] if e['execution_id']==head['execution_id'] and e['candidate_id']==candidate['id'] and e['status']=='COMPLETED' and e['report_root']==candidate['report_root']]
            assert len(completed)==1
            binding=json.loads(completed[0]['binding'])
            assert binding['candidate_root']==candidate['state_root'] and binding['checker_version']==VERSION and binding['mission_hash']==digest(state['mission']) and binding['rule_hash']==state['mission']['rule_hash']
            assert completed;execution=archive.get(completed[-1]['evidence_root'])
            assert execution['status']==execution['supervision']['status']=='COMPLETED' and execution['supervision']['containment']['active_processes']==0
            write(folder/'execution-evidence.json',execution);pass_checks.append(case)
        else:
            assert candidate['status'] in ('UNKNOWN','REJECTED')
            case['nonpassing']={k:v for k,v in checks.items() if v['status'] not in ('PASS','NOT_APPLICABLE')}
        cases.append(case)
    if positive:
        assert run['status']=='COMPLETED' and project['revision']==2 and project['status']=='ACCEPTED' and len(pass_checks)==2
        revision=next(r for r in archive.tables['revisions'] if r['revision']==2)
        selected=next(c for c in pass_checks if c['candidate_id']==revision['candidate_id'])
        assert project['state_root']==revision['root']==selected['state_root']
        events=[json.loads(e['payload']) for e in archive.tables['events']]
        decision=[e for e in events if e.get('run_id')==run['id'] and e.get('stage')=='complete'][-1]
        assert decision['payload']['selected_candidate_ids']==[selected['candidate_id']]
        assert decision['payload']['global_gap'] is None and decision['payload']['global_lower_bound'] is None
        write(out/'selection-event.json',decision)
        exports=[(h,v) for h,v in archive.blobs.items() if isinstance(v,dict) and 'verification_root' in v and v.get('candidate_id')==selected['candidate_id']]
        export_root,export=exports[0];write(out/'export-manifest.json',export)
        assert len(export['checking']['release_bindings'])==9 and all(x is True for x in export['checking']['release_bindings'].values())
        fresh=next(c for c in pass_checks if c['candidate_id']==export['checking']['exported_candidate_id'])
        assert fresh['report_root']==export['verification_root'] and fresh['state_root']!=selected['state_root']
        assert fresh['pressure']['model_root']!=selected['pressure']['model_root'] and fresh['pressure']['deliveries']==selected['pressure']['deliveries']
    else:
        assert run['status']=='NO_INCUMBENT_FOUND' and project['revision']==1 and not pass_checks and len(cases)==2
        unknown=next(c for c in cases if c['status']=='UNKNOWN')
        assert 'native' in unknown and unknown['checks']['network-pressure-operating-point']==unknown['checks']['network-demand-conditioned-service']=='UNKNOWN'
        assert unknown['nonpassing']['network-pressure-operating-point']['reason'].startswith('Operating relation unverified:')
        export_root=None;selected=None;fresh=None
    assert archive.unchanged() and all(sha(p)==h for p,h in files.items())
    retained=out/'blobs';retained.mkdir()
    for h in archive.blobs:
        shutil.copy2(archive.path/'blobs'/(h+'.json.z'),retained/(h+'.json.z'))
    imported,import_query=archive.request('import')
    for number,path in enumerate(import_query['paths']):shutil.copy2(path,out/('original-'+str(number)+'.ifc'))
    return {'status':'PASS','generation_root':root,'authored_query':authored,'catalogue_provenance':proof,'finite_proof':finite,
        'cases':cases,'source_and_actual_files':files,'original_store_unchanged':True,'accepted_revision':project['revision'],
        'selected_candidate_id':selected['candidate_id'] if selected else None,'fresh_export_candidate_id':fresh['candidate_id'] if fresh else None,'export_manifest_root':export_root}

def main():
    global VERSION
    from fractions import Fraction
    from oma.build_identity import checker_version
    from oma.routing import shared_tree_proposals as producer
    from oma.optimization import shared_tree_synthesis as synthesis
    started=time.monotonic()
    out=ROOT/'evidence/math/general-shared-tree-native-independent'/uuid.uuid4().hex
    out.mkdir(parents=True)
    shutil.copy2(__file__,out/'executed-replay.py')
    receipt=read(V/'result.json');VERSION=receipt['checker_version'];src=Path(receipt['source_directory'])
    assert checker_version()==VERSION
    assert {p.relative_to(src).as_posix():sha(p) for p in src.rglob('*.py')}==receipt['source_files']
    assert all(sha(V/p)==h for p,h in receipt['input_files'].items())
    assert receipt['status']=='PASS' and receipt['returncode']==0
    xml=ET.parse(V/'tests.xml').getroot()
    assert len(xml.findall('.//testcase'))==13 and not any(xml.findall('.//'+k) for k in ('failure','error','skipped'))
    for p in ('result.json','tests.xml','pytest.log','runner.py'):shutil.copy2(V/p,out/('validation-'+p))
    def forbidden(*args,**kwargs):raise AssertionError('Producer must not run in independent review')
    producer.build_connector_catalogue=producer.compile_shared_tree_proposals=forbidden
    synthesis.compile_shared_tree_catalogue=synthesis._producer_assignments=synthesis._producer_general_assignments=forbidden
    adapter.evaluate_coupled_tree=adapter.local.compile_coupled_tree_pressure=adapter.global_proof.compile_coupled_tree_univalence=forbidden
    positive=Archive(V/'native-stores/test_four_sink_generated_press0/store')
    negative=Archive(V/'native-stores/test_four_sink_reverse_pressur0/store')
    result={'status':'RUNNING','source_checkpoint':VERSION,'scope':'Read-only saved four-sink generated/native acceptance/export evidence and independent producer-disabled proof replay'}
    write(out/'result.json',result)
    try:
        passed=audit_archive(positive,out/'positive',True)
        reverse=audit_archive(negative,out/'reverse',False)
        current=passed['authored_query'];different=deepcopy(reverse['authored_query'])
        different['requirements']['coupled_tree']['sink_total_pressures_pa']['sink-main']=current['requirements']['coupled_tree']['sink_total_pressures_pa']['sink-main']
        assert different==current
        # Preserve the original failed assertion and prove its sole numerical issue.
        old=read(OLD/'result.json');assert old['returncode']==1 and old['source_files']==receipt['source_files']
        oldlog=(OLD/'pytest.log').read_text()
        assert '2 failed, 11 passed' in oldlog and "'196133/20000'" in oldlog and "'9.80665'" in oldlog
        assert Fraction('196133/20000')==Fraction('9.80665')
        initial=out/'initial-harness-failure';initial.mkdir()
        for p in ('result.json','tests.xml','pytest.log','runner.py'):shutil.copy2(OLD/p,initial/p)
        for rel in old['input_files']:
            p=initial/'inputs'/rel;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(OLD/rel,p)
            assert sha(p)==old['input_files'][rel]
        initial_cases=[]
        for name in ('test_four_sink_generated_press0','test_four_sink_reverse_pressur0'):
            archived=Archive(OLD/'native-stores'/name/'store')
            assert not archived.tables['candidates'] and all(r['operation']!='optimize' for r in archived.tables['runs'])
            target=initial/name;target.mkdir();shutil.copy2(archived.path/'oma.sqlite3',target/'oma.sqlite3')
            shutil.copytree(archived.path/'blobs',target/'blobs')
            write(target/'store-rows.json',archived.tables)
            initial_cases.append({'fixture':name,'no_native_candidate_created':True,'state_unchanged':archived.unchanged()})
        # Exact source and test inputs are retained once for reproducibility.
        for rel,expected in receipt['source_files'].items():
            p=out/'source'/rel;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src/rel,p);assert sha(p)==expected
        for rel,expected in receipt['input_files'].items():
            p=out/'inputs'/rel;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(V/rel,p);assert sha(p)==expected
        assert positive.unchanged() and negative.unchanged()
        assert {p.relative_to(src).as_posix():sha(p) for p in src.rglob('*.py')}==receipt['source_files']
        result.update(status='PASS',positive=passed,reverse=reverse,validation_cases=13,
            original_validation_sha256=sha(V/'result.json'),original_xml_sha256=sha(V/'tests.xml'),
            source_file_count=len(receipt['source_files']),native_geometry_rerun=False,proof_producers_disabled=True,
            initial_harness_failure={'old_receipt_sha256':sha(OLD/'result.json'),'cases':initial_cases,
                'reason':'Decimal versus exact rational spelling only; equality independently checked with Fraction; failed assertions preceded native candidate creation'},
            elapsed_seconds=time.monotonic()-started,
            limitations='Finite supplied catalogue and declared positive-flow polynomial/native numerical scope only. No unrestricted topology optimum, reverse-flow solution, installed-equipment validation or new native geometry computation in this independent replay.')
        write(out/'result.json',result)
        manifest={p.relative_to(out).as_posix():{'sha256':sha(p),'bytes':p.stat().st_size} for p in out.rglob('*') if p.is_file()}
        write(out/'files.json',{'files':manifest,'count':len(manifest),'bytes':sum(v['bytes'] for v in manifest.values())})
        print(json.dumps({'status':'PASS','evidence':str(out),'seconds':result['elapsed_seconds']}),flush=True)
    except BaseException as exc:
        result.update(status='FAILED_RETAINED',error=repr(exc));write(out/'result.json',result);raise

if __name__=='__main__':main()
