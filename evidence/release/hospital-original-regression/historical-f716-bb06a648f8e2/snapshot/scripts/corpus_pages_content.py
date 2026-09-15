"""Resolve historical Pages text attachment tables using retained native IWA.

Only explicitly decoded cell types are accepted. Unknown cells, dangling object
references, attachment mismatches and unhandled equations are recorded, never
silently discarded. Reading and interpretation require separate review records.
"""
from pathlib import Path
from collections import Counter
import json
import struct
from decimal import Decimal
from corpus_pages import OUT, fields, one, sha


def ref(value):return one(fields(value),1)


def decimal128(raw):
    if len(raw)!=16:raise ValueError("Truncated decimal128")
    bits=int.from_bytes(raw,"little")
    if (bits>>125)&3==3:raise ValueError("Special decimal128 encoding requires review")
    exponent=((bits>>113)&0x3fff)-6176
    coefficient=bits&((1<<113)-1)
    if coefficient>=10**34:raise ValueError("Noncanonical decimal128 coefficient")
    return str(Decimal((bits>>127,tuple(map(int,str(coefficient))),exponent)))


def main(directory):
    inventory=json.loads((directory/"inventory.json").read_text())
    objects={};sources={};buffers={};multiple=set()
    for record in inventory["messages"]:
        member=record["member"]
        if member not in buffers:buffers[member]=(directory/(member.replace("/","__")+".bin")).read_bytes()
        data=buffers[member][record["payload_offset"]:record["payload_offset"]+record["payload_length"]]
        key=record["object_id"]
        if key in objects:multiple.add(key)
        objects[key]=(record["message_type"],fields(data))
        sources[key]=record
    storages=[json.loads(line) for line in (directory/"text-storages.jsonl").read_text(encoding="utf8").split("\n") if line]
    by_storage={r["object_id"]:r for r in storages}
    bodies=[r for r in storages if r["storage_kind"]==0]
    if len(bodies)!=1:raise ValueError("Ambiguous body")
    body=bodies[0];attachments={};tables=[];issues=[];source_issues=[];cell_types=Counter();equations=[]

    def obj(ident,kind=None):
        if ident in multiple:raise ValueError("Referenced multiple-payload object requires merge semantics")
        actual,parsed=objects[ident]
        if kind is not None and actual!=kind:raise ValueError(f"Object {ident}: expected {kind}, found {actual}")
        return parsed

    def data_list(identifier):
        parsed=obj(identifier,6005)
        if any(n==4 for n,w,v,s,e in parsed):raise ValueError("Segmented data list unresolved")
        return {one(fields(v),1):fields(v) for n,w,v,s,e in parsed if n==3}

    def table(drawable):
        info=obj(drawable,6000)
        model_id=ref(one(info,2));model=obj(model_id,6001)
        rows,cols=one(model,6),one(model,7)
        data=obj(model_id,6001);store=fields(one(data,4))
        strings=data_list(ref(one(store,4)))
        rich=data_list(ref(one(store,17))) if one(store,17) else {}
        tiles=fields(one(store,3));tile_size=one(tiles,2,256)
        result=[[""]*cols for _ in range(rows)];seen=set();cells=[]
        for n,w,value,s,e in tiles:
            if n!=1:continue
            entry=fields(value);tile_number=one(entry,1);tile_id=ref(one(entry,2))
            tile=obj(tile_id,6002)
            if one(tile,7)!=1:raise ValueError("Pre-BNC tile unresolved")
            for n,w,value,s,e in tile:
                if n!=5:continue
                row=fields(value);row_number=tile_number*tile_size+one(row,1)
                raw=one(row,6);offset_bytes=one(row,7)
                offsets=struct.unpack("<"+"h"*(len(offset_bytes)//2),offset_bytes)
                if one(row,8,0):offsets=tuple(o*4 if o>=0 else -1 for o in offsets)
                for col,start in enumerate(offsets[:cols]):
                    if start<0:continue
                    end=next((o for o in offsets[col+1:] if o>=0),len(raw))
                    cell=raw[start:end]
                    if row_number>=rows:raise ValueError("Cell outside table rows")
                    if len(cell)<12 or cell[0]!=5:raise ValueError("Unsupported cell storage")
                    kind=cell[1];cell_types[kind]+=1
                    flags=int.from_bytes(cell[8:12],"little")
                    position=12+16*bool(flags&1)+8*bool(flags&2)+8*bool(flags&4)
                    string_id=rich_id=None
                    if flags&8:string_id=int.from_bytes(cell[position:position+4],"little");position+=4
                    if flags&16:rich_id=int.from_bytes(cell[position:position+4],"little")
                    if kind==0:text=""
                    elif kind==2 and flags&1:text=decimal128(cell[12:28])
                    elif kind==3 and string_id is not None:text=one(strings[string_id],3).decode("utf8")
                    elif kind==9 and rich_id is not None:
                        wrapper=ref(one(rich[rich_id],9))
                        storage_id=ref(one(obj(wrapper,6218),1))
                        text=by_storage[storage_id]["text"]
                    elif kind==8:
                        text="<SOURCE_FORMULA_ERROR>"
                        source_issues.append({"table":drawable,"row":row_number,"column":col,"cell_type":kind,"cell_hex":cell.hex(),
                            "meaning":"Native Pages formula-error cell, not readable mathematical text. Compare surrounding prose; do not invent the missing display."})
                    else:
                        text=f"<UNRESOLVED_CELL_TYPE_{kind}>"
                        issues.append({"table":drawable,"row":row_number,"column":col,"cell_type":kind,"cell_hex":cell.hex()})
                    if (row_number,col) in seen:raise ValueError("Duplicate table cell")
                    seen.add((row_number,col));result[row_number][col]=text
                    cells.append({"row":row_number,"column":col,"tile_object":tile_id,"cell_sha256":sha(cell),"type":kind})
        record={"drawable_id":drawable,"model_id":model_id,"rows":result,"native_model":sources[model_id],"cells":cells}
        tables.append(record)
        return record

    for hex_value in body["attachment_object_table_hex"]:
        for n,w,value,s,e in fields(bytes.fromhex(hex_value)):
            if n!=1:raise ValueError("Unknown attachment table field")
            entry=fields(value);position=one(entry,1);reference=one(entry,2)
            if reference is None:continue
            attachment_id=ref(reference)
            attachment=obj(attachment_id,2003)
            drawable=ref(one(attachment,1))
            if objects[drawable][0]!=6000:
                issues.append({"attachment":attachment_id,"drawable":drawable,"type":objects[drawable][0]})
                continue
            attachments[position]=table(drawable)
    # Image equation extensions are detected across every parsed object, not
    # assumed absent merely because the main body contains literal LaTeX.
    for ident,(kind,parsed) in objects.items():
        for number,wire,value,start,end in parsed:
            if kind==3005 and number in (100,103) and wire==2:
                equations.append({"object_id":ident,"field":number,"source":value.decode("utf8")})
    # Native text attachment offsets count UTF-16 code units.
    records=[];utf16=0;character=0
    for line_no,line in enumerate(body["text"].split("\n"),1):
        start=character;u_start=utf16
        embedded=[]
        for char in line:
            if char=="\ufffc":
                if utf16 not in attachments:issues.append({"unresolved_attachment_utf16":utf16})
                else:embedded.append(attachments[utf16]["drawable_id"])
            utf16+=len(char.encode("utf-16-le"))//2;character+=1
        records.append({"paragraph":line_no,"text":line,"character_range":[start,character],
            "utf16_range":[u_start,utf16],"tables":embedded,"text_sha256":sha(line.encode())})
        utf16+=1;character+=1
    marker_count=body["text"].count("\ufffc")
    if marker_count!=len(attachments):issues.append({"attachment_count_mismatch":[marker_count,len(attachments)]})
    for name,value in [("tables",tables),("body-records",records),("equation-extensions",equations)]:
        (directory/(name+".jsonl")).write_text("".join(json.dumps(r,ensure_ascii=True)+"\n" for r in value),encoding="utf8")
    report={"source_sha256":inventory["source_sha256"],"body_storage_id":body["object_id"],"body_text_sha256":body["text_sha256"],
        "body_paragraphs":len(records),"body_characters":len(body["text"]),"attachment_markers":marker_count,
        "resolved_tables":len(tables),"table_cells":sum(len(t["cells"]) for t in tables),"cell_type_counts":dict(cell_types),
        "equation_extensions":len(equations),"issues":issues,"semantic_read_status":"NOT_READ",
        "source_content_issues":source_issues,
        "unreferenced_multiple_payload_objects":sorted(multiple),
        "notice":"Structural native extraction only; table contents and body mathematics still require tracked reading."}
    (directory/"content-audit.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf8")
    print(directory.name,json.dumps({k:v for k,v in report.items() if k not in ("issues","source_content_issues")}),
        "extraction_issues",len(issues),"source_content_issues",len(source_issues))


if __name__=="__main__":
    for directory in sorted(OUT.iterdir()):
        if (directory/"inventory.json").exists():main(directory)
