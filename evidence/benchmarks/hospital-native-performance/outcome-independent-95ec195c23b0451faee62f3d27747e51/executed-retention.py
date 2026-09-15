"""Retain only a completed independent Hospital outcome audit, losslessly."""
from pathlib import Path
import argparse,gzip,hashlib,json,shutil,uuid
ROOT=Path(__file__).resolve().parents[3]
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
p=argparse.ArgumentParser();p.add_argument('attempt',type=Path);p.add_argument('--watcher',type=Path,required=True);p.add_argument('--comparison',type=Path,required=True);args=p.parse_args()
attempt=args.attempt.resolve();watcher=args.watcher.resolve();result=read(attempt/'result.json');watch=read(watcher/'result.json')
assert result['status']=='BOTH_FIXED_ALTERNATIVES_AND_SELECTED_FRESH_EXPORT_AUDITED'
assert result['files_unchanged'] and result['app_unchanged'] and result['store_project_unchanged']
assert watch['status']=='AUDIT_CHILD_CLOSED' and watch['supervision']['status']=='COMPLETED' and watch['supervision']['returncode']==0
assert Path(watch['audit_summary']['output']).resolve()==attempt and watch['audit_summary']['status']==result['status']
comparison=args.comparison.resolve();metric=read(comparison/'result.json');assert metric['status']=='EXACT_CHECKED_ALTERNATIVE_METRIC_COMPARISON' and metric['audit_result_sha256']==sha(attempt/'result.json')
inputs=read(attempt/'inputs.json');assert all(sha(Path(path))==value for path,value in inputs['files'].items())
source=Path(inputs['source']);assert {x.relative_to(source).as_posix():sha(x) for x in source.rglob('*.py')}==inputs['app']
out=ROOT/'evidence/benchmarks/hospital-native-performance'/('outcome-independent-'+attempt.name);out.mkdir(parents=True,exist_ok=False)
records=[]
for label,directory in [('audit',attempt),('watcher',watcher),('comparison',comparison)]:
 for item in sorted(directory.rglob('*')):
  if not item.is_file():continue
  data=item.read_bytes();before=hashlib.sha256(data).hexdigest();rel=label+'/'+item.relative_to(directory).as_posix();compressed=len(data)>1024**2
  target=out/(rel+'.gz' if compressed else rel);target.parent.mkdir(parents=True,exist_ok=True)
  target.write_bytes(gzip.compress(data,compresslevel=9,mtime=0) if compressed else data)
  decoded=gzip.decompress(target.read_bytes()) if compressed else target.read_bytes();assert decoded==data and sha(item)==before
  records.append({'original':str(item),'retained':target.relative_to(out).as_posix(),'original_sha256':before,'original_bytes':len(data),'lossless_gzip':compressed})
shutil.copyfile(__file__,out/'executed-retention.py')
summary={'status':'CLOSED_HOSPITAL_OUTCOME_INDEPENDENT_AUDIT','audit_result_sha256':sha(attempt/'result.json'),'watcher_result_sha256':sha(watcher/'result.json'),
 'result':result,'comparison_result_sha256':sha(comparison/'result.json'),'original_files':inputs['files'],'source':inputs['source'],'source_files':inputs['app'],'copy_map':records}
(out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
files={x.relative_to(out).as_posix():sha(x) for x in out.rglob('*') if x.is_file()}
(out/'handoff.json').write_text(json.dumps({'status':'CLOSED_HOSPITAL_OUTCOME_INDEPENDENT_AUDIT','retained_files':files},indent=2),encoding='utf-8')
print(json.dumps({'output':str(out),'handoff_sha256':sha(out/'handoff.json'),'audit_result_sha256':sha(attempt/'result.json'),'retained_files':len(files)}))

