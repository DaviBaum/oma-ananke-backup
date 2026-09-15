"""Accept only an exactly retained and reviewed owned shutdown disposition."""
from pathlib import Path
import hashlib
import json
import shutil
import psutil
import store_inventory

HERE = Path(__file__).resolve().parent

def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))

def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def check_shutdown(directory, *, recheck_store=False):
    directory = Path(directory)
    result = read(directory / 'shutdown-complete.json')
    preflight = read(directory / 'preflight.json')
    for record in (preflight['server'], preflight['launcher']):
        try:
            assert psutil.Process(record['pid']).create_time() != record['created'], 'Old owned process still alive'
        except psutil.NoSuchProcess:
            pass
    assert result['port_released'] is True
    log = (directory / 'closed-old-backend.stderr.log').read_text(encoding='utf-8-sig')
    if result['status'] == 'GRACEFUL_OWNED_SHUTDOWN_COMPLETED':
        assert result['force_termination'] is False
        assert f"Finished server process [{preflight['server']['pid']}]" in log
        assert 'Application shutdown complete.' in log
        disposition = {'status': result['status'], 'graceful_application_lifespan_completed': True, 'second_ctrl_c': False, 'force_termination': False}
    elif result['status'] == 'OWNED_FORCED_CONNECTION_DRAIN_COMPLETED':
        assert result['force_termination'] is False
        assert f"Finished server process [{preflight['server']['pid']}]" in log
        assert result['owned_processes_gone'] is True and result['store_before_after_exact'] is True
        assert result['second_ctrl_c'] is True and result['graceful_application_lifespan_completed'] is False
        attempt = directory / 'second-interrupt'
        assert read(attempt / 'result.json') == result
        manifest = read(attempt / 'handoff.json')
        assert manifest['status'] == result['status']
        assert {p.name: sha(p) for p in attempt.iterdir() if p.is_file() and p.name != 'handoff.json'} == manifest['retained_files']
        review_path = HERE.parent / 'second-interrupt-review.json'
        review = read(review_path)
        assert sha(attempt / 'review.json') == sha(review_path)
        assert sha(attempt / 'executed-second-interrupt.py') == review['supplemental_script_sha256']
        assert sha(attempt / 'request.json') == result['request_sha256']
        request = read(attempt / 'request.json')
        assert request['status'] == 'VERIFIED_OWNED_SECOND_CTRL_C_REQUESTED' and request['signal'] == 'CTRL_C_EVENT'
        assert request['launcher'] == preflight['launcher'] and request['server'] == preflight['server']
        assert request['first_request_sha256'] == sha(directory / 'shutdown-request.json')
        assert result['before_snapshot_sha256'] == sha(directory / 'before-all-store.json')
        assert sha(attempt / 'after-stderr.log') == sha(directory / 'closed-old-backend.stderr.log')
        assert sha(attempt / 'after-stdout.log') == sha(directory / 'closed-old-backend.stdout.log')
        disposition = {k: result[k] for k in ('status', 'force_termination', 'graceful_application_lifespan_completed', 'second_ctrl_c', 'normal_lifespan_shutdown_claim', 'disposition')}
        disposition['supplemental_handoff_sha256'] = sha(attempt / 'handoff.json')
    else:
        assert result['status'] == 'FORCED_OWNED_IDLE_PROCESS_RECOVERY_COMPLETED'
        assert result['force_termination'] is True and result['graceful_application_lifespan_completed'] is False
        assert result['owned_processes_gone'] is True and result['store_before_after_exact'] is True
        assert result['server_terminated'] is True and type(result['launcher_terminated']) is bool
        assert result['sqlite_quick_check_before'] == result['sqlite_quick_check_after'] == ['ok']
        attempt = directory / 'forced-process-recovery'
        assert read(attempt / 'result.json') == result
        manifest = read(attempt / 'handoff.json')
        assert manifest['status'] == result['status']
        assert {p.name: sha(p) for p in attempt.iterdir() if p.is_file() and p.name != 'handoff.json'} == manifest['retained_files']
        review_path = HERE.parent / 'forced-recovery-review.json'
        review = read(review_path)
        assert sha(attempt / 'review.json') == sha(review_path)
        assert sha(attempt / 'executed-recovery.py') == review['recovery_script_sha256']
        assert sha(attempt / 'request.json') == result['request_sha256']
        request = read(attempt / 'request.json')
        assert request['status'] == 'VERIFIED_OWNED_IDLE_PROCESS_RECOVERY_REQUESTED'
        assert request['first_request_sha256'] == sha(directory / 'shutdown-request.json')
        assert request['second_request_sha256'] == sha(directory / 'second-interrupt/request.json')
        assert request['failed_second_wait_sha256'] == sha(directory / 'second-interrupt/wait-result.json')
        for label in ('server', 'launcher'):
            assert request['identities'][label]['pid'] == preflight[label]['pid']
            assert request['identities'][label]['cmdline'] == preflight[label]['cmdline']
            assert Path(request['identities'][label]['image']).resolve() == Path(preflight[label]['exe']).resolve()
            assert abs((request['identities'][label]['creation_filetime'] - 116444736000000000) / 10000000 - preflight[label]['created']) < .00001
        assert result['before_snapshot_sha256'] == sha(directory / 'before-all-store.json')
        assert result['consistent_preflight_backup_sha256'] == sha(directory / 'before-store.sqlite3')
        process_exit = read(attempt / 'process-exit.json')
        assert process_exit['server_handle_signalled'] is True and process_exit['launcher_handle_signalled'] is True
        assert process_exit['server_terminated'] is True and process_exit['launcher_terminated'] == result['launcher_terminated']
        assert sha(attempt / 'after-stderr.log') == sha(directory / 'closed-old-backend.stderr.log')
        assert sha(attempt / 'after-stdout.log') == sha(directory / 'closed-old-backend.stdout.log')
        disposition = {k: result[k] for k in ('status', 'force_termination', 'graceful_application_lifespan_completed', 'second_ctrl_c', 'normal_lifespan_shutdown_claim', 'disposition')}
        disposition['supplemental_handoff_sha256'] = sha(attempt / 'handoff.json')
    if recheck_store:
        assert store_inventory.snapshot() == read(directory / 'before-all-store.json'), 'Store changed before restarting'
        if result['force_termination']:
            import sqlite3
            with sqlite3.connect((store_inventory.DATA / 'oma.sqlite3').as_uri() + '?mode=ro', uri=True) as db:
                assert list(db.execute('PRAGMA quick_check')) == [('ok',)]
    shutil.copyfile(__file__, directory / 'handover-supplement-shutdown_guard.py')
    return disposition
