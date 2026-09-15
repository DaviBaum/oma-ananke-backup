"""Independent exact full-regression completion audit; never invokes pytest."""
from pathlib import Path
from collections import Counter,defaultdict
import argparse,datetime,hashlib,importlib.metadata,json,re,shutil,sys,uuid
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[3]
STAGE=Path(__file__).resolve().parent
RUN=ROOT/'.oma/development/building-services-20260915/combined-validation/c3482addaad441e5958746e2ab7a41ba'
CAMPAIGN=ROOT/'.oma/development/building-services-20260915/campaigns/1cbf8d8cc3c3485896f01b7a41a007fa/predeclaration.json'
VERSION='oma-independent-checker/2:b72cb24732b8b1d5ab08fdebda5e5649640a652b82bdda24a58f00d4da81b52c'
FAMILIES={'joint-fitting-budget-audit':{'declared-source.ifc','source-after-pause.ifc','result.json'},
          'joint-probe-native-audit':{'current-separated.ifc','transient-overlap.ifc','result.json'}}
PRODUCERS={'joint-fitting-budget-audit':'tests/test_joint_fitting_budget_adversarial.py',
           'joint-probe-native-audit':'tests/test_joint_probe_native_audit.py'}
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def dump(p,v):Path(p).write_text(json.dumps(v,indent=2),encoding='utf-8')
def inventory(p):return {f.relative_to(p).as_posix():sha(f) for f in p.rglob('*.py')}
def snapshot_files(p):
    return {f.relative_to(p).as_posix():sha(f) for f in p.rglob('*') if f.is_file()
            and not {'__pycache__','.pytest_cache'}.intersection(f.relative_to(p).parts)}
