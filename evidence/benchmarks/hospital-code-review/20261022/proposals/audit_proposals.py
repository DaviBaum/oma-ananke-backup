"""Independent retained-hospital proposal audit; no application imports.

Checks persisted bindings and arithmetic, and inventories physical assumptions.
Does not establish jurisdiction, code applicability, source geometry or engineering.
"""
from pathlib import Path
from fractions import Fraction as F
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib, json, zlib, gzip, sqlite3

HERE = Path(__file__).resolve().parent
ROOT = next(p for p in HERE.parents if (p / 'AGENTS.md').exists())
CAMPAIGNS = ['2f25fd1064cb4547ae3667b9bbd4e69b', '3d9c5dc8a37b41f78b7a2233b2cb5c2d']
def sha(b): return hashlib.sha256(b).hexdigest()
def canonical(x): return json.dumps(x, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
def jread(p): return json.loads(p.read_text(encoding='utf-8'))
def require(ok, msg):
    if not ok: raise AssertionError(msg)
def finish(x):
    if isinstance(x, F): return str(x)
    if isinstance(x, dict): return {str(k):finish(v) for k,v in x.items()}
    if isinstance(x, (list,tuple)): return [finish(v) for v in x]
    return x

def run(cid):
    p = ROOT / 'evidence/benchmarks/hospital-whole-procurement' / cid
    files = {}; roots = {}
    def bound_file(relative):
        target=p/relative; data=target.read_bytes();files[str(target.relative_to(ROOT))]=sha(data); return data
    handoff=json.loads(bound_file('handoff.json'))
    for relative,expected_sha in handoff['retained_files'].items():
        require(sha((p/relative).read_bytes())==expected_sha,'Closed retained file changed: '+relative)
    index = json.loads(bound_file('artifact-index.json'))
    def blob(identity):
        entry=index[identity]; path=ROOT/entry['path_from_repository_root']; raw=path.read_bytes()
        require(sha(raw)==entry['encoded_sha256'], 'Compressed artifact hash mismatch')
        data=zlib.decompress(raw); require(sha(data)==identity, 'Persisted artifact root mismatch')
        roots[identity]={'path':str(path.relative_to(ROOT)),'encoded_sha256':sha(raw)}
        return json.loads(data)
    report=json.loads(bound_file('campaign/report.json'))
    replay=json.loads(gzip.decompress(bound_file('independent-review/replay.json.gz')))
    require(replay['status']=='PASS','Earlier independent arithmetic replay did not pass')
    require(blob(replay['packet_root'])==report,'Readable report differs from persisted report')
    require(replay['plan_root']==report['purchasing_plan_root'],'Replay plan binding mismatch')
    plan=blob(report['purchasing_plan_root'])
    mission=json.loads(bound_file('campaign/mission.json'))
    declaration=json.loads(bound_file('campaign/predeclaration.json'))
    db=p/'store/oma.sqlite3';db_before=sha(db.read_bytes())
    with sqlite3.connect(db.resolve().as_uri()+'?mode=ro&immutable=1', uri=True) as con:
        row=con.execute('SELECT status,request,base_root,base_revision FROM runs WHERE id=?',(replay['run_id'],)).fetchone()
    require(row is not None and row[0]=='COMPLETED','Run not persisted completed')
    request=json.loads(row[1]);require(sha(canonical(request))==report['request_root'],'Request root mismatch')
    require(request==declaration['request'],'Declaration/request mismatch')
    require(request['mission']==mission,'Mission/request mismatch')
    require(row[2]==report['base_root'] and row[3]==report['base_revision'],'Base identity mismatch')
    require(declaration['checker_version']==report['checker_version'],'Checker version mismatch')
    require(sha(db.read_bytes())==db_before,'Store changed during read')
    files[str(db.relative_to(ROOT))]=db_before
    source_checks=[]
    for source in report['source_files']:
        raw=Path(source['path']).read_bytes();require(sha(raw)==source['sha256'],'Original source changed')
        source_checks.append({'path':source['path'],'sha256':sha(raw),'bytes':len(raw)})
    pieces={};source_labels={};takeoffs=[]
    for source in report['sources']:
        takeoff=blob(source['takeoff_root']);require(takeoff['source_sha256']==source['source_id'],'Source/takeoff identity')
        source_labels[source['source_id']]=source['discipline_label']
        takeoffs.append({'source':source['name'],'source_id':source['source_id'],'takeoff_root':source['takeoff_root'],'summary':takeoff['summary']})
        for piece in takeoff['pieces']:
            require(piece['id'] not in pieces,'Duplicate measured piece'); pieces[piece['id']]=piece
    metadata=json.loads(bound_file('price-basis/mission-basis.json'))['price_metadata']
    reference_prices=json.loads(bound_file('price-basis/reference-prices.json'))
    by_discipline=defaultdict(Counter);by_type=defaultdict(Counter); price_method=defaultdict(Counter)
    grouped=[];short_grooved=[];short_fabrication=defaultdict(list); plan_counts=Counter()
    total_splices=0; seen_original=[]; total_rounded=F(0); total_original=F(0)
    for group in plan['groups']:
        gid=group['stock_group']; source=group['source_id']; label=source_labels[source]
        originals=[pieces[i] for i in group['original_piece_ids']];seen_original.extend(group['original_piece_ids'])
        require(all(x['stock_group']==gid and x['source_id']==source for x in originals),'Group/source compatibility identity mismatch')
        policy=mission['group_policies'].get(gid,mission['stock_policies'].get(group['stock_kind']))
        gp=group['policy']
        require(set(policy)==set(gp),'Policy fields differ from mission')
        for key in policy:
            if key in ('kerf_m','end_trim_m','cut_increment_m'): require(F(policy[key])==F(gp[key]),'Policy scalar differs')
            elif key=='stock_lengths_m': require([F(x) for x in policy[key]]==[F(x) for x in gp[key]],'Policy stock lengths differ')
            elif key=='unit_price_per_m': require({k:F(v) for k,v in policy[key].items()}=={k:F(v) for k,v in gp[key].items()},'Policy price differs')
            else: require(policy[key]==gp[key],'Policy differs from mission')
        opt=group['optimization'];ins=opt['inputs']; demands={x['id']:x for x in ins['pieces']};stock={x['id']:x for x in ins['stock_catalogue']}
        kerf=F(policy['kerf_m']);trim=F(policy['end_trim_m']);increment=F(policy['cut_increment_m'])
        capacity=((max(F(x) for x in policy['stock_lengths_m'])-kerf-trim)//increment)*increment
        expected={}; fab_by_source={x['source_piece_id']:x for x in group['fabrication']}
        for piece in originals:
            pid=piece['id'];length=F(piece['length_m']);rounded=-(-length//increment)*increment
            total_rounded+=rounded;total_original+=length
            chunks=[];rem=rounded
            while rem>0:
                chunks.append(min(rem,capacity));rem-=chunks[-1]
            if policy['long_segments']=='RETAIN_OVERSIZE': require(len(chunks)==1,'Split in no-split scenario')
            f=fab_by_source[pid]; require(f['assumed_additional_splices']==len(chunks)-1,'Splice count mismatch')
            require(F(f['required_length_m'])==rounded,'Rounded quantity mismatch')
            for n,v in enumerate(chunks): expected[f'{pid}/fabrication/{n}']=v
            splices=len(chunks)-1;total_splices+=splices
            typ=' | '.join(x.get('name','') or '' for x in piece['ifc_types']) or piece.get('object_type') or 'UNSPECIFIED'
            key=label+' :: '+typ
            for counter in (by_discipline[label],by_type[key]):
                counter['original_segments']+=1;counter['fabrication_pieces']+=len(chunks);counter['assumed_additional_splices']+=splices
                counter['source_spans_split']+=int(splices>0)
                counter['missing_material']+=int(not piece['materials'])
                counter['unverified_compatibility']+=int(not piece['stock_compatibility_verified'])
                counter['unverified_engineering']+=int(piece['engineering_status']!='VERIFIED')
                counter['unverified_global_geometry']+=int(not piece['geometry_evidence']['global_geometry_verified'])
            for n,v in enumerate(chunks):
                if v<F('0.1'):
                    short_fabrication[label].append({'piece_id':pid,'fabrication_index':n,'length_m':str(v),'original_length_m':str(length),'created_by_splitting_long_span':bool(splices),'type':typ})
                if 'grov' in typ.lower() and v<F('0.205'):
                    short_grooved.append({'piece_id':pid,'fabrication_index':n,'length_m':str(v),'original_length_m':str(length),'created_by_splitting_long_span':bool(splices),'type':typ,'profile':piece['profile_si']})
        require(set(expected)==set(demands),'Fabrication identity differs from independently rebuilt demand')
        require(all(F(demands[k]['length_m'])==v for k,v in expected.items()),'Fabrication quantity differs')
        for pname,cutplan in opt['plans'].items():
            observed=[];required=F(0);purchased=F(0);offcut=F(0);price=F(0);count=0
            for bar in cutplan['bins']:
                s=stock[bar['stock_id']];L=F(s['length_m']);require(L==F(bar['stock_length_m']),'Stock length identity')
                require(F(bar['end_trim_m'])==trim,'Trim mismatch'); cursor=trim
                for cut in bar['cuts']:
                    cid2=cut['piece_id'];require(cid2 in demands,'Unknown fabrication piece');v=F(demands[cid2]['length_m'])
                    require(F(cut['length_m'])==v and F(cut['start_m'])==cursor and F(cut['end_m'])==cursor+v,'Cut geometry mismatch')
                    require(F(cut['kerf_after_m'])==kerf,'Kerf mismatch');cursor+=v+kerf
                    observed.append(cid2);required+=v;count+=1
                require(cursor<=L,'Stock capacity exceeded');require(F(bar['offcut_length_m'])==L-cursor,'Offcut mismatch')
                purchased+=L;offcut+=L-cursor;price+=F(s['unit_price'])
            require(Counter(observed)==Counter(demands.keys()),'Missing or repeated fabrication piece')
            computed={'required_length_m':required,'purchased_length_m':purchased,'kerf_loss_m':kerf*count,'trim_loss_m':trim*len(cutplan['bins']),'offcut_length_m':offcut,'total_waste_m':purchased-required,'stock_count':len(cutplan['bins']),'piece_count':count,'total_price':price}
            require(all(F(cutplan['totals'][k])==v for k,v in computed.items()),'Plan total mismatch')
            plan_counts[pname+'_cuts']+=count;plan_counts[pname+'_stock']+=len(cutplan['bins']);plan_counts['group_plans_checked']+=1
        meta=metadata[gid]; cost=F(group['plans']['selected']['total_price']); method=meta['price_method']
        price_method[method]['groups']+=1;price_method[method]['selected_material_cost_usd']+=cost
        price_method[method]['original_segments']+=len(originals)
        grouped.append({'stock_group':gid,'source_id':source,'discipline':label,'stock_kind':group['stock_kind'],'original_segments':len(originals),'assumed_splices':group['assumed_splices'],'cost_usd':str(cost),'reference_ids':meta['reference_ids'],'actual_material_or_quote_match':meta['actual_material_or_quote_match'],'price_method':method})
    require(len(seen_original)==len(set(seen_original)),'Duplicate original span across groups')
    require(total_splices==plan['assumed_splices_same_in_all_plans'],'Total splice mismatch')
    require(len(seen_original)==plan['planned_original_piece_count'],'Planned source coverage mismatch')
    return finish({'campaign':cid,'run_id':replay['run_id'],'audit_status':'INDEPENDENT_ARITHMETIC_AND_BINDINGS_PASS_ENGINEERING_UNVERIFIED','all_closed_handoff_file_hashes_match':True,'closed_handoff_file_count':len(handoff['retained_files']),'packet_root':replay['packet_root'],'plan_root':replay['plan_root'],'request_root':report['request_root'],'base_root':report['base_root'],'checker_version':report['checker_version'],'source_checks':source_checks,'files':files,'artifact_bindings':roots,'takeoffs':takeoffs,'planned_original_segments':len(seen_original),'assumed_additional_splices':total_splices,'exact_original_length_m':total_original,'rounded_fabrication_length_m':total_rounded,'rounding_allowance_m':total_rounded-total_original,'fresh_cut_arithmetic_checks':plan_counts,'per_discipline':dict(by_discipline),'per_type':dict(by_type),'price_methods':dict(price_method),'groups':grouped,'grooved_label_cuts_below_205mm':short_grooved,'short_fabrication_pieces_below_100mm':dict(short_fabrication),'no_manufacturer_or_project_specification_match_count':sum(not g['actual_material_or_quote_match'] for g in grouped),'construction_approval':False,'physical_suitability':'NOT_ESTABLISHED','jurisdiction_and_code_applicability':'NOT_ESTABLISHED','previous_replay':{k:replay[k] for k in ['status','scope','verifier_sha256','whole_building_engineering_verdict']},'scope_limits':['Arithmetic replay does not validate source geometry, end treatment, tolerances, stock compatibility, specified product identity or code compliance.','Short grooved-label pieces are conditional manufacturer-screen flags, not proven project code violations. Tool and joint method are unspecified.','No product is approved by dimension-only pricing interpolation or extrapolation.','Zero additional splits does not authenticate original geometry, design or material.']})

if __name__=='__main__':
    result={'schema':'oma.hospital-proposal-code-evidence-audit/1','generated_at_utc':datetime.now(timezone.utc).isoformat(),'script_sha256':sha(Path(__file__).read_bytes()),'producer_modules_imported':False,'campaigns':[run(x) for x in CAMPAIGNS]}
    (HERE/'proposal-audit.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps([{'campaign':x['campaign'],'status':x['audit_status'],'planned_segments':x['planned_original_segments'],'splices':x['assumed_additional_splices'],'discipline':x['per_discipline'],'short_grooved':len(x['grooved_label_cuts_below_205mm'])} for x in result['campaigns']],indent=2))
