"""Independently rehash the finished 5e8 package and its exact validation closure."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
import uuid

ROOT=next(p for p in Path(__file__).resolve().parents if (p/'AGENTS.md').exists())
PACKAGE=ROOT/'.release/native-build/portable-candidates/5e8fe9659cfd-82d3a00a6ff4'
EVIDENCE=ROOT/'evidence/dependencies/native-build/portable-candidates/5e8fe9659cfd-82d3a00a6ff4'
read=lambda p:json.loads(Path(p).read_text(encoding='utf8'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as stream:
        for chunk in iter(lambda:stream.read(4*1024*1024),b''):h.update(chunk)
    return h.hexdigest()
def main():
    sealed=EVIDENCE/'sealed-handoff.json';assert sealed.is_file(),'Seal is not complete'
    started=time.monotonic();out=EVIDENCE/'independent-seal'/uuid.uuid4().hex;out.mkdir(parents=True)
    shutil.copy2(__file__,out/'executed.py')
    scripts=out/'scripts';scripts.mkdir()
    for name in ('native_package_evidence.py','native_command_evidence.py','native_real_model_validation.py','native_prepare.py','native_build.py'):
        shutil.copy2(PACKAGE/'provenance/build-recipes'/name,scripts/name)
    sys.path.insert(0,str(scripts))
    from native_package_evidence import verify_suite_xml,verify_checkpoint_inputs,verify_real_model_receipt,REAL_MODEL_ROLES,PAYLOAD_DIRECTORIES,PAYLOAD_FILES
    from native_command_evidence import candidate_command_closure
    handoff=read(sealed);portable=read(EVIDENCE/'result.json');index=read(PACKAGE/'artifact-files.json')
    assert handoff['status']=='ISOLATED_NATIVE_PORTABLE_CANDIDATE_SEALED_NOT_PROMOTED'
    assert sha(EVIDENCE/'result.json')==handoff['validation_result_sha256']
    assert sha(PACKAGE/'artifact-files.json')==handoff['artifact_index_sha256']
    rows={r['path']:r for r in index['files']};assert len(rows)==len(index['files'])==handoff['file_count']
    inventory=[]
    for p in PACKAGE.rglob('*'):
        assert not p.is_symlink()
        if p.is_file() and p!=PACKAGE/'artifact-files.json':inventory.append(p.relative_to(PACKAGE).as_posix())
    assert set(rows)==set(inventory)
    def check(relative):
        p=PACKAGE/relative;before=p.stat();hashed=sha(p);after=p.stat()
        assert (before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns)
        assert rows[relative]['bytes']==after.st_size and rows[relative]['sha256']==hashed,relative
        return after.st_size
    total=0
    with ThreadPoolExecutor(max_workers=4) as pool:
        for number,size in enumerate(pool.map(check,sorted(rows)),1):
            total+=size
            if number%3000==0:print(json.dumps({'stage':'INDEPENDENT_HASH','files':number,'total':len(rows)}),flush=True)
    assert total==index['logical_bytes']==handoff['logical_bytes']
    payload=read(PACKAGE/'validated-payload.json')
    assert sha(PACKAGE/'validated-payload.json')==handoff['validated_payload_manifest_sha256']==portable['validated_payload_manifest_sha256']
    current_payload={name:{k:r[k] for k in ('bytes','sha256')} for name,r in rows.items() if name in PAYLOAD_FILES or name.split('/')[0] in PAYLOAD_DIRECTORIES}
    assert current_payload==payload['files']
    source={p.removeprefix('src/'):v['sha256'] for p,v in payload['files'].items() if p.startswith('src/') and p.endswith('.py')}
    assert source==portable['source_python_files'] and len(source)==107
    extension=Path(portable['identity']['extension']);assert extension.is_relative_to(PACKAGE)
    assert rows[extension.relative_to(PACKAGE).as_posix()]['sha256']==handoff['native_extension_sha256']==portable['identity']['extension_sha256']
    checkpoint,test_manifest=verify_checkpoint_inputs(PACKAGE,portable)
    full=read(EVIDENCE/'bundled-full-suite.json')
    assert sha(EVIDENCE/'bundled-full-suite.json')==handoff['bundled_full_suite_sha256']
    assert sha(EVIDENCE/'bundled-tests.xml')==handoff['bundled_test_xml_sha256']==full['test_xml_sha256']
    nodes=PACKAGE/'provenance/checkpoint-validation/selected-tests.args'
    assert sha(nodes)==full['test_node_manifest_sha256']==portable['application_test_validation']['test_node_manifest_sha256']
    accounting=verify_suite_xml(EVIDENCE/'bundled-tests.xml',nodes.read_text(encoding='utf8').splitlines())
    assert all(full[k]==v for k,v in accounting.items())
    assert accounting['passed']==2464 and len(accounting['skipped'])==3 and full['test_node_count']==2467
    assert full['test_source_manifest']==test_manifest
    assert full['checker_version']==handoff['checker_version']==portable['identity']['checker_version']
    assert full['source_checkpoint']==portable['source_checkpoint'] and full['portable_validation_result_sha256']==sha(EVIDENCE/'result.json')
    assert full['validated_payload_manifest_sha256']==portable['validated_payload_manifest_sha256']
    receipts={role:read(EVIDENCE/names[0]) for role,names in REAL_MODEL_ROLES.items()}
    scopes={role:verify_real_model_receipt(PACKAGE,portable,EVIDENCE/'result.json',role,r) for role,r in receipts.items()}
    assert scopes==handoff['real_model_scopes']
    closure=candidate_command_closure(PACKAGE,portable,checkpoint,full,receipts,workspace=ROOT,
        commands_root=ROOT/'evidence/dependencies/native-build/commands',validation_directory=EVIDENCE)
    assert closure==read(PACKAGE/'provenance/command-closure.json')
    assert sha(PACKAGE/'provenance/command-closure.json')==handoff['command_closure_sha256']
    for name,row in closure['commands'].items():
        for relative,expected in row['files'].items():
            assert rows['provenance/commands/'+name+'/'+relative]['sha256']==expected
    guard=read(EVIDENCE/'offline-guard-probe.json')
    assert sha(EVIDENCE/'offline-guard-probe.json')==handoff['offline_guard_sha256']
    assert guard['status']=='BUNDLED_AND_FROZEN_PYTHON_NETWORK_DENIAL_VERIFIED'
    assert len(guard['records'])==2 and {x['mode'] for x in guard['records']}=={'BUNDLED','FROZEN_CHECKER'}
    assert all(x['status']=='PYTHON_SOCKET_CONNECT_DENIED' and x['checker_version']==handoff['checker_version'] for x in guard['records'])
    assert guard['package_validation_sha256']==sha(EVIDENCE/'result.json')
    assert sha(PACKAGE/'artifact-files.json')==handoff['artifact_index_sha256']
    result={'status':'PASS','scope':'Finished local candidate byte index, payload identity, exact suite XML, command closure and three actual managed Office receipt/proof replays; no native rerun or promotion/redistribution claim',
        'package':str(PACKAGE),'checker_version':handoff['checker_version'],'source_checkpoint':portable['source_checkpoint'],
        'index_sha256':handoff['artifact_index_sha256'],'sealed_handoff_sha256':sha(sealed),'files':len(rows),'bytes':total,
        'app_source_files':len(source),'test_input_files':len(test_manifest['files']),'suite':accounting,'command_records':len(closure['commands']),
        'real_model_scopes':scopes,'guard_modes':['BUNDLED','FROZEN_CHECKER'],'elapsed_seconds':time.monotonic()-started,
        'executed_interpreter':sys.executable,'review_helpers':{p.name:sha(p) for p in scripts.glob('*.py')}}
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    (out/'README.md').write_text('Every indexed package file was independently rehashed and the complete file inventory matched. Executable payload, source/native identities, exact2467 XML cases (2464 PASS and3 named direct-interpreter N/A), copied checkpoint/test inventory, current command closure, two network guards and all three genuine Office receipts passed. No package bytes, application runtime or prior package were changed. This remains a local candidate with no promotion or redistribution claim.\n',encoding='utf8')
    print(json.dumps({'status':'PASS','audit':str(out),'files':len(rows),'bytes':total,'elapsed_seconds':result['elapsed_seconds']}))

if __name__=='__main__':main()
