"""Read-only source capture and exact role/outlet incidence design oracle."""
from pathlib import Path
from fractions import Fraction as Q
from itertools import permutations
import hashlib,json

STAGE=Path(__file__).resolve().parents[1]
ROOT=STAGE.parents[2]
APP=ROOT/'.oma/development/shared-tree-native/src'
OUT=STAGE/'evidence';OUT.mkdir(parents=True,exist_ok=True)
def sha(b):return hashlib.sha256(b).hexdigest()
paths=['oma/routing/shared_tree_requirements.py','oma/routing/shared_tree_proposals.py',
 'oma/routing/shared_tree_catalogue_check.py','oma/routing/network_scenario.py',
 'oma/routing/coupled_tree_scenario.py','oma/routing/coupled_tree_pressure.py',
 'oma/routing/network_checker.py','oma/routing/selection.py','oma/optimization/shared_tree_synthesis.py',
 'oma/optimization/coupled_tree_pressure.py','oma/optimization/coupled_tree_univalence.py']
records=[]
for p in paths:
    data=(APP/p).read_bytes();target=OUT/'reviewed-source'/p;target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():assert target.read_bytes()==data,'Refuse to replace reviewed source'
    else:target.write_bytes(data)
    records.append({'path':p,'sha256':sha(data)})
excerpt=ROOT/'.oma/development/next-math-priority/evidence/source-excerpts.json'
(OUT/'source-excerpts.json').write_bytes(excerpt.read_bytes())
roles={'tee-A':{'b':Q(1,5),'branch':Q(3,10)},'tee-C':{'b':Q(1,4),'branch':Q(2,5)}}
leaves=('sink-a','sink-b','sink-c');flow=dict(zip(leaves,(Q(3,1000),Q(2,1000),Q(1,1000))))
def square_sum(ids):return sum((flow[x] for x in ids),Q(0))**2
def derive(root,child,child_port,single,child_b,child_branch,coefficients):
    root_leaf_port='branch' if child_port=='b' else 'b'
    descendants=(child_b,child_branch)
    # Independent abstract path accounting, not native diameter/length data.
    energy={single:(Q(1,10)+coefficients[root][root_leaf_port])*square_sum(leaves)+flow[single]**2}
    for leaf,outlet in ((child_b,'b'),(child_branch,'branch')):
        energy[leaf]=(Q(1,10)+coefficients[root][child_port])*square_sum(leaves)
        energy[leaf]+=(Q(1,20)+coefficients[child][outlet])*square_sum(descendants)+flow[leaf]**2
    return energy
rows=[]
for root,child in permutations(roles):
    for child_port in ('b','branch'):
        for single,b,branch in permutations(leaves):
            energies=derive(root,child,child_port,single,b,branch,roles)
            rows.append({'root':root,'child':child,'child_enters_from_root_port':child_port,
              'root_direct_sink':single,'child_b_sink':b,'child_branch_sink':branch,
              'tee_ids':sorted(roles),'head_at_manufactured_flow':{k:str(energies[k]) for k in leaves}})
assert len(rows)==24
assert len({json.dumps(r,sort_keys=True) for r in rows})==24
assert all(r['tee_ids']==sorted(roles) for r in rows)
first=derive('tee-A','tee-C','b','sink-a','sink-b','sink-c',roles)
swapped={'tee-A':roles['tee-C'],'tee-C':roles['tee-A']}
wrong=derive('tee-A','tee-C','b','sink-a','sink-b','sink-c',swapped)
residual={leaf:str(wrong[leaf]-first[leaf]) for leaf in leaves}
assert all(Q(x)!=0 for x in residual.values())
result={'schema':'oma.generated-coupled-tree-design-oracle/1','status':'PASS',
 'source_files':records,'source_manifest_root':sha(json.dumps(records,sort_keys=True,separators=(',',':')).encode()),
 'topological_templates':24,'source_of_count':'Two ordered distinct tee roles, two root child outlets, six sink permutations',
 'role_outlet_coefficients':{r:{k:str(v) for k,v in x.items()} for r,x in roles.items()},
 'manufactured_leaf_flows_m3_s':{k:str(v) for k,v in flow.items()},
 'templates':rows,'coefficient_swap_counterexample':{'bound_available_heads':{k:str(v) for k,v in first.items()},
 'wrong_role_permutation_residual':residual},
 'scope':'Exact abstract path-accounting/design example only; ignores cap geometry and native metric authority. No root existence theorem, physical feasible template count or pressure acceptance claim.'}
(OUT/'assessment.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'path':str(OUT/'assessment.json'),'sha256':sha((OUT/'assessment.json').read_bytes()),'templates':24,'swap_residual':residual}))
