from pathlib import Path
import hashlib,json,shutil,sys,uuid,xml.etree.ElementTree as ET
ROOT=Path.cwd();STAGE=ROOT/'.oma/development/hospital-outcome-audit';out=ROOT/'evidence/benchmarks/hospital-native-performance'/('local-tee-independent-'+uuid.uuid4().hex);out.mkdir(parents=True)
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def copy(source,relative):
 target=out/relative;target.parent.mkdir(parents=True,exist_ok=True);data=source.read_bytes();target.write_bytes(data);assert sha(source)==sha(target)
old=ROOT/'.oma/development/hospital-clearance-20260915/runtimes/f716dd5cbdd84134a50d855b217b91a886832abc582ee761b1340cec2026b8e7/src'
new=ROOT/'.oma/development/hospital-clearance-20260915/campaign-v2/runtimes/06aa865600b4ab2dc8f42f77b2cb5f82816dec99bbf8a1ff5f67673fb44c1949/src'
for name,path in [('before',old),('after',new)]:
 mapping={p.relative_to(path).as_posix():sha(p) for p in path.rglob('*.py')};assert len(mapping)==114
 (out/(name+'-source.json')).write_text(json.dumps(mapping,indent=2))
 for rel in ['oma/ifc/network.py','oma/ifc/network_semantics.py','oma/ifc/cad.py']:copy(path/rel,'source/'+name+'/'+rel)
copy(ROOT/'tests/test_network_local_tee.py','tests/test_network_local_tee.py')
for p in (STAGE/'local-tee-tests').iterdir():copy(p,'tests/'+p.name)
copy(ROOT/'.oma/development/hospital-outcomecome-before.xml','tests/initial-unbound-current.xml')
for label,path in [('precision',STAGE/'precision-probes/a77813e5cac842cd97e2b73cdcf38555'),('analytic',STAGE/'analytic-conversion-probes/0961827640114bca95535e08d29e4376')]:
 for p in path.iterdir():copy(p,label+'/'+p.name)
for name in ['test_ifc_network.py','test_ifc_pipeline.py','test_ifc_ports.py']:copy(ROOT/'tests'/name,'tests/support/'+name)
copy(ROOT/'docs/ifc-network-spec.json','tests/support/ifc-network-spec.json')
copy(Path(__file__),'executed-retain.py')
xml=ET.parse(out/'tests/after-06aa.xml');cases=xml.findall('.//testcase');assert len(cases)==11 and not xml.findall('.//failure') and not xml.findall('.//error') and not xml.findall('.//skipped')
oldxml=ET.parse(out/'tests/before-f716.xml');assert len(oldxml.findall('.//testcase'))==1 and len(oldxml.findall('.//failure'))==1
report={'status':'LOCAL_TEE_INDEPENDENT_REGRESSION_PASS','scope':'Same nominal cylinder-union geometry, current native volume threshold, source preservation and native ports. No Hospital clearance/service/acceptance claim from these fixtures.',
 'tests':{'passed':11,'pytest_seconds':11.80,'before_expected_failures':1,'initial_unbound_run':'pyproject pythonpath overrode environment; this is current-source smoke only, excluded from historical comparison','test_sha256':sha(ROOT/'tests/test_network_local_tee.py')},
 'before_source':str(old),'after_source':str(new),'frozen_paths_unchanged_now':True,
 'commands':[{'argv':[str(ROOT/'.venv/Scripts/python.exe'),'-m','pytest','-o','pythonpath='+str(path),'tests/test_network_local_tee.py',*(['-k','False-True-IFC4'] if name=='before' else []),'-q','--junitxml=.oma/development/hospital-outcome-audit/local-tee-tests/'+('before-f716.xml' if name=='before' else 'after-06aa.xml')], 'cwd':str(ROOT),'PYTHONPATH':str(path),'observed_pytest_exit':1 if name=='before' else 0} for name,path in [('before',old),('after',new)]] ,
 'provenance_note':'Exact command/exit logs captured during execution; this retention manifest and source-map reconciliation were assembled after those closed runs.',
 'analytic_probe':{'cases':54,'default_world_failures':2,'default_local_failures':0,'precision_forced_failures':0,'threshold_unchanged':True},
 'decision':'Do not change CAD integration or global precision; author equivalent tee CSG around component-local center, preserving full independent world geometry/port checks.'}
(out/'result.json').write_text(json.dumps(report,indent=2))
files={p.relative_to(out).as_posix():sha(p) for p in out.rglob('*') if p.is_file()}
(out/'handoff.json').write_text(json.dumps({'status':'CLOSED_INDEPENDENT_LOCAL_TEE_EVIDENCE','retained_files':files},indent=2))
print(json.dumps({'output':str(out),'handoff_sha256':sha(out/'handoff.json'),'result_sha256':sha(out/'result.json'),'files':len(files)}))

