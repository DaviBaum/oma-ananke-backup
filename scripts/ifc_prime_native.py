"""Build or independently revalidate native source geometry without a route verdict."""
from __future__ import annotations
import argparse
from collections import Counter
from pathlib import Path
import json
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from oma.ifc.audit import atomic_json
from oma.ifc.cad import load_cad,VERTEX_HULL_SOURCE_REPRESENTATION_POLICY,DEFAULT_SOURCE_REPRESENTATION_POLICY


def prime(source,output,policy):
    started=time.perf_counter();last=started;stages=Counter();cache={}
    def checkpoint(stage):
        nonlocal last
        stages[stage]+=1
        if time.perf_counter()-last>=30:
            print(json.dumps({"source":str(source),"stage":stage,"counts":dict(stages),"seconds":time.perf_counter()-started}),flush=True)
            last=time.perf_counter()
    objects,errors=load_cad(source,cache_directory=ROOT/".oma/cad-cache",cache_report=cache,
                           source_representation_policy=policy,checkpoint=checkpoint)
    unresolved=[{"entity_id":o.entity_id,"reason":o.reason,"support_evidence":o.support_evidence} for o in objects
                if not o.valid and o.support_kind!="exact_source_support_enclosure"]
    result={"source":str(source),"source_representation_policy":policy,"cache":cache,"objects":len(objects),
            "errors":errors,"unresolved":unresolved,"support_counts":dict(Counter(o.support_kind for o in objects)),
            "checkpoint_counts":dict(stages),"seconds":time.perf_counter()-started,
            "scope":"Native source artifact readiness only; no candidate or whole-building verdict"}
    atomic_json(output,result)
    print(json.dumps({k:v for k,v in result.items() if k!="unresolved"}),flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source",type=Path)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--representation-policy",choices=(DEFAULT_SOURCE_REPRESENTATION_POLICY,VERTEX_HULL_SOURCE_REPRESENTATION_POLICY),default=DEFAULT_SOURCE_REPRESENTATION_POLICY)
    args=parser.parse_args()
    prime(args.source,args.output,args.representation_policy)
