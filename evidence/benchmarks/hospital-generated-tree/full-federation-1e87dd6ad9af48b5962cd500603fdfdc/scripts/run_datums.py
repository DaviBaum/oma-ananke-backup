import os,sys,time,uuid,json,shutil
from pathlib import Path
from oma.export_checks import supervise_check
from oma.ifc.audit import atomic_json,sha256_file
stage=Path(__file__).resolve().parent
out=stage/'datums'/uuid.uuid4().hex;out.mkdir(parents=True)
for path in (Path(__file__),stage/'assess_datums.py'):shutil.copyfile(path,out/path.name)
result=supervise_check([sys.executable,str(stage/'assess_datums.py'),str(out)],environment=dict(os.environ),
    directory=out/'supervision',deadline=time.monotonic()+300,memory_limit_bytes=12*1024**3)
atomic_json(out/'supervision-result.json',result)
print(json.dumps({'output':str(out),'supervision':result['status']}),flush=True)
