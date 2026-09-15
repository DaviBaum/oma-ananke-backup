"""Prepare exact forced-recovery review bytes; no execution or live changes."""
from pathlib import Path
import ast
import hashlib
import json
import shutil

HERE = Path(__file__).resolve().parent
ROOT = next(p for p in HERE.parents if (p / 'AGENTS.md').is_file())
EVIDENCE = ROOT / 'evidence/release/validated-backend-hospital-update/19be511c32ca447da2c213f0ce377940/forced-recovery-preparation'

def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def write(p, value):
    p.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')

guards = [HERE / 'second_interrupt_owned.py', *[HERE / 'prepared' / name for name in ('store_inventory.py', 'reachable_inventory.py', 'validation_gate.py')]]
scripts = [HERE / 'recover_owned_idle.py', HERE / 'prepared/shutdown_guard.py', HERE / 'prepared/verify_after.py', *guards]
for path in scripts:
    ast.parse(path.read_text(encoding='utf-8-sig'), filename=str(path))
    shutil.copyfile(path, EVIDENCE / ('prepared-' + path.name))
shutil.copyfile(HERE / 'prepared/start.ps1', EVIDENCE / 'prepared-start.ps1')
review = {'status': 'FORCED_OWNED_IDLE_RECOVERY_PREPARATION_REVIEWED_NO_EXECUTION',
          'recovery_script_sha256': sha(HERE / 'recover_owned_idle.py'),
          'guard_files': {str(p): sha(p) for p in guards},
          'scope': 'Only two exact prior idle process identities after both bounded interrupt attempts failed. The server is terminated through a retained Win32 process handle with verified creation FILETIME/image plus freshly verified command/environment/parent/children. The launcher is terminated only if its retained handle remains unsignalled after15 seconds and its identity and remaining children are freshly rechecked. No tree-wide termination or process discovery cleanup.',
          'store_protection': 'Completed06aa full/outcome gates, exact preflight metadata, complete14-table/file/reachable snapshot and SQLite quick_check before/after. Consistent preflight SQLite backup hash retained. No automatic Store repair/restore.',
          'status_on_success': 'FORCED_OWNED_IDLE_PROCESS_RECOVERY_COMPLETED', 'force_termination': True,
          'graceful_application_lifespan_completed': False, 'root_execution_required': True,
          'signals_or_terminations_executed_by_preparation': 0, 'active_runtime_source_changes': False}
write(HERE / 'forced-recovery-review.json', review)
shutil.copyfile(HERE / 'forced-recovery-review.json', EVIDENCE / 'review.json')
shutil.copyfile(__file__, EVIDENCE / 'executed-prepare-review.py')
write(EVIDENCE / 'handoff.json', {'status': review['status'], 'retained_files': {p.name: sha(p) for p in EVIDENCE.iterdir() if p.is_file() and p.name != 'handoff.json'}})
print(json.dumps({'script_sha256': review['recovery_script_sha256'], 'handoff': str(EVIDENCE / 'handoff.json'), 'handoff_sha256': sha(EVIDENCE / 'handoff.json')}))
