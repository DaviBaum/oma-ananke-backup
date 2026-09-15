"""Read-only independent full Hospital graph and publication reconciliation.

Does not call the extraction producer, design screener or native CAD. Verifies
the retained raw-source semantic receipts and current source bytes, reconstructs
explicit components independently with iterative BFS, and reads SQLite mode=ro.
"""
from pathlib import Path
from collections import Counter,defaultdict,deque
import argparse,hashlib,json,sqlite3,shutil,time,uuid,zlib

ROOT=Path(__file__).resolve().parents[3]
STAGE=Path(__file__).resolve().parent
EXPECTED_BUILD='b72cb24732b8b1d5ab08fdebda5e5649640a652b82bdda24a58f00d4da81b52c'

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def digest(v):return hashlib.sha256(canonical(v)).hexdigest()
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def dump(p,v):Path(p).write_text(json.dumps(v,indent=2,allow_nan=False),encoding='utf-8')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('campaign',type=Path);args=parser.parse_args()
    campaign=args.campaign.resolve();result=load(campaign/'result.json')
    assert result['status']=='WHOLE_PROJECT_SERVICE_JOB_COMPLETED_WITH_DESIGN_INPUTS_REQUIRED'
    out=STAGE/'campaign-peer'/uuid.uuid4().hex;out.mkdir(parents=True)
    shutil.copyfile(__file__,out/'executed-audit.py')
    start=time.perf_counter();inputs={};blob_roots={}
    def read(p):
        p=Path(p).resolve();inputs[str(p)]=sha(p);return load(p)
    result=read(campaign/'result.json');declaration=read(campaign/'predeclaration.json')
    packet=read(campaign/'whole-project-service-report.json');events=read(campaign/'events.json')
    assert declaration['checker_version']=='oma-independent-checker/2:'+EXPECTED_BUILD
    source=Path(declaration['source_path'])
    source_map={p.relative_to(source).as_posix():sha(p) for p in source.rglob('*.py')}
    assert source_map==declaration['application_sources']
    assert len(source_map)==117
    assert result['execution']['status']=='COMPLETED'
    assert declaration['request_root']==digest(declaration['request'])==packet['request_root']
    assert declaration['request']['mission']['contracts']==[] and declaration['request']['scope']==[]
    assert packet['checker_version']==declaration['checker_version']
    store=Path(result['store']);db_path=store/'oma.sqlite3'
    def blob(root):
        p=store/'blobs'/(root+'.json.z');raw=p.read_bytes();decoded=zlib.decompress(raw)
        assert hashlib.sha256(decoded).hexdigest()==root
        inputs[str(p.resolve())]=hashlib.sha256(raw).hexdigest();blob_roots[root]=str(p.resolve())
        return json.loads(decoded)
    assert digest(packet)==result['report_root']
    assert packet==blob(result['report_root'])
    db=sqlite3.connect(db_path.as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    def database_snapshot():
        run=dict(db.execute('SELECT * FROM runs WHERE id=?',(result['run_id'],)).fetchone())
        run['request']=json.loads(run['request'])
        project=dict(db.execute('SELECT * FROM projects WHERE id=?',(declaration['new_project']['id'],)).fetchone())
        candidates=[dict(r) for r in db.execute('SELECT * FROM candidates WHERE project_id=?',(project['id'],))]
        revisions=[dict(r) for r in db.execute('SELECT * FROM revisions WHERE project_id=? ORDER BY revision',(project['id'],))]
        raw_events=[dict(r) for r in db.execute('SELECT seq,payload FROM events WHERE project_id=? ORDER BY seq',(project['id'],))]
        return {'run':run,'project':project,'candidates':candidates,'revisions':revisions,'events':raw_events}
    before=database_snapshot();run=before['run']
    assert run==result['run'] and run['status']=='MISSING_INPUTS'
    assert run['request']==declaration['request'] and run['operation']=='design_services'
    assert before['project']==declaration['new_project']==result['project']
    assert not before['candidates'] and len(before['revisions'])==1
    assert packet['base_root']==run['base_root']==before['project']['state_root']
    assert packet['base_revision']==run['base_revision']==before['project']['revision']==0
    assert packet['whole_building_optimized'] is False and packet['native_checks_run'] is False
    assert packet['project_state_changed'] is False and packet['construction_approval'] is False
    state=blob(run['base_root']);sources=state['sources']
    names={'arc_ifc4.ifc','str_ifc4.ifc','mech_ifc4.ifc','plumb_ifc4.ifc','elec_ifc4.ifc','sprinkle_ifc4.ifc','fire_ifc4.ifc'}
    assert len(sources)==7 and {s['name'] for s in sources}==names
    assert len({s['id'] for s in sources})==7
    assert len(packet['sources'])==7 and {s['source_id'] for s in packet['sources']}=={s['id'] for s in sources}
    assert set(declaration['request']['mission']['source_disciplines'])=={s['id'] for s in sources}
    published=[e for e in events if e.get('stage')=='service_design_complete' and e.get('run_id')==run['id']]
    assert len(published)==1 and published[0]['payload']['service_design_artifact_root']==result['report_root']
    sql_events=[{**json.loads(e['payload']),'seq':e['seq']} for e in before['events']]
    assert sql_events==events
    summaries=[];all_network_ids=set();expected_portless=0
    for item in sources:
        sid=item['id'];assert sid==item['sha256']
        original=Path(item['immutable_path']);inputs[str(original.resolve())]=sha(original)
        assert inputs[str(original.resolve())]==sid==declaration['source_files'][str(original)]
        audit=blob(item['audit_root']);assert audit['source_sha256']==sid and digest(audit)==item['audit_root']
        source_row,=[s for s in packet['sources'] if s['source_id']==sid]
        graph=blob(source_row['network_inventory_root']);receipt=blob(source_row['source_reconciliation_root'])
        on_disk=read(campaign/'networks'/(item['name']+'.json'))
        assert graph==on_disk and graph['source_sha256']==sid and graph['audit_input_sha256']==item['audit_root']
        assert graph['graph_sha256']==digest({k:v for k,v in graph.items() if k!='graph_sha256'})
        assert receipt['status']=='MATCHED_ACTUAL_SOURCE' and receipt['source_sha256']==receipt['parsed_snapshot_sha256']==sid
        assert receipt['audit_input_sha256']==item['audit_root'] and receipt['source_inventory_reconciled'] is True
        assert receipt['port_ownership_and_system_membership_reconciled'] is True
        assert receipt['geometry_verified'] is False and receipt['engineering_parameters_verified'] is False
        collections=(('products','step_id'),('ports','step_id'),('explicit_connections','relationship_step_id'),('systems','step_id'))
        raw_maps={}
        for name,key in collections:
            raw_map={r[key]:r for r in audit[name]};new_map={r[key]:r for r in graph[name]}
            assert len(raw_map)==len(audit[name])==len(new_map)==len(graph[name])
            assert set(raw_map)==set(new_map)
            for ident,row in raw_map.items():
                assert new_map[ident]['source_record_sha256']==digest(row)
                assert all(new_map[ident][k]==v for k,v in row.items())
            raw_maps[name]=raw_map
            assert receipt['counts'][name]==len(raw_map)
        products,ports,connections,systems=(raw_maps[n] for n,_ in collections)
        if item['name']=='str_ifc4.ifc':
            service=set()
            assert not any(p['type']=='IfcBuildingElementProxy' and p.get('physical') for p in products.values())
        elif item['name']=='arc_ifc4.ifc':
            service={i for i,p in products.items() if p['type']=='IfcBuildingElementProxy' and p.get('physical')}
            assert len(service)==1770
            actual_category={p['step_id']:p['category'] for p in graph['products']}
            assert all(actual_category[i]=='UNCLASSIFIED_PHYSICAL' for i in service)
        else:
            # Actual retained MEP source products all have explicit IFC service
            # classes or generic physical proxies; no source product is sampled.
            service={i for i,p in products.items() if p.get('physical') is True}
        assert service==set(graph['accounting']['service_product_step_ids'])
        adj=defaultdict(set)
        for i in service:adj[('product',i)]
        owner={}
        for pid,p in ports.items():
            node=('port',pid);adj[node]
            owners=p['owner_step_ids']
            if len(set(owners))==1 and owners[0] in service:
                owner[pid]=owners[0];product_node=('product',owners[0])
                adj[node].add(product_node);adj[product_node].add(node)
        for edge in connections.values():
            a=('port',edge['port_a_step_id']);b=('port',edge['port_b_step_id'])
            adj[a].add(b);adj[b].add(a)
        pending=set(adj);components=[]
        while pending:
            start_node=min(pending);pending.remove(start_node);queue=deque([start_node]);component={start_node}
            while queue:
                node=queue.popleft()
                for other in adj[node]:
                    if other not in component:
                        component.add(other);pending.discard(other);queue.append(other)
            components.append(frozenset(component))
        actual_components={frozenset([('product',i) for i in n['product_step_ids']]+[('port',i) for i in n['port_step_ids']]):n for n in graph['networks']}
        assert len(actual_components)==len(graph['networks'])==len(components) and set(actual_components)==set(components)
        claimed_edges=[]
        for component in components:
            n=actual_components[component];edge_ids=sorted(i for i,e in connections.items() if ('port',e['port_a_step_id']) in component)
            assert edge_ids==n['connection_step_ids'];claimed_edges.extend(edge_ids)
            assert all(('port',connections[i]['port_b_step_id']) in component for i in edge_ids)
            ownership_edges=sum(('port',pid) in component for pid in owner)
            assert n['topology']['cycle_rank']==ownership_edges+len(edge_ids)-len(component)+1
            assert n['engineering_status']=='UNKNOWN' and n['missing_design_inputs']
            assert n['terminal_candidates']['engineering_role_inference']=='NOT_PERFORMED'
            assert n['id'] not in all_network_ids;all_network_ids.add(n['id'])
            linked,=[r for r in packet['networks'] if r['network_id']==n['id']]
            assert linked['network_root']==digest({'network':n,'source_inventory_root':source_row['network_inventory_root'],'source_audit_root':item['audit_root']})
            assert linked['source_sha256']==sid and linked['status']=='MISSING_DESIGN_CONTRACT'
            assert linked['network_service_verified'] is False and linked['native_optimization_ready'] is False
        assert sorted(claimed_edges)==sorted(connections)
        portless=service-{o for p in ports.values() for o in p['owner_step_ids']}
        expected_portless+=len(portless)
        assert graph['summary']['portless_service_product_count']==len(portless)
        assert source_row['summary']==graph['summary'] and source_row['accounting']==graph['accounting']
        summaries.append({'name':item['name'],'source_sha256':sid,'audit_root':item['audit_root'],'graph_root':source_row['network_inventory_root'],'reconciliation_root':source_row['source_reconciliation_root'],'summary':graph['summary']})
        print(json.dumps({'source':item['name'],'verified_networks':len(components),'products':len(service)}),flush=True)
    assert len(packet['networks'])==len(all_network_ids)==packet['summary']['network_count']
    assert packet['summary']['network_status_counts']=={'MISSING_DESIGN_CONTRACT':len(all_network_ids)}
    assert packet['status']=='DESIGN_INPUTS_REQUIRED' and packet['summary']['contract_count']==0
    assert database_snapshot()==before
    assert source_map=={p.relative_to(source).as_posix():sha(p) for p in source.rglob('*.py')}
    assert all(sha(Path(p))==h for p,h in inputs.items())
    dump(out/'inputs.json',inputs);dump(out/'database-records.json',before);dump(out/'source-map.json',source_map)
    dump(out/'result.json',{'status':'INDEPENDENT_ALL_SOURCE_INSTALLED_SERVICE_ACCOUNTING_AUDIT_PASS','checker_version':declaration['checker_version'],'campaign_result_sha256':sha(campaign/'result.json'),'predeclaration_sha256':sha(campaign/'predeclaration.json'),'report_root':result['report_root'],'request_root':packet['request_root'],'source_count':len(sources),'network_count':len(all_network_ids),'portless_product_count':expected_portless,'summaries':summaries,'all_bound_inputs_and_store_rows_unchanged':True,'seconds':time.perf_counter()-start,'scope':'Current source hashes and retained raw-IFC reconciliation receipts, complete graph record equality and independent BFS components, exact published Store/request/app/root bindings. No CAD or extractor/designer producer rerun. Actual engineering inputs remain missing; no whole-building or construction approval.'})
    files={p.name:{'sha256':sha(p),'bytes':p.stat().st_size} for p in out.iterdir() if p.is_file()}
    dump(out/'handoff.json',{'status':'CLOSED_INDEPENDENT_AUDIT','retained_files':files,'result_sha256':sha(out/'result.json')})
    print(json.dumps({'result':str(out/'result.json'),'sha256':sha(out/'result.json'),'handoff_sha256':sha(out/'handoff.json')}),flush=True)

if __name__=='__main__':main()
