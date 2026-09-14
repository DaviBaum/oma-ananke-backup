"""Read-only comparison of the new package's six pre-existing UI assets."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
output = Path(__file__).resolve().parent
portable_path = output / 'result.json'
portable = json.loads(portable_path.read_text())
reference = json.loads((ROOT / 'evidence/release/pressure-packaging-inputs/ui-reference.json').read_text())
package = Path(portable['package'])
def files(directory):
    return {p.relative_to(directory).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in directory.rglob('*') if p.is_file()}
assert files(package / 'ui/dist') == files(Path(reference['reference_directory'])) == reference['files']
assert files(ROOT / 'ui/dist') == reference['files']
assert len(reference['files']) == 6
result = {'status': 'SIX_PREEXISTING_UI_ASSETS_BYTE_IDENTICAL', 'package': str(package),
          'portable_validation_result_sha256': hashlib.sha256(portable_path.read_bytes()).hexdigest(),
          'reference_directory': reference['reference_directory'], 'files': reference['files'],
          'ui_build_performed': False}
(output / 'ui-byte-equivalence.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({'status': result['status'], 'files': len(result['files'])}))
