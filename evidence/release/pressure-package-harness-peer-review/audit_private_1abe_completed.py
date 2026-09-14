"""Account for retained private 1abe completion, preserving any wrapper rejection."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
from datetime import datetime,timezone

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
spec=importlib.util.spec_from_file_location('independent_inventory',HERE/'audit_completed_suites.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
BASE=ROOT/'.oma/development/next-best-fabrication/evidence/full-backend-14bff19b88c54779af3d15b1295b5d8b'
r=json.loads((BASE/'result.json').read_text());assert r['status']!='RUNNING'
assert r['returncode']==0
assert r['status']=='PASS' or (r['status']=='FAIL' and r['error']=="AssertionError('Unexpected files outside declared test inputs')")
nodes=json.loads((BASE/'test-nodes.json').read_text())
assert a.sha(BASE/'test-nodes.json')==r['test_nodes_sha256']
assert len(nodes)==len(set(nodes))==r['test_node_count']==1847
collected=[line.strip() for line in (BASE/'collection.log').read_text().splitlines() if line.startswith('tests/') and '::' in line];assert collected==nodes
assert a.sha(BASE/'runner.py')==r['runner_sha256']
assert len(r['snapshot_files'])==106
inventory=a.snapshot(Path(r['test_snapshot']),r['snapshot_files'])
xml=a.account_xml(BASE/'tests.xml',nodes)
source_arg=next(arg for arg in r['command'] if arg.startswith('pythonpath='));source=Path(source_arg.split('=',1)[1]);assert source.is_dir()
env=os.environ.copy();env['PYTHONPATH']=str(source);env.pop('OMA_EXECUTABLE_BUILD',None)
probe="""import json,hashlib,sys;from pathlib import Path;import oma;from oma.build_identity import checker_version
import ifcopenshell._ifcopenshell_wrapper as ext
print(json.dumps({'checker_version':checker_version(),'oma_path':oma.__file__,'python':sys.executable,'source_files':{p.relative_to(Path(oma.__file__).parent).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(oma.__file__).parent.rglob('*.py')},'native_extension':ext.__file__,'native_extension_sha256':hashlib.sha256(Path(ext.__file__).read_bytes()).hexdigest()}))"""
identity=json.loads(subprocess.check_output([r['command'][0],'-c',probe],cwd=ROOT,env=env,text=True));assert identity['checker_version']==r['checker_version'];assert Path(identity['oma_path']).resolve().is_relative_to(source.resolve())
result={'status':'RETAINED_PRIVATE_SUITE_INDEPENDENT_COMPLETION_PASS','audited_at':datetime.now(timezone.utc).isoformat(),'scope':'Private application checkpoint only; exact retained tests, inputs and code identity. No rerun, no bundle/native promotion or public release approval.','original_wrapper_status':r['status'],'original_wrapper_error':r.get('error'),'original_result_sha256':a.sha(BASE/'result.json'),'original_runner_sha256':a.sha(BASE/'runner.py'),'test_nodes_sha256':a.sha(BASE/'test-nodes.json'),'xml':xml,'snapshot':inventory,'rederived_identity':identity,'audit_script_sha256':a.sha(__file__),'inventory_helper_sha256':a.sha(HERE/'audit_completed_suites.py')}
out=HERE/'private-1abe-completed-audit.json';out.open('x').write(json.dumps(result,indent=2)+'\n');print(json.dumps({'status':result['status'],'passed':xml['passed'],'raw_status':r['status'],'sha256':a.sha(out)}))
