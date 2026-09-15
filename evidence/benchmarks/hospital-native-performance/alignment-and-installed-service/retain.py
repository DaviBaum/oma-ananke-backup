from pathlib import Path
import hashlib,json,shutil
ROOT=Path.cwd();source=ROOT/'.oma/development/hospital-alignment-service-audit'
target=ROOT/'evidence/benchmarks/hospital-native-performance/alignment-and-installed-service';target.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
receipt=json.loads((source/'handoff.json').read_text())
assert receipt['status']=='READ_ONLY_AUDIT_COMPLETE_NO_ALIGNMENT_OR_SERVICE_APPROVAL'
assert sha(source/'handoff.json')=='810efcaa0cc59dac01c8ebc072f9d782543dbbfa75a289359f60cee496a66ac8'
for row in receipt['files']:
 assert sha(source/row['path'])==row['sha256']
 shutil.copyfile(source/row['path'],target/row['path']);assert sha(target/row['path'])==row['sha256']
shutil.copyfile(source/'handoff.json',target/'original-handoff.json')
shutil.copyfile(__file__,target/'retain.py')
retention={'status':'UNCHANGED_READ_ONLY_ALIGNMENT_SERVICE_AUDIT_RETAINED','retained_files':{p.name:sha(p) for p in target.iterdir() if p.is_file()},'scope':receipt['scope'],'no_alignment_or_service_approval_inferred':True}
(target/'handoff.json').write_text(json.dumps(retention,indent=2))
print(target/'handoff.json')
