"""Retain installed-code review and syntax checks; no signal or runtime mutation."""
from pathlib import Path
import ast
import asyncio.runners
import hashlib
import inspect
import json
import shutil
import uvicorn.server

HERE = Path(__file__).resolve().parent
ROOT = next(p for p in HERE.parents if (p / 'AGENTS.md').is_file())
EVIDENCE = ROOT / 'evidence/release/validated-backend-hospital-update/19be511c32ca447da2c213f0ce377940/shutdown-adaptation'

def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def write(p, value):
    p.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')

meta = json.loads((ROOT / '.oma/service.validated.json').read_text(encoding='utf-8-sig'))
source = Path(meta['pythonpath'])
dependencies = [Path(inspect.getfile(uvicorn.server)), Path(inspect.getfile(asyncio.runners)), source / 'oma/api.py', source / 'oma/service.py']
for p in dependencies:
    target = EVIDENCE / ('reviewed-' + p.parent.name + '-' + p.name)
    shutil.copyfile(p, target)
reviewed = {}
for name in ('handle_exit', 'shutdown', '_wait_tasks_to_complete', 'capture_signals', '_serve'):
    reviewed[name] = inspect.getsource(getattr(uvicorn.server.Server, name))
reviewed['asyncio_runner_close'] = inspect.getsource(asyncio.runners.Runner.close)
write(EVIDENCE / 'installed-control-paths.json', reviewed)
scripts = [HERE / 'second_interrupt_owned.py', HERE / 'prepared/shutdown_guard.py', HERE / 'prepared/verify_after.py']
for p in scripts:
    ast.parse(p.read_text(encoding='utf-8-sig'), filename=str(p))
    shutil.copyfile(p, EVIDENCE / ('prepared-' + p.name))
shutil.copyfile(HERE / 'prepared/start.ps1', EVIDENCE / 'prepared-start.ps1')
review = {'status': 'CONTROLLED_SECOND_INTERRUPT_STATIC_REVIEW_PASS_NO_EXECUTION',
          'reviewed_dependency_files': {str(p): sha(p) for p in dependencies},
          'supplemental_script_sha256': sha(HERE / 'second_interrupt_owned.py'),
          'review': 'Installed Uvicorn sets force_exit on a second SIGINT after should_exit. Connection/task wait loops stop; normal lifespan.shutdown is skipped. asyncio runner subsequently cancels pending tasks. This is a forced connection/task drain, not graceful application lifecycle completion.',
          'applicability': 'Only the exact already-shutting-down idle owned console, released listener, no live run owner/child worker, unchanged completed validation packet and exact complete Store snapshots before/after. One extra CTRL_C only; no process termination API or retries.',
          'result_status': 'OWNED_FORCED_CONNECTION_DRAIN_COMPLETED',
          'active_runtime_modified': False, 'signals_sent_by_this_preparation': 0,
          'syntax_parsed': [str(p) for p in scripts],
          'root_execution_required': True}
write(HERE / 'second-interrupt-review.json', review)
shutil.copyfile(HERE / 'second-interrupt-review.json', EVIDENCE / 'review.json')
shutil.copyfile(__file__, EVIDENCE / 'executed-prepare-review.py')
write(EVIDENCE / 'handoff.json', {'status': review['status'], 'retained_files': {p.name: sha(p) for p in EVIDENCE.iterdir() if p.is_file() and p.name != 'handoff.json'}})
print(json.dumps({'review': str(HERE / 'second-interrupt-review.json'), 'script_sha256': review['supplemental_script_sha256'], 'handoff': str(EVIDENCE / 'handoff.json'), 'handoff_sha256': sha(EVIDENCE / 'handoff.json')}))
