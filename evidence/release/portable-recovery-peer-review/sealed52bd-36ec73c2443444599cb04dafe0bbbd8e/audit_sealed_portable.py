"""Independently rehash a completed immutable local candidate file index."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil
import time
import uuid

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').is_file())
BASE=ROOT/'evidence/dependencies/native-build/portable-candidates/52bd5d292171-2563efa50156'
PRIOR=ROOT/'evidence/release/portable-recovery-peer-review/actual-81970589751c46d1ad87703559e64979'
def sha(p):
    with Path(p).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,x):p.write_text(json.dumps(x,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')

def main():
    start=time.perf_counter();handoff=read(BASE/'sealed-handoff.json');portable=read(BASE/'result.json')
    package=Path(handoff['package']).resolve();indexpath=package/'artifact-files.json';index=read(indexpath)
    assert handoff['status']=='ISOLATED_NATIVE_PORTABLE_CANDIDATE_SEALED_NOT_PROMOTED'
    assert sha(BASE/'result.json')==handoff['validation_result_sha256']
    assert handoff['checker_version']==portable['identity']['checker_version']
    assert handoff['native_extension_sha256']==portable['identity']['extension_sha256']
    assert sha(indexpath)==handoff['artifact_index_sha256']
    assert index['status']=='COMPLETE_LOCAL_CANDIDATE_FILE_INDEX' and index['exclusions']==['artifact-files.json itself']
    rows=index['files'];expected={r['path']:r for r in rows}
    assert len(rows)==len(expected)==index['file_count']==handoff['file_count']
    assert sum(r['bytes'] for r in rows)==index['logical_bytes']==handoff['logical_bytes']
    actual={}
    for p in package.rglob('*'):
        assert not p.is_symlink()
        if p.is_file() and p!=indexpath:
            assert p.resolve().is_relative_to(package)
            actual[p.relative_to(package).as_posix()]=p
    assert set(actual)==set(expected)
    def check(name):
        path=actual[name];before=path.stat();h=sha(path);after=path.stat();row=expected[name]
        assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
        assert h==row['sha256'] and after.st_size==row['bytes'],name
        return 1
    with ThreadPoolExecutor(max_workers=4) as pool:assert sum(pool.map(check,sorted(actual)))==len(rows)
    payload=read(package/'validated-payload.json')
    assert sha(package/'validated-payload.json')==handoff['validated_payload_manifest_sha256']==portable['validated_payload_manifest_sha256']
    assert all(expected[name]['sha256']==row['sha256'] and expected[name]['bytes']==row['bytes'] for name,row in payload['files'].items())
    assert {name.removeprefix('src/'):row['sha256'] for name,row in payload['files'].items() if name.startswith('src/') and name.endswith('.py')}==portable['source_python_files']
    extension=Path(portable['identity']['extension']).resolve();assert extension.is_relative_to(package)
    assert expected[extension.relative_to(package).as_posix()]['sha256']==handoff['native_extension_sha256']
    full=read(BASE/'bundled-full-suite.json');old=read(PRIOR/'result.json')
    observed={row['path']:row['sha256'] for row in old['reviewed_artifacts']}
    assert sha(BASE/'bundled-full-suite.json')==observed[str(BASE/'bundled-full-suite.json')]==handoff['bundled_full_suite_sha256']
    assert sha(BASE/'bundled-tests.xml')==handoff['bundled_test_xml_sha256']==full['test_xml_sha256']
    assert full['passed']==handoff['bundled_passed']==1976 and full['skipped']==handoff['bundled_not_applicable'] and len(full['skipped'])==3
    closure=package/'provenance/command-closure.json'
    assert sha(closure)==handoff['command_closure_sha256'] and read(closure)==read(PRIOR/'command-closure.json')
    assert sha(package/'provenance/bundled-tests.xml')==sha(BASE/'bundled-tests.xml')
    assert sha(package/'provenance/bundled-full-suite.json')==sha(BASE/'bundled-full-suite.json')
    guard=read(BASE/'offline-guard-probe.json');assert sha(BASE/'offline-guard-probe.json')==handoff['offline_guard_sha256']
    assert len(guard['records'])==2 and {r['mode'] for r in guard['records']}=={'BUNDLED','FROZEN_CHECKER'}
    assert all(r['status']=='PYTHON_SOCKET_CONNECT_DENIED' and r['checker_version']==handoff['checker_version'] for r in guard['records'])
    for filename,key in [('real-office-validation.json','real_office_validation_sha256'),('real-office-pressure-validation.json','real_office_pressure_validation_sha256')]:
        assert sha(BASE/filename)==handoff[key]==sha(package/'provenance'/filename)
    assert handoff['real_model_scopes']['joint_fitting_budget']['source_pairs']==4818
    assert handoff['real_model_scopes']['joint_fitting_budget']['cross_route_pairs']==5
    assert handoff['real_model_scopes']['pressure_network']['source_pairs']==3212
    assert handoff['active_runtime_modified'] is False and handoff['previous_portable_preview_modified'] is False
    assert sha(indexpath)==handoff['artifact_index_sha256']
    out=ROOT/'evidence/release/portable-recovery-peer-review'/('sealed52bd-'+uuid.uuid4().hex);out.mkdir(parents=True)
    result={'status':'INDEPENDENT_SEALED_LOCAL_CANDIDATE_FILE_INDEX_AUDIT_PASS','package':str(package),
        'source_checkpoint':portable['source_checkpoint'],'checker_version':handoff['checker_version'],
        'file_count':len(rows),'logical_bytes':index['logical_bytes'],'index_sha256':sha(indexpath),
        'handoff_sha256':sha(BASE/'sealed-handoff.json'),'source_python_files':len(portable['source_python_files']),
        'native_extension_sha256':handoff['native_extension_sha256'],'payload_files':len(payload['files']),
        'bundled_suite_accounting':{'nodes':1979,'passed':1976,'named_not_applicable':full['skipped']},
        'prior_recovery_and_command_audit_sha256':sha(PRIOR/'result.json'),'command_closure_sha256':sha(closure),
        'raw_running_and_monitor_gap_retained':True,'native_scopes':handoff['real_model_scopes'],
        'offline_guard_modes':['BUNDLED','FROZEN_CHECKER'],'package_written':False,'native_tests_rerun':False,
        'promotion_claim':False,'public_redistribution':'NOT_CLEARED','seconds':time.perf_counter()-start}
    write(out/'result.json',result)
    for path in (BASE/'sealed-handoff.json',indexpath,Path(__file__)):
        shutil.copyfile(path,out/path.name)
    (out/'README.md').write_text('Every indexed file in the completed local 52bd candidate was independently rehashed, and the exact actual file set matches its sealed index without extra or missing members. Source/native identities, tested payload, exact recovered bundled accounting, two offline guard modes and two distinct real Office receipts match the previously reviewed evidence. The command closure and original interrupted wrapper are retained, with the monitoring gap explicit. This audit wrote no package bytes, ran no native tests, promoted no runtime, and does not clear public redistribution or broader application engineering coverage.\n',encoding='utf-8')
    print(json.dumps({'directory':str(out),'result_sha256':sha(out/'result.json'),'files':len(rows),'seconds':result['seconds']}))

if __name__=='__main__':main()
