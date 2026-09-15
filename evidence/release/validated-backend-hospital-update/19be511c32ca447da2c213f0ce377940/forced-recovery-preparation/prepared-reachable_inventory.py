"""Read-only supported Store content/file closure, including external assets.

File-field vocabulary matches the portable Store contract. Arbitrary IFC
property strings are not file authority. All database fields seed root scans.
"""
from pathlib import Path
import hashlib
import json
import zlib

def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def capture_reachable(directory, tables):
    directory = Path(directory).resolve()
    available = {p.name.removesuffix('.json.z'): p for p in (directory / 'blobs').glob('*.json.z')}
    roots, seen, references = set(), set(), set()
    keys = {'immutable_path', 'source_path', 'export_path', 'mesh_json_gz', 'mesh_npz', 'audit', 'replacement_path'}
    def scan(value):
        stack = [(value, True)]
        while stack:
            item, assets = stack.pop()
            if isinstance(item, str):
                if item in available:
                    roots.add(item)
            elif isinstance(item, list):
                stack.extend((v, assets) for v in item)
            elif isinstance(item, dict):
                for key, value in item.items():
                    if assets and isinstance(value, str) and (key in keys or key == 'path' and ('sha256' in item or 'source_sha256' in item)):
                        references.add(value)
                    stack.append((value, assets and key not in {'properties', 'artifact_sha256'}))
    def rows(name):
        table = tables[name]
        return [dict(zip(table['columns'], r)) for r in table['rows']]
    mandatory = [('projects', 'state_root'), ('revisions', 'root'), ('candidates', 'state_root'), ('candidates', 'report_root'), ('runs', 'base_root')]
    for table, key in mandatory:
        for row in rows(table):
            if row.get(key):
                assert row[key] in available, ('Missing authoritative Store root', table, key, row[key])
                roots.add(row[key])
    for table in tables.values():
        for row in table['rows']:
            for value in row:
                if isinstance(value, str):
                    scan(value)
                    if value.startswith(('{', '[')):
                        try:
                            scan(json.loads(value))
                        except json.JSONDecodeError:
                            pass
    blobs = {}
    while roots - seen:
        root = next(iter(roots - seen))
        raw = available[root].read_bytes()
        content = zlib.decompress(raw)
        assert hashlib.sha256(content).hexdigest() == root
        blobs[root] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
        seen.add(root)
        scan(json.loads(content))
        del content, raw
    aliases = {r['original_path']: r['relative_path'] for r in rows('asset_aliases')}
    metadata = {r['key']: r['value'] for r in rows('metadata')}
    relocations = json.loads(metadata.get('relocation_roots', '[]'))
    def resolve(value):
        path = Path(value).expanduser()
        if str(path) in aliases:
            target = (directory / aliases[str(path)]).resolve()
            assert target.is_relative_to(directory)
            return target
        for old in relocations:
            if path.is_relative_to(Path(old)):
                return (directory / path.relative_to(Path(old))).resolve()
        return path.resolve()
    files = {}
    for reference in sorted(references):
        path = resolve(reference)
        targets = [path]
        if path.suffix.lower() == '.ifc' and path.with_suffix('.manifest.json').is_file():
            targets.append(path.with_suffix('.manifest.json'))
        for target in targets:
            assert target.is_file() and not target.is_symlink() and not target.is_junction(), str(target)
            if str(target) not in files:
                before = target.stat()
                digest = sha(target)
                after = target.stat()
                assert (before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns)
                files[str(target)] = {'bytes': after.st_size, 'sha256': digest}
    return {'reachable_blobs': dict(sorted(blobs.items())), 'referenced_files': dict(sorted(files.items())),
            'reference_count': len(references),
            'scope': 'All database/root-reachable supported file references, including excluded runtime/development/external paths and present IFC sidecars; exact before/after preservation'}
