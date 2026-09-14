"""Retain the new residual proof and freshly regenerated native correspondence."""
from pathlib import Path
import json
import os
import subprocess
import sys
import uuid

STAGE=Path(__file__).resolve().parents[1]
if __name__=='__main__':
    if '--worker' not in sys.argv:
        sys.path.insert(0,str(STAGE/'src'))
        from oma.build_identity import frozen_environment
        env=frozen_environment(STAGE/'evidence'/'native-builds')
        raise SystemExit(subprocess.call([sys.executable,str(Path(__file__).resolve()),'--worker'],env=env))
    sys.path.insert(0,str(STAGE/'tests'))
    from test_optimization_fabrication_alternatives import native_residual_wall_case
    from oma.ifc.audit import sha256_file
    directory=STAGE/'evidence'/'native-residual'/uuid.uuid4().hex
    result=native_residual_wall_case(directory)
    receipt={'schema':'oma.residual-fabrication-native-receipt/1','status':result['status'],
        'build':result['checker_version'],'directory':directory.relative_to(STAGE).as_posix(),
        'script_sha256':sha256_file(__file__),
        'test_sha256':sha256_file(STAGE/'tests/test_optimization_fabrication_alternatives.py'),
        'kernel_sha256':sha256_file(STAGE/'src/oma/optimization/fabrication_alternatives.py'),
        'result_sha256':sha256_file(directory/'result.json'),
        'source_pairs':result['native_source_check']['pairs_accounted'],
        'current_cross_pairs':len(result['complete_current_cross_route_pairs']),
        'original_source_unchanged':True,'full_joint_acceptance_executed':False}
    (directory/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')
    (STAGE/'evidence/native-residual-latest.json').write_text(json.dumps(receipt,indent=2),encoding='utf8')
    print(json.dumps(receipt,indent=2))
