"""Freeze the unchanged 33a application and a narrow prerequisite-order delta."""
from pathlib import Path
import hashlib,json,shutil,difflib

STAGE=Path(__file__).resolve().parent
ROOT=next(p for p in STAGE.parents if (p/'AGENTS.md').exists())
BASE=ROOT/'.oma/validated-runtimes/33a20d125bba-c304a60d38e9/src'
TARGET=STAGE/'src'
assert not TARGET.exists()
before={p.relative_to(BASE).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in BASE.rglob('*.py')}
assert len(before)==112
for rel in before:
    p=TARGET/rel;p.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(BASE/rel,p)
cad=TARGET/'oma/ifc/cad.py';old=cad.read_text(encoding='utf8')
line='    valid = BRepCheck_Analyzer(shape, True).IsValid()\n'
assert old.count(line)==1
new=old.replace(line,'')
anchor='        return bounds, 0., 0., False, "PARTIALLY_NON_SOLID_TOPOLOGY"\n'
assert new.count(anchor)==1
new=new.replace(anchor,anchor+'    # Shapes lacking complete solid topology already have an unconditional\n'
    '    # rejection above. Only candidates with that prerequisite need the\n'
    '    # expensive geometric validity analysis; successful solids still do.\n'+line)
cad.write_text(new,encoding='utf8',newline='\n')
(STAGE/'cad-prerequisite-order.patch').write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='33a/oma/ifc/cad.py',tofile='private/oma/ifc/cad.py')),encoding='utf8')
after={p.relative_to(TARGET).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in TARGET.rglob('*.py')}
assert [rel for rel in before if before[rel]!=after[rel]]==['oma/ifc/cad.py']
(STAGE/'source-declaration.json').write_text(json.dumps({'base_source':str(BASE),'private_source':str(TARGET),'base_files':before,'private_files':after,
    'change':'BRepCheck_Analyzer runs only after existing no-solid and full-solid-topology prerequisite failures. No source enumeration, promotion, enclosure, Boolean, tolerance, or successful-solid validity predicates changed.'},indent=2),encoding='utf8')
print(json.dumps({'files':len(after),'changed':['oma/ifc/cad.py'],'cad_sha256':after['oma/ifc/cad.py']},indent=2))
