"""Pin reread original source paragraphs and current reusable implementation lines."""
from pathlib import Path
import hashlib
import json
import sys
import zipfile
import xml.etree.ElementTree as ET

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'scripts/corpus_audit.py').is_file())
STAGE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from corpus_audit import paragraph_text, NS
source=ROOT/'math1/math1/the 5 things that combine ceiling router with ananke.docx'
sha=hashlib.sha256(source.read_bytes()).hexdigest()
assert sha=='72379f535f744b15ccbdcbbb6f68904f6c1177ace27a8fcc028229039b8bd129'
with zipfile.ZipFile(source) as archive:
    raw=archive.read('word/document.xml')
paragraphs=ET.fromstring(raw).findall('.//w:p',NS)
locations=[4472,4473,4474,4475,4476,4477,4478,4479,4480,4481,4482,4483,4484,5514,5515,5520,5521,5522,5523,5524,5525,5536,5537,5544,5545,5546,5547,5548,5549,5550,5551,5552,5553,5568,5569]
extracted={r['location']:r for r in map(json.loads,(ROOT/'evidence/math/extracted/oma-integration.jsonl').read_text(encoding='utf8').splitlines())}
records=[]
for n in locations:
    text=paragraph_text(paragraphs[n-1])
    assert text==extracted[n]['text']
    records.append({'locator':f'word/document.xml::p[{n}]','text':text,'text_sha256':hashlib.sha256(text.encode()).hexdigest()})
paths=['src/oma/optimization/fabrication_frontier.py','src/oma/optimization/fabrication_search.py',
       'src/oma/routing/certified_fabrication.py','src/oma/routing/proposals.py','src/oma/routing/joint.py']
code=[]
for relative in paths:
    path=ROOT/relative
    text=path.read_text(encoding='utf8')
    code.append({'path':relative,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'functions':[{'line':i,'signature':line} for i,line in enumerate(text.splitlines(),1) if line.startswith('def ')]})
result={'schema':'oma.next-best-fabrication-design-source-basis/1','original_modified':False,
    'original_path':source.relative_to(ROOT).as_posix(),'original_sha256':sha,
    'document_xml_sha256':hashlib.sha256(raw).hexdigest(),'paragraphs':records,
    'code_review':code,'full_source_algorithm_implemented':False,
    'specialization':'Whole finite graph-word terminal exclusions via a prefix-trie product; proposed new bounded construction, not source-prescribed code.'}
(STAGE/'evidence/source-basis.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf8')
print(json.dumps({'source_sha256':sha,'paragraphs':len(records),'files':len(code)},indent=2))
