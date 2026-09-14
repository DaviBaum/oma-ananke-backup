from pathlib import Path
from copy import deepcopy
import sys,json
root=Path(__file__).resolve().parents[4];sys.path.insert(0,str(root/'scripts'))
from native_package_evidence import payload_files,verify_payload,PAYLOAD_DIRECTORIES,PAYLOAD_FILES
from native_prepare import sha
package=Path(__file__).with_name('synthetic-payload');package.mkdir()
for name in PAYLOAD_DIRECTORIES:(package/name).mkdir()
for name in PAYLOAD_FILES:(package/name).write_bytes(b'SYNTHETIC VALIDATOR FIXTURE - NOT EXECUTABLE')
source=package/'src/oma';source.mkdir();(source/'__init__.py').write_text('# synthetic validator fixture')
ext=package/'runtime/synthetic-extension.pyd';ext.write_bytes(b'not a native executable')
portable={'identity':{'checker_version':'synthetic-checker','extension':str(ext.resolve()),'extension_sha256':sha(ext)},'source_checkpoint':'a'*64,'source_python_files':{'oma/__init__.py':sha(source/'__init__.py')}}
manifest={'checker_version':'synthetic-checker','source_checkpoint':'a'*64,'files':payload_files(package)}
path=package/'validated-payload.json';path.write_text(json.dumps(manifest));portable['validated_payload_manifest_sha256']=sha(path)
verify_payload(package,portable)
rows=[]
def must_reject(name,p=portable):
    try:verify_payload(package,p)
    except AssertionError:rows.append({'mutation':name,'status':'REJECTED'})
    else:raise AssertionError(name+' accepted')
raw=ext.read_bytes();ext.write_bytes(raw+b'changed');must_reject('changed_native_bytes');ext.write_bytes(raw)
extra=source/'unvalidated.py';extra.write_text('# added');must_reject('additional_source_file');extra.unlink()
old=(source/'__init__.py').read_bytes();(source/'__init__.py').write_bytes(old+b'changed');must_reject('changed_source_bytes');(source/'__init__.py').write_bytes(old)
bad=deepcopy(portable);bad['identity']['extension_sha256']='b'*64;must_reject('native_identity_disagrees_with_payload',bad)
bad=deepcopy(portable);bad['source_python_files']['oma/__init__.py']='c'*64;must_reject('source_identity_disagrees_with_payload',bad)
verify_payload(package,portable)
result={'status':'PAYLOAD_VALIDATOR_HELPER_REVIEW_PASS','helper_sha256':sha(root/'scripts/native_package_evidence.py'),'rejected_mutations':rows,'scope':'Synthetic byte inventory only; no native code or packaged runtime executed'}
Path(__file__).with_name('payload-validator-result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
