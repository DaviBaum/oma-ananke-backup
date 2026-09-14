"""Copy completed campaign evidence without rewriting any retained input."""
from pathlib import Path
import hashlib
import json
import shutil
import zlib

ROOT = next(p for p in Path(__file__).resolve().parents if (p / 'AGENTS.md').is_file())
STAGE = ROOT / '.oma/development/next-best-fabrication'
ID = '310e9ac661714f8e91fcf67d91409415'
SOURCE = STAGE / 'evidence/benchmarks/office-budgets' / ID
STORE = STAGE / 'bench-stores' / ID
TARGET = ROOT / 'evidence/benchmarks/residual-fitting/office' / ID


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')


def main():
    if TARGET.exists():
        raise RuntimeError('Retention destination already exists; refusing to overwrite')
    reconciliation = read(SOURCE / 'campaign-reconciliation.json')
    assert reconciliation['status'] == 'UNCHANGED_OFFICE_B2_RESIDUAL_ACCEPTED_EXPORTED_AND_B0_BOUNDED_NO_INCUMBENT'
    assert all(reconciliation['preservation'].values())
    assert sum(len(c['candidates']) for c in reconciliation['cases'].values()) == 7
    declared = read(SOURCE / 'predeclaration.json')
    TARGET.mkdir(parents=True)
    copies = []

    def copy(source, relative):
        source = Path(source).resolve()
        destination = TARGET / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        expected = sha(source)
        shutil.copyfile(source, destination)
        assert sha(destination) == sha(source) == expected
        copies.append({'original_path': str(source), 'path': destination.relative_to(TARGET).as_posix(),
                       'sha256': expected, 'bytes': destination.stat().st_size})

    def tree(source, relative, suffix=None):
        for path in sorted(source.rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts and (suffix is None or path.suffix == suffix):
                copy(path, Path(relative) / path.relative_to(source))

    tree(SOURCE, 'campaign')
    for name in ('candidates', 'exports', 'checks', 'blobs'):
        tree(STORE / name, Path('store-evidence') / name)
    copy(STORE / 'baseline-input-copy.json', 'store-evidence/baseline-input-copy.json')
    copy(STORE / 'oma.sqlite3', 'store-evidence/oma.sqlite3')
    # Preserve all complete content-addressed documents and verify their logical roots.
    for path in (TARGET / 'store-evidence/blobs').glob('*.json.z'):
        value = json.loads(zlib.decompress(path.read_bytes()))
        encoded = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')
        assert hashlib.sha256(encoded).hexdigest() == path.name.removesuffix('.json.z')
    frozen = STORE / 'runtimes' / declared['checker_version'].rsplit(':', 1)[-1] / 'src/oma'
    actual = {p.relative_to(frozen).as_posix(): sha(p) for p in frozen.rglob('*.py')}
    assert actual == declared['application_source_sha256']
    tree(frozen, 'provenance/src/oma', '.py')
    for name in ('office_residual_budget_campaign.py', 'finalize_office_residual_budget.py',
                 'audit_office_residual_completion.py', 'retain_office_residual_evidence.py'):
        copy(STAGE / 'scripts' / name, Path('provenance/scripts') / name)
    copy(ROOT / 'scripts/ifc_joint_fitting_budget_campaign.py', 'provenance/scripts/historical_campaign_reference.py')
    external = []
    for row in declared['original_sources']:
        assert sha(row['path']) == row['sha256']
        external.append({**row, 'disposition': 'EXTERNAL_IMMUTABLE_IFC_BENCH_SOURCE_NOT_BUNDLED'})
    ifcs = [row for row in copies if row['path'].lower().endswith('.ifc')]
    assert len([row for row in ifcs if '/exports/' in row['path']]) == 1
    assert any(row['sha256'] == '3b89bccc41090526e57a8bc8ce04e9aaea45dcff5d573ce15038729d5c94c08b' for row in ifcs)
    write(TARGET / 'locator.json', {'schema': 'oma.campaign-relative-locator/1', 'copies': copies,
        'ifc_files': ifcs, 'external_sources': external,
        'source': str(SOURCE), 'store_source': str(STORE), 'originals_unchanged_after_copy': True,
        'reconciliation_sha256': sha(TARGET / 'campaign/campaign-reconciliation.json'),
        'checker_version': declared['checker_version'],
        'relocation_scope': 'Evidence paths are mapped here; immutable original documents retain their original paths. Not an automatically restored Store or self-contained native runtime.'})
    readme = (SOURCE / 'README.md').read_text(encoding='utf-8')
    readme += '\n\nThis retained copy includes all seven candidate outcomes, intermediate and final authored IFCs, the fresh exported IFC, all 210 isolated content-addressed documents, managed checker receipts, the immutable database snapshot, and exact Python source/script provenance. `locator.json` maps unchanged original paths to local relative files. `files.json` hashes every retained file except itself. Acquired original IFC-Bench inputs remain external SHA-bound dependencies; this is local evidence retention, not a source-asset redistribution or application release.\n'
    readme += '\nThe normally selected residual route ties the checked original-frontier route at 3.2964797960769348 m and two elbows. This mission demonstrates an independently checked alternative and its real IFC export; it does not demonstrate a length improvement, continuous optimum, global physical infeasibility for B0, or hydraulic adequacy. Both original wrapper failures and their read-only reconciliation are preserved under `campaign/`.\n'
    (TARGET / 'README.md').write_text(readme, encoding='utf-8')
    for row in copies:
        assert sha(row['original_path']) == sha(TARGET / row['path']) == row['sha256']
    inventory = [{'path': p.relative_to(TARGET).as_posix(), 'bytes': p.stat().st_size, 'sha256': sha(p)}
                 for p in sorted(TARGET.rglob('*')) if p.is_file()]
    write(TARGET / 'files.json', {'schema': 'oma.relative-file-inventory/1', 'files': inventory,
        'count': len(inventory), 'bytes': sum(r['bytes'] for r in inventory),
        'inventory_excludes_only_itself': True})
    print(json.dumps({'status': 'RETAINED_BYTE_IDENTICAL', 'directory': str(TARGET),
        'inventory_sha256': sha(TARGET / 'files.json'), 'files': len(inventory),
        'bytes': sum(r['bytes'] for r in inventory), 'ifc_files': len(ifcs)}))


if __name__ == '__main__':
    main()
