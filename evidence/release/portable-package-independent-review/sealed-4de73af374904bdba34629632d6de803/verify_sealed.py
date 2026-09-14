from pathlib import Path
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib,json,sqlite3,time,xml.etree.ElementTree as ET,zlib
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).parent
E=ROOT/'evidence/dependencies/native-build/portable-candidates/43d9e1f20085-0334c44cd3ba'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
start=time.monotonic();result={'status':'RUNNING','scope':'Read-only independent integrity and evidence-accounting audit; no test rerun, runtime launch, promotion or public redistribution conclusion'}
def save(): (OUT/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
save()
try:
    hand=read(E/'sealed-handoff.json');p=Path(hand['package']).resolve();portable=read(E/'result.json')
    assert hand['status']=='ISOLATED_NATIVE_PORTABLE_CANDIDATE_SEALED_NOT_PROMOTED'
    assert p==Path(portable['package']).resolve() and p.is_relative_to((ROOT/'.release/native-build/portable-candidates').resolve())
    assert sha(E/'result.json')==hand['validation_result_sha256']
    assert sha(p/'artifact-files.json')==hand['artifact_index_sha256']
    index=read(p/'artifact-files.json');rows=index['files'];lookup={r['path']:r for r in rows}
    assert len(rows)==len(lookup)==index['file_count']==hand['file_count']==14378
    assert sum(r['bytes'] for r in rows)==index['logical_bytes']==hand['logical_bytes']==1976870039
    current={x.relative_to(p).as_posix() for x in p.rglob('*') if x.is_file()}
    assert current==set(lookup)|{'artifact-files.json'}
    def check(row):
        path=p/row['path'];assert path.resolve().is_relative_to(p) and not path.is_symlink()
        assert path.stat().st_size==row['bytes'] and sha(path)==row['sha256'],row['path']
    with ThreadPoolExecutor(max_workers=4) as pool:
        for i,_ in enumerate(pool.map(check,rows),1):
            if i%4000==0:print('Verified indexed files '+str(i),flush=True)
    payload=read(p/'validated-payload.json');assert sha(p/'validated-payload.json')==portable['validated_payload_manifest_sha256']==hand['validated_payload_manifest_sha256']
    dirs={'src','runtime','ui','wheelhouse','docs','scripts'};files={'OMA.cmd','Start-OMA.ps1','Install-OMA.ps1','README.md','requirements-runtime.lock'}
    actual_payload={name:{'sha256':r['sha256'],'bytes':r['bytes']} for name,r in lookup.items() if name.split('/')[0] in dirs or name in files}
    assert actual_payload==payload['files']
    source={n[4:]:r['sha256'] for n,r in actual_payload.items() if n.startswith('src/') and n.endswith('.py')}
    assert source==portable['source_python_files']
    pinned=ROOT/'.oma/runtimes'/portable['source_checkpoint']/'src'
    assert source=={x.relative_to(pinned).as_posix():sha(x) for x in pinned.rglob('*.py')}
    ext=Path(portable['identity']['extension']).resolve();assert ext.is_relative_to(p)
    assert sha(ext)==payload['files'][ext.relative_to(p).as_posix()]['sha256']==portable['identity']['extension_sha256']==hand['native_extension_sha256']=='398b43db6952d07645d4fbea2c23c73cb83696369871e22880b85a8c35bfd875'
    suite=read(E/'bundled-full-suite.json');assert sha(E/'bundled-full-suite.json')==hand['bundled_full_suite_sha256']
    assert suite['status']=='BUNDLED_EXACT_FROZEN_FULL_SUITE_PASS_WITH_DECLARED_DIRECT_INTERPRETER_NOT_APPLICABLE'
    assert Path(suite['package']).resolve()==p and suite['portable_validation_result_sha256']==sha(E/'result.json')
    assert suite['validated_payload_manifest_sha256']==hand['validated_payload_manifest_sha256']
    assert suite['checker_version']==hand['checker_version']==portable['identity']['checker_version']==payload['checker_version']
    nodes_path=p/'provenance/checkpoint-validation/selected-tests.args';nodes=nodes_path.read_text().splitlines();assert len(nodes)==len(set(nodes))==1490
    assert sha(nodes_path)==suite['test_node_manifest_sha256']==portable['application_test_validation']['test_node_manifest_sha256']
    expected=[]
    for node in nodes:
        a=node.split('::');expected.append((a[0][:-3].replace('/','.').replace('\\','.')+(''.join('.'+v for v in a[1:-1])),a[-1]))
    xml_path=E/'bundled-tests.xml';assert sha(xml_path)==suite['test_xml_sha256']==hand['bundled_test_xml_sha256']
    xml=ET.parse(xml_path).getroot();cases=xml.findall('.//testcase');assert Counter((c.attrib.get('classname'),c.attrib['name']) for c in cases)==Counter(expected)
    assert not xml.findall('.//failure') and not xml.findall('.//error')
    skipped=[{'classname':c.attrib['classname'],'name':c.attrib['name'],'reason':c.find('skipped').attrib.get('message')} for c in cases if c.find('skipped') is not None]
    wanted={('tests.test_windows_job_containment','test_private_bridge_corruption_is_not_reused['+v+']','Current Python is a direct interpreter and needs no bridge') for v in ('binary','configuration','extra_startup')}
    assert len(skipped)==3 and {(x['classname'],x['name'],x['reason']) for x in skipped}==wanted
    assert skipped==suite['skipped']==hand['bundled_not_applicable'] and suite['passed']==hand['bundled_passed']==1487
    assert len(cases)==1490 and suite['failed']==0
    recovered=suite['recovery'];assert recovered['tests_rerun'] is False and sha(recovered['original_xml'])==sha(xml_path)==recovered['original_xml_sha256']
    for key in ('suite','collection'):
        recpath=Path(suite[key+'_record']);rec=read(recpath);assert rec['status']=='PASS' and rec['exit_code']==0
        assert sha(recpath)==recovered[key+'_record_sha256'] and sha(recpath.parent/'output.log')==rec['log_sha256']
        assert Path(rec['command'][0]).resolve()==p/'runtime/python.exe'
    frozen_tests=Path(suite['directory'])/'test-suite';decl=suite['test_source_manifest']['files']
    assert len(decl)==97 and all(sha(frozen_tests/name)==value for name,value in decl.items())
    assert all(sha(p/'provenance/checkpoint-test-sources'/name)==value for name,value in decl.items())
    guards=read(E/'offline-guard-probe.json');assert sha(E/'offline-guard-probe.json')==hand['offline_guard_sha256']
    assert guards['package_validation_sha256']==sha(E/'result.json') and len(guards['records'])==2
    assert {r['mode'] for r in guards['records']}=={'BUNDLED','FROZEN_CHECKER'}
    for row in guards['records']:
        assert row['status']=='PYTHON_SOCKET_CONNECT_DENIED' and row['checker_version']==hand['checker_version']
        assert Path(row['guard']).resolve().is_relative_to(p) and sha(row['guard'])==row['guard_sha256']
    actual=read(E/'real-office-validation.json');assert sha(E/'real-office-validation.json')==hand['real_office_validation_sha256']
    assert actual['status']=='REAL_EXPORTED_OFFICE_RECHECK_PASS' and actual['checker_version']==hand['checker_version']
    execution=actual['execution'];report=actual['report'];store=Path(actual['isolated_store'])
    assert execution['status']=='COMPLETED' and execution['report_published'] is True and execution['report_root']==actual['report_root']==digest(report)
    assert report['status']=='PASS' and report['candidate_root']==actual['candidate_root'] and report['checker_version']==hand['checker_version']
    assert execution['supervision']['status']=='COMPLETED' and execution['supervision']['returncode']==0
    containment=execution['supervision']['containment'];assert containment['assigned_before_resume'] is True and containment['active_processes']==0
    assert execution['supervision']['interpreter']['method']=='DIRECT_LOADED_PYTHON_IMAGE'
    assert sha(p/'runtime/python.exe')==execution['supervision']['interpreter']['sha256']
    def blob(h):
        path=store/'blobs'/(h+'.json.z');value=json.loads(zlib.decompress(path.read_bytes()));assert digest(value)==h;return value
    assert blob(actual['report_root'])==report
    db=sqlite3.connect((store/'oma.sqlite3').resolve().as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
    candidate=dict(db.execute('SELECT * FROM candidates WHERE id=?',(actual['candidate_id'],)).fetchone());managed=dict(db.execute('SELECT * FROM check_executions WHERE execution_id=?',(execution['execution_id'],)).fetchone());db.close()
    assert candidate['status']=='CHECKED' and candidate['report_root']==actual['report_root'] and managed['status']=='COMPLETED'
    checks={c['id']:c for c in report['results']};budget=checks['joint-new-fitting-budget']['witness']
    assert checks['joint-new-fitting-budget']['status']=='PASS' and budget['count']==budget['declared_budget']==2 and budget['count_complete'] is True
    assert sum(budget['per_new_route'].values())==2
    assert sum(part['units'] for parts in budget['actual_parts'].values() for part in parts)==2
    native=[]
    for route,ref in budget['native_artifact_roots'].items():
        body=blob(ref);assert body['coordination_status']=='PASS' and body['self_interference_status']=='PASS'
        assert body['obstacle_count']==803 and body['pairs_accounted']==body['route_count']*803
        native.append({'route_id':route,'route_parts':body['route_count'],'source_obstacles':body['obstacle_count'],'pairs':body['pairs_accounted'],'artifact':ref})
    assert sorted(x['route_parts'] for x in native)==[1,5]
    assert checks['cross-route-interference']['status']=='PASS' and checks['cross-route-interference']['witness']['pairs_accounted']==5
    for path,value in actual['source_and_exported_files'].items():assert sha(path)==value
    assert actual['original_bytes_and_head_unchanged'] and actual['same_objective_and_obligation_dispositions']
    result.update(status='INDEPENDENT_SEALED_PORTABLE_EVIDENCE_PASS',package=str(p),artifact_index_sha256=sha(p/'artifact-files.json'),indexed_files=len(rows),logical_bytes=index['logical_bytes'],validated_payload_files=len(payload['files']),source_python_files=len(source),source_checkpoint=portable['source_checkpoint'],checker_version=hand['checker_version'],native_extension_sha256=sha(ext),bundled_test_cases=len(cases),passed=1487,not_applicable=skipped,test_source_files=len(decl),xml_sha256=sha(xml_path),recovered_suite_xml=True,tests_rerun=False,guard_modes=sorted(r['mode'] for r in guards['records']),real_candidate_id=actual['candidate_id'],real_report_root=actual['report_root'],real_native_denominators=native,real_new_fittings=2,real_cross_route_pairs=5,managed_kernel_job_completed=True,public_redistribution='NOT_CLEARED')
except BaseException as exc:
    result.update(status='INCOMPLETE_OR_FAILED',error=repr(exc));raise
finally:
    result.update(seconds=time.monotonic()-start,auditor_script_sha256=sha(Path(__file__)));save();print(json.dumps({k:v for k,v in result.items() if k not in ('not_applicable','real_native_denominators')}),flush=True)
