"""Verify public retention only; no application/native imports or original-path reads."""
from pathlib import Path
import argparse
import hashlib
import json

MATH = Path(__file__).resolve().parent
OFFICE = MATH.parent.parent / 'benchmarks' / 'shared-tree-generation-office'
ROOTS = {'math': MATH, 'office': OFFICE}
PREFIXES = {'evidence/math/shared-tree-native-independent/': MATH,
            'evidence/benchmarks/shared-tree-generation-office/': OFFICE}
EXCLUDED = {'files-index.json', 'handoff.json', 'verification-result.json'}

def read(path):
    return json.loads(path.read_text(encoding='utf8'))

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def write_new(path, obj):
    assert not path.exists(), f'Refusing to overwrite {path}'
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n', encoding='utf8')

def local(root, relative):
    path = (root / relative).resolve()
    assert path.is_relative_to(root.resolve()) and not path.is_symlink(), relative
    return path

def mapped(relative):
    for prefix, root in PREFIXES.items():
        if relative.startswith(prefix):
            return local(root, relative[len(prefix):])
    raise AssertionError(f'Unrecognized public mapping: {relative}')

def index_rows(root):
    return [{'path': p.relative_to(root).as_posix(), 'bytes': p.stat().st_size,
             'sha256': digest(p)} for p in sorted(root.rglob('*'))
            if p.is_file() and p.relative_to(root).as_posix() not in EXCLUDED]

def run(finalize=False):
    if finalize:
        for root in ROOTS.values():
            rows = index_rows(root)
            write_new(root / 'files-index.json', {
                'schema': 'oma.public-evidence-exact-index/1',
                'excluded_root_files': sorted(EXCLUDED),
                'file_count': len(rows), 'bytes': sum(r['bytes'] for r in rows), 'files': rows})
    summaries = {}
    for name, root in ROOTS.items():
        index = read(root / 'files-index.json')
        assert index['excluded_root_files'] == sorted(EXCLUDED)
        rows = index_rows(root)
        assert rows == index['files'], f'Exact indexed bytes/file set changed: {name}'
        assert index['file_count'] == len(rows)
        assert index['bytes'] == sum(r['bytes'] for r in rows)
        summaries[name] = {'indexed_file_count': len(rows), 'indexed_bytes': index['bytes'],
                           'index_sha256': digest(root / 'files-index.json')}
    mapping = read(MATH / 'public-mapping.json')
    originals = {}
    for row in mapping['files']:
        path = mapped(row['public_path'])
        assert path.stat().st_size == row['bytes'] and digest(path) == row['sha256'], path
        originals.setdefault(row['original_path'], []).append(row)
    manifests = []
    for record in mapping['declared_inventory_rechecks']:
        candidates = originals[record['original_manifest']]
        for mapped_row in candidates:
            manifest = mapped(mapped_row['public_path'])
            assert digest(manifest) == record['sha256']
            rows = read(manifest)['files']
            if isinstance(rows, dict):
                rows = [{'path': p, **r} for p, r in rows.items()]
            names = [r['path'] for r in rows]
            assert len(names) == len(set(names)) == record['declared_file_count']
            total = 0
            for row in rows:
                path = local(manifest.parent, row['path'])
                size = row.get('size_bytes', row.get('bytes'))
                assert path.stat().st_size == size and digest(path) == row['sha256'], path
                total += size
            assert total == record['declared_bytes']
        manifests.append({'public_path': candidates[0]['public_path'],
                          'sha256': record['sha256'], 'declared_files': len(rows)})
    office_mapping = read(OFFICE / 'public-mapping.json')
    assert office_mapping['files'] == [r for r in mapping['files']
        if r['public_path'].startswith('evidence/benchmarks/shared-tree-generation-office/')]
    result = {'status': 'PASS', 'method': 'PUBLIC_RELATIVE_EXACT_FILE_SET_AND_SHA256',
              'collections': summaries, 'mapped_rows': len(mapping['files']),
              'original_declared_inventories': manifests,
              'original_paths_read': False, 'native_or_proof_rerun': False,
              'scope': 'Retained bytes and declared inventories; original native/proof scope remains in immutable receipts.'}
    if finalize:
        write_new(MATH / 'verification-result.json', result)
        for name, root in ROOTS.items():
            write_new(root / 'handoff.json', {
                'schema': 'oma.public-evidence-handoff/1', 'status': 'VERIFIED_RETENTION',
                'collection': name, **summaries[name],
                'verification_receipt': ('verification-result.json' if name == 'math' else
                    '../../math/shared-tree-native-independent/verification-result.json'),
                'verification_receipt_sha256': digest(MATH / 'verification-result.json'),
                'application_or_store_changes': False,
                'checkpoint_scope': ('Independent historical sources 5e8/2b6e/f90/4b0/119 and final 33a analytic workflow'
                    if name == 'math' else 'Historical 4b0 Office fixed-flow mission; not final 33a Office validation')})
    else:
        assert read(MATH / 'verification-result.json') == result
        for name, root in ROOTS.items():
            handoff = read(root / 'handoff.json')
            assert all(handoff[k] == v for k, v in summaries[name].items())
            assert handoff['verification_receipt_sha256'] == digest(MATH / 'verification-result.json')
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--finalize', action='store_true', help='Create absent indexes and final handoffs exactly once')
    run(parser.parse_args().finalize)
