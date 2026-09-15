"""Capture native IFC converter diagnostics and source dependency coverage."""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from oma.ifc.audit import atomic_json,sha256_file


def probe(path,output):
    import ifcopenshell,ifcopenshell.geom
    start=time.perf_counter()
    ifcopenshell.get_log()
    ifcopenshell.ifcopenshell_wrapper.set_log_format_json()
    model=ifcopenshell.open(str(path))
    products=[e for e in model.by_type("IfcElement") if not e.is_a("IfcFeatureElementSubtraction")]
    settings=ifcopenshell.geom.settings()
    settings.set("iterator-output",ifcopenshell.ifcopenshell_wrapper.SERIALIZED)
    settings.set("use-world-coords",True)
    iterator=ifcopenshell.geom.iterator(settings,model,4,include=products)
    produced=[]
    if iterator.initialize():
        while True:
            produced.append(iterator.get().id)
            if not iterator.next():
                break
    raw=ifcopenshell.get_log()
    records=[]
    for line in raw.splitlines():
        try:
            row=json.loads(line)
        except Exception:
            row={"level":"UNPARSEABLE","message":line}
        records.append(row)
    result={"source_path":str(Path(path).resolve()),"source_sha256":sha256_file(path),
            "physical_products":len(products),"products_with_native_output":len(produced),
            "diagnostic_counts":dict(Counter(r.get("level") for r in records)),
            "message_counts":dict(Counter(r.get("message") for r in records)),
            "diagnostics":records,"seconds":time.perf_counter()-start}
    atomic_json(output,result)
    print(json.dumps({k:result[k] for k in ("physical_products","products_with_native_output","diagnostic_counts","message_counts","seconds")}),flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    probe(args.source,Path(args.output))
