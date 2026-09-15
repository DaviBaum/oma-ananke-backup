"""Exact interval comparison of independently replayed Hospital alternatives."""
from pathlib import Path
from fractions import Fraction
import argparse,hashlib,json,shutil,uuid
ROOT=Path(__file__).resolve().parents[3];STAGE=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('audit',type=Path);a=p.parse_args();audit=a.audit.resolve()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def enc(lo,hi):return {'lower':str(lo),'upper':str(hi)}
def interval(record):return Fraction(record['lower']),Fraction(record['upper'])
root=sha(audit/'result.json');result=read(audit/'result.json');assert result['status']=='BOTH_FIXED_ALTERNATIVES_AND_SELECTED_FRESH_EXPORT_AUDITED'
assert result['files_unchanged'] and result['app_unchanged'] and result['store_project_unchanged']
rows={r['id']:r for r in result['candidates']};assert len(rows)==2
selected=rows[result['selection']['selected']];other=next(r for r in rows.values() if r['id']!=selected['id'])
assert selected['status']==other['status']=='CHECKED'
assert selected['fixed_flow']['prescribed_sink_flows_m3_s']==other['fixed_flow']['prescribed_sink_flows_m3_s']
assert selected['fixed_flow']['source_flow_m3_s']==other['fixed_flow']['source_flow_m3_s']=='1/1000'
assert selected['fixed_flow']['operating_point_solution']==other['fixed_flow']['operating_point_solution']=='NOT_ESTABLISHED'
packet=read(audit/'generation-packet.json');physics=packet['result']['mission']['physics'];rho_g=Fraction(str(physics['density_kg_m3']))*Fraction(str(physics['gravity_m_s2']));assert rho_g>0
paths={}
for sid,one in selected['fixed_flow']['paths'].items():
 two=other['fixed_flow']['paths'][sid];assert one['status']==two['status']=='PASS';comparisons={}
 for key in ['irreversible_loss_pa','required_source_minus_sink_static_pressure_pa']:
  slo,shi=interval(one[key]);olo,ohi=interval(two[key]);dlo,dhi=olo-shi,ohi-slo
  comparisons[key]={'selected':one[key],'other':two[key],'other_minus_selected':enc(dlo,dhi),'strict_separated_improvement':dlo>0,'identical_enclosures':one[key]==two[key]}
  if key=='irreversible_loss_pa':comparisons[key]['head_loss_other_minus_selected_m']=enc(dlo/rho_g,dhi/rho_g)
 paths[sid]=comparisons
firstfit=selected['reported_objective']['fitting_count'];secondfit=other['reported_objective']['fitting_count'];assert firstfit.is_integer() and secondfit.is_integer() and secondfit>0
length_first=Fraction(str(selected['reported_objective']['length_m']));length_other=Fraction(str(other['reported_objective']['length_m']))
summary={'status':'EXACT_CHECKED_ALTERNATIVE_METRIC_COMPARISON','audit_result':str(audit/'result.json'),'audit_result_sha256':root,'selected_candidate':selected['id'],'comparison_candidate':other['id'],
 'length_m':{'selected':str(length_first),'other':str(length_other),'reduction':str(length_other-length_first),'fraction_reduction':str((length_other-length_first)/length_other)},
 'fitting_count':{'selected':int(firstfit),'other':int(secondfit),'reduction':int(secondfit-firstfit),'fraction_reduction':str(Fraction(int(secondfit-firstfit),int(secondfit)))},
 'declared_metric_cost_improvement':result['improvement'],'prescribed_sink_flows_m3_s':selected['fixed_flow']['prescribed_sink_flows_m3_s'],'source_flow_m3_s':'1/1000','paths':paths,
 'scope':'New hypothetical fixed simultaneous-flow mission, two completely checked generated alternatives. Head/pressure differences are exact rational deductions under declared native metric, ideal bore and friction/loss assumptions. This does not establish an operating point or improvement over an installed Hospital network.'}
assert sha(audit/'result.json')==root
out=STAGE/'metric-comparisons'/uuid.uuid4().hex;out.mkdir(parents=True);shutil.copyfile(__file__,out/'executed-comparison.py');(out/'result.json').write_text(json.dumps(summary,indent=2));print(json.dumps({'output':str(out),'sha256':sha(out/'result.json')}))
