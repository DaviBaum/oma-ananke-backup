"""Exact attribution of a retained failed certificate's center-image enclosure.

No producer, native conversion, altered query, root solver or feasibility claim.
"""
from pathlib import Path
from fractions import Fraction as Q
import hashlib,json,uuid

STAGE=Path(__file__).resolve().parents[1];ROOT=STAGE.parents[2]
SOURCE=ROOT/'.oma/development/shared-tree-coupled-review/native-failure-diagnosis/bf30660a8c004eb2ac3ca5b145d4e6d4/4da629335f274aaa952503accba8b714'
OUT=STAGE/'evidence/native-center-width'/uuid.uuid4().hex;OUT.mkdir(parents=True)
inputs={}
for name in ('derived-current-model.json','original-flow-box.json','independent-inclusion-diagnostic.json'):
 data=(SOURCE/name).read_bytes();(OUT/name).write_bytes(data);inputs[name]=hashlib.sha256(data).hexdigest()
(OUT/'executed.py').write_bytes(Path(__file__).read_bytes())
m=json.loads((OUT/'derived-current-model.json').read_text(encoding='utf-8'))
box=json.loads((OUT/'original-flow-box.json').read_text(encoding='utf-8'))
d=json.loads((OUT/'independent-inclusion-diagnostic.json').read_text(encoding='utf-8'))
def center(interval):return (Q(interval['lower'])+Q(interval['upper']))/2
def radius(interval):return (Q(interval['upper'])-Q(interval['lower']))/2
leaves=m['leaves'];x={sid:center(box[sid]) for sid in leaves}
R=[[Q(value) for value in row] for row in d['inverse']]
coefficient_width=[];head_width=[]
for leaf in leaves:
 coefficient_width.append(sum((radius(m['coefficients'][term['coefficient_id']])*sum((x[sid] for sid in term['descendant_leaves']),Q(0))**2
  for term in m['terms'] if leaf in term['applies_to_leaves']),Q(0)))
 head_width.append(radius(m['available_heads'][leaf]))
rows=[]
for i,leaf in enumerate(leaves):
 coefficient=sum((abs(R[i][j])*coefficient_width[j] for j in range(len(leaves))),Q(0))
 head=sum((abs(R[i][j])*head_width[j] for j in range(len(leaves))),Q(0))
 total=coefficient+head;query=radius(box[leaf])
 rows.append({'leaf':leaf,'query_half_width':str(query),'center_image_half_width':str(total),
   'coefficient_contribution':str(coefficient),'available_head_contribution':str(head),
   'head_fraction':str(head/total),'width_minus_query':str(total-query),
   'display':{'query_half_width':float(query),'center_image_half_width':float(total),
    'coefficient_contribution':float(coefficient),'available_head_contribution':float(head),'head_fraction':float(head/total)}})
result={'schema':'oma.retained-center-enclosure-width-attribution/1','status':'DIAGNOSTIC_ONLY',
 'input_hashes':inputs,'model_root':d['model_root'],'flow_box_root':d['flow_box_root'],
 'method':'Exact Fraction decomposition of sum_j |R_ij| rad(F_j(center)) into named coefficient and available-head interval widths',
 'rows':rows,'row_residual_widths':{'coefficient':list(map(str,coefficient_width)),'available_head':list(map(str,head_width))},
 'original_inputs_unchanged':all(hashlib.sha256((SOURCE/name).read_bytes()).hexdigest()==value for name,value in inputs.items()),
 'scope':'Attribution of the original conservative center-image enclosure only, not actual solution error or root location. No changed pressure, query box, physical parameter, local/global producer or native execution.'}
assert result['original_inputs_unchanged']
(OUT/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'path':str(OUT/'result.json'),'rows':[{k:v for k,v in row.items() if k in ('leaf','display')} for row in rows]}))
