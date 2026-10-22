"""Retain a completed actual Hospital campaign and source-bound independent replay."""
from pathlib import Path
import argparse, gzip, hashlib, json, shutil, sqlite3, zlib

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').is_file())
STAGE = Path(__file__).resolve().parent
ARCHIVE = ROOT/'evidence/benchmarks/hospital-generated-tree/full-federation-1e87dd6ad9af48b5962cd500603fdfdc'

def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def write(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n', encoding='utf-8')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('campaign', type=Path)
    parser.add_argument('--review', type=Path, required=True)
    parser.add_argument('--tests', type=Path, required=True)
    args=parser.parse_args()
    campaign=args.campaign.resolve()
    out=ROOT/'evidence/benchmarks/hospital-whole-procurement'/campaign.name
    assert not out.exists(), 'Never replace a retained campaign'
    result=json.loads((campaign/'result.json').read_text())
    declaration=json.loads((campaign/'predeclaration.json').read_text())
    packet=json.loads((campaign/'report.json').read_text())
    review=json.loads(args.review.read_text())
    assert result['status']=='ALL_SEVEN_SOURCE_PURCHASING_SCENARIOS_COMPLETED'
    assert review['status']=='PASS' and review['packet_root']==result['packet_root']
    assert review['plan_root']==result['purchasing_plan_root'] and review['run_id']==result['run_id']
    assert packet['summary']['source_count']==7 and not packet['whole_building_networks_redesigned']
    tests=json.loads((args.tests/'result.json').read_text())
    assert tests['status']=='PASS' and tests['checker_version']==packet['checker_version']
    assert tests['application_sources_unchanged'] and tests['test_sources_unchanged']
    out.mkdir(parents=True)
    mapping=[]
    def retain(p, relative):
        raw=p.read_bytes()
        compressed=(len(raw)>=500_000 and p.suffix in {'.json','.log','.xml'}
                    and p.name not in {'mission.json','predeclaration.json','report.json','readable-results.json'})
        target=out/(relative+('.gz' if compressed else ''))
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(gzip.compress(raw,compresslevel=9,mtime=0) if compressed else raw)
        assert (gzip.decompress(target.read_bytes()) if compressed else target.read_bytes())==raw
        mapping.append(dict(original=str(p), retained=target.relative_to(out).as_posix(),
            original_sha256=hashlib.sha256(raw).hexdigest(), retained_sha256=sha(target),
            encoding='gzip' if compressed else 'identity'))
    for p in sorted(campaign.rglob('*')):
        if p.is_file() and 'takeoffs' not in p.relative_to(campaign).parts and p.name!='purchasing-plans.json':
            retain(p, 'campaign/'+p.relative_to(campaign).as_posix())
    store=Path(result['store'])
    artifact_index={}
    for p in sorted((store/'blobs').glob('*.json.z')):
        root=p.name.removesuffix('.json.z')
        raw=zlib.decompress(p.read_bytes())
        assert hashlib.sha256(raw).hexdigest()==root
        archived=ARCHIVE/'source-audits'/p.name
        if archived.is_file() and sha(archived)==sha(p):
            target=archived
        else:
            retain(p, 'store/blobs/'+p.name)
            target=out/'store/blobs'/p.name
        artifact_index[root]=dict(path_from_repository_root=target.relative_to(ROOT).as_posix(),
            encoding='zlib', encoded_sha256=sha(target), encoded_bytes=target.stat().st_size,
            decoded_sha256=root, decoded_bytes=len(raw))
    write(out/'artifact-index.json',artifact_index)
    source_db=sqlite3.connect((store/'oma.sqlite3').as_uri()+'?mode=ro',uri=True)
    target_db=sqlite3.connect(out/'store/oma.sqlite3')
    source_db.backup(target_db)
    assert target_db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    for table, in source_db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
        assert table.replace('_','').isalnum()
        assert source_db.execute(f'SELECT * FROM "{table}"').fetchall()==target_db.execute(f'SELECT * FROM "{table}"').fetchall()
    source_db.close(); target_db.close()
    source_index=[]
    for original, expected in declaration['source_files'].items():
        p=Path(original); assert sha(p)==expected
        archived=ARCHIVE/'original-ifc'/(p.name+'.gz')
        with gzip.open(archived,'rb') as f:
            assert hashlib.file_digest(f,'sha256').hexdigest()==expected
        source_index.append(dict(name=p.name,original_sha256=expected,original_path=original,
            archive=archived.relative_to(ROOT).as_posix(),archive_sha256=sha(archived),encoding='gzip'))
    write(out/'original-source-index.json',source_index)
    source=Path(declaration['source_path'])
    actual={p.relative_to(source).as_posix():sha(p) for p in source.rglob('*.py')}
    assert actual==declaration['application_sources']
    for relative in actual:
        retain(source/relative,'source/'+relative)
    write(out/'application-source-manifest.json',actual)
    retain(args.review,'independent-review/replay.json')
    retain(STAGE/'independent-review/verify_campaign.py','independent-review/verify_campaign.py')
    for name in ('build-binding.json','verify_build_binding.py'):
        retain(STAGE/'independent-review'/name,'independent-review/'+name)
    for p in sorted(args.tests.rglob('*')):
        if p.is_file() and '__pycache__' not in p.parts:
            retain(p,'focused-validation/'+p.relative_to(args.tests).as_posix())
    for name in ('reference-prices.json','policy_builder.py','review-receipt.json','axis-peer-review.json','README.md'):
        p=STAGE/'cost-research/20261022'/name
        if p.is_file(): retain(p,'price-basis/'+name)
    for p in sorted((STAGE/'takeoff-interval-review').glob('*')):
        if p.is_file(): retain(p,'takeoff-review/'+p.name)
    for name in ('result-subset.json','subset-comparison.json','tests-subset.xml','pytest-subset.log'):
        p=STAGE/'procurement-validation'/name
        if p.is_file(): retain(p,'packing-review/'+name)
    mission=Path(declaration['mission_source'])
    if mission.with_suffix('.basis.json').is_file():
        retain(mission.with_suffix('.basis.json'),'price-basis/mission-basis.json')
    for name in ('campaign.py','build_mission.py','retain_campaign.py','summarize_campaign.py','validate_final.py'):
        p=STAGE/name
        if p.is_file(): retain(p,'tools/'+name)
    write(out/'file-mapping.json',mapping)
    files={p.relative_to(out).as_posix():sha(p) for p in out.rglob('*') if p.is_file()}
    handoff=dict(schema='oma.hospital-procurement-retention/1', status='CLOSED_CONDITIONAL_PURCHASING_SCENARIOS',
        checker_version=packet['checker_version'], campaign_id=campaign.name,run_id=result['run_id'],
        project_id=result['project']['id'], packet_root=result['packet_root'],
        purchasing_plan_root=result['purchasing_plan_root'],retained_files=files,
        retained_bytes=sum((out/p).stat().st_size for p in files),
        external_dependencies=dict(original_sources='original-source-index.json',artifacts='artifact-index.json'),
        independent_quantity_cost_baseline_replay='PASS',original_sources_unchanged=True,
        whole_building_networks_redesigned=False,construction_approval=False,
        full_regression='Only the retained focused suite applies to this new build; historical full regression has a separate source identity.')
    write(out/'handoff.json',handoff)
    assert all(sha(out/p)==v for p,v in files.items())
    print(json.dumps(dict(status='RETAINED_AND_VERIFIED',directory=str(out),files=len(files),bytes=handoff['retained_bytes'],handoff_sha256=sha(out/'handoff.json'))))

if __name__=='__main__':
    main()
