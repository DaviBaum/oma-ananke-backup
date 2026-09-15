"""Independent read-only arithmetic/retained-connection review; no producer calls."""
from pathlib import Path
from fractions import Fraction as Q
from collections import Counter
from math import isqrt
import hashlib,json,shutil,uuid

ROOT=Path(__file__).resolve().parents[3]
STAGE=Path(__file__).resolve().parent
BILL=ROOT/'.oma/development/hospital-cost-readiness/checked-bill-v3'
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def dump(p,v):p.write_text(json.dumps(v,indent=2),encoding='utf-8')

out=STAGE/'bill-peer'/uuid.uuid4().hex;out.mkdir(parents=True)
shutil.copyfile(__file__,out/'executed-review.py')
report_path=BILL/'result.json';report=json.loads(report_path.read_text())
inputs={str(report_path):sha(report_path),str(ROOT/'scripts/checked_network_takeoff.py'):sha(ROOT/'scripts/checked_network_takeoff.py')}
assert inputs[str(ROOT/'scripts/checked_network_takeoff.py')]==report['script_sha256']
for path,h in report['inputs'].items():
    assert sha(path)==h
    inputs[path]=h
assert report['status']=='SOURCE_BOUND_UNPRICED_NOMINAL_BILL_COMPARISON'
rows=[]
for declared in report['alternatives']:
    directory=BILL/declared['candidate_id']
    for name in ('materialization','network-native-semantics'):
        p=directory/(name+'.json');inputs[str(p)]=sha(p)
    material=json.loads((directory/'materialization.json').read_text())
    sem=json.loads((directory/'network-native-semantics.json').read_text())
    spec=material['network_spec'];components=spec['components']
    total=Q(0);counts=Counter(c['kind'] for c in components)
    for c in components:
        if c['kind']!='segment':continue
        g=c['geometry'];d=[Q(str(a))-Q(str(b)) for a,b in zip(g['start_m'],g['end_m'],strict=True)]
        square=sum(x*x for x in d);n=isqrt(square.numerator);den=isqrt(square.denominator)
        assert n*n==square.numerator and den*den==square.denominator
        total+=Q(n,den)
    ports={(p['component_id'],p['slot']):p['port_step_id'] for p in sem['ports']}
    assert len(ports)==len(sem['ports'])==len(set(ports.values()))
    intended=[(ports[(c['source']['component'],c['source']['port'])],ports[(c['sink']['component'],c['sink']['port'])]) for c in spec['connections']]
    assert len(intended)==len(set(intended))==sem['connections']
    assert Counter(intended)==Counter(tuple(pair) for pair in sem['connectivity'])
    bill={'P':str(total),'T':str(counts['tee']),'E':str(counts['elbow']),'J':str(len(intended))}
    assert bill==declared['bill_quantities']
    assert declared['site_fabrication_joint_count'] is None and declared['installed_cost'] is None
    rows.append({'candidate':declared['candidate_id'],'role':declared['role'],'quantities':bill,'straight_piece_count':counts['segment'],'actual_retained_IFC_port_connections':len(intended),'source_ifc_sha256':material['source_sha256'],'export_ifc_sha256':material['export_sha256']})
selected=next(r for r in rows if r['candidate']==report['selected_candidate'])
other,=[r for r in rows if r['role']=='alternative' and r!=selected]
fresh,=[r for r in rows if r['role']=='fresh_export']
assert selected['quantities']==fresh['quantities']
assert selected['export_ifc_sha256']==fresh['export_ifc_sha256']
delta={k:str(Q(other['quantities'][k])-Q(selected['quantities'][k])) for k in selected['quantities']}
assert delta=={'P':'0','T':'0','E':'4','J':'8'}
assert all(sha(p)==h for p,h in inputs.items())
dump(out/'bound-bill-result.json',report)
dump(out/'inputs.json',inputs)
result={'status':'READ_ONLY_NOMINAL_BILL_AND_SYMBOLIC_FORMULA_REVIEW_PASS','bill_result_sha256':sha(report_path),'rows':rows,'difference_other_minus_selected':delta,'selected_formula':'4.625 P + T + 3 J + C','other_formula':'4.625 P + T + 4 E + 11 J + C','conditional_difference':'4 E + 8 J','conditional_relative_savings':'(4 E + 8 J)/(4.625 P + T + 4 E + 11 J + C), only for positive denominator and common excluded cost C','assumptions':['Common nonnegative rates for identical items. E is elbow supply only.','J is separate work per model interface only if an installation mapping supports it; otherwise set aside J. Do not double-count joint work already included in installed component rates.','C must actually be equal for cancellation. Cutting/waste, seven versus three stock pieces, prefabrication, supports and other excluded costs can differ.'],'distinctions':['Both networks use 37/8 m nominal straight pieces. The 13.6% full-centreline reduction is not a 13.6% straight-pipe purchase reduction.','3 and 11 are exact retained IFC internal port relationships, not verified site weld/coupler/joint counts.','No authenticated price, procurement allowance or installed construction saving; no whole-hospital or structural safety claim.','Review reused prior pinned native evidence and rehashed current IFC bytes; no new native geometry or producer run.'],'all_inputs_unchanged':True}
dump(out/'result.json',result)
print(json.dumps({'path':str(out),'result_sha256':sha(out/'result.json'),'difference':delta}))
