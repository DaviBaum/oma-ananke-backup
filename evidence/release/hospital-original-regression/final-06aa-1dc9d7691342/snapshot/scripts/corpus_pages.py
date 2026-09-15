"""Read-only native IWA inventory and text extraction for historical Pages files.

No claim that recovered text covers tables, equations or all graphical objects.
All archive/message payloads are retained, with exact offsets and hashes. Wire
format references are recorded in the output; originals are never modified.
"""
from pathlib import Path
import argparse
from collections import Counter
import hashlib
import json
import zipfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"evidence/math/pages"


def sha(data):return hashlib.sha256(data).hexdigest()


def varint(data,offset):
    value=0
    for shift in range(0,70,7):
        if offset>=len(data):raise ValueError("Truncated varint")
        b=data[offset];offset+=1
        value|=(b&127)<<shift
        if b<128:return value,offset
    raise ValueError("Oversized varint")


def fields(data):
    result=[];offset=0
    while offset<len(data):
        start=offset
        key,offset=varint(data,offset)
        number,wire=key>>3,key&7
        if number==0:raise ValueError("Zero field")
        if wire==0:value,offset=varint(data,offset)
        elif wire in (1,5):
            count=8 if wire==1 else 4
            value=data[offset:offset+count];offset+=count
        elif wire==2:
            count,offset=varint(data,offset)
            value=data[offset:offset+count];offset+=count
        else:raise ValueError("Unsupported protobuf group/wire")
        if offset>len(data):raise ValueError("Truncated field")
        result.append((number,wire,value,start,offset))
    return result


def one(parsed,number,default=None):
    found=[v for n,w,v,s,e in parsed if n==number]
    if len(found)>1:raise ValueError("Ambiguous singular field")
    return found[0] if found else default


def snappy(data):
    size,pos=varint(data,0)
    if size>128*1024*1024:raise ValueError("Oversized decoded block")
    output=bytearray()
    while pos<len(data):
        tag=data[pos];pos+=1
        kind=tag&3
        if kind==0:
            count=tag>>2
            if count<60:count+=1
            else:
                width=count-59
                if pos+width>len(data):raise ValueError("Truncated literal size")
                count=int.from_bytes(data[pos:pos+width],"little")+1;pos+=width
            if pos+count>len(data):raise ValueError("Truncated literal")
            output.extend(data[pos:pos+count]);pos+=count
        else:
            width={1:1,2:2,3:4}[kind]
            if pos+width>len(data):raise ValueError("Truncated copy")
            offset=int.from_bytes(data[pos:pos+width],"little");pos+=width
            count=(4+((tag>>2)&7)) if kind==1 else 1+(tag>>2)
            if kind==1:offset|=(tag>>5)<<8
            if not 1<=offset<=len(output):raise ValueError("Invalid copy distance")
            for _ in range(count):output.append(output[-offset])
        if len(output)>size:raise ValueError("Decoded length overflow")
    if len(output)!=size:raise ValueError("Decoded length mismatch")
    return bytes(output)


def unframe(data):
    decoded=bytearray();pos=0;frames=[]
    while pos<len(data):
        start=pos
        if pos+4>len(data):raise ValueError("Truncated frame")
        kind=data[pos]
        count=int.from_bytes(data[pos+1:pos+4],"little");pos+=4
        if kind!=0:raise ValueError("Unrecognized IWA frame")
        if pos+count>len(data):raise ValueError("Truncated compressed block")
        block=snappy(data[pos:pos+count]);pos+=count
        frames.append({"compressed_offset":start,"compressed_length":count+4,
            "decoded_offset":len(decoded),"decoded_length":len(block),"decoded_sha256":sha(block)})
        decoded.extend(block)
    return bytes(decoded),frames


def extract(path):
    dest=OUT/path.stem;dest.mkdir(parents=True,exist_ok=True)
    members=[];messages=[];storages=[];failures=[]
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if not name.endswith(".iwa"):continue
            raw=z.read(name)
            try:
                decoded,frames=unframe(raw)
                basename=name.replace("/","__")
                (dest/(basename+".bin")).write_bytes(decoded)
                members.append({"member":name,"compressed_sha256":sha(raw),"decoded_sha256":sha(decoded),"frames":frames})
                pos=0
                while pos<len(decoded):
                    start=pos
                    hlen,pos=varint(decoded,pos)
                    header=fields(decoded[pos:pos+hlen]);pos+=hlen
                    ident=one(header,1)
                    for n,w,value,s,e in header:
                        if n!=2:continue
                        info=fields(value)
                        kind,length=one(info,1),one(info,3)
                        if not isinstance(length,int) or pos+length>len(decoded):raise ValueError("Bad IWA payload length")
                        payload=decoded[pos:pos+length]
                        record={"member":name,"archive_offset":start,"payload_offset":pos,"payload_length":length,
                            "object_id":ident,"message_type":kind,"sha256":sha(payload)}
                        messages.append(record)
                        if kind==2001:
                            storage=fields(payload)
                            pieces=[v.decode("utf8") for n,w,v,s,e in storage if n==3 and w==2]
                            text="".join(pieces)
                            if text:
                                storages.append({**record,"storage_kind":one(storage,1,3),"text":text,
                                    "text_sha256":sha(text.encode()),"field3_piece_lengths":[len(v) for v in pieces],
                                    "attachment_object_table_hex":[v.hex() for n,w,v,s,e in storage if n==9]})
                        pos+=length
            except (ValueError,UnicodeDecodeError) as exc:
                failures.append({"member":name,"error":str(exc)})
    (dest/"text-storages.jsonl").write_text("".join(json.dumps(r,ensure_ascii=False)+"\n" for r in storages),encoding="utf8")
    report={"source":str(path),"source_sha256":sha(path.read_bytes()),"originals_modified":False,
        "schema":"oma.historical.pages/1","decoding_failures":failures,"members":members,"messages":messages,
        "message_type_counts":dict(Counter(r["message_type"] for r in messages)),
        "text_storage_count":len(storages),"text_characters":sum(len(r["text"]) for r in storages),
        "storage_kind_counts":dict(Counter(r["storage_kind"] for r in storages)),
        "review_status":"EXTRACTED_NOT_READ","equation_and_table_completeness":"UNRESOLVED",
        "format_references":["https://raw.githubusercontent.com/google/snappy/main/format_description.txt",
            "https://oss.sheetjs.com/notes/iwa/","https://raw.githubusercontent.com/isoparametric/python-pages/main/schema/TSWP_partial.proto",
            "https://raw.githubusercontent.com/isoparametric/python-pages/main/schema/TSPArchiveInfo.proto"]}
    (dest/"inventory.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf8")
    print(json.dumps({k:v for k,v in report.items() if k not in ("members","messages")},ensure_ascii=False))


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source",nargs="?")
    args=parser.parse_args()
    for source in [Path(args.source)] if args.source else sorted((ROOT/"math1/math1").glob("*.pages")):
        extract(source)
