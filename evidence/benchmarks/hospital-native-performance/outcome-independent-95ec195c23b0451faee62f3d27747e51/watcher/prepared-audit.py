"""Read-only audit of one fixed Hospital campaign; no native work or publication."""
from pathlib import Path
import argparse,copy,gzip,hashlib,json,shutil,sqlite3,sys,time,traceback,uuid
from fractions import Fraction
from itertools import combinations

ROOT=Path(__file__).resolve().parents[3]
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(path,value):Path(path).write_text(json.dumps(value,indent=2,allow_nan=False),encoding='utf-8')
def unique(rows,key):
    result={r[key]:r for r in rows}
    assert len(result)==len(rows)
    return result

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('campaign',type=Path)
    parser.add_argument('--source-directory',type=Path,required=True)
    parser.add_argument('--prior-declaration',type=Path,default=ROOT/'.oma/development/hospital-generated-tree/campaigns/eac181c60f1748f4841b0796dfd69e00/predeclaration.json')
    args=parser.parse_args()
    sys.path.insert(0,str(args.source_directory.resolve()))
    from oma.store import Store,_Connection,digest
    from oma.build_identity import checker_version
    from oma.ifc.inventory import physical_inventory,inventory_evidence
    from oma.models import VerificationReport
    from oma.routing.selection import current_selection_evidence
    from oma.routing.network_scenario import SharedNetworkScenario
    from oma.routing.network_flow import evaluate_network_flow
    from oma.optimization.physical import Interval
    from oma.optimization.shared_tree_synthesis import verify_shared_tree_catalogue
    from oma.routing.shared_tree_catalogue_check import verify_generated_catalogue
    import numpy as np

    class ReadOnly(Store):
        def __init__(self,path):
            self.directory=Path(path).resolve();self.database=self.directory/'oma.sqlite3';self.blobs=self.directory/'blobs'
        def connect(self):
            db=sqlite3.connect(self.database.as_uri()+'?mode=ro',uri=True,factory=_Connection)
            db.row_factory=sqlite3.Row;return db
        def put(self,value):raise RuntimeError('Read-only audit cannot publish artifacts')

    started=time.monotonic();campaign=args.campaign.resolve()
    out=Path(__file__).resolve().parent/'attempts'/uuid.uuid4().hex;out.mkdir(parents=True)
    shutil.copyfile(__file__,out/'executed-audit.py')
    result={'status':'RUNNING','scope':'Comparison of two declared generated alternatives, never an installed Hospital baseline or unrestricted optimum','candidates':[]}
    files={str(p):sha(p) for p in (campaign/'result.json',campaign/'predeclaration.json',args.prior_declaration)}
    app={p.relative_to(args.source_directory).as_posix():sha(p) for p in args.source_directory.rglob('*.py')}
    write(out/'inputs.json',{'files':files,'source':str(args.source_directory.resolve()),'app':app})
    try:
        current=read(campaign/'result.json');declaration=read(campaign/'predeclaration.json');prior=read(args.prior_declaration)
        assert checker_version()==declaration['checker_version']
        assert app==declaration['app_sources']
        assert digest(declaration['authored_query'])==declaration['authored_query_root']==digest(prior['authored_query'])
        store=ReadOnly(current['store']);project_before=store.project(current['project_id'])
        run=store.run(current['optimization_run_id']);baseline=store.get(run['base_root'])
        assert run['base_root']==declaration['baseline_root']
        packet=store.get(current['generation_artifact_root']);generated=packet['result']
        assert packet['authored_query']==declaration['authored_query']
        assert digest(generated['mission'])==digest(run['request']['mission'])
        query=declaration['authored_query'];maximum=query['max_results'];assert maximum==2
        finite=verify_shared_tree_catalogue(generated['generation']['catalogue'],generated['synthesis']['certificate'],max_results=maximum)
        catalogue=verify_generated_catalogue(query['requirements'],query['search'],generated['generation'],context=packet['context'])
        assert finite['status']==catalogue['status']=='PASS'
        assert finite['proposals']==generated['synthesis']['proposals']
        write(out/'finite-replay.json',finite);write(out/'catalogue-replay.json',catalogue)
        write(out/'generation-packet.json',packet)
        proposals={'generated-'+p['assignment_root'][:24]:p for p in finite['proposals']}
        scenario=SharedNetworkScenario.model_validate(run['request']['mission'])
        alternatives={n.network_id:n for n in scenario.network_alternatives}
        assert len(alternatives)==len(proposals)==2 and set(alternatives)==set(proposals)
        # Bind the ranked nominal assignment to the actual expanded alternative,
        # rather than trusting a generated-* label as geometry attribution.
        rows_by_id=unique(generated['generation']['catalogue']['connectors'],'id')
        macros=generated['generation']['connector_macros']
        def edge(source,sink):return (source['component'],source['port'],sink['component'],sink['port'])
        for network_id,proposal in proposals.items():
            network=alternatives[network_id]
            expected_parts={tid:generated['generation']['tee_components'][tid] for tid in proposal['tee_ids']}
            expected_edges=set()
            for cid in proposal['connector_ids']:
                macro=macros[cid];row=rows_by_id[cid];parts=macro['geometry']['components']
                assert digest(macro['geometry'])==row['geometry_root']
                assert macro['certificate']['certificate_root']==row['fabrication_root']
                for part in parts:assert part['id'] not in expected_parts;expected_parts[part['id']]=part
                for first,last in zip(parts,parts[1:]):expected_edges.add((first['id'],'b',last['id'],'a'))
                if row['from']['node'] in proposal['tee_ids']:
                    expected_edges.add((row['from']['node'],row['from']['port'],parts[0]['id'],'a'))
                if row['to']['node'] in proposal['tee_ids']:
                    expected_edges.add((parts[-1]['id'],'b',row['to']['node'],'a'))
            assert {c.id for c in network.components}==set(expected_parts)
            for part in network.components:
                assert part.model_dump(mode='json')==type(part).model_validate(expected_parts[part.id]).model_dump(mode='json')
            actual_edges=[edge(c.source.model_dump(),c.sink.model_dump()) for c in network.connections]
            assert len(actual_edges)==len(set(actual_edges)) and set(actual_edges)==expected_edges
            demand_paths={p.sink_id:p for p in network.demand_paths};endpoints={s.id:s.endpoint for s in network.sinks}
            for sink in proposal['sinks']:
                connector_path=sink['connector_path'];steps=[]
                for i,cid in enumerate(connector_path):
                    parts=macros[cid]['geometry']['components']
                    steps.extend({'component':part['id'],'entry_port':'a','exit_port':'b'} for part in parts)
                    if i+1<len(connector_path):
                        incoming=rows_by_id[cid]['to'];outgoing=rows_by_id[connector_path[i+1]]['from']
                        assert incoming['node']==outgoing['node'] and incoming['node'] in proposal['tee_ids']
                        steps.append({'component':incoming['node'],'entry_port':'a','exit_port':outgoing['port']})
                assert [s.model_dump() for s in demand_paths[sink['id']].steps]==steps
                assert demand_paths[sink['id']].demand_id==sink['demand_id']
                assert endpoints[sink['id']].model_dump()=={'component':steps[-1]['component'],'port':'b'}
                assert network.source.model_dump()=={'component':steps[0]['component'],'port':'a'}
        assert all(getattr(scenario,k) is None for k in ('pressure_driven','passive_tree','coupled_tree'))
        original_files={str(store.resolve_path(s['immutable_path'])):s['sha256'] for s in baseline['sources']}
        assert original_files==declaration['original_files']
        assert len(baseline['sources'])==1 and baseline['sources'][0]['name']=='arc_ifc4.ifc'
        for path,value in original_files.items():assert sha(path)==value
        files.update(original_files)
        # Complete source inventory is reparsed once; this does not compute CAD.
        import ifcopenshell
        inventories={}
        for source in baseline['sources']:
            path=store.resolve_path(source['immutable_path'])
            inventory=physical_inventory(ifcopenshell.open(str(path)))
            assert not inventory['errors']
            inventories[source['sha256']]=inventory_evidence(inventory,source['sha256'])
        write(out/'fresh-source-inventories.json',inventories)

        observed_candidates={}
        def audit_candidate(candidate):
            observed_candidates[candidate['id']]=copy.deepcopy(candidate)
            state=store.get(candidate['state_root']);record,=state['physical_networks']
            material=store.get(record['geometry_artifact']);network_id=record['id']
            contract=state['derived_artifacts']['network_contract']
            assert candidate['run_id']==run['id'] and contract['scenario']==scenario.model_dump(mode='json',by_alias=True)
            assert network_id==contract['selected_alternative'] and network_id in alternatives
            assert state['sources']==baseline['sources']
            source=next(s for s in state['sources'] if s['id']==contract['source_id'])
            spec=alternatives[network_id].model_dump(mode='json',by_alias=True)
            spec['source_to_federation_matrix']=source['transform_m']
            assert material['network_spec']==spec and material['source_sha256']==source['sha256']
            assert store.resolve_path(material['source_path'])==store.resolve_path(source['immutable_path'])
            assert material['port_axis_convention']=='IFC_FLOW_AXIS_V1'
            path=store.resolve_path(material['export_path']);assert sha(path)==material['export_sha256'];files[str(path)]=material['export_sha256']
            dest=out/candidate['id'];dest.mkdir()
            for name,value in [('candidate',candidate),('state',state),('materialization',material)]:write(dest/(name+'.json'),value)
            row={'id':candidate['id'],'status':candidate['status'],'state_root':candidate['state_root'],'report_root':candidate.get('report_root'),
                'network_id':network_id,'actual_ifc_sha256':material['export_sha256'],'declared_nominal_cost_a_plus_b_pi':proposals[network_id]['nominal_cost'],
                'declared_components':len(alternatives[network_id].components)}
            if not candidate.get('report_root'):return row
            report=store.get(candidate['report_root']);VerificationReport.model_validate(report)
            assert report['candidate_root']==candidate['state_root'] and report['checker_version']==checker_version()
            checks=unique(report['results'],'id');write(dest/'report.json',report)
            row.update(report_status=report['status'],checks={k:v['status'] for k,v in checks.items()},reported_objective=report['objective'])
            if candidate['status']!='CHECKED':return row
            admission=current_selection_evidence(store,run,candidate['id'],'physical_network',scenario.objective_weights)
            row['admission']=admission
            with store.connect() as db:
                jobs=[dict(r) for r in db.execute('SELECT * FROM check_executions WHERE candidate_id=?',(candidate['id'],))]
            completed=[j for j in jobs if j['status']=='COMPLETED' and j['report_root']==candidate['report_root']]
            assert len(completed)==1
            execution=store.get(completed[0]['evidence_root']);write(dest/'execution.json',execution);write(dest/'execution-row.json',completed[0])
            assert execution['supervision']['status']=='COMPLETED' and execution['supervision']['returncode']==0
            artifacts={key:store.get(checks[key]['witness']['artifact']) for key in ('network-native-semantics','network-all-source-clearance')}
            semantics,cad=artifacts['network-native-semantics'],artifacts['network-all-source-clearance']
            assert cad['implementation']['cad_code_sha256']==app['oma/ifc/cad.py']
            assert cad['implementation']['enclosure_code_sha256']==app['oma/ifc/enclosure.py']
            for key,value in artifacts.items():write(dest/(key+'.json'),value)
            parts=unique(semantics['parts'],'component_id');guids=[p['ifc_guid'] for p in parts.values()];count=len(parts)
            assert count==len(set(guids))==len(record['component_ids'])==semantics['physical_components']>0
            assert type(semantics['fitting_count']) is int
            assert semantics['fitting_count']==sum(p['kind']!='segment' for p in parts.values())
            assert semantics['unique_length_m']==sum(p['length_m'] for p in semantics['parts'])
            assert semantics['demand_path_lengths_m']=={
                demand.demand_id:sum(parts[s.component]['path_lengths_m'][s.entry_port+':'+s.exit_port] for s in demand.steps)
                for demand in alternatives[network_id].demand_paths}
            assert report['objective']=={'length_m':semantics['unique_length_m'],'fitting_count':float(semantics['fitting_count'])}
            assert set(parts)==set(record['component_ids'])=={c.id for c in alternatives[network_id].components}
            assert cad['export_sha256']==material['export_sha256']
            assert len(cad['route_guids'])==cad['route_count']==count and set(cad['route_guids'])==set(guids)
            assert cad['coordination_status']==cad['self_interference_status']==semantics['status']=='PASS'
            assert not any(cad[k] for k in ('failed_pairs','unknown_pairs','blocked_pairs','missing_geometry'))
            assert cad['pairs_accounted']==count*cad['obstacle_count']
            assert cad['broad_separation_passes']+len(cad['pair_results'])==cad['pairs_accounted']
            assert all(r['status']=='PASS' for r in cad['pair_results'])
            pairs=cad['self_pair_results'];assert len(pairs)==count*(count-1)//2
            assert all(p['status']=='PASS' and len(p['participant_guids'])==len(set(p['participant_guids']))==2 for p in pairs)
            assert {frozenset(p['participant_guids']) for p in pairs}=={frozenset(p) for p in combinations(guids,2)}
            caches=cad['performance']['source_cache'];assert len(caches)==len(inventories)
            represented=0
            for cache in caches:
                actual=cache['physical_inventory'];expected=inventories[actual['source_sha256']]
                assert digest(actual)==digest(expected) and cache['selected_physical_count']==expected['physical_product_count']
                covered={int(k) for k,v in expected['assemblies'].items() if v['status']=='COVERED_BY_DECLARED_PHYSICAL_DESCENDANTS'}
                assert len(cache['accounted_assembly_step_ids'])==len(covered) and set(cache['accounted_assembly_step_ids'])==covered
                represented+=expected['physical_product_count']-len(covered)
            assert represented==cad['obstacle_count']
            assert sorted(s['sha256'] for s in cad['sources'])==sorted(inventories)
            ports={(p['component_id'],p['slot']):p for p in semantics['ports']}
            expected_ports={(c.id,p) for c in alternatives[network_id].components for p in c.ports}
            assert len(ports)==len(semantics['ports'])==semantics['physical_ports'] and set(ports)==expected_ports
            assert len({p['port_step_id'] for p in ports.values()})==len({p['port_guid'] for p in ports.values()})==len(ports)
            expected_links={(ports[(link.source.component,link.source.port)]['port_step_id'],
                             ports[(link.sink.component,link.sink.port)]['port_step_id']) for link in alternatives[network_id].connections}
            actual_links=[tuple(link) for link in semantics['connectivity']]
            assert len(actual_links)==len(set(actual_links))==semantics['connections']==len(expected_links)
            assert set(actual_links)==expected_links and all(p['status']=='PASS' for p in ports.values())
            budget=Fraction(str(max(1e-6,state.get('numerical_policy',{}).get('absolute_tolerance_m',1e-6))))
            lengths={cid:Interval(max(Fraction(0),Fraction(str(p['length_m']))-budget),Fraction(str(p['length_m']))+budget) for cid,p in parts.items()}
            radii={cid:Interval(Fraction(str(p['radius_m']))-budget,Fraction(str(p['radius_m']))+budget) for cid,p in parts.items()}
            source=next(s for s in state['sources'] if s['id']==contract['source_id']);matrix=np.asarray(source['transform_m'])
            def position(endpoint):
                point=matrix[:3,:3]@np.asarray(ports[(endpoint.component,endpoint.port)]['position_m'])+matrix[:3,3]
                return [Interval(Fraction(str(float(v)))-budget,Fraction(str(float(v)))+budget) for v in point]
            network=alternatives[network_id]
            positions={'source':position(network.source),'sinks':{s.id:position(s.endpoint) for s in network.sinks}}
            replay=evaluate_network_flow(scenario,network,lengths,positions,component_outer_radii=radii)
            assert replay['verdict']=='PASS' and digest(replay)==digest(checks['network-demand-conditioned-service']['witness']['calculation'])
            write(dest/'independent-fixed-flow-replay.json',replay)
            length_cost=sum(lengths.values(),Interval.point(0))*Fraction(str(scenario.objective_weights.get('length_m',0)))
            fitting_cost=Fraction(str(scenario.objective_weights.get('fitting_count',0)))*semantics['fitting_count']
            declared_cost=length_cost+fitting_cost
            assert declared_cost.lo<=Fraction(admission['cost'])<=declared_cost.hi
            row.update(native={'components':count,'ports':len(ports),'obstacles':represented,'source_pairs':cad['pairs_accounted'],
                'self_pairs':len(pairs),'exact_support_enclosures':cad['represented_support_enclosures'],'cad_performance':cad['performance']},
                exact_reported_cost=admission['cost'],declared_metric_cost_enclosure=declared_cost.encoded(),
                fixed_flow={'source_flow_m3_s':replay['source_flow_m3_s'],
                    'prescribed_sink_flows_m3_s':{s.id:str(Fraction(str(s.required_flow_m3_s))) for s in scenario.sinks},
                    'paths':replay['paths'],'components':replay['components'],'operating_point_solution':replay['operating_point_solution']})
            return row

        all_candidates=[c for c in store.candidates(current['project_id']) if c['run_id']==run['id']]
        original=[c for c in all_candidates if not store.get(c['state_root'])['derived_artifacts'].get('export_correspondence')]
        assert len(original)<=2
        rows=[audit_candidate(c) for c in original];result['candidates']=rows
        assert len({r['network_id'] for r in rows})==len(rows)
        # Public event decoder retains schema details; scan the full event stream.
        events=[];cursor=0
        while batch:=store.events(current['project_id'],cursor,1000):events.extend(batch);cursor=batch[-1]['seq']
        complete=next((e for e in reversed(events) if e['run_id']==run['id'] and e['stage']=='complete'),None)
        write(out/'events.json',events)
        checked=[r for r in rows if r['status']=='CHECKED'];checked.sort(key=lambda r:(Fraction(r['exact_reported_cost']),r['id']))
        selected=current.get('selected_candidate_id')
        if selected:
            assert checked and selected==checked[0]['id']
            assert complete['payload']['selected_candidate_ids']==[selected]
            retained=store.get(complete['payload']['selection_evidence_root'])
            assert retained['selected']['candidate_id']==selected and retained['selected']['report_root']==checked[0]['report_root']
            assert {r['candidate_id'] for r in retained['examined_current_reports']}=={r['id'] for r in checked}
            assert retained['master_optimality_claim'] is False and retained['continuous_global_optimality_claim'] is False
            write(out/'selection-current-evidence.json',retained)
            result['selection']={'selected':selected,'minimum_current_checked_reported_cost':checked[0]['exact_reported_cost'],
                'checked_count':len(checked),'scope':'Exact weighted reported values among freshly applicable complete candidates; no continuous/unrestricted optimum'}
        if len(checked)==2:
            difference=Fraction(checked[1]['exact_reported_cost'])-Fraction(checked[0]['exact_reported_cost'])
            lesser,greater=(r['declared_metric_cost_enclosure'] for r in checked)
            separation=Fraction(greater['lower'])-Fraction(lesser['upper'])
            result['improvement']={'compared_with_candidate':checked[1]['id'],'selected_candidate':checked[0]['id'],
                'exact_reported_cost_reduction':str(difference),'nominal_cost_is_native_lower_bound':False,
                'fraction_of_other_reported_cost':str(difference/Fraction(checked[1]['exact_reported_cost'])),
                'minimum_reduction_under_declared_native_metric_enclosures':str(separation),
                'strict_improvement_under_declared_metric_model':separation>0,
                'scope':'Native tolerance/metric enclosure assumptions remain explicit; not a formally interval-certified CAD model.',
                'installed_building_baseline_comparison':False}
        if current.get('export'):
            acceptance=current['accepted']
            assert acceptance['status']=='ACCEPTED' and acceptance['state_root']==checked[0]['state_root']
            assert acceptance['revision']==run['base_revision']+1
            with store.connect() as db:
                revision=dict(db.execute('SELECT * FROM revisions WHERE project_id=? AND revision=?',
                    (current['project_id'],acceptance['revision'])).fetchone())
            assert revision['status']=='ACCEPTED' and revision['candidate_id']==selected
            assert revision['root']==checked[0]['state_root'] and revision['parent_root']==run['base_root']
            event=next(e for e in events if e['seq']==acceptance['event_seq'])
            assert event['candidate_id']==selected and event['state_root']==checked[0]['state_root'] and event['status']=='ACCEPTED'
            assert checked[0]['report_root'] in event['artifacts']
            result['acceptance']={'revision':revision,'event':event}
            manifest=store.get(current['export']['artifact_root']);assert digest(manifest)==digest(read(campaign/'export-manifest.json'))
            assert manifest['status']=='CHECKED_LOCAL_SCOPE' and manifest['round_trip']=='PASS' and manifest['candidate_id']==selected
            assert len(manifest['checking']['release_bindings'])==9 and all(v is True for v in manifest['checking']['release_bindings'].values())
            exported=store.candidate(manifest['checking']['exported_candidate_id'])
            row=audit_candidate(exported);assert row['status']=='CHECKED' and exported['id']!=selected
            assert row['actual_ifc_sha256']==checked[0]['actual_ifc_sha256'] and row['reported_objective']==checked[0]['reported_objective']
            assert row['native']['source_pairs']==checked[0]['native']['source_pairs'] and row['native']['self_pairs']==checked[0]['native']['self_pairs']
            result['fresh_export']=row;write(out/'export-manifest.json',manifest)
        result['status']='BOTH_FIXED_ALTERNATIVES_AND_SELECTED_FRESH_EXPORT_AUDITED' if len(checked)==2 and result.get('fresh_export') else 'INCOMPLETE_TWO_CHECKED_ALTERNATIVE_COMPARISON'
        assert store.project(current['project_id'])==project_before
        assert store.run(run['id'])==run
        assert all(store.candidate(cid)==value for cid,value in observed_candidates.items())
        result['store_project_unchanged']=True
    except Exception:
        result['status']='AUDIT_REJECTED_OR_INCOMPLETE';result['traceback']=traceback.format_exc()
    finally:
        result['files_unchanged']=all(sha(path)==value for path,value in files.items())
        result['app_unchanged']=app=={p.relative_to(args.source_directory).as_posix():sha(p) for p in args.source_directory.rglob('*.py')}
        if not result['files_unchanged'] or not result['app_unchanged']:result['status']='AUDIT_INPUTS_CHANGED'
        result['seconds']=time.monotonic()-started
        write(out/'result.json',result)
        print(json.dumps({'output':str(out),'status':result['status'],'seconds':result['seconds'],'traceback':result.get('traceback')}))

if __name__=='__main__':main()
