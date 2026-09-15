from pathlib import Path
import sqlite3,json,zlib
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').exists())
V=ROOT/'.oma/development/shared-tree-native/validation/f9c75d13b1334319a6d4822e3acc05da'
p=next(V.rglob('oma.sqlite3'));print(p)
d=sqlite3.connect(p.resolve().as_uri()+'?mode=ro',uri=True);d.row_factory=sqlite3.Row
for table in ('candidates','runs'):
    print(table,[{k:v for k,v in dict(r).items() if k not in ('payload','request')} for r in d.execute('select * from '+table)])
print('export-files',[str(f) for f in p.parent.rglob('*.manifest.json')])
for file in (p.parent/'blobs').glob('*.z'):
    value=json.loads(zlib.decompress(file.read_bytes()))
    if isinstance(value,dict) and (value.get('status')=='PROPOSALS_READY' or 'verification_root' in value):
        print('artifact',file.stem,value.keys())
        if value.get('status')=='PROPOSALS_READY':print('generation',value['generation'].keys(),value['synthesis']['counts'],value['generation'].get('counts'))