def build_identity(source,version):
    h=hashlib.sha256();h.update(version.encode());root=source/'oma'
    for p in sorted(root.rglob('*.py')):
        h.update(p.relative_to(root).as_posix().encode());h.update(b'\0');h.update(p.read_bytes());h.update(b'\0')
    packages={}
    for name in ('ifcopenshell','cadquery-ocp','numpy','scipy','pydantic','cupy-cuda12x'):
        try:v=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:v='absent'
        packages[name]=v;h.update(f'{name}={v}\0'.encode())
    return 'oma-independent-checker/2:'+h.hexdigest(),packages

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--prepare',action='store_true');parser.add_argument('--prepared',type=Path)
    args=parser.parse_args()
    if args.prepare:
        out=STAGE/'regression-peer'/uuid.uuid4().hex;out.mkdir(parents=True)
        shutil.copyfile(__file__,out/'executed-verifier.py')
        result=load(RUN/'result.json');native=load(RUN/'native-environment.json');manifest=load(RUN/'inputs.json');sources=load(RUN/'source.json')
        source=Path(result['source_directory']);snapshot=Path(result['snapshot']);nodes=load(RUN/'test-nodes.json')
        assert result['checker_version']==native['checker_version']==VERSION
        assert len(sources)==117 and len(manifest['files'])==315
        assert len(nodes)==len(set(nodes))==result['test_node_count']==3426
        assert sources==result['source_files']==inventory(source)==load(CAMPAIGN)['application_sources']
        assert manifest['files']==result['snapshot_files']
        assert all(sha(snapshot/k)==v for k,v in manifest['files'].items())
        version,packages=build_identity(source,native['version']);assert version==VERSION
        pins={n:sha(RUN/n) for n in ('runner.py','source.json','inputs.json','test-nodes.json','collection.log','native-environment.json')}
        for name in pins:shutil.copyfile(RUN/name,out/('prepared-'+name))
        shutil.copyfile(RUN/'result.json',out/'prepared-running-result.json')
        dump(out/'preparation.json',{'status':'PREPARED_NOT_A_COMPLETED_TEST_CLAIM','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
             'run':str(RUN),'source':str(source),'snapshot':str(snapshot),'checker_version':VERSION,'source_files':len(sources),'input_files':len(manifest['files']),
             'nodes':len(nodes),'pinned_files':pins,'packages':packages,'campaign_declaration_sha256':sha(CAMPAIGN),'executed_verifier_sha256':sha(out/'executed-verifier.py')})
        print(json.dumps({'prepared':str(out),'preparation_sha256':sha(out/'preparation.json'),'status':result['status']}),flush=True)
        return
    assert args.prepared is not None
    prepared=args.prepared.resolve();pins=load(prepared/'preparation.json')
    assert sha(__file__)==pins['executed_verifier_sha256']
    result=load(RUN/'result.json');assert result['status']=='PASS','Regression has not completed PASS'
    out=prepared/'completed';out.mkdir(exist_ok=False)
    bound={str(RUN/'result.json'):sha(RUN/'result.json'),str(CAMPAIGN):sha(CAMPAIGN)}
    assert bound[str(CAMPAIGN)]==pins['campaign_declaration_sha256']
    for name,h in pins['pinned_files'].items():
        assert sha(RUN/name)==h==sha(prepared/('prepared-'+name));bound[str(RUN/name)]=h
    native=load(RUN/'native-environment.json');source=Path(pins['source']);snapshot=Path(pins['snapshot'])
    manifest=load(RUN/'inputs.json');sources=load(RUN/'source.json');nodes=load(RUN/'test-nodes.json')
    assert inventory(source)==sources==result['source_files']==load(CAMPAIGN)['application_sources']
    assert len(sources)==117 and len(manifest['files'])==315
    version,packages=build_identity(source,native['version']);assert version==VERSION and packages==pins['packages']
    assert native['checker_version']==result['checker_version']==VERSION
    assert native['version']==sys.version and sha(native['interpreter'])==native['python_sha256']
    assert set(native['native_extensions'])=={'OCP.OCP','ifcopenshell._ifcopenshell_wrapper'}
    for row in native['native_extensions'].values():assert sha(row['path'])==row['sha256']
    assert result['kernel_direct_load_path']==str(source/'oma/optimization/shared_tree_synthesis.py')
    kernel='oma/optimization/shared_tree_synthesis.py';assert sha(Path(result['kernel_direct_load_path']))==sources[kernel]
    expected_command=[native['interpreter'],'-m','pytest','-q','-o','pythonpath='+source.as_posix(),'tests',
                      '--junitxml='+str(RUN/'tests.xml'),'--basetemp='+str(RUN/'native-stores')]
    assert result['command']==expected_command and result['returncode']==0 and result['phase']=='full'
    assert result['snapshot']==str(snapshot) and result['source_directory']==str(source)
    collected=[s.strip() for s in (RUN/'collection.log').read_text(encoding='utf-8').splitlines() if s.startswith('tests/') and '::' in s]
    assert collected==nodes and len(nodes)==len(set(nodes))==3426
    assert result['exact_collected_nodes_sha256']==sha(RUN/'test-nodes.json')
    xml=ET.parse(RUN/'tests.xml').getroot();cases=xml.findall('.//testcase')
    expected=[]
    for node in nodes:
        prefix,bracket,parameters=node.partition('[');parts=prefix.split('::')
        classname=parts[0][:-3].replace('/','.')
        if len(parts)>2:classname+='.'+'.'.join(parts[1:-1])
        expected.append((classname,parts[-1]+bracket+parameters))
    assert Counter((c.attrib['classname'],c.attrib['name']) for c in cases)==Counter(expected)
    counts={name:len(xml.findall('.//'+name)) for name in ('testcase','failure','error','skipped')}
    assert counts=={'testcase':3426,'failure':0,'error':0,'skipped':0}==result['observed_xml_counts']
    for suite in xml.findall('.//testsuite'):
        assert all(int(suite.get(name,'0'))==0 for name in ('failures','errors','skipped'))
    assert result['passed']==3426 and result['test_xml_sha256']==sha(RUN/'tests.xml')
    actual=snapshot_files(snapshot)
    assert all(actual.get(k)==v for k,v in manifest['files'].items())
    assert manifest['files']==result['snapshot_files']
    assert all(sha(manifest['origins'][k])==v for k,v in manifest['files'].items())
    extra={k:v for k,v in actual.items() if k not in manifest['files']}
    assert extra==result['derived_outputs']==load(RUN/'derived-outputs.json')
    grouped=defaultdict(set)
    for key in extra:
        match=re.fullmatch(r'evidence/release/(joint-fitting-budget-audit|joint-probe-native-audit)/([0-9a-f]{32})/([^/]+)',key)
        assert match,key
        family,attempt,name=match.groups();assert name in FAMILIES[family]
        grouped[(family,attempt)].add(name)
    assert len(extra)==6 and len(grouped)==2
    assert {f for f,a in grouped}==set(FAMILIES)
    assert all(names==FAMILIES[family] for (family,a),names in grouped.items())
    producer_binding={family:{'test_input':name,'sha256':manifest['files'][name]} for family,name in PRODUCERS.items()}
    for name in ('tests.xml','derived-outputs.json','pytest.log','result.json'):
        p=RUN/name;bound[str(p)]=sha(p);shutil.copyfile(p,out/name)
    dump(out/'independent-result.json',{'status':'INDEPENDENT_EXACT_3426_CASE_NATIVE_REGRESSION_AUDIT_PASS','checker_version':VERSION,
        'source_python_files':len(sources),'input_files':len(manifest['files']),'exact_xml_counts':counts,
        'collected_nodes_sha256':sha(RUN/'test-nodes.json'),'xml_sha256':sha(RUN/'tests.xml'),'result_sha256':sha(RUN/'result.json'),
        'source_manifest_sha256':sha(RUN/'source.json'),'input_manifest_sha256':sha(RUN/'inputs.json'),'native_environment_sha256':sha(RUN/'native-environment.json'),
        'declared_and_reconstructed_command':expected_command,'direct_kernel_source_sha256':sources[kernel],'derived_outputs':extra,'derived_producer_binding':producer_binding,
        'all_origin_and_copied_inputs_unchanged':True,'all_application_and_native_inputs_unchanged':True,'same_source_as_all_seven_hospital_campaign':True,
        'pytest_returncode':result['returncode'],'pytest_seconds':result['test_seconds'],'wrapper_seconds':result['seconds'],
        'scope':'Read-only reconciliation of closed original-native run. No tests or native geometry rerun; does not convert catalogue screens or missing Hospital design contracts into engineering approval.'})
    dump(out/'bound-files.json',bound)
    assert all(sha(p)==h for p,h in bound.items())
    files={p.relative_to(prepared).as_posix():{'sha256':sha(p),'bytes':p.stat().st_size} for p in prepared.rglob('*') if p.is_file() and p.name!='handoff.json'}
    dump(prepared/'handoff.json',{'schema':'oma.independent-exact-native-regression-audit/1','status':'CLOSED','retained_files':files,'independent_result':'completed/independent-result.json','independent_result_sha256':sha(out/'independent-result.json')})
    print(json.dumps({'handoff':str(prepared/'handoff.json'),'handoff_sha256':sha(prepared/'handoff.json'),'result':str(out/'independent-result.json'),'result_sha256':sha(out/'independent-result.json')}),flush=True)

if __name__=='__main__':main()
