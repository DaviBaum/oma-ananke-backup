"""Retain exact local/global proof evidence and integrate only two new files."""
from pathlib import Path
import hashlib,json,shutil,sys
STAGE=Path(__file__).resolve().parent
ROOT=next(p for p in STAGE.parents if (p/'AGENTS.md').is_file())
AGENT=ROOT/'.oma/development/coupled-tree-univalence'
OUT=STAGE/'evidence/integration-a3bc493618a742f9a4270b4ea06dc075'
PUBLIC=ROOT/'evidence/math/coupled-tree-univalence'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf8'))
def copy(s,d,h=None):
    h=h or sha(s);assert sha(s)==h
    assert not d.exists(),d
    d.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(s,d);assert sha(d)==h
def main():
    r=read(OUT/'result.json');h=read(AGENT/'handoff.json')
    assert sha(AGENT/'handoff.json')=='04cc24053581ae297d4154911d1ca85af9c1a456cd768a5e210a415d38de61fb'
    assert r['status']=='PASS' and r['passed']==484 and r['exact_case_identities_checked']
    assert r['snapshot_unchanged'] and r['frozen_source_unchanged']
    assert sha(OUT/'tests.xml')==r['test_xml_sha256']
    current={p.relative_to(ROOT/'src/oma').as_posix():sha(p) for p in (ROOT/'src/oma').rglob('*.py')}
    assert current==r['base_application_hashes']
    assert set(r['source_files'])-set(current)=={'optimization/coupled_tree_univalence.py'}
    assert all(r['source_files'][k]==v for k,v in current.items())
    for rel,digest in h['files'].items():copy(AGENT/rel,PUBLIC/'private-handoff'/rel,digest)
    copy(AGENT/'handoff.json',PUBLIC/'handoff.json')
    peer=read(AGENT/'native-peer-handoff.json')
    assert sha(AGENT/'native-peer-handoff.json')=='562f04511dd81da04ee22386d9005bede4fc1d91195b825bfd1a738b91f97042'
    for row in peer['audit_files']+peer['bound_native_reference_inputs']:
        copy(ROOT/row['path'],PUBLIC/'native-derived-peer'/row['path'].removeprefix('.oma/development/'),row['sha256'])
    copy(AGENT/'native-peer-handoff.json',PUBLIC/'native-peer-handoff.json')
    for name in ('result.json','tests.xml','test-nodes.json','runner.py','inventory-helper.py','pytest.log','collection.log'):
        copy(OUT/name,PUBLIC/'combined-focused'/name)
    for rel,digest in r['source_files'].items():copy(Path(r['source_directory'])/'oma'/rel,PUBLIC/'tested-source/oma'/rel,digest)
    for rel,digest in r['snapshot_files'].items():copy(Path(r['test_snapshot'])/rel,PUBLIC/'focused-inputs'/rel,digest)
    for row in h['merge_new_files_only']:copy(ROOT/row['path'],ROOT/row['destination'],row['sha256'])
    copy(AGENT/'docs/univalence-design.md',ROOT/'docs/math/coupled-tree-univalence.md')
    sys.path.insert(0,str(ROOT/'src'))
    from oma.build_identity import checker_version
    assert checker_version()==r['checker_version']
    copy(Path(__file__),PUBLIC/'integration-runner.py')
    result={'schema':'oma.integrated-coupled-tree-univalence/1','status':'INTEGRATED_FOCUSED_AND_INDEPENDENT_REVIEW_PASS',
        'source_before':'8f6f5c18b77bb9ef45e7cd3b2c24987a13c822cca706178f0a8d173fc03c1206',
        'source_after':r['checker_version'],'focused_tests':484,'focused_wrapper_seconds':r['seconds'],
        'source_python_files':105,'test_support_files':122,'focused_xml_sha256':r['test_xml_sha256'],
        'kernel_tests':57,'independent_models':24,'resealed_attacks':240,'theorem':h['theorem'],
        'native_adapter_integrated':False,'full_source_algorithms_complete':False,'current_full_regression':'NOT_YET_RUN_ON_NEW_SOURCE',
        'retained_files':{p.relative_to(PUBLIC).as_posix():{'sha256':sha(p),'bytes':p.stat().st_size} for p in PUBLIC.rglob('*') if p.is_file()}}
    (PUBLIC/'latest.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:result[k] for k in ('status','source_after','focused_tests')}))
if __name__=='__main__':main()
