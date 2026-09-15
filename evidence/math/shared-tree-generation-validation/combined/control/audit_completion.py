"""Post-completion read-only reaccounting; never starts or repeats a test."""
from pathlib import Path
import hashlib,importlib.util,json,time

STAGE=Path(__file__).resolve().parent
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text(encoding='utf-8'))
frozen=read(STAGE/'frozen-inputs.json')
assert sha(STAGE/'frozen-inputs.json')=='d974f896a9d0f2d78ac9b03af3d91bed4419e4996417eecbbcae8d94263c3b9b'
assert sha(STAGE/'inventory-helper.py')==frozen['inventory_helper_sha256']
spec=importlib.util.spec_from_file_location('exact_inventory_postcompletion',STAGE/'inventory-helper.py')
helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
records={}
for phase,expected_count in (('focused',360),('full',2788)):
 completed=read(STAGE/(phase+'-complete.json'));directory=Path(completed['directory']);record=read(directory/'result.json')
 assert completed['status']==record['status']=='PASS' and sha(directory/'result.json')==completed['result_sha256']
 assert record['source_files']==frozen['source_files'] and record['snapshot_files']==frozen['snapshot_files']
 nodes=read(STAGE/frozen['collection'][phase]['node_manifest'])
 assert len(nodes)==expected_count and read(directory/'test-nodes.json')==nodes
 exact=helper.account_xml(directory/'tests.xml',nodes)
 assert exact['passed']==expected_count
 assert sha(directory/'runner.py')==record['runner_sha256']
 assert sha(directory/'inventory-helper.py')==record['inventory_helper_sha256']==frozen['inventory_helper_sha256']
 assert all(sha(Path(record['test_snapshot'])/key)==value for key,value in frozen['snapshot_files'].items())
 source=Path(record['source_directory'])
 assert {p.relative_to(source).as_posix():sha(p) for p in source.rglob('*.py')}==frozen['source_files']
 native=read(directory/'native-environment.json');assert sha(directory/'native-environment.json')==record['native_environment_sha256']
 assert sha(Path(native['python']))==native['python_sha256']
 assert native['native_extensions'] and all(sha(Path(value['path']))==value['sha256'] for value in native['native_extensions'].values())
 records[phase]={'receipt':str(directory/'result.json'),'receipt_sha256':sha(directory/'result.json'),
  'exact_xml':exact,'native_environment_sha256':sha(directory/'native-environment.json'),
  'all_source_input_interpreter_native_extension_hashes_rechecked':True}
 if phase=='full':
  inventory=helper.snapshot(Path(record['test_snapshot']),frozen['snapshot_files'])
  assert inventory['derived_output_sha256']==record['derived_test_outputs'] and len(inventory['derived_output_sha256'])==6
  records[phase]['complete_input_and_six_derived_output_inventory']=inventory
assert all(sha(Path(frozen['input_snapshot'])/key)==value for key,value in frozen['snapshot_files'].items())
result={'schema':'oma.shared-tree-combined-original-native-postcompletion-audit/1','status':'PASS',
 'checked_at_unix':time.time(),'checker_version':frozen['checker_version'],'frozen_inputs_sha256':sha(STAGE/'frozen-inputs.json'),
 'source_files':112,'declared_inputs':162,'focused_tests':360,'full_tests':2788,
 'records':records,'script_sha256':sha(Path(__file__)),'no_test_rerun':True,
 'scope':'Exact original-native completed validation identity/XML/input/native-file accounting; no custom-suite or new package release assertion'}
path=STAGE/'completed-independent-audit.json';assert not path.exists()
path.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'status':'PASS','path':str(path),'sha256':sha(path)}))
