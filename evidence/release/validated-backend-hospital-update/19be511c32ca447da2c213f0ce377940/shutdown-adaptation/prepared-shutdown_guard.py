"""Accept only a verified graceful stop or the specifically reviewed second SIGINT."""
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
    assert result['port_released'] is True and result['force_termination'] is False
    log = (directory / 'closed-old-backend.stderr.log').read_text(encoding='utf-8-sig')
    assert f"Finished server process [{preflight['server']['pid']}]" in log
    if result['status'] == 'GRACEFUL_OWNED_SHUTDOWN_COMPLETED':
        assert 'Application shutdown complete.' in log
        disposition = {'status': result['status'], 'graceful_application_lifespan_completed': True, 'second_ctrl_c': False}
    else:
        assert result['status'] == 'OWNED_FORCED_CONNECTION_DRAIN_COMPLETED'
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
        disposition = {k: result[k] for k in ('status', 'graceful_application_lifespan_completed', 'second_ctrl_c', 'normal_lifespan_shutdown_claim', 'disposition')}
        disposition['supplemental_handoff_sha256'] = sha(attempt / 'handoff.json')
    if recheck_store:
        assert store_inventory.snapshot() == read(directory / 'before-all-store.json'), 'Store changed before restarting'
    shutil.copyfile(__file__, directory / 'handover-supplement-shutdown_guard.py')
    return disposition
