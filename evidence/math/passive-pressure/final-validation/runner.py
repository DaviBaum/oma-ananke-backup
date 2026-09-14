"""Run the new kernel against immutable test and oracle fixture bytes."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET

STAGE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(STAGE/'src'))
from oma.build_identity import checker_version, frozen_environment


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    identity=uuid.uuid4().hex
    target=STAGE/'validation'/identity
    target.mkdir(parents=True,exist_ok=False)
    names=['tests/test_passive_pressure.py','tests/fixtures/passive-pressure/reference-results.json',
        'tests/fixtures/passive-pressure/coupled-loop-result.json']
    inputs={}
    for name in names:
        dst=target/name;dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(STAGE/name,dst);inputs[name]=sha(dst)
        assert inputs[name]==sha(STAGE/name)
    shutil.copyfile(Path(__file__),target/'runner.py')
    inputs['runner.py']=sha(target/'runner.py')
    env=frozen_environment(STAGE/'evidence/test-builds')
    command=[sys.executable,'-m','pytest','-o','pythonpath=', 'tests/test_passive_pressure.py','-q',
        '--junitxml='+str(target/'tests.xml')]
    started=time.perf_counter()
    run=subprocess.run(command,cwd=target,env=env,capture_output=True,text=True,encoding='utf-8',timeout=120)
    (target/'pytest.log').write_text(run.stdout+run.stderr,encoding='utf-8')
    print(run.stdout+run.stderr,flush=True)
    xml=ET.parse(target/'tests.xml').getroot();cases=xml.findall('.//testcase')
    assert run.returncode==0 and len(cases)==119
    assert not any(xml.findall('.//'+name) for name in ('failure','error','skipped'))
    assert len({(c.get('classname'),c.get('name')) for c in cases})==119
    assert all(sha(target/name)==value for name,value in inputs.items())
    assert all(sha(STAGE/name)==inputs[name] for name in names)
    assert checker_version()==env['OMA_EXECUTABLE_BUILD']
    result={'status':'PASS','build':env['OMA_EXECUTABLE_BUILD'],'tests':119,'failures':0,'skips':0,
        'seconds':time.perf_counter()-started,'test_and_fixture_hashes':inputs,'test_snapshot_unchanged':True,
        'source_unchanged':True,'module_sha256':sha(STAGE/'src/oma/optimization/passive_pressure.py'),
        'xml_sha256':sha(target/'tests.xml'),'validation_directory':target.relative_to(STAGE).as_posix(),
        'scope':'New exact model kernel and independent certificate tests only; no native adapter or whole-backend regression'}
    (target/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    (STAGE/'evidence/kernel-final-checkpoint.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result),flush=True)


if __name__=='__main__':main()
