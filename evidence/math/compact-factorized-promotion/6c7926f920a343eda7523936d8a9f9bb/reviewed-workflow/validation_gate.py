"""Read-only gate. Both exact final suites and frozen artifacts are mandatory."""
from pathlib import Path
from collections import Counter
import hashlib,json,re,xml.etree.ElementTree as ET
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').is_file())
FULL=ROOT/'evidence/release/compact-tree-original-full-d6d1204384b8'
CUSTOM=ROOT/'evidence/dependencies/native-build/checkpoint-validation/f73a8793ae0d-0cf1c8bf0868'
BUILD='f73a8793ae0df76d9ec53400cec18b05d2731f63c735b225c2246fee62df6b21'
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def xml_check(path,nodes):
    expected=[]
    for node in nodes:
        bits=node.split('::');assert bits[0].endswith('.py') and len(bits)>1
        cls=bits[0][:-3].replace('/','.').replace('\\','.')
        if len(bits)>2:cls+='.'+'.'.join(bits[1:-1])
        expected.append((cls,bits[-1]))
    root=ET.parse(path);cases=root.findall('.//testcase')
    assert Counter((c.attrib['classname'],c.attrib['name']) for c in cases)==Counter(expected)
    assert all(not root.findall('.//'+name) for name in ('error','failure','skipped'))
def inventory(path):
    files={}
    for p in Path(path).rglob('*'):
        assert not p.is_symlink() and not p.is_junction()
        if p.is_file() and not {'__pycache__','.pytest_cache'}.intersection(p.relative_to(path).parts):files[p.relative_to(path).as_posix()]=sha(p)
    return files
def completed_validation():
    full=read(FULL/'result.json');custom=read(CUSTOM/'result.json');handoff=read(FULL/'handoff.json')
    assert full['status']=='PASS' and full['passed']==3275 and full['returncode']==0
    assert full['inputs_unchanged'] and full['source_unchanged'] and full['native_unchanged'] and full['exact_case_identity_multiset']
    assert custom['status']=='CUSTOM_NATIVE_NEW_CHECKPOINT_FULL_SUITE_PASS' and custom['passed']==3275 and custom['failed']==custom['skipped']==0
    assert full['checker_version']=='oma-independent-checker/2:'+BUILD and custom['source_checkpoint']==BUILD
    assert handoff['status']=='ORIGINAL_F73_3275_EXACT_PUBLIC_RETENTION_PASS' and handoff['original_receipt_sha256']==sha(FULL/'result.json')
    sources=read(FULL/'source.json');inputs=read(FULL/'inputs.json')['files'];nodes=read(FULL/'test-nodes.json')
    assert len(sources)==114 and len(inputs)==305 and len(nodes)==len(set(nodes))==3275
    assert sources==full['source_files']==handoff['source_manifest'] and inputs==full['snapshot_files']==handoff['snapshot_inputs']
    assert inventory(FULL/'src')==sources and inventory(FULL/'snapshot')==inputs
    assert sha(FULL/'test-nodes.json')==full['exact_collected_nodes_sha256']==handoff['test_nodes_sha256']
    assert sha(FULL/'tests.xml')==full['test_xml_sha256']==handoff['test_xml_sha256'];xml_check(FULL/'tests.xml',nodes)
    custom_manifest=read(CUSTOM/'test-source-manifest.json');assert custom_manifest['files']==inputs
    assert sha(CUSTOM/'test-source-manifest.json')==custom['test_source_manifest_sha256']
    manifest=Path(custom['test_node_manifest']);assert manifest.read_text().splitlines()==nodes and sha(manifest)==custom['test_node_manifest_sha256']
    assert sha(CUSTOM/'tests.xml')==custom['test_xml_sha256'];xml_check(CUSTOM/'tests.xml',nodes)
    assert custom['test_node_count']==3275
    comparison=read(CUSTOM/'identity-comparison.json')
    for name in ('original','candidate'):
        normalized={('oma/'+k if not k.startswith('oma/') else k):v for k,v in comparison[name]['source_files'].items()}
        assert normalized==sources
    assert comparison['original']['checker_version']==full['checker_version']
    assert comparison['candidate']['checker_version']==custom['runtime']['OMA_EXECUTABLE_BUILD']!=full['checker_version']
    assert inventory(Path(custom['runtime']['PYTHONPATH']))==sources
    custom_actual=inventory(Path(custom['destination'])/'test-suite')
    extras={k:v for k,v in custom_actual.items() if k not in inputs}
    assert len(extras)==6 and all(re.fullmatch(r'evidence/release/(?:joint-fitting-budget-audit/[0-9a-f]{32}/(?:declared-source\.ifc|source-after-pause\.ifc|result\.json)|joint-probe-native-audit/[0-9a-f]{32}/(?:current-separated\.ifc|transient-overlap\.ifc|result\.json))',k) for k in extras)
    assert {k:v for k,v in custom_actual.items() if k not in extras}==inputs
    assert custom['final_test_snapshot_inventory']['inputs']==inputs and custom['final_test_snapshot_inventory']['generated_evidence']==extras
    python=ROOT/'.release/native-build/test-venv/Scripts/python.exe'
    expected_commands={
        'test_collection_record':[str(python),'-m','pytest','--collect-only','-q','-o','pythonpath=','tests'],
        'test_suite_record':[str(python),'-m','pytest','-q','-o','pythonpath=','@'+str(manifest),'--junitxml='+str(CUSTOM/'tests.xml')]}
    for key in ('test_collection_record','test_suite_record'):
        p=Path(custom[key]);r=read(p);assert r['status']=='PASS' and r['exit_code']==0 and sha(p.parent/'output.log')==r['log_sha256']
        assert r['command']==expected_commands[key] and Path(r['cwd']).resolve()==(Path(custom['destination'])/'test-suite').resolve()
        assert r['stage']==('checkpoint-test-collection' if key=='test_collection_record' else 'checkpoint-full-suite')
    direct_kernel=Path(custom['runtime']['PYTHONPATH'])/'oma/optimization/shared_tree_synthesis.py'
    assert Path(custom['kernel_direct_load']['path']).resolve()==direct_kernel.resolve()
    assert sha(direct_kernel)==custom['kernel_direct_load']['sha256']==sources['oma/optimization/shared_tree_synthesis.py']
    original_direct=Path(full['source_directory'])/'oma/optimization/shared_tree_synthesis.py'
    assert Path(full['kernel_direct_load_path']).resolve()==original_direct.resolve() and sha(original_direct)==sources['oma/optimization/shared_tree_synthesis.py']
    native=read(FULL/'native-environment.json');assert sha(native['interpreter'])==native['python_sha256']
    for record in native['native_extensions'].values():assert sha(record['path'])==record['sha256']
    assert sha(comparison['candidate']['extension_path'])==custom['native_extension_sha256']==comparison['candidate']['extension_sha256']
    return {'checker_version':full['checker_version'],'source_directory':str(FULL/'src'),'files':sources,
        'original_full_receipt':str(FULL/'result.json'),'original_full_receipt_sha256':sha(FULL/'result.json'),
        'custom_native_receipt':str(CUSTOM/'result.json'),'custom_native_receipt_sha256':sha(CUSTOM/'result.json'),
        'custom_collection_command_sha256':sha(Path(custom['test_collection_record'])),'custom_suite_command_sha256':sha(Path(custom['test_suite_record'])),
        'custom_direct_kernel_sha256':sha(direct_kernel),
        'original_nodes_sha256':sha(FULL/'test-nodes.json'),'custom_nodes_sha256':sha(manifest),'input_manifest_sha256':sha(FULL/'inputs.json')}
