from pathlib import Path
import hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[3];STAGE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
target=STAGE/'combined-src';assert not target.exists()
files={p.relative_to(STAGE/'src').as_posix():sha(p) for p in (STAGE/'src').rglob('*.py')}
assert files['oma/ifc/cad.py']=='8089f26991339369b4f433cd5ed7bcc277ca2e55907c4c6aa353aae643ccd073'
expected={'oma/ifc/enclosure.py':'798be75dd170559a39eca6ed5c82237ceed73e5df18e1ffe0410fa60b9f0daf9','oma/ifc/federation.py':'728e152aa57d6e81f8bb5cc6b2316ecfb0cd91f5c565d0c97b591be5567f3612'}
for name,before in files.items():
    source=ROOT/'src'/name if name in expected else STAGE/'src'/name
    assert sha(source)==expected.get(name,before)
    dest=target/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest)
    assert sha(dest)==expected.get(name,before)
(STAGE/'combined-source.json').write_text(json.dumps({'files':{p.relative_to(target).as_posix():sha(p) for p in target.rglob('*.py')},'changed_from_private_cad_snapshot':expected},indent=2),encoding='utf8')
print('Created combined immutable114 source copy with reviewed3file geometry delta')
