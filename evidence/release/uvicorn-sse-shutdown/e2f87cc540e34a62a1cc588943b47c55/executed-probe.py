"""Isolated actual-SSE Uvicorn draining probe; never opens the live Store."""
from pathlib import Path
import argparse,asyncio,hashlib,http.client,inspect,json,os,shutil,signal,socket,sqlite3,subprocess,sys,time,traceback,uuid
ROOT=Path(__file__).resolve().parents[3];STAGE=Path(__file__).resolve().parent
SOURCE=ROOT/'.oma/development/hospital-clearance-20260915/campaign-v2/runtimes/06aa865600b4ab2dc8f42f77b2cb5f82816dec99bbf8a1ff5f67673fb44c1949/src'
def sha(path):
 with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def write(path,obj):Path(path).write_text(json.dumps(obj,indent=2),encoding='utf-8')
def read(path):return json.loads(Path(path).read_text())
def snapshot(directory):
 db=sqlite3.connect((directory/'oma.sqlite3').resolve().as_uri()+'?mode=ro',uri=True);db.execute('BEGIN')
 tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
 result={table:db.execute('SELECT * FROM "'+table+'" ORDER BY rowid').fetchall() for table in tables};db.close()
 return {'sql':result,'blobs':{p.relative_to(directory).as_posix():sha(p) for p in (directory/'blobs').rglob('*') if p.is_file()}}
p=argparse.ArgumentParser();p.add_argument('--child',type=Path);p.add_argument('--port',type=int);p.add_argument('--timeout');args=p.parse_args()
if args.child:
 out=args.child.resolve();assert out.is_relative_to(STAGE.resolve());sys.path.insert(0,str(SOURCE))
 import uvicorn
 from oma.api import create_app
 from oma.build_identity import checker_version
 app=create_app(out/'store',recover=False);service=app.state.engine
 project=service.store.create_project('Isolated SSE shutdown probe',{'sources':[],'entities':[{'id':'preserved-probe-value','properties':{'value':37}}]})
 assert checker_version()==os.environ['OMA_EXECUTABLE_BUILD'];assert not service.threads
 original=service.shutdown
 def observe_shutdown():
  write(out/'cleanup-entered.json',{'time':time.perf_counter(),'threads':len(service.threads),'alive':sum(t.is_alive() for t in service.threads.values())})
  original()
  write(out/'cleanup-complete.json',{'time':time.perf_counter(),'closing':service.closing,'threads':len(service.threads),'alive':sum(t.is_alive() for t in service.threads.values())})
 service.shutdown=observe_shutdown
 def emit_signal():
  write(out/'signal.json',{'time':time.perf_counter(),'kind':'signal.raise_signal(SIGINT)','pid':os.getpid()})
  signal.raise_signal(signal.SIGINT)
 @app.post('/__probe/first-sigint')
 async def first_sigint():
  asyncio.get_running_loop().call_later(.1,emit_signal)
  return {'scheduled':'single SIGINT','active_workers':sum(t.is_alive() for t in service.threads.values())}
 write(out/'child-start.json',{'pid':os.getpid(),'project_id':project['id'],'checker_version':checker_version(),'source':str(SOURCE),'timeout':args.timeout})
 uvicorn.run(app,host='127.0.0.1',port=args.port,timeout_graceful_shutdown=None if args.timeout=='none' else int(args.timeout),access_log=False,log_level='info')
 assert service.closing and (out/'cleanup-complete.json').exists()
 write(out/'child-complete.json',{'time':time.perf_counter(),'closing':service.closing,'active_workers':sum(t.is_alive() for t in service.threads.values())})
 raise SystemExit(0)
