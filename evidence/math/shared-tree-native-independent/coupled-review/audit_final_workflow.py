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
V=ROOT/'.oma/development/shared-tree-coupled/validation/0b39284a65564d34b94af6500453051b'
OLD=V.parent/'3a0b4376378449f1b52402ffb412f546'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def write(p,v):Path(p).write_text(json.dumps(v,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf8')

class Archive:
    def __init__(self,path):
        self.path=path;self.db=sqlite3.connect((path/'oma.sqlite3').resolve().as_uri()+'?mode=ro',uri=True);self.db.row_factory=sqlite3.Row
        self.tables={t:[dict(r) for r in self.db.execute('SELECT * FROM '+t)] for t in ('projects','runs','candidates','revisions','check_executions')}
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
    assert 'network_alternatives' not in authored['requirements'] and len(authored['search']['tee_instances'])==2
    proof=verify_generated_catalogue(authored['requirements'],authored['search'],generated['generation'],context=packet['context'])
    finite=verify_shared_tree_catalogue(generated['generation']['catalogue'],generated['synthesis']['certificate'],max_results=authored['max_results'])
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
            assert len(guids)==len(set(guids))==11 and cad['route_count']==11 and cad['obstacle_count']==2 and cad['pairs_accounted']==22
            assert len(cad['self_pair_results'])==55 and all(x['status']=='PASS' for x in cad['self_pair_results'])
            assert {frozenset(x['participant_guids']) for x in cad['self_pair_results']}=={frozenset(x) for x in combinations(guids,2)}
            assert sem['physical_ports']==len(sem['ports'])==24 and checks['network-permitted-zone']['status']=='PASS'
            case['native']={'components':11,'ports':24,'source_obstacles':2,'source_pairs':22,'self_pairs':55,'status':'PASS'}
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
            service=fresh['service'];assert service['counts']=={'physical_ports':24,'deliveries':3,'conservation_identities':25,'head_path_identities':27}
            assert len({(x['component'],x['port']) for x in service['physical_ports']})==24
            assert all(x['forward_status']==x['maximum_velocity_status']=='PASS' for x in service['physical_ports'])
            assert len(service['deliveries'])==3 and all(x['status']=='PASS' for x in service['deliveries'])
            assert all(x['difference']=={} for x in service['conservation_identities'])
            assert len({x['id'] for x in service['conservation_identities']})==25 and len({x['id'] for x in service['head_path_identities']})==27
            write(folder/'independent-pressure-replay.json',fresh)
            case['pressure']={'model_root':fresh['model_root'],'local_certificate_root':fresh['local_check']['certificate_root'],
                'global_certificate_root':fresh['global_check']['certificate_root'],'counts':service['counts'],'deliveries':service['deliveries']}
            completed=[e for e in archive.tables['check_executions'] if e['candidate_id']==candidate['id'] and e['status']=='COMPLETED' and e['report_root']==candidate['report_root']]
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
    started=time.monotonic();out=STAGE/'final-native-workflow'/uuid.uuid4().hex;out.mkdir(parents=True)
    shutil.copy2(__file__,out/'executed.py');receipt=read(V/'result.json');VERSION=receipt['checker_version']
    src=Path(os.environ['PYTHONPATH']);assert {p.relative_to(src).as_posix():sha(p) for p in src.rglob('*.py')}==receipt['source_files']
    assert all(sha(V/p)==h for p,h in receipt['input_files'].items()) and receipt['status']=='PASS' and receipt['returncode']==0
    xml=ET.parse(V/'tests.xml').getroot();assert len(xml.findall('.//testcase'))==54 and not any(xml.findall('.//'+k) for k in ('failure','error','skipped'))
    for p in ('result.json','tests.xml','pytest.log'):shutil.copy2(V/p,out/('validation-'+p))
    from oma.routing import shared_tree_proposals as producer
    from oma.optimization import shared_tree_synthesis as synthesis
    def forbidden(*args,**kwargs):raise AssertionError('Producer must not run in review')
    producer.build_connector_catalogue=producer.compile_shared_tree_proposals=forbidden
    synthesis.compile_shared_tree_catalogue=forbidden
    adapter.evaluate_coupled_tree=adapter.local.compile_coupled_tree_pressure=adapter.global_proof.compile_coupled_tree_univalence=forbidden
    positive=Archive(V/'native-stores/test_generated_two_tee_pressur0/store');negative=Archive(V/'native-stores/test_nominal_generated_pressur0/store')
    first=audit_archive(positive,out/'positive',True);reverse=audit_archive(negative,out/'reverse',False)
    old=Archive(OLD/'native-stores/test_generated_two_tee_pressur0/store');_,oldrequest=old.request('propose_network')
    prior=oldrequest['mission'];current=first['authored_query'];a=deepcopy(prior);b=deepcopy(current)
    oldbox=a['requirements']['coupled_tree'].pop('flow_search_box_m3_s');newbox=b['requirements']['coupled_tree'].pop('flow_search_box_m3_s')
    assert a==b and all(v=={'lower':'99/100000','upper':'101/100000'} for v in oldbox.values()) and all(v=={'lower':'98/100000','upper':'102/100000'} for v in newbox.values())
    reverse_query=deepcopy(reverse['authored_query']);reverse_query['requirements']['coupled_tree']['sink_total_pressures_pa']['sink-a']=current['requirements']['coupled_tree']['sink_total_pressures_pa']['sink-a']
    assert reverse_query==current
    oldreceipt=read(OLD/'result.json');changed=[k for k,h in receipt['source_files'].items() if oldreceipt['source_files'].get(k)!=h]
    assert changed==['oma/routing/network_checker.py']
    diff=''.join(difflib.unified_diff((Path(oldreceipt['source_directory'])/changed[0]).read_text().splitlines(True),(src/changed[0]).read_text().splitlines(True)))
    (out/'source-delta.diff').write_text(diff,encoding='utf8')
    assert old.unchanged() and positive.unchanged() and negative.unchanged()
    result={'status':'PASS','checker_version':VERSION,'validation_cases':54,'source_file_count':len(receipt['source_files']),
        'validation_receipt_sha256':sha(V/'result.json'),'test_xml_sha256':sha(V/'tests.xml'),'declared_input_count':len(receipt['input_files']),
        'positive':first,'reverse':reverse,'prior119_comparison':{'all_authored_physical_requirements_search_and_parameters_equal':True,
            'only_authored_change':'flow_search_box_m3_s','old_box':oldbox,'new_box':newbox,'source_changed_files':changed,
            'prior_failure_retained':'3a0b4376378449f1b52402ffb412f546','prior_nominal_oracle_still_applicable':True},
        'native_geometry_rerun':False,'proof_producers_disabled':True,'elapsed_seconds':time.monotonic()-started,
        'scope':'Read-only actual generated catalogue/job-handler, native geometry and managed verification, independent existing local/global/service certificate replay, accepted revision and fresh exported bytes. The proposal handler itself ran directly in the retained test process, not a separate API worker.'}
    write(out/'result.json',result)
    (out/'README.md').write_text('PASS: frozen33a54-case workflow reviewed read-only. Two complete trees were generated from the authored fixed sites/stubs/planes. The cheapest blocked candidate remains rejected. The clear11-component candidate passes24ports,22sourcepairs,55selfpairs,zone,local+global pressure proof and complete service (3deliveries,25continuity,27head relations), is accepted at revision2 and its actual IFC freshly rechecked with new candidate/report/model identities. Original parsed IFC entities are preserved. Independent catalogue/finite/local/global/service verifier replays ran with all producer functions disabled; no native checker rerun.\n\nThe retained119physical requirements/search/pressure/loss/minimum/velocity data match exactly; only the computational flow-search box widened from.99–1.01 to.98–1.02L/s. The original failed reports remain unchanged. The separate reverse-head request still has no incumbent: blocked geometry stays rejected and the clear unsupported regime is UNKNOWN, with no accepted revision. The only application-source delta is the retained network-checker diagnostic/unsupported-boundary handling diff.\n\nThe proposal job handler was invoked directly inside the test process; this review does not claim an additional subprocess/API generation campaign. Actual candidate checks and export recheck used completed managed execution. These remain hypothetical finite-catalogue/native/model-scope results, not unrestricted topology optimality or measured installed-system performance.\n',encoding='utf8')
    files={p.relative_to(out).as_posix():{'sha256':sha(p),'bytes':p.stat().st_size} for p in out.rglob('*') if p.is_file()}
    write(out/'files.json',{'files':files,'count':len(files),'bytes':sum(x['bytes'] for x in files.values())})
    print(json.dumps({'status':'PASS','evidence':str(out),'files':len(files),'elapsed_seconds':result['elapsed_seconds']}))

if __name__=='__main__':main()
