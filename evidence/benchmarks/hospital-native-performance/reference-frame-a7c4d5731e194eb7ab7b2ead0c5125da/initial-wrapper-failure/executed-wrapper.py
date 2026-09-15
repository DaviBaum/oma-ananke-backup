from pathlib import Path
import json,os,time,sys
ROOT=Path(__file__).resolve().parents[3];STAGE=Path(__file__).resolve().parent
FROZEN=ROOT/'.oma/development/factorized-tree-pressure/runtimes/f73a8793ae0df76d9ec53400cec18b05d2731f63c735b225c2246fee62df6b21/src'
sys.path.insert(0,str(FROZEN))
from oma.export_checks import supervise_check
env=dict(os.environ,PYTHONPATH=str(FROZEN))
result=supervise_check([str(ROOT/'.venv/Scripts/python.exe'),str(STAGE/'profile.py')],environment=env,
    directory=STAGE/'supervision',deadline=time.monotonic()+180,memory_limit_bytes=12*1024**3)
print(json.dumps(result))
