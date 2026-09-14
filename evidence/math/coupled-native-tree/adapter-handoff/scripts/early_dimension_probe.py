from pathlib import Path
import sys,json
from fractions import Fraction as Q
STAGE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(STAGE/"src"))
from oma.routing.coupled_tree_pressure import derive_coupled_tree_model,METRIC_SCHEMA
from oma.optimization.coupled_tree_pressure import compile_coupled_tree_pressure


def inputs():
    old=STAGE.parent/"passive-native-tree/evidence/native-three-sink/5c0e4ad0641d4acab0aca886eb023bf0"
    net=json.loads((old/"specification.json").read_text(encoding="utf-8"))
    metric=json.loads((old/"native-metrics.json").read_text(encoding="utf-8"));metric["schema"]=METRIC_SCHEMA
    bd=json.loads((old/"new-boundary-declaration.json").read_text(encoding="utf-8"))
    bd["schema"]="oma.coupled-tree-boundary/1";bd.pop("tee_common_loss_coefficients")
    bd["tee_outlet_loss_coefficients"]={"tee-1":{"b":"1/5","branch":"3/10"},"tee-2":{"b":"1/4","branch":"2/5"}}
    bd["tee_loss_reference"]="OUTLET_SPECIFIC_TOTAL_LOSS_AT_TOTAL_INLET_FLOW"
    bd["applicability"]="New synthetic unequal-outlet total inlet-flow loss contract on copied geometric data, no prior pressure acceptance reused"
    bd["source_total_pressure_pa"]={"lower":"200","upper":"200"}
    bd["sink_total_pressures_pa"]={k:{"lower":"0","upper":"0"} for k in bd["sink_total_pressures_pa"]}
    flows=dict(zip(sorted(bd["sink_total_pressures_pa"]),map(Q,["3/1000","3/2000","1/1000"])))
    bd["flow_search_box_m3_s"]={k:{"lower":str(q-Q(1,100000)),"upper":str(q+Q(1,100000))} for k,q in flows.items()}
    model,_,_=derive_coupled_tree_model(bd,net,metric,context={"case":"early-dimensional-size-probe"})
    for leaf in flows:
        total=sum((sum(map(Q,model["coefficients"][t["coefficient_id"]].values()))/2*sum((flows[k] for k in t["descendant_leaves"]),Q())**2
                   for t in model["terms"] if leaf in t["applies_to_leaves"]),Q())
        point=Q(200)-total;lo=(point*1000000).__floor__()
        bd["sink_total_pressures_pa"][leaf]={"lower":str(Q(lo,1000000)),"upper":str(Q(lo+1,1000000))}
    return bd,net,metric


if __name__=="__main__":
    bd,net,metric=inputs()
    model,box,der=derive_coupled_tree_model(bd,net,metric,context={"case":"early-dimensional-size-probe"})
    result=compile_coupled_tree_pressure(model,box,max_leaves=3,max_terms=16,max_matrix_entries=9)
    path=STAGE/"evidence/early-dimensional-size-probe";path.mkdir(parents=True,exist_ok=True)
    for name,value in [("model",model),("box",box),("boundary",bd),("result",result)]:
        (path/(name+".json")).write_text(json.dumps(value,indent=2)+"\n",encoding="utf-8")
    print(result["status"],result.get("reason"),result.get("contraction_norm_upper"))
