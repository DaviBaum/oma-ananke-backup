from pathlib import Path
import hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[3];STAGE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
files={p.relative_to(ROOT/'src').as_posix():sha(p) for p in (ROOT/'src').rglob('*.py')}
assert len(files)==114
for folder in ('base-src','src'):
    target=STAGE/folder;target.mkdir(exist_ok=False)
    for name,h in files.items():
        out=target/name;out.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/'src'/name,out);assert sha(out)==h
assert files=={p.relative_to(ROOT/'src').as_posix():sha(p) for p in (ROOT/'src').rglob('*.py')}
(STAGE/'source-preparation.json').write_text(json.dumps({'status':'PRIVATE_SOURCE_COPY','source_checkpoint':'f73a8793ae0df76d9ec53400cec18b05d2731f63c735b225c2246fee62df6b21','files':files},indent=2),encoding='utf8')
print('Copied immutable 114-source baseline and private candidate')
