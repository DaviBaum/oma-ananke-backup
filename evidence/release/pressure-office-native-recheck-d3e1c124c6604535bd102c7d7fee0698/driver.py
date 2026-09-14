"""Fresh current-source recheck of saved pressure Office bytes; no regeneration."""
from pathlib import Path
import json
import os
import shutil
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from native_prepare import DEST, sha, json_write
from native_build import run

SOURCE = 'bac10b7f20d44219f13fe5df2a70600f22b4fe69a4021dbe0e8e2172f76743ac'
PRIOR = 'oma-independent-checker/2:b61a7a9f20f0f5dccc7f4f69207037e36110e895fdd3835f232d4f3f62d6d895'
ORIGINAL = ROOT / '.oma/development/two-sink-pressure/bench-stores/b44b3123cdb641709b2aa32ae5bd526c'
CANDIDATE = 'cde5e507fca2488d9a957364f6d5a763'
EXPORT_SHA = 'c116e3cf909e97719a613888043ca2b214aba538575e17f79dd3639bb5a12e58'


def main():
    script = ROOT / 'scripts/native_real_model_validation.py'
    script_sha = sha(script)
    shutil.copyfile(script, HERE / script.name)
    manifest_path = ORIGINAL / 'exports/315e5dacd14b4fa8be1687b7b2ee67d0/manifest.json'
    manifest = json.loads(manifest_path.read_text())
    assert manifest['checking']['exported_candidate_id'] == CANDIDATE
    assert manifest['status'] == 'CHECKED_LOCAL_SCOPE' and manifest['round_trip'] == 'PASS'
    assert len(manifest['files']) == 1 and manifest['files'][0]['sha256'] == EXPORT_SHA
    assert sha(Path(manifest['files'][0]['path'])) == EXPORT_SHA
    directory = DEST / 'real-model-validation' / HERE.name.rsplit('-', 1)[-1]
    environment = os.environ.copy()
    environment.update(PYTHONPATH=str(ROOT / '.oma/runtimes' / SOURCE / 'src'),
        OMA_EXECUTABLE_BUILD='oma-independent-checker/2:' + SOURCE,
        PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1')
    environment.pop('OMA_CONTROL_RUN_ID', None)
    result = {'status': 'RUNNING', 'source_checkpoint': SOURCE, 'prior_checker_version': PRIOR,
        'candidate_id': CANDIDATE, 'expected_export_sha256': EXPORT_SHA,
        'original_store': str(ORIGINAL), 'export_manifest_sha256': sha(manifest_path),
        'script_sha256': script_sha, 'isolated_store': str(directory),
        'scope': 'Existing real Office pressure-network export, same fixed hypothetical boundaries and exact IFC; current native original-wheel recheck, no geometry regeneration'}
    json_write(HERE / 'result.json', result)
    print(json.dumps(result), flush=True)
    started = time.monotonic()
    try:
        command = [sys.executable, script, '--child-directory', directory, '--original-store', ORIGINAL,
            '--candidate-id', CANDIDATE, '--source-checkpoint', SOURCE,
            '--expected-export-sha256', EXPORT_SHA, '--prior-checker-version', PRIOR]
        record = run('saved-office-pressure-native-recheck', command, cwd=ROOT, env=environment, budget=1200)
        actual = json.loads((directory / 'real-model-result.json').read_text())
        assert actual['status'] == 'REAL_EXPORTED_OFFICE_RECHECK_PASS'
        assert actual['checker_version'] == environment['OMA_EXECUTABLE_BUILD']
        assert actual['prior_checker_version'] == PRIOR and actual['physical_kind'] == 'physical_network'
        native = actual['network_evidence']
        assert native['physical_components'] == 4 and native['physical_ports'] == 9
        assert native['original_obstacles'] == 803 and native['source_pairs'] == 3212 and native['component_pairs'] == 6
        assert native['component_velocity_count'] == 9 and len(native['deliveries']) == 2
        assert actual['original_candidate_and_run_unchanged'] and actual['original_bytes_and_head_unchanged']
        assert sha(script) == script_sha and sha(manifest_path) == result['export_manifest_sha256']
        for filename in ('real-model-result.json', 'validation-input-copy.json', 'prior-semantics.json', 'prior-cad.json',
                         'prior-pressure.json', 'current-semantics.json', 'current-cad.json', 'current-pressure.json'):
            shutil.copyfile(directory / filename, HERE / filename)
        result.update(status='PASS', validation=actual, command_record=str(record / 'record.json'))
    except BaseException as exc:
        result.update(status='INCOMPLETE_OR_FAILED', error=repr(exc))
        raise
    finally:
        result['seconds'] = time.monotonic() - started
        json_write(HERE / 'result.json', result)
        print(json.dumps({k:result.get(k) for k in ('status', 'seconds', 'error', 'command_record')}), flush=True)


if __name__ == '__main__':
    main()
