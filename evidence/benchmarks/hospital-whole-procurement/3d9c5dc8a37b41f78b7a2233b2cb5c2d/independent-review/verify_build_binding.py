"""Recompute completed campaign software bindings with standard library only."""
from pathlib import Path
import hashlib
import importlib.metadata
import json
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
STAGE=HERE.parent
identities={
    'split':'2f25fd1064cb4547ae3667b9bbd4e69b',
    'no-split':'3d9c5dc8a37b41f78b7a2233b2cb5c2d',
}
packages={d.metadata['Name'].lower().replace('_','-'):d.version
          for d in importlib.metadata.distributions(path=[str(ROOT/'.venv/Lib/site-packages')])}
versions={p:packages.get(p,'absent') for p in ('ifcopenshell','cadquery-ocp','numpy','scipy','pydantic','cupy-cuda12x')}
results=[]
for name,ident in identities.items():
    directory=STAGE/'campaigns'/ident
    declaration=json.loads((directory/'predeclaration.json').read_text())
    result=json.loads((directory/'result.json').read_text())
    packet=json.loads((directory/'report.json').read_text())
    replay=json.loads((HERE/('replay-'+name+'.json')).read_text())
    source=Path(declaration['source_path'])/'oma'
    observed={p.relative_to(source.parent).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(source.rglob('*.py'))}
    assert observed and observed==declaration['application_sources']
    fingerprint=hashlib.sha256(sys.version.encode())
    for path in sorted(source.rglob('*.py')):
        fingerprint.update(path.relative_to(source).as_posix().encode())
        fingerprint.update(b'\0')
        fingerprint.update(path.read_bytes())
        fingerprint.update(b'\0')
    for package,version in versions.items():
        fingerprint.update(f'{package}={version}\0'.encode())
    version='oma-independent-checker/2:'+fingerprint.hexdigest()
    assert version==declaration['checker_version']==result['execution']['checker_version']==packet['checker_version']
    assert version=='oma-independent-checker/2:1ccc8728fbf6ba0ad1bbb16b2dd339896e8bb292b03e08754e3b1b93156b48c6'
    assert replay['status']=='PASS' and replay['summary']['source_count']==7
    assert replay['packet_root']==result['packet_root'] and replay['plan_root']==result['purchasing_plan_root']
    results.append({'scenario':name,'status':'PASS','checker_version':version,'source_file_count':len(observed),
        'replay_sha256':hashlib.sha256((HERE/('replay-'+name+'.json')).read_bytes()).hexdigest(),
        'predeclaration_sha256':hashlib.sha256((directory/'predeclaration.json').read_bytes()).hexdigest(),
        'packet_root':replay['packet_root'],'plan_root':replay['plan_root']})
out={'status':'PASS','scope':'FROZEN_SOURCE_BYTES_AND_SOFTWARE_IDENTITY','producer_modules_imported':False,
     'python_version':sys.version,'package_versions':versions,'campaigns':results,
     'verifier_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
(HERE/'build-binding.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out))
