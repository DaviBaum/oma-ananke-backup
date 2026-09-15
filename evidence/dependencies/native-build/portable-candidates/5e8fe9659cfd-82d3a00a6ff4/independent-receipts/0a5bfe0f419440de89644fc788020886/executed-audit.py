"""Read-only actual three-role receipt replay; never reconvert native geometry."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
import uuid

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'AGENTS.md').exists())
PACKAGE = ROOT / '.release/native-build/portable-candidates/5e8fe9659cfd-82d3a00a6ff4'
EVIDENCE = ROOT / 'evidence/dependencies/native-build/portable-candidates/5e8fe9659cfd-82d3a00a6ff4'
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    started = time.monotonic()
    out = EVIDENCE / 'independent-receipts' / uuid.uuid4().hex
    out.mkdir(parents=True)
    shutil.copy2(__file__, out / 'executed-audit.py')
    scripts = out / 'scripts'
    scripts.mkdir()
    for name in ('native_package_evidence.py', 'native_real_model_validation.py', 'native_build.py', 'native_prepare.py'):
        shutil.copy2(ROOT / 'scripts' / name, scripts / name)
    sys.path.insert(0, str(scripts))
    from native_package_evidence import verify_real_model_receipt, REAL_MODEL_ROLES
    result_path = EVIDENCE / 'result.json'
    portable = json.loads(result_path.read_text())
    receipts = {role: json.loads((EVIDENCE / names[0]).read_text()) for role, names in REAL_MODEL_ROLES.items()}
    before = {str(p): sha(p) for p in [result_path, *[EVIDENCE / names[0] for names in REAL_MODEL_ROLES.values()], *scripts.glob('*.py')]}
    output = {'scope': 'Read-only managed receipts and bounded mathematical replay; no CAD rerun, payload-wide hash, suite or seal claim',
              'package': str(PACKAGE), 'interpreter': sys.executable, 'inputs': before, 'roles': {}}
    for role, receipt in receipts.items():
        summary = verify_real_model_receipt(PACKAGE, portable, result_path, role, receipt)
        output['roles'][role] = {'status': 'PASS', 'report_root': receipt['report_root'], 'candidate_root': receipt['candidate_root'], 'evidence': summary}
    forged = copy.deepcopy(portable)
    key = 'oma/routing/coupled_tree_pressure.py'
    assert key in forged['source_python_files']
    forged['source_python_files'][key] = '0' * 64
    try:
        verify_real_model_receipt(PACKAGE, forged, result_path, 'coupled_pressure_network', receipts['coupled_pressure_network'])
    except AssertionError as exc:
        assert 'Replay source differs' in str(exc)
        output['source_map_mutation'] = {'status': 'REJECTED', 'field': key, 'reason': str(exc), 'package_files_modified': False}
    else:
        raise AssertionError('Altered source-map identity was accepted')
    loaded = {n: {'path': str(Path(m.__file__).resolve()), 'sha256': sha(m.__file__)} for n, m in sys.modules.copy().items()
              if (n == 'oma' or n.startswith('oma.')) and getattr(m, '__file__', None)}
    assert all(Path(row['path']).is_relative_to(PACKAGE / 'src') for row in loaded.values())
    assert before == {p: sha(p) for p in before}
    output.update(status='PASS', elapsed_seconds=time.monotonic()-started, loaded_app_sources=loaded, inputs_unchanged=True)
    (out / 'result.json').write_text(json.dumps(output, indent=2)+'\n')
    (out / 'README.md').write_text('All three actual bundled Office receipts replayed successfully against their read-only isolated Store and exact declared source/export bytes. The coupled role additionally independently rebuilt its local/global mathematical proof and complete service inventory using the package source. An in-memory source-map mismatch was rejected; package bytes were never edited. Full bundled-suite completion and final seal/index audit remain separate.\n')
    print(json.dumps({'status': 'PASS', 'evidence': str(out), 'elapsed_seconds': output['elapsed_seconds']}))

if __name__ == '__main__':
    main()
