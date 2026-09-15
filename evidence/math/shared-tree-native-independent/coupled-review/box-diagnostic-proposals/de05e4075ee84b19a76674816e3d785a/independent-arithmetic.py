"""Read retained native reports and diagnose the unchanged pressure box exactly."""
from fractions import Fraction as Q
from pathlib import Path
import hashlib,json,os,shutil,sqlite3,time,uuid,zlib

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').exists())
STAGE=Path(__file__).resolve().parent
VALIDATION=ROOT/'.oma/development/shared-tree-coupled/validation/3a0b4376378449f1b52402ffb412f546'
STORE=VALIDATION/'native-stores/test_generated_two_tee_pressur0/store'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf8'))
def encode(v):
    if isinstance(v,Q):return str(v)
    if isinstance(v,dict):return {k:encode(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [encode(x) for x in v]
    return v
def write(p,v):Path(p).write_text(json.dumps(encode(v),indent=2)+'\n',encoding='utf8')
def plus(a,b):return a[0]+b[0],a[1]+b[1]
def minus(a,b):return a[0]-b[1],a[1]-b[0]
def times(a,b):
    products=[x*y for x in a for y in b];return min(products),max(products)
def isum(vs):
    r=(Q(0),Q(0))
    for v in vs:r=plus(r,v)
    return r
def inverse(m):
    n=len(m);a=[list(row)+[Q(i==j) for j in range(n)] for i,row in enumerate(m)]
    for k in range(n):
        p=next(i for i in range(k,n) if a[i][k]);a[k],a[p]=a[p],a[k]
        factor=a[k][k];a[k]=[v/factor for v in a[k]]
        for i in range(n):
            if i!=k:
                factor=a[i][k];a[i]=[v-factor*w for v,w in zip(a[i],a[k])]
    return [row[n:] for row in a]

def diagnostic(model,box):
    leaves=model['leaves'];n=len(leaves)
    iv=lambda r:(Q(r['lower']),Q(r['upper']))
    coefficients={k:iv(v) for k,v in model['coefficients'].items()};bounds={k:iv(v) for k,v in box.items()}
    center={k:sum(v)/2 for k,v in bounds.items()}
    f={k:(-Q(v['upper']),-Q(v['lower'])) for k,v in model['available_heads'].items()}
    j=[[(Q(0),Q(0)) for _ in leaves] for _ in leaves];midj=[[Q(0) for _ in leaves] for _ in leaves]
    for term in model['terms']:
        a=coefficients[term['coefficient_id']];total=sum(center[k] for k in term['descendant_leaves'])
        span=isum(bounds[k] for k in term['descendant_leaves']);loss=times(a,(total**2,total**2));derivative=times((2*a[0],2*a[1]),span)
        for i,leaf in enumerate(leaves):
            if leaf not in term['applies_to_leaves']:continue
            f[leaf]=plus(f[leaf],loss)
            for col,other in enumerate(leaves):
                if other in term['descendant_leaves']:
                    j[i][col]=plus(j[i][col],derivative);midj[i][col]+=sum(a)*total
    r=inverse(midj)
    assert all(sum(r[i][k]*midj[k][col] for k in range(n))==Q(i==col) for i in range(n) for col in range(n))
    B=[[minus((Q(i==col),Q(i==col)),isum(times((r[i][k],r[i][k]),j[k][col]) for k in range(n))) for col in range(n)] for i in range(n)]
    norms=[sum(max(abs(a),abs(b)) for a,b in row) for row in B]
    images={};rows={}
    for i,leaf in enumerate(leaves):
        image=minus((center[leaf],center[leaf]),isum(times((r[i][k],r[i][k]),f[other]) for k,other in enumerate(leaves)))
        remainder=isum(times(B[i][k],minus(bounds[other],(center[other],center[other]))) for k,other in enumerate(leaves))
        K=plus(image,remainder);margins=(K[0]-bounds[leaf][0],bounds[leaf][1]-K[1]);images[leaf]=K
        rows[leaf]={'original_box':bounds[leaf],'center':center[leaf],'center_residual_pa':f[leaf],'center_image':image,
            'interval_remainder':remainder,'K':K,'margins':margins,'strict_inclusion':min(margins)>0,
            'float_diagnostic':{'center_residual_pa':list(map(float,f[leaf])),'center_image_m3_s':list(map(float,image)),
                'K_m3_s':list(map(float,K)),'margins_m3_s':list(map(float,margins)),'row_norm':float(norms[i])}}
    return {'method':'Independent Fraction F/J/midpoint inverse/B/K reconstruction on original unchanged model and box',
        'model_root':digest(model),'flow_box_root':digest(box),'jacobian':j,'midpoint_jacobian':midj,'inverse':r,'B':B,
        'norm_upper':max(norms),'norm_upper_float':float(max(norms)),'contraction':max(norms)<1,'coordinates':rows,
        'strict_inclusion':all(x['strict_inclusion'] for x in rows.values()),'pressure_producer_or_solver_called':False}

def main():
    started=time.monotonic();out=STAGE/'native-failure-diagnosis'/uuid.uuid4().hex;out.mkdir(parents=True)
    shutil.copy2(__file__,out/'executed.py')
    receipt=read(VALIDATION/'result.json');src=Path(os.environ['PYTHONPATH'])
    assert {p.relative_to(src).as_posix():sha(p) for p in src.rglob('*.py')}==receipt['source_files']
    db=sqlite3.connect((STORE/'oma.sqlite3').resolve().as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    before={t:[dict(row) for row in db.execute('SELECT * FROM '+t)] for t in ('projects','runs','candidates','revisions','check_executions')}
    get=lambda root:read_blob(root)
    blobs={}
    def read_blob(root):
        if root not in blobs:
            value=json.loads(zlib.decompress((STORE/'blobs'/(root+'.json.z')).read_bytes()));assert digest(value)==root;blobs[root]=value
        return blobs[root]
    cases=[];file_hashes={};clear=None
    for candidate in before['candidates']:
        state=get(candidate['state_root']);report=get(candidate['report_root']);rows={x['id']:x for x in report['results']}
        directory=out/candidate['id'];directory.mkdir()
        write(directory/'candidate.json',candidate);write(directory/'state.json',state);write(directory/'report.json',report)
        material=get(state['physical_networks'][0]['geometry_artifact']);write(directory/'materialization.json',material)
        path=Path(material['export_path']);assert sha(path)==material['export_sha256'];file_hashes[str(path)]=sha(path);shutil.copy2(path,directory/'actual.ifc')
        for source in state['sources']:
            path=Path(source['immutable_path']);assert sha(path)==source['sha256'];file_hashes[str(path)]=sha(path)
        artifacts={}
        for key,row in rows.items():
            for field in ('artifact','native_metrics_artifact'):
                root=(row.get('witness') or {}).get(field)
                if root:artifacts[key+':'+field]=get(root);write(directory/(key+'-'+field+'.json'),get(root))
        case={'candidate_id':candidate['id'],'status':candidate['status'],'report_root':candidate['report_root'],
            'checks':{k:v['status'] for k,v in rows.items()},'nonpassing':{k:v for k,v in rows.items() if v['status'] not in ('PASS','NOT_APPLICABLE')}}
        if candidate['status']=='UNKNOWN':clear=(candidate,state,report,rows,artifacts,directory)
        cases.append(case)
    candidate,state,report,rows,artifacts,directory=clear
    from oma.routing.network_scenario import SharedNetworkScenario
    from oma.routing.coupled_tree_pressure import derive_coupled_tree_model
    contract=state['derived_artifacts']['network_contract'];request=SharedNetworkScenario.model_validate(contract['scenario'])
    network=next(n for n in request.network_alternatives if n.network_id==contract['selected_alternative'])
    run=next(x for x in before['runs'] if x['id']==candidate['run_id']);material=get(state['physical_networks'][0]['geometry_artifact'])
    source=next(s for s in state['sources'] if s['id']==contract['source_id'])
    metrics_root=rows['network-pressure-operating-point']['witness']['native_metrics_artifact'];metrics=get(metrics_root)
    context={'candidate_root':candidate['state_root'],'baseline_root':run['base_root'],'source_sha256':source['sha256'],
        'export_sha256':material['export_sha256'],'native_semantics_root':rows['network-native-semantics']['witness']['artifact'],
        'native_metrics_root':metrics_root,'native_cad_root':rows['network-all-source-clearance']['witness']['artifact'],
        'checker_version':report['checker_version'],'mission_hash':digest(state['mission']),'rule_hash':state['mission']['rule_hash'],
        'native_metric_absolute_tolerance_m':'1/1000000'}
    model,box,derivation=derive_coupled_tree_model(request.coupled_tree,network,metrics,context=context)
    write(directory/'derived-current-model.json',model);write(directory/'original-flow-box.json',box);write(directory/'current-context.json',context);write(directory/'derivation.json',derivation)
    analysis=diagnostic(model,box);write(directory/'independent-inclusion-diagnostic.json',analysis)
    assert analysis['contraction'] and not analysis['strict_inclusion']
    assert all([dict(row) for row in db.execute('SELECT * FROM '+table)]==values for table,values in before.items())
    assert all(sha(p)==h for p,h in file_hashes.items())
    write(out/'store-rows.json',before)
    result={'status':'DIAGNOSIS_COMPLETE','validation_status':receipt['status'],'checker_version':report['checker_version'],'source_files':receipt['source_files'],
        'validation_receipt_sha256':sha(VALIDATION/'result.json'),'cases':cases,'original_input_files':file_hashes,
        'original_store_rows_and_files_unchanged':True,'native_or_pressure_producer_rerun':False,'requirements_or_flow_box_changed':False,
        'clear_candidate_model_root':digest(model),'clear_candidate_diagnostic':analysis,'elapsed_seconds':time.monotonic()-started,
        'conclusion':'One candidate has a conclusive native obstacle overlap; the other passes full native geometry but its unchanged local interval fixed-point box fails strict inclusion while contraction passes. This is unresolved local certification, not physical infeasibility or demonstrated delivery failure.'}
    write(out/'result.json',result)
    print(json.dumps({'status':result['status'],'evidence':str(out),'norm':analysis['norm_upper_float'],
        'coordinates':{k:v['float_diagnostic'] for k,v in analysis['coordinates'].items()}}))

if __name__=='__main__':main()
