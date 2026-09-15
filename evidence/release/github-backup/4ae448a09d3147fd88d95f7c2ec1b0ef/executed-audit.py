"""Read-only repository backup sizing and bounded credential-pattern audit."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import time
import uuid

ROOT=Path(__file__).resolve().parents[3]
TARGET=ROOT/'evidence/release/github-backup'/uuid.uuid4().hex
TARGET.mkdir(parents=True)
def run(*args):return subprocess.check_output(args,cwd=ROOT)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(name,value):(TARGET/name).write_text(json.dumps(value,indent=2),encoding='utf-8')
start=time.monotonic()
head=run('git','rev-parse','HEAD').decode().strip()
index_before=sha(ROOT/'.git/index')
status=run('git','status','--porcelain=v1','-z').decode().split('\0')
write('pending-status.json',[s for s in status if s])
tracked=[]
for row in run('git','ls-files','-s','-z').split(b'\0'):
    if not row:continue
    meta,path=row.split(b'\t',1);mode,oid,stage=meta.decode().split()
    name=path.decode();p=ROOT/name
    tracked.append({'path':name,'oid':oid,'bytes':p.stat().st_size if p.is_file() else None})
objects={}
for row in run('git','rev-list','--objects','--all').splitlines():
    oid,_,name=row.partition(b' ');objects[oid.decode()]=name.decode(errors='replace')
metadata=subprocess.run(['git','cat-file','--batch-check=%(objectname) %(objecttype) %(objectsize)'],cwd=ROOT,
    input=('\n'.join(objects)+'\n').encode(),stdout=subprocess.PIPE,check=True).stdout
blobs=[]
for row in metadata.splitlines():
    oid,kind,size=row.decode().split()
    if kind=='blob':blobs.append({'oid':oid,'path':objects[oid],'bytes':int(size)})
blobs.sort(key=lambda row:row['bytes'],reverse=True)
write('history-blob-inventory.json',blobs)
write('tracked-inventory.json',tracked)
patterns={
    'private-key-header':rb'-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----',
    'github-token':rb'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{60,})\b',
    'aws-access-key':rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b',
    'openai-token':rb'\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{32,}\b',
    'slack-token':rb'\bxox[baprs]-[A-Za-z0-9-]{20,}\b',
}
patterns={name:re.compile(pattern) for name,pattern in patterns.items()}
suspicious_names=[r['path'] for r in tracked if re.search(r'(^|/)(?:\.env(?:\.|$)|credentials?(?:\.|$)|id_rsa$|id_ed25519$|\.npmrc$|\.pypirc$)',r['path'],re.I)]
matches=[]
proc=subprocess.Popen(['git','cat-file','--batch'],cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE)
try:
    for row in blobs:
        proc.stdin.write((row['oid']+'\n').encode());proc.stdin.flush()
        header=proc.stdout.readline().split();assert header[0].decode()==row['oid'] and header[1]==b'blob'
        data=proc.stdout.read(int(header[2]));assert len(data)==row['bytes'] and proc.stdout.read(1)==b'\n'
        for label,pattern in patterns.items():
            hits=list(pattern.finditer(data))
            if hits:matches.append({'oid':row['oid'],'path':row['path'],'pattern':label,'count':len(hits),'values':'REDACTED_NOT_RECORDED'})
finally:
    proc.stdin.close();assert proc.wait(timeout=10)==0
git_files=[p for p in (ROOT/'.git').rglob('*') if p.is_file()]
pending=[]
for raw in run('git','ls-files','--others','--exclude-standard','-z').split(b'\0'):
    if raw:
        p=ROOT/raw.decode();pending.append({'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size})
counts=run('git','count-objects','-vH').decode()
write('secret-pattern-findings.json',{'history_matches':matches,'tracked_suspicious_paths':suspicious_names,
    'scope':'Finite recognizable token/private-key patterns over reachable history blobs; not a comprehensive secret guarantee; values never retained'})
result={'status':'READ_ONLY_BACKUP_READINESS_AUDIT_COMPLETED','head_at_start':head,
    'head_at_end':run('git','rev-parse','HEAD').decode().strip(),'index_unchanged':index_before==sha(ROOT/'.git/index'),
    'tracked_files':len(tracked),'tracked_worktree_bytes':sum(r['bytes'] or 0 for r in tracked),
    'history_blob_count':len(blobs),'history_blob_uncompressed_bytes':sum(r['bytes'] for r in blobs),
    'largest_history_blobs':blobs[:15],
    'history_blobs_over_50_mib':[r for r in blobs if r['bytes']>50*1024**2],
    'history_blobs_over_100_mib':[r for r in blobs if r['bytes']>100*1024**2],
    'git_directory_files':len(git_files),'git_directory_bytes':sum(p.stat().st_size for p in git_files),
    'git_count_objects':counts,'untracked_count':len(pending),'untracked_bytes':sum(r['bytes'] for r in pending),
    'untracked_files':pending,'secret_pattern_match_rows':len(matches),'tracked_suspicious_paths':suspicious_names,
    'seconds':time.monotonic()-start,'actions':'Read-only git/history and filesystem access; no remote/index mutation',
    'ignored_scope':'Standard git backup excludes .oma Store/private stages, .release runtimes/packages, .venv, math1, data and ui/dist; these need a separate chosen backup artifact if desired.'}
write('result.json',result)
shutil.copyfile(__file__,TARGET/'executed-audit.py')
print(json.dumps({'result':str(TARGET/'result.json'),**{k:result[k] for k in ('tracked_files','tracked_worktree_bytes','history_blob_count','history_blob_uncompressed_bytes','git_directory_bytes','secret_pattern_match_rows','tracked_suspicious_paths','index_unchanged','seconds')},'largest_history_blob':blobs[0]}))
