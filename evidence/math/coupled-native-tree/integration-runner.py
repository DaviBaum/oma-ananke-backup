"""Promote exact independently reviewed adapter/glue after real integration checks."""
from pathlib import Path
import hashlib,json,shutil,sys,xml.etree.ElementTree as ET
STAGE=Path(__file__).resolve().parent
ROOT=next(p for p in STAGE.parents if (p/'AGENTS.md').is_file())
AGENT=ROOT/'.oma/development/coupled-native-tree'
PACKAGE=AGENT/'evidence/math/coupled-native-tree'
PUBLIC=ROOT/'evidence/math/coupled-native-tree'
GOOD=STAGE/'evidence/integration-c536888a755d43718fe15b882776ee9f'
INITIAL=STAGE/'evidence/integration-5aa41849e4584b10a4368ede96e8d9cb'
REVIEW=ROOT/'.oma/development/coupled-native-glue-review/evidence/d67505e1e5194ca186927d249059fdf1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf8'))
def copy(s,d,h=None,replace=None):
    h=h or sha(s);assert sha(s)==h,s
    if d.exists():assert replace is not None and sha(d)==replace,d
    d.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(s,d);assert sha(d)==h
def tree(s,d):
    for p in s.rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts and '.pytest_cache' not in p.parts:copy(p,d/p.relative_to(s))
def main():
    good,initial,h=read(GOOD/'result.json'),read(INITIAL/'result.json'),read(PACKAGE/'handoff.json')
    assert good['status']=='PASS' and good['passed']==20
    assert good['frozen_source_unchanged'] and good['snapshot_unchanged'] and good['exact_case_identities_checked']
    assert initial['status']=='FAIL' and initial['test_node_count']==746
    assert initial['source_files']==good['source_files']
    failed=[x for x in ET.parse(INITIAL/'tests.xml').getroot().findall('.//testcase') if x.find('failure') is not None or x.find('error') is not None]
    assert len(failed)==2 and all('test_native_geometry_cannot_override_bad_or_uncertified_coupled_service' in x.attrib['name'] for x in failed)
    changed=[k for k in good['snapshot_files'] if good['snapshot_files'][k]!=initial['snapshot_files'][k]]
    assert changed==['tests/test_coupled_tree_integration.py']
    assert sha(PACKAGE/'handoff.json')=='0d324adeca8a8bf61f22873aff4cdf305abf5944f19f3d5e1a4f988adf0bf09a'
    current={p.relative_to(ROOT/'src/oma').as_posix():sha(p) for p in (ROOT/'src/oma').rglob('*.py')}
    assert current==good['base_application_hashes']
    assert len(current)==105 and len(good['source_files'])==107 and len(good['snapshot_files'])==131
    glue=good['glue_manifest']['source_files']
    assert {k for k in current if current[k]!=good['source_files'][k]}==set(glue)
    for rel,row in read(PACKAGE/'contents.json')['files'].items():copy(PACKAGE/rel,PUBLIC/'adapter-handoff'/rel,row['sha256'])
    for name in ('contents.json','handoff.json'):copy(PACKAGE/name,PUBLIC/name)
    for name,attempt in (('initial-integration',INITIAL),('corrected-integration',GOOD)):
        tree(attempt,PUBLIC/name)
        receipt=read(attempt/'result.json')
        for rel,digest in receipt['snapshot_files'].items():copy(Path(receipt['test_snapshot'])/rel,PUBLIC/name/'exact-inputs'/rel,digest)
    for rel,digest in good['source_files'].items():copy(Path(good['source_directory'])/'oma'/rel,PUBLIC/'tested-source/oma'/rel,digest)
    tree(REVIEW,PUBLIC/'glue-independent-review')
    for name in ('prepare_glue.py','glue-manifest.json','capture_legacy_contracts.py','prepare_corrected_validation.py'):
        copy(STAGE/name,PUBLIC/'glue-preparation'/name)
    for rel,digest in h['merge_files'].items():copy(AGENT/rel,ROOT/rel,digest)
    for rel,row in glue.items():copy(STAGE/'src/oma'/rel,ROOT/'src/oma'/rel,row['after'],replace=row['before'])
    for rel in ('tests/test_coupled_tree_integration.py','tests/fixtures/coupled-native-tree/legacy-contracts.json'):
        copy(Path(good['test_snapshot'])/rel,ROOT/rel,good['snapshot_files'][rel])
    for rel,digest in h['docs'].items():copy(AGENT/rel,ROOT/rel,digest)
    sys.path.insert(0,str(ROOT/'src'))
    from oma.build_identity import checker_version
    assert checker_version()==good['checker_version']
    copy(Path(__file__),PUBLIC/'integration-runner.py')
    result={'schema':'oma.integrated-coupled-native-tree/1','status':'INTEGRATED_NATIVE_ACCEPTANCE_AND_FRESH_EXPORT_PASS_FULL_SUITE_RUNNING',
        'source_before':'68acbb9d3ef6a3cafd39bf231e6a3274d5e96bb2c281baeeddc27bbbb6938aee','source_after':good['checker_version'],
        'source_python_files':107,'test_support_files':131,'adapter_tests':113,
        'initial_compatibility':{'passed':744,'failed':2,'seconds':94.03,'cause':'Two tests incorrectly expected REJECTED for truthful UNKNOWN candidates; no application change'},
        'corrected_native_integration':{'passed':20,'failed':0,'wrapper_seconds':good['seconds'],'xml_sha256':good['test_xml_sha256']},
        'native_reference':h['actual_native_reference'],'full_source_algorithms_complete':False,
        'full_regression':'RUNNING_SEPARATELY_ON_EXACT_2467_CASE_SNAPSHOT',
        'full_original_receipt':'evidence/release/coupled-tree-full-17ea63bc503a4b78bb572ffee1dce06f/result.json',
        'scope':'Explicit unequal-outlet fixed-loss ideal-bore directed pressure trees. Same-model local/global proofs and all-port service are necessary; complete native checks, managed publication, exact current bytes and fresh IFC export remain mandatory. No general topology or full physical applicability claim.',
        'retained_files':{p.relative_to(PUBLIC).as_posix():{'sha256':sha(p),'bytes':p.stat().st_size} for p in PUBLIC.rglob('*') if p.is_file()}}
    (PUBLIC/'latest.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:result[k] for k in ('status','source_after','source_python_files','test_support_files')}))
if __name__=='__main__':main()