out=STAGE/'attempts'/uuid.uuid4().hex;out.mkdir(parents=True);shutil.copyfile(__file__,out/'executed-probe.py')
source_map={p.relative_to(SOURCE).as_posix():sha(p) for p in SOURCE.rglob('*.py')};assert len(source_map)==114
write(out/'source.json',source_map)
import uvicorn,uvicorn.server,uvicorn.config,psutil
for name,module in [('server',uvicorn.server),('config',uvicorn.config)]:shutil.copyfile(module.__file__,out/('uvicorn-'+name+'.py'))
write(out/'library.json',{'uvicorn':uvicorn.__version__,'server_file':uvicorn.server.__file__,'server_sha256':sha(uvicorn.server.__file__),'config_file':uvicorn.config.__file__,'config_sha256':sha(uvicorn.config.__file__),'primary_docs':['https://www.uvicorn.org/settings/','https://www.uvicorn.org/server-behavior/'],'interpretation':'Graceful timeout bounds waiting for connection/task drain; lifespan cleanup is still awaited separately. It is not a hard whole-process shutdown deadline.'})
result={'status':'RUNNING','scope':'Actual isolated06aa app, native Python environment, two real idle SSE TCP connections. Instrumentation only observes the unchanged EngineService.shutdown and injects one actual Python SIGINT; no OS console-control delivery or active-worker cancellation claim.','cases':[]};write(out/'result.json',result)
for timeout in ['none','1','10']:
 case=out/('timeout-'+timeout);case.mkdir();proc=None;streams=[];created=None
 try:
  sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
  command=[str(ROOT/'.venv/Scripts/python.exe'),str(Path(__file__).resolve()),'--child',str(case),'--port',str(port),'--timeout',timeout]
  env=dict(os.environ,PYTHONPATH=str(SOURCE),OMA_EXECUTABLE_BUILD='oma-independent-checker/2:06aa865600b4ab2dc8f42f77b2cb5f82816dec99bbf8a1ff5f67673fb44c1949')
  with (case/'stdout.log').open('wb') as stdout,(case/'stderr.log').open('wb') as stderr:
   proc=subprocess.Popen(command,cwd=ROOT,env=env,stdout=stdout,stderr=stderr,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));created=psutil.Process(proc.pid).create_time()
   deadline=time.monotonic()+30
   while time.monotonic()<deadline:
    assert proc.poll() is None,'Server exited before health'
    try:
     conn=http.client.HTTPConnection('127.0.0.1',port,timeout=1);conn.request('GET','/api/health');resp=conn.getresponse();health=json.loads(resp.read());conn.close()
     if resp.status==200:break
    except (OSError,http.client.HTTPException):time.sleep(.05)
   else:raise AssertionError('Health deadline')
   assert health['server_identity']['checker_version']==env['OMA_EXECUTABLE_BUILD'] and health['server_identity']['source_changed'] is False
   assert Path(health['server_identity']['data_directory']).resolve()==case/'store'
   start=read(case/'child-start.json');before=snapshot(case/'store');write(case/'before.json',before)
   for index in range(2):
    conn=http.client.HTTPConnection('127.0.0.1',port,timeout=3);conn.request('GET',f'/api/projects/{start["project_id"]}/stream?after=999999999',headers={'Accept-Encoding':'identity'});resp=conn.getresponse();assert resp.status==200 and resp.getheader('Content-Type').startswith('text/event-stream');line=resp.readline();assert line==b': heartbeat\n';streams.append((conn,resp));write(case/f'sse-{index}.json',{'status':resp.status,'first_line':line.decode(),'content_type':resp.getheader('Content-Type')})
   conn=http.client.HTTPConnection('127.0.0.1',port,timeout=3);conn.request('POST','/__probe/first-sigint');resp=conn.getresponse();signal_response=json.loads(resp.read());conn.close();assert signal_response['active_workers']==0
   while not (case/'signal.json').exists():time.sleep(.01)
   if timeout=='none':
    time.sleep(2);assert proc.poll() is None and not (case/'cleanup-entered.json').exists(),'Unbounded control did not retain open SSE'
    for conn,resp in streams:resp.close();conn.close()
    streams=[]
   code=proc.wait(timeout=25);elapsed=time.perf_counter()-read(case/'signal.json')['time'];assert code==0
  cleanup=read(case/'cleanup-complete.json');assert cleanup['closing'] and cleanup['alive']==cleanup['threads']==0
  after=snapshot(case/'store');write(case/'after.json',after);assert after==before
  db=sqlite3.connect((case/'store/oma.sqlite3').as_uri()+'?mode=ro',uri=True);quick=db.execute('PRAGMA quick_check').fetchall();db.close();assert quick==[('ok',)]
  probe=socket.socket();probe.settimeout(1);closed=probe.connect_ex(('127.0.0.1',port))!=0;probe.close();assert closed
  logs=(case/'stderr.log').read_text()
  if timeout!='none':assert int(timeout)<=elapsed<int(timeout)+5 and 'timeout graceful shutdown exceeded' in logs
  else:assert elapsed>=2
  row={'status':'PASS','timeout_graceful_shutdown':None if timeout=='none' else int(timeout),'command':command,'environment':{'PYTHONPATH':env['PYTHONPATH'],'OMA_EXECUTABLE_BUILD':env['OMA_EXECUTABLE_BUILD']},'pid':proc.pid,'created':created,'server_pid':start['pid'],'returncode':code,'signal_to_closed_seconds':elapsed,'two_SSE_heartbeats_observed':True,'cleanup_complete':cleanup,'store_semantically_unchanged':True,'quick_check':'ok','port_released':closed}
  result['cases'].append(row);write(case/'result.json',row)
 except BaseException:
  result['status']='FAILED';result['traceback']=traceback.format_exc();write(out/'result.json',result);raise
 finally:
  for conn,resp in streams:resp.close();conn.close()
  if proc is not None and proc.poll() is None:
   tracked=psutil.Process(proc.pid);assert tracked.create_time()==created
   descendants=tracked.children(recursive=True)
   for child in reversed(descendants):
    try:child.terminate()
    except psutil.NoSuchProcess:pass
   proc.terminate();proc.wait(timeout=10)
 write(out/'result.json',result)
assert source_map=={p.relative_to(SOURCE).as_posix():sha(p) for p in SOURCE.rglob('*.py')}
result['status']='BOUNDED_SSE_DRAIN_AND_LIFESPAN_CLEANUP_PASS';result['source_unchanged']=True;write(out/'result.json',result)
print(json.dumps({'output':str(out),'status':result['status'],'times':[(r['timeout_graceful_shutdown'],r['signal_to_closed_seconds']) for r in result['cases']]}))
